#!/usr/bin/env python3
"""Duplicate audit of the release.

Levels: exact id, identical full conversation, identical first user turn, and same source prompt (normalized
source_text) split by language and mode. A same-source pair is a real duplicate risk only when both
records are in the same language; across languages it is intended. Writes <release-dir>/duplicate_audit.json.

  python -m personafactory.release.stats.duplicates --release-dir ./release_out --workers 60
"""
import argparse, collections, glob, hashlib, json, os, re
from multiprocessing import Pool


def norm(t):
    return re.sub(r'\s+', ' ', (t or '').strip().lower())


def h(t):
    return hashlib.sha1(t.encode('utf-8', 'ignore')).hexdigest()[:16]


def shard(path):
    out = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            conv = r.get('conversation') or []
            user = next((m.get('content') for m in conv if m.get('role') == 'user'), '')
            out.append((r['id'], str(r.get('language_mode')), r.get('language_mode'),
                        r.get('text_language'), r.get('persona_id'),
                        h(norm(r.get('source_text'))) if r.get('source_text') else None,
                        h(json.dumps(conv, ensure_ascii=False, sort_keys=True)), h(norm(user))))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release-dir', required=True)
    ap.add_argument('--out', default=None, help='default: <release-dir>/duplicate_audit.json')
    ap.add_argument('--workers', type=int, default=60)
    args = ap.parse_args()
    rows = []
    with Pool(args.workers) as pool:
        for chunk in pool.imap_unordered(shard, sorted(glob.glob(os.path.join(args.release_dir, 'data', '*.jsonl')))):
            rows.extend(chunk)
    n = len(rows)
    res = {'records': n}
    for name, idx in (('exact_id_dupes', 0), ('exact_conversation_dupes', 6), ('exact_first_user_turn_dupes', 7)):
        c = collections.Counter(r[idx] for r in rows)
        res[name] = sum(v - 1 for v in c.values() if v > 1)
    res['missing_source_text'] = sum(1 for r in rows if r[5] is None)
    groups = collections.defaultdict(list)
    for r in rows:
        if r[5]:
            groups[r[5]].append(r)
    sizes = collections.Counter(min(len(g), 6) for g in groups.values())
    res['distinct_sources'] = len(groups)
    res['source_group_sizes'] = {str(k) + ('+' if k == 6 else ''): v for k, v in sorted(sizes.items())}
    pair_kinds = collections.Counter()
    same_lang_groups, extra_same_lang = collections.Counter(), collections.Counter()
    same_persona = 0
    examples = collections.defaultdict(list)
    for g in groups.values():
        if len(g) < 2:
            continue
        by_lang = collections.defaultdict(list)
        for r in g:
            by_lang[r[3]].append(r)
        for lang, rs in by_lang.items():
            if len(rs) < 2:
                continue
            kind = ' + '.join(sorted(r[1] + '/' + str(r[2]) for r in rs)) if len(rs) <= 3 else f'{len(rs)} records'
            same_lang_groups[kind] += 1
            extra_same_lang[kind] += len(rs) - 1
            same_persona += len(rs) - len({r[4] for r in rs})
            if len(examples[kind]) < 3:
                examples[kind].append([r[0] for r in rs])
        kinds = set()
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                a, b = g[i], g[j]
                kinds.add(('same_lang' if a[3] == b[3] else 'diff_lang') + ':' + '+'.join(sorted([a[1], b[1]])))
        pair_kinds.update(kinds)
    res['groups_with_pair_kind'] = dict(pair_kinds.most_common())
    res['same_language_same_source'] = {
        'groups': dict(same_lang_groups.most_common()),
        'redundant_records': dict(extra_same_lang.most_common()),
        'redundant_records_total': sum(extra_same_lang.values()),
        'redundant_pct_of_release': round(100 * sum(extra_same_lang.values()) / n, 2),
        'of_which_same_persona_too': same_persona,
        'example_ids': dict(examples)}
    json.dump(res, open(args.out or os.path.join(args.release_dir, 'duplicate_audit.json'), 'w'), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
