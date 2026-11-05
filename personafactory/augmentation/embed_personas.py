#!/usr/bin/env python3
"""MiniLM embeddings for language-matched ("free") persona selection.

Reproduces sentence-transformers all-MiniLM-L6-v2 exactly with plain transformers: BERT, mean pooling
over the attention mask, L2 normalisation, max_seq_length 256, fp32. Persona text = description or
character_description or pipeline.get_persona_characteristics_str (as in pipeline.process_dataset);
prompt text = the first user turn of each seed.

Inputs:  --bank persona_bank.jsonl (or PF_BANK) and one of
         --pairs-dir  persona-pair shards (*.jsonl, sorted file order; augmentation.prepare_pairs): every pair
         --seeds-dir  seed-pool shards (augmentation.prepare_seeds): only the language-matched seeds (free-*.jsonl),
                      the only ones that use embedding matching
Outputs: <out-dir>/pemb.npy (bank order), <out-dir>/qemb.npy (seed order), [N, 384] in --dtype; with --seeds-dir
         also <out-dir>/qkeys.txt (pair_key per qemb row).
The seed-pool assignment of the released corpus used --dtype float16 --batch-size 1024.

Run (GPU node):
  python -m personafactory.augmentation.embed_personas --bank $PF_BANK --pairs-dir ./data/pairs --out-dir ./outputs/assign
  python -m personafactory.augmentation.embed_personas --bank $PF_BANK --seeds-dir ./data/seeds/shards \
      --out-dir ./outputs/assign_seeds --dtype float16 --batch-size 1024
"""
import argparse, glob, json, os
import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from personafactory.augmentation.pipeline import get_persona_characteristics_str


def load_pair_prompts(pairs_dir):
    msgs = []
    for fp in sorted(glob.glob(os.path.join(pairs_dir, '*.jsonl'))):
        for l in open(fp, encoding='utf-8'):
            if l.strip():
                p = json.loads(l)
                msgs.append(next((m['content'] for m in p['conversation'] if m['role'] == 'user'), ''))
    return msgs


def load_seed_prompts(seeds_dir):
    keys, msgs = [], []
    for fp in sorted(glob.glob(os.path.join(seeds_dir, 'free-*.jsonl'))):
        for l in open(fp, encoding='utf-8'):
            if l.strip():
                r = json.loads(l)
                keys.append(r['pair_key'])
                msgs.append(next((m['content'] for m in r['conversation'] if m['role'] == 'user'), ''))
    return keys, msgs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--bank', default=os.environ.get('PF_BANK'), required='PF_BANK' not in os.environ)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--pairs-dir')
    src.add_argument('--seeds-dir')
    ap.add_argument('--out-dir', default=os.path.join(os.environ.get('PF_OUT_DIR', './outputs'), 'assign'))
    ap.add_argument('--minilm', default='sentence-transformers/all-MiniLM-L6-v2', help='HF id or local path')
    ap.add_argument('--device', default='cuda')
    ap.add_argument('--batch-size', type=int, default=512)
    ap.add_argument('--dtype', choices=('float32', 'float16'), default='float32', help='storage dtype (compute is fp32)')
    a = ap.parse_args()

    tok = AutoTokenizer.from_pretrained(a.minilm)
    model = AutoModel.from_pretrained(a.minilm).to(a.device).eval()  # fp32, as sentence-transformers

    @torch.no_grad()
    def enc(texts, bs=a.batch_size):
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        out = np.zeros((len(texts), 384), dtype=a.dtype)
        for s in range(0, len(order), bs):
            idx = order[s:s + bs]
            b = tok([texts[i] or ' ' for i in idx], padding=True, truncation=True, max_length=256,
                    return_tensors='pt').to(a.device)
            h = model(**b).last_hidden_state.float()
            m = b['attention_mask'].unsqueeze(-1).float()
            v = torch.nn.functional.normalize((h * m).sum(1) / m.sum(1).clamp(min=1e-9), dim=-1)
            out[idx] = v.cpu().numpy().astype(a.dtype)
        return out

    personas = [json.loads(l) for l in open(a.bank, encoding='utf-8') if l.strip()]
    ptxt = [p.get('description') or p.get('character_description') or get_persona_characteristics_str(p)
            for p in personas]
    os.makedirs(a.out_dir, exist_ok=True)
    np.save(os.path.join(a.out_dir, 'pemb.npy'), enc(ptxt))
    if a.seeds_dir:
        keys, msgs = load_seed_prompts(a.seeds_dir)
        open(os.path.join(a.out_dir, 'qkeys.txt'), 'w').write('\n'.join(keys) + '\n')
    else:
        msgs = load_pair_prompts(a.pairs_dir)
    np.save(os.path.join(a.out_dir, 'qemb.npy'), enc(msgs))
    print('embedded personas', len(ptxt), 'prompts', len(msgs))


if __name__ == '__main__':
    main()
