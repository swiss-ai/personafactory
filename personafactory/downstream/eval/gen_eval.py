#!/usr/bin/env python3
"""Greedy generations of one fine-tuned model for every prompt of a styled evaluation file (styled.jsonl or
styled_all.jsonl) against OpenAI-compatible servers (vLLM, one replica per GPU; thinking disabled through
chat_template_kwargs). Max new tokens per benchmark: IFEval 1,536, GSM8K and MBPP 1,024, MMLU and ARC 256, WildChat
2,048. Resumable by bench/id/variant. Writes <out>/gen.jsonl.

  python -m personafactory.downstream.eval.gen_eval --urls http://HOST:8000/v1 http://HOST:8001/v1 \
      --data $PF_DATA_DIR/downstream_eval/styled_all.jsonl --out $PF_OUT_DIR/downstream/eval/A2
"""
import argparse, asyncio, json, os, random
import aiohttp

MAX_TOKENS = {'ifeval': 1536, 'gsm8k': 1024, 'mbpp': 1024, 'mmlu': 256, 'arc': 256, 'wildchat': 2048}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--urls', nargs='+', required=True)
    ap.add_argument('--model', default='m')
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--concurrency', type=int, default=256)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    path = a.out + '/gen.jsonl'
    done = set()
    if os.path.exists(path):
        for l in open(path, encoding='utf-8'):
            try:
                r = json.loads(l)
                done.add((r['bench'], r['id'], r['variant']))
            except Exception:
                pass
    rows = [r for r in map(json.loads, open(a.data, encoding='utf-8')) if (r['bench'], r['id'], r['variant']) not in done]
    print(len(rows), 'to generate,', len(done), 'done', flush=True)
    fh = open(path, 'a', encoding='utf-8')
    sem = asyncio.Semaphore(a.concurrency)
    n = 0
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=a.concurrency)) as s:
        async def one(r):
            nonlocal n
            body = {'model': a.model, 'messages': [{'role': 'user', 'content': r['prompt']}], 'temperature': 0.0,
                    'max_tokens': MAX_TOKENS[r['bench']], 'chat_template_kwargs': {'enable_thinking': False}}
            out, fin = None, None
            async with sem:
                for attempt in range(5):
                    try:
                        async with s.post(random.choice(a.urls) + '/chat/completions', json=body,
                                          timeout=aiohttp.ClientTimeout(total=1200)) as resp:
                            d = await resp.json()
                        out, fin = d['choices'][0]['message'].get('content') or '', d['choices'][0].get('finish_reason')
                        break
                    except Exception as e:
                        fin = 'error:' + str(e)[:100]
                        await asyncio.sleep(3 + 5 * attempt)
            if out is None:
                return
            fh.write(json.dumps({k: r[k] for k in ('bench', 'id', 'variant')} | {'response': out, 'finish': fin}, ensure_ascii=False) + '\n')
            n += 1
            if n % 2000 == 0:
                fh.flush()
                print(n, flush=True)
        await asyncio.gather(*(one(r) for r in rows))
    fh.close()
    print('done', n, flush=True)


if __name__ == '__main__':
    asyncio.run(main())
