#!/usr/bin/env python3
"""LaBSE row of the full-corpus judge-free fidelity table: cosine similarity of every released user turn with its
source turn, over the whole release. GPU job.

Definition (as labse.py): the source turn is the seed user turn the rewriter started from; for cross-lingual
records it is the English seed turn, not the translation. All user turns count, including turns kept verbatim.
Turn pairs are (source turn t, released user turn t) for t < min(len(source), len(released)).

Source turns come from either input (both may be given; --originals wins on overlap):
  --originals  pipeline output records (metadata.turns_detail[t].user_message_source, else user_message_original;
               fallback source_conversation), matched by record id, as in prep_items.py
  --seeds      seed records with `pair_key`, `mode` and `conversation`, matched by the pipeline key of
               (pair_key, mode) (augmentation.run_augmentation.key_of)

Optional turn-weighted combination with an already scored subset (e.g. the judge items of a fully judged part of
the corpus, whose LaBSE was computed with labse.py): --subset-items <judge-dir>/items --subset-labse labse.json.
Conversations in the subset items are skipped here and the report gives `rest_of_corpus`, `fully_scored_subset` and
`combined` = sum(mean * n) / sum(n) over turn pairs, for `all`, `mode/free` and `mode/multilingual`.

Outputs: --out JSON (default <release-dir>/labse_full.json)
Run:     python -m personafactory.evaluation.corpus_judge.labse_full --release-dir $PF_OUT_DIR/release \
             --originals $PF_OUT_DIR/accepted --model sentence-transformers/LaBSE
"""
import argparse, ast, collections, glob, json, os

import numpy as np

GROUPS = ('all', 'mode/free', 'mode/multilingual')


def expand(paths):
    out = []
    for p in paths:
        out += sorted(glob.glob(os.path.join(p, '**', '*.jsonl'), recursive=True)) if os.path.isdir(p) else sorted(glob.glob(p))
    return out


def source_turns(r):
    """Per-turn source user turns of one pipeline output record (same rule as prep_items.originals_of)."""
    td = (r.get('metadata') or {}).get('turns_detail') or []
    if td:
        return [t.get('user_message_source') or t.get('user_message_original') or '' for t in td]
    return [m['content'] for m in (r.get('source_conversation') or []) if m.get('role') == 'user']


def subset_ids(items_dir):
    ids = set()
    for fp in glob.glob(os.path.join(items_dir, '*.jsonl')):
        for line in open(fp, encoding='utf-8'):
            ids.add(json.loads(line)['key'].rsplit('#', 1)[0])
    return ids


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release-dir', required=True, help='release directory with data/*.jsonl')
    ap.add_argument('--originals', nargs='*', default=[], help='pipeline output JSONL files, dirs or globs')
    ap.add_argument('--seeds', nargs='*', default=[], help='seed JSONL files, dirs or globs')
    ap.add_argument('--model', default=os.environ.get('PF_LABSE_MODEL', 'sentence-transformers/LaBSE'),
                    help='local sentence-transformers/LaBSE snapshot or hub id (or PF_LABSE_MODEL)')
    ap.add_argument('--subset-items', default=None, help='judge items dir of an already scored subset (skipped here)')
    ap.add_argument('--subset-labse', default=None, help='labse.py report of that subset (labse_vs_source groups)')
    ap.add_argument('--chunk', type=int, default=200000, help='turn pairs encoded per chunk')
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    if not a.originals and not a.seeds:
        ap.error('give --originals and/or --seeds')

    skip = subset_ids(a.subset_items) if a.subset_items else set()
    need = {}
    for fp in sorted(glob.glob(os.path.join(a.release_dir, 'data', '*.jsonl'))):
        for line in open(fp, encoding='utf-8'):
            r = json.loads(line)
            if r['id'] not in skip:
                need[r['id']] = (r['language_mode'], [m['content'] for m in r['conversation'] if m['role'] == 'user'])
    print('conversations', len(need), 'skipped (scored subset)', len(skip), flush=True)

    src = {}
    if a.seeds:
        from personafactory.augmentation.run_augmentation import key_of  # pipeline id of (pair_key, mode)
        for fp in expand(a.seeds):
            for line in open(fp, encoding='utf-8'):
                s = json.loads(line)
                k = key_of(s['pair_key'], s.get('mode') or os.path.basename(fp).split('-')[0])
                if k in need:
                    conv = s['conversation']
                    conv = ast.literal_eval(conv) if isinstance(conv, str) else conv
                    src[k] = [m['content'] for m in conv if m['role'] == 'user']
    for fp in expand(a.originals):
        for line in open(fp, encoding='utf-8', errors='ignore'):
            if line.strip():
                r = json.loads(line)
                k = r.get('id') or r.get('key')
                if k in need:
                    src[k] = source_turns(r)
    print('sources found', len(src), flush=True)

    rows, miss = [], collections.Counter()
    for k, (mode, users) in need.items():
        if k not in src:
            miss['no_source'] += 1
            continue
        if len(src[k]) < len(users):
            miss['source_shorter'] += 1
        rows.extend((mode, o, rw) for o, rw in zip(src[k], users))
    print('pairs', len(rows), dict(miss), flush=True)

    from personafactory.evaluation.corpus_judge.labse import LaBSE
    path = a.model
    if not os.path.isdir(path):
        from huggingface_hub import snapshot_download
        path = snapshot_download(path)
    model = LaBSE(path)
    sims = np.zeros(len(rows), dtype=np.float32)
    for s in range(0, len(rows), a.chunk):
        chunk = rows[s:s + a.chunk]
        sims[s:s + len(chunk)] = (model.encode([r[1] for r in chunk]) * model.encode([r[2] for r in chunk])).sum(1)
        print('encoded', s + len(chunk), flush=True)
    modes = np.array([r[0] for r in rows])
    rest = {'all': (float(sims.mean()), len(rows))}
    for m in ('free', 'multilingual'):
        sel = sims[modes == m]
        rest['mode/' + m] = (float(sel.mean()) if sel.size else float('nan'), int(sel.size))
    out = {'rest_of_corpus' if skip else 'corpus': {g: {'mean': round(m, 4), 'n': n} for g, (m, n) in rest.items()},
           'missing': dict(miss)}
    if a.subset_labse:
        sub = json.load(open(a.subset_labse))['labse_vs_source']
        out['fully_scored_subset'] = {g: sub[g] for g in GROUPS if g in sub}
        out['combined'] = {}
        for g, (mean, n) in rest.items():
            if g in sub:
                sm, sn = sub[g]['mean'], sub[g]['n']
                out['combined'][g] = {'mean': round((mean * n + sm * sn) / (n + sn), 4), 'n': n + sn}
    dst = a.out or os.path.join(a.release_dir, 'labse_full.json')
    json.dump(out, open(dst, 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
