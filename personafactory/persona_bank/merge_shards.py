#!/usr/bin/env python3
"""Merge generator shards into per-model banks and one combined raw bank (model-count-agnostic).

Globs every ``persona_bank_<model>.shard*.jsonl`` under --data-dir, merges each model's shards
(sorted file order) into ``persona_bank_<model>.jsonl``, then concatenates all models (sorted by
model name) into ``persona_bank_all.jsonl``. A model with only a standalone (non-sharded)
``persona_bank_<model>.jsonl`` is included as-is. Every persona keeps its ``generator_model``
key, so no provenance is lost by flattening. Duplicates are dropped by ``id`` by default. The per-call logs
``*.attempts.jsonl`` written by generate_bank.py are skipped.

Example:
    python -m personafactory.persona_bank.merge_shards --data-dir ./data/persona_bank/base
"""
import argparse
import collections
import glob
import json
import os

PREFIX = "persona_bank_"
COMBINED = "all"


def clean_name(fname: str) -> str:
    """'persona_bank_<clean>.shardNNofMM.jsonl' or 'persona_bank_<clean>.jsonl' -> '<clean>'."""
    base = os.path.basename(fname)
    rest = base[len(PREFIX):]
    return rest.split(".shard", 1)[0].rsplit(".jsonl", 1)[0]


def dumpline(r) -> str:
    """JSON line, readable (ensure_ascii=False) but resilient to broken lone
    surrogates in model output (fall back to escaped form for those records)."""
    s = json.dumps(r, ensure_ascii=False)
    try:
        s.encode("utf-8")
        return s + "\n"
    except UnicodeEncodeError:
        return json.dumps(r, ensure_ascii=True) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=os.path.join(os.environ.get("PF_DATA_DIR", "./data"), "persona_bank"),
                    help="Directory holding the shard/per-model files.")
    ap.add_argument("--out", default=None,
                    help="Combined output path (default: persona_bank_all.jsonl in data-dir).")
    ap.add_argument("--dedup", choices=["id", "character_description", "none"], default="id",
                    help="Drop duplicate personas by this key (default: id).")
    ap.add_argument("--no-per-model", action="store_true",
                    help="Do not (re)write the per-model merged files, only the combined bank.")
    args = ap.parse_args()

    data_dir = os.path.abspath(args.data_dir)
    out_path = os.path.abspath(args.out) if args.out else os.path.join(
        data_dir, f"{PREFIX}{COMBINED}.jsonl")
    out_base = os.path.basename(out_path)

    # 1) group shard files by model
    by_model = collections.defaultdict(list)
    for f in glob.glob(os.path.join(data_dir, f"{PREFIX}*.shard*.jsonl")):
        if f.endswith(".attempts.jsonl"):
            continue
        c = clean_name(f)
        if not c.startswith(COMBINED):          # skip validated shards of the combined bank
            by_model[c].append(f)

    # 2) standalone per-model files (non-sharded runs); skip the combined file & shards
    standalone = {}
    for f in glob.glob(os.path.join(data_dir, f"{PREFIX}*.jsonl")):
        if os.path.basename(f) == out_base or ".shard" in os.path.basename(f) or f.endswith(".attempts.jsonl"):
            continue
        c = clean_name(f)
        if not c.startswith(COMBINED):
            standalone[c] = f

    models = sorted(set(by_model) | set(standalone))
    if not models:
        print(f"No shard or per-model files under {data_dir}.")
        return

    def key(rec):
        if args.dedup == "id":
            return rec.get("id")
        if args.dedup == "character_description":
            return (rec.get("character_description") or "").strip().lower()
        return None

    combined, seen_all = [], set()
    per_counts, gen_counter = {}, collections.Counter()
    cross_dupes = 0

    for c in models:
        srcs = sorted(by_model.get(c, [])) or [standalone[c]]
        recs, seen = [], set()
        for src in srcs:
            with open(src, errors="ignore") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    k = key(rec)
                    if args.dedup != "none" and k is not None and k in seen:
                        continue
                    if k is not None:
                        seen.add(k)
                    recs.append(rec)
        per_counts[c] = len(recs)

        # rewrite the per-model merged file from its shards (only when sharded)
        if not args.no_per_model and by_model.get(c):
            with open(os.path.join(data_dir, f"{PREFIX}{c}.jsonl"), "w") as g:
                for r in recs:
                    g.write(dumpline(r))

        for r in recs:
            k = key(r)
            if args.dedup != "none" and k is not None and k in seen_all:
                cross_dupes += 1
                continue
            if k is not None:
                seen_all.add(k)
            combined.append(r)
            gen_counter[r.get("generator_model", "?")] += 1

    with open(out_path, "w") as g:
        for r in combined:
            g.write(dumpline(r))

    print(f"Merged {len(models)} model(s) from {data_dir} (dedup={args.dedup})")
    for c in models:
        src = f"{len(by_model[c])} shards" if by_model.get(c) else "standalone"
        print(f"  {c:<36}{per_counts[c]:>7}   ({src})")
    tail = f"   ({cross_dupes} cross-model dupes dropped)" if cross_dupes else ""
    print(f"  {'-> ' + out_base:<36}{len(combined):>7}{tail}")
    print("\n  generator_model provenance in combined bank:")
    for g_, n in gen_counter.most_common():
        print(f"    {g_:<42}{n:>7}")


if __name__ == "__main__":
    main()
