#!/usr/bin/env python3
"""Programmatic compliance with checkable system prompts, per output file of assistant.augment_assistant_only.

Test set: single-turn conversations (system, user, assistant), each given one of the four system prompts in
SYSTEM_PROMPTS; the row id is `<set>-<kind>-<source id>` with kind in SYSTEM_PROMPTS. Augment it with
--with-system apply (step none, and step regen with AO_SYS_POSITION=first and =last), then check the first
assistant reply of every row. Prints per-kind and overall compliance for each file.

  python -m personafactory.assistant.system_prompt_check OUT_last/none/sys.jsonl OUT_first/regen/sys.jsonl OUT_last/regen/sys.jsonl
"""
import collections, json, re, sys

SYSTEM_PROMPTS = {
    'three': 'You are a support assistant. Always answer in at most three sentences, in plain prose without lists or headers.',
    'numbered': 'Format every answer as a numbered list of steps or points, with no introduction before the list.',
    'short': 'Keep every answer under 80 words.',
    'nomd': 'Never use Markdown formatting: no bold, italics, headers, bullet points, numbered lists or code fences. '
            'Write plain text only.',
}
MD = re.compile(r'(\*\*|__|^\s*#|^\s*[-*•]\s|^\s*\d+[.)]\s|```)', re.M)
LIST = re.compile(r'^\s*([-*•]|\d+[.)]|#)', re.M)


def ok(kind, t):
    t = t.strip()
    if kind == 'three':
        return len(re.findall(r'[.!?](\s|$)', t)) <= 3 and not LIST.search(t)
    if kind == 'numbered':
        return bool(re.match(r'\s*(\*\*)?1[.)]', t))
    if kind == 'short':
        return len(t.split()) < 80
    if kind == 'nomd':
        return not MD.search(t)


def main():
    res = {}
    for d in sys.argv[1:]:
        c = collections.defaultdict(list)
        for l in open(d):
            x = json.loads(l)
            if not x.get('messages'):
                continue
            kind = x['id'].split('-')[1]
            t = next(m['content'] for m in x['messages'] if m['role'] == 'assistant')
            c[kind].append(ok(kind, t))
            c['all'].append(ok(kind, t))
        res[d] = {k: f'{100 * sum(v) / len(v):.0f}% ({len(v)})' for k, v in c.items()}
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
