#!/usr/bin/env python3
"""Pairwise comparison of fine-tuned models on real messy WildChat prompts (wildchat_prompts.py).

  prep  items for every pair X:Y, both presentation orders, from <results-dir>/<tag>/gen.jsonl (gen_eval.py)
        -> <data-dir>/wc_items<_run>/all.jsonl
  agg   per judge (<data-dir>/wc_results_<judge><_run>/, judge_client.py output) and pair: win / draw / loss over
        prompts (win = same pick in both orders), raw win rate over decisive verdicts, and a length-controlled (LC)
        win rate: logistic regression of the per-order verdict on log(len X / len Y), read off at equal length
        (intercept), 95% interval by bootstrap over prompts (1,000 resamples)
        -> <results-dir>/wildchat_pairwise<_run>.json and .md

Pairs come from --pairs (X:Y ...), else a file (--pairs-file, one X:Y per line), else the PAIRS environment
variable ('X:Y,X:Y'). Pass PAIRS through the environment or a file, never through `sbatch --export`: it splits its
argument on commas. Judges in the paper: Qwen/Qwen3.6-35B-A3B (label qwen36) and Muse-Glimmer-30B (label muse), both
outside the pipeline.

  python -m personafactory.downstream.eval.wildchat_pairwise prep --data-dir $D --results-dir $R --pairs A2:A0r A2:A1 A2:A0
  python -m personafactory.downstream.eval.judge_client --shards $D/wc_items/all.jsonl --outdir $D/wc_results_qwen36 \
      --urls $QWEN_URL --model qwen --max-tokens 8192 --concurrency 256
  python -m personafactory.downstream.eval.wildchat_pairwise agg --data-dir $D --results-dir $R --judges qwen36 muse
"""
import argparse, collections, glob, json, math, os

import numpy as np

PROMPT = """A user sent the message below to an AI assistant. Two assistant responses follow. Which response serves this user better: it understands what they meant (even if the message is informal, misspelled or in another language), answers in the user's language, is correct and helpful, and fits how the user wrote? Do not prefer a response just because it is longer.

User message:
<<<
{q}
>>>

Response 1:
<<<
{r1}
>>>

Response 2:
<<<
{r2}
>>>

Respond with a JSON object exactly in this format:
{{"answer": 1 or 2, "reason": "brief explanation"}}
Output strictly the raw JSON and nothing else."""


def gens(results_dir, tag):
    out = {}
    for l in open(os.path.join(results_dir, tag, 'gen.jsonl'), encoding='utf-8'):
        r = json.loads(l)
        if r['bench'] == 'wildchat':
            out[r['id']] = r['response'] or ''
    return out


def prep(D, R, PAIRS, SX):
    prompts = {r['id']: r for r in map(json.loads, open(os.path.join(D, 'wildchat.jsonl'), encoding='utf-8'))}
    tags = sorted({t for p in PAIRS for t in p})
    G = {t: gens(R, t) for t in tags}
    os.makedirs(os.path.join(D, f'wc_items{SX}'), exist_ok=True)
    n = 0
    with open(os.path.join(D, f'wc_items{SX}', 'all.jsonl'), 'w', encoding='utf-8') as f:
        for x, y in PAIRS:
            for i, p in prompts.items():
                if i not in G[x] or i not in G[y]:
                    continue
                for first, second in ((x, y), (y, x)):
                    f.write(json.dumps({'key': f'{x}|{y}|{i}|{first}', 'kind': 'pair', 'pair': f'{x}|{y}', 'id': i, 'first': first,
                                        'group': p['meta']['group'], 'len_x': len(G[x][i]), 'len_y': len(G[y][i]),
                                        'prompt': PROMPT.format(q=p['prompt'], r1=G[first][i], r2=G[second][i])}, ensure_ascii=False) + '\n')
                    n += 1
    print('items', n)


def logit_fit(X, y, iters=50):
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ w))
        H = X.T @ (X * (p * (1 - p))[:, None]) + 1e-6 * np.eye(X.shape[1])
        w += np.linalg.solve(H, X.T @ (y - p))
    return w


def agg(D, R, JUDGES, SX):
    rep = {}
    rng = np.random.default_rng(0)
    for J in JUDGES:
        res = []
        for f in glob.glob(os.path.join(D, f'wc_results_{J}{SX}', '*.jsonl')):
            res += [json.loads(l) for l in open(f, encoding='utf-8')]
        for pair in sorted({r['pair'] for r in res}):
            x, y = pair.split('|')
            for group in ('all', 'en', 'other'):
                rs = [r for r in res if r['pair'] == pair and r['result'] in (1, 2) and (group == 'all' or r['group'] == group)]
                by = collections.defaultdict(dict)
                rows = []
                for r in rs:
                    winner = r['first'] if r['result'] == 1 else (y if r['first'] == x else x)
                    by[r['id']][r['first']] = winner
                    rows.append((r['id'], 1.0 if winner == x else 0.0, math.log(max(1, r['len_x']) / max(1, r['len_y']))))
                c = collections.Counter(v[x] if v[x] == v[y] else 'draw' for v in by.values() if len(v) == 2)
                n = c[x] + c[y] + c['draw']
                if not rows:
                    continue
                ids = sorted({r[0] for r in rows})
                pos = collections.defaultdict(list)
                for k, (i, yv, lr) in enumerate(rows):
                    pos[i].append(k)
                Y = np.array([r[1] for r in rows]); L = np.array([r[2] for r in rows])
                X = np.column_stack([np.ones(len(rows)), L])
                lc = 1 / (1 + math.exp(-logit_fit(X, Y)[0]))
                bs = []
                for _ in range(1000):
                    pick = rng.choice(len(ids), len(ids))
                    k = np.concatenate([pos[ids[j]] for j in pick])
                    bs.append(1 / (1 + math.exp(-logit_fit(X[k], Y[k])[0])))
                rep[f'{J}/{pair}/{group}'] = {
                    'x_wins': round(100 * c[x] / n, 1) if n else None, 'draws': round(100 * c['draw'] / n, 1) if n else None,
                    'y_wins': round(100 * c[y] / n, 1) if n else None, 'prompts': n,
                    'raw_winrate_x': round(100 * Y.mean(), 1), 'lc_winrate_x': round(100 * lc, 1),
                    'lc_ci95': [round(100 * v, 1) for v in np.percentile(bs, [2.5, 97.5])],
                    'median_len_ratio': round(float(np.exp(np.median(L))), 2)}
    json.dump(rep, open(os.path.join(R, f'wildchat_pairwise{SX}.json'), 'w'), indent=1)
    L_ = ['# WildChat messy prompts: pairwise, both orders (win = same pick in both orders)', '',
          '| judge | X vs Y | prompts | X wins | draws | Y wins | raw win rate X | LC win rate X (95% CI) | len X / len Y |',
          '|---|---|---|---|---|---|---|---|---|']
    for k, v in rep.items():
        J, pair, group = k.split('/')
        if group != 'all':
            continue
        L_.append(f"| {J} | {pair.replace('|', ' vs ')} | {v['prompts']} | {v['x_wins']} | {v['draws']} | {v['y_wins']} | "
                  f"{v['raw_winrate_x']} | {v['lc_winrate_x']} [{v['lc_ci95'][0]}, {v['lc_ci95'][1]}] | {v['median_len_ratio']} |")
    open(os.path.join(R, f'wildchat_pairwise{SX}.md'), 'w').write('\n'.join(L_) + '\n')
    print('\n'.join(L_))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('step', choices=['prep', 'agg'])
    ap.add_argument('--data-dir', required=True, help='dir with wildchat.jsonl; items and judge results go here')
    ap.add_argument('--results-dir', required=True, help='dir with <tag>/gen.jsonl; the report goes here')
    ap.add_argument('--pairs', nargs='*', default=None, metavar='X:Y')
    ap.add_argument('--pairs-file', default=None)
    ap.add_argument('--judges', nargs='+', default=['qwen36', 'muse'], help='judge labels (result dir suffixes)')
    ap.add_argument('--run', default=os.environ.get('RUN', ''), help='name suffix of items / results / report')
    a = ap.parse_args()
    if a.pairs:
        spec = a.pairs
    elif a.pairs_file:
        spec = [l.strip() for l in open(a.pairs_file) if l.strip()]
    else:
        spec = [p for p in os.environ.get('PAIRS', '').split(',') if p]
    pairs = [tuple(p.split(':')) for p in spec]
    sx = f'_{a.run}' if a.run else ''
    if a.step == 'prep':
        if not pairs:
            ap.error('give --pairs, --pairs-file or PAIRS')
        prep(a.data_dir, a.results_dir, pairs, sx)
    else:
        agg(a.data_dir, a.results_dir, a.judges, sx)


if __name__ == '__main__':
    main()
