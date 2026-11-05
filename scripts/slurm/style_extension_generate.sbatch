#!/bin/bash
# Style extension of existing personas (persona_bank.extend_style) with Gemma 4 31B: two TP2 replicas per node,
# NSH client shards spread over all replicas. Builds RUN/sources.jsonl first if it is missing (prep, needs the
# source datasets in the local Hugging Face cache), then generates (resumable by source id) and collects the
# successful rows into RUN/raw/persona_bank_extend.jsonl. Judge them with persona_bank_judge.sbatch (RUN=same dir).
#
#   RUN=$PF_DATA_DIR/style_extension NSH=16 PER_COUNTRY=160 PERSONAHUB=220 \
#   sbatch --nodes=4 [--account=... --partition=...] scripts/slurm/style_extension_generate.sbatch
#
# Env: RUN, optional NSH (8), CONC (48 sources in flight per shard), PER_COUNTRY (500), PERSONAHUB (1000), SEED (0),
#      PF_ROOT, PYTHON, ENV_SETUP, server variables of persona_bank_servers.sh.
#SBATCH --job-name=pf-style-ext-gen
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=4
#SBATCH --exclusive
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --time=04:00:00
#SBATCH --output=%x_%j.out
set -u
: "${RUN:?}"
NSH=${NSH:-8}
PF_ROOT=${PF_ROOT:-$SLURM_SUBMIT_DIR}
cd "$PF_ROOT" || exit 1
eval "${ENV_SETUP:-true}"
export PYTHONPATH=$PF_ROOT${PYTHONPATH:+:$PYTHONPATH} PF_API_KEY=${PF_API_KEY:-EMPTY}
export PF_LOG_DIR=${PF_LOG_DIR:-$RUN/logs/servers}
PY=${PYTHON:-python}
LOGC=$RUN/logs/gen_clients; mkdir -p "$LOGC" "$RUN/raw"
echo "== start $(date) job $SLURM_JOB_ID nodes $SLURM_JOB_NODELIST restart ${SLURM_RESTART_COUNT:-0}"
if [ ! -s "$RUN/sources.jsonl" ]; then
  $PY -m personafactory.persona_bank.extend_style prep --out "$RUN" --per_country "${PER_COUNTRY:-500}" \
    --personahub "${PERSONAHUB:-1000}" --seed "${SEED:-0}" || exit 1
fi
ROLES=$(for _ in $(seq 1 "$SLURM_JOB_NUM_NODES"); do echo -n "gemma "; done)
source scripts/slurm/persona_bank_servers.sh
EPS=($GEMMA_URLS)
[ ${#EPS[@]} -gt 0 ] || { echo "no healthy server"; stop_servers; exit 1; }
CP=""
for i in $(seq 0 $((NSH - 1))); do
  $PY -u -m personafactory.persona_bank.extend_style gen --out "$RUN" --base_url "${EPS[$((i % ${#EPS[@]}))]}" \
    --model_name "${GEMMA_SERVED:-google/gemma-4-31B-it}" --shard_count "$NSH" --shard_index "$i" \
    --concurrency "${CONC:-48}" >> "$LOGC/c_$i.txt" 2>&1 &
  CP="$CP $!"
done
# shellcheck disable=SC2086
wait $CP
stop_servers
$PY -m personafactory.persona_bank.extend_style collect --out "$RUN"
echo "== end $(date)"
