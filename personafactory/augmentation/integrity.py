"""Literal protection for user-turn rewrites and translations.

protect() masks quoted text, code, URLs, paths, numbers and snake_case identifiers with opaque
PFSPAN_<hash>_<i>_END markers; restore() puts them back and raises if a marker was lost, duplicated or
invented; audit() checks that every protected span of the source survives in the output (modulo the
typographic sanitizer). Used by augmentation.pipeline.
"""
from collections import Counter
import hashlib
import re

# Prefer whole spans before subspans; apostrophes within words are not quotations.
PATTERN = re.compile(
    r'```[^\n]*\n.*?```|~~~[^\n]*\n.*?~~~|`[^`\n]+`'
    r'|https?://[^\s<>"\)\]]+'
    r'|(?<!\w)(?:/[A-Za-z0-9_.-]+){2,}(?:\.[A-Za-z0-9]+)?'
    r'|"[^"\n]+"|“[^”\n]+”|«[^»\n]+»|「[^」\n]+」'
    r"|(?<!\w)'[^'\n]+'(?!\w)"
    r'|(?<!\w)[+-]?\d+(?:[.,:/-]\d+)*(?:%|[kKmMbB](?!\w))?'
    r'|\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+\b', re.DOTALL)
TOKEN = re.compile(r'PFSPAN_[0-9a-f]{12}_[0-9]+_END', re.I)


def spans(text):
    return [m.group(0) for m in PATTERN.finditer(text)]


def protect(text):
    if re.search(r'PFSPAN_', text, re.I):
        raise ValueError('Source already contains reserved protection tokens')
    prefix = hashlib.sha256(text.encode()).hexdigest()[:12]
    mapping = {}
    def replace(match):
        marker = f'PFSPAN_{prefix}_{len(mapping)}_END'
        mapping[marker] = match.group(0)
        return marker
    return PATTERN.sub(replace, text), mapping


def restore(text, mapping):
    seen = Counter(token.upper() for token in TOKEN.findall(text))
    expected = Counter(token.upper() for token in mapping)
    if seen != expected:
        raise ValueError('Missing, duplicated or invented protected tokens')
    upper = {token.upper(): value for token, value in mapping.items()}
    restored = TOKEN.sub(lambda m: upper[m.group(0).upper()], text)
    if re.search(r'PFSPAN_', restored, re.I):
        raise ValueError('Leaked or invented protection-marker instruction')
    return restored


def audit(source, output, sanitizer):
    originals = spans(source)
    required = Counter(originals)
    raw_missing = [token for token, n in required.items() if output.count(token) < n]
    normalized = Counter(sanitizer(token) for token in originals)
    # An unchanged strict-task bypass is intact too. Match both raw and normalized
    # forms without counting the same occurrence twice when normalization merges
    # two distinct source strings.
    variants = sorted(set(required) | set(normalized), key=lambda t: (-len(t), t))
    observed = Counter(sanitizer(m.group(0)) for m in re.finditer(
        '|'.join(re.escape(t) for t in variants), output)) if variants else Counter()
    missing = [token for token, n in normalized.items() if observed[token] < n]
    return {'protected_spans': len(originals), 'raw_intact': not raw_missing,
            'policy_intact': not missing, 'raw_missing': raw_missing,
            'policy_missing': missing,
            'dash_policy_exceptions': [t for t in originals if sanitizer(t) != t and t in raw_missing],
            'dash_policy_applicable': [t for t in originals if sanitizer(t) != t],
            'policy': 'sanitizer_retained; raw differences are not hidden'}


def protection_instruction():
    return (' Opaque PFSPAN_*_END markers stand for protected original content. '
            'Keep EVERY marker exactly once and unchanged. Do not answer, translate, '
            'spell out or explain a marker; it is restored afterward. ')
