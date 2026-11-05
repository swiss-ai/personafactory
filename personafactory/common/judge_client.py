#!/usr/bin/env python3
"""Minimal async client for an OpenAI-compatible judge endpoint (the corpus judge is MiniMax-M2.5).

Temperature 0.1, pass/fail JSON verdicts. Reasoning text before </think> is stripped before parsing; a null
verdict (truncated or malformed output) is retried once with a larger token budget and recorded as such.
Set URLS (list of .../v1/chat/completions endpoints) and MODEL before use, or PF_JUDGE_URLS / PF_JUDGE_MODEL.
"""
import argparse, asyncio, json, os, random, re, time
import aiohttp

URL = os.environ.get('PF_JUDGE_URL', 'http://127.0.0.1:30000/v1/chat/completions')
URLS = [u for u in os.environ.get('PF_JUDGE_URLS', '').split(',') if u]  # one endpoint is picked per call
MODEL = os.environ.get('PF_JUDGE_MODEL', 'MiniMax-M2.5')


def parse(text):
    if not text:
        return None
    text = text.split('</think>')[-1]
    for m in reversed(list(re.finditer(r'\{[^{}]*"verdict"[^{}]*\}', text, re.S))):
        try:
            v = json.loads(m.group(0)).get('verdict', '').lower()
        except Exception:
            v = re.search(r'"verdict"\s*:\s*"(pass|fail)"', m.group(0), re.I)
            v = v.group(1).lower() if v else ''
        if v in ('pass', 'fail'):
            return v
    return None


async def ask(session, prompt, max_tokens):
    body = {'model': MODEL, 'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.1, 'max_tokens': max_tokens}
    for attempt in range(4):
        try:
            async with session.post(random.choice(URLS) if URLS else URL, json=body, timeout=aiohttp.ClientTimeout(total=600)) as r:
                d = await r.json()
                msg = d['choices'][0]['message']
                return (msg.get('content') or ''), d['choices'][0].get('finish_reason')
        except Exception as e:
            err = str(e)
            await asyncio.sleep(2 + 5 * attempt)
    return '', 'error:' + err[:100]


async def verdict(session, prompt):
    text, fin = await ask(session, prompt, 2048)
    v = parse(text)
    if v is None:
        text, fin2 = await ask(session, prompt, 4096)
        v = parse(text)
        return v, f'retry:{fin}->{fin2}'
    return v, fin
