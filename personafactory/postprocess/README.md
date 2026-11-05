# postprocess

Quality stages on the merged release directory (`release/merge_release.py` output, `$REL` below). They target
seed-pool conversations (`release_part == seeds`): low-resource languages, the Ministral responder in cross-lingual
conversations, user turns in the wrong script, and the share of cross-lingual Russian. Every stage rewrites
`$REL/data/*.jsonl` in place (or, for the first filter, moves it to `data_unfiltered/`) and logs what it removed or
replaced next to it, so each change can be rolled back. Run all commands from the repository root;
`scripts/examples/corpus.sh` has them in order with the released settings.

## Stages, in order

| # | module | what | output in `$REL` |
|---|---|---|---|
| 1 | `lowres_quality --stage metrics` | per-conversation metrics for 59 low-resource languages + German / Spanish (control): per-turn LID, expected-script share, English share, length ratio, 3-gram repetition, duplicate first turns | `rows.jsonl`, `metrics.json`, `sample.jsonl` in `--out` |
| 1b | `lowres_quality --stage judge / report` (optional) | API judge (1-5 scores and flags for user / assistant language, fluency, fidelity, quality) on 20 conversations per language | `judge_<tag>.jsonl`, `report.json` in `--out` |
| 2 | `apply_lowres_filter` | drop: language-matched Maori / Tswana LID mislabels; Quechua, Shan, Guarani, Dhivehi, Ewe, Bambara, Fula, Aymara (judge < 2.5 even with Gemma); Ministral responder in a low-resource language except Uzbek and Nepali; 3-gram repetition > 0.3; cross-lingual with > 50% English user turns | `data_unfiltered/`, `lowres_removed.jsonl`, `lowres_filter.json` |
| 3 | `lowres_regen_prep --source removed` -> generation with `--responder gemma` -> `augmentation.build_corpus` -> `finalize_lowres_regen --mode append` | the conversations dropped only for the Ministral responder, regenerated end to end with Gemma under the same ids; survivors of the step-2 checks are added back | `lowres_regen_append.json` |
| 3b | `judge_lowres_regen` (optional) | paired before / after judge on the same seeds | `compare.json` in `--out` |
| 4 | `lowres_regen_prep --source kept` -> generation -> build -> `finalize_lowres_regen --mode replace` | the remaining low-resource cross-lingual Ministral conversations (Uzbek, Nepali) regenerated with Gemma and replaced in place when they pass the checks | `lowres_regen_replaced.jsonl`, `lowres_regen_replace.json` |
| 5 | `asst_regen_prep` -> `assistant.regenerate_assistant --stage user_persona` -> `finalize_asst_regen` | cross-lingual high-resource conversations with a Ministral responder: assistant side regenerated with Gemma (user turns fixed, user persona system prompt, continuity loop, sanity gate); swapped when every turn passes, the user turns match and repetition <= 0.3 | `asst_regen_replaced.jsonl`, `asst_regen.json` |
| 5b | `asst_regen_judge` (optional, before the swap) | paired Ministral vs Gemma judge on 20 conversations per language | `compare.json` in `--out` |
| 6 | `drop_lowscript` | low-resource conversations whose user turns use the expected script for < 10% of letters (recomputed on the current text) | `lowscript_removed.jsonl`, `lowscript_filter.json`, `summary.json`, pruned `persona_bank.jsonl` |
| 7 | `judge_sample_prep` -> `evaluation.corpus_judge.run_judge` | intent / style judge items (MiniMax-M2.5) for 25,000 random seed-pool conversations, one item per user turn | items, results in `--out` |
| 8 | `drop_crosslingual_russian` | cross-lingual seed-pool conversations whose detected language is Russian | `ml_russian_removed.jsonl`, `ml_russian_filter.json`, `summary.json`, pruned `persona_bank.jsonl` |
| 9 | `corpus_stats`, `judge_sample_agg` | corpus counts and crossings per part; judge pass rates with 95% Wilson intervals (conversations still in the release) | `corpus_stats.json`, `judge_sample.json` |

The regenerations run on GPU units (`scripts/slurm/corpus_generate.sbatch` with `PAIRS_DIR` and `RESPONDER=gemma`,
`scripts/slurm/corpus_asst_regen.sbatch`); everything else is CPU. The optional judge passes (1b, 3b, 5b) informed the
fixed lists in `apply_lowres_filter.py`; the filters themselves only use the metrics of step 1.

## Commands

```bash
REL=./release_merged Q=./outputs/lowres_quality
python -m personafactory.postprocess.lowres_quality --stage metrics --release-dir $REL --out $Q --workers 128 --n 20
python -m personafactory.postprocess.apply_lowres_filter --release-dir $REL --quality-dir $Q

python -m personafactory.postprocess.lowres_regen_prep --source removed --release-dir $REL --seeds-dir ./data/seeds/shards \
    --assign-dir ./outputs/assign_seeds --run ./outputs/regen_lowres --units 4
#   generation: PAIRS_DIR=./outputs/regen_lowres/pairs RUN=./outputs/regen_lowres RESPONDER=gemma ... corpus_generate.sbatch
python -m personafactory.augmentation.build_corpus --stage user --run ./outputs/regen_lowres --shards 8
python -m personafactory.augmentation.build_corpus --stage final --run ./outputs/regen_lowres
python -m personafactory.postprocess.finalize_lowres_regen --mode append --release-dir $REL --run ./outputs/regen_lowres
#   same with --source kept --units 2, --shards 4 and --mode replace

python -m personafactory.postprocess.asst_regen_prep --release-dir $REL --assistant-input ./outputs/seeds_run/assistant_input \
    --out ./outputs/asst_regen
#   generation: IN=./outputs/asst_regen/input OUT=./outputs/asst_regen ... corpus_asst_regen.sbatch
python -m personafactory.postprocess.finalize_asst_regen --release-dir $REL --regen-dir ./outputs/asst_regen/user_persona

python -m personafactory.postprocess.drop_lowscript --release-dir $REL --quality-dir $Q
python -m personafactory.postprocess.judge_sample_prep --release-dir $REL --gen ./outputs/seeds_run/gen --out ./outputs/judge_sample
#   judge: JUDGE_DIR=./outputs/judge_sample ... corpus_judge.sbatch
python -m personafactory.postprocess.drop_crosslingual_russian --release-dir $REL
python -m personafactory.postprocess.corpus_stats --release-dir $REL --gen ./outputs/seeds_run/gen
python -m personafactory.postprocess.judge_sample_agg --judge-dir ./outputs/judge_sample --release-dir $REL
```

## Judge endpoint

`lowres_quality --stage judge` posts to an OpenAI-compatible chat endpoint (`--judge-url`, base URL ending in `/v1`,
or `PF_JUDGE_URL`; key from `PF_API_KEY`) with a global request-rate limit (`--rpm`, 13 requests per minute with 16
threads for `deepseek-ai/DeepSeek-V4.1-Flash` in the released analysis), temperature 0, 8,192 tokens, and stores the
parsed JSON verdict per conversation. `judge_lowres_regen` and `asst_regen_judge` write a `sample.jsonl` in the same
format and reuse this stage with `--out` pointing at their directory.

## Record fields added here

`regenerated: "lowres_gemma"` (steps 3 and 4: user and assistant side regenerated with Gemma under the same id),
`assistant_regenerated: "gemma"` (step 5: assistant side only; the user side was rewritten by Ministral).
