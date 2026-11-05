#!/usr/bin/env python3
"""Numbers for the structured vs flat tables: per judge, parsed pairs, preference shares (structured / flat / tie,
over parsed verdicts), structured share of decisive verdicts with a 95% Wilson interval, Wilson intervals of the
structured and flat shares, and intent preservation of each representation (pass rate over non-null intent
verdicts of the parsed pairs).

Accepts both layouts: ab_style_test.py output (field "winner") and ab_rejudge.py / re_judge_ab.py --out output
(summary line followed by per-pair rows with field "outcome").

Inputs:  one or more LABEL=PATH arguments
Outputs: printed table, optional --out JSON
Run:     python -m personafactory.evaluation.structured_vs_flat.ab_table minimax_first_pass=./outputs/ab_first_pass.jsonl \
             minimax=./outputs/ab_rejudge_minimax.jsonl qwen36=./outputs/ab_rejudge_qwen36.jsonl --out ./outputs/ab_table.json
"""
import argparse, collections, json

from personafactory.evaluation.stats_utils import wilson_pct


def load(path):
    rows = []
    for l in open(path):
        r = json.loads(l)
        if 'winner' in r and 'status' in r:          # ab_style_test.py layout
            if r['status'] != 'ok':
                continue
            rows.append({'outcome': r.get('winner'), 'intent_flat': r.get('intent_flat'), 'intent_struct': r.get('intent_struct')})
        elif 'outcome' in r:                          # ab_rejudge.py layout (the summary line has no "outcome")
            rows.append(r)
    return rows


def table(rows):
    parsed = [x for x in rows if x.get('outcome')]
    c = collections.Counter(x['outcome'] for x in parsed)
    n, dec = len(parsed), c['structured'] + c['flat']

    def intent(key):
        v = [x[key] for x in parsed if x.get(key)]
        return round(100 * v.count('pass') / len(v), 1) if v else None
    return {'pairs': len(rows), 'parsed': n,
            'structured_pct': round(100 * c['structured'] / n, 1) if n else None,
            'flat_pct': round(100 * c['flat'] / n, 1) if n else None,
            'tie_pct': round(100 * c['tie'] / n, 1) if n else None,
            'structured_ci95': wilson_pct(c['structured'], n), 'flat_ci95': wilson_pct(c['flat'], n),
            'structured_decisive': wilson_pct(c['structured'], dec),
            'intent_flat_pct': intent('intent_flat'), 'intent_struct_pct': intent('intent_struct')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('runs', nargs='+', help='LABEL=PATH')
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    res = {}
    for spec in a.runs:
        label, path = spec.split('=', 1)
        res[label] = table(load(path))
    print(f"{'judge':28s} {'parsed':>6s} {'struct':>7s} {'flat':>6s} {'tie':>5s}  {'struct decisive (95% CI)':26s} intent flat/struct")
    for label, t in res.items():
        d = t['structured_decisive'] or {}
        print(f"{label:28s} {t['parsed']:6d} {t['structured_pct']!s:>7s} {t['flat_pct']!s:>6s} {t['tie_pct']!s:>5s}  "
              f"{d.get('pct')!s} ({d.get('lo')}-{d.get('hi')}){'':8s} {t['intent_flat_pct']} / {t['intent_struct_pct']}")
    if a.out:
        json.dump(res, open(a.out, 'w'), indent=1)


if __name__ == '__main__':
    main()
