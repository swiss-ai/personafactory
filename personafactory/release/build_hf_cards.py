#!/usr/bin/env python3
"""Dataset card (README.md) of the Hugging Face release, generated from <hf-dir>/{bank,chats}/stats.json
(written by build_hf.py). One dataset repo with two subsets, `chats` (default) and `persona_bank`, each with a single
train split. Every number in the card comes from the stats files; the prose is fixed text. The per-subset cards are
rendered first and merged into one card with a shared intro, license and citation section.

  python -m personafactory.release.build_hf_cards --hf-dir $PF_OUT_DIR/hf_release
"""
import argparse, json, os

ISO = {'English': 'en', 'Chinese': 'zh', 'Spanish': 'es', 'Russian': 'ru', 'French': 'fr', 'Arabic': 'ar', 'Indonesian': 'id',
       'Vietnamese': 'vi', 'Portuguese': 'pt', 'German': 'de', 'Italian': 'it', 'Japanese': 'ja', 'Thai': 'th', 'Tagalog': 'tl',
       'Polish': 'pl', 'Korean': 'ko', 'Ukrainian': 'uk', 'Dutch': 'nl', 'Bengali': 'bn', 'Persian': 'fa', 'Turkish': 'tr',
       'Croatian': 'hr', 'Romanian': 'ro', 'Swedish': 'sv', 'Greek': 'el', 'Hindi': 'hi', 'Albanian': 'sq', 'Swahili': 'sw',
       'Hungarian': 'hu', 'Burmese': 'my', 'Czech': 'cs', 'Finnish': 'fi', 'Danish': 'da', 'Norwegian': 'no', 'Bulgarian': 'bg',
       'Urdu': 'ur', 'Malay': 'ms', 'Slovak': 'sk', 'Bosnian': 'bs', 'Tamil': 'ta', 'Punjabi': 'pa', 'Lithuanian': 'lt',
       'Azerbaijani': 'az', 'Slovenian': 'sl', 'Catalan': 'ca', 'Macedonian': 'mk', 'Estonian': 'et', 'Amharic': 'am',
       'Icelandic': 'is', 'Belarusian': 'be', 'Somali': 'so', 'Latin': 'la', 'Telugu': 'te', 'Yoruba': 'yo', 'Kannada': 'kn',
       'Kazakh': 'kk', 'Serbian': 'sr', 'Latvian': 'lv', 'Nepali': 'ne', 'Hebrew': 'he', 'Cebuano': 'ceb', 'Marathi': 'mr',
       'Sotho': 'st', 'Sinhala': 'si', 'Mongolian': 'mn', 'Pashto': 'ps', 'Welsh': 'cy', 'Zulu': 'zu', 'Gujarati': 'gu',
       'Shona': 'sn', 'Ganda': 'lg', 'Esperanto': 'eo', 'Basque': 'eu', 'Georgian': 'ka', 'Xhosa': 'xh', 'Afrikaans': 'af',
       'Luxembourgish': 'lb', 'Tsonga': 'ts', 'Armenian': 'hy', 'Sindhi': 'sd', 'Tswana': 'tn', 'Irish': 'ga', 'Maori': 'mi',
       'Uzbek': 'uz', 'Romansh': 'rm'}

TITLE = 'PersonaFactory: Stylistic User Prompt Augmentation with Synthetic Persona Bank'
AUTHORS = 'Bich Ngoc Doan, Hanna Yukhymenko and Imanol Schlag'
CITATION = """```bibtex
@misc{doan2026personafactorystylisticuserprompt,
      title={PersonaFactory: Stylistic User Prompt Augmentation with Synthetic Persona Bank},
      author={Bich Ngoc Doan and Hanna Yukhymenko and Imanol Schlag},
      year={2026},
      eprint={2611.34785},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2611.34785},
}
```"""
# per-subset cards are rendered with placeholder repo names; merged_card() rewrites them to the one repo (REPO)
BANK_REPO, CHATS_REPO = 'swiss-ai/PersonaFactory-PersonaBank', 'swiss-ai/PersonaFactory-Chats'


def badges(other_repo, other_label):
    return '\n'.join([
        f'[![{other_label}](https://img.shields.io/badge/%F0%9F%A4%97%20Dataset-{other_label.replace(" ", "%20")}-yellow)](https://huggingface.co/datasets/{other_repo})',
        '[![arXiv](https://img.shields.io/badge/arXiv-2611.34785-b31b1b)](https://arxiv.org/abs/2611.34785)'])


def iso_codes(names):
    """Language names -> ISO 639 codes (ISO table first, then langcodes); names without a code are skipped."""
    import langcodes
    out = set()
    for n in names:
        if n in ISO:
            out.add(ISO[n]); continue
        try:
            code = langcodes.find(n.split('(')[0].strip()).language
            if code and code != 'und':
                out.add(code)
        except LookupError:
            pass
    return out


def fmt(n):
    return f'{n:,}'


def top(d, k, total):
    return [(a, b, 100 * b / total) for a, b in list(d.items())[:k]]


def yaml_list(xs):
    return '\n'.join(f"- '{x}'" if x in ('no', 'yes', 'on', 'off') else f'- {x}' for x in xs)


def bank_card(s):
    n = s['n']
    langs = sorted({ISO[l] for l in s['main_language'] if l in ISO})
    head = f"""---
pretty_name: PersonaFactory Persona Bank
license: apache-2.0
size_categories:
- 100K<n<1M
task_categories:
- text-generation
tags:
- synthetic
- personas
- user-simulation
- multilingual
multilinguality: multilingual
language:
{yaml_list(langs)}
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train-*
---
"""
    reg = '\n'.join(f'| {a} | {fmt(b)} | {p:.1f} |' for a, b, p in top(s['region'], 13, n))
    gen = '\n'.join(f'| `{a}` | {fmt(b)} | {p:.1f} |' for a, b, p in top(s['generator_model'], 5, n))
    body = f"""# PersonaFactory Persona Bank

{badges(CHATS_REPO, 'PersonaFactory Chats')}

The PersonaFactory Persona Bank is the synthetic user-persona bank of *"{TITLE}"* by {AUTHORS}.

It contains **{fmt(n)} profiles** from **{s['countries']} countries** and **{fmt(s['sub_regions'])} sub-regions**, sampled on a per-country grid over demographic, occupational and linguistic attributes. Every profile has two layers:

* **Background**: who the person is (region, country, sub-region, occupation and education, age, gender, main and native language, dialect, hobbies, attitude towards AI, digital fluency).
* **Style**: how the person types to a chatbot (sentence length, question framing, native-language error patterns, code-switching, a reference pool of things they mention, structured typing habits such as capitalization, punctuation, emoji, abbreviations, typos and greetings, linguistic quirks, and an example message).

Profiles were generated by three open-weight models and screened by an LLM judge (`MiniMax-M2.5`) for internal coherence, location and user plausibility, realism and stereotypes; only profiles the judge kept are released. The bank is used to restyle user turns of chat data, see [PersonaFactory Chats](https://huggingface.co/datasets/{CHATS_REPO}).

```python
from datasets import load_dataset

bank = load_dataset("{BANK_REPO}", split="train")
```

## Composition

| Macro-region | Profiles | % |
|---|---|---|
{reg}

| Generator | Profiles | % |
|---|---|---|
{gen}

## Fields

| Field | Description |
|---|---|
| `id` | profile id; referenced by `persona_id` in PersonaFactory Chats |
| `generator_model` | model that generated the profile |
| `background` | background layer: `region`, `country`, `sub_region`, `occupation`, `sector`, `job_title`, `education` (`level`, `field_of_study`, `institution_type`), `age`, `gender`, `main_language`, `native_language`, `dialect`, `hobbies_interests`, `ai_stance`, `digital_fluency`, `llm_user_segment` |
| `style` | style layer: `sentence_length_tendency`, `question_framing`, `native_language_error_patterns`, `code_switching_freq`, `code_switching_type`, `reference_pool`, `chatting_style` (free text), `chatting_style_structured` (`capitalization`, `punctuation`, `emoji_use`, `abbreviation_habits`, `message_structure`, `typo_tendency`, `greeting_signoff`), `example_message`, `chatbot_language_pref`, `linguistic_quirks` |
| `character_description` | short free-text description of the person |
| `validation` | judge scores: `coherent`, `location_plausible`, `llm_user_plausible`, `stereotype_severity` (0 to 3, lower is better), `realism` (1 to 3) |

## Intended use and limitations

The bank is meant for user simulation and for augmenting chat data with realistic, diverse user voices. The profiles are synthetic and do not describe real people. The bank is not a representative sample of any population: it is younger, more highly educated and more digitally fluent than the general population, and occupations concentrate on students and technology roles. Dialect labels are free text and not a validated dialect taxonomy.

## License

Released under the Apache 2.0 license. Profiles were generated with `google/gemma-4-31B-it`, `mistralai/Ministral-3-14B-Instruct-2512` and `zai-org/GLM-4.7-Flash`; please also follow their terms of use.

## Citation

{CITATION}
"""
    return head + body


def chats_card(s):
    n = s['n']
    langs = ['en'] + sorted({ISO[l] for l in s['language'] if l in ISO} - {'en'})
    src = '\n'.join(f'| {a} | {fmt(b)} | {p:.1f} |' for a, b, p in top(s['source'], 5, n))
    lang = '\n'.join(f'| {a} | {fmt(b)} | {p:.1f} |' for a, b, p in top(s['language'], 15, n))
    tier = '\n'.join(f'| `{a}` | {fmt(b)} | {p:.1f} |' for a, b, p in top(s['match_tier'], 5, n))
    resp = '\n'.join(f'| `{a}` | {fmt(b)} | {p:.1f} |' for a, b, p in top(s['responder'], 5, n))
    turns = '\n'.join(f'| {a} | {fmt(b)} | {100 * b / n:.1f} |' for a, b in sorted(s['num_turns'].items()))
    nmp = n - s['model_persona'].get('none', 0)
    head = f"""---
pretty_name: PersonaFactory Chats
license: odc-by
size_categories:
- 1M<n<10M
task_categories:
- text-generation
tags:
- synthetic
- personas
- user-simulation
- multilingual
- conversational
- sft
multilinguality: multilingual
language:
{yaml_list(langs)}
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train-*
---
"""
    body = f"""# PersonaFactory Chats

{badges(BANK_REPO, 'PersonaFactory Persona Bank')}

PersonaFactory Chats is the conversational dataset of *"{TITLE}"* by {AUTHORS}.

It contains **{fmt(n)} multi-turn conversations** ({fmt(s['user_turns']['all'])} user turns) in **{len([l for l in s['language'] if l != 'undetermined'])} languages**. Each conversation starts from a real seed conversation ([WildChat](https://huggingface.co/datasets/allenai/WildChat-1M), [UltraChat](https://huggingface.co/datasets/HuggingFaceH4/ultrachat_200k) or [Nemotron Instruction-Following Chat](https://huggingface.co/datasets/nvidia/Nemotron-Instruction-Following-Chat-v1)) and is matched to a profile from the [PersonaFactory Persona Bank](https://huggingface.co/datasets/{BANK_REPO}):

1. **User turns** are rewritten in the persona's voice (typing habits, register, code-switching, quirks) while the request stays the same. Quoted text, code, numbers and strict-format tasks are protected; turns that cannot be restyled safely are kept verbatim.
2. **Assistant turns** are regenerated for that user by the responder model, with the user persona in the system prompt; {fmt(nmp)} conversations additionally use a matched assistant response style (`model_persona`).
3. A next-turn continuity check and a per-turn LLM sanity gate (`MiniMax-M2.5`) filter the result; only conversations that pass every check are released.

There are two settings. In the **language-matched** setting the persona shares the language of the seed prompt. In the **cross-lingual** setting a persona is drawn from the whole bank and the user turns are translated into the persona's language before they are restyled, so the conversation moves into that language.

```python
from datasets import load_dataset

chats = load_dataset("{CHATS_REPO}", split="train")
print(chats[0]["messages"])
```

The subset has a single `train` split. To hold out data without seed leakage, split by `source_id`, which identifies the seed conversation where available.

## Composition

| Seed source | Conversations | % |
|---|---|---|
{src}

| Language (first user turn) | Conversations | % |
|---|---|---|
{lang}

| Persona match tier | Conversations | % |
|---|---|---|
{tier}

| Responder | Conversations | % |
|---|---|---|
{resp}

| User turns | Conversations | % |
|---|---|---|
{turns}

## Fields

| Field | Description |
|---|---|
| `id` | conversation id |
| `messages` | the conversation, a list of `{{role, content}}` with alternating `user` and `assistant` turns |
| `persona_id` | id of the matched profile in the [Persona Bank](https://huggingface.co/datasets/{BANK_REPO}) |
| `language` | detected language of the first user turn (null when too short to detect) |
| `setting` | `language_matched` or `cross_lingual` |
| `match_tier` | how the persona was matched: `location` (place named in the prompt), `embedding` (topic similarity), `language_pool` (language only) or `cross_lingual` |
| `source`, `source_id` | seed dataset and, where available, the id of the seed conversation |
| `original_prompt` | first user turn of the seed conversation, before rewriting |
| `num_turns` | number of user turns |
| `responder` | model that generated the assistant turns |
| `model_persona` | assistant response style used for the assistant turns, or null |
| `sanity_verdicts` | per-turn sanity-gate verdicts |

## Intended use and limitations

The dataset is meant for supervised fine-tuning and evaluation of assistants on diverse, realistically written user messages, and for research on user simulation. User turns are synthetic rewrites of real prompts, and assistant turns are model generations that passed an automatic gate; they can still contain errors. Casual style markers (greetings, slang, emoji, repeated punctuation) occur more often than in real user messages. Languages, regions and seed sources are not evenly represented.

## License

Released under the [ODC-BY](https://opendatacommons.org/licenses/by/1-0/) license. The seed conversations come from WildChat (ODC-BY), UltraChat (MIT) and Nemotron Instruction-Following Chat (CC BY 4.0), and the text was generated with `google/gemma-4-31B-it` and `mistralai/Ministral-3-14B-Instruct-2512`; please also follow their terms.

## Citation

{CITATION}
"""
    return head + body


REPO = 'swiss-ai/PersonaFactory'


def merged_card(b, c):
    """One repo, two subsets: persona_bank (train) and chats (train). Body sections reuse the
    per-dataset cards with their YAML headers, titles and citations stripped."""
    def body(card):
        card = card.split('---\n', 2)[2]
        card = card.split('\n## License')[0]  # one license and citation section for the whole repo
        lines = card.split('\n')
        lines = [l for l in lines if not l.startswith('[![') and not l.startswith('# ')]
        return '\n'.join(lines).strip()
    bt = body(bank_card(b)).replace(f'load_dataset("{BANK_REPO}", split="train")', f'load_dataset("{REPO}", "persona_bank", split="train")')
    ct = body(chats_card(c)).replace(f'load_dataset("{CHATS_REPO}", split="train")', f'load_dataset("{REPO}", "chats", split="train")')
    for old in (f'https://huggingface.co/datasets/{BANK_REPO}', f'https://huggingface.co/datasets/{CHATS_REPO}'):
        bt, ct = bt.replace(old, '#'), ct.replace(old, '#')
    bt = bt.replace('[PersonaFactory Chats](#)', 'the `chats` subset')
    ct = ct.replace('[PersonaFactory Persona Bank](#)', 'the `persona_bank` subset').replace('[Persona Bank](#)', '`persona_bank` subset')
    bt = bt.replace('referenced by `persona_id` in PersonaFactory Chats', 'referenced by `persona_id` in the `chats` subset')
    ct = ct.replace('from the the `persona_bank` subset', 'from the `persona_bank` subset')
    # the repo intro already names the paper; drop the per-subset paper sentence and duplicate load snippets
    for t in ('bt', 'ct'):
        v = locals()[t]
        v = '\n\n'.join(p for p in v.split('\n\n') if not p.startswith(('The PersonaFactory Persona Bank is the', 'PersonaFactory Chats is the')))
        v = v.replace('```python\nfrom datasets import load_dataset\n\nbank = load_dataset("swiss-ai/PersonaFactory", "persona_bank", split="train")\n```\n\n', '')
        v = v.replace('```python\nfrom datasets import load_dataset\n\nchats = load_dataset("swiss-ai/PersonaFactory", "chats", split="train")\nprint(chats[0]["messages"])\n```\n\n', '')
        if t == 'bt': bt = v
        else: ct = v
    bt = bt.replace('## ', '### ')
    ct = ct.replace('## ', '### ')
    langs = ['en'] + sorted((iso_codes(c['language']) | iso_codes(b['main_language'])) - {'en'})
    head = f"""---
pretty_name: PersonaFactory
license: apache-2.0
size_categories:
- 1M<n<10M
task_categories:
- text-generation
tags:
- synthetic
- personas
- user-simulation
- multilingual
- conversational
- sft
multilinguality: multilingual
language:
{yaml_list(langs)}
configs:
- config_name: chats
  default: true
  data_files:
  - split: train
    path: chats/train-*
- config_name: persona_bank
  data_files:
  - split: train
    path: persona_bank/train-*
---
"""
    return head + f"""# PersonaFactory

[![arXiv](https://img.shields.io/badge/arXiv-2611.34785-b31b1b)](https://arxiv.org/abs/2611.34785)
[![Persona bank](https://img.shields.io/badge/persona__bank-{b['n']:,}%20profiles-yellow)](#persona_bank)
[![Chats](https://img.shields.io/badge/chats-{c['n']:,}%20conversations-yellow)](#chats)

PersonaFactory is the dataset of *"{TITLE}"* by {AUTHORS}. It has two subsets:

| Subset | Content | Splits | Rows |
|---|---|---|---|
| `persona_bank` | synthetic user personas with a background and a style layer | `train` | {fmt(b['n'])} |
| `chats` | multi-turn conversations whose user turns are rewritten in a persona's voice and whose assistant turns are regenerated for that user | `train` | {fmt(c['n'])} |

```python
from datasets import load_dataset

chats = load_dataset("{REPO}", "chats", split="train")
bank = load_dataset("{REPO}", "persona_bank", split="train")
```

Every conversation links to its persona through `persona_id`, which matches `id` in `persona_bank`.

## `persona_bank`

{bt}

## `chats`

{ct}

## License

Released under the Apache 2.0 license. The seed conversations come from WildChat, UltraChat and Nemotron Instruction-Following Chat, and the text was generated with `google/gemma-4-31B-it`, `mistralai/Ministral-3-14B-Instruct-2512` and `zai-org/GLM-4.7-Flash`; please also follow the terms of these sources and models.

## Citation

{CITATION}
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--hf-dir', required=True, help='output directory of build_hf.py (bank/stats.json, chats/stats.json)')
    ap.add_argument('--out', default=None, help='default: <hf-dir>/README.md')
    a = ap.parse_args()
    b = json.load(open(os.path.join(a.hf_dir, 'bank', 'stats.json'), encoding='utf-8'))
    c = json.load(open(os.path.join(a.hf_dir, 'chats', 'stats.json'), encoding='utf-8'))
    out = a.out or os.path.join(a.hf_dir, 'README.md')
    open(out, 'w', encoding='utf-8').write(merged_card(b, c))
    print('wrote', out)


if __name__ == '__main__':
    main()
