#!/usr/bin/env python3
"""Instruction-echo / persona-name leak filter for the regenerated assistant side.

A reply leaks when it contains a phrase that echoes the hidden style instructions (a model-persona name, a
"<name>-style" label, the "optional touch" wording, a "(no sign-off" aside, ...) that no user message of the
conversation contains. The arms without a model persona in the prompt (default, user_persona) give the natural
base rate of each phrase, so only phrases over-represented in user_persona_model_persona are treated as leaks.
Persona names are read from model_personas.json for scanning only; they never enter a prompt.

Steps (all read <arms-dir>/<arm>/*.jsonl written by assistant.regenerate_assistant):
  phrases   per-phrase leak counts per arm (and the excess of the model-persona arm over the larger baseline);
            writes <out>/leak_phrases.json and <out>/leak_ids.txt, the model-persona-arm conversations matching
            one of the four leak patterns (LEAK_PATTERNS)
  names     per-name counts of model-persona names in the replies of every arm (split by matched persona) and,
            optionally, in SFT training files (--sft-train); writes <out>/name_scan.json
  assemble  clean model-persona arm: the arm minus the leak ids, plus their regenerations (see below) when those
            are leak-free under the same four patterns; regenerations that leak again are dropped. Writes
            <arms-dir>/<arm>_clean/<shard>.jsonl and <out>/clean_stats.json

Leak repair between `phrases` and `assemble` (same matched persona and model, name-free prompt):
  python -m personafactory.assistant.regenerate_assistant --stage user_persona_model_persona --ids <out>/leak_ids.txt \
      --out-name user_persona_model_persona_leakfix ...

  python -m personafactory.assistant.leak_filter phrases  --arms-dir ./outputs/assistant --out ./outputs/assistant/leaks
  python -m personafactory.assistant.leak_filter names    --arms-dir ./outputs/assistant --out ./outputs/assistant/leaks
  python -m personafactory.assistant.leak_filter assemble --arms-dir ./outputs/assistant --out ./outputs/assistant/leaks
"""
import argparse, collections, glob, json, os, re
from personafactory.assistant import model_persona

ARMS = ('default', 'user_persona', 'user_persona_model_persona')
MP_ARM = 'user_persona_model_persona'
NAMES = [p['name'] for p in model_persona.PERSONAS]
_NAME_ALT = '|'.join(re.escape(n) for n in NAMES)
_NAME_ALT_HYPHEN = '|'.join(re.escape(n).replace(r'\-', r'[- ]') for n in NAMES)

PHRASES = {
    'optional touch': r'optional touch', 'signature touch': r'signature touch', 'content rules': r'content rules',
    'response style': r'response style', 'quirk': r'\bquirks?\b', 'style requires/remains': r'\b(?:style|tone) (?:requires|remains|calls for)\b',
    '<name>-style': r'\b(?:' + _NAME_ALT_HYPHEN + r')[- ](?:style|tone|register|mode)\b',
    'persona name (title case)': r'\b(?:' + _NAME_ALT + r')\b',
    '(no sign-off': r'\(\s*no sign[- ]?off', 'no em-dash': r'\bno em[- ]?dash', 'no emojis': r'\bno emojis?\b',
    'no opener': r'\bno opener', 'no preamble': r'\bno preamble', 'as instructed': r'\bas instructed\b',
    'system prompt': r'\bsystem prompt\b', 'my instructions': r'\bmy instructions\b', 'priority:': r'\bpriority: \(1\)',
    'the user\'s background': r"\bthe user'?s background\b",
}
# phrases that only the model-persona prompt produces: these define the leak ids and the clean-set check
LEAK_KEYS = ('persona name (title case)', '<name>-style', 'optional touch', '(no sign-off')
LEAK_PATTERNS = [re.compile(r'\b(?:' + _NAME_ALT + r')\b'),
                 re.compile(r'\b(?:' + _NAME_ALT_HYPHEN + r')[- ](?:style|tone|register|mode)\b', re.I),
                 re.compile(r'optional touch', re.I), re.compile(r'\(\s*no sign[- ]?off', re.I)]


def iter_arm(arms_dir, arm):
    for fp in glob.glob(os.path.join(arms_dir, arm, '*.jsonl')):
        for l in open(fp, encoding='utf-8'):
            yield json.loads(l)


def user_asst(conv):
    user = '\n'.join(m['content'] for m in conv if m['role'] == 'user').lower()
    asst = '\n'.join(m['content'] for m in conv if m['role'] == 'assistant')
    return user, asst


def leaks(x):
    conv = x.get('conversation') or []
    user, asst = user_asst(conv)
    for rx in LEAK_PATTERNS:
        m = rx.search(asst)
        if m and m.group(0).lower() not in user:
            return True
    return False


def cmd_phrases(a):
    rxs = {k: re.compile(v, re.I if k != 'persona name (title case)' else 0) for k, v in PHRASES.items()}
    out, ids, ex = {}, collections.defaultdict(set), collections.defaultdict(list)
    for arm in ARMS:
        c = collections.Counter()
        n = 0
        for x in iter_arm(a.arms_dir, arm):
            conv = x.get('conversation')
            if not conv:
                continue
            n += 1
            user, asst = user_asst(conv)
            for k, rx in rxs.items():
                m = rx.search(asst)
                if m and m.group(0).lower() not in user:
                    c[k] += 1
                    ids[(arm, k)].add(x['id'])
                    if len(ex[(arm, k)]) < 4:
                        ex[(arm, k)].append(asst[max(0, m.start() - 90):m.end() + 70].replace('\n', ' '))
        out[arm] = {'conversations': n, 'per_phrase': dict(c)}
    table = {}
    for k in PHRASES:
        d, r, m = (out[arm]['per_phrase'].get(k, 0) for arm in ARMS)
        table[k] = {'default': d, 'user_persona': r, MP_ARM: m, 'model_persona_excess_vs_max_baseline': m - max(d, r)}
    json.dump({'arms': out, 'table': table, 'examples': {f'{arm}/{k}': v for (arm, k), v in ex.items()},
               'ids': {f'{arm}/{k}': sorted(v) for (arm, k), v in ids.items()}},
              open(os.path.join(a.out, 'leak_phrases.json'), 'w'), indent=1, ensure_ascii=False)
    bad = set()
    for k in LEAK_KEYS:
        bad |= ids.get((MP_ARM, k), set())
    with open(os.path.join(a.out, 'leak_ids.txt'), 'w') as fh:
        fh.write(''.join(i + '\n' for i in sorted(bad)))
    for k, v in sorted(table.items(), key=lambda kv: -kv[1]['model_persona_excess_vs_max_baseline']):
        print(f"{k:28s} default={v['default']:5d} user_persona={v['user_persona']:5d} {MP_ARM}={v[MP_ARM]:5d} "
              f"excess={v['model_persona_excess_vs_max_baseline']}")
    print('leak ids:', len(bad))


def cmd_names(a):
    names = {p['id']: p['name'] for p in model_persona.PERSONAS}
    rx_by = {pid: re.compile(r'\b' + re.escape(n).replace(r'\-', r'[- ]') + r'\b', re.I) for pid, n in names.items()}
    generic_rx = re.compile(r'\b(persona|response style)\b', re.I)
    match = {x['id']: x['matched'] for x in iter_arm(a.arms_dir, 'match')}
    out = {}
    examples = collections.defaultdict(list)
    for arm in ARMS:
        conv = turns = own = generic = 0
        hits_conv = collections.Counter()
        for x in iter_arm(a.arms_dir, arm):
            if x.get('status') not in ('pass', 'fail') or not x.get('conversation'):
                continue
            conv += 1
            text = '\n'.join(m['content'] for m in x['conversation'] if m['role'] == 'assistant')
            turns += sum(m['role'] == 'assistant' for m in x['conversation'])
            found = [pid for pid, rx in rx_by.items() if rx.search(text)]
            for pid in found:
                hits_conv[pid] += 1
                if len(examples[(arm, pid)]) < 3:
                    m = rx_by[pid].search(text)
                    examples[(arm, pid)].append(text[max(0, m.start() - 120):m.end() + 80].replace('\n', ' '))
            if arm == MP_ARM and match.get(x['id']) in found:
                own += 1
            if generic_rx.search(text):
                generic += 1
        out[arm] = {'conversations': conv, 'assistant_turns': turns,
                    'per_name_conversations': {names[k]: v for k, v in hits_conv.most_common()},
                    'total_name_hits': sum(hits_conv.values()),
                    'mentions_own_matched_persona': own if arm == MP_ARM else None,
                    'mentions_word_persona_or_response_style': generic}
    if a.sft_train:
        sft = {}
        for fp in a.sft_train:
            n = hit = 0
            for l in open(fp, encoding='utf-8'):
                x = json.loads(l)
                n += 1
                if any(rx.search(x['messages'][-1]['content']) for rx in rx_by.values()):
                    hit += 1
            sft[fp] = {'rows': n, 'rows_whose_target_reply_contains_a_name': hit}
        out['sft_training_sets'] = sft
    out['examples'] = {f'{arm}/{names[p]}': v for (arm, p), v in examples.items()}
    json.dump(out, open(os.path.join(a.out, 'name_scan.json'), 'w'), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in out.items() if k != 'examples'}, indent=1))


def cmd_assemble(a):
    bad = {l.strip() for l in open(a.leak_ids or os.path.join(a.out, 'leak_ids.txt')) if l.strip()}
    fix = {}
    for x in iter_arm(a.arms_dir, a.fix_name):
        if x.get('conversation'):
            fix[x['id']] = x
    fixed_ok = {i: x for i, x in fix.items() if not leaks(x)}
    clean_dir = os.path.join(a.arms_dir, MP_ARM + '_clean')
    os.makedirs(clean_dir, exist_ok=True)
    stats = {'leak_conversations': len(bad), 'regenerated': len(fix), 'regenerated_leak_free': len(fixed_ok),
             'regenerated_still_leaking_dropped': len(fix) - len(fixed_ok), 'not_regenerated_dropped': len(bad - set(fix))}
    n = 0
    for fp in sorted(glob.glob(os.path.join(a.arms_dir, MP_ARM, '*.jsonl'))):
        stem = os.path.basename(fp).split('.')[0]  # part files <shard>.p<k>of<n> go back into their shard
        with open(os.path.join(clean_dir, stem + '.jsonl'), 'a', encoding='utf-8') as fo:
            for l in open(fp, encoding='utf-8'):
                x = json.loads(l)
                if x['id'] in bad:
                    if x['id'] in fixed_ok:
                        y = fixed_ok[x['id']]
                        y['regenerated_for_leak'] = True
                        fo.write(json.dumps(y, ensure_ascii=False) + '\n')
                        n += 1
                    continue
                fo.write(l if l.endswith('\n') else l + '\n')
                n += 1
    stats['clean_records'] = n
    json.dump(stats, open(os.path.join(a.out, 'clean_stats.json'), 'w'), indent=1)
    print(json.dumps(stats, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('step', choices=('phrases', 'names', 'assemble'))
    ap.add_argument('--arms-dir', default=os.path.join(os.environ.get('PF_OUT_DIR', './outputs'), 'assistant'),
                    help='directory with match/, default/, user_persona/, user_persona_model_persona/')
    ap.add_argument('--out', help='report directory (default: <arms-dir>/leaks)')
    ap.add_argument('--sft-train', nargs='*', help='names: SFT training JSONL files (messages; last message is the target)')
    ap.add_argument('--leak-ids', help='assemble: leak id file (default: <out>/leak_ids.txt)')
    ap.add_argument('--fix-name', default=MP_ARM + '_leakfix', help='assemble: directory name of the leak regenerations')
    a = ap.parse_args()
    a.out = a.out or os.path.join(a.arms_dir, 'leaks')
    os.makedirs(a.out, exist_ok=True)
    {'phrases': cmd_phrases, 'names': cmd_names, 'assemble': cmd_assemble}[a.step](a)


if __name__ == '__main__':
    main()
