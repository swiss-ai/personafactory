#!/usr/bin/env python3
"""Corpus-details figure: (a) top 10 non-English text languages, (b) top 10 persona macro-regions, stacked by
seed source. Writes <release-dir>/corpus_dist.json and the PDF given by --fig.

  python -m personafactory.release.stats.corpus_distribution --release-dir ./release_out \
      --fig ./outputs/figures/fig_stacked_languages_regions.pdf
"""
import argparse, collections, glob, json, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--release-dir', required=True)
ap.add_argument('--bank', default=None, help='persona bank JSONL (default: <release-dir>/persona_bank.jsonl)')
ap.add_argument('--out', default=None, help='default: <release-dir>/corpus_dist.json')
ap.add_argument('--fig', default='./outputs/figures/fig_stacked_languages_regions.pdf')
args = ap.parse_args()
region = {}
for l in open(args.bank or os.path.join(args.release_dir, 'persona_bank.jsonl'), encoding='utf-8'):
    p = json.loads(l)
    region[p['id']] = p['background'].get('region')
lang, reg, src = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter), collections.Counter()
for fp in sorted(glob.glob(os.path.join(args.release_dir, 'data', '*.jsonl'))):
    for l in open(fp, encoding='utf-8'):
        r = json.loads(l)
        s = r['source_name']
        src[s] += 1
        if r['text_language'] not in ('English', 'TooShort', 'Unknown'):
            lang[r['text_language']][s] += 1
        reg[region.get(r['persona_id'])][s] += 1
out = {'sources': dict(src), 'languages': {k: dict(v) for k, v in lang.items()}, 'regions': {str(k): dict(v) for k, v in reg.items()}}
json.dump(out, open(args.out or os.path.join(args.release_dir, 'corpus_dist.json'), 'w'), indent=1)
C = {'nemotron': '#4F46E5', 'ultrachat': '#06B6D4'}
fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.3))
for ax, data, title in ((axes[0], lang, '(a) Top 10 Non-English Languages'), (axes[1], reg, '(b) Top 10 Macro-Regions')):
    top = sorted(data.items(), key=lambda kv: -sum(kv[1].values()))[:10][::-1]
    names = [k for k, _ in top]
    left = [0] * len(top)
    for s in ('nemotron', 'ultrachat'):
        vals = [v[s] for _, v in top]
        ax.barh(names, vals, left=left, color=C[s], height=0.62, label=f"{'Nemotron' if s == 'nemotron' else 'UltraChat'} ({src[s] / 1000:.1f}k)")
        left = [a + b for a, b in zip(left, vals)]
    mx = max(left)
    for i, t in enumerate(left):
        ax.text(t + mx * 0.015, i, f'{t:,}', va='center', fontsize=9, color='#1f2937')
    ax.set_xlim(0, mx * 1.2)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f'{x / 1000:.0f}k' if x else '0'))
    ax.set_xlabel('Conversations')
    ax.set_title(title, fontweight='bold')
    ax.grid(axis='x', linestyle='--', alpha=0.5)
    ax.set_axisbelow(True)
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)
h, lb = axes[0].get_legend_handles_labels()
fig.legend(h, lb, loc='upper center', ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.02))
fig.tight_layout(rect=(0, 0, 1, 0.95))
os.makedirs(os.path.dirname(os.path.abspath(args.fig)), exist_ok=True)
fig.savefig(args.fig, bbox_inches='tight')
tl = sorted(lang.items(), key=lambda kv: -sum(kv[1].values()))[:10]
tr = sorted(reg.items(), key=lambda kv: -sum(kv[1].values()))
print(json.dumps({'sources': src, 'top_lang': [(k, sum(v.values())) for k, v in tl], 'regions': [(k, sum(v.values()), round(v['ultrachat'] / max(1, sum(v.values())), 3)) for k, v in tr]}))
