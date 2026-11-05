#!/bin/bash
#SBATCH --job-name=pf-corpus-judge
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus-per-node=4
#SBATCH --exclusive
#SBATCH --time=06:00:00
#SBATCH --output=%x_%A_%a.out
# Corpus judge on the sampled items (postprocess.judge_sample_prep): one MiniMax-M2.5 node per array task, two item
# shards each (8 shards -> --array=0-3). Resumable.
#   JUDGE_DIR=./outputs/judge_sample sbatch --array=0-3 scripts/slurm/corpus_judge.sbatch
set -uo pipefail
: "${JUDGE_DIR:?}"
cd "${SLURM_SUBMIT_DIR:-.}"
eval "${ENV_SETUP:-true}"
export PYTHONPATH=$PWD${PYTHONPATH:+:$PYTHONPATH} PF_LOG_DIR=${PF_LOG_DIR:-$JUDGE_DIR/logs} PF_JUDGE_CONTEXT=${PF_JUDGE_CONTEXT:-16384}
i=${SLURM_ARRAY_TASK_ID:-0}
SH="$JUDGE_DIR/items/$(printf %03d $((2*i))).jsonl $JUDGE_DIR/items/$(printf %03d $((2*i+1))).jsonl"
source scripts/slurm/serve_models.sh judge || { stop_servers; exit 1; }
python -u -m personafactory.evaluation.corpus_judge.run_judge --shards $SH --outdir "$JUDGE_DIR/results" \
  --url "$JUDGE_URL/chat/completions" --model MiniMax-M2.5 --concurrency 96
RC=$?
stop_servers
exit $RC
