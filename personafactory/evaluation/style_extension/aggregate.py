#!/usr/bin/env python3
"""Aggregate the style-extension A/B (generate.py output + judge_client.py results) -> DIR/<--out>.

  yield       conversation status per arm; user turns left unchanged (persona_user_message_changed False)
  intent      pass rate per arm (all pass conversations, and the pairs where all three arms passed), by mode
  style       arm C pass rate (style template)
  identify    accuracy per arm picking the true author among 4 same-release candidates (chance 25%), by mode / release
  pairwise_both_orders   per arm pair and question, each comparison judged in both orders: wins (both orders agree),
              draws (they disagree), share won by the message shown first; calib_real = real WildChat turn (R) vs each
              arm (the calibration table of the paper)
  surface     first user turn, per arm: length, ratio to the rewriter's input, lowercase start, no final punctuation,
              emoji, ellipsis, repeated !/?, and the entropy of the joint surface profile (higher = more varied
              typing across personas). Reference row: the English WildChat seed turns (real users), free mode.
Results are read from DIR/<--judge>/{results,results_rejudge,results_pair2}; a parsed rejudge answer replaces an
unparsable first answer.

Usage:
    python -m personafactory.evaluation.style_extension.aggregate --dir ./outputs/style_extension            # MiniMax-M2.5
    python -m personafactory.evaluation.style_extension.aggregate --dir ./outputs/style_extension \
        --judge judge_qwen36 --out report_qwen36.json                                                       # external judge
"""
import argparse, collections, glob, json, math, re

EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿]')
CASED = {'English', 'German', 'French', 'Dutch', 'Portuguese', 'Spanish', 'Vietnamese'}


def ci(k, n):
    if not n:
        return None
    p, z = k / n, 1.96
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h), 1), round(100 * (c + h), 1)]


def rate(k, n):
    return {'pct': round(100 * k / n, 1) if n else None, 'n': n, 'ci95': ci(k, n)}


def surface(texts_refs):
    f = collections.Counter()
    prof = collections.Counter()
    n = len(texts_refs)
    for t, ref, cased in texts_refs:
        s = t.strip()
        first = next((ch for ch in s if ch.isalpha()), '')
        low = cased and first.islower()
        nofin = bool(s) and s[-1] not in '.!?。！？…)"\''
        emo = bool(EMOJI.search(s))
        ell = '...' in s or '…' in s
        rep = bool(re.search(r'[!?！？]{2,}', s))
        L = len(s)
        f['lower_start'] += low
        f['no_final_punct'] += nofin
        f['emoji'] += emo
        f['ellipsis'] += ell
        f['repeated_!?'] += rep
        f['chars'] += L
        f['ratio'] += L / max(1, len((ref or '').strip()))
        prof[(low, nofin, emo, ell, rep, min(4, int(math.log2(max(1, L // 25)))))] += 1
    out = {k: round(100 * f[k] / n, 1) for k in ('lower_start', 'no_final_punct', 'emoji', 'ellipsis', 'repeated_!?')}
    out.update(mean_chars=round(f['chars'] / n), mean_len_ratio=round(f['ratio'] / n, 2), n=n,
               profile_entropy_bits=round(-sum(v / n * math.log2(v / n) for v in prof.values()), 2))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir', required=True)
    ap.add_argument('--judge', default='judge', help='judge subdir; judge_<label> for the external judges')
    ap.add_argument('--out', default='report.json')
    a = ap.parse_args()
    rep = {}
    meta = {json.loads(l)['pair_key']: json.loads(l) for l in open(a.dir + '/assign.jsonl')}
    gen = collections.defaultdict(dict)
    st = collections.Counter()
    unch = collections.Counter()
    for f in sorted(glob.glob(a.dir + '/gen/*.jsonl')):
        for l in open(f, encoding='utf-8'):
            r = json.loads(l)
            st[(r['arm'], r['status'])] += 1
            st[(r['arm'], 'all')] += 1
            if r['status'] == 'pass':
                gen[r['pair_key']][r['arm']] = r
                for t in r['result']['metadata']['turns_detail']:
                    unch[(r['arm'], 'turns')] += 1
                    unch[(r['arm'], 'unchanged')] += t.get('persona_user_message_changed') is False
    arms = ('A', 'B', 'C')
    rep['yield'] = {x: {s: st[(x, s)] for s in ('all', 'pass', 'fail', 'error', 'lang_fail')} | {
        'pass_rate': rate(st[(x, 'pass')], st[(x, 'all')]), 'unchanged_turns': rate(unch[(x, 'unchanged')], unch[(x, 'turns')])}
        for x in arms}
    common = {k for k, v in gen.items() if len(v) == 3}
    rep['pairs'] = {'attempted': len(meta), 'all_three_pass': len(common)}

    res = {}
    for sub in ('results', 'results_rejudge', 'results_pair2'):   # a parsed rejudge answer replaces the truncated first pass
        for f in sorted(glob.glob(f'{a.dir}/{a.judge}/{sub}/*.jsonl')):
            for l in open(f, encoding='utf-8'):
                r = json.loads(l)
                if r['key'] not in res or r['result'] is not None:
                    res[r['key']] = r
    res = list(res.values())
    by = collections.defaultdict(list)
    for r in res:
        by[r['kind']].append(r)
    rep['unparsed'] = dict(collections.Counter(r['kind'] for r in res if r['result'] is None))

    def passrate(rs):
        rs = [r for r in rs if r['result'] is not None]
        return rate(sum(r['result'] == 'pass' for r in rs), len(rs))

    rep['intent'] = {x: {'all': passrate([r for r in by['intent'] if r['arm'] == x]),
                         'common': passrate([r for r in by['intent'] if r['arm'] == x and r['pair_key'] in common]),
                         **{m: passrate([r for r in by['intent'] if r['arm'] == x and r['mode'] == m]) for m in ('free', 'multilingual')}}
                     for x in arms}
    rep['style_C'] = {'all': passrate(by['style']),
                      **{m: passrate([r for r in by['style'] if r['mode'] == m]) for m in ('free', 'multilingual')}}

    def acc(rs):
        rs = [r for r in rs if r['result'] is not None]
        return rate(sum(r['result'] == r['truth'] for r in rs), len(rs))

    groups = sorted({r['persona_source'].split('/')[-1].replace('Nemotron-Personas-', '') for r in by['identify']})
    rep['identify'] = {x: {'all': acc([r for r in by['identify'] if r['arm'] == x]),
                           'common': acc([r for r in by['identify'] if r['arm'] == x and r['pair_key'] in common]),
                           **{m: acc([r for r in by['identify'] if r['arm'] == x and r['mode'] == m]) for m in ('free', 'multilingual')},
                           'by_release': {g: acc([r for r in by['identify'] if r['arm'] == x and r['persona_source'].endswith(g)])['pct']
                                          for g in groups}}
                       for x in arms}
    # both orders (items.py pairwise): win = same arm chosen in both orders, draw = the orders disagree,
    # missing = an order left unparsed. Rates over decided comparisons (wins + draws)
    two = collections.defaultdict(dict)
    for r in by['pair_real'] + by['pair_fit'] + by['calib_real']:
        if r['key'].count('#') == 3 and r['result'] in (1, 2):
            x, y = r['pair']
            two[(r['kind'], r['pair'], r['pair_key'])][r['first']] = r['first'] if r['result'] == 1 else (y if r['first'] == x else x)
    rep['pairwise_both_orders'] = {}
    for kind, pairs in (('pair_real', ('AC', 'BC', 'AB')), ('pair_fit', ('AC', 'BC', 'AB')), ('calib_real', ('RA', 'RB', 'RC'))):
        for pair in pairs:
            x, y = pair
            items = [r for r in by[kind] if r['pair'] == pair and r['key'].count('#') == 3]
            pks = {r['pair_key'] for r in items}
            c = collections.Counter()
            for pk in pks:
                v = two.get((kind, pair, pk), {})
                c['missing' if len(v) < 2 else v[x] if v[x] == v[y] else 'draw'] += 1
            n = c[x] + c[y] + c['draw']
            firsts = [r for r in items if r['result'] in (1, 2)]
            rep['pairwise_both_orders'][f'{kind}/{pair}'] = {
                f'{x}_wins': rate(c[x], n), f'{y}_wins': rate(c[y], n), 'draws': rate(c['draw'], n), 'missing': c['missing'],
                'first_shown_wins': rate(sum(r['result'] == 1 for r in firsts), len(firsts))}
    surf = {}
    for x in arms:
        rows = []
        for pk in common:
            r = gen[pk][x]
            td = r['result']['metadata']['turns_detail'][0]
            u = next(m['content'] for m in r['result']['conversation'] if m['role'] == 'user')
            ref = td.get('user_message_original') or td.get('user_message_source')
            rows.append((u, ref, (meta[pk]['target_language'] or 'English') in CASED))
        surf[x] = surface(rows)
    seeds = []
    for pk in common:
        if meta[pk]['mode'] == 'free' and meta[pk]['source_name'] == 'wildchat':
            s = gen[pk]['C']['result']['metadata']['turns_detail'][0].get('user_message_source')
            seeds.append((s, s, True))
    surf['wildchat_seed_reference'] = surface(seeds) if seeds else None
    rep['surface_first_turn'] = surf
    json.dump(rep, open(f'{a.dir}/{a.out}', 'w'), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == '__main__':
    main()
