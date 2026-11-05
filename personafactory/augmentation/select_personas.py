#!/usr/bin/env python3
"""Persona + responder assignment.

Two inputs:
  --pairs-dir  persona-pair set (augmentation.prepare_pairs): every pair is assigned in both settings, as below.
  --seeds-dir  seed pool (augmentation.prepare_seeds): every seed is assigned in its own setting, with a
               per-persona cap and the extended language tables; see assign_seeds below.

Persona-pair set:
free (language-matched): the conservative tiered selection of pipeline.select_persona:
    language filter -> location match (argmax MiniLM similarity inside the location pool)
    -> top-1 MiniLM embedding over the language pool (similarity >= 0.15) -> md5 language-pool fallback.
    Language / location analysis calls the pipeline functions in worker processes; MiniLM embeddings
    come from augmentation.embed_personas (GPU); the argmax runs on CPU in chunks with the same tier
    order and threshold. Tiers: location, embedding, language_pool, none (language not detected),
    unsupported_language (no persona speaks it); the last two get no persona.
multilingual (cross-lingual): one persona uniformly over the bank by a fixed hash of the pair key; the
    target language is the persona's resolved language (`target_language` of the pair records, see
    augmentation.prepare_pairs). Personas without a resolved language are excluded from this pool.
responder: Gemma / Ministral 50/50 by a fixed hash of (pair key, mode); one model per conversation
    (it rewrites the user turns, responds and runs the continuity check).

Inputs:  --bank (or PF_BANK), --pairs-dir (*.jsonl, sorted order, same as embed_personas),
         <out-dir>/pemb.npy and qemb.npy from augmentation.embed_personas.
Outputs: <out-dir>/free.jsonl and <out-dir>/multilingual.jsonl, one record per pair:
         {pair_key, mode, persona_id, match_tier, responder, target_language[, source_language_detected,
         source_script]}; <out-dir>/free_analysis.pkl caches the language/location analysis.

Run (CPU, after embed_personas):
  python -m personafactory.augmentation.select_personas --bank $PF_BANK --pairs-dir ./data/pairs --out-dir ./outputs/assign
  python -m personafactory.augmentation.select_personas --bank $PF_BANK --seeds-dir ./data/seeds/shards \\
      --out-dir ./outputs/assign_seeds --cap 40 --holdout-free 4002 --holdout-multilingual 6000 --workers 128
"""
import argparse, collections, glob, hashlib, json, os, pickle, re, time
from multiprocessing import Pool

from personafactory.augmentation import pipeline as H

MIN_SIM = 0.15  # persona.matching.min_embedding_similarity

PERSONAS = []
_POOLS = {}


def init_worker(bank):
    global PERSONAS
    PERSONAS = [json.loads(l) for l in open(bank, encoding='utf-8')]


def valid_pool(raw_lang_str, user_script):
    """select_persona step 2 (language_match=True), cached per (language, script)."""
    key = (raw_lang_str, user_script)
    if key not in _POOLS:
        ps = PERSONAS
        if user_script not in ('unknown', 'mixed'):
            if user_script == 'latin':
                v = [i for i, p in enumerate(ps) if H.persona_speaks_language(p, raw_lang_str)]
                if not v and raw_lang_str != 'english':
                    v = None
                elif not v:
                    v = list(range(len(ps)))
            else:
                v = [i for i, p in enumerate(ps) if H.persona_speaks_language(p, raw_lang_str)]
                if not v:
                    v = [i for i, p in enumerate(ps) if H.persona_speaks_script(p, user_script)]
                if not v:
                    v = None
        else:
            v = list(range(len(ps)))
        _POOLS[key] = v
    return _POOLS[key]


def analyse(args):
    pair_key, msg = args
    script = H.detect_script(msg)
    raw = H.detect_language(msg)
    if not raw:
        return pair_key, None, script, None, None
    raw_str = str(raw).lower()
    pool = valid_pool(raw_str, script)
    if pool is None:
        return pair_key, raw_str, script, None, None
    ok = set(pool)
    loc = sorted(i for i in H._match_by_location(msg, PERSONAS, user_script=script) if i in ok)
    return pair_key, raw_str, script, (raw_str, script), loc


def h(*parts):
    return int(hashlib.sha256('|'.join(parts).encode()).hexdigest(), 16)


def _pool_for(poolkey):
    return valid_pool(*poolkey)


def assign_pairs(a):
    """Persona-pair set: free and multilingual assignment for every pair (see the module docstring)."""
    out_dir = a.out_dir
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    init_worker(a.bank)
    pairs = []
    for fp in sorted(glob.glob(os.path.join(a.pairs_dir, '*.jsonl'))):
        for l in open(fp, encoding='utf-8'):
            if l.strip():
                p = json.loads(l)
                first = next((m['content'] for m in p['conversation'] if m['role'] == 'user'), '')
                pairs.append((p['pair_key'], first, p['persona_id'], p.get('target_language')))
    lang_of = {pid: tl for _, _, pid, tl in pairs if tl}
    ml_pool = [i for i, p in enumerate(PERSONAS) if lang_of.get(p['id'])]
    print('pairs', len(pairs), 'bank', len(PERSONAS), 'multilingual pool', len(ml_pool), flush=True)

    # multilingual + responders
    stats = collections.Counter()
    with open(os.path.join(out_dir, 'multilingual.jsonl'), 'w') as fm:
        for pk, _, _, _ in pairs:
            p = PERSONAS[ml_pool[h(pk, 'multilingual-persona') % len(ml_pool)]]
            resp = ('gemma', 'ministral')[h(pk, 'multilingual', 'responder') % 2]
            fm.write(json.dumps({'pair_key': pk, 'mode': 'multilingual', 'persona_id': p['id'],
                                 'match_tier': 'cross_lingual', 'responder': resp,
                                 'target_language': lang_of[p['id']]}) + '\n')
            stats['ml_responder/' + resp] += 1

    # free: language + location analysis in workers, MiniLM similarities from embed_personas
    cache = os.path.join(out_dir, 'free_analysis.pkl')  # the slow part; reused on reruns
    if os.path.exists(cache):
        ana = pickle.load(open(cache, 'rb'))
    else:
        with Pool(a.workers, initializer=init_worker, initargs=(a.bank,)) as pool:
            ana = {r[0]: r for r in pool.imap_unordered(analyse, [(pk, m) for pk, m, _, _ in pairs], chunksize=16)}
        pickle.dump(ana, open(cache, 'wb'))
    print('analysis done', round(time.time() - t0), 's', flush=True)
    import numpy as np
    pemb = np.load(os.path.join(out_dir, 'pemb.npy'))  # bank order
    qemb = np.load(os.path.join(out_dir, 'qemb.npy'))  # pair order, same as `pairs`
    assert pemb.shape[0] == len(PERSONAS) and qemb.shape[0] == len(pairs)
    masks = {}
    CH = 512
    with open(os.path.join(out_dir, 'free.jsonl'), 'w') as ff:
        for c0 in range(0, len(pairs), CH):
            sims_blk = qemb[c0:c0 + CH] @ pemb.T
            for j in range(sims_blk.shape[0]):
                n = c0 + j
                pk, msg = pairs[n][0], pairs[n][1]
                sims = sims_blk[j]
                _, raw, script, poolkey, loc = ana[pk]
                resp = ('gemma', 'ministral')[h(pk, 'free', 'responder') % 2]
                rec = {'pair_key': pk, 'mode': 'free', 'source_language_detected': raw, 'source_script': script,
                       'responder': resp, 'target_language': None}
                if raw is None:
                    rec.update(persona_id=None, match_tier='none')
                elif poolkey is None:
                    rec.update(persona_id=None, match_tier='unsupported_language')
                elif loc:
                    best = loc[int(np.argmax(sims[loc]))]
                    rec.update(persona_id=PERSONAS[best]['id'], match_tier='location')
                else:
                    if poolkey not in masks:
                        mk = np.zeros(len(PERSONAS), dtype=bool)
                        mk[_pool_for(poolkey)] = True
                        masks[poolkey] = mk
                    cand = np.where(masks[poolkey] & (sims >= MIN_SIM), sims, -9.0)
                    best = int(np.argmax(cand))
                    if cand[best] > -9:
                        rec.update(persona_id=PERSONAS[best]['id'], match_tier='embedding')
                    else:
                        vp = _pool_for(poolkey)
                        hh = int(hashlib.md5(msg.encode('utf-8')).hexdigest(), 16)
                        rec.update(persona_id=PERSONAS[vp[hh % len(vp)]]['id'], match_tier='language_pool')
                stats['free_tier/' + rec['match_tier']] += 1
                stats['free_responder/' + resp] += 1
                ff.write(json.dumps(rec) + '\n')
    free_ids = [json.loads(l)['persona_id'] for l in open(os.path.join(out_dir, 'free.jsonl'))]
    stats['free_distinct_personas'] = len(set(free_ids) - {None})
    stats['free_max_uses_one_persona'] = max(collections.Counter(x for x in free_ids if x).values())
    stats['multilingual_distinct_personas'] = len(
        {json.loads(l)['persona_id'] for l in open(os.path.join(out_dir, 'multilingual.jsonl'))})
    print(json.dumps(dict(stats), indent=1), 'elapsed', round(time.time() - t0), flush=True)


# ---------------------------------------------------------------- seed pool
# Hash salt shared with augmentation.prepare_seeds; it fixes persona order, seed order, responders and the
# held-out sample.
from personafactory.augmentation.prepare_seeds import HOLDOUT_SALT, SALT  # noqa: E402


def hs(*parts):
    return int(hashlib.sha256('|'.join(map(str, parts)).encode()).hexdigest(), 16)


def analyse_seed(args):
    """Prompt script / language (pipeline.detect_script / detect_language) + location-signal keywords."""
    pk, msg = args
    script = H.detect_script(msg)
    raw = H.detect_language(msg)
    raw_tokens = H._LOCATION_PATTERN.findall(msg)
    prep_tokens = H._PREP_LOCATION_PATTERN.findall(msg)
    tw = set()
    for tok in set(t.lower() for t in raw_tokens + prep_tokens):
        tw.update(re.findall(r'\b[a-z]{2,}\b', tok))
    exp = set(tw)
    if tw:
        for kws in H._SCRIPT_COUNTRY_KEYWORDS.values():
            if tw & kws:
                exp |= kws
    return pk, (str(raw).lower() if raw else None), script, sorted(exp)


def assign_seeds(a):
    """Seed pool: per-seed assignment in the seed's own setting (prepare_seeds `mode`).

    free (language-matched), same tiers as pipeline.select_persona, with two differences:
      language filter: the prompt language (pipeline.detect_language) must equal the canonical base language
        (common.lang_canon) of the persona's native_language OR main_language. Non-Latin prompts with no such
        persona fall back to script-compatible personas (pipeline.persona_speaks_script); unknown / mixed script ->
        whole bank; Latin non-English with no persona -> unsupported_language; no detected language -> none.
      per-persona cap (--cap, 40 in the released corpus): in each tier the best candidate that is not yet capped is
        taken (seeds in a fixed hash order). Location tier (pipeline._match_by_location signals: script keywords and
        place words, via an inverted index) -> best MiniLM inside the location pool; a seed whose location matches
        are all capped falls through to the embedding tier (top MiniLM over the language pool with sim >= 0.15);
        then an md5 pick in the pool. The cap is ignored only when every candidate is capped.
    multilingual (cross-lingual): personas with a resolved non-English target (lang_canon.resolve), shuffled by a
      fixed hash, assigned to the cross-lingual seeds (hash order) without replacement, cycling when exhausted.
      target_language = canonical label (translation prompt); lid_base / lid_verifiable are recorded.
    responder: Gemma / Ministral 50/50 by hash of (pair_key, mode).
    held-out sample (--holdout-free / --holdout-multilingual): the seeds with the lowest hash rank among those with a
      persona, an equal number per source, written to holdout.txt; pass it to run_augmentation --exclude.
    Needs <out-dir>/pemb.npy, qemb.npy, qkeys.txt from embed_personas --seeds-dir.
    Writes <out-dir>/{free,multilingual}.jsonl, select_stats.json and (if requested) holdout.txt.
    """
    import numpy as np
    from personafactory.common import lang_canon as L, lid
    t0 = time.time()
    out_dir = a.out_dir
    stats = collections.Counter()

    # ---- bank ----
    ids, res, words = [], [], []
    for l in open(a.bank, encoding='utf-8'):
        p = json.loads(l)
        bg = p.get('background') or {}
        r = L.resolve(p)
        ids.append(p['id'])
        res.append(r)
        # location / script fields exactly as pipeline._match_by_location uses them
        txt = f"{bg.get('sub_region', '')} {bg.get('country', '')} {bg.get('sub_region', '')} {bg.get('country', '')} {bg.get('native_language', '')} {bg.get('dialect', '')}".lower()
        words.append((set(re.findall(r'\b[a-z]{2,}\b', txt)), p))
    N = len(ids)
    stats['bank'] = N
    print('bank loaded', N, round(time.time() - t0), flush=True)
    inv = collections.defaultdict(list)
    for i, (ws, _) in enumerate(words):
        for w in ws:
            inv[w].append(i)
    inv = {w: np.array(v, dtype=np.int32) for w, v in inv.items()}
    script_sets = {}
    for sc, kws in H._SCRIPT_COUNTRY_KEYWORDS.items():
        script_sets[sc] = np.array(sorted({i for w in kws if w in inv for i in inv[w]}), dtype=np.int32)
    speaks = collections.defaultdict(list)  # base language -> persona idx (native or main)
    for i, r in enumerate(res):
        for b in {r['native_base'], r['main_base']} - {None}:
            speaks[b].append(i)
    speaks = {k: np.array(v, dtype=np.int32) for k, v in speaks.items()}
    script_ok_cache, pool_cache = {}, {}

    def script_pool(sc):
        if sc not in script_ok_cache:
            script_ok_cache[sc] = np.array([i for i, (_, p) in enumerate(words) if H.persona_speaks_script(p, sc)], dtype=np.int32)
        return script_ok_cache[sc]

    def lang_pool(raw, script):
        if script in ('unknown', 'mixed'):
            return 'all', None
        base = L.base_of(lid.norm(raw))
        v = speaks.get(base)
        if v is not None and len(v):
            return ('lang', base), v
        if script == 'latin':
            return (('all', None) if base == 'English' else (None, None))
        v = script_pool(script)
        return (('script', script), v) if len(v) else (None, None)

    def pool_of(key):
        if key not in pool_cache:
            kind, v = key
            pool_cache[key] = speaks[v] if kind == 'lang' else script_pool(v)
        return pool_cache[key]

    # ---- seeds ----
    seeds = {'free': [], 'multilingual': []}
    for fp in sorted(glob.glob(os.path.join(a.seeds_dir, '*.jsonl'))):
        mode = os.path.basename(fp).split('-')[0]
        for l in open(fp, encoding='utf-8'):
            r = json.loads(l)
            seeds[mode].append((r['pair_key'], next((m['content'] for m in r['conversation'] if m['role'] == 'user'), ''), r['source_name']))
    print('seeds', {k: len(v) for k, v in seeds.items()}, flush=True)
    os.makedirs(out_dir, exist_ok=True)

    # ---- multilingual ----
    ml = [i for i, r in enumerate(res) if r['target'] and r['base'] != 'English']
    ml.sort(key=lambda i: hs(ids[i], SALT + '-ml-order'))
    stats['ml_eligible_personas'] = len(ml)
    tl, unver, uses_ml = collections.Counter(), collections.Counter(), collections.Counter()
    with open(os.path.join(out_dir, 'multilingual.jsonl'), 'w') as fm:
        for n, (pk, _, src) in enumerate(sorted(seeds['multilingual'], key=lambda s: hs(s[0], SALT + '-ml-seed'))):
            i = ml[n % len(ml)]
            r = res[i]
            resp = ('gemma', 'ministral')[hs(pk, 'multilingual', SALT + '-responder') % 2]
            fm.write(json.dumps({'pair_key': pk, 'mode': 'multilingual', 'persona_id': ids[i], 'match_tier': 'cross_lingual',
                                 'responder': resp, 'target_language': r['target'], 'lid_base': r['base'],
                                 'lid_verifiable': r['lid_verifiable'], 'source_name': src}) + '\n')
            tl[r['target']] += 1
            uses_ml[i] += 1
            if not r['lid_verifiable']:
                unver[r['target']] += 1
            stats['ml_responder/' + resp] += 1
    stats['ml_seeds'] = len(seeds['multilingual'])
    stats['ml_distinct_personas'] = len(uses_ml)
    stats['ml_max_uses_one_persona'] = max(uses_ml.values()) if uses_ml else 0
    stats['ml_unverifiable_target_seeds'] = sum(unver.values())
    print('multilingual done', round(time.time() - t0), flush=True)

    # ---- free ----
    keys = [l.strip() for l in open(os.path.join(out_dir, 'qkeys.txt')) if l.strip()]
    qemb = np.load(os.path.join(out_dir, 'qemb.npy'), mmap_mode='r')
    pemb = np.load(os.path.join(out_dir, 'pemb.npy')).astype(np.float32)
    assert pemb.shape[0] == N and qemb.shape[0] == len(keys)
    qrow = {k: j for j, k in enumerate(keys)}
    free = sorted(seeds['free'], key=lambda s: hs(s[0], SALT + '-free-order'))
    with Pool(a.workers) as pool:
        ana = {r[0]: r for r in pool.imap_unordered(analyse_seed, [(pk, m) for pk, m, _ in free], chunksize=64)}
    print('analysis done', round(time.time() - t0), flush=True)
    uses = np.zeros(N, dtype=np.int32)
    groups = collections.defaultdict(list)
    out_rows = {}
    for pk, msg, src in free:
        _, raw, script, exp = ana[pk]
        resp = ('gemma', 'ministral')[hs(pk, 'free', SALT + '-responder') % 2]
        base_rec = {'pair_key': pk, 'mode': 'free', 'source_language_detected': raw, 'source_script': script,
                    'responder': resp, 'target_language': None, 'source_name': src}
        if raw is None:
            out_rows[pk] = dict(base_rec, persona_id=None, match_tier='none')
            continue
        key, _ = lang_pool(raw, script)
        if key is None:
            out_rows[pk] = dict(base_rec, persona_id=None, match_tier='unsupported_language')
            continue
        groups[key].append((pk, msg, exp, base_rec))
    CH = 1024
    for key, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        P = np.arange(N, dtype=np.int32) if key == 'all' else pool_of(key)
        PE = pemb[P]
        inpool = np.zeros(N, dtype=bool)
        inpool[P] = True
        pos = np.full(N, -1, dtype=np.int64)
        pos[P] = np.arange(len(P))
        for c0 in range(0, len(items), CH):
            blk = items[c0:c0 + CH]
            Q = np.stack([np.asarray(qemb[qrow[it[0]]], dtype=np.float32) for it in blk])
            S = Q @ PE.T
            for j, (pk, msg, exp, rec) in enumerate(blk):
                sims = S[j]
                sel = None
                # location tier: script keywords + place words, inside the language pool
                parts = []
                sc = rec['source_script']
                if sc in script_sets and len(script_sets[sc]):
                    parts.append(script_sets[sc])
                parts += [inv[w] for w in exp if w in inv]
                if parts:
                    mask = np.zeros(N, dtype=bool)
                    for arr in parts:
                        mask[arr] = True
                    mask &= inpool
                    loc = np.flatnonzero(mask)
                    if len(loc):
                        ls = sims[pos[loc]]
                        k = min(len(loc), 512)
                        top = np.argpartition(-ls, k - 1)[:k] if k < len(loc) else np.arange(len(loc))
                        top = top[np.argsort(-ls[top], kind='stable')]
                        ok = top[uses[loc[top]] < a.cap]
                        if len(ok) == 0 and k < len(loc):
                            top = np.argsort(-ls, kind='stable')
                            ok = top[uses[loc[top]] < a.cap]
                        if len(ok):  # all location matches capped: fall through to the embedding tier
                            sel = int(loc[ok[0]])
                            rec = dict(rec, match_tier='location', capped=False)
                        else:
                            stats['free_location_capped_to_embedding'] += 1
                if sel is None:
                    k = min(len(P), 512)
                    top = np.argpartition(-sims, k - 1)[:k]
                    top = top[np.argsort(-sims[top], kind='stable')]
                    top = top[sims[top] >= MIN_SIM]
                    cand = P[top]
                    ok = cand[uses[cand] < a.cap]
                    if len(ok) == 0 and len(top) == k:  # all of the top 512 capped: full ranking
                        allc = np.argsort(-sims, kind='stable')
                        allc = allc[sims[allc] >= MIN_SIM]
                        cand = P[allc]
                        ok = cand[uses[cand] < a.cap]
                    if len(ok):
                        sel = int(ok[0])
                        rec = dict(rec, match_tier='embedding', capped=False)
                    elif len(cand):
                        sel = int(cand[0])
                        rec = dict(rec, match_tier='embedding', capped=True)
                if sel is None:
                    free_pool = P[uses[P] < a.cap]
                    vp = free_pool if len(free_pool) else P
                    hh = int(hashlib.md5(msg.encode('utf-8')).hexdigest(), 16)
                    sel = int(vp[hh % len(vp)])
                    rec = dict(rec, match_tier='language_pool', capped=not len(free_pool))
                uses[sel] += 1
                rec['persona_id'] = ids[sel]
                rec['pool'] = key if isinstance(key, str) else '/'.join(map(str, key))
                out_rows[pk] = rec
                stats['free_capped_fallback'] += bool(rec.get('capped'))
        print('group', key, len(items), round(time.time() - t0), flush=True)
    with open(os.path.join(out_dir, 'free.jsonl'), 'w') as ff:
        for pk, _, _ in free:
            r = out_rows[pk]
            stats['free_tier/' + r['match_tier']] += 1
            stats['free_responder/' + r['responder']] += 1
            ff.write(json.dumps(r) + '\n')
    stats['free_seeds'] = len(free)
    stats['free_distinct_personas'] = int((uses > 0).sum())
    stats['free_max_uses_one_persona'] = int(uses.max())

    # ---- held-out sample ----
    held = []
    for mode, n in (('free', a.holdout_free), ('multilingual', a.holdout_multilingual)):
        if not n:
            continue
        has = {json.loads(l)['pair_key'] for l in open(os.path.join(out_dir, mode + '.jsonl'))
               if json.loads(l)['persona_id']}
        for src in ('ultrachat', 'nemotron', 'wildchat'):
            ranked = sorted((hs(HOLDOUT_SALT, pk), pk)
                            for pk, _, s in seeds[mode] if s == src and pk in has)
            held += [pk for _, pk in ranked[:n // 3]]
            stats[f'holdout/{mode}/{src}'] = len(ranked[:n // 3])
    if held:
        open(os.path.join(out_dir, 'holdout.txt'), 'w').write(''.join(k + '\n' for k in held))
    pools = collections.Counter(r.get('pool') for r in out_rows.values() if r.get('persona_id'))
    out = {'stats': dict(stats), 'free_pool_top40': pools.most_common(40),
           'free_uses_hist': {str(k): int(v) for k, v in zip(*np.unique(uses[uses > 0], return_counts=True))},
           'ml_target_distribution': tl.most_common(), 'ml_unverifiable_targets': unver.most_common(),
           'elapsed_s': round(time.time() - t0)}
    json.dump(out, open(os.path.join(out_dir, 'select_stats.json'), 'w'), indent=1, ensure_ascii=False)
    print(json.dumps(out['stats'], indent=1), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--bank', default=os.environ.get('PF_BANK'), required='PF_BANK' not in os.environ)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--pairs-dir', help='persona-pair shards (augmentation.prepare_pairs)')
    src.add_argument('--seeds-dir', help='seed-pool shards (augmentation.prepare_seeds)')
    ap.add_argument('--out-dir', default=os.path.join(os.environ.get('PF_OUT_DIR', './outputs'), 'assign'))
    ap.add_argument('--workers', type=int, default=64)
    ap.add_argument('--cap', type=int, default=40, help='seed pool: max language-matched seeds per persona')
    ap.add_argument('--holdout-free', type=int, default=0, help='seed pool: language-matched seeds held out of generation')
    ap.add_argument('--holdout-multilingual', type=int, default=0, help='seed pool: cross-lingual seeds held out')
    a = ap.parse_args()
    if a.seeds_dir:
        assign_seeds(a)
    else:
        assign_pairs(a)


if __name__ == '__main__':
    main()
