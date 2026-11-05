#!/usr/bin/env python3
"""Pairwise LLM judge of presentation fit to the user, with a length-controlled win rate (Table tab:mp-sft-judge,
Figure fig:mp-sft-lc).

For every styled probe and every model pair (a, b), the judge (MiniMax-M2.5 in the paper) sees the probe persona's
reduced user card (AI stance, digital fluency, structured typing keys; no demographics), the user message and both
responses in randomised order, and picks the one presented better for this user (assistant.model_persona.FIT_JUDGE).
Reported per pair: raw win rate of a (ties excluded) with a 95% normal-approximation interval, and a
length-controlled win rate: logistic regression of 'a wins' on d = log(words_a / words_b); the LC win rate is the
fitted probability at d = 0 (the AlpacaEval-LC idea).
Writes judge_lc.json and judge_lc_verdicts.jsonl (resumable: finished verdicts are reused).

Run from the repo root (judge endpoints are OpenAI-compatible base URLs ending in /v1; model name from
PF_JUDGE_MODEL, default MiniMax-M2.5):
  python -m personafactory.sft_ablation.judge_lc --judge-urls http://HOST1:30000/v1,http://HOST2:30000/v1 \
      --pairs llama_C_user_persona_model_persona:llama_B_user_persona,llama_B_user_persona:llama_A_default
"""
import argparse, asyncio, glob, hashlib, itertools, json, math, os, re
import aiohttp
import numpy as np
from sklearn.linear_model import LogisticRegression
from personafactory.common import judge_client
from personafactory.assistant import model_persona as mp_core

OUT_ROOT = os.path.join(os.environ.get('PF_OUT_DIR', './outputs'), 'sft_ablation')


def ask_winner(text):
    text = (text or '').split('</think>')[-1]
    m = re.search(r'"winner"\s*:\s*"(1|2|tie)"', text)
    return m.group(1) if m else None


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--judge-urls', required=True, help='comma-separated OpenAI-compatible base URLs (.../v1)')
    ap.add_argument('--pairs', required=True, help='a:b,c:d model tags (file names in --responses without .jsonl)')
    ap.add_argument('--concurrency', type=int, default=256)
    ap.add_argument('--bank', default=os.environ.get('PF_BANK', 'data/persona_bank.jsonl'))
    ap.add_argument('--probes', default=os.path.join(OUT_ROOT, 'probes', 'probes.jsonl'))
    ap.add_argument('--responses', default=os.path.join(OUT_ROOT, 'responses'))
    ap.add_argument('--out-dir', default=OUT_ROOT, help='judge_lc.json and judge_lc_verdicts.jsonl go here')
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    judge_client.URLS = [u + '/chat/completions' for u in a.judge_urls.split(',')]
    probes = {json.loads(l)['probe_id']: json.loads(l) for l in open(a.probes, encoding='utf-8')}
    bank = {}
    need = {p['persona_id'] for p in probes.values() if p['persona_id']}
    for l in open(a.bank, encoding='utf-8'):
        x = json.loads(l)
        if x['id'] in need:
            bank[x['id']] = x
    resp = {}
    for fp in glob.glob(os.path.join(a.responses, '*.jsonl')):
        for l in open(fp, encoding='utf-8'):
            r = json.loads(l)
            resp[(r['model'], r['probe_id'])] = r['response']
    pairs = [tuple(x.split(':')) for x in a.pairs.split(',')]
    done = {}
    vf = os.path.join(a.out_dir, 'judge_lc_verdicts.jsonl')
    if os.path.exists(vf):
        for l in open(vf, encoding='utf-8'):
            v = json.loads(l)
            done[(v['a'], v['b'], v['probe_id'])] = v
    fh = open(vf, 'a', encoding='utf-8')
    sem = asyncio.Semaphore(a.concurrency)
    jobs = []
    for (ma, mb) in pairs:
        for pid, p in probes.items():
            if p['persona_idx'] is None or (ma, pid) not in resp or (mb, pid) not in resp or (ma, mb, pid) in done:
                continue
            jobs.append((ma, mb, pid, p))
    print('judge calls', len(jobs), flush=True)
    async with aiohttp.ClientSession() as session:
        async def one(ma, mb, pid, p):
            flip = int(hashlib.sha256(f'{ma}|{mb}|{pid}'.encode()).hexdigest(), 16) % 2 == 1
            ra, rb = resp[(ma, pid)], resp[(mb, pid)]
            r1, r2 = (rb, ra) if flip else (ra, rb)
            prompt = mp_core.FIT_JUDGE.format(card=mp_core.reduced_user_card(bank[p['persona_id']]),
                                              user_message=p['user_message'], r1=r1, r2=r2)
            w = None
            async with sem:
                for mt in (2048, 4096):
                    text, _ = await judge_client.ask(session, prompt, mt)
                    w = ask_winner(text)
                    if w:
                        break
            winner = None if w is None else 'tie' if w == 'tie' else (ma if (w == '1') != flip else mb)
            v = {'a': ma, 'b': mb, 'probe_id': pid, 'winner': winner,
                 'words_a': len(ra.split()), 'words_b': len(rb.split())}
            fh.write(json.dumps(v) + '\n')
            fh.flush()
            done[(ma, mb, pid)] = v
        await asyncio.gather(*(one(*j) for j in jobs))
    fh.close()
    out = {}
    for (ma, mb) in pairs:
        vs = [v for (x, y, _), v in done.items() if (x, y) == (ma, mb) and v['winner'] in (ma, mb)]
        ties = sum(1 for (x, y, _), v in done.items() if (x, y) == (ma, mb) and v['winner'] == 'tie')
        if not vs:
            continue
        y = np.array([v['winner'] == ma for v in vs], dtype=int)
        d = np.array([[math.log(max(v['words_a'], 1) / max(v['words_b'], 1))] for v in vs])
        raw = float(y.mean())
        lc = None
        if 0 < y.sum() < len(y):
            m = LogisticRegression(C=1e6).fit(d, y)
            lc = float(1 / (1 + math.exp(-m.intercept_[0])))
        se = math.sqrt(raw * (1 - raw) / len(y))
        out[f'{ma}_vs_{mb}'] = {'n_decisive': len(vs), 'ties': ties, f'{ma}_win_pct': round(100 * raw, 1),
                                'ci95_pct': [round(100 * (raw - 1.96 * se), 1), round(100 * (raw + 1.96 * se), 1)],
                                f'{ma}_lc_win_pct': round(100 * lc, 1) if lc is not None else None,
                                'median_log_len_ratio': round(float(np.median(d)), 3)}
    json.dump(out, open(os.path.join(a.out_dir, 'judge_lc.json'), 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    asyncio.run(main())
