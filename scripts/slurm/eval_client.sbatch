#!/bin/bash
# Generic CPU job for one Python module of the package: judge clients, corpus statistics, judge-item preparation,
# aggregation. Model calls go to OpenAI-compatible endpoints (serve them first, e.g. with eval_vllm_server.sbatch or
# scripts/slurm/serve_models.sh); the client itself only needs CPUs, but a full-corpus pass should not run on a
# login node.
#
#   MODULE=personafactory.evaluation.corpus_judge.run_judge \
#   MODULE_ARGS="--shards $J/items/000.jsonl --outdir $J/results --url @URL@/chat/completions --model MiniMax-M2.5" \
#   URL=$PF_OUT_DIR/endpoints/judge-minimax.endpoint sbatch [$SBATCH_ARGS] scripts/slurm/eval_client.sbatch
#
# Placeholders in MODULE_ARGS: @URL@ and @URL2@ are replaced with URL / URL2 (a URL, a comma-separated list, or an
# endpoint file whose lines are joined with commas; the job waits up to WAIT_MIN minutes (60) for the file).
# MODULE_ARGS is split on whitespace. List-valued settings that contain commas (e.g. PAIRS=a:b,c:d) must be set in
# the environment before `sbatch` (inherited by default), never passed through `sbatch --export=...`, which splits
# its argument on commas.
# MODULE_ARGS globs are expanded by the shell; NOGLOB=1 passes them through literally (for modules that take a pattern).
# Optional env: PYTHON (python), NOGLOB, ENV_SETUP, PF_ROOT (repository root, default: submit dir).
#SBATCH --job-name=pf-client
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --time=12:00:00
#SBATCH --output=%x_%j.out
set -euo pipefail
: "${MODULE:?module to run, e.g. personafactory.release.stats.corpus_numbers}" "${MODULE_ARGS:?}"
PF_ROOT=${PF_ROOT:-$SLURM_SUBMIT_DIR}
cd "$PF_ROOT"
eval "${ENV_SETUP:-true}"
export PYTHONPATH=$PF_ROOT${PYTHONPATH:+:$PYTHONPATH}
resolve() {
  local v=$1
  if [[ -n "$v" && ! "$v" =~ ^https?:// ]]; then
    for _ in $(seq 1 $(( ${WAIT_MIN:-60} * 2 ))); do [[ -s "$v" ]] && break; sleep 30; done
    [[ -s "$v" ]] || { echo "no endpoint file $v" >&2; exit 1; }
    paste -sd, "$v"
  else
    echo "$v"
  fi
}
ARGS=${MODULE_ARGS//@URL@/$(resolve "${URL:-}")}
ARGS=${ARGS//@URL2@/$(resolve "${URL2:-}")}
echo "module $MODULE  started $(date)"
[[ ${NOGLOB:-0} == 1 ]] && set -f
# shellcheck disable=SC2086
srun "${PYTHON:-python}" -u -m "$MODULE" $ARGS
echo "finished $(date)"
