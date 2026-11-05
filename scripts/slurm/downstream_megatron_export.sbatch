#!/bin/bash
# Downstream SFT, step 6/6 (per arm and seed): export the final iteration to a Hugging Face directory (text view, chat
# template included): torch_dist -> torch (Megatron scripts/conversion/torchdist_2_torch.py), then torch -> HF with the
# Apertus HF saver of the Megatron-LM checkout (tools/checkpoint/saver_<HF_SAVER>.py); loaded with transformers
# before the final move. The export is what gen_eval / lm_eval serve with vLLM.
#
# Required env: WORK_ROOT, ARM, MEGATRON_ROOT, TRANSFORMERS_ROOT, EXPORT_ROOT (new output dir), HF_SAVER.
# Optional env: SEED (1234), ENV_SETUP, SRUN_ARGS.
#SBATCH --job-name=pf-sft-export
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus-per-node=4
#SBATCH --cpus-per-task=64
#SBATCH --time=01:30:00
#SBATCH --output=%x_%j.out
set -euo pipefail
: "${WORK_ROOT:?}" "${ARM:?}" "${MEGATRON_ROOT:?}" "${TRANSFORMERS_ROOT:?}" "${EXPORT_ROOT:?}" "${HF_SAVER:?}"
[[ -f "$MEGATRON_ROOT/tools/checkpoint/saver_${HF_SAVER}.py" && ! -e "$EXPORT_ROOT" ]]
ARM_ROOT=$WORK_ROOT/arms/$ARM; SEED=${SEED:-1234}
source "$ARM_ROOT/training_plan.env"
ITER_DIR=$(printf 'iter_%07d' "$TRAIN_ITERS")
export TRAIN_CHECKPOINT=$ARM_ROOT/runs/seed$SEED/checkpoints
export TORCH_CONVERT_ROOT=$ARM_ROOT/conversion/seed${SEED}_${ITER_DIR}_$SLURM_JOB_ID
export TORCH_CHECKPOINT=$TORCH_CONVERT_ROOT/torch EXPORT_STAGE=$(dirname "$EXPORT_ROOT")/.$(basename "$EXPORT_ROOT").incomplete-$SLURM_JOB_ID
[[ "$(tr -d '[:space:]' < "$TRAIN_CHECKPOINT/latest_checkpointed_iteration.txt")" == "$TRAIN_ITERS" && -d $TRAIN_CHECKPOINT/$ITER_DIR ]]
export MEGATRON_ROOT TRANSFORMERS_ROOT HF_SAVER TRAIN_ITERS TOKENIZER_VIEW=$WORK_ROOT/tokenizer_sft_view TEXT_VOCAB_SIZE=131072
export CUDA_DEVICE_MAX_CONNECTIONS=1 PYTHONUNBUFFERED=1 ENV_SETUP="${ENV_SETUP:-}"
# shellcheck disable=SC2086
srun ${SRUN_ARGS:-} --cpus-per-task="$SLURM_CPUS_PER_TASK" bash -lc '
  set -euo pipefail
  eval "${ENV_SETUP}"
  export PYTHONPATH="${TRANSFORMERS_ROOT}/src:${MEGATRON_ROOT}"
  cd "$MEGATRON_ROOT"
  python -m torch.distributed.run --standalone --nproc-per-node=4 scripts/conversion/torchdist_2_torch.py \
    --bf16 --load "$TRAIN_CHECKPOINT" --ckpt-convert-save "$TORCH_CONVERT_ROOT" --ckpt-step "$TRAIN_ITERS"
  python tools/checkpoint/convert.py --model-type GPT --loader core --saver "$HF_SAVER" \
    --load-dir "$TORCH_CHECKPOINT" --save-dir "$EXPORT_STAGE" --hf-tokenizer "$TOKENIZER_VIEW" \
    --true-vocab-size "$TEXT_VOCAB_SIZE" --position-embedding-type rope --save-chat-model
  python - <<"PY"
import json, os
from pathlib import Path
from transformers import AutoConfig, AutoTokenizer
root = Path(os.environ["EXPORT_STAGE"])
c = json.loads((root / "config.json").read_text())
rp = c.get("rope_parameters") or c.get("rope_scaling") or {}
if "rope_scaling" not in c and rp:  # vLLM reads rope_scaling; keep both spellings
    c["rope_scaling"] = dict(rp); (root / "config.json").write_text(json.dumps(c, indent=2) + "\n")
tok = AutoTokenizer.from_pretrained(root)
assert len(tok) == 131072, len(tok)
s = tok.apply_chat_template([{"role": "user", "content": "hi"}], tokenize=False, add_generation_prompt=True)
AutoConfig.from_pretrained(root)
idx = json.loads((root / "model.safetensors.index.json").read_text())["weight_map"]
assert all((root / f).is_file() for f in set(idx.values()))
print("hf_export_validation=pass", root, "tensors", len(idx))
PY
'
mv "$EXPORT_STAGE" "$EXPORT_ROOT"
rm -rf "$TORCH_CONVERT_ROOT"
echo "EXPORT_COMPLETE arm=$ARM seed=$SEED export_root=$EXPORT_ROOT"
