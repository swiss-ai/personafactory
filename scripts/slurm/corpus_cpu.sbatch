#!/bin/bash
#SBATCH --job-name=pf-corpus-cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --exclusive
#SBATCH --time=12:00:00
#SBATCH --output=%x_%j.out
# One CPU step of scripts/examples/corpus.sh on a compute node (seed preparation, selection, build, merge,
# postprocess stages). Submit from the repository root:
#   CMD="python -m personafactory.augmentation.prepare_seeds ..." sbatch [--account=... --partition=...] scripts/slurm/corpus_cpu.sbatch
# Optional: ENV_SETUP (command run first, e.g. activating an environment).
set -euo pipefail
: "${CMD:?command to run}"
cd "${SLURM_SUBMIT_DIR:-.}"
eval "${ENV_SETUP:-true}"
export PYTHONPATH=$PWD${PYTHONPATH:+:$PYTHONPATH} PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-1} OPENBLAS_NUM_THREADS=${OPENBLAS_NUM_THREADS:-1} MKL_NUM_THREADS=${MKL_NUM_THREADS:-1}
echo "started $(date): $CMD"
bash -euo pipefail -c "$CMD"
echo "finished $(date)"
