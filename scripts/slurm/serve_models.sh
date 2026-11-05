#!/bin/bash
# Start the model servers used by the pipeline on the current node(s) and export their endpoints.
# Source it inside an allocation (sbatch/salloc), e.g.:  source scripts/slurm/serve_models.sh gemma ministral judge
#
# Roles (one per invocation argument; each takes the GPUs listed below on one node):
#   gemma      google/gemma-4-31B-it                   vLLM, tensor parallel 2 (GPUs 0,1), port 8000
#   ministral  mistralai/Ministral-3-14B-Instruct-2512 vLLM, tensor parallel 2 (GPUs 2,3), port 8001
#   judge      MiniMaxAI/MiniMax-M2.5                  SGLang, TP 4 / EP 4 (all 4 GPUs of its own node), port 30000
# gemma + ministral share one 4-GPU node; the judge needs a node of its own. Typical unit: 2 nodes,
# "gemma ministral judge". Several units can be started by repeating the roles (node i, i+1, ...).
#
# Context lengths: PF_MAX_MODEL_LEN (responders, default 65536) and PF_JUDGE_CONTEXT (judge, default 65536).
# The seed-pool generation and regenerations used 65536 for all three; the persona-pair set used 32768, and the
# corpus judge (evaluation.corpus_judge.run_judge, postprocess.judge_sample_prep items) 16384 for the judge.
# Model weights are read from $PF_MODEL_DIR/<hf-id> (set PF_MODEL_DIR to a local model cache or leave it unset to
# let vLLM/SGLang resolve the Hugging Face ids). Logs go to $PF_LOG_DIR (default ./logs).
# Optional: PF_SRUN_ARGS (extra srun arguments, e.g. a container environment).
# Exported: GEMMA_URL, MINISTRAL_URL, JUDGE_URL (comma-separated lists when several replicas run).
# Stop everything with: stop_servers
set -u
M=${PF_MODEL_DIR:+$PF_MODEL_DIR/}
LOGD=${PF_LOG_DIR:-./logs}; mkdir -p "$LOGD"
LEN=${PF_MAX_MODEL_LEN:-65536}
JLEN=${PF_JUDGE_CONTEXT:-65536}
SRUN="srun --overlap --nodes=1 --ntasks=1 ${PF_SRUN_ARGS:-}"
TAG=${SLURM_JOB_ID:-local}${SLURM_ARRAY_TASK_ID:+_$SLURM_ARRAY_TASK_ID}
CACHE=${PF_SERVER_CACHE:-/tmp/pf-$TAG}   # per-job compile caches on node-local disk
mapfile -t NODES < <(scontrol show hostnames "${SLURM_JOB_NODELIST:-$(hostname)}")
SRV_PIDS=""; CHECKS=(); GEMMA_URL=""; MINISTRAL_URL=""; JUDGE_URL=""
caches() { echo "mkdir -p $CACHE/$1; export XDG_CACHE_HOME=$CACHE/$1 VLLM_CACHE_ROOT=$CACHE/$1/vllm TRITON_CACHE_DIR=$CACHE/$1/triton TORCHINDUCTOR_CACHE_DIR=$CACHE/$1/inductor CUDA_CACHE_PATH=$CACHE/$1/cuda"; }
i=0
for role in "$@"; do
  case $role in
    gemma)
      n=${NODES[$i]}
      $SRUN --nodelist=$n bash -c "$(caches g$i); export CUDA_VISIBLE_DEVICES=0,1 RAY_CGRAPH_get_timeout=1800; vllm serve ${M}google/gemma-4-31B-it --served-model-name gemma --host 0.0.0.0 --port 8000 --tensor-parallel-size 2 --max-model-len $LEN --gpu-memory-utilization 0.90 --max-num-seqs 128" > $LOGD/gemma_${TAG}_$n.log 2>&1 &
      SRV_PIDS="$SRV_PIDS $!"; GEMMA_URL="${GEMMA_URL:+$GEMMA_URL,}http://$n:8000/v1"; CHECKS+=(http://$n:8000/health) ;;
    ministral)
      n=${NODES[$i]}
      $SRUN --nodelist=$n bash -c "$(caches m$i); export CUDA_VISIBLE_DEVICES=2,3; vllm serve ${M}mistralai/Ministral-3-14B-Instruct-2512 --served-model-name ministral --host 0.0.0.0 --port 8001 --tensor-parallel-size 2 --max-model-len $LEN --gpu-memory-utilization 0.90 --max-num-seqs 128 --tokenizer_mode mistral --load_format mistral --config_format mistral" > $LOGD/ministral_${TAG}_$n.log 2>&1 &
      SRV_PIDS="$SRV_PIDS $!"; MINISTRAL_URL="${MINISTRAL_URL:+$MINISTRAL_URL,}http://$n:8001/v1"; CHECKS+=(http://$n:8001/health)
      i=$((i + 1)) ;;   # gemma + ministral share one 4-GPU node
    judge)
      [ "$i" -lt "${#NODES[@]}" ] || { echo "no node left for the judge"; break; }
      n=${NODES[$i]}
      $SRUN --nodelist=$n bash -c "$(caches x$i); export SGL_ENABLE_JIT_DEEPGEMM=false SGLANG_ENABLE_JIT_DEEPGEMM=false; python3 -m sglang.launch_server --model-path ${M}MiniMaxAI/MiniMax-M2.5 --served-model-name MiniMax-M2.5 --host 0.0.0.0 --port 30000 --tp-size 4 --ep-size 4 --reasoning-parser minimax-append-think --trust-remote-code --mem-fraction-static 0.88 --context-length $JLEN --max-running-requests 128 --cuda-graph-max-bs 128" > $LOGD/judge_${TAG}_$n.log 2>&1 &
      SRV_PIDS="$SRV_PIDS $!"; JUDGE_URL="${JUDGE_URL:+$JUDGE_URL,}http://$n:30000/v1"; CHECKS+=(http://$n:30000/health)
      i=$((i + 1)) ;;
    *) echo "unknown role $role" ;;
  esac
done
export GEMMA_URL MINISTRAL_URL JUDGE_URL
stop_servers() { kill $SRV_PIDS 2>/dev/null; sleep 5; kill -9 $SRV_PIDS 2>/dev/null; }
up=0
for t in $(seq 1 240); do   # up to 40 min (first start compiles kernels)
  up=0; for c in "${CHECKS[@]}"; do curl -sf "$c" >/dev/null 2>&1 && up=$((up + 1)); done
  [ $up -eq ${#CHECKS[@]} ] && break
  for p in $SRV_PIDS; do kill -0 $p 2>/dev/null || { echo "a server exited early, see $LOGD"; break 2; }; done
  sleep 10
done
echo "servers up: $up / ${#CHECKS[@]}  gemma=$GEMMA_URL ministral=$MINISTRAL_URL judge=$JUDGE_URL"
[ $up -eq ${#CHECKS[@]} ]
