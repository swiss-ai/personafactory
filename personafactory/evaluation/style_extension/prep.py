#!/usr/bin/env python3
"""Inputs of the style-extension A/B: one seed conversation per extended persona, three persona arms.

Personas: the judge-kept personas of a style-extension run (persona_bank.extend_style, judged with
validate_personas; --run/judge_out/*.jsonl, verdict keep), shuffled with --seed.
Seeds: one seed conversation per persona from the augmentation seed shards (augmentation.prepare_seeds output,
files <mode>-<source>-NNNN.jsonl with pair_key, conversation, seed_language), English seeds only (seed_language
English or unset), sources in turn WildChat, UltraChat, Nemotron (1/3 each). English personas run in free mode on
the English seed; every other persona runs in multilingual mode with its main language as target (literal
translation, then restyle). All three arms use the same persona and seed per pair, so they differ only in the
persona text the rewriter and responder see (generate.py).

Writes OUT/personas.jsonl, OUT/pairs_free.jsonl, OUT/pairs_multilingual.jsonl, OUT/assign.jsonl.

Usage:
    python -m personafactory.evaluation.style_extension.prep --run ./data/style_extension \\
        --seeds ./data/seeds/shards --out ./outputs/style_extension
"""
import argparse, collections, glob, json, os, random

SOURCES = ('wildchat', 'ultrachat', 'nemotron')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--run', required=True, help='style-extension run dir with judge_out/*.jsonl')
    ap.add_argument('--seeds', required=True, help='directory with <mode>-<source>-*.jsonl seed shards')
    ap.add_argument('--out', required=True)
    ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    os.makedirs(a.out, exist_ok=True)
    ps = {}
    for f in sorted(glob.glob(a.run + '/judge_out/*.jsonl')):
        for l in open(f, encoding='utf-8'):
            if l.strip():
                p = json.loads(l)
                if p['validation'].get('verdict') == 'keep':
                    ps[p['id']] = p
    ps = [ps[k] for k in sorted(ps)]
    rng.shuffle(ps)
    need = collections.Counter()
    plan = []
    for i, p in enumerate(ps):
        mode = 'free' if p['background']['main_language'] == 'English' else 'multilingual'
        src = SOURCES[i % 3]
        plan.append((p, mode, src))
        need[(mode, src)] += 1
    pool = {}
    for (mode, src), n in need.items():
        cand = []
        files = sorted(glob.glob(os.path.join(a.seeds, f'{mode}-{src}-*.jsonl')))
        rng.shuffle(files)
        for f in files:
            for l in open(f, encoding='utf-8'):
                r = json.loads(l)
                if r.get('seed_language') in (None, 'English'):
                    cand.append(r)
            if len(cand) >= 5 * n:
                break
        pool[(mode, src)] = rng.sample(cand, n)
    with open(a.out + '/personas.jsonl', 'w', encoding='utf-8') as fp, \
            open(a.out + '/assign.jsonl', 'w', encoding='utf-8') as fa, \
            open(a.out + '/pairs_free.jsonl', 'w', encoding='utf-8') as ff, \
            open(a.out + '/pairs_multilingual.jsonl', 'w', encoding='utf-8') as fm:
        c = collections.Counter()
        for p, mode, src in plan:
            r = pool[(mode, src)].pop()
            fp.write(json.dumps(p, ensure_ascii=False) + '\n')
            (ff if mode == 'free' else fm).write(json.dumps(r, ensure_ascii=False) + '\n')
            fa.write(json.dumps({'pair_key': r['pair_key'], 'mode': mode, 'persona_id': p['id'], 'match_tier': 'style_ab',
                                 'responder': 'gemma', 'source_name': src, 'persona_source': p['source']['source'],
                                 'target_language': None if mode == 'free' else p['background']['main_language']}) + '\n')
            c[(mode, src)] += 1
    print(len(ps), 'personas', dict(c))


if __name__ == '__main__':
    main()
