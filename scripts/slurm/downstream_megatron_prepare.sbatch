#!/bin/bash
# Downstream SFT, step 2/6 (per arm): render the run config (downstream/megatron/render_config.py) and tokenize the
# arm's full multi-turn conversations into Megatron IndexedDataset bins (prepare_dataset.py; loss on every assistant
# turn, family-level validation split stratified by language).
#
# Required env: WORK_ROOT, ARM (A0, A1, A0r, A2, X1, X2), SOURCE (<ARM>_source.jsonl), MEGATRON_ROOT, TRANSFORMERS_ROOT.
# Optional env: VALID_FRAC (0.01; the paper used 0.03 for X1/X2), ENV_SETUP, SRUN_ARGS, PF_ROOT.
#SBATCH --job-name=pf-sft-prepare
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=128
#SBATCH --time=01:00:00
#SBATCH --output=%x_%j.out
set -euo pipefail
: "${WORK_ROOT:?}" "${ARM:?}" "${SOURCE:?}" "${MEGATRON_ROOT:?}" "${TRANSFORMERS_ROOT:?}"
PF_ROOT=${PF_ROOT:-$SLURM_SUBMIT_DIR}
export ARM_ROOT=$WORK_ROOT/arms/$ARM TOKENIZER_VIEW=$WORK_ROOT/tokenizer_sft_view
[[ -f $SOURCE && -d $TOKENIZER_VIEW && ! -e $ARM_ROOT/dataset ]]
mkdir -p "$ARM_ROOT"
export PF_ROOT ARM SOURCE MEGATRON_ROOT TRANSFORMERS_ROOT VALID_FRAC="${VALID_FRAC:-0.01}" ENV_SETUP="${ENV_SETUP:-}"
# shellcheck disable=SC2086
srun ${SRUN_ARGS:-} --cpus-per-task="$SLURM_CPUS_PER_TASK" bash -lc '
  set -euo pipefail
  eval "${ENV_SETUP}"
  export PYTHONPATH="${TRANSFORMERS_ROOT}/src:${MEGATRON_ROOT}:${PF_ROOT}"
  [[ -f "$ARM_ROOT/config.json" ]] || python -m personafactory.downstream.megatron.render_config --arm "$ARM" --source "$SOURCE" \
    --work-root "$ARM_ROOT" --tokenizer-view "$TOKENIZER_VIEW" --validation-fraction "$VALID_FRAC" --output "$ARM_ROOT/config.json"
  python -m personafactory.downstream.megatron.prepare_dataset --config "$ARM_ROOT/config.json" \
    --output-root "$ARM_ROOT/dataset" --workers 64 --max-token-id 131071
'
[[ -f $ARM_ROOT/dataset/dataset_manifest.json && -f $ARM_ROOT/dataset/per_split_data_args.json ]]
echo "PREPARE_COMPLETE arm=$ARM"
