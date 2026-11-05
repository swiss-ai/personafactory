#!/bin/bash
# Style-extension A/B generation, one array task per arm (0, 1, 2 = A, B, C), two nodes each: node 0 serves two
# Gemma 4 31B replicas (rewriter, translator and responder), node 1 MiniMax-M2.5 (per-turn sanity judge).
# Resumable by key.
#
#   DIR=$PF_OUT_DIR/style_extension sbatch --array=0-2 [--account=... --partition=...] scripts/slurm/style_extension_ab.sbatch
#
# Env: DIR (evaluation.style_extension.prep output), optional CONC (120), PF_LID_MODEL, PF_ROOT, PYTHON, ENV_SETUP,
#      server variables of persona_bank_servers.sh (MAX_MODEL_LEN defaults to 65536 here).
#SBATCH --job-name=pf-style-ab-gen
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=4
#SBATCH --exclusive
#SBATCH --requeue
#SBATCH --time=03:00:00
#SBATCH --output=%x_%A_%a.out
set -uo pipefail
: "${DIR:?}"
ARMS=(A B C); ARM=${ARMS[${SLURM_ARRAY_TASK_ID:-2}]}
PF_ROOT=${PF_ROOT:-$SLURM_SUBMIT_DIR}
cd "$PF_ROOT" || exit 1
eval "${ENV_SETUP:-true}"
export PYTHONPATH=$PF_ROOT${PYTHONPATH:+:$PYTHONPATH}
export PF_LOG_DIR=${PF_LOG_DIR:-$DIR/logs/servers} MAX_MODEL_LEN=${MAX_MODEL_LEN:-65536}
mkdir -p "$DIR/logs"
echo "== start $(date) arm $ARM nodes $SLURM_JOB_NODELIST restart ${SLURM_RESTART_COUNT:-0}"
ROLES="gemma minimax"
source scripts/slurm/persona_bank_servers.sh
[ -n "$GEMMA_URLS" ] && [ -n "$MINIMAX_URLS" ] || { echo "servers not healthy"; stop_servers; exit 1; }
# shellcheck disable=SC2086
"${PYTHON:-python}" -u -m personafactory.evaluation.style_extension.generate --arm "$ARM" --dir "$DIR" \
  --gemma $GEMMA_URLS --gemma-model "${GEMMA_SERVED:-google/gemma-4-31B-it}" \
  --minimax ${MINIMAX_URLS%% *} --minimax-model "${MINIMAX_SERVED:-MiniMaxAI/MiniMax-M2.5}" \
  --concurrency "${CONC:-120}" >> "$DIR/logs/generate_$ARM.log" 2>&1
RC=$?
stop_servers
echo "== end $(date) exit $RC"; exit $RC
