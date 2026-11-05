#!/usr/bin/env python3
"""Seed pool for the seed-first part of the corpus: one conversation per seed, each seed used once, with a
setting (language-matched `free` or cross-lingual `multilingual`) drawn per seed. Personas are assigned later
(augmentation.select_personas --seeds-dir).

Sources, in priority order:
  1. UltraChat, full release (stingning/ultrachat, jsonl {"id", "data": [u, a, u, a, ...]}); conversations whose
     assistant turns contain an AI disclaimer ("as an AI", "language model", "OpenAI", ...) are dropped.
  2. Nemotron-Instruction-Following-Chat-v1, split chat_if (jsonl): licence odc-by-1.0 only; conversations with tools
     are dropped; message fields other than role/content are stripped; <think> blocks are removed from assistant turns.
  3. WildChat-4.8M (allenai/WildChat-4.8M, parquet): toxic == False and redacted == False on the row and on every
     turn, conversation_hash dedup, first user message >= 5 words (>= 10 characters for unspaced scripts); the
     dataset's language label is kept as `seed_language`.
Common filters (as augmentation.prepare_pairs): strict user/assistant alternation (an optional empty leading system
turn is dropped, a non-empty one rejects the conversation), no empty message, the first 3 user turns are kept with
their replies, <= 1000 user words in the kept turns, <= 45,000 kept characters.

Dedup and exclusion keys on the first user message: exact = sha1 of the NFKC-casefolded, whitespace-collapsed text;
near = sha1 of its first 200 alphanumeric characters. Seeds whose key matches any conversation passed with
--exclude-* (seeds already used elsewhere in the corpus) are excluded, and duplicates across sources are removed in
priority order.

Allocation: the needed number of seeds is (free + multilingual attempts) x margin; sources are filled in priority
order, each by a fixed hash rank of the seed id. The setting is `free` with probability free / (free + multilingual)
by the same rank.

Phases: (A) parallel scan of sources and exclusion inputs -> candidate files in <work>/cand; (B) dedup and exclusion;
(C) allocation and setting; (D) shards <work>/shards/{mode}-{source}-NNNN.jsonl (2,000 rows) + <work>/manifest.json.
Shard record:
  {pair_key, seed_id, source_id, source_name, mode, seed_language, conversation, split, source_user_words,
   retained_user_turns, source_truncated, source_metadata}
  pair_key = sha256 digest of [ID_NAMESPACE, seed_id]; split (train / validation / test = 90 / 5 / 5) is a hash of
  the user prefix (as prepare_pairs.source_split).

Run (CPU node, many cores):
  python -m personafactory.augmentation.prepare_seeds --ultrachat 'sources/ultrachat/train_*.jsonl' \\
      --nemotron sources/nemotron/chat_if.jsonl --wildchat 'sources/wildchat/data/train-*.parquet' \\
      --exclude-release "$PAIRS_RELEASE/data/*.jsonl" --exclude-pairs ./data/pairs --work ./data/seeds --procs 128
"""
import argparse, collections, glob, hashlib, json, math, os, re, time, unicodedata
from multiprocessing import Pool

from personafactory.augmentation.prepare_pairs import digest, source_split
from personafactory.common import lid

# Hash salt of the seed pool: seed ranks, pair keys and conversation ids derive from it.
SALT = 'personafactory-seeds'
ID_NAMESPACE = SALT + '-id'
HOLDOUT_SALT = SALT + '-holdout'  # rank of the held-out sample (select_personas --holdout-*)
ORDER = ['ultrachat', 'nemotron', 'wildchat']
SHARD = 2000
MAX_TURNS, MAX_WORDS, MAX_CHARS = 3, 1000, 45000

DISCLAIMER = re.compile('|'.join([
    r"\bas an ai\b", r"\bas an a\.i\.", r"\bas a language model\b", r"\bas an artificial intelligence\b",
    r"\bi'?m an ai\b", r"\bi am an ai\b", r"\bi'?m just an ai\b", r"\bi am just an ai\b", r"\bi am an artificial\b",
    r"\bai language model\b", r"\bai assistant,? i\b", r"\bi'?m a language model\b", r"\bi am a language model\b",
    r"\bi (?:do not|don'?t) have (?:personal |any )?(?:opinions|feelings|emotions|beliefs|preferences|experiences)\b",
    r"\bi (?:do not|don'?t) have the ability to (?:browse|access the internet|feel)\b",
    r"\bi (?:cannot|can'?t|am unable to) (?:browse|access) (?:the internet|the web|external websites|real-time)\b",
    r"\bi (?:do not|don'?t) have (?:access to|the ability to access) (?:the internet|real-time|current|external)\b",
    r"\bmy (?:knowledge cutoff|training data)\b", r"\bi (?:am|'m) not capable of (?:having|feeling)\b",
    r"\bi (?:cannot|can'?t) (?:provide|give) (?:personal )?opinions\b", r"\bopenai\b", r"\bchatgpt\b"]), re.I)
UNSPACED = {'Chinese', 'Japanese', 'Korean', 'Thai', 'Lao', 'Khmer', 'Burmese', 'Tibetan'}


def norm_text(t):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', t or '').casefold()).strip()


def kexact(t):
    return hashlib.sha1(norm_text(t).encode()).hexdigest()[:16]


def knear(t):
    a = re.sub(r'[\W_]+', '', norm_text(t))[:200]
    return 'n' + hashlib.sha1(a.encode()).hexdigest()[:15]


def keys_of(t):
    return kexact(t), knear(t)


def view(messages):
    """Retained prefix of {role, content} messages (leading empty system turn dropped) with the common filters."""
    if not isinstance(messages, list) or not messages:
        raise ValueError('missing_messages')
    kept, users, expected = [], 0, 'user'
    for i, m in enumerate(messages):
        role, content = m.get('role'), m.get('content')
        if not isinstance(content, str):
            raise ValueError('nontext_message')
        if role == 'system' and i == 0:
            if content.strip():
                raise ValueError('nonempty_system')
            continue
        if role != expected:
            raise ValueError('invalid_role_sequence')
        if not content.strip():
            raise ValueError('empty_message')
        if role == 'user':
            users += 1
            expected = 'assistant'
        else:
            expected = 'user'
        if users <= MAX_TURNS:
            kept.append({'role': role, 'content': content})
    if not users:
        raise ValueError('no_user_turns')
    utexts = [m['content'] for m in kept if m['role'] == 'user']
    words = sum(len(t.split()) for t in utexts)
    if words > MAX_WORDS:
        raise ValueError('too_many_user_words')
    if sum(len(m['content']) for m in kept) > MAX_CHARS:
        raise ValueError('too_many_retained_characters')
    return {'conversation': kept, 'retained_user_turns': len(utexts), 'original_user_turns': users,
            'source_user_words': words, 'source_truncated': users > MAX_TURNS,
            'source_user_prefix_sha256': digest([re.sub(r'\s+', ' ', t).strip() for t in utexts])}


DEC = json.JSONDecoder()
THINK = re.compile(r'<think>.*?</think>\s*', re.S)


def rows_jsonl(path, start, end):
    """JSON records of the byte range [start, end) of a jsonl file (start == end == 0: whole file)."""
    with open(path, 'rb') as f:
        if start:
            f.seek(start - 1)
            f.readline()
        while f.tell() < end or (start == 0 and end == 0):
            line = f.readline()
            if not line:
                break
            s = line.decode('utf-8').strip()
            while s:  # the upstream UltraChat files contain a line with two records glued together; yield both
                obj, k = DEC.raw_decode(s)
                yield obj
                s = s[k:].lstrip()


def ranges(path, n):
    size = os.path.getsize(path)
    step = math.ceil(size / n)
    return [(path, i * step, min(size, (i + 1) * step)) for i in range(n) if i * step < size]


def scan(task):
    """Phase A worker: one (source, path, start, end, out) chunk -> candidate file + stats."""
    source, path, start, end, out = task
    st = collections.Counter()
    fo = open(out, 'w', encoding='utf-8')
    if source == 'wildchat':
        import pyarrow.parquet as pq
        cols = ['conversation_hash', 'conversation', 'language', 'toxic', 'redacted', 'turn', 'model']
        it = (r for b in pq.ParquetFile(path).iter_batches(batch_size=1024, columns=cols) for r in b.to_pylist())
    else:
        it = rows_jsonl(path, start, end)
    for row in it:
        st['raw'] += 1
        try:
            lang = None
            if source == 'ultrachat':
                data = row.get('data') or []
                msgs = [{'role': ('user', 'assistant')[i % 2], 'content': t} for i, t in enumerate(data)]
                sid = 'ultrachat:' + str(row.get('id'))
                lang = 'English'
            elif source == 'nemotron':
                if str(row.get('license', '')).lower() != 'odc-by-1.0':
                    raise ValueError('license')
                if row.get('tools') not in (None, [], '[]', ''):
                    raise ValueError('tool_conversation')
                raw = row.get('messages') or []
                if any(set(m) - {'role', 'content'} for m in raw if isinstance(m, dict)):
                    st['stripped_extra_fields'] += 1
                msgs = [{'role': m.get('role'), 'content': THINK.sub('', m.get('content') or '') if m.get('role') == 'assistant'
                         else m.get('content')} for m in raw if isinstance(m, dict)]
                sid = 'nemotron:' + str(row.get('uuid'))
            else:
                if row.get('toxic') or row.get('redacted'):
                    raise ValueError('toxic_or_redacted')
                conv = row.get('conversation') or []
                if any(m.get('toxic') or m.get('redacted') for m in conv):
                    raise ValueError('toxic_or_redacted_turn')
                msgs = [{'role': m.get('role'), 'content': m.get('content')} for m in conv]
                tid = next((m.get('turn_identifier') for m in conv if m.get('turn_identifier') is not None), None)
                sid = f"wildchat:{row.get('conversation_hash')}:{tid}"
                lang = row.get('language')
            v = view(msgs)
            asst = [m['content'] for m in v['conversation'] if m['role'] == 'assistant']
            first = v['conversation'][0]['content']
            if source == 'ultrachat' and any(DISCLAIMER.search(a) for a in asst):
                raise ValueError('ai_disclaimer')
            if source == 'wildchat':
                short = (len(first.strip()) < 10) if lid.norm(lang or '') in UNSPACED else (len(first.split()) < 5)
                if short:
                    raise ValueError('short_first_message')
        except ValueError as e:
            st['drop/' + str(e)[:50]] += 1
            continue
        ke, kn = keys_of(first)
        rec = {'seed_id': sid, 'source_name': source, 'ke': ke, 'kn': kn,
               'chash': row.get('conversation_hash') if source == 'wildchat' else None,
               'seed_language': lang, **v}
        if source == 'nemotron':
            rec['source_metadata'] = {k: row.get(k) for k in ('capability_target', 'reasoning', 'used_in') if k in row}
        if source == 'wildchat':
            rec['source_metadata'] = {'model': row.get('model'), 'turn': row.get('turn')}
        fo.write(json.dumps(rec, ensure_ascii=False) + '\n')
        st['filtered'] += 1
    fo.close()
    return task, dict(st)


def used_chunk(task):
    """Phase A worker for the exclusion inputs: exact + near keys of first user messages."""
    kind, path, start, end = task
    ks, st = set(), collections.Counter()
    if kind == 'responses':  # pipeline outputs with per-turn details (metadata.turns_detail)
        for r in rows_jsonl(path, start, end):
            st['responses_rows'] += 1
            tds = (r.get('metadata') or {}).get('turns_detail') or []
            t = tds[0].get('user_message_original') if tds else None
            if not t:
                st['responses_no_original'] += 1
                continue
            ks.update(keys_of(t))
    elif kind == 'release':  # released records (source_text)
        for fp in sorted(glob.glob(path)):
            for l in open(fp, encoding='utf-8'):
                r = json.loads(l)
                st['release_rows'] += 1
                ks.update(keys_of(r.get('source_text') or ''))
    elif kind == 'pairs':  # seed-pair shards (conversation)
        for fp in glob.glob(os.path.join(path, '*.jsonl')):
            for l in open(fp, encoding='utf-8'):
                if l.strip():
                    p = json.loads(l)
                    st['pair_rows/' + path] += 1
                    ks.update(keys_of(next((m['content'] for m in p['conversation'] if m['role'] == 'user'), '')))
    return ks, dict(st)


def h(*parts):
    return int(hashlib.sha256('|'.join(map(str, parts)).encode()).hexdigest(), 16)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ultrachat', required=True, help='glob of the full UltraChat jsonl files (train_*.jsonl)')
    ap.add_argument('--nemotron', required=True, help='Nemotron-Instruction-Following-Chat-v1 chat_if.jsonl')
    ap.add_argument('--wildchat', required=True, help='glob of the WildChat-4.8M parquet files')
    ap.add_argument('--exclude-release', nargs='*', default=[], help='globs of released records (source_text) to exclude')
    ap.add_argument('--exclude-pairs', nargs='*', default=[], help='directories of seed-pair shards to exclude')
    ap.add_argument('--exclude-responses', nargs='*', default=[],
                    help='pipeline output files (metadata.turns_detail) whose seeds are excluded')
    ap.add_argument('--work', default=os.path.join(os.environ.get('PF_DATA_DIR', './data'), 'seeds'))
    ap.add_argument('--free-attempts', type=int, default=710_000)
    ap.add_argument('--multilingual-attempts', type=int, default=966_000)
    ap.add_argument('--margin', type=float, default=1.05)
    ap.add_argument('--procs', type=int, default=128)
    a = ap.parse_args()
    t0 = time.time()
    src = {'ultrachat': sorted(glob.glob(a.ultrachat)), 'nemotron': sorted(glob.glob(a.nemotron)),
           'wildchat': sorted(glob.glob(a.wildchat))}
    assert all(src.values()), {k: len(v) for k, v in src.items()}
    cand_dir, shard_dir = os.path.join(a.work, 'cand'), os.path.join(a.work, 'shards')
    os.makedirs(cand_dir, exist_ok=True)
    os.makedirs(shard_dir, exist_ok=True)
    scan_tasks = []
    for p in src['ultrachat']:
        stem = os.path.basename(p)[:-len('.jsonl')]
        scan_tasks += [('ultrachat',) + r + (os.path.join(cand_dir, f'ultrachat-{stem}-{i:02d}.jsonl'),)
                       for i, r in enumerate(ranges(p, 8))]
    for k, p in enumerate(src['nemotron']):
        scan_tasks += [('nemotron',) + r + (os.path.join(cand_dir, f'nemotron-{i if k == 0 else f"{k}-{i}":0>2}.jsonl'),)
                       for i, r in enumerate(ranges(p, 32))]
    scan_tasks += [('wildchat', p, 0, 0, os.path.join(cand_dir, f"wildchat-{os.path.basename(p)[:-len('.parquet')]}.jsonl"))
                   for p in src['wildchat']]
    used_tasks = ([('responses',) + r for f in a.exclude_responses for r in ranges(f, 32)]
                  + [('release', g, 0, 0) for g in a.exclude_release] + [('pairs', d, 0, 0) for d in a.exclude_pairs])
    scan_stats = collections.defaultdict(collections.Counter)
    used, used_stats = set(), collections.Counter()
    with Pool(a.procs) as pool:
        ru = pool.map_async(used_chunk, used_tasks, chunksize=1)
        for task, st in pool.imap_unordered(scan, scan_tasks, chunksize=1):
            scan_stats[task[0]].update(st)
        for ks, st in ru.get():
            used |= ks
            used_stats.update(st)
    print('phase A done', round(time.time() - t0), 's; excluded keys', len(used), json.dumps(used_stats), flush=True)

    # Phase B: priority-ordered dedup + exclusion
    seen, seen_chash = set(), set()
    stats = {s: collections.Counter() for s in ORDER}
    accepted = {s: [] for s in ORDER}  # (rank, candidate file, line no)
    for s in ORDER:
        for fp in sorted(glob.glob(os.path.join(cand_dir, f'{s}-*.jsonl'))):
            for ln, l in enumerate(open(fp, encoding='utf-8')):
                r = json.loads(l)
                c = stats[s]
                if r['ke'] in used or r['kn'] in used:
                    c['excluded_already_used'] += 1
                    continue
                if r['chash'] and r['chash'] in seen_chash:
                    c['dup_conversation_hash'] += 1
                    continue
                if r['ke'] in seen:
                    c['dup_exact_first_message'] += 1
                    continue
                if r['kn'] in seen:
                    c['dup_near_first_message'] += 1
                    continue
                seen.add(r['ke'])
                seen.add(r['kn'])
                if r['chash']:
                    seen_chash.add(r['chash'])
                c['unused_unique'] += 1
                accepted[s].append((h(SALT + '-rank', r['seed_id']), fp, ln))
    print('phase B done', round(time.time() - t0), 's', {s: stats[s]['unused_unique'] for s in ORDER}, flush=True)

    # Phase C: allocation in priority order, setting by rank
    need = int(round((a.free_attempts + a.multilingual_attempts) * a.margin))
    alloc, left = {}, need
    for s in ORDER:
        acc = sorted(accepted[s])
        take = acc[:max(0, left)]
        alloc[s] = take
        left -= len(take)
        stats[s]['allocated'] = len(take)
        stats[s]['unallocated'] = len(acc) - len(take)
    if left > 0:
        print('WARNING: seed shortfall', left, flush=True)
    p_free = a.free_attempts / (a.free_attempts + a.multilingual_attempts)
    chosen = collections.defaultdict(dict)  # candidate file -> {line no: mode}
    for s in ORDER:
        for rank, fp, ln in alloc[s]:
            chosen[fp][ln] = 'free' if (rank % 1_000_000) / 1_000_000 < p_free else 'multilingual'

    # Phase D: shards per (mode, source) in candidate-file order
    writers, counts, shard_list = {}, collections.Counter(), []

    def write(rec):
        k = (rec['mode'], rec['source_name'])
        w = writers.get(k)
        if w is None or w[1] >= SHARD:
            if w:
                w[0].close()
            n = sum(1 for x in shard_list if x.startswith(f'{k[0]}-{k[1]}-'))
            name = f'{k[0]}-{k[1]}-{n:04d}.jsonl'
            shard_list.append(name)
            w = writers[k] = [open(os.path.join(shard_dir, name), 'w', encoding='utf-8'), 0]
        w[0].write(json.dumps(rec, ensure_ascii=False) + '\n')
        w[1] += 1

    for s in ORDER:
        for fp in sorted(glob.glob(os.path.join(cand_dir, f'{s}-*.jsonl'))):
            want = chosen.get(fp)
            if not want:
                continue
            for ln, l in enumerate(open(fp, encoding='utf-8')):
                mode = want.get(ln)
                if not mode:
                    continue
                r = json.loads(l)
                rec = {'pair_key': digest([ID_NAMESPACE, r['seed_id']]), 'seed_id': r['seed_id'], 'source_id': r['seed_id'],
                       'source_name': s, 'mode': mode, 'seed_language': r['seed_language'], 'conversation': r['conversation'],
                       'split': source_split(r['source_user_prefix_sha256']),
                       'source_user_words': r['source_user_words'], 'retained_user_turns': r['retained_user_turns'],
                       'source_truncated': r['source_truncated'], 'source_metadata': r.get('source_metadata')}
                write(rec)
                counts[f'{mode}/{s}'] += 1
                stats[s]['allocated_' + mode] += 1
                if r['seed_language']:
                    counts[f'lang/{s}/{r["seed_language"]}'] += 1
    for w in writers.values():
        w[0].close()
    manifest = {'need_attempts': need, 'free_attempts_target': a.free_attempts,
                'multilingual_attempts_target': a.multilingual_attempts, 'margin': a.margin, 'p_free': p_free,
                'shard_rows': SHARD, 'sources': src, 'priority': ORDER,
                'filters': {'max_user_turns_kept': MAX_TURNS, 'max_user_words': MAX_WORDS, 'max_kept_chars': MAX_CHARS,
                            'ultrachat_ai_disclaimer_regex': DISCLAIMER.pattern,
                            'wildchat': 'toxic==False, redacted==False (row and turn), conversation_hash dedup, first user msg >= 5 words (>= 10 chars unspaced scripts)',
                            'nemotron': 'licence odc-by-1.0, tools -> drop, non-empty system -> drop, non role/content fields stripped, <think> stripped'},
                'excluded': {'keys': len(used), **dict(used_stats)},
                'scan_stats': {k: dict(v) for k, v in scan_stats.items()},
                'dedup_exclusion_allocation': {k: dict(v) for k, v in stats.items()},
                'shard_counts': {k: v for k, v in counts.items() if not k.startswith('lang/')},
                'seed_language': {k: v for k, v in sorted(counts.items(), key=lambda kv: -kv[1]) if k.startswith('lang/')},
                'shards': shard_list, 'elapsed_s': round(time.time() - t0)}
    json.dump(manifest, open(os.path.join(a.work, 'manifest.json'), 'w'), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in manifest.items() if k not in ('shards', 'seed_language', 'sources')}, indent=1), flush=True)


if __name__ == '__main__':
    main()
