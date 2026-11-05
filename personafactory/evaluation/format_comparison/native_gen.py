#!/usr/bin/env python3
"""Native-persona conditions for the persona-format comparison.

For each item, a REAL persona from each prior dataset rewrites the same seed prompt, in that dataset's own native
form: a PersonaHub persona sentence (background only, as PersonaHub has no style field) and a SynthPAI profile
(attribute list plus its own free-text writing-style description). Same rewriter, template, decoding and call path
as run_conditions.py, so the new rewrites are comparable with the stored ones. Personas are drawn by a fixed hash
of the item id. Resumable.

Inputs:  --items, --config (rewrite_gen, verbal_quirks_instruction), --personahub (PersonaHub persona.jsonl),
         --synthpai (SynthPAI synthpai.jsonl; see README for how to obtain both), --rewriter-urls, --rewriter-model
Outputs: --out JSONL (item_id, condition native_personahub | native_synthpai, rewrite, native persona)
Run:     python -m personafactory.evaluation.format_comparison.native_gen --items ./outputs/format_comparison/items.jsonl \
             --personahub ./data/personahub/persona.jsonl --synthpai ./data/synthpai/synthpai.jsonl \
             --rewriter-urls http://HOST:8080/v1 --rewriter-model google/gemma-4-31B-it \
             --out ./outputs/format_comparison/generations_native.jsonl
"""
import argparse, asyncio, hashlib, itertools, json, os
import aiohttp, yaml

from personafactory.augmentation.pipeline import call_api
from personafactory.augmentation.prompts import ADAPT_USER_PROMPT_TEMPLATE
from personafactory.evaluation.format_comparison import renderers

SP_FIELDS = ('age', 'sex', 'city_country', 'birth_city_country', 'education', 'occupation', 'income_level', 'relationship_status')


def h(*a):
    return int(hashlib.sha256('|'.join(map(str, a)).encode()).hexdigest(), 16)


def load_natives(personahub, synthpai):
    ph = [json.loads(l)['persona'] for l in open(personahub)]
    sp = {}
    for l in open(synthpai):
        r = json.loads(l)
        sp.setdefault(r['author'], r['profile'])
    return ph, [sp[k] for k in sorted(sp)]


def native_blocks(item, cond, ph, sp):
    if cond == 'native_personahub':
        p = ph[h(item['item_id'], 'ph') % len(ph)]
        return p, renderers.UNSPEC, {'persona_text': p}
    prof = sp[h(item['item_id'], 'sp') % len(sp)]
    attrs = {k: prof[k] for k in SP_FIELDS if prof.get(k) not in (None, '')}
    style = str(prof.get('style', '')).strip()
    return json.dumps(attrs, ensure_ascii=False, indent=2), style, {'profile': attrs, 'style': style}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--items', default='./outputs/format_comparison/items.jsonl')
    ap.add_argument('--config', default='evaluation/format_comparison/config.yaml')
    ap.add_argument('--personahub', required=True, help='PersonaHub persona.jsonl')
    ap.add_argument('--synthpai', required=True, help='SynthPAI synthpai.jsonl')
    ap.add_argument('--rewriter-urls', required=True, help='comma-separated base URLs (.../v1)')
    ap.add_argument('--rewriter-model', required=True, help='served rewriter model name')
    ap.add_argument('--out', default='./outputs/format_comparison/generations_native.jsonl')
    ap.add_argument('--concurrency', type=int, default=128)
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config))
    items = [json.loads(l) for l in open(a.items)]
    ph, sp = load_natives(a.personahub, a.synthpai)
    pool = itertools.cycle([{'name': 'rewriter', 'base_url': u, 'api_key': os.environ.get('PF_API_KEY', 'dummy'),
                             'model': a.rewriter_model} for u in a.rewriter_urls.split(',')])
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            r = json.loads(l)
            if r.get('rewrite'):
                done.add((r['item_id'], r['condition']))
    todo = [(it, c) for it in items for c in ('native_personahub', 'native_synthpai') if (it['item_id'], c) not in done]
    print(f'{len(todo)} native rewrites to run', flush=True)
    sem = asyncio.Semaphore(a.concurrency)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    fh = open(a.out, 'a', encoding='utf-8')
    async with aiohttp.ClientSession() as session:
        async def one(it, c):
            bg, st, meta = native_blocks(it, c, ph, sp)
            prompt = ADAPT_USER_PROMPT_TEMPLATE.format(background=bg, writing_style=st, user_message=it['seed_prompt'],
                                                       verbal_quirks_instruction=cfg.get('verbal_quirks_instruction', ''))
            async with sem:
                txt, err = None, None
                for _ in range(3):
                    txt, err = await call_api(session, next(pool), cfg['rewrite_gen'], [{'role': 'user', 'content': prompt}], f'native/{c}')
                    if txt and txt.strip():
                        break
            fh.write(json.dumps({'item_id': it['item_id'], 'condition': c, 'stratum': it['stratum'], 'seed_prompt': it['seed_prompt'],
                                 'rewrite': (txt or '').strip(), 'persona_block_words': len((bg + ' ' + (st if st != renderers.UNSPEC else '')).split()),
                                 'native': meta, 'errors': [err] if err else []}, ensure_ascii=False) + '\n')
            fh.flush()
        await asyncio.gather(*(one(it, c) for it, c in todo))
    print('done', flush=True)


if __name__ == '__main__':
    asyncio.run(main())
