#!/usr/bin/env python3
"""Real messy WildChat prompts for the pairwise comparison: 500 English and 500 non-English first user turns of
WildChat conversations that no training arm uses. Candidates are WildChat conversations that are not the seed of any
language-matched released conversation (every arm trains on language-matched conversations only; in the paper the
pool was the WildChat seeds of the cross-lingual setting), and prompts identical to a training user turn are excluded.
Messy = starts lowercase or has no final punctuation, or mixes Latin with another script (code-switching).
Dropped: under 15 or over 800 characters, duplicates, e-mail addresses, phone-number-like digit runs, URLs, a short
list of sexual / violent terms, and assistant-style boilerplate (likely copied model output).

Candidate source: --seed-shards (pipeline seed records with `source_id`, `source_name`, `seed_language`,
`conversation`) or --wildchat (hub id or local parquet of WildChat, default allenai/WildChat-4.8M; toxic or redacted
conversations are skipped). Writes <data-dir>/wildchat.jsonl (bench `wildchat`, variant `clean`) and
<data-dir>/wildchat_stats.json.

  python -m personafactory.downstream.eval.wildchat_prompts --data-dir $PF_DATA_DIR/downstream_eval \
      --train $PF_OUT_DIR/downstream/data/A0_source.jsonl --release swiss-ai/PersonaFactory
"""
import argparse, ast, collections, json, os, random, re

from personafactory.downstream.common import HF_REPO, iter_rows, load_release

BLOCK = re.compile(r'\b(sex|sexy|porn|nsfw|nude|naked|fuck|rape|kill|murder|suicide|gore|erotic|fetish|hentai|boobs?|penis|vagina)\b', re.I)
BOILER = re.compile(r"as an ai|i'm sorry, but|i cannot (help|assist)|language model|certainly! here", re.I)
PII = re.compile(r'[\w.+-]+@[\w-]+\.\w+|\+?\d[\d\s()-]{8,}\d|https?://')
LATIN = re.compile(r'[A-Za-z]')
OTHER = re.compile(r'[^\x00-\u024f\s\d\W]')


def messy(t):
    first = next((c for c in t if c.isalpha()), '')
    lower = first.islower()
    nopunct = t[-1:] not in '.!?\u3002\uff01\uff1f)"\''
    mixed = bool(LATIN.search(t)) and bool(OTHER.search(t))
    return lower or nopunct or mixed


def candidates(a):
    """(source_id, language, first user turn) of WildChat conversations."""
    if a.seed_shards:
        for fp in a.seed_shards:
            for s in iter_rows(fp, None):
                if (s.get('source_name') or (s.get('source_id') or '').split(':')[0]) != 'wildchat':
                    continue
                conv = s['conversation']
                conv = ast.literal_eval(conv) if isinstance(conv, str) else conv
                yield s.get('source_id') or s.get('seed_id'), s.get('seed_language') or 'English', \
                    next((m['content'] for m in conv if m['role'] == 'user'), '')
        return
    for row in iter_rows(a.wildchat, None):
        conv = row.get('conversation') or []
        if row.get('toxic') or row.get('redacted') or any(m.get('toxic') or m.get('redacted') for m in conv):
            continue
        tid = next((m.get('turn_identifier') for m in conv if m.get('turn_identifier') is not None), None)
        yield f"wildchat:{row.get('conversation_hash')}:{tid}", row.get('language') or 'English', \
            next((m.get('content') or '' for m in conv if m.get('role') == 'user'), '')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data-dir', required=True)
    ap.add_argument('--train', nargs='+', required=True, help='arm source JSONL(s) whose user turns are excluded')
    ap.add_argument('--release', default=HF_REPO, help='released chats; seeds of language-matched conversations are excluded')
    ap.add_argument('--seed-shards', nargs='*', default=[])
    ap.add_argument('--wildchat', default='allenai/WildChat-4.8M')
    ap.add_argument('--per-group', type=int, default=500)
    a = ap.parse_args()
    rng = random.Random('pf-downstream-wildchat')
    train_users = set()
    for fp in a.train:
        for l in open(fp, encoding='utf-8'):
            for m in json.loads(l)['messages']:
                if m['role'] == 'user':
                    train_users.add(m['content'].strip())
    used = {r['source_id'] for r in load_release(a.release) if r['setting'] == 'language_matched' and r['source_id']}
    pools, st = {'en': [], 'other': []}, collections.Counter()
    seen = set()
    for sid, lang, t in candidates(a):
        t = (t or '').strip()
        st['seen'] += 1
        if sid in used:
            st['drop/seed_of_training_setting'] += 1
            continue
        if not (15 <= len(t) <= 800) or t in seen:
            st['drop/length_or_dup'] += 1
            continue
        seen.add(t)
        if t in train_users:
            st['drop/in_training'] += 1
            continue
        if BLOCK.search(t) or BOILER.search(t) or PII.search(t):
            st['drop/filter'] += 1
            continue
        if not messy(t):
            st['drop/not_messy'] += 1
            continue
        pools['en' if lang in (None, 'English') else 'other'].append((sid, lang, t))
    rows = []
    for k in ('en', 'other'):
        pick = rng.sample(pools[k], min(a.per_group, len(pools[k])))
        st[f'pool/{k}'] = len(pools[k])
        for sid, lang, t in pick:
            rows.append({'bench': 'wildchat', 'id': sid, 'variant': 'clean', 'prompt': t, 'meta': {'lang': lang, 'group': k}})
    with open(os.path.join(a.data_dir, 'wildchat.jsonl'), 'w', encoding='utf-8') as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    st['selected'] = len(rows)
    st.update({f'lang/{k}': v for k, v in collections.Counter(r['meta']['lang'] for r in rows).most_common(12)})
    json.dump(dict(st), open(os.path.join(a.data_dir, 'wildchat_stats.json'), 'w'), indent=1)
    print(json.dumps(dict(st), indent=1))


if __name__ == '__main__':
    main()
