#!/usr/bin/env python3
"""Intent check of the persona-rewritten benchmark prompts (perturb_persona.py) with the paper's intent template
(VALIDATE_PERSONA_INTENT_TEMPLATE, original benchmark prompt vs rewrite), judged by MiniMax-M2.5 with judge_client.py.
In the paper 99.6% of the rewrites passed.

  prep    <data-dir>/intent_items/000.jsonl
  merge   keeps rewrites whose verdict is pass and writes <data-dir>/styled_all.jsonl = rule-based variants
          (styled.jsonl) + WildChat prompts (wildchat.jsonl, if present) + intent-checked persona variants, plus
          <data-dir>/intent_stats.json

  python -m personafactory.downstream.eval.intent_check prep --data-dir $PF_DATA_DIR/downstream_eval
  python -m personafactory.downstream.eval.judge_client --shards $PF_DATA_DIR/downstream_eval/intent_items/000.jsonl \
      --outdir $PF_DATA_DIR/downstream_eval/intent_results --urls $MINIMAX_URL --model MiniMax-M2.5 --max-tokens 2048
  python -m personafactory.downstream.eval.intent_check merge --data-dir $PF_DATA_DIR/downstream_eval
"""
import argparse, collections, glob, json, os

from personafactory.augmentation.prompts import VALIDATE_PERSONA_INTENT_TEMPLATE as INTENT


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('step', choices=['prep', 'merge'])
    ap.add_argument('--data-dir', required=True)
    a = ap.parse_args()
    E = a.data_dir
    orig = {(r['bench'], r['id']): r['prompt'] for r in map(json.loads, open(os.path.join(E, 'styled.jsonl'), encoding='utf-8'))
            if r['variant'] == 'clean'}
    rows = [json.loads(l) for l in open(os.path.join(E, 'styled_persona.jsonl'), encoding='utf-8')]
    if a.step == 'prep':
        os.makedirs(os.path.join(E, 'intent_items'), exist_ok=True)
        with open(os.path.join(E, 'intent_items', '000.jsonl'), 'w', encoding='utf-8') as f:
            for r in rows:
                f.write(json.dumps({'key': f"{r['bench']}#{r['id']}#{r['variant']}", 'kind': 'intent', 'prompt': INTENT.format(
                    original_message=orig[(r['bench'], r['id'])], rewritten_message=r['prompt'])}, ensure_ascii=False) + '\n')
        print('items', len(rows))
        return
    verdict = {}
    for fp in glob.glob(os.path.join(E, 'intent_results', '*.jsonl')):
        for line in open(fp, encoding='utf-8'):
            x = json.loads(line)
            verdict[x['key']] = x['result']
    st = collections.Counter()
    with open(os.path.join(E, 'styled_all.jsonl'), 'w', encoding='utf-8') as out:
        for line in open(os.path.join(E, 'styled.jsonl'), encoding='utf-8'):
            out.write(line)
        if os.path.exists(os.path.join(E, 'wildchat.jsonl')):
            for line in open(os.path.join(E, 'wildchat.jsonl'), encoding='utf-8'):
                out.write(line)
        for r in rows:
            v = verdict.get(f"{r['bench']}#{r['id']}#{r['variant']}")
            st[f"{r['bench']}/{v}"] += 1
            if v == 'pass':
                out.write(json.dumps(r, ensure_ascii=False) + '\n')
    json.dump(dict(sorted(st.items())), open(os.path.join(E, 'intent_stats.json'), 'w'), indent=1)
    print(dict(sorted(st.items())))


if __name__ == '__main__':
    main()
