#!/usr/bin/env python3
"""Re-judge the structured vs flat A/B pairwise on the STORED rewrites (no re-rewriting), with order randomized
per item and requests rotated and retried across judge endpoints.

The judge's reasoning block is split off at </think> and the trailing JSON is read, so the token budget must fit
reasoning plus answer (3072 here); dropped calls are retried on another endpoint.

Inputs:  --results (ab_style_test.py output), --bank (the persona bank the A/B used), --judge-urls, --judge-model
Outputs: printed summary (preference shares, decisive share); with --out, a JSONL in the ab_rejudge.py layout
         (summary line, then one row per pair) that ab_table.py can read
Run:     python -m personafactory.evaluation.structured_vs_flat.re_judge_ab --results ./outputs/ab_style_results.jsonl \
             --bank ./data/bank.jsonl --judge-urls http://HOST:30000/v1 --judge-model MiniMax-M2.5
"""
import argparse, asyncio, json, os, random, collections
import aiohttp

from personafactory.augmentation.pipeline import get_persona_background_str, get_persona_style_str
from personafactory.evaluation.structured_vs_flat.ab_style_test import endpoints
from personafactory.evaluation.structured_vs_flat.prompts import PAIRWISE


async def judge(session, urls, model, prompt):
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
               "max_tokens": 3072, "temperature": 0.0}
    for attempt in range(4):
        url = random.choice(urls).rstrip("/") + "/chat/completions"
        try:
            async with session.post(url, json=payload, headers={"Authorization": "Bearer " + os.environ.get("PF_API_KEY", "dummy")},
                                    timeout=aiohttp.ClientTimeout(total=300)) as r:
                d = await r.json()
                txt = (d["choices"][0]["message"].get("content") or "")
                if "</think>" in txt:
                    txt = txt.split("</think>")[-1]
                a, b = txt.find("{"), txt.rfind("}")
                if a >= 0 and b >= 0:
                    return json.loads(txt[a:b + 1])
        except Exception:
            pass
        await asyncio.sleep(1.5 * (attempt + 1))
    return None


async def one(session, urls, model, persona, row, sem):
    async with sem:
        bg = get_persona_background_str(persona)
        style = get_persona_style_str(persona, style_mode="both")
        flat_is_A = random.random() < 0.5
        A, B = (row["rewrite_flat"], row["rewrite_structured"]) if flat_is_A else (row["rewrite_structured"], row["rewrite_flat"])
        pj = await judge(session, urls, model, PAIRWISE.format(background=bg, style=style, original=row["original"], a=A, b=B))
        if pj and pj.get("winner") in ("A", "B", "tie"):
            w = pj["winner"]
            return "tie" if w == "tie" else ("flat" if (w == "A") == flat_is_A else "structured")
        return None


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--bank", required=True)
    ap.add_argument("--judge-urls", required=True)
    ap.add_argument("--judge-model", required=True)
    ap.add_argument("--concurrency", type=int, default=60)
    ap.add_argument("--out", default=None, help="optional per-pair output JSONL")
    args = ap.parse_args()
    urls = endpoints(args.judge_urls)
    assert urls, "no judge endpoints"
    rows = [json.loads(l) for l in open(args.results)]
    ok = [r for r in rows if r["status"] == "ok" and r.get("rewrite_flat") and r.get("rewrite_structured")]
    bank = {}
    for l in open(args.bank, errors="ignore"):
        l = l.strip()
        if l:
            d = json.loads(l)
            bank[d.get("id")] = d
    ok = [r for r in ok if r.get("persona_id") in bank]
    print(f"re-judging {len(ok)} stored pairs | judges={len(urls)}")
    sem = asyncio.Semaphore(args.concurrency)
    async with aiohttp.ClientSession() as s:
        res = await asyncio.gather(*[one(s, urls, args.judge_model, bank[r["persona_id"]], r, sem) for r in ok])
    win = collections.Counter(x for x in res if x)
    scored = sum(win.values())
    print("\n=== RE-JUDGED A/B (full sample) ===")
    print(f"scored: {scored} / {len(ok)}")
    if scored:
        print(f"  STRUCTURED better: {win['structured']} ({100 * win['structured'] // scored}%)")
        print(f"  FLAT better:       {win['flat']} ({100 * win['flat'] // scored}%)")
        print(f"  tie:               {win['tie']} ({100 * win['tie'] // scored}%)")
        dec = win['structured'] + win['flat']
        if dec:
            print(f"  decisive (excl. tie): STRUCTURED {100 * win['structured'] // dec}% vs FLAT {100 * win['flat'] // dec}%")
    if args.out:
        with open(args.out, "w") as f:
            f.write(json.dumps({"judge": args.judge_model, "pairs": len(ok), "scored": scored, "outcomes": dict(win)}) + "\n")
            for i, (r, x) in enumerate(zip(ok, res)):
                f.write(json.dumps({"idx": i, "persona_id": r["persona_id"], "outcome": x,
                                    "intent_flat": r.get("intent_flat"), "intent_struct": r.get("intent_struct")}) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
