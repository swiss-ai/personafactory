#!/usr/bin/env python3
"""Build the seed-pair input of the augmentation pipeline: one seed conversation per persona.

Seed conversations come from two chat datasets with a `messages` list of {role, content}:
UltraChat (HuggingFaceH4/ultrachat_200k, split train_sft) and Nemotron
(nvidia/Nemotron-Instruction-Following-Chat-v1, split chat_if). Each can be given as an HF dataset id
(loaded with `datasets`, optionally pinned with --*-revision) or as local .jsonl / .parquet files (glob).

Source filtering (per row, in file order):
  - reject tool conversations, a non-empty system message, non-text or extra message fields, empty
    messages, and role sequences that are not user/assistant alternating (an empty system message at
    position 0 is kept);
  - keep at most the first 3 user turns (and the assistant reply to the third); reject if the kept user
    turns exceed 1000 words or the kept text exceeds 45,000 characters;
  - reject rows with a license outside MIT / Apache-2.0 / CC-BY / ODC-BY (when a row carries one);
  - deduplicate by source id, by full conversation hash and by normalised user-prefix hash.
From the eligible rows a fixed hash (seed, source id, conversation hash) ranks rows; each dataset
contributes half of the pairs. Split (train / validation / test = 90 / 5 / 5) is a hash of the user
prefix, so both modes of a pair share a split.

Personas are grouped by (resolved language, country), strata and personas within a stratum are ordered
by seed hash, and personas are drawn round-robin across strata; the i-th persona gets the next row of
UltraChat for even i and of Nemotron for odd i. The resolved language (`target_language`, the language
used in the cross-lingual mode) is: Ukrainian for Ukraine + Ukrainian-main personas, Swiss German for
Swiss personas with explicit Swiss-German evidence, else the canonical label of native_language, else of
main_language, else unresolved (null; such personas are left out of the cross-lingual pool).

Output: <out-dir>/NNNN.jsonl shards of 512 records:
  {pair_key, persona_id, target_language, language_resolution, conversation, source_id, source_name,
   source_license, split, seed, assignment_index}
  conversation = the retained source prefix [{role, content}, ...] (original assistant replies included;
  the pipeline rewrites the user turns and regenerates the assistant turns).
Only pair_key, persona_id, target_language, conversation (select_personas / embed_personas) and
source_id, source_name, split (run_augmentation) are consumed downstream.

Run (CPU):
  python -m personafactory.augmentation.prepare_pairs --bank $PF_BANK --out-dir ./data/pairs
"""
import argparse, copy, glob, hashlib, heapq, json, os, re
from collections import Counter, defaultdict, deque

from personafactory.common.lang_canon import canonical_label_core

SEED = 2026092017
# Namespaces of the pair key and the split hash.
PAIR_NAMESPACE = 'personafactory-pairs'
SPLIT_NAMESPACE = 'personafactory-split'
CHUNK = 512
MAX_TURNS, MAX_USER_WORDS, MAX_CHARS = 3, 1000, 45000
LICENSES = {'mit', 'apache-2.0', 'cc-by-3.0', 'cc-by-4.0', 'odc-by-1.0'}

SWISS_GERMAN_MARKERS = ('swiss german', 'swiss-german', 'schweizerdeutsch', 'schwiizerd',
                        'zürichdeutsch', 'zuerichdeutsch', 'zurich german', 'zürich german',
                        'berndeutsch', 'bernese german', 'baseldytsch', 'basel german',
                        'walliserdeutsch', 'valais german', 'alemannic')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


# ---------------------------------------------------------------- persona language resolution
canonical_label = canonical_label_core  # strict resolution on the core label tables


def cohort_of(persona):
    """Ukrainian cohort, or Swiss German with explicit evidence (not Swiss residence alone)."""
    background = persona.get('background', {})
    country = str(background.get('country', '')).strip().casefold()
    language = str(background.get('main_language', '')).strip().casefold()
    if country == 'ukraine' and language == 'ukrainian':
        return 'ukrainian'
    if country != 'switzerland' or language not in {'german', 'swiss german', 'swiss-german', 'schweizerdeutsch'}:
        return None
    evidence = ' '.join(str(background.get(key, '')) for key in ('main_language', 'native_language', 'dialect')).casefold()
    return 'swiss_german' if any(marker in evidence for marker in SWISS_GERMAN_MARKERS) else None


def language_of(persona):
    bg = persona['background']
    cohort = cohort_of(persona)
    if cohort == 'ukrainian':
        return 'Ukrainian', 'ukrainian_cohort'
    if cohort == 'swiss_german':
        return 'Swiss German', 'explicit_swiss_german_evidence'
    native = canonical_label(bg.get('native_language'))
    if native:
        return native, 'native_language'
    main = canonical_label(bg.get('main_language'))
    if main:
        return main, 'declared_main_fallback_unresolved_native'
    return None, 'held_unresolved_language'


# ---------------------------------------------------------------- seed conversations
def conversation_view(row):
    """Retain the source-exact prefix (up to MAX_TURNS user turns), including original replies."""
    messages = row.get('messages')
    if not isinstance(messages, list) or not messages:
        raise ValueError('missing_messages')
    if row.get('tools'):
        raise ValueError('tool_conversation')
    original, users, retained = [], 0, []
    expected = 'user'
    for index, message in enumerate(messages):
        if not isinstance(message, dict) or not isinstance(message.get('content'), str):
            raise ValueError('nontext_message')
        if set(message) - {'role', 'content'}:
            raise ValueError('unsupported_message_fields')
        role = message.get('role')
        if role == 'system' and index == 0:
            if message['content'].strip():
                raise ValueError('nonempty_system_prompt')
            original.append(copy.deepcopy(message))
            retained.append(copy.deepcopy(message))
            continue
        if role != expected:
            raise ValueError('invalid_role_sequence')
        if not message['content'].strip():
            raise ValueError('empty_message')
        if role == 'user':
            users += 1
            expected = 'assistant'
        else:
            expected = 'user'
        original.append(copy.deepcopy(message))
        if users <= MAX_TURNS:
            retained.append(copy.deepcopy(message))
    if not users:
        raise ValueError('no_user_turns')
    user_messages = [m['content'] for m in retained if m['role'] == 'user']
    if sum(len(t.split()) for t in user_messages) > MAX_USER_WORDS:
        raise ValueError('too_many_user_words')
    if sum(len(m['content']) for m in retained) > MAX_CHARS:
        raise ValueError('too_many_retained_characters')
    # whitespace is normalised for dedup only, never in the retained text
    prefix_key = digest([re.sub(r'\s+', ' ', t).strip() for t in user_messages])
    return {'conversation': retained, 'parent': digest(original), 'prefix': prefix_key}


def source_split(prefix_hash):
    bucket = int(digest([SPLIT_NAMESPACE, prefix_hash])[:16], 16) % 100
    return 'train' if bucket < 90 else 'validation' if bucket < 95 else 'test'


def iter_rows(spec, split, revision):
    """(row_index, row) from local .jsonl/.parquet files (glob) or an HF dataset id."""
    files = sorted(glob.glob(spec))
    if files:
        for path in files:
            offset = 0
            if path.endswith('.parquet'):
                import pyarrow.parquet as pq
                for batch in pq.ParquetFile(path).iter_batches(batch_size=512, use_threads=False):
                    for row in batch.to_pylist():
                        yield f'{os.path.basename(path)}:row:{offset}', row
                        offset += 1
            else:
                for line in open(path, encoding='utf-8'):
                    if line.strip():
                        yield f'{os.path.basename(path)}:row:{offset}', json.loads(line)
                    offset += 1
    else:
        from datasets import load_dataset
        for offset, row in enumerate(load_dataset(spec, split=split, revision=revision)):
            yield f'row:{offset}', row


def sample_source(name, spec, split, revision, license_default, quota, seen):
    stats, heap = Counter(), []
    for row_ref, row in iter_rows(spec, split, revision):
        stats['rows_seen'] += 1
        lic = str(row.get('license') or license_default).lower()
        if lic not in LICENSES:
            stats['unsupported_license'] += 1
            continue
        try:
            view = conversation_view(row)
        except ValueError as exc:
            stats[str(exc)] += 1
            continue
        key = next((k for k in ('uuid', 'prompt_id', 'id') if row.get(k) is not None), None)
        source_id = f'{name}:{revision or "main"}:{row[key] if key else row_ref}'
        if source_id in seen['ids'] or view['parent'] in seen['parents'] or view['prefix'] in seen['prefixes']:
            stats['duplicate'] += 1
            continue
        seen['ids'].add(source_id)
        seen['parents'].add(view['parent'])
        seen['prefixes'].add(view['prefix'])
        stats['eligible_unique'] += 1
        rank = int(digest([SEED, 'source', source_id, view['parent']]), 16)
        entry = (-rank, source_id, {'conversation': view['conversation'], 'source_id': source_id,
                                    'source_name': name, 'source_license': lic,
                                    'split': source_split(view['prefix'])})
        if len(heap) < quota:
            heapq.heappush(heap, entry)
        elif entry[:2] > heap[0][:2]:
            heapq.heapreplace(heap, entry)
    if len(heap) != quota:
        raise ValueError(f'{name}: only {len(heap)} eligible rows for quota {quota}: {dict(stats)}')
    print(json.dumps({'source': name, 'statistics': stats}), flush=True)
    return deque(e[2] for e in sorted(heap, key=lambda e: (-e[0], e[1])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bank', default=os.environ.get('PF_BANK'), required='PF_BANK' not in os.environ)
    ap.add_argument('--out-dir', default=os.path.join(os.environ.get('PF_DATA_DIR', './data'), 'pairs'))
    ap.add_argument('--ultrachat', default='HuggingFaceH4/ultrachat_200k', help='HF id or local file glob')
    ap.add_argument('--ultrachat-split', default='train_sft')
    ap.add_argument('--ultrachat-revision', default='8049631c405ae6576f93f445c6b8166f76f5505a')
    ap.add_argument('--nemotron', default='nvidia/Nemotron-Instruction-Following-Chat-v1', help='HF id or local file glob')
    ap.add_argument('--nemotron-split', default='chat_if')
    ap.add_argument('--nemotron-revision', default='83dcd3aded0d289b0bbc018d3f9af4c5dd4005df')
    a = ap.parse_args()

    bank = [json.loads(l) for l in open(a.bank, encoding='utf-8') if l.strip()]
    profiles, strata, counts = {}, defaultdict(list), Counter()
    for persona in bank:
        language, basis = language_of(persona)
        profiles[persona['id']] = (language, basis)
        counts['language_basis/' + basis] += 1
        strata[(language or 'unresolved', persona['background'].get('country', ''))].append(persona['id'])

    names = ('ultrachat', 'nemotron')
    quota = {n: sum(1 for i in range(len(bank)) if i % 2 == k) for k, n in enumerate(names)}
    seen = {'ids': set(), 'parents': set(), 'prefixes': set()}
    sources = {
        'ultrachat': sample_source('ultrachat', a.ultrachat, a.ultrachat_split, a.ultrachat_revision, 'mit',
                                   quota['ultrachat'], seen),
        'nemotron': sample_source('nemotron', a.nemotron, a.nemotron_split, a.nemotron_revision, 'odc-by-1.0',
                                  quota['nemotron'], seen),
    }

    queues = [deque(sorted(ids, key=lambda i: digest([SEED, 'persona', i])))
              for _, ids in sorted(strata.items(), key=lambda kv: digest([SEED, kv[0]]))]
    order = []
    while queues:
        for q in queues:
            order.append(q.popleft())
        queues = [q for q in queues if q]

    os.makedirs(a.out_dir, exist_ok=True)
    for offset in range(0, len(order), CHUNK):
        with open(os.path.join(a.out_dir, f'{offset // CHUNK:04d}.jsonl'), 'w', encoding='utf-8') as f:
            for i, identity in enumerate(order[offset:offset + CHUNK], offset):
                source = sources[names[i % 2]].popleft()
                language, basis = profiles[identity]
                rec = {'pair_key': digest([PAIR_NAMESPACE, SEED, identity, source['source_id']]), 'persona_id': identity,
                       'target_language': language, 'language_resolution': basis, **source,
                       'seed': SEED, 'assignment_index': i}
                f.write(json.dumps(rec, ensure_ascii=False, separators=(',', ':')) + '\n')
                counts['source/' + source['source_name']] += 1
    print(json.dumps({'pairs': len(order), **dict(sorted(counts.items()))}, indent=1), flush=True)


if __name__ == '__main__':
    main()
