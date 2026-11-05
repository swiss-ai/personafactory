#!/bin/bash
# Style-extension A/B judge with MiniMax-M2.5: one judge node per array task, SHARDS_PER_TASK item shards each
# (task i judges shards i*SHARDS_PER_TASK ... (i+1)*SHARDS_PER_TASK - 1 of $DIR/$ITEMS).
#
#   DIR=$PF_OUT_DIR/style_extension sbatch --array=0-3 [...] scripts/slurm/style_extension_judge.sbatch       # items (8 shards)
#   DIR=... ITEMS=judge/items_rejudge RESULTS=judge/results_rejudge MAXTOK=6000 sbatch --array=0-7 [...] ...  # 16 shards
#   DIR=... ITEMS=judge/items_pair2 RESULTS=judge/results_pair2 MAXTOK=6000 sbatch --array=0-7 [...] ...      # 16 shards
#
# Env: DIR, optional ITEMS (judge/items), RESULTS (judge/results), MAXTOK (2048), SHARDS_PER_TASK (2), CONC (96),
#      PF_ROOT, PYTHON, ENV_SETUP, server variables of persona_bank_servers.sh (MINIMAX_CONTEXT defaults to 16384).
#SBATCH --job-name=pf-style-ab-judge
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus-per-node=4
#SBATCH --exclusive
#SBATCH --time=03:00:00
#SBATCH --output=%x_%A_%a.out
set -uo pipefail
: "${DIR:?}"
PF_ROOT=${PF_ROOT:-$SLURM_SUBMIT_DIR}
cd "$PF_ROOT" || exit 1
eval "${ENV_SETUP:-true}"
export PYTHONPATH=$PF_ROOT${PYTHONPATH:+:$PYTHONPATH}
export PF_LOG_DIR=${PF_LOG_DIR:-$DIR/logs/servers} MINIMAX_CONTEXT=${MINIMAX_CONTEXT:-16384}
i=${SLURM_ARRAY_TASK_ID:-0}; K=${SHARDS_PER_TASK:-2}
ITEMS=$DIR/${ITEMS:-judge/items}; RESULTS=$DIR/${RESULTS:-judge/results}; mkdir -p "$RESULTS"
SH=$(for j in $(seq $((K * i)) $((K * i + K - 1))); do printf "%s/%03d.jsonl " "$ITEMS" "$j"; done)
echo "node $(hostname) shards $SH"
ROLES="minimax"
source scripts/slurm/persona_bank_servers.sh
[ -n "$MINIMAX_URLS" ] || { echo "judge not healthy"; stop_servers; exit 1; }
# shellcheck disable=SC2086
"${PYTHON:-python}" -u -m personafactory.evaluation.style_extension.judge_client --shards $SH --outdir "$RESULTS" \
  --urls $MINIMAX_URLS --model "${MINIMAX_SERVED:-MiniMaxAI/MiniMax-M2.5}" --concurrency "${CONC:-96}" \
  --max-tokens "${MAXTOK:-2048}"
RC=$?
stop_servers
exit $RC
