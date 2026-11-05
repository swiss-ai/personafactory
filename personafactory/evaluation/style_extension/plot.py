#!/usr/bin/env python3
"""Calibration figure of the style-extension A/B (DIR/report.json + DIR/gen) -> DIR/figs/style_ab_calibration.{png,pdf}.
  (a) both-orders 'reads more like a real person' verdicts: real WildChat turn vs each arm's rewrite of it
  (b) typing features of the same first turns (English, free mode, WildChat seeds, all three arms passed):
      real users vs arms A / B / C
Uses the shared paper figure style (personafactory.figures.style).

Usage:
    python -m personafactory.evaluation.style_extension.plot --dir ./outputs/style_extension
"""
import argparse, collections, glob, json, os, re

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from personafactory.figures import style as S   # configures matplotlib (Agg, Inter if available)

INK_PRIMARY, INK_SECONDARY, INK_MUTED, GRID = S.INK_PRIMARY, S.INK_SECONDARY, S.INK_MUTED, S.GRID
plt.rcParams.update({'axes.titlesize': 9, 'font.size': 8})
# arms as a three-step ramp (light -> dark = less -> more persona detail)
ARM = {'A': ('#cbccf3', 'A: raw source record'), 'B': ('#9b9ae6', 'B: converted background'),
       'C': ('#4a448e', 'C: background + style')}
REAL = INK_SECONDARY
EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿]|[:;]-?[)(DP]')
GREET = re.compile(r'^\W*(hi+|hello|hey+|yo|good (morning|evening|afternoon))\b', re.I)
CLOSE = re.compile(r'\b(thanks?|thx|ty|cheers|plz|pls|please)\W*$', re.I)
SLANG = re.compile(r'\b(u|ur|pls|plz|fr|lol|idk|tbh|btw|ngl|thx|gonna|wanna|kinda)\b', re.I)
FEATURES = [('starts lowercase', lambda s: s[:1].isalpha() and s[:1].islower()),
            ('no final punctuation', lambda s: s[-1:] not in '.!?)"\''),
            ('chat slang (u, plz, lol, fr)', lambda s: bool(SLANG.search(s))),
            ('greeting at start', lambda s: bool(GREET.search(s))),
            ('thanks / please at end', lambda s: bool(CLOSE.search(s))),
            ('ellipsis', lambda s: '...' in s or '…' in s),
            ('emoji or emoticon', lambda s: bool(EMOJI.search(s))),
            ('repeated !! or ??', lambda s: bool(re.search(r'[!?]{2,}', s)))]


def hgrid(ax):
    for side in ('top', 'right', 'left'):
        ax.spines[side].set_visible(False)
    ax.spines['bottom'].set_color(GRID)
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir', required=True, help='A/B directory with report.json, assign.jsonl and gen/')
    ap.add_argument('--report', default='report.json', help='report file in --dir (aggregate.py --out)')
    a = ap.parse_args()
    rep = json.load(open(os.path.join(a.dir, a.report)))
    meta = {json.loads(l)['pair_key']: json.loads(l) for l in open(a.dir + '/assign.jsonl')}
    gen = collections.defaultdict(dict)
    for f in glob.glob(a.dir + '/gen/*.jsonl'):
        for l in open(f, encoding='utf-8'):
            r = json.loads(l)
            if r['status'] == 'pass':
                gen[r['pair_key']][r['arm']] = r
    keys = [k for k, v in gen.items() if len(v) == 3 and meta[k]['mode'] == 'free' and meta[k]['source_name'] == 'wildchat']
    texts = {'real': [gen[k]['C']['result']['metadata']['turns_detail'][0]['user_message_source'].strip() for k in keys]}
    for x in 'ABC':
        texts[x] = [next(m['content'] for m in gen[k][x]['result']['conversation'] if m['role'] == 'user').strip() for k in keys]
    rates = {g: [100 * sum(map(fn, ts)) / len(ts) for _, fn in FEATURES] for g, ts in texts.items()}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.6, 3.3), gridspec_kw={'width_ratios': [1, 1.1], 'wspace': 0.75})

    # (a) diverging stacked bars: real wins | orders disagree | rewrite wins
    for y, x in enumerate('CBA'):
        d = rep['pairwise_both_orders'][f'calib_real/R{x}']
        rw, dr, aw = d['R_wins']['pct'], d['draws']['pct'], d[f'{x}_wins']['pct']
        h = dr / 2   # draws straddle the centre line
        ax1.barh(y, -rw, left=-h, color=REAL, height=0.62, edgecolor='white', linewidth=1.0)
        ax1.barh(y, dr, left=-h, color=GRID, height=0.62, edgecolor='white', linewidth=1.0)
        ax1.barh(y, aw, left=h, color=ARM[x][0], height=0.62, edgecolor='white', linewidth=1.0)
        ax1.text(-h - rw - 2, y, f'{rw:.0f}', ha='right', va='center', fontsize=7, color=INK_SECONDARY)
        ax1.text(0, y, f'{dr:.0f}', ha='center', va='center', fontsize=6.5, color=INK_MUTED)
        ax1.text(h + aw + 2, y, f'{aw:.0f}', ha='left', va='center', fontsize=7,
                 color=INK_PRIMARY if x == 'C' else INK_SECONDARY, fontweight='bold' if x == 'C' else None)
    ax1.set_yticks(range(3), [f'real vs {ARM[x][1]}' for x in 'CBA'], fontsize=7.5)
    ax1.set_xlim(-70, 90)
    ax1.set_xticks([])
    for side in ('top', 'right', 'left', 'bottom'):
        ax1.spines[side].set_visible(False)
    ax1.tick_params(length=0)
    ax1.text(-30, 2.5, '← real message\npreferred', ha='center', va='bottom', fontsize=7, color=INK_SECONDARY)
    ax1.text(45, 2.5, 'rewrite →\npreferred', ha='center', va='bottom', fontsize=7, color=INK_SECONDARY)
    ax1.set_ylim(-0.55, 3.05)
    ax1.set_xlabel('% of seeds (grey: verdict flips with order)')
    ax1.set_title('(a) "Reads more like a real person"', loc='left', fontweight='bold', color=INK_PRIMARY)

    # (b) dot plot of typing features, real users as the reference
    n = len(FEATURES)
    for j in range(n):
        y = n - 1 - j
        vals = [rates[g][j] for g in ('real', 'A', 'B', 'C')]
        ax2.plot([min(vals), max(vals)], [y, y], color=GRID, linewidth=1.2, zorder=1)
        for x, dy in (('A', 0.14), ('B', -0.14)):   # A and B often coincide; offset so both stay visible
            ax2.plot(rates[x][j], y + dy, 'o', ms=4.5, color=ARM[x][0], mec='white', mew=0.6, zorder=3)
        ax2.plot(rates['C'][j], y, 'o', ms=6, color=ARM['C'][0], mec='white', mew=0.8, zorder=4)
        ax2.plot(rates['real'][j], y, 'D', ms=5.5, color=REAL, mec='white', mew=0.8, zorder=5)
        ax2.text(max(rates['C'][j], rates['real'][j]) + 2, y, f"{rates['C'][j]:.0f}", ha='left', va='center', fontsize=6.5,
                 color=ARM['C'][0])
    ax2.set_yticks(range(n), [f for f, _ in FEATURES][::-1], fontsize=7.5)
    ax2.set_ylim(-0.6, n - 0.4)
    ax2.set_xlim(-2, 68)
    ax2.set_xlabel(f'% of first user turns ({len(keys)} English seeds)')
    ax2.set_title('(b) Typing features vs real users', loc='left', fontweight='bold', color=INK_PRIMARY)
    hgrid(ax2)
    handles = [Line2D([], [], marker='D', ls='', ms=5, color=REAL, label='real WildChat user')]
    handles += [Line2D([], [], marker='o', ls='', ms=5, color=ARM[x][0], label=ARM[x][1]) for x in 'ABC']
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(0.5, 0.01), ncol=4, fontsize=7, frameon=False)
    os.makedirs(a.dir + '/figs', exist_ok=True)
    for ext in ('png', 'pdf'):
        fig.savefig(f'{a.dir}/figs/style_ab_calibration.{ext}', dpi=250, bbox_inches='tight')
    print(json.dumps({g: [round(v, 1) for v in r] for g, r in rates.items()}), len(keys))


if __name__ == '__main__':
    main()
