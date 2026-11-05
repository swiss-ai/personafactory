#!/usr/bin/env python3
"""Evaluate a model-persona pilot on the conversations present (non-error) in every arm (MiniMax-M2.5 judge).

Judges: style adoption against the matched persona (the random persona for the random-persona arm), same
content as the reference arm, pairwise presentation fit to the user (reduced user card, order randomised),
continuity with the real next user turn, instruction compliance on later turns whose user message carries a
format/length/style instruction, and the sanity gate for the restyled arm. Plus judge-free formatting
statistics (words, headers, bullets, emoji, stock openers, offer-to-help closings, self-reference).

Presets (the arms of assistant.pilot_regenerate / assistant.pilot_restyle):
  design  arms source, user_persona, user_persona_model_persona, user_persona_random_model_persona, restyled;
          content reference: source (the reply generated with the user persona)
  main    arms source, default, default_resample, model_persona, user_persona_model_persona;
          content reference: default (default_resample gives the noise floor)
--arms / --ref / --fit / --persona-arm override the preset; the first arm must be `source`.

Inputs: accepted source records (--source-dir), <out-dir>/match.jsonl and <out-dir>/arm_<arm>.jsonl.
Output: <out-dir>/eval.json (or --out).

  python -m personafactory.assistant.pilot_eval --preset design --source-dir ./outputs/pilot_design/src --out-dir ./outputs/pilot_design \
      --bank $PF_BANK --minimax $MINIMAX_URL
  python -m personafactory.assistant.pilot_eval --preset main --source-dir ./outputs/pilot_main/src --out-dir ./outputs/pilot_main \
      --bank $PF_BANK --minimax $MINIMAX_URL
"""
import argparse, asyncio, collections, json, os, re, statistics as st
import aiohttp
from personafactory.assistant import model_persona
from personafactory.assistant.pilot_regenerate import load_matches
from personafactory.assistant.shared import accepted_records, add_server_args, bank_for, h, setup_judge
from personafactory.augmentation import pipeline
from personafactory.augmentation.prompts import JUDGE_CONSISTENCY_TEMPLATE, SANITY_VERIFICATION_TEMPLATE
from personafactory.common import judge_client

SOURCE, RANDOM_ARM, RESTYLED = 'source', 'user_persona_random_model_persona', 'restyled'
UPMP = 'user_persona_model_persona'
PRESETS = {
    'design': {'arms': (SOURCE, 'user_persona', UPMP, RANDOM_ARM, RESTYLED), 'ref': SOURCE,
               'fit': ((UPMP, RANDOM_ARM), (UPMP, 'user_persona'), (RESTYLED, SOURCE)), 'persona_arm': UPMP},
    'main': {'arms': (SOURCE, 'default', 'default_resample', 'model_persona', UPMP), 'ref': 'default',
             'fit': ((UPMP, SOURCE), (UPMP, 'model_persona'), (UPMP, 'default'), ('model_persona', 'default')),
             'persona_arm': UPMP},
}
ARMS, REF, FIT, PARM = PRESETS['design']['arms'], SOURCE, PRESETS['design']['fit'], UPMP

EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿]')


def fmt(t):
    lines = t.splitlines()
    return {'words': len(t.split()), 'headers': sum(bool(re.match(r'\s*#{1,6} ', l)) for l in lines),
            'bullets': sum(bool(re.match(r'\s*([-*•]|\d+[.)]) ', l)) for l in lines),
            'bold': t.count('**') // 2, 'emoji': bool(EMOJI.search(t)),
            'stock_opener': bool(re.match(r"\s*(certainly|of course|great question|absolutely|sure[!,])", t, re.I)),
            'offer_close': bool(re.search(r"(let me know|feel free to|happy to help|hope this helps)[^\n]*\s*$", t, re.I)),
            'self_ref': bool(model_persona.SELF_REF_RX.search(t))}


async def verdict(session, prompt, key='verdict', ok=('pass', 'fail')):
    for mt in (2048, 4096):
        text, _ = await judge_client.ask(session, prompt, mt)
        text = (text or '').split('</think>')[-1]
        m = re.search(r'"' + key + r'"\s*:\s*"([^"]+)"', text)
        if m and m.group(1).lower() in ok:
            return m.group(1).lower()
    return None


async def run(a):
    global ARMS, REF, FIT, PARM
    preset = PRESETS[a.preset]
    ARMS = tuple(a.arms.split(',')) if a.arms else preset['arms']
    REF = a.ref or preset['ref']
    FIT = tuple(tuple(x.split(':')) for x in a.fit.split(',')) if a.fit else preset['fit']
    PARM = a.persona_arm or preset['persona_arm']
    assert ARMS[0] == SOURCE, f'the first arm must be {SOURCE}'
    setup_judge(a)
    src = {r['key']: r for r in accepted_records(a.source_dir)}
    arms = {SOURCE: {k: {'key': k, 'mode': r['mode'], 'responder': r['responder'], 'status': 'pass', 'result': r['result']}
                     for k, r in src.items()}}
    for arm in ARMS[1:]:
        arms[arm] = {}
        for l in open(os.path.join(a.out_dir, f'arm_{arm}.jsonl'), encoding='utf-8'):
            x = json.loads(l)
            if x.get('result'):
                arms[arm][x['key']] = x
    mt = load_matches(a.out_dir)
    keys = sorted(set.intersection(*(set(arms[a_]) for a_ in ARMS)))
    bank = bank_for(a.bank, {src[k]['persona_id'] for k in keys})
    gen_status = {arm: dict(collections.Counter(x['status'][:5] for x in arms[arm].values())) for arm in ARMS[1:]}
    print('paired conversations', len(keys), gen_status, flush=True)

    jobs, rows = [], []
    for k in keys:
        m = mt[k]
        card = model_persona.reduced_user_card(bank[src[k]['persona_id']])
        tds = src[k]['result']['metadata']['turns_detail']
        convs = {arm: arms[arm][k]['result']['conversation'] for arm in ARMS}
        n = min(len([x for x in c if x['role'] == 'assistant']) for c in convs.values())
        for t in range(n):
            user = convs[SOURCE][2 * t]['content']
            nxt = convs[SOURCE][2 * t + 2]['content'] if 2 * t + 2 < len(convs[SOURCE]) else None
            src_en = tds[t].get('user_message_source') or tds[t].get('user_message_original') or user
            row = {'key': k, 'turn': t, 'mode': src[k]['mode'], 'responder': src[k]['responder'],
                   'matched': m['matched'], 'random': m['random'],
                   'instr': t >= 1 and bool(model_persona.INSTRUCTION_RX.search(src_en)), 'res': {}}
            resp = {arm: convs[arm][2 * t + 1]['content'] for arm in ARMS}
            for arm in ARMS:
                row['res'][arm] = {'fmt': fmt(resp[arm])}
                sp = model_persona.BY_ID[m['random'] if arm == RANDOM_ARM else m['matched']]
                jobs.append((row, arm, 'style', model_persona.STYLE_JUDGE.format(style=model_persona.render_model_persona(sp), response=resp[arm])))
                if arm != REF:
                    jobs.append((row, arm, 'content', model_persona.CONTENT_JUDGE.format(user_message=user, a=resp[REF], b=resp[arm])))
                if nxt is not None:
                    ctx = pipeline.format_context(convs[arm][:2 * t + 1])
                    jobs.append((row, arm, 'continuity', JUDGE_CONSISTENCY_TEMPLATE.format(context=ctx, response=resp[arm], next_user_message=nxt)))
                if row['instr']:
                    jobs.append((row, arm, 'instr', model_persona.IF_JUDGE.format(context=pipeline.format_context(convs[arm][:2 * t]) or 'Start of conversation',
                                                                             user_message=user, response=resp[arm])))
            if RESTYLED in ARMS:
                ctx_s = pipeline.format_context(convs[RESTYLED][:2 * t]) if t else 'Start of conversation'
                jobs.append((row, RESTYLED, 'sanity', SANITY_VERIFICATION_TEMPLATE.format(context=ctx_s, user_message=user, response=resp[RESTYLED])))
            for pa, pb in FIT:
                flip = h(k, t, pa, pb) % 2 == 1
                r1, r2 = (resp[pb], resp[pa]) if flip else (resp[pa], resp[pb])
                jobs.append((row, f'{pa}_vs_{pb}', ('fit', flip), model_persona.FIT_JUDGE.format(card=card, user_message=user, r1=r1, r2=r2)))
            rows.append(row)
    print('judge calls', len(jobs), flush=True)
    sem = asyncio.Semaphore(a.concurrency)
    done = [0]
    async with aiohttp.ClientSession() as session:
        async def one(job):
            row, arm, kind, prompt = job
            async with sem:
                if isinstance(kind, tuple):
                    w = await verdict(session, prompt, 'winner', ('1', '2', 'tie'))
                    if w in ('1', '2'):
                        first_is_a = not kind[1]
                        w = 'a' if (w == '1') == first_is_a else 'b'
                    row.setdefault('fit', {})[arm] = w
                elif kind == 'continuity':
                    row['res'][arm]['continuity'] = await verdict(session, prompt, 'verdict', ('pass', 'needs_adaptation'))
                else:
                    row['res'][arm][kind] = await verdict(session, prompt)
            done[0] += 1
            if done[0] % 2000 == 0:
                print('judged', done[0], flush=True)
        await asyncio.gather(*(one(j) for j in jobs))

    def rate(vals, good):
        v = [x for x in vals if x is not None]
        return round(100 * sum(x == good for x in v) / len(v), 1) if v else None

    out = {'paired_conversations': len(keys), 'turns': len(rows), 'generation_status': gen_status,
           'match_distribution': dict(collections.Counter(mt[k]['matched'] for k in keys).most_common()), 'arms': {}}
    for arm in ARMS:
        rs = [r['res'][arm] for r in rows]
        f = [x['fmt'] for x in rs]
        out['arms'][arm] = {
            'style_adoption_pct': rate([x.get('style') for x in rs], 'pass'),
            'content_same_as_ref_pct': rate([x.get('content') for x in rs], 'pass') if arm != REF else None,
            'continuity_pass_pct': rate([x.get('continuity') for x in rs], 'pass'),
            'instruction_compliance_pct': rate([r['res'][arm].get('instr') for r in rows if r['instr']], 'pass'),
            'instruction_turns': sum(r['instr'] for r in rows),
            'median_words': st.median(x['words'] for x in f), 'with_headers_pct': rate([x['headers'] > 0 for x in f], True),
            'with_bullets_pct': rate([x['bullets'] > 0 for x in f], True), 'emoji_pct': rate([x['emoji'] for x in f], True),
            'stock_opener_pct': rate([x['stock_opener'] for x in f], True), 'offer_close_pct': rate([x['offer_close'] for x in f], True),
            'self_reference_pct': rate([x['self_ref'] for x in f], True)}
    out['content_reference_arm'] = REF
    if RESTYLED in ARMS:
        out['arms'][RESTYLED]['sanity_pass_pct'] = rate([r['res'][RESTYLED].get('sanity') for r in rows], 'pass')
    out['pairwise_fit'] = {}
    for pair in [f'{x}_vs_{y}' for x, y in FIT]:
        pa, pb = pair.split('_vs_')
        v = [r.get('fit', {}).get(pair) for r in rows]
        v = [x for x in v if x]
        out['pairwise_fit'][pair] = {'n': len(v), f'{pa}_wins_pct': rate(v, 'a'), f'{pb}_wins_pct': rate(v, 'b'), 'tie_pct': rate(v, 'tie')}
    out['by_mode'] = {md: {arm: {'style': rate([r['res'][arm].get('style') for r in rows if r['mode'] == md], 'pass'),
                                 'content': rate([r['res'][arm].get('content') for r in rows if r['mode'] == md], 'pass')}
                           for arm in ARMS} for md in ('free', 'multilingual')}
    out['by_responder'] = {rp: {arm: {'style': rate([r['res'][arm].get('style') for r in rows if r['responder'] == rp], 'pass'),
                                      'content': rate([r['res'][arm].get('content') for r in rows if r['responder'] == rp], 'pass')}
                                for arm in ARMS} for rp in ('gemma', 'ministral')}
    out['matched_arm_by_persona'] = {}
    for pid in model_persona.BY_ID:
        rs = [r for r in rows if r['matched'] == pid]
        if rs:
            f = [r['res'][PARM]['fmt'] for r in rs]
            out['matched_arm_by_persona'][pid] = {'turns': len(rs), 'style_persona_arm': rate([r['res'][PARM].get('style') for r in rs], 'pass'),
                                                  'style_ref': rate([r['res'][REF].get('style') for r in rs], 'pass'),
                                                  'content_persona_arm': rate([r['res'][PARM].get('content') for r in rs], 'pass'),
                                                  'median_words_persona_arm': st.median(x['words'] for x in f),
                                                  'median_words_ref': st.median(r['res'][REF]['fmt']['words'] for r in rs)}
    json.dump(out, open(a.out or os.path.join(a.out_dir, 'eval.json'), 'w'), indent=1)
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preset', choices=tuple(PRESETS), default='design')
    ap.add_argument('--source-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--bank', default=os.environ.get('PF_BANK'), required='PF_BANK' not in os.environ)
    ap.add_argument('--out', help='output JSON (default: <out-dir>/eval.json)')
    ap.add_argument('--arms', help="comma list, first must be 'source'")
    ap.add_argument('--ref', help='content reference arm')
    ap.add_argument('--fit', help='pairs a:b,c:d')
    ap.add_argument('--persona-arm', help='arm reported per model persona')
    ap.add_argument('--concurrency', type=int, default=128, help='concurrent judge calls')
    add_server_args(ap)
    asyncio.run(run(ap.parse_args()))


if __name__ == '__main__':
    main()
