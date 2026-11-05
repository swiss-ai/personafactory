#!/usr/bin/env python3
"""Regenerate the assistant side of the released corpus with the user turns fixed as released.

Stages (run match first; the three generation stages are independent and can run concurrently):
  match                      the judge model (MiniMax-M2.5) ranks the model personas per conversation from the
                             reduced user card and the first user turn (options shuffled per conversation)
  default                    arm A: no system prompt at all
  user_persona               arm B: the paper's persona system prompt (user background and style)
  user_persona_model_persona arm C: B plus the matched model persona (style section, quirk p=0.25, content rules);
                             this is the assistant side of the released corpus
Each conversation keeps its released responder model (Gemma or Ministral); continuity loop and sanity gate as in
the augmentation pipeline. Resumable per shard. --ids regenerates only a subset (e.g. leak repair, see
assistant.leak_filter), usually with --out-name to write it to a separate directory.

Inputs: <input-dir>/<shard>.jsonl from assistant.prepare_inputs, the persona bank (--bank or PF_BANK).
Output: <out-dir>/<stage or out-name>/<shard>.jsonl. Endpoints are OpenAI-compatible base URLs ending in /v1
(comma-separated replicas; or PF_GEMMA_URL / PF_MINISTRAL_URL / PF_MINIMAX_URL), model names as served.

  python -m personafactory.assistant.regenerate_assistant --stage match --input-dir ./outputs/assistant/input \
      --out-dir ./outputs/assistant --bank $PF_BANK --minimax $MINIMAX_URL
  python -m personafactory.assistant.regenerate_assistant --stage user_persona_model_persona --input-dir ./outputs/assistant/input \
      --out-dir ./outputs/assistant --bank $PF_BANK --gemma $GEMMA_URL --ministral $MINISTRAL_URL --minimax $MINIMAX_URL
"""
import argparse, asyncio, copy, glob, json, os, random
import aiohttp
from personafactory.assistant import model_persona
from personafactory.assistant.shared import add_server_args, bank_for, done_ids, h, parse_ranking, responders, setup_judge
from personafactory.augmentation import pipeline
from personafactory.augmentation.run_augmentation import BASE_CONFIG
from personafactory.common import judge_client

STAGES = ('match', 'default', 'user_persona', 'user_persona_model_persona')


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', choices=STAGES, required=True)
    ap.add_argument('--input-dir', required=True)
    ap.add_argument('--out-dir', default=os.path.join(os.environ.get('PF_OUT_DIR', './outputs'), 'assistant'))
    ap.add_argument('--bank', default=os.environ.get('PF_BANK'), required='PF_BANK' not in os.environ)
    ap.add_argument('--shards', nargs='+', help='shard file names in --input-dir (default: all)')
    add_server_args(ap)
    ap.add_argument('--concurrency', type=int, default=100)
    ap.add_argument('--ids', help='file with one conversation id per line: only regenerate these')
    ap.add_argument('--out-name', help='output directory name under --out-dir (default: the stage name)')
    ap.add_argument('--part', default='', help='k/n: only records with hash(id) %% n == k, written to <shard>.p<k>of<n>.jsonl')
    a = ap.parse_args()
    shards = a.shards or sorted(os.path.basename(f) for f in glob.glob(os.path.join(a.input_dir, '*.jsonl')))
    part = tuple(int(x) for x in a.part.split('/')) if a.part else None
    judge = setup_judge(a)
    recs = {sh: [json.loads(l) for l in open(os.path.join(a.input_dir, sh), encoding='utf-8')] for sh in shards}
    bank = bank_for(a.bank, {r['persona_id'] for rs in recs.values() for r in rs if r['persona_id']})
    # records without a persona in the bank are skipped in every stage so all arms cover the same conversations
    recs = {sh: [r for r in rs if r['persona_id'] in bank] for sh, rs in recs.items()}
    if part:
        recs = {sh: [r for r in rs if h(r['id'], 'part') % part[1] == part[0]] for sh, rs in recs.items()}
    if a.ids:
        want = {l.strip() for l in open(a.ids) if l.strip()}
        recs = {sh: [r for r in rs if r['id'] in want] for sh, rs in recs.items()}
    out_dir = os.path.join(a.out_dir, a.out_name or a.stage)
    ids = [p['id'] for p in model_persona.PERSONAS]
    os.makedirs(out_dir, exist_ok=True)
    sem = asyncio.Semaphore(a.concurrency)
    stats = {}
    if a.stage != 'match':
        matches = {}
        for sh in shards:
            for fp in glob.glob(os.path.join(a.out_dir, 'match', sh[:-len('.jsonl')] + '*.jsonl')):
                for l in open(fp, encoding='utf-8'):
                    x = json.loads(l)
                    matches[x['id']] = x['matched']
        base = copy.deepcopy(BASE_CONFIG)
        base['responders'] = responders(a)
        base['judge'] = judge
        base['_lang_ok'] = lambda t, l: True
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=a.concurrency * 3),
                                     timeout=aiohttp.ClientTimeout(total=900)) as session:
        work = []
        for sh, rs in recs.items():
            stem = sh[:-len('.jsonl')]
            dn = set()
            for f in glob.glob(os.path.join(out_dir, stem + '*.jsonl')):  # shard file and any part files
                dn |= done_ids(f)
            fp = os.path.join(out_dir, f'{stem}.p{part[0]}of{part[1]}.jsonl' if part else sh)
            fh = open(fp, 'a', encoding='utf-8')
            work += [(r, fh) for r in rs if r['id'] not in dn]

        async def one(r, fh):
            async with sem:
                if a.stage == 'match':
                    order = ids[:]
                    random.Random(h(r['id'], 'mp-order')).shuffle(order)
                    prompt = model_persona.MATCH_PROMPT.format(card=model_persona.reduced_user_card(bank[r['persona_id']]),
                                                               message=r['fixed'][0]['user_message'],
                                                               options=model_persona.match_options(order))
                    rk = reason = None
                    for _ in range(3):
                        text, _f = await judge_client.ask(session, prompt, 4096)
                        rk, reason = parse_ranking(text)
                        if rk:
                            break
                    rec = {'id': r['id'], 'matched': rk[0] if rk else None, 'ranking': rk, 'reason': reason}
                    status = 'matched' if rk else 'unmatched'
                else:
                    with_mp = a.stage == 'user_persona_model_persona'
                    mp_id = matches.get(r['id']) if with_mp else None
                    if with_mp and not mp_id:
                        fh.write(json.dumps({'id': r['id'], 'arm': a.stage, 'status': 'unmatched'}) + '\n')
                        stats['unmatched'] = stats.get('unmatched', 0) + 1
                        return
                    cfg = dict(base)
                    cfg['persona'] = dict(base['persona'], language_match=False, cross_lingual=False,
                                          inject_system_prompt=a.stage != 'default')
                    cfg['_assigned'] = {'persona': bank[r['persona_id']], 'match_tier': None,
                                        'responder': r['responder'], 'target_language': None}
                    cfg['_fixed'] = r['fixed']
                    cfg['_model_persona'] = model_persona.BY_ID[mp_id] if mp_id else None
                    src = []
                    for fx in r['fixed']:
                        src += [{'role': 'user', 'content': fx['user_message_original']}, {'role': 'assistant', 'content': ''}]
                    try:
                        res = await pipeline.process_conversation(session, src, cfg, r['id'])
                        md = res['metadata']
                        status = 'pass' if md.get('sanity_pass') else 'fail'
                        rec = {'id': r['id'], 'arm': a.stage, 'model_persona': mp_id, 'responder': r['responder'], 'status': status,
                               'conversation': res['conversation'], 'sanity_verdicts': md.get('sanity_verdicts'),
                               'quirks': [td.get('model_persona_quirk') for td in md.get('turns_detail') or []],
                               'adaptations': [td.get('num_adaptations', 0) for td in md.get('turns_detail') or []]}
                    except Exception as exc:
                        status = 'error'
                        rec = {'id': r['id'], 'arm': a.stage, 'status': status, 'exception': f'{type(exc).__name__}: {exc}'[:300]}
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
            fh.flush()
            stats[status] = stats.get(status, 0) + 1
            if sum(stats.values()) % 500 == 0:
                print(a.stage, json.dumps(stats), flush=True)

        await asyncio.gather(*(one(r, fh) for r, fh in work))
    print('final', a.stage, json.dumps(stats), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
