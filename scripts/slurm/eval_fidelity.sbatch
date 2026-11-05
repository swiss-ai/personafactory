#!/bin/bash
# Full-corpus judge-free fidelity table on one GPU node: the four CPU statistics of release/stats (transformation
# depth and constraint retention, entity integrity, style adherence, length by tendency; first user turn vs seed
# prompt) and the LaBSE similarity over every user turn (evaluation.corpus_judge.labse_full) in parallel on one GPU.
#
#   REL=$PF_OUT_DIR/release_merged LABSE_ARGS="--seeds $PF_DATA_DIR/seeds/*.jsonl" \
#       sbatch [$SBATCH_ARGS] scripts/slurm/eval_fidelity.sbatch
#
# Required env: REL (release directory with data/*.jsonl and persona_bank.jsonl).
# Optional env: OUT (report dir, default $REL), PF_BANK (default $REL/persona_bank.jsonl), LABSE_ARGS (source inputs of
# labse_full: --originals ... and/or --seeds ..., plus --subset-items/--subset-labse to reuse a scored subset),
# PF_LABSE_MODEL (local LaBSE snapshot; compute nodes are often offline), WORKERS (60), PYTHON, ENV_SETUP, SRUN_ARGS
# (applied to the GPU step, e.g. a container), PF_ROOT.
#SBATCH --job-name=pf-fidelity
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=64
#SBATCH --time=04:00:00
#SBATCH --output=%x_%j.out
set -uo pipefail
: "${REL:?release directory}" "${LABSE_ARGS:?--originals and/or --seeds for labse_full}"
PF_ROOT=${PF_ROOT:-$SLURM_SUBMIT_DIR}
cd "$PF_ROOT"
eval "${ENV_SETUP:-true}"
export PYTHONPATH=$PF_ROOT${PYTHONPATH:+:$PYTHONPATH}
OUT=${OUT:-$REL}; mkdir -p "$OUT"
BANK=${PF_BANK:-$REL/persona_bank.jsonl}
PY=${PYTHON:-python}; W=${WORKERS:-60}
# shellcheck disable=SC2086
srun ${SRUN_ARGS:-} --overlap --ntasks=1 "$PY" -u -m personafactory.evaluation.corpus_judge.labse_full --release-dir "$REL" \
    $LABSE_ARGS --out "$OUT/labse_full.json" > "$OUT/labse_full.log" 2>&1 &
LP=$!
RC=0
"$PY" -m personafactory.release.stats.corpus_numbers --release-dir "$REL" --bank "$BANK" --out "$OUT/corpus_numbers.json" --workers "$W" || RC=1
"$PY" -m personafactory.release.stats.entity_integrity --release-dir "$REL" --out "$OUT/entity_integrity.json" || RC=1
"$PY" -m personafactory.release.stats.style_adherence --release-dir "$REL" --bank "$BANK" --out "$OUT/style_adherence.json" --workers "$W" || RC=1
"$PY" -m personafactory.release.stats.length_by_tendency --release-dir "$REL" --bank "$BANK" --out "$OUT/length_by_tendency.json" || RC=1
wait $LP || RC=1
echo "== end $(date) rc $RC"; exit $RC
