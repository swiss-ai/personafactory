#!/usr/bin/env python
"""Render one PersonaFactory persona into each condition's persona block.

Every condition fills the same two slots of ADAPT_USER_PROMPT_TEMPLATE /
PERSONA_SYSTEM_PROMPT_TEMPLATE -- {background} and {writing_style} -- so the prompt
scaffold, rewriter, decoding params and judge are identical across conditions and the
persona representation is the only thing that varies.

  C0 none            background "(not specified)"          style "(not specified)"
  C1 personahub      one flat sentence, third person       style "(not specified)"
  C2 synthpai        shared-schema attribute JSON          style flat prose + example
  C3 personafactory  native structured background          style native structured block

C1 is deliberately style-free: PersonaHub's released personas mention any writing cue in
1.4% of cases (measured over all 200,000), so a projection that described writing behaviour
would not be testing PersonaHub. C2 keeps only the feature types SynthPAI's schema has.

Run `python -m personafactory.evaluation.format_comparison.renderers <persona.json | bank.jsonl> [persona_id]` to print all four
renderings of one persona.
"""
from __future__ import annotations

import json
import sys

from personafactory.augmentation.pipeline import get_persona_background_str, get_persona_style_str

CONDITIONS = ["none", "personahub", "synthpai", "personafactory"]
UNSPEC = "(not specified)"

# SynthPAI's profile schema. Fields it has that we cannot fill from a PF persona are
# listed so they are omitted deliberately rather than invented.
SYNTHPAI_FIELDS = ["age", "sex", "city_country", "birth_city_country", "education",
                   "occupation", "income", "income_level", "relationship_status"]
SYNTHPAI_UNFILLABLE = ["birth_city_country", "income", "income_level", "relationship_status"]


def _synthpai_attributes(p: dict) -> dict:
    """Project a PF background onto the feature types SynthPAI's schema shares with it."""
    bg = p.get("background") or {}
    edu = bg.get("education") or {}
    loc = ", ".join(x for x in [bg.get("sub_region"), bg.get("country")] if x)
    level, field = edu.get("level"), edu.get("field_of_study")
    out = {
        "age": bg.get("age"),
        "sex": (bg.get("gender") or "").lower() or None,
        "city_country": loc or None,
        "education": f"{level} in {field}" if level and field else (level or None),
        "occupation": (bg.get("occupation") or "").lower() or None,
    }
    return {k: v for k, v in out.items() if v not in (None, "")}


def _synthpai_style(p: dict, include_example: bool = True) -> str:
    """SynthPAI's style slot: flat prose plus a verbatim example, no per-axis structure."""
    st = p.get("style") or {}
    flat = (st.get("chatting_style") or "").strip()
    parts = [f"Writing style: {flat}"] if flat else []
    ex = (st.get("example_message") or "").strip()
    if include_example and ex:
        parts.append(f"Example: {ex}")
    return "\n\n".join(parts) if parts else UNSPEC


def _personahub_heuristic(p: dict) -> str:
    """Deterministic stand-in for the LLM projection.

    For dry runs and unit tests only. The real C1 sentences come from
    build_projections.py, which matches PersonaHub's length and style-mention rates.
    """
    bg = p.get("background") or {}
    job = (bg.get("job_title") or bg.get("occupation") or "person").strip()
    job = job.split(",")[0].split(" at ")[0].strip()
    hobbies = bg.get("hobbies_interests") or []
    tail = ""
    if hobbies:
        h = str(hobbies[0]).split("(")[0].strip().rstrip(".")
        tail = f" who is interested in {h}"
    art = "An" if job[:1].lower() in "aeiou" else "A"
    return f"{art} {job}{tail}."


def render(persona: dict, condition: str, projections: dict | None = None,
           synthpai_example: bool = True) -> tuple[str, str]:
    """Return (background_block, writing_style_block) for one persona under one condition."""
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}; expected one of {CONDITIONS}")

    if condition == "none":
        return UNSPEC, UNSPEC

    if condition == "personahub":
        pid = persona.get("id")
        sent = (projections or {}).get(pid)
        if not sent:
            sent = _personahub_heuristic(persona)
        # PersonaHub carries no writing-behaviour information: that is the condition.
        return sent.strip(), UNSPEC

    if condition == "synthpai":
        attrs = _synthpai_attributes(persona)
        return json.dumps(attrs, ensure_ascii=False, indent=2), _synthpai_style(
            persona, include_example=synthpai_example)

    # personafactory: the native blocks, exactly as the production pipeline builds them
    return (get_persona_background_str(persona),
            get_persona_style_str(persona, include_quirks=True, style_mode="both"))


def budget(persona: dict, condition: str, projections: dict | None = None) -> int:
    bgs, sts = render(persona, condition, projections)
    words = 0
    for blk in (bgs, sts):
        if blk and blk != UNSPEC:
            words += len(blk.split())
    return words


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        sys.exit("usage: python -m personafactory.evaluation.format_comparison.renderers <persona.json | bank.jsonl> [persona_id]")
    if path.endswith(".jsonl"):
        want = sys.argv[2] if len(sys.argv) > 2 else None
        persona = None
        for line in open(path):
            r = json.loads(line)
            if want is None or r.get("id") == want:
                persona = r
                break
    else:
        persona = json.load(open(path))
    for c in CONDITIONS:
        bgs, sts = render(persona, c)
        print("=" * 86)
        print(f"CONDITION: {c}   [{budget(persona, c)} words]")
        print("-" * 86)
        print("background:\n" + bgs)
        print("\nwriting_style:\n" + sts)
