#!/usr/bin/env python3
"""Judge-free constraint retention over the release (full-corpus judge-free fidelity table).

For numbers, code/identifiers and quoted literals in the source turn, the share that survives in the first
rewritten user turn, overall and by mode. Writes <release-dir>/entity_integrity.json.

  python -m personafactory.release.stats.entity_integrity --release-dir ./release_out
"""
import argparse,json,glob,re,collections,os
ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--release-dir',required=True)
ap.add_argument('--out',default=None,help='default: <release-dir>/entity_integrity.json')
args=ap.parse_args()
NUM=re.compile(r'(?<![\w])[-+]?\d+(?:[.,]\d+)*%?')
CODE=re.compile(r'```.*?```|`[^`\n]+`|https?://\S+|(?:/[\w.-]+){2,}|\b[A-Za-z_]+\(\)|--[A-Za-z][\w-]+')
QUOTE=re.compile(r'"[^"\n]{2,}"|“[^”\n]{2,}”|«[^»\n]{2,}»|「[^」\n]{2,}」')
def ents(t,rx): return set(m.group(0).strip() for m in rx.finditer(t or ''))
def keep(src,out,rx):
    s=ents(src,rx)
    if not s: return None
    o=ents(out,rx)
    return len(s&o)/len(s)
agg=collections.defaultdict(list); mode_agg=collections.defaultdict(lambda: collections.defaultdict(list))
allok=collections.Counter(); n=0
for fp in sorted(glob.glob(os.path.join(args.release_dir,'data','*.jsonl'))):
    for line in open(fp,encoding='utf-8',errors='ignore'):
        if not line.strip(): continue
        r=json.loads(line); n+=1
        src=r.get('source_text') or ''
        out=next((m.get('content') for m in r.get('conversation') or [] if m.get('role')=='user'),'')
        if not src or not out: continue
        per={}
        for name,rx in (('numbers',NUM),('code',CODE),('quotes',QUOTE)):
            v=keep(src,out,rx)
            if v is not None:
                agg[name].append(v); mode_agg[r['language_mode']][name].append(v); per[name]=v
        if per:
            allok['with_entities']+=1
            if all(v==1.0 for v in per.values()): allok['all_intact']+=1
def pct(v): return round(100*sum(v)/len(v),1) if v else None
res={'records':n,
     'overall':{k:{'mean_retention_pct':pct(v),'records_with_this_entity':len(v)} for k,v in agg.items()},
     'all_entities_intact_pct':round(100*allok['all_intact']/max(1,allok['with_entities']),1),
     'records_with_any_entity':allok['with_entities'],
     'by_mode':{m:{k:pct(v) for k,v in d.items()} for m,d in mode_agg.items()}}
json.dump(res,open(args.out or os.path.join(args.release_dir,'entity_integrity.json'),'w'),indent=2)
print(json.dumps(res,indent=2))
