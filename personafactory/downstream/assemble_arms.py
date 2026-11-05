#!/usr/bin/env python3
"""The four language-matched arms on one shared id set:

  A0   original seed conversation                                   (<work>/data/A0_source.jsonl)
  A1   styled user turns + original assistant turns                 (<work>/data/A1_source.jsonl)
  A0r  original user turns + assistant regenerated without persona  (<work>/a0r/out, status pass)
  A2   the released conversation: styled user turns + assistant turns regenerated for that user

Ids: the build_arms.py ids whose A0r regeneration passed the sanity gate and whose conversation fits the packing
window in every arm (contents plus 10 tokens per turn <= --max-tokens). Conversations that fail in one arm are
removed from all arms (79,817 conversations in the paper). Writes <work>/data_paired/{A0,A1,A0r,A2}_source.jsonl and
<work>/data_paired/manifest.json (counts, median assistant characters per arm, verbatim user-turn fraction).

  python -m personafactory.downstream.assemble_arms --work $PF_OUT_DIR/downstream --release swiss-ai/PersonaFactory \
      --tokenizer $PF_MODEL_DIR/Apertus-v1.5-8B
"""
import argparse, glob, json, os, statistics

from personafactory.downstream.common import HF_REPO, MAX_TOKENS, clean, load_release, sha256_file, token_counter


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--work', default=os.path.join(os.environ.get('PF_OUT_DIR', './outputs'), 'downstream'))
    ap.add_argument('--release', default=HF_REPO)
    ap.add_argument('--tokenizer', required=True, help='Apertus tokenizer (tokenizer.json, model dir or hub id)')
    ap.add_argument('--max-tokens', type=int, default=MAX_TOKENS)
    ap.add_argument('--out-name', default='data_paired')
    a = ap.parse_args()
    arms, base = {'A0': {}, 'A1': {}}, {}
    for name in ('A0', 'A1'):
        for line in open(os.path.join(a.work, 'data', f'{name}_source.jsonl'), encoding='utf-8'):
            r = json.loads(line)
            arms[name][r['id']] = r['messages']
            base[r['id']] = {k: r[k] for k in ('id', 'family_id', 'language', 'response_mode', 'training_role')}
    status, arms['A0r'] = {}, {}
    for fp in glob.glob(os.path.join(a.work, 'a0r', 'out', '*.jsonl')):
        for line in open(fp, encoding='utf-8'):
            r = json.loads(line)
            status[r['id']] = r['status']
            if r['status'] == 'pass':
                c = clean(r['conversation'])
                if c and len(c) == len(arms['A0'][r['id']]):
                    arms['A0r'][r['id']] = c
    arms['A2'] = {}
    for r in load_release(a.release):
        if r['id'] in base:
            c = clean(r['messages'])
            if c and len(c) == len(arms['A1'][r['id']]):
                arms['A2'][r['id']] = c
    ids = sorted(set.intersection(*(set(v) for v in arms.values())))
    ntok = token_counter(a.tokenizer)
    n_common = len(ids)
    ids = [i for i in ids if max(ntok(d[i]) for d in arms.values()) <= a.max_tokens]
    out = os.path.join(a.work, a.out_name)
    os.makedirs(out, exist_ok=True)
    vals = list(status.values())
    man = {'n': len(ids), 'dropped_over_token_cap': n_common - len(ids), 'a0r_status': {s: vals.count(s) for s in set(vals)},
           'per_arm_available': {k: len(v) for k, v in arms.items()}, 'median_assistant_chars': {}, 'sha256': {}}
    for name, d in arms.items():
        fp = os.path.join(out, f'{name}_source.jsonl')
        with open(fp, 'w', encoding='utf-8') as fh:
            for i in ids:
                fh.write(json.dumps(dict(base[i], messages=d[i]), ensure_ascii=False) + '\n')
        man['median_assistant_chars'][name] = statistics.median(len(m['content']) for i in ids for m in d[i] if m['role'] == 'assistant')
        man['sha256'][name] = sha256_file(fp)
    a0u = [m['content'].strip() for i in ids for m in arms['A0'][i] if m['role'] == 'user']
    a2u = [m['content'].strip() for i in ids for m in arms['A2'][i] if m['role'] == 'user']
    man['verbatim_user_turn_fraction_A2'] = round(sum(x == y for x, y in zip(a0u, a2u)) / max(1, len(a0u)), 4)
    json.dump(man, open(os.path.join(out, 'manifest.json'), 'w'), indent=1)
    print(json.dumps(man, indent=1))


if __name__ == '__main__':
    main()
