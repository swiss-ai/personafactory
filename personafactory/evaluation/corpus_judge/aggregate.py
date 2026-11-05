#!/usr/bin/env python3
"""Corpus-scale judge table: intent / style / both pass rates with 95% Wilson intervals and the paper's
breakdowns (generator backbone = responder, seed source), plus mode, cohort and language slices.

Rates exclude null verdicts (reported separately as unparsed). Translated cross-lingual turns are judged against
the translation (same-language); their English-source variant is reported separately.

Inputs:  <judge-dir>/items/*.jsonl, <judge-dir>/results/*.jsonl
Outputs: --out JSON (default <judge-dir>/corpus_judge.json; corpus_judge.estimate combines it with a sample)
Run:     python -m personafactory.evaluation.corpus_judge.aggregate --judge-dir ./outputs/corpus_judge --out ./outputs/corpus_judge/corpus_judge.json
"""
import argparse, collections, glob, json, os

from personafactory.evaluation.stats_utils import wilson


def ci(k, n):
    w = wilson(k, n)
    return [round(100 * w[0], 2), round(100 * w[1], 2)] if w else None


def summ(rs, intent_key='intent'):
    i = [r for r in rs if r.get(intent_key) is not None]
    s = [r for r in rs if r.get('style') is not None]
    b = [r for r in rs if r.get(intent_key) is not None and r.get('style') is not None]
    ip = sum(r[intent_key] == 'pass' for r in i)
    sp = sum(r['style'] == 'pass' for r in s)
    bp = sum(r[intent_key] == 'pass' and r['style'] == 'pass' for r in b)
    return {'turns': len(rs), 'intent_pct': round(100 * ip / len(i), 2) if i else None, 'intent_ci95': ci(ip, len(i)),
            'style_pct': round(100 * sp / len(s), 2) if s else None, 'style_ci95': ci(sp, len(s)),
            'both_pct': round(100 * bp / len(b), 2) if b else None, 'both_ci95': ci(bp, len(b)),
            'unparsed_intent': len(rs) - len(i), 'unparsed_style': len(rs) - len(s)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--judge-dir', required=True)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    rows = []
    for fp in sorted(glob.glob(os.path.join(a.judge_dir, 'results', '*.jsonl'))):
        for line in open(fp, encoding='utf-8'):
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    items = sum(1 for fp in glob.glob(os.path.join(a.judge_dir, 'items', '*.jsonl')) for _ in open(fp, encoding='utf-8'))

    out = {'items_total': items, 'items_judged': len(rows), 'complete': len(rows) >= items,
           'entire_release': summ(rows)}
    for key in ('mode', 'responder', 'source_name', 'intent_basis', 'changed'):
        out['by_' + key] = {k: summ([r for r in rows if str(r.get(key)) == k])
                            for k in sorted({str(r.get(key)) for r in rows})}
    out['by_mode_x_cohort'] = {f'{m}/{c}': summ([r for r in rows if r.get('mode') == m and str(r.get('cohort')) == c])
                               for m in ('free', 'multilingual') for c in sorted({str(r.get('cohort')) for r in rows})}
    tr = [r for r in rows if r.get('intent_basis') == 'translation_baseline']
    out['multilingual_intent_vs_english_source'] = summ(tr, 'intent_vs_en')
    langs = collections.Counter(r['lang'] for r in rows)
    out['by_language_top25'] = {l: summ([r for r in rows if r['lang'] == l]) for l, _ in langs.most_common(25)}
    finish = collections.Counter(str(r.get('intent_finish')).split(':')[0] for r in rows)
    out['intent_finish_reasons'] = dict(finish.most_common(8))
    dst = a.out or os.path.join(a.judge_dir, 'corpus_judge.json')
    json.dump(out, open(dst, 'w'), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k not in ('by_language_top25', 'by_mode_x_cohort')}, indent=1))


if __name__ == '__main__':
    main()
