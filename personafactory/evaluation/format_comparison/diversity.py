#!/usr/bin/env python
"""Style diversity, measured properly.

The naive version -- spread of adherence booleans -- is wrong: a condition that matches
its target consistently scores LOW variance and looks undiverse. What the paper's premise
actually claims is that persona conditioning spreads realized style ACROSS personas.

Each item pairs one seed prompt with one persona, so raw spread confounds persona
variation with seed variation. The `none` condition gives the seed-only rewrite for the
same item, so the per-item deviation from it isolates the persona's contribution:

    delta_i(c) = feature(rewrite_i under c) - feature(rewrite_i under none)

The spread of delta across items is persona-driven style variance. Mean |delta| says how
far conditioning moves style at all; sd(delta) says how differently it moves it per persona.

Run: python -m personafactory.evaluation.format_comparison.diversity --generations ./outputs/format_comparison/generations.jsonl --label gemma
"""
import argparse, json, re, statistics, sys, unicodedata
from collections import defaultdict

EMOJI = re.compile("[" "\U0001F300-\U0001FAFF" "\U00002600-\U000027BF" "]")
CONDS = ["personahub", "synthpai", "personafactory"]


def feats(t):
    t = t or ""
    letters = [c for c in t if c.isalpha()]
    words = re.findall(r"\w+", t, re.UNICODE)
    sents = [s for s in re.split(r"[.!?\n]+", t) if s.strip()]
    return {
        "lowercase_ratio": (sum(1 for c in letters if c.islower()) / len(letters)) if letters else 0.0,
        "emoji_per_100w": 100 * len(EMOJI.findall(t)) / max(1, len(words)),
        "ends_terminal": 1.0 if re.search(r"[.!?]\s*$", t.strip()) else 0.0,
        "mean_sent_words": (len(words) / len(sents)) if sents else 0.0,
        "exclaim_per_100w": 100 * t.count("!") / max(1, len(words)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--generations", default="./outputs/format_comparison/generations.jsonl")
    ap.add_argument("--label", default="gemma")
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.generations)]
    by = defaultdict(dict)
    for r in rows:
        if r.get("rewrite"):
            by[r["item_id"]][r["condition"]] = r["rewrite"]

    keys = list(feats(""))
    print(f"[{a.label}] style diversity across personas, "
          f"deviation from the same item's no-persona rewrite\n")
    print(f"  {'feature':20s}" + "".join(f"{c[:14]:>17s}" for c in CONDS))
    for k in keys:
        line_sd, line_mag = f"  {k:20s}", f"  {'  (mean |move|)':20s}"
        for c in CONDS:
            d = [feats(v[c])[k] - feats(v["none"])[k]
                 for v in by.values() if c in v and "none" in v]
            if len(d) > 1:
                line_sd += f"{statistics.stdev(d):16.3f} "
                line_mag += f"{statistics.mean(abs(x) for x in d):16.3f} "
            else:
                line_sd += f"{'-':>17s}"; line_mag += f"{'-':>17s}"
        print(line_sd); print(line_mag)
    n = sum(1 for v in by.values() if "none" in v and all(c in v for c in CONDS))
    print(f"\n  sd  = how DIFFERENTLY the representation moves style per persona (diversity)")
    print(f"  mean|move| = how FAR it moves style at all (effect size)")
    print(f"  n = {n} items")


if __name__ == "__main__":
    main()
