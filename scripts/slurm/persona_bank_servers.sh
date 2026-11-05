#!/bin/bash
# Start the model servers of the persona-bank and style-extension jobs on the nodes of the current allocation
# and export their endpoints. Source it inside an allocation, one role per node in node order:
#
#   ROLES="gemma gemma minimax" source scripts/slurm/persona_bank_servers.sh   ...   stop_servers
#
# Roles (each takes one 4-GPU node):
#   gemma      google/gemma-4-31B-it                    vLLM, 2 replicas x TP2, ports 8000/8001
#   ministral  mistralai/Ministral-3-14B-Instruct-2512  vLLM, 4 replicas x TP1 (mistral formats), ports 8000-8003
#   glm        zai-org/GLM-4.7-Flash                    SGLang, TP4, port 30000
#   minimax    MiniMaxAI/MiniMax-M2.5                   SGLang, TP4 / EP4, reasoning parser, port 30000
#   qwen       Qwen/Qwen3.6-35B-A3B-FP8                 vLLM, 2 replicas x TP2, qwen3 reasoning parser, ports 8000/8001
#   muse       Muse-Glimmer-30B ($MUSE_MODEL)           vLLM (a build that supports the model), 2 x TP2, ports 8000/8001
# Served model names are the Hugging Face ids, unless overridden with GEMMA_SERVED, MINISTRAL_SERVED, GLM_SERVED,
# MINIMAX_SERVED, QWEN_SERVED, MUSE_SERVED (generate_bank.py stores the served name as generator_model).
#
# Env: PF_MODEL_DIR (local model directory holding <hf-id>/; unset = let vLLM / SGLang resolve the ids),
#      PF_LOG_DIR (server logs, default ./logs/servers), MAX_MODEL_LEN (default 32768; 65536 for the style A/B
#      generation), MINIMAX_CONTEXT (default MAX_MODEL_LEN), SRUN_ARGS (extra srun flags, e.g. a container),
#      SERVER_SETUP (command run before each server, e.g. activating the serving environment).
# Exports: GEMMA_URLS MINISTRAL_URLS GLM_URLS MINIMAX_URLS QWEN_URLS MUSE_URLS (space-separated http://host:port/v1,
#      healthy servers only), SRV_PIDS; defines stop_servers.
: "${ROLES:?set ROLES, one role per node}"
M=${PF_MODEL_DIR:+$PF_MODEL_DIR/}
LOGD=${PF_LOG_DIR:-./logs/servers}; mkdir -p "$LOGD"
LEN=${MAX_MODEL_LEN:-32768}
mapfile -t NODES < <(scontrol show hostnames "$SLURM_JOB_NODELIST")
SRV_PIDS=""; CHECKS=""; GEMMA_URLS=""; MINISTRAL_URLS=""; GLM_URLS=""; MINIMAX_URLS=""; QWEN_URLS=""; MUSE_URLS=""
_launch() {  # node tag gpus command
  # shellcheck disable=SC2086
  srun --overlap --nodes=1 --ntasks=1 --nodelist=$1 ${SRUN_ARGS:-} bash -c \
    "${SERVER_SETUP:-true}; export CUDA_VISIBLE_DEVICES=$3; $4" > "$LOGD/${2}_${SLURM_JOB_ID}.log" 2>&1 &
  SRV_PIDS="$SRV_PIDS $!"
}
_i=0
for role in $ROLES; do
  n=${NODES[$_i]}
  case $role in
    gemma|qwen|muse)
      case $role in
        gemma) path=${M}google/gemma-4-31B-it; name=${GEMMA_SERVED:-google/gemma-4-31B-it}; extra="--enable-prefix-caching" ;;
        qwen)  path=${M}Qwen/Qwen3.6-35B-A3B-FP8; name=${QWEN_SERVED:-Qwen/Qwen3.6-35B-A3B-FP8}
               extra="--reasoning-parser qwen3 --limit-mm-per-prompt '{\"image\":0,\"video\":0}'" ;;
        muse)  path=${MUSE_MODEL:?set MUSE_MODEL to the Muse-Glimmer-30B weights}; name=${MUSE_SERVED:-Muse-Glimmer-30B}
               extra="--limit-mm-per-prompt '{\"image\":0}'" ;;
      esac
      for r in 0 1; do
        _launch "$n" "${role}_${n}_$r" "$([ $r = 0 ] && echo 0,1 || echo 2,3)" \
          "vllm serve $path --served-model-name $name --host 0.0.0.0 --port 800$r --tensor-parallel-size 2 --max-model-len $LEN --gpu-memory-utilization 0.90 --max-num-seqs 128 $extra"
        u="http://$n:800$r/v1"; CHECKS="$CHECKS http://$n:800$r/health"
        case $role in gemma) GEMMA_URLS="$GEMMA_URLS $u" ;; qwen) QWEN_URLS="$QWEN_URLS $u" ;; muse) MUSE_URLS="$MUSE_URLS $u" ;; esac
      done ;;
    ministral)
      for r in 0 1 2 3; do
        _launch "$n" "ministral_${n}_$r" "$r" \
          "vllm serve ${M}mistralai/Ministral-3-14B-Instruct-2512 --served-model-name ${MINISTRAL_SERVED:-mistralai/Ministral-3-14B-Instruct-2512} --host 0.0.0.0 --port 800$r --tensor-parallel-size 1 --max-model-len $LEN --gpu-memory-utilization 0.90 --max-num-seqs 128 --enable-prefix-caching --tokenizer_mode mistral --load_format mistral --config_format mistral"
        MINISTRAL_URLS="$MINISTRAL_URLS http://$n:800$r/v1"; CHECKS="$CHECKS http://$n:800$r/health"
      done ;;
    glm)
      _launch "$n" "glm_$n" 0,1,2,3 \
        "python3 -m sglang.launch_server --model-path ${M}zai-org/GLM-4.7-Flash --served-model-name ${GLM_SERVED:-zai-org/GLM-4.7-Flash} --host 0.0.0.0 --port 30000 --tp-size 4 --context-length $LEN --mem-fraction-static 0.85 --max-running-requests 128"
      GLM_URLS="$GLM_URLS http://$n:30000/v1"; CHECKS="$CHECKS http://$n:30000/health" ;;
    minimax)
      _launch "$n" "minimax_$n" 0,1,2,3 \
        "python3 -m sglang.launch_server --model-path ${M}MiniMaxAI/MiniMax-M2.5 --served-model-name ${MINIMAX_SERVED:-MiniMaxAI/MiniMax-M2.5} --host 0.0.0.0 --port 30000 --tp-size 4 --ep-size 4 --reasoning-parser minimax-append-think --trust-remote-code --mem-fraction-static 0.88 --context-length ${MINIMAX_CONTEXT:-$LEN} --max-running-requests 128 --cuda-graph-max-bs 128"
      MINIMAX_URLS="$MINIMAX_URLS http://$n:30000/v1"; CHECKS="$CHECKS http://$n:30000/health" ;;
    *) echo "unknown role $role" ;;
  esac
  _i=$((_i + 1))
done
stop_servers() { kill $SRV_PIDS 2>/dev/null; sleep 5; kill -9 $SRV_PIDS 2>/dev/null; }
_healthy() { local out=""; for u in $1; do curl -sf --max-time 5 "${u%/v1}/health" >/dev/null 2>&1 && out="$out $u"; done; echo $out; }
_t0=$(date +%s)
for _t in $(seq 1 270); do   # up to 45 min
  ok=0; tot=0
  for c in $CHECKS; do tot=$((tot + 1)); curl -sf --max-time 5 "$c" >/dev/null 2>&1 && ok=$((ok + 1)); done
  [ "$ok" -eq "$tot" ] && break
  sleep 10
done
echo "servers healthy $ok/$tot after $(( $(date +%s) - _t0 ))s"
GEMMA_URLS=$(_healthy "$GEMMA_URLS"); MINISTRAL_URLS=$(_healthy "$MINISTRAL_URLS"); GLM_URLS=$(_healthy "$GLM_URLS")
MINIMAX_URLS=$(_healthy "$MINIMAX_URLS"); QWEN_URLS=$(_healthy "$QWEN_URLS"); MUSE_URLS=$(_healthy "$MUSE_URLS")
export GEMMA_URLS MINISTRAL_URLS GLM_URLS MINIMAX_URLS QWEN_URLS MUSE_URLS SRV_PIDS
echo "gemma=[$GEMMA_URLS] ministral=[$MINISTRAL_URLS] glm=[$GLM_URLS] minimax=[$MINIMAX_URLS] qwen=[$QWEN_URLS] muse=[$MUSE_URLS]"
