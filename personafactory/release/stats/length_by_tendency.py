#!/usr/bin/env python3
"""Length row of the full-corpus judge-free fidelity table: median length ratio (first rewritten user turn / source turn, same-language free mode)
by the persona's sentence-length tendency, and the per-item Spearman rho between tendency (short<medium<long)
and ratio. Writes <release-dir>/length_by_tendency.json.

  python -m personafactory.release.stats.length_by_tendency --release-dir ./release_out --bank ./release_out/persona_bank.jsonl
"""
import argparse, glob, json, os, statistics
from scipy.stats import spearmanr

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--release-dir', required=True)
ap.add_argument('--bank', default=os.environ.get('PF_BANK'), help='persona bank JSONL (default: PF_BANK, else <release-dir>/persona_bank.jsonl)')
ap.add_argument('--out', default=None, help='default: <release-dir>/length_by_tendency.json')
args = ap.parse_args()
bank = {}
for l in open(args.bank or os.path.join(args.release_dir, 'persona_bank.jsonl'), encoding='utf-8'):
    p = json.loads(l)
    bank[p['id']] = str((p.get('style') or {}).get('sentence_length_tendency', '')).lower()
tier = lambda s: 0 if 'short' in s else 2 if ('long' in s or 'elaborate' in s) else 1 if 'medium' in s else None
xs, ys, by = [], [], {0: [], 1: [], 2: []}
for fp in sorted(glob.glob(os.path.join(args.release_dir, 'data', '*.jsonl'))):
    for l in open(fp, encoding='utf-8'):
        r = json.loads(l)
        if r.get('language_mode') != 'free' or not r.get('source_text'):
            continue
        t = tier(bank.get(r['persona_id'], ''))
        u = next(m['content'] for m in r['conversation'] if m['role'] == 'user')
        if t is None:
            continue
        ratio = len(u) / len(r['source_text'])
        xs.append(t); ys.append(ratio); by[t].append(ratio)
out = {'n': len(xs), 'median_ratio': {k: round(statistics.median(by[i]), 2) for i, k in enumerate(('short', 'medium', 'long'))},
       'n_by_tier': {k: len(by[i]) for i, k in enumerate(('short', 'medium', 'long'))}, 'spearman_rho': round(spearmanr(xs, ys)[0], 3)}
json.dump(out, open(args.out or os.path.join(args.release_dir, 'length_by_tendency.json'), 'w'), indent=1)
print(json.dumps(out))
