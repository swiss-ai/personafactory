"""Dedup / diversity filter, run on judged candidates after validate_personas. Greedy and order-aware:
the best-scored profiles are kept first, then every candidate must pass, in this order:

  1. exact / normalized duplicate check on character_description and example_message;
  2. caps: max profiles per (country, sub_region, occupation) cell, per full seed cell
     (cell x gender x age bin x AI stance x fluency) and per canonical 7-key typing-style combination
     (as a share of the expected output);
  3. embedding near-duplicate check against everything already kept and against the reference bank(s):
     drop when the character_description cosine, or the joint cosine min(desc, style), exceeds its
     threshold. Embeddings: intfloat/multilingual-e5-large, mean pooling, "query: " prefix.

Reference banks (--reference, any number of files) are always kept and count toward every cap; candidates
are deduplicated against them. For the released bank the extended-grid candidates were filtered against
the base-grid bank, and the Europe / Southeast Asia candidates against the base-grid bank plus the kept
extended-grid profiles (see README.md).

Priority order: judge realism (desc), stereotype severity (asc), then sha1(salt + id); the salt makes the
order deterministic.

Inputs : judged JSONL (rows without validation.verdict == "keep" are ignored unless --no_verdict).
Outputs: --output kept JSONL, --dropped JSONL (with a `diversity_drop` reason), --report JSON.

Example (one GPU node; on offline compute nodes the embedding model must already be in $HF_HOME):
    python -m personafactory.persona_bank.diversity_filter \
        --input  ./data/persona_bank/extended/validated_all.jsonl \
        --reference ./data/persona_bank/base/persona_bank.jsonl \
        --output ./data/persona_bank/extended/diversity/kept.jsonl \
        --dropped ./data/persona_bank/extended/diversity/dropped.jsonl \
        --report ./data/persona_bank/extended/diversity/report.json \
        --emb_cache ./data/persona_bank/extended/diversity/emb
"""
import argparse
import collections
import hashlib
import json
import os
import time

import numpy as np

from personafactory.persona_bank.style_norm import canon_style, style_string, text_norm

DEFAULTS = dict(desc_thr=0.96, joint_thr=0.95, max_per_cell=12, max_per_full_cell=2,
                max_style_combo_share=0.03)


def age_bin(a):
    a = int(a)
    return "18-29" if a < 30 else "30-44" if a < 45 else "45-59" if a < 60 else "60+"


def keys(p):
    b = p["background"]
    cell = (b["country"], b["sub_region"], b["occupation"])
    full = cell + (b["gender"], age_bin(b["age"]), b["ai_stance"], b["digital_fluency"])
    combo = canon_style(p["style"].get("chatting_style_structured") or {})
    return cell, full, combo


def priority(p, salt):
    v = p.get("validation") or {}
    realism = v.get("realism", 0) or 0
    stereo = v.get("stereotype_severity", 0) or 0
    h = int(hashlib.sha1((salt + p["id"]).encode()).hexdigest()[:8], 16) / 0xffffffff
    return (-realism, stereo, h)


class Embedder:
    def __init__(self, model_name, device, batch, max_len):
        import torch
        from transformers import AutoModel, AutoTokenizer
        self.torch = torch
        self.dev = device
        self.tok = AutoTokenizer.from_pretrained(model_name)
        dtype = torch.bfloat16 if device == "cuda" else torch.float32
        self.model = AutoModel.from_pretrained(model_name, torch_dtype=dtype).to(device).eval()
        self.batch, self.max_len = batch, max_len

    def __call__(self, texts):
        torch = self.torch
        # Lone UTF-16 surrogates (broken emoji from the generators) make the fast tokenizer raise TypeError,
        # so round-trip every text through UTF-8 with replacement (strip_surrogates.py fixes the files).
        texts = [t.encode("utf-8", "replace").decode("utf-8") for t in texts]
        out = np.zeros((len(texts), self.model.config.hidden_size), dtype=np.float16)
        order = np.argsort([len(t) for t in texts])[::-1]
        for s in range(0, len(texts), self.batch):
            idx = order[s:s + self.batch]
            enc = self.tok(["query: " + texts[i] for i in idx], padding=True, truncation=True,
                           max_length=self.max_len, return_tensors="pt").to(self.dev)
            with torch.no_grad():
                h = self.model(**enc).last_hidden_state.float()
            m = enc["attention_mask"].unsqueeze(-1).float()
            e = torch.nn.functional.normalize((h * m).sum(1) / m.sum(1), dim=-1)
            out[idx] = e.cpu().numpy().astype(np.float16)
        return out


def embed_rows(rows, emb, cache_dir, tag):
    # The cache is reused only if it holds the same ids in the same order (a run with other caps or
    # thresholds has a different candidate set, possibly of equal size).
    ids = hashlib.sha1("\n".join(p["id"] for p in rows).encode()).hexdigest()
    if cache_dir:
        fd, fs = os.path.join(cache_dir, f"{tag}_desc.npy"), os.path.join(cache_dir, f"{tag}_style.npy")
        fi = os.path.join(cache_dir, f"{tag}_ids.sha1")
        if (os.path.exists(fd) and os.path.exists(fs) and os.path.exists(fi)
                and open(fi).read().strip() == ids and len(np.load(fd, mmap_mode="r")) == len(rows)):
            return np.load(fd), np.load(fs)
    A = emb([p.get("character_description") or "" for p in rows])
    B = emb([style_string(p["style"]) for p in rows])
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        np.save(fd, A)
        np.save(fs, B)
        open(fi, "w").write(ids + "\n")
    return A, B


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--dropped", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--reference", nargs="*", default=[],
                    help="Bank file(s) that are always kept; candidates are deduped against them and they count "
                         "toward the caps.")
    ap.add_argument("--no_verdict", action="store_true", help="Do not require validation.verdict == 'keep'.")
    ap.add_argument("--target_total", type=int, default=0,
                    help="Expected output size (reference + kept), used for the style-combo cap. 0 = candidates + reference.")
    ap.add_argument("--desc_thr", type=float, default=DEFAULTS["desc_thr"],
                    help="Drop if character_description cosine to any kept profile exceeds this.")
    ap.add_argument("--joint_thr", type=float, default=DEFAULTS["joint_thr"],
                    help="Drop if min(desc cosine, style cosine) to any kept profile exceeds this.")
    ap.add_argument("--max_per_cell", type=int, default=DEFAULTS["max_per_cell"],
                    help="Max profiles per (country, sub_region, occupation); 0 = no cap.")
    ap.add_argument("--max_per_full_cell", type=int, default=DEFAULTS["max_per_full_cell"],
                    help="Max per cell x gender x age bin x stance x fluency; 0 = no cap.")
    ap.add_argument("--max_style_combo_share", type=float, default=DEFAULTS["max_style_combo_share"],
                    help="Max share of the output per canonical 7-key typing-style combination; 0 = no cap.")
    ap.add_argument("--emb_model", default="intfloat/multilingual-e5-large")
    ap.add_argument("--emb_cache", default="", help="Directory to cache embeddings (npy).")
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--max_len", type=int, default=512)
    ap.add_argument("--chunk", type=int, default=2048, help="Candidates per greedy GPU block.")
    ap.add_argument("--salt", default="personafactory-diversity",
                    help="Tie-break hash salt (deterministic order).")
    ap.add_argument("--device", default="auto")
    args = ap.parse_args()
    t0 = time.time()
    for path in (args.output, args.dropped, args.report):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    import torch
    dev = ("cuda" if torch.cuda.is_available() else "cpu") if args.device == "auto" else args.device

    rows = []
    n_in, n_not_keep = 0, 0
    for line in open(args.input):
        if not line.strip():
            continue
        p = json.loads(line)
        n_in += 1
        if not args.no_verdict and (p.get("validation") or {}).get("verdict") != "keep":
            n_not_keep += 1
            continue
        rows.append(p)
    ref = [json.loads(l) for path in args.reference for l in open(path) if l.strip()]
    rows.sort(key=lambda p: priority(p, args.salt))
    total = args.target_total or (len(rows) + len(ref))
    combo_cap = int(args.max_style_combo_share * total) if args.max_style_combo_share > 0 else 0
    print(f"input {n_in} (not keep: {n_not_keep}), candidates {len(rows)}, reference {len(ref)}, "
          f"style-combo cap {combo_cap}, device {dev}", flush=True)

    # ---- 1+2: exact dups and caps (reference rows count toward the caps) ----
    seen_desc, seen_msg = set(), set()
    n_cell, n_full, n_combo = collections.Counter(), collections.Counter(), collections.Counter()
    for p in ref:
        seen_desc.add(text_norm(p.get("character_description")))
        seen_msg.add(text_norm(p["style"].get("example_message")))
        c, f, s = keys(p)
        n_cell[c] += 1
        n_full[f] += 1
        n_combo[s] += 1
    stage1, dropped = [], []
    reasons = collections.Counter()
    for p in rows:
        d, m = text_norm(p.get("character_description")), text_norm(p["style"].get("example_message"))
        c, f, s = keys(p)
        why = None
        if d in seen_desc:
            why = "dup_description"
        elif m and m in seen_msg:
            why = "dup_example_message"
        elif args.max_per_cell and n_cell[c] >= args.max_per_cell:
            why = "cap_cell"
        elif args.max_per_full_cell and n_full[f] >= args.max_per_full_cell:
            why = "cap_full_cell"
        elif combo_cap and n_combo[s] >= combo_cap:
            why = "cap_style_combo"
        if why:
            reasons[why] += 1
            p["diversity_drop"] = {"reason": why}
            dropped.append(p)
            continue
        seen_desc.add(d)
        seen_msg.add(m)
        n_cell[c] += 1
        n_full[f] += 1
        n_combo[s] += 1
        stage1.append(p)
    print(f"after exact-dup + caps: {len(stage1)} ({dict(reasons)})", flush=True)

    # ---- 3: embedding near-dup greedy ----
    emb = Embedder(args.emb_model, dev, args.batch, args.max_len)
    RA, RB = embed_rows(ref, emb, args.emb_cache, "reference") if ref else (np.zeros((0, 1024), np.float16),) * 2
    CA, CB = embed_rows(stage1, emb, args.emb_cache, "candidates")
    print(f"embedded ({time.time() - t0:.0f}s)", flush=True)
    dim = CA.shape[1]
    cap = len(RA) + len(CA)
    KA = torch.zeros((cap, dim), dtype=torch.float16, device=dev)
    KB = torch.zeros((cap, dim), dtype=torch.float16, device=dev)
    nk = len(RA)
    kept_ids = [p["id"] for p in ref]   # row of KA/KB -> profile id (for audit of near-dup drops)
    if nk:
        KA[:nk] = torch.from_numpy(RA).to(dev)
        KB[:nk] = torch.from_numpy(RB).to(dev)
    kept = []
    for s in range(0, len(stage1), args.chunk):
        e = min(len(stage1), s + args.chunk)
        qa = torch.from_numpy(CA[s:e]).to(dev)
        qb = torch.from_numpy(CB[s:e]).to(dev)
        if nk:
            sa = (qa @ KA[:nk].T).float()
            sb = (qb @ KB[:nk].T).float()
            best_d, arg_d = sa.max(1)
            best_j, arg_j = torch.minimum(sa, sb).max(1)
            del sa, sb
        else:
            best_d = torch.full((e - s,), -1.0, device=dev)
            best_j = torch.full((e - s,), -1.0, device=dev)
            arg_d = arg_j = torch.zeros((e - s,), dtype=torch.long, device=dev)
        # within-block greedy: a candidate is compared with earlier ACCEPTED candidates of the block
        wa = (qa @ qa.T).float()
        wj = torch.minimum(wa, (qb @ qb.T).float())
        bd, bj = best_d.cpu().numpy(), best_j.cpu().numpy()
        ad, aj = arg_d.cpu().numpy(), arg_j.cpu().numpy()
        wa_np, wj_np = wa.cpu().numpy(), wj.cpu().numpy()
        acc = []
        for i in range(e - s):
            d_i, j_i = float(bd[i]), float(bj[i])
            nn_d = kept_ids[ad[i]] if nk else None
            nn_j = kept_ids[aj[i]] if nk else None
            if acc:
                k = int(np.argmax(wa_np[i, acc]))
                if wa_np[i, acc[k]] > d_i:
                    d_i, nn_d = float(wa_np[i, acc[k]]), stage1[s + acc[k]]["id"]
                k = int(np.argmax(wj_np[i, acc]))
                if wj_np[i, acc[k]] > j_i:
                    j_i, nn_j = float(wj_np[i, acc[k]]), stage1[s + acc[k]]["id"]
            p = stage1[s + i]
            if d_i > args.desc_thr:
                reasons["near_dup_description"] += 1
                p["diversity_drop"] = {"reason": "near_dup_description", "cos": round(d_i, 4), "nn_id": nn_d}
                dropped.append(p)
            elif j_i > args.joint_thr:
                reasons["near_dup_joint"] += 1
                p["diversity_drop"] = {"reason": "near_dup_joint", "cos": round(j_i, 4), "nn_id": nn_j}
                dropped.append(p)
            else:
                acc.append(i)
        if acc:
            ia = torch.tensor(acc, device=dev)
            KA[nk:nk + len(acc)] = qa[ia]
            KB[nk:nk + len(acc)] = qb[ia]
            nk += len(acc)
            kept.extend(stage1[s + i] for i in acc)
            kept_ids.extend(stage1[s + i]["id"] for i in acc)
        print(f"  block {e}/{len(stage1)}: kept {len(kept)} ({time.time() - t0:.0f}s)", flush=True)

    with open(args.output, "w") as f:
        for p in kept:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    with open(args.dropped, "w") as f:
        for p in dropped:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    combos = collections.Counter(keys(p)[2] for p in kept + ref)
    cells = collections.Counter(keys(p)[0] for p in kept + ref)
    rep = {"input": n_in, "not_keep_verdict": n_not_keep, "candidates": len(rows), "reference": len(ref),
           "kept_new": len(kept), "output_total_with_reference": len(kept) + len(ref),
           "dropped": dict(reasons), "params": vars(args),
           "style_combos_distinct": len(combos), "style_combo_top1_share": round(combos.most_common(1)[0][1] / max(1, sum(combos.values())), 4),
           "cells_occupied": len(cells), "max_cell": max(cells.values()) if cells else 0,
           "seconds": round(time.time() - t0, 1)}
    json.dump(rep, open(args.report, "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in rep.items() if k != "params"}, default=str))


if __name__ == "__main__":
    main()
