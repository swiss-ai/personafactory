#!/usr/bin/env python3
"""SFT data for the assistant-side ablation. Same N conversations in every arm, identical user turns:
  A_default                     assistant regenerated without a system prompt
  B_user_persona                assistant conditioned on the user persona (paper method)
  C_user_persona_model_persona  B plus a matched model persona

Eligible: sanity pass in all three arms, split not test/validation, and the source request is not one of the
probe requests (probes come from held-out test pairs; the corpus sources were sampled independently, so the
text is checked as well).

Inputs:  one directory of assistant-regeneration JSONL per arm ({id, status, conversation}), the released
         corpus directory (--release-dir, *.jsonl with id / split / source_text), probes.jsonl.
Outputs: <out-dir>/<arm>/train.jsonl, one row per assistant turn {"id", "messages": history + that assistant
         turn}; <out-dir>/conversation_ids.json (the picked ids, reused by apertus/build_sources.py) and stats.json.

Run from the repo root:
  python -m personafactory.sft_ablation.build_sft_data --release-dir data/release \
      --arm-dir A_default=outputs/assistant/A_default --arm-dir B_user_persona=outputs/assistant/B_user_persona \
      --arm-dir C_user_persona_model_persona=outputs/assistant/C_user_persona_model_persona
"""
import argparse, glob, json, os, random, re

ARMS = ('A_default', 'B_user_persona', 'C_user_persona_model_persona')
OUT_ROOT = os.path.join(os.environ.get('PF_OUT_DIR', './outputs'), 'sft_ablation')
norm = lambda t: re.sub(r'\s+', ' ', (t or '').strip().lower())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--n', type=int, default=100000, help='conversations per arm')
    ap.add_argument('--arm-dir', action='append', required=True, metavar='ARM=DIR',
                    help=f'assistant-regeneration output directory per arm; arms: {", ".join(ARMS)}')
    ap.add_argument('--release-dir', required=True, help='released corpus directory (*.jsonl)')
    ap.add_argument('--probes', default=os.path.join(OUT_ROOT, 'probes', 'probes.jsonl'))
    ap.add_argument('--out-dir', default=os.path.join(OUT_ROOT, 'sft_data'))
    a = ap.parse_args()
    arm_dirs = dict(x.split('=', 1) for x in a.arm_dir)
    if set(arm_dirs) != set(ARMS):
        raise SystemExit(f'need exactly one --arm-dir for each of {ARMS}, got {sorted(arm_dirs)}')

    probe_reqs = {norm(json.loads(l)['request']) for l in open(a.probes, encoding='utf-8')}
    meta = {}
    for fp in glob.glob(os.path.join(a.release_dir, '*.jsonl')):
        for l in open(fp, encoding='utf-8'):
            r = json.loads(l)
            meta[r['id']] = (r.get('split'), norm(r.get('source_text')))
    conv = {}
    for name in ARMS:
        conv[name] = {}
        for fp in glob.glob(os.path.join(arm_dirs[name], '*.jsonl')):
            for l in open(fp, encoding='utf-8'):
                x = json.loads(l)
                if x.get('status') == 'pass' and x.get('conversation'):
                    conv[name][x['id']] = x['conversation']
    ok = set.intersection(*(set(v) for v in conv.values()))
    stats = {'pass_all_arms': len(ok)}
    ok = {i for i in ok if meta.get(i, ('x',))[0] not in ('test', 'validation')}
    stats['train_split'] = len(ok)
    ok = {i for i in ok if meta[i][1] not in probe_reqs}
    stats['after_probe_overlap'] = len(ok)
    pick = sorted(ok)
    random.Random(20260925).shuffle(pick)
    pick = pick[:a.n]
    stats['picked'] = len(pick)
    for name in ARMS:
        os.makedirs(os.path.join(a.out_dir, name), exist_ok=True)
        rows = 0
        with open(os.path.join(a.out_dir, name, 'train.jsonl'), 'w', encoding='utf-8') as fh:
            for i in pick:
                c = conv[name][i]
                for t in range(1, len(c), 2):
                    if c[t]['role'] == 'assistant' and c[t]['content'].strip():
                        fh.write(json.dumps({'id': f'{i}#{t // 2}', 'messages': c[:t + 1]}, ensure_ascii=False) + '\n')
                        rows += 1
        stats['rows_' + name] = rows
    json.dump({'ids': pick}, open(os.path.join(a.out_dir, 'conversation_ids.json'), 'w'))
    json.dump(stats, open(os.path.join(a.out_dir, 'stats.json'), 'w'), indent=1)
    print(json.dumps(stats, indent=1))


if __name__ == '__main__':
    main()
