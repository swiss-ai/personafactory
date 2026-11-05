#!/usr/bin/env python3
"""Aggregate the corpus judge on the seed-pool sample (judge_sample_prep items, evaluation.corpus_judge.run_judge
results) into intent / style / both pass rates with 95% Wilson intervals, overall and by generator, seed source
and setting.

Only conversations still in the release are counted (later filters remove some sampled ones). The generator
breakdown uses the model that rewrote the user turns: conversations whose assistant side was later regenerated with
Gemma (assistant_regenerated) were rewritten by Ministral, although their released responder is gemma.
Writes <release>/judge_sample.json.

  python -m personafactory.postprocess.judge_sample_agg --judge-dir ./outputs/judge_sample --release-dir ./release_merged
"""
import argparse, glob, json, math, os


def ci(k, n):
    p, z = k / n, 1.96
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h), 2), round(100 * (c + h), 2)]


def summ(rs, ik='intent'):
    i = [r for r in rs if r.get(ik) is not None]
    s = [r for r in rs if r.get('style') is not None]
    b = [r for r in rs if r.get(ik) is not None and r.get('style') is not None]
    ip, sp = sum(r[ik] == 'pass' for r in i), sum(r['style'] == 'pass' for r in s)
    bp = sum(r[ik] == 'pass' and r['style'] == 'pass' for r in b)
    return {'turns': len(rs), 'intent_pct': round(100 * ip / len(i), 1), 'intent_ci95': ci(ip, len(i)),
            'style_pct': round(100 * sp / len(s), 1), 'style_ci95': ci(sp, len(s)), 'both_pct': round(100 * bp / len(b), 1),
            'unparsed_intent': len(rs) - len(i), 'unparsed_style': len(rs) - len(s)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--judge-dir', required=True, help='directory with items/ and results/')
    ap.add_argument('--release-dir', required=True)
    a = ap.parse_args()
    rows = [json.loads(l) for fp in sorted(glob.glob(os.path.join(a.judge_dir, 'results', '*.jsonl')))
            for l in open(fp, encoding='utf-8') if l.strip()]
    items = sum(1 for fp in glob.glob(os.path.join(a.judge_dir, 'items', '*.jsonl')) for _ in open(fp, encoding='utf-8'))
    ids = {r['key'].split('#')[0] for r in rows}
    regen, present = set(), set()
    for fp in sorted(glob.glob(os.path.join(a.release_dir, 'data', '*.jsonl'))):
        for l in open(fp, encoding='utf-8'):
            r = json.loads(l)
            if r['id'] in ids:
                present.add(r['id'])
                if r.get('assistant_regenerated'):
                    regen.add(r['id'])
    dropped = len(ids - present)
    rows = [r for r in rows if r['key'].split('#')[0] in present]
    for r in rows:
        r['generator'] = 'ministral' if r['key'].split('#')[0] in regen else r['responder']
    out = {'items': items, 'judged': len(rows), 'conversations': len(present), 'sample_dropped_from_release': dropped,
           'assistant_regenerated_in_sample': len(regen), 'all': summ(rows)}
    for k in ('generator', 'source_name', 'mode'):
        out['by_' + k] = {v: summ([r for r in rows if r[k] == v]) for v in sorted({r[k] for r in rows})}
    out['multilingual_intent_vs_english_source'] = summ([r for r in rows if r['mode'] == 'multilingual'], 'intent_vs_en')
    json.dump(out, open(os.path.join(a.release_dir, 'judge_sample.json'), 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
