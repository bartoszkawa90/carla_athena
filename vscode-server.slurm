#!/bin/bash
#SBATCH --partition plgrid-gpu-a100
#SBATCH --nodes 1
#SBATCH --ntasks-per-node 1
#SBATCH --cpus-per-task 6
#SBATCH --mem 20G
#SBATCH --time 10:00:00
#SBATCH --gpus=1
#SBATCH --account plgdyplomanci6-gpu-a100
#SBATCH --job-name code-server-tunnel
#SBATCH --output code-server-log-%J.txt
ln -s $TMPDIR  /tmp/${SLURM_JOB_ID}
export TMPDIR=/tmp/${SLURM_JOB_ID}
module load VSCode/1.100.1
ml GCCcore/13.2.0 Python/3.11.5
cd $SCRATCH
code tunnel --name vscode-athena --accept-server-license-terms --no-sleep
