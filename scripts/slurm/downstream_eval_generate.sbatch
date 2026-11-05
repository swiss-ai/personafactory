#!/bin/bash
# Robustness, clean and WildChat generations of one fine-tuned model, then scoring: one vLLM replica per GPU (thinking
# disabled through chat_template_kwargs, max model length 8,192), downstream.eval.gen_eval over the styled evaluation
# file (greedy), downstream.eval.score (IFEval checkers from lm-evaluation-harness; MBPP code runs in a subprocess).
#
#   MODEL=$PF_MODEL_DIR/Apertus-v1.5-8B-base-PF-A2 TAG=A2 DATA=$PF_DATA_DIR/downstream_eval/styled_all.jsonl \
#   OUT_DIR=$PF_OUT_DIR/downstream/eval sbatch [$SBATCH_ARGS] scripts/slurm/downstream_eval_generate.sbatch
#
# Required env: MODEL (HF dir or id), TAG (result name), DATA (styled.jsonl or styled_all.jsonl), OUT_DIR.
# Optional env: GPUS (4), CONCURRENCY (512), ENV_SETUP, SRUN_ARGS (container for vLLM), PF_ROOT.
#SBATCH --job-name=pf-downstream-eval
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=4
#SBATCH --exclusive
#SBATCH --time=03:00:00
#SBATCH --output=%x_%j.out
set -uo pipefail
: "${MODEL:?}" "${TAG:?}" "${DATA:?}" "${OUT_DIR:?}"
PF_ROOT=${PF_ROOT:-$SLURM_SUBMIT_DIR}
cd "$PF_ROOT"
eval "${ENV_SETUP:-true}"
export PYTHONPATH=$PF_ROOT${PYTHONPATH:+:$PYTHONPATH} no_proxy="*" NO_PROXY="*"
OUT=$OUT_DIR/$TAG; mkdir -p "$OUT"
PIDS=""; URLS=()
for g in $(seq 0 $(( ${GPUS:-4} - 1 ))); do
  C=/tmp/pf-eval-$SLURM_JOB_ID-$g
  # shellcheck disable=SC2086
  srun ${SRUN_ARGS:-} --overlap --ntasks=1 bash -c "export CUDA_VISIBLE_DEVICES=$g XDG_CACHE_HOME=$C VLLM_CACHE_ROOT=$C/vllm TRITON_CACHE_DIR=$C/triton; \
    vllm serve $MODEL --served-model-name m --host 127.0.0.1 --port 800$g --max-model-len 8192 --gpu-memory-utilization 0.90 \
    --max-num-seqs 256 --chat-template-content-format string" > "$OUT/vllm_$g.log" 2>&1 &
  PIDS="$PIDS $!"; URLS+=("http://127.0.0.1:800$g/v1")
done
stop() { kill $PIDS 2>/dev/null; sleep 5; kill -9 $PIDS 2>/dev/null; }
trap stop EXIT
for t in $(seq 1 120); do
  ok=0; for u in "${URLS[@]}"; do curl -sf "${u%/v1}/health" >/dev/null 2>&1 && ok=$((ok + 1)); done
  [ $ok -eq ${#URLS[@]} ] && break
  sleep 15
done
H=(); for u in "${URLS[@]}"; do curl -sf "${u%/v1}/health" >/dev/null 2>&1 && H+=("$u"); done
echo "healthy ${#H[@]}/${#URLS[@]}"
[ ${#H[@]} -gt 0 ] || exit 1
python -u -m personafactory.downstream.eval.gen_eval --urls "${H[@]}" --model m --data "$DATA" --out "$OUT" --concurrency "${CONCURRENCY:-512}"
RC=$?
stop; trap - EXIT
python -u -m personafactory.downstream.eval.score --data "$DATA" --out "$OUT" > "$OUT/score.log" 2>&1 || RC=1
echo "== end $(date) rc $RC"; exit $RC
