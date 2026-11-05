#!/usr/bin/env python3
"""Seed pairs for regenerating seed-pool conversations end to end with Gemma (user side and assistant side), keeping
their conversation ids, for low-resource languages answered by Ministral.

  --source removed  conversations removed by apply_lowres_filter only because Ministral was the responder
                    (reason drop_ministral), both settings; the regenerations are added back by
                    finalize_lowres_regen --mode append.
  --source kept     cross-lingual conversations still in the release with a Ministral responder in a low-resource
                    language (the Uzbek and Nepali ones the filter keeps); the regenerations replace them in place
                    (finalize_lowres_regen --mode replace).
The conversation id is run_augmentation.key_of(pair_key, mode), so the pair keys are recovered from the assignment
files. Writes <run>/pairs/{mode}-uNN.jsonl (--units files, round robin, for parallel jobs), <run>/select_{mode}.txt
(pair keys for run_augmentation --select) and <run>/ids.txt (id <TAB> language).

  python -m personafactory.postprocess.lowres_regen_prep --source removed --release-dir ./release_merged \\
      --seeds-dir ./data/seeds/shards --assign-dir ./outputs/assign_seeds --run ./outputs/regen_lowres --units 4
"""
import argparse, glob, json, os

from personafactory.augmentation.run_augmentation import key_of
from personafactory.postprocess.lowres_quality import LOWRES, lang_of, release_lines


def target_ids(a):
    ids = {}
    if a.source == 'removed':
        for l in open(os.path.join(a.release_dir, 'lowres_removed.jsonl'), encoding='utf-8'):
            x = json.loads(l)
            if x['reason'] == 'drop_ministral' and x['release_part'] == a.part:
                ids[x['id']] = x['lang']
    else:
        for l in release_lines(a.release_dir):
            if '"ministral"' not in l:
                continue
            r = json.loads(l)
            if r.get('release_part') == a.part and r.get('language_mode') == 'multilingual' \
                    and r.get('responder') == 'ministral' and lang_of(r) in LOWRES:
                ids[r['id']] = lang_of(r)
    return ids


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', choices=('removed', 'kept'), required=True)
    ap.add_argument('--release-dir', required=True)
    ap.add_argument('--seeds-dir', required=True, help='seed-pool shards (prepare_seeds)')
    ap.add_argument('--assign-dir', required=True, help='seed-pool assignments (select_personas --seeds-dir)')
    ap.add_argument('--run', required=True, help='output run directory of the regeneration')
    ap.add_argument('--units', type=int, default=4)
    ap.add_argument('--part', default='seeds', help='release_part label of the seed-pool records')
    a = ap.parse_args()
    ids = target_ids(a)
    modes = ('free', 'multilingual') if a.source == 'removed' else ('multilingual',)
    os.makedirs(os.path.join(a.run, 'pairs'), exist_ok=True)
    open(os.path.join(a.run, 'ids.txt'), 'w').write(''.join(f'{i}\t{L}\n' for i, L in sorted(ids.items())))
    for mode in modes:
        sel = set()
        for l in open(os.path.join(a.assign_dir, f'{mode}.jsonl'), encoding='utf-8'):
            r = json.loads(l)
            if r['responder'] == 'ministral' and key_of(r['pair_key'], mode, 'seeds') in ids:
                sel.add(r['pair_key'])
        open(os.path.join(a.run, f'select_{mode}.txt'), 'w').write(''.join(k + '\n' for k in sorted(sel)))
        outs = [open(os.path.join(a.run, 'pairs', f'{mode}-u{u:02d}.jsonl'), 'w', encoding='utf-8') for u in range(a.units)]
        n = 0
        for fp in sorted(glob.glob(os.path.join(a.seeds_dir, f'{mode}-*.jsonl'))):
            for l in open(fp, encoding='utf-8'):
                if l.strip() and json.loads(l)['pair_key'] in sel:
                    outs[n % a.units].write(l if l.endswith('\n') else l + '\n')
                    n += 1
        for f in outs:
            f.close()
        print(mode, 'selected', len(sel), 'pairs written', n)
    print('target ids', len(ids))


if __name__ == '__main__':
    main()
