#!/bin/bash
#SBATCH --job-name=pf-augment
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=4
#SBATCH --exclusive
#SBATCH --time=12:00:00
# Persona-pair set (augmentation.prepare_pairs input): one node with Gemma + Ministral (the two rewriter/responder
# models) and one node with the judge, one driver per mode. Submit from the repository root.
# For the seed pool use scripts/slurm/corpus_generate.sbatch. See personafactory/augmentation/README.md.
set -uo pipefail
cd "${SLURM_SUBMIT_DIR:-.}"
export PYTHONPATH=$PWD${PYTHONPATH:+:$PYTHONPATH}
export PF_MAX_MODEL_LEN=${PF_MAX_MODEL_LEN:-32768} PF_JUDGE_CONTEXT=${PF_JUDGE_CONTEXT:-32768}
source scripts/slurm/serve_models.sh gemma ministral judge || { stop_servers; exit 1; }
for mode in free multilingual; do
  python -m personafactory.augmentation.run_augmentation --input-kind pairs --pairs data/pairs/*.jsonl --mode $mode \
    --assign-dir outputs/assign --bank "$PF_BANK" --lid-model "$PF_LID_MODEL" --outdir outputs/generated \
    --gemma "$GEMMA_URL" --ministral "$MINISTRAL_URL" --minimax "$JUDGE_URL" --concurrency 100 &
done
wait
stop_servers
