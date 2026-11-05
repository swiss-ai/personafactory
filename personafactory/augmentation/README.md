# augmentation

Rewrites the user side of seed chat logs with synthetic personas from the persona bank and generates the assistant
side. The request of every user turn stays fixed; only its voice changes. Two settings:

- `free` (language-matched): a persona that speaks the language of the seed prompt, chosen by the tiered selection
  location -> MiniLM embedding -> language pool; the user turns are restyled in the same language.
- `multilingual` (cross-lingual): a persona with a resolved non-English language; each user turn is first translated
  literally into that language (checked by language ID), then restyled.

In both settings one responder (Gemma or Ministral, 50/50 per conversation) rewrites the user turns and answers them,
a continuity loop adapts each non-final answer to the next original user turn, and a separate judge (MiniMax-M2.5)
sanity-checks every turn. A conversation is accepted only if every turn passes.

The corpus has two record sets that go through the same pipeline core (`pipeline.py`):

| set | seeds | personas | modules |
|---|---|---|---|
| persona pairs | UltraChat-200k `train_sft` and Nemotron-IF `chat_if`, one seed per persona, every pair in both settings | the bank the pairs were drawn from | `prepare_pairs`, `embed_personas --pairs-dir`, `select_personas --pairs-dir`, `run_augmentation --input-kind pairs`, `extract_accepted`, then `release/build_release.py` |
| seed pool | full UltraChat, Nemotron-IF `chat_if` and WildChat-4.8M, one setting per seed | full bank, at most 40 language-matched seeds per persona | `prepare_seeds`, `embed_personas --seeds-dir`, `select_personas --seeds-dir`, `run_augmentation --input-kind seeds`, `build_corpus` |

`release/merge_release.py` merges both sets; `postprocess/` holds the quality stages on the merged corpus.
`scripts/examples/corpus.sh` runs the seed pool end to end with the released settings.

## Files

| file | role |
|---|---|
| `pipeline.py` | pipeline core: persona rendering, persona selection (`select_persona`), literal-protected user rewrite, translate-then-restyle (`translate_turn`), persona system prompt, continuity loop, sanity gate (`process_conversation`), OpenAI-compatible client (`call_api`), dataset adapters. Optional hooks for fixed user turns (`_fixed`) and assistant model personas (`_model_persona`, `_source_system`, via `assistant.model_persona`). |
| `prompts.py` | prompt templates (rewrite, persona system prompt, continuity judge and repair, sanity judge, style/intent validators). |
| `integrity.py` | literal protection: mask quotes / code / URLs / numbers before a rewrite, restore and audit after. |
| `prepare_pairs.py` | persona-pair seeds: one filtered UltraChat / Nemotron conversation per persona, plus the persona's resolved target language. |
| `prepare_seeds.py` | seed pool: filtered, deduplicated seeds from full UltraChat, Nemotron and WildChat, seeds already used excluded, setting drawn per seed. |
| `embed_personas.py` | MiniLM (all-MiniLM-L6-v2) embeddings of personas and seed prompts (GPU). |
| `select_personas.py` | persona, match tier and responder per seed (both sets), per-persona cap and held-out sample for the seed pool. |
| `run_augmentation.py` | generation driver (async, resumable per shard) against served model endpoints. |
| `extract_accepted.py` | persona pairs: accepted (`status == pass`) conversations into the record schema of `release/build_release.py`. |
| `build_corpus.py` | seed pool: accepted conversations into release records (LID, dedup) and assistant-side inputs; final records. |
| `../common/lang_canon.py` | canonical persona languages, dialect -> base language, LID verifiability (`resolve`). |
| `../common/lid.py` | fastText lid.176 + Lingua language ID. |

## Seed pool

### Seeds (`prepare_seeds.py`)

| source | filter |
|---|---|
| UltraChat, full release (`stingning/ultrachat`) | conversations with an AI disclaimer in an assistant turn ("as an AI", "language model", "OpenAI", ...) dropped |
| Nemotron-Instruction-Following-Chat-v1 `chat_if` (rev. `83dcd3a`) | licence `odc-by-1.0`; tool conversations dropped; fields other than role/content stripped; `<think>` removed from assistant turns |
| WildChat-4.8M | `toxic == False` and `redacted == False` on the row and every turn; `conversation_hash` dedup; first user message >= 5 words (>= 10 characters for Chinese, Japanese, Korean, Thai, Lao, Khmer, Burmese, Tibetan); WildChat's language label kept as `seed_language` |

All sources: strict user/assistant alternation (non-empty system prompt rejected), the first 3 user turns with their
replies, <= 1,000 user words, <= 45,000 characters. Dedup keys on the first user message: exact (NFKC, casefold,
collapsed whitespace) and near (first 200 alphanumeric characters); seeds matching any conversation given with
`--exclude-release` / `--exclude-pairs` / `--exclude-responses` (the persona-pair part) are excluded. Sources are
filled in priority order UltraChat > Nemotron > WildChat by a fixed hash rank until
(710,000 + 966,000) x 1.05 seeds; each seed is `free` with probability 710 / 1,676 by the same rank.
Output: `<work>/shards/{mode}-{source}-NNNN.jsonl` (2,000 rows), `<work>/manifest.json`.

### Persona assignment (`embed_personas.py --seeds-dir`, `select_personas.py --seeds-dir`)

- Persona languages: `common/lang_canon.resolve` maps native_language (else main_language) to a canonical label
  (aliases, native spellings, a fuzzy fallback for misspellings) and to the base language the LID can verify
  (Cantonese -> Chinese, Swiss German -> German, ...).
- `free`: the prompt language (pipeline `detect_language`) must equal the base of the persona's native or main
  language (non-Latin prompts fall back to script-compatible personas). Tiers: location keywords -> best MiniLM inside
  the location pool; else top MiniLM over the language pool (similarity >= 0.15); else an md5 pick. A persona serves
  at most `--cap 40` seeds; capped candidates are skipped within each tier.
- `multilingual`: personas with a resolved non-English target, in a fixed hash order, assigned without replacement
  (cycling when exhausted); `target_language` is the canonical label used in the translation prompt.
- Responder: Gemma / Ministral 50/50 by hash. Held-out sample (`--holdout-free 4002 --holdout-multilingual 6000`):
  the lowest-ranked seeds with a persona, equal per source, written to `holdout.txt` and skipped by the driver.

### Generation (`run_augmentation.py --input-kind seeds`)

Settings (`BASE_CONFIG`, shared by both sets): generation T 0.3, top_p 0.95, 4,096 tokens; sanity / continuity judge
T 0.1, 3,072 tokens; adaptation 8,192 tokens; up to 2 continuity adaptations and 3 retries; persona temperature 0.7,
verbal quirk probability 0.25; literal translation T 0.3. The cross-lingual check (`lang_ok_base`) compares the
detected language of each restyled turn with the base of the target; targets the detector cannot label, and Uzbek
(lid.176 reads Latin Uzbek as Turkish), are accepted unchecked. Conversation id = sha256 of
`[namespace, pair_key, mode]` (namespace fixed per input kind, see `run_augmentation.NAMESPACE`), so reruns
keep the same ids. Status per conversation: `pass`, `fail`, `lang_fail`, `no_persona`, `error`.

### Corpus records (`build_corpus.py`)

`--stage user`: `pass` conversations -> release records (`text_language` = LID of the first user turn), duplicate
ids and torn lines skipped, one record per normalized source text and language (free first), sharded by md5(id);
also `assistant_input/` with the fixed user turns for assistant-side regeneration. `--stage final`: the assistant
turns of the user-side pass are final (`sanity_verdicts` = the user-side verdicts).

## Persona pairs

```bash
python -m personafactory.augmentation.prepare_pairs --bank $PF_BANK --out-dir ./data/pairs
python -m personafactory.augmentation.embed_personas --bank $PF_BANK --pairs-dir ./data/pairs --out-dir ./outputs/assign
python -m personafactory.augmentation.select_personas --bank $PF_BANK --pairs-dir ./data/pairs --out-dir ./outputs/assign
for mode in free multilingual; do      # see scripts/slurm/example_augmentation.sbatch
  python -m personafactory.augmentation.run_augmentation --input-kind pairs --pairs ./data/pairs/*.jsonl --mode $mode \
      --assign-dir ./outputs/assign --outdir ./outputs/generated --bank $PF_BANK --lid-model $PF_LID_MODEL \
      --gemma $PF_GEMMA_URL --ministral $PF_MINISTRAL_URL --minimax $PF_MINIMAX_URL --concurrency 100 &
done; wait
python -m personafactory.augmentation.extract_accepted --in-dir ./outputs/generated --out-dir ./outputs/accepted --bank $PF_BANK
```

`free` personas come from the tiered selection without a cap; `multilingual` personas are drawn uniformly by hash
over personas with a resolved language (`target_language` of the pair records, strict core label table). Their
release build is `release/build_release.py` followed by the assistant regeneration in `assistant/`.

## Seed pool commands

```bash
python -m personafactory.augmentation.prepare_seeds --ultrachat 'src/ultrachat/train_*.jsonl' \
    --nemotron src/nemotron/chat_if.jsonl --wildchat 'src/wildchat/data/train-*.parquet' \
    --exclude-release "$PAIRS_REL/data/*.jsonl" --exclude-pairs ./data/pairs --exclude-responses ./data/responses.jsonl \
    --work ./data/seeds --procs 140
python -m personafactory.augmentation.embed_personas --bank $PF_BANK --seeds-dir ./data/seeds/shards \
    --out-dir ./outputs/assign_seeds --dtype float16 --batch-size 1024                    # 1 GPU
python -m personafactory.augmentation.select_personas --bank $PF_BANK --seeds-dir ./data/seeds/shards \
    --out-dir ./outputs/assign_seeds --cap 40 --holdout-free 4002 --holdout-multilingual 6000 --workers 140
# one 2-node unit per array task (scripts/slurm/corpus_generate.sbatch), 44 units:
python -m personafactory.augmentation.run_augmentation --input-kind seeds --pairs <every 44th shard of the mode> \
    --mode free --assign-dir ./outputs/assign_seeds --exclude ./outputs/assign_seeds/holdout.txt \
    --outdir ./outputs/seeds_run/gen --bank $PF_BANK --lid-model $PF_LID_MODEL \
    --gemma $GEMMA_URL --ministral $MINISTRAL_URL --minimax $JUDGE_URL --concurrency 100
python -m personafactory.augmentation.build_corpus --stage user --run ./outputs/seeds_run --shards 200 --workers 128
python -m personafactory.augmentation.build_corpus --stage final --run ./outputs/seeds_run
```

The driver skips conversation ids already in its output file, so an interrupted run is resumed by rerunning the same
command; shard files can be split over several jobs (each with its own servers) as long as each shard file is
processed by one job at a time. `--select` / `--responder gemma` regenerate a subset with Gemma under the same ids
(used by `postprocess/`).

## Models and serving

`google/gemma-4-31B-it` and `mistralai/Ministral-3-14B-Instruct-2512` with vLLM (TP 2 each on one 4-GPU node, served
names `gemma` / `ministral`), `MiniMaxAI/MiniMax-M2.5` with SGLang (TP 4 / EP 4 on its own node, reasoning parser
`minimax-append-think`, served name `MiniMax-M2.5`). Context length 65,536 for the seed pool, 32,768 for the persona
pairs. `scripts/slurm/serve_models.sh` starts them and exports the endpoints.

## Formats

Persona bank (`$PF_BANK`): JSONL, one persona per line with `id`, `background` (country, sub_region, native_language,
main_language, dialect, occupation, ...), `style` (chatting_style, chatting_style_structured, example_message,
linguistic_quirks, ...), `character_description`.

Persona-pair seeds (`prepare_pairs.py`, `NNNN.jsonl` shards of 512): `{pair_key, persona_id, target_language,
language_resolution, conversation, source_id, source_name, source_license, split, seed, assignment_index}`.

Seed pool (`prepare_seeds.py`): `{pair_key, seed_id, source_id, source_name, mode, seed_language, conversation, split,
source_user_words, retained_user_turns, source_truncated, source_metadata}`.

Assignments (`<assign-dir>/{free,multilingual}.jsonl`): `{pair_key, mode, persona_id (null if none), match_tier
(location | embedding | language_pool | none | unsupported_language | cross_lingual), responder (gemma | ministral),
target_language}`; the seed pool adds `source_name`, `source_language_detected`, `source_script`, `pool`, `capped`
(free) or `lid_base`, `lid_verifiable` (multilingual), and `select_stats.json`.

Driver output (`<outdir>/<mode>-<shard>.jsonl`): `{key, pair_key, mode, persona_id, match_tier, responder,
target_language, source_id, source_name, split, [seed_language, lid_verifiable,] pipeline, status, [sanity_status,]
result}`; `result` has `conversation`, `source_conversation` and `metadata.turns_detail` (per turn: source,
translated and rewritten user message, persona flags, continuity adaptations, sanity verdicts).

Seed-pool records (`build_corpus.py`): `{id, conversation, persona_id, target_language, text_language, language_mode,
source_text, source_name, source_id, seed_language, responder, num_turns, match_basis, split, lid_verifiable,
user_sanity_verdicts, sanity_verdicts, assistant_generation}`.

## Environment variables

`PF_BANK` (persona bank), `PF_DATA_DIR` (default `./data`), `PF_OUT_DIR` (default `./outputs`), `PF_LID_MODEL`
(fastText `lid.176.ftz`), `PF_GEMMA_URL`, `PF_MINISTRAL_URL`, `PF_MINIMAX_URL` (OpenAI-compatible `.../v1` base
URLs), optional `PF_GEMMA_MODEL` / `PF_MINISTRAL_MODEL` / `PF_MINIMAX_MODEL` (served names, default `gemma`,
`ministral`, `MiniMax-M2.5`) and `PF_API_KEY`.
