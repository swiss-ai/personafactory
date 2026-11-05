#!/usr/bin/env python
"""Render the attribute-ablation figures as vector PDFs.

  fig_ablation_heatmap.pdf   17 single-attribute conditions x 3 fidelity metrics
  fig_ablation_models.pdf    the same run summarised per rewriter model

Palette, font and axis styling come from figures.style so these match the persona-bank figures
exactly. Input: ablation_stats.json from evaluation.attribute_ablation.summarize --figure-stats.

Usage:
    python -m personafactory.figures.make_ablation_figures --stats ./outputs/figures/ablation_stats.json \
        --out-dir ./outputs/figures
"""
import argparse
import json

import matplotlib.pyplot as plt
import numpy as np

# Shared house style: purple ramp, Inter, ink colours, recessive axes.
from personafactory.figures.style import (SEQ_CMAP, SERIES_1, INK_PRIMARY, INK_SECONDARY,
                           INK_MUTED, NO_DATA, style_axes, out_path)

A = None
MODEL_LABEL = {"gemma": "Gemma 4 31B", "ministral": "Ministral 3 14B",
               "glm": "GLM 4.7 Flash", "minimax": "MiniMax M2.5"}
# Shorter than the dashboard labels so the row axis stays narrow.
SHORT = {
    "Baseline (no persona)": "Baseline (no persona)",
    "Digital fluency: Low": "Digital fluency: low",
    "Digital fluency: High": "Digital fluency: high",
    "Sentence length: Short/Fragmented": "Sentence length: short",
    "Sentence length: Long/Elaborate": "Sentence length: long",
    "AI stance: Skeptical": "AI stance: skeptical",
    "AI stance: Enthusiastic": "AI stance: enthusiastic",
    "Age: Young (20)": "Age: young (20)",
    "Age: Old (68)": "Age: old (68)",
    "Gender: Male": "Gender: male",
    "Gender: Female": "Gender: female",
    "Education: No formal": "Education: none",
    "Education: Doctoral": "Education: doctoral",
    "Occupation: Software Engineer": "Occupation: software engineer",
    "Occupation: Manual laborer": "Occupation: manual laborer",
    "Hobbies: Tech/Gaming": "Hobbies: tech/gaming",
    "Hobbies: Outdoor/Nature": "Hobbies: outdoor/nature",
}


def make_heatmap(path="fig_ablation_heatmap.pdf"):
    hm = A["heatmap"]
    rows = hm["conditions"]
    cols = hm["metrics"]
    z = np.array([[np.nan if v is None else v for v in r] for r in hm["z"]],
                 dtype=float)

    fig, ax = plt.subplots(figsize=(5.4, 5.6))
    # One shared 0-1 scale across all three columns: the columns genuinely sit at
    # different levels, and rescaling per column would invent contrast that the
    # data does not have.
    im = ax.imshow(z, cmap=SEQ_CMAP, vmin=0, vmax=1, aspect="auto")

    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, fontsize=8)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([SHORT.get(r, r) for r in rows], fontsize=7.5)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)

    # Thin white gaps between cells rather than a drawn grid.
    ax.set_xticks(np.arange(-.5, len(cols), 1), minor=True)
    ax.set_yticks(np.arange(-.5, len(rows), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.4)
    ax.tick_params(which="minor", length=0)

    for i in range(z.shape[0]):
        for j in range(z.shape[1]):
            v = z[i, j]
            if np.isnan(v):
                ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1,
                                           facecolor=NO_DATA, edgecolor="white",
                                           linewidth=1.4, zorder=2))
                ax.text(j, i, "n/a", ha="center", va="center", fontsize=7,
                        color=INK_MUTED, zorder=3)
            else:
                # Ink flips to white once the cell is dark enough to need it.
                ax.text(j, i, f"{v:.3f}", ha="center", va="center", fontsize=7,
                        color="white" if v > 0.62 else INK_PRIMARY, zorder=3)

    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02, shrink=0.55)
    cb.set_label("score (0--1)", fontsize=7.5, color=INK_SECONDARY)
    cb.ax.tick_params(labelsize=7, length=0)
    cb.outline.set_visible(False)

    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def make_models(path="fig_ablation_models.pdf"):
    pm = A["per_model"]
    metrics = A["heatmap"]["metrics"]
    models = ["gemma", "ministral", "minimax", "glm"]

    fig, axes = plt.subplots(1, 3, figsize=(7.4, 2.9))
    for ax, metric in zip(axes, metrics):
        vals = [float(np.mean(pm[m][metric])) for m in models]
        x = np.arange(len(models))
        ax.bar(x, vals, width=0.66, color=SERIES_1, linewidth=0)
        ax.set_xticks(x)
        ax.set_xticklabels([MODEL_LABEL[m] for m in models], fontsize=7,
                           rotation=30, ha="right", rotation_mode="anchor")
        style_axes(ax)
        ax.set_ylim(0, 1.08)
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_title(metric, loc="left", fontweight="bold",
                     color=INK_PRIMARY, pad=6)
        for xi, v in zip(x, vals):
            ax.text(xi, v + 0.03, f"{v:.2f}", ha="center", va="bottom",
                    fontsize=7, color=INK_SECONDARY)
    axes[0].set_ylabel("mean score", fontsize=7, color=INK_MUTED)

    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def main():
    global A
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stats", default="ablation_stats.json", help="output of evaluation.attribute_ablation.summarize --figure-stats")
    ap.add_argument("--out-dir", default=".", help="directory for the PDFs")
    args = ap.parse_args()
    A = json.load(open(args.stats))
    make_heatmap(out_path(args.out_dir, "fig_ablation_heatmap.pdf"))
    make_models(out_path(args.out_dir, "fig_ablation_models.pdf"))


if __name__ == "__main__":
    main()
