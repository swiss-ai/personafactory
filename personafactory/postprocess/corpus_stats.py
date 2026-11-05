#!/usr/bin/env python3
"""Corpus statistics of the merged release directory (corpus table, corpus section and appendix numbers).

Counts per release part and overall: seed source, setting (language_mode), responder, match tier, number of user
turns, detected language of the first user turn, persona macro-region, and the crossings mode x language,
source x mode, responder x source; summary per part (languages, cross-lingual languages, English shares, user turns
per conversation). With --gen, also the user turns of the seed-pool conversations that the pipeline left unchanged,
by skip reason (from the generation output turns_detail). Writes <release>/corpus_stats.json. The stacked
language / region figure is release.stats.corpus_distribution.

  python -m personafactory.postprocess.corpus_stats --release-dir ./release_merged --gen ./outputs/seeds_run/gen
"""
import argparse, collections, glob, json, os
from multiprocessing import Pool

SKIPLANG = ('TooShort', 'Unknown', 'None')
KEYS = set()


def scan(fp):
    c = collections.Counter()
    for l in open(fp, encoding='utf-8'):
        if not l.strip():
            continue
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if r['status'] != 'pass' or r['key'] not in KEYS:
            continue
        for t in r['result']['metadata']['turns_detail']:
            c['turns'] += 1
            if t.get('persona_user_message_changed') is False or not t.get('persona_applied', True):
                c['unchanged'] += 1
                c['unchanged/' + str(t.get('persona_skip_reason'))] += 1
    return c


def main():
    global KEYS
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release-dir', required=True)
    ap.add_argument('--gen', help='generation output directory of the seed pool (<run>/gen) for unchanged-turn counts')
    ap.add_argument('--part', default='seeds', help='release_part label of the seed-pool records')
    ap.add_argument('--workers', type=int, default=64)
    a = ap.parse_args()
    region = {}
    for l in open(os.path.join(a.release_dir, 'persona_bank.jsonl'), encoding='utf-8'):
        p = json.loads(l)
        region[p['id']] = p['background'].get('region')
    d = collections.defaultdict(collections.Counter)
    parts = set()
    for fp in sorted(glob.glob(os.path.join(a.release_dir, 'data', '*.jsonl'))):
        for l in open(fp, encoding='utf-8'):
            r = json.loads(l)
            part, s, L = r['release_part'], r['source_name'], str(r['text_language'])
            parts.add(part)
            if part == a.part:
                KEYS.add(r['id'])
            nu = sum(m['role'] == 'user' for m in r['conversation'])
            for p in (part, 'all'):
                for k, v in (('source', s), ('mode', r['language_mode']), ('responder', r['responder']),
                             ('match', r.get('match_basis')), ('user_turns', nu), ('language', L),
                             ('region', region.get(r['persona_id'])), ('mode_x_language', f"{r['language_mode']}|{L}"),
                             ('source_x_mode', f"{s}|{r['language_mode']}"), ('responder_x_source', f"{r['responder']}|{s}")):
                    d[f'{p}/{k}'][str(v)] += 1
                d[f'{p}/totals']['conversations'] += 1
                d[f'{p}/totals']['user_turns'] += nu
    out = {k: dict(v.most_common()) for k, v in sorted(d.items())}
    if a.gen:
        unch = collections.Counter()
        with Pool(a.workers) as pool:
            for c in pool.imap_unordered(scan, sorted(glob.glob(os.path.join(a.gen, '*.jsonl')))):
                unch.update(c)
        out[f'{a.part}_gen_unchanged_turns'] = dict(unch.most_common())
    for p in sorted(parts) + ['all']:
        langs = {k for k in out[f'{p}/language'] if k not in SKIPLANG}
        ml = {k.split('|')[1] for k in out[f'{p}/mode_x_language'] if k.startswith('multilingual|') and k.split('|')[1] not in SKIPLANG}
        tot = out[f'{p}/totals']['conversations']
        mtot = sum(v for k, v in out[f'{p}/mode_x_language'].items() if k.startswith('multilingual|'))
        out[f'{p}/summary'] = {'languages': len(langs), 'languages_multilingual': len(ml),
                               'english_pct': round(100 * out[f'{p}/language'].get('English', 0) / tot, 2),
                               'english_pct_multilingual': round(100 * out[f'{p}/mode_x_language'].get('multilingual|English', 0) / mtot, 2) if mtot else None,
                               'turns_per_conv': round(out[f'{p}/totals']['user_turns'] / tot, 3)}
    json.dump(out, open(os.path.join(a.release_dir, 'corpus_stats.json'), 'w'), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in out.items() if k.endswith('summary') or k.endswith('totals') or 'unchanged' in k}, indent=1))


if __name__ == '__main__':
    main()
