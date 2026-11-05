#!/bin/bash
# Downstream SFT of one arm with Megatron-LM: submit prepare -> pack -> smoke (1 node) -> train (4 nodes, one job per
# seed) -> export (one per seed). Run downstream_megatron_setup.sbatch once first (tokenizer view and TP4 init
# checkpoint under WORK_ROOT); pass its job id as DEP to chain on it.
#
#   ARM=A2 SOURCE=$PF_OUT_DIR/downstream/data_paired/A2_source.jsonl WORK_ROOT=$PF_OUT_DIR/downstream/sft \
#   EXPORT_PREFIX=$PF_MODEL_DIR/Apertus-v1.5-8B-base-PF MEGATRON_ROOT=... TRANSFORMERS_ROOT=... HF_SAVER=... \
#   SEEDS="1234 2 3" bash scripts/slurm/downstream_megatron_pipeline.sh
#
# Exports land in $EXPORT_PREFIX-$ARM (seed 1234) and $EXPORT_PREFIX-$ARM-s<seed>. Cross-lingual arms: VALID_FRAC=0.03.
# Optional env: DEP, SEEDS (1234), NODES (4), VALID_FRAC, SBATCH_ARGS (cluster flags for every job), ENV_SETUP,
# SRUN_ARGS, PF_ROOT.
set -euo pipefail
: "${ARM:?}" "${SOURCE:?}" "${WORK_ROOT:?}" "${EXPORT_PREFIX:?}" "${MEGATRON_ROOT:?}" "${TRANSFORMERS_ROOT:?}" "${HF_SAVER:?}"
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export PF_ROOT=${PF_ROOT:-$(cd "$HERE/../.." && pwd)}
export ARM SOURCE WORK_ROOT MEGATRON_ROOT TRANSFORMERS_ROOT HF_SAVER
cd "$PF_ROOT"
# shellcheck disable=SC2086
SB="sbatch --parsable ${SBATCH_ARGS:-} --export=ALL"
PR=$($SB ${DEP:+--dependency=afterok:$DEP} --job-name=pf-sft-prepare-$ARM "$HERE/downstream_megatron_prepare.sbatch")
PK=$($SB --dependency=afterok:$PR --job-name=pf-sft-pack-$ARM "$HERE/downstream_megatron_pack.sbatch")
SM=$(MODE=smoke $SB --dependency=afterok:$PK --nodes=1 --time=00:45:00 --job-name=pf-sft-smoke-$ARM "$HERE/downstream_megatron_train.sbatch")
echo "arm=$ARM prepare=$PR pack=$PK smoke=$SM"
for seed in ${SEEDS:-1234}; do
  sfx=$([[ $seed == 1234 ]] && echo "" || echo "-s$seed")
  TR=$(MODE=train SEED=$seed $SB --dependency=afterok:$SM --nodes=${NODES:-4} --job-name=pf-sft-train-$ARM$sfx "$HERE/downstream_megatron_train.sbatch")
  XP=$(SEED=$seed EXPORT_ROOT=$EXPORT_PREFIX-$ARM$sfx $SB --dependency=afterok:$TR --job-name=pf-sft-export-$ARM$sfx "$HERE/downstream_megatron_export.sbatch")
  echo "  seed=$seed train=$TR export=$XP -> $EXPORT_PREFIX-$ARM$sfx"
done
