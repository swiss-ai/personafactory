#!/bin/bash
# Clean capability of one fine-tuned model with upstream lm-evaluation-harness (vLLM backend): chat template with
# few-shot examples as multi-turn, thinking disabled, greedy decoding, max 2,048 new tokens. Task list:
# personafactory/downstream/eval/lm_eval_tasks.txt (uncomment the cross-lingual block for X1 / X2).
#
#   MODEL=$PF_MODEL_DIR/Apertus-v1.5-8B-base-PF-A2 OUT=$PF_OUT_DIR/downstream/lm_eval/A2 \
#       sbatch [$SBATCH_ARGS] scripts/slurm/downstream_lm_eval.sbatch
#
# Required env: MODEL, OUT. Optional env: TASKS (comma-separated; default: the active lines of the task file),
# TP (1), DP (4), ENV_SETUP, SRUN_ARGS, PF_ROOT. Needs `pip install "lm_eval[vllm]"`; MBPP executes model code.
#SBATCH --job-name=pf-lm-eval
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus-per-node=4
#SBATCH --exclusive
#SBATCH --time=06:00:00
#SBATCH --output=%x_%j.out
set -euo pipefail
: "${MODEL:?}" "${OUT:?}"
PF_ROOT=${PF_ROOT:-$SLURM_SUBMIT_DIR}
eval "${ENV_SETUP:-true}"
TASKS=${TASKS:-$(sed 's/#.*//' "$PF_ROOT/personafactory/downstream/eval/lm_eval_tasks.txt" | awk 'NF {print $1}' | paste -sd,)}
export HF_ALLOW_CODE_EVAL=1
echo "model $MODEL tasks $TASKS"
# shellcheck disable=SC2086
srun ${SRUN_ARGS:-} lm_eval --model vllm \
  --model_args "pretrained=$MODEL,tensor_parallel_size=${TP:-1},data_parallel_size=${DP:-4},gpu_memory_utilization=0.75,enable_thinking=False" \
  --tasks "$TASKS" --apply_chat_template --fewshot_as_multiturn --gen_kwargs max_gen_toks=2048 \
  --batch_size auto --confirm_run_unsafe_code --log_samples --output_path "$OUT"
