"""Emoji helpers shared by the release scripts (same definitions as the persona-bank emoji rebalancing).

EMOJI matches pictographic emoji only; plain dingbats and symbols are counted only with the emoji selector
U+FE0F or when they are in the common-emoji set. tier() maps a bank `emoji_use` string to
none / rare / emoticons / frequent / unknown; strip_emoji() removes emoji and tidies whitespace.
"""
import re

# Pictographic emoji only. Plain dingbats and symbols (✓ ✔ ★ → ✗) are left alone because users
# type them in lists and specs; symbols from those blocks count only with the emoji selector
# U+FE0F or when they are in the common-emoji set below.
_COMMON = '✨✅❌❤⭐☕⚡✌✊✋☺⌛⏳⏰☀☁⛔⚽❗❓⚠♥☹'
EMOJI = re.compile('(?:[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\U0001F000-\U0001F2FF' + _COMMON + ']'
                   '|[☀-➿⬀-⯿]️)'
                   '[\U0001F3FB-\U0001F3FF️‍⃣]*(?:‍[\U0001F300-\U0001FAFF☀-➿]️?)*')


def tier(raw):
    raw = (raw or '').lower()
    if not raw:
        return 'unknown'
    if 'none' in raw or 'never' in raw:
        return 'none'
    if any(k in raw for k in ('rare', 'occasional', 'functional')):
        return 'rare'
    if 'emoticon' in raw:
        return 'emoticons'
    return 'frequent'


def strip_emoji(text, keep=()):
    """Remove emoji (keeping any in `keep`), then tidy the whitespace left behind."""
    if not text:
        return text
    out = EMOJI.sub(lambda m: m.group(0) if m.group(0) in keep else '', text)
    if out == text:
        return text
    out = re.sub(r'[ \t]+([,.!?;:…])', r'\1', out)
    out = re.sub(r'[ \t]{2,}', ' ', out)
    lines = [ln.rstrip() for ln in out.split('\n')]
    orig_lines = text.split('\n')
    # drop lines that only held emoji; keep intentionally blank lines
    lines = [ln for ln, o in zip(lines, orig_lines) if ln.strip() or not o.strip()]
    return '\n'.join(lines).strip()
