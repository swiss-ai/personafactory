#!/usr/bin/env python3
"""Structured vs flat chatting-style A/B (rewrite only).

For each prompt: pick a persona deterministically with the pipeline's matcher, rewrite the prompt twice with the
same model, once with style_mode="flat" (the free-text chatting_style sentence) and once with "structured" (the
chatting_style_structured keys), everything else identical. A pairwise judge (order randomized) says which rewrite
better adopts the persona's writing style, and an intent check confirms each preserved the request.

Inputs:  --samples JSONL files with an "original_message" field (records without it are skipped),
         --bank persona bank JSONL, rewriter and judge endpoints (comma lists or files with one base URL per line)
Outputs: --out JSONL, one row per prompt (status, winner, intent verdicts, both rewrites), plus a printed summary
Run:     python -m personafactory.evaluation.structured_vs_flat.ab_style_test --samples ./data/ab_prompts.jsonl --bank ./data/bank.jsonl \
             --rewriter-urls http://HOST:8080/v1 --rewriter-model google/gemma-4-31B-it \
             --judge-urls http://HOST:30000/v1 --judge-model MiniMax-M2.5 --out ./outputs/ab_style_results.jsonl
"""
import argparse, asyncio, json, os, random, collections
import aiohttp

from personafactory.augmentation.pipeline import (select_persona, get_persona_background_str, get_persona_style_str,
                                   call_api, should_skip_persona)
from personafactory.augmentation.prompts import ADAPT_USER_PROMPT_TEMPLATE
from personafactory.evaluation.structured_vs_flat.prompts import PAIRWISE_FIRST_PASS as PAIRWISE, INTENT

GEN = {"max_tokens": 4096, "temperature": 0.3, "top_p": 0.95}
JGEN = {"max_tokens": 1024, "temperature": 0.1, "top_p": 1.0}
QUIRK_INSTR = "Use the persona's typing style and, if natural, one of their verbal mannerisms."
PERSONA_CFG = {"language_match": True, "random_fallback": True, "verbal_quirk_prob": 0.25,
               "matching": {"location_regex": True, "topic_keywords": True, "embedding_fallback": False,
                            "top_k_location": 3, "top_k_topic": 3, "top_k_embedding": 3, "min_embedding_similarity": 0.15}}


def endpoints(spec):
    """Comma-separated base URLs, or a file with one base URL per line."""
    if spec and os.path.exists(spec):
        return [l.strip() for l in open(spec) if l.strip().startswith("http")]
    return [u.strip() for u in (spec or "").split(",") if u.strip().startswith("http")]


def cfg(url, model):
    return {"base_url": url, "model": model, "api_key": os.environ.get("PF_API_KEY", "dummy")}


def parse_json(txt):
    if not txt:
        return None
    if "</think>" in txt:
        txt = txt.split("</think>")[-1]
    if "```json" in txt:
        txt = txt.split("```json")[-1]
    txt = txt.replace("```", "")
    a, b = txt.find("{"), txt.rfind("}")
    if a == -1 or b == -1:
        return None
    try:
        return json.loads(txt[a:b + 1])
    except Exception:
        return None


async def rewrite(session, resp_urls, model, background, style, msg):
    prompt = ADAPT_USER_PROMPT_TEMPLATE.format(background=background, writing_style=style,
                                               user_message=msg, verbal_quirks_instruction=QUIRK_INSTR)
    txt, err = await call_api(session, cfg(random.choice(resp_urls), model), GEN,
                              [{"role": "user", "content": prompt}], error_prefix="REWRITE")
    return (txt or "").strip() if not err else None


async def judge(session, judge_urls, model, prompt):
    txt, err = await call_api(session, cfg(random.choice(judge_urls), model), JGEN,
                              [{"role": "user", "content": prompt}], error_prefix="JUDGE", is_judge=True)
    return parse_json(txt) if not err else None


async def one(session, a, resp_urls, judge_urls, personas, rec, sem):
    async with sem:
        msg = (rec.get("original_message") or "").strip()
        if not msg or should_skip_persona(msg):
            return {"status": "skip_prompt"}
        persona, tier, _ = select_persona(msg, personas, PERSONA_CFG)
        if persona is None:
            return {"status": "no_persona"}
        bg = get_persona_background_str(persona)
        flat = get_persona_style_str(persona, style_mode="flat")
        struct = get_persona_style_str(persona, style_mode="structured")
        full = get_persona_style_str(persona, style_mode="both")
        rw_flat, rw_struct = await asyncio.gather(
            rewrite(session, resp_urls, a.rewriter_model, bg, flat, msg),
            rewrite(session, resp_urls, a.rewriter_model, bg, struct, msg))
        if not rw_flat or not rw_struct:
            return {"status": "rewrite_fail"}
        # pairwise with randomized A/B order to avoid position bias
        flat_is_A = random.random() < 0.5
        A, B = (rw_flat, rw_struct) if flat_is_A else (rw_struct, rw_flat)
        pj, i_flat, i_struct = await asyncio.gather(
            judge(session, judge_urls, a.judge_model, PAIRWISE.format(background=bg, style=full, original=msg, a=A, b=B)),
            judge(session, judge_urls, a.judge_model, INTENT.format(original=msg, rewrite=rw_flat)),
            judge(session, judge_urls, a.judge_model, INTENT.format(original=msg, rewrite=rw_struct)))
        winner = None
        if pj and pj.get("winner") in ("A", "B", "tie"):
            w = pj["winner"]
            winner = "tie" if w == "tie" else ("flat" if (w == "A") == flat_is_A else "structured")
        return {"status": "ok", "persona_id": persona.get("id"), "tier": tier,
                "winner": winner, "reason": (pj or {}).get("reason", ""),
                "intent_flat": (i_flat or {}).get("verdict"), "intent_struct": (i_struct or {}).get("verdict"),
                "rewrite_flat": rw_flat, "rewrite_structured": rw_struct, "original": msg}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", nargs="+", required=True, help="prompt JSONL files (field original_message)")
    ap.add_argument("--bank", required=True, help="persona bank JSONL")
    ap.add_argument("--rewriter-urls", required=True)
    ap.add_argument("--rewriter-model", required=True)
    ap.add_argument("--judge-urls", required=True)
    ap.add_argument("--judge-model", required=True)
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--concurrency", type=int, default=48)
    ap.add_argument("--out", default="./outputs/ab_style_results.jsonl")
    args = ap.parse_args()
    resp_urls, judge_urls = endpoints(args.rewriter_urls), endpoints(args.judge_urls)
    assert resp_urls and judge_urls, f"missing endpoints: resp={len(resp_urls)} judge={len(judge_urls)}"
    print(f"responders={len(resp_urls)} judges={len(judge_urls)}")
    prompts = []
    for f in args.samples:
        for l in open(f, errors="ignore"):
            l = l.strip()
            if l:
                prompts.append(json.loads(l))
    seen = set()
    uniq = []
    for r in prompts:
        m = (r.get("original_message") or "").strip()
        if m and m not in seen:
            seen.add(m)
            uniq.append(r)
    random.seed(1337)
    random.shuffle(uniq)
    uniq = uniq[:args.n]
    personas = [json.loads(l) for l in open(args.bank, errors="ignore") if l.strip()]
    random.seed(7)
    if len(personas) > 20000:   # select_persona scans all personas per call; 20k keeps variety at a fraction of the cost
        personas = random.sample(personas, 20000)
    print(f"prompts={len(uniq)} personas={len(personas)}")
    sem = asyncio.Semaphore(args.concurrency)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*[one(session, args, resp_urls, judge_urls, personas, r, sem) for r in uniq])
    with open(args.out, "w") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=True) + "\n")
    st = collections.Counter(r["status"] for r in results)
    ok = [r for r in results if r["status"] == "ok"]
    win = collections.Counter(r["winner"] for r in ok if r["winner"])
    scored = sum(win.values())
    ifl = sum(1 for r in ok if r["intent_flat"] == "pass")
    istr = sum(1 for r in ok if r["intent_struct"] == "pass")
    print("\n=== A/B RESULTS (flat vs structured chatting-style) ===")
    print(f"statuses: {dict(st)}")
    print(f"scored pairs: {scored}")
    if scored:
        print(f"  STRUCTURED better: {win['structured']} ({100 * win['structured'] // scored}%)")
        print(f"  FLAT better:       {win['flat']} ({100 * win['flat'] // scored}%)")
        print(f"  tie:               {win['tie']} ({100 * win['tie'] // scored}%)")
    if ok:
        print(f"intent preserved: flat {100 * ifl // len(ok)}%  structured {100 * istr // len(ok)}%  (n={len(ok)})")
    print(f"-> {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
