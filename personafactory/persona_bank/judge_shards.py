#!/usr/bin/env python3
"""Split generated profiles into judge input shards, and merge the judge outputs back.

  split  read every generator file <raw_dir>/persona_bank_*.jsonl (sharded or not; *.attempts.jsonl logs
         are skipped), keep one row per id, write them sorted by id to --raw_all and into --nsh judge input
         files <judge_in>/shard_XXXX.jsonl (row -> int(sha1(id)[:8], 16) % nsh). Each judge client then reads
         only its own small file. Deterministic: rerunning gives the same split.
  merge  read the judge outputs <judge_out>/val_*.jsonl (written by validate_personas.py, one per input
         shard), keep one row per id (the last one read) and write them sorted by id to --out.

Usage:
    python -m personafactory.persona_bank.judge_shards split --raw_dir ./data/persona_bank/extended/raw \\
        --raw_all ./data/persona_bank/extended/raw_all.jsonl --judge_in ./data/persona_bank/extended/judge_in --nsh 2304
    # judge: validate_personas --input judge_in/shard_XXXX.jsonl --output judge_out/val_XXXX.jsonl (one per shard)
    python -m personafactory.persona_bank.judge_shards merge --judge_out ./data/persona_bank/extended/judge_out \\
        --out ./data/persona_bank/extended/validated_all.jsonl
"""
import argparse
import glob
import hashlib
import json
import os


def _read_by_id(files):
    rows = {}
    for f in files:
        for line in open(f, errors="ignore"):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            rows[r["id"]] = line if line.endswith("\n") else line + "\n"
    return rows


def split(a):
    files = [f for f in sorted(glob.glob(os.path.join(a.raw_dir, "persona_bank_*.jsonl")))
             if not f.endswith(".attempts.jsonl")]
    rows = _read_by_id(files)
    os.makedirs(a.judge_in, exist_ok=True)
    outs = [open(os.path.join(a.judge_in, f"shard_{i:04d}.jsonl"), "w") for i in range(a.nsh)]
    raw_all = a.raw_all or os.path.join(a.raw_dir, "..", "raw_all.jsonl")
    with open(raw_all, "w") as fa:
        for k in sorted(rows):
            fa.write(rows[k])
            outs[int(hashlib.sha1(k.encode()).hexdigest()[:8], 16) % a.nsh].write(rows[k])
    for o in outs:
        o.close()
    print(f"{len(files)} generator files, {len(rows)} profiles -> {raw_all} and {a.nsh} judge shards in {a.judge_in}")


def merge(a):
    files = sorted(glob.glob(os.path.join(a.judge_out, "val_*.jsonl")))
    rows = _read_by_id(files)
    with open(a.out, "w") as fh:
        for k in sorted(rows):
            fh.write(rows[k])
    print(f"{len(files)} judge files, {len(rows)} judged profiles -> {a.out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="stage", required=True)
    s = sub.add_parser("split", help="merge generator files and split them into judge input shards")
    s.add_argument("--raw_dir", required=True, help="generate_bank.py --output_dir")
    s.add_argument("--judge_in", required=True, help="output directory for shard_XXXX.jsonl")
    s.add_argument("--nsh", type=int, required=True, help="number of judge shards")
    s.add_argument("--raw_all", default=None, help="merged raw profiles (default: <raw_dir>/../raw_all.jsonl)")
    m = sub.add_parser("merge", help="merge judge outputs val_*.jsonl into one file")
    m.add_argument("--judge_out", required=True, help="directory with val_*.jsonl")
    m.add_argument("--out", required=True)
    a = ap.parse_args()
    split(a) if a.stage == "split" else merge(a)


if __name__ == "__main__":
    main()
