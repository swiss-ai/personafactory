#!/bin/bash
# Build the released persona bank (743,010 profiles, 599 locations in 177 countries) end to end on a Slurm cluster.
# Every step is one job submitted with a dependency on the step before it; the exact settings of the released bank
# are written out below (shards, seeds, temperatures, targets, judge and filter settings). Node counts only change
# the speed: every generator shard and judge shard resumes on any node count.
#
#   PF_DATA_DIR=./data SBATCH_ARGS="--account=... --partition=..." ENV_SETUP="source .venv/bin/activate" \
#   bash scripts/examples/persona_bank.sh
#
# Model weights: PF_MODEL_DIR/<hf-id> or the Hugging Face ids (see scripts/slurm/persona_bank_servers.sh).
# Compute nodes without internet need intfloat/multilingual-e5-large and google/gemma-4-31B-it in the HF cache.
set -euo pipefail
: "${PF_DATA_DIR:?}"
D=$PF_DATA_DIR/persona_bank
export ENV_SETUP=${ENV_SETUP:-true}
SB="sbatch --parsable ${SBATCH_ARGS:-}"
GEMMA=${PF_MODEL_DIR:+$PF_MODEL_DIR/}google/gemma-4-31B-it
mkdir -p "$D/base" "$D/extended/raw" "$D/extended_eu_sea/raw"
task() {   # task <dependency or ""> <extra sbatch args> <module> <args...>
  local dep=$1 extra=$2 mod=$3; shift 3
  STAGE=$mod STAGE_ARGS="$*" $SB ${dep:+--dependency=$dep} $extra scripts/slurm/persona_bank_task.sbatch
}

# ---------------------------------------------------------------------------------------------------------------
# 1. Base grid: 201 locations in 81 countries, 211 occupations. 80 shards per generator (location sharding),
#    --coverage_per_location 88 (x region weight x sub-region scale), temperature 0.8, max_tokens 8000,
#    seed 1000+i (Gemma), 2000+i (Ministral), 3000+i (GLM) for shard i.
# ---------------------------------------------------------------------------------------------------------------
B=""
for g in gemma:1000 ministral:2000 glm:3000; do
  j=$(GEN=${g%%:*} NSH=80 SEEDBASE=${g##*:} TEMP=0.8 OUT=$D/base GEN_ARGS="--coverage_per_location 88" \
      $SB --nodes=4 scripts/slurm/persona_bank_generate.sbatch)
  B="$B:$j"
done
# merge the generator shards into persona_bank_all.jsonl (102,520 profiles)
j=$(task "afterok$B" "" personafactory.persona_bank.merge_shards --data-dir "$D/base")
# judge: MiniMax-M2.5, two-pass repair, 120 strided shards of the one file, max_tokens 1600
j=$(JUDGE_INPUT=$D/base/persona_bank_all.jsonl JUDGE_OUTPUT=$D/base/persona_bank_all.validated.jsonl NSH=120 \
    JUDGE_ARGS="--max_tokens 1600" $SB --nodes=4 --dependency=afterok:$j scripts/slurm/persona_bank_judge.sbatch)
# keep-only bank (99,696 kept)
j=$(task "afterok:$j" "" personafactory.persona_bank.finalize_bank \
    --validated "$D/base/persona_bank_all.validated.jsonl" --clean "$D/base/persona_bank_all.clean.jsonl")
# emoji rebalancing: 5% of the bank keeps frequent/decorative emoji (Gemma 4 31B offline, TP4)
j=$(task "afterok:$j" "--gpus-per-node=4" personafactory.persona_bank.rebalance_emoji fix \
    --bank "$D/base/persona_bank_all.clean.jsonl" --out "$D/base/persona_bank.jsonl" \
    --log "$D/base/persona_emoji_changes.jsonl" --model "$GEMMA")
BASE=$(task "afterok:$j" "--gpus-per-node=4" personafactory.persona_bank.rebalance_emoji repair \
    --orig "$D/base/persona_bank_all.clean.jsonl" --bank "$D/base/persona_bank.jsonl" \
    --log "$D/base/persona_emoji_changes.jsonl" --model "$GEMMA")

# ---------------------------------------------------------------------------------------------------------------
# 2. Extended grid, all 13 target blocks: 599 locations in 177 countries, 575 occupations, all five additional
#    seed axes (settlement, education, life_stage, home_language, style; style seed: at most 1 of 7 keys may
#    differ). 590,000 raw profiles from per-country quotas, split evenly over the 3 generators; slot sharding;
#    max_tokens 4096. Gemma: 1920 shards, seed 31000+i, temperature 0.9; Ministral: 1152 shards, seed 32000+i,
#    temperature 0.8; GLM: 1536 shards, seed 33000+i, temperature 0.8.
# ---------------------------------------------------------------------------------------------------------------
X="--grid extended --target_total 590000 --n_generators 3 --shard_by slot"
E=""
for g in gemma:1920:31000:0.9:20 ministral:1152:32000:0.8:12 glm:1536:33000:0.8:16; do
  IFS=: read -r name nsh seed temp nodes <<< "$g"
  j=$(GEN=$name NSH=$nsh SEEDBASE=$seed TEMP=$temp OUT=$D/extended/raw GEN_ARGS="$X" \
      $SB --nodes="$nodes" scripts/slurm/persona_bank_generate.sbatch)
  E="$E:$j"
done
# judge: MiniMax-M2.5, two-pass repair, 2304 shards (sha1(id) split), max_tokens 3072 -> validated_all.jsonl
j=$(RUN=$D/extended NSH=2304 PREP=1 $SB --nodes=24 --dependency=afterany$E scripts/slurm/persona_bank_judge.sbatch)
# diversity filter against the base-grid bank: thresholds desc 0.96 / joint 0.95, caps 12 per location x occupation,
# 2 per full seed cell, 3% per typing-style combination (all defaults)
EXT=$(task "afterok:$j:$BASE" "--gpus-per-node=1" personafactory.persona_bank.diversity_filter \
    --input "$D/extended/validated_all.jsonl" --reference "$D/base/persona_bank.jsonl" \
    --output "$D/extended/diversity/kept.jsonl" --dropped "$D/extended/diversity/dropped.jsonl" \
    --report "$D/extended/diversity/report.json" --emb_cache "$D/extended/diversity/emb")

# ---------------------------------------------------------------------------------------------------------------
# 3. Extended grid, European blocks and Southeast Asia: 110,000 raw profiles (55,000 for the four European blocks,
#    55,000 for Southeast Asia, same country / sub-region split as above), seed axes education, home_language and
#    style. Gemma: 384 shards, seed 31500+i, temperature 0.9; Ministral: 384 shards, seed 32500+i, temperature 0.8;
#    GLM: 288 shards, seed 33500+i, temperature 0.8. (GEN_ARGS is passed through the environment; do not use
#    sbatch --export=GEN_ARGS=..., which would split it at the commas.)
# ---------------------------------------------------------------------------------------------------------------
X="--grid extended --target_total 110000 --n_generators 3 --shard_by slot --block_totals Europe:55000,Southeast_Asia:55000 --seed_axes education,home_language,style"
F=""
for g in gemma:384:31500:0.9:4 ministral:384:32500:0.8:4 glm:288:33500:0.8:3; do
  IFS=: read -r name nsh seed temp nodes <<< "$g"
  j=$(GEN=$name NSH=$nsh SEEDBASE=$seed TEMP=$temp OUT=$D/extended_eu_sea/raw GEN_ARGS="$X" \
      $SB --nodes="$nodes" scripts/slurm/persona_bank_generate.sbatch)
  F="$F:$j"
done
j=$(RUN=$D/extended_eu_sea NSH=768 PREP=1 $SB --nodes=8 --dependency=afterany$F scripts/slurm/persona_bank_judge.sbatch)
# diversity filter against the base-grid bank and the kept profiles of step 2 (same settings)
EU=$(task "afterok:$j:$EXT" "--gpus-per-node=1" personafactory.persona_bank.diversity_filter \
    --input "$D/extended_eu_sea/validated_all.jsonl" \
    --reference "$D/base/persona_bank.jsonl" "$D/extended/diversity/kept.jsonl" \
    --output "$D/extended_eu_sea/diversity/kept.jsonl" --dropped "$D/extended_eu_sea/diversity/dropped.jsonl" \
    --report "$D/extended_eu_sea/diversity/report.json" --emb_cache "$D/extended_eu_sea/diversity/emb")

# ---------------------------------------------------------------------------------------------------------------
# 4. Released bank: base-grid bank, then the kept profiles of steps 2 and 3 (seeded settlement / life_stage removed)
# ---------------------------------------------------------------------------------------------------------------
task "afterok:$EU" "" personafactory.persona_bank.assemble_bank --base "$D/base/persona_bank.jsonl" \
  --part "$D/extended/diversity/kept.jsonl" --part "$D/extended_eu_sea/diversity/kept.jsonl" \
  --dropped "$D/extended/diversity/dropped.jsonl" --dropped "$D/extended_eu_sea/diversity/dropped.jsonl" \
  --out "$PF_DATA_DIR/persona_bank.jsonl" --report "$PF_DATA_DIR/persona_bank_report.json"
