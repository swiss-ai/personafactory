#!/usr/bin/env python3
"""Drop low-resource conversations whose user turns barely use the language's expected script, then rebuild
summary.json and prune persona_bank.jsonl.

Candidates: rows of <quality-dir>/rows.jsonl (postprocess.lowres_quality) that the low-resource filter kept and whose
user-turn script share is < 0.1 (mostly Khmer, Lao, Odia, Assamese written in Latin script). The share is recomputed
on the current text (conversations regenerated after rows.jsonl was written may have changed), and only
conversations still below 0.1 are dropped. Shards of <release>/data are rewritten in place (tmp + rename); removed
records -> <release>/lowscript_removed.jsonl, counts -> <release>/lowscript_filter.json.

  python -m personafactory.postprocess.drop_lowscript --release-dir ./release_merged --quality-dir ./outputs/lowres_quality
"""
import argparse, collections, glob, json, os

from personafactory.postprocess.apply_lowres_filter import REF, reason
from personafactory.postprocess.lowres_quality import LOWRES, script_share
from personafactory.release.merge_release import summarize

THRESH = .1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release-dir', required=True)
    ap.add_argument('--quality-dir', required=True, help='lowres_quality --out directory (rows.jsonl)')
    a = ap.parse_args()
    cand = {}
    for l in open(os.path.join(a.quality_dir, 'rows.jsonl'), encoding='utf-8'):
        x = json.loads(l)
        if x['lang'] in REF or reason(x):
            continue
        if x['user_script'] is not None and x['user_script'] < THRESH:
            cand[x['id']] = x['lang']
    print('candidates', len(cand))
    st, by_lang = collections.Counter(), collections.Counter()
    with open(os.path.join(a.release_dir, 'lowscript_removed.jsonl'), 'w', encoding='utf-8') as fr:
        for fp in sorted(glob.glob(os.path.join(a.release_dir, 'data', '*.jsonl'))):
            with open(fp + '.tmp', 'w', encoding='utf-8') as fo:
                for l in open(fp, encoding='utf-8'):
                    r = json.loads(l)
                    if r['id'] in cand:
                        L = cand[r['id']]
                        share = script_share(' '.join(m['content'] for m in r['conversation'] if m['role'] == 'user'), LOWRES[L])
                        if share is not None and share < THRESH:
                            st['removed'] += 1
                            st[f"removed/{r['release_part']}"] += 1
                            by_lang[L] += 1
                            fr.write(json.dumps({**r, 'lowscript_lang': L, 'user_script': share}, ensure_ascii=False) + '\n')
                            continue
                        st['candidate_kept_now_ok'] += 1
                    fo.write(l)
            os.replace(fp + '.tmp', fp)
    counts = summarize(a.release_dir, st)
    json.dump({'counts': dict(st), 'candidates': len(cand), 'by_language': dict(by_lang.most_common())},
              open(os.path.join(a.release_dir, 'lowscript_filter.json'), 'w'), indent=1, ensure_ascii=False)
    print(json.dumps(counts, indent=1))


if __name__ == '__main__':
    main()
