"""PersonaFactory augmentation pipeline core.

process_conversation rewrites the user side of one seed conversation with a synthetic persona and
regenerates the assistant side:
  1. Persona / match tier / responder model are pre-assigned per conversation (config["_assigned"],
     computed by augmentation.select_personas), so runs are deterministic and resumable. Without an
     assignment, select_persona picks one online (language filter -> location -> embedding -> pool).
  2. Cross-lingual mode = translate, then restyle: each user turn is first translated literally into the
     persona's language (persona-blind, temperature 0.3, literal protection, target-language check), and
     that translation is then restyled by the same-language rewrite (ADAPT_USER_PROMPT_TEMPLATE).
  3. Literal protection: quoted text, code, URLs and numbers are masked with PFSPAN markers before the
     rewrite, restored after, and a rewrite that loses one is retried (augmentation.integrity).
  4. Cross-lingual restyles must still be detected in the target language (config["_lang_ok"]), else retried.
  5. The responder gets a persona system prompt (background + style), each non-final response is checked
     against the next original user turn and minimally adapted if it does not fit (continuity loop), and
     every turn passes a separate sanity judge.
Optional hooks (inactive unless the config key is present):
  _fixed          reuse previously generated user turns verbatim (no rewrite), e.g. to regenerate only
                  the assistant side;
  _model_persona  add an assistant response style (assistant.model_persona) on every turn;
  _source_system  assistant-only mode: keep the dataset's own system prompt next to the style.
"""
import sys
from personafactory.augmentation import integrity
import aiohttp
import json
import random
import os
import asyncio
import time
import re
from pathlib import Path
from datasets import load_dataset
from tqdm.asyncio import tqdm as tqdm_asyncio
from personafactory.augmentation.prompts import (ADAPT_RESPONSE_TEMPLATE, ADAPT_USER_PROMPT_TEMPLATE,
                                  JUDGE_CONSISTENCY_TEMPLATE, PERSONA_SYSTEM_PROMPT_TEMPLATE,
                                  SANITY_VERIFICATION_TEMPLATE)

# Track if we've printed the first error details (per endpoint type)
_first_responder_error_printed = False
_first_judge_error_printed = False

def sanitize_constitution(text: str) -> str:
    """Post-processing sanitizer to enforce typographic constitution rules deterministically."""
    if not text:
        return text
    # Replace em-dashes and en-dashes with standard hyphens
    text = re.sub(r'\s*[\u2014\u2013]\s*', ' - ', text)
    # Strip common assistant filler openers if present at start of text
    for opener in ["Certainly!", "Great question!", "Of course!", "Absolutely!", "Sure!"]:
        if text.startswith(opener):
            text = text[len(opener):].lstrip()
    return text

# --- Persona matching helpers ---

_LOCATION_PATTERN = re.compile(r'\b([A-Z][a-z]{2,}(?:[ -][A-Z][a-z]{2,})*)\b')
_PREP_LOCATION_PATTERN = re.compile(
    r'\b(?:in|from|to|at|near|around|of)\s+([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*)\b'
)

# Maps each dominant script to keywords expected in persona location / language fields.
# Used by _match_by_location (Signal 1: script-based country/language matching).
# Latin is intentionally omitted: it covers too many countries for useful filtering;
# text-based regex (Signal 2) is the only location signal for Latin-script messages.
_SCRIPT_COUNTRY_KEYWORDS: dict[str, frozenset] = {
    "cjk": frozenset({
        # countries / regions (Chinese-speaking)
        "china", "chinese", "taiwan", "taiwanese", "hong kong", "macau",
        "singapore",
        # major Chinese cities
        "beijing", "shanghai", "guangzhou", "shenzhen", "chengdu", "wuhan",
        "hangzhou", "nanjing", "tianjin",
        # Chinese languages/dialects
        "mandarin", "cantonese", "wu", "hokkien", "shanghainese", "sichuanese",
    }),
    "japanese": frozenset({
        # countries / regions
        "japan", "japanese",
        # major Japanese cities
        "tokyo", "osaka", "kyoto", "yokohama", "nagoya", "sapporo", "fukuoka",
    }),
    "korean": frozenset({
        "korea", "korean", "south korea", "north korea", "seoul", "busan",
        "incheon", "daegu",
    }),
    "cyrillic": frozenset({
        "russia", "russian", "ukraine", "ukrainian", "bulgaria", "bulgarian",
        "serbia", "serbian", "belarus", "belarusian", "kazakhstan",
        "macedonian", "mongolian",
        "moscow", "kyiv", "saint petersburg", "minsk", "sofia",
    }),
    "arabic": frozenset({
        "saudi arabia", "saudi", "egypt", "egyptian", "iraq", "iraqi",
        "syria", "syrian", "jordan", "jordanian", "morocco", "moroccan",
        "algeria", "algerian", "uae", "emirates", "iran", "iranian",
        "arabic", "arab", "lebanon", "lebanese", "kuwait", "kuwaiti",
        "bahrain", "qatar", "oman", "yemen", "libya", "libyan",
        "tunisia", "tunisian", "persian", "farsi",
    }),
    "devanagari": frozenset({
        "india", "indian", "nepal", "nepalese", "nepali",
        "hindi", "marathi", "bhojpuri", "sanskrit",
        "mumbai", "delhi", "kolkata", "bangalore", "chennai",
        "hyderabad", "pune", "ahmedabad", "kathmandu",
    }),
    "thai": frozenset({
        "thailand", "thai", "bangkok", "chiang mai",
    }),
    "hebrew": frozenset({
        "israel", "israeli", "hebrew", "tel aviv", "jerusalem",
    }),
    "greek": frozenset({
        "greece", "greek", "cyprus", "athens", "thessaloniki",
    }),
}
_STOP_WORDS = frozenset({
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'have', 'has', 'had', 'will',
    'would', 'should', 'may', 'might', 'can', 'could', 'shall', 'must', 'do',
    'does', 'did', 'been', 'being', 'and', 'or', 'but', 'not', 'nor', 'so',
    'for', 'yet', 'both', 'either', 'neither', 'whether', 'also', 'just',
    'how', 'what', 'when', 'where', 'who', 'which', 'why', 'that', 'this',
    'these', 'those', 'my', 'your', 'his', 'her', 'its', 'our', 'their',
    'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'us', 'them',
    'use', 'get', 'make', 'take', 'give', 'know', 'see', 'say', 'ask',
    'tell', 'come', 'go', 'look', 'want', 'need', 'like', 'help', 'work',
    'think', 'feel', 'try', 'put', 'find', 'let', 'keep', 'mean', 'call',
    'any', 'all', 'some', 'more', 'most', 'other', 'than', 'then', 'into',
    'from', 'with', 'about', 'against', 'between', 'through', 'during',
    'before', 'after', 'above', 'below', 'over', 'under', 'again', 'out',
    'off', 'much', 'very', 'such', 'own', 'same', 'few', 'new', 'old',
    'good', 'big', 'high', 'first', 'last', 'long', 'great', 'little',
    'many', 'next', 'early', 'young', 'important', 'public', 'private',
    'real', 'best', 'free', 'sure', 'even', 'still', 'since', 'while',
    'way', 'well', 'back', 'also', 'here', 'just', 'now', 'only', 'right',
    'come', 'could', 'have', 'into', 'look', 'make', 'most', 'over', 'same',
    'their', 'there', 'they', 'time', 'two', 'very', 'want', 'were', 'what',
    'when', 'will', 'with', 'year', 'your',
})


# Patterns that indicate the user wants a verbatim / format-strict response,
# where rewriting their message in a persona voice or shifting the assistant's
# register would corrupt the task.
_SKIP_PERSONA_PATTERNS = [
    re.compile(r'\b(repeat|echo)\b.{0,60}?\b(this|that|the following|after me|back|verbatim|exactly|word for word)\b', re.IGNORECASE | re.DOTALL),
    re.compile(r'\btranslate\b\s+(this|that|the following|it|the\s+\w+|to|into|from)\b', re.IGNORECASE),
    re.compile(r'\b(say|write|output|return|print)\b\s*[:\-]?\s*["\'`].+?["\'`]', re.IGNORECASE | re.DOTALL),
    re.compile(r'\bverbatim\b', re.IGNORECASE),
    re.compile(r'\bword[- ]for[- ]word\b', re.IGNORECASE),
    re.compile(r'\bspell\s+(out|check)\b', re.IGNORECASE),
]


def should_skip_persona(user_message: str) -> bool:
    """Return True if persona injection would likely corrupt the task.

    Triggers on verbatim/repeat/translate/spell-out tasks and explicit
    quoted-output instructions, where persona-induced register or dialect
    shifts would break the user's intent.
    """
    if not user_message or not user_message.strip():
        return True
    return any(p.search(user_message) for p in _SKIP_PERSONA_PATTERNS)


# --- Language / script detection for persona compatibility ---
#
# Script-level detection is sufficient to catch the most damaging persona
# mismatches (e.g. CJK persona applied to a Latin-script user message,
# which biases the responder into replying in the wrong language).
# We don't try to distinguish between Latin-script languages here because
# zero-dependency detection isn't reliable enough; the persona system
# prompt's language invariant is the second line of defense for those.
def detect_script(text: str) -> str:
    """Return the dominant Unicode script in `text`, or 'unknown' if it can't be classified.

    Returned values: cjk, japanese, korean, cyrillic, arabic, devanagari, thai,
    hebrew, greek, latin, mixed, unknown.

    Japanese and Chinese are kept separate:
    - Hiragana (U+3040–U+309F) and Katakana (U+30A0–U+30FF) are exclusively
      Japanese; any kana presence causes the CJK ideograph count to be merged
      into a combined "japanese" bucket.
    - Pure CJK Unified Ideographs with no kana are classified as "cjk"
      (Chinese/Taiwanese/Singaporean Mandarin).
    """
    if not text or not text.strip():
        return "unknown"

    kana_count = 0   # Hiragana + Katakana: unambiguously Japanese
    cjk_count  = 0   # CJK Unified Ideographs (shared Chinese/Japanese kanji)
    other_counts = {
        "korean": 0, "cyrillic": 0, "arabic": 0,
        "devanagari": 0, "thai": 0, "hebrew": 0, "greek": 0, "latin": 0,
    }

    for ch in text:
        cp = ord(ch)
        # Hiragana (3040-309F) + Katakana (30A0-30FF): exclusively Japanese
        if 0x3040 <= cp <= 0x30FF:
            kana_count += 1
        # CJK Unified Ideographs + extension A (shared Chinese/Japanese kanji)
        elif (0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF):
            cjk_count += 1
        elif 0xAC00 <= cp <= 0xD7AF:
            other_counts["korean"] += 1
        elif 0x0400 <= cp <= 0x04FF:
            other_counts["cyrillic"] += 1
        elif 0x0600 <= cp <= 0x06FF:
            other_counts["arabic"] += 1
        elif 0x0900 <= cp <= 0x097F:
            other_counts["devanagari"] += 1
        elif 0x0E00 <= cp <= 0x0E7F:
            other_counts["thai"] += 1
        elif 0x0590 <= cp <= 0x05FF:
            other_counts["hebrew"] += 1
        elif 0x0370 <= cp <= 0x03FF:
            other_counts["greek"] += 1
        elif ch.isalpha() and cp < 0x250:
            other_counts["latin"] += 1

    # Merge kana + kanji into "japanese" when kana is present; otherwise
    # kanji alone is treated as Chinese ("cjk").
    counts = dict(other_counts)
    if kana_count > 0:
        counts["japanese"] = kana_count + cjk_count
    else:
        counts["cjk"] = cjk_count

    # Prioritize non-Latin scripts if they have a non-trivial presence (e.g. > 3 characters),
    # since programming prompts often contain large Latin-script code blocks.
    for script_name, count in counts.items():
        if script_name != "latin" and count > 3:
            return script_name

    total = sum(counts.values())
    if total == 0:
        return "unknown"

    dominant_name, dominant_count = max(counts.items(), key=lambda x: x[1])
    # Require the dominant script to account for at least 60% of letter
    # characters; otherwise the message mixes scripts and we shouldn't
    # confidently lock the persona to one of them.
    if dominant_count / total < 0.60:
        return "mixed"
    return dominant_name


# Languages that share a script. Lowercase exact tokens are matched as
# substrings against the persona's "Languages: ..." characteristic.
_SCRIPT_LANGUAGES = {
    "cjk": {"chinese", "mandarin", "cantonese", "wu", "hokkien", "shanghainese", "sichuanese"},
    "japanese": {"japanese"},
    "korean": {"korean"},
    "cyrillic": {"russian", "ukrainian", "bulgarian", "serbian", "belarusian", "kazakh", "macedonian", "mongolian"},
    "arabic": {"arabic", "urdu", "persian", "farsi", "pashto", "kurdish"},
    "devanagari": {"hindi", "marathi", "nepali", "sanskrit", "bhojpuri"},
    "thai": {"thai"},
    "hebrew": {"hebrew", "yiddish"},
    "greek": {"greek"},
    "latin": {
        "english", "spanish", "french", "german", "italian", "portuguese",
        "dutch", "swedish", "norwegian", "danish", "finnish", "polish",
        "czech", "slovak", "hungarian", "romanian", "croatian", "slovenian",
        "estonian", "latvian", "lithuanian", "vietnamese", "indonesian",
        "malay", "swahili", "tagalog", "filipino", "yoruba", "igbo", "hausa",
        "zulu", "afrikaans", "turkish", "azerbaijani", "uzbek", "pidgin",
        "creole", "luxembourgish", "catalan", "basque", "galician",
        "icelandic", "irish", "welsh", "albanian", "maltese",
    },
}
import re

LANG_CODE_MAP = {
    "en": "english", "es": "spanish", "fr": "french", "de": "german",
    "it": "italian", "pt": "portuguese", "pl": "polish", "nl": "dutch",
    "sv": "swedish", "da": "danish", "no": "norwegian", "fi": "finnish",
    "tr": "turkish", "vi": "vietnamese", "id": "indonesian", "ms": "malay",
    "ko": "korean", "zh-cn": "chinese", "zh-tw": "chinese", "zh": "chinese",
    "ja": "japanese", "ru": "russian", "uk": "ukrainian", "bg": "bulgarian",
    "ar": "arabic", "fa": "persian", "ur": "urdu", "hi": "hindi", "th": "thai",
    "he": "hebrew", "el": "greek", "ca": "catalan", "cs": "czech", "sk": "slovak",
    "hu": "hungarian", "ro": "romanian", "hr": "croatian", "sr": "serbian",
    "et": "estonian", "lt": "lithuanian", "lv": "latvian", "sl": "slovenian",
    "sq": "albanian", "af": "afrikaans", "bn": "bengali", "cy": "welsh",
    "tl": "tagalog", "sw": "swahili", "pa": "punjabi", "gu": "gujarati",
    "ta": "tamil", "te": "telugu", "kn": "kannada", "ml": "malayalam",
    "mr": "marathi", "ne": "nepali", "si": "sinhala", "my": "burmese",
    "km": "khmer", "lo": "lao", "ka": "georgian", "hy": "armenian",
    "az": "azerbaijani", "kk": "kazakh", "uz": "uzbek", "mn": "mongolian",
    "eu": "basque", "gl": "galician", "is": "icelandic", "ga": "irish",
    "mt": "maltese", "so": "somali", "bs": "bosnian", "mk": "macedonian"
}

import re

_LINGUA_DETECTOR = None

def get_lingua_detector():
    global _LINGUA_DETECTOR
    if _LINGUA_DETECTOR is None:
        try:
            from lingua import LanguageDetectorBuilder
            _LINGUA_DETECTOR = LanguageDetectorBuilder.from_all_languages().build()
        except Exception:
            _LINGUA_DETECTOR = False
    return _LINGUA_DETECTOR if _LINGUA_DETECTOR is not False else None


def detect_language(text: str, threshold: float = 0.50):
    if not text or not text.strip():
        return None

    clean = text.strip()

    # 1. Deterministic CJK Unicode Script Checks (100% precision for Hanzi, Hangul, Kana)
    cjk_hanzi = len(re.findall(r"[\u4e00-\u9fff]", clean))
    hangul = len(re.findall(r"[\uac00-\ud7af\u3130-\u318f]", clean))
    kana = len(re.findall(r"[\u3040-\u30ff]", clean))

    if hangul > 0:
        return "korean"
    if kana > 0:
        return "japanese"
    if cjk_hanzi > 0:
        return "chinese"

    # 2. Lingua detector. Accept the top language if it is confident in ABSOLUTE terms OR a
    #    clear RELATIVE winner over the runner-up. Short text (e.g. "how do i center a div")
    #    spreads absolute confidence across many languages, so English can top the list at
    #    only ~0.1 while still dominating: the relative margin catches that; genuinely
    #    ambiguous text (top ≈ second) still falls through to None.
    detector = get_lingua_detector()
    if detector:
        try:
            confidences = detector.compute_language_confidence_values(clean)
            if confidences:
                top = confidences[0]
                top_name = top.language.name.lower()
                top_prob = top.value
                second_prob = confidences[1].value if len(confidences) > 1 else 0.0
                if top_prob >= threshold or top_prob >= 1.3 * second_prob:
                    return LANG_CODE_MAP.get(top_name, top_name).lower()
        except Exception:
            pass

    # 3. Low Confidence / Uncertain -> Return None (Signals to Skip Sample)
    return None

def persona_speaks_language(persona: dict, lang: str) -> bool:
    if not lang:
        return True
    bg = persona.get("background", {})
    native = (bg.get('native_language', '') or '').lower()
    spoken = bg.get('languages_spoken', [])
    spoken_str = (" ".join(spoken) if isinstance(spoken, list) else str(spoken or "")).lower()
    # NOTE: `dialect` is intentionally EXCLUDED. It is free-text flavor that often names
    # OTHER languages ("Central Latvian … with rural Lithuanian/Ukrainian exposure"), which
    # would falsely make a Latvian persona "speak" Ukrainian. Only the native language (and a
    # real languages_spoken list, if present) count as spoken languages.
    hay = f"{native} {spoken_str}".strip() or "english"
    lang = lang.lower()
    if lang in hay:
        return True
    # detect_language cannot distinguish Chinese variants (all return "chinese"), so accept
    # any Chinese-family native as a match for a "chinese" prompt.
    if lang == "chinese":
        return any(v in hay for v in ("chinese", "mandarin", "cantonese", "hokkien", "shanghainese", "sichuanese"))
    return False


def persona_speaks_script(persona: dict, script: str) -> bool:
    """Return True if persona's languages include any language using `script`.

    'unknown' or 'mixed' scripts are treated as compatible (we don't have
    enough signal to confidently skip).
    """
    if script in ("unknown", "mixed"):
        return True

    # Latin (English) prompts are compatible with all personas in the bank,
    # as they all contain English writing and register styles.
    if script == "latin":
        return True

    expected = _SCRIPT_LANGUAGES.get(script)
    if not expected:
        return True

    bg = persona.get("background", {})
    languages_str = f"{bg.get('native_language', '')} {bg.get('dialect', '')}".lower()
    if not languages_str.strip():
        return True

    return any(lang in languages_str for lang in expected)


def get_persona_background_str(p: dict) -> str:
    """Format the background layer into a string for LLM prompt injection.
    Contains demographic/contextual facts only: no communication style.
    """
    bg = p.get("background", {})
    parts = []

    # Identity
    age = bg.get("age")
    gender = bg.get("gender", "")
    if age and gender:
        parts.append(f"Age: {age} | Gender: {gender}")
    elif age:
        parts.append(f"Age: {age}")

    # Occupation (+ concrete job_title detail)
    occ = bg.get("occupation", "")
    job_title = bg.get("job_title", "")
    if occ and job_title:
        parts.append(f"Occupation: {occ} — {job_title}")
    elif occ:
        parts.append(f"Occupation: {occ}")

    # Location
    country = bg.get("country", "")
    sub_region = bg.get("sub_region", "")
    region = bg.get("region", "")
    loc_parts = [x for x in [sub_region, country, region] if x]
    if loc_parts:
        parts.append(f"From: {', '.join(loc_parts)}")

    # Education
    edu = bg.get("education")
    if isinstance(edu, dict):
        edu_str = edu.get("level", "")
        if edu.get("field_of_study"):
            edu_str += f" in {edu['field_of_study']}"
        if edu.get("institution_type") and edu.get("institution_type") != "None":
            edu_str += f" ({edu['institution_type']})"
    else:
        edu_str = bg.get("education_level") or str(edu or "")
    if edu_str:
        parts.append(f"Education: {edu_str}")

    # Language
    native_lang = bg.get("native_language", "")
    dialect = bg.get("dialect", "")
    lang_str = native_lang
    if dialect and dialect.lower() != native_lang.lower():
        lang_str += f" ({dialect} dialect)"
    if lang_str:
        parts.append(f"Native language: {lang_str}")

    # AI stance & digital fluency
    ai_stance = bg.get("ai_stance", "")
    digital_fluency = bg.get("digital_fluency", "")
    if ai_stance:
        parts.append(f"AI stance: {ai_stance}")
    if digital_fluency:
        parts.append(f"Digital fluency: {digital_fluency}")

    # Hobbies
    hobbies = bg.get("hobbies_interests", [])
    if hobbies:
        parts.append(f"Hobbies: {', '.join(hobbies) if isinstance(hobbies, list) else str(hobbies)}")

    return "\n".join(parts)


def get_persona_style_str(p: dict, include_quirks: bool = True, style_mode: str = "both") -> str:
    """Format the style layer into a string for LLM prompt injection.
    Contains communication style only: no demographic background facts.

    style_mode selects the chatting-style representation (enables the structured-vs-flat
    A/B): "flat" = the one-sentence chatting_style; "structured" = the per-axis keys;
    "both" (default) = both. The verbatim example_message is always included: it is the
    highest-leverage signal for the rewriter to imitate.
    """
    sty = p.get("style", {})
    parts = []

    chatting_style = sty.get("chatting_style") or sty.get("typing_style", "")
    if style_mode in ("flat", "both") and chatting_style:
        parts.append(f"Chatting style: {chatting_style}")

    # structured chatting-style keys (concrete, per-axis)
    cs = sty.get("chatting_style_structured") or {}
    if style_mode in ("structured", "both") and isinstance(cs, dict):
        axes = [("capitalization", "Capitalization"), ("punctuation", "Punctuation"),
                ("emoji_use", "Emoji"), ("abbreviation_habits", "Abbreviations"),
                ("message_structure", "Message structure"), ("typo_tendency", "Typos"),
                ("greeting_signoff", "Greeting/sign-off")]
        detail = "; ".join(f"{label}: {cs[k]}" for k, label in axes if (cs.get(k) or "").strip())
        if detail:
            parts.append(f"Typing details: {detail}")

    # verbatim example the rewriter should imitate (always included: highest leverage)
    example_message = sty.get("example_message", "")
    if example_message:
        parts.append(f'Example message they would actually type: "{example_message}"')

    if include_quirks:
        quirks = sty.get("linguistic_quirks", [])
        if quirks:
            quirk_list = quirks if isinstance(quirks, list) else [quirks]
            parts.append("Linguistic quirks:\n" + "\n".join(f"  - {q}" for q in quirk_list))

    sentence_len = sty.get("sentence_length_tendency", "")
    q_framing = sty.get("question_framing", "")
    if sentence_len:
        parts.append(f"Sentence length: {sentence_len}")
    if q_framing:
        parts.append(f"Question framing: {q_framing}")

    cs_freq = sty.get("code_switching_freq", "")
    cs_type = sty.get("code_switching_type", "")
    if cs_freq and cs_type:
        parts.append(f"Code-switching: {cs_freq} ({cs_type})")
    elif cs_freq:
        parts.append(f"Code-switching: {cs_freq}")

    error_patterns = sty.get("native_language_error_patterns", "")
    if error_patterns:
        parts.append(f"Native language influence: {error_patterns}")

    ref_pool = sty.get("reference_pool", [])
    if ref_pool:
        parts.append(f"Reference pool: {', '.join(ref_pool) if isinstance(ref_pool, list) else str(ref_pool)}")

    return "\n".join(parts)


def get_persona_characteristics_str(p: dict) -> str:
    """Legacy combined string used by the keyword-matching pipeline (Tier 2).
    For prompt injection, use get_persona_background_str + get_persona_style_str instead.
    """
    bg_str = get_persona_background_str(p)
    sty_str = get_persona_style_str(p)
    # Also include character_description for richer keyword coverage in matching
    char_desc = p.get("character_description", "") or p.get("description", "")
    combined = [x for x in [bg_str, sty_str, char_desc] if x]
    return " | ".join(combined)



def _match_by_location(
    user_message: str,
    personas: list[dict],
    user_script: str = "unknown",
) -> list[int]:
    """Tier 1: match personas whose location/country/language is congruent with the user message.

    Two complementary signals are combined (union):

    Signal 1 – script-based (primary for non-Latin messages):
        Maps the user's dominant Unicode script to a set of country/language
        keywords (``_SCRIPT_COUNTRY_KEYWORDS``) and checks whether those
        keywords appear in the persona's *place of birth*, *country of origin*,
        *location*, or *languages* fields.  This is the main lever that makes
        a Chinese-script message match Chinese-born personas even when no
        explicit place name is mentioned in the text.

    Signal 2 – text-based (regex place-name extraction):
        Capitalised tokens and preposition-introduced names are extracted from
        the user message and matched against all persona location fields.
        Useful for Latin-script messages that explicitly name a city/country,
        e.g. "restaurants in Berlin".

    Returns a list of persona indices (may be empty).
    """
    matched: set[int] = set()

    # ------------------------------------------------------------------
    # Signal 1: script → country/language keyword matching
    # ------------------------------------------------------------------
    script_keywords = _SCRIPT_COUNTRY_KEYWORDS.get(user_script, frozenset())
    if script_keywords:
        for i, p in enumerate(personas):
            bg = p.get("background", {})
            pob = bg.get("sub_region", "").lower()
            country = bg.get("country", "").lower()
            location = f"{bg.get('sub_region', '')} {bg.get('country', '')}".lower()
            langs = f"{bg.get('native_language', '')} {bg.get('dialect', '')}".lower()
                
            persona_text = f"{pob} {country} {location} {langs}"
            persona_words = set(re.findall(r'\b[a-z]{2,}\b', persona_text))
            if persona_words & script_keywords:
                matched.add(i)

    # ------------------------------------------------------------------
    # Signal 2: regex-extracted place names from the user message
    # ------------------------------------------------------------------
    raw_tokens  = _LOCATION_PATTERN.findall(user_message)
    prep_tokens = _PREP_LOCATION_PATTERN.findall(user_message)
    all_tokens  = set(t.lower() for t in raw_tokens + prep_tokens)
    token_words: set[str] = set()
    for tok in all_tokens:
        token_words.update(re.findall(r'\b[a-z]{2,}\b', tok))

    if token_words:
        # Synonym expansion: if any extracted token is a recognised country /
        # language keyword (e.g. "Chinese", "Japan", "Mandarin"), pull in all
        # related keywords for that script group.  This bridges adjective/noun
        # mismatches like "Chinese" (in message) vs "Mandarin" or "China" (in
        # persona field), and is bounded to a specific cultural/script group so
        # it doesn't become globally over-inclusive.
        expanded_keywords: set[str] = set(token_words)
        for keywords in _SCRIPT_COUNTRY_KEYWORDS.values():
            if token_words & keywords:
                expanded_keywords |= keywords

        for i, p in enumerate(personas):
            bg = p.get("background", {})
            pob = bg.get("sub_region", "").lower()
            country = bg.get("country", "").lower()
            location = f"{bg.get('sub_region', '')} {bg.get('country', '')}".lower()
            langs = f"{bg.get('native_language', '')} {bg.get('dialect', '')}".lower()

            place_words = set(re.findall(r'\b[a-z]{2,}\b',
                                         f"{location} {country} {pob} {langs}".lower()))
            if expanded_keywords & place_words:
                matched.add(i)

    return list(matched)


def _match_by_topic(
    user_message: str,
    personas: list[dict],
    subset_indices: list[int]
) -> list[int]:
    """Tier 2: rank personas by keyword overlap between user message and characteristics."""
    msg_words = set(re.findall(r'\b[a-z]{3,}\b', user_message.lower())) - _STOP_WORDS
    if not msg_words:
        return []

    scores = []
    for i in subset_indices:
        p = personas[i]
        bg = p.get("background", {})
        sty = p.get("style", {})
        fields_to_join = [
            bg.get("occupation", ""),
            bg.get("education_level", ""),
            bg.get("native_language", ""),
            bg.get("dialect", ""),
            " ".join(bg.get("hobbies_interests", [])) if isinstance(bg.get("hobbies_interests"), list) else str(bg.get("hobbies_interests", "")),
            " ".join(sty.get("reference_pool", [])) if isinstance(sty.get("reference_pool"), list) else str(sty.get("reference_pool", "")),
            " ".join(sty.get("linguistic_quirks", [])) if isinstance(sty.get("linguistic_quirks"), list) else str(sty.get("linguistic_quirks", "")),
            p.get("character_description", ""),
            p.get("description", ""),
        ]
        char_text = " ".join(str(f) for f in fields_to_join if f)
        char_words = set(re.findall(r'\b[a-z]{3,}\b', char_text.lower())) - _STOP_WORDS
        overlap = len(msg_words & char_words)
        if overlap > 0:
            scores.append((overlap, i))

    if not scores:
        return []

    scores.sort(key=lambda x: x[0], reverse=True)
    best_score = scores[0][0]
    # Keep candidates within half of the best overlap score for diversity
    candidates = [i for s, i in scores if s >= max(1, best_score // 2)]
    return candidates


def select_persona(
    user_message: str,
    personas: list[dict],
    persona_config: dict,
    embedding_model=None,
    persona_embeddings=None,
    user_script: str = None,
) -> tuple[dict | None, str, str | None]:
    """Select a persona using strict tiered matching. Returns (persona_or_None, tier_used, detected_lang_str)."""
    if not personas or not user_message:
        return None, "none", None

    # Cross-lingual mode: language-BLIND selection. Apply a persona from the WHOLE bank
    # regardless of the prompt's language, so the diverse bank actually gets exercised
    # (a Ukrainian / Yoruba / Thai persona re-voices an English prompt in their own register).
    if persona_config.get("cross_lingual"):
        return random.choice(personas), "cross_lingual", None

    # Step 1: Detect Language & Script internally
    raw_lang = detect_language(user_message)
    if not raw_lang:
        return None, "none", None

    raw_lang_str = str(raw_lang).lower()
    if not user_script:
        user_script = "cjk" if raw_lang_str in ("chinese", "japanese", "korean") else ("cyrillic" if raw_lang_str in ("russian", "bulgarian", "ukrainian") else "latin")

    # Step 2: Filter candidate personas by script / language match
    persona_lang_check = persona_config.get("language_match", True)
    if persona_lang_check and user_script not in ("unknown", "mixed"):
        if user_script == "latin":
            valid_indices = [
                i for i, p in enumerate(personas)
                if persona_speaks_language(p, raw_lang_str)
            ]
            if not valid_indices and raw_lang_str != "english":
                return None, "unsupported_language", raw_lang_str
            elif not valid_indices:
                valid_indices = list(range(len(personas)))
        else:
            # Non-Latin scripts: prefer personas whose native/dialect language actually
            # MATCHES the detected language, not merely the shared script. Otherwise
            # languages that share a script get cross-assigned (Cyrillic ru/uk/bg/sr/…,
            # Arabic ar/ur/fa/…, Devanagari hi/mr/ne/…), e.g. a Ukrainian prompt drawing
            # a Russian persona. Fall back to script-compatible only if the bank has no
            # same-language persona at all.
            valid_indices = [
                i for i, p in enumerate(personas)
                if persona_speaks_language(p, raw_lang_str)
            ]
            if not valid_indices:
                valid_indices = [
                    i for i, p in enumerate(personas)
                    if persona_speaks_script(p, user_script)
                ]
        if not valid_indices:
            return None, "unsupported_language", raw_lang_str
    else:
        valid_indices = list(range(len(personas)))

    matching_cfg = persona_config.get("matching", {})
    use_location  = matching_cfg.get("location_regex", True)
    use_embedding = matching_cfg.get("embedding_fallback", True)

    # Step 3: Location Matching
    location_pool: list[int] = []
    if use_location:
        loc_candidates = _match_by_location(
            user_message, personas, user_script=user_script
        )
        location_pool = [i for i in loc_candidates if i in valid_indices]

    if location_pool:
        if embedding_model is not None and persona_embeddings is not None:
            try:
                from sentence_transformers import util
                import torch
                prompt_embedding = embedding_model.encode(user_message, convert_to_tensor=True)
                pool_embeddings = torch.stack([persona_embeddings[idx] for idx in location_pool])
                similarities = util.cos_sim(prompt_embedding, pool_embeddings)[0]
                best_pool_idx = torch.argmax(similarities).item()
                return personas[location_pool[best_pool_idx]], "location", raw_lang_str
            except Exception:
                pass
        import hashlib
        h = int(hashlib.md5(user_message.encode('utf-8')).hexdigest(), 16)
        return personas[location_pool[h % len(location_pool)]], "location", raw_lang_str

    # Step 4: Embedding cosine similarity search
    if use_embedding and embedding_model is not None and persona_embeddings is not None:
        from sentence_transformers import util
        prompt_embedding = embedding_model.encode(user_message, convert_to_tensor=True)
        similarities = util.cos_sim(prompt_embedding, persona_embeddings)[0]
        min_sim = matching_cfg.get("min_embedding_similarity", 0.15)
        
        emb_candidates = [
            i for i in valid_indices
            if similarities[i].item() >= min_sim
        ]
        if emb_candidates:
            emb_candidates.sort(key=lambda i: similarities[i].item(), reverse=True)
            return personas[emb_candidates[0]], "embedding", raw_lang_str

    # Step 5: Deterministic fallback selection within valid language personas pool
    if valid_indices:
        import hashlib
        h = int(hashlib.md5(user_message.encode('utf-8')).hexdigest(), 16)
        return personas[valid_indices[h % len(valid_indices)]], "language_pool", raw_lang_str

    return None, "unsupported_language", raw_lang_str


def strip_reasoning(text: str) -> str:
    """Strip Qwen/Deepseek/GLM style reasoning tags from the response."""
    if not text:
        return text
    original = text
    # Remove <|channel|>analysis... up to <|channel|>final<|message|>
    text = re.sub(r"<\|channel\|>analysis<\|message\|>.*?<\|channel\|>final<\|message\|>\s*", "", text, flags=re.DOTALL)
    # Remove any remaining standalone <|start|>assistant or <|end|>
    text = re.sub(r"<\|start\|>assistant|<\|end\|>", "", text)
    # Remove everything from start to </think> or /think> (handles <think>...</think>, think>.../think>, and Thinking Process:...</think>)
    text = re.sub(r"^.*?(?:<\/think>|/think>)\s*", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove <think>...</think> or think>.../think> if any remains
    text = re.sub(r"(?:<think>|think>).*?(?:<\/think>|/think>)\s*", "", text, flags=re.DOTALL | re.IGNORECASE)
    
    result = text.strip()
    
    # If the response starts with/contains "Thinking Process:" and has no </think>
    if "thinking process" in result.lower():
        # Try to find common final response markers
        markers = [
            r'(?:final polish|final response|final output|output|my rewrite|rewrite|rewritten message|output only the rewritten message|final choice|selected draft|my version|version|response)\s*:\s*\*?\*?([^\n]+(?:\n[^\n]+)*)'
        ]
        for marker_pat in markers:
            matches = list(re.finditer(marker_pat, result, re.IGNORECASE))
            if matches:
                # Get the last match
                last_match = matches[-1]
                candidate = last_match.group(1).strip()
                # Clean surrounding quotes/stars
                candidate = re.sub(r'^["\'`*]+|["\'`*]+$', '', candidate).strip()
                if candidate and "thinking process" not in candidate.lower():
                    return candidate

    if result:
        return result
        
    # All content was inside reasoning tags: extract last paragraph from inside <think>
    think_match = re.search(r"<think>(.*?)</think>", original, re.DOTALL | re.IGNORECASE)
    if think_match:
        paragraphs = [p.strip() for p in think_match.group(1).split("\n\n") if p.strip()]
        if paragraphs:
            return paragraphs[-1]
            
    # Fallback to extract last paragraph from before </think>
    think_match = re.search(r"^(.*?)</think>", original, re.DOTALL | re.IGNORECASE)
    if think_match:
        paragraphs = [p.strip() for p in think_match.group(1).split("\n\n") if p.strip()]
        if paragraphs:
            return paragraphs[-1]
            
    return original.strip()

def extract_conversation_turns(conversation: list[dict]) -> list[dict]:
    """Extract user/assistant turn pairs from conversation."""
    turns = []
    for msg in conversation:
        role = msg.get("role")
        content = msg.get("content")
        if role in ("user", "assistant") and content:
            turns.append({"role": role, "content": content})
    return turns

def build_url(base_url: str) -> str:
    """Build the chat completions URL from base URL."""
    base_url = base_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    return f"{base_url}/chat/completions"

async def call_api(
    session: aiohttp.ClientSession,
    api_config: dict,
    gen_config: dict,
    messages: list[dict],
    error_prefix: str,
    is_judge: bool = False,
) -> tuple[str | None, str | None]:
    """Make an API call and return (response_text, error_msg)."""
    global _first_responder_error_printed, _first_judge_error_printed

    raw_key = api_config.get("api_key", "")
    if isinstance(raw_key, str) and raw_key.startswith("ENV="):
        var_name = raw_key.split("ENV=", 1)[1].strip()
        api_key = os.environ.get(var_name, "")
    else:
        api_key = raw_key or os.environ.get("PF_API_KEY") or ""

    url = build_url(api_config["base_url"])
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": api_config["model"],
        "messages": messages,
        "max_tokens": gen_config.get("max_tokens", 8192),
        "temperature": gen_config.get("temperature", 0.7),
        "top_p": gen_config.get("top_p", 0.95),
    }
    model_name_lower = api_config["model"].lower()
    if "qwen" in model_name_lower or "glm" in model_name_lower:
        payload["chat_template_kwargs"] = {"enable_thinking": False}

    first_error_printed = _first_judge_error_printed if is_judge else _first_responder_error_printed

    start_time = time.time()
    attempt = 0
    max_attempts = 5
    delay = 2.0
    
    while True:
        attempt += 1
        try:
            async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=300.0)) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    response_text = result["choices"][0]["message"]["content"]

                    if not response_text:
                        err_msg = "Model returned null/empty content"
                    else:
                        response_text = strip_reasoning(response_text)
                        if not response_text:
                            err_msg = "Response contained only reasoning with no final answer"
                        else:
                            return response_text, None

                    # If we reached here, the content was empty or null
                    if is_judge:
                        if time.time() - start_time > 300:
                            print(f"\n[WARNING] Validator (judge) unreachable for > 5 minutes (empty content). Skipping scoring to let execution continue.", file=sys.stderr)
                            return None, "Validator unreachable"
                        print(f"[{error_prefix}] Validator returned empty content. Retrying in 15 seconds...", file=sys.stderr)
                        await asyncio.sleep(15)
                        continue
                    else:
                        if "kimi" in api_config.get("id", "").lower():
                            print(f"[{error_prefix}] Kimi model returned empty content (token limit exhausted during thinking). Skipping retries.", file=sys.stderr)
                            return None, err_msg
                        if attempt < max_attempts:
                            print(f"[{error_prefix}] Model returned empty content. Retrying in {delay}s (attempt {attempt}/{max_attempts})...", file=sys.stderr)
                            await asyncio.sleep(delay)
                            delay = min(delay * 2, 30.0)
                            continue
                        else:
                            return None, err_msg
                else:
                    error_text = await resp.text()
                    error_msg = f"HTTP {resp.status}: {error_text}"

                    if is_judge:
                        if time.time() - start_time > 300:
                            print(f"\n[WARNING] Validator (judge) unreachable for > 5 minutes ({resp.status}). Skipping scoring to let execution continue.", file=sys.stderr)
                            return None, "Validator unreachable"
                        print(f"[{error_prefix}] Validator returned {resp.status}. Retrying in 15 seconds...", file=sys.stderr)
                        await asyncio.sleep(15)
                        continue
                    else:
                        if (resp.status == 429 or resp.status >= 500) and attempt < max_attempts:
                            print(f"[{error_prefix}] HTTP {resp.status}. Retrying in {delay}s (attempt {attempt}/{max_attempts})...", file=sys.stderr)
                            await asyncio.sleep(delay)
                            delay = min(delay * 2, 30.0)
                            continue

                        if not first_error_printed:
                            if is_judge:
                                _first_judge_error_printed = True
                            else:
                                _first_responder_error_printed = True
                            print(f"\n[{error_prefix} ERROR] URL: {url}", file=sys.stderr)
                            print(f"[{error_prefix} ERROR] Status: {resp.status}", file=sys.stderr)
                            print(f"[{error_prefix} ERROR] Headers: {dict(resp.headers)}", file=sys.stderr)
                            print(f"[{error_prefix} ERROR] Response body:\n{error_text}", file=sys.stderr)
                            print(f"[{error_prefix} ERROR] Request payload:\n{json.dumps(payload, indent=2)}", file=sys.stderr)

                        return None, error_msg
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"

            if is_judge:
                if time.time() - start_time > 300:
                    print(f"\n[WARNING] Validator (judge) unreachable for > 5 minutes ({error_msg}). Skipping scoring to let execution continue.", file=sys.stderr)
                    return None, "Validator unreachable"
                print(f"[{error_prefix}] Validator connection error ({error_msg}). Retrying in 15 seconds...", file=sys.stderr)
                await asyncio.sleep(15)
                continue
            else:
                if "kimi" in api_config.get("id", "").lower() and "timeout" in error_msg.lower():
                    print(f"[{error_prefix}] Kimi model request timed out. Skipping retries.", file=sys.stderr)
                    return None, error_msg
                if attempt < max_attempts:
                    print(f"[{error_prefix}] Connection error ({type(e).__name__}: {e}). Retrying in {delay}s (attempt {attempt}/{max_attempts})...", file=sys.stderr)
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 30.0)
                    continue

                if not first_error_printed:
                    if is_judge:
                        _first_judge_error_printed = True
                    else:
                        _first_responder_error_printed = True
                    print(f"\n[{error_prefix} ERROR] URL: {url}", file=sys.stderr)
                    print(f"[{error_prefix} ERROR] Exception: {error_msg}", file=sys.stderr)

                return None, error_msg

def format_context(messages: list[dict]) -> str:
    """Format conversation messages for prompts."""
    lines = []
    for msg in messages:
        role = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['content']}")
    return "\n\n".join(lines)

def parse_judge_response(judge_response: str | None) -> tuple[str, str]:
    """Parse judge response JSON, return (verdict, reason)."""
    if judge_response is None:
        return "error", "No response received"
    
    judge_text = judge_response.strip()
    
    # Try regex first to be extremely robust to thinking process prefixes, markdown, 
    # unescaped quotes, and truncation in JSON formatting.
    verdict_match = re.search(r'"verdict"\s*:\s*"?([a-zA-Z_0-9\-]+)"?', judge_text, re.IGNORECASE)
    reason_match = re.search(r'"reason"\s*:\s*"?(.*?)"?\s*(?:,|\s*\})', judge_text, re.IGNORECASE)
    
    verdict = verdict_match.group(1).lower() if verdict_match else None
    reason = reason_match.group(1).strip() if reason_match else ""
    
    # Clean reason quotes if it ended up with leading/trailing quotes
    if reason.startswith('"') and reason.endswith('"'):
        reason = reason[1:-1]
        
    if verdict in ("pass", "fail", "needs_adaptation", "needs_change"):
        return verdict, reason

    # Fallback to standard JSON parsing if regex didn't extract a valid verdict
    try:
        # Find JSON object directly using regex to avoid markdown/backtick issues
        match = re.search(r'\{.*\}', judge_text, re.DOTALL)
        if match:
            judge_text = match.group(0)

        judge_result = json.loads(judge_text)
        return judge_result.get("verdict", "unknown"), judge_result.get("reason", "")
    except (json.JSONDecodeError, IndexError, ValueError):
        return "parse_error", judge_response
    
async def process_conversation(
    session: aiohttp.ClientSession,
    conversation: list[dict],
    config: dict,
    sample_id,  # int (single dataset) or "source:idx" str (blended datasets); stored as result["id"]
) -> dict:
    """Process a multi-turn conversation with same responder for all turns."""
    responders = config["responders"]
    judge_config = config["judge"]
    gen_config = config["generation"]
    judge_gen_config = config["judge_generation"]
    adaptation_gen_config = config.get("adaptation_generation", gen_config)
    max_adaptations = config.get("processing", {}).get("max_adaptations", 2)
    max_retries = config.get("processing", {}).get("max_retries", 3)
    max_conv_turns = config.get("processing", {}).get("max_conv_turns", 0)
    max_sanity_retries = config.get("processing", {}).get("max_sanity_retries", 2)

    # Extract turns from conversation
    turns = extract_conversation_turns(conversation)

    # Find user turn indices (where we need to generate responses)
    user_turn_indices = [i for i, t in enumerate(turns) if t["role"] == "user"]
    original_num_turns = len(user_turn_indices)

    # Limit conversation turns if max_conv_turns is set (0 = no limit)
    truncated = False
    if max_conv_turns > 0 and len(user_turn_indices) > max_conv_turns:
        user_turn_indices = user_turn_indices[:max_conv_turns]
        truncated = True

    if not user_turn_indices:
        return {
            "id": sample_id,
            "conversation": [],
            "metadata": {
                "num_turns": 0,
                "original_num_turns": original_num_turns,
                "truncated": False,
                "responder": None,
                "responder_model": None,
                "status": "no_user_turns",
            },
        }

    # Select persona for the whole conversation
    conversation_persona = None
    persona_match_tier = None
    persona_config = config.get("persona", {})
    assigned = config.get("_assigned")  # pre-assigned persona / tier / responder
    if assigned:
        conversation_persona = assigned["persona"]
        persona_match_tier = assigned["match_tier"]
    elif persona_config.get("use_persona", False):
        loaded_personas = persona_config.get("loaded_personas", [])
        if loaded_personas:
            first_user_message = next((t["content"] for t in turns if t["role"] == "user"), "")
            overall_script = detect_script(first_user_message)
            conversation_persona, persona_match_tier, _ = select_persona(
                first_user_message,
                loaded_personas,
                persona_config,
                embedding_model=persona_config.get("embedding_model"),
                persona_embeddings=persona_config.get("persona_embeddings"),
                user_script=overall_script,
            )

    # Randomly sample a responder (same for entire conversation)
    if assigned:
        responder = random.choice([r for r in responders if r["name"] == assigned["responder"]])
    else:
        responder = random.choice(responders)

    result = {
        "id": sample_id,
        "conversation": [],  # Will be built in original format
        "metadata": {
            "num_turns": len(user_turn_indices),
            "original_num_turns": original_num_turns,
            "truncated": truncated,
            "responder": responder["name"],
            "responder_model": responder["model"],
            "status": "success",
            "turns_detail": [],  # Detailed info per turn
        },
    }

    if conversation_persona:
        result["metadata"]["persona"] = conversation_persona
        result["metadata"]["persona_match_tier"] = persona_match_tier

    # Process each user turn
    generated_history = []  # Track our generated conversation

    for turn_idx, user_idx in enumerate(user_turn_indices):
        is_last_turn = (turn_idx == len(user_turn_indices) - 1)

        user_message_original = turns[user_idx]["content"]
        # cross-lingual turns are translated first; the translation is what gets restyled
        user_message_source = user_message_original
        target_language = (assigned or {}).get("target_language")
        if target_language and not config.get("_fixed"):  # fixed turns are already translated
            user_message_original = await translate_turn(session, config, user_message_source, target_language)
        user_message = user_message_original
        persona_active_for_turn = False
        persona_user_message_changed = False
        persona_skip_reason = None
        persona_adapt_attempts = 0

        # --- Persona Injection ---
        # Persona application is all-or-nothing per turn: if we cannot fully
        # apply it (verbatim task, language mismatch, or adaptation fails),
        # we skip both the user-message rewrite AND the system prompt to
        # avoid half-applied personas leaking style without context.
        if config.get("_fixed"):  # reuse a previously generated user turn exactly (no rewrite)
            fx = config["_fixed"][turn_idx]
            user_message_original = fx["user_message_original"]
            user_message_source = fx.get("user_message_source", user_message_original)
            user_message = fx["user_message"]
            persona_active_for_turn = bool(fx["persona_applied"])
            persona_user_message_changed = user_message.strip() != user_message_original.strip()
            persona_skip_reason = fx.get("persona_skip_reason")
        elif conversation_persona:
            persona_lang_check = persona_config.get("language_match", True)
            user_script = detect_script(user_message_original)

            if should_skip_persona(user_message_original):
                persona_skip_reason = "task_requires_verbatim_or_strict_format"
            elif persona_lang_check and not persona_speaks_script(conversation_persona, user_script):
                # Persona's languages don't include any language using the
                # user's script. Applying the persona biases the responder
                # into the wrong language.
                persona_skip_reason = f"persona_language_mismatch: user_script={user_script}"
            else:
                quirk_prob = persona_config.get("verbal_quirk_prob", 0.25)
                if random.random() <= quirk_prob:
                    verbal_quirks_instruction = "Use the persona's typing style and, if natural, you may include one of their verbal mannerisms or tics."
                else:
                    verbal_quirks_instruction = "For this turn, maintain typing/punctuation style only; do NOT include any verbal filler words or mannerisms."

                template = ADAPT_USER_PROMPT_TEMPLATE
                # literal protection
                masked_message, span_map = integrity.protect(user_message_original)
                adapt_prompt = template.format(
                    background=get_persona_background_str(conversation_persona),
                    writing_style=get_persona_style_str(conversation_persona),
                    verbal_quirks_instruction=verbal_quirks_instruction,
                    user_message=masked_message
                )
                if span_map:
                    adapt_prompt += "\n\n" + integrity.protection_instruction().strip()
                adapt_messages = [{"role": "user", "content": adapt_prompt}]

                persona_gen_config = {
                    "max_tokens": gen_config.get("max_tokens", 4096),
                    "temperature": persona_config.get("temperature", 0.7),
                    "top_p": gen_config.get("top_p", 0.95),
                }

                # Retry budget for the adaptation call. Distinct from
                # max_retries (responder generation) and max_adaptations
                # (consistency-driven response rewriting).
                max_persona_retries = persona_config.get("max_adapt_retries", 2)
                min_length_ratio = persona_config.get("min_adapt_length_ratio", 0.5)
                # Below this length, ratio-based truncation detection misfires
                # on legitimately short messages.
                length_check_min_chars = 50

                adapted_user_message = None
                adapt_err = None
                last_failure = None

                for attempt in range(max_persona_retries + 1):
                    persona_adapt_attempts = attempt + 1
                    candidate, candidate_err = await call_api(
                        session, responder, persona_gen_config, adapt_messages,
                        error_prefix=f"PERSONA_ADAPT:{responder['name']}",
                        is_judge=False,
                    )

                    if not candidate or candidate_err:
                        last_failure = f"empty_or_error: {candidate_err}"
                        adapt_err = candidate_err or "empty content"
                        continue

                    # restore protected spans; retry if any was lost
                    try:
                        candidate = sanitize_constitution(integrity.restore(candidate, span_map))
                    except ValueError:
                        last_failure = "literal_integrity: protected span missing or duplicated"
                        continue
                    if span_map and not integrity.audit(user_message_original, candidate, sanitize_constitution)["policy_intact"]:
                        last_failure = "literal_integrity"
                        continue

                    # Truncation guard: a vastly shorter adaptation usually
                    # means the model dropped the actual task (e.g. a long
                    # translation request collapsing to its title).
                    if (
                        len(user_message_original) >= length_check_min_chars
                        and len(candidate) < min_length_ratio * len(user_message_original)
                    ):
                        last_failure = (
                            f"adapt_truncated: {len(candidate)} chars vs "
                            f"original {len(user_message_original)} chars"
                        )
                        continue

                    # Script-stability guard: adaptation must not switch
                    # the dominant script. The system prompt's language
                    # invariant only protects the response, not the rewrite.
                    candidate_script = detect_script(candidate)
                    if (
                        not persona_config.get("cross_lingual")   # cross-lingual: allow the persona to re-voice in its own script
                        and user_script not in ("unknown", "mixed")
                        and candidate_script not in ("unknown", "mixed")
                        and candidate_script != user_script
                    ):
                        last_failure = (
                            f"adapt_changed_script: {user_script} -> {candidate_script}"
                        )
                        continue

                    # cross-lingual rewrite must be in the target language
                    if target_language and not config["_lang_ok"](candidate, target_language):
                        last_failure = f"adapt_wrong_language: target={target_language}"
                        continue

                    adapted_user_message = candidate
                    adapt_err = None
                    break

                if adapted_user_message:
                    user_message = adapted_user_message
                    persona_user_message_changed = (
                        adapted_user_message.strip() != user_message_original.strip()
                    )
                    # The system prompt is still useful for register/tone
                    # even when the user-message rewrite produced no change.
                    persona_active_for_turn = True
                    if not persona_user_message_changed:
                        persona_skip_reason = "no_adaptation_made"
                else:
                    persona_skip_reason = f"adapt_failed: {last_failure or adapt_err}"
                    print(
                        f"[{responder['name']}] Turn {turn_idx}: Persona adaptation failed after "
                        f"{persona_adapt_attempts} attempt(s): {persona_skip_reason}. Skipping persona for this turn.",
                        flush=True,
                    )

        # Build messages: previous generated history + current user message.
        # Inject persona system prompt only when persona was successfully applied
        # for this turn: partial application produces inconsistent style signals.
        messages = generated_history + [{"role": "user", "content": user_message}]
        if persona_active_for_turn and persona_config.get("inject_system_prompt", True):
            system_content = PERSONA_SYSTEM_PROMPT_TEMPLATE.format(
                background=get_persona_background_str(conversation_persona),
                writing_style=get_persona_style_str(conversation_persona),
            )
            messages = [{"role": "system", "content": system_content}] + messages
        mp_quirk = None
        if config.get("_model_persona"):  # assistant response style on every turn
            from personafactory.assistant import model_persona as mp_core
            mp_quirk = mp_core.quirk_for(config["_model_persona"], sample_id, turn_idx)
            style = mp_core.style_section(config["_model_persona"], mp_quirk)
            if messages[0]["role"] == "system":
                messages[0] = {"role": "system", "content": messages[0]["content"] + "\n\n" + style}
            elif config.get("_source_system"):  # assistant-only mode keeps the dataset's own system prompt
                if os.environ.get("AO_SYS_POSITION", "last") == "first":  # style below the source prompt
                    content = (config["_source_system"] + "\n\n" + style +
                               "\n\nThe instructions above this response style take priority over it.")
                else:  # source prompt last, as hard constraints the style works within
                    content = (style + "\n\nSYSTEM INSTRUCTIONS (these override the response style above whenever they "
                               "conflict, including on length, format and language; apply the style only within them):\n" +
                               config["_source_system"])
                messages = [{"role": "system", "content": content}] + messages
            else:
                messages = [{"role": "system", "content": "You are an AI assistant.\n\n" + style +
                             "\n\nRespond in the same language as the user's message."}] + messages
        elif config.get("_source_system") and messages[0]["role"] != "system":  # assistant-only mode, no-persona control
            messages = [{"role": "system", "content": config["_source_system"]}] + messages

        # Generate initial response with retries
        response_text = None
        response_error = None
        retry_count = 0

        while response_text is None and retry_count < max_retries:
            #print(f"[{responder['name']}] Turn {turn_idx}: Generating response (attempt {retry_count + 1})...", flush=True)
            response_text, response_error = await call_api(
                session, responder, gen_config, messages,
                error_prefix=f"RESPONDER:{responder['name']}",
                is_judge=False,
            )
            if response_text is None:
                #print(f"[{responder['name']}] Error: {response_error}. Retrying...", flush=True)
                retry_count += 1
            else:
                print(f"[{responder['name']}] Turn {turn_idx}: Generation successful! Length: {len(response_text)} chars", flush=True)

        turn_result = {
            "turn": turn_idx,
            "user_message_original": user_message_original,
            "user_message": user_message,
            "user_message_source": user_message_source,  # source turn before translation
            "translated": bool(target_language),
            "model_persona_quirk": mp_quirk,  # model-persona signature touch offered on this turn
            "persona_applied": persona_active_for_turn,
            "persona_user_message_changed": persona_user_message_changed,
            "persona_adapt_attempts": persona_adapt_attempts,
            "persona_skip_reason": persona_skip_reason,
            "original_response": response_text,
            "response_status": "success" if response_text else "error",
            "retry_count": retry_count,
            "adaptations": [],
        }

        if response_error:
            turn_result["response_error"] = response_error
            turn_result["final_response"] = None
            result["metadata"]["turns_detail"].append(turn_result)
            result["metadata"]["status"] = "partial_error"
            # Still add to history and conversation for subsequent turns (with empty response)
            generated_history.append({"role": "user", "content": user_message})
            generated_history.append({"role": "assistant", "content": ""})
            result["conversation"].append({"role": "user", "content": user_message})
            result["conversation"].append({"role": "assistant", "content": ""})
            continue

        final_response = response_text

        # For non-last turns, check consistency and adapt if needed
        if not is_last_turn:
            next_user_idx = user_turn_indices[turn_idx + 1]
            next_user_message = turns[next_user_idx]["content"]
            turn_result["next_user_message"] = next_user_message

            current_response = response_text
            adaptation_count = 0

            while adaptation_count < max_adaptations:
                # print(f"[{responder['name']}] Turn {turn_idx}: Running judge consistency check...", flush=True)
                # Check if response fits with next user message
                judge_prompt = JUDGE_CONSISTENCY_TEMPLATE.format(
                    context=format_context(messages),
                    response=current_response,
                    next_user_message=next_user_message,
                )
                judge_messages = [{"role": "user", "content": judge_prompt}]
                # Use responder model for consistency check (self-evaluation)
                judge_response, judge_error = await call_api(
                    session, responder, adaptation_gen_config, judge_messages,
                    error_prefix=f"CONSISTENCY:{responder['name']}",
                    is_judge=False,
                )

                if judge_error or judge_response is None:
                    turn_result["adaptations"].append({
                        "attempt": adaptation_count,
                        "judge_status": "error",
                        "judge_error": judge_error or "No response received",
                    })
                    break

                verdict, reason = parse_judge_response(judge_response)

                if verdict == "pass":
                    # print(f"[{responder['name']}] Turn {turn_idx}: Consistency check PASSED", flush=True)
                    turn_result["adaptations"].append({
                        "attempt": adaptation_count,
                        "judge_verdict": verdict,
                        "judge_reason": reason,
                    })
                    final_response = current_response
                    break
                elif verdict == "needs_adaptation":
                    # print(f"[{responder['name']}] Turn {turn_idx}: Needs adaptation ({reason}). Generating new response...", flush=True)
                    # Ask model to adapt the response
                    adapt_prompt = ADAPT_RESPONSE_TEMPLATE.format(
                        context=format_context(messages),
                        original_response=current_response,
                        reason=reason,
                        next_user_message=next_user_message,
                    )
                    if config.get("_model_persona"):  # continuity repair keeps the style
                        from personafactory.assistant import model_persona as mp_core
                        adapt_prompt += mp_core.continuity_style_reminder(config["_model_persona"])
                    adapt_messages = [{"role": "user", "content": adapt_prompt}]
                    adapted_response, adapt_error = await call_api(
                        session, responder, adaptation_gen_config, adapt_messages,
                        error_prefix=f"ADAPT:{responder['name']}",
                        is_judge=False,
                    )

                    turn_result["adaptations"].append({
                        "attempt": adaptation_count,
                        "judge_verdict": verdict,
                        "judge_reason": reason,
                        "adapted_response": adapted_response,
                        "adapt_status": "success" if adapted_response else "error",
                        "adapt_error": adapt_error,
                    })

                    if adapted_response:
                        current_response = adapted_response
                        final_response = adapted_response
                    else:
                        break

                    adaptation_count += 1
                else:
                    # Parse error or unknown verdict
                    turn_result["adaptations"].append({
                        "attempt": adaptation_count,
                        "judge_verdict": verdict,
                        "judge_reason": reason,
                    })
                    break

            turn_result["num_adaptations"] = adaptation_count
            turn_result["final_verdict"] = verdict if 'verdict' in locals() else "unknown"

        final_response = sanitize_constitution(final_response)
        turn_result["final_response"] = final_response

        # Sanity verification by judge model after adaptation step.
        # Retry on null/empty content and parse errors: these are
        # transient model failures, distinct from a genuine fail verdict.
        sanity_prompt = SANITY_VERIFICATION_TEMPLATE.format(
            context=format_context(generated_history) if generated_history else "Start of conversation",
            user_message=user_message,
            response=final_response,
        )
        sanity_messages = [{"role": "user", "content": sanity_prompt}]

        sanity_attempts = 0
        sanity_response = None
        sanity_error = None
        sanity_verdict = "error"
        sanity_reason = ""

        # Round-robin the judge across all served judge endpoints. The judge (e.g. MiniMax) can be
        # slow, so a single endpoint would bottleneck the sanity gate at scale; `base_urls` (if
        # present) lists every judge replica and we pick one per call/retry. Falls back to the single
        # `base_url` for backward compatibility.
        _judge_urls = [u for u in (judge_config.get("base_urls") or [judge_config.get("base_url")]) if u]
        for attempt in range(max_sanity_retries + 1):
            sanity_attempts = attempt + 1
            _jc = dict(judge_config)
            _jc["base_url"] = random.choice(_judge_urls) if _judge_urls else judge_config.get("base_url")
            sanity_response, sanity_error = await call_api(
                session, _jc, judge_gen_config, sanity_messages,
                error_prefix="SANITY_JUDGE",
                is_judge=True,
            )

            if sanity_error or sanity_response is None:
                sanity_verdict = "error"
                sanity_reason = sanity_error or "No response received"
                continue

            parsed_verdict, parsed_reason = parse_judge_response(sanity_response)
            sanity_verdict = parsed_verdict
            sanity_reason = parsed_reason
            if parsed_verdict in ("pass", "fail"):
                sanity_error = None
                break
            # parse_error / unknown -> retry

        if sanity_verdict in ("pass", "fail"):
            turn_result["sanity_check"] = {
                "status": "success",
                "verdict": sanity_verdict,
                "reason": sanity_reason,
                "attempts": sanity_attempts,
            }
        else:
            turn_result["sanity_check"] = {
                "status": "error",
                "error": sanity_error or sanity_reason or "judge produced no parseable verdict",
                "verdict": sanity_verdict,
                "attempts": sanity_attempts,
            }

        # Update generated history with final response
        generated_history.append({"role": "user", "content": user_message})
        generated_history.append({"role": "assistant", "content": final_response})

        # Add to conversation in original format
        result["conversation"].append({"role": "user", "content": user_message})
        result["conversation"].append({"role": "assistant", "content": final_response})

        result["metadata"]["turns_detail"].append(turn_result)

    # Aggregate sanity verdicts from all turns
    sanity_verdicts = []
    for turn_detail in result["metadata"]["turns_detail"]:
        sanity_check = turn_detail.get("sanity_check", {})
        verdict = sanity_check.get("verdict", "unknown")
        sanity_verdicts.append(verdict)

    # Conversation passes only if all turns pass sanity check.
    # `sanity_status` distinguishes fail (judge said no) from error
    # (judge produced no parseable verdict): silent errors should not
    # be treated identically to genuine failures downstream.
    all_passed = bool(sanity_verdicts) and all(v == "pass" for v in sanity_verdicts)
    has_fail = any(v == "fail" for v in sanity_verdicts)
    if all_passed:
        sanity_status = "pass"
    elif has_fail:
        sanity_status = "fail"
    else:
        sanity_status = "error"

    result["metadata"]["sanity_verdicts"] = sanity_verdicts
    result["metadata"]["sanity_pass"] = all_passed
    result["metadata"]["sanity_status"] = sanity_status

    return result

def append_checkpoint(result: dict, output_path: Path) -> None:
    """Append a single completed result to the JSONL file."""
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")
            
            
# --- Dataset adapters: normalise arbitrary chat datasets to WildChat's `conversation` shape ---
# Each adapter maps one raw row -> a list of {"role": "user"|"assistant"|"system", "content": str}.
# Used by process_dataset so one augmentation run can blend WildChat / UltraChat / Nemotron / etc.
_ROLE_MAP = {"human": "user", "user": "user", "prompter": "user",
             "gpt": "assistant", "assistant": "assistant", "bot": "assistant", "model": "assistant",
             "system": "system"}

def _norm_msg(m):
    if not isinstance(m, dict):
        return None
    role = m.get("role") or m.get("from") or m.get("speaker")
    content = m.get("content") or m.get("value") or m.get("text")
    role = _ROLE_MAP.get(str(role).lower().strip()) if role is not None else None
    if not role or not isinstance(content, str) or not content.strip():
        return None
    return {"role": role, "content": content}

def _msgs_to_conv(msgs):
    out = []
    for m in (msgs or []):
        nm = _norm_msg(m)
        if nm:
            out.append(nm)
    return out

def adapt_wildchat(row):   # allenai/WildChat-1M -> `conversation` (already role/content)
    return _msgs_to_conv(row.get("conversation"))

def adapt_ultrachat(row):  # HuggingFaceH4/ultrachat_200k -> `messages`
    return _msgs_to_conv(row.get("messages"))

def adapt_sharegpt(row):   # ShareGPT-style -> `conversations` with from/value
    return _msgs_to_conv(row.get("conversations"))

def adapt_auto(row):
    """Best-effort: try common multi-turn fields, then single-turn prompt/response pairs."""
    for key in ("conversation", "messages", "conversations", "turns", "dialogue", "chat"):
        v = row.get(key)
        if isinstance(v, list):
            c = _msgs_to_conv(v)
            if c:
                return c
    for uk, ak in (("prompt", "response"), ("instruction", "output"), ("input", "output"),
                   ("question", "answer"), ("query", "response")):
        u = row.get(uk)
        if isinstance(u, str) and u.strip():
            conv = [{"role": "user", "content": u}]
            a = row.get(ak)
            if isinstance(a, str) and a.strip():
                conv.append({"role": "assistant", "content": a})
            return conv
    return []

DATASET_ADAPTERS = {"wildchat": adapt_wildchat, "ultrachat": adapt_ultrachat,
                    "sharegpt": adapt_sharegpt, "nemotron": adapt_auto, "auto": adapt_auto}

def _add_conversation(row, adapter_name):
    """Picklable map fn (usable with datasets.map num_proc>1) that adds a `conversation` column."""
    return {"conversation": DATASET_ADAPTERS.get(adapter_name, adapt_auto)(row)}


def is_valid_and_short(item):
    """Filters out empty conversations AND keeps user prompts <= 1000 words."""
    conversation = item.get("conversation", [])
    
    # 1. Filter out completely empty conversations
    if not conversation:
        return False
        
    # Extract user messages, ensuring they are strings
    user_messages = [
        msg["content"] for msg in conversation 
        if msg.get("role") == "user" and isinstance(msg.get("content"), str)
    ]
    
    # 2. Filter out conversations that don't have any user turns
    if not user_messages:
        return False
    
    # 3. Filter out conversations with more than 3 user turns
    if len(user_messages) > 3:
        return False
        
    # Calculate total words
    total_words = sum(len(msg.split()) for msg in user_messages)
    
    # 3. Ensure the word count is greater than 0 AND less than or equal to 1000
    return 0 < total_words <= 1000

def get_processed_ids(output_path: Path) -> set[int]:
    """Reads the output JSONL file and returns a set of already processed sample IDs."""
    processed_ids = set()
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if "id" in data:
                        processed_ids.add(data["id"])
                except json.JSONDecodeError:
                    continue  # Skip corrupted lines if the script crashed mid-write
    return processed_ids


async def process_dataset(config: dict) -> list[dict]:
    """Process the dataset and generate responses."""
    dataset_config = config["dataset"]
    processing_config = config["processing"]
    output_config = config["output"]

    # Load personas if enabled
    persona_config = config.get("persona", {})
    if persona_config.get("use_persona", False):
        persona_file = persona_config.get("file_path")
        personas = []
        if os.path.exists(persona_file):
            with open(persona_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        personas.append(json.loads(line.strip()))
            config["persona"]["loaded_personas"] = personas
            print(f"Loaded {len(personas)} personas from {persona_file}")

            matching_cfg = persona_config.get("matching", {})
            if matching_cfg.get("embedding_fallback", True):
                try:
                    from sentence_transformers import SentenceTransformer
                    print("Encoding personas for embedding fallback matching...")
                    model = SentenceTransformer('all-MiniLM-L6-v2')
                    config["persona"]["embedding_model"] = model
                    persona_texts = [
                        p.get("description") or p.get("character_description") or get_persona_characteristics_str(p)
                        for p in personas
                    ]
                    config["persona"]["persona_embeddings"] = model.encode(persona_texts, convert_to_tensor=True)
                    print("Done encoding personas.")
                except ImportError:
                    print("sentence-transformers not installed. Embedding fallback disabled; will use random sampling.")
        else:
            print(f"Warning: Persona file {persona_file} not found. Persona injection will be disabled.")
            config["persona"]["use_persona"] = False

    # Set random seed
    seed = processing_config["seed"]
    random.seed(seed)

    # Get checkpoint settings
    output_path = Path(output_config["path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    processed_ids = get_processed_ids(output_path)
    if processed_ids:
        print(f"Found {len(processed_ids)} already processed conversations. Resuming where we left off...")
    # Extra "already done" files: parallel-shard drivers seed their skip-set from the main output
    # (and each other) so no conversation is generated twice across shards. Env-gated; no-op if unset.
    for _extra in [p.strip() for p in os.environ.get("AUG_RESUME_FROM", "").split(",") if p.strip()]:
        _n0 = len(processed_ids)
        processed_ids |= get_processed_ids(Path(_extra))
        print(f"  + resume-from {_extra}: +{len(processed_ids) - _n0} ids (total {len(processed_ids)})")

    # --- Load one or more datasets: new `datasets:` list, or fall back to single `dataset:` ---
    # Each `datasets` entry: {name, split, adapter, num_samples[, source]}. Adapters normalise the
    # raw schema to WildChat's `conversation` shape so WildChat / UltraChat / Nemotron can be blended
    # in ONE run. IDs are namespaced per source (`source:idx`) so they never collide and resume works.
    from functools import partial
    dataset_specs = config.get("datasets")
    if not dataset_specs:
        dataset_specs = [{"name": dataset_config["name"], "split": dataset_config["split"],
                          "adapter": dataset_config.get("adapter", "wildchat"),
                          "num_samples": dataset_config["num_samples"]}]

    num_cores = os.cpu_count() or 1
    conversations = []  # list of (composite_id, conversation)
    for spec in dataset_specs:
        name = spec["name"]; split = spec.get("split", "train")
        source = spec.get("source") or name.split("/")[-1].lower().replace("-", "_")
        adapter_name = spec.get("adapter", "auto")
        want = spec.get("num_samples") or dataset_config.get("num_samples", 0)
        print(f"Loading dataset: {name} (split={split}, adapter={adapter_name}, source={source})...")
        ds = load_dataset(name, split=split)
        print(f"  original size: {len(ds)}")
        # normalise to a `conversation` column unless it is already WildChat-shaped
        if not (adapter_name == "wildchat" and "conversation" in ds.column_names):
            ds = ds.map(partial(_add_conversation, adapter_name=adapter_name),
                        num_proc=num_cores, desc=f"adapt:{source}")
        ds = ds.filter(is_valid_and_short, num_proc=num_cores)
        print(f"  filtered size: {len(ds)}")
        if len(ds) == 0:
            print(f"  WARNING: '{name}' produced 0 valid conversations: adapter '{adapter_name}' may "
                  f"not match its schema (cols: {ds.column_names}). Skipping.")
            continue
        k = min(want, len(ds)) if want else len(ds)
        idxs = random.sample(range(len(ds)), k)
        added = 0
        for idx in idxs:
            cid = f"{source}:{idx}"
            if cid in processed_ids:
                continue
            conv = ds[idx].get("conversation", [])
            if conv:
                conversations.append((cid, conv)); added += 1
        print(f"  sampled {k}, queued {added} new (rest already processed)")

    # Optional sharding for parallel single-core drivers: keep only this shard's disjoint slice
    # (partitioned by the numeric idx of the composite id). Env-gated; no-op if AUG_SHARD unset.
    _shard = os.environ.get("AUG_SHARD")
    if _shard:
        _si, _ns = (int(x) for x in _shard.split("/"))
        _before = len(conversations)
        conversations = [(cid, conv) for (cid, conv) in conversations
                         if int(cid.rsplit(":", 1)[-1]) % _ns == _si]
        print(f"SHARD {_si}/{_ns}: kept {len(conversations)}/{_before} conversations for this driver")

    print(f"Extracted {len(conversations)} un-processed conversations across {len(dataset_specs)} "
          f"dataset(s). {len(processed_ids)} already processed and will be skipped.")

    # Count total turns for progress reporting
    total_turns = sum(
        len([t for t in extract_conversation_turns(conv) if t["role"] == "user"])
        for _, conv in conversations
    )
    print(f"Total user turns to process: {total_turns}")

    # Setup async HTTP session and semaphore for concurrency control
    concurrency = processing_config["concurrency"]
    semaphore = asyncio.Semaphore(concurrency)

    connector = aiohttp.TCPConnector(limit=concurrency * 2)
    timeout = aiohttp.ClientTimeout(total=600)  # Increased timeout from 120 to 600 seconds

    results = []

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # NEW: Wrapper forces the whole conversation to wait in line
        async def process_with_limit(idx, conv):
            async with semaphore:
                return await process_conversation(session, conv, config, idx)
        
        tasks = [
            asyncio.create_task(process_with_limit(idx, conv))
            for idx, conv in conversations
        ]

        with tqdm_asyncio(total=len(tasks), desc="Processing conversations") as pbar:
            for coro in asyncio.as_completed(tasks):
                result = await coro
                results.append(result)
                
                # Append to file immediately instead of rewriting the whole file
                append_checkpoint(result, output_path)
                
                pbar.update(1)
                pbar.set_postfix({"completed": len(results)})

    return results


def print_stats(results: list[dict], output_path: str) -> None:
    """Print statistics about the results."""
    output_path = Path(output_path)

    # Helper to get metadata
    def get_meta(r):
        return r.get("metadata", {})

    def get_turns(r):
        return get_meta(r).get("turns_detail", [])

    # Compute stats
    total_conversations = len(results)
    total_turns = sum(len(get_turns(r)) for r in results)

    response_success = sum(
        1 for r in results for t in get_turns(r)
        if t.get("response_status") == "success"
    )
    response_error = sum(
        1 for r in results for t in get_turns(r)
        if t.get("response_status") == "error"
    )

    # Adaptation stats
    total_adaptations = sum(
        t.get("num_adaptations", 0)
        for r in results for t in get_turns(r)
    )
    turns_needing_adaptation = sum(
        1 for r in results for t in get_turns(r)
        if t.get("num_adaptations", 0) > 0
    )

    # Retry stats
    total_retries = sum(
        t.get("retry_count", 0)
        for r in results for t in get_turns(r)
    )
    turns_needing_retries = sum(
        1 for r in results for t in get_turns(r)
        if t.get("retry_count", 0) > 0
    )

    # Truncation stats
    truncated_conversations = sum(1 for r in results if get_meta(r).get("truncated", False))

    # Sanity check stats. Distinguish genuine fails from judge errors so
    # silent judge failures don't pollute the fail rate.
    sanity_pass_conversations = sum(
        1 for r in results if get_meta(r).get("sanity_status") == "pass"
        or (get_meta(r).get("sanity_status") is None and get_meta(r).get("sanity_pass", False))
    )
    sanity_fail_conversations = sum(
        1 for r in results if get_meta(r).get("sanity_status") == "fail"
    )
    sanity_error_conversations = sum(
        1 for r in results if get_meta(r).get("sanity_status") == "error"
    )

    # Per-turn sanity stats
    sanity_pass_turns = sum(
        1 for r in results for t in get_turns(r)
        if t.get("sanity_check", {}).get("verdict") == "pass"
    )
    sanity_fail_turns = sum(
        1 for r in results for t in get_turns(r)
        if t.get("sanity_check", {}).get("verdict") == "fail"
    )
    sanity_error_turns = sum(
        1 for r in results for t in get_turns(r)
        if t.get("sanity_check", {}).get("verdict") in ("error", "parse_error", "unknown")
    )

    # Persona stats
    persona_skip_reasons: dict[str, int] = {}
    persona_applied_turns = 0
    persona_changed_turns = 0
    persona_adapt_retry_turns = 0
    for r in results:
        for t in get_turns(r):
            if t.get("persona_applied"):
                persona_applied_turns += 1
            if t.get("persona_user_message_changed"):
                persona_changed_turns += 1
            if t.get("persona_adapt_attempts", 0) > 1:
                persona_adapt_retry_turns += 1
            reason = t.get("persona_skip_reason")
            if reason:
                # Bucket by prefix before ":" so we don't have a long tail of
                # unique error strings.
                key = reason.split(":", 1)[0]
                persona_skip_reasons[key] = persona_skip_reasons.get(key, 0) + 1

    # Count per responder
    responder_counts = {}
    for r in results:
        name = get_meta(r).get("responder", "unknown")
        if name:
            responder_counts[name] = responder_counts.get(name, 0) + 1

    # Turn distribution
    turn_counts = {}
    for r in results:
        num_turns = get_meta(r).get("num_turns", 0)
        turn_counts[num_turns] = turn_counts.get(num_turns, 0) + 1

    print(f"\nResults saved to: {output_path}")
    print(f"\nConversations: {total_conversations}, Total turns: {total_turns}")
    print(f"Truncated conversations: {truncated_conversations}")
    print(f"Response stats: {response_success} success, {response_error} errors")
    print(f"Retry stats: {turns_needing_retries} turns retried, {total_retries} total retries")
    print(f"Adaptation stats: {turns_needing_adaptation} turns adapted, {total_adaptations} total adaptation attempts")
    print(f"Sanity check stats (conversations): {sanity_pass_conversations} pass, {sanity_fail_conversations} fail, {sanity_error_conversations} error")
    print(f"Sanity check stats (turns): {sanity_pass_turns} pass, {sanity_fail_turns} fail, {sanity_error_turns} error/unknown")
    print(f"\nPersona stats (turns): {persona_applied_turns} applied, {persona_changed_turns} user-message rewritten, {persona_adapt_retry_turns} required retries")
    if persona_skip_reasons:
        print("Persona skip reasons:")
        for reason, count in sorted(persona_skip_reasons.items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count}")
    print(f"\nResponder distribution:")
    for name, count in sorted(responder_counts.items()):
        print(f"  {name}: {count} conversations")
    print(f"\nTurns per conversation:")
    for num_turns, count in sorted(turn_counts.items()):
        print(f"  {num_turns} turns: {count} conversations")

# literal translation step (cross-lingual mode only)
TRANSLATION_GEN = {"max_tokens": 4096, "temperature": 0.3, "top_p": 0.95}


def translation_prompt(message, language):
    extra = ("Use natural contemporary written Swiss German (Schweizerdeutsch), not Standard German. "
             "Swiss German has variable spelling; do not manufacture accent caricatures. "
             if language == "Swiss German" else "Use natural contemporary " + language + ". ")
    return ("Translate the following user message into " + language + ". " + extra +
            "\nTranslate the request, do NOT answer it. Preserve all requirements and details. "
            "Keep code, URLs, paths, numbers, named entities, and text explicitly requested verbatim unchanged. "
            "Preserve the language of quoted translation payloads and any explicitly requested output language. "
            "Do not add facts, extra requests, explanations, or a translation preamble. "
            "Output only the translated user message.\n\nUSER MESSAGE:\n" + message)


async def translate_turn(session, config, message, language):
    """Persona-blind literal translation by the responder named "gemma". Raises if no valid translation
    after 3 tries."""
    gemmas = [r for r in config["responders"] if r["name"] == "gemma"]
    masked, span_map = integrity.protect(message)
    prompt = translation_prompt(masked, language)
    if span_map:
        prompt += "\n\n" + integrity.protection_instruction().strip()
    last = None
    for attempt in range(3):
        text, err = await call_api(session, random.choice(gemmas), TRANSLATION_GEN,
                                   [{"role": "user", "content": prompt}], error_prefix="TRANSLATE", is_judge=False)
        if not text or err:
            last = f"empty_or_error: {err}"
            continue
        try:
            text = sanitize_constitution(integrity.restore(text.strip(), span_map))
        except ValueError:
            last = "literal_integrity: protected span missing or duplicated"
            continue
        if span_map and not integrity.audit(message, text, sanitize_constitution)["policy_intact"]:
            last = "literal_integrity"
            continue
        if not config["_lang_ok"](text, language):
            last = "wrong_language"
            continue
        return text
    raise RuntimeError(f"translation_failed: {last}")
