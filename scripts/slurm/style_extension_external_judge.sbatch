#!/bin/bash
# Style-extension A/B with the two external judges: the first half of the nodes serves Qwen3.6-35B-A3B-FP8, the
# second half Muse-Glimmer-30B (each node 2 x TP2 vLLM replicas). Both judge $DIR/judge/items_ext/all.jsonl
# (items.py external: calibration, identify, both-orders pairwise) into $DIR/judge_<label>/results, then
# aggregate.py writes $DIR/report_<label>.json.
#
#   DIR=$PF_OUT_DIR/style_extension MUSE_MODEL=/path/to/Muse-Glimmer-30B \
#   sbatch --nodes=8 [--account=... --partition=...] scripts/slurm/style_extension_external_judge.sbatch
#
# Env: DIR, MUSE_MODEL, optional CONC (800 requests in flight per judge), MAXTOK (8192), PF_ROOT, PYTHON, ENV_SETUP,
#      server variables of persona_bank_servers.sh. Muse-Glimmer needs a vLLM build that supports it; if it needs
#      another environment than Qwen, run the two judges as two jobs (QWEN_ONLY=1 / MUSE_ONLY=1).
#SBATCH --job-name=pf-style-ab-extjudge
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=4
#SBATCH --exclusive
#SBATCH --time=03:00:00
#SBATCH --output=%x_%j.out
set -uo pipefail
: "${DIR:?}"
PF_ROOT=${PF_ROOT:-$SLURM_SUBMIT_DIR}
cd "$PF_ROOT" || exit 1
eval "${ENV_SETUP:-true}"
export PYTHONPATH=$PF_ROOT${PYTHONPATH:+:$PYTHONPATH}
export PF_LOG_DIR=${PF_LOG_DIR:-$DIR/logs/servers}
PY=${PYTHON:-python}
NN=$SLURM_JOB_NUM_NODES
if [ "${QWEN_ONLY:-0}" = 1 ]; then ROLES=$(for _ in $(seq 1 "$NN"); do echo -n "qwen "; done)
elif [ "${MUSE_ONLY:-0}" = 1 ]; then ROLES=$(for _ in $(seq 1 "$NN"); do echo -n "muse "; done)
else ROLES="$(for _ in $(seq 1 $((NN / 2))); do echo -n "qwen "; done)$(for _ in $(seq 1 $((NN - NN / 2))); do echo -n "muse "; done)"
fi
source scripts/slurm/persona_bank_servers.sh
CPIDS=""
# shellcheck disable=SC2086
[ -n "$QWEN_URLS" ] && { $PY -u -m personafactory.evaluation.style_extension.judge_client --shards "$DIR/judge/items_ext/all.jsonl" \
  --outdir "$DIR/judge_qwen36/results" --urls $QWEN_URLS --model "${QWEN_SERVED:-Qwen/Qwen3.6-35B-A3B-FP8}" \
  --max-tokens "${MAXTOK:-8192}" --concurrency "${CONC:-800}" > "$DIR/logs/extjudge_qwen36.log" 2>&1 & CPIDS="$CPIDS $!"; }
# shellcheck disable=SC2086
[ -n "$MUSE_URLS" ] && { $PY -u -m personafactory.evaluation.style_extension.judge_client --shards "$DIR/judge/items_ext/all.jsonl" \
  --outdir "$DIR/judge_muse/results" --urls $MUSE_URLS --model "${MUSE_SERVED:-Muse-Glimmer-30B}" \
  --max-tokens "${MAXTOK:-8192}" --concurrency "${CONC:-800}" > "$DIR/logs/extjudge_muse.log" 2>&1 & CPIDS="$CPIDS $!"; }
RC=0
for p in $CPIDS; do wait "$p" || RC=1; done
stop_servers
for L in qwen36 muse; do
  [ -d "$DIR/judge_$L/results" ] && $PY -m personafactory.evaluation.style_extension.aggregate --dir "$DIR" \
    --judge "judge_$L" --out "report_$L.json" > "$DIR/logs/aggregate_$L.log" 2>&1
done
echo "== end $(date) rc $RC"; exit $RC
