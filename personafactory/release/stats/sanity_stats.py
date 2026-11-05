#!/usr/bin/env python3
"""Sanity-gate pass rates of the assistant regeneration over the release conversations.

Conversation-level pass rates by responder, seed source and mode, plus the turn-level rate. Reads the
regeneration inputs (one line per conversation with id, responder, source_name, mode) and the cleaned
regeneration outputs (id, status, sanity_verdicts). Writes <release-dir>/assistant_sanity.json.

  python -m personafactory.release.stats.sanity_stats --release-dir ./release_out \
      --regen-input ./outputs/assistant_regen/input --regen-dir ./outputs/assistant_regen_clean
"""
import argparse, collections, glob, json, os

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--release-dir', required=True)
ap.add_argument('--regen-input', required=True, help='directory with the assistant regeneration input shards')
ap.add_argument('--regen-dir', required=True, help='directory with the cleaned assistant regeneration outputs')
ap.add_argument('--out', default=None, help='default: <release-dir>/assistant_sanity.json')
args = ap.parse_args()
meta = {}
for fp in glob.glob(os.path.join(args.regen_input, '*.jsonl')):
    for l in open(fp, encoding='utf-8'):
        r = json.loads(l)
        meta[r['id']] = (r['responder'], r['source_name'], r['mode'])
c = collections.defaultdict(lambda: [0, 0])
turns = [0, 0]
for fp in glob.glob(os.path.join(args.regen_dir, '*.jsonl')):
    for l in open(fp, encoding='utf-8'):
        x = json.loads(l)
        m = meta.get(x['id'])
        if not m:
            continue
        ok = x.get('status') == 'pass'
        for k in ('all', 'responder/' + m[0], 'source/' + m[1], 'mode/' + m[2]):
            c[k][0] += 1
            c[k][1] += ok
        for v in x.get('sanity_verdicts') or []:
            turns[0] += 1
            turns[1] += v == 'pass'
out = {k: {'total': t, 'pass': p, 'pct': round(100 * p / t, 2)} for k, (t, p) in sorted(c.items())}
out['turn_level'] = {'total': turns[0], 'pass': turns[1], 'pct': round(100 * turns[1] / turns[0], 2)}
json.dump(out, open(args.out or os.path.join(args.release_dir, 'assistant_sanity.json'), 'w'), indent=1)
print(json.dumps(out, indent=1))
