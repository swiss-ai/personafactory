#!/usr/bin/env python3
"""Aggregate the format-neutral re-judging (rejudge_neutral.py): per judge, format-neutral style adoption,
naturalness, neutral pairwise (PersonaFactory vs each condition), native-persona intent and reference-free pairwise,
all with 95% Wilson intervals; plus judge-free style movement of every condition relative to the same item's
no-persona rewrite. Writes <run-dir>/results_neutral.json and prints a compact report.

Judges whose label contains an --exclude substring are skipped (default: llama; its naturalness verdicts were
unreliable, it rated the unconditioned rewrites least natural, so the report uses the pipeline judge and the
external judges).

Run: python -m personafactory.evaluation.format_comparison.analyze_neutral --run-dir ./outputs/format_comparison
"""
import argparse, collections, glob, json, math, os, statistics

from personafactory.evaluation.format_comparison.diversity import feats

V = './outputs/format_comparison'

CONDS = ['none', 'personahub', 'synthpai', 'personafactory', 'native_personahub', 'native_synthpai']


def wil(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    hw = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return {'pct': round(100 * p, 1), 'lo': round(100 * (c - hw), 1), 'hi': round(100 * (c + hw), 1), 'n': n}


def judge_report(fp):
    rows = [json.loads(l) for l in open(fp)]
    last = {}
    for r in rows:  # later lines win (resumed runs)
        if r.get('value') is not None or r['key'] not in last:
            last[r['key']] = r
    rows = list(last.values())
    out = {'failures': dict(collections.Counter(r['failure'] for r in rows if r.get('value') is None))}
    for task in ('style_neutral', 'natural', 'intent'):
        t = {}
        for c in CONDS:
            v = [r['value'] for r in rows if r['task'] == task and r['condition'] == c and r.get('value')]
            if v:
                t[c] = wil(sum(x == 'pass' for x in v), len(v))
        out[task] = t
    for task in ('pairwise_neutral', 'pairwise_free'):
        t = {}
        for c in CONDS:
            cnt = collections.Counter()
            for r in rows:
                if r['task'] == task and r['condition'] == c and r.get('value'):
                    w = r['value']
                    cnt['tie' if w == 'tie' else ('pf' if (w == 'a') == r['pf_is_A'] else 'other')] += 1
            n = sum(cnt.values())
            if n:
                t[c] = {'n': n, 'pf_pct': round(100 * cnt['pf'] / n, 1), 'other_pct': round(100 * cnt['other'] / n, 1),
                        'tie_pct': round(100 * cnt['tie'] / n, 1), 'pf_decisive': wil(cnt['pf'], cnt['pf'] + cnt['other'])}
        out[task] = t
    return out


def judge_free():
    rw = collections.defaultdict(dict)
    for fp in (V + '/generations.jsonl', V + '/generations_native.jsonl'):
        if os.path.exists(fp):
            for l in open(fp):
                r = json.loads(l)
                if r.get('rewrite'):
                    rw[r['item_id']][r['condition']] = r['rewrite']
    res = {}
    for c in CONDS[1:]:
        d = collections.defaultdict(list)
        for v in rw.values():
            if c in v and 'none' in v:
                f, f0 = feats(v[c]), feats(v['none'])
                for k in f:
                    d[k].append(f[k] - f0[k])
        if d:
            res[c] = {k: {'mean_abs_move': round(statistics.mean(abs(x) for x in xs), 3), 'sd_move': round(statistics.stdev(xs), 3)}
                      for k, xs in d.items()}
    return res


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-dir', default=V)
    ap.add_argument('--exclude', default='llama', help='comma list of judge-label substrings to skip')
    a = ap.parse_args()
    V = a.run_dir
    excl = [x for x in a.exclude.split(',') if x]
    res = {os.path.basename(fp)[len('judged_'):-len('.jsonl')]: judge_report(fp) for fp in sorted(glob.glob(V + '/judged_*.jsonl'))
           if not any(x in os.path.basename(fp) for x in excl)}
    res['judge_free_move_vs_none'] = judge_free()
    json.dump(res, open(V + '/results_neutral.json', 'w'), indent=1)
    for j, r in res.items():
        if j == 'judge_free_move_vs_none':
            continue
        print(f'== {j}  failures {r["failures"]}')
        for task in ('style_neutral', 'natural', 'intent'):
            print(f'  {task:16s}', '  '.join(f'{c}={v["pct"]}[{v["lo"]},{v["hi"]}]' for c, v in r[task].items()))
        for task in ('pairwise_neutral', 'pairwise_free'):
            for c, v in r[task].items():
                d = v['pf_decisive']
                print(f'  {task:16s} PF vs {c:18s} PF {v["pf_pct"]} / other {v["other_pct"]} / tie {v["tie_pct"]}  PF decisive {d["pct"]} [{d["lo"]},{d["hi"]}] n={v["n"]}')
    print('== judge-free style movement vs the no-persona rewrite (mean |delta| / sd)')
    for c, fs in res['judge_free_move_vs_none'].items():
        print(f'  {c:18s}', '  '.join(f'{k} {v["mean_abs_move"]}/{v["sd_move"]}' for k, v in fs.items()))
