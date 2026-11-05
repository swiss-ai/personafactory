"""Judge prompts for the structured vs flat style A/B.

PAIRWISE_FIRST_PASS and INTENT are the prompts of the original pass (ab_style_test.py). PAIRWISE is the pairwise
prompt used for every re-judging of the stored pairs (re_judge_ab.py, ab_rejudge.py) and by the persona-format
comparison (evaluation/format_comparison).
"""

PAIRWISE_FIRST_PASS = """You are judging which of two rewrites better captures a specific person's writing style.

Persona background:
{background}
Persona writing style:
{style}

Original message: {original}

Rewrite A: {a}
Rewrite B: {b}

Which rewrite better reflects THIS persona's writing style — capitalization, punctuation,
emoji, abbreviations, typos, sentence rhythm, code-switching — while keeping the original
request fully intact? If they are genuinely equal, answer "tie".
Respond ONLY with JSON: {{"winner": "A" or "B" or "tie", "reason": "one short sentence"}}"""

INTENT = """Does the rewritten message ask for the SAME thing as the original (same request,
same constraints, same language)? Ignore style differences.
Original: {original}
Rewrite: {rewrite}
Respond ONLY with JSON: {{"verdict": "pass" or "fail"}}"""

PAIRWISE = """You are judging which of two rewrites better captures a specific person's writing style.

Persona background:
{background}
Persona writing style:
{style}

Original message: {original}

Rewrite A: {a}
Rewrite B: {b}

Which rewrite better reflects THIS persona's writing style — capitalization, punctuation,
emoji, abbreviations, typos, sentence rhythm, code-switching — while keeping the original
request fully intact? If genuinely equal, answer "tie".
Respond ONLY with JSON: {{"winner": "A" or "B" or "tie", "reason": "one short sentence"}}"""
