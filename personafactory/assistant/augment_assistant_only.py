#!/usr/bin/env python3
"""Assistant-only model-persona augmentation for any chat dataset (no seeded user persona).

The user turns are kept exactly as in the source; only the assistant side changes. Steps:
  --step assign : choose a model persona per conversation. The matcher (MiniMax-M2.5) sees only the user's own
                  messages (first 3, capped), since there is no user card. --assign top3 samples uniformly from
                  the matcher's top 3 (spreads the skewed match distribution); random / fixed:<id> need no judge.
  --step regen  : seeded generation, as arm C without the user background: the persona's style section (quirk
                  p=0.25, content rules, priority clause) is in the system prompt on every turn. Responder path
                  otherwise unchanged: next-turn continuity loop and sanity gate. Gemma / Ministral 50/50 per
                  conversation (hash).
  --step none   : the same regeneration with no model persona (control).
  --step restyle: post-hoc restyle of the source assistant replies (code, numbers, URLs, quotes protected;
                  retried, else the original reply is kept and flagged). For sources whose answers must not
                  change (verified math/code); no sanity gate, content kept by construction. Gemma only by
                  default (Ministral kept the original reply on far more turns).
Conversations with a non-empty system prompt are passed through unchanged by default (--with-system skip):
on 200 conversations with checkable system constraints (length, sentence count, numbered list, no Markdown)
compliance fell from 86% without a persona to 58% (style above the prompt) / 66% (prompt last, as hard
constraints). --with-system apply augments them anyway; the placement is set by AO_SYS_POSITION (last, the
default: source prompt after the style as overriding constraints; first: style below the source prompt).
Persona names never enter a prompt.

Input: JSONL rows with `messages` or `conversation` (role/content, or ShareGPT from/value) and an optional id.
Output: <outdir>/<step>/<input basename>, one row per conversation, resumable; assignments in <outdir>/assign.jsonl.
Endpoints: OpenAI-compatible /v1 base URLs (or PF_GEMMA_URL / PF_MINISTRAL_URL / PF_MINIMAX_URL).

  python -m personafactory.assistant.augment_assistant_only --step assign --input data/*.jsonl --outdir ./outputs/assistant_only \
      --minimax $MINIMAX_URL
  python -m personafactory.assistant.augment_assistant_only --step regen --input data/*.jsonl --outdir ./outputs/assistant_only \
      --gemma $GEMMA_URL --ministral $MINISTRAL_URL --minimax $MINIMAX_URL
"""
import argparse, asyncio, copy, hashlib, json, os, random
import aiohttp
from personafactory.assistant import model_persona
from personafactory.assistant.shared import add_server_args, done_ids, h, parse_ranking, responder_urls, responders, restyle, setup_judge
from personafactory.augmentation import pipeline
from personafactory.augmentation.run_augmentation import BASE_CONFIG
from personafactory.common import judge_client

ROLE = {'user': 'user', 'human': 'user', 'assistant': 'assistant', 'gpt': 'assistant', 'model': 'assistant',
        'system': 'system'}


def normalise(row):
    msgs = row.get('messages') or row.get('conversation') or row.get('conversations') or []
    out = []
    for m in msgs:
        role = ROLE.get(str(m.get('role', m.get('from', ''))).lower())
        content = m.get('content', m.get('value'))
        if role and isinstance(content, str) and content.strip():
            out.append({'role': role, 'content': content})
    rid = row.get('id') or row.get('source_id') or hashlib.sha256(json.dumps(out, ensure_ascii=False).encode()).hexdigest()[:24]
    return str(rid), out


def split_system(msgs):
    sys_ = '\n\n'.join(m['content'] for m in msgs if m['role'] == 'system')
    return sys_, [m for m in msgs if m['role'] != 'system']


def load(paths):
    rows = []
    for p in paths:
        for l in open(p, encoding='utf-8'):
            rid, msgs = normalise(json.loads(l))
            sys_, turns = split_system(msgs)
            if any(m['role'] == 'user' for m in turns):
                rows.append({'id': rid, 'file': os.path.basename(p), 'system': sys_, 'turns': turns, 'source': msgs})
    return rows


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--step', choices=('assign', 'regen', 'none', 'restyle'), required=True)
    ap.add_argument('--input', nargs='+', required=True)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--assign', default='match', help='match | top3 | random | fixed:<persona id>')
    add_server_args(ap, judge_required=False)
    ap.add_argument('--concurrency', type=int, default=100)
    ap.add_argument('--restyle-model', default='gemma', help='restyle step: gemma (default; Ministral loses protected spans far more often) or hash (50/50 per conversation)')
    ap.add_argument('--with-system', choices=('skip', 'apply'), default='skip',
                    help='conversations with a system prompt: pass through unchanged (default) or augment anyway')
    ap.add_argument('--keep-source', action='store_true', help='store the source messages in each output row')
    a = ap.parse_args()
    ids = [p['id'] for p in model_persona.PERSONAS]
    judge = setup_judge(a)
    rows = load(a.input)
    os.makedirs(a.outdir, exist_ok=True)
    afp = os.path.join(a.outdir, 'assign.jsonl')
    sem = asyncio.Semaphore(a.concurrency)
    stats = {}

    def bump(k):
        stats[k] = stats.get(k, 0) + 1
        if sum(stats.values()) % 500 == 0:
            print(a.step, json.dumps(stats), flush=True)

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=a.concurrency * 3),
                                     timeout=aiohttp.ClientTimeout(total=900)) as session:
        if a.step == 'assign':
            dn = done_ids(afp)
            fh = open(afp, 'a', encoding='utf-8')

            async def assign(r):
                async with sem:
                    rk = reason = None
                    if a.assign.startswith('fixed:'):
                        pick = a.assign.split(':', 1)[1]
                        assert pick in model_persona.BY_ID, pick
                    elif a.assign == 'random':
                        pick = ids[h(r['id'], 'ao-random') % len(ids)]
                    else:
                        order = ids[:]
                        random.Random(h(r['id'], 'mp-order')).shuffle(order)
                        users = [m['content'] for m in r['turns'] if m['role'] == 'user']
                        prompt = model_persona.MATCH_PROMPT_MESSAGES.format(messages=model_persona.user_messages_block(users),
                                                                      options=model_persona.match_options(order))
                        for _ in range(3):
                            text, _f = await judge_client.ask(session, prompt, 4096)
                            rk, reason = parse_ranking(text)
                            if rk:
                                break
                        pick = None if not rk else (rk[h(r['id'], 'ao-top3') % min(3, len(rk))] if a.assign == 'top3' else rk[0])
                    fh.write(json.dumps({'id': r['id'], 'model_persona': pick, 'assign': a.assign, 'ranking': rk,
                                         'reason': reason}, ensure_ascii=False) + '\n')
                    fh.flush()
                    bump('assigned' if pick else 'unmatched')

            await asyncio.gather(*(assign(r) for r in rows if r['id'] not in dn))
            print('final assign', json.dumps(stats), flush=True)
            return

        assigned = {}
        if a.step != 'none':
            for l in open(afp, encoding='utf-8'):
                x = json.loads(l)
                assigned[x['id']] = x['model_persona']
        servers = responder_urls(a)
        models = [m for m in ('gemma', 'ministral') if servers[m]]
        assert models, 'need --gemma and/or --ministral'
        base = copy.deepcopy(BASE_CONFIG)
        base['persona'] = dict(base['persona'], use_persona=False, inject_system_prompt=False)
        if judge:
            base['judge'] = judge
        base['_lang_ok'] = lambda t, l: True
        sd = os.path.join(a.outdir, a.step)
        os.makedirs(sd, exist_ok=True)
        handles, work = {}, []
        for r in rows:
            fp = os.path.join(sd, r['file'])
            if fp not in handles:
                handles[fp] = (open(fp, 'a', encoding='utf-8'), done_ids(fp))
            fh, dn = handles[fp]
            if r['id'] not in dn:
                work.append((r, fh))

        async def one(r, fh):
            if r['system'] and a.with_system == 'skip' and a.step != 'none':
                rec = {'id': r['id'], 'step': a.step, 'model_persona': None, 'status': 'skipped_system', 'messages': r['source']}
                fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
                fh.flush()
                bump('skipped_system')
                return
            mp_id = None if a.step == 'none' else assigned.get(r['id'])
            if a.step != 'none' and not mp_id:
                bump('unassigned')
                return
            model = models[h(r['id'], 'ao-responder') % len(models)]
            if a.step == 'restyle' and a.restyle_model != 'hash' and servers.get(a.restyle_model):
                model = a.restyle_model
            rec = {'id': r['id'], 'step': a.step, 'model_persona': mp_id, 'responder': model}
            async with sem:
                if a.step == 'restyle':
                    if not any(m['role'] == 'assistant' for m in r['turns']):
                        rec['status'] = 'no_assistant'
                    else:
                        responder = random.choice(responders(a, (model,)))
                        conv, flags, last_user = [dict(m) for m in r['turns']], [], ''
                        for m in conv:
                            if m['role'] == 'user':
                                last_user = m['content']
                            else:
                                m['content'], fail = await restyle(session, responder, model_persona.BY_ID[mp_id], last_user, m['content'])
                                flags.append(fail)
                        rec.update(status='pass' if not all(flags) else 'kept_original',
                                   messages=([{'role': 'system', 'content': r['system']}] if r['system'] else []) + conv,
                                   restyle_failures=flags)
                else:
                    cfg = dict(base)
                    cfg['responders'] = responders(a, (model,))
                    cfg['_model_persona'] = model_persona.BY_ID[mp_id] if mp_id else None
                    cfg['_source_system'] = r['system'] or None
                    try:
                        res = await pipeline.process_conversation(session, r['turns'], cfg, r['id'])
                        md = res['metadata']
                        rec.update(status=md.get('sanity_status', 'error'),
                                   messages=([{'role': 'system', 'content': r['system']}] if r['system'] else []) + res['conversation'],
                                   sanity_verdicts=md.get('sanity_verdicts'),
                                   quirks=[td.get('model_persona_quirk') for td in md.get('turns_detail') or []],
                                   adaptations=[len(td.get('adaptations') or []) for td in md.get('turns_detail') or []])
                    except Exception as exc:
                        rec.update(status='error', exception=f'{type(exc).__name__}: {exc}'[:300])
            if a.keep_source:
                rec['source_messages'] = r['source']
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
            fh.flush()
            bump(rec['status'])

        await asyncio.gather(*(one(r, fh) for r, fh in work))
    print('final', a.step, json.dumps(stats), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
