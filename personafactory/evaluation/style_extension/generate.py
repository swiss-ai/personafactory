#!/usr/bin/env python3
"""Style-extension A/B generation: the augmentation user side (augmentation.pipeline.process_conversation, the
production settings of augmentation.run_augmentation, Gemma responder) on the prep.py pairs, with one of three
persona inputs:
  A  source as is: the original Nemotron-Personas / PersonaHub record as background, no writing style
  B  background only: our converted background (get_persona_background_str), no writing style
  C  full extension: converted background + generated style layer (the normal pipeline)
Only the persona text in the rewrite prompt and the responder system prompt changes; persona language checks,
seeds and targets are identical across arms.

Output OUT/gen/{arm}-{mode}.jsonl, one wrapper per pair (status pass / fail / lang_fail / error), resumable by key.

Usage (one process per arm; Gemma replicas serve the rewriter, translator and responder, MiniMax the sanity judge):
    python -m personafactory.evaluation.style_extension.generate --arm C --dir ./outputs/style_extension \\
        --gemma http://HOST:8000/v1 http://HOST:8001/v1 --minimax http://HOST2:30000/v1 --lid-model $PF_LID_MODEL
"""
import argparse, asyncio, collections, copy, hashlib, json, os, time

import aiohttp

from personafactory.augmentation import pipeline as H
from personafactory.augmentation.run_augmentation import BASE_CONFIG, lang_ok
from personafactory.common import lid

NO_STYLE = 'Not specified. Infer how this person would plausibly write from their background.'


def source_text(p):
    return '\n'.join(f'{k}: {v}' for k, v in p['source']['record'].items())


def set_arm(arm):
    if arm == 'A':
        H.get_persona_background_str = source_text
    if arm in ('A', 'B'):
        H.get_persona_style_str = lambda p, *a, **k: NO_STYLE


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--arm', choices=('A', 'B', 'C'), required=True)
    ap.add_argument('--dir', required=True, help='prep.py output dir')
    ap.add_argument('--gemma', nargs='+', required=True, help='Gemma base URL(s) (.../v1), served as --gemma-model')
    ap.add_argument('--gemma-model', default='gemma')
    ap.add_argument('--minimax', required=True, help='MiniMax-M2.5 base URL (.../v1), the sanity judge')
    ap.add_argument('--minimax-model', default='MiniMax-M2.5')
    ap.add_argument('--lid-model', default=os.environ.get('PF_LID_MODEL'), help='fastText lid.176 model (PF_LID_MODEL)')
    ap.add_argument('--concurrency', type=int, default=100)
    a = ap.parse_args()
    set_arm(a.arm)
    lid.init(a.lid_model)
    key = os.environ.get('PF_API_KEY', 'dummy')
    bank = {}
    for l in open(a.dir + '/personas.jsonl', encoding='utf-8'):
        p = json.loads(l)
        bank[p['id']] = p
    assign = {}
    for l in open(a.dir + '/assign.jsonl'):
        r = json.loads(l)
        assign[r['pair_key']] = r
    os.makedirs(a.dir + '/gen', exist_ok=True)
    t0 = time.time()
    stats = collections.Counter()
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=a.concurrency * 3),
                                     timeout=aiohttp.ClientTimeout(total=900)) as session:
        sem = asyncio.Semaphore(a.concurrency)
        work, handles = [], []
        for mode in ('free', 'multilingual'):
            config = copy.deepcopy(BASE_CONFIG)
            config['persona']['language_match'] = mode == 'free'
            config['persona']['cross_lingual'] = False
            config['responders'] = [{'name': 'gemma', 'base_url': u, 'api_key': key, 'model': a.gemma_model}
                                    for u in a.gemma]
            config['judge'] = {'base_url': a.minimax, 'api_key': key, 'model': a.minimax_model}
            config['_lang_ok'] = lang_ok
            out = f'{a.dir}/gen/{a.arm}-{mode}.jsonl'
            done = set()
            if os.path.exists(out):
                for l in open(out, encoding='utf-8'):
                    try:
                        done.add(json.loads(l)['key'])
                    except Exception:
                        pass
            fh = open(out, 'a', encoding='utf-8')
            handles.append(fh)
            for l in open(f'{a.dir}/pairs_{mode}.jsonl', encoding='utf-8'):
                p = json.loads(l)
                k = hashlib.sha256(json.dumps(['style-ab', a.arm, p['pair_key']]).encode()).hexdigest()
                if k not in done:
                    work.append((p, k, config, fh))

        async def one(p, k, config, fh):
            asg = assign[p['pair_key']]
            wrap = {'key': k, 'arm': a.arm, 'pair_key': p['pair_key'], 'mode': asg['mode'], 'persona_id': asg['persona_id'],
                    'persona_source': asg['persona_source'], 'target_language': asg['target_language'],
                    'source_name': p.get('source_name')}
            cfg = dict(config)
            cfg['_assigned'] = {'persona': bank[asg['persona_id']], 'match_tier': 'style_ab', 'responder': 'gemma',
                                'target_language': asg['target_language']}
            async with sem:
                try:
                    res = await H.process_conversation(session, p['conversation'], cfg, k)
                    md = res.get('metadata', {})
                    md.pop('persona', None)   # the persona is in personas.jsonl; keep the output small
                    first = next((m['content'] for m in res.get('conversation', []) if m['role'] == 'user'), '')
                    if md.get('status') != 'success' or not res.get('conversation'):
                        status = 'error'
                    elif asg['target_language'] and not lang_ok(first, asg['target_language']):
                        status = 'lang_fail'
                    else:
                        status = 'pass' if md.get('sanity_pass') else 'fail'
                    res['source_conversation'] = p['conversation']
                    wrap.update(status=status, result=res)
                except Exception as exc:
                    wrap.update(status='error', result=None, exception=f'{type(exc).__name__}: {exc}'[:500])
            fh.write(json.dumps(wrap, ensure_ascii=False) + '\n')
            fh.flush()
            stats[wrap['status']] += 1
            n = sum(stats.values())
            if n % 100 == 0:
                print(json.dumps({**stats, 'elapsed_min': round((time.time() - t0) / 60, 1)}), flush=True)

        await asyncio.gather(*(one(*w) for w in work))
        for fh in handles:
            fh.close()
    print('final', a.arm, json.dumps(stats), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
