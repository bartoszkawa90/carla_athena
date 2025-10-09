"""
Run multiple CARLA servers, each inside its own Apptainer container.
If any server exits, it gets relaunched after `DELAY` seconds.

PORT MAP
────────
instance 0 → 2000  
instance 1 → 3000
instance 2 → 4000
instance 3 → 5000
"""

import multiprocessing as mp
import os
import signal
import subprocess
from time import sleep
from typing import List


NUM_SERVERS: int = 2
CONTAINER_IMAGE: str = (
    "/net/tscratch/people/plgbartoszkawa/carla_0.9.15.sif"
)
CARLA_BINARY: List[str] = [
    "/home/carla/CarlaUE4.sh",
    "-RenderOffScreen",
    "-nosound",
    "--carla-server",
]
START_PORT: int = 2000
PORT_STEP: int = 1000
DELAY: int = 0.1  # seconds

BASE_CMD: List[str] = ["apptainer", "exec", "--nv", CONTAINER_IMAGE]

# Map instance index → GPU ID (1–4)
GPU_MAP = {
    0: 1,
    1: 2,
    2: 3,
    3: 4,
}


def supervise(idx: int) -> None:
    """Launch & babysit one CARLA instance identified by `idx`."""
    port = START_PORT + idx * PORT_STEP
    gpu_id = GPU_MAP.get(idx, 1)  # default to GPU 1 if not mapped
    cmd = BASE_CMD + CARLA_BINARY + [
        f"-carla-rpc-port={port}",
        f"-graphicsadapter={gpu_id}",
    ]

    while True:
        try:
            print(f"[{idx}] Launching: {' '.join(cmd)}", flush=True)
            proc = subprocess.Popen(cmd, preexec_fn=os.setsid)
            proc.wait()

            print(
                f"[{idx}] Carla (port {port}, GPU {gpu_id}) exited with code {proc.returncode}. "
                f"Restarting in {DELAY}s…",
                flush=True,
            )
            sleep(DELAY)

        except KeyboardInterrupt:
            print(f"[{idx}] Keyboard interrupt → terminating server…", flush=True)
            _kill_process_tree(proc)
            break

        except Exception as exc:
            print(f"[{idx}] Error: {exc}. Restarting in {DELAY}s…", flush=True)
            sleep(DELAY)


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """SIGTERM the entire process group started via `setsid`."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        pass


# main
def main() -> None:
    print(f"Starting {NUM_SERVERS} CARLA servers (first port {START_PORT})")

    workers: List[mp.Process] = []
    for idx in range(NUM_SERVERS):
        p = mp.Process(target=supervise, args=(idx,), daemon=True)
        p.start()
        workers.append(p)

    try:
        for p in workers:
            p.join()
    except KeyboardInterrupt:
        print("\nKeyboard interrupt – shutting down all servers…", flush=True)
        for p in workers:
            p.terminate()
        for p in workers:
            p.join()


if __name__ == "__main__":
    mp.set_start_method("spawn")
    main()
