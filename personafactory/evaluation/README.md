# personafactory.evaluation

Scripts behind the evaluation results of the paper (Section 5 and the evaluation, persona-format and per-attribute
appendices). Run everything from the repository root as `python -m personafactory.evaluation.<subpackage>.<module> ...`;
every module has `--help`. The downstream fine-tuning experiments are in `personafactory/downstream/`.

Endpoints are OpenAI-compatible servers (`.../v1`, e.g. `vllm serve` or SGLang), passed on the command line or in the
YAML configs; configs reference API keys as `ENV=<VAR>` (default variable `PF_API_KEY`, any value works for local
servers). The corpus judge also reads `PF_JUDGE_URL(S)` / `PF_JUDGE_MODEL` (see `common/judge_client.py`). No paths
are hard-coded: data and outputs come from arguments or `PF_DATA_DIR`, `PF_OUT_DIR`, `PF_BANK`. LLM calls and LaBSE
are compute jobs: run them on a serving or GPU node (`scripts/slurm/eval_*.sbatch`), not on a login node.
`scripts/examples/evaluation.sh` chains the corpus-scale steps.

## Paper result -> script

| Paper result | Scripts | Output |
|---|---|---|
| Full-corpus LLM-judge table (`tab:full-judge`), fully scored rows | `corpus_judge/prep_items.py` -> `corpus_judge/run_judge.py` -> `corpus_judge/aggregate.py` | `corpus_judge.json` |
| Full-corpus LLM-judge table, sample rows | `postprocess/judge_sample_prep.py` -> `corpus_judge/run_judge.py` -> `postprocess/judge_sample_agg.py` (random sample of the remaining conversations, same templates and judge; see `postprocess/README.md`) | `judge_sample.json` (`all`, `by_generator`, `by_source_name`) |
| Corpus-wide judge estimate (96.6% intent, 67.1% style, 64.9% both) | `corpus_judge/estimate.py` | `judge_estimate.json` |
| Full-corpus judge-free fidelity table (`tab:fidelity`), LaBSE row | `corpus_judge/labse_full.py` (all turns of the corpus; `corpus_judge/labse.py` for a judged subset) | `labse_full.json` |
| Full-corpus judge-free fidelity table, all other rows | `release/stats/corpus_numbers.py`, `entity_integrity.py`, `style_adherence.py`, `length_by_tendency.py` (see `release/README.md`) | `corpus_numbers.json`, `entity_integrity.json`, `style_adherence.json`, `length_by_tendency.json` |
| Structured vs flat A/B (`tab:structured`) | `structured_vs_flat/ab_style_test.py`, `structured_vs_flat/re_judge_ab.py`, `structured_vs_flat/ab_table.py` | `ab_style_results.jsonl`, `ab_first_pass.jsonl` |
| External re-judging of the A/B (`tab:ab-rejudge`, `fig:ab-rejudge`) | `structured_vs_flat/ab_rejudge.py` (one run per judge), `structured_vs_flat/ab_table.py` | `ab_rejudge_<judge>.jsonl`, `ab_table.json` |
| Multi-judge agreement (`tab:judge-means`, `tab:judge-agree`, `tab:judge-kappa`) | `attribute_ablation/run_judge_ablation.py`, `attribute_ablation/agreement_stats.py` | `judge_ablation.json` |
| Per-attribute ablation (`tab:attribution`, `fig:abl_heatmap`, `fig:abl_models`) | `attribute_ablation/sample_dataset.py` -> `attribute_ablation/run_ablation.py` -> `attribute_ablation/summarize.py` (figures: `figures/make_ablation_figures.py --stats ablation_stats.json`) | `results.jsonl`, `summary.json`, `ablation_stats.json` |
| Persona-format comparison (`tab:formats`, `tab:formatresults`, `tab:formats-main`, `fig:format-tradeoff`, `tab:formatrobust`) | `format_comparison/sample_items.py` -> `build_projections.py` -> `run_conditions.py` (gemma and ministral) -> `score_conditions.py` -> `score_labse.py` -> `multi_judge.py` -> `make_comparison_appendix.py`; inspection: `analyze.py`, `diversity.py` | `comparison_appendix.tex`, `comparison_main.tex` |
| Format-neutral re-judging, naturalness, real PersonaHub / SynthPAI personas (`fig:format-neutral`) | `format_comparison/native_gen.py` -> `format_comparison/rejudge_neutral.py` (one run per judge) -> `format_comparison/analyze_neutral.py` | `results_neutral.json` (input of `figures/make_results_figures.py --format-results`) |
| Downstream fine-tuning (`tab:downstream-clean`, `tab:downstream-paired`, `tab:downstream-x`) | `personafactory/downstream/` | see `downstream/README.md` |
| Style extension of external persona banks and its style A/B (MiniMax-M2.5 and external Qwen3.6 / Muse judges) | [`style_extension/`](style_extension/README.md) | see `style_extension/README.md` |

Not included: the persona selection x rewrite prompt ablation (`tab:rewriteabl`) and the cross-lingual strategy
ablation (`tab:crossling`); see "Not included" below.

## Corpus-scale judge, corpus-wide estimate and LaBSE

`$REL` is the release directory (`data/*.jsonl` and `persona_bank.jsonl`, see `release/README.md`). `--originals` are
the pipeline output records the release was built from; the per-turn source turn and translation baseline are read
from `metadata.turns_detail`. The fully scored subset is the persona-pair record set
(`release_part == pairs`, every conversation with originals in `--originals`); the sample covers the seed-pool set
(`release_part == seeds`).

Judge protocol: `MiniMax-M2.5` (served with SGLang, TP4/EP4, `--reasoning-parser minimax-append-think`, context 16k),
temperature 0.1, max 2,048 tokens, one retry at 4,096 tokens for an unparsable verdict; one intent and one style
verdict per user turn with the paper's templates. For cross-lingual turns, which are translated before they are
restyled, intent is judged against the translation (the intent template fails any language switch); the verdict
against the English source is reported separately. Rates exclude unparsed verdicts and carry 95% Wilson intervals.

```bash
J=$PF_OUT_DIR/corpus_judge
# 1. fully scored subset: every user turn of the given records
python -m personafactory.evaluation.corpus_judge.prep_items --release-dir $REL --bank $REL/persona_bank.jsonl \
    --originals $PF_OUT_DIR/accepted --out-dir $J --shards 64
python -m personafactory.evaluation.corpus_judge.run_judge --shards $J/items/000.jsonl $J/items/001.jsonl \
    --outdir $J/results --url http://HOST:30000/v1/chat/completions --model MiniMax-M2.5     # one client per shard group
python -m personafactory.evaluation.corpus_judge.aggregate --judge-dir $J --out $J/corpus_judge.json
# 2. random sample of the remaining conversations (25,000 conversations, seed 0, same templates and judge):
#    postprocess.judge_sample_prep -> run_judge -> postprocess.judge_sample_agg (postprocess/README.md) -> $REL/judge_sample.json
# 3. corpus-wide estimate: both strata weighted by the user turns they stand for in the release
python -m personafactory.evaluation.corpus_judge.estimate --scored $J/corpus_judge.json \
    --sample $REL/judge_sample.json --release-dir $REL --out $J/judge_estimate.json
```

`estimate.py` computes `(rate_scored * T_scored + rate_sample * (T_total - T_scored)) / T_total`, with `T_scored` the
user turns of the fully scored subset and `T_total` all user turns of the release. With the paper's strata
(552,654 fully scored turns from the conversations with a model persona, a 44,687-turn sample from 24,570 of the other
conversations, 2,387,392 user turns in total) it gives 96.6% intent, 67.1% style and 64.9% both. The backbone rows of the table group turns by the model
that rewrote the user turns.

LaBSE (`sentence-transformers/LaBSE`, CLS pooling, dense tanh head, L2 normalization, max 256 tokens, fp16; one GPU):

```bash
# over every user turn of the corpus, sources from the pipeline output records and/or the seed shards
python -m personafactory.evaluation.corpus_judge.labse_full --release-dir $REL --originals $PF_OUT_DIR/accepted \
    --seeds "$PF_DATA_DIR/seeds/*.jsonl" --out $REL/labse_full.json
# optional: reuse a subset scored with labse.py (its conversations are skipped; turn-weighted combination)
python -m personafactory.evaluation.corpus_judge.labse --judge-dir $J --out $J/labse.json
python -m personafactory.evaluation.corpus_judge.labse_full --release-dir $REL --seeds "$PF_DATA_DIR/seeds/*.jsonl" \
    --subset-items $J/items --subset-labse $J/labse.json --out $REL/labse_full.json
```

The LaBSE row of the fidelity table is the turn-pair mean over the whole corpus (`combined.all` with a reused
subset, else `corpus.all`; 0.791 in the paper). The source turn is the seed user turn
(the English seed for cross-lingual turns), and verbatim turns are included. `scripts/slurm/eval_fidelity.sbatch`
runs this job together with the CPU rows of the table.

`--reuse-results <previous results dir>` in `prep_items.py` copies verdicts of an earlier judge run with the same
sharding for items whose key exists there (only valid when the user turns are unchanged, e.g. after an
assistant-side-only rebuild).

## Structured vs flat style A/B

```
python -m personafactory.evaluation.structured_vs_flat.ab_style_test --samples ./data/ab_prompts.jsonl --bank ./data/ab_bank.jsonl \
    --rewriter-urls http://HOST:8080/v1 --rewriter-model google/gemma-4-31B-it \
    --judge-urls http://HOST:30000/v1 --judge-model MiniMax-M2.5 --out ./outputs/ab_style_results.jsonl
# first-pass pairwise verdicts on the stored pairs (max_tokens 3072)
python -m personafactory.evaluation.structured_vs_flat.re_judge_ab --results ./outputs/ab_style_results.jsonl --bank ./data/ab_bank.jsonl \
    --judge-urls http://HOST:30000/v1 --judge-model MiniMax-M2.5 --out ./outputs/ab_first_pass.jsonl
# external re-judging, one run per judge (hosted endpoints: --rpm to stay within quota)
python -m personafactory.evaluation.structured_vs_flat.ab_rejudge --results ./outputs/ab_style_results.jsonl --bank ./data/ab_bank.jsonl \
    --url http://127.0.0.1:30000/v1 --model MiniMax-M2.5 --max-tokens 8192 --out ./outputs/ab_rejudge_minimax.jsonl
python -m personafactory.evaluation.structured_vs_flat.ab_rejudge ... --url $HOSTED_API_URL --model deepseek-ai/DeepSeek-V4-Flash \
    --rpm 14 --concurrency 8 --max-tokens 4096 --out ./outputs/ab_rejudge_deepseek.jsonl
python -m personafactory.evaluation.structured_vs_flat.ab_table first_pass=./outputs/ab_first_pass.jsonl \
    minimax=./outputs/ab_rejudge_minimax.jsonl deepseek=./outputs/ab_rejudge_deepseek.jsonl --out ./outputs/ab_table.json
```

`--samples` are JSONL prompt files with an `original_message` field; `--bank` is the persona bank the A/B used (an
earlier bank release with the same structured style schema). `ab_table.py` reports parsed pairs, preference shares,
the structured share of decisive verdicts with a 95% Wilson interval and intent preservation per representation.

## Per-attribute ablation and multi-judge agreement

Fill the endpoints in `attribute_ablation/ablation_config.yaml` (four rewriters, one judge, the `judges` section).

```
python -m personafactory.evaluation.attribute_ablation.sample_dataset --num-per-dataset 150 --output ./data/attribute_ablation/samples.jsonl
python -m personafactory.evaluation.attribute_ablation.run_ablation --config evaluation/attribute_ablation/ablation_config.yaml
python -m personafactory.evaluation.attribute_ablation.summarize --results ./outputs/attribute_ablation/results.jsonl \
    --out ./outputs/attribute_ablation/summary.json --figure-stats ./outputs/figures/ablation_stats.json
python -m personafactory.evaluation.attribute_ablation.run_judge_ablation --results ./outputs/attribute_ablation/results.jsonl \
    --config evaluation/attribute_ablation/ablation_config.yaml --out ./outputs/attribute_ablation/judge_ablation.json
python -m personafactory.evaluation.attribute_ablation.agreement_stats --judge-results ./outputs/attribute_ablation/judge_ablation.json
```

`agreement_stats.py` prints Cohen's kappa and Gwet's AC1 per judge pair twice: with the pair's own marginals (standard
definition) and with each judge's overall pass rate (`marginal`, how the paper table was computed).

## Persona-format comparison

Fill the endpoints in `format_comparison/config.yaml` (rewriters, the pipeline judge, a projection model that is
neither rewriter nor judge). The corpus passed to `sample_items.py` is a pipeline output JSONL with
`metadata.persona` and `metadata.turns_detail`.

```
D=./outputs/format_comparison; C=evaluation/format_comparison/config.yaml
python -m personafactory.evaluation.format_comparison.sample_items --corpus ./outputs/pipeline_output.jsonl --n 800 --out $D/items.jsonl
python -m personafactory.evaluation.format_comparison.build_projections --items $D/items.jsonl --config $C \
    --personahub ./data/personahub/persona.jsonl --out $D/projections_personahub.json
python -m personafactory.evaluation.format_comparison.run_conditions --items $D/items.jsonl --projections $D/projections_personahub.json \
    --config $C --responder gemma --out $D/generations.jsonl
python -m personafactory.evaluation.format_comparison.score_conditions --generations $D/generations.jsonl --items $D/items.jsonl \
    --config $C --out-metrics $D/metrics.jsonl --out-judge $D/judgments.jsonl
python -m personafactory.evaluation.format_comparison.score_labse --generations $D/generations.jsonl --metrics $D/metrics.jsonl --cache $D/labse_sims.npy
# robustness: Ministral rewriter
python -m personafactory.evaluation.format_comparison.run_conditions ... --responder ministral --out $D/generations_ministral.jsonl
python -m personafactory.evaluation.format_comparison.score_conditions --generations $D/generations_ministral.jsonl --items $D/items.jsonl \
    --config $C --out-metrics $D/metrics_ministral.jsonl --out-judge $D/judgments_ministral.jsonl
python -m personafactory.evaluation.format_comparison.multi_judge --generations $D/generations.jsonl --items $D/items.jsonl --config $C \
    --out $D/multi_judge.jsonl --n 200 --judges minimax,gemma,ministral,glm
python -m personafactory.evaluation.format_comparison.make_comparison_appendix --run-dir $D --out-dir $D/tex
python -m personafactory.evaluation.format_comparison.analyze --metrics $D/metrics.jsonl --judge $D/judgments.jsonl --slice cross_lingual
# format-neutral re-judging, naturalness, real personas
python -m personafactory.evaluation.format_comparison.native_gen --items $D/items.jsonl --config $C \
    --personahub ./data/personahub/persona.jsonl --synthpai ./data/synthpai/synthpai.jsonl \
    --rewriter-urls http://HOST:8080/v1 --rewriter-model google/gemma-4-31B-it --out $D/generations_native.jsonl
python -m personafactory.evaluation.format_comparison.rejudge_neutral --run-dir $D --urls http://HOST:30000/v1 --model MiniMax-M2.5 --label minimax --max-tokens 8192
python -m personafactory.evaluation.format_comparison.rejudge_neutral --run-dir $D --urls http://HOST:8000/v1 --model Qwen/Qwen3.6-35B-A3B --label qwen36 --max-tokens 6144
python -m personafactory.evaluation.format_comparison.analyze_neutral --run-dir $D
```

### External persona datasets

No PersonaHub or SynthPAI content is shipped; download them yourself (both CC-BY-NC-SA-4.0):

- PersonaHub: the `persona` subset of `proj-persona/PersonaHub` on the Hugging Face hub (`persona.jsonl`, 200,000 lines
  of `{"persona": ...}`), e.g. `huggingface-cli download proj-persona/PersonaHub persona.jsonl --repo-type dataset
  --local-dir ./data/personahub`. Used for the projection length gate and the real-persona condition.
- SynthPAI: the released `synthpai.jsonl` from the SynthPAI paper's data release (the SynthPAI dataset on the Hugging
  Face hub; comment records with `author` and `profile`, 300 distinct profiles). Place it at
  `./data/synthpai/synthpai.jsonl`. Used for the real-persona condition.

## Not included

- Persona selection x rewrite prompt 2x2 (`tab:rewriteabl`) and cross-lingual single pass vs translate-then-restyle
  (`tab:crossling`): the arms were generated with separate experiment tooling (pair preparation, variant switches
  for persona swapping and rewrite framing) that is not part of this release; their judging used the same templates
  and judge settings as `corpus_judge/` applied per arm.
