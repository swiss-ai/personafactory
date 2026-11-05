#!/usr/bin/env python3
"""Replace lone UTF-16 surrogates (broken emoji from the generators) with U+FFFD in JSONL files.

A few generated profiles carry lone surrogates in their strings; they break the embedding tokenizer of
diversity_filter.py and UTF-8 output. Run this on the merged judge output before the diversity filter.
Rows without an escaped surrogate are copied byte-for-byte; the others are re-serialized.

Usage (in place):
    python -m personafactory.persona_bank.strip_surrogates ./data/persona_bank/extended/validated_all.jsonl
"""
import argparse
import json
import os
import re

SUR = re.compile(r"[\ud800-\udfff]")


def clean(x):
    if isinstance(x, str):
        return SUR.sub("�", x)
    if isinstance(x, list):
        return [clean(v) for v in x]
    if isinstance(x, dict):
        return {clean(k): clean(v) for k, v in x.items()}
    return x


def strip_file(path, out=None):
    """Clean `path` into `out` (default: in place). Returns (rows, rows changed)."""
    dst = out or path
    tmp, n, fixed = dst + ".tmp", 0, 0
    with open(path) as fi, open(tmp, "w") as fo:
        for line in fi:
            if not line.strip():
                continue
            n += 1
            if "\\ud" in line or "\\uD" in line:
                p = json.loads(line)
                q = clean(p)
                if q != p:
                    fixed += 1
                    line = json.dumps(q, ensure_ascii=False) + "\n"
            fo.write(line)
    os.replace(tmp, dst)
    return n, fixed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="JSONL files, cleaned in place unless --out is given.")
    ap.add_argument("--out", default=None, help="Output path (only with a single input file).")
    a = ap.parse_args()
    if a.out and len(a.files) != 1:
        ap.error("--out needs exactly one input file")
    for path in a.files:
        n, fixed = strip_file(path, a.out)
        print(f"{path}: {n} rows, {fixed} cleaned")


if __name__ == "__main__":
    main()
