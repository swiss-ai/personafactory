#!/usr/bin/env python3
"""Judge items of the style-extension A/B (generate.py output in DIR/gen; only conversations with status pass).

  single    DIR/judge/items/NNN.jsonl (--shards, default 8):
              intent     per arm and user turn: VALIDATE_PERSONA_INTENT_TEMPLATE, rewritten turn vs the source turn
                         (free) or the translation the rewriter saw (multilingual)
              style      arm C only, per user turn: VALIDATE_PERSONA_STYLE_TEMPLATE
              identify   per arm, first user turn: which of 4 people wrote it. Candidates are converted backgrounds
                         (no style) of the true persona and 3 personas from the same source release and mode, in the
                         same order for every arm of a pair
              pair_real, pair_fit   single-order pairwise items (superseded by `pairwise`; kept because they are
                         drawn from the same random stream as the identify candidates)
  pairwise  DIR/judge/items_pair2/NNN.jsonl (--shards, default 16), every comparison in both orders:
              pair_real  per arm pair (AC, BC, AB), first user turn, pairs where all three arms passed: which of two
                         messages reads more like a real person typing to a chatbot
              pair_fit   same pairs: which fits the described person better
              calib_real the real English WildChat seed turn (free mode) against each arm's rewrite of it (pair 'R' + arm)
  rejudge   items whose answer was unparsable in DIR/judge/results -> DIR/judge/items_rejudge/NNN.jsonl
            (--shards, default 16) for a second pass with a larger budget
  external  identify items of `single` + all `pairwise` items -> DIR/judge/items_ext/all.jsonl, the item set given
            to the two external judges

Usage:
    python -m personafactory.evaluation.style_extension.items single --dir ./outputs/style_extension
    python -m personafactory.evaluation.style_extension.items pairwise --dir ./outputs/style_extension
"""
import argparse, collections, glob, hashlib, json, os, random

from personafactory.augmentation.pipeline import get_persona_background_str as bg_str, get_persona_style_str as style_str
from personafactory.augmentation.prompts import (VALIDATE_PERSONA_INTENT_TEMPLATE as INTENT,
                                                 VALIDATE_PERSONA_STYLE_TEMPLATE as STYLE)

IDENTIFY = """Below is a message that one person typed to an AI chat assistant, and short descriptions of four people. All four could have asked for the same thing; decide who most likely WROTE this message, judging only from HOW it is written: register, word choice, sentence length, punctuation, capitalization, typos, emoji, formality, and anything else in the wording.

Message:
<<<
{message}
>>>

{candidates}

Respond with a JSON object exactly in this format:
{{"answer": 1, 2, 3 or 4, "reason": "brief explanation"}}
Output strictly the raw JSON and nothing else."""

PAIR_REAL = """Two versions of the same request, typed to an AI chat assistant. Which one reads more like something a real person actually typed (rather than text written or polished by an AI)? Judge naturalness and human-likeness of the wording and typing, not the quality of the request.

Message 1:
<<<
{m1}
>>>

Message 2:
<<<
{m2}
>>>

Respond with a JSON object exactly in this format:
{{"answer": 1 or 2, "reason": "brief explanation"}}
Output strictly the raw JSON and nothing else."""

PAIR_FIT = """Two versions of the same request, typed to an AI chat assistant. Which one is more plausibly written by the person described below, in their own voice? Judge the writing (register, wording, typing habits), not the request itself. Do not reward messages that merely mention facts about the person.

The person:
{background}

Message 1:
<<<
{m1}
>>>

Message 2:
<<<
{m2}
>>>

Respond with a JSON object exactly in this format:
{{"answer": 1 or 2, "reason": "brief explanation"}}
Output strictly the raw JSON and nothing else."""


def load(d):
    ps = {json.loads(l)['id']: json.loads(l) for l in open(d + '/personas.jsonl', encoding='utf-8')}
    gen = collections.defaultdict(dict)   # pair_key -> arm -> record
    for f in sorted(glob.glob(d + '/gen/*.jsonl')):
        for l in open(f, encoding='utf-8'):
            r = json.loads(l)
            if r['status'] == 'pass':
                gen[r['pair_key']][r['arm']] = r
    return ps, gen


def single(a):
    rng = random.Random(0)
    ps, gen = load(a.dir)
    # distractor pools: same source release and mode
    pool = collections.defaultdict(list)
    meta = {}
    for l in open(a.dir + '/assign.jsonl'):
        r = json.loads(l)
        meta[r['pair_key']] = r
        pool[(r['persona_source'], r['mode'])].append(r['persona_id'])
    os.makedirs(a.dir + '/judge/items', exist_ok=True)
    os.makedirs(a.dir + '/judge/results', exist_ok=True)
    shards = a.shards or 8
    sinks = [open(f'{a.dir}/judge/items/{i:03d}.jsonl', 'w', encoding='utf-8') for i in range(shards)]
    c = collections.Counter()

    def put(item):
        sinks[int(hashlib.md5(item['key'].encode()).hexdigest(), 16) % shards].write(json.dumps(item, ensure_ascii=False) + '\n')
        c[item['kind']] += 1

    for pk in sorted(gen):
        arms = gen[pk]
        m = meta[pk]
        p = ps[m['persona_id']]
        base = {'pair_key': pk, 'mode': m['mode'], 'persona_source': m['persona_source'], 'source_name': m['source_name'],
                'lang': m['target_language'] or 'English'}
        others = [x for x in pool[(m['persona_source'], m['mode'])] if x != p['id']]
        cands = rng.sample(others, 3) + [p['id']]
        rng.shuffle(cands)
        cand_txt = '\n\n'.join(f'Person {i + 1}:\n{bg_str(ps[x])}' for i, x in enumerate(cands))
        firsts = {}
        for arm, r in sorted(arms.items()):
            users = [x['content'] for x in r['result']['conversation'] if x['role'] == 'user']
            td = r['result']['metadata']['turns_detail']
            for t, rw in enumerate(users):
                if t >= len(td):
                    break
                ref = td[t].get('user_message_original') if m['mode'] == 'multilingual' else td[t].get('user_message_source')
                ref = ref or td[t].get('user_message_source')
                put(dict(base, key=f'{pk}#{arm}#intent#{t}', kind='intent', arm=arm, turn=t,
                         changed=rw.strip() != (ref or '').strip(),
                         prompt=INTENT.format(original_message=ref, rewritten_message=rw)))
                if arm == 'C':
                    put(dict(base, key=f'{pk}#C#style#{t}', kind='style', arm='C', turn=t,
                             prompt=STYLE.format(background=bg_str(p), writing_style=style_str(p, include_quirks=True),
                                                 rewritten_message=rw)))
            firsts[arm] = users[0]
            put(dict(base, key=f'{pk}#{arm}#identify', kind='identify', arm=arm, truth=cands.index(p['id']) + 1,
                     prompt=IDENTIFY.format(message=users[0], candidates=cand_txt)))
        if len(firsts) == 3:
            for x, y in (('A', 'C'), ('B', 'C'), ('A', 'B')):
                for kind, tpl in (('pair_real', PAIR_REAL), ('pair_fit', PAIR_FIT)):
                    first = rng.choice((x, y))
                    second = y if first == x else x
                    put(dict(base, key=f'{pk}#{x}{y}#{kind}', kind=kind, pair=x + y, first=first,
                             prompt=tpl.format(m1=firsts[first], m2=firsts[second], background=bg_str(p))))
    for s in sinks:
        s.close()
    json.dump({'pairs_with_any_pass': len(gen), 'all_three_pass': sum(len(v) == 3 for v in gen.values()), **c},
              open(a.dir + '/judge/prep.json', 'w'), indent=1)
    print(dict(c), sum(len(v) == 3 for v in gen.values()), 'pairs with all three arms')


def pairwise(a):
    ps, gen = load(a.dir)
    meta = {json.loads(l)['pair_key']: json.loads(l) for l in open(a.dir + '/assign.jsonl')}
    calib, main_items = [], []
    for pk in sorted(k for k, v in gen.items() if len(v) == 3):
        m = meta[pk]
        p = ps[m['persona_id']]
        base = {'pair_key': pk, 'mode': m['mode'], 'persona_source': m['persona_source'], 'source_name': m['source_name'],
                'lang': m['target_language'] or 'English'}
        msg = {x: next(t['content'] for t in r['result']['conversation'] if t['role'] == 'user') for x, r in gen[pk].items()}
        if m['mode'] == 'free' and m['source_name'] == 'wildchat':
            msg['R'] = gen[pk]['C']['result']['metadata']['turns_detail'][0]['user_message_source']
            for x in 'ABC':
                for first, second in (('R', x), (x, 'R')):
                    calib.append(dict(base, key=f'{pk}#R{x}#calib_real#{first}', kind='calib_real', pair='R' + x, first=first,
                                      prompt=PAIR_REAL.format(m1=msg[first], m2=msg[second])))
        for x, y in (('A', 'C'), ('B', 'C'), ('A', 'B')):
            for kind, tpl in (('pair_real', PAIR_REAL), ('pair_fit', PAIR_FIT)):
                for first, second in ((x, y), (y, x)):
                    main_items.append(dict(base, key=f'{pk}#{x}{y}#{kind}#{first}', kind=kind, pair=x + y, first=first,
                                           prompt=tpl.format(m1=msg[first], m2=msg[second], background=bg_str(p))))
    shards_n = a.shards or 16
    os.makedirs(a.dir + '/judge/items_pair2', exist_ok=True)
    shards = [[] for _ in range(shards_n)]
    for it in calib + main_items:   # calibration items first in every shard, so they finish first
        shards[int(hashlib.md5(it['pair_key'].encode()).hexdigest(), 16) % shards_n].append(it)
    for i, items in enumerate(shards):
        with open(f'{a.dir}/judge/items_pair2/{i:03d}.jsonl', 'w', encoding='utf-8') as fh:
            for it in items:
                fh.write(json.dumps(it, ensure_ascii=False) + '\n')
    print(len(calib), 'calibration items,', len(main_items), 'pairwise items,', shards_n, 'shards')


def rejudge(a):
    todo = {json.loads(l)['key'] for f in glob.glob(a.dir + '/judge/results/*.jsonl') for l in open(f, encoding='utf-8')
            if json.loads(l)['result'] is None}
    shards_n = a.shards or 16
    os.makedirs(a.dir + '/judge/items_rejudge', exist_ok=True)
    sinks = [open(f'{a.dir}/judge/items_rejudge/{i:03d}.jsonl', 'w', encoding='utf-8') for i in range(shards_n)]
    c, n = collections.Counter(), 0
    for f in sorted(glob.glob(a.dir + '/judge/items/*.jsonl')):
        for l in open(f, encoding='utf-8'):
            it = json.loads(l)
            if it['key'] in todo:
                sinks[n % shards_n].write(l)
                c[it['kind']] += 1
                n += 1
    for s in sinks:
        s.close()
    print(n, 'items to rejudge', dict(c))


def external(a):
    def read(sub, keep):
        return [l for f in sorted(glob.glob(f'{a.dir}/judge/{sub}/*.jsonl')) for l in open(f, encoding='utf-8')
                if keep(json.loads(l)['kind'])]
    calib = read('items_pair2', lambda k: k == 'calib_real')
    ident = read('items', lambda k: k == 'identify')
    pairs = read('items_pair2', lambda k: k != 'calib_real')
    os.makedirs(a.dir + '/judge/items_ext', exist_ok=True)
    with open(a.dir + '/judge/items_ext/all.jsonl', 'w', encoding='utf-8') as fh:
        fh.writelines(calib + ident + pairs)
    print(len(calib), 'calibration,', len(ident), 'identify,', len(pairs), 'pairwise items')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('stage', choices=['single', 'pairwise', 'rejudge', 'external'])
    ap.add_argument('--dir', required=True, help='prep.py / generate.py directory')
    ap.add_argument('--shards', type=int, default=0, help='output shards (default 8 for single, 16 otherwise)')
    a = ap.parse_args()
    {'single': single, 'pairwise': pairwise, 'rejudge': rejudge, 'external': external}[a.stage](a)


if __name__ == '__main__':
    main()
