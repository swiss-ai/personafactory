#!/usr/bin/env python3
"""Low-resource quality filter on the merged release directory.

Decisions come from <quality-dir>/rows.jsonl (postprocess.lowres_quality --stage metrics). A low-resource conversation
(control languages German / Spanish are never dropped) is removed with the first matching reason:
  drop_free_lid_mislabel     language-matched setting, detected as Maori / Tswana (Nigerian Pidgin, pinyin misdetected)
  drop_language              languages that score < 2.5 with the judge even with Gemma (DROP_LANG)
  drop_ministral             Ministral responder in a low-resource language (except Uzbek and Nepali)
  drop_repetition            user or assistant 3-gram repeat share > 0.3
  drop_user_mostly_english   cross-lingual setting, > 50% of the user turns detected as English
<release>/data is moved to <release>/data_unfiltered (kept), the filtered shards are written to <release>/data,
removed ids + reason to <release>/lowres_removed.jsonl, counts to <release>/lowres_filter.json.
Conversations removed as drop_ministral can be regenerated with Gemma (postprocess.lowres_regen_prep --source removed).

  python -m personafactory.postprocess.apply_lowres_filter --release-dir ./release_merged --quality-dir ./outputs/lowres_quality
"""
import argparse, collections, glob, json, os

REF = {'German', 'Spanish'}
KEEP_MINISTRAL = {'Uzbek', 'Nepali'}
DROP_LANG = {'Quechua', 'Shan', 'Guarani', 'Dhivehi', 'Ewe', 'Bambara', 'Fula', 'Aymara'}
REPETITION = .3


def reason(x):
    """Drop reason of one rows.jsonl row (None = keep)."""
    L = x['lang']
    if L in REF:
        return None
    if x['mode'] == 'free' and L in ('Maori', 'Tswana'):
        return 'drop_free_lid_mislabel'
    if L in DROP_LANG:
        return 'drop_language'
    if x['responder'] == 'ministral' and L not in KEEP_MINISTRAL:
        return 'drop_ministral'
    if x['user_rep'] > REPETITION or x['asst_rep'] > REPETITION:
        return 'drop_repetition'
    ul = [t for t in x['user_lid'] if t != 'TooShort']
    if x['mode'] == 'multilingual' and ul and sum(t == 'English' for t in ul) / len(ul) > .5:
        return 'drop_user_mostly_english'
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release-dir', required=True)
    ap.add_argument('--quality-dir', required=True, help='lowres_quality --out directory (rows.jsonl)')
    a = ap.parse_args()
    rel = a.release_dir
    drop = {}
    for l in open(os.path.join(a.quality_dir, 'rows.jsonl'), encoding='utf-8'):
        x = json.loads(l)
        r = reason(x)
        if r:
            drop[x['id']] = (r, x['lang'], x['part'], x['responder'])
    src = os.path.join(rel, 'data_unfiltered')
    if not os.path.isdir(src):
        os.rename(os.path.join(rel, 'data'), src)
    os.makedirs(os.path.join(rel, 'data'), exist_ok=True)
    st, by_lang = collections.Counter(), collections.defaultdict(collections.Counter)
    with open(os.path.join(rel, 'lowres_removed.jsonl'), 'w', encoding='utf-8') as fr:
        for fp in sorted(glob.glob(os.path.join(src, '*.jsonl'))):
            with open(os.path.join(rel, 'data', os.path.basename(fp)), 'w', encoding='utf-8') as fo:
                for l in open(fp, encoding='utf-8'):
                    i = json.loads(l)['id']
                    st['in'] += 1
                    if i in drop:
                        r, L, part, resp = drop[i]
                        st[r] += 1
                        st[f'removed/{part}'] += 1
                        by_lang[L][r] += 1
                        fr.write(json.dumps({'id': i, 'reason': r, 'lang': L, 'release_part': part, 'responder': resp}, ensure_ascii=False) + '\n')
                    else:
                        fo.write(l)
                        st['kept'] += 1
    res = {'counts': dict(st), 'decisions': len(drop), 'by_language': {L: dict(c) for L, c in sorted(by_lang.items())}}
    json.dump(res, open(os.path.join(rel, 'lowres_filter.json'), 'w'), indent=1, ensure_ascii=False)
    print(json.dumps(res['counts'], indent=1))
    assert st['in'] - st['kept'] == len(drop), 'some dropped ids were not found in the release'


if __name__ == '__main__':
    main()
