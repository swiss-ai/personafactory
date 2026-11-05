#!/bin/bash
# Serve one model (judge or fine-tuned model) with `vllm serve` on one node and write its OpenAI-compatible URL
# (http://<ip>:<port>/v1) to $ENDPOINT_DIR/$SLURM_JOB_NAME.endpoint once /v1/models answers. Clients read that file
# (eval_client.sbatch replaces @URL@ with it). Runs until cancelled or the time limit.
#
#   sbatch --job-name=judge-qwen36 [$SBATCH_ARGS] scripts/slurm/eval_vllm_server.sbatch Qwen/Qwen3.6-35B-A3B 2 32768 \
#       --served-model-name qwen --reasoning-parser qwen3
#
# Args: MODEL [TP (4)] [MAX_MODEL_LEN (32768)] [extra vllm serve args...]. Optional env: PORT (8000),
# ENDPOINT_DIR ($PF_OUT_DIR/endpoints), ENV_SETUP (command run first, e.g. activating an env), SRUN_ARGS (e.g. a
# container). Cluster flags (account, partition, ...) go on the sbatch command line.
# The corpus judge (MiniMax-M2.5) is served with SGLang instead: see scripts/slurm/serve_models.sh (role `judge`).
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=4
#SBATCH --exclusive
#SBATCH --time=12:00:00
#SBATCH --output=%x_%j.out
set -euo pipefail
MODEL=${1:?model id or path}; TP=${2:-4}; MAXLEN=${3:-32768}; shift $(( $# < 3 ? $# : 3 ))
PORT=${PORT:-8000}
ENDPOINT_DIR=${ENDPOINT_DIR:-${PF_OUT_DIR:-$PWD}/endpoints}
mkdir -p "$ENDPOINT_DIR"
EP_FILE=$ENDPOINT_DIR/$SLURM_JOB_NAME.endpoint
rm -f "$EP_FILE"
IP=$(hostname -i | awk '{print $1}')
eval "${ENV_SETUP:-true}"
echo "node $(hostname) ip $IP model $MODEL tp $TP max_model_len $MAXLEN"
# shellcheck disable=SC2086
srun ${SRUN_ARGS:-} --overlap --ntasks=1 vllm serve "$MODEL" --host 0.0.0.0 --port "$PORT" \
    --tensor-parallel-size "$TP" --max-model-len "$MAXLEN" --gpu-memory-utilization 0.9 "$@" &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
for i in $(seq 1 360); do
  if curl -sf -m 5 --noproxy '*' "http://$IP:$PORT/v1/models" >/dev/null; then
    echo "http://$IP:$PORT/v1" > "$EP_FILE"; echo "healthy after $((i * 10))s -> $(cat "$EP_FILE")"; break
  fi
  kill -0 $SERVER_PID 2>/dev/null || { echo "vllm exited before becoming healthy" >&2; exit 1; }
  sleep 10
done
wait $SERVER_PID
