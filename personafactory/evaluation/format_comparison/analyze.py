#!/usr/bin/env python
"""Paired analysis across conditions: per-condition metric means, paired deltas vs PersonaFactory with
bootstrap CIs, style spread, the PersonaHub-form inertness check, and the judge tallies (pairwise preference with
McNemar test, per-rewrite verdict rates).

Run: python -m personafactory.evaluation.format_comparison.analyze --metrics ./outputs/format_comparison/metrics.jsonl \
         --judge ./outputs/format_comparison/judgments.jsonl [--slice english | cross_lingual]
"""
from __future__ import annotations

import argparse, json, math, random, statistics
from collections import defaultdict

CONDS = ["none", "personahub", "synthpai", "personafactory"]


def paired_bootstrap(pairs, n=10000, seed=7):
    """CI on mean(a-b) over items present in both conditions."""
    rng = random.Random(seed)
    d = [a - b for a, b in pairs]
    if not d: return (float("nan"),) * 3
    obs = statistics.mean(d)
    boots = []
    for _ in range(n):
        s = [d[rng.randrange(len(d))] for _ in range(len(d))]
        boots.append(sum(s) / len(s))
    boots.sort()
    return obs, boots[int(0.025 * n)], boots[int(0.975 * n)]


def mcnemar(b, c):
    """Exact-ish two-sided McNemar on discordant counts."""
    n = b + c
    if n == 0: return 1.0
    p = sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / (2 ** n)
    return min(1.0, 2 * p)


def load(path):
    return [json.loads(l) for l in open(path)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", default="./outputs/format_comparison/metrics.jsonl")
    ap.add_argument("--judge", default="./outputs/format_comparison/judgments.jsonl")
    ap.add_argument("--slice", default="", help="e.g. english / cross_lingual")
    args = ap.parse_args()

    M = load(args.metrics)
    if args.slice:
        M = [m for m in M if m.get("stratum") and args.slice in m["stratum"][0]]
    by = defaultdict(dict)
    for m in M: by[m["item_id"]][m["condition"]] = m
    print(f"{len(by)} items" + (f" (slice={args.slice})" if args.slice else ""))

    # ---------------- the ladder: per-condition means -------------------------------
    keys = ["persona_block_words",
            "cap_adherence", "punct_adherence", "emoji_adherence",     # style register
            "jaccard_distance", "norm_levenshtein_distance",           # transformation depth
            "core_vocab_retention_rate", "labse_similarity",
            "num_retention_rate", "code_retention_rate",                # constraint retention
            "quote_retention_rate", "entities_fully_preserved",
            "asst_words", "asst_labse_dist_from_none"]                  # assistant side
    print(f"\n{'metric':22s}" + "".join(f"{c[:13]:>14s}" for c in CONDS))
    for k in keys:
        row = f"{k:22s}"
        for c in CONDS:
            vals = [by[i][c][k] for i in by if c in by[i] and by[i][c].get(k) is not None]
            vals = [float(v) for v in vals]
            vals = [v for v in vals if v == v]        # drop NaN
            row += f"{statistics.mean(vals):13.3f} " if vals else f"{'-':>14s}"
        print(row)

    # ---------------- paired deltas vs PersonaFactory --------------------------------
    print("\npaired delta vs personafactory  (negative = PF better), 95% bootstrap CI")
    for k in ["cap_adherence", "punct_adherence", "emoji_adherence",
              "core_vocab_retention_rate", "labse_similarity",
              "num_retention_rate", "quote_retention_rate",
              "entities_fully_preserved", "asst_labse_dist_from_none"]:
        for c in CONDS:
            if c == "personafactory": continue
            pairs = [(float(by[i][c][k]), float(by[i]["personafactory"][k]))
                     for i in by
                     if c in by[i] and "personafactory" in by[i]
                     and by[i][c].get(k) is not None
                     and by[i]["personafactory"].get(k) is not None]
            if not pairs: continue
            o, lo, hi = paired_bootstrap(pairs)
            sig = "" if lo <= 0 <= hi else "  *"
            print(f"  {k:18s} {c:16s} n={len(pairs):4d}  {o:+.3f}  [{lo:+.3f},{hi:+.3f}]{sig}")

    # ---------------- diversity collapse (the non-tautological C1 result) ------------
    print("\nstyle diversity across personas (higher = more varied corpus)")
    print("  spread of realized style per condition, over items sharing a stratum")
    for c in CONDS:
        vals = defaultdict(list)
        for i in by:
            if c not in by[i]: continue
            for k in ["cap_adherence", "punct_adherence", "emoji_adherence"]:
                v = by[i][c].get(k)
                if v is not None: vals[k].append(float(v))
        parts = []
        for k, arr in vals.items():
            if len(arr) > 1: parts.append(f"{k.split('_')[0]} sd={statistics.stdev(arr):.3f}")
        print(f"  {c:16s} " + "  ".join(parts))

    # ---------------- C1 inertness check --------------------------------------------
    print("\nis conditioning inert? (distance of each condition's rewrite from the "
          "no-persona control)")
    for c in CONDS:
        if c == "none": continue
        vals = [by[i][c]["rewrite_lex_dist_from_none"] for i in by
                if c in by[i] and by[i][c].get("rewrite_lex_dist_from_none") is not None]
        if vals:
            print(f"  {c:16s} mean {statistics.mean(vals):.3f}  n={len(vals)}")
    print("  (personahub ~ 0 would mean its conditioning is stylistically inert,")
    print("   a sharper finding than simply scoring lower)")

    # ---------------- judge ----------------------------------------------------------
    try:
        J = load(args.judge)
    except FileNotFoundError:
        print("\n(no judgments yet)"); return
    # judgments carry no stratum of their own, so restrict them to the sliced items --
    # without this every slice silently reports the pooled result
    if args.slice:
        keep = set(by)
        J = [j for j in J if j.get("item_id") in keep]
    print(f"(judge rows in scope: {len(J)})")
    print("\njudge: style preference vs personafactory")
    tally = defaultdict(lambda: defaultdict(int))
    for j in J:
        if j.get("kind") == "pairwise" and not j.get("error") and j.get("winner"):
            tally[j["condition"]][j["winner"]] += 1
    for c, t in tally.items():
        ref, cond, tie = t["ref"], t["cond"], t["tie"]
        tot = ref + cond + tie
        if not tot: continue
        p = mcnemar(ref, cond)
        ratio = ref / cond if cond else float("inf")
        print(f"  PF {ref:4d} / {c} {cond:4d} / tie {tie:3d}   "
              f"PF wins {100*ref/tot:.0f}%  ratio {ratio:.2f}:1  McNemar p={p:.3g}")

    print("\njudge: per-rewrite verdicts (production templates)")
    fams = [("style_ok", "style adoption"), ("intent_ok", "intent preserved"),
            ("sanity_ok", "assistant sanity")]
    print(f"  {'condition':18s}" + "".join(f"{lbl:>20s}" for _, lbl in fams))
    for c in CONDS:
        row = f"  {c:18s}"
        for key, _ in fams:
            vals = [1.0 if j[key] else 0.0 for j in J
                    if j.get("condition") == c and key in j and j[key] is not None]
            row += f"{100*statistics.mean(vals):17.1f}% " if vals else f"{'-':>20s}"
        print(row)
    print("  (a style-free format that preserves intent better is the expected trade-off;")
    print("   compare intent alongside style)")


if __name__ == "__main__":
    main()
