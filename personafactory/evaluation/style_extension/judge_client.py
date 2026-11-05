#!/usr/bin/env python3
"""Judge style-extension A/B items (items.py) against OpenAI-compatible endpoints.

Settings as the corpus judge: temperature 0.1, --max-tokens on the first try (2048 for `single`, 6000 for the
`rejudge` and `pairwise` items with MiniMax-M2.5, 8192 for the external judges), one retry at 4096 tokens on an
unparsable answer. intent / style items return pass|fail; identify, pair_* and calib_real items return the chosen
number. Output OUTDIR/<shard file name>, resumable by key.

Usage:
    python -m personafactory.evaluation.style_extension.judge_client \\
        --shards ./outputs/style_extension/judge/items/000.jsonl ./outputs/style_extension/judge/items/001.jsonl \\
        --outdir ./outputs/style_extension/judge/results --urls http://127.0.0.1:30000/v1 --model MiniMax-M2.5
"""
import argparse, asyncio, json, os, random, re, time

import aiohttp

URLS = [u for u in os.environ.get('PF_JUDGE_URLS', '').split(',') if u] or ['http://127.0.0.1:30000/v1']
MODEL = os.environ.get('PF_JUDGE_MODEL', 'MiniMax-M2.5')


def parse(text, kind):
    if not text:
        return None
    text = text.split('</think>')[-1]
    field = 'verdict' if kind in ('intent', 'style') else 'answer'
    for m in reversed(list(re.finditer(r'\{[^{}]*"' + field + r'"[^{}]*\}', text, re.S))):
        g = re.search(r'"' + field + r'"\s*:\s*"?(pass|fail|[1-4])"?', m.group(0), re.I)
        if g:
            v = g.group(1).lower()
            return v if field == 'verdict' else int(v)
    return None


def _base(u):
    """Accept .../v1 or .../v1/chat/completions."""
    return u[:-len('/chat/completions')] if u.endswith('/chat/completions') else u.rstrip('/')


async def ask(session, prompt, max_tokens):
    body = {'model': MODEL, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.1, 'max_tokens': max_tokens}
    headers = {'Authorization': 'Bearer ' + (os.environ.get('PF_API_KEY') or os.environ.get('OPENAI_API_KEY') or 'EMPTY')}
    err = ''
    for attempt in range(4):
        try:
            async with session.post(_base(random.choice(URLS)) + '/chat/completions', json=body, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=900)) as r:
                d = await r.json()
                msg = d['choices'][0]['message']
                # servers with a reasoning parser split the thinking off; keep it first so the answer still wins
                think = msg.get('reasoning_content') or msg.get('reasoning') or ''
                return think + '\n' + (msg.get('content') or ''), d['choices'][0].get('finish_reason')
        except Exception as e:
            err = str(e)
            await asyncio.sleep(2 + 5 * attempt)
    return '', 'error:' + err[:100]


async def run(shards, outdir, conc, max_tokens):
    os.makedirs(outdir, exist_ok=True)
    sem = asyncio.Semaphore(conc)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=conc)) as session:
        for path in shards:
            out = os.path.join(outdir, os.path.basename(path))
            done = set()
            if os.path.exists(out):
                for line in open(out, encoding='utf-8'):
                    try:
                        done.add(json.loads(line)['key'])
                    except Exception:
                        pass
            items = [json.loads(l) for l in open(path, encoding='utf-8')]
            items = [i for i in items if i['key'] not in done]
            print(f'{path}: {len(items)} to judge, {len(done)} done', flush=True)
            fh = open(out, 'a', encoding='utf-8')
            t0, n = time.time(), 0

            async def one(it):
                nonlocal n
                async with sem:
                    text, fin = await ask(session, it['prompt'], max_tokens)
                    v = parse(text, it['kind'])
                    if v is None:
                        text, fin2 = await ask(session, it['prompt'], 4096)
                        v, fin = parse(text, it['kind']), f'retry:{fin}->{fin2}'
                rec = {k: x for k, x in it.items() if k != 'prompt'}
                rec.update(result=v, finish=fin)
                fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
                n += 1
                if n % 1000 == 0:
                    fh.flush()
                    print(f'  {n}/{len(items)} {n / (time.time() - t0):.1f} items/s', flush=True)

            await asyncio.gather(*(one(it) for it in items))
            fh.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--shards', nargs='+', required=True, help='item files from items.py')
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--concurrency', type=int, default=96)
    ap.add_argument('--max-tokens', type=int, default=2048, help='first try; an unparsable answer is retried at 4096')
    ap.add_argument('--urls', nargs='+', help='OpenAI-compatible base URLs (.../v1); default PF_JUDGE_URLS or a local server')
    ap.add_argument('--model', help='served model name; default PF_JUDGE_MODEL or MiniMax-M2.5')
    a = ap.parse_args()
    URLS = a.urls or URLS
    MODEL = a.model or MODEL
    asyncio.run(run(a.shards, a.outdir, a.concurrency, a.max_tokens))
