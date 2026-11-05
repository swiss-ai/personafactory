#!/bin/bash
#SBATCH --job-name=pf-corpus-asst
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=4
#SBATCH --exclusive
#SBATCH --requeue
#SBATCH --time=06:00:00
#SBATCH --output=%x_%A_%a.out
# Assistant-side regeneration with Gemma (assistant.regenerate_assistant --stage user_persona: user turns fixed,
# user persona system prompt, no model persona, continuity loop + sanity gate) on the postprocess.asst_regen_prep
# inputs. Task k of NT takes the input shards with (line number - 1) % NT == k; outputs are resumable.
#   IN=./outputs/asst_regen/input OUT=./outputs/asst_regen NT=40 sbatch --array=0-39%4 scripts/slurm/corpus_asst_regen.sbatch
set -uo pipefail
: "${IN:?}" "${OUT:?}" "${PF_BANK:?}"
cd "${SLURM_SUBMIT_DIR:-.}"
eval "${ENV_SETUP:-true}"
export PYTHONPATH=$PWD${PYTHONPATH:+:$PYTHONPATH} PF_LOG_DIR=${PF_LOG_DIR:-$OUT/logs}
K=${SLURM_ARRAY_TASK_ID:-0}
NT=${NT:-${SLURM_ARRAY_TASK_COUNT:-1}}
mkdir -p "$PF_LOG_DIR"
SH=$(ls "$IN" | awk -v i=$K -v n=$NT '(NR - 1) % n == i')
SH=$(for s in $SH; do [ -s "$IN/$s" ] && echo $s; done)
echo "task $K/$NT: $(echo $SH | wc -w) shards"
[ -n "$SH" ] || { echo "exit 0"; exit 0; }
source scripts/slurm/serve_models.sh gemma ministral judge || { stop_servers; exit 1; }
python -u -m personafactory.assistant.regenerate_assistant --stage user_persona --input-dir "$IN" --shards $SH \
  --out-dir "$OUT" --bank "$PF_BANK" --gemma "$GEMMA_URL" --ministral "$MINISTRAL_URL" --minimax "$JUDGE_URL" \
  --concurrency 150 >> "$PF_LOG_DIR/asst_regen_$K.log" 2>&1
RC=$?
stop_servers
echo "exit $RC"; exit $RC
