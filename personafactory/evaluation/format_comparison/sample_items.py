#!/usr/bin/env python
"""Sample the paired evaluation set for the persona-format comparison from a pipeline output corpus.

One item = (seed prompt at turn 0, the persona that was matched to it). We take the
matching from the corpus so the persona/conversation pairing is the pipeline's own, but
we deliberately do NOT reuse the corpus rewrite: every condition, PersonaFactory included, is
regenerated in run_conditions.py. Strata: (metadata.persona_set, seed source).

Sampling must be independent of the corpus outcome. Filtering on metadata.sanity_pass would
condition on the very quantity the experiment measures and hand PersonaFactory a selection
advantage, so `--require-pass` exists only to demonstrate the bias, never for the real run.

Inputs:  --corpus pipeline output JSONL (records with metadata.persona and metadata.turns_detail)
Outputs: --out items JSONL (item_id, stratum, seed_prompt, persona_id, persona, corpus_* slicing fields)
Run:     python -m personafactory.evaluation.format_comparison.sample_items --corpus ./outputs/pipeline_output.jsonl \
             --n 800 --out ./outputs/format_comparison/items.jsonl
"""
from __future__ import annotations

import argparse
import os
import json
import random
from collections import defaultdict


def stratum(rec: dict) -> tuple:
    md = rec.get("metadata") or {}
    src = "nemotron" if str(rec.get("id", "")).startswith("nemotron") else "ultrachat"
    return (md.get("persona_set") or "unknown", src)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--n", type=int, default=800)
    ap.add_argument("--seed", type=int, default=20260901)
    ap.add_argument("--out", default="./outputs/format_comparison/items.jsonl")
    ap.add_argument("--require-pass", action="store_true",
                    help="BIAS CHECK ONLY: restrict to sanity_pass records.")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)

    rng = random.Random(args.seed)
    # Reservoir sample per stratum in a single pass over the corpus file.
    reservoirs: dict[tuple, list] = defaultdict(list)
    counts: dict[tuple, int] = defaultdict(int)
    per_stratum = args.n  # oversample; we trim to exact quotas after the pass

    kept = skipped = 0
    with open(args.corpus) as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            md = rec.get("metadata") or {}
            persona = md.get("persona")
            turns = md.get("turns_detail") or []
            if not persona or not turns:
                skipped += 1
                continue
            if args.require_pass and not md.get("sanity_pass"):
                skipped += 1
                continue
            t0 = turns[0]
            seed_prompt = t0.get("user_message_original")
            if not seed_prompt or not str(seed_prompt).strip():
                skipped += 1
                continue

            st = stratum(rec)
            counts[st] += 1
            item = {
                "item_id": rec.get("id"),
                "stratum": list(st),
                "seed_prompt": seed_prompt,
                "persona_id": persona.get("id"),
                "persona": persona,
                # carried for slicing only; never used to select
                "corpus_sanity_pass": md.get("sanity_pass"),
                "corpus_match_tier": md.get("persona_match_tier"),
                "corpus_responder": md.get("responder"),
            }
            res = reservoirs[st]
            if len(res) < per_stratum:
                res.append(item)
            else:
                j = rng.randrange(counts[st])
                if j < per_stratum:
                    res[j] = item
            kept += 1

    # Proportional quotas, then a deterministic trim to exactly n.
    total = sum(counts.values())
    quotas = {st: max(1, round(args.n * counts[st] / total)) for st in counts}
    items: list[dict] = []
    for st, res in reservoirs.items():
        rng.shuffle(res)
        items.extend(res[: quotas[st]])
    rng.shuffle(items)
    items = items[: args.n]

    with open(args.out, "w") as fh:
        for it in items:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")

    print(f"scanned {kept + skipped} records, eligible {kept}, skipped {skipped}")
    print(f"wrote {len(items)} items -> {args.out}")
    by = defaultdict(int)
    for it in items:
        by[tuple(it["stratum"])] += 1
    for st, c in sorted(by.items()):
        print(f"  {st[0]:14s} {st[1]:10s} {c:5d}   (pool {counts[st]})")
    npass = sum(1 for it in items if it["corpus_sanity_pass"])
    print(f"corpus sanity_pass among sampled: {npass}/{len(items)} "
          f"({100*npass/max(1,len(items)):.1f}%), NOT used for selection")
    uniq = len({it['persona_id'] for it in items})
    print(f"distinct personas: {uniq}")


if __name__ == "__main__":
    main()
