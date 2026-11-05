#!/usr/bin/env python3
#!/usr/bin/env python3
"""Judge client for the downstream evaluation: item shards (JSONL with `key`, `kind`, `prompt`) against
OpenAI-compatible judge endpoints. Used for the intent check of the persona-rewritten prompts (kind `intent`,
returns pass / fail; MiniMax-M2.5) and for the WildChat pairwise comparison (kind `pair`, returns 1 / 2;
Qwen3.6-35B-A3B and Muse-Glimmer-30B). Settings as the corpus judge: temperature 0.1, one retry at 4,096 tokens on an
unparsable answer (--max-tokens sets the first try). Reasoning returned by a server-side reasoning parser is
prepended so that the final answer wins. Resumable by key. Writes <outdir>/<shard name> with `result` and `finish`.

  python -m personafactory.downstream.eval.judge_client --shards items/000.jsonl --outdir results \
      --urls http://HOST:8000/v1 --model MiniMax-M2.5 --max-tokens 2048
"""
import argparse, asyncio, json, os, random, re, time
import aiohttp

URLS = [u for u in os.environ.get('PF_JUDGE_URLS', 'http://127.0.0.1:30000/v1').split(',') if u]
MODEL = os.environ.get('PF_JUDGE_MODEL', 'MiniMax-M2.5')
API_KEY = os.environ.get('PF_API_KEY', 'dummy')


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


async def ask(session, prompt, max_tokens):
    body = {'model': MODEL, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.1, 'max_tokens': max_tokens}
    err = ''
    for attempt in range(4):
        try:
            async with session.post(random.choice(URLS) + '/chat/completions', json=body,
                                    headers={'Authorization': 'Bearer ' + API_KEY},
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
    ap = argparse.ArgumentParser()
    ap.add_argument('--shards', nargs='+', required=True)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--concurrency', type=int, default=96)
    ap.add_argument('--max-tokens', type=int, default=2048, help='first try; the retry doubles it')
    ap.add_argument('--urls', nargs='+', help='OpenAI-compatible base URLs (.../v1); default PF_JUDGE_URLS')
    ap.add_argument('--model', help='served model name; default PF_JUDGE_MODEL or MiniMax-M2.5')
    a = ap.parse_args()
    URLS = a.urls or URLS
    MODEL = a.model or MODEL
    asyncio.run(run(a.shards, a.outdir, a.concurrency, a.max_tokens))
