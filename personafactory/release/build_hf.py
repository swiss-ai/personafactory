#!/usr/bin/env python3
"""Build the Hugging Face release (parquet shards) of the persona bank and the conversation corpus.

  persona_bank  every judge-kept profile of the bank      -> <out>/bank/data/train-XXXXX-of-NNNNN.parquet
  chats         every conversation of the release dir     -> <out>/chats/data/train-XXXXX-of-NNNNN.parquet

Chats are written with one uniform schema in a single train split (`source_id` lets users build seed-disjoint
splits). Conversation ids are 64-hex for every record; ids in another format are replaced by
sha256(["personafactory", id]). Also writes <out>/{bank,chats}/stats.json, which build_hf_cards.py turns into the
dataset card. `--id-map` optionally writes a release id -> pipeline id table (not part of the published dataset).

Inputs: --release-dir (data/*.jsonl, the release record schema of build_release.py / swap_assistant.py) and --bank
(persona bank JSONL; default PF_BANK, else <release-dir>/persona_bank.jsonl).

  python -m personafactory.release.build_hf --release-dir $PF_OUT_DIR/release --bank $PF_BANK --out $PF_OUT_DIR/hf_release
"""
import argparse, collections, glob, hashlib, json, os, re

import pyarrow as pa
import pyarrow.parquet as pq

# release responder short names -> published model ids (override with --responder name=model_id)
RESPONDER = {'gemma': 'google/gemma-4-31B-it', 'ministral': 'mistralai/Ministral-3-14B-Instruct-2512'}
SETTING = {'free': 'language_matched', 'multilingual': 'cross_lingual'}
VALIDATION_KEEP = ('coherent', 'location_plausible', 'llm_user_plausible', 'stereotype_severity', 'realism')
HEX = re.compile(r'^[0-9a-f]{64}$')
CHATS_SCHEMA = pa.schema([
    ('id', pa.string()), ('messages', pa.list_(pa.struct([('role', pa.string()), ('content', pa.string())]))),
    ('persona_id', pa.string()), ('language', pa.string()), ('setting', pa.string()), ('match_tier', pa.string()),
    ('source', pa.string()), ('source_id', pa.string()), ('original_prompt', pa.string()), ('num_turns', pa.int64()),
    ('responder', pa.string()), ('model_persona', pa.string()), ('sanity_verdicts', pa.list_(pa.string()))])


def write_shards(rows, schema, outdir, per_shard, split='train'):
    n = (len(rows) + per_shard - 1) // per_shard
    for i in range(n):
        t = pa.Table.from_pylist(rows[i * per_shard:(i + 1) * per_shard], schema=schema)
        pq.write_table(t, os.path.join(outdir, f'{split}-{i:05d}-of-{n:05d}.parquet'), compression='zstd', row_group_size=10000)
    return n


def build_bank(bank_path, out, per_shard):
    os.makedirs(os.path.join(out, 'data'), exist_ok=True)
    rows, st = [], collections.defaultdict(collections.Counter)
    for line in open(bank_path, encoding='utf-8'):
        p = json.loads(line)
        if (p.get('validation') or {}).get('verdict', 'keep') != 'keep':
            st['skipped']['not_kept'] += 1
            continue
        bg, sty = p['background'], p['style']
        rows.append({'id': p['id'], 'generator_model': p['generator_model'], 'background': bg, 'style': sty,
                     'character_description': p['character_description'],
                     'validation': {k: (p.get('validation') or {}).get(k) for k in VALIDATION_KEEP}})
        for k in ('region', 'country', 'main_language', 'gender', 'digital_fluency', 'ai_stance'):
            st[k][bg.get(k)] += 1
        st['generator_model'][p['generator_model']] += 1
    schema = pa.Table.from_pylist(rows).schema  # inferred over all rows so optional keys become nullable
    n = write_shards(rows, schema, os.path.join(out, 'data'), per_shard)
    stats = {'n': len(rows), 'shards': n, 'schema': schema.to_string(), 'countries': len(st['country']),
             'sub_regions': len({(r['background'].get('country'), r['background'].get('sub_region')) for r in rows}),
             **{k: {str(a): b for a, b in v.most_common()} for k, v in st.items()}}
    json.dump(stats, open(os.path.join(out, 'stats.json'), 'w'), indent=1, ensure_ascii=False)
    print('persona_bank', len(rows), 'shards', n, flush=True)


def build_chats(release_dir, out, per_shard, responder, id_map=None):
    os.makedirs(os.path.join(out, 'data'), exist_ok=True)
    rows, st = [], collections.defaultdict(collections.Counter)
    idmap = open(id_map, 'w', encoding='utf-8') if id_map else None
    for fp in sorted(glob.glob(os.path.join(release_dir, 'data', '*.jsonl'))):
        for line in open(fp, encoding='utf-8'):
            r = json.loads(line)
            sid = r.get('source_id') or (r['id'] if ':' in r['id'] else None)
            rid = r['id'] if HEX.match(r['id']) else hashlib.sha256(json.dumps(['personafactory', r['id']]).encode()).hexdigest()
            if idmap:
                idmap.write(json.dumps({'id': rid, 'pipeline_id': r['id']}) + '\n')
            msgs = [{'role': m['role'], 'content': m['content']} for m in r['conversation']]
            lang = r['text_language'] if r.get('text_language') not in (None, 'TooShort', 'Unknown') else None
            setting, resp = SETTING[r['language_mode']], responder.get(r['responder'], r['responder'])
            rows.append({
                'id': rid, 'messages': msgs, 'persona_id': r['persona_id'], 'language': lang, 'setting': setting,
                'match_tier': r.get('match_basis'), 'source': r.get('source_name'), 'source_id': sid,
                'original_prompt': r.get('source_text'), 'num_turns': r.get('num_turns'), 'responder': resp,
                'model_persona': r.get('model_persona'), 'sanity_verdicts': r.get('sanity_verdicts')})
            for k, v in (('setting', setting), ('match_tier', r.get('match_basis')), ('source', r.get('source_name')),
                         ('responder', resp), ('language', lang or 'undetermined'), ('num_turns', r.get('num_turns')),
                         ('model_persona', r.get('model_persona') or 'none')):
                st[k][v] += 1
            st['user_turns']['all'] += sum(m['role'] == 'user' for m in msgs)
    if idmap:
        idmap.close()
    n = write_shards(rows, CHATS_SCHEMA, os.path.join(out, 'data'), per_shard)
    stats = {'n': len(rows), 'shards': n, 'personas': len({x['persona_id'] for x in rows}),
             **{k: {str(a): b for a, b in v.most_common()} for k, v in st.items()}}
    json.dump(stats, open(os.path.join(out, 'stats.json'), 'w'), indent=1, ensure_ascii=False)
    print('chats', stats['n'], 'shards', n, flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release-dir', required=True, help='release directory with data/*.jsonl')
    ap.add_argument('--bank', default=os.environ.get('PF_BANK'), help='persona bank JSONL (default: PF_BANK, else <release-dir>/persona_bank.jsonl)')
    ap.add_argument('--out', required=True, help='output directory (bank/, chats/)')
    ap.add_argument('--part', choices=['bank', 'chats', 'all'], default='all')
    ap.add_argument('--bank-rows-per-shard', type=int, default=100000)
    ap.add_argument('--chat-rows-per-shard', type=int, default=50000)
    ap.add_argument('--responder', nargs='*', default=[], metavar='NAME=MODEL_ID', help='extra responder name -> model id mappings')
    ap.add_argument('--id-map', default=None, help='optional JSONL path for a release id -> pipeline id table (off by default)')
    a = ap.parse_args()
    responder = dict(RESPONDER, **dict(x.split('=', 1) for x in a.responder))
    if a.part in ('bank', 'all'):
        build_bank(a.bank or os.path.join(a.release_dir, 'persona_bank.jsonl'), os.path.join(a.out, 'bank'), a.bank_rows_per_shard)
    if a.part in ('chats', 'all'):
        build_chats(a.release_dir, os.path.join(a.out, 'chats'), a.chat_rows_per_shard, responder, a.id_map)


if __name__ == '__main__':
    main()
