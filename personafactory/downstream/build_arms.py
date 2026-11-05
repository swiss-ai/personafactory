#!/usr/bin/env python3
"""Arms A0 and A1 of the downstream fine-tuning experiment (language-matched conversations).

  A0  the original seed conversation (user and assistant turns as in WildChat / UltraChat / Nemotron)
  A1  the released persona-styled user turns with the original seed assistant turns

Population: language-matched released conversations whose seed was recovered (seeds.py). 5% of all persona ids are
held out (fixed hash, common.heldout) and every conversation of a held-out persona is dropped; those personas are
used for the persona-rewritten evaluation prompts. Conversations that are malformed, whose user-turn count differs
between release and seed, longer than --max-chars characters, or over --max-tokens Apertus tokens (contents plus
10 per turn, the larger of the two arms) are dropped. --n conversations are sampled (fixed seed); both arms share ids,
order and assistant turns. Arms A0r and A2 are added on the same ids by a0r.py and assemble_arms.py.

Writes <work>/data/{A0,A1}_source.jsonl (Megatron prepare schema: id, family_id, language, response_mode,
training_role, messages), <work>/data/heldout_personas.json and <work>/data/manifest.json.

  python -m personafactory.downstream.build_arms --release swiss-ai/PersonaFactory \
      --seeds $PF_OUT_DIR/downstream/seeds_language_matched.jsonl --tokenizer $PF_MODEL_DIR/Apertus-v1.5-8B \
      --work $PF_OUT_DIR/downstream
"""
import argparse, collections, hashlib, json, os, random

from personafactory.downstream.common import (HELDOUT_FRAC, HELDOUT_SEED, HF_REPO, MAX_TOKENS, clean, heldout,
                                              load_release, sft_record, sha256_file, token_counter)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release', default=HF_REPO, help='released chats: hub id, local snapshot / parquet, or release dir')
    ap.add_argument('--seeds', required=True, help='seeds.py output for the language-matched setting')
    ap.add_argument('--tokenizer', required=True, help='Apertus tokenizer (tokenizer.json, model dir or hub id)')
    ap.add_argument('--work', default=os.path.join(os.environ.get('PF_OUT_DIR', './outputs'), 'downstream'))
    ap.add_argument('--n', type=int, default=100000)
    ap.add_argument('--heldout-frac', type=float, default=HELDOUT_FRAC)
    ap.add_argument('--max-chars', type=int, default=24000)
    ap.add_argument('--max-tokens', type=int, default=MAX_TOKENS)
    ap.add_argument('--seed', default=HELDOUT_SEED, help='seed of the persona hold-out and of the sample')
    ap.add_argument('--exclude-ids', default=None, help='optional file with one conversation id per line to leave out')
    a = ap.parse_args()
    out = os.path.join(a.work, 'data')
    os.makedirs(out, exist_ok=True)
    drop = collections.Counter()
    excl = {l.strip() for l in open(a.exclude_ids)} if a.exclude_ids else set()

    seeds = {}
    for line in open(a.seeds, encoding='utf-8'):
        s = json.loads(line)
        seeds[s['id']] = s['conversation']
    rel, held = {}, set()
    for r in load_release(a.release):
        if r['setting'] != 'language_matched' or r['id'] in excl:
            continue
        if heldout(r['persona_id'], a.heldout_frac, a.seed):
            held.add(r['persona_id'])
            drop['heldout_persona'] += 1
            continue
        if r['id'] not in seeds:
            drop['no_seed'] += 1
            continue
        rel[r['id']] = r
    print('release candidates', len(rel), 'held-out personas', len(held), flush=True)

    ok = []
    for k in sorted(rel):
        a0, styled = clean(seeds[k]), clean(rel[k]['messages'])
        if a0 is None or styled is None:
            drop['malformed'] += 1
            continue
        if len(a0) != len(styled):
            drop['turn_mismatch'] += 1
            continue
        a1 = [styled[i] if m['role'] == 'user' else m for i, m in enumerate(a0)]
        if max(sum(len(m['content']) for m in x) for x in (a0, a1)) > a.max_chars:
            drop['too_long'] += 1
            continue
        ok.append((k, a0, a1))
    ntok = token_counter(a.tokenizer)
    kept = [x for x in ok if max(ntok(x[1]), ntok(x[2])) <= a.max_tokens]
    drop['too_many_tokens'] = len(ok) - len(kept)
    ok = kept
    print('eligible', len(ok), dict(drop), flush=True)

    chosen = sorted(random.Random(a.seed).sample(ok, min(a.n, len(ok))))
    st, langs = collections.Counter(), collections.Counter()
    with open(os.path.join(out, 'A0_source.jsonl'), 'w', encoding='utf-8') as f0, \
            open(os.path.join(out, 'A1_source.jsonl'), 'w', encoding='utf-8') as f1:
        for k, a0, a1 in chosen:
            r = rel[k]
            f0.write(json.dumps(sft_record(k, r['language'], a0), ensure_ascii=False) + '\n')
            f1.write(json.dumps(sft_record(k, r['language'], a1), ensure_ascii=False) + '\n')
            st['conversations'] += 1
            st[f'source/{r["source"]}'] += 1
            st[f'turns/{len(a0) // 2}'] += 1
            for m0, m1 in zip(a0, a1):
                if m0['role'] == 'user':
                    st['user_turns'] += 1
                    st['user_turns_verbatim'] += m0['content'].strip() == m1['content'].strip()
                    st['user_chars_A0'] += len(m0['content'])
                    st['user_chars_A1'] += len(m1['content'])
                else:
                    st['assistant_chars'] += len(m0['content'])
            langs[r['language']] += 1
    json.dump(sorted(held), open(os.path.join(out, 'heldout_personas.json'), 'w'))
    manifest = {'n': len(chosen), 'drops': dict(drop), 'heldout_personas': len(held), 'args': vars(a),
                'sha256': {x: sha256_file(os.path.join(out, f'{x}_source.jsonl')) for x in ('A0', 'A1')},
                'verbatim_user_turn_fraction': round(st['user_turns_verbatim'] / max(1, st['user_turns']), 4),
                'stats': dict(st), 'top_languages': dict(langs.most_common(25))}
    json.dump(manifest, open(os.path.join(out, 'manifest.json'), 'w'), indent=1)
    print(json.dumps(manifest, indent=1))


if __name__ == '__main__':
    main()
