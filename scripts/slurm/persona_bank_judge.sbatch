#!/bin/bash
# Persona-bank judge: one MiniMax-M2.5 replica (SGLang TP4 / EP4) per node, NSH validate_personas.py clients
# spread over all nodes (two-pass repair, resumable by id on any node count).
#
# Split mode (extended grid, style extension): RUN holds raw/ (generate_bank.py or extend_style.py output).
# The raw files are merged and split into RUN/judge_in/shard_XXXX.jsonl (judge_shards.py split, when PREP=1 or
# the split is missing); results go to RUN/judge_out/val_XXXX.jsonl and are merged into RUN/validated_all.jsonl,
# then lone surrogates are replaced (strip_surrogates.py).
#   RUN=$PF_DATA_DIR/persona_bank/extended NSH=2304 sbatch --nodes=24 [...] scripts/slurm/persona_bank_judge.sbatch
#
# Single-file mode (base grid): JUDGE_INPUT=<persona_bank_all.jsonl> JUDGE_OUTPUT=<..._all.validated.jsonl>; every
# client strides over the one file (validate_personas.py --shard_count NSH) and writes <JUDGE_OUTPUT stem>.shardIIofNN;
# merge them with finalize_bank.py.
#   JUDGE_INPUT=.../persona_bank_all.jsonl JUDGE_OUTPUT=.../persona_bank_all.validated.jsonl NSH=120 \
#   JUDGE_ARGS="--max_tokens 1600" sbatch --nodes=4 [...] scripts/slurm/persona_bank_judge.sbatch
#
# Env: NSH, RUN or JUDGE_INPUT/JUDGE_OUTPUT, optional PREP, JUDGE_ARGS, JCONC (personas in flight per client;
#      few shards per node need ~16 to 32 to fill the server), PF_ROOT, PYTHON, ENV_SETUP, server variables of
#      persona_bank_servers.sh.
#SBATCH --job-name=pf-bank-judge
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=4
#SBATCH --exclusive
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --time=06:00:00
#SBATCH --output=%x_%j.out
set -u
: "${NSH:?}"
PF_ROOT=${PF_ROOT:-$SLURM_SUBMIT_DIR}
cd "$PF_ROOT" || exit 1
eval "${ENV_SETUP:-true}"
export PYTHONPATH=$PF_ROOT${PYTHONPATH:+:$PYTHONPATH} PF_API_KEY=${PF_API_KEY:-EMPTY}
PY=${PYTHON:-python}
if [ -n "${JUDGE_INPUT:-}" ]; then
  JIN=$JUDGE_INPUT; JOUT=${JUDGE_OUTPUT:?set JUDGE_OUTPUT}; LOGBASE=$(dirname "$JOUT")/logs
else
  : "${RUN:?set RUN (split mode) or JUDGE_INPUT (single-file mode)}"
  JIN=$RUN/judge_in; JOUT=$RUN/judge_out; LOGBASE=$RUN/logs
  if [ "${PREP:-0}" = 1 ] || [ ! -s "$JIN/shard_0000.jsonl" ]; then
    $PY -m personafactory.persona_bank.judge_shards split --raw_dir "$RUN/raw" --judge_in "$JIN" \
      --raw_all "$RUN/raw_all.jsonl" --nsh "$NSH" || exit 1
  fi
  mkdir -p "$JOUT"
fi
export PF_LOG_DIR=${PF_LOG_DIR:-$LOGBASE/servers}
LOGC=$LOGBASE/judge_clients; mkdir -p "$LOGC"
echo "== start $(date) job $SLURM_JOB_ID nodes $SLURM_JOB_NODELIST restart ${SLURM_RESTART_COUNT:-0}"
NN=$SLURM_JOB_NUM_NODES
ROLES=$(for _ in $(seq 1 "$NN"); do echo -n "minimax "; done)
source scripts/slurm/persona_bank_servers.sh
[ -n "$MINIMAX_URLS" ] || { echo "no judge endpoint"; stop_servers; exit 1; }
CP=""
for k in $(seq 0 $((NN - 1))); do
  n=${NODES[$k]}
  mine=$(for u in $MINIMAX_URLS; do case $u in http://$n:*) echo -n "$u ";; esac; done)
  [ -n "$mine" ] || mine=$MINIMAX_URLS
  srun --overlap --nodes=1 --ntasks=1 --nodelist="$n" /usr/bin/env MODE=judge NODE_IDX=$k NNODES=$NN NSH=$NSH EPS="$mine" \
    LOGDIR="$LOGC" JIN="$JIN" JOUT="$JOUT" JUDGE_MODEL="${MINIMAX_SERVED:-MiniMaxAI/MiniMax-M2.5}" \
    JUDGE_ARGS="${JUDGE_ARGS:-}" JCONC="${JCONC:-1}" PYTHON="$PY" \
    bash scripts/slurm/persona_bank_node_clients.sh >> "$LOGC/node_$k.txt" 2>&1 &
  CP="$CP $!"
done
# shellcheck disable=SC2086
wait $CP
stop_servers
if [ -z "${JUDGE_INPUT:-}" ]; then
  $PY -m personafactory.persona_bank.judge_shards merge --judge_out "$JOUT" --out "$RUN/validated_all.jsonl" &&
    $PY -m personafactory.persona_bank.strip_surrogates "$RUN/validated_all.jsonl"
fi
echo "== end $(date)"
