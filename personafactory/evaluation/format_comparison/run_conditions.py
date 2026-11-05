#!/usr/bin/env python
"""Generate, for every item x condition: the rewritten user turn and the assistant reply.

The rewriter, decoding params, judge and prompt scaffold are identical across conditions.
Only {background} and {writing_style} differ, which is the whole design.

Resumable: completed (item_id, condition) pairs are read back from the output file and
skipped, so a preempted job can be relaunched with the same command.

Inputs:  --items, --projections (build_projections.py output), --config (rewriter endpoints, decoding)
Outputs: --out generations JSONL (item_id, condition, rewrite, assistant, persona_block_words, ...)
Run:     python -m personafactory.evaluation.format_comparison.run_conditions --items ./outputs/format_comparison/items.jsonl \
             --projections ./outputs/format_comparison/projections_personahub.json \
             --config evaluation/format_comparison/config.yaml --responder gemma \
             --out ./outputs/format_comparison/generations.jsonl
         (the Ministral robustness run: --responder ministral --out .../generations_ministral.jsonl)
"""
from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import os
import random
import sys
import time

import aiohttp
import yaml

from personafactory.augmentation.pipeline import call_api
from personafactory.augmentation.prompts import ADAPT_USER_PROMPT_TEMPLATE, PERSONA_SYSTEM_PROMPT_TEMPLATE
from personafactory.evaluation.format_comparison import renderers


def done_keys(path: str) -> set:
    keys = set()
    if os.path.exists(path):
        with open(path) as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                keys.add((r.get("item_id"), r.get("condition")))
    return keys


async def one_unit(session, item, cond, projections, rw_pool, gen_rw, gen_rs, quirks_instr):
    """Rewrite the seed prompt under `cond`, then answer it under the same persona block."""
    persona = item["persona"]
    bg_block, style_block = renderers.render(persona, cond, projections)

    # Round-robin the rewriter endpoints; the model is identical across conditions.
    api = next(rw_pool)

    t0 = time.time()
    if cond == "none":
        # Neutral rewrite: same instruction, no persona. This is the control for
        # "did conditioning change anything at all", so it must be generated, not copied.
        adapt = ADAPT_USER_PROMPT_TEMPLATE.format(
            background=renderers.UNSPEC, writing_style=renderers.UNSPEC,
            user_message=item["seed_prompt"], verbal_quirks_instruction="")
    else:
        adapt = ADAPT_USER_PROMPT_TEMPLATE.format(
            background=bg_block, writing_style=style_block,
            user_message=item["seed_prompt"], verbal_quirks_instruction=quirks_instr)

    rewrite, err1 = await call_api(session, api, gen_rw,
                                   [{"role": "user", "content": adapt}], f"rewrite/{cond}")
    rewrite = (rewrite or "").strip()

    reply = None
    err2 = None
    if rewrite:
        sys_prompt = PERSONA_SYSTEM_PROMPT_TEMPLATE.format(
            background=bg_block, writing_style=style_block)
        reply, err2 = await call_api(
            session, api, gen_rs,
            [{"role": "system", "content": sys_prompt},
             {"role": "user", "content": rewrite}], f"respond/{cond}")

    return {
        "item_id": item["item_id"],
        "condition": cond,
        "stratum": item["stratum"],
        "persona_id": item["persona_id"],
        "seed_prompt": item["seed_prompt"],
        "rewrite": rewrite,
        "assistant": (reply or "").strip(),
        "persona_block_words": renderers.budget(persona, cond, projections),
        "rewriter_model": api["model"],
        "errors": [e for e in (err1, err2) if e],
        "latency_s": round(time.time() - t0, 2),
        "corpus_sanity_pass": item.get("corpus_sanity_pass"),
    }


async def main_async(args, cfg):
    items = [json.loads(l) for l in open(args.items)]
    if args.limit:
        items = items[: args.limit]
    projections = {}
    if os.path.exists(args.projections):
        projections = json.load(open(args.projections))
    else:
        print(f"WARNING: {args.projections} missing -- C1 will fall back to the "
              f"heuristic sentence, which is for dry runs only.")

    conds = args.conditions.split(",") if args.conditions else renderers.CONDITIONS
    pool_all = cfg["responders"]
    if args.responder:
        pool_all = [r for r in pool_all if r.get("name") == args.responder]
        if not pool_all:
            raise SystemExit(f"no responder named {args.responder!r} in config")
    names = sorted({r.get("name") for r in pool_all})
    print(f"rewriter/responder: {names} over {len(pool_all)} endpoint(s)")
    rw_pool = itertools.cycle(pool_all)
    gen_rw, gen_rs = cfg["rewrite_gen"], cfg["respond_gen"]
    quirks_instr = cfg.get("verbal_quirks_instruction", "")

    todo = [(it, c) for it in items for c in conds]
    have = done_keys(args.out)
    todo = [(it, c) for it, c in todo if (it["item_id"], c) not in have]
    print(f"{len(items)} items x {len(conds)} conditions; {len(have)} already done; "
          f"{len(todo)} to run")

    sem = asyncio.Semaphore(cfg.get("concurrency", 32))
    lock = asyncio.Lock()
    n_done = [0]
    out = open(args.out, "a")

    async with aiohttp.ClientSession() as session:
        async def worker(it, c):
            async with sem:
                try:
                    rec = await one_unit(session, it, c, projections, rw_pool,
                                         gen_rw, gen_rs, quirks_instr)
                except Exception as e:                      # keep the run alive
                    rec = {"item_id": it["item_id"], "condition": c,
                           "errors": [f"{type(e).__name__}: {e}"],
                           "rewrite": "", "assistant": ""}
                async with lock:
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    out.flush()
                    n_done[0] += 1
                    if n_done[0] % 50 == 0:
                        print(f"  {n_done[0]}/{len(todo)}", flush=True)

        await asyncio.gather(*(worker(it, c) for it, c in todo))
    out.close()
    print(f"done -> {args.out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="./outputs/format_comparison/items.jsonl")
    ap.add_argument("--projections", default="./outputs/format_comparison/projections_personahub.json")
    ap.add_argument("--config", default="evaluation/format_comparison/config.yaml")
    ap.add_argument("--out", default="./outputs/format_comparison/generations.jsonl")
    ap.add_argument("--conditions", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--responder", default="",
                    help="restrict to one responder family, e.g. gemma or ministral; "
                         "the rewriter must be fixed within a run or conditions are confounded")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    random.seed(cfg.get("seed", 20260901))
    asyncio.run(main_async(args, cfg))


if __name__ == "__main__":
    main()
