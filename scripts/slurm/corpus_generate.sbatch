#!/bin/bash
#SBATCH --job-name=pf-corpus-gen
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=4
#SBATCH --exclusive
#SBATCH --requeue
#SBATCH --time=12:00:00
#SBATCH --output=%x_%A_%a.out
# Seed-pool generation, one 2-node unit per array task: Gemma + Ministral on node 0, the MiniMax judge on node 1,
# one driver per setting (free, multilingual) against the unit's servers. Unit U of NU takes every NU-th seed shard of
# each setting (sorted names, so sources mix). The driver skips conversation ids already written, so a requeued or
# resubmitted task resumes. Submit from the repository root, e.g. 44 units, at most 24 at a time:
#   SEEDS=./data/seeds/shards ASSIGN=./outputs/assign_seeds RUN=./outputs/seeds_run NU=44 \
#     sbatch --array=0-43%24 scripts/slurm/corpus_generate.sbatch
# Regeneration of a subset with Gemma (postprocess.lowres_regen_prep output): PAIRS_DIR=<run>/pairs, which holds
#   {mode}-uNN.jsonl and select_{mode}.txt one level up, and RESPONDER=gemma:
#   PAIRS_DIR=./outputs/regen_lowres/pairs ASSIGN=./outputs/assign_seeds RUN=./outputs/regen_lowres RESPONDER=gemma \
#     sbatch --array=0-3 --time=04:00:00 scripts/slurm/corpus_generate.sbatch
# Optional: EXCLUDE (pair keys to skip, e.g. <ASSIGN>/holdout.txt), CONCURRENCY (100), ENV_SETUP.
set -uo pipefail
: "${ASSIGN:?}" "${RUN:?}" "${PF_BANK:?}" "${PF_LID_MODEL:?}"
cd "${SLURM_SUBMIT_DIR:-.}"
eval "${ENV_SETUP:-true}"
export PYTHONPATH=$PWD${PYTHONPATH:+:$PYTHONPATH} PF_LOG_DIR=${PF_LOG_DIR:-$RUN/logs}
U=${SLURM_ARRAY_TASK_ID:-0}
NU=${NU:-${SLURM_ARRAY_TASK_COUNT:-1}}
mkdir -p "$RUN/gen" "$PF_LOG_DIR"
source scripts/slurm/serve_models.sh gemma ministral judge || { stop_servers; exit 1; }
DP=""
for m in free multilingual; do
  if [ -n "${PAIRS_DIR:-}" ]; then
    P="$PAIRS_DIR/$m-u$(printf %02d $U).jsonl"; [ -s "$P" ] || continue
    FILES=("$P"); EXTRA=(--select "$(dirname "$PAIRS_DIR")/select_$m.txt")
  else
    mapfile -t FILES < <(ls "$SEEDS"/$m-*.jsonl | sort | awk -v u=$U -v n=$NU '(NR-1)%n==u')
    EXTRA=()
  fi
  [ ${#FILES[@]} -gt 0 ] || continue
  [ -n "${EXCLUDE:-}" ] && EXTRA+=(--exclude "$EXCLUDE")
  [ -n "${RESPONDER:-}" ] && EXTRA+=(--responder "$RESPONDER")
  echo "unit $U/$NU $m: ${#FILES[@]} shard files"
  python -u -m personafactory.augmentation.run_augmentation --input-kind seeds --pairs "${FILES[@]}" --mode $m \
    --assign-dir "$ASSIGN" --outdir "$RUN/gen" ${EXTRA[@]+"${EXTRA[@]}"} --bank "$PF_BANK" --lid-model "$PF_LID_MODEL" \
    --gemma "$GEMMA_URL" --ministral "$MINISTRAL_URL" --minimax "$JUDGE_URL" --concurrency "${CONCURRENCY:-100}" \
    >> "$PF_LOG_DIR/gen_${m}_u$U.log" 2>&1 &
  DP="$DP $!"
done
RC=0
for p in $DP; do wait $p || RC=1; done
stop_servers
echo "exit $RC"; exit $RC
