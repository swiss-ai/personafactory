#!/bin/bash
#SBATCH --job-name=pf-corpus-embed
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus-per-node=1
#SBATCH --time=02:00:00
#SBATCH --output=%x_%j.out
# MiniLM embeddings of the persona bank and the language-matched seed prompts (one GPU, ~15 min for 743k personas
# and 650k prompts). Submit from the repository root:
#   SEEDS=./data/seeds/shards ASSIGN=./outputs/assign_seeds sbatch scripts/slurm/corpus_embed.sbatch
set -euo pipefail
: "${SEEDS:?seed shard dir}" "${ASSIGN:?assignment dir}" "${PF_BANK:?persona bank}"
cd "${SLURM_SUBMIT_DIR:-.}"
eval "${ENV_SETUP:-true}"
export PYTHONPATH=$PWD${PYTHONPATH:+:$PYTHONPATH} TOKENIZERS_PARALLELISM=false
srun python -m personafactory.augmentation.embed_personas --bank "$PF_BANK" --seeds-dir "$SEEDS" --out-dir "$ASSIGN" \
  --dtype float16 --batch-size 1024
