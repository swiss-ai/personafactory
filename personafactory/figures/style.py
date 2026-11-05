"""Shared house style of all paper figures: purple ramp, Inter font, ink colours, recessive axes.

Importing this module configures matplotlib (Agg backend, rcParams). The Inter font is not
shipped with the code (OFL-licensed); put Inter-*.ttf into $PF_FONT_DIR (default: figures/fonts)
or install it system-wide. Without it the figures fall back to DejaVu Sans.
"""
import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# ---------------------------------------------------------------- palette
# Single-hue purple ramp, light->dark, stepped in OKLCH off the house palette's
# violet slot (#4a3aa7) on the lightness envelope of its sequential ramp.
PURPLE_RAMP = ["#dcddf9", "#cbccf3", "#bbbcf0", "#ababea", "#9b9ae6",
               "#8c8ae0", "#7d78dc", "#7069cd", "#635db7", "#5650a3",
               "#4a448e", "#3e397b", "#332e66"]
# Bar hue: the ramp step whose lightness matches the palette's slot-1 anchor.
# Validated light-mode: lightness band, chroma floor and >=3:1 contrast all pass.
SERIES_1 = "#7069cd"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#77756f"
GRID = "#dedcd6"
NO_DATA = "#eceae5"           # countries absent from the bank
SEQ_CMAP = LinearSegmentedColormap.from_list("bank_purple", PURPLE_RAMP)
# Two-series figures use the ramp pair dark / light (validated light-mode, CVD dE 28.5),
# always direct-labelled.
DARK, LIGHT = "#4a448e", "#9b9ae6"

# Inter, loaded from PF_FONT_DIR if present so the figures render identically anywhere.
FONT_DIR = os.environ.get("PF_FONT_DIR",
                          os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts"))
for _f in glob.glob(os.path.join(FONT_DIR, "*.ttf")):
    fm.fontManager.addfont(_f)
_FONT = "Inter" if any(f.name == "Inter" for f in fm.fontManager.ttflist) else "DejaVu Sans"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": [_FONT, "DejaVu Sans"],
    "pdf.fonttype": 42,        # embed TrueType so text stays selectable
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK_SECONDARY,
    "text.color": INK_PRIMARY,
    "xtick.color": INK_SECONDARY,
    "ytick.color": INK_SECONDARY,
    "axes.titlesize": 9,
    "font.size": 8,
})


def style_axes(ax):
    """Recessive grid and axes: value grid only, no chartjunk."""
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, labelsize=7)


def hgrid(ax):
    """Horizontal-bar / dot-plot variant of style_axes: value grid on x."""
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.yaxis.grid(False)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def out_path(out_dir, name):
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, name)
