#!/usr/bin/env python3
"""Merge the two record sets of the corpus into one release directory.

Parts (--part LABEL=DIR, in priority order; DIR holds *.jsonl records):
  pairs  the persona-pair conversations: release/build_release.py output after the emoji scrub and the assistant
         swap (UltraChat and Nemotron seeds, one seed per persona, assistant side with a matched model persona)
  seeds  the seed-pool conversations: augmentation.build_corpus --stage final output (UltraChat, Nemotron and
         WildChat seeds, assistant side from the user-side pass)
Every record keeps its own fields (union schema, missing fields null) plus `release_part` (the part label).
Cross-part dedup: a record with the same id, or with the same normalized source_text and text_language as a
record of a part listed before it (parts are read in --part order), is dropped. Records are sharded by md5(id) into <out>/data/NNNN.jsonl;
<out>/persona_bank.jsonl holds the bank profiles of every persona used; <out>/summary.json has the counts.

  python -m personafactory.release.merge_release --part pairs=$REL/data --part seeds=./outputs/seeds_run/final/data \\
      --bank $PF_BANK --out ./release_merged
"""
import argparse, collections, glob, hashlib, json, os, re

FIELDS = ['id', 'release_part', 'conversation', 'persona_id', 'persona_language', 'target_language', 'text_language',
          'language_mode', 'source_text', 'source_name', 'source_id', 'seed_language', 'cohort', 'responder', 'num_turns',
          'match_basis', 'split', 'lid_verifiable', 'user_sanity_verdicts', 'sanity_verdicts', 'model_persona',
          'model_persona_quirks', 'assistant_generation']
SHARDS = 256
DIST_KEYS = (('mode', 'language_mode'), ('text_language', 'text_language'), ('source', 'source_name'),
             ('responder', 'responder'), ('num_turns', 'num_turns'))


def src_key(r):
    return hashlib.sha1(re.sub(r'\s+', ' ', (r.get('source_text') or '').strip().lower()).encode('utf-8', 'ignore')).hexdigest(), r.get('text_language')


def to_release(r):
    """Release field order: FIELDS first (missing -> null), then any extra fields of the record."""
    out = {f: r.get(f) for f in FIELDS}
    out.update({f: v for f, v in r.items() if f not in out})
    return out


def shard_of(rid, shards=SHARDS):
    return int(hashlib.md5(rid.encode()).hexdigest(), 16) % shards


def summarize(release_dir, extra_counts=None):
    """Recompute <release_dir>/summary.json from the current data/ shards and prune persona_bank.jsonl to the personas
    still used. Returns the counts."""
    st, dist, personas = collections.Counter(extra_counts or {}), collections.defaultdict(collections.Counter), set()
    for fp in sorted(glob.glob(os.path.join(release_dir, 'data', '*.jsonl'))):
        for l in open(fp, encoding='utf-8'):
            r = json.loads(l)
            part = r['release_part']
            st[f'kept/{part}'] += 1
            personas.add(r['persona_id'])
            for name, f in DIST_KEYS:
                dist[f'{part}/{name}'][str(r[f])] += 1
                dist[f'all/{name}'][str(r[f])] += 1
    st['kept/all'] = sum(v for k, v in list(st.items()) if k.startswith('kept/'))
    bank = os.path.join(release_dir, 'persona_bank.jsonl')
    found = 0
    with open(bank + '.tmp', 'w', encoding='utf-8') as fo:
        for l in open(bank, encoding='utf-8'):
            if json.loads(l)['id'] in personas:
                fo.write(l)
                found += 1
    os.replace(bank + '.tmp', bank)
    st['personas_used'] = len(personas)
    st['personas_found_in_bank'] = found
    res = {'counts': dict(sorted(st.items())), 'distributions': {k: dict(v.most_common()) for k, v in sorted(dist.items())}}
    json.dump(res, open(os.path.join(release_dir, 'summary.json'), 'w'), indent=1, ensure_ascii=False)
    return res['counts']


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--part', action='append', required=True, metavar='LABEL=DIR', help='record set, in priority order')
    ap.add_argument('--bank', default=os.environ.get('PF_BANK'), required='PF_BANK' not in os.environ,
                    help='persona bank containing every persona of both parts')
    ap.add_argument('--out', required=True)
    ap.add_argument('--shards', type=int, default=SHARDS)
    a = ap.parse_args()
    parts = [p.split('=', 1) for p in a.part]
    os.makedirs(os.path.join(a.out, 'data'), exist_ok=True)
    sinks = [open(os.path.join(a.out, 'data', f'{i:04d}.jsonl'), 'w', encoding='utf-8') for i in range(a.shards)]
    st = collections.Counter()
    dist = collections.defaultdict(collections.Counter)
    seen, ids, personas = set(), set(), set()
    for part, d in parts:
        for fp in sorted(glob.glob(os.path.join(d, '*.jsonl'))):
            for l in open(fp, encoding='utf-8'):
                r = json.loads(l)
                r['release_part'] = part
                st[f'in/{part}'] += 1
                if r['id'] in ids:
                    st[f'drop_duplicate_id/{part}'] += 1
                    continue
                k = src_key(r)
                if k in seen:
                    st[f'drop_same_source_same_language/{part}'] += 1
                    continue
                seen.add(k)
                ids.add(r['id'])
                personas.add(r['persona_id'])
                sinks[shard_of(r['id'], a.shards)].write(json.dumps(to_release(r), ensure_ascii=False) + '\n')
                st[f'kept/{part}'] += 1
                for name, f in DIST_KEYS:
                    dist[f'{part}/{name}'][str(r[f])] += 1
                    dist[f'all/{name}'][str(r[f])] += 1
    for f in sinks:
        f.close()
    found = 0
    with open(os.path.join(a.out, 'persona_bank.jsonl'), 'w', encoding='utf-8') as fo:
        for l in open(a.bank, encoding='utf-8'):
            if json.loads(l)['id'] in personas:
                fo.write(l if l.endswith('\n') else l + '\n')
                found += 1
    st['personas_used'] = len(personas)
    st['personas_found_in_bank'] = found
    st['kept/all'] = sum(st[f'kept/{p}'] for p, _ in parts)
    res = {'counts': dict(sorted(st.items())), 'distributions': {k: dict(v.most_common()) for k, v in sorted(dist.items())}}
    json.dump(res, open(os.path.join(a.out, 'summary.json'), 'w'), indent=1, ensure_ascii=False)
    print(json.dumps(res['counts'], indent=1))


if __name__ == '__main__':
    main()
