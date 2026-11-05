#!/bin/bash
# Downstream fine-tuning on the released corpus (paper appendix "Downstream Fine-tuning on the Released Corpus").
# Run the stages in order (STAGE=data | regen | assemble | train | eval | report); each stage submits jobs and
# returns. See personafactory/downstream/README.md. Cluster flags go into SBATCH_ARGS, environment activation into
# ENV_SETUP, containers into SRUN_ARGS / PF_SRUN_ARGS.
set -euo pipefail
: "${PF_OUT_DIR:?output root}" "${PF_DATA_DIR:?data root}" "${PF_MODEL_DIR:?model dir}" "${STAGE:?data|regen|assemble|train|eval|report}"
W=${W:-$PF_OUT_DIR/downstream}
RELEASE=${RELEASE:-swiss-ai/PersonaFactory}           # or a local snapshot of the dataset
TOK=${TOK:-$PF_MODEL_DIR/Apertus-v1.5-8B}               # Apertus tokenizer (token cap)
E=${E:-$PF_DATA_DIR/downstream_eval}                    # evaluation prompts
R=$W/eval                                               # generations, scores, reports
SB="sbatch --parsable ${SBATCH_ARGS:-}"
client() { MODULE=$1 MODULE_ARGS=$2 $SB --job-name=$3 ${4:+--dependency=afterok:$4} scripts/slurm/eval_client.sbatch; }
mkdir -p "$W" "$E" "$R"

case $STAGE in
data)  # seeds, arms A0 / A1, A0r and X1 inputs; benchmarks and WildChat prompts (fetch needs internet: run it first)
  python -m personafactory.downstream.eval.fetch_benchmarks --data-dir "$E"
  S1=$(client personafactory.downstream.seeds "--release $RELEASE --setting language_matched ${SEED_ARGS:-} --out $W/seeds_language_matched.jsonl" pfd-seeds-lm)
  S2=$(client personafactory.downstream.seeds "--release $RELEASE --setting cross_lingual ${SEED_ARGS:-} --out $W/seeds_cross_lingual.jsonl" pfd-seeds-x)
  A=$(client personafactory.downstream.build_arms "--release $RELEASE --seeds $W/seeds_language_matched.jsonl --tokenizer $TOK --work $W" pfd-arms "$S1")
  A0R=$(client personafactory.downstream.a0r "build --work $W --release $RELEASE" pfd-a0r-build "$A")
  X=$(client personafactory.downstream.x_arms "build --work $W --release $RELEASE --seeds $W/seeds_cross_lingual.jsonl --tokenizer $TOK --n 50000" pfd-x-build "$S2")
  P=$(client personafactory.downstream.eval.perturb_rules "--data-dir $E" pfd-rules)
  WC=$(client personafactory.downstream.eval.wildchat_prompts "--data-dir $E --train $W/data/A0_source.jsonl --release $RELEASE" pfd-wildchat "$A")
  echo "seeds=$S1,$S2 arms=$A a0r_build=$A0R x_build=$X rules=$P wildchat=$WC"
  ;;
regen)  # A0r and X1 regeneration (2-node units: Gemma + Ministral, MiniMax-M2.5 judge); persona rewrites of the benchmarks
  STEP_MODULE=personafactory.downstream.a0r WORK=$W $SB --array=0-3 scripts/slurm/downstream_regen.sbatch
  STEP_MODULE=personafactory.downstream.x_arms WORK=$W $SB --array=0-3 scripts/slurm/downstream_regen.sbatch
  G=$($SB --job-name=pfd-rewriter scripts/slurm/eval_vllm_server.sbatch google/gemma-4-31B-it 2 16384 --served-model-name gemma)
  RW=$(URL=$PF_OUT_DIR/endpoints/pfd-rewriter.endpoint client personafactory.downstream.eval.perturb_persona "--data-dir $E --heldout $W/data/heldout_personas.json --urls @URL@ --model gemma --k 3" pfd-persona-rewrite)
  echo "rewriter server=$G (cancel it after job $RW); then serve MiniMax-M2.5 (serve_models.sh judge) and run the intent check:"
  echo "  python -m personafactory.downstream.eval.intent_check prep --data-dir $E"
  echo "  python -m personafactory.downstream.eval.judge_client --shards $E/intent_items/000.jsonl --outdir $E/intent_results --urls \$JUDGE_URL --model MiniMax-M2.5"
  echo "  python -m personafactory.downstream.eval.intent_check merge --data-dir $E"
  ;;
assemble)  # four language-matched arms on shared ids; X1 / X2
  client personafactory.downstream.assemble_arms "--work $W --release $RELEASE --tokenizer $TOK" pfd-assemble
  client personafactory.downstream.x_arms "assemble --work $W --release $RELEASE --tokenizer $TOK" pfd-x-assemble
  ;;
train)  # Megatron-LM SFT per arm (setup once: scripts/slurm/downstream_megatron_setup.sbatch); seeds 1234, 2, 3 for A0 A1 A2
  : "${MEGATRON_ROOT:?}" "${TRANSFORMERS_ROOT:?}" "${HF_SAVER:?}"
  export WORK_ROOT=$W/sft EXPORT_PREFIX=$PF_MODEL_DIR/Apertus-v1.5-8B-base-PF
  for arm in A0 A1 A2; do ARM=$arm SOURCE=$W/data_paired/${arm}_source.jsonl SEEDS="1234 2 3" bash scripts/slurm/downstream_megatron_pipeline.sh; done
  ARM=A0r SOURCE=$W/data_paired/A0r_source.jsonl bash scripts/slurm/downstream_megatron_pipeline.sh
  for arm in X1 X2; do ARM=$arm SOURCE=$W/data_x/${arm}_source.jsonl VALID_FRAC=0.03 bash scripts/slurm/downstream_megatron_pipeline.sh; done
  ;;
eval)  # per model: styled / clean / WildChat generations + scoring, and lm-evaluation-harness
  for tag in ${TAGS:-A0 A1 A0r A2 X1 X2}; do
    M=$PF_MODEL_DIR/Apertus-v1.5-8B-base-PF-$tag
    MODEL=$M TAG=$tag DATA=$E/styled_all.jsonl OUT_DIR=$R $SB --job-name=pfd-eval-$tag scripts/slurm/downstream_eval_generate.sbatch
    MODEL=$M OUT=$W/lm_eval/$tag $SB --job-name=pfd-lmeval-$tag scripts/slurm/downstream_lm_eval.sbatch
  done
  ;;
report)  # robustness report; WildChat pairwise with two external judges (serve them first, e.g.
         #   sbatch --job-name=judge-qwen36 scripts/slurm/eval_vllm_server.sbatch Qwen/Qwen3.6-35B-A3B 2 32768 --served-model-name qwen --reasoning-parser qwen3
         #   sbatch --job-name=judge-muse   scripts/slurm/eval_vllm_server.sbatch <Muse-Glimmer-30B> 2 32768 --served-model-name muse)
  python -m personafactory.downstream.eval.report --results-dir "$R" --models A0 A1 A0r A2 --compare A1:A0 A2:A0r A2:A1 A2:A0
  python -m personafactory.downstream.eval.report --results-dir "$R" --models X1 X2 --compare X2:X1 --suffix _x
  # PAIRS is a comma-separated list: pass it through the environment or a file, never via sbatch --export
  export PAIRS=${PAIRS:-A2:A0r,A2:A1,A2:A0,A0:A0r,A1:A0r}
  python -m personafactory.downstream.eval.wildchat_pairwise prep --data-dir "$E" --results-dir "$R"
  EP=$PF_OUT_DIR/endpoints
  for j in qwen36:qwen muse:muse; do
    label=${j%%:*} served=${j#*:}
    URL=$EP/judge-$label.endpoint client personafactory.downstream.eval.judge_client \
      "--shards $E/wc_items/all.jsonl --outdir $E/wc_results_$label --urls @URL@ --model $served --max-tokens 8192 --concurrency 256" \
      pfd-wc-$label > /dev/null
  done
  echo "after both judge clients: python -m personafactory.downstream.eval.wildchat_pairwise agg --data-dir $E --results-dir $R --judges qwen36 muse"
  ;;
esac
