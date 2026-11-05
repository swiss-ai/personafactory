#!/usr/bin/env python3
"""Merge the judged shards and write the clean (keep-only) bank.

Concatenates ``<validated>.shard*.jsonl`` (as written by validate_personas.py with --shard_count)
in sorted file-name order into ``<validated>.jsonl``, then writes ``<clean>`` with every line whose
``validation.verdict`` is ``keep``. Lines are copied byte-for-byte, so the clean bank keeps the
``validation`` block (scores and repair records) for auditing; rejected and unscored profiles are
dropped.

Example:
    python -m personafactory.persona_bank.finalize_bank \
        --validated ./data/persona_bank/base/persona_bank_all.validated.jsonl \
        --clean ./data/persona_bank/base/persona_bank_all.clean.jsonl
"""
import argparse
import collections
import glob
import json
import os


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--validated", required=True,
                    help="Merged validated bank; its shards are <stem>.shard*<ext> next to it.")
    ap.add_argument("--clean", required=True, help="Output keep-only bank.")
    ap.add_argument("--no-merge", action="store_true",
                    help="--validated already exists as one file (unsharded run); skip merging.")
    args = ap.parse_args()

    if not args.no_merge:
        stem, ext = os.path.splitext(args.validated)
        shards = sorted(glob.glob(f"{stem}.shard*{ext}"))
        if not shards:
            raise SystemExit(f"no shards matching {stem}.shard*{ext}")
        with open(args.validated, "w") as out:
            for s in shards:
                with open(s) as fh:
                    for line in fh:
                        if line.strip():
                            out.write(line if line.endswith("\n") else line + "\n")
        print(f"merged {len(shards)} shards -> {args.validated}")

    verdicts = collections.Counter()
    with open(args.validated) as fh, open(args.clean, "w") as out:
        for line in fh:
            if not line.strip():
                continue
            v = (json.loads(line).get("validation") or {}).get("verdict", "unscored")
            verdicts[v] += 1
            if v == "keep":
                out.write(line)
    total = sum(verdicts.values())
    print(f"{total} judged: " + ", ".join(f"{k}={n}" for k, n in verdicts.most_common()))
    print(f"kept {verdicts['keep']} ({100 * verdicts['keep'] / max(total, 1):.1f}%) -> {args.clean}")


if __name__ == "__main__":
    main()
