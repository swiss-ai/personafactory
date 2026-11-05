#!/usr/bin/env python3
"""Style-perturbation probe set for the downstream SFT ablation.

300 held-out requests (prepared-pair split 'test', English, single turn, no strict-format task) x
(12 English-speaking user personas spanning digital fluency / AI stance / capitalization / message length /
typos + the unstyled original as control). Each styled variant is the pipeline's user rewrite (ADAPT template
as one user message, full persona, quirk p=0.25, literal protection, length guard) by the rewriter model, so the
request is fixed and only the user's voice changes.

Inputs:  persona bank JSONL (--bank), prepared source pairs (--pairs-glob), an OpenAI-compatible rewriter
         endpoint (--rewriter-url, served model name --rewriter-model; the paper used google/gemma-4-31B-it).
Outputs: <out-dir>/probes.jsonl and <out-dir>/probe_personas.json.

Run from the repo root:
  python -m personafactory.sft_ablation.build_probes --rewriter-url http://HOST:8000/v1 --rewriter-model gemma \
      --bank data/persona_bank.jsonl --pairs-glob 'data/prepared/pairs/*.jsonl'
"""
import argparse, asyncio, collections, glob, json, os, random
import aiohttp
from personafactory.augmentation import pipeline as H, prompts, integrity

N_REQ, SEED = 300, 20260925
OUT_ROOT = os.path.join(os.environ.get('PF_OUT_DIR', './outputs'), 'sft_ablation')


def english_single(p):
    users = [m['content'] for m in p['conversation'] if m['role'] == 'user']
    u = users[0] if users else ''
    return u if 40 <= len(u) <= 800 and H.detect_language(u) == 'english' and not H.should_skip_persona(u) else None


def pick_personas(bank):
    """12 English-speaking personas, greedily maximising coverage of style buckets."""
    rng = random.Random(SEED)
    cands = []
    for p in bank:
        bg, st = p['background'], p.get('style') or {}
        s = st.get('chatting_style_structured') or {}
        if str(bg.get('main_language')) != 'English' or not st.get('chatting_style'):
            continue
        key = (str(bg.get('digital_fluency')), str(bg.get('ai_stance')),
               'lower' if 'lower' in str(s.get('capitalization', '')).lower() else 'std',
               'terse' if any(w in str(s.get('message_structure', '')).lower() for w in ('terse', 'short', 'fragment')) else 'full',
               'typos' if 'typo' in str(s.get('typo_tendency', '')).lower() and 'clean' not in str(s.get('typo_tendency', '')).lower() else 'clean')
        cands.append((key, p))
    rng.shuffle(cands)
    chosen, seen = [], [set() for _ in range(5)]
    while len(chosen) < 12:
        best = max(cands, key=lambda kp: sum(kp[0][i] not in seen[i] for i in range(5)))
        chosen.append(best)
        for i in range(5):
            seen[i].add(best[0][i])
        cands.remove(best)
    return chosen


async def rewrite(session, rewriter, persona, msg, rng):
    quirk = ("Use the persona's typing style and, if natural, you may include one of their verbal mannerisms or tics."
             if rng.random() <= 0.25 else
             "For this turn, maintain typing/punctuation style only; do NOT include any verbal filler words or mannerisms.")
    masked, spans = integrity.protect(msg)
    prompt = prompts.ADAPT_USER_PROMPT_TEMPLATE.format(background=H.get_persona_background_str(persona),
                                                       writing_style=H.get_persona_style_str(persona),
                                                       verbal_quirks_instruction=quirk, user_message=masked)
    if spans:
        prompt += "\n\n" + integrity.protection_instruction().strip()
    for _ in range(3):
        text, err = await H.call_api(session, rewriter, {'max_tokens': 4096, 'temperature': 0.7, 'top_p': 0.95},
                                     [{'role': 'user', 'content': prompt}], error_prefix='PROBE', is_judge=False)
        if not text or err:
            continue
        try:
            text = H.sanitize_constitution(integrity.restore(text.strip(), spans))
        except ValueError:
            continue
        if len(msg) >= 50 and len(text) < 0.5 * len(msg):  # length guard
            continue
        return text
    return None


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--rewriter-url', required=True, help='OpenAI-compatible base URL, e.g. http://HOST:8000/v1')
    ap.add_argument('--rewriter-model', default='gemma', help='served model name of the rewriter')
    ap.add_argument('--rewriter-api-key', default='dummy', help='API key, or ENV=VARNAME to read it from the environment')
    ap.add_argument('--bank', default=os.environ.get('PF_BANK', 'data/persona_bank.jsonl'))
    ap.add_argument('--pairs-glob', required=True, help="prepared source pairs with a 'split' field, e.g. 'data/prepared/pairs/*.jsonl'")
    ap.add_argument('--out-dir', default=os.path.join(OUT_ROOT, 'probes'))
    ap.add_argument('--concurrency', type=int, default=96)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    bank = [json.loads(l) for l in open(a.bank, encoding='utf-8')]
    personas = pick_personas(bank)
    reqs = []
    for fp in sorted(glob.glob(a.pairs_glob)):
        for l in open(fp, encoding='utf-8'):
            p = json.loads(l)
            if p.get('split') == 'test':
                u = english_single(p)
                if u:
                    reqs.append((p['pair_key'], p.get('source_name'), u))
    rng = random.Random(SEED)
    by_src = collections.defaultdict(list)
    for r in reqs:
        by_src[r[1]].append(r)
    pick = []
    for src, rs in sorted(by_src.items()):
        pick += rng.sample(rs, min(N_REQ // len(by_src), len(rs)))
    rewriter = {'name': 'rewriter', 'base_url': a.rewriter_url, 'api_key': a.rewriter_api_key, 'model': a.rewriter_model}
    sem = asyncio.Semaphore(a.concurrency)
    out = []
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=900)) as session:
        async def one(i, req, pi, persona):
            async with sem:
                styled = await rewrite(session, rewriter, persona, req[2], random.Random(f'{SEED}|{i}|{pi}'))
            out.append({'probe_id': f'{i:03d}-p{pi:02d}', 'request_id': i, 'source_pair': req[0], 'source_name': req[1],
                        'request': req[2], 'persona_idx': pi, 'persona_id': persona['id'], 'persona_key': list(key_of[persona['id']]),
                        'user_message': styled})
        key_of = {p['id']: k for k, p in personas}
        jobs = [one(i, r, pi, p) for i, r in enumerate(pick) for pi, (_, p) in enumerate(personas)]
        await asyncio.gather(*jobs)
    for i, r in enumerate(pick):  # unstyled control
        out.append({'probe_id': f'{i:03d}-orig', 'request_id': i, 'source_pair': r[0], 'source_name': r[1], 'request': r[2],
                    'persona_idx': None, 'persona_id': None, 'persona_key': None, 'user_message': r[2]})
    out.sort(key=lambda x: x['probe_id'])
    with open(os.path.join(a.out_dir, 'probes.jsonl'), 'w', encoding='utf-8') as fh:
        for x in out:
            fh.write(json.dumps(x, ensure_ascii=False) + '\n')
    json.dump([{'idx': i, 'persona_id': p['id'], 'key': list(k)} for i, (k, p) in enumerate(personas)],
              open(os.path.join(a.out_dir, 'probe_personas.json'), 'w'), indent=1)
    print(json.dumps({'requests': len(pick), 'probes': len(out), 'failed_rewrites': sum(x['user_message'] is None for x in out),
                      'persona_keys': [list(k) for k, _ in personas]}, indent=1))


if __name__ == '__main__':
    asyncio.run(main())
