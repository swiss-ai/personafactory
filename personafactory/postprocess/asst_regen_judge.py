#!/usr/bin/env python3
"""Paired quality check of the assistant-side Gemma regeneration; run it before finalize_asst_regen (it reads the
released Ministral version from the release directory).

  --stage sample   sanity-gate status per language; --n passing ids per language (seed 20261102), each judged twice:
                   the released Ministral version (id#ministral) and the same conversation with the Gemma assistant
                   turns (id#gemma) -> <out>/sample.jsonl, <out>/gate.json
  (judge)          python -m personafactory.postprocess.lowres_quality --stage judge --out <out>
  --stage compare  paired Ministral vs Gemma scores and flag rates, overall and per language -> <out>/compare.json

  python -m personafactory.postprocess.asst_regen_judge --stage sample --release-dir ./release_merged \\
      --targets ./outputs/asst_regen/targets.tsv --regen-dir ./outputs/asst_regen/user_persona --out ./outputs/asst_regen/judge --n 20
"""
import argparse, collections, glob, json, os, random

from personafactory.postprocess import lowres_quality as Q


def load_regen(regen_dir):
    res = {}
    for fp in glob.glob(os.path.join(regen_dir, '*.jsonl')):
        for l in open(fp, encoding='utf-8'):
            try:
                x = json.loads(l)
            except ValueError:
                continue
            res[x['id']] = x
    return res


def stage_sample(a):
    os.makedirs(a.out, exist_ok=True)
    lang = dict(l.rstrip('\n').split('\t') for l in open(a.targets, encoding='utf-8'))
    regen = load_regen(a.regen_dir)
    st = collections.defaultdict(collections.Counter)
    for i, x in regen.items():
        st[lang.get(i)][x['status']] += 1
    rnd = random.Random(20261102)
    by = collections.defaultdict(list)
    for i, x in sorted(regen.items()):
        if x['status'] == 'pass':
            by[lang[i]].append(i)
    want = {}
    for L, ids in by.items():
        rnd.shuffle(ids)
        for i in ids[:a.n]:
            want[i] = L
    n = 0
    with open(os.path.join(a.out, 'sample.jsonl'), 'w', encoding='utf-8') as f:
        for l in Q.release_lines(a.release_dir):
            r = json.loads(l)
            if r['id'] not in want:
                continue
            old = dict(r, id=r['id'] + '#ministral', _lang=want[r['id']])
            new = dict(r, id=r['id'] + '#gemma', _lang=want[r['id']], responder='gemma', conversation=regen[r['id']]['conversation'])
            f.write(json.dumps(old, ensure_ascii=False) + '\n' + json.dumps(new, ensure_ascii=False) + '\n')
            n += 1
    gate = {str(L): dict(c) for L, c in sorted(st.items(), key=lambda kv: str(kv[0]))}
    json.dump(gate, open(os.path.join(a.out, 'gate.json'), 'w'), indent=1, ensure_ascii=False)
    print(json.dumps(gate, indent=1, ensure_ascii=False))
    print('pairs', n)


def stage_compare(a):
    rows = [json.loads(l) for l in open(os.path.join(a.out, f'judge_{a.tag}.jsonl'), encoding='utf-8')]
    v = {r['id']: r for r in rows if isinstance(r['verdict'], dict)}
    pairs = collections.defaultdict(list)
    for k, r in v.items():
        base, side = k.split('#')
        if side == 'gemma' and base + '#ministral' in v:
            pairs[r['lang']].append((v[base + '#ministral']['verdict'], r['verdict']))
    m6 = lambda x: sum(x[s] for s in Q.SCORES) / len(Q.SCORES)

    def summ(ps):
        if not ps:
            return None
        o = {'n': len(ps), 'ministral_mean6': round(sum(m6(p[0]) for p in ps) / len(ps), 2),
             'gemma_mean6': round(sum(m6(p[1]) for p in ps) / len(ps), 2),
             'gemma_better': sum(m6(p[1]) > m6(p[0]) for p in ps), 'ministral_better': sum(m6(p[1]) < m6(p[0]) for p in ps)}
        for s in Q.SCORES:
            o[s] = [round(sum(p[0][s] for p in ps) / len(ps), 2), round(sum(p[1][s] for p in ps) / len(ps), 2)]
        for fl in Q.FLAGS:
            o[fl] = [round(sum(bool(p[0].get(fl)) for p in ps) / len(ps), 3), round(sum(bool(p[1].get(fl)) for p in ps) / len(ps), 3)]
        return o
    allp = [p for ps in pairs.values() for p in ps]
    res = {'judged': len(rows), 'failed': len(rows) - len(v), 'overall': summ(allp),
           'by_language': {L: summ(ps) for L, ps in sorted(pairs.items())},
           'gate': json.load(open(os.path.join(a.out, 'gate.json')))}
    json.dump(res, open(os.path.join(a.out, 'compare.json'), 'w'), indent=1, ensure_ascii=False)
    print(json.dumps(res['overall'], indent=1))
    for L, s in res['by_language'].items():
        print(f"{L:12s} n={s['n']:3d} ministral={s['ministral_mean6']} gemma={s['gemma_mean6']} "
              f"aqual={s['assistant_quality']} trunc={s['truncated']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--stage', choices=('sample', 'compare'), required=True)
    ap.add_argument('--release-dir')
    ap.add_argument('--targets', help='asst_regen_prep targets.tsv')
    ap.add_argument('--regen-dir', help='regenerate_assistant output directory (<out-dir>/user_persona)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--n', type=int, default=20)
    ap.add_argument('--tag', default='dsv41flash')
    a = ap.parse_args()
    {'sample': stage_sample, 'compare': stage_compare}[a.stage](a)


if __name__ == '__main__':
    main()
