import subprocess
from time import sleep
import sys

# carla image path
CONTAINER_IMAGE = "/net/tscratch/people/plgbartoszkawa/carla_0.9.15.sif"
# run container
COMMAND = ["apptainer", "exec", "--nv", CONTAINER_IMAGE, "/home/carla/CarlaUE4.sh", "-RenderOffScreen", "-nosound", "--carla-server"]

# delay before restart
delay = 2

def main():
    print("Apptainer Container Auto-Restarter Started.")
    
    while True:
        try:
            print(f"Launching container: {' '.join(COMMAND)}")
            # launch process 
            process = subprocess.Popen(COMMAND)
            
            # wait for process to finish
            process.wait()
            
            print(f"Container exited with code {process.returncode}. Restarting in {delay} seconds...")
            
            # restart with some small delay
            sleep(delay)
        
        except KeyboardInterrupt:
            print("Keyboard interrupt detected. Stopping container auto-restart.")
            try:
                process.terminate()
            except Exception:
                pass
            sys.exit(0)
        except Exception as e:
            print(f"Error occurred: {e}. Restarting container in {delay} seconds...")
            sleep(delay)

if __name__ == "__main__":
    main()
