#!/usr/bin/env python3
"""Per-language and per-mode record counts of the release (text_language of the first user turn).

Writes <release-dir>/full_stats.json and prints the non-English language coverage.

  python -m personafactory.release.stats.language_counts --release-dir ./release_out
"""
import argparse, json, glob, collections, os
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--release-dir', required=True)
ap.add_argument('--out', default=None, help='default: <release-dir>/full_stats.json')
args = ap.parse_args()
lang=collections.Counter(); mode=collections.Counter(); lm=collections.defaultdict(collections.Counter)
turns=0; recs=0
for fp in sorted(glob.glob(os.path.join(args.release_dir,'data','*.jsonl'))):
    for line in open(fp,encoding='utf-8',errors='ignore'):
        if not line.strip(): continue
        r=json.loads(line); recs+=1
        lang[r['text_language']]+=1; mode[r['language_mode']]+=1
        lm[r['language_mode']][r['text_language']]+=1
        turns+=len(r.get('conversation') or [])
out={'records':recs,'turns':turns,'by_mode':dict(mode),
     'languages':dict(lang.most_common()),
     'multilingual_languages':dict(lm['multilingual'].most_common()),
     'free_languages':dict(lm['free'].most_common())}
json.dump(out,open(args.out or os.path.join(args.release_dir,'full_stats.json'),'w'),ensure_ascii=False,indent=2)
ne={k:v for k,v in lang.items() if k not in ('English','TooShort','Unknown')}
print('records',recs,'turns',turns)
print('non-English',sum(ne.values()),'across',len(ne),'languages')
print('>=1000:',sum(1 for v in ne.values() if v>=1000),' >=500:',sum(1 for v in ne.values() if v>=500),' >=100:',sum(1 for v in ne.values() if v>=100))
