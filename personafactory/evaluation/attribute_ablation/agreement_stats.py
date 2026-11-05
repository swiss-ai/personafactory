#!/usr/bin/env python3
"""Chance-corrected pairwise judge agreement (Cohen's kappa and Gwet's AC1) from per-judge binary verdicts.

For judges j1, j2 on the items both scored: observed agreement p_o, pass rates p1, p2.
  Cohen's kappa: p_e = p1 p2 + (1 - p1)(1 - p2),      kappa = (p_o - p_e) / (1 - p_e)
  Gwet's AC1:    pi = (p1 + p2) / 2, p_e = 2 pi (1 - pi), AC1 = (p_o - p_e) / (1 - p_e)
Two variants of the marginals are reported:
  paired:    p1, p2 over the items both judges scored (standard definition)
  marginal:  p1, p2 = each judge's overall mean verdict rate (how the paper table was computed from the
             per-judge means and the observed agreement)

Inputs:  run_judge_ablation.py output JSON ({"cells": [{"judge_scores": {judge: {"style": 1.0, "intent": 0.0}}}]})
Outputs: printed per-judge means, raw agreement, kappa and AC1 per pair and metric; optional --out JSON
Run:     python -m personafactory.evaluation.attribute_ablation.agreement_stats --judge-results ./outputs/attribute_ablation/judge_ablation.json
"""
import argparse, itertools, json


def chance_corrected(po, p1, p2):
    pe_k = p1 * p2 + (1 - p1) * (1 - p2)
    pi = (p1 + p2) / 2
    pe_g = 2 * pi * (1 - pi)
    kappa = (po - pe_k) / (1 - pe_k) if pe_k < 1 else None
    ac1 = (po - pe_g) / (1 - pe_g) if pe_g < 1 else None
    return kappa, ac1


def r3(x):
    return None if x is None else round(x, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--judge-results', required=True)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    cells = json.load(open(a.judge_results))['cells']
    judges = list(cells[0]['judge_scores']) if cells else []
    out = {'means': {}, 'pairs': {}}
    for metric in ('style', 'intent'):
        for j in judges:
            v = [c['judge_scores'][j][metric] for c in cells if c['judge_scores'].get(j, {}).get(metric) is not None]
            out['means'].setdefault(j, {})[metric] = {'mean': r3(sum(v) / len(v)) if v else None, 'n': len(v)}
    for j1, j2 in itertools.combinations(judges, 2):
        for metric in ('style', 'intent'):
            both = [(c['judge_scores'][j1][metric], c['judge_scores'][j2][metric]) for c in cells
                    if c['judge_scores'].get(j1, {}).get(metric) is not None
                    and c['judge_scores'].get(j2, {}).get(metric) is not None]
            if not both:
                continue
            n = len(both)
            po = sum(x == y for x, y in both) / n
            p1, p2 = sum(x for x, _ in both) / n, sum(y for _, y in both) / n
            k, g = chance_corrected(po, p1, p2)
            m1, m2 = out['means'][j1][metric]['mean'], out['means'][j2][metric]['mean']
            km, gm = chance_corrected(po, m1, m2) if m1 is not None and m2 is not None else (None, None)
            out['pairs'].setdefault(f'{j1}--{j2}', {})[metric] = {
                'n': n, 'observed_agreement': r3(po),
                'paired': {'kappa': r3(k), 'ac1': r3(g)}, 'marginal': {'kappa': r3(km), 'ac1': r3(gm)}}
    print('per-judge mean verdict rate (n)')
    for j, m in out['means'].items():
        print(f"  {j:12s} style {m['style']['mean']} ({m['style']['n']})  intent {m['intent']['mean']} ({m['intent']['n']})")
    print(f"\n{'pair':24s} {'metric':7s} {'n':>4s} {'p_o':>6s} {'kappa':>7s} {'AC1':>7s}   {'kappa_m':>7s} {'AC1_m':>7s}")
    for pair, d in out['pairs'].items():
        for metric, s in d.items():
            print(f"{pair:24s} {metric:7s} {s['n']:4d} {s['observed_agreement']:6.3f} {s['paired']['kappa']!s:>7s} "
                  f"{s['paired']['ac1']!s:>7s}   {s['marginal']['kappa']!s:>7s} {s['marginal']['ac1']!s:>7s}")
    if a.out:
        json.dump(out, open(a.out, 'w'), indent=1)


if __name__ == '__main__':
    main()
