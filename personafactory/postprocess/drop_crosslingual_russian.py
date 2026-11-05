#!/usr/bin/env python3
"""Drop the cross-lingual (multilingual setting) seed-pool conversations whose detected language is Russian, then
rebuild summary.json and prune persona_bank.jsonl. Russian is already strongly represented through WildChat's
language-matched conversations; cross-lingual Russian conversations of the persona-pair part are kept.

Shards of <release>/data are rewritten in place (tmp + rename); removed records -> <release>/ml_russian_removed.jsonl,
counts -> <release>/ml_russian_filter.json.

  python -m personafactory.postprocess.drop_crosslingual_russian --release-dir ./release_merged
"""
import argparse, collections, glob, json, os

from personafactory.release.merge_release import summarize


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release-dir', required=True)
    ap.add_argument('--part', default='seeds', help='release_part label of the seed-pool records')
    ap.add_argument('--language', default='Russian')
    a = ap.parse_args()

    def drop(r):
        return r['release_part'] == a.part and r['language_mode'] == 'multilingual' and r['text_language'] == a.language

    st, by = collections.Counter(), collections.Counter()
    with open(os.path.join(a.release_dir, 'ml_russian_removed.jsonl'), 'w', encoding='utf-8') as fr:
        for fp in sorted(glob.glob(os.path.join(a.release_dir, 'data', '*.jsonl'))):
            with open(fp + '.tmp', 'w', encoding='utf-8') as fo:
                for l in open(fp, encoding='utf-8'):
                    r = json.loads(l)
                    if drop(r):
                        st['removed'] += 1
                        by[f"{r['source_name']}/{r['responder']}"] += 1
                        fr.write(l)
                        continue
                    fo.write(l)
            os.replace(fp + '.tmp', fp)
    counts = summarize(a.release_dir, st)
    json.dump({'counts': counts, 'removed_by_source_responder': dict(by.most_common())},
              open(os.path.join(a.release_dir, 'ml_russian_filter.json'), 'w'), indent=1, ensure_ascii=False)
    print(json.dumps(counts, indent=1))


if __name__ == '__main__':
    main()
