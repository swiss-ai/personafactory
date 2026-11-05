#!/bin/bash
# Downstream SFT, steps 4-5/6 (per arm): smoke run (MODE=smoke: 1 node, global batch 4, 40 samples) and the full run.
# Recipe of the paper: Apertus-v1.5-8B base, one epoch, TP 4, micro batch 1, global batch 128 packed 4,096-token
# sequences, lr 1e-5 -> 1e-6 cosine, 3% warmup, weight decay 0, clip 1.0, bf16, loss on every assistant turn
# (--ap-sft-plw 0), seed 1234 (extra seeds 2 and 3 for A0, A1, A2). 4 nodes x 4 GPUs per arm (data parallel 4,
# 32 gradient-accumulation steps per batch). Resumes from the run's last checkpoint when requeued.
#
#   ARM=A2 SEED=1234 sbatch --nodes=4 [$SBATCH_ARGS] scripts/slurm/downstream_megatron_train.sbatch
#   ARM=A2 MODE=smoke sbatch --nodes=1 --time=00:45:00 scripts/slurm/downstream_megatron_train.sbatch
#
# Required env: WORK_ROOT, ARM, MEGATRON_ROOT, TRANSFORMERS_ROOT. Optional env: MODE (train | smoke), SEED (1234),
# MASTER_PORT, ENV_SETUP, SRUN_ARGS, PF_ROOT. Run root: $WORK_ROOT/arms/$ARM/runs/{smoke,seed<SEED>}.
#SBATCH --job-name=pf-sft-train
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=4
#SBATCH --gpus-per-node=4
#SBATCH --cpus-per-task=64
#SBATCH --exclusive
#SBATCH --requeue
#SBATCH --time=06:00:00
#SBATCH --output=%x_%j.out
set -euo pipefail
: "${WORK_ROOT:?}" "${ARM:?}" "${MEGATRON_ROOT:?}" "${TRANSFORMERS_ROOT:?}"
MODE=${MODE:-train}; SEED=${SEED:-1234}
ARM_ROOT=$WORK_ROOT/arms/$ARM
TOKENIZER_VIEW=$WORK_ROOT/tokenizer_sft_view; INIT_CHECKPOINT=$WORK_ROOT/megatron_init_tp4; TEXT_VOCAB_SIZE=131072
[[ -f $ARM_ROOT/training_plan.env && -d $ARM_ROOT/dataset_cache && -d $INIT_CHECKPOINT ]]
source "$ARM_ROOT/training_plan.env"
(( TRAIN_SAMPLES > 0 && TRAIN_ITERS > 0 && GLOBAL_BATCH_SIZE == 128 ))
if [[ $MODE == smoke ]]; then
  OUT_ROOT=$ARM_ROOT/runs/smoke; GBS=4; SAMPLES=40; EVAL_INTERVAL=5; EVAL_ITERS=1; SAVE_INTERVAL=10
  [[ ! -e $OUT_ROOT ]]
else
  OUT_ROOT=$ARM_ROOT/runs/seed$SEED; GBS=$GLOBAL_BATCH_SIZE; SAMPLES=$TRAIN_SAMPLES
  SAVE_INTERVAL=$((TRAIN_ITERS / 3)); (( SAVE_INTERVAL < 10 )) && SAVE_INTERVAL=10
fi
LOAD=$INIT_CHECKPOINT; FT="--finetune"
if [[ $MODE != smoke && -f $OUT_ROOT/checkpoints/latest_checkpointed_iteration.txt ]]; then
  LOAD=$OUT_ROOT/checkpoints; FT=""; echo "resuming from $(cat "$OUT_ROOT/checkpoints/latest_checkpointed_iteration.txt")"
fi
mkdir -p "$OUT_ROOT/checkpoints" "$OUT_ROOT/tensorboard" "$OUT_ROOT/triggers" "$ARM_ROOT/triton_cache"
export PYTHONUNBUFFERED=1 TRITON_CACHE_DIR=$ARM_ROOT/triton_cache TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
export TORCH_NCCL_AVOID_RECORD_STREAMS=1 TORCH_NCCL_ASYNC_ERROR_HANDLING=1 CUDA_DEVICE_MAX_CONNECTIONS=1
export MASTER_ADDR=$(scontrol show hostnames "$SLURM_JOB_NODELIST" | head -n 1)
export MASTER_PORT=${MASTER_PORT:-60420} WORLD_SIZE=$SLURM_NTASKS
export MEGATRON_ROOT TRANSFORMERS_ROOT ARM_ROOT LOAD FT OUT_ROOT TOKENIZER_VIEW TEXT_VOCAB_SIZE SAMPLES EVAL_INTERVAL EVAL_ITERS GBS SAVE_INTERVAL SEED
export ENV_SETUP="${ENV_SETUP:-}"
echo "MODE=$MODE arm=$ARM seed=$SEED nodes=$SLURM_NNODES gbs=$GBS samples=$SAMPLES iters=$TRAIN_ITERS out=$OUT_ROOT"
# shellcheck disable=SC2086
srun ${SRUN_ARGS:-} --cpu-bind=none --cpus-per-task="$SLURM_CPUS_PER_TASK" bash -lc '
  set -euo pipefail
  eval "${ENV_SETUP}"
  export PYTHONPATH="${TRANSFORMERS_ROOT}/src:${MEGATRON_ROOT}" RANK=$SLURM_PROCID LOCAL_RANK=$SLURM_LOCALID
  cd "$MEGATRON_ROOT"
  exec python pretrain_gpt.py \
    --transformer-impl transformer_engine --use-precision-aware-optimizer --main-grads-dtype bf16 \
    --num-layers 32 --hidden-size 4096 --ffn-hidden-size 21504 --num-attention-heads 32 --group-query-attention --num-query-groups 8 \
    --max-position-embeddings 262144 --position-embedding-type rope --rotary-base 4000000 --use-rope-scaling --rope-scaling-factor 32 \
    --make-vocab-size-divisible-by 128 --vocab-size "$TEXT_VOCAB_SIZE" --padded-vocab-size "$TEXT_VOCAB_SIZE" \
    --normalization RMSNorm --xielu --qk-layernorm --disable-bias-linear --untie-embeddings-and-output-weights \
    --tensor-model-parallel-size 4 --pipeline-model-parallel-size 1 --sequence-parallel --use-distributed-optimizer --overlap-grad-reduce --overlap-param-gather \
    --tokenizer-type HuggingFaceTokenizer --tokenizer-model "$TOKENIZER_VIEW" \
    --per-split-data-args-path "$ARM_ROOT/dataset/per_split_data_args.json" --data-cache-path "$ARM_ROOT/dataset_cache" --seq-length 4096 --num-workers 1 --num-dataset-builder-threads 1 --dataloader-type single \
    --ap-sft --ap-sft-pack-samples --ap-sft-packing-strategy bfd --max-docs-per-bin-sft 8 --ap-sft-plw 0 --calculate-per-token-loss \
    --micro-batch-size 1 --global-batch-size "$GBS" --train-samples "$SAMPLES" --eval-interval "$EVAL_INTERVAL" --eval-iters "$EVAL_ITERS" \
    --lr 1.0e-5 --min-lr 1.0e-6 --lr-decay-style cosine --lr-warmup-fraction 0.03 --weight-decay 0.0 --clip-grad 1.0 \
    --bf16 --seed "$SEED" $FT --auto-detect-ckpt-format --exit-on-missing-checkpoint --load "$LOAD" \
    --save "$OUT_ROOT/checkpoints" --save-interval "$SAVE_INTERVAL" --ckpt-format torch_dist --tensorboard-dir "$OUT_ROOT/tensorboard" \
    --log-interval 1 --log-throughput --log-progress --trigger-path "$OUT_ROOT/triggers"
' || echo "pretrain_gpt exited non-zero (the post-epoch validation can do this); checking the checkpoint"
[[ "$(tr -d '[:space:]' < "$OUT_ROOT/checkpoints/latest_checkpointed_iteration.txt")" == "$([[ $MODE == smoke ]] && echo 10 || echo "$TRAIN_ITERS")" ]]
echo "${MODE^^}_COMPLETE arm=$ARM root=$OUT_ROOT"
