# CARLA .sif Image Builds

This repository is about how to run CARLA simulator and experiments on Athena cluster.

## Overview

CARLA `.def` files are required to build `.sif` images. This README outlines how to build the following images:

* **Client**: A CARLA client image, based on the `carla-common` project repository.
* **Server**: A CARLA server image, pulled directly from the official CARLA Docker container.
* **CARLA Viz**: A visualization image for CARLA, built from the `carlaviz` repository.

To build image use: apptainer build <sif file> <def file>

## Prerequisites

* [Apptainer](https://sylabs.io/docs/) (version 1.3.6 or later)
* Access to the relevant Git repositories:

  * [`carla-common`](https://github.com/wielgosz-info/carla-common.git) (for the client)
  * Official CARLA Docker container (for the server)
  * [`carlaviz`](https://github.com/mjxu96/carlaviz.git) (for the visualization)

## Building Images

### 1. Client Image

1. Clone the `carla-common` repository:

   ```bash
   git clone https://github.com/wielgosz-info/carla-common.git
   cd carla-common
   ```
2. Ensure `client.def` is in the project root (customize base image and dependencies as needed).
3. Build the Apptainer image:

   ```bash
   apptainer build client.sif client.def
   ```
4. Example run for client:
```
apptainer exec --nv <path_to_client_image> python3 <path_to_python_script> <name_of_.log_file> 2>&1 
```

### 2. Server Image

Build the CARLA server image by pulling the official Docker container.

1. Pull carla image: 
```
apptainer pull carla_0.9.15.sif docker://carlasim/carla:0.9.15
```
2. To run carla server use:
```
apptainer exec --nv <path_to_carla_image> /home/carla/CarlaUE4.sh -RenderOffScreen -nosound --carla-server
```
3. Server may sometimes crash so one way to solve it is to continously restart it like in ```carla_server.py```.

4. Ideally use `carla_athena_multiserver_v3.py` where you can choose how many servers you want and how many should work on 
      one GPU.
      Script starts servers in separate containers and restart each one individually when server crashes.
      Logs are saved to server_logs dir and there each run has its own subdir with log files.
      When `ENABLE_DASHBOARD` is true program serves real time resources usage and logs on localhost:5000 in dashboard.
      If dashboard does not work, check if generated `templates` dir is in same place as `carla_athena_multiserver_v3.py`, if not move it there.
      Ideally to kill all servers use `pkill -f 'carla|pyth'`.
      !!! MAKE SURE YOU HAVE CORRECT PATHS FOR YOUR CASE, PROBABLY PATH TO CARLA IMAGE (.sif file) SHOULD BE ADJUSTED. 

### 3. CARLA Viz Image

Build the visualization interface from the `carlaviz` repository.

1. Clone the `carlaviz` repository:

   ```bash
   git clone https://github.com/mjxu96/carlaviz.git
   cd carlaviz
   ```
2. Ensure `carlaviz.def` is in the repository root, and adjust dependencies if required.
3. Build the Apptainer image:

   ```bash
   apptainer build carlaviz.sif carlaviz.def
   ```
   
4. SSH tunel to athena with Carla viz
Get ip address of node on athena
   ```bash
   hostname -i
   ```
Use ip address to create tunnel to node. (Ports 8080 and 8081 are required only when running carlaviz on athena, is is alco possible to run it on local machine)
  ```bash
  TARGET_IP="node_ip_address"; ssh -o ServerAliveInterval=300 -N -L 2000:$TARGET_IP:2000 -L 2001:$TARGET_IP:2001 -L 2002:$TARGET_IP:2002 -L 8080:$TARGET_IP:8080 -L 8081:$TARGET_IP:8081 <user_name>@athena.cyfronet.pl 
  ```

### 4. VS Code Server on Athena (Better solution for debugging and )

Run job which will run vs code server and tunnel so it can be accessed in local vs code app.

1. Run job with sbatch (on athena) : 
```
sbatch vscode-server.slurm
```

2. Check job status until it is 'R' for Running, if status id SD you have to wait for resources: 
```
squeue --me
```
3. You can cancel job with command: 
```
scancel <JOBID>
```

4. To get inside running job it has to have state 'R' (means Running) and execute: 
```
srun --jobid=<JOBID> --pty /bin/bash
```

5. Take ssh command from code-server-log-<JOBID>.txt and create tunnel on local terminal, then connect via local vs code.
You have to copy link to github, go to this site on you local machine and pass code which is in code-server-log-<JOBID>.txt.
After you authenticate you can connect to JOB Node via tunnel in vs code.

---


