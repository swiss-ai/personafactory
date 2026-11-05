#!/usr/bin/env python3
"""Re-judge the stored structured vs flat A/B pairs with any OpenAI-compatible judge (external re-judging table).

Same pairwise prompt and inputs as re_judge_ab.py (the persona bank the original A/B used). A/B order is
randomized per item with a fixed seed; every item gets an outcome or an explicit failure class
(http_error / rate_limited / empty / unparsed), so attrition is auditable. An optional token bucket (--rpm)
keeps rate-limited hosted endpoints within quota. The API key is read from --key or PF_API_KEY.

Inputs:  --results (ab_style_test.py output), --bank, --url (base .../v1), --model
Outputs: --out JSONL: first line = summary, then one row per pair (idx, persona_id, flat_is_A, raw, outcome,
         failure, intent_flat, intent_struct)
Run:     python -m personafactory.evaluation.structured_vs_flat.ab_rejudge --results ./outputs/ab_style_results.jsonl \
             --bank ./data/bank.jsonl --url http://127.0.0.1:30000/v1 --model MiniMax-M2.5 --max-tokens 8192 \
             --out ./outputs/ab_rejudge_minimax.jsonl
"""
import argparse, asyncio, collections, json, os, random, time
import aiohttp

from personafactory.augmentation.pipeline import get_persona_background_str, get_persona_style_str
from personafactory.evaluation.structured_vs_flat.prompts import PAIRWISE


class Bucket:
    def __init__(self, rpm):
        self.gap, self.next, self.lock = 60.0 / rpm, 0.0, asyncio.Lock()

    async def wait(self):
        async with self.lock:
            now = time.monotonic()
            t = max(now, self.next)
            self.next = t + self.gap
        await asyncio.sleep(max(0, t - time.monotonic()))


async def call(session, a, prompt, bucket):
    body = {'model': a.model, 'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': a.max_tokens, 'temperature': 0.0}
    last = 'http_error'
    for attempt in range(5):
        if bucket:
            await bucket.wait()
        try:
            async with session.post(a.url.rstrip('/') + '/chat/completions', json=body,
                                    headers={'Authorization': 'Bearer ' + a.key},
                                    timeout=aiohttp.ClientTimeout(total=600)) as r:
                if r.status == 429:
                    last = 'rate_limited'
                    await asyncio.sleep(30)
                    continue
                d = await r.json()
                msg = d['choices'][0]['message']
                txt = msg.get('content') or ''
                if not txt.strip():
                    last = 'empty'
                    continue
                txt = txt.split('</think>')[-1]
                i, j = txt.find('{'), txt.rfind('}')
                if i < 0 or j < 0:
                    last = 'unparsed'
                    continue
                w = json.loads(txt[i:j + 1]).get('winner')
                if w in ('A', 'B', 'tie'):
                    return w, None
                last = 'unparsed'
        except Exception:
            last = 'http_error'
            await asyncio.sleep(3 * (attempt + 1))
    return None, last


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', required=True, help='ab_style_test.py output JSONL')
    ap.add_argument('--bank', required=True, help='persona bank the A/B used')
    ap.add_argument('--url', required=True, help='OpenAI-compatible base URL (.../v1)')
    ap.add_argument('--model', required=True)
    ap.add_argument('--key', default=os.environ.get('PF_API_KEY', 'dummy'))
    ap.add_argument('--rpm', type=float, default=0, help='requests per minute limit (0 = unlimited)')
    ap.add_argument('--concurrency', type=int, default=32)
    ap.add_argument('--max-tokens', type=int, default=3072)
    ap.add_argument('--seed', type=int, default=20260923)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(a.results)]
    status = collections.Counter(r['status'] for r in rows)
    ok = [r for r in rows if r['status'] == 'ok' and r.get('rewrite_flat') and r.get('rewrite_structured')]
    bank = {}
    for l in open(a.bank, errors='ignore'):
        if l.strip():
            d = json.loads(l)
            bank[d.get('id')] = d
    ok = [r for r in ok if r.get('persona_id') in bank]
    rng = random.Random(a.seed)
    order = [rng.random() < 0.5 for _ in ok]
    sem, bucket = asyncio.Semaphore(a.concurrency), (Bucket(a.rpm) if a.rpm else None)

    async def one(i, r, s):
        p = bank[r['persona_id']]
        flat_A = order[i]
        A, Bb = (r['rewrite_flat'], r['rewrite_structured']) if flat_A else (r['rewrite_structured'], r['rewrite_flat'])
        prompt = PAIRWISE.format(background=get_persona_background_str(p),
                                 style=get_persona_style_str(p, style_mode='both'),
                                 original=r['original'], a=A, b=Bb)
        async with sem:
            w, fail = await call(s, a, prompt, bucket)
        out = None if w is None else ('tie' if w == 'tie' else ('flat' if (w == 'A') == flat_A else 'structured'))
        return {'idx': i, 'persona_id': r['persona_id'], 'flat_is_A': flat_A, 'raw': w, 'outcome': out,
                'failure': fail, 'intent_flat': r.get('intent_flat'), 'intent_struct': r.get('intent_struct')}

    async with aiohttp.ClientSession() as s:
        res = await asyncio.gather(*(one(i, r, s) for i, r in enumerate(ok)))
    win = collections.Counter(x['outcome'] for x in res if x['outcome'])
    dec = win['structured'] + win['flat']
    both_pass = [x for x in res if x['outcome'] and x['intent_flat'] == 'pass' and x['intent_struct'] == 'pass']
    wb = collections.Counter(x['outcome'] for x in both_pass)
    summary = {'judge': a.model, 'input_status': dict(status), 'pairs': len(ok),
               'scored': sum(win.values()), 'failures': dict(collections.Counter(x['failure'] for x in res if x['failure'])),
               'outcomes': dict(win), 'structured_pct_of_decisive': round(100 * win['structured'] / dec, 1) if dec else None,
               'both_intent_pass_subset': {'n': sum(wb.values()), 'outcomes': dict(wb)},
               'position_A_win_rate': round(100 * sum(1 for x in res if x['raw'] == 'A') / max(1, sum(1 for x in res if x['raw'] in ('A', 'B'))), 1)}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'w') as f:
        f.write(json.dumps(summary) + '\n')
        for x in res:
            f.write(json.dumps(x) + '\n')
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    asyncio.run(main())
