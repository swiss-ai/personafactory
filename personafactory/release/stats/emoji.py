#!/usr/bin/env python3
"""Emoji incidence in released user turns, by language, mode and persona emoji setting.

The baseline is the source (real-user) turn: how often real users in the seed logs use emoji, versus the
rewritten turn.
Writes <release-dir>/emoji_audit.json.

  python -m personafactory.release.stats.emoji --release-dir ./release_out --bank ./release_out/persona_bank.jsonl
"""
import argparse, collections, glob, json, os, re
from multiprocessing import Pool

from personafactory.release.emoji_utils import EMOJI  # pictographic emoji; plain symbols like ✓ ★ → not counted

EMOTICON = re.compile(r'(?<!\w)[:;=]-?[)(DP](?!\w)|<3')
BANK = None


def init(path):
    global BANK
    BANK = {}
    for line in open(path, errors='ignore'):
        try:
            p = json.loads(line)
        except Exception:
            continue
        s = (p.get('style') or {}).get('chatting_style_structured') or {}
        BANK[p['id']] = str(s.get('emoji_use') or '').lower()


def tier(raw):
    if not raw:
        return 'unknown'
    for k in ('none', 'never'):
        if k in raw:
            return 'none'
    for k in ('rare', 'occasional', 'functional'):
        if k in raw:
            return 'rare'
    if 'emoticon' in raw:
        return 'emoticons'
    return 'frequent'


def handle(raw):
    try:
        r = json.loads(raw)
    except Exception:
        return None
    users = [m.get('content') or '' for m in r.get('conversation') or [] if m.get('role') == 'user']
    if not users:
        return None
    n_emo = [len(EMOJI.findall(u)) for u in users]
    return {'lang': r.get('text_language'),
            'mode': r.get('language_mode'), 'tier': tier(BANK.get(r.get('persona_id'), '')),
            'turns': len(users), 'turns_emo': sum(1 for n in n_emo if n), 'emo_total': sum(n_emo),
            'any': any(n_emo), 'src_emo': bool(EMOJI.search(r.get('source_text') or '')),
            'emoticon': any(EMOTICON.search(u) for u in users)}


def lines(pattern):
    for fp in sorted(glob.glob(pattern)):
        with open(fp, 'rb') as f:
            for raw in f:
                if raw.strip():
                    yield raw.decode('utf-8', 'ignore')


def agg(rows):
    n = len(rows)
    t = sum(r['turns'] for r in rows)
    return {'n': n, 'conv_with_emoji_pct': round(100 * sum(r['any'] for r in rows) / n, 1) if n else None,
            'turns_with_emoji_pct': round(100 * sum(r['turns_emo'] for r in rows) / t, 1) if t else None,
            'emoji_per_emoji_turn': round(sum(r['emo_total'] for r in rows) / max(1, sum(r['turns_emo'] for r in rows)), 2),
            'source_emoji_pct': round(100 * sum(r['src_emo'] for r in rows) / n, 2) if n else None,
            'emoticon_pct': round(100 * sum(r['emoticon'] for r in rows) / n, 1) if n else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release-dir', required=True)
    ap.add_argument('--bank', default=os.environ.get('PF_BANK'), help='persona bank JSONL (or PF_BANK)')
    ap.add_argument('--out', default=None, help='default: <release-dir>/emoji_audit.json')
    ap.add_argument('--workers', type=int, default=60)
    ap.add_argument('--languages', nargs='*', default=[], help='languages reported even if outside the top 30')
    args = ap.parse_args()
    with Pool(args.workers, initializer=init, initargs=(args.bank,)) as pool:
        rows = [r for r in pool.imap_unordered(handle, lines(os.path.join(args.release_dir, 'data', '*.jsonl')),
                                               chunksize=128) if r]
    res = {'overall': agg(rows)}
    for key in ('mode', 'tier'):
        res['by_' + key] = {k: agg([r for r in rows if r[key] == k]) for k in sorted({str(r[key]) for r in rows})}
    res['by_mode_x_tier'] = {f'{m}/{t}': agg([r for r in rows if r['mode'] == m and r['tier'] == t])
                             for m in ('free', 'multilingual') for t in ('none', 'rare', 'emoticons', 'frequent', 'unknown')}
    top = [l for l, _ in collections.Counter(r['lang'] for r in rows).most_common(30)]
    for extra in args.languages:
        if extra not in top:
            top.append(extra)
    res['by_language'] = {}
    for l in top:
        sel = [r for r in rows if r['lang'] == l]
        res['by_language'][l] = {'all': agg(sel), **{m: agg([r for r in sel if r['mode'] == m]) for m in ('free', 'multilingual')},
                                 'tier': {t: agg([r for r in sel if r['tier'] == t]) for t in ('none', 'rare', 'frequent')}}
    json.dump(res, open(args.out or os.path.join(args.release_dir, 'emoji_audit.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != 'by_language'}, indent=1))
    print('lang  n  conv%(all/free/multilingual)  turn%  src%  tiers none/rare/frequent')
    for l, v in res['by_language'].items():
        print(f"{l:12s} {v['all']['n']:7d}  {v['all']['conv_with_emoji_pct']}/{v['free']['conv_with_emoji_pct']}/{v['multilingual']['conv_with_emoji_pct']}"
              f"  {v['all']['turns_with_emoji_pct']}  {v['all']['source_emoji_pct']}  "
              f"{v['tier']['none']['conv_with_emoji_pct']}/{v['tier']['rare']['conv_with_emoji_pct']}/{v['tier']['frequent']['conv_with_emoji_pct']}")


if __name__ == '__main__':
    main()
