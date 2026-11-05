#!/bin/bash
# Release directory -> corpus statistics -> Hugging Face dataset (swiss-ai/PersonaFactory layout: subsets `chats` and
# `persona_bank`, one train split each). See personafactory/release/README.md.
# The CPU steps read the whole corpus: they are submitted as jobs (scripts/slurm/eval_client.sbatch); only the upload
# runs where there is internet access. Cluster flags go into SBATCH_ARGS.
set -euo pipefail
: "${PF_OUT_DIR:?output root}" "${PF_LID_MODEL:?fastText lid.176 model}"
REL=${REL:-$PF_OUT_DIR/release_merged}
HF=${HF:-$PF_OUT_DIR/hf_release}
export PF_BANK=${PF_BANK:-$REL/persona_bank.jsonl}
SB="sbatch --parsable ${SBATCH_ARGS:-}"
client() { MODULE=$1 MODULE_ARGS=$2 $SB --job-name=$3 ${4:+--dependency=afterok:$4} scripts/slurm/eval_client.sbatch; }

# 1-3. persona-pair record set: assemble, emoji scrub, assistant swap (the swap needs the assistant regeneration of
#      the scrubbed set, see personafactory/assistant/README.md); 4. merge with the seed-pool set and post-process
#      (personafactory/postprocess/README.md). Skip with BUILD=0 when $REL already holds the final release.
if [[ ${BUILD:-0} == 1 ]]; then
  PAIRS=${PAIRS:-$PF_OUT_DIR/release_pairs}
  B=$(client personafactory.release.build_release "--accepted $PF_OUT_DIR/accepted --lid-model $PF_LID_MODEL --dedup --outdir $PAIRS --workers 60" pf-build)
  S=$(NOGLOB=1 client personafactory.release.scrub_emoji "--bank $PF_BANK --data $PAIRS/data/*.jsonl" pf-scrub "$B")
  echo "build=$B scrub=$S; run the assistant regeneration, then:"
  echo "  python -m personafactory.release.swap_assistant --release-dir $PAIRS --regen-dir $PF_OUT_DIR/assistant_regen_clean --model-personas personafactory/assistant/model_personas.json"
  echo "  python -m personafactory.release.merge_release --part pairs=$PAIRS/data --part seeds=$PF_OUT_DIR/seeds_run/final/data --bank $PF_BANK --out $REL"
  echo "  postprocess stages on $REL (personafactory/postprocess/README.md), then rerun this script with BUILD=0"
  exit 0
fi

# 5. corpus statistics (6. the full-corpus fidelity table: scripts/examples/evaluation.sh)
for s in duplicates emoji language_counts; do
  client personafactory.release.stats.$s "--release-dir $REL" pf-stats-$s > /dev/null
done
client personafactory.release.stats.register_stats "--release-dir $REL --lid-model $PF_LID_MODEL --workers 60" pf-stats-register > /dev/null
client personafactory.release.stats.corpus_distribution "--release-dir $REL --fig $PF_OUT_DIR/figures/fig_stacked_languages_regions.pdf" pf-stats-dist > /dev/null

# 7. Hugging Face build on the final post-processed release (CPU job) and dataset card
H=$(client personafactory.release.build_hf "--release-dir $REL --bank $PF_BANK --out $HF" pf-build-hf)
C=$(client personafactory.release.build_hf_cards "--hf-dir $HF" pf-hf-card "$H")
echo "build_hf=$H card=$C"
# after both jobs finish, on a machine with internet access and a Hugging Face write token:
echo "python -m personafactory.release.upload_hf --hf-dir $HF --repo ${HF_REPO:-<org>/<name>} [--private]"
