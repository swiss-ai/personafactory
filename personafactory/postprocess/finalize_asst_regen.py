#!/usr/bin/env python3
"""Swap the Ministral assistant turns of the cross-lingual high-resource seed-pool conversations for their Gemma
regeneration (assistant.regenerate_assistant --stage user_persona on the postprocess.asst_regen_prep inputs).

A conversation is swapped only if the regeneration passed the sanity gate on every turn, its user turns are identical
to the released ones, its assistant 3-gram repeat share is <= 0.3 and the released responder is Ministral; otherwise
the Ministral version stays. Swapped records get responder 'gemma', the new sanity_verdicts and
assistant_regenerated 'gemma'. Shards of <release>/data are rewritten in place (tmp + rename); replaced originals are
appended to <release>/asst_regen_replaced.jsonl, counts -> <release>/asst_regen.json.

  python -m personafactory.postprocess.finalize_asst_regen --release-dir ./release_merged \\
      --regen-dir ./outputs/asst_regen/user_persona
"""
import argparse, collections, glob, json, os
from multiprocessing import Pool

from personafactory.postprocess.lowres_quality import rep_score

NEW = {}


def load(regen_dir):
    for fp in glob.glob(os.path.join(regen_dir, '*.jsonl')):
        for l in open(fp, encoding='utf-8'):
            try:
                x = json.loads(l)
            except ValueError:
                continue
            if x.get('status') == 'pass' or x['id'] not in NEW:
                NEW[x['id']] = x


def rid(line):
    return line[8:72] if line.startswith('{"id": "') else json.loads(line)['id']


def shard(fp):
    st, out, rep = collections.Counter(), [], []
    for l in open(fp, encoding='utf-8'):
        x = NEW.get(rid(l))
        if x is None:
            out.append(l)
            continue
        r = json.loads(l)
        conv = x.get('conversation') or []
        why = None
        if x.get('status') != 'pass':
            why = 'keep_gate_' + str(x.get('status'))
        elif [m['content'] for m in conv if m['role'] == 'user'] != [m['content'] for m in r['conversation'] if m['role'] == 'user']:
            why = 'keep_user_turns_differ'
        elif rep_score('\n'.join(m['content'] for m in conv if m['role'] == 'assistant')) > .3:
            why = 'keep_repetition'
        elif r.get('responder') != 'ministral':
            why = 'keep_not_ministral'
        if why:
            st[why] += 1
            out.append(l)
            continue
        rep.append(l)
        r.update(conversation=conv, responder='gemma', sanity_verdicts=x.get('sanity_verdicts'), assistant_regenerated='gemma')
        out.append(json.dumps(r, ensure_ascii=False) + '\n')
        st['swapped'] += 1
    if rep:
        with open(fp + '.tmp', 'w', encoding='utf-8') as fo:
            fo.writelines(out)
        os.replace(fp + '.tmp', fp)
    return st, rep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release-dir', required=True)
    ap.add_argument('--regen-dir', required=True, help='regenerate_assistant output directory (<out-dir>/user_persona)')
    ap.add_argument('--workers', type=int, default=64)
    a = ap.parse_args()
    load(a.regen_dir)  # before the fork, so the workers share NEW
    st = collections.Counter({'regenerated': len(NEW)})
    with Pool(a.workers) as pool, open(os.path.join(a.release_dir, 'asst_regen_replaced.jsonl'), 'a', encoding='utf-8') as fr:
        for s, rep in pool.imap_unordered(shard, sorted(glob.glob(os.path.join(a.release_dir, 'data', '*.jsonl')))):
            st.update(s)
            fr.writelines(rep)
    st['not_found_in_release'] = st['regenerated'] - sum(v for k, v in st.items() if k == 'swapped' or k.startswith('keep_'))
    json.dump({'counts': dict(st)}, open(os.path.join(a.release_dir, 'asst_regen.json'), 'w'), indent=1)
    print(json.dumps(dict(st), indent=1))


if __name__ == '__main__':
    main()
