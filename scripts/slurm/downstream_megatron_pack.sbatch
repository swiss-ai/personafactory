#!/bin/bash
# Downstream SFT, step 3/6 (per arm): one-epoch packing plan (downstream/megatron/plan.py, Megatron's exact BFD counter)
# and the packed-data cache. Packing: best-fit decreasing, sequence length 4,096, at most 8 documents per packed
# sequence; budget: one packed epoch rounded down to a full global batch of 128.
#
# Required env: WORK_ROOT, ARM, MEGATRON_ROOT, TRANSFORMERS_ROOT. Optional env: ENV_SETUP, SRUN_ARGS, PF_ROOT.
#SBATCH --job-name=pf-sft-pack
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=64
#SBATCH --time=01:00:00
#SBATCH --output=%x_%j.out
set -euo pipefail
: "${WORK_ROOT:?}" "${ARM:?}" "${MEGATRON_ROOT:?}" "${TRANSFORMERS_ROOT:?}"
PF_ROOT=${PF_ROOT:-$SLURM_SUBMIT_DIR}
export ARM_ROOT=$WORK_ROOT/arms/$ARM TOKENIZER_VIEW=$WORK_ROOT/tokenizer_sft_view TEXT_VOCAB_SIZE=131072
[[ -f $ARM_ROOT/dataset/dataset_manifest.json && ! -e $ARM_ROOT/training_plan.json && ! -e $ARM_ROOT/dataset_cache ]]
mkdir -p "$ARM_ROOT/dataset_cache"
export PF_ROOT MEGATRON_ROOT TRANSFORMERS_ROOT ENV_SETUP="${ENV_SETUP:-}"
# shellcheck disable=SC2086
srun ${SRUN_ARGS:-} --cpus-per-task="$SLURM_CPUS_PER_TASK" bash -lc '
  set -euo pipefail
  eval "${ENV_SETUP}"
  export PYTHONPATH="${TRANSFORMERS_ROOT}/src:${MEGATRON_ROOT}:${PF_ROOT}"
  python -m personafactory.downstream.megatron.plan --config "$ARM_ROOT/config.json" --dataset-root "$ARM_ROOT/dataset" \
    --output "$ARM_ROOT/training_plan.json"
  source "$ARM_ROOT/training_plan.env"
  cd "$MEGATRON_ROOT"
  exec python -m torch.distributed.run --nproc-per-node=1 tools/initialize_sft_dataset.py \
    --tensor-model-parallel-size 1 --pipeline-model-parallel-size 1 \
    --num-layers 32 --hidden-size 4096 --ffn-hidden-size 21504 --num-attention-heads 32 --group-query-attention --num-query-groups 8 \
    --max-position-embeddings 262144 --position-embedding-type rope --rotary-base 4000000 --use-rope-scaling --rope-scaling-factor 32 \
    --make-vocab-size-divisible-by 128 --vocab-size "$TEXT_VOCAB_SIZE" --padded-vocab-size "$TEXT_VOCAB_SIZE" \
    --normalization RMSNorm --xielu --qk-layernorm --disable-bias-linear --untie-embeddings-and-output-weights \
    --tokenizer-type HuggingFaceTokenizer --tokenizer-model "$TOKENIZER_VIEW" \
    --per-split-data-args-path "$ARM_ROOT/dataset/per_split_data_args.json" --data-cache-path "$ARM_ROOT/dataset_cache" \
    --seq-length 4096 --num-workers 1 --num-dataset-builder-threads 1 --dataloader-type single \
    --ap-sft --ap-sft-pack-samples --ap-sft-packing-strategy bfd --max-docs-per-bin-sft 8 \
    --ap-sft-plw 0 --ap-sft-mask-special-tokens --ap-sft-equalize-sample-loss --calculate-per-token-loss \
    --micro-batch-size 1 --global-batch-size "$GLOBAL_BATCH_SIZE" --train-samples "$TRAIN_SAMPLES" \
    --eval-interval "$EVAL_INTERVAL" --eval-iters "$EVAL_ITERS" --bf16 --seed 1234 --trigger-path /tmp
'
[[ -f $ARM_ROOT/training_plan.env && -n "$(find "$ARM_ROOT/dataset_cache" -type f -print -quit)" ]]
cat "$ARM_ROOT/training_plan.env"; echo "PACK_COMPLETE arm=$ARM"
