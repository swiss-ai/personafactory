#!/bin/bash
# Assistant regeneration of the downstream arms A0r (STEP_MODULE=personafactory.downstream.a0r) and X1
# (STEP_MODULE=personafactory.downstream.x_arms) on one 2-node unit: node 0 Gemma 4 31B + Ministral 3 14B (the
# released responders), node 1 the MiniMax-M2.5 sanity judge (scripts/slurm/serve_models.sh). Array task i takes the
# input shards with index % N_TASKS == i; resumable by id, so a requeued or repeated task continues.
#
#   STEP_MODULE=personafactory.downstream.a0r WORK=$PF_OUT_DIR/downstream \
#       sbatch --array=0-3 [$SBATCH_ARGS] scripts/slurm/downstream_regen.sbatch
#
# Required env: STEP_MODULE, WORK (downstream work dir; inputs from `<module> build`).
# Optional env: N_TASKS (4, the array size), CONCURRENCY (160), PF_BANK, PF_LID_MODEL (X1 translation check),
# PF_MODEL_DIR, PF_SRUN_ARGS (container for the servers), ENV_SETUP, PF_ROOT.
#SBATCH --job-name=pf-downstream-regen
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=4
#SBATCH --exclusive
#SBATCH --time=12:00:00
#SBATCH --output=%x_%A_%a.out
set -uo pipefail
: "${STEP_MODULE:?personafactory.downstream.a0r or personafactory.downstream.x_arms}" "${WORK:?}"
PF_ROOT=${PF_ROOT:-$SLURM_SUBMIT_DIR}
cd "$PF_ROOT"
eval "${ENV_SETUP:-true}"
export PYTHONPATH=$PF_ROOT${PYTHONPATH:+:$PYTHONPATH}
SUB=$([[ $STEP_MODULE == *x_arms ]] && echo x1 || echo a0r)
SH=$(ls "$WORK/$SUB/input" | awk -v i="${SLURM_ARRAY_TASK_ID:-0}" -v n="${N_TASKS:-4}" '(NR - 1) % n == i')
echo "== start $(date) task ${SLURM_ARRAY_TASK_ID:-0} shards $(echo $SH | wc -w)"
source scripts/slurm/serve_models.sh gemma ministral judge || { stop_servers; exit 1; }
# shellcheck disable=SC2086
python -u -m "$STEP_MODULE" run --work "$WORK" --shards $SH --gemma "$GEMMA_URL" --ministral "$MINISTRAL_URL" \
    --minimax "$JUDGE_URL" --concurrency "${CONCURRENCY:-160}"
RC=$?
stop_servers
echo "== end $(date) rc $RC"; exit $RC
