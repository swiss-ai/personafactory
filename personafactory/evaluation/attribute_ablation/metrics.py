"""Scoring functions for the per-attribute ablation.

The two LLM judges reuse the production templates and API helper of the pipeline, so the ablation uses the same
evaluation path as the corpus:
  score_style(...)             -> 1.0 (pass) / 0.0 (fail)  [LLM judge]
  score_intent(...)            -> 1.0 (pass) / 0.0 (fail)  [LLM judge]
  score_script_stability(...)  -> 1.0 (same script) / 0.0  [detect_script, no LLM call]
"""
from personafactory.augmentation.pipeline import (detect_script, parse_judge_response, call_api, should_skip_persona,
                                   get_persona_background_str, get_persona_style_str)
from personafactory.augmentation.prompts import VALIDATE_PERSONA_STYLE_TEMPLATE, VALIDATE_PERSONA_INTENT_TEMPLATE


async def score_style(session, model_config, judge_gen_config, adapted_message, condition_persona):
    """Judge whether `adapted_message` reflects the persona's style. Returns 1.0 / 0.0, or None for the baseline
    (no persona) and for unparsed verdicts."""
    if condition_persona is None:
        return None
    prompt = VALIDATE_PERSONA_STYLE_TEMPLATE.format(
        background=get_persona_background_str(condition_persona),
        writing_style=get_persona_style_str(condition_persona),
        rewritten_message=adapted_message,
    )
    response_text, error = await call_api(
        session, model_config, judge_gen_config, [{"role": "user", "content": prompt}],
        error_prefix="STYLE_JUDGE", is_judge=True,
    )
    if error or not response_text:
        return None
    verdict, _ = parse_judge_response(response_text)
    if verdict == "pass":
        return 1.0
    elif verdict == "fail":
        return 0.0
    return None  # parse error


async def score_intent(session, model_config, judge_gen_config, original_message, adapted_message):
    """Judge whether `adapted_message` preserves the intent of `original_message`. Returns 1.0 / 0.0 / None."""
    prompt = VALIDATE_PERSONA_INTENT_TEMPLATE.format(
        original_message=original_message,
        rewritten_message=adapted_message,
    )
    response_text, error = await call_api(
        session, model_config, judge_gen_config, [{"role": "user", "content": prompt}],
        error_prefix="INTENT_JUDGE", is_judge=True,
    )
    if error or not response_text:
        return None
    verdict, _ = parse_judge_response(response_text)
    if verdict == "pass":
        return 1.0
    elif verdict == "fail":
        return 0.0
    return None


def score_script_stability(original_message, response):
    """1.0 if the dominant Unicode script of `response` matches that of `original_message`, else 0.0.

    'unknown' or 'mixed' on either side counts as stable (insufficient signal); verbatim / format-strict prompts
    that the pipeline never restyles count as stable.
    """
    if should_skip_persona(original_message):
        return 1.0
    orig_script = detect_script(original_message)
    resp_script = detect_script(response)
    if orig_script in ("unknown", "mixed") or resp_script in ("unknown", "mixed"):
        return 1.0
    return 1.0 if orig_script == resp_script else 0.0
