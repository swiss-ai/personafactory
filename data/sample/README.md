# Data sample

A small, fixed sample of the released dataset ([swiss-ai/PersonaFactory](https://huggingface.co/datasets/swiss-ai/PersonaFactory)) for inspection without downloading it.

| File | Contents |
|---|---|
| `conversations_sample.json` | 341 conversations from the `chats` subset: up to two per (language, setting) for all 86 language labels (85 languages plus the label for turns too short to detect), plus at least three per (seed source, setting, responder, with or without model persona) |
| `persona_bank_sample.json` | the 336 personas these conversations use, from the `persona_bank` subset (background, style, validation) |
| `model_personas.json` | the 12 assistant response styles (model personas) |

Records use the released schema (see the dataset card and `docs/DATA.md`). `persona_id` joins a conversation to its
persona, `model_persona` names its assistant style (empty for conversations without one), and `original_prompt` is
the seed's first user turn before rewriting. `setting` is `language_matched` (the rewrite keeps the seed's language)
or `cross_lingual` (an English seed is translated into the persona's language, then restyled). Conversations were
chosen by a fixed hash of their id, skipping those longer than 12,000 characters to keep the files small.

```python
import json
convs = json.load(open("data/sample/conversations_sample.json"))
bank = {p["id"]: p for p in json.load(open("data/sample/persona_bank_sample.json"))}
c = convs[0]
print(bank[c["persona_id"]]["style"]["chatting_style"])
print(c["original_prompt"], "->", c["messages"][0]["content"])
```

## License

The sample follows the license of the released dataset (see the [dataset card](https://huggingface.co/datasets/swiss-ai/PersonaFactory)). `original_prompt` and other text that comes from the seed conversations (WildChat, UltraChat, Nemotron Instruction-Following Chat) stays under the terms of those datasets.
