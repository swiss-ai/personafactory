#!/usr/bin/env python3
"""Persona-rewritten variants of the verifiable benchmarks, by personas held out of every training arm
(<work>/data/heldout_personas.json from build_arms.py) that speak English. Each IFEval / GSM8K / MBPP prompt is
rewritten by K personas (variants persona0..persona{K-1}, fixed seed) with the pipeline's own user rewrite:
ADAPT_USER_PROMPT_TEMPLATE, background + style strings, quirk instruction with p = 0.25, temperature 0.7, literal
protection (augmentation.integrity protect / restore / audit) and the truncation guard, up to 3 attempts. On top of
the pipeline masks, every IFEval string kwarg found verbatim in the prompt must survive; MBPP rewrites only the
description and keeps the shown test verbatim. Items whose rewrite fails every attempt are dropped and counted.
The rewrites are then intent-checked (intent_check.py).

Rewriter in the paper: Gemma 4 31B (google/gemma-4-31B-it), K = 3. Reads <data-dir>/{ifeval,gsm8k,mbpp}.jsonl; writes
<data-dir>/styled_persona.jsonl and <data-dir>/styled_persona_stats.json.

  python -m personafactory.downstream.eval.perturb_persona --data-dir $PF_DATA_DIR/downstream_eval \
      --heldout $PF_OUT_DIR/downstream/data/heldout_personas.json --bank $PF_BANK --urls http://HOST:8000/v1 --model gemma
"""
import argparse, asyncio, collections, json, os, random

import aiohttp

from personafactory.augmentation import integrity
from personafactory.augmentation import pipeline as H
from personafactory.augmentation.prompts import ADAPT_USER_PROMPT_TEMPLATE
from personafactory.downstream.common import load_bank
from personafactory.downstream.eval.perturb_rules import ifeval_protect


async def rewrite(session, urls, model, persona, text, protect, rng):
    masked, span_map = integrity.protect(text)
    quirk = ("Use the persona's typing style and, if natural, you may include one of their verbal mannerisms or tics."
             if rng.random() <= 0.25 else
             "For this turn, maintain typing/punctuation style only; do NOT include any verbal filler words or mannerisms.")
    prompt = ADAPT_USER_PROMPT_TEMPLATE.format(background=H.get_persona_background_str(persona),
                                                 writing_style=H.get_persona_style_str(persona),
                                                 verbal_quirks_instruction=quirk, user_message=masked)
    if span_map:
        prompt += '\n\n' + integrity.protection_instruction().strip()
    last = None
    for _ in range(3):
        body = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.7, 'top_p': 0.95,
                'max_tokens': 4096}
        try:
            async with session.post(rng.choice(urls) + '/chat/completions', json=body,
                                    timeout=aiohttp.ClientTimeout(total=600)) as r:
                d = await r.json()
            cand = H.strip_reasoning(d['choices'][0]['message'].get('content') or '').strip()
        except Exception as e:
            last = 'error:' + str(e)[:80]
            continue
        if not cand:
            last = 'empty'
            continue
        try:
            cand = H.sanitize_constitution(integrity.restore(cand, span_map))
        except ValueError:
            last = 'literal_integrity'
            continue
        if span_map and not integrity.audit(text, cand, H.sanitize_constitution)['policy_intact']:
            last = 'literal_integrity'
            continue
        if len(text) >= 50 and len(cand) < 0.5 * len(text):
            last = 'truncated'
            continue
        if not all(p in cand for p in protect):
            last = 'kwarg_lost'
            continue
        return cand, None
    return None, last


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--urls', nargs='+', required=True)
    ap.add_argument('--model', default='gemma')
    ap.add_argument('--k', type=int, default=3)
    ap.add_argument('--concurrency', type=int, default=200)
    ap.add_argument('--data-dir', required=True, help='benchmark JSONL dir (fetch_benchmarks.py)')
    ap.add_argument('--heldout', required=True, help='heldout_personas.json from build_arms.py')
    ap.add_argument('--bank', default=os.environ.get('PF_BANK', 'swiss-ai/PersonaFactory:persona_bank'))
    ap.add_argument('--out', default=None, help='default: <data-dir>/styled_persona.jsonl')
    a = ap.parse_args()
    E = a.data_dir
    a.out = a.out or os.path.join(E, 'styled_persona.jsonl')
    held = set(json.load(open(a.heldout)))
    personas = [p for p in load_bank(a.bank, held).values() if H.persona_speaks_language(p, 'english')]
    personas.sort(key=lambda p: p['id'])
    print('held-out English-speaking personas', len(personas), flush=True)
    items = []
    for r in map(json.loads, open(os.path.join(E, 'ifeval.jsonl'))):
        prot = [x for x in ifeval_protect(r) if x in r['prompt']]
        items.append(('ifeval', str(r['key']), r['prompt'], prot, '', {'instruction_id_list': r['instruction_id_list'],
                      'kwargs': r['kwargs'], 'prompt': r['prompt']}))
    for i, r in enumerate(map(json.loads, open(os.path.join(E, 'gsm8k.jsonl')))):
        items.append(('gsm8k', str(i), r['question'], [], '', {'gold': r['answer'].split('####')[-1].strip().replace(',', '')}))
    for r in map(json.loads, open(os.path.join(E, 'mbpp.jsonl'))):
        items.append(('mbpp', str(r['task_id']), r['prompt'].strip(), [], f"\n\nYour code should pass this test:\n{r['test_list'][0]}",
                      {'tests': r['test_list'], 'imports': r.get('test_imports') or []}))
    done = set()
    if os.path.exists(a.out):
        done = {(x['bench'], x['id'], x['variant']) for x in map(json.loads, open(a.out, encoding='utf-8'))}
    fh = open(a.out, 'a', encoding='utf-8')
    stats = collections.Counter()
    sem = asyncio.Semaphore(a.concurrency)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=a.concurrency)) as s:
        async def one(b, i, text, prot, suffix, meta, k):
            v = f'persona{k}'
            if (b, i, v) in done:
                return
            rng = random.Random(f'{b}:{i}:{k}')
            p = rng.choice(personas)
            async with sem:
                out, why = await rewrite(s, a.urls, a.model, p, text, prot, rng)
            stats[f'{b}/{"kept" if out else "dropped:" + str(why)}'] += 1
            if out:
                fh.write(json.dumps({'bench': b, 'id': i, 'variant': v, 'prompt': out + suffix, 'persona_id': p['id'],
                                     'meta': meta}, ensure_ascii=False) + '\n')
                fh.flush()
        await asyncio.gather(*(one(*it, k) for it in items for k in range(a.k)))
    fh.close()
    json.dump(dict(sorted(stats.items())), open(os.path.join(E, 'styled_persona_stats.json'), 'w'), indent=1)
    print(json.dumps(dict(sorted(stats.items())), indent=1))


if __name__ == '__main__':
    asyncio.run(main())
