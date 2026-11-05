#!/usr/bin/env python3
"""Judge item shards (from prep_items.py) against an OpenAI-compatible judge server. Resumable: skips keys
already written to the output shard.

Settings follow the corpus judge in common/judge_client.py: temperature 0.1, max_tokens 2048, pass/fail JSON,
one retry with 4096 tokens for a null verdict (recorded in the *_finish field).

Inputs:  --shards <items/NNN.jsonl ...>
Outputs: <outdir>/NNN.jsonl with intent / style (and intent_vs_en for translated turns) verdicts
Run:     python -m personafactory.evaluation.corpus_judge.run_judge --shards ./outputs/corpus_judge/items/000.jsonl \
             --outdir ./outputs/corpus_judge/results --url http://127.0.0.1:30000/v1/chat/completions --model MiniMax-M2.5
"""
import argparse, asyncio, json, os, time
import aiohttp

from personafactory.common import judge_client
from personafactory.common.judge_client import verdict

META = ('key', 'mode', 'lang', 'cohort', 'responder', 'source_name', 'turn', 'changed', 'intent_basis')


async def run(shards, outdir, conc):
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
                    jobs = [verdict(session, it['intent_prompt']), verdict(session, it['style_prompt'])]
                    if 'intent_prompt_vs_english_source' in it:
                        jobs.append(verdict(session, it['intent_prompt_vs_english_source']))
                    res = await asyncio.gather(*jobs)
                rec = {k: it.get(k) for k in META}
                rec.update(intent=res[0][0], intent_finish=res[0][1], style=res[1][0], style_finish=res[1][1])
                if len(res) > 2:
                    rec.update(intent_vs_en=res[2][0], intent_vs_en_finish=res[2][1])
                fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
                n += 1
                if n % 2000 == 0:
                    fh.flush()
                    print(f'  {n}/{len(items)} {n / (time.time() - t0):.1f} items/s', flush=True)

            await asyncio.gather(*(one(it) for it in items))
            fh.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--shards', nargs='+', required=True)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--concurrency', type=int, default=96)
    ap.add_argument('--url', nargs='*', default=None,
                    help='judge .../v1/chat/completions endpoint(s); default PF_JUDGE_URL(S)')
    ap.add_argument('--model', default=None, help='served judge model name; default PF_JUDGE_MODEL')
    a = ap.parse_args()
    if a.url:
        judge_client.URLS = list(a.url)
    if a.model:
        judge_client.MODEL = a.model
    asyncio.run(run(a.shards, a.outdir, a.concurrency))
