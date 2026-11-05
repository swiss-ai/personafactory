#!/usr/bin/env python3
"""Build per-user-turn judge items for the released corpus (corpus-scale judge table), sharded for a judge fleet.

Each item holds two prompts built from the production templates (augmentation/prompts.py):
  intent: original vs rewritten user turn. The original is the turn the rewriter restyled: the source turn, or,
          for cross-lingual turns that were translated before restyling, the literal translation, because the
          intent template fails any language switch. For translated turns the English-source variant is stored
          as well (intent_prompt_vs_english_source) so both can be reported.
  style:  persona background + writing style (release bank) vs rewritten turn.
Rewritten turns are taken from the release; per-turn originals come from the pipeline output
(metadata.turns_detail: user_message_original = restyled basis, user_message_source = English source when
translated), with a fallback to source_conversation + metadata.localized_user_messages.

Optionally reuses verdicts from a previous judge run (--reuse-results) for items whose key already exists
there, e.g. after an assistant-side-only rebuild of the release. Only valid if the user turns are unchanged.

Inputs:  --release-dir (data/*.jsonl), --bank (persona_bank.jsonl), --originals (pipeline output files, dirs or globs)
Outputs: <out-dir>/items/NNN.jsonl (and <out-dir>/results/NNN.jsonl when reusing verdicts)
Run:     python -m personafactory.evaluation.corpus_judge.prep_items --release-dir ./release_out --bank ./release_out/persona_bank.jsonl \
             --originals ./outputs/accepted --out-dir ./outputs/corpus_judge --shards 64
"""
import argparse, glob, hashlib, json, os

from personafactory.augmentation.prompts import VALIDATE_PERSONA_INTENT_TEMPLATE as INTENT, VALIDATE_PERSONA_STYLE_TEMPLATE as STYLE
from personafactory.augmentation.pipeline import get_persona_background_str as bg_str, get_persona_style_str as style_str


def expand(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            out += sorted(glob.glob(os.path.join(p, '**', '*.jsonl'), recursive=True))
        else:
            out += sorted(glob.glob(p))
    return out


def originals_of(r):
    """Per-turn (source, restyle basis) lists from one pipeline output record."""
    md = r.get('metadata') or {}
    td = md.get('turns_detail') or []
    if td:
        basis = [t.get('user_message_original') or '' for t in td]
        src = [t.get('user_message_source') or t.get('user_message_original') or '' for t in td]
        return {'src': src, 'basis': basis}
    src = [m['content'] for m in (r.get('source_conversation') or []) if m.get('role') == 'user']
    loc = md.get('localized_user_messages') or []
    return {'src': src, 'basis': [loc[t] if t < len(loc) and loc[t] else s for t, s in enumerate(src)]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--release-dir', required=True, help='release directory with data/*.jsonl')
    ap.add_argument('--bank', required=True, help='release persona_bank.jsonl')
    ap.add_argument('--originals', nargs='+', required=True, help='pipeline output JSONL files, dirs or globs')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--shards', type=int, default=64)
    ap.add_argument('--reuse-results', default=None, help='results/ dir of a previous run with the same sharding')
    a = ap.parse_args()
    out = os.path.join(a.out_dir, 'items')
    os.makedirs(out, exist_ok=True)

    bank = {}
    for line in open(a.bank, encoding='utf-8'):
        p = json.loads(line)
        bank[p['id']] = p
    print('bank', len(bank), flush=True)

    orig = {}
    for fp in expand(a.originals):
        for line in open(fp, encoding='utf-8', errors='ignore'):
            if not line.strip():
                continue
            r = json.loads(line)
            orig[r.get('id') or r.get('key')] = originals_of(r)
    print('records with originals', len(orig), flush=True)

    sinks = [open(os.path.join(out, f'{i:03d}.jsonl'), 'w', encoding='utf-8') for i in range(a.shards)]
    n = miss = 0
    for fp in sorted(glob.glob(os.path.join(a.release_dir, 'data', '*.jsonl'))):
        for line in open(fp, encoding='utf-8'):
            r = json.loads(line)
            o = orig.get(r['id'])
            p = bank.get(r.get('persona_id'))
            if not o or not p:
                miss += 1
                continue
            users = [m['content'] for m in r['conversation'] if m.get('role') == 'user']
            bgs, sty = bg_str(p), style_str(p, include_quirks=True)
            for t, rw in enumerate(users):
                if t >= len(o['src']):
                    break
                source, basis = o['src'][t], o['basis'][t]
                translated = basis.strip() != source.strip()
                item = {'key': f"{r['id']}#{t}",
                        'mode': r.get('language_mode'),
                        'lang': r.get('text_language'), 'cohort': r.get('cohort'), 'responder': r.get('responder'),
                        'source_name': r.get('source_name'), 'turn': t,
                        'changed': rw.strip() != basis.strip(),
                        'intent_basis': 'translation_baseline' if translated else 'source',
                        'intent_prompt': INTENT.format(original_message=basis, rewritten_message=rw),
                        'style_prompt': STYLE.format(background=bgs, writing_style=sty, rewritten_message=rw)}
                if translated:
                    item['intent_prompt_vs_english_source'] = INTENT.format(original_message=source, rewritten_message=rw)
                shard = int(hashlib.md5(item['key'].encode()).hexdigest(), 16) % a.shards
                sinks[shard].write(json.dumps(item, ensure_ascii=False) + '\n')
                n += 1
    for s in sinks:
        s.close()

    reused = 0
    if a.reuse_results:
        # same md5 % shards mapping as the previous run, so shard i only needs previous shard i
        res_dir = os.path.join(a.out_dir, 'results')
        os.makedirs(res_dir, exist_ok=True)
        for i in range(a.shards):
            keys = {json.loads(l)['key'] for l in open(os.path.join(out, f'{i:03d}.jsonl'), encoding='utf-8')}
            src_fp = os.path.join(a.reuse_results, f'{i:03d}.jsonl')
            with open(os.path.join(res_dir, f'{i:03d}.jsonl'), 'w', encoding='utf-8') as fo:
                if os.path.exists(src_fp):
                    for l in open(src_fp, encoding='utf-8'):
                        try:
                            row = json.loads(l)
                        except Exception:
                            continue
                        if row['key'] in keys:
                            fo.write(l if l.endswith('\n') else l + '\n')
                            reused += 1
        print(json.dumps({'reused_verdicts': reused}), flush=True)
    print(json.dumps({'items': n, 'records_missing_originals_or_persona': miss, 'shards': a.shards}), flush=True)


if __name__ == '__main__':
    main()
