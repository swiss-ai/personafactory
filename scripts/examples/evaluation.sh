#!/bin/bash
# Corpus-scale evaluation of the release: full-corpus judge-free fidelity table, LLM judge on the fully scored subset,
# corpus-wide judge estimate. See personafactory/evaluation/README.md. Cluster flags go into SBATCH_ARGS.
set -euo pipefail
: "${PF_OUT_DIR:?output root}"
REL=${REL:-$PF_OUT_DIR/release_merged}
J=${J:-$PF_OUT_DIR/corpus_judge}
SB="sbatch --parsable ${SBATCH_ARGS:-}"

# 1. full-corpus judge-free fidelity table: 4 CPU statistics + LaBSE over every user turn (one GPU node).
#    Source turns from the pipeline output records and/or the seed shards; PF_LABSE_MODEL = local LaBSE snapshot.
F=$(REL=$REL LABSE_ARGS=${LABSE_ARGS:-"--originals $PF_OUT_DIR/accepted"} $SB scripts/slurm/eval_fidelity.sbatch)
echo "fidelity=$F -> $REL/{corpus_numbers,entity_integrity,style_adherence,length_by_tendency,labse_full}.json"

# 2. LLM judge (MiniMax-M2.5) on every user turn of the fully scored subset: items, judge, aggregate
P=$(MODULE=personafactory.evaluation.corpus_judge.prep_items \
    MODULE_ARGS="--release-dir $REL --bank $REL/persona_bank.jsonl --originals $PF_OUT_DIR/accepted --out-dir $J --shards 64" \
    $SB --job-name=pf-judge-prep scripts/slurm/eval_client.sbatch)
#    one MiniMax-M2.5 node per array task, two item shards each (scripts/slurm/corpus_judge.sbatch, 64 shards -> 32 tasks)
JJ=$(JUDGE_DIR=$J $SB --array=0-31 --dependency=afterok:$P scripts/slurm/corpus_judge.sbatch)
A=$(MODULE=personafactory.evaluation.corpus_judge.aggregate MODULE_ARGS="--judge-dir $J --out $J/corpus_judge.json" \
    $SB --job-name=pf-judge-agg --dependency=afterok:$JJ scripts/slurm/eval_client.sbatch)
echo "judge prep=$P judge=$JJ aggregate=$A"

# 3. random sample of the remaining conversations: postprocess.judge_sample_prep -> corpus_judge.sbatch ->
#    postprocess.judge_sample_agg (personafactory/postprocess/README.md), writing $REL/judge_sample.json. Then:
cat <<EOC
python -m personafactory.evaluation.corpus_judge.estimate --scored $J/corpus_judge.json \\
    --sample $REL/judge_sample.json --release-dir $REL --out $J/judge_estimate.json
EOC
