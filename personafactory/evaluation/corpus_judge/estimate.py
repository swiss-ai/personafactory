#!/usr/bin/env python3
"""Corpus-wide LLM-judge estimate from a fully scored subset and a random sample of the remaining conversations.

The full-corpus judge table scores every user turn of one subset of the release (prep_items.py -> run_judge.py ->
aggregate.py) and a random conversation sample of the rest (same intent and style templates and judge;
postprocess.judge_sample_prep -> run_judge.py -> postprocess.judge_sample_agg). Each stratum's pass rates are weighted by the number
of user turns it stands for in the release:

    estimate = (rate_scored * T_scored + rate_sample * (T_total - T_scored)) / T_total

T_scored is the number of user turns of the fully scored subset (default: its `turns` count), T_total the number of
user turns in the release (--total-turns, or counted from --release-dir). The paper's estimate (96.6% intent,
67.1% style, 64.9% both) is this formula on the 552,654 fully scored turns and the 44,687-turn sample, with
T_total = 2,387,392.

Inputs:  --scored  aggregate.py report (overall rates under `entire_release`)
         --sample  sample aggregate report (overall rates under `all` or `entire_release`)
Outputs: --out JSON (overall estimate, the two strata and their weights)
Run:     python -m personafactory.evaluation.corpus_judge.estimate --scored ./outputs/corpus_judge/corpus_judge.json \
             --sample $REL/judge_sample.json --release-dir $REL --out judge_estimate.json
"""
import argparse, glob, json, os

RATES = ('intent_pct', 'style_pct', 'both_pct')


def overall(rep):
    for k in ('entire_release', 'all'):
        if k in rep:
            return rep[k]
    raise KeyError('report has neither `entire_release` nor `all`')


def count_user_turns(release_dir):
    n = 0
    for fp in glob.glob(os.path.join(release_dir, 'data', '*.jsonl')):
        for line in open(fp, encoding='utf-8'):
            n += sum(m['role'] == 'user' for m in json.loads(line)['conversation'])
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--scored', required=True, help='aggregate.py report of the fully scored subset')
    ap.add_argument('--sample', required=True, help='aggregate report of the random sample of the remaining conversations')
    ap.add_argument('--scored-turns', type=int, default=None, help='user turns of the scored subset (default: its `turns`)')
    ap.add_argument('--total-turns', type=int, default=None, help='user turns in the release')
    ap.add_argument('--release-dir', default=None, help='count --total-turns from <release-dir>/data/*.jsonl')
    ap.add_argument('--decimals', type=int, default=1, help='round the stratum rates before weighting (paper: 1)')
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    sc, sa = overall(json.load(open(a.scored))), overall(json.load(open(a.sample)))
    total = a.total_turns or (count_user_turns(a.release_dir) if a.release_dir else None)
    if not total:
        ap.error('give --total-turns or --release-dir')
    t_sc = a.scored_turns or sc['turns']
    t_rest = total - t_sc
    est = {}
    for k in RATES:
        r1, r2 = round(sc[k], a.decimals), round(sa[k], a.decimals)
        est[k] = round((r1 * t_sc + r2 * t_rest) / total, 1)
    out = {'estimate': est,
           'weights': {'total_user_turns': total, 'scored_subset_turns': t_sc, 'remaining_turns': t_rest},
           'scored_subset': {k: sc[k] for k in ('turns',) + RATES},
           'sample': {k: sa[k] for k in ('turns',) + RATES}}
    if a.out:
        json.dump(out, open(a.out, 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
