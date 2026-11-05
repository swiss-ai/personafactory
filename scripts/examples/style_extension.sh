#!/bin/bash
# Style extension of existing persona banks and its A/B evaluation (paper appendix: 2,140 Nemotron-Personas and
# PersonaHub records converted to the bank format; rewrites with the raw record (A), the converted background (B)
# and background + generated style layer (C); judged by MiniMax-M2.5, Qwen3.6-35B-A3B and Muse-Glimmer-30B).
#
#   PF_DATA_DIR=./data PF_OUT_DIR=./outputs PF_SEEDS_DIR=./data/seeds/shards PF_LID_MODEL=./data/lid.176.ftz \
#   MUSE_MODEL=/path/to/Muse-Glimmer-30B SBATCH_ARGS="--account=... --partition=..." bash scripts/examples/style_extension.sh
#
# Inputs: nvidia/Nemotron-Personas-{USA,UK,Singapore,Germany,France,Belgium,Japan,Korea,Vietnam,Brazil,El-Salvador,India}
# and proj-persona/PersonaHub in the local Hugging Face cache; augmentation seed shards <mode>-<source>-NNNN.jsonl
# (augmentation.prepare_seeds) in PF_SEEDS_DIR.
set -euo pipefail
: "${PF_DATA_DIR:?}" "${PF_OUT_DIR:?}" "${PF_SEEDS_DIR:?}" "${PF_LID_MODEL:?}"
RUN=$PF_DATA_DIR/style_extension
DIR=$PF_OUT_DIR/style_extension
export ENV_SETUP=${ENV_SETUP:-true} PF_LID_MODEL
SB="sbatch --parsable ${SBATCH_ARGS:-}"
mkdir -p "$RUN" "$DIR"
task() {   # task <dependency> <module> <args...>
  local dep=$1 mod=$2; shift 2
  STAGE=$mod STAGE_ARGS="$*" $SB --dependency="$dep" scripts/slurm/persona_bank_task.sbatch
}
judge() {  # judge <dependency> <array> <items subdir> <results subdir> <max tokens>
  DIR=$DIR ITEMS=$3 RESULTS=$4 MAXTOK=$5 $SB --dependency="$1" --array="$2" scripts/slurm/style_extension_judge.sbatch
}

# 1. Extension: 160 records per Nemotron-Personas country release (12) + 220 PersonaHub records = 2,140 sources;
#    Gemma 4 31B, temperature 0.8, fluency inferred first, typing-style seed sampled; 16 shards
j=$(RUN=$RUN NSH=16 PER_COUNTRY=160 PERSONAHUB=220 SEED=0 $SB --nodes=4 scripts/slurm/style_extension_generate.sbatch)
# 2. Judge like the bank (MiniMax-M2.5, two-pass repair, max_tokens 3072): 8 shards, 32 personas in flight each
j=$(RUN=$RUN NSH=8 PREP=1 JCONC=32 $SB --nodes=4 --dependency=afterok:$j scripts/slurm/persona_bank_judge.sbatch)
# 3. A/B inputs: judge-kept personas, one English seed each (WildChat / UltraChat / Nemotron in turn)
j=$(task "afterok:$j" personafactory.evaluation.style_extension.prep --run "$RUN" --seeds "$PF_SEEDS_DIR" --out "$DIR")
# 4. Generation, arms A / B / C (array 0-2)
j=$(DIR=$DIR $SB --array=0-2 --dependency=afterok:$j scripts/slurm/style_extension_ab.sbatch)
# 5. MiniMax-M2.5 judge: single items (8 shards, max_tokens 2048), then the unparsable ones again (16 shards, 6000)
j=$(task "afterok:$j" personafactory.evaluation.style_extension.items single --dir "$DIR")
j=$(judge "afterok:$j" 0-3 judge/items judge/results 2048)
j=$(task "afterok:$j" personafactory.evaluation.style_extension.items rejudge --dir "$DIR" --shards 16)
j=$(judge "afterok:$j" 0-7 judge/items_rejudge judge/results_rejudge 6000)
# 6. Both-orders pairwise items and the WildChat calibration (16 shards, max_tokens 6000)
j=$(task "afterok:$j" personafactory.evaluation.style_extension.items pairwise --dir "$DIR" --shards 16)
j=$(judge "afterok:$j" 0-7 judge/items_pair2 judge/results_pair2 6000)
j=$(task "afterok:$j" personafactory.evaluation.style_extension.aggregate --dir "$DIR")
# 7. External judges (Qwen3.6-35B-A3B-FP8, Muse-Glimmer-30B; max_tokens 8192) on calibration, identify and pairwise items
j=$(task "afterok:$j" personafactory.evaluation.style_extension.items external --dir "$DIR")
j=$(DIR=$DIR $SB --nodes=8 --dependency=afterok:$j scripts/slurm/style_extension_external_judge.sbatch)
# 8. Calibration figure (MiniMax-M2.5 verdicts)
task "afterok:$j" personafactory.evaluation.style_extension.plot --dir "$DIR"
