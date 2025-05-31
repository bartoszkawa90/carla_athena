# CARLA .sif Image Builds

This repository provides instructions and definition files for building Apptainer `.sif` images for various CARLA components using `.def` files.

## Overview

CARLA `.def` files are required to build `.sif` images. This README outlines how to build the following images:

* **Client**: A CARLA client image, based on the `carla-common` project repository.
* **Server**: A CARLA server image, pulled directly from the official CARLA Docker container.
* **CARLA Viz**: A visualization image for CARLA, built from the `carlaviz` repository.

## Prerequisites

* [Apptainer](https://sylabs.io/docs/) (version 1.3.6 or later)
* Access to the relevant Git repositories:

  * [`carla-common`](https://github.com/wielgosz-info/carla-common.git) (for the client)
  * Official CARLA Docker container (for the server)
  * [`carlaviz`](https://github.com/mjxu96/carlaviz.git) (for the visualization)

## Directory Structure

```text
.
├── client.def       # Definition file for the CARLA client image
├── server.def       # Definition file for the CARLA server image
├── viz.def          # Definition file for the CARLA Viz image
└── README.md        # This instruction file
```

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

### 2. Server Image

Build the CARLA server image by pulling the official Docker container.

1. Place `server.def` in your working directory.
2. Build the Apptainer image:

   ```bash
   apptainer build server.sif server.def
   ```

Your `server.def` should reference the CARLA Docker image, for example:

```def
Bootstrap: docker
From: carlasim/carla:latest
```

### 3. CARLA Viz Image

Build the visualization interface from the `carlaviz` repository.

1. Clone the `carlaviz` repository:

   ```bash
   git clone https://github.com/mjxu96/carlaviz.git
   cd carlaviz
   ```
2. Ensure `viz.def` is in the repository root, and adjust dependencies if required.
3. Build the Apptainer image:

   ```bash
   apptainer build viz.sif viz.def
   ```
   
4. SSH tunel to athena with Carla viz
Get ip address of node on athena
   ```bash
   hostname -i
   ```
Use ip address to create tunnel to node
  ```bash
  TARGET_IP="node_ip_address"; ssh -o ServerAliveInterval=300 -N -L 2000:$TARGET_IP:2000 -L 2001:$TARGET_IP:2001 -L 2002:$TARGET_IP:2002 -L 8080:$TARGET_IP:8080 -L 8081:$TARGET_IP:8081 <user_name>@athena.cyfronet.pl 
  ```

---


