#!/usr/bin/env python3
"""LaBSE cosine similarity between original and rewritten user turns (judge-free fidelity table, LaBSE row).

Pairs are recovered from the judge items (prep_items.py). 'labse_vs_source' compares with the source turn (English
for cross-lingual records); 'labse_vs_translation_baseline' uses the literal translation for translated turns,
i.e. the same-language comparison. GPU job.

Inputs:  <judge-dir>/items/*.jsonl, --model (local sentence-transformers/LaBSE snapshot dir or hub id)
Outputs: --out JSON (default <judge-dir>/labse.json; labse_full.py can reuse its labse_vs_source groups)
Run:     python -m personafactory.evaluation.corpus_judge.labse --judge-dir ./outputs/corpus_judge --model sentence-transformers/LaBSE \
             --out $REL/labse.json
"""
import argparse, collections, glob, json, os, re
import numpy as np
import torch
from safetensors.torch import load_file
from transformers import AutoModel, AutoTokenizer


class LaBSE:
    # sentence-transformers LaBSE = BERT -> CLS pooling -> Dense(768, tanh) -> L2 normalize, max_seq 256
    def __init__(self, path):
        self.tok = AutoTokenizer.from_pretrained(path)
        self.bert = AutoModel.from_pretrained(path, torch_dtype=torch.float16).cuda().eval()
        d = load_file(os.path.join(path, '2_Dense', 'model.safetensors'))
        self.w, self.b = d['linear.weight'].cuda().half(), d['linear.bias'].cuda().half()

    @torch.no_grad()
    def encode(self, texts, batch_size=512, **_):
        out = []
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        for s in range(0, len(order), batch_size):
            idx = order[s:s + batch_size]
            enc = self.tok([texts[i] or ' ' for i in idx], padding=True, truncation=True, max_length=256, return_tensors='pt').to('cuda')
            h = self.bert(**enc).last_hidden_state[:, 0]
            v = torch.tanh(h @ self.w.T + self.b)
            out.append((idx, torch.nn.functional.normalize(v.float(), dim=-1).cpu().numpy()))
        res = np.zeros((len(texts), 768), dtype=np.float32)
        for idx, v in out:
            res[idx] = v
        return res


RX = re.compile(r'Original User Message:\n(.*)\n\nRewritten User Message:\n(.*)\n\nEvaluate whether', re.S)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--judge-dir', required=True)
    ap.add_argument('--model', default=os.environ.get('PF_LABSE_MODEL', 'sentence-transformers/LaBSE'))
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    path = a.model
    if not os.path.isdir(path):
        from huggingface_hub import snapshot_download
        path = snapshot_download(path)

    rows = []
    for fp in sorted(glob.glob(os.path.join(a.judge_dir, 'items', '*.jsonl'))):
        for line in open(fp, encoding='utf-8'):
            it = json.loads(line)
            src = RX.search(it.get('intent_prompt_vs_english_source') or it['intent_prompt'])
            base = RX.search(it['intent_prompt'])
            if src:
                rows.append((it['mode'], None, src.group(1), src.group(2), base.group(1) if base else None))
    print('pairs', len(rows), flush=True)
    model = LaBSE(path)

    rw = model.encode([r[3] for r in rows])
    so = model.encode([r[2] for r in rows])
    sim_src = (rw * so).sum(1)
    multi_idx = [i for i, r in enumerate(rows) if r[4] is not None and r[4] != r[2]]
    ba = model.encode([rows[i][4] for i in multi_idx])
    sim_base = dict(zip(multi_idx, (rw[multi_idx] * ba).sum(1)))

    def m(idx, arr):
        v = [float(arr[i]) for i in idx]
        return round(float(np.mean(v)), 4) if v else None

    groups = collections.defaultdict(list)
    for i, r in enumerate(rows):
        groups['all'].append(i)
        groups['mode/' + str(r[0])].append(i)
        groups['same_language_pairs' if (r[0] == 'free') else 'cross_or_multilingual_pairs'].append(i)
    out = {'pairs': len(rows), 'labse_vs_source': {k: {'mean': m(v, sim_src), 'n': len(v)} for k, v in groups.items()},
           'labse_vs_translation_baseline': {
               'mean': round(float(np.mean(list(sim_base.values()))), 4) if sim_base else None, 'n': len(sim_base)}}
    json.dump(out, open(a.out or os.path.join(a.judge_dir, 'labse.json'), 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
