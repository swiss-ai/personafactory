"""Assistant regeneration without a persona, shared by arm A0r (a0r.py) and arm X1 (x_arms.py).

Each conversation keeps its released responder (Gemma 4 31B or Ministral 3 14B) and runs through the pipeline's
own conversation loop (augmentation.pipeline.process_conversation) with fixed user turns: no persona rewrite, no
persona system prompt, no model persona, the next-turn continuity loop and the MiniMax-M2.5 sanity gate as in the
corpus. For X1 every seed user turn is first translated into the persona's language by the pipeline's persona-blind
translation step (augmentation.pipeline.translate_turn: Gemma, temperature 0.3, protected spans, LID check).
Output records: {id, responder, status (pass / fail / error / translate_fail), conversation, sanity_verdicts}.
Resumable by id per shard."""
import asyncio, copy, json, os

import aiohttp

from personafactory.assistant.shared import bank_for, done_ids, responders, setup_judge
from personafactory.augmentation import pipeline
from personafactory.augmentation.run_augmentation import BASE_CONFIG, lang_ok
from personafactory.downstream.common import load_bank


def add_args(ap):
    from personafactory.assistant.shared import add_server_args
    ap.add_argument('--bank', default=os.environ.get('PF_BANK', 'swiss-ai/PersonaFactory:persona_bank'),
                    help='persona bank (JSONL, parquet or hub id:config; default PF_BANK)')
    ap.add_argument('--shards', nargs='+', help='input shard file names (default: all in the input dir)')
    ap.add_argument('--concurrency', type=int, default=160)
    ap.add_argument('--lid-model', default=os.environ.get('PF_LID_MODEL'), help='fastText lid.176 model for the X1 translation check')
    add_server_args(ap)


def _bank(spec, ids):
    if os.path.isfile(spec) and spec.endswith('.jsonl'):
        return bank_for(spec, ids)
    return load_bank(spec, ids)


async def run(a, input_dir, out_dir, translate):
    shards = a.shards or sorted(f for f in os.listdir(input_dir) if f.endswith('.jsonl'))
    recs = {sh: [json.loads(l) for l in open(os.path.join(input_dir, sh), encoding='utf-8')] for sh in shards}
    bank = _bank(a.bank, {r['persona_id'] for rs in recs.values() for r in rs})
    judge = setup_judge(a)
    base = copy.deepcopy(BASE_CONFIG)
    base['responders'] = responders(a)
    base['judge'] = judge
    if translate:
        from personafactory.common import lid
        lid.init(a.lid_model)
    base['_lang_ok'] = lang_ok if translate else (lambda t, l: True)
    os.makedirs(out_dir, exist_ok=True)
    sem = asyncio.Semaphore(a.concurrency)
    stats = {}
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=a.concurrency * 3),
                                     timeout=aiohttp.ClientTimeout(total=900)) as session:
        work = []
        for sh, rs in recs.items():
            fp = os.path.join(out_dir, sh)
            done = done_ids(fp)
            fh = open(fp, 'a', encoding='utf-8')
            work += [(r, fh) for r in rs if r['id'] not in done]
        print('to process', len(work), flush=True)

        async def one(r, fh):
            async with sem:
                rec = None
                if translate:
                    tr = []
                    for u in r['users']:
                        try:
                            tr.append(await pipeline.translate_turn(session, base, u, r['lang']))
                        except Exception:
                            tr.append(None)
                            break
                    if any(t is None for t in tr):
                        rec = {'id': r['id'], 'status': 'translate_fail', 'translations': tr}
                    fixed = [{'user_message': t, 'user_message_original': t, 'persona_applied': False} for t in tr]
                else:
                    fixed = r['fixed']
                if rec is None:
                    cfg = dict(base)
                    cfg['persona'] = dict(base['persona'], language_match=False, cross_lingual=False, inject_system_prompt=False)
                    cfg['_assigned'] = {'persona': bank[r['persona_id']], 'match_tier': None, 'responder': r['responder'],
                                        'target_language': None}
                    cfg['_fixed'] = fixed
                    cfg['_model_persona'] = None
                    src = []
                    for fx in fixed:
                        src += [{'role': 'user', 'content': fx['user_message_original']}, {'role': 'assistant', 'content': ''}]
                    try:
                        res = await pipeline.process_conversation(session, src, cfg, r['id'])
                        md = res['metadata']
                        rec = {'id': r['id'], 'responder': r['responder'], 'status': 'pass' if md.get('sanity_pass') else 'fail',
                               'conversation': res['conversation'], 'sanity_verdicts': md.get('sanity_verdicts'),
                               'adaptations': [td.get('num_adaptations', 0) for td in md.get('turns_detail') or []]}
                    except Exception as exc:
                        rec = {'id': r['id'], 'status': 'error', 'exception': f'{type(exc).__name__}: {exc}'[:300]}
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
            fh.flush()
            stats[rec['status']] = stats.get(rec['status'], 0) + 1
            if sum(stats.values()) % 500 == 0:
                print(json.dumps(stats), flush=True)

        await asyncio.gather(*(one(r, fh) for r, fh in work))
    print('final', json.dumps(stats), flush=True)
