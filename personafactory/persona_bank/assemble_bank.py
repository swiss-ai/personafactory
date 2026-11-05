#!/usr/bin/env python3
"""Assemble the released persona bank from the base-grid bank and the diversity-filtered extended-grid profiles.

Writes, in this order: every profile of --base, then the profiles of each --part (diversity_filter.py
--output files) in the order given. Within a part, a repeated id is kept once; a part profile whose id is
already in the bank is counted as a clash and skipped. From every profile the two seeded fields that the
released bank does not keep are removed: background.life_stage and background.settlement_type, and their
copies in gen_meta.seed_axes (life_stage, settlement). Every line is written as json.dumps(profile,
ensure_ascii=False).

The released bank: --base = the base-grid bank after emoji rebalancing (99,696 profiles), --part 1 = the
extended-grid profiles over all 13 target blocks (546,547 kept), --part 2 = the extended-grid profiles of
the European blocks and Southeast Asia (96,767 kept): 743,010 profiles.

The report (--report) has the number of profiles per part and in total, id clashes, the diversity-filter
drop reasons (from --dropped files, if given), and counts by target block, region, country, location,
main_language and generator.

Usage:
    python -m personafactory.persona_bank.assemble_bank \\
        --base ./data/persona_bank/base/persona_bank.jsonl \\
        --part ./data/persona_bank/extended/diversity/kept.jsonl \\
        --part ./data/persona_bank/extended_eu_sea/diversity/kept.jsonl \\
        --dropped ./data/persona_bank/extended/diversity/dropped.jsonl \\
        --dropped ./data/persona_bank/extended_eu_sea/diversity/dropped.jsonl \\
        --out ./data/persona_bank.jsonl --report ./data/persona_bank_report.json
"""
import argparse
import collections
import json
import os

from personafactory.persona_bank.grid_extended import target_block

DROP_BACKGROUND = ("life_stage", "settlement_type")
DROP_SEED_AXES = ("life_stage", "settlement")


def drop_seed_fields(p):
    """Remove the seeded fields that are not part of the released schema (in place)."""
    bg = p.get("background") or {}
    for k in DROP_BACKGROUND:
        bg.pop(k, None)
    axes = (p.get("gen_meta") or {}).get("seed_axes") or {}
    for k in DROP_SEED_AXES:
        axes.pop(k, None)
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True, help="base-grid bank (after rebalance_emoji)")
    ap.add_argument("--part", action="append", default=[], help="diversity_filter.py output; repeat, in order")
    ap.add_argument("--dropped", action="append", default=[], help="diversity_filter.py --dropped files (report only)")
    ap.add_argument("--out", required=True, help="assembled bank (JSONL)")
    ap.add_argument("--report", default=None, help="JSON report (default: <out without .jsonl>_report.json)")
    a = ap.parse_args()
    report_path = a.report or os.path.splitext(a.out)[0] + "_report.json"

    C = collections.defaultdict(collections.Counter)
    per_part = collections.OrderedDict()
    seen, clashes = set(), collections.Counter()
    with open(a.out, "w", encoding="utf-8") as fo:
        for name, path in [("base", a.base)] + [(f"part{i + 1}", p) for i, p in enumerate(a.part)]:
            n, part_ids = 0, set()
            for line in open(path, encoding="utf-8"):
                if not line.strip():
                    continue
                p = json.loads(line)
                if p["id"] in part_ids:
                    continue
                part_ids.add(p["id"])
                if p["id"] in seen:
                    clashes[name] += 1
                    continue
                seen.add(p["id"])
                fo.write(json.dumps(drop_seed_fields(p), ensure_ascii=False) + "\n")
                n += 1
                b = p["background"]
                C["block"][target_block(b.get("region"), b.get("country"))] += 1
                C["region"][b.get("region")] += 1
                C["country"][b.get("country")] += 1
                C["location"][f"{b.get('country')} / {b.get('sub_region')}"] += 1
                C["main_language"][b.get("main_language")] += 1
                C["generator"][p.get("generator_model")] += 1
                C[f"generator/{name}"][p.get("generator_model")] += 1
            per_part[name] = {"path": path, "profiles": n}

    drops = collections.Counter()
    for path in a.dropped:
        for line in open(path, encoding="utf-8"):
            if line.strip():
                drops[(json.loads(line).get("diversity_drop") or {}).get("reason")] += 1

    total = sum(v["profiles"] for v in per_part.values())
    rep = {"total": total, "parts": per_part, "id_clashes": dict(clashes), "diversity_drops": dict(drops),
           "n_countries": len(C["country"]), "n_locations": len(C["location"]),
           "n_main_language_strings": len(C["main_language"]),
           "share_block_pct": {k: round(100 * v / max(1, total), 2) for k, v in C["block"].most_common()}}
    rep.update({k: dict(v.most_common()) for k, v in C.items()})
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1, ensure_ascii=False)
    print(json.dumps({k: rep[k] for k in ("total", "parts", "id_clashes", "diversity_drops", "n_countries",
                                         "n_locations", "generator")}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
