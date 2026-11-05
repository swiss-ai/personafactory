#!/usr/bin/env python3
"""Style metrics of the SFT ablation over the probe responses of every model in --responses.

Judge-free style features per response (Table tab:mp-sft-features): words, markdown headers / bullets / bold,
emoji, exclamations, contractions per 100 words, questions, Flesch reading ease (own syllable heuristic), mean
sentence length, and formality (s-nlp/roberta-base-formality-ranker, P(formal)).

Style-perturbation analysis (same request, 12 user personas + unstyled control; Table tab:mp-sft-adapt):
  - sensitivity: within-request (request-demeaned) Pearson r between a user-message feature and the
    matching response feature, pooled over requests (formality->formality, words->words, emoji->emoji,
    lowercase start->formality). 0 = the model ignores the user's style.
  - style diversity: mean pairwise cosine distance between the 12 persona-variant responses of a request in
    a content-independent style embedding (AnnaWegmann/Style-Embedding), averaged over requests.
  - content stability: LaBSE cosine between each persona-variant response and the control response of the
    same request (high = the answer stays the same while the style adapts).
Writes style_metrics.json. GPU optional (used if available). The three encoders are loaded from the Hugging Face
cache (downloaded on first use; set HF_HUB_OFFLINE=1 on offline nodes after pre-fetching).

Run from the repo root:
  python -m personafactory.sft_ablation.style_metrics
"""
import argparse, collections, glob, json, math, os, re, statistics as st
import numpy as np
import torch
from huggingface_hub import snapshot_download
from safetensors.torch import load_file
from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer

OUT_ROOT = os.path.join(os.environ.get('PF_OUT_DIR', './outputs'), 'sft_ablation')


def snap(repo):
    """Local snapshot directory of a HF model repo (PyTorch weights, tokenizer and config files only)."""
    return snapshot_download(repo, ignore_patterns=['*.h5', '*.onnx', 'onnx/*', 'openvino/*', '*.msgpack', '*.ot', 'tf_model*'])


DEV = 'cuda' if torch.cuda.is_available() else 'cpu'
EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿]')
VOW = re.compile(r'[aeiouy]+', re.I)


def syllables(w):
    w = w.lower().strip('.,!?;:"\'()')
    n = len(VOW.findall(w))
    if w.endswith('e') and n > 1:
        n -= 1
    return max(n, 1)


def feats(t):
    words = re.findall(r"[A-Za-z']+", t)
    sents = [s for s in re.split(r'[.!?]+\s', t) if s.strip()]
    lines = t.splitlines()
    nw = max(len(words), 1)
    fre = 206.835 - 1.015 * (nw / max(len(sents), 1)) - 84.6 * (sum(syllables(w) for w in words) / nw)
    return {'words': len(t.split()), 'headers': sum(bool(re.match(r'\s*#{1,6} ', l)) for l in lines),
            'bullets': sum(bool(re.match(r'\s*([-*•]|\d+[.)]) ', l)) for l in lines), 'bold': t.count('**') // 2,
            'emoji': len(EMOJI.findall(t)), 'exclaim': t.count('!'), 'questions': t.count('?'),
            'contractions_per100': 100 * len(re.findall(r"\b\w+'(s|re|ve|ll|d|t|m)\b", t, re.I)) / nw,
            'flesch': fre, 'sent_len': nw / max(len(sents), 1)}


class Formality:
    def __init__(self):
        p = snap('s-nlp/roberta-base-formality-ranker')
        self.tok = AutoTokenizer.from_pretrained(p)
        self.m = AutoModelForSequenceClassification.from_pretrained(p).to(DEV).eval()
        labels = {v.lower(): k for k, v in self.m.config.id2label.items()}
        self.idx = labels.get('formal', 1)

    @torch.no_grad()
    def __call__(self, texts, bs=64):
        out = []
        for i in range(0, len(texts), bs):
            b = self.tok(texts[i:i + bs], truncation=True, max_length=256, padding=True, return_tensors='pt').to(DEV)
            out += torch.softmax(self.m(**b).logits, -1)[:, self.idx].tolist()
        return out


class Encoder:
    """sentence-transformers-equivalent encoders without the library dependency.
    style: AnnaWegmann/Style-Embedding = RoBERTa, mean pooling, max 512 tokens.
    labse: sentence-transformers/LaBSE = BERT CLS -> Dense(768, tanh), max 256 tokens. Both L2-normalised."""
    def __init__(self, kind):
        self.kind = kind
        self.path = snap('AnnaWegmann/Style-Embedding') if kind == 'style' else snap('sentence-transformers/LaBSE')
        self.tok = AutoTokenizer.from_pretrained(self.path)
        self.m = AutoModel.from_pretrained(self.path).to(DEV).eval()
        self.maxlen = 512 if kind == 'style' else 256
        if kind == 'labse':
            d = load_file(self.path + '/2_Dense/model.safetensors')
            self.w, self.b = d['linear.weight'].to(DEV), d['linear.bias'].to(DEV)

    @torch.no_grad()
    def encode(self, texts, batch_size=64, **_):
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        out = np.zeros((len(texts), 768), dtype=np.float32)
        for s0 in range(0, len(order), batch_size):
            idx = order[s0:s0 + batch_size]
            b = self.tok([texts[i] or ' ' for i in idx], padding=True, truncation=True, max_length=self.maxlen,
                         return_tensors='pt').to(DEV)
            h = self.m(**b).last_hidden_state
            if self.kind == 'style':
                mk = b['attention_mask'].unsqueeze(-1).float()
                v = (h * mk).sum(1) / mk.sum(1).clamp(min=1e-9)
            else:
                v = torch.tanh(h[:, 0] @ self.w.T + self.b)
            out[idx] = torch.nn.functional.normalize(v.float(), dim=-1).cpu().numpy()
        return out


def demeaned_r(xs, ys, groups):
    gx, gy = collections.defaultdict(list), collections.defaultdict(list)
    for x, y, g in zip(xs, ys, groups):
        gx[g].append(x); gy[g].append(y)
    mx = {g: st.mean(v) for g, v in gx.items()}
    my = {g: st.mean(v) for g, v in gy.items()}
    dx = np.array([x - mx[g] for x, g in zip(xs, groups)])
    dy = np.array([y - my[g] for y, g in zip(ys, groups)])
    if dx.std() == 0 or dy.std() == 0:
        return None
    return round(float(np.corrcoef(dx, dy)[0, 1]), 3)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--probes', default=os.path.join(OUT_ROOT, 'probes', 'probes.jsonl'))
    ap.add_argument('--responses', default=os.path.join(OUT_ROOT, 'responses'), help='directory of <tag>.jsonl files')
    ap.add_argument('--out', default=os.path.join(OUT_ROOT, 'style_metrics.json'))
    a = ap.parse_args()
    probes = {json.loads(l)['probe_id']: json.loads(l) for l in open(a.probes, encoding='utf-8')}
    models = {}
    for fp in sorted(glob.glob(os.path.join(a.responses, '*.jsonl'))):
        rs = [json.loads(l) for l in open(fp, encoding='utf-8')]
        models[rs[0]['model']] = {r['probe_id']: r['response'] for r in rs}
    form = Formality()
    style = Encoder('style')
    labse = Encoder('labse')
    styled = [pid for pid, p in probes.items() if p['persona_idx'] is not None and p['user_message']]
    uf = {pid: feats(probes[pid]['user_message']) for pid in styled}
    ufm = dict(zip(styled, form([probes[pid]['user_message'] for pid in styled])))
    for pid in styled:
        m = probes[pid]['user_message'].strip()
        uf[pid]['lower_start'] = float(bool(m) and m[0].islower())
    out = {'probes_styled': len(styled), 'models': {}}
    for name, resp in models.items():
        pids = [p for p in probes if p in resp]
        fs = {p: feats(resp[p]) for p in pids}
        fm = dict(zip(pids, form([resp[p] for p in pids])))
        for p in pids:
            fs[p]['formality'] = fm[p]
        sp = [p for p in styled if p in resp]
        g = [probes[p]['request_id'] for p in sp]
        sens = {'formality->formality': demeaned_r([ufm[p] for p in sp], [fs[p]['formality'] for p in sp], g),
                'user_words->words': demeaned_r([math.log1p(uf[p]['words']) for p in sp], [math.log1p(fs[p]['words']) for p in sp], g),
                'user_emoji->emoji': demeaned_r([float(uf[p]['emoji'] > 0) for p in sp], [float(fs[p]['emoji'] > 0) for p in sp], g),
                'user_lowercase->formality': demeaned_r([uf[p]['lower_start'] for p in sp], [fs[p]['formality'] for p in sp], g),
                'user_formality->contractions': demeaned_r([ufm[p] for p in sp], [fs[p]['contractions_per100'] for p in sp], g)}
        emb = dict(zip(sp, style.encode([resp[p] for p in sp], batch_size=64, normalize_embeddings=True)))
        by_req = collections.defaultdict(list)
        for p in sp:
            by_req[probes[p]['request_id']].append(emb[p])
        div = []
        for vs in by_req.values():
            if len(vs) > 1:
                M = np.stack(vs)
                sim = M @ M.T
                n = len(vs)
                div.append(1 - (sim.sum() - n) / (n * (n - 1)))
        ctrl = {probes[p]['request_id']: resp[p] for p in pids if probes[p]['persona_idx'] is None}
        pairs = [(p, ctrl[probes[p]['request_id']]) for p in sp if probes[p]['request_id'] in ctrl]
        e1 = labse.encode([resp[p] for p, _ in pairs], batch_size=64, normalize_embeddings=True)
        e2 = labse.encode([c for _, c in pairs], batch_size=64, normalize_embeddings=True)
        stab = (e1 * e2).sum(1)
        agg = {k: round(st.mean(f[k] for f in fs.values()), 3) for k in next(iter(fs.values()))}
        agg['pct_with_headers'] = round(100 * st.mean(f['headers'] > 0 for f in fs.values()), 1)
        agg['pct_with_bullets'] = round(100 * st.mean(f['bullets'] > 0 for f in fs.values()), 1)
        agg['pct_with_emoji'] = round(100 * st.mean(f['emoji'] > 0 for f in fs.values()), 1)
        agg['median_words'] = st.median(f['words'] for f in fs.values())
        out['models'][name] = {'responses': len(pids), 'point2_style_features_mean': agg, 'point1_sensitivity_r': sens,
                               'point1_style_diversity': round(float(st.mean(div)), 4),
                               'point1_content_stability_labse': round(float(stab.mean()), 4),
                               'formality_sd_across_personas': round(float(st.mean(
                                   st.pstdev([fs[p]['formality'] for p in sp if probes[p]['request_id'] == r])
                                   for r in by_req)), 4)}
    json.dump(out, open(a.out, 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
