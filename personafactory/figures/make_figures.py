#!/usr/bin/env python
"""Render the persona-bank coverage figures as vector PDFs.

  fig_persona_map.pdf         world choropleth of personas per country
  fig_persona_background.pdf  per-feature background distributions
  fig_persona_style.pdf       per-feature communication-style distributions

Inputs: bank_stats.json from compute_stats.py and a Natural Earth admin-0 countries GeoJSON
(figures/world.geojson).

Usage:
    python -m personafactory.figures.make_figures --stats ./outputs/figures/bank_stats.json \
        --world figures/world.geojson --out-dir ./outputs/figures
"""
import argparse
import json
import os

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection

from personafactory.figures.style import (SEQ_CMAP, SERIES_1, INK_PRIMARY, INK_SECONDARY, INK_MUTED,
                           NO_DATA, style_axes, out_path)

STATS = None
TOTAL = None

# Features whose categories have an inherent order; everything else is
# sorted by frequency.
ORDERED = {
    "fluency": ["Low", "Medium", "High"],
    "sentence_length": ["Short/Fragmented", "Medium", "Long/Elaborate"],
    "education": ["No formal education", "Primary school", "Some high school",
                  "High school diploma", "Vocational / Trade training",
                  "Some college", "Associate's degree", "Bachelor's degree",
                  "Professional degree", "Master's degree", "Doctoral degree"],
}


# Rotated tick labels must stay on one line: a second line runs into the
# neighbouring label. Long names are shortened instead.
ABBREV = {
    "Vocational / Trade training": "Vocational/Trade",
    "minimal (drops end punctuation)": "minimal (no punct.)",
    "fragmented across short lines": "fragmented lines",
    "medium, complete sentences": "medium sentences",
    "first-word only, no final period": "first-word only",
    "ALL-CAPS for emphasis": "ALL-CAPS",
    "occasional uncorrected typos": "occasional typos",
    "voice-to-text/autocorrect": "voice-to-text",
    "other (free-text)": "other",
    "Cloud infrastructure engineer": "Cloud infra engineer",
    "Central & North Asia": "Central/North Asia",
}


def short_label(s, width=22):
    s = ABBREV.get(s, s)
    return s if len(s) <= width else s[:width - 1] + "…"


def bar(ax, counts, title, top=None, order=None, show_total=True):
    """Vertical bar panel for one feature. Single series -> one hue, no legend."""
    items = list(counts.items())
    if order:
        rank = {k: i for i, k in enumerate(order)}
        unknown = [k for k, _ in items if k not in rank]
        if unknown:  # never drop a category silently
            raise ValueError(f"{title}: categories missing from the order list: {unknown}")
        items.sort(key=lambda kv: rank[kv[0]])
    else:
        items.sort(key=lambda kv: kv[1], reverse=True)
        if top:
            items = items[:top]
    labels = [k for k, _ in items]
    values = np.array([v for _, v in items], dtype=float)
    pct = 100 * values / TOTAL

    x = np.arange(len(labels))
    ax.bar(x, pct, width=0.68, color=SERIES_1, linewidth=0)
    ax.set_xticks(x)
    ax.set_xticklabels([short_label(l) for l in labels], fontsize=6.5,
                       rotation=45, ha="right", rotation_mode="anchor")
    style_axes(ax)
    ax.set_ylim(0, pct.max() * 1.18)
    ax.set_ylabel("% of bank", fontsize=7, color=INK_MUTED)

    # Direct value labels only where they fit: on dense panels the axis carries
    # the magnitude instead.
    if len(labels) <= 8:
        for xi, p in zip(x, pct):
            ax.text(xi, p + pct.max() * 0.03, f"{p:.1f}", ha="center",
                    va="bottom", fontsize=6.5, color=INK_SECONDARY)

    if top and len(counts) > top:
        title = (f"{title}  (top {top} of {len(counts)})" if show_total
                 else f"{title}  (top {top})")
    ax.set_title(title, loc="left", fontweight="bold", color=INK_PRIMARY, pad=6)


def age_panel(ax):
    ages = np.array(STATS["_ages"])
    ax.hist(ages, bins=np.arange(15, 85, 5), color=SERIES_1, linewidth=0)
    style_axes(ax)
    ax.set_xlabel("age", fontsize=7, color=INK_MUTED)
    ax.set_ylabel("personas", fontsize=7, color=INK_MUTED)
    ax.set_title("Age", loc="left", fontweight="bold", color=INK_PRIMARY, pad=6)
    ax.axvline(ages.mean(), color=INK_SECONDARY, linewidth=1.0, linestyle="--")
    ax.text(ages.mean() + 1.2, ax.get_ylim()[1] * 0.93, f"mean {ages.mean():.1f}",
            fontsize=6.5, color=INK_SECONDARY)


# ---------------------------------------------------------------- map
def iter_polys(geom):
    if geom["type"] == "Polygon":
        yield geom["coordinates"][0]
    elif geom["type"] == "MultiPolygon":
        for part in geom["coordinates"]:
            yield part[0]


def make_map(world_path, path="fig_persona_map.pdf"):
    world = json.load(open(world_path))
    counts = STATS["country"]
    iso = STATS["_country_iso"]
    by_iso = {iso[c]: n for c, n in counts.items() if c in iso}

    vmax = max(by_iso.values())
    norm = Normalize(vmin=0, vmax=vmax)

    fig, ax = plt.subplots(figsize=(7.4, 3.9))
    patches, colors, missing = [], [], []
    for feat in world["features"]:
        code = feat["properties"].get("ISO_A3_EH") or feat["properties"].get("ISO_A3")
        n = by_iso.get(code)
        for ring in iter_polys(feat["geometry"]):
            poly = Polygon(np.array(ring), closed=True)
            if n:
                patches.append(poly)
                colors.append(n)
            else:
                missing.append(poly)

    # Countries outside the sampling grid first, so they read as background.
    ax.add_collection(PatchCollection(missing, facecolor=NO_DATA,
                                      edgecolor="white", linewidth=0.25))
    pc = PatchCollection(patches, cmap=SEQ_CMAP, norm=norm,
                         edgecolor="white", linewidth=0.25)
    pc.set_array(np.array(colors))
    ax.add_collection(pc)

    ax.set_xlim(-170, 185)
    ax.set_ylim(-58, 84)          # trims Antarctica; keeps every sampled country
    ax.set_aspect("equal")
    ax.axis("off")

    cb = fig.colorbar(pc, ax=ax, orientation="vertical", fraction=0.023,
                      pad=0.01, shrink=0.72)
    cb.set_label("personas per country", fontsize=7.5, color=INK_SECONDARY)
    cb.ax.tick_params(labelsize=7, length=0)
    cb.outline.set_visible(False)

    # Title and framing text live in the LaTeX caption, not in the figure.
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def make_background(path="fig_persona_background.pdf"):
    fig, axes = plt.subplots(3, 3, figsize=(7.6, 7.6))
    bar(axes[0, 0], STATS["region"], "Macro-region")
    age_panel(axes[0, 1])
    bar(axes[0, 2], STATS["gender"], "Gender")
    bar(axes[1, 0], STATS["education"], "Education", order=ORDERED["education"])
    bar(axes[1, 1], STATS["fluency"], "Digital fluency", order=ORDERED["fluency"])
    bar(axes[1, 2], STATS["ai_stance"], "AI stance")
    bar(axes[2, 0], STATS["occupation"], "Occupation", top=10)
    bar(axes[2, 1], STATS["language"], "Main language", top=10, show_total=False)
    bar(axes[2, 2], STATS["generator"], "Generator model")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def make_style(path="fig_persona_style.pdf"):
    fig, axes = plt.subplots(4, 2, figsize=(7.6, 9.4))
    bar(axes[0, 0], STATS["capitalization"], "Capitalization")
    bar(axes[0, 1], STATS["punctuation"], "Punctuation")
    bar(axes[1, 0], STATS["emoji_use"], "Emoji use")
    bar(axes[1, 1], STATS["typo_tendency"], "Typo tendency")
    bar(axes[2, 0], STATS["message_structure"], "Message structure")
    bar(axes[2, 1], STATS["sentence_length"], "Sentence length",
        order=ORDERED["sentence_length"])
    bar(axes[3, 0], STATS["code_switching_freq"], "Code-switching frequency")
    bar(axes[3, 1], STATS["question_framing"], "Question framing")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def main():
    global STATS, TOTAL
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stats", default="bank_stats.json", help="bank_stats.json from compute_stats.py")
    ap.add_argument("--world", default=os.path.join(here, "world.geojson"),
                    help="Natural Earth admin-0 countries GeoJSON")
    ap.add_argument("--out-dir", default=".", help="directory for the PDFs")
    args = ap.parse_args()

    STATS = json.load(open(args.stats))
    TOTAL = STATS["_total"]
    make_map(args.world, out_path(args.out_dir, "fig_persona_map.pdf"))
    make_background(out_path(args.out_dir, "fig_persona_background.pdf"))
    make_style(out_path(args.out_dir, "fig_persona_style.pdf"))


if __name__ == "__main__":
    main()
