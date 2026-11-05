#!/usr/bin/env python
"""Score every generation: judge-free heuristics, style-axis adherence, assistant-side
effects, and LLM-judge verdicts.

The important asymmetry: style-axis adherence is scored against the persona's TRUE
declared axes, whether or not the condition exposed them to the rewriter. That is the
point -- C1 is never shown the axes, and we measure how far the rewrite lands from them
anyway.

Inputs:  --generations (run_conditions.py output), --items, --config (judge endpoints, decoding)
Outputs: --out-metrics JSONL (judge-free, per item x condition), --out-judge JSONL (pairwise / style / intent /
         sanity verdicts; appended)
Run:     python -m personafactory.evaluation.format_comparison.score_conditions --generations ./outputs/format_comparison/generations.jsonl \
             --items ./outputs/format_comparison/items.jsonl --config evaluation/format_comparison/config.yaml \
             --out-metrics ./outputs/format_comparison/metrics.jsonl --out-judge ./outputs/format_comparison/judgments.jsonl
"""
from __future__ import annotations

import argparse, asyncio, itertools, json, os, random, re, statistics, sys, unicodedata
from collections import defaultdict

import aiohttp, yaml

from personafactory.augmentation.pipeline import call_api
from personafactory.augmentation.prompts import (VALIDATE_PERSONA_STYLE_TEMPLATE, VALIDATE_PERSONA_INTENT_TEMPLATE,
                                  SANITY_VERIFICATION_TEMPLATE)
from personafactory.evaluation.structured_vs_flat.prompts import PAIRWISE
from personafactory.evaluation.format_comparison import renderers
# The corpus-scale fidelity metric definitions, so these numbers sit on the same scale as the corpus table.
from personafactory.evaluation.format_comparison.chat_metrics import (
    compute_lexical_metrics, compute_entity_retention,
    normalise_cap, normalise_punct, normalise_emoji,
    evaluate_capitalization, evaluate_punctuation, evaluate_emoji)

EMOJI_RE = re.compile("[" "\U0001F300-\U0001FAFF" "\U00002600-\U000027BF" "]")
WORD_RE = re.compile(r"\w+", re.UNICODE)


# ------------------------------------------------------- judge-free metrics (reference)
def dominant_script(s):
    """Cheap language proxy; the reference module handles the rest."""
    counts = defaultdict(int)
    for ch in s or "":
        if not ch.isalpha():
            continue
        try:
            counts[unicodedata.name(ch).split()[0]] += 1
        except ValueError:
            pass
    return max(counts, key=counts.get) if counts else None


def style_axis_hits(persona, text):
    """Register adherence against the persona's TRUE declared axes, using the paper's
    own normalisers and evaluators -- whether or not the condition exposed them."""
    cs = ((persona.get("style") or {}).get("chatting_style_structured") or {})
    out = {}
    for key, norm, ev in (("capitalization", normalise_cap, evaluate_capitalization),
                          ("punctuation", normalise_punct, evaluate_punctuation),
                          ("emoji_use", normalise_emoji, evaluate_emoji)):
        raw = cs.get(key) or ""
        if not raw:
            continue
        target = norm(raw)
        verdict = ev(text, target)          # None when the target is unmarked/other
        if verdict is not None:
            out[{"capitalization": "cap_adherence",
                 "punctuation": "punct_adherence",
                 "emoji_use": "emoji_adherence"}[key]] = 1.0 if verdict else 0.0
    return out


def score_row(rec, persona, c0_map):
    seed = rec.get("seed_prompt", "")
    rew = rec.get("rewrite", "")
    asst = rec.get("assistant", "")

    m = {}
    m.update(compute_lexical_metrics(seed, rew))        # jaccard, core-vocab, norm-lev
    m.update(compute_entity_retention(seed, rew))       # numbers / code / quotes / entities
    m.update(style_axis_hits(persona, rew))             # cap / punct / emoji adherence

    m["length_ratio"] = len(rew) / max(1, len(seed))
    m["script_match_seed"] = dominant_script(rew) == dominant_script(seed)

    # assistant side
    m["asst_words"] = len(re.findall(r"\w+", asst, re.UNICODE))
    m["asst_sent_len"] = m["asst_words"] / max(1, len(re.findall(r"[.!?]+", asst)))
    m["asst_script_match_user"] = dominant_script(asst) == dominant_script(rew)

    # distance from the no-persona control; LaBSE is filled in by the GPU pass
    base = c0_map.get(rec["item_id"])
    if base:
        m["rewrite_lex_dist_from_none"] = compute_lexical_metrics(
            base.get("rewrite", ""), rew).get("jaccard_distance")
        m["asst_lex_dist_from_none"] = compute_lexical_metrics(
            base.get("assistant", ""), asst).get("jaccard_distance")
        m["asst_len_ratio_vs_none"] = (
            len(asst) / max(1, len(base.get("assistant", "") or "")))
    return m


def _greedy_json(text):
    """First '{' to LAST '}' -- MiniMax prepends a think block that itself contains
    braces, so a non-greedy match grabs the wrong span."""
    if not text:
        return None
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b <= a:
        return None
    try:
        return json.loads(text[a:b + 1])
    except Exception:
        return None


def _json_verdict(text):
    """The validated templates return {"verdict": "pass"|"fail", ...}."""
    d = _greedy_json(text)
    if isinstance(d, dict) and "verdict" in d:
        return str(d["verdict"]).strip().lower() == "pass"
    # the templates warn that `reason` may carry unescaped quotes and break json.loads,
    # so fall back to reading the verdict field directly
    m = re.findall(r'"verdict"\s*:\s*"?(pass|fail)"?', text or "", re.I)
    return m[-1].lower() == "pass" if m else None


def _pairwise_winner(text):
    """Return 'a' / 'b' / 'tie' / None from the PAIRWISE judge response."""
    d = _greedy_json(text)
    if isinstance(d, dict) and str(d.get("winner", "")).strip().lower() in ("a", "b", "tie"):
        return str(d["winner"]).strip().lower()
    m = re.findall(r'"winner"\s*:\s*"?(A|B|tie)"?', text or "", re.I)
    return m[-1].lower() if m else None


async def judge_all(rows, personas, cfg, out_path, reference="personafactory"):
    """Four judge families, all reusing the production templates so the numbers are
    directly comparable to the paper:

      pairwise  structured_vs_flat PAIRWISE        -- the pairwise judge of the structured vs flat A/B
      style     VALIDATE_PERSONA_STYLE_TEMPLATE    -- per-rewrite style adoption
      intent    VALIDATE_PERSONA_INTENT_TEMPLATE   -- per-rewrite intent preservation
      sanity    SANITY_VERIFICATION_TEMPLATE       -- the sanity gate, on the assistant turn
    """
    # Round-robin across every judge endpoint. Without this, extra MiniMax nodes are
    # simply idle: judging is the only stage that scales with fleet size.
    jcfg = cfg["judge"]
    urls = jcfg.get("base_urls") or [jcfg["base_url"]]
    pool = itertools.cycle([{**jcfg, "base_url": u} for u in urls])
    gen = cfg["judge_gen"]
    print(f"judging across {len(urls)} MiniMax endpoint(s)")
    rng = random.Random(cfg.get("seed", 20260901))
    by_item = defaultdict(dict)
    for r in rows:
        by_item[r["item_id"]][r["condition"]] = r

    tasks = []
    for item_id, conds in by_item.items():
        ref = conds.get(reference)
        if not ref or not ref.get("rewrite"):
            continue
        p = personas.get(ref["persona_id"])
        if not p:
            continue
        # The judge always sees the persona's FULL true background and style, whichever
        # condition produced the rewrite. Anything else would ask it to grade against a
        # target it cannot see.
        bg_true, style_true = renderers.render(p, "personafactory")

        for cond, r in conds.items():
            if not r.get("rewrite"):
                continue
            if cond != reference:
                flip = rng.random() < 0.5
                a, b = (r, ref) if flip else (ref, r)
                tasks.append(("pairwise", item_id, cond, flip, PAIRWISE.format(
                    background=bg_true, style=style_true,
                    original=ref["seed_prompt"], a=a["rewrite"], b=b["rewrite"])))
            tasks.append(("style", item_id, cond, None,
                          VALIDATE_PERSONA_STYLE_TEMPLATE.format(
                              background=bg_true, writing_style=style_true,
                              rewritten_message=r["rewrite"])))
            tasks.append(("intent", item_id, cond, None,
                          VALIDATE_PERSONA_INTENT_TEMPLATE.format(
                              original_message=r["seed_prompt"],
                              rewritten_message=r["rewrite"])))
            if r.get("assistant"):
                tasks.append(("sanity", item_id, cond, None,
                              SANITY_VERIFICATION_TEMPLATE.format(
                                  context="(single-turn)", user_message=r["rewrite"],
                                  response=r["assistant"])))

    print(f"{len(tasks)} judge calls "
          f"(pairwise + style + intent + sanity, production templates)")
    sem = asyncio.Semaphore(cfg.get("concurrency", 32))
    lock = asyncio.Lock(); fh = open(out_path, "a"); n = [0]

    async with aiohttp.ClientSession() as session:
        def _parsed(kind, text):
            return (_pairwise_winner(text) if kind == "pairwise"
                    else _json_verdict(text))

        async def run(kind, item_id, cond, flip, prompt):
            msg = [{"role": "user", "content": prompt}]
            async with sem:
                text, err = await call_api(session, next(pool), gen, msg,
                                           f"judge/{kind}", is_judge=True)
            # MiniMax sometimes degenerates into a repetition loop and never reaches the
            # JSON. These failures are not uniform across conditions: in an early
            # test they hit synthpai (16%) four times as often as personahub (4%),
            # because near-tie comparisons make the judge deliberate longer. Silently
            # dropping them would bias the very comparison the paper rests on, so retry
            # with escalating temperature until a verdict is read.
            attempts = 0
            for temp in (0.4, 0.7, 1.0):
                if _parsed(kind, text) is not None:
                    break
                attempts += 1
                retry_gen = dict(gen); retry_gen["temperature"] = temp
                async with sem:
                    text2, err2 = await call_api(session, next(pool), retry_gen, msg,
                                                 f"judge/{kind}/retry{attempts}",
                                                 is_judge=True)
                if _parsed(kind, text2) is not None:
                    text, err = text2, err2
                    break
            rec = {"kind": kind, "item_id": item_id, "condition": cond,
                   "error": err, "retries": attempts}
            if kind == "pairwise":
                w = _pairwise_winner(text)
                if w == "tie":
                    rec["winner"] = "tie"
                elif w in ("a", "b"):
                    chose_first = (w == "a")
                    rec["winner"] = "cond" if chose_first == flip else "ref"
                else:
                    rec["winner"] = None          # unparsed; excluded from the tally
                    rec["raw"] = (text or "")[-400:]
            else:
                v = _json_verdict(text)
                rec[{"style": "style_ok", "intent": "intent_ok",
                     "sanity": "sanity_ok"}[kind]] = v
                if v is None:
                    rec["raw"] = (text or "")[-400:]
            async with lock:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n"); fh.flush()
                n[0] += 1
                if n[0] % 200 == 0:
                    print(f"  judged {n[0]}/{len(tasks)}", flush=True)

        await asyncio.gather(*(run(*t) for t in tasks))
    fh.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--generations", default="./outputs/format_comparison/generations.jsonl")
    ap.add_argument("--items", default="./outputs/format_comparison/items.jsonl")
    ap.add_argument("--config", default="evaluation/format_comparison/config.yaml")
    ap.add_argument("--out-metrics", default="./outputs/format_comparison/metrics.jsonl")
    ap.add_argument("--out-judge", default="./outputs/format_comparison/judgments.jsonl")
    ap.add_argument("--skip-judge", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    for p in (args.out_metrics, args.out_judge):
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    personas = {}
    for l in open(args.items):
        it = json.loads(l); personas[it["persona_id"]] = it["persona"]
    rows = [json.loads(l) for l in open(args.generations)]
    rows = [r for r in rows if r.get("rewrite") is not None]
    c0 = {r["item_id"]: r for r in rows if r["condition"] == "none"}

    with open(args.out_metrics, "w") as fh:
        for r in rows:
            p = personas.get(r.get("persona_id"))
            if not p: continue
            m = score_row(r, p, c0)
            m.update({"item_id": r["item_id"], "condition": r["condition"],
                      "stratum": r.get("stratum"), "persona_id": r["persona_id"],
                      "persona_block_words": r.get("persona_block_words")})
            fh.write(json.dumps(m, ensure_ascii=False) + "\n")
    print(f"wrote heuristics -> {args.out_metrics}")

    if not args.skip_judge:
        asyncio.run(judge_all(rows, personas, cfg, args.out_judge))
        print(f"wrote judgments -> {args.out_judge}")


if __name__ == "__main__":
    main()
