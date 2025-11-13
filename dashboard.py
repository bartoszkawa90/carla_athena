"""
Real-time Dashboard for CARLA Multi-Server Manager
Displays server status, health checks, and system resources in real-time
Uses lsof to check port status
"""
from flask import Flask, render_template, Response, jsonify
import json
import os
import sys
from pathlib import Path
from datetime import datetime
import time
import psutil
import subprocess
from typing import Set

app = Flask(__name__)

# Get configuration from environment
LOG_DIR = os.environ.get('CARLA_LOG_DIR', 'server_logs/latest')
NUM_SERVERS = int(os.environ.get('CARLA_NUM_SERVERS', 4))
START_PORT = int(os.environ.get('CARLA_START_PORT', 2000))

# Shared status file for inter-process communication
STATUS_FILE = Path(LOG_DIR) / 'dashboard_status.json'


def get_listening_ports_lsof() -> Set[int]:
    """
    Get all TCP ports that are currently in LISTEN state using lsof.
    Returns a set of port numbers.
    """
    try:
        result = subprocess.run(
            ['lsof', '-nP', '-iTCP', '-sTCP:LISTEN'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        listening_ports = set()
        
        # Parse lsof output
        for line in result.stdout.split('\n')[1:]:  # Skip header
            if line.strip():
                parts = line.split()
                if len(parts) >= 9:
                    port_info = parts[8]
                    if ':' in port_info:
                        port_str = port_info.split(':')[-1]
                        try:
                            port_num = int(port_str)
                            listening_ports.add(port_num)
                        except ValueError:
                            pass
        
        return listening_ports
    
    except Exception:
        return set()


def get_server_status():
    """Read server status from the parent process."""
    try:
        # Try to read from shared file first
        if STATUS_FILE.exists():
            with open(STATUS_FILE, 'r') as f:
                data = json.load(f)
                # Verify status with lsof
                listening_ports = get_listening_ports_lsof()
                for server in data.get('servers', []):
                    port = server.get('port')
                    if port and port in listening_ports:
                        # If lsof shows port is listening, ensure status is correct
                        if server.get('health_status') == 'DOWN':
                            server['health_status'] = 'HEALTHY'
                        if server.get('process_status') == 'EXITED':
                            server['process_status'] = 'RUNNING'
                return data
    except Exception:
        pass
    
    # Fallback: construct status from lsof
    listening_ports = get_listening_ports_lsof()
    servers = []
    for idx in range(NUM_SERVERS):
        port = START_PORT + (idx * 100)
        is_listening = port in listening_ports
        
        servers.append({
            'index': idx,
            'port': port,
            'process_status': 'RUNNING' if is_listening else 'UNKNOWN',
            'health_status': 'HEALTHY' if is_listening else 'UNKNOWN',
            'last_health_check': datetime.now().strftime("%Y-%m-%d %H:%M:%S") if is_listening else None,
            'restart_count': 0,
            'uptime_start': None,
            'last_error': None if is_listening else 'Status file not available',
            'pid': None,
            'memory_mb': 0,
            'cpu_percent': 0
        })
    
    return {'servers': servers, 'timestamp': datetime.now().isoformat()}


def get_system_metrics():
    """Get current system metrics."""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        
        # GPU info
        gpu_info = []
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu',
                 '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                timeout=5
            )
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 6:
                        gpu_info.append({
                            'index': int(parts[0]),
                            'name': parts[1],
                            'utilization': float(parts[2]),
                            'memory_used': float(parts[3]),
                            'memory_total': float(parts[4]),
                            'temperature': float(parts[5])
                        })
        except Exception:
            pass
        
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': mem.percent,
            'memory_used_gb': round(mem.used / (1024**3), 2),
            'memory_total_gb': round(mem.total / (1024**3), 2),
            'gpus': gpu_info,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        return {'error': str(e)}


def get_port_info():
    """Get detailed port information from lsof."""
    try:
        result = subprocess.run(
            ['lsof', '-nP', '-iTCP', '-sTCP:LISTEN'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        port_info = {}
        for line in result.stdout.split('\n')[1:]:
            if line.strip():
                parts = line.split()
                if len(parts) >= 9:
                    port_str_full = parts[8]
                    if ':' in port_str_full:
                        port_str = port_str_full.split(':')[-1]
                        try:
                            port_num = int(port_str)
                            port_info[port_num] = {
                                'command': parts[0],
                                'pid': parts[1],
                                'user': parts[2]
                            }
                        except ValueError:
                            pass
        
        return port_info
    except Exception:
        return {}


def read_log_tail(log_file, lines=50):
    """Read last N lines from a log file."""
    try:
        log_path = Path(LOG_DIR) / log_file
        if not log_path.exists():
            return []
        
        with open(log_path, 'r') as f:
            return f.readlines()[-lines:]
    except Exception:
        return []


@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('dashboard.html', 
                         num_servers=NUM_SERVERS,
                         start_port=START_PORT,
                         log_dir=LOG_DIR)


@app.route('/api/status')
def api_status():
    """API endpoint for server status."""
    status = get_server_status()
    metrics = get_system_metrics()
    port_info = get_port_info()
    
    # Add port info to servers
    for server in status.get('servers', []):
        port = server.get('port')
        if port and port in port_info:
            server['port_info'] = port_info[port]
    
    return jsonify({
        'servers': status.get('servers', []),
        'system': metrics,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/logs/<log_type>')
def api_logs(log_type):
    """API endpoint for log files."""
    valid_logs = ['servers', 'health', 'ports', 'psutil', 'gpu']
    
    if log_type not in valid_logs:
        return jsonify({'error': 'Invalid log type'}), 400
    
    lines = read_log_tail(f'{log_type}.log', lines=100)
    return jsonify({'logs': lines})


@app.route('/stream')
def stream():
    """Server-Sent Events stream for real-time updates."""
    def event_stream():
        while True:
            try:
                status = get_server_status()
                metrics = get_system_metrics()
                port_info = get_port_info()
                
                # Add port info to servers
                for server in status.get('servers', []):
                    port = server.get('port')
                    if port and port in port_info:
                        server['port_info'] = port_info[port]
                
                data = {
                    'servers': status.get('servers', []),
                    'system': metrics,
                    'timestamp': datetime.now().isoformat()
                }
                
                yield f"data: {json.dumps(data)}\n\n"
                time.sleep(2)  # Update every 2 seconds
            except GeneratorExit:
                break
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                time.sleep(5)
    
    return Response(event_stream(), mimetype='text/event-stream')


# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CARLA Multi-Server Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
        }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
        }
        
        header {
            background: white;
            padding: 20px 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        
        h1 {
            color: #667eea;
            font-size: 2em;
            margin-bottom: 10px;
        }
        
        .header-info {
            color: #666;
            font-size: 0.9em;
        }
        
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: bold;
            background: #28a745;
            color: white;
            margin-left: 10px;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .card h2 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.3em;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        
        .server-item {
            background: #f8f9fa;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 8px;
            border-left: 4px solid #ddd;
            transition: all 0.3s ease;
        }
        
        .server-item:hover {
            transform: translateX(5px);
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .server-item.healthy {
            border-left-color: #28a745;
        }
        
        .server-item.starting {
            border-left-color: #ffc107;
        }
        
        .server-item.unhealthy {
            border-left-color: #dc3545;
        }
        
        .server-item.unknown {
            border-left-color: #6c757d;
        }
        
        .server-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .server-title {
            font-weight: bold;
            font-size: 1.1em;
        }
        
        .status-badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: bold;
        }
        
        .status-healthy {
            background: #28a745;
            color: white;
        }
        
        .status-starting {
            background: #ffc107;
            color: #333;
        }
        
        .status-unhealthy {
            background: #dc3545;
            color: white;
        }
        
        .status-unknown {
            background: #6c757d;
            color: white;
        }
        
        .server-details {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            font-size: 0.9em;
            color: #666;
        }
        
        .metric {
            background: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 10px;
        }
        
        .metric-label {
            font-size: 0.85em;
            color: #666;
            margin-bottom: 5px;
        }
        
        .metric-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #667eea;
        }
        
        .progress-bar {
            width: 100%;
            height: 20px;
            background: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
            margin-top: 5px;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transition: width 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 0.75em;
            font-weight: bold;
        }
        
        .gpu-card {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
            border-left: 4px solid #667eea;
        }
        
        .gpu-header {
            font-weight: bold;
            margin-bottom: 10px;
            color: #667eea;
            font-size: 1.05em;
        }
        
        .gpu-metrics {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 10px;
        }
        
        .gpu-metric {
            font-size: 0.9em;
        }
        
        .gpu-metric-label {
            color: #666;
            font-size: 0.85em;
            margin-bottom: 5px;
        }
        
        .gpu-metric-value {
            font-weight: bold;
            color: #333;
        }
        
        .logs-container {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 15px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            max-height: 400px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        
        .log-line {
            margin-bottom: 5px;
            padding: 2px 0;
        }
        
        .timestamp {
            color: #858585;
            font-size: 0.85em;
        }
        
        .error-message {
            color: #ff6b6b;
            font-size: 0.9em;
            margin-top: 5px;
        }
        
        .port-info {
            font-size: 0.85em;
            color: #28a745;
            margin-top: 5px;
            font-style: italic;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .loading {
            animation: pulse 2s infinite;
        }
        
        .wide-card {
            grid-column: 1 / -1;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚗 CARLA Multi-Server Dashboard
                <span class="badge">lsof monitoring</span>
            </h1>
            <div class="header-info">
                <span>Log Directory: <strong id="log-dir">{{ log_dir }}</strong></span> | 
                <span>Last Update: <strong id="last-update">Loading...</strong></span>
            </div>
        </header>
        
        <div class="grid">
            <!-- System Metrics -->
            <div class="card">
                <h2>📊 System Resources</h2>
                <div class="metric">
                    <div class="metric-label">CPU Usage</div>
                    <div class="metric-value" id="cpu-usage">--%</div>
                    <div class="progress-bar">
                        <div class="progress-fill" id="cpu-progress" style="width: 0%"></div>
                    </div>
                </div>
                <div class="metric">
                    <div class="metric-label">Memory Usage</div>
                    <div class="metric-value" id="memory-usage">-- / -- GB</div>
                    <div class="progress-bar">
                        <div class="progress-fill" id="memory-progress" style="width: 0%"></div>
                    </div>
                </div>
            </div>
            
            <!-- Server Overview -->
            <div class="card">
                <h2>🖥️ Server Overview</h2>
                <div class="metric">
                    <div class="metric-label">Active Servers</div>
                    <div class="metric-value" id="active-servers">0 / {{ num_servers }}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Healthy Servers</div>
                    <div class="metric-value" id="healthy-servers">0 / {{ num_servers }}</div>
                </div>
            </div>
        </div>
        
        <!-- GPU Info -->
        <div class="card wide-card">
            <h2>🎮 GPU Status (Real-time)</h2>
            <div id="gpu-container" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px;">
                <p class="loading">Loading GPU information...</p>
            </div>
        </div>
        
        <!-- Servers -->
        <div class="card wide-card">
            <h2>🔌 Server Status</h2>
            <div id="servers-container" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 15px;">
                <p class="loading">Loading server status...</p>
            </div>
        </div>
        
        <!-- Logs -->
        <div class="card wide-card">
            <h2>📝 Recent Logs</h2>
            <div style="margin-bottom: 15px;">
                <label for="log-select" style="font-weight: bold; margin-right: 10px;">Select Log:</label>
                <select id="log-select" style="padding: 8px 12px; border-radius: 5px; border: 1px solid #ddd; font-size: 0.9em; cursor: pointer;">
                    <option value="health">Health Check</option>
                    <option value="servers">Servers</option>
                    <option value="ports">Ports</option>
                    <option value="psutil">System Resources</option>
                    <option value="gpu">GPU</option>
                </select>
            </div>
            <div class="logs-container" id="logs-container">
                <p class="loading">Loading logs...</p>
            </div>
        </div>
    </div>
    
    <script>
        // Connect to SSE stream
        const eventSource = new EventSource('/stream');
        
        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                updateDashboard(data);
            } catch (e) {
                console.error('Error parsing SSE data:', e);
            }
        };
        
        eventSource.onerror = function(error) {
            console.error('SSE Error:', error);
        };
        
        function updateDashboard(data) {
            // Update timestamp
            const timestamp = new Date(data.timestamp).toLocaleString();
            document.getElementById('last-update').textContent = timestamp;
            
            // Update system metrics
            if (data.system) {
                const cpu = data.system.cpu_percent || 0;
                document.getElementById('cpu-usage').textContent = cpu.toFixed(1) + '%';
                const cpuProgress = document.getElementById('cpu-progress');
                cpuProgress.style.width = cpu + '%';
                cpuProgress.textContent = cpu.toFixed(1) + '%';
                
                const memUsed = data.system.memory_used_gb || 0;
                const memTotal = data.system.memory_total_gb || 0;
                const memPercent = data.system.memory_percent || 0;
                document.getElementById('memory-usage').textContent = 
                    `${memUsed.toFixed(2)} / ${memTotal.toFixed(2)} GB`;
                const memProgress = document.getElementById('memory-progress');
                memProgress.style.width = memPercent + '%';
                memProgress.textContent = memPercent.toFixed(1) + '%';
                
                // Update GPU info
                updateGPUs(data.system.gpus || []);
            }
            
            // Update servers
            if (data.servers) {
                updateServers(data.servers);
            }
        }
        
        function updateGPUs(gpus) {
            const container = document.getElementById('gpu-container');
            
            if (gpus.length === 0) {
                container.innerHTML = '<p>No GPU information available</p>';
                return;
            }
            
            container.innerHTML = gpus.map(gpu => {
                const util = gpu.utilization || 0;
                const memPercent = gpu.memory_total > 0 ? 
                    (gpu.memory_used / gpu.memory_total * 100) : 0;
                
                return `
                    <div class="gpu-card">
                        <div class="gpu-header">GPU ${gpu.index}: ${gpu.name || 'Unknown'}</div>
                        
                        <div class="gpu-metrics">
                            <div class="gpu-metric">
                                <div class="gpu-metric-label">Utilization</div>
                                <div class="progress-bar" style="margin-top: 5px;">
                                    <div class="progress-fill" style="width: ${util}%">${util.toFixed(0)}%</div>
                                </div>
                            </div>
                            
                            <div class="gpu-metric">
                                <div class="gpu-metric-label">Memory</div>
                                <div class="progress-bar" style="margin-top: 5px;">
                                    <div class="progress-fill" style="width: ${memPercent}%">
                                        ${gpu.memory_used.toFixed(0)} / ${gpu.memory_total.toFixed(0)} MB
                                    </div>
                                </div>
                            </div>
                            
                            <div class="gpu-metric">
                                <div class="gpu-metric-label">Temperature</div>
                                <div class="gpu-metric-value">${gpu.temperature || 0}°C</div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        function updateServers(servers) {
            const activeCount = servers.filter(s => s.process_status === 'RUNNING').length;
            const healthyCount = servers.filter(s => s.health_status === 'HEALTHY').length;
            
            document.getElementById('active-servers').textContent = 
                `${activeCount} / ${servers.length}`;
            document.getElementById('healthy-servers').textContent = 
                `${healthyCount} / ${servers.length}`;
            
            const container = document.getElementById('servers-container');
            container.innerHTML = servers.map(server => {
                const healthClass = server.health_status === 'HEALTHY' ? 'healthy' : 
                                  server.health_status === 'STARTING' ? 'starting' :
                                  server.health_status === 'DOWN' ? 'unhealthy' : 'unknown';
                const statusClass = 'status-' + healthClass;
                
                let uptime = '';
                if (server.uptime_start) {
                    const uptimeSec = Math.floor(Date.now() / 1000 - server.uptime_start);
                    const hours = Math.floor(uptimeSec / 3600);
                    const minutes = Math.floor((uptimeSec % 3600) / 60);
                    uptime = `${hours}h ${minutes}m`;
                }
                
                let portInfoHtml = '';
                if (server.port_info) {
                    portInfoHtml = `<div class="port-info">✓ Port listening (PID: ${server.port_info.pid}, CMD: ${server.port_info.command})</div>`;
                }
                
                return `
                    <div class="server-item ${healthClass}">
                        <div class="server-header">
                            <span class="server-title">Server ${server.index} (Port ${server.port})</span>
                            <span class="status-badge ${statusClass}">${server.health_status}</span>
                        </div>
                        <div class="server-details">
                            <div>Process: <strong>${server.process_status}</strong></div>
                            <div>GPU: <strong>${server.gpu_id}</strong></div>
                            <div>Restarts: <strong>${server.restart_count}</strong></div>
                            <div>Uptime: <strong>${uptime || 'N/A'}</strong></div>
                            ${server.pid ? `<div>PID: <strong>${server.pid}</strong></div>` : ''}
                            ${server.memory_mb ? `<div>Memory: <strong>${server.memory_mb.toFixed(0)} MB</strong></div>` : ''}
                            ${server.cpu_percent !== undefined ? `<div>CPU: <strong>${server.cpu_percent.toFixed(1)}%</strong></div>` : ''}
                            ${server.last_health_check ? `<div>Last Check: <strong>${new Date(server.last_health_check).toLocaleTimeString()}</strong></div>` : ''}
                        </div>
                        ${portInfoHtml}
                        ${server.last_error ? `<div class="error-message">⚠️ ${server.last_error}</div>` : ''}
                    </div>
                `;
            }).join('');
        }
        
        // Fetch logs periodically
        let currentLogType = 'health';
        
        // Log selector change handler
        document.getElementById('log-select').addEventListener('change', function(e) {
            currentLogType = e.target.value;
            fetchLogs();
        });
        
        async function fetchLogs() {
            try {
                const response = await fetch(`/api/logs/${currentLogType}`);
                const data = await response.json();
                const container = document.getElementById('logs-container');
                
                if (data.logs && data.logs.length > 0) {
                    container.innerHTML = data.logs.slice(-30).map(line => 
                        `<div class="log-line">${line}</div>`
                    ).join('');
                    container.scrollTop = container.scrollHeight;
                } else {
                    container.innerHTML = '<p style="color: #858585;">No logs available</p>';
                }
            } catch (e) {
                console.error('Error fetching logs:', e);
                document.getElementById('logs-container').innerHTML = 
                    '<p style="color: #ff6b6b;">Error loading logs</p>';
            }
        }
        
        // Fetch logs every 10 seconds
        setInterval(fetchLogs, 10000);
        fetchLogs();
    </script>
</body>
</html>
"""

# Create templates directory and save HTML
os.makedirs('templates', exist_ok=True)
with open('templates/dashboard.html', 'w') as f:
    f.write(HTML_TEMPLATE)


if __name__ == '__main__':
    print(f"Starting CARLA Dashboard...")
    print(f"Log directory: {LOG_DIR}")
    print(f"Monitoring {NUM_SERVERS} servers starting from port {START_PORT}")
    print(f"Port check method: lsof (reliable)")
    print(f"Dashboard available at: http://localhost:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)