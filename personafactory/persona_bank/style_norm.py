"""Normalization helpers for the structured typing keys and free-text fields.

`canon_style` maps the free-string values of `chatting_style_structured` onto the canonical
vocabulary suggested in the generation prompt (plus "other"), and binarizes the two open keys
(abbreviation_habits, greeting_signoff) into none / some. Used by the generator (typing-style seed
check on the extended grid) and by the diversity filter, so both use the same buckets.
"""
import re
import unicodedata

STYLE_KEYS = ("capitalization", "punctuation", "emoji_use", "abbreviation_habits",
              "message_structure", "typo_tendency", "greeting_signoff")

_WS = re.compile(r"\s+")


def light_norm(s):
    """Lowercase, NFKC, collapse whitespace, strip surrounding punctuation."""
    s = unicodedata.normalize("NFKC", str(s or "")).lower().strip()
    s = _WS.sub(" ", s)
    return s.strip(" .;:,!-\"'")


def text_norm(s):
    """Aggressive normalization for duplicate detection: drop punctuation/symbols, collapse ws."""
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    s = "".join(" " if unicodedata.category(ch)[0] in "PSZC" else ch for ch in s)
    return _WS.sub(" ", s).strip()


def _has(s, *needles):
    return any(n in s for n in needles)


def _is_none(s):
    return (not s) or s in ("none", "no", "n/a", "na", "-", "nothing", "never") or \
        s.startswith(("none", "no abbreviation", "no greeting", "no sign", "rarely any", "does not use",
                      "doesn't use", "never uses", "no ")) and len(s) < 60


# Canonical labels as written in the generation prompt; a value that starts with one of these
# prefixes is mapped directly, everything else falls through to keyword rules.
_PREFIX = {
    "capitalization": [("standard", "Standard"), ("all lowercase", "all lowercase"),
                       ("first-word-only", "first-word-only"), ("inconsistent", "inconsistent"),
                       ("all-caps", "ALL-CAPS for emphasis")],
    "punctuation": [("standard", "standard"), ("minimal", "minimal"), ("ellipsis", "ellipsis-heavy"),
                    ("excessive", "excessive"), ("emoji or line-breaks", "emoji/line-breaks"),
                    ("line-breaks", "emoji/line-breaks")],
    "emoji_use": [("none", "none"), ("rare", "rare/functional"), ("frequent", "frequent/decorative"),
                  ("emoticons", "emoticons only"), ("kaomoji", "kaomoji/stickers")],
    "message_structure": [("terse", "terse one-liners"), ("medium", "medium complete"),
                          ("long", "long/elaborate"), ("fragmented", "fragmented")],
    "typo_tendency": [("clean", "clean"), ("occasional", "occasional typos"), ("phonetic", "phonetic"),
                      ("voice", "voice-to-text/autocorrect")],
}


def _prefix(key, s):
    for p, lab in _PREFIX.get(key, []):
        if s.startswith(p):
            return lab
    return None


def canon_capitalization(v):
    s = light_norm(v)
    hit = _prefix("capitalization", s)
    if hit:
        return hit
    if _has(s, "all lowercase", "all-lowercase", "lowercase", "lower case", "lower-case"):
        return "all lowercase"
    if _has(s, "all-caps", "all caps", "allcaps", "uppercase", "upper case", "caps for", "caps"):
        return "ALL-CAPS for emphasis"
    if _has(s, "first-word", "first word", "first letter only", "no final period"):
        return "first-word-only"
    if _has(s, "inconsistent", "random", "mixed", "sporadic", "erratic", "irregular", "varies"):
        return "inconsistent"
    if _has(s, "standard", "proper", "normal", "sentence case", "correct", "conventional", "formal"):
        return "Standard"
    return "other"


def canon_punctuation(v):
    s = light_norm(v)
    hit = _prefix("punctuation", s)
    if hit:
        return hit
    if _has(s, "ellipsis", "ellipses", "...", "\u2026"):
        return "ellipsis-heavy"
    if _has(s, "excessive", "!!!", "???", "multiple exclamation", "repeated", "lots of"):
        return "excessive"
    if _has(s, "emoji", "line-break", "line break", "linebreak", "newline"):
        return "emoji/line-breaks"
    if _has(s, "minimal", "drop", "no end", "omit", "sparse", "missing", "none", "little", "rarely", "skips", "light"):
        return "minimal"
    if _has(s, "standard", "proper", "correct", "full", "normal", "careful", "precise", "formal", "complete"):
        return "standard"
    return "other"


def canon_emoji(v):
    s = light_norm(v)
    hit = _prefix("emoji_use", s)
    if hit:
        return hit
    if _has(s, "kaomoji", "sticker"):
        return "kaomoji/stickers"
    if _has(s, "emoticon", ":)", ":-)", ":d", "^^", "xd"):
        return "emoticons only"
    if _has(s, "frequent", "decorative", "heavy", "lots", "many", "often", "abundant"):
        return "frequent/decorative"
    if _has(s, "rare", "functional", "occasional", "sparing", "sometimes", "minimal", "light", "few"):
        return "rare/functional"
    if _is_none(s) or _has(s, "never", "no emoji"):
        return "none"
    return "other"


def canon_structure(v):
    s = light_norm(v)
    hit = _prefix("message_structure", s)
    if hit:
        return hit
    if _has(s, "fragment", "several short", "multiple short", "multiple lines", "split", "across lines",
            "several lines", "bursts", "multiple messages"):
        return "fragmented"
    if _has(s, "terse", "one-liner", "one liner", "very short", "brief"):
        return "terse one-liners"
    if _has(s, "long", "elaborate", "detailed", "paragraph", "lengthy"):
        return "long/elaborate"
    if _has(s, "medium", "complete", "moderate", "full sentence"):
        return "medium complete"
    if s.startswith("short"):
        return "terse one-liners"
    return "other"


def canon_typo(v):
    s = light_norm(v)
    hit = _prefix("typo_tendency", s)
    if hit:
        return hit
    if _has(s, "voice", "autocorrect", "auto-correct", "predictive", "dictation"):
        return "voice-to-text/autocorrect"
    if _has(s, "phonetic"):
        return "phonetic"
    if _has(s, "no typo", "proofread", "proof-read", "clean", "careful", "rarely makes"):
        return "clean"
    if _has(s, "occasional", "uncorrected", "typo", "frequent", "sloppy", "some ", "errors"):
        return "occasional typos"
    if _has(s, "rare", "none", "minimal", "few"):
        return "clean"
    return "other"


def canon_open(v):
    s = light_norm(v)
    return "none" if _is_none(s) else "some"


CANON_FUNCS = {
    "capitalization": canon_capitalization,
    "punctuation": canon_punctuation,
    "emoji_use": canon_emoji,
    "abbreviation_habits": canon_open,
    "message_structure": canon_structure,
    "typo_tendency": canon_typo,
    "greeting_signoff": canon_open,
}


def canon_style(structured):
    """Tuple of canonical buckets in STYLE_KEYS order."""
    structured = structured or {}
    return tuple(CANON_FUNCS[k](structured.get(k) or "") for k in STYLE_KEYS)


def style_string(style):
    """Text used to embed the style layer: chatting_style + structured keys + quirks."""
    cs = style.get("chatting_style_structured") or {}
    keys = "; ".join(f"{k}: {cs.get(k, '')}" for k in STYLE_KEYS)
    quirks = "; ".join(style.get("linguistic_quirks") or [])
    return f"{style.get('chatting_style', '')} | {keys} | {quirks}"


# ---------------------------------------------------------------------------
# main_language canonicalization (the generator is asked for a canonical name but returns variants
# such as "Chinese", "Mandarin", "Bahasa Indonesia", "Filipino (Tagalog)").
# ---------------------------------------------------------------------------
LANG_ALIASES = {
    "chinese": "Mandarin Chinese", "mandarin": "Mandarin Chinese", "chinese mandarin": "Mandarin Chinese",
    "chinese, mandarin": "Mandarin Chinese", "standard chinese": "Mandarin Chinese",
    "traditional chinese": "Mandarin Chinese", "chinese (mandarin)": "Mandarin Chinese",
    "chinese (mandarin, standard)": "Mandarin Chinese",
    "bangla": "Bengali", "bengali (bangla)": "Bengali", "bangladesh": "Bengali",
    "slovene": "Slovenian", "slovenčina": "Slovak", "sinhalese": "Sinhala",
    "bahasa indonesia": "Indonesian", "bahasa indonesian": "Indonesian",
    "bahasa malaysia": "Malay", "bahasa melayu": "Malay", "malay (bahasa melayu)": "Malay",
    "filipino (tagalog)": "Filipino", "tagalog": "Filipino", "filipino (taglish)": "Filipino",
    "persian (farsi)": "Persian", "farsi": "Persian", "afaan oromo": "Oromo", "afaan oromoo": "Oromo",
    "afan oromo": "Oromo", "norwegian bokmål": "Norwegian", "bokmål": "Norwegian",
    "norwegian (bokmål)": "Norwegian", "bokmål norwegian": "Norwegian", "norsk": "Norwegian",
    "nynorsk": "Norwegian", "european portuguese": "Portuguese", "português": "Portuguese",
    "portuguese (european)": "Portuguese", "portuguese (br)": "Portuguese", "deutsch": "German",
    "swiss german": "German", "german (swiss standard)": "German", "german (swiss)": "German",
    "română": "Romanian", "român": "Romanian", "myanmar": "Burmese", "burma": "Burmese",
    "burmes": "Burmese", "burma (burmese)": "Burmese", "bamar": "Burmese", "panjabi": "Punjabi",
    "modern greek": "Greek", "modern standard greek": "Greek", "luxembourish": "Luxembourgish",
    "luxembourgesch": "Luxembourgish", "luxembourgish (letzebuergesch)": "Luxembourgish",
    "dutch (flemish)": "Dutch", "flemish": "Dutch", "netherlands": "Dutch", "korean (hangul)": "Korean",
    "darija": "Arabic", "arabic (darija)": "Arabic", "modern standard arabic": "Arabic",
    "arabic (standard)": "Arabic", "lebanese arabic": "Arabic", "arabic (moroccan darija)": "Arabic",
    "amarigna": "Amharic", "akan": "Twi", "binisaya": "Cebuano", "urdū": "Urdu", "pakistani urdu": "Urdu",
    "roman urdu": "Urdu", "central thai": "Thai", "thai (siamese)": "Thai",
}


def canon_language(v):
    s = light_norm(v)
    if not s:
        return ""
    if s in LANG_ALIASES:
        return LANG_ALIASES[s]
    if s.startswith("english"):
        return "English"
    if s.endswith(" english"):
        return "English"
    if s.startswith(("montenegrin", "bosnian/", "serbo-croatian")):
        return "Montenegrin" if s.startswith("montenegrin") else "Serbo-Croatian"
    base = re.sub(r"\s*\(.*\)$", "", s).strip()
    if base in LANG_ALIASES:
        return LANG_ALIASES[base]
    return base.title()
