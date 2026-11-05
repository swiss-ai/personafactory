#!/usr/bin/env python3
"""Design pilot, `restyled` arm: post-hoc restyle of the source assistant replies with the matched model persona,
one call per assistant turn by the conversation's own responder model. Code, numbers, URLs and quotes are
protected; a restyle that loses a protected span or shrinks below 50% of the original is retried (3 tries), then
the original reply is kept and flagged (assistant.shared.restyle).

Inputs: accepted source records (--source-dir) and <out-dir>/match.jsonl from assistant.pilot_regenerate match.
Output: <out-dir>/arm_restyled.jsonl (resumable).

  python -m personafactory.assistant.pilot_restyle --source-dir ./outputs/pilot_design/src --out-dir ./outputs/pilot_design \
      --gemma $GEMMA_URL --ministral $MINISTRAL_URL
"""
import argparse, asyncio, json, os
import aiohttp
from personafactory.assistant import model_persona
from personafactory.assistant.pilot_regenerate import load_matches
from personafactory.assistant.shared import accepted_records, add_server_args, responders, restyle


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--concurrency', type=int, default=80)
    add_server_args(ap, judge_required=False)
    a = ap.parse_args()
    recs = accepted_records(a.source_dir)
    mt = load_matches(a.out_dir)
    out_fp = os.path.join(a.out_dir, 'arm_restyled.jsonl')
    done = set()
    if os.path.exists(out_fp):
        done = {json.loads(l)['key'] for l in open(out_fp)}
    fh = open(out_fp, 'a', encoding='utf-8')
    sem = asyncio.Semaphore(a.concurrency)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=900)) as session:
        async def one(r):
            m = mt.get(r['key'])
            if r['key'] in done or not m or not m['matched']:
                return
            persona = model_persona.BY_ID[m['matched']]
            responder = responders(a, (r['responder'],))[0]
            conv = json.loads(json.dumps(r['result']['conversation']))
            flags = []
            async with sem:
                for i in range(0, len(conv) - 1, 2):
                    new, fail = await restyle(session, responder, persona, conv[i]['content'], conv[i + 1]['content'])
                    conv[i + 1]['content'] = new
                    flags.append(fail)
            res = {'conversation': conv, 'metadata': {'restyle_failures': flags}}
            fh.write(json.dumps({'key': r['key'], 'arm': 'restyled', 'mode': r['mode'], 'responder': r['responder'],
                                 'model_persona': m['matched'], 'status': 'pass', 'result': res}, ensure_ascii=False) + '\n')
            fh.flush()
        await asyncio.gather(*(one(r) for r in recs))
    fh.close()
    rs = [json.loads(l) for l in open(out_fp)]
    tot = sum(len(x['result']['metadata']['restyle_failures']) for x in rs)
    bad = sum(f is not None for x in rs for f in x['result']['metadata']['restyle_failures'])
    print(json.dumps({'arm': 'restyled', 'conversations': len(rs), 'turns': tot, 'restyle_kept_original': bad}), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
