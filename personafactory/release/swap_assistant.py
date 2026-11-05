#!/usr/bin/env python3
"""Replace the assistant side of every released conversation with its regenerated version.

The regenerated assistant turns are written with the user-persona system prompt (the user's background and
style) plus a matched model persona (assistant/model_personas.json); style names never enter the prompt, and
replies that leak a style name have already been regenerated or dropped by the leak filter. Inputs are the
cleaned regeneration outputs, one or more files per release shard named <shard stem>*.jsonl, each line
{id, status, conversation, sanity_verdicts, model_persona, quirks}.

A conversation is kept only if its regeneration passed the sanity gate on every turn and its user turns are
exactly the released ones (checked turn by turn). Rewrites <release-dir>/data in place, copies the model
personas to <release-dir>/model_personas.json, writes <release-dir>/assistant_side.json and updates the
counts in <release-dir>/dataset_summary.json to the kept records.

  python -m personafactory.release.swap_assistant --release-dir $PF_OUT_DIR/release --regen-dir $PF_OUT_DIR/assistant_regen_clean \
      --model-personas assistant/model_personas.json
"""
import argparse, collections, glob, json, os, shutil, statistics

GEN = 'user persona system prompt (user background + style) + matched model persona'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release-dir', required=True)
    ap.add_argument('--regen-dir', required=True, help='cleaned assistant regeneration outputs')
    ap.add_argument('--model-personas', default='assistant/model_personas.json')
    args = ap.parse_args()
    rel = args.release_dir

    st = collections.Counter()
    by = collections.defaultdict(collections.Counter)
    words, lt = collections.defaultdict(list), collections.Counter()
    langs, modes = collections.Counter(), collections.Counter()
    for fp in sorted(glob.glob(os.path.join(rel, 'data', '*.jsonl'))):
        stem = os.path.basename(fp)[:-len('.jsonl')]
        regen = {}
        for cf in glob.glob(os.path.join(args.regen_dir, stem + '*.jsonl')):
            for l in open(cf, encoding='utf-8'):
                x = json.loads(l)
                regen[x['id']] = x
        out = []
        for l in open(fp, encoding='utf-8'):
            r = json.loads(l)
            tag = f"mode/{r.get('language_mode')}"
            st['release_in'] += 1
            x = regen.get(r['id'])
            if not x:
                st['drop_not_regenerated'] += 1
                continue
            if x.get('status') != 'pass' or not x.get('conversation'):
                st['drop_sanity_fail'] += 1
                by[tag]['drop_sanity_fail'] += 1
                continue
            u_old = [m['content'] for m in r['conversation'] if m['role'] == 'user']
            u_new = [m['content'] for m in x['conversation'] if m['role'] == 'user']
            if u_old != u_new:
                st['drop_user_turn_mismatch'] += 1
                continue
            r['conversation'] = x['conversation']
            r['sanity_verdicts'] = x.get('sanity_verdicts')
            r['model_persona'] = x['model_persona']
            r['model_persona_quirks'] = x.get('quirks')
            r['assistant_generation'] = GEN
            out.append(r)
            st['kept'] += 1
            by[tag]['kept'] += 1
            by['model_persona'][x['model_persona']] += 1
            langs[r['text_language']] += 1
            modes[r['language_mode']] += 1
            for q in x.get('quirks') or []:
                by['quirk_offered']['yes' if q else 'no'] += 1
            for m in x['conversation']:
                if m['role'] == 'assistant':
                    words[tag].append(len(m['content'].split()))
                    lt[tag] += '<' in m['content']
        tmp = fp + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fo:
            for r in out:
                fo.write(json.dumps(r, ensure_ascii=False) + '\n')
        os.replace(tmp, fp)
    shutil.copy(args.model_personas, os.path.join(rel, 'model_personas.json'))
    res = {'counts': dict(st), 'by_mode': {k.split('/', 1)[1]: dict(v) for k, v in by.items() if k.startswith('mode/')},
           'model_persona_distribution': dict(by['model_persona'].most_common()),
           'quirk_offered_turns': dict(by['quirk_offered']),
           'assistant_turn_median_words': {k: statistics.median(v) for k, v in words.items()},
           'assistant_turns': {k: len(v) for k, v in words.items()},
           'assistant_turns_with_lt_char': dict(lt), 'assistant_generation': GEN}
    json.dump(res, open(os.path.join(rel, 'assistant_side.json'), 'w'), indent=1)
    print(json.dumps(res, indent=1))

    # dataset_summary.json: build-stage counts (dedup, exclusions) stay; record counts follow the kept records
    sp = os.path.join(rel, 'dataset_summary.json')
    s = json.load(open(sp))
    s['records'] = st['kept']
    s['by_mode'] = dict(modes)
    s['assistant_swap'] = {'records_before': st['release_in'], 'dropped_sanity_fail': st['drop_sanity_fail'],
                           'dropped_not_regenerated': st['drop_not_regenerated'],
                           'dropped_user_turn_mismatch': st['drop_user_turn_mismatch']}
    s['text_language_top'] = dict(langs.most_common(30))
    s['distinct_text_languages'] = len(set(langs) - {'TooShort', 'Unknown'})
    s['non_english_records'] = sum(v for k, v in langs.items() if k not in ('English', 'TooShort', 'Unknown'))
    with open(sp, 'w') as fh:
        json.dump(s, fh, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
