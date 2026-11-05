#!/usr/bin/env python3
"""Style adherence rows of the full-corpus judge-free fidelity table, tier-aware per the paper's appendix definitions.

Checks the first user turn of every record against its persona's emoji, capitalization and punctuation
targets (persona bank). Writes <release-dir>/style_adherence.json.

  python -m personafactory.release.stats.style_adherence --release-dir ./release_out --bank ./release_out/persona_bank.jsonl
"""
import argparse, json, glob, re, collections, os
from multiprocessing import Pool
EMOJI=re.compile('[\U0001F300-\U0001FAFF☀-➿⬀-⯿]')
KAO=re.compile(r'\(\s*[^\w\s]{1,4}\s*[_\-^]\s*[^\w\s]{1,4}\s*\)|orz')
EMOT=re.compile(r"[:;=]-?[)(DPpOo3]|<3")
BANK=None
def init(bank):
    global BANK; BANK={}
    for line in open(bank,errors='ignore'):
        try: p=json.loads(line)
        except Exception: continue
        s=(p.get('style') or {}).get('chatting_style_structured') or {}
        BANK[p['id']]={k:str(s.get(k) or '').lower() for k in ('emoji_use','capitalization','punctuation')}
def emoji_ok(t,want):
    n=len(EMOJI.findall(t))+len(EMOT.findall(t)); kao=bool(KAO.search(t))
    if 'kaomoji' in want or 'sticker' in want: return kao or n>0
    if 'none' in want: return n==0 and not kao
    if 'rare' in want or 'functional' in want or 'occasional' in want: return n<=2
    if 'frequent' in want or 'decorative' in want: return n>=1
    return None
def caps_ok(t,want):
    sents=[x.strip() for x in re.split(r'[.!?\n]+',t) if x.strip()]
    if not sents: return None
    capped=sum(1 for x in sents if x[:1].isupper())/len(sents)
    if 'first-word' in want or 'first word' in want:
        return t.strip()[:1].isupper() and capped<=0.5
    if 'lowercase' in want: return capped<=0.3
    if 'standard' in want: return capped>=0.7
    if 'all caps' in want or 'all-caps' in want: return any(w.isupper() and len(w)>2 for w in t.split())
    return None   # 'inconsistent' and free text: unconstrained
def punct_ok(t,want):
    s=t.rstrip()
    if not s: return None
    if 'ellipsis' in want: return ('...' in t) or ('…' in t)
    if 'expressive' in want: return ('!!' in t) or ('??' in t) or ('!' in t) or ('?' in t)
    if 'minimal' in want or 'drop' in want or 'omit' in want: return s[-1] not in '.!?'
    if 'standard' in want: return s[-1] in '.!?'
    return None
def handle(raw):
    try: r=json.loads(raw)
    except Exception: return None
    out=next((m.get('content') for m in r.get('conversation') or [] if m.get('role')=='user'),'')
    tgt=BANK.get(r.get('persona_id'))
    if not out or not tgt: return None
    return (emoji_ok(out,tgt['emoji_use']), caps_ok(out,tgt['capitalization']),
            punct_ok(out,tgt['punctuation']), r.get('language_mode'))
def lines(pat):
    for fp in sorted(glob.glob(pat)):
        with open(fp,'rb') as f:
            for raw in f:
                if raw.strip(): yield raw.decode('utf-8','ignore')
def main():
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release-dir',required=True)
    ap.add_argument('--bank',default=os.environ.get('PF_BANK'),help='persona bank JSONL (or PF_BANK)')
    ap.add_argument('--out',default=None,help='default: <release-dir>/style_adherence.json')
    ap.add_argument('--workers',type=int,default=30)
    args=ap.parse_args()
    agg=collections.defaultdict(lambda:[0,0]); bymode=collections.defaultdict(lambda: collections.defaultdict(lambda:[0,0]))
    with Pool(args.workers,initializer=init,initargs=(args.bank,)) as pool:
        for res in pool.imap_unordered(handle, lines(os.path.join(args.release_dir,'data','*.jsonl')), chunksize=64):
            if not res: continue
            e,c,p,mode=res
            for name,v in (('emoji',e),('capitalization',c),('punctuation',p)):
                if v is None: continue
                agg[name][1]+=1; bymode[mode][name][1]+=1
                if v: agg[name][0]+=1; bymode[mode][name][0]+=1
    out={'overall':{k:{'pct':round(100*v[0]/v[1],1),'n':v[1]} for k,v in agg.items()},
         'by_mode':{m:{k:round(100*v[0]/v[1],1) for k,v in d.items()} for m,d in bymode.items()}}
    json.dump(out,open(args.out or os.path.join(args.release_dir,'style_adherence.json'),'w'),indent=2)
    print(json.dumps(out,indent=2))
if __name__=='__main__':
    main()
