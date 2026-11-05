#!/usr/bin/env python3
"""Emoji rebalancing of the persona bank: keep frequent emoji use for 5% of profiles.

Frequent-emoji personas are ranked by sha256(salt + id); the lowest-ranked 5% of the bank stay
frequent, the rest are set to emoji_use "none". For each downgraded persona, every profile field
that mentions emoji (emoji characters or the words emoji/emoticon/smiley/kaomoji/sticker) is
minimally rewritten by an LLM (Gemma 4 31B, offline vLLM) so the profile no longer describes emoji
use; example_message is stripped deterministically. Rewrites are validated; failures fall back to
a rule-based scrub.

Two stages, run one after the other (each loads the model once):
  fix     write the rebalanced bank (--out) and a per-persona change log (--log)
  repair  restore fields whose only match was "sticker" (physical stickers, not messaging), and
          re-edit rule-scrubbed personas with a relaxed length check; if the model still fails,
          a "None" left by the rule scrub is replaced by a clause-level scrub. Rewrites --bank and
          --log in place, re-deriving every edited field from the unedited bank (--orig).

Usage:
    python -m personafactory.persona_bank.rebalance_emoji fix --bank persona_bank_all.clean.jsonl \
        --out persona_bank.jsonl --log persona_emoji_changes.jsonl --model google/gemma-4-31B-it
    python -m personafactory.persona_bank.rebalance_emoji repair --orig persona_bank_all.clean.jsonl \
        --bank persona_bank.jsonl --log persona_emoji_changes.jsonl --model google/gemma-4-31B-it
"""
import argparse, copy, hashlib, json, re

# Hash salt of the keep ranking; it fixes which personas stay frequent in the released bank.
KEEP_SALT = 'emoji-keep:'

# Pictographic emoji only. Plain dingbats and symbols (✓ ✔ ★ → ✗) are left alone because users
# type them in lists and specs; symbols from those blocks count only with the emoji selector
# U+FE0F or when they are in the common-emoji set below.
_COMMON = '✨✅❌❤⭐☕⚡✌✊✋☺⌛⏳⏰☀☁⛔⚽❗❓⚠♥☹'
EMOJI = re.compile('(?:[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\U0001F000-\U0001F2FF' + _COMMON + ']'
                   '|[☀-➿⬀-⯿]️)'
                   '[\U0001F3FB-\U0001F3FF️‍⃣]*(?:‍[\U0001F300-\U0001FAFF☀-➿]️?)*')
EMOJI_WORD = re.compile(r'emoji|emoticon|smiley|kaomoji|sticker', re.I)
TEXT_KEYS = ('chatting_style', 'code_switching_type', 'chatbot_language_pref',
             'native_language_error_patterns', 'question_framing')
STRUCT_KEYS = ('greeting_signoff', 'punctuation', 'abbreviation_habits', 'message_structure',
               'typo_tendency', 'capitalization')
LIST_KEYS = ('linguistic_quirks', 'reference_pool')


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


def mentions(text):
    return bool(text) and bool(EMOJI.search(text) or EMOJI_WORD.search(text))


def affected_fields(p):
    s = p.get('style') or {}
    cs = s.get('chatting_style_structured') or {}
    f = {}
    for k in TEXT_KEYS:
        if isinstance(s.get(k), str) and mentions(s[k]):
            f['style.' + k] = s[k]
    for k in STRUCT_KEYS:
        if isinstance(cs.get(k), str) and mentions(cs[k]):
            f['style.chatting_style_structured.' + k] = cs[k]
    for k in LIST_KEYS:
        v = s.get(k)
        if isinstance(v, list) and any(isinstance(x, str) and mentions(x) for x in v):
            f['style.' + k] = v
    if isinstance(p.get('character_description'), str) and mentions(p['character_description']):
        f['character_description'] = p['character_description']
    for k, v in (p.get('background') or {}).items():
        if isinstance(v, str) and mentions(v):
            f['background.' + k] = v
        elif isinstance(v, list) and any(isinstance(x, str) and mentions(x) for x in v):
            f['background.' + k] = v
    return f


PROMPT = """You are editing a synthetic persona profile. This person must NOT use emoji, emoticons, kaomoji or stickers in their messages.

Edit the JSON fields below with the SMALLEST possible change:
- Remove every emoji character.
- Delete or rephrase any phrase that says the person uses emoji, emoticons, smileys, kaomoji or stickers, so the text no longer mentions them at all. Do not replace it with a statement like "no emoji".
- Keep every other word, fact, example and language exactly as it is. Keep the same language as the original text.
- For list values: drop items that are only about emoji; for mixed items, edit only the emoji part. Keep all other items unchanged and in order.
- A string field that would become empty must be "None".
- Keep the result grammatical.

Return ONLY a JSON object with exactly the same keys, and the same value types (string or list of strings).

FIELDS:
{fields}"""


def valid(orig, new):
    if not isinstance(new, dict) or set(new) != set(orig):
        return False
    for k, v in orig.items():
        n = new[k]
        if isinstance(v, list):
            if not isinstance(n, list) or not all(isinstance(x, str) and x.strip() for x in n):
                return False
            if len(n) > len(v) or any(mentions(x) for x in n):
                return False
        else:
            if not isinstance(n, str) or not n.strip() or mentions(n):
                return False
            # guard against rewriting beyond the emoji mention
            if len(v) > 120 and len(n) < 0.5 * len(v):
                return False
            if len(n) > 1.2 * len(v) + 20:
                return False
    return True


def rule_scrub(v):
    """Fallback: strip emoji; drop sentences/clauses or list items that mention emoji words."""
    if isinstance(v, list):
        return [strip_emoji(x) for x in v if isinstance(x, str) and not EMOJI_WORD.search(x)
                and strip_emoji(x).strip()]
    parts = re.split(r'(?<=[.;!?])\s+', v)
    kept = [strip_emoji(x) for x in parts if not EMOJI_WORD.search(x)]
    out = ' '.join(x for x in kept if x.strip()).strip()
    return out or 'None'


def put(p, path, value):
    keys = path.split('.')
    d = p
    for k in keys[:-1]:
        d = d[k]
    d[keys[-1]] = value


def parse_json(text):
    text = (text or '').strip()
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text)
    a, b = text.find('{'), text.rfind('}')
    return json.loads(text[a:b + 1]) if a >= 0 and b > a else None


def run_fix(args):
    bank = [json.loads(l) for l in open(args.bank, encoding='utf-8') if l.strip()]
    freq = [p for p in bank if tier(((p.get('style') or {}).get('chatting_style_structured') or {})
                                     .get('emoji_use')) == 'frequent']
    keep_n = round(args.target_share * len(bank))
    freq.sort(key=lambda p: hashlib.sha256((KEEP_SALT + p['id']).encode()).hexdigest())
    keep = {p['id'] for p in freq[:keep_n]}
    down = [p for p in freq if p['id'] not in keep]
    print(f'bank {len(bank)} frequent {len(freq)} keep {len(keep)} downgrade {len(down)}', flush=True)

    jobs = []
    for p in down:
        f = affected_fields(p)
        f.pop('style.example_message', None)
        if f:
            jobs.append((p, f))
    print(f'personas needing LLM field edits: {len(jobs)}', flush=True)

    from vllm import LLM, SamplingParams
    llm = LLM(model=args.model, tensor_parallel_size=args.tensor_parallel_size, max_model_len=8192,
              gpu_memory_utilization=0.9, max_num_seqs=256)
    results = {}
    pending = list(range(len(jobs)))
    for attempt in range(3):
        if not pending:
            break
        sp = SamplingParams(temperature=0.0 if attempt == 0 else 0.5, max_tokens=3072, seed=attempt)
        convs = [[{'role': 'user', 'content': PROMPT.format(
            fields=json.dumps(jobs[i][1], ensure_ascii=False, indent=1))}] for i in pending]
        outs = llm.chat(convs, sp, use_tqdm=False)
        nxt = []
        for i, o in zip(pending, outs):
            try:
                new = parse_json(o.outputs[0].text)
            except Exception:
                new = None
            if valid(jobs[i][1], new):
                results[i] = ('llm', new)
            else:
                nxt.append(i)
        pending = nxt
        print(f'attempt {attempt}: {len(results)} valid, {len(pending)} pending', flush=True)
    for i in pending:
        results[i] = ('rule', {k: rule_scrub(v) for k, v in jobs[i][1].items()})

    edits = {}
    for i, (p, f) in enumerate(jobs):
        edits[p['id']] = (results[i][0], f, results[i][1])
    down_ids = {p['id'] for p in down}
    n_llm = n_rule = 0
    with open(args.out, 'w', encoding='utf-8') as fo, open(args.log, 'w', encoding='utf-8') as fl:
        for p in bank:
            if p['id'] in down_ids:
                q = copy.deepcopy(p)
                s = q.setdefault('style', {})
                cs = s.setdefault('chatting_style_structured', {})
                change = {'id': p['id'], 'emoji_use': [cs.get('emoji_use'), 'none']}
                cs['emoji_use'] = 'none'
                if s.get('example_message'):
                    ex = strip_emoji(s['example_message'])
                    if ex != s['example_message']:
                        change['example_message'] = [s['example_message'], ex]
                        s['example_message'] = ex
                if p['id'] in edits:
                    how, before, after = edits[p['id']]
                    for k, v in after.items():
                        put(q, k, v)
                    change.update(method=how, fields={k: [before[k], after[k]] for k in before})
                    n_llm += how == 'llm'; n_rule += how == 'rule'
                q.setdefault('validation', {})['emoji_downgrade'] = {
                    'from': change['emoji_use'][0], 'to': 'none'}
                fl.write(json.dumps(change, ensure_ascii=False) + '\n')
                p = q
            fo.write(json.dumps(p, ensure_ascii=False) + '\n')
    print(json.dumps({'bank': len(bank), 'frequent_before': len(freq), 'kept_frequent': len(keep),
                      'downgraded': len(down), 'field_edits_llm': n_llm, 'field_edits_rule': n_rule,
                      'frequent_share_after_pct': round(100 * len(keep) / len(bank), 2)}), flush=True)


# ---------------------------------------------------------------- repair stage
# Same as EMOJI_WORD without "sticker": a sticker-only match is a physical sticker.
WORD_NO_STICKER = re.compile(r'emoji|emoticon|smiley|kaomoji', re.I)


def mentions_repair(t):
    return bool(t) and bool(EMOJI.search(t) or WORD_NO_STICKER.search(t))


def any_mention(v):
    return any(mentions_repair(x) for x in v) if isinstance(v, list) else mentions_repair(v)


def relaxed_valid(orig, new):
    if not isinstance(new, dict) or set(new) != set(orig):
        return False
    for k, v in orig.items():
        n = new[k]
        if isinstance(v, list):
            if not isinstance(n, list) or len(n) > len(v) or any(not isinstance(x, str) or mentions_repair(x) for x in n):
                return False
        elif not isinstance(n, str) or not n.strip() or mentions_repair(n) or len(n) > 1.2 * len(v) + 20:
            return False
    return True


def clause_scrub(v):
    parts = re.split(r'(?<=[,.;])\s+|\s+(?:and|but|with)\s+', v)
    kept = [strip_emoji(p).strip(' ,;') for p in parts if not WORD_NO_STICKER.search(p)]
    out = ', '.join(p for p in kept if p)
    return (out[0].upper() + out[1:] + ('' if out.endswith('.') else '.')) if out else 'None'


def run_repair(args):
    changes = {}
    for l in open(args.log, encoding='utf-8'):
        c = json.loads(l)
        changes[c['id']] = c
    orig = {}
    for l in open(args.orig, encoding='utf-8'):
        p = json.loads(l)
        if p['id'] in changes:
            orig[p['id']] = p

    restored, redo = 0, []
    for pid, c in changes.items():
        fields = c.get('fields') or {}
        for k in list(fields):
            before, _ = fields[k]
            if not any_mention(before):          # sticker-only match: restore
                fields.pop(k)
                restored += 1
        if c.get('method') == 'rule' and fields:
            redo.append(pid)
        if not fields:
            c.pop('fields', None)
            c.pop('method', None)
    print(f'restored {restored} sticker-only fields; re-editing {len(redo)} rule personas', flush=True)

    from vllm import LLM, SamplingParams
    llm = LLM(model=args.model, tensor_parallel_size=args.tensor_parallel_size, max_model_len=8192, gpu_memory_utilization=0.9)
    pending, done = list(redo), {}
    for attempt in range(6):
        if not pending:
            break
        sp = SamplingParams(temperature=0.0 if attempt == 0 else 0.7, max_tokens=3072, seed=100 + attempt)
        convs = [[{'role': 'user', 'content': PROMPT.format(fields=json.dumps(
            {k: v[0] for k, v in changes[pid]['fields'].items()}, ensure_ascii=False, indent=1))}] for pid in pending]
        nxt = []
        for pid, o in zip(pending, llm.chat(convs, sp, use_tqdm=False)):
            src = {k: v[0] for k, v in changes[pid]['fields'].items()}
            try:
                new = parse_json(o.outputs[0].text)
            except Exception:
                new = None
            if relaxed_valid(src, new):
                done[pid] = new
            else:
                nxt.append(pid)
        pending = nxt
        print(f'attempt {attempt}: {len(done)} ok, {len(pending)} pending', flush=True)
    for pid in redo:
        c = changes[pid]
        if pid in done:
            c['method'] = 'llm_repair'
            for k, v in done[pid].items():
                c['fields'][k][1] = v
        else:
            c['method'] = 'rule_clause'
            for k, (before, after) in c['fields'].items():
                if isinstance(before, str) and after == 'None':
                    c['fields'][k][1] = clause_scrub(before)

    n = 0
    with open(args.bank, encoding='utf-8') as f:
        rows = [json.loads(l) for l in f if l.strip()]
    for p in rows:
        pid = p['id']
        if pid not in changes:
            continue
        o = orig[pid]
        # re-derive every edited field from the original plus the final change set
        for k in ('character_description',):
            p[k] = o.get(k)
        p['background'] = json.loads(json.dumps(o.get('background')))
        s, os_ = p['style'], o['style']
        for k, v in os_.items():
            if k in ('chatting_style_structured', 'example_message'):
                continue
            s[k] = json.loads(json.dumps(v))
        for k, v in os_.get('chatting_style_structured', {}).items():
            if k != 'emoji_use':
                s['chatting_style_structured'][k] = v
        for k, (_, after) in (changes[pid].get('fields') or {}).items():
            put(p, k, after)
        n += 1
    with open(args.bank, 'w', encoding='utf-8') as f:
        for p in rows:
            f.write(json.dumps(p, ensure_ascii=False) + '\n')
    with open(args.log, 'w', encoding='utf-8') as f:
        for c in changes.values():
            f.write(json.dumps(c, ensure_ascii=False) + '\n')
    methods = {}
    for c in changes.values():
        methods[c.get('method')] = methods.get(c.get('method'), 0) + 1
    print(json.dumps({'personas_rebuilt': n, 'methods': methods, 'sticker_fields_restored': restored}), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='stage', required=True)
    f = sub.add_parser('fix', help='rebalance and write --out / --log')
    f.add_argument('--bank', required=True, help='input bank (the clean judged bank)')
    f.add_argument('--out', required=True, help='rebalanced bank')
    f.add_argument('--log', required=True, help='per-persona change log (JSONL)')
    f.add_argument('--model', required=True, help='rewrite model (path or id), e.g. google/gemma-4-31B-it')
    f.add_argument('--target-share', type=float, default=0.05)
    f.add_argument('--tensor-parallel-size', type=int, default=4)
    r = sub.add_parser('repair', help='repair pass over the fix output (in place)')
    r.add_argument('--orig', required=True, help='the unedited input bank of the fix stage')
    r.add_argument('--bank', required=True, help='the fix-stage output, rewritten in place')
    r.add_argument('--log', required=True, help='the fix-stage change log, rewritten in place')
    r.add_argument('--model', required=True)
    r.add_argument('--tensor-parallel-size', type=int, default=4)
    args = ap.parse_args()
    run_fix(args) if args.stage == 'fix' else run_repair(args)


if __name__ == '__main__':
    main()
