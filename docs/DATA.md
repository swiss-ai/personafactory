# Data layout

## Released data

The dataset is on Hugging Face as [`swiss-ai/PersonaFactory`](https://huggingface.co/datasets/swiss-ai/PersonaFactory)
with two subsets, one `train` split each:

```python
from datasets import load_dataset
chats = load_dataset("swiss-ai/PersonaFactory", "chats", split="train")          # 1,237,976 conversations
bank = load_dataset("swiss-ai/PersonaFactory", "persona_bank", split="train")    # 743,010 profiles
```

`persona_bank` fields:

| Field | Description |
|---|---|
| `id` | profile id; referenced by `persona_id` in `chats` |
| `generator_model` | model that generated the profile (`google/gemma-4-31B-it`, `mistralai/Ministral-3-14B-Instruct-2512`, `zai-org/GLM-4.7-Flash`) |
| `background` | `region`, `country`, `sub_region`, `occupation`, `sector`, `job_title`, `education` (`level`, `field_of_study`, `institution_type`), `age`, `gender`, `main_language`, `native_language`, `dialect`, `hobbies_interests`, `ai_stance`, `digital_fluency`, `llm_user_segment` |
| `style` | `sentence_length_tendency`, `question_framing`, `native_language_error_patterns`, `code_switching_freq`, `code_switching_type`, `reference_pool`, `chatting_style`, `chatting_style_structured` (`capitalization`, `punctuation`, `emoji_use`, `abbreviation_habits`, `message_structure`, `typo_tendency`, `greeting_signoff`), `example_message`, `chatbot_language_pref`, `linguistic_quirks` |
| `character_description` | short free-text description |
| `validation` | judge scores: `coherent`, `location_plausible`, `llm_user_plausible`, `stereotype_severity` (0 to 3), `realism` (1 to 3) |

`chats` fields:

| Field | Description |
|---|---|
| `id` | conversation id |
| `messages` | `[{role, content}, ...]`, alternating `user` and `assistant` |
| `persona_id` | profile in `persona_bank` |
| `language` | detected language of the first user turn (null when too short) |
| `setting` | `language_matched` or `cross_lingual` |
| `match_tier` | `location`, `embedding`, `language_pool` or `cross_lingual` |
| `source`, `source_id` | seed dataset (`wildchat`, `ultrachat`, `nemotron`) and seed conversation id where available |
| `original_prompt` | first user turn of the seed, before rewriting |
| `num_turns` | number of user turns |
| `responder` | model that generated the assistant turns |
| `model_persona` | assistant response style (`personafactory/assistant/model_personas.json`), or null |
| `sanity_verdicts` | per-turn sanity-gate verdicts |

`data/sample/` holds a small sample of both subsets in this schema.

## Working directories

Scripts read inputs from `$PF_DATA_DIR` and write to `$PF_OUT_DIR` (see `configs/.env.example`); every path can also
be passed on the command line. The layout used by `scripts/examples/`:

```
$PF_DATA_DIR/
├── persona_bank/              persona bank build (persona_bank.sh): generator shards, judge shards, filtered sets,
│                              the assembled bank (PF_BANK points to it, or to the released subset)
├── seeds/
│   ├── src/                   local copies of the seed datasets (UltraChat, Nemotron Instruction-Following Chat,
│   │                          WildChat-4.8M)
│   └── shards/                seed pool written by augmentation.prepare_seeds (PF_SEEDS_DIR)
├── pairs/                     persona-first seed pairs written by augmentation.prepare_pairs
├── lid.176.ftz                fastText language ID (PF_LID_MODEL)
└── style_extension/           converted external persona records (style_extension.sh)

$PF_OUT_DIR/
├── assign_seeds/              embeddings, persona / responder assignment, held-out persona sample
├── seeds_run/                 generation output (gen/), corpus records (user/, final/)
├── accepted/                  accepted records of the persona-pair runs (augmentation.extract_accepted)
├── assistant/                 assistant regeneration with model personas and the leak filter
├── release_pairs/             persona-pair release part (release.build_release, scrub_emoji, swap_assistant)
├── release_merged/            merged corpus; the post-processing stages work in place here
│   ├── data/                  NNNN.jsonl shards (the input of release.build_hf)
│   ├── persona_bank.jsonl     profiles of every persona used
│   └── summary.json           counts
├── lowres_quality/, asst_regen/, judge_sample/     post-processing work directories
├── corpus_judge/              corpus-scale judge items, verdicts and aggregates
├── hf_release/                parquet shards and dataset card (release.build_hf, build_hf_cards)
├── style_extension/, downstream/                   evaluation outputs
```

Generation and judge shards are append-only JSONL and every stage resumes from what is already written, so a killed
job can be resubmitted unchanged.
