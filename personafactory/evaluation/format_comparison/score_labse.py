#!/usr/bin/env python
"""LaBSE semantic-similarity pass for the persona-format comparison (GPU job).

Uses the same LaBSE evaluator definition as the corpus-scale metrics. Merges `labse_similarity` (seed prompt vs
rewrite) and `asst_labse_dist_from_none` (1 - similarity of each condition's reply to the no-persona reply for
the same item) into metrics.jsonl in place.

Inputs:  --generations (run_conditions.py output), --metrics (score_conditions.py output)
Outputs: metrics.jsonl updated in place; similarity caches (--cache, --cache.drift)
Run:     python -m personafactory.evaluation.format_comparison.score_labse --generations ./outputs/format_comparison/generations.jsonl \
             --metrics ./outputs/format_comparison/metrics.jsonl --cache ./outputs/format_comparison/labse_sims.npy
"""
from __future__ import annotations

import argparse, json, os

from personafactory.evaluation.format_comparison.chat_metrics import MultilingualEmbeddingEvaluator


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--generations", default="./outputs/format_comparison/generations.jsonl")
    ap.add_argument("--metrics", default="./outputs/format_comparison/metrics.jsonl")
    ap.add_argument("--cache", default="./outputs/format_comparison/labse_sims.npy")
    ap.add_argument("--model", default=os.environ.get("PF_LABSE_MODEL", "sentence-transformers/LaBSE"))
    ap.add_argument("--batch-size", type=int, default=512)
    args = ap.parse_args()

    gens = [json.loads(l) for l in open(args.generations)]
    gens = [g for g in gens if g.get("rewrite")]
    keys = [(g["item_id"], g["condition"]) for g in gens]

    ev = MultilingualEmbeddingEvaluator(model_name=args.model, batch_size=args.batch_size)
    # rewrite fidelity: seed prompt vs persona rewrite
    sims = ev.compute_similarity_batch([g["seed_prompt"] for g in gens],
                                       [g["rewrite"] for g in gens],
                                       cache_file=args.cache)
    lookup = dict(zip(keys, sims))

    # assistant drift: each condition's reply vs the no-persona reply for the same item
    base = {g["item_id"]: g.get("assistant", "") for g in gens if g["condition"] == "none"}
    pairs = [(base.get(g["item_id"], ""), g.get("assistant", "")) for g in gens]
    ok = [i for i, (a, b) in enumerate(pairs) if a and b]
    drift = {}
    if ok:
        ds = ev.compute_similarity_batch([pairs[i][0] for i in ok],
                                         [pairs[i][1] for i in ok],
                                         cache_file=args.cache + ".drift")
        drift = {keys[i]: d for i, d in zip(ok, ds)}

    n = 0
    tmp = args.metrics + ".tmp"
    with open(args.metrics) as fh, open(tmp, "w") as out:
        for line in fh:
            m = json.loads(line)
            k = (m.get("item_id"), m.get("condition"))
            if k in lookup:
                m["labse_similarity"] = lookup[k]
                n += 1
            if k in drift:
                # 1 - similarity: how far the persona moved the assistant's reply
                m["asst_labse_dist_from_none"] = 1.0 - drift[k]
            out.write(json.dumps(m, ensure_ascii=False) + "\n")
    os.replace(tmp, args.metrics)
    print(f"merged LaBSE into {n} rows -> {args.metrics}")


if __name__ == "__main__":
    main()
