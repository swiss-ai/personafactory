#!/usr/bin/env python3
"""Share of released user turns left unrewritten, by detected language (top 15 languages by turns), and the
share guarded for verbatim/script/language reasons. Reads the per-turn details from the assistant
regeneration inputs. Writes <release-dir>/guards_by_language.json.

  python -m personafactory.release.stats.guard_by_language --release-dir ./release_out --regen-input ./outputs/assistant_regen/input
"""
import argparse, collections, glob, json, os

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--release-dir', required=True)
ap.add_argument('--regen-input', required=True, help='directory with the assistant regeneration input shards')
ap.add_argument('--out', default=None, help='default: <release-dir>/guards_by_language.json')
args = ap.parse_args()
lang = {}
for fp in glob.glob(os.path.join(args.release_dir, 'data', '*.jsonl')):
    for l in open(fp, encoding='utf-8'):
        r = json.loads(l)
        lang[r['id']] = r['text_language']
c = collections.defaultdict(collections.Counter)
for fp in glob.glob(os.path.join(args.regen_input, '*.jsonl')):
    for l in open(fp, encoding='utf-8'):
        r = json.loads(l)
        if r['id'] not in lang:
            continue
        for f in r['fixed']:
            k = lang[r['id']]
            c[k]['turns'] += 1
            if not f['persona_applied'] or f['persona_skip_reason'] == 'no_adaptation_made':
                c[k]['guarded'] += 1
                if 'verbatim' in str(f['persona_skip_reason']) or 'script' in str(f['persona_skip_reason']) or 'language' in str(f['persona_skip_reason']):
                    c[k]['verbatim_or_script'] += 1
out = {k: {'turns': v['turns'], 'guarded_pct': round(100 * v['guarded'] / v['turns'], 2), 'verbatim_or_script_pct': round(100 * v['verbatim_or_script'] / v['turns'], 2)}
       for k, v in sorted(c.items(), key=lambda kv: -kv[1]['turns'])[:15]}
json.dump(out, open(args.out or os.path.join(args.release_dir, 'guards_by_language.json'), 'w'), indent=1)
print(json.dumps(out, indent=1))
