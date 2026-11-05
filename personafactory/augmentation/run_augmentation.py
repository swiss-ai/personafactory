#!/usr/bin/env python3
"""Generation driver: runs pipeline.process_conversation on seed records with the persona / match tier / responder
pre-assigned by augmentation.select_personas. Resumable per output shard.

Two input kinds (--input-kind):
  pairs  persona-pair shards (augmentation.prepare_pairs); target languages are checked by their LID-normalized
         name (common.lid.norm).
  seeds  seed-pool shards (augmentation.prepare_seeds); target languages are checked as their canonical base
         language (common.lang_canon.base_of: dialects and varieties count as their base language), and targets
         the detector cannot label (lid_verifiable False) or labels unreliably (Uzbek) are accepted unchecked.
The conversation id (`key`) is the sha256 of json [namespace, pair_key, mode]; the namespace is fixed per input kind
(PAIRS_NAMESPACE / prepare_seeds.ID_NAMESPACE), so ids are deterministic across reruns.

Inputs:
  --pairs         seed shard files (*.jsonl); only pair_key, conversation, source_id, source_name, split
                  (and seed_language) are read here.
  --assign-dir    directory with free.jsonl / multilingual.jsonl from select_personas.
  --select / --exclude  optional files of pair_keys to restrict to / to skip (e.g. the held-out sample).
  --responder     optional override of the assigned responder (used to regenerate a subset with Gemma).
  --bank          persona bank JSONL (or PF_BANK).
  --gemma / --ministral / --minimax
                  OpenAI-compatible base URLs (.../v1) of the two responders and the sanity judge
                  (or PF_GEMMA_URL / PF_MINISTRAL_URL / PF_MINIMAX_URL); model names as served
                  (--gemma-model etc.). The responder named "gemma" also does the literal translation
                  in the multilingual mode. An API key, if needed, is read from PF_API_KEY.
  --lid-model     fastText lid.176 model (or PF_LID_MODEL) for the target-language check.
Output: <outdir>/<mode>-<shard>.jsonl, one wrapper per pair:
  {key, pair_key, mode, persona_id, match_tier, responder, target_language, source_id, source_name, split,
   [seed_language, lid_verifiable,] pipeline, status, [sanity_status,] result[, exception]}
  status: pass = every turn passed the sanity judge; fail = at least one turn did not; lang_fail =
  multilingual record whose first user turn is not in the target language; no_persona = selection found
  no persona (free mode); error otherwise. result = process_conversation output plus source_conversation.

Run (per shard group, both modes can run in parallel against the same servers):
  python -m personafactory.augmentation.run_augmentation --input-kind seeds --pairs ./data/seeds/shards/free-*.jsonl \\
      --mode free --assign-dir ./outputs/assign_seeds --exclude ./outputs/assign_seeds/holdout.txt \\
      --outdir ./outputs/seeds_run/gen --gemma http://HOST:8000/v1 --ministral http://HOST:8001/v1 \\
      --minimax http://HOST:30000/v1 --concurrency 100
"""
import argparse, asyncio, collections, copy, hashlib, json, os, re, time
from pathlib import Path
import aiohttp

from personafactory.augmentation import pipeline as H
from personafactory.augmentation.prepare_seeds import ID_NAMESPACE as SEEDS_NAMESPACE
from personafactory.common import lang_canon, lid

# Id namespace of the persona-pair set.
PAIRS_NAMESPACE = 'personafactory-pairs-id'
NAMESPACE = {'pairs': PAIRS_NAMESPACE, 'seeds': SEEDS_NAMESPACE}
# lid.176 labels correct Latin Uzbek as Turkish (p < 0.5) and Lingua has no Uzbek
LID_UNRELIABLE = {'Uzbek'}

# production generation settings
BASE_CONFIG = {
    'generation': {'max_tokens': 4096, 'temperature': 0.3, 'top_p': 0.95},
    'judge_generation': {'max_tokens': 3072, 'temperature': 0.1, 'top_p': 1.0},
    'adaptation_generation': {'max_tokens': 8192, 'temperature': 0.3, 'top_p': 0.95},
    'processing': {'max_adaptations': 2, 'max_retries': 3},
    'persona': {'use_persona': True, 'inject_system_prompt': True, 'temperature': 0.7,
                'max_adapt_retries': 2, 'min_adapt_length_ratio': 0.5, 'verbal_quirk_prob': 0.25},
}


def lang_ok(text, target):
    """Persona-pair set: target checked by its LID-normalized name."""
    # TooShort / Unknown cannot be verified either way; English would be detected, so accept them
    found = lid.detect(text)
    t = lid.norm(target)
    if t == 'Norwegian' and found == 'Danish':  # lid.176 routinely labels Bokmal as Danish
        return True
    return found in ('TooShort', 'Unknown') or lid.matches(found, t)


def lang_ok_base(text, target):
    """Seed pool: target checked as its canonical base language; unverifiable targets are accepted."""
    t = lang_canon.base_of(target)
    if not lang_canon.lid_verifiable(target) or t in LID_UNRELIABLE:
        return True
    found = lid.detect(text)
    if t == 'Norwegian' and found == 'Danish':
        return True
    return found in ('TooShort', 'Unknown') or lid.matches(found, t)


LANG_CHECK = {'pairs': lang_ok, 'seeds': lang_ok_base}


def key_of(pair_key, mode, kind='seeds'):
    return hashlib.sha256(json.dumps([NAMESPACE[kind], pair_key, mode]).encode()).hexdigest()


def load_bank(path, need):
    """Bank records whose id is in need (cheap regex pre-filter on the raw line, then a full parse)."""
    bank, rid = {}, re.compile(r'"id":\s*"([^"]+)"')
    for l in open(path, encoding='utf-8'):
        m = rid.search(l)
        if m and m.group(1) in need:
            p = json.loads(l)
            if p['id'] in need:
                bank[p['id']] = p
    if len(bank) < len(need):  # the first "id" of a line was not the persona id: full parse
        for l in open(path, encoding='utf-8'):
            p = json.loads(l)
            if p['id'] in need:
                bank[p['id']] = p
    return bank


async def main():
    env = os.environ.get
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--input-kind', choices=('pairs', 'seeds'), required=True,
                    help='pairs: persona-pair shards (prepare_pairs); seeds: seed-pool shards (prepare_seeds)')
    ap.add_argument('--pairs', nargs='+', required=True)
    ap.add_argument('--select', help='file of pair_keys to restrict to')
    ap.add_argument('--exclude', help='file of pair_keys to skip (e.g. select_personas holdout.txt)')
    ap.add_argument('--responder', choices=('gemma', 'ministral'), help='override the assigned responder')
    ap.add_argument('--mode', choices=('free', 'multilingual'), required=True)
    ap.add_argument('--assign-dir', default=os.path.join(env('PF_OUT_DIR', './outputs'), 'assign'))
    ap.add_argument('--bank', default=env('PF_BANK'), required='PF_BANK' not in os.environ)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--gemma', default=env('PF_GEMMA_URL'), required='PF_GEMMA_URL' not in os.environ)
    ap.add_argument('--ministral', default=env('PF_MINISTRAL_URL'), required='PF_MINISTRAL_URL' not in os.environ)
    ap.add_argument('--minimax', default=env('PF_MINIMAX_URL'), required='PF_MINIMAX_URL' not in os.environ)
    ap.add_argument('--gemma-model', default=env('PF_GEMMA_MODEL', 'gemma'), help='served model name')
    ap.add_argument('--ministral-model', default=env('PF_MINISTRAL_MODEL', 'ministral'))
    ap.add_argument('--minimax-model', default=env('PF_MINIMAX_MODEL', 'MiniMax-M2.5'))
    ap.add_argument('--lid-model', default=env('PF_LID_MODEL'), required='PF_LID_MODEL' not in os.environ,
                    help='fastText lid.176.ftz')
    ap.add_argument('--concurrency', type=int, default=120)
    a = ap.parse_args()
    lid.init(a.lid_model)
    kind, check = a.input_kind, LANG_CHECK[a.input_kind]
    sel = set(l.strip() for l in open(a.select)) if a.select else None
    excl = set(l.strip() for l in open(a.exclude)) if a.exclude else set()
    assign = {}
    for l in open(os.path.join(a.assign_dir, a.mode + '.jsonl')):
        r = json.loads(l)
        if (sel is None or r['pair_key'] in sel) and r['pair_key'] not in excl:
            if a.responder:
                r['responder'] = a.responder
            assign[r['pair_key']] = r
    bank = load_bank(a.bank, {r['persona_id'] for r in assign.values() if r['persona_id']})
    config = copy.deepcopy(BASE_CONFIG)
    config['persona']['language_match'] = a.mode == 'free'
    # multilingual restyles a same-language translation, so the script-stability guard stays on
    config['persona']['cross_lingual'] = False
    api_key = env('PF_API_KEY', 'dummy')  # local vLLM / SGLang servers ignore the key
    config['responders'] = [{'name': 'gemma', 'base_url': a.gemma, 'api_key': api_key, 'model': a.gemma_model},
                            {'name': 'ministral', 'base_url': a.ministral, 'api_key': api_key, 'model': a.ministral_model}]
    config['judge'] = {'base_url': a.minimax, 'api_key': api_key, 'model': a.minimax_model}
    config['_lang_ok'] = check
    os.makedirs(a.outdir, exist_ok=True)
    stats = collections.Counter()
    t0 = time.time()
    conn = aiohttp.TCPConnector(limit=a.concurrency * 3)
    async with aiohttp.ClientSession(connector=conn, timeout=aiohttp.ClientTimeout(total=900)) as session:
        sem = asyncio.Semaphore(a.concurrency)
        handles, done, work = {}, set(), []
        for fp in a.pairs:
            pairs = [json.loads(l) for l in open(fp, encoding='utf-8') if l.strip()]
            pairs = [p for p in pairs if p['pair_key'] in assign]
            if not pairs:
                continue
            out = os.path.join(a.outdir, f'{a.mode}-{Path(fp).stem}.jsonl')
            if os.path.exists(out):
                for l in open(out, encoding='utf-8'):
                    try:
                        done.add(json.loads(l)['key'])
                    except Exception:
                        pass
            handles[out] = open(out, 'a', encoding='utf-8')
            work += [(p, handles[out]) for p in pairs]

        async def one(p, fh):
            asg = assign[p['pair_key']]
            key = key_of(p['pair_key'], a.mode, kind)
            if key in done:
                stats['skipped_done'] += 1
                return
            wrap = {'key': key, 'pair_key': p['pair_key'], 'mode': a.mode, 'persona_id': asg['persona_id'],
                    'match_tier': asg['match_tier'], 'responder': asg['responder'],
                    'target_language': asg['target_language'], 'source_id': p.get('source_id'),
                    'source_name': p.get('source_name'), 'split': p.get('split')}
            if kind == 'seeds':
                wrap.update(seed_language=p.get('seed_language'), lid_verifiable=asg.get('lid_verifiable'))
            wrap['pipeline'] = NAMESPACE[kind]
            if not asg['persona_id']:
                wrap.update(status='no_persona', result=None)
            else:
                cfg = dict(config)
                cfg['_assigned'] = {'persona': bank[asg['persona_id']], 'match_tier': asg['match_tier'],
                                    'responder': asg['responder'], 'target_language': asg['target_language']}
                async with sem:
                    try:
                        res = await H.process_conversation(session, p['conversation'], cfg, key)
                        md = res.get('metadata', {})
                        first = next((m['content'] for m in res.get('conversation', []) if m['role'] == 'user'), '')
                        if md.get('status') != 'success' or not res.get('conversation'):
                            status = 'error'
                        elif asg['target_language'] and not check(first, asg['target_language']):
                            status = 'lang_fail'
                        else:
                            status = 'pass' if md.get('sanity_pass') else 'fail'
                        if kind == 'seeds':
                            wrap['sanity_status'] = md.get('sanity_status')
                        res['source_conversation'] = p['conversation']
                        wrap.update(status=status, result=res)
                    except Exception as exc:
                        wrap.update(status='error', result=None, exception=f'{type(exc).__name__}: {exc}'[:500])
            fh.write(json.dumps(wrap, ensure_ascii=False) + '\n')
            fh.flush()
            stats[wrap['status']] += 1
            n = sum(v for k, v in stats.items() if k != 'skipped_done')
            if n % 200 == 0:
                print(json.dumps({**stats, 'elapsed_min': round((time.time() - t0) / 60, 1)}), flush=True)

        await asyncio.gather(*(one(p, fh) for p, fh in work))
        for fh in handles.values():
            fh.close()
    print('final', json.dumps(stats), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
