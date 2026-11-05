#!/usr/bin/env python3
"""Collect accepted conversations (status == pass) from the driver output into the accepted-record
schema read by the release build. One file per mode, deduplicated by key.

Input:  <in-dir>/{free,multilingual}-*.jsonl (augmentation.run_augmentation output), persona bank.
Output: <out-dir>/<mode>/<mode>.jsonl with records
  {id, key, persona_id, cohort (persona country), target_language, persona_native_language,
   language_mode, conversation, source_conversation, metadata}
  persona_native_language: target language for multilingual, persona main language for free
  metadata.localized_user_messages: the translation of each user turn (multilingual intent baseline)
  metadata.split / source_name / source_id / pair_key / language_resolution (= match tier) / pipeline /
  responder / num_turns are copied from the driver wrapper; the persona itself is dropped from
  metadata (it lives in the bank).

Run:
  python -m personafactory.augmentation.extract_accepted --in-dir ./outputs/generated --out-dir ./outputs/accepted --bank $PF_BANK
"""
import argparse, collections, glob, json, os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in-dir', default=os.path.join(os.environ.get('PF_OUT_DIR', './outputs'), 'generated'))
    ap.add_argument('--out-dir', default=os.path.join(os.environ.get('PF_OUT_DIR', './outputs'), 'accepted'))
    ap.add_argument('--bank', default=os.environ.get('PF_BANK'), required='PF_BANK' not in os.environ)
    a = ap.parse_args()
    bank = {}
    for l in open(a.bank, encoding='utf-8'):
        p = json.loads(l)
        bank[p['id']] = p
    stats = collections.Counter()
    for mode in ('free', 'multilingual'):
        os.makedirs(os.path.join(a.out_dir, mode), exist_ok=True)
        seen = set()
        with open(os.path.join(a.out_dir, mode, f'{mode}.jsonl'), 'w', encoding='utf-8') as out:
            for fp in sorted(glob.glob(os.path.join(a.in_dir, f'{mode}-*.jsonl'))):
                for line in open(fp, encoding='utf-8'):
                    if not line.strip():
                        continue
                    w = json.loads(line)
                    stats[f'{mode}/{w["status"]}'] += 1
                    if w['status'] != 'pass' or w['key'] in seen:
                        continue
                    seen.add(w['key'])
                    res = w['result']
                    md = res['metadata']
                    tds = md.get('turns_detail') or []
                    bg = (bank.get(w['persona_id']) or {}).get('background') or {}
                    md.update(split=w.get('split'), source_name=w.get('source_name'), source_id=w.get('source_id'),
                              pair_key=w['pair_key'], language_resolution=w['match_tier'], pipeline=w['pipeline'],
                              responder=w['responder'], num_turns=len(tds))
                    if mode == 'multilingual':
                        md['localized_user_messages'] = [td.get('user_message_original') for td in tds]
                    md.pop('persona', None)  # the persona lives in the bank
                    rec = {'id': w['key'], 'key': w['key'], 'persona_id': w['persona_id'], 'cohort': bg.get('country'),
                           'target_language': w.get('target_language'),
                           'persona_native_language': w.get('target_language') or bg.get('main_language'),
                           'language_mode': mode, 'conversation': res['conversation'],
                           'source_conversation': res['source_conversation'], 'metadata': md}
                    stats[f'{mode}/responder/{w["responder"]}'] += 1
                    stats[f'{mode}/tier/{w["match_tier"]}'] += 1
                    out.write(json.dumps(rec, ensure_ascii=False) + '\n')
    print(json.dumps(dict(sorted(stats.items())), indent=1))


if __name__ == '__main__':
    main()
