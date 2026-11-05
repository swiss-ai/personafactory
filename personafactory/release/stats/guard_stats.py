#!/usr/bin/env python3
"""Why released user turns were left unrewritten: per-turn persona skip reasons, grouped into the paper's
guard classes (truncation, strict format, unchanged, literal integrity, language or script).

Reads the per-turn details (`fixed`: persona_applied, persona_skip_reason) from the assistant regeneration
inputs, restricted to the released conversations. Writes <release-dir>/guards.json.

  python -m personafactory.release.stats.guard_stats --release-dir ./release_out --regen-input ./outputs/assistant_regen/input
"""
import argparse, collections, glob, json, os

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--release-dir', required=True)
ap.add_argument('--regen-input', required=True, help='directory with the assistant regeneration input shards')
ap.add_argument('--out', default=None, help='default: <release-dir>/guards.json')
args = ap.parse_args()
keep = set()
for fp in glob.glob(os.path.join(args.release_dir, 'data', '*.jsonl')):
    for l in open(fp, encoding='utf-8'):
        keep.add(json.loads(l)['id'])
def cls(reason):
    r = str(reason)
    if 'truncated' in r: return 'truncation'
    if 'verbatim' in r or 'strict_format' in r: return 'strict_format'
    if 'no_adaptation' in r or 'unchanged' in r: return 'unchanged'
    if 'literal_integrity' in r: return 'literal_integrity'
    if 'language' in r or 'script' in r: return 'language_or_script'
    return 'other'
c = collections.Counter()
n = 0
for fp in glob.glob(os.path.join(args.regen_input, '*.jsonl')):
    for l in open(fp, encoding='utf-8'):
        r = json.loads(l)
        if r['id'] not in keep:
            continue
        for f in r['fixed']:
            n += 1
            if not f['persona_applied'] or f['persona_skip_reason'] == 'no_adaptation_made':
                c[cls(f['persona_skip_reason'])] += 1
g = sum(c.values())
out = {'user_turns': n, 'guarded': g, 'guarded_pct': round(100 * g / n, 2),
       'classes': {k: {'n': v, 'pct_of_guarded': round(100 * v / g, 1)} for k, v in c.most_common()}}
json.dump(out, open(args.out or os.path.join(args.release_dir, 'guards.json'), 'w'), indent=1)
print(json.dumps(out, indent=1))
