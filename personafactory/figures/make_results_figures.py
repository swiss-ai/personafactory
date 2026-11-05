#!/usr/bin/env python
"""Result figures in the house style of make_figures.py (purple ramp, Inter, recessive grid, ink
tokens). Two-series figures use the ramp pair DARK / LIGHT and are always direct-labelled.

  fig_stacked_languages_regions.pdf  released corpus: top non-English languages and macro-regions, by seed source
                                     (input: --corpus-dist, corpus_dist.json from the release statistics)
  fig_format_tradeoff.pdf            style adoption vs intent across persona formats (values of tab:formats-main)
  fig_ab_rejudge.pdf                 structured-vs-flat A/B under pipeline and external judges (values of tab:ab-rejudge)
  fig_sft_lc.pdf                     raw vs length-controlled pairwise wins after fine-tuning (values of tab:mp-sft-judge)
  fig_format_neutral_rejudge.pdf     persona-format comparison re-judged against a format-neutral reference
                                     (input: --format-results, results JSON of the persona-format comparison)

The three table-backed figures plot the numbers reported in the paper tables, which are written
out below. A figure whose input file is not given is skipped.

Usage:
    python -m personafactory.figures.make_results_figures --out-dir ./outputs/figures \
        --corpus-dist ./outputs/release/corpus_dist.json \
        --format-results ./outputs/persona_formats/results.json
"""
import argparse
import json

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

from personafactory.figures.style import (SERIES_1, INK_PRIMARY, INK_SECONDARY, INK_MUTED, DARK, LIGHT,
                           style_axes, hgrid, out_path)


def err(v, lo, hi):
    return [[v - lo], [hi - v]]


def make_stacked(corpus_dist, path="fig_stacked_languages_regions.pdf"):
    """corpus_dist: {"sources": {src: n}, "languages": {lang: {src: n}}, "regions": {region: {src: n}}}."""
    d = json.load(open(corpus_dist))
    src = d["sources"]
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.4))
    for ax, data, title in ((axes[0], d["languages"], "Top 10 non-English languages"),
                            (axes[1], d["regions"], "Top 10 persona macro-regions")):
        top = sorted(data.items(), key=lambda kv: -sum(kv[1].values()))[:10][::-1]
        names = [k for k, _ in top]
        left = [0] * len(top)
        for s, col in (("nemotron", DARK), ("ultrachat", LIGHT)):
            vals = [v.get(s, 0) for _, v in top]
            ax.barh(names, vals, left=left, color=col, height=0.66, edgecolor="white", linewidth=1.0)
            left = [a + b for a, b in zip(left, vals)]
        mx = max(left)
        for i, t in enumerate(left):
            ax.text(t + mx * 0.015, i, f"{t:,}", va="center", fontsize=7, color=INK_SECONDARY)
        ax.set_xlim(0, mx * 1.18)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x / 1000:.0f}k" if x else "0"))
        ax.set_xlabel("conversations", color=INK_SECONDARY)
        ax.set_title(title, color=INK_PRIMARY, loc="left", fontweight="bold")
        hgrid(ax)
    handles = [plt.Rectangle((0, 0), 1, 1, color=DARK), plt.Rectangle((0, 0), 1, 1, color=LIGHT)]
    fig.legend(handles, [f"Nemotron ({src['nemotron'] / 1000:.1f}k)", f"UltraChat ({src['ultrachat'] / 1000:.1f}k)"],
               loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.03), fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def make_format_tradeoff(path="fig_format_tradeoff.pdf"):
    # (label, style %, style lo, style hi, intent %, intent lo, intent hi)
    fmt = [("No persona\n0 words", 3.1, 2.1, 4.6, 99.8, 99.1, 99.9),
           ("PersonaHub form\n13 words", 5.5, 4.1, 7.3, 99.8, 99.1, 99.9),
           ("SynthPAI form\n83 words", 43.5, 40.1, 47.0, 98.0, 96.8, 98.8),
           ("PersonaFactory\n280 words", 69.2, 66.0, 72.3, 96.1, 94.6, 97.3)]
    fig, ax = plt.subplots(figsize=(4.8, 2.9))
    xs = list(range(len(fmt)))
    for name, col, idx, dy in (("intent preserved", LIGHT, 4, -12), ("style adopted", DARK, 1, 8)):
        ys = [f[idx] for f in fmt]
        ax.plot(xs, ys, color=col, lw=2, zorder=2)
        for x, f in zip(xs, fmt):
            ax.errorbar(x, f[idx], yerr=err(f[idx], f[idx + 1], f[idx + 2]), fmt="o", ms=6, color=col,
                        mec="white", mew=1.2, ecolor=col, elinewidth=1.1, capsize=2.5, zorder=3)
            ax.annotate(f"{f[idx]:.1f}", (x, f[idx]), textcoords="offset points", xytext=(0, dy), ha="center",
                        fontsize=7, color=INK_SECONDARY)
        ax.annotate(name, (xs[-1], ys[-1]), textcoords="offset points", xytext=(12, 0), va="center",
                    fontsize=8, color=INK_PRIMARY)
    ax.set_xticks(xs, [f[0] for f in fmt], fontsize=7.5)
    ax.set_ylim(0, 108)
    ax.set_xlim(-0.3, len(fmt) - 0.3 + 1.0)
    ax.set_ylabel("share of rewrites (%)")
    style_axes(ax)
    ax.tick_params(length=0)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def make_ab_rejudge(path="fig_ab_rejudge.pdf"):
    # (judge, structured preferred % of decisive verdicts, lo, hi, is pipeline judge)
    rows = [("MiniMax-M2.5, original pass (n=433)", 64.0, None, None, True),
            ("MiniMax-M2.5, larger budget (n=514)", 62.4, 58.0, 66.6, True),
            ("DeepSeek-V4-Flash (n=518)", 54.2, 49.8, 58.6, False),
            ("Qwen3.5-397B-A17B (n=444)", 70.7, 66.2, 74.9, False),
            ("Qwen3.6-35B-A3B (n=518)", 64.2, 59.9, 68.3, False)][::-1]
    fig, ax = plt.subplots(figsize=(4.8, 2.2))
    ax.axvline(50, color=INK_MUTED, ls="--", lw=0.9)
    ax.text(50.4, len(rows) - 0.4, "parity", color=INK_MUTED, fontsize=7)
    for i, (name, v, lo, hi, pipe) in enumerate(rows):
        col, mk = (DARK, "o") if pipe else (LIGHT, "s")
        if lo is None:
            ax.plot(v, i, mk, ms=6, mfc="white", mec=col, mew=1.5)
        else:
            ax.errorbar(v, i, xerr=err(v, lo, hi), fmt=mk, ms=6, color=col, mec="white", mew=1.0,
                        ecolor=col, elinewidth=1.4, capsize=2.5)
        ax.annotate(f"{v:.1f}", (hi or v, i), textcoords="offset points", xytext=(6, 0), va="center",
                    fontsize=7, color=INK_SECONDARY)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=7.5)
    ax.set_xlim(40, 80)
    ax.set_xlabel("structured preferred (% of decisive verdicts)")
    hgrid(ax)
    ax.legend(handles=[Line2D([], [], marker="o", ls="", color=DARK, label="pipeline judge"),
                       Line2D([], [], marker="s", ls="", color=LIGHT, label="external judge")],
              loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=2, fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def make_sft_lc(path="fig_sft_lc.pdf"):
    # (comparison, raw win rate %, length-controlled win rate %)
    cmp_ = [("Llama B vs A", 57.0, 48.8), ("Llama C vs A", 54.9, 42.4), ("Llama C vs B", 48.1, 48.6),
            ("Llama C vs Llama-3.1-8B-Instruct", 79.4, 68.6), ("Apertus B vs A", 66.3, 52.1),
            ("Apertus C vs A", 57.1, 44.8), ("Apertus C vs B", 42.0, 42.6)][::-1]
    fig, ax = plt.subplots(figsize=(4.8, 2.6))
    ax.axvline(50, color=INK_MUTED, ls="--", lw=0.9)
    for i, (name, raw, lc) in enumerate(cmp_):
        if abs(raw - lc) >= 1:
            ax.annotate("", xy=(lc, i), xytext=(raw, i),
                        arrowprops=dict(arrowstyle="-|>", color=LIGHT, lw=1.4, shrinkA=4, shrinkB=5))
        ax.plot(raw, i, "o", ms=6, mfc="white", mec=SERIES_1, mew=1.5, zorder=3)
        ax.plot(lc, i, "o", ms=6, color=DARK, mec="white", mew=1.0, zorder=3)
    ax.set_yticks(range(len(cmp_)), [c[0] for c in cmp_], fontsize=7.5)
    ax.set_xlim(38, 84)
    ax.set_xlabel("win rate of the first model (%)")
    hgrid(ax)
    ax.legend(handles=[Line2D([], [], marker="o", ls="", mfc="white", mec=SERIES_1, mew=1.5, label="raw"),
                       Line2D([], [], marker="o", ls="", color=DARK, label="length-controlled")],
              loc="upper center", bbox_to_anchor=(0.5, -0.26), ncol=2, fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def make_neutral_rejudge(results, path="fig_format_neutral_rejudge.pdf"):
    """Representation comparison re-judged against a format-neutral reference (style attribute values only)
    by the pipeline judge and two external judges. (a) style adoption per format; (b) PersonaFactory's share
    of decisive pairwise verdicts against each alternative, 95% Wilson intervals.

    results: {judge: {"style_neutral": {cond: {pct, lo, hi}},
                      "pairwise_neutral": {cond: {"pf_decisive": {pct, lo, hi}}},
                      "pairwise_free": {native_cond: {"pf_decisive": {pct, lo, hi}}}}}
    for judges minimax / qwen36 / muse."""
    import numpy as np
    R = json.load(open(results))
    judges = [("minimax", "MiniMax-M2.5\n(pipeline)"), ("qwen36", "Qwen3.6-35B\n(external)"), ("muse", "Muse-Glimmer-30B\n(external)")]
    conds = [("personahub", "PersonaHub form", "#cbccf3"), ("synthpai", "SynthPAI form", "#9b9ae6"), ("personafactory", "PersonaFactory", DARK)]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.6, 3.3), gridspec_kw={"width_ratios": [1.05, 1]})
    x = np.arange(len(judges))
    w = 0.26
    for k, (c, lab, col) in enumerate(conds):
        vals = [R[j]["style_neutral"][c] for j, _ in judges]
        ys = [v["pct"] for v in vals]
        ax1.bar(x + (k - 1) * w, ys, w * 0.92, color=col, label=lab, zorder=2)
        ax1.errorbar(x + (k - 1) * w, ys, yerr=[[v["pct"] - v["lo"] for v in vals], [v["hi"] - v["pct"] for v in vals]],
                     fmt="none", ecolor=INK_SECONDARY, elinewidth=0.8, capsize=1.8, zorder=3)
        if c == "personafactory":
            for xi, y in zip(x + (k - 1) * w, ys):
                ax1.text(xi, y + 4, f"{y:.0f}", ha="center", fontsize=7, color=INK_PRIMARY, fontweight="bold")
    ax1.set_xticks(x, [l for _, l in judges], fontsize=7.5)
    ax1.set_ylim(0, 100)
    ax1.set_ylabel("style adoption (%)")
    ax1.set_title("(a) Style adoption, format-neutral reference", loc="left", fontweight="bold", color=INK_PRIMARY)
    style_axes(ax1)
    ax1.tick_params(length=0)
    ax1.legend(loc="upper left", fontsize=7, frameon=False, ncol=1)
    rows = []
    for c, lab, task in (("personahub", "PersonaHub form", "pairwise_neutral"), ("synthpai", "SynthPAI form", "pairwise_neutral"),
                         ("native_personahub", "real PersonaHub personas", "pairwise_free"),
                         ("native_synthpai", "real SynthPAI personas", "pairwise_free")):
        for j, jl in judges:
            d = R[j][task][c]["pf_decisive"]
            rows.append((lab, jl.split("\n")[0], d["pct"], d["lo"], d["hi"]))
    rows = rows[::-1]
    marks = {"MiniMax-M2.5": ("o", DARK), "Qwen3.6-35B": ("s", SERIES_1), "Muse-Glimmer-30B": ("D", LIGHT)}
    ax2.axvline(50, color=INK_MUTED, ls="--", lw=0.9)
    ypos, labels, y = [], [], 0
    last = None
    for lab, j, v, lo, hi in rows:
        if last is not None and lab != last:
            y += 0.6
        mk, col = marks[j]
        ax2.errorbar(v, y, xerr=[[v - lo], [hi - v]], fmt=mk, ms=5, color=col, mec="white", mew=0.8, ecolor=col, elinewidth=1.3, capsize=2)
        ypos.append(y)
        labels.append(lab if j == "Qwen3.6-35B" else "")
        last = lab
        y += 1
    ax2.set_yticks(ypos, labels, fontsize=7.5)
    ax2.set_xlim(40, 85)
    ax2.set_xlabel("PersonaFactory preferred (% of decisive verdicts)")
    ax2.set_title("(b) Pairwise style preference", loc="left", fontweight="bold", color=INK_PRIMARY)
    ax2.text(50.6, ypos[0] - 0.75, "parity", color=INK_MUTED, fontsize=7)
    ax2.set_ylim(ypos[0] - 1.0, ypos[-1] + 0.6)
    hgrid(ax2)
    ax2.legend(handles=[Line2D([], [], marker=m, ls="", color=c, label=k) for k, (m, c) in marks.items()],
               loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=3, fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=".", help="directory for the PDFs")
    ap.add_argument("--corpus-dist", help="corpus_dist.json (languages/regions by seed source)")
    ap.add_argument("--format-results", help="persona-format comparison results JSON (format-neutral re-judge)")
    ap.add_argument("--only", nargs="+", choices=["stacked", "tradeoff", "ab", "sft", "neutral"],
                    help="render only these figures")
    args = ap.parse_args()
    want = set(args.only or ["stacked", "tradeoff", "ab", "sft", "neutral"])

    if "stacked" in want:
        if args.corpus_dist:
            make_stacked(args.corpus_dist, out_path(args.out_dir, "fig_stacked_languages_regions.pdf"))
        else:
            print("skip fig_stacked_languages_regions.pdf (no --corpus-dist)")
    if "tradeoff" in want:
        make_format_tradeoff(out_path(args.out_dir, "fig_format_tradeoff.pdf"))
    if "ab" in want:
        make_ab_rejudge(out_path(args.out_dir, "fig_ab_rejudge.pdf"))
    if "sft" in want:
        make_sft_lc(out_path(args.out_dir, "fig_sft_lc.pdf"))
    if "neutral" in want:
        if args.format_results:
            make_neutral_rejudge(args.format_results, out_path(args.out_dir, "fig_format_neutral_rejudge.pdf"))
        else:
            print("skip fig_format_neutral_rejudge.pdf (no --format-results)")


if __name__ == "__main__":
    main()
