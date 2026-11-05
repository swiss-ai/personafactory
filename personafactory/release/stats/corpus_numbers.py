#!/usr/bin/env python3
"""Corpus composition and judge-free fidelity numbers of the release (corpus composition table and the full-corpus judge-free fidelity table).

Covers the composition table and the judge-free fidelity table except LaBSE similarity, which needs a
sentence-transformer and is computed by the evaluation package. Style adherence joins each record back to
the persona bank for its declared style targets. Writes <release-dir>/corpus_numbers.json.

  python -m personafactory.release.stats.corpus_numbers --release-dir ./release_out --bank ./release_out/persona_bank.jsonl --workers 60
"""
import argparse, collections, glob, json, os, re, statistics as st, sys, unicodedata
from multiprocessing import Pool

NUM = re.compile(r'(?<![\w])[-+]?\d+(?:[.,]\d+)*%?')
CODE = re.compile(r'```.*?```|`[^`\n]+`|https?://\S+|(?:/[\w.-]+){2,}|\b[A-Za-z_]+\(\)|--[A-Za-z][\w-]+')
QUOTE = re.compile(r'"[^"\n]{2,}"|“[^”\n]{2,}”|«[^»\n]{2,}»|「[^」\n]{2,}」')
EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿⬀-⯿]')
KAOMOJI = re.compile(r'\(\s*[^\w\s]{1,4}\s*[_\-^]\s*[^\w\s]{1,4}\s*\)|orz')
EMOTICON = re.compile(r'[:;=]-?[)(DPpOo3]|<3')
BANK = None


def tokens(text):
    """Multilingual tokens: CJK ideographs are atomic, other scripts split on non-word chars."""
    out, buf = [], []
    for ch in text or '':
        if '぀' <= ch <= '鿿' or '가' <= ch <= '힯':
            if buf:
                out.append(''.join(buf)); buf = []
            out.append(ch)
        elif ch.isalnum() or ch in "'’-":
            buf.append(ch.lower())
        else:
            if buf:
                out.append(''.join(buf)); buf = []
    if buf:
        out.append(''.join(buf))
    return out


def edit_ratio(a, b, cap=2000):
    a, b = (a or '')[:cap], (b or '')[:cap]
    if not a and not b:
        return 0.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / max(len(a), len(b), 1)


def init(bank_path):
    global BANK
    BANK = {}
    for line in open(bank_path, errors='ignore'):
        try:
            p = json.loads(line)
        except Exception:
            continue
        s = (p.get('style') or {}).get('chatting_style_structured') or {}
        BANK[p['id']] = {k: str(s.get(k) or '').lower() for k in
                         ('emoji_use', 'capitalization', 'punctuation')}


def handle(raw):
    try:
        r = json.loads(raw)
    except Exception:
        return None
    src = r.get('source_text') or ''
    out = next((m.get('content') for m in r.get('conversation') or [] if m.get('role') == 'user'), '')
    if not out:
        return None
    same_lang = r.get('language_mode') == 'free'
    st_ = {'mode': r.get('language_mode'), 'lang': r.get('text_language'),
           'responder': r.get('responder'), 'source_name': r.get('source_name'),
           'turns': r.get('num_turns') or len(r.get('conversation') or []),
           'basis': r.get('match_basis'), 'chars': len(out), 'src_chars': len(src)}
    if src and same_lang:
        ts, to = set(tokens(src)), set(tokens(out))
        if ts or to:
            st_['jaccard'] = 1 - len(ts & to) / max(1, len(ts | to))
        core = {t for t in tokens(src) if len(t) > 2 or not t.isascii()}
        if core:
            st_['core_retention'] = len(core & set(tokens(out))) / len(core)
        st_['edit'] = edit_ratio(src, out)
    for name, rx in (('numbers', NUM), ('code', CODE), ('quotes', QUOTE)):
        s = set(m.group(0).strip() for m in rx.finditer(src))
        if s:
            st_[name] = len(s & set(m.group(0).strip() for m in rx.finditer(out))) / len(s)
    tgt = BANK.get(r.get('persona_id'))
    if tgt:
        has_emo = bool(EMOJI.search(out) or EMOTICON.search(out) or KAOMOJI.search(out))
        want = tgt['emoji_use']
        if 'none' in want or 'never' in want:
            st_['emoji_ok'] = not has_emo
        elif want:
            st_['emoji_ok'] = has_emo
        sents = [x for x in re.split(r'[.!?\n]+', out) if x.strip()]
        if sents:
            caps = sum(1 for x in sents if x.strip()[:1].isupper()) / len(sents)
            low = 'lower' in tgt['capitalization']
            if tgt['capitalization']:
                st_['caps_ok'] = (caps <= 0.3) if low else (caps >= 0.7)
        p = tgt['punctuation']
        if p:
            ends = out.rstrip()[-1:] in '.!?'
            st_['punct_ok'] = (not ends) if ('minimal' in p or 'drop' in p) else ends
    return st_


def lines(pattern):
    for fp in sorted(glob.glob(pattern)):
        with open(fp, 'rb') as f:
            for raw in f:
                if raw.strip():
                    yield raw.decode('utf-8', 'ignore')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release-dir', required=True)
    ap.add_argument('--bank', default=os.environ.get('PF_BANK'), help='persona bank JSONL (or PF_BANK)')
    ap.add_argument('--out', default=None, help='default: <release-dir>/corpus_numbers.json')
    ap.add_argument('--workers', type=int, default=30)
    args = ap.parse_args()
    data = os.path.join(args.release_dir, 'data', '*.jsonl')
    out_path = args.out or os.path.join(args.release_dir, 'corpus_numbers.json')

    rows = []
    with Pool(args.workers, initializer=init, initargs=(args.bank,)) as pool:
        for i, r in enumerate(pool.imap_unordered(handle, lines(data), chunksize=64), 1):
            if r:
                rows.append(r)
            if i % 50000 == 0:
                print(i, flush=True)
    print('scored', len(rows), flush=True)

    def mean(key, sel=None):
        v = [r[key] for r in (sel or rows) if key in r]
        return round(sum(v) / len(v), 4) if v else None

    def pctok(key, sel=None):
        v = [r[key] for r in (sel or rows) if key in r]
        return round(100 * sum(v) / len(v), 1) if v else None

    free = [r for r in rows if r['mode'] == 'free']
    multi = [r for r in rows if r['mode'] == 'multilingual']
    langs = collections.Counter(r['lang'] for r in rows)
    ne = {k: v for k, v in langs.items() if k not in ('English', 'TooShort', 'Unknown')}

    out = {
        'composition': {
            'conversations': len(rows),
            'turns': sum(r['turns'] for r in rows),
            'by_mode': {'multilingual': len(multi), 'free': len(free)},
            'by_source': dict(collections.Counter(str(r['source_name']) for r in rows)),
            'by_responder': dict(collections.Counter(str(r['responder']) for r in rows).most_common(8)),
            'turn_depth_mean': round(st.mean(r['turns'] for r in rows), 2),
            'turn_depth_dist': dict(collections.Counter(min(r['turns'], 6) for r in rows)),
            'match_basis': dict(collections.Counter(str(r['basis']) for r in rows).most_common(8)),
            'text_languages': len(ne) + 1,
            'english_share_pct': round(100 * langs.get('English', 0) / len(rows), 1),
            'non_english_records': sum(ne.values()),
            'languages_ge_1000': sum(1 for v in ne.values() if v >= 1000),
            'languages_ge_100': sum(1 for v in ne.values() if v >= 100),
        },
        'fidelity_transformation_depth_same_language': {
            'token_jaccard_distance': mean('jaccard'),
            'normalized_edit_distance': mean('edit'),
            'core_vocab_retention_pct': round(100 * mean('core_retention'), 1) if mean('core_retention') else None,
            'n': sum(1 for r in rows if 'jaccard' in r),
        },
        'fidelity_constraint_retention': {
            'numbers_intact_pct': round(100 * mean('numbers'), 1),
            'code_intact_pct': round(100 * mean('code'), 1),
            'quoted_literals_intact_pct': round(100 * mean('quotes'), 1),
            'by_mode': {'multilingual': {k: round(100 * mean(k, multi), 1) for k in ('numbers', 'code', 'quotes')},
                        'free': {k: round(100 * mean(k, free), 1) for k in ('numbers', 'code', 'quotes')}},
        },
        'fidelity_style_adherence': {
            'emoji_register_pct': pctok('emoji_ok'),
            'capitalization_register_pct': pctok('caps_ok'),
            'punctuation_register_pct': pctok('punct_ok'),
            'n_with_bank_targets': sum(1 for r in rows if 'emoji_ok' in r or 'caps_ok' in r),
        },
        'median_length_ratio': round(st.median([r['chars'] / r['src_chars'] for r in rows if r['src_chars']]), 3),
    }
    json.dump(out, open(out_path, 'w'), ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
