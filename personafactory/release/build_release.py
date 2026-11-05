#!/usr/bin/env python3
"""Assemble the release directory from the pipeline's accepted conversations.

Two input formats share one record schema:
  --accepted   accepted records from augmentation/extract_accepted.py (<accepted>/free/*.jsonl and
               <accepted>/multilingual/*.jsonl); `split` is copied from the record metadata
  --responses  optional raw pipeline output records (one JSON per line, per-turn details in
               metadata.turns_detail); only sanity-passing conversations are used and `split` is null

Every record gets `text_language`, the LID-detected language of its first user turn (common.lid), never
the persona's declared language. Raw output records whose persona declares a non-English language but whose
text is English are excluded. With --dedup, records that rewrite the same source prompt (normalized
source_text) into the same text_language are kept once; priority is emission order (accepted free,
accepted multilingual, raw output records).

Outputs: <outdir>/data/0000.jsonl ... 0199.jsonl and <outdir>/dataset_summary.json.

  python -m personafactory.release.build_release --accepted $PF_OUT_DIR/accepted \
      --lid-model $PF_LID_MODEL --dedup --outdir $PF_OUT_DIR/release --workers 60
"""
import argparse, collections, glob, hashlib, json, os, re
from multiprocessing import Pool

from personafactory.common.lid import init, detect, norm

SHARDS = 200


def accepted_record(raw):
    try:
        r = json.loads(raw)
    except Exception:
        return None
    conv = r.get('conversation') or []
    user = next((m.get('content') for m in conv if m.get('role') == 'user'), '')
    if not user or len(conv) < 2:
        return None
    src = r.get('source_conversation') or []
    return {
        'id': r.get('id') or r.get('key'),
        'conversation': conv,
        'persona_id': r.get('persona_id'),
        'persona_language': norm(r.get('persona_native_language')),
        'text_language': detect(user),
        'language_mode': r.get('language_mode'),
        'source_text': next((m.get('content') for m in src if m.get('role') == 'user'), ''),
        'cohort': r.get('cohort'),
        'responder': (r.get('metadata') or {}).get('responder'),
        'source_name': (r.get('metadata') or {}).get('source_name'),
        'num_turns': (r.get('metadata') or {}).get('num_turns') or len(conv),
        'match_basis': (r.get('metadata') or {}).get('language_resolution'),
        'split': (r.get('metadata') or {}).get('split'),
        'sanity_verdicts': (r.get('metadata') or {}).get('sanity_verdicts'),
    }


def response_record(raw):
    try:
        r = json.loads(raw)
    except Exception:
        return None
    md = r.get('metadata') or {}
    if md.get('sanity_pass') is not True:
        return None
    conv = r.get('conversation') or []
    turns = md.get('turns_detail') or []
    if not conv or not turns:
        return None
    user = turns[0].get('user_message') or ''
    if not user:
        return None
    bg = ((md.get('persona') or {}).get('background') or {})
    return {
        'id': r.get('id'),
        'conversation': conv,
        'persona_id': (md.get('persona') or {}).get('id'),
        'persona_language': norm(bg.get('main_language')),
        'text_language': detect(user),
        'language_mode': 'multilingual' if md.get('persona_set') == 'cross_lingual' else 'free',
        'source_text': turns[0].get('user_message_original') or '',
        'cohort': bg.get('country'),
        'responder': md.get('responder'),
        'source_name': str(r.get('id') or '').split(':')[0] or None,
        'num_turns': md.get('num_turns') or len(conv),
        'match_basis': md.get('persona_match_tier'),
        'split': None,
        'sanity_verdicts': md.get('sanity_verdicts'),
    }


def lines(pattern):
    for fp in sorted(glob.glob(pattern)):
        with open(fp, 'rb') as f:
            for raw in f:
                if raw.strip():
                    yield raw.decode('utf-8', 'ignore')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--accepted', required=True, help='directory with free/ and multilingual/ accepted records')
    ap.add_argument('--responses', default=None, help='optional raw pipeline output JSONL (glob allowed)')
    ap.add_argument('--lid-model', default=os.environ.get('PF_LID_MODEL'), help='fastText lid.176 model (or PF_LID_MODEL)')
    ap.add_argument('--lid-deps', default=None, help='optional directory with the fasttext/lingua packages')
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--workers', type=int, default=30)
    ap.add_argument('--dedup', action='store_true')
    args = ap.parse_args()
    out = os.path.join(args.outdir, 'data')
    os.makedirs(out, exist_ok=True)
    sinks = [open(os.path.join(out, f'{i:04d}.jsonl'), 'w', encoding='utf-8') for i in range(SHARDS)]
    stats = collections.Counter()
    langs = collections.Counter()
    seen = set()
    seen_src = set()

    def emit(rec, origin=''):
        if not rec or rec['id'] in seen:
            stats['duplicate_id_skipped'] += 1 if rec else 0
            return False
        if args.dedup and rec.get('source_text'):
            src = re.sub(r'\s+', ' ', rec['source_text'].strip().lower())
            k = (hashlib.sha1(src.encode('utf-8', 'ignore')).hexdigest(), rec['text_language'])
            if k in seen_src:
                stats['dedup_same_source_same_language/' + origin] += 1
                return False
            seen_src.add(k)
        seen.add(rec['id'])
        sinks[int(hashlib.md5(str(rec['id']).encode()).hexdigest(), 16) % SHARDS].write(json.dumps(rec, ensure_ascii=False) + '\n')
        stats['total'] += 1
        stats['mode/' + str(rec['language_mode'])] += 1
        langs[rec['text_language']] += 1
        return True

    with Pool(args.workers, initializer=init, initargs=(args.lid_model, args.lid_deps)) as pool:
        for mode in ('free', 'multilingual'):
            n = 0
            # imap (ordered) so dedup keeps the same record on every rebuild
            for rec in pool.imap(accepted_record, lines(f'{args.accepted}/{mode}/*.jsonl'), chunksize=64):
                if rec and emit(rec, 'accepted_' + mode):
                    n += 1
            stats['source/accepted_' + mode] = n
            print(f'accepted {mode}: {n}', flush=True)

        kept = dropped = 0
        for rec in pool.imap(response_record, lines(args.responses) if args.responses else iter(()), chunksize=64):
            if not rec:
                continue
            # keep English free-mode records and records verified non-English by text; drop the rest,
            # i.e. records whose persona claims another language but whose text is English
            is_en = rec['text_language'] == 'English'
            if is_en and rec['language_mode'] == 'free':
                kept += emit(rec, 'responses')
            elif not is_en and rec['text_language'] not in ('TooShort', 'Unknown'):
                rec['language_mode'] = 'multilingual'
                kept += emit(rec, 'responses')
            else:
                dropped += 1
        stats['source/responses_kept'] = kept
        stats['source/responses_dropped_text_not_in_declared_language'] = dropped
        print(f'raw output records kept {kept}, dropped {dropped}', flush=True)

    for s in sinks:
        s.close()
    summary = {'records': stats['total'], 'by_mode': {k.split('/')[1]: v for k, v in stats.items() if k.startswith('mode/')},
               'by_source': {k.split('/', 1)[1]: v for k, v in stats.items() if k.startswith('source/')},
               'dedup_dropped': {k.split('/', 1)[1]: v for k, v in stats.items() if k.startswith('dedup_')},
               'text_language_top': dict(langs.most_common(30)),
               'distinct_text_languages': len(set(langs) - {'TooShort', 'Unknown'}),
               'non_english_records': sum(v for k, v in langs.items() if k not in ('English', 'TooShort', 'Unknown')),
               'shards': SHARDS}
    with open(os.path.join(args.outdir, 'dataset_summary.json'), 'w') as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
