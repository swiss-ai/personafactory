#!/usr/bin/env python3
"""Format-neutral re-judging, naturalness and native-persona comparison for the persona-format comparison.

1. Format-neutral style reference. The original style and pairwise judges saw every condition's persona
   rendered in the PersonaFactory format, which the PersonaFactory rewriter also saw. Here the reference is
   the persona's writing-behaviour ATTRIBUTE VALUES only (structured typing keys, sentence length, question
   framing, code-switching frequency): no quirk text, no example message, no free-text style description,
   so no rewrite can score by echoing phrasing from its own prompt.
     style_neutral     per rewrite, pass/fail            (none / personahub / synthpai / personafactory)
     pairwise_neutral  PersonaFactory vs each other condition, order randomized per item
2. Naturalness / caricature, reference-free:
     natural           per rewrite, pass/fail            (all conditions, incl. native ones)
3. Native personas (real PersonaHub persona, real SynthPAI profile; see native_gen.py):
     intent            production intent template
     pairwise_free     PersonaFactory vs native rewrite: more distinctive and realistic individual voice,
                       request intact; no persona reference at all, so the two sides are judged on equal terms
Judges: any OpenAI-compatible endpoints (comma list). Output: one JSONL per judge (judged_<label>.jsonl in
--run-dir), resumable by task key.

Inputs:  --run-dir with items.jsonl, generations.jsonl and (optionally) generations_native.jsonl
Run:     python -m personafactory.evaluation.format_comparison.rejudge_neutral --run-dir ./outputs/format_comparison \
             --urls http://HOST:30000/v1 --model MiniMax-M2.5 --label minimax --max-tokens 8192
"""
import argparse, asyncio, hashlib, json, os, random, re
import aiohttp

from personafactory.augmentation.prompts import VALIDATE_PERSONA_INTENT_TEMPLATE as INTENT

PB = './outputs/format_comparison'

JSON_VERDICT = """Respond with a JSON object exactly in this format:
{{"verdict": "pass" or "fail", "reason": "brief explanation"}}
Output only the JSON."""
JSON_WINNER = """Respond with a JSON object exactly in this format:
{{"winner": "A" or "B" or "tie", "reason": "one short sentence"}}
Output only the JSON."""

STYLE_NEUTRAL = """You judge whether a rewritten chat message shows a specific user's writing behaviour.

The user's writing-behaviour attributes:
{attrs}

Original message:
{original}

Rewritten message:
{rewrite}

Judge only writing behaviour (capitalization, punctuation, emoji, abbreviations, typos, message structure, sign-offs, sentence length, question framing, code-switching), not content. PASS if the rewrite clearly shows this user's writing behaviour on several of the listed attributes and contradicts none of the prominent ones. FAIL if it reads like a generic, standard-register message or contradicts the attributes.

""" + JSON_VERDICT

PAIRWISE_NEUTRAL = """You judge which of two rewrites of the same chat message better reflects a specific user's writing behaviour.

The user's writing-behaviour attributes:
{attrs}

Original message:
{original}

Rewrite A:
{a}

Rewrite B:
{b}

Which rewrite better reflects THIS user's writing behaviour as described by the attributes (capitalization, punctuation, emoji, abbreviations, typos, message structure, sign-offs, sentence length, question framing, code-switching), while keeping the original request fully intact? Judge only writing behaviour. If genuinely equal, answer "tie".

""" + JSON_WINNER

NATURAL = """You judge whether a chat message sent to an AI assistant reads like something a real person would plausibly type.

Original message (shown only as a reference for the request):
{original}

Message to judge:
{rewrite}

PASS if a real person could plausibly have typed this message, including informal, terse, non-native or error-prone writing. FAIL if it reads as a caricature or as artificially stylized: stacked stereotypical markers, forced slang or catchphrases, exaggerated or implausible typos, cultural cliches, or a persona being performed rather than a request being made.

""" + JSON_VERDICT

PAIRWISE_FREE = """Two rewrites of the same chat message to an AI assistant are shown, each written in the voice of a different synthetic user. The goal is training data in which users sound like distinct, real individuals rather than a generic, standard-register user.

Original message:
{original}

Rewrite A:
{a}

Rewrite B:
{b}

Which rewrite gives the message a more distinctive and realistic individual writing voice (register, typing habits, rhythm, word choice), while keeping the original request fully intact? A caricatured or over-stylized rewrite should lose to a plausible one. If genuinely equal, answer "tie".

""" + JSON_WINNER


def h(*a):
    return int(hashlib.sha256('|'.join(map(str, a)).encode()).hexdigest(), 16)


def strip_examples(v):
    # keep the categorical value, drop quoted or bracketed examples that only the PersonaFactory prompt contained
    v = re.sub(r'\([^)]*\)', '', str(v))
    v = re.sub(r"[\"'\u2018\u2019\u201c\u201d][^\"'\u2018\u2019\u201c\u201d]{1,60}[\"'\u2018\u2019\u201c\u201d]", '', v)
    v = re.sub(r'\be\.g\.,?|\bi\.e\.,?', '', v)
    v = re.sub(r'\s*([,;])(\s*[,;])+', r'\1', v)
    return re.sub(r'\s{2,}', ' ', v).strip(' ,;:-') or 'unspecified'


def neutral_attrs(p):
    st = p.get('style') or {}
    lines = [f"- sentence length: {st.get('sentence_length_tendency', 'unspecified')}",
             f"- question framing: {st.get('question_framing', 'unspecified')}",
             f"- code-switching frequency: {strip_examples(st.get('code_switching_freq', 'unspecified'))}"]
    for k, v in (st.get('chatting_style_structured') or {}).items():
        lines.append(f"- {k.replace('_', ' ')}: {strip_examples(v)}")
    return '\n'.join(lines)


def build_tasks():
    items = {json.loads(l)['item_id']: json.loads(l) for l in open(PB + '/items.jsonl')}
    gen = {}
    for l in open(PB + '/generations.jsonl'):
        r = json.loads(l)
        if r.get('rewrite'):
            gen[(r['item_id'], r['condition'])] = r['rewrite']
    nat = {}
    fp = PB + '/generations_native.jsonl'
    if os.path.exists(fp):
        for l in open(fp):
            r = json.loads(l)
            if r.get('rewrite'):
                nat[(r['item_id'], r['condition'])] = r['rewrite']
    tasks = []
    for iid, it in items.items():
        orig, attrs = it['seed_prompt'], neutral_attrs(it['persona'])
        pf = gen.get((iid, 'personafactory'))
        for c in ('none', 'personahub', 'synthpai', 'personafactory'):
            rw = gen.get((iid, c))
            if not rw:
                continue
            tasks.append((f'style_neutral|{iid}|{c}', STYLE_NEUTRAL.format(attrs=attrs, original=orig, rewrite=rw), 'verdict', {}))
            tasks.append((f'natural|{iid}|{c}', NATURAL.format(original=orig, rewrite=rw), 'verdict', {}))
            if c != 'personafactory' and pf:
                flip = h(iid, c, 'pn') % 2 == 1  # flip: PersonaFactory shown as B
                a, b = (rw, pf) if flip else (pf, rw)
                tasks.append((f'pairwise_neutral|{iid}|{c}', PAIRWISE_NEUTRAL.format(attrs=attrs, original=orig, a=a, b=b), 'winner', {'pf_is_A': not flip}))
        for c in ('native_personahub', 'native_synthpai'):
            rw = nat.get((iid, c))
            if not rw:
                continue
            tasks.append((f'natural|{iid}|{c}', NATURAL.format(original=orig, rewrite=rw), 'verdict', {}))
            tasks.append((f'intent|{iid}|{c}', INTENT.format(original_message=orig, rewritten_message=rw), 'verdict', {}))
            if pf:
                flip = h(iid, c, 'pf') % 2 == 1
                a, b = (rw, pf) if flip else (pf, rw)
                tasks.append((f'pairwise_free|{iid}|{c}', PAIRWISE_FREE.format(original=orig, a=a, b=b), 'winner', {'pf_is_A': not flip}))
    return tasks


def parse(text, kind):
    for part in (text or '').split('</think>')[::-1]:
        for m in reversed(list(re.finditer(r'\{[^{}]*\}', part, re.S))):
            try:
                d = json.loads(m.group(0))
            except Exception:
                v = re.search(r'"%s"\s*:\s*"([A-Za-z]+)"' % kind, m.group(0))
                d = {kind: v.group(1)} if v else {}
            v = str(d.get(kind, '')).strip().lower()
            if kind == 'verdict' and v in ('pass', 'fail'):
                return v
            if kind == 'winner' and v in ('a', 'b', 'tie'):
                return v
    return None


async def ask(session, urls, model, prompt, max_tokens, kind):
    body = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.1, 'max_tokens': max_tokens}
    fail = 'http_error'
    for attempt in range(4):
        try:
            async with session.post(random.choice(urls) + '/chat/completions', json=body,
                                    headers={'Authorization': 'Bearer ' + os.environ.get('PF_API_KEY', 'dummy')}, timeout=aiohttp.ClientTimeout(total=900)) as r:
                d = await r.json()
            msg = d['choices'][0]['message']
            for txt in (msg.get('content'), msg.get('reasoning_content'), msg.get('reasoning')):
                v = parse(txt, kind)
                if v:
                    return v, None
            fail = 'unparsed' if (msg.get('content') or '').strip() else 'empty'
        except Exception:
            fail = 'http_error'
            await asyncio.sleep(3 + 5 * attempt)
    return None, fail


async def main():
    global PB
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-dir', default=PB)
    ap.add_argument('--urls', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--label', required=True)
    ap.add_argument('--max-tokens', type=int, default=4096)
    ap.add_argument('--concurrency', type=int, default=256)
    ap.add_argument('--only', default='', help='comma list of task kinds')
    a = ap.parse_args()
    PB = a.run_dir
    urls = [u.rstrip('/') for u in a.urls.split(',') if u]
    out = f'{PB}/judged_{a.label}.jsonl'
    done = set()
    if os.path.exists(out):
        for l in open(out):
            x = json.loads(l)
            if x.get('value') is not None:
                done.add(x['key'])
    tasks = [t for t in build_tasks() if t[0] not in done and (not a.only or t[0].split('|')[0] in a.only.split(','))]
    print(f'{a.label}: {len(tasks)} tasks to judge ({len(done)} done)', flush=True)
    sem = asyncio.Semaphore(a.concurrency)
    fh = open(out, 'a', encoding='utf-8')
    n = [0]
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=a.concurrency)) as session:
        async def one(key, prompt, kind, meta):
            async with sem:
                v, fail = await ask(session, urls, a.model, prompt, a.max_tokens, kind)
            task, iid, cond = key.split('|')
            fh.write(json.dumps({'key': key, 'task': task, 'item_id': iid, 'condition': cond, 'value': v, 'failure': fail, **meta}) + '\n')
            fh.flush()
            n[0] += 1
            if n[0] % 1000 == 0:
                print(f'{a.label}: {n[0]}/{len(tasks)}', flush=True)
        await asyncio.gather(*(one(*t) for t in tasks))
    print(f'{a.label}: done', flush=True)


if __name__ == '__main__':
    asyncio.run(main())
