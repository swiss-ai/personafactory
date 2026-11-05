#!/bin/bash
# One persona-bank step on one node: python -m $STAGE $STAGE_ARGS. Used for the steps that do not talk to model
# servers: merge_shards, finalize_bank, judge_shards, strip_surrogates and assemble_bank (CPU), and
# diversity_filter (one GPU, multilingual-e5-large) and rebalance_emoji (offline vLLM, 4 GPUs).
#
#   STAGE=personafactory.persona_bank.diversity_filter \
#   STAGE_ARGS="--input .../validated_all.jsonl --reference .../persona_bank.jsonl --output ... --dropped ... --report ..." \
#   sbatch [--gpus-per-node=4 --account=... --partition=...] scripts/slurm/persona_bank_task.sbatch
#
# Env: STAGE, STAGE_ARGS, optional PF_ROOT (repo root, default submit dir), PYTHON, ENV_SETUP (command run first,
#      e.g. activating the environment). Compute nodes without internet need the embedding / rewrite models in the
#      local Hugging Face cache (HF_HOME, HF_HUB_OFFLINE=1).
#SBATCH --job-name=pf-bank-task
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --exclusive
#SBATCH --time=03:00:00
#SBATCH --output=%x_%j.out
set -euo pipefail
: "${STAGE:?module, e.g. personafactory.persona_bank.assemble_bank}" "${STAGE_ARGS:?}"
PF_ROOT=${PF_ROOT:-$SLURM_SUBMIT_DIR}
cd "$PF_ROOT"
eval "${ENV_SETUP:-true}"
export PYTHONPATH=$PF_ROOT${PYTHONPATH:+:$PYTHONPATH}
echo "stage $STAGE started $(date)"
# shellcheck disable=SC2086
srun "${PYTHON:-python}" -u -m "$STAGE" $STAGE_ARGS
echo "finished $(date)"
