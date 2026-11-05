#!/usr/bin/env python3
"""Strip emoji from user turns of personas whose bank entry says emoji_use none.

Emoji already present in the record's source_text are kept, since they belong to the real task. Assistant
turns are untouched. Shards are rewritten in place; keep a copy of the data if you need the unscrubbed
version. Prints the scrub counts.

  python -m personafactory.release.scrub_emoji --bank ./release_out/persona_bank.jsonl --data "./release_out/data/*.jsonl"
"""
import argparse, collections, glob, json
from multiprocessing import Pool

from personafactory.release.emoji_utils import EMOJI, strip_emoji, tier

NONE_IDS = None


def init(bank):
    global NONE_IDS
    NONE_IDS = set()
    for line in open(bank, encoding='utf-8'):
        p = json.loads(line)
        if tier(((p.get('style') or {}).get('chatting_style_structured') or {}).get('emoji_use')) == 'none':
            NONE_IDS.add(p['id'])


def shard(path):
    st = collections.Counter()
    out = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            st['records'] += 1
            if r.get('persona_id') in NONE_IDS:
                keep = set(m.group(0) for m in EMOJI.finditer(r.get('source_text') or ''))
                touched = False
                for m in r.get('conversation') or []:
                    if m.get('role') != 'user' or not m.get('content'):
                        continue
                    new = strip_emoji(m['content'], keep)
                    if new != m['content']:
                        if not new.strip():
                            st['emoji_only_turn_kept'] += 1
                            continue
                        m['content'] = new
                        st['turns_scrubbed'] += 1
                        touched = True
                st['records_scrubbed'] += touched
            out.append(json.dumps(r, ensure_ascii=False))
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')
    return st


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--bank', required=True, help='persona bank JSONL (after the emoji rebalancing)')
    ap.add_argument('--data', required=True, help='glob of release data shards')
    ap.add_argument('--workers', type=int, default=50)
    args = ap.parse_args()
    total = collections.Counter()
    with Pool(args.workers, initializer=init, initargs=(args.bank,)) as pool:
        for st in pool.imap_unordered(shard, sorted(glob.glob(args.data))):
            total.update(st)
    print(json.dumps(dict(total), indent=1))


if __name__ == '__main__':
    main()
