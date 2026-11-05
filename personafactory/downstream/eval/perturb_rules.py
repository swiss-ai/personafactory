#!/usr/bin/env python3
"""Rule-based styled variants of the verifiable benchmarks. Deterministic and independent of any generator. Variants of every prompt:
  clean      unchanged
  lower      lowercase everything outside protected spans
  nopunct    drop sentence-final . ? ! (not inside protected spans or numbers)
  typo3      typos on 3% of eligible words (adjacent swap, drop, keyboard neighbour), seeded per item
  typo8      the same at 8%
  abbrev     chat abbreviations (you -> u, please -> pls, thanks -> thx, ...)
  terse      politeness and filler stripped (please, could you, I would like you to, ...)
  messy      lower + nopunct + typo3 + abbrev combined
Protected spans are never changed: IFEval string kwargs (keywords, forbidden words, required phrases, markers, the
prompt to repeat), quoted text, inline code, URLs, numbers, number words, and for MBPP every identifier-like token.
After perturbing, every IFEval string kwarg must still appear verbatim; items that fail are dropped (logged).
Benchmarks: IFEval (541), GSM8K (1319, question only, scored on the last number), MBPP sanitized (257, description
perturbed, the first test shown verbatim). MMLU and ARC-Challenge are added as clean letter-answer chat prompts.
Reads <data-dir>/{ifeval,gsm8k,mbpp,mmlu,arc_challenge}.jsonl (fetch_benchmarks.py); writes <data-dir>/styled.jsonl and
<data-dir>/styled_stats.json.

  python -m personafactory.downstream.eval.perturb_rules --data-dir $PF_DATA_DIR/downstream_eval
"""
import argparse, json, random, re, collections, os

D = None
VARIANTS = ('clean', 'lower', 'nopunct', 'typo3', 'typo8', 'abbrev', 'terse', 'messy')
NUMWORDS = set('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen '
               'seventeen eighteen nineteen twenty thirty forty fifty hundred thousand first second third fourth fifth '
               'once twice'.split())
ABBREV = [('you', 'u'), ('your', 'ur'), ("you're", 'ur'), ('please', 'pls'), ('thanks', 'thx'), ('thank you', 'ty'),
          ('because', 'bc'), ('are', 'r'), ('people', 'ppl'), ('something', 'smth'), ('about', 'abt'),
          ('really', 'rly'), ('information', 'info'), ('message', 'msg'), ('probably', 'prob'), ('though', 'tho'),
          ('with', 'w/'), ('without', 'w/o'), ('before', 'b4'), ('tomorrow', 'tmrw'), ('okay', 'ok'),
          ('I don\'t know', 'idk'), ('by the way', 'btw'), ('going to', 'gonna'), ('want to', 'wanna')]
FILLER = [r'\bplease\b,?\s*', r'\bkindly\b\s*', r'\bcould you\s+(please\s+)?', r'\bcan you\s+(please\s+)?',
          r'\bwould you\s+(please\s+)?', r'\bI would like you to\s+', r'\bI want you to\s+', r'\bI\'d like you to\s+',
          r'\bI need you to\s+', r'^\s*(hi|hello|hey)( there)?[,!.]?\s*', r'\s*\bthank you( in advance)?[.!]?\s*$',
          r'\s*\bthanks( in advance)?[.!]?\s*$', r'\bif you can\b,?\s*', r'\bif possible\b,?\s*']
KEYS = 'qwertyuiop asdfghjkl zxcvbnm'.split()
NEIGH = {}
for r, row in enumerate(KEYS):
    for c, ch in enumerate(row):
        n = [row[c - 1]] if c > 0 else []
        n += [row[c + 1]] if c + 1 < len(row) else []
        n += [KEYS[r - 1][c]] if r > 0 and c < len(KEYS[r - 1]) else []
        n += [KEYS[r + 1][c]] if r + 1 < len(KEYS) and c < len(KEYS[r + 1]) else []
        NEIGH[ch] = n
PROT_RE = re.compile(r'"[^"\n]{1,200}"|“[^”\n]{1,200}”|`[^`\n]+`|https?://\S+|\b\d[\d.,:/%-]*\b|<<[^>]+>>|\*[^*\n]+\*')


def spans(text, protect, ident=False):
    """Sorted, merged protected (start, end) intervals."""
    iv = [m.span() for m in PROT_RE.finditer(text)]
    for p in protect:
        for m in re.finditer(re.escape(p), text):
            iv.append(m.span())
    for m in re.finditer(r'[A-Za-z]+', text):
        if m.group().lower() in NUMWORDS:
            iv.append(m.span())
    if ident:
        iv += [m.span() for m in re.finditer(r'\b\w*[_\d]\w*\b|\w+\(\)?|\b[a-z]+[A-Z]\w*\b', text)]
    iv.sort()
    out = []
    for s, e in iv:
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def apply_free(text, iv, fn):
    """Apply fn to the unprotected stretches only."""
    res, pos = [], 0
    for s, e in iv:
        res.append(fn(text[pos:s]))
        res.append(text[s:e])
        pos = e
    res.append(fn(text[pos:]))
    return ''.join(res)


def typo_word(w, rng):
    i = rng.randrange(len(w) - 1)
    op = rng.choice(('swap', 'drop', 'neigh'))
    if op == 'swap':
        return w[:i] + w[i + 1] + w[i] + w[i + 2:]
    if op == 'drop':
        return w[:i] + w[i + 1:]
    ch = w[i]
    n = NEIGH.get(ch.lower())
    if not n:
        return w[:i] + w[i + 1:]
    r = rng.choice(n)
    return w[:i] + (r.upper() if ch.isupper() else r) + w[i + 1:]


def typos(rate, rng):
    def f(seg):
        return re.sub(r'[A-Za-z]{3,}', lambda m: typo_word(m.group(), rng) if rng.random() < rate else m.group(), seg)
    return f


def abbrev(seg):
    for full, short in ABBREV:
        seg = re.sub(r'\b' + re.escape(full) + r'\b', lambda m: short.upper() if m.group().isupper() and len(m.group()) > 1 else short, seg,
                     flags=re.I)
    return seg


def terse(seg):
    for pat in FILLER:
        seg = re.sub(pat, '', seg, flags=re.I | re.M)
    return seg


def nopunct(seg):
    return re.sub(r'(?<=[A-Za-z)\]])[.?!]+(?=\s|$)', '', seg)


def variant(text, v, iv, rng):
    if v == 'clean':
        return text
    if v == 'lower':
        return apply_free(text, iv, str.lower)
    if v == 'nopunct':
        return apply_free(text, iv, nopunct)
    if v in ('typo3', 'typo8'):
        return apply_free(text, iv, typos(0.03 if v == 'typo3' else 0.08, rng))
    if v == 'abbrev':
        return apply_free(text, iv, abbrev)
    if v == 'terse':
        out = apply_free(text, iv, terse).strip()
        return out[:1].upper() + out[1:] if out else text
    if v == 'messy':
        typo = typos(0.03, rng)
        return apply_free(text, iv, lambda s: abbrev(typo(nopunct(s.lower()))))
    raise ValueError(v)


def ifeval_protect(row):
    out = []
    for kw in row['kwargs']:
        for k, val in (kw or {}).items():
            if isinstance(val, str) and val.strip():
                out.append(val)
            elif isinstance(val, list):
                out += [x for x in val if isinstance(x, str) and x.strip()]
    return out


def main():
    global D
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data-dir', required=True)
    D = os.path.join(ap.parse_args().data_dir, '')
    rows, stats = [], collections.Counter()
    for r in map(json.loads, open(D + 'ifeval.jsonl')):
        prot = [x for x in ifeval_protect(r) if x in r['prompt']]   # kwargs not verbatim in the prompt cannot be lost
        iv = spans(r['prompt'], prot)
        for v in VARIANTS:
            rng = random.Random(f"ifeval:{r['key']}:{v}")
            p = variant(r['prompt'], v, iv, rng)
            ok = all(x in p for x in prot)
            stats[f'ifeval/{v}/{"kept" if ok else "dropped"}'] += 1
            stats[f'ifeval/{v}/changed'] += p != r['prompt']
            if ok:
                rows.append({'bench': 'ifeval', 'id': str(r['key']), 'variant': v, 'prompt': p,
                             'meta': {'instruction_id_list': r['instruction_id_list'], 'kwargs': r['kwargs'],
                                      'prompt': r['prompt']}})
    for i, r in enumerate(map(json.loads, open(D + 'gsm8k.jsonl'))):
        iv = spans(r['question'], [])
        gold = r['answer'].split('####')[-1].strip().replace(',', '')
        for v in VARIANTS:
            p = variant(r['question'], v, iv, random.Random(f'gsm8k:{i}:{v}'))
            stats[f'gsm8k/{v}/changed'] += p != r['question']
            rows.append({'bench': 'gsm8k', 'id': str(i), 'variant': v, 'prompt': p, 'meta': {'gold': gold}})
    for r in map(json.loads, open(D + 'mbpp.jsonl')):
        desc = r['prompt'].strip()
        iv = spans(desc, [], ident=True)
        for v in VARIANTS:
            d = variant(desc, v, iv, random.Random(f"mbpp:{r['task_id']}:{v}"))
            stats[f'mbpp/{v}/changed'] += d != desc
            p = f"{d}\n\nYour code should pass this test:\n{r['test_list'][0]}"
            rows.append({'bench': 'mbpp', 'id': str(r['task_id']), 'variant': v, 'prompt': p,
                         'meta': {'tests': r['test_list'], 'imports': r.get('test_imports') or []}})
    for i, r in enumerate(map(json.loads, open(D + 'mmlu.jsonl'))):
        ch = '\n'.join(f'{"ABCD"[j]}. {c}' for j, c in enumerate(r['choices']))
        rows.append({'bench': 'mmlu', 'id': str(i), 'variant': 'clean', 'prompt':
                     f"{r['question']}\n\n{ch}\n\nAnswer with the letter of the correct option.", 'meta': {'gold': 'ABCD'[r['answer']], 'subject': r['subject']}})
    for r in map(json.loads, open(D + 'arc_challenge.jsonl')):
        labels = r['choices']['label']
        ch = '\n'.join(f'{l}. {t}' for l, t in zip(labels, r['choices']['text']))
        rows.append({'bench': 'arc', 'id': r['id'], 'variant': 'clean', 'prompt':
                     f"{r['question']}\n\n{ch}\n\nAnswer with the letter of the correct option.", 'meta': {'gold': r['answerKey'], 'labels': labels}})
    with open(D + 'styled.jsonl', 'w', encoding='utf-8') as f:
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False) + '\n')
    json.dump(dict(sorted(stats.items())), open(D + 'styled_stats.json', 'w'), indent=1)
    print(len(rows), 'prompts;', collections.Counter(x['bench'] for x in rows))
    print(json.dumps(dict(sorted(stats.items())), indent=0))


if __name__ == '__main__':
    main()
