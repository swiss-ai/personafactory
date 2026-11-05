#!/usr/bin/env python3
"""Build assistant-regeneration inputs for every conversation of the released corpus, one file per corpus shard.

Each output row carries the user turns fixed as released, the per-turn original (pre-rewrite) user text (the
continuity check compares a reply with the next original user turn) and the per-turn persona_applied flag
(which decides whether the persona system prompt is used on that turn), taken from the pipeline records.

Inputs:
  --corpus-dir   released conversation shards (*.jsonl with id, conversation, persona_id, language_mode,
                 responder, split, source_name, text_language)
  --records      one or more pipeline output files or globs (records with id and metadata.turns_detail, as
                 written by augmentation.run_augmentation / its accepted extraction)
Output: <out-dir>/<shard>.jsonl, the input of assistant.regenerate_assistant.

  python -m personafactory.assistant.prepare_inputs --corpus-dir ./data/corpus --records './outputs/accepted/*/*.jsonl' \
      --out-dir ./outputs/assistant/input
"""
import argparse, glob, json, os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus-dir', required=True)
    ap.add_argument('--records', nargs='+', required=True)
    ap.add_argument('--out-dir', default=os.path.join(os.environ.get('PF_OUT_DIR', './outputs'), 'assistant', 'input'))
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    shards = sorted(glob.glob(os.path.join(a.corpus_dir, '*.jsonl')))
    need = set()
    for fp in shards:
        for l in open(fp, encoding='utf-8'):
            need.add(json.loads(l)['id'])
    meta = {}
    for pat in a.records:
        for fp in sorted(glob.glob(pat)):
            for l in open(fp, encoding='utf-8', errors='ignore'):
                r = json.loads(l)
                if r.get('id') not in need:
                    continue
                meta[r['id']] = [(td.get('user_message_original') or '', bool(td.get('persona_applied', td.get('persona_active'))),
                                  td.get('persona_skip_reason')) for td in r['metadata'].get('turns_detail') or []]
    n = miss = 0
    for fp in shards:
        with open(os.path.join(a.out_dir, os.path.basename(fp)), 'w', encoding='utf-8') as fo:
            for l in open(fp, encoding='utf-8'):
                r = json.loads(l)
                users = [m['content'] for m in r['conversation'] if m['role'] == 'user']
                md = meta.get(r['id'])
                if not md or len(md) < len(users):
                    miss += 1
                    continue
                fo.write(json.dumps({'id': r['id'], 'mode': r['language_mode'],
                                     'persona_id': r['persona_id'], 'responder': str(r.get('responder') or 'gemma').lower(),
                                     'split': r.get('split'), 'source_name': r.get('source_name'), 'text_language': r.get('text_language'),
                                     'fixed': [{'user_message': u, 'user_message_original': md[t][0] or u, 'persona_applied': md[t][1],
                                                'persona_skip_reason': md[t][2]} for t, u in enumerate(users)]},
                                    ensure_ascii=False) + '\n')
                n += 1
    print(json.dumps({'written': n, 'missing_meta': miss}))


if __name__ == '__main__':
    main()
