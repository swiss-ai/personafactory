#!/bin/bash
# Downstream SFT, step 1/6 (once per base model): run-local tokenizer view with SFT markers
# (downstream/megatron/tokenizer_view.py) and the Hugging Face -> Megatron TP4 conversion of the base checkpoint.
#
# Required env: WORK_ROOT (shared training root), MEGATRON_ROOT (Megatron-LM checkout with Apertus support, pinned
#   commit in downstream/megatron/apertus_v15_8b_sft.json), TRANSFORMERS_ROOT (transformers checkout with Apertus),
#   BASE_MODEL (text-only Apertus-v1.5-8B base checkpoint, 131,072-row vocabulary), TOKENIZER_SOURCE (its trimmed text
#   tokenizer), TEMPLATE_SOURCE (Apertus-v1.5-8B instruct checkpoint: chat template).
# Optional env: ENV_SETUP, SRUN_ARGS (e.g. a container), PF_ROOT.
#SBATCH --job-name=pf-sft-setup
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus-per-node=4
#SBATCH --cpus-per-task=64
#SBATCH --time=01:30:00
#SBATCH --output=%x_%j.out
set -euo pipefail
: "${WORK_ROOT:?}" "${MEGATRON_ROOT:?}" "${TRANSFORMERS_ROOT:?}" "${BASE_MODEL:?}" "${TOKENIZER_SOURCE:?}" "${TEMPLATE_SOURCE:?}"
PF_ROOT=${PF_ROOT:-$SLURM_SUBMIT_DIR}
export TOKENIZER_VIEW=$WORK_ROOT/tokenizer_sft_view INIT_CHECKPOINT=$WORK_ROOT/megatron_init_tp4 TEXT_VOCAB_SIZE=131072
[[ ! -e $TOKENIZER_VIEW && ! -e $INIT_CHECKPOINT ]]
mkdir -p "$WORK_ROOT"
export PF_ROOT MEGATRON_ROOT TRANSFORMERS_ROOT BASE_MODEL TOKENIZER_SOURCE TEMPLATE_SOURCE ENV_SETUP="${ENV_SETUP:-}"
export CUDA_DEVICE_MAX_CONNECTIONS=1 PYTHONUNBUFFERED=1
# shellcheck disable=SC2086
srun ${SRUN_ARGS:-} --cpus-per-task="$SLURM_CPUS_PER_TASK" bash -lc '
  set -euo pipefail
  eval "${ENV_SETUP}"
  export PYTHONPATH="${TRANSFORMERS_ROOT}/src:${MEGATRON_ROOT}:${PF_ROOT}"
  python -m personafactory.downstream.megatron.tokenizer_view --source "$TOKENIZER_SOURCE" --template "$TEMPLATE_SOURCE" \
    --expected-vocab-size "$TEXT_VOCAB_SIZE" --output "$TOKENIZER_VIEW"
  cd "$MEGATRON_ROOT"
  python tools/checkpoint/convert.py --model-type GPT --loader apertus --saver core --loader-saver-mode process \
    --load-dir "$BASE_MODEL" --save-dir "$INIT_CHECKPOINT" --tokenizer-model "$TOKENIZER_VIEW" \
    --true-vocab-size "$TEXT_VOCAB_SIZE" --target-tensor-parallel-size 4 --target-pipeline-parallel-size 1 \
    --make-vocab-size-divisible-by 128 --bf16
'
[[ -n "$(find "$INIT_CHECKPOINT" -type f -print -quit)" ]]
echo "SETUP_COMPLETE $WORK_ROOT"
