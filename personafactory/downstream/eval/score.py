#!/usr/bin/env python3
"""Score <out>/gen.jsonl (gen_eval.py) against the styled evaluation file it was generated from.
  ifeval  prompt-level strict and loose accuracy (lm-eval's checkers; the checker always sees the clean prompt)
  gsm8k   last number in the response equals the gold answer
  mbpp    first python code block (or the whole reply) passes every test assert (subprocess, 10 s timeout)
  mmlu, arc   letter parsed from the reply equals the gold letter
Writes OUT/items.jsonl (one 0/1 per bench, id, variant; IFEval strict and loose) and OUT/scores.json
(score and n per bench x variant, plus gap = clean - variant on items present in both). IFEval checkers come from
lm-evaluation-harness (`pip install lm_eval`); MBPP runs model code in a subprocess, so run this in a sandbox.

  python -m personafactory.downstream.eval.score --data $PF_DATA_DIR/downstream_eval/styled_all.jsonl \
      --out $PF_OUT_DIR/downstream/eval/A2
"""
import argparse, collections, json, os, re, subprocess, sys, tempfile
from concurrent.futures import ProcessPoolExecutor

NUM = re.compile(r'-?\$?\d[\d,]*(?:\.\d+)?')


def gsm8k_ok(resp, gold):
    nums = NUM.findall(resp.replace('**', ''))
    if not nums:
        return 0
    x = nums[-1].replace('$', '').replace(',', '').rstrip('.')
    try:
        return int(abs(float(x) - float(gold)) < 1e-6)
    except ValueError:
        return 0


def letter(resp, labels):
    lab = ''.join(labels)
    t = resp.strip()
    for pat in (rf'answer(?: is|:)?\s*\**\(?([{lab}])\)?\b', rf'^\**\(?([{lab}])[).:\s*]', rf'\b([{lab}])\b'):
        m = re.search(pat, t, re.I | re.M) if 'answer' in pat else re.search(pat, t, re.M)
        if m:
            return m.group(1).upper()
    return None


def mbpp_code(resp):
    blocks = re.findall(r'```(?:python|py)?\s*\n(.*?)```', resp, re.S)
    for b in blocks:
        if 'def ' in b:
            return b
    return blocks[0] if blocks else resp


def mbpp_run(args):
    code, tests, imports = args
    prog = '\n'.join(imports) + '\n' + code + '\n\n' + '\n'.join(tests) + '\n'
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'prog.py')
        open(p, 'w').write(prog)
        try:
            r = subprocess.run([sys.executable, '-I', p], cwd=d, capture_output=True, timeout=10)
            return int(r.returncode == 0)
        except subprocess.TimeoutExpired:
            return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    from lm_eval.tasks.ifeval import utils as ifu
    meta = {(r['bench'], r['id'], r['variant']): r for r in map(json.loads, open(a.data, encoding='utf-8'))}
    gen = {}
    for l in open(a.out + '/gen.jsonl', encoding='utf-8'):
        r = json.loads(l)
        gen[(r['bench'], r['id'], r['variant'])] = r
    items, mb = [], []
    for k, g in gen.items():
        b, i, v = k
        m, resp = meta[k]['meta'], g['response'] or ''
        if b == 'ifeval':
            doc = {'key': int(i), 'instruction_id_list': m['instruction_id_list'], 'prompt': m['prompt'],
                   'kwargs': [{kk: vv for kk, vv in (kw or {}).items() if vv is not None} for kw in m['kwargs']]}
            res = ifu.process_results(doc, [resp])
            items.append({'bench': 'ifeval', 'id': i, 'variant': v, 'ok': int(res['prompt_level_strict_acc'])})
            items.append({'bench': 'ifeval_loose', 'id': i, 'variant': v, 'ok': int(res['prompt_level_loose_acc'])})
        elif b == 'gsm8k':
            items.append({'bench': b, 'id': i, 'variant': v, 'ok': gsm8k_ok(resp, m['gold'])})
        elif b in ('mmlu', 'arc'):
            items.append({'bench': b, 'id': i, 'variant': v, 'ok': int(letter(resp, m.get('labels') or list('ABCD')) == m['gold'])})
        elif b == 'mbpp':
            mb.append((k, (mbpp_code(resp), m['tests'], m['imports'])))
    with ProcessPoolExecutor(32) as ex:
        for (k, _), ok in zip(mb, ex.map(mbpp_run, [x for _, x in mb], chunksize=8)):
            items.append({'bench': 'mbpp', 'id': k[1], 'variant': k[2], 'ok': ok})
    with open(a.out + '/items.jsonl', 'w') as f:
        for x in items:
            f.write(json.dumps(x) + '\n')
    by = collections.defaultdict(dict)
    for x in items:
        by[(x['bench'], x['variant'])][x['id']] = x['ok']
    scores = {}
    for (b, v), d in sorted(by.items()):
        clean = by.get((b, 'clean'), {})
        both = [i for i in d if i in clean]
        scores[f'{b}/{v}'] = {'score': round(100 * sum(d.values()) / len(d), 2), 'n': len(d),
                              'gap': round(100 * sum(clean[i] - d[i] for i in both) / len(both), 2) if both else None}
    json.dump(scores, open(a.out + '/scores.json', 'w'), indent=1)
    print(json.dumps(scores, indent=1))


if __name__ == '__main__':
    main()
