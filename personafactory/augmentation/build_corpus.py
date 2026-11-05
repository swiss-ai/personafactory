#!/usr/bin/env python3
"""Corpus records from the generation output of the seed pool (CPU). Run directory layout: <run>/gen/{mode}-*.jsonl
(augmentation.run_augmentation --input-kind seeds output).

  --stage user   accepted conversations (status == pass) -> release record schema, with
                 text_language = LID of the first user turn (common.lid); a conversation id seen before and lines
                 torn by an interrupted job are skipped; dedup of the same normalized source_text in the same
                 text_language (free first, then multilingual). Writes <run>/user/data/NNNN.jsonl (--shards files,
                 by md5(id)), <run>/user/summary.json and the assistant-side inputs <run>/assistant_input/NNNN.jsonl
                 (fixed user turns, original per-turn text and persona_applied flags; the input format of
                 assistant.regenerate_assistant, used by postprocess.asst_regen_prep).
  --stage final  the assistant turns of the user-side pass are final (one pass: the responder answers under the user
                 persona system prompt, no model persona). Copies <run>/user/data to <run>/final/data with
                 sanity_verdicts and assistant_generation set; writes <run>/final/summary.json.

Record: {id, conversation, persona_id, target_language, text_language, language_mode, source_text, source_name,
         source_id, seed_language, responder, num_turns, match_basis, split, lid_verifiable, user_sanity_verdicts
         [, sanity_verdicts, assistant_generation]}

  python -m personafactory.augmentation.build_corpus --stage user --run ./outputs/seeds_run --shards 200 --workers 128
  python -m personafactory.augmentation.build_corpus --stage final --run ./outputs/seeds_run
"""
import argparse, collections, glob, hashlib, json, os, re
from multiprocessing import Pool

from personafactory.common import lid

ASSISTANT_GENERATION = 'user persona system prompt (user background + style), single pass'


def to_record(line):
    try:  # lines torn by an interrupted job are dropped (the resumed job rewrote that key)
        w = json.loads(line)
    except ValueError:
        return None, {'status': 'torn_line'}
    if w.get('status') != 'pass':
        return None, w
    res = w['result']
    md = res['metadata']
    conv = res['conversation']
    tds = md.get('turns_detail') or []
    user = next((m['content'] for m in conv if m['role'] == 'user'), '')
    src = res.get('source_conversation') or []
    rec = {'id': w['key'], 'conversation': conv, 'persona_id': w['persona_id'],
           'target_language': w.get('target_language'), 'text_language': lid.detect(user),
           'language_mode': w['mode'], 'source_text': next((m['content'] for m in src if m['role'] == 'user'), ''),
           'source_name': w.get('source_name'), 'source_id': w.get('source_id'), 'seed_language': w.get('seed_language'),
           'responder': w['responder'], 'num_turns': len(tds), 'match_basis': w['match_tier'], 'split': w.get('split'),
           'lid_verifiable': w.get('lid_verifiable'), 'user_sanity_verdicts': md.get('sanity_verdicts'),
           '_fixed': [{'user_message': td.get('user_message') or '', 'user_message_original': td.get('user_message_original') or '',
                       'persona_applied': bool(td.get('persona_applied')), 'persona_skip_reason': td.get('persona_skip_reason')}
                      for td in tds]}
    return rec, w


def stage_user(run, shards, workers, lid_model):
    st = collections.Counter()
    seen_src, seen_key = set(), set()
    os.makedirs(os.path.join(run, 'user', 'data'), exist_ok=True)
    os.makedirs(os.path.join(run, 'assistant_input'), exist_ok=True)
    sinks = [open(os.path.join(run, 'user', 'data', f'{i:04d}.jsonl'), 'w', encoding='utf-8') for i in range(shards)]
    asst = [open(os.path.join(run, 'assistant_input', f'{i:04d}.jsonl'), 'w', encoding='utf-8') for i in range(shards)]
    with Pool(workers, initializer=lid.init, initargs=(lid_model,)) as pool:
        for mode in ('free', 'multilingual'):
            def lines():
                for fp in sorted(glob.glob(os.path.join(run, 'gen', f'{mode}-*.jsonl'))):
                    for l in open(fp, encoding='utf-8'):
                        if l.strip():
                            yield l
            for rec, w in pool.imap(to_record, lines(), chunksize=32):  # ordered, so dedup is reproducible
                tag = f"{mode}/{w.get('source_name')}"
                st[f'gen/{tag}/{w["status"]}'] += 1
                if not rec:
                    continue
                if rec['id'] in seen_key:
                    st[f'drop_duplicate_key/{tag}'] += 1
                    continue
                seen_key.add(rec['id'])
                users = [m['content'] for m in rec['conversation'] if m['role'] == 'user']
                if len(rec['_fixed']) < len(users):
                    st[f'drop_missing_turn_meta/{tag}'] += 1
                    continue
                k = (hashlib.sha1(re.sub(r'\s+', ' ', rec['source_text'].strip().lower()).encode('utf-8', 'ignore')).hexdigest(), rec['text_language'])
                if k in seen_src:
                    st[f'dedup_same_source_same_language/{tag}'] += 1
                    continue
                seen_src.add(k)
                i = int(hashlib.md5(rec['id'].encode()).hexdigest(), 16) % shards
                fixed = rec.pop('_fixed')
                sinks[i].write(json.dumps(rec, ensure_ascii=False) + '\n')
                asst[i].write(json.dumps({'id': rec['id'], 'mode': mode, 'persona_id': rec['persona_id'],
                                          'responder': rec['responder'], 'split': rec['split'], 'source_name': rec['source_name'],
                                          'text_language': rec['text_language'],
                                          'fixed': [dict(fixed[t], user_message=u, user_message_original=fixed[t]['user_message_original'] or u)
                                                    for t, u in enumerate(users)]}, ensure_ascii=False) + '\n')
                st[f'user_kept/{tag}'] += 1
    for f in sinks + asst:
        f.close()
    json.dump(dict(sorted(st.items())), open(os.path.join(run, 'user', 'summary.json'), 'w'), indent=1)
    print(json.dumps(dict(sorted(st.items())), indent=1))


def stage_final(run):
    st = collections.Counter()
    os.makedirs(os.path.join(run, 'final', 'data'), exist_ok=True)
    for fp in sorted(glob.glob(os.path.join(run, 'user', 'data', '*.jsonl'))):
        with open(os.path.join(run, 'final', 'data', os.path.basename(fp)), 'w', encoding='utf-8') as fo:
            for l in open(fp, encoding='utf-8'):
                r = json.loads(l)
                tag = f"{r['language_mode']}/{r['source_name']}"
                st['in/' + tag] += 1
                r['sanity_verdicts'] = r.get('user_sanity_verdicts')
                r['assistant_generation'] = ASSISTANT_GENERATION
                fo.write(json.dumps(r, ensure_ascii=False) + '\n')
                st['kept/' + tag] += 1
    res = {'counts': dict(sorted(st.items())), 'assistant_generation': ASSISTANT_GENERATION}
    json.dump(res, open(os.path.join(run, 'final', 'summary.json'), 'w'), indent=1)
    print(json.dumps(res, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--stage', choices=('user', 'final'), required=True)
    ap.add_argument('--run', required=True, help='run directory with gen/')
    ap.add_argument('--shards', type=int, default=8)
    ap.add_argument('--workers', type=int, default=64)
    ap.add_argument('--lid-model', default=os.environ.get('PF_LID_MODEL'), help='fastText lid.176 (or PF_LID_MODEL)')
    a = ap.parse_args()
    if a.stage == 'user':
        stage_user(a.run, a.shards, a.workers, a.lid_model)
    else:
        stage_final(a.run)


if __name__ == '__main__':
    main()
