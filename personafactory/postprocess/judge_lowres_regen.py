#!/usr/bin/env python3
"""Quality check of the low-resource Gemma regeneration (records with regenerated == 'lowres_gemma').

  --stage sample   every regenerated id whose Ministral original was judged in the first pass (--first, a
                   lowres_quality judge file; paired before / after on the same seed), topped up at random to --n per
                   language (seed 20261101) -> <out>/sample.jsonl
  (judge)          python -m personafactory.postprocess.lowres_quality --stage judge --out <out> (same prompt and judge)
  --stage compare  <out>/judge_<tag>.jsonl vs the first pass: paired Ministral -> Gemma deltas, and per language the
                   regenerated mean vs the first-pass Ministral and Gemma means -> <out>/compare.json

  python -m personafactory.postprocess.judge_lowres_regen --stage sample --release-dir ./release_merged \\
      --first ./outputs/lowres_quality/judge_dsv41flash.jsonl --out ./outputs/lowres_quality/regen --n 10
"""
import argparse, collections, json, os, random

from personafactory.postprocess import lowres_quality as Q


def stage_sample(a):
    os.makedirs(a.out, exist_ok=True)
    first = {}
    for l in open(a.first, encoding='utf-8'):
        x = json.loads(l)
        if x['responder'] == 'ministral' and x['part'] == a.part:
            first[x['id']] = x['lang']
    recs = collections.defaultdict(list)
    for l in Q.release_lines(a.release_dir):
        if '"lowres_gemma"' not in l:
            continue
        r = json.loads(l)
        if r.get('regenerated') == 'lowres_gemma':
            recs[first.get(r['id']) or Q.lang_of(r)].append(r)
    rnd = random.Random(20261101)
    n_pair = 0
    with open(os.path.join(a.out, 'sample.jsonl'), 'w', encoding='utf-8') as f:
        for L, rs in sorted(recs.items(), key=lambda kv: str(kv[0])):
            rs.sort(key=lambda r: r['id'])
            pair = [r for r in rs if r['id'] in first]
            rest = [r for r in rs if r['id'] not in first]
            rnd.shuffle(rest)
            pick = pair + rest[:max(0, a.n - len(pair))]
            n_pair += len(pair)
            for r in pick:
                r['_lang'] = L
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
            print(L, 'regen', len(rs), 'paired', len(pair), 'sampled', len(pick))
    print('paired total', n_pair)


def stage_compare(a):
    old = collections.defaultdict(dict)
    for l in open(a.first, encoding='utf-8'):
        x = json.loads(l)
        if isinstance(x['verdict'], dict):
            old[x['lang']].setdefault(x['responder'], []).append(x['verdict'])
            old['_id'][x['id']] = x['verdict']
    new = [json.loads(l) for l in open(os.path.join(a.out, f'judge_{a.tag}.jsonl'), encoding='utf-8')]
    ok = [x for x in new if isinstance(x['verdict'], dict)]
    by = collections.defaultdict(list)
    for x in ok:
        by[x['lang']].append(x['verdict'])
    mean = lambda v: round(sum(v[s] for s in Q.SCORES if isinstance(v.get(s), (int, float))) / len(Q.SCORES), 3)

    def m(vs):
        return round(sum(mean(v) for v in vs) / len(vs), 2) if vs else None
    langs = {}
    for L in sorted(by, key=str):
        langs[L] = {'regen_gemma': {**Q.agg(by[L]), 'mean6': m(by[L])},
                    'first_ministral_mean6': m(old[L].get('ministral', [])),
                    'first_gemma_mean6': m(old[L].get('gemma', []))}
    pairs = [(old['_id'][x['id']], x['verdict']) for x in ok if x['id'] in old['_id']]
    delta = {s: round(sum(n[s] - o[s] for o, n in pairs if all(isinstance(v.get(s), (int, float)) for v in (o, n))) / len(pairs), 2)
             for s in Q.SCORES} if pairs else {}
    flags = {f: [round(sum(bool(o.get(f)) for o, _ in pairs) / len(pairs), 3), round(sum(bool(n.get(f)) for _, n in pairs) / len(pairs), 3)]
             for f in Q.FLAGS} if pairs else {}
    res = {'judged': len(new), 'failed': len(new) - len(ok), 'overall_regen': {**Q.agg([x['verdict'] for x in ok]), 'mean6': m([x['verdict'] for x in ok])},
           'paired': {'n': len(pairs), 'ministral_mean6': m([o for o, _ in pairs]), 'gemma_mean6': m([n for _, n in pairs]),
                      'delta_by_score': delta, 'flag_rate_ministral_vs_gemma': flags},
           'by_language': langs}
    json.dump(res, open(os.path.join(a.out, 'compare.json'), 'w'), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in res.items() if k != 'by_language'}, indent=1))
    for L, v in langs.items():
        print(f"{str(L):16s} n={v['regen_gemma']['n']:3d} regen={v['regen_gemma']['mean6']} "
              f"first_ministral={v['first_ministral_mean6']} first_gemma={v['first_gemma_mean6']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--stage', choices=('sample', 'compare'), required=True)
    ap.add_argument('--release-dir', help='merged release directory (sample stage)')
    ap.add_argument('--first', required=True, help='first-pass judge file (lowres_quality judge_<tag>.jsonl)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--n', type=int, default=10)
    ap.add_argument('--tag', default='dsv41flash')
    ap.add_argument('--part', default='seeds', help='release_part label of the seed-pool records')
    a = ap.parse_args()
    {'sample': stage_sample, 'compare': stage_compare}[a.stage](a)


if __name__ == '__main__':
    main()
