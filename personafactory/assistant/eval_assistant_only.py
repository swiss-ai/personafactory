#!/usr/bin/env python3
"""Evaluate assistant-only augmentation (assistant.augment_assistant_only) with the MiniMax-M2.5 judge.

Per variant (source replies, none, regen, restyle): status counts, style adoption of every assistant turn
against the conversation's assigned persona, same content as the source on the first assistant turn, median
words, and self-reference leaks (persona names, instruction echoes). Only conversations present in every
variant are compared. The step runs must use --keep-source (the source replies are read from the regen step).

Input: <outdir>/assign.jsonl and <outdir>/{none,regen,restyle}/*.jsonl. Output: <outdir>/eval.json.

  python -m personafactory.assistant.eval_assistant_only --outdir ./outputs/assistant_only --minimax $MINIMAX_URL
"""
import argparse, asyncio, collections, json, os, re, statistics
import aiohttp
from personafactory.assistant import model_persona
from personafactory.common import judge_client

NAMES = re.compile(r'\b(' + '|'.join(re.escape(p['name']) for p in model_persona.PERSONAS) + r')\b', re.I)
TOUCH = re.compile(r'optional touch|\(\s*no sign[- ]?off', re.I)


def rows(fp):
    out = {}
    for fn in sorted(os.listdir(fp)):
        for l in open(os.path.join(fp, fn), encoding='utf-8'):
            x = json.loads(l)
            out[x['id']] = x
    return out


def asst(msgs):
    return [m['content'] for m in msgs if m['role'] == 'assistant']


def first_user(msgs):
    return next(m['content'] for m in msgs if m['role'] == 'user')


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--minimax', required=True)
    ap.add_argument('--concurrency', type=int, default=200)
    a = ap.parse_args()
    judge_client.URLS = [u + '/chat/completions' for u in a.minimax.split(',')]
    assigned = {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(a.outdir, 'assign.jsonl'))}
    steps = {s: rows(os.path.join(a.outdir, s)) for s in ('none', 'regen', 'restyle') if os.path.isdir(os.path.join(a.outdir, s))}
    common = set.intersection(*(set(v) for v in steps.values())) & {k for k, v in assigned.items() if v['model_persona']}
    src = {k: steps['regen'][k]['source_messages'] for k in common}
    report = {'conversations': len(common),
              'status': {s: dict(collections.Counter(v[k]['status'] for k in common)) for s, v in steps.items()},
              'matched_distribution': collections.Counter(assigned[k]['model_persona'] for k in common).most_common()}
    variants = {'source': {k: src[k] for k in common}}
    for s, v in steps.items():
        variants[s] = {k: v[k]['messages'] for k in common if v[k].get('messages')}
    sem = asyncio.Semaphore(a.concurrency)
    res = collections.defaultdict(lambda: collections.defaultdict(list))
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=a.concurrency)) as session:
        async def style(var, k, i, text):
            p = model_persona.BY_ID[assigned[k]['model_persona']]
            async with sem:
                v, _ = await judge_client.verdict(session, model_persona.STYLE_JUDGE.format(style=model_persona.render_model_persona(p), response=text))
            if v:
                res[var]['style'].append(v == 'pass')
                res[var]['style_' + p['id']].append(v == 'pass')

        async def content(var, k, ref, text):
            async with sem:
                v, _ = await judge_client.verdict(session, model_persona.CONTENT_JUDGE.format(user_message=first_user(src[k]), a=ref, b=text))
            if v:
                res[var]['content'].append(v == 'pass')

        jobs = []
        for var, conv in variants.items():
            for k, msgs in conv.items():
                ts = asst(msgs)
                for i, t in enumerate(ts):
                    jobs.append(style(var, k, i, t))
                    res[var]['words'].append(len(t.split()))
                    res[var]['name_leak'].append(bool(NAMES.search(t)) and not NAMES.search(' '.join(m['content'] for m in msgs if m['role'] == 'user')))
                    res[var]['touch_leak'].append(bool(TOUCH.search(t)))
                s0 = asst(src[k])
                if var != 'source' and ts and s0:
                    jobs.append(content(var, k, s0[0], ts[0]))
        await asyncio.gather(*jobs)
    pct = lambda xs: round(100 * sum(xs) / len(xs), 1) if xs else None
    report['variants'] = {var: {'turns': len(d['words']), 'style_adoption': pct(d['style']),
                                'same_content_first_turn': pct(d['content']), 'median_words': statistics.median(d['words']) if d['words'] else None,
                                'name_leak_turns': sum(d['name_leak']), 'touch_leak_turns': sum(d['touch_leak']),
                                'style_by_persona': {p['id']: pct(d['style_' + p['id']]) for p in model_persona.PERSONAS if d['style_' + p['id']]}}
                          for var, d in res.items()}
    json.dump(report, open(os.path.join(a.outdir, 'eval.json'), 'w'), indent=1)
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    asyncio.run(main())
