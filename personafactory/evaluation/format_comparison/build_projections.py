#!/usr/bin/env python
"""Build the C1 (PersonaHub) one-sentence projections, then run the fairness gates.

The projection model must be neither the rewriter nor the judge, so no model scores its
own output. Default is GLM-4.7-Flash.

Gates, all run before any augmentation:
  G1 length      projected sentences match PersonaHub's real word-count distribution (KS)
  G2 style rate  projections mention writing behaviour at PersonaHub's real 1.4% rate,
                 not more -- a projection that described style would not be PersonaHub
  G3 recall      attribute recall per rendering, the mediator reported in the paper

G1 and G2 are hard gates. G3 is measurement, not pass/fail: it quantifies what each format
retains (the attribute-presence table of the format comparison).

Inputs:  --items (sample_items.py output), --config (projector endpoint), --personahub (real PersonaHub
         persona.jsonl, see README for how to obtain it)
Outputs: --out JSON {persona_id: sentence}; exit code 1 if a hard gate fails
Run:     python -m personafactory.evaluation.format_comparison.build_projections --items ./outputs/format_comparison/items.jsonl \
             --config evaluation/format_comparison/config.yaml --personahub ./data/personahub/persona.jsonl \
             --out ./outputs/format_comparison/projections_personahub.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys

import aiohttp

from personafactory.augmentation.pipeline import call_api
from personafactory.evaluation.format_comparison import renderers

PERSONAHUB_REAL = "./data/personahub/persona.jsonl"

# Mirrors PersonaHub's observed form: third person, one sentence, occupation/interest only.
PROJECT_PROMPT = """You rewrite a detailed user profile into the terse persona format used by the PersonaHub dataset.

PersonaHub personas are ONE sentence, third person, typically 12-20 words (most often about 14), beginning with "A" or "An".
They describe WHO someone is: their role, occupation, or a defining interest.
They almost never describe HOW the person writes or types.

Rules:
1. Output exactly one sentence of 12-20 words, aiming for about 14, starting with "A" or "An".
2. Describe the role or occupation, plus one or two defining interests, concerns or specialisms.
3. Do NOT mention writing style, typing habits, punctuation, emoji, capitalization, tone or language use.
4. Do NOT invent facts that are not in the profile.
5. Output the sentence only, with no preamble, quotes or explanation.

Profile:
{profile}

PersonaHub-style persona:"""

STYLE_WORDS = re.compile(
    r"\b(writes?|writing|types?|typing|style|tone|punctuation|emoji|capitali[sz]|"
    r"abbrevia|slang|lowercase|uppercase|grammar|phras(e|ing)|voice|register|"
    r"speaks? in|communicat)\w*", re.I)


def profile_summary(p: dict) -> str:
    """Compact, faithful input for the projector: background facts only, no style layer."""
    bg = p.get("background") or {}
    edu = bg.get("education") or {}
    hob = bg.get("hobbies_interests") or []
    lines = [
        f"Age: {bg.get('age')}, Gender: {bg.get('gender')}",
        f"Occupation: {bg.get('occupation')} ({bg.get('job_title')})",
        f"Location: {bg.get('sub_region')}, {bg.get('country')}",
        f"Education: {edu.get('level')} in {edu.get('field_of_study')}",
        f"Interests: {', '.join(str(h) for h in hob[:4])}",
    ]
    return "\n".join(l for l in lines if "None" not in l or ":" in l)


async def project_all(personas: list[dict], api: dict, gen: dict,
                      concurrency: int = 16) -> dict:
    out: dict[str, str] = {}
    sem = asyncio.Semaphore(concurrency)

    async with aiohttp.ClientSession() as session:
        async def one(p: dict) -> None:
            async with sem:
                msg = [{"role": "user",
                        "content": PROJECT_PROMPT.format(profile=profile_summary(p))}]
                text, err = await call_api(session, api, gen, msg, "project")
                if err or not text:
                    print(f"  ! {p.get('id')}: {err}")
                    return
                s = text.strip().strip('"').split("\n")[0].strip()
                out[p["id"]] = s

        await asyncio.gather(*(one(p) for p in personas))
    return out


def gate_length(proj: dict) -> bool:
    from scipy import stats
    real = [len(json.loads(l)["persona"].split()) for l in open(PERSONAHUB_REAL)]
    ours = [len(v.split()) for v in proj.values()]
    ks = stats.ks_2samp(ours, real)
    import statistics
    print(f"G1 length  ours median {statistics.median(ours):.1f} "
          f"vs real {statistics.median(real):.1f} | KS D={ks.statistic:.3f} p={ks.pvalue:.3g}")
    ok = abs(statistics.median(ours) - statistics.median(real)) <= 2
    print(f"   -> {'PASS' if ok else 'FAIL'} (median within 2 words of the real corpus)")
    return ok


def gate_style_rate(proj: dict) -> bool:
    real_rate = 0.014  # measured over all 200,000 PersonaHub core personas
    hits = sum(1 for v in proj.values() if STYLE_WORDS.search(v))
    rate = hits / max(1, len(proj))
    print(f"G2 style-mention rate {rate*100:.1f}% (real PersonaHub {real_rate*100:.1f}%)")
    ok = rate <= 0.05
    print(f"   -> {'PASS' if ok else 'FAIL'} (must stay at/near the real rate; "
          f"describing style would not be PersonaHub)")
    return ok


def gate_recall(personas: list[dict], proj: dict) -> None:
    """Mediator: which attribute families each rendering still carries, by construction."""
    fams = {
        "age": lambda p: [str((p.get('background') or {}).get('age'))],
        "location": lambda p: [str((p.get('background') or {}).get('country'))],
        "occupation": lambda p: [str((p.get('background') or {}).get('occupation'))],
        "language": lambda p: [str((p.get('background') or {}).get('main_language'))],
        "style axes": lambda p: list(((p.get('style') or {})
                                      .get('chatting_style_structured') or {}).values()),
        "quirks": lambda p: list((p.get('style') or {}).get('linguistic_quirks') or []),
        "reference pool": lambda p: list((p.get('style') or {}).get('reference_pool') or []),
    }
    print("\nG3 attribute presence per rendering (share of personas whose value appears):")
    header = f"  {'family':16s}" + "".join(f"{c:>16s}" for c in renderers.CONDITIONS)
    print(header)
    for fam, get in fams.items():
        row = f"  {fam:16s}"
        for cond in renderers.CONDITIONS:
            hit = 0
            for p in personas:
                bgs, sts = renderers.render(p, cond, proj)
                blob = f"{bgs}\n{sts}".lower()
                vals = [v for v in get(p) if v and v != "None"]
                if vals and any(str(v).lower()[:40] in blob for v in vals):
                    hit += 1
            row += f"{100*hit/max(1,len(personas)):15.0f}%"
        print(row)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="./outputs/format_comparison/items.jsonl")
    ap.add_argument("--out", default="./outputs/format_comparison/projections_personahub.json")
    ap.add_argument("--config", default="evaluation/format_comparison/config.yaml")
    ap.add_argument("--personahub", default="./data/personahub/persona.jsonl",
                    help="real PersonaHub persona.jsonl (one {'persona': ...} per line)")
    ap.add_argument("--gates-only", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    global PERSONAHUB_REAL
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    PERSONAHUB_REAL = args.personahub

    personas, seen = [], set()
    for line in open(args.items):
        it = json.loads(line)
        if it["persona_id"] in seen:
            continue
        seen.add(it["persona_id"])
        personas.append(it["persona"])
    if args.limit:
        personas = personas[: args.limit]
    print(f"{len(personas)} distinct personas to project")

    if args.gates_only:
        proj = json.load(open(args.out))
    else:
        import yaml
        cfg = yaml.safe_load(open(args.config))
        api = cfg["projector"]
        gen = cfg["projector_gen"]
        proj = asyncio.run(project_all(personas, api, gen,
                                       cfg.get("concurrency", 16)))
        json.dump(proj, open(args.out, "w"), ensure_ascii=False, indent=1)
        print(f"wrote {len(proj)} projections -> {args.out}")

    print()
    ok1, ok2 = gate_length(proj), gate_style_rate(proj)
    gate_recall(personas[:200], proj)
    print("\nHARD GATES:", "PASS" if (ok1 and ok2) else "FAIL -- fix the prompt and re-run")
    sys.exit(0 if (ok1 and ok2) else 1)


if __name__ == "__main__":
    main()
