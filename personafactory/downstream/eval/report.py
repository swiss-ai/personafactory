#!/usr/bin/env python3
#!/usr/bin/env python3
"""Robustness and clean-score report from <results-dir>/<tag>/items.jsonl (score.py), nothing hand-edited.

Per model: clean score per benchmark, styled score and robustness gap = clean - styled per perturbation and pooled
over the rule-based variants, with 95% bootstrap intervals over items (10,000 resamples); the same for the
intent-checked persona rewrites. Per comparison X:Y: difference in pooled gap and in clean score, paired bootstrap
over the same items (positive gap difference: X loses more). Writes <results-dir>/main_table<suffix>.md,
report<suffix>.json and gap_by_perturbation<suffix>.png.

  python -m personafactory.downstream.eval.report --results-dir $PF_OUT_DIR/downstream/eval \
      --models A0 A1 A0r A2 --compare A1:A0 A2:A0r A2:A1 A2:A0
"""
import argparse, collections, json, os
import numpy as np

E = SFX = None
BENCHES = ('ifeval', 'ifeval_loose', 'gsm8k', 'mbpp')
STYLED = ('lower', 'nopunct', 'typo3', 'typo8', 'abbrev', 'terse', 'messy')
PERSONA = ('persona0', 'persona1', 'persona2')   # held-out persona rewrites (perturb_persona.py), intent-checked


def load(tag):
    d = collections.defaultdict(dict)
    for l in open(os.path.join(E, tag, 'items.jsonl')):
        x = json.loads(l)
        d[(x['bench'], x['variant'])][x['id']] = x['ok']
    return d


def matrix(d, bench, ids, styled=STYLED):
    """items x (clean + styled variants) 0/1 matrix, NaN where missing."""
    cols = ('clean',) + styled
    return np.array([[d.get((bench, v), {}).get(i, np.nan) for v in cols] for i in ids], dtype=float)


def stats(M, rng, B=10000, styled=STYLED):
    clean = M[:, 0]
    gaps = clean[:, None] - M[:, 1:]
    pooled = np.nanmean(gaps, axis=1)
    idx = rng.integers(0, len(M), (B, len(M)))
    out = {'clean': np.nanmean(clean) * 100}
    out['clean_ci'] = list(np.percentile(np.nanmean(clean[idx], axis=1) * 100, [2.5, 97.5]))
    out['styled'] = np.nanmean(M[:, 1:]) * 100
    out['gap'] = np.nanmean(pooled) * 100
    out['gap_ci'] = list(np.percentile(np.nanmean(pooled[idx], axis=1) * 100, [2.5, 97.5]))
    out['gap_by'] = {v: np.nanmean(gaps[:, j]) * 100 for j, v in enumerate(styled)}
    out['gap_by_ci'] = {v: list(np.percentile(np.nanmean(gaps[idx, j], axis=1) * 100, [2.5, 97.5])) for j, v in enumerate(styled)}
    return out, pooled, clean, idx


def main():
    global E, SFX
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--results-dir', required=True, help='dir with <tag>/items.jsonl')
    ap.add_argument('--models', nargs='+', default=['A0', 'A1', 'A0r', 'A2'])
    ap.add_argument('--compare', nargs='+', default=['A1:A0', 'A2:A0r', 'A2:A1', 'A2:A0'])
    ap.add_argument('--suffix', default='', help='report file name suffix')
    a = ap.parse_args()
    E, SFX = a.results_dir, a.suffix
    rng = np.random.default_rng(0)
    models = [m for m in a.models if os.path.exists(os.path.join(E, m, 'items.jsonl'))]
    data = {m: load(m) for m in models}
    rep = {'models': {}, 'compare': {}, 'clean_only': {}}
    for b in BENCHES:
        ids = sorted(set.intersection(*[set(data[m].get((b, 'clean'), {})) for m in models]), key=str)
        for m in models:
            s, *_ = stats(matrix(data[m], b, ids), rng)
            rep['models'].setdefault(m, {})[b] = s | {'n': len(ids)}
        for c in a.compare:
            x, y = c.split(':')
            if x not in data or y not in data:
                continue
            Mx, My = matrix(data[x], b, ids), matrix(data[y], b, ids)
            px, py = np.nanmean(Mx[:, 0:1] - Mx[:, 1:], axis=1), np.nanmean(My[:, 0:1] - My[:, 1:], axis=1)
            idx = rng.integers(0, len(ids), (10000, len(ids)))
            dg = np.nanmean(px[idx], axis=1) - np.nanmean(py[idx], axis=1)
            dc = np.nanmean(Mx[idx, 0], axis=1) - np.nanmean(My[idx, 0], axis=1)
            rep['compare'].setdefault(c, {})[b] = {
                'gap_diff': (np.nanmean(px) - np.nanmean(py)) * 100, 'gap_diff_ci': list(np.percentile(dg * 100, [2.5, 97.5])),
                'clean_diff': (np.nanmean(Mx[:, 0]) - np.nanmean(My[:, 0])) * 100, 'clean_diff_ci': list(np.percentile(dc * 100, [2.5, 97.5]))}
    rep['persona'], rep['persona_compare'] = {}, {}
    for b in BENCHES:
        ids = sorted(set.intersection(*[set(data[m].get((b, 'clean'), {})) for m in models]), key=str)
        has = [m for m in models if any(data[m].get((b, v)) for v in PERSONA)]
        if not has:
            continue
        for m in has:
            M = matrix(data[m], b, ids, PERSONA)
            keep = ~np.all(np.isnan(M[:, 1:]), axis=1)
            s_, *_ = stats(M[keep], rng, styled=PERSONA)
            rep['persona'].setdefault(m, {})[b] = s_ | {'n': int(keep.sum())}
        for c in a.compare:
            x, y = c.split(':')
            if x not in has or y not in has:
                continue
            Mx, My = matrix(data[x], b, ids, PERSONA), matrix(data[y], b, ids, PERSONA)
            keep = ~(np.all(np.isnan(Mx[:, 1:]), axis=1) | np.all(np.isnan(My[:, 1:]), axis=1))
            Mx, My = Mx[keep], My[keep]
            px, py = np.nanmean(Mx[:, 0:1] - Mx[:, 1:], axis=1), np.nanmean(My[:, 0:1] - My[:, 1:], axis=1)
            idx = rng.integers(0, len(Mx), (10000, len(Mx)))
            dg = np.nanmean(px[idx], axis=1) - np.nanmean(py[idx], axis=1)
            rep['persona_compare'].setdefault(c, {})[b] = {'gap_diff': (np.nanmean(px) - np.nanmean(py)) * 100,
                                                          'gap_diff_ci': list(np.percentile(dg * 100, [2.5, 97.5]))}
    for b in ('mmlu', 'arc'):
        for m in models:
            d = data[m].get((b, 'clean'), {})
            if d:
                v = np.array(list(d.values()), float)
                bs = v[rng.integers(0, len(v), (10000, len(v)))].mean(1) * 100
                rep['clean_only'].setdefault(m, {})[b] = {'score': v.mean() * 100, 'ci': list(np.percentile(bs, [2.5, 97.5])), 'n': len(v)}
    f = lambda x: f'{x:.1f}'
    ci = lambda c: f'[{c[0]:.1f}, {c[1]:.1f}]'
    L = ['# Robustness gap (clean - styled), rule-based perturbations', '',
         '| model | benchmark | n | clean | styled (mean of 7) | gap (95% CI) | ' + ' | '.join(STYLED) + ' |',
         '|---|---|---|---|---|---|' + '---|' * len(STYLED)]
    for m in models:
        for b in BENCHES:
            s = rep['models'][m][b]
            L.append(f"| {m} | {b} | {s['n']} | {f(s['clean'])} | {f(s['styled'])} | {f(s['gap'])} {ci(s['gap_ci'])} | "
                     + ' | '.join(f(s['gap_by'][v]) for v in STYLED) + ' |')
    L += ['', '## Paired comparisons (difference in pooled gap and in clean score, 10k paired bootstrap over items)', '',
          '| comparison | benchmark | gap difference (95% CI) | clean difference (95% CI) |', '|---|---|---|---|']
    for c, d in rep['compare'].items():
        for b, s in d.items():
            L.append(f"| {c} | {b} | {f(s['gap_diff'])} {ci(s['gap_diff_ci'])} | {f(s['clean_diff'])} {ci(s['clean_diff_ci'])} |")
    if rep['persona']:
        L += ['', '## Robustness gap, persona rewrites (held-out personas, Gemma 4 rewriter, intent-checked)', '',
              '| model | benchmark | n items | clean | persona (mean of 3) | gap (95% CI) |', '|---|---|---|---|---|---|']
        for m, d in rep['persona'].items():
            for b, s_ in d.items():
                L.append(f"| {m} | {b} | {s_['n']} | {f(s_['clean'])} | {f(s_['styled'])} | {f(s_['gap'])} {ci(s_['gap_ci'])} |")
        L += ['', '| comparison | benchmark | persona gap difference (95% CI) |', '|---|---|---|']
        for c, d in rep['persona_compare'].items():
            for b, s_ in d.items():
                L.append(f"| {c} | {b} | {f(s_['gap_diff'])} {ci(s_['gap_diff_ci'])} |")
    L += ['', '## Clean capability (letter-answer chat prompts)', '', '| model | MMLU | ARC-Challenge |', '|---|---|---|']
    for m in models:
        d = rep['clean_only'].get(m, {})
        L.append(f"| {m} | " + ' | '.join(f"{f(d[b]['score'])} {ci(d[b]['ci'])}" if b in d else '-' for b in ('mmlu', 'arc')) + ' |')
    open(os.path.join(E, f'main_table{SFX}.md'), 'w').write('\n'.join(L) + '\n')
    json.dump(rep, open(os.path.join(E, f'report{SFX}.json'), 'w'), indent=1, default=float)
    print('\n'.join(L))
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 3, figsize=(11, 3.2), sharey=False)
        cols = ['#cbccf3', '#4a448e', '#77756f']
        for ax, b in zip(axes, ('ifeval', 'gsm8k', 'mbpp')):
            w = 0.8 / len(models)
            for k, m in enumerate(models):
                s = rep['models'][m][b]
                xs = np.arange(len(STYLED)) + (k - (len(models) - 1) / 2) * w
                ys = [s['gap_by'][v] for v in STYLED]
                lo = [ys[j] - s['gap_by_ci'][v][0] for j, v in enumerate(STYLED)]
                hi = [s['gap_by_ci'][v][1] - ys[j] for j, v in enumerate(STYLED)]
                ax.bar(xs, ys, w * 0.9, color=cols[k % 3], label=m, yerr=[lo, hi], error_kw={'elinewidth': 0.7, 'capsize': 1.5})
            ax.axhline(0, color='#52514e', lw=0.6)
            ax.set_xticks(range(len(STYLED)), STYLED, rotation=40, fontsize=7)
            ax.set_title(b, loc='left', fontsize=9, fontweight='bold')
            ax.set_ylabel('gap, clean - styled (points)', fontsize=7)
            for sd in ('top', 'right'):
                ax.spines[sd].set_visible(False)
        axes[0].legend(fontsize=7, frameon=False)
        fig.tight_layout()
        fig.savefig(os.path.join(E, f'gap_by_perturbation{SFX}.png'), dpi=200)
    except Exception as e:
        print('plot skipped:', e)


if __name__ == '__main__':
    main()
