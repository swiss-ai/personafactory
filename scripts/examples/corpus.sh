#!/bin/bash
# The released conversation corpus end to end, in the order the stages ran, with the released settings.
#
# Inputs:
#   PF_BANK         the full persona bank (743,010 profiles; persona_bank/ README)
#   PF_LID_MODEL    fastText lid.176.ftz
#   PAIRS_REL       the persona-pair part, built as in personafactory/release/README.md (build_release, emoji scrub,
#                   assistant swap): $PAIRS_REL/data/*.jsonl
#   PAIRS_DIR       its seed pairs (augmentation.prepare_pairs output), RESPONSES the source-response file of its
#                   assistant-regeneration inputs; both only serve to exclude seeds already used
#   SRC             local copies of the seed datasets:
#                     $SRC/ultrachat/train_*.jsonl                   stingning/ultrachat (full UltraChat)
#                     $SRC/nemotron/chat_if.jsonl                    nvidia/Nemotron-Instruction-Following-Chat-v1
#                                                                    (revision 83dcd3aded0d289b0bbc018d3f9af4c5dd4005df)
#                     $SRC/wildchat/data/train-*.parquet             allenai/WildChat-4.8M (86 files)
#   JUDGE_URL       OpenAI-compatible base URL (.../v1) of the API judge used by the optional quality analyses
#                   (deepseek-ai/DeepSeek-V4.1-Flash), PF_API_KEY its key
# CPU steps run through scripts/slurm/corpus_cpu.sbatch (or directly on a compute node, never on a login node);
# GPU steps are Slurm arrays of 2-node units (scripts/slurm/corpus_generate.sbatch, corpus_asst_regen.sbatch).
# Add your --account / --partition to SB. Every step resumes or rewrites its own output if rerun.
set -euo pipefail
: "${PF_BANK:?}" "${PF_LID_MODEL:?}" "${PAIRS_REL:?}" "${PAIRS_DIR:?}" "${RESPONSES:?}" "${SRC:?}"
D=${PF_DATA_DIR:-./data}
O=${PF_OUT_DIR:-./outputs}
SEEDS=$D/seeds/shards          # seed pool
ASSIGN=$O/assign_seeds         # persona / responder assignment
RUN=$O/seeds_run               # generation (gen/), corpus records (user/, final/), assistant inputs
REL=$O/release_merged          # merged release, all quality stages work in place here
Q=$O/lowres_quality
SB=${SB:-"sbatch --wait"}
cpu() { CMD="$*" $SB scripts/slurm/corpus_cpu.sbatch; }
export PF_BANK PF_LID_MODEL

# ------------------------------------------------------------------------------------------------ seeds and personas
# 1. Seed pool: full UltraChat (AI-disclaimer filter), Nemotron chat_if, WildChat-4.8M (non-toxic, non-redacted),
#    3 user turns / 1,000 user words / 45,000 characters, exact + near dedup of the first user message, seeds of the
#    persona-pair part excluded; (710,000 language-matched + 966,000 cross-lingual attempts) x 1.05 seeds, sources
#    filled in priority order UltraChat > Nemotron > WildChat.
cpu python -m personafactory.augmentation.prepare_seeds \
  --ultrachat "'$SRC/ultrachat/train_*.jsonl'" --nemotron "$SRC/nemotron/chat_if.jsonl" \
  --wildchat "'$SRC/wildchat/data/train-*.parquet'" \
  --exclude-release "'$PAIRS_REL/data/*.jsonl'" --exclude-pairs "$PAIRS_DIR" --exclude-responses "$RESPONSES" \
  --free-attempts 710000 --multilingual-attempts 966000 --margin 1.05 --work "$D/seeds" --procs 140
cpu python -m personafactory.common.lang_canon --bank "$PF_BANK" --out "$D/seeds/lang_report.json"   # optional report

# 2. MiniLM embeddings of the bank and the language-matched seed prompts (1 GPU; float16 storage, batch 1024)
SEEDS=$SEEDS ASSIGN=$ASSIGN $SB scripts/slurm/corpus_embed.sbatch

# 3. Assignment: language-matched seeds by location -> MiniLM (>= 0.15) -> language pool with at most 40 seeds per
#    persona; cross-lingual seeds over every persona with a non-English resolved target, without replacement;
#    Gemma / Ministral 50/50; held-out sample 4,002 language-matched + 6,000 cross-lingual seeds (equal per source).
OMP_NUM_THREADS=72 OPENBLAS_NUM_THREADS=72 cpu python -m personafactory.augmentation.select_personas \
  --bank "$PF_BANK" --seeds-dir "$SEEDS" --out-dir "$ASSIGN" --cap 40 --holdout-free 4002 --holdout-multilingual 6000 \
  --workers 140

# ------------------------------------------------------------------------------------------------ generation
# 4. User-side rewrite (+ literal translation first in the cross-lingual setting), responder answer, continuity loop,
#    MiniMax-M2.5 per-turn sanity gate. Generation T 0.3 (top_p 0.95, 4,096 tokens), judge T 0.1 (3,072 tokens),
#    adaptation 8,192 tokens, persona T 0.7, quirk p 0.25, 2 adaptations, 3 retries (run_augmentation.BASE_CONFIG).
#    44 units of 2 nodes, at most 24 at a time, 100 concurrent conversations per driver, 65,536-token contexts.
SEEDS=$SEEDS ASSIGN=$ASSIGN RUN=$RUN NU=44 EXCLUDE=$ASSIGN/holdout.txt \
  $SB --array=0-43%24 scripts/slurm/corpus_generate.sbatch

# 5. Corpus records: accepted conversations, text_language by LID, dedup of the same source in the same language,
#    200 shards; the assistant turns of this pass are final.
cpu python -m personafactory.augmentation.build_corpus --stage user --run "$RUN" --shards 200 --workers 128
cpu python -m personafactory.augmentation.build_corpus --stage final --run "$RUN"

# 6. Merge with the persona-pair part (the persona-pair part wins on the same source + language), 256 shards
cpu python -m personafactory.release.merge_release --part pairs="$PAIRS_REL/data" --part seeds="$RUN/final/data" \
  --bank "$PF_BANK" --out "$REL"

# ------------------------------------------------------------------------------------------------ quality stages
# 7. Low-resource metrics (and the judge sample, 20 per language); the API judge and report are analysis only.
cpu python -m personafactory.postprocess.lowres_quality --stage metrics --release-dir "$REL" --out "$Q" --workers 128 --n 20
if [ -n "${JUDGE_URL:-}" ]; then
  cpu python -m personafactory.postprocess.lowres_quality --stage judge --out "$Q" --judge-url "$JUDGE_URL" \
    --model deepseek-ai/DeepSeek-V4.1-Flash --tag dsv41flash --rpm 13 --threads 16
  cpu python -m personafactory.postprocess.lowres_quality --stage report --out "$Q"
fi

# 8. Low-resource filter (data/ -> data_unfiltered/, filtered data/)
cpu python -m personafactory.postprocess.apply_lowres_filter --release-dir "$REL" --quality-dir "$Q"

# 9. Regenerate the conversations dropped only for their Ministral responder end to end with Gemma (4 units)
R1=$O/regen_lowres
cpu python -m personafactory.postprocess.lowres_regen_prep --source removed --release-dir "$REL" --seeds-dir "$SEEDS" \
  --assign-dir "$ASSIGN" --run "$R1" --units 4
PAIRS_DIR=$R1/pairs ASSIGN=$ASSIGN RUN=$R1 RESPONDER=gemma $SB --array=0-3 --time=04:00:00 scripts/slurm/corpus_generate.sbatch
cpu python -m personafactory.augmentation.build_corpus --stage user --run "$R1" --shards 8 --workers 64
cpu python -m personafactory.augmentation.build_corpus --stage final --run "$R1"
cpu python -m personafactory.postprocess.finalize_lowres_regen --mode append --release-dir "$REL" --run "$R1"
if [ -n "${JUDGE_URL:-}" ]; then   # optional paired check against the first judge pass
  cpu python -m personafactory.postprocess.judge_lowres_regen --stage sample --release-dir "$REL" \
    --first "$Q/judge_dsv41flash.jsonl" --out "$Q/regen" --n 10
  cpu python -m personafactory.postprocess.lowres_quality --stage judge --out "$Q/regen" --judge-url "$JUDGE_URL" \
    --model deepseek-ai/DeepSeek-V4.1-Flash --tag dsv41flash --rpm 13 --threads 16
  cpu python -m personafactory.postprocess.judge_lowres_regen --stage compare --first "$Q/judge_dsv41flash.jsonl" --out "$Q/regen"
fi

# 10. Regenerate the remaining low-resource cross-lingual Ministral conversations (Uzbek, Nepali) with Gemma, in place
R2=$O/regen_lowres_kept
cpu python -m personafactory.postprocess.lowres_regen_prep --source kept --release-dir "$REL" --seeds-dir "$SEEDS" \
  --assign-dir "$ASSIGN" --run "$R2" --units 2
PAIRS_DIR=$R2/pairs ASSIGN=$ASSIGN RUN=$R2 RESPONDER=gemma $SB --array=0-1 --time=04:00:00 scripts/slurm/corpus_generate.sbatch
cpu python -m personafactory.augmentation.build_corpus --stage user --run "$R2" --shards 4 --workers 64
cpu python -m personafactory.augmentation.build_corpus --stage final --run "$R2"
cpu python -m personafactory.postprocess.finalize_lowres_regen --mode replace --release-dir "$REL" --run "$R2"

# 11. Assistant side of the high-resource cross-lingual Ministral conversations regenerated with Gemma (user turns
#     fixed, user persona system prompt, sanity gate); 40 tasks, 4 units at a time.
A=$O/asst_regen
cpu python -m personafactory.postprocess.asst_regen_prep --release-dir "$REL" --assistant-input "$RUN/assistant_input" --out "$A"
IN=$A/input OUT=$A NT=40 $SB --array=0-39%4 scripts/slurm/corpus_asst_regen.sbatch
if [ -n "${JUDGE_URL:-}" ]; then   # optional paired check (before the swap: it reads the Ministral version)
  cpu python -m personafactory.postprocess.asst_regen_judge --stage sample --release-dir "$REL" --targets "$A/targets.tsv" \
    --regen-dir "$A/user_persona" --out "$A/judge" --n 20
  cpu python -m personafactory.postprocess.lowres_quality --stage judge --out "$A/judge" --judge-url "$JUDGE_URL" \
    --model deepseek-ai/DeepSeek-V4.1-Flash --tag dsv41flash --rpm 13 --threads 16
  cpu python -m personafactory.postprocess.asst_regen_judge --stage compare --out "$A/judge"
fi
cpu python -m personafactory.postprocess.finalize_asst_regen --release-dir "$REL" --regen-dir "$A/user_persona"

# 12. Drop low-resource conversations whose user turns barely use the expected script (< 10%)
cpu python -m personafactory.postprocess.drop_lowscript --release-dir "$REL" --quality-dir "$Q"

# 13. Corpus judge on 25,000 random seed-pool conversations (MiniMax-M2.5, per user turn: intent + style)
J=$O/judge_sample
cpu python -m personafactory.postprocess.judge_sample_prep --release-dir "$REL" --gen "$RUN/gen" --out "$J" --n 25000 --shards 8
JUDGE_DIR=$J $SB --array=0-3 scripts/slurm/corpus_judge.sbatch

# 14. Drop the cross-lingual seed-pool conversations whose text is Russian
cpu python -m personafactory.postprocess.drop_crosslingual_russian --release-dir "$REL"

# 15. Corpus statistics and the judge table (conversations still in the release)
cpu python -m personafactory.postprocess.corpus_stats --release-dir "$REL" --gen "$RUN/gen"
cpu python -m personafactory.postprocess.judge_sample_agg --judge-dir "$J" --release-dir "$REL"
# Released (paper, Table 3): 1,237,976 conversations (wildchat 718,365, ultrachat 310,798, nemotron 208,813;
# language_matched 685,209, cross_lingual 552,767; Gemma-4-31B-it 905,661, Ministral-3-14B 332,315), 2,387,392 user turns.
# The paper's count includes a final rule-based filter that drops 4,785 conversations in which a user turn restates the
# instructions of the rewrite prompt; that filter is not part of this script.
# Figure and further statistics: personafactory/release/README.md (release.stats.*) on $REL.
