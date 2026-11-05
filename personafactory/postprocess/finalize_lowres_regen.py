#!/usr/bin/env python3
"""Bring the Gemma regenerations of postprocess.lowres_regen_prep into the release directory.

Input: <run>/final/data/*.jsonl (augmentation.build_corpus --stage user and --stage final on the regeneration run).
Each regenerated record keeps the id of the Ministral conversation it stands for and goes through the same automatic
checks as apply_lowres_filter (repetition > 0.3, cross-lingual with > 50% English user turns, the language rules);
records that fail keep nothing new. Survivors get regenerated = 'lowres_gemma'.

  --mode append   (after --source removed) a survivor is added to <release>/data/NNNN.jsonl (shard md5(id) % 256) if
                  its id is in lowres_removed.jsonl and not already present; counts -> <release>/lowres_regen_append.json.
  --mode replace  (after --source kept) a survivor replaces the record with the same id in place (tmp + rename);
                  otherwise the Ministral original stays. Replaced originals -> <release>/lowres_regen_replaced.jsonl,
                  counts -> <release>/lowres_regen_replace.json.

  python -m personafactory.postprocess.finalize_lowres_regen --mode append --release-dir ./release_merged --run ./outputs/regen_lowres
"""
import argparse, collections, glob, json, os
from multiprocessing import Pool

from personafactory.common import lid
from personafactory.postprocess import apply_lowres_filter as F
from personafactory.postprocess import lowres_quality as Q
from personafactory.release.merge_release import shard_of, to_release

PART = 'seeds'


def check(line):
    r = json.loads(line)
    r['release_part'] = PART
    x = Q.analyse(json.dumps(r, ensure_ascii=False))
    if x is None:
        return r, 'drop_not_lowres', None
    return r, F.reason(x), x['lang']


def _init(lid_model, part):
    global PART
    PART = part
    lid.init(lid_model)


def regenerated(a):
    lines = [l for fp in sorted(glob.glob(os.path.join(a.run, 'final', 'data', '*.jsonl'))) for l in open(fp, encoding='utf-8')]
    with Pool(a.workers, initializer=_init, initargs=(a.lid_model, a.part)) as pool:
        yield from pool.imap(check, lines, chunksize=16)


def append(a):
    rel = a.release_dir
    removed = {json.loads(l)['id'] for l in open(os.path.join(rel, 'lowres_removed.jsonl'), encoding='utf-8')}
    present = {json.loads(l)['id'] for l in Q.release_lines(rel)}
    st, by_lang, sinks = collections.Counter(), collections.defaultdict(collections.Counter), {}
    for r, why, L in regenerated(a):
        st['in'] += 1
        if r['id'] not in removed:
            st['drop_not_a_removed_id'] += 1
            continue
        if r['id'] in present:
            st['drop_already_present'] += 1
            continue
        if why:
            st[why] += 1
            by_lang[L][why] += 1
            continue
        out = to_release(r)
        out['regenerated'] = 'lowres_gemma'
        i = shard_of(r['id'])
        if i not in sinks:
            sinks[i] = open(os.path.join(rel, 'data', f'{i:04d}.jsonl'), 'a', encoding='utf-8')
        sinks[i].write(json.dumps(out, ensure_ascii=False) + '\n')
        present.add(r['id'])
        st['added'] += 1
        by_lang[L]['added'] += 1
    for f in sinks.values():
        f.close()
    res = {'counts': dict(st), 'by_language': {L: dict(c) for L, c in sorted(by_lang.items(), key=lambda kv: str(kv[0]))},
           'release_total_after': len(present)}
    json.dump(res, open(os.path.join(rel, 'lowres_regen_append.json'), 'w'), indent=1, ensure_ascii=False)
    print(json.dumps(res['counts'], indent=1), 'release total', len(present))


def replace(a):
    rel = a.release_dir
    want = dict(l.rstrip('\n').split('\t') for l in open(os.path.join(a.run, 'ids.txt'), encoding='utf-8'))
    st, by_lang, new = collections.Counter(), collections.defaultdict(collections.Counter), {}
    for r, why, _ in regenerated(a):
        st['in'] += 1
        L = want.get(r['id'])
        if L is None:
            st['drop_not_a_target_id'] += 1
            continue
        if why:
            st[why] += 1
            by_lang[L][why] += 1
            continue
        out = to_release(r)
        out['regenerated'] = 'lowres_gemma'
        new[r['id']] = json.dumps(out, ensure_ascii=False) + '\n'
    with open(os.path.join(rel, 'lowres_regen_replaced.jsonl'), 'w', encoding='utf-8') as fr:
        for fp in sorted(glob.glob(os.path.join(rel, 'data', '*.jsonl'))):
            buf, hit = [], 0
            for l in open(fp, encoding='utf-8'):
                i = json.loads(l)['id'] if new else None
                if i in new:
                    fr.write(l)
                    buf.append(new.pop(i))
                    hit += 1
                    st['replaced'] += 1
                    by_lang[want[i]]['replaced'] += 1
                else:
                    buf.append(l)
            if hit:
                with open(fp + '.tmp', 'w', encoding='utf-8') as fo:
                    fo.writelines(buf)
                os.replace(fp + '.tmp', fp)
    st['not_found_in_release'] = len(new)
    st['kept_ministral'] = len(want) - st['replaced']
    res = {'counts': dict(st), 'targets': len(want), 'by_language': {L: dict(c) for L, c in sorted(by_lang.items())}}
    json.dump(res, open(os.path.join(rel, 'lowres_regen_replace.json'), 'w'), indent=1, ensure_ascii=False)
    print(json.dumps(res, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--mode', choices=('append', 'replace'), required=True)
    ap.add_argument('--release-dir', required=True)
    ap.add_argument('--run', required=True, help='regeneration run directory (final/data, ids.txt)')
    ap.add_argument('--part', default='seeds', help='release_part label of the seed-pool records')
    ap.add_argument('--lid-model', default=os.environ.get('PF_LID_MODEL'))
    ap.add_argument('--workers', type=int, default=64)
    a = ap.parse_args()
    (append if a.mode == 'append' else replace)(a)


if __name__ == '__main__':
    main()
