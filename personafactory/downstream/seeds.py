#!/usr/bin/env python3
"""Recover the seed conversation of released conversations (needed for arms A0, A1 and X1).

A released conversation keeps its seed reference in `source_id` (`wildchat:<conversation_hash>:<turn_identifier>`,
`ultrachat:<id>`, `nemotron:<uuid>`) and the seed's first user turn in `original_prompt`. Seeds are looked up by
`source_id`, and by the normalized first user turn for records without one. Two seed inputs are supported:

  --seed-shards   seed records of the pipeline's seed preparation (JSONL with `source_id` or `seed_id` and
                  `conversation`); exact, use these when you have them
  --source        the public seed datasets, NAME=SPEC with SPEC a hub id or local parquet / JSONL glob
                  (defaults: wildchat=allenai/WildChat-4.8M, ultrachat=stingning/ultrachat,
                  nemotron=nvidia/Nemotron-Instruction-Following-Chat-v1); rows are normalized as in the pipeline:
                  a leading empty system turn is dropped, the first 3 user turns are kept with their replies,
                  reasoning blocks are removed from Nemotron replies

Only records of the requested setting(s) are resolved. Output: JSONL {id, source_id, conversation} per released
conversation whose seed was found, plus <out>.stats.json.

  python -m personafactory.downstream.seeds --release swiss-ai/PersonaFactory --setting language_matched \
      --seed-shards "$PF_DATA_DIR/seeds/*.jsonl" --out $PF_OUT_DIR/downstream/seeds_language_matched.jsonl
"""
import argparse, ast, collections, json, re, unicodedata

from personafactory.downstream.common import HF_REPO, iter_rows, load_release

DEFAULT_SOURCES = {'wildchat': 'allenai/WildChat-4.8M', 'ultrachat': 'stingning/ultrachat',
                   'nemotron': 'nvidia/Nemotron-Instruction-Following-Chat-v1'}
MAX_TURNS = 3
THINK = re.compile(r'<think>.*?</think>\s*', re.S)


def norm_text(t):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', t or '').casefold()).strip()


def view(messages):
    """Pipeline seed view: optional empty leading system turn dropped, alternation required, first 3 user turns kept."""
    kept, users, expected = [], 0, 'user'
    for i, m in enumerate(messages or []):
        role, content = m.get('role'), m.get('content')
        if not isinstance(content, str):
            return None
        if role == 'system' and i == 0 and not content.strip():
            continue
        if role != expected or not content.strip():
            return None
        if role == 'user':
            users += 1
        expected = 'assistant' if role == 'user' else 'user'
        if users <= MAX_TURNS:
            kept.append({'role': role, 'content': content})
    return kept if users else None


def source_rows(name, spec):
    """(source_id, messages) of one public seed dataset."""
    for row in iter_rows(spec, None):
        if name == 'ultrachat':
            msgs = [{'role': ('user', 'assistant')[i % 2], 'content': t} for i, t in enumerate(row.get('data') or [])]
            yield f"ultrachat:{row.get('id')}", msgs
        elif name == 'nemotron':
            msgs = [{'role': m.get('role'), 'content': THINK.sub('', m.get('content') or '') if m.get('role') == 'assistant'
                     else m.get('content')} for m in row.get('messages') or [] if isinstance(m, dict)]
            yield f"nemotron:{row.get('uuid')}", msgs
        else:
            conv = row.get('conversation') or []
            tid = next((m.get('turn_identifier') for m in conv if m.get('turn_identifier') is not None), None)
            yield f"wildchat:{row.get('conversation_hash')}:{tid}", [{'role': m.get('role'), 'content': m.get('content')} for m in conv]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release', default=HF_REPO, help='released chats: hub id, local snapshot / parquet, or release dir')
    ap.add_argument('--setting', nargs='+', default=['language_matched', 'cross_lingual'], choices=['language_matched', 'cross_lingual'])
    ap.add_argument('--seed-shards', nargs='*', default=[], help='pipeline seed JSONL files or globs')
    ap.add_argument('--source', nargs='*', default=None, metavar='NAME=SPEC',
                    help='public seed datasets to scan (default: all three hub datasets when --seed-shards is not given)')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    by_sid, by_text = collections.defaultdict(list), collections.defaultdict(list)
    n = 0
    for r in load_release(a.release):
        if r['setting'] not in a.setting:
            continue
        n += 1
        if r['source_id']:
            by_sid[r['source_id']].append(r['id'])
        elif r['original_prompt']:
            by_text[(r['source'], norm_text(r['original_prompt']))].append(r['id'])
    print('records', n, 'with source_id', sum(map(len, by_sid.values())), 'by text', sum(map(len, by_text.values())), flush=True)

    found, st = {}, collections.Counter()

    def offer(source, sid, conv):
        v = view(conv)
        if not v:
            return
        for rid in by_sid.get(sid, ()):
            found.setdefault(rid, (sid, v))
        key = (source, norm_text(v[0]['content']))
        for rid in by_text.get(key, ()):
            found.setdefault(rid, (sid, v))

    for fp in a.seed_shards:
        for s in iter_rows(fp, None):
            conv = s['conversation']
            conv = ast.literal_eval(conv) if isinstance(conv, str) else conv
            sid = s.get('source_id') or s.get('seed_id')
            offer(s.get('source_name') or (sid or '').split(':')[0], sid, conv)
            st['seed_shard_rows'] += 1
    sources = a.source if a.source is not None else ([] if a.seed_shards else [f'{k}={v}' for k, v in DEFAULT_SOURCES.items()])
    for item in sources:
        name, _, spec = item.partition('=')
        for sid, conv in source_rows(name, spec or DEFAULT_SOURCES[name]):
            offer(name, sid, conv)
            st[f'rows/{name}'] += 1
        print(name, 'scanned; found so far', len(found), flush=True)

    with open(a.out, 'w', encoding='utf-8') as f:
        for rid, (sid, conv) in found.items():
            f.write(json.dumps({'id': rid, 'source_id': sid, 'conversation': conv}, ensure_ascii=False) + '\n')
    st.update({'records': n, 'found': len(found), 'missing': n - len(found)})
    json.dump(dict(st), open(a.out + '.stats.json', 'w'), indent=1)
    print(json.dumps(dict(st), indent=1))


if __name__ == '__main__':
    main()
