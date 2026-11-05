#!/usr/bin/env python3
"""Corpus-judge items for a random sample of the seed-pool conversations of the release, plus the sanity-gate
outcome counts of the whole seed-pool generation.

Same templates and inputs as evaluation.corpus_judge.prep_items (one item per user turn):
  intent: original vs rewritten user turn. Language-matched setting: the source turn. Cross-lingual setting: the
          literal translation the rewriter restyled (user_message_original), since the intent template fails any
          language switch; the English-source variant is stored as well.
  style:  persona background + writing style (the persona the generator saw) vs rewritten turn.
Rewritten turns come from the current release (after all quality stages); originals and personas come from the
generation output (<run>/gen). Sampled conversations that are not in that output (low-resource regenerations) are
skipped and counted. Items go to <out>/items/NNN.jsonl (--shards files) for evaluation.corpus_judge.run_judge;
<out>/gen_status.json counts generation status by mode x source x responder; <out>/prep.json the item counts.

  python -m personafactory.postprocess.judge_sample_prep --release-dir ./release_merged --gen ./outputs/seeds_run/gen \\
      --out ./outputs/judge_sample --n 25000
"""
import argparse, collections, glob, hashlib, json, os, random
from multiprocessing import Pool

from personafactory.augmentation.pipeline import get_persona_background_str as bg_str, get_persona_style_str as style_str
from personafactory.augmentation.prompts import VALIDATE_PERSONA_INTENT_TEMPLATE as INTENT, VALIDATE_PERSONA_STYLE_TEMPLATE as STYLE

SAMPLE = set()


def scan(fp):
    st, hits = collections.Counter(), {}
    for l in open(fp, encoding='utf-8'):
        if not l.strip():
            continue
        try:
            r = json.loads(l)
        except ValueError:
            continue
        st[(r['mode'], str(r['source_name']), r['responder'], r['status'])] += 1
        if r['key'] in SAMPLE and r['status'] == 'pass':
            md = r['result']['metadata']
            hits[r['key']] = {'td': [(t.get('user_message_source'), t.get('user_message_original')) for t in md['turns_detail']],
                              'persona': md['persona']}
    return st, hits


def main():
    global SAMPLE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release-dir', required=True)
    ap.add_argument('--gen', required=True, help='seed-pool generation output directory (<run>/gen)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--n', type=int, default=25000, help='sampled conversations')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--shards', type=int, default=8)
    ap.add_argument('--part', default='seeds', help='release_part label of the seed-pool records')
    ap.add_argument('--workers', type=int, default=64)
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, 'items'), exist_ok=True)
    os.makedirs(os.path.join(a.out, 'results'), exist_ok=True)
    files = sorted(glob.glob(os.path.join(a.release_dir, 'data', '*.jsonl')))
    recs = {}
    for fp in files:
        for l in open(fp, encoding='utf-8'):
            r = json.loads(l)
            if r['release_part'] == a.part:
                recs[r['id']] = None
    ids = sorted(recs)
    SAMPLE = set(random.Random(a.seed).sample(ids, a.n))
    print('seed-pool conversations', len(ids), 'sample', len(SAMPLE), flush=True)
    for fp in files:
        for l in open(fp, encoding='utf-8'):
            r = json.loads(l)
            if r['id'] in SAMPLE:
                recs[r['id']] = r
    st, gen = collections.Counter(), {}
    with Pool(a.workers) as pool:  # forked after SAMPLE is set
        for s, h in pool.imap_unordered(scan, sorted(glob.glob(os.path.join(a.gen, '*.jsonl')))):
            st.update(s)
            gen.update(h)
    json.dump({'/'.join(k): v for k, v in sorted(st.items())}, open(os.path.join(a.out, 'gen_status.json'), 'w'), indent=1)
    sinks = [open(os.path.join(a.out, 'items', f'{i:03d}.jsonl'), 'w', encoding='utf-8') for i in range(a.shards)]
    c = collections.Counter()
    for i in sorted(SAMPLE):
        r, g = recs[i], gen.get(i)
        if g is None:
            c['skip_not_in_gen'] += 1
            continue
        c['conversations'] += 1
        users = [m['content'] for m in r['conversation'] if m['role'] == 'user']
        p = g['persona']
        bgs, sty = bg_str(p), style_str(p, include_quirks=True)
        multi = r['language_mode'] == 'multilingual'
        for t, rw in enumerate(users):
            if t >= len(g['td']):
                break
            source, loc = g['td'][t]
            base = (loc or source) if multi else source
            item = {'key': f'{i}#{t}', 'part': a.part, 'mode': r['language_mode'], 'lang': r['text_language'],
                    'cohort': r.get('cohort'), 'responder': r['responder'], 'source_name': r['source_name'], 'turn': t,
                    'changed': rw.strip() != (base or '').strip(),
                    'intent_basis': 'translation_baseline' if multi else 'source',
                    'intent_prompt': INTENT.format(original_message=base, rewritten_message=rw),
                    'style_prompt': STYLE.format(background=bgs, writing_style=sty, rewritten_message=rw)}
            if multi:
                item['intent_prompt_vs_english_source'] = INTENT.format(original_message=source, rewritten_message=rw)
            sinks[int(hashlib.md5(item['key'].encode()).hexdigest(), 16) % a.shards].write(json.dumps(item, ensure_ascii=False) + '\n')
            c['turns'] += 1
    for s in sinks:
        s.close()
    json.dump(dict(c), open(os.path.join(a.out, 'prep.json'), 'w'), indent=1)
    print(dict(c), flush=True)


if __name__ == '__main__':
    main()
