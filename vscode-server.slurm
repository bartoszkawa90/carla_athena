#!/bin/bash
#SBATCH --partition plgrid-gpu-a100
#SBATCH --nodes 1
#SBATCH --ntasks-per-node 1
#SBATCH --cpus-per-task 56
#SBATCH --mem 100G
#SBATCH --time 18:30:00
#SBATCH --gpus=4
#SBATCH --account plgdyplomanci7-gpu-a100
#SBATCH --job-name code-server-tunnel
#SBATCH --output code-server-log-%J.txt
ln -s $TMPDIR  /tmp/${SLURM_JOB_ID}
export TMPDIR=/tmp/${SLURM_JOB_ID}
module load VSCode/1.100.1
ml GCCcore/13.2.0 Python/3.11.5
cd $SCRATCH
code tunnel --name vscode-athena --accept-server-license-terms --no-sleep
cat code-server-log-%J.txt

