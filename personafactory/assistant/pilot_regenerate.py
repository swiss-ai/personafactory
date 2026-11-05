#!/usr/bin/env python3
"""Model-persona pilots (paper appendix): sample source conversations, match model personas, and regenerate the
assistant side with the user turns fixed. Evaluate with assistant.pilot_eval; the restyled arm comes from
assistant.pilot_restyle.

Source conversations are accepted records written by augmentation.run_augmentation (fields key, mode,
persona_id, match_tier, responder, target_language, result). The source record itself is the `source` arm:
the reply generated with the user persona in the system prompt.

Steps:
  sample      draw the pilot set from accepted run outputs that are in the released corpus: --n-random random
              conversations plus --n-instruction conversations whose later user turns carry an explicit
              format/length/style instruction. Writes <source-dir>/sample.jsonl.
              (The design pilot instead uses all accepted records of a small pilot run as <source-dir>.)
  match       the judge model ranks the model personas per conversation from the reduced user card and the first
              user message (options shuffled per conversation); the top-ranked id is the match. A random persona
              different from the match (fixed hash) is drawn for the random-persona arm. Writes <out-dir>/match.jsonl.
  regenerate  one arm (--arm), written to <out-dir>/arm_<arm>.jsonl (resumable). Same responder model as the
              source conversation; persona system prompt, continuity loop and sanity gate as in the pipeline.

Arms:
  default                            no system prompt (no user background, no model persona)
  default_resample                   as default, an independent second sample (content-drift noise floor)
  user_persona                       the paper's persona system prompt, regenerated (sampling-drift control)
  model_persona                      matched model persona only, no user background
  user_persona_model_persona         persona system prompt + matched model persona (the release setup)
  user_persona_random_model_persona  persona system prompt + random model persona

Design pilot: source, user_persona, user_persona_model_persona, user_persona_random_model_persona, restyled.
Main pilot:   source, default, default_resample, model_persona, user_persona_model_persona.

  python -m personafactory.assistant.pilot_regenerate sample --runs './outputs/generated/*.jsonl' --corpus-dir ./data/corpus \
      --source-dir ./outputs/pilot_main/src --n-random 700 --n-instruction 300
  python -m personafactory.assistant.pilot_regenerate match --source-dir ./outputs/pilot_main/src --out-dir ./outputs/pilot_main \
      --bank $PF_BANK --minimax $MINIMAX_URL
  python -m personafactory.assistant.pilot_regenerate regenerate --arm default --source-dir ./outputs/pilot_main/src \
      --out-dir ./outputs/pilot_main --bank $PF_BANK --lid-model $PF_LID_MODEL \
      --gemma $GEMMA_URL --ministral $MINISTRAL_URL --minimax $MINIMAX_URL
"""
import argparse, asyncio, collections, copy, glob, json, os, random
import aiohttp
from personafactory.assistant import model_persona
from personafactory.assistant.shared import accepted_records, add_server_args, bank_for, h, parse_ranking, responders, setup_judge
from personafactory.common import judge_client

ARMS = ('default', 'default_resample', 'user_persona', 'model_persona', 'user_persona_model_persona',
        'user_persona_random_model_persona')
NO_BACKGROUND = ('default', 'default_resample', 'model_persona')  # no user background in the assistant context


def load_matches(out_dir):
    return {json.loads(l)['key']: json.loads(l) for l in open(os.path.join(out_dir, 'match.jsonl'))}


def cmd_sample(a):
    rel = set()
    for fp in glob.glob(os.path.join(a.corpus_dir, '*.jsonl')):
        for l in open(fp, encoding='utf-8'):
            rel.add(json.loads(l)['id'])
    pool, instr = [], []
    for fp in sorted(glob.glob(a.runs)):
        for l in open(fp, encoding='utf-8'):
            r = json.loads(l)
            if r['status'] != 'pass' or r['key'] not in rel:
                continue
            tds = r['result']['metadata']['turns_detail']
            has = any(model_persona.INSTRUCTION_RX.search(td.get('user_message_source') or td.get('user_message_original') or '')
                      for td in tds[1:])
            (instr if has else pool).append(l if l.endswith('\n') else l + '\n')
    rng = random.Random(a.seed)
    pick = rng.sample(instr, min(a.n_instruction, len(instr))) + rng.sample(pool, a.n_random)
    os.makedirs(a.source_dir, exist_ok=True)
    open(os.path.join(a.source_dir, 'sample.jsonl'), 'w', encoding='utf-8').write(''.join(pick))
    print(json.dumps({'corpus_ids': len(rel), 'eligible_with_later_instruction': len(instr), 'eligible_other': len(pool),
                      'picked': len(pick)}))


async def cmd_match(a):
    setup_judge(a)
    recs = accepted_records(a.source_dir)
    bank = bank_for(a.bank, {r['persona_id'] for r in recs})
    ids = [p['id'] for p in model_persona.PERSONAS]
    os.makedirs(a.out_dir, exist_ok=True)
    sem = asyncio.Semaphore(a.concurrency)
    out = []
    async with aiohttp.ClientSession() as session:
        async def one(r):
            order = ids[:]
            random.Random(h(r['key'], 'mp-order')).shuffle(order)
            first = r['result']['metadata']['turns_detail'][0]['user_message']
            prompt = model_persona.MATCH_PROMPT.format(card=model_persona.reduced_user_card(bank[r['persona_id']]),
                                                       message=first, options=model_persona.match_options(order))
            rk = reason = None
            async with sem:
                for _ in range(3):
                    text, _fin = await judge_client.ask(session, prompt, 4096)
                    rk, reason = parse_ranking(text)
                    if rk:
                        break
            matched = rk[0] if rk else None
            others = [i for i in ids if i != matched]
            out.append({'key': r['key'], 'mode': r['mode'], 'persona_id': r['persona_id'], 'matched': matched,
                        'ranking': rk, 'reason': reason,
                        'random': others[h(r['key'], 'mp-random') % len(others)]})
        await asyncio.gather(*(one(r) for r in recs))
    with open(os.path.join(a.out_dir, 'match.jsonl'), 'w') as fh:
        for x in out:
            fh.write(json.dumps(x, ensure_ascii=False) + '\n')
    print(json.dumps({'conversations': len(out), 'unmatched': sum(x['matched'] is None for x in out),
                      'matched_distribution': collections.Counter(x['matched'] for x in out).most_common()}, indent=1))


async def cmd_regenerate(a):
    from personafactory.augmentation import pipeline
    from personafactory.augmentation.run_augmentation import BASE_CONFIG, lang_ok
    from personafactory.common import lid
    lid.init(ftz=a.lid_model)
    recs = accepted_records(a.source_dir)
    bank = bank_for(a.bank, {r['persona_id'] for r in recs})
    mt = load_matches(a.out_dir)
    base = copy.deepcopy(BASE_CONFIG)
    # comma-separated server lists: each call picks one replica of the conversation's model
    base['responders'] = responders(a)
    base['judge'] = setup_judge(a)
    base['_lang_ok'] = lang_ok
    out_fp = os.path.join(a.out_dir, f'arm_{a.arm}.jsonl')
    done = set()
    if os.path.exists(out_fp):
        done = {json.loads(l)['key'] for l in open(out_fp)}
    fh = open(out_fp, 'a', encoding='utf-8')
    sem = asyncio.Semaphore(a.concurrency)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=a.concurrency * 3),
                                     timeout=aiohttp.ClientTimeout(total=900)) as session:
        async def one(r):
            m = mt.get(r['key'])
            if r['key'] in done or not m or not m['matched']:
                return
            mp_id = {'default': None, 'default_resample': None, 'user_persona': None, 'model_persona': m['matched'],
                     'user_persona_model_persona': m['matched'], 'user_persona_random_model_persona': m['random']}[a.arm]
            cfg = dict(base)
            cfg['persona'] = dict(base['persona'], language_match=r['mode'] == 'free', cross_lingual=False,
                                  inject_system_prompt=a.arm not in NO_BACKGROUND)
            cfg['_assigned'] = {'persona': bank[r['persona_id']], 'match_tier': r['match_tier'],
                                'responder': r['responder'], 'target_language': r['target_language']}
            cfg['_fixed'] = r['result']['metadata']['turns_detail']
            cfg['_model_persona'] = model_persona.BY_ID[mp_id] if mp_id else None
            async with sem:
                try:
                    res = await pipeline.process_conversation(session, r['result']['source_conversation'], cfg, r['key'])
                    status = 'pass' if res['metadata'].get('sanity_pass') else 'fail'
                except Exception as exc:
                    res, status = None, 'error: ' + f'{type(exc).__name__}: {exc}'[:300]
            fh.write(json.dumps({'key': r['key'], 'arm': a.arm, 'mode': r['mode'], 'responder': r['responder'],
                                 'model_persona': mp_id, 'status': status, 'result': res}, ensure_ascii=False) + '\n')
            fh.flush()
        await asyncio.gather(*(one(r) for r in recs))
    fh.close()
    print(a.arm, dict(collections.Counter(json.loads(l)['status'][:5] for l in open(out_fp))), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('step', choices=('sample', 'match', 'regenerate'))
    ap.add_argument('--source-dir', required=True, help='directory with the accepted source records (*.jsonl)')
    ap.add_argument('--out-dir', help='pilot output directory (match.jsonl, arm_<arm>.jsonl)')
    ap.add_argument('--bank', default=os.environ.get('PF_BANK'))
    ap.add_argument('--arm', choices=ARMS)
    ap.add_argument('--concurrency', type=int, default=80)
    ap.add_argument('--lid-model', default=os.environ.get('PF_LID_MODEL'), help='fastText lid.176 model (regenerate)')
    ap.add_argument('--runs', help='sample: glob of accepted run outputs')
    ap.add_argument('--corpus-dir', help='sample: released corpus shards (only conversations in the corpus are drawn)')
    ap.add_argument('--n-random', type=int, default=700)
    ap.add_argument('--n-instruction', type=int, default=300)
    ap.add_argument('--seed', type=int, default=20260924)
    add_server_args(ap, judge_required=False)
    a = ap.parse_args()
    if a.step == 'sample':
        assert a.runs and a.corpus_dir, 'sample needs --runs and --corpus-dir'
        return cmd_sample(a)
    assert a.out_dir and a.bank and a.minimax, 'match / regenerate need --out-dir, --bank (or PF_BANK) and --minimax'
    if a.step == 'match':
        asyncio.run(cmd_match(a))
    else:
        assert a.arm and a.lid_model, 'regenerate needs --arm and --lid-model (or PF_LID_MODEL)'
        asyncio.run(cmd_regenerate(a))


if __name__ == '__main__':
    main()
