# assistant: model personas and assistant-side regeneration

Model personas are assistant response styles. They govern how the assistant presents an answer, never what it
says. The released corpus pairs every persona-conditioned user side with an assistant side regenerated under the
paper's user-persona system prompt plus a matched model persona. Persona names are bookkeeping only; they never
enter a prompt.

Run everything from the repository root as `python -m personafactory.assistant.<module> ...`.

## Files

| file | purpose |
|---|---|
| `model_personas.json` | the 12 model personas (style description, axes, signature quirks, content safeguards) |
| `model_persona.py` | persona rendering, style section, quirk sampling, continuity reminder, matcher prompts, restyle prompt, judge prompts (style, content, fit, instruction following); used by `augmentation.pipeline` |
| `shared.py` | helpers: hashing, bank lookup, ranking parser, resumable outputs, server arguments, post-hoc restyler |
| `prepare_inputs.py` | builds the regeneration inputs (fixed user turns + per-turn metadata) for every corpus conversation |
| `regenerate_assistant.py` | matching and regeneration of the assistant side over the corpus (arms A, B, C) |
| `leak_filter.py` | instruction-echo / persona-name leak scan, leak ids, clean-set assembly |
| `augment_assistant_only.py` | model personas for any chat dataset without a user persona (assign, regen, none, restyle) |
| `eval_assistant_only.py` | judge-based evaluation of the assistant-only variants |
| `system_prompt_check.py` | programmatic compliance with checkable system prompts (assistant-only mode) |
| `pilot_regenerate.py` | data-level pilots: sample, match, regenerate one arm |
| `pilot_restyle.py` | design pilot, restyled arm |
| `pilot_eval.py` | pilot evaluation (design and main presets) |

## Endpoints and environment

All generation scripts talk to OpenAI-compatible servers (vLLM / SGLang). URLs are base URLs ending in `/v1`;
a comma-separated list spreads calls over replicas.

| argument | env var | meaning |
|---|---|---|
| `--gemma`, `--gemma-model` | `PF_GEMMA_URL`, `PF_GEMMA_MODEL` (default `gemma`) | responder google/gemma-4-31B-it |
| `--ministral`, `--ministral-model` | `PF_MINISTRAL_URL`, `PF_MINISTRAL_MODEL` (default `ministral`) | responder mistralai/Ministral-3-14B-Instruct-2512 |
| `--minimax`, `--minimax-model` | `PF_MINIMAX_URL`, `PF_MINIMAX_MODEL` (default `MiniMax-M2.5`) | matcher, sanity gate and judge MiniMaxAI/MiniMax-M2.5 |
| `--bank` | `PF_BANK` | persona bank JSONL |
| `--lid-model` | `PF_LID_MODEL` | fastText lid.176 (pilot regeneration only) |
| | `PF_API_KEY` | API key, if the servers need one |
| | `PF_OUT_DIR` | default output root (`./outputs`) |
| | `AO_SYS_POSITION` | assistant-only mode with `--with-system apply`: `last` (default) puts the dataset's system prompt after the style as overriding constraints; `first` puts the style below it. Read by `augmentation.pipeline`. |

## Assistant side of the corpus

```
# 1. inputs: fixed user turns + original user turns + persona_applied flags per turn
python -m personafactory.assistant.prepare_inputs --corpus-dir ./data/corpus --records './outputs/accepted/*/*.jsonl' \
    --out-dir ./outputs/assistant/input

# 2. match a model persona per conversation (reduced user card + first user message)
python -m personafactory.assistant.regenerate_assistant --stage match --input-dir ./outputs/assistant/input --out-dir ./outputs/assistant

# 3. regenerate the assistant side (the three stages can run concurrently; --part k/n splits the work)
for st in default user_persona user_persona_model_persona; do
  python -m personafactory.assistant.regenerate_assistant --stage $st --input-dir ./outputs/assistant/input --out-dir ./outputs/assistant
done

# 4. leak filter: scan, regenerate leaking conversations, assemble the clean set
python -m personafactory.assistant.leak_filter phrases --arms-dir ./outputs/assistant
python -m personafactory.assistant.leak_filter names   --arms-dir ./outputs/assistant
python -m personafactory.assistant.regenerate_assistant --stage user_persona_model_persona --input-dir ./outputs/assistant/input \
    --out-dir ./outputs/assistant --ids ./outputs/assistant/leaks/leak_ids.txt --out-name user_persona_model_persona_leakfix
python -m personafactory.assistant.leak_filter assemble --arms-dir ./outputs/assistant
```

Stages: `default` (arm A, no system prompt), `user_persona` (arm B, the paper's persona system prompt),
`user_persona_model_persona` (arm C, B plus the matched model persona; the assistant side of released conversations that carry a model persona). Outputs are
JSONL rows `{id, arm, model_persona, responder, status, conversation, sanity_verdicts, quirks, adaptations}` in
`<out-dir>/<stage>/<shard>.jsonl`; the clean arm C is `<out-dir>/user_persona_model_persona_clean/`. The release
build keeps the sanity-pass rows of the clean set; arms A, B and C also feed the SFT ablation (`sft_ablation/`).

The leak filter compares each phrase's rate in arm C with the two baselines (A, B have no model persona in the
prompt). The leak ids are the arm C conversations with a persona name, a "<name>-style" label, the "optional
touch" wording or a "(no sign-off" aside that no user message contains. Their regenerations replace them when
leak-free under the same patterns; those that leak again are dropped.

## Assistant-only mode (datasets without a user persona)

```
python -m personafactory.assistant.augment_assistant_only --step assign --input data/*.jsonl --outdir ./outputs/assistant_only
python -m personafactory.assistant.augment_assistant_only --step regen  --input data/*.jsonl --outdir ./outputs/assistant_only
# optional: control and post-hoc restyle, then evaluation (needs --keep-source on the step runs)
python -m personafactory.assistant.augment_assistant_only --step none    --input data/*.jsonl --outdir ./outputs/assistant_only --keep-source
python -m personafactory.assistant.augment_assistant_only --step restyle --input data/*.jsonl --outdir ./outputs/assistant_only --keep-source
python -m personafactory.assistant.eval_assistant_only --outdir ./outputs/assistant_only
```

- `assign`: the matcher sees only the user's own messages (first 3). `--assign top3` samples from the top 3,
  `random`, `fixed:<persona id>` need no judge.
- `regen`: style section, quirk (p = 0.25) and content rules in the system prompt on every turn, continuity loop
  and sanity gate; Gemma / Ministral 50/50 per conversation.
- `restyle`: post-hoc restyle of the source replies with protected spans (Gemma by default).
- `none`: regeneration without a persona (control).
- Conversations with a system prompt pass through unchanged by default (`--with-system skip`).
  System-prompt test: build single-turn rows with the prompts in `system_prompt_check.SYSTEM_PROMPTS` (row id
  `<set>-<kind>-<source id>`), run `none` and `regen` with `--with-system apply` under `AO_SYS_POSITION=first`
  and `=last`, then `python -m personafactory.assistant.system_prompt_check <output files>`.

## Data-level pilots (appendix)

Source conversations are accepted records of `augmentation.run_augmentation`. The `source` arm is the reply
generated with the user persona in the system prompt.

Design pilot (all accepted records of a small pilot run in `SRC`):

```
python -m personafactory.assistant.pilot_regenerate match --source-dir SRC --out-dir ./outputs/pilot_design
for arm in user_persona user_persona_model_persona user_persona_random_model_persona; do
  python -m personafactory.assistant.pilot_regenerate regenerate --arm $arm --source-dir SRC --out-dir ./outputs/pilot_design
done
python -m personafactory.assistant.pilot_restyle --source-dir SRC --out-dir ./outputs/pilot_design
python -m personafactory.assistant.pilot_eval --preset design --source-dir SRC --out-dir ./outputs/pilot_design
```

Main pilot (1,000 corpus conversations, 300 with later-turn instructions):

```
python -m personafactory.assistant.pilot_regenerate sample --runs './outputs/generated/*.jsonl' --corpus-dir ./data/corpus \
    --source-dir ./outputs/pilot_main/src --n-random 700 --n-instruction 300
python -m personafactory.assistant.pilot_regenerate match --source-dir ./outputs/pilot_main/src --out-dir ./outputs/pilot_main
for arm in default default_resample model_persona user_persona_model_persona; do
  python -m personafactory.assistant.pilot_regenerate regenerate --arm $arm --source-dir ./outputs/pilot_main/src --out-dir ./outputs/pilot_main
done
python -m personafactory.assistant.pilot_eval --preset main --source-dir ./outputs/pilot_main/src --out-dir ./outputs/pilot_main
```

Arms: `default` (no system prompt), `default_resample` (independent second default sample, content noise floor),
`user_persona` (persona system prompt, regenerated), `model_persona` (matched model persona only),
`user_persona_model_persona` (both), `user_persona_random_model_persona` (persona system prompt + random model
persona), `restyled` (source replies restyled post hoc). `pilot_eval` writes `<out-dir>/eval.json` with style
adoption, content agreement with the reference arm, continuity, instruction compliance, sanity (restyled arm),
formatting statistics and pairwise fit.

The pilots use the persona set in `model_personas.json` with name-free prompts.
