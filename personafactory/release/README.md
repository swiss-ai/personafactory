# personafactory.release

Turns the pipeline's accepted conversations into the released corpus, computes every corpus statistic of the paper
(composition, guards, sanity gate, duplicates, and the full-corpus judge-free fidelity table), and builds and uploads
the Hugging Face dataset [`swiss-ai/PersonaFactory`](https://huggingface.co/datasets/swiss-ai/PersonaFactory)
(subsets `chats`, default, and `persona_bank`; one `train` split each; Apache 2.0).

Everything here is CPU only, except the LaBSE row of the fidelity table (one GPU, `evaluation/corpus_judge`). The
build and the statistics read the whole corpus: run them on a compute node (`scripts/slurm/eval_client.sbatch`), not
on a login node. Only the upload needs internet access.

Environment: `PF_OUT_DIR` (output root), `PF_BANK` (persona bank JSONL, or `--bank`), `PF_LID_MODEL` (fastText
`lid.176.ftz`, or `--lid-model`). Python packages: `fasttext`, `lingua-language-detector`, `scipy`, `matplotlib`,
`pyarrow`, `langcodes`, `huggingface_hub`.

The corpus has two record sets that are assembled separately and then merged: the persona-pair conversations
(UltraChat and Nemotron seeds; steps 1 to 3 here, in `PAIRS=$PF_OUT_DIR/release_pairs`) and the seed-pool
conversations (UltraChat, Nemotron and WildChat seeds; `augmentation.build_corpus`). Step 4 merges them
(`merge_release.py`) and runs the post-processing stages (`personafactory/postprocess/`). Below, `REL` is the final
release directory after step 4: `data/*.jsonl` in the release record schema (one conversation per line: `id`, `conversation`, `persona_id`, `text_language`, `language_mode` (`free` = language-matched,
`multilingual` = cross-lingual), `match_basis`, `source_name`, `source_id`, `source_text`, `num_turns`, `responder`,
`sanity_verdicts`, `model_persona`, `release_part`) plus `persona_bank.jsonl`. Statistics, the fidelity table and the
Hugging Face build (steps 5 to 7) run on `REL`. `scripts/examples/release_hf.sh` runs the steps below.

## Steps

### 1. Assemble the persona-pair record set (`build_release.py`)

Inputs: accepted conversations from `augmentation/extract_accepted.py` (`<accepted>/free/*.jsonl`,
`<accepted>/multilingual/*.jsonl`) and, optionally, raw pipeline output records (`--responses`). Adds the LID language
of the first user turn (`text_language`, never the persona's declared language) and, with `--dedup`, keeps one record
per (normalized source prompt, text language).

```bash
python -m personafactory.release.build_release --accepted $PF_OUT_DIR/accepted \
    --lid-model $PF_LID_MODEL --dedup --outdir $PAIRS --workers 60
```

Outputs: `$PAIRS/data/0000.jsonl ... 0199.jsonl`, `$PAIRS/dataset_summary.json`.

### 2. Emoji scrub (`scrub_emoji.py`, in place)

Removes emoji from user turns of personas whose bank entry says `emoji_use: none` (emoji already in the seed prompt
are kept).

```bash
python -m personafactory.release.scrub_emoji --bank $PF_BANK --data "$PAIRS/data/*.jsonl"
```

### 3. Assistant side (`swap_assistant.py`, in place)

After the assistant regeneration of step 2's output (user persona system prompt plus a matched model persona, see
`assistant/`), replaces every assistant side with its regenerated version and drops conversations that failed the
sanity gate or whose user turns changed.

```bash
python -m personafactory.release.swap_assistant --release-dir $PAIRS --regen-dir $PF_OUT_DIR/assistant_regen_clean \
    --model-personas personafactory/assistant/model_personas.json
```

Outputs: `assistant_side.json`, `model_personas.json`, updated `dataset_summary.json`.

### 4. Merge and post-processing (`merge_release.py`, `personafactory/postprocess/`)

`merge_release.py` merges the persona-pair set (`release_part = pairs`) with the seed-pool set
(`release_part = seeds`, output of `augmentation.build_corpus --stage final`), drops cross-set duplicates (same id, or
same normalized seed prompt in the same language) and writes the bank profiles of every persona used. The
post-processing stages then run in place on the merged directory, in the order given in `postprocess/README.md`
(quality filters, assistant regeneration of flagged conversations, the judge sample, `corpus_stats.json`).

```bash
REL=$PF_OUT_DIR/release_merged
python -m personafactory.release.merge_release --part pairs=$PAIRS/data --part seeds=$PF_OUT_DIR/seeds_run/final/data \
    --bank $PF_BANK --out $REL
# then the postprocess stages on --release-dir $REL (postprocess/README.md)
```

### 5. Corpus statistics (`stats/`, any order)

```bash
export PF_BANK=$REL/persona_bank.jsonl
python -m personafactory.release.stats.corpus_numbers --release-dir $REL --workers 60
python -m personafactory.release.stats.entity_integrity --release-dir $REL
python -m personafactory.release.stats.style_adherence --release-dir $REL --workers 60
python -m personafactory.release.stats.length_by_tendency --release-dir $REL
python -m personafactory.release.stats.duplicates --release-dir $REL --workers 60
python -m personafactory.release.stats.emoji --release-dir $REL
python -m personafactory.release.stats.language_counts --release-dir $REL
python -m personafactory.release.stats.register_stats --release-dir $REL --lid-model $PF_LID_MODEL --workers 60
# assistant regeneration statistics of the persona-pair set (inputs and outputs of step 3)
python -m personafactory.release.stats.sanity_stats --release-dir $REL --regen-input $PF_OUT_DIR/assistant_regen/input \
    --regen-dir $PF_OUT_DIR/assistant_regen_clean
python -m personafactory.release.stats.guard_stats --release-dir $REL --regen-input $PF_OUT_DIR/assistant_regen/input
python -m personafactory.release.stats.guard_by_language --release-dir $REL --regen-input $PF_OUT_DIR/assistant_regen/input
python -m personafactory.release.stats.corpus_distribution --release-dir $REL --fig $PF_OUT_DIR/figures/fig_stacked_languages_regions.pdf
```

Every script accepts `--out` to write its report elsewhere.

### 6. Full-corpus judge-free fidelity table

All rows are computed over the whole released corpus (1,242,761 conversations). Transformation depth (token Jaccard
distance, normalized edit distance, core-vocabulary retention) and the length ratio compare the first rewritten user
turn with the seed prompt (`source_text`) of language-matched conversations; constraint retention and style adherence
use the first user turn of every conversation; LaBSE uses every user turn.

| Row | Script | Report key |
|---|---|---|
| Token Jaccard distance, normalized edit distance, core-vocabulary retention | `stats.corpus_numbers` | `corpus_numbers.json`: `fidelity_transformation_depth_same_language` |
| LaBSE similarity | `evaluation.corpus_judge.labse_full` (GPU) | `labse_full.json`: `combined.all` (or `corpus.all`) |
| Numbers, code, quoted literals intact; all entities preserved | `stats.entity_integrity` | `entity_integrity.json`: `overall`, `all_entities_intact_pct` |
| Emoji, capitalization, punctuation register | `stats.style_adherence` | `style_adherence.json`: `overall` |
| Length ratio short / medium / long and Spearman rho | `stats.length_by_tendency` | `length_by_tendency.json` |

`corpus_numbers.json` also has a simpler binary style check (`fidelity_style_adherence`); the paper's register rows
use the tier-aware definitions of `style_adherence.py`. `scripts/slurm/eval_fidelity.sbatch` runs the four CPU
scripts and the LaBSE job on one node; see `evaluation/README.md` for the LaBSE inputs and for the corpus-wide
LLM-judge estimate.

### 7. Hugging Face release (`build_hf.py`, `build_hf_cards.py`, `upload_hf.py`)

Runs on the final, post-processed release directory.

```bash
HF=$PF_OUT_DIR/hf_release
python -m personafactory.release.build_hf --release-dir $REL --bank $PF_BANK --out $HF
python -m personafactory.release.build_hf_cards --hf-dir $HF
python -m personafactory.release.upload_hf --hf-dir $HF --repo <org>/<name> [--private]   # needs internet
```

`build_hf` writes zstd parquet shards (`bank/data/train-*.parquet`, 100,000 profiles each; `chats/data/train-*.parquet`,
50,000 conversations each) and `stats.json` per subset. Chat fields: `id`, `messages`, `persona_id`, `language`,
`setting` (`language_matched` / `cross_lingual`), `match_tier`, `source`, `source_id`, `original_prompt`, `num_turns`,
`responder` (published model id), `model_persona`, `sanity_verdicts`. Bank rows keep only judge-kept profiles with
`id`, `generator_model`, `background`, `style`, `character_description` and the judge scores. `--id-map <path>`
additionally writes a release id to pipeline id table for your own bookkeeping (off by default, never uploaded).
`build_hf_cards` renders the dataset card (`README.md`) from the two `stats.json` files; `upload_hf` puts every shard
of a subset into its single `train` split.

## Reports

| Step | Script | Report |
|---|---|---|
| 1 | `build_release` | `$PAIRS/dataset_summary.json` |
| 3 | `swap_assistant` | `$PAIRS/assistant_side.json`, `$PAIRS/model_personas.json` |
| 4 | `merge_release` | `$REL/data/*.jsonl`, `$REL/persona_bank.jsonl`, `$REL/summary.json` |
| 5 | `stats.corpus_numbers` | `corpus_numbers.json` (composition; transformation depth and constraint retention) |
| 5 | `stats.entity_integrity` | `entity_integrity.json` |
| 5 | `stats.style_adherence` | `style_adherence.json` |
| 5 | `stats.length_by_tendency` | `length_by_tendency.json` |
| 5 | `stats.duplicates` | `duplicate_audit.json` |
| 5 | `stats.emoji` | `emoji_audit.json` |
| 5 | `stats.language_counts` | `full_stats.json` |
| 5 | `stats.register_stats` | `register_stats.json` |
| 5 | `stats.sanity_stats` | `assistant_sanity.json` |
| 5 | `stats.guard_stats`, `stats.guard_by_language` | `guards.json`, `guards_by_language.json` |
| 5 | `stats.corpus_distribution` | `corpus_dist.json` and the figure PDF |
| 7 | `build_hf` | `$HF/{bank,chats}/data/*.parquet`, `$HF/{bank,chats}/stats.json` |
| 7 | `build_hf_cards` | `$HF/README.md` |

## Files

| File | Purpose |
|---|---|
| `build_release.py` | assemble the release directory (LID language, dedup) |
| `scrub_emoji.py`, `emoji_utils.py` | emoji scrub for `emoji_use: none` personas |
| `swap_assistant.py` | swap in the regenerated assistant side |
| `merge_release.py` | merge the persona-pair and seed-pool record sets into the release directory |
| `stats/` | corpus statistics and the judge-free fidelity rows |
| `build_hf.py` | parquet shards and stats for the Hugging Face dataset |
| `build_hf_cards.py` | dataset card from the stats |
| `upload_hf.py` | upload to a Hugging Face dataset repo |

Code: [github.com/swiss-ai/personafactory](https://github.com/swiss-ai/personafactory).
