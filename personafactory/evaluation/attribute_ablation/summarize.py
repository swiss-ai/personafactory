#!/usr/bin/env python3
"""Per-attribute table, heatmap grid and per-rewriter summary from run_ablation.py output.

Rows are deduplicated to the latest attempt per (sample_id, condition, model_id) cell. Per condition, each metric
(style, intent, script_stability) is the mean over all non-null cell scores pooled across the rewriters (heatmap
grid); a family value is the mean of its two (3-decimal) condition values (per-attribute table). Valid rewrites
are cells without an adaptation or generation error. Per rewriter, a metric is the mean
over the sixteen attribute conditions of that rewriter's per-condition means (per-rewriter figure).

Inputs:  --results (run_ablation.py output JSONL)
Outputs: printed tables; --out JSON {by_condition, by_family, by_model, valid_rewrites};
         --figure-stats JSON in the layout figures/make_ablation_figures.py reads (ablation_stats.json)
Run:     python -m personafactory.evaluation.attribute_ablation.summarize --results ./outputs/attribute_ablation/results.jsonl \
             --out ./outputs/attribute_ablation/summary.json --figure-stats ./outputs/figures/ablation_stats.json
"""
import argparse, json, os, statistics
from collections import defaultdict

from personafactory.evaluation.attribute_ablation.conditions import CONDITIONS, CONDITION_FAMILIES, CONDITION_LABELS

METRICS = ('style', 'intent', 'script_stability')
METRIC_LABELS = ('Style Adoption', 'Intent Preservation', 'Script Stability')


def mean(v):
    v = [x for x in v if x is not None]
    return statistics.mean(v) if v else None


def r3(x):
    return None if x is None else round(x, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', required=True)
    ap.add_argument('--out', default=None)
    ap.add_argument('--figure-stats', default=None)
    a = ap.parse_args()
    dedup = {}
    for line in open(a.results, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        dedup[(r.get('sample_id'), r.get('condition'), r.get('model_id'))] = r
    rows = list(dedup.values())

    by_cond = defaultdict(lambda: defaultdict(list))
    by_model = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for r in rows:
        sc = r.get('scores') or {}
        for m in METRICS:
            if sc.get(m) is not None:
                by_cond[r['condition']][m].append(sc[m])
                by_model[r['model_id']][r['condition']][m].append(sc[m])
    conds = [c for c in CONDITIONS if c in by_cond]
    attr = [c for c in conds if c != 'baseline']
    cond = {c: {m: mean(by_cond[c][m]) for m in METRICS} for c in conds}
    model_cond = {k: {c: {m: mean(v[c][m]) for m in METRICS} for c in attr} for k, v in by_model.items()}
    fam = {f: {m: mean([r3(cond[c][m]) for c in members if c in cond]) for m in METRICS}
           for f, members in CONDITION_FAMILIES.items()}
    model = {k: {m: mean([(mc[c][m] or 0) for c in attr]) for m in METRICS} for k, mc in sorted(model_cond.items())}
    valid = sum(1 for r in rows if not r.get('error'))
    rd = lambda d: {k: {m: r3(x) for m, x in v.items()} for k, v in d.items()}
    out = {'cells': len(rows), 'valid_rewrites': valid, 'by_condition': rd(cond), 'by_family': rd(fam), 'by_model': rd(model)}

    for title, table in (('family', fam), ('condition', cond), ('rewriter', model)):
        print(f"\n{title:22s} {'style':>7s} {'intent':>7s} {'script':>7s}")
        for k, v in table.items():
            print(f"{k:22s} " + ' '.join(f"{r3(v[m])!s:>7s}" for m in METRICS))
    print(f"\ncells {len(rows)}, valid rewrites {valid}")
    if a.out:
        json.dump(out, open(a.out, 'w'), indent=1)
    if a.figure_stats:
        labels = [CONDITION_LABELS.get(c, c) for c in conds]
        fs = {'stats': {'total': len(rows), 'errors': sum(1 for r in rows if r.get('error')), 'conds': len(conds),
                        'models': len(model_cond), 'samples': len({r['sample_id'] for r in rows})},
              'condition_labels': CONDITION_LABELS,
              'heatmap': {'conditions': labels, 'metrics': list(METRIC_LABELS),
                          'z': [[r3(cond[c][m]) for m in METRICS] for c in conds]},
              'conditions': [CONDITION_LABELS.get(c, c) for c in attr],
              'per_model': {k: {lab: [r3(mc[c][m] or 0) for c in attr] for m, lab in zip(METRICS, METRIC_LABELS)}
                            for k, mc in sorted(model_cond.items())}}
        os.makedirs(os.path.dirname(os.path.abspath(a.figure_stats)), exist_ok=True)
        json.dump(fs, open(a.figure_stats, 'w'), indent=1)
        print('wrote', a.figure_stats)


if __name__ == '__main__':
    main()
