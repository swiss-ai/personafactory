#!/usr/bin/env python
"""Multi-judge robustness: re-score the pairwise comparisons with every available judge.

All results so far come from a single judge (MiniMax-M2.5). If that judge systematically
favours a kind of output, the ranking could be an artifact. Here the same stored rewrites
are re-judged by gemma, Ministral and GLM as well, using the identical PAIRWISE template
and the same order randomisation, so only the judge changes.

The bar is ranking stability, not agreement on absolute rates: judges are known to differ
sharply in severity (multi-judge agreement study: GLM 0.93 vs MiniMax 0.78 mean style verdict).
Judge families are read from the config: the judge, every responder name and the projector.

Run: python -m personafactory.evaluation.format_comparison.multi_judge --generations ./outputs/format_comparison/generations.jsonl \
         --items ./outputs/format_comparison/items.jsonl --config evaluation/format_comparison/config.yaml \
         --out ./outputs/format_comparison/multi_judge.jsonl --n 200 --judges minimax,gemma,ministral,glm
"""
from __future__ import annotations
import argparse, asyncio, itertools, json, os, random, re, sys
from collections import defaultdict

import aiohttp, yaml

from personafactory.augmentation.pipeline import call_api
from personafactory.evaluation.structured_vs_flat.prompts import PAIRWISE
from personafactory.evaluation.format_comparison import renderers
from personafactory.evaluation.format_comparison.score_conditions import _pairwise_winner

REF = "personafactory"


def judge_pools(cfg):
    """Every distinct model family we can serve as a judge."""
    pools = {}
    j = cfg["judge"]
    pools["minimax"] = [{**j, "base_url": u}
                        for u in (j.get("base_urls") or [j["base_url"]])]
    fam = defaultdict(list)
    for r in cfg.get("responders", []):
        fam[r["name"]].append(r)
    for name, eps in fam.items():
        pools[name] = eps
    if cfg.get("projector"):
        pools[cfg["projector"]["name"]] = [cfg["projector"]]
    return pools


async def main_async(a, cfg):
    rows = [json.loads(l) for l in open(a.generations)]
    personas = {json.loads(l)["persona_id"]: json.loads(l)["persona"]
                for l in open(a.items)}
    by = defaultdict(dict)
    for r in rows:
        if r.get("rewrite"):
            by[r["item_id"]][r["condition"]] = r

    ids = sorted(i for i in by if REF in by[i] and len(by[i]) == 4)
    random.Random(cfg.get("seed", 20260901)).shuffle(ids)
    ids = ids[: a.n]
    pools = judge_pools(cfg)
    names = [n for n in a.judges.split(",") if n in pools]
    print(f"{len(ids)} items x 3 comparisons x {len(names)} judges "
          f"= {len(ids)*3*len(names)} calls   judges={names}")

    gen = cfg["judge_gen"]
    sem = asyncio.Semaphore(cfg.get("concurrency", 96))
    lock = asyncio.Lock(); out = open(a.out, "a"); done = [0]
    rng = random.Random(7)
    tasks = []
    for jn in names:
        pool = itertools.cycle(pools[jn])
        for iid in ids:
            ref = by[iid][REF]
            p = personas.get(ref["persona_id"])
            if not p:
                continue
            bg, st = renderers.render(p, "personafactory")
            for cond in ("none", "personahub", "synthpai"):
                r = by[iid].get(cond)
                if not r:
                    continue
                flip = rng.random() < 0.5
                A, B = (r, ref) if flip else (ref, r)
                tasks.append((jn, next(pool), iid, cond, flip, PAIRWISE.format(
                    background=bg, style=st, original=ref["seed_prompt"],
                    a=A["rewrite"], b=B["rewrite"])))

    async with aiohttp.ClientSession() as session:
        async def run(jn, api, iid, cond, flip, prompt):
            msg = [{"role": "user", "content": prompt}]
            text = None
            for temp in (gen.get("temperature", 0.1), 0.4, 0.8):
                g = dict(gen); g["temperature"] = temp
                async with sem:
                    text, _ = await call_api(session, api, g, msg,
                                             f"mj/{jn}", is_judge=True)
                if _pairwise_winner(text) is not None:
                    break
            w = _pairwise_winner(text)
            winner = None
            if w == "tie":
                winner = "tie"
            elif w in ("a", "b"):
                winner = "cond" if (w == "a") == flip else "ref"
            async with lock:
                out.write(json.dumps({"judge": jn, "item_id": iid, "condition": cond,
                                      "winner": winner}) + "\n")
                out.flush(); done[0] += 1
                if done[0] % 200 == 0:
                    print(f"  {done[0]}/{len(tasks)}", flush=True)
        await asyncio.gather(*(run(*t) for t in tasks))
    out.close()
    print(f"wrote {a.out}")


def report(path):
    J = [json.loads(l) for l in open(path)]
    t = defaultdict(lambda: defaultdict(int))
    for j in J:
        if j.get("winner"):
            t[j["judge"]][(j["condition"], j["winner"])] += 1
    print("\nPF win rate by judge (ranking must be stable; absolute rates need not be)")
    print(f"  {'judge':12s}" + "".join(f"{c:>16s}" for c in ("none","personahub","synthpai")))
    for jn in sorted(t):
        line = f"  {jn:12s}"
        for c in ("none", "personahub", "synthpai"):
            r, cd, ti = t[jn][(c,"ref")], t[jn][(c,"cond")], t[jn][(c,"tie")]
            n = r+cd+ti
            line += f"{100*r/n:14.1f}% " if n else f"{'-':>16s}"
        print(line)
    # item-level agreement with MiniMax
    per = defaultdict(dict)
    for j in J:
        if j.get("winner"):
            per[(j["item_id"], j["condition"])][j["judge"]] = j["winner"]
    base = "minimax"
    print("\nitem-level agreement with minimax")
    others = sorted({j["judge"] for j in J} - {base})
    for o in others:
        both = [(v[base], v[o]) for v in per.values() if base in v and o in v]
        if both:
            agr = sum(1 for x, y in both if x == y) / len(both)
            print(f"  {base} vs {o:10s} {agr:.3f}   n={len(both)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--generations", default="./outputs/format_comparison/generations.jsonl")
    ap.add_argument("--items", default="./outputs/format_comparison/items.jsonl")
    ap.add_argument("--config", default="evaluation/format_comparison/config.yaml")
    ap.add_argument("--out", default="./outputs/format_comparison/multi_judge.jsonl")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--judges", default="minimax,gemma,ministral,glm")
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args()
    if not a.report_only:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        asyncio.run(main_async(a, yaml.safe_load(open(a.config))))
    report(a.out)
