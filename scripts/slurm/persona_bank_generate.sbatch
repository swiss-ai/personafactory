#!/bin/bash
# Persona-bank generation for ONE generator: every node serves the generator (persona_bank_servers.sh) and runs
# its own share of the NSH client shards of generate_bank.py (shard i on node i % nodes, seed SEEDBASE + i).
# NSH is fixed per generator (it is part of the output file names and of the seeds), so a requeue or a resubmit
# on any node count resumes where the shards stopped.
#
#   GEN=gemma NSH=1920 SEEDBASE=31000 TEMP=0.9 OUT=$PF_DATA_DIR/persona_bank/extended/raw \
#   GEN_ARGS="--grid extended --target_total 590000 --n_generators 3 --shard_by slot" \
#   sbatch --nodes=20 [--account=... --partition=...] scripts/slurm/persona_bank_generate.sbatch
#
# Env: GEN (gemma | ministral | glm), NSH, SEEDBASE, TEMP, OUT (generate_bank.py --output_dir), GEN_ARGS (grid
#      flags; see scripts/examples/persona_bank.sh), optional PF_ROOT (repo root, default submit dir), PYTHON,
#      ENV_SETUP (command run first, e.g. activating the client environment), and the server variables of
#      persona_bank_servers.sh (PF_MODEL_DIR, SRUN_ARGS, SERVER_SETUP).
#SBATCH --job-name=pf-bank-gen
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=4
#SBATCH --exclusive
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --time=06:00:00
#SBATCH --output=%x_%j.out
set -u
: "${GEN:?gemma|ministral|glm}" "${NSH:?}" "${SEEDBASE:?}" "${TEMP:?}" "${OUT:?}"
case $GEN in
  gemma) MODEL=google/gemma-4-31B-it ;;
  ministral) MODEL=mistralai/Ministral-3-14B-Instruct-2512 ;;
  glm) MODEL=zai-org/GLM-4.7-Flash ;;
  *) echo "unknown GEN $GEN"; exit 1 ;;
esac
PF_ROOT=${PF_ROOT:-$SLURM_SUBMIT_DIR}
cd "$PF_ROOT" || exit 1
eval "${ENV_SETUP:-true}"
export PYTHONPATH=$PF_ROOT${PYTHONPATH:+:$PYTHONPATH} PF_API_KEY=${PF_API_KEY:-EMPTY}
export PF_LOG_DIR=${PF_LOG_DIR:-$OUT/../logs/servers}
LOGC=$OUT/../logs/gen_$GEN; mkdir -p "$OUT" "$LOGC"
echo "== start $(date) job $SLURM_JOB_ID $GEN nodes $SLURM_JOB_NODELIST restart ${SLURM_RESTART_COUNT:-0}"
NN=$SLURM_JOB_NUM_NODES
ROLES=$(for _ in $(seq 1 "$NN"); do echo -n "$GEN "; done)
source scripts/slurm/persona_bank_servers.sh
case $GEN in gemma) ALL=$GEMMA_URLS ;; ministral) ALL=$MINISTRAL_URLS ;; glm) ALL=$GLM_URLS ;; esac
[ -n "$ALL" ] || { echo "no healthy server"; stop_servers; exit 1; }
CP=""
for k in $(seq 0 $((NN - 1))); do
  n=${NODES[$k]}
  mine=$(for u in $ALL; do case $u in http://$n:*) echo -n "$u ";; esac; done)
  [ -n "$mine" ] || mine=$ALL      # no healthy local server: use the others
  srun --overlap --nodes=1 --ntasks=1 --nodelist="$n" /usr/bin/env MODE=gen NODE_IDX=$k NNODES=$NN NSH=$NSH EPS="$mine" \
    LOGDIR="$LOGC" MODEL=$MODEL TEMP=$TEMP SEEDBASE=$SEEDBASE OUT="$OUT" GEN_ARGS="${GEN_ARGS:-}" PYTHON="${PYTHON:-python}" \
    bash scripts/slurm/persona_bank_node_clients.sh >> "$LOGC/node_$k.txt" 2>&1 &
  CP="$CP $!"
done
# shellcheck disable=SC2086
wait $CP
stop_servers
echo "== end $(date) profiles $(cat "$OUT"/persona_bank_"${MODEL##*/}"*of*[0-9].jsonl 2>/dev/null | wc -l)"
