#!/usr/bin/env python3
"""Inputs for regenerating the assistant side with Gemma for the cross-lingual seed-pool conversations in
high-resource languages (language not in lowres_quality.LOWRES) whose responder is Ministral. User turns stay as
released: the records are the assistant-side inputs written by augmentation.build_corpus --stage user (fixed user
turns, original per-turn text, persona_applied flags) with `responder` set to gemma.

Writes <out>/input/NNNN.jsonl (same shard names as the inputs; the input of
assistant.regenerate_assistant --stage user_persona) and <out>/targets.tsv (id <TAB> language).

  python -m personafactory.postprocess.asst_regen_prep --release-dir ./release_merged \\
      --assistant-input ./outputs/seeds_run/assistant_input --out ./outputs/asst_regen
"""
import argparse, collections, glob, json, os

from personafactory.postprocess.lowres_quality import LOWRES, lang_of, release_lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release-dir', required=True)
    ap.add_argument('--assistant-input', required=True, help='build_corpus <run>/assistant_input directory')
    ap.add_argument('--out', required=True)
    ap.add_argument('--part', default='seeds', help='release_part label of the seed-pool records')
    a = ap.parse_args()
    t = {}
    for l in release_lines(a.release_dir):
        if '"ministral"' not in l:
            continue
        r = json.loads(l)
        if r.get('release_part') == a.part and r.get('language_mode') == 'multilingual' and r.get('responder') == 'ministral':
            L = lang_of(r)
            if L not in LOWRES:
                t[r['id']] = L
    os.makedirs(os.path.join(a.out, 'input'), exist_ok=True)
    with open(os.path.join(a.out, 'targets.tsv'), 'w', encoding='utf-8') as f:
        f.writelines(f'{i}\t{L}\n' for i, L in sorted(t.items()))
    st = collections.Counter()
    for fp in sorted(glob.glob(os.path.join(a.assistant_input, '*.jsonl'))):
        with open(os.path.join(a.out, 'input', os.path.basename(fp)), 'w', encoding='utf-8') as fo:
            for l in open(fp, encoding='utf-8'):
                r = json.loads(l)
                if r['id'] in t:
                    r['responder'] = 'gemma'
                    fo.write(json.dumps(r, ensure_ascii=False) + '\n')
                    st['written'] += 1
    st['targets'] = len(t)
    st['missing_input'] = len(t) - st['written']
    print(dict(st), collections.Counter(t.values()).most_common(12))


if __name__ == '__main__':
    main()
