#!/usr/bin/env python3
"""LID re-check and register statistics of the released first user turns.

Re-runs LID on every first user turn after the emoji scrub (reports label changes, does not edit the data),
and compares the surface register (emoji, lowercase start, missing final punctuation, ellipsis, length) of
free and multilingual records, both over the whole release and over
records paired by persona (personas that occur in both settings).
Writes <release-dir>/register_stats.json.

  python -m personafactory.release.stats.register_stats --release-dir ./release_out --lid-model ./models/lid.176.ftz --workers 60
"""
import argparse, collections, glob, json, os, statistics as st
from multiprocessing import Pool

from personafactory.common.lid import init, detect
from personafactory.release.emoji_utils import EMOJI


def handle(line):
    r = json.loads(line)
    u = next((m.get('content') for m in r['conversation'] if m.get('role') == 'user'), '')
    return {'old': r['text_language'], 'new': detect(u),
            'mode': r['language_mode'], 'pid': r.get('persona_id'),
            'emoji': bool(EMOJI.search(u)), 'lower_start': u[:1].islower(),
            'no_end_punct': bool(u.rstrip()) and u.rstrip()[-1] not in '.!?;·',
            'ellipsis': '...' in u or '…' in u, 'chars': len(u)}


def lines(release_dir):
    for fp in sorted(glob.glob(os.path.join(release_dir, 'data', '*.jsonl'))):
        for l in open(fp, encoding='utf-8'):
            if l.strip():
                yield l


def reg(rs):
    n = len(rs)
    p = lambda k: round(100 * sum(r[k] for r in rs) / n, 1)
    return {'n': n, 'emoji_pct': p('emoji'), 'lower_start_pct': p('lower_start'),
            'no_end_punct_pct': p('no_end_punct'), 'ellipsis_pct': p('ellipsis'),
            'median_chars': int(st.median(r['chars'] for r in rs))}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release-dir', required=True)
    ap.add_argument('--lid-model', default=os.environ.get('PF_LID_MODEL'), help='fastText lid.176 model (or PF_LID_MODEL)')
    ap.add_argument('--lid-deps', default=None, help='optional directory with the fasttext/lingua packages')
    ap.add_argument('--out', default=None, help='default: <release-dir>/register_stats.json')
    ap.add_argument('--workers', type=int, default=60)
    args = ap.parse_args()
    with Pool(args.workers, initializer=init, initargs=(args.lid_model, args.lid_deps)) as pool:
        rows = list(pool.imap_unordered(handle, lines(args.release_dir), chunksize=128))
    changed = [r for r in rows if r['old'] != r['new']]
    res = {'records': len(rows), 'lid_label_changes_after_scrub': len(changed),
           'lid_change_examples': collections.Counter(f"{r['old']}->{r['new']}" for r in changed).most_common(15)}
    f = {r['pid']: r for r in rows if r['mode'] == 'free'}
    m = {r['pid']: r for r in rows if r['mode'] == 'multilingual'}
    shared = sorted(set(f) & set(m))
    res['register_paired_by_persona'] = {'pairs': len(shared), 'free': reg([f[i] for i in shared]),
                                                'multilingual': reg([m[i] for i in shared])}
    res['register_all_by_mode'] = {k: reg([r for r in rows if r['mode'] == k]) for k in ('free', 'multilingual')}
    json.dump(res, open(args.out or os.path.join(args.release_dir, 'register_stats.json'), 'w'), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
