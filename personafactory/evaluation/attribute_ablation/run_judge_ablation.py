"""Multi-judge agreement study: re-score a stratified sample of ablation rewrites with several judges.

Each sampled cell (non-baseline, rewritten, with a reply) gets a binary style-adoption and intent-preservation
verdict from every reachable judge in the config's `judges` section. Reports per-judge mean verdict rates,
pairwise raw agreement and per-rewriter means, and stores per-cell verdicts for agreement_stats.py
(Cohen's kappa, Gwet's AC1).

Inputs:  --results (run_ablation.py output), --config (judges + judge_generation)
Outputs: --out JSON {averages, agreements, by_model, cells}
Run:     python -m personafactory.evaluation.attribute_ablation.run_judge_ablation --results ./outputs/attribute_ablation/results.jsonl \
             --config evaluation/attribute_ablation/ablation_config.yaml --out ./outputs/attribute_ablation/judge_ablation.json
"""
import os
import sys
import json
import random
import asyncio
import argparse
from collections import defaultdict
from pathlib import Path
import aiohttp

from personafactory.augmentation.pipeline import build_url
from personafactory.evaluation.attribute_ablation.run_ablation import load_config
from personafactory.evaluation.attribute_ablation.metrics import score_style, score_intent


async def evaluate_cell_with_judge(session, row, judge_id, judge_config, judge_gen_cfg, sem):
    original_message = row.get("original_message")
    adapted_message = row.get("adapted_message")
    persona = row.get("persona_used")

    style_score = None
    intent_score = None

    async with sem:
        try:
            # Ask the judge for the style adoption score
            style_score = await score_style(
                session, judge_config, judge_gen_cfg,
                adapted_message, persona,
            )
        except Exception:
            pass

        try:
            # Ask the judge for the intent preservation score
            intent_score = await score_intent(
                session, judge_config, judge_gen_cfg,
                original_message, adapted_message,
            )
        except Exception:
            pass

    return judge_id, style_score, intent_score

async def process_row(session, row, resolved_judges, judge_gen_cfg, sem):
    tasks = []
    for jid, cfg in resolved_judges.items():
        tasks.append(
            asyncio.create_task(
                evaluate_cell_with_judge(session, row, jid, cfg, judge_gen_cfg, sem)
            )
        )

    results = await asyncio.gather(*tasks)
    row_scores = {}
    for jid, style, intent in results:
        row_scores[jid] = {"style": style, "intent": intent}

    return {
        "sample_id": row.get("sample_id"),
        "condition": row.get("condition"),
        "model_id": row.get("model_id"),
        "original_message": row.get("original_message"),
        "adapted_message": row.get("adapted_message"),
        "response": row.get("response"),
        "judge_scores": row_scores
    }

async def check_judge_online(session, judge_config) -> bool:
    url = build_url(judge_config["base_url"])
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {judge_config['api_key']}"
    }
    payload = {
        "model": judge_config["model"],
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1
    }
    try:
        async with session.post(url, headers=headers, json=payload, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False

async def main():
    parser = argparse.ArgumentParser(description="Run Judge Ablation Study")
    parser.add_argument(
        "--results",
        required=True,
        help="run_ablation.py output JSONL",
    )
    parser.add_argument(
        "--config",
        default=os.path.join(os.path.dirname(__file__), "ablation_config.yaml"),
        help="config with the `judges` section and judge_generation",
    )
    parser.add_argument("--out", default="./outputs/attribute_ablation/judge_ablation.json")
    parser.add_argument(
        "--samples-count",
        type=int,
        default=100,
        help="Number of cells to sample for the judge ablation",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Maximum concurrent judge API calls",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    judge_gen_cfg = config["judge_generation"]

    resolved_judges = {jid: {"id": jid, **cfg} for jid, cfg in config["judges"].items()}

    # Check online status of judges dynamically
    online_judges = {}
    print("Checking judge endpoints status...")
    async with aiohttp.ClientSession() as session:
        for jid, cfg in resolved_judges.items():
            is_online = await check_judge_online(session, cfg)
            if is_online:
                online_judges[jid] = cfg
                print(f"  - {jid:<12} ({cfg['model']}): ONLINE")
            else:
                print(f"  - {jid:<12} ({cfg['model']}): OFFLINE (skipping)")
                
    if not online_judges:
        print("Error: No judge models are online. Exiting.")
        return
        
    resolved_judges = online_judges

    # Load rows that are completed and have persona/response
    rows = []
    with open(args.results, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cond = row.get("condition")
                orig = row.get("original_message")
                adap = row.get("adapted_message")
                resp = row.get("response")
                persona = row.get("persona_used")
                
                if cond != "baseline" and orig and adap and resp and persona and adap != orig:
                    rows.append(row)

    print(f"Loaded {len(rows)} candidate cells for judge ablation.")
    if not rows:
        print("No completed cells found.")
        return

    # Group by responder model
    rows_by_model = defaultdict(list)
    for r in rows:
        model_id = r.get("model_id")
        if model_id:
            rows_by_model[model_id].append(r)

    # Select a deterministic sample stratified by model_id
    random.seed(42)
    
    num_models = len(rows_by_model)
    if num_models == 0:
        print("No responder models found in completed cells.")
        return
        
    samples_per_model = args.samples_count // num_models
    if samples_per_model == 0:
        samples_per_model = 1

    sampled_rows = []
    print(f"Performing stratified sampling (target: {samples_per_model} cells per responder model):")
    for model_id, model_rows in sorted(rows_by_model.items()):
        k = min(samples_per_model, len(model_rows))
        sampled = random.sample(model_rows, k)
        sampled_rows.extend(sampled)
        print(f"  - {model_id}: sampled {len(sampled)} / {len(model_rows)} cells")

    sample_size = len(sampled_rows)
    print(f"Total sampled cells for evaluation: {sample_size}")

    sem = asyncio.Semaphore(args.concurrency)
    completed = 0
    evaluated_rows = []

    async with aiohttp.ClientSession() as session:
        tasks = []
        for r in sampled_rows:
            tasks.append(
                asyncio.create_task(
                    process_row(session, r, resolved_judges, judge_gen_cfg, sem)
                )
            )

        for fut in asyncio.as_completed(tasks):
            res = await fut
            evaluated_rows.append(res)
            completed += 1
            print(f"  Processed cell [{completed}/{sample_size}]", flush=True)

    # Output stats
    # 1. Average scores per judge
    averages = {}
    for jid in resolved_judges.keys():
        style_vals = [r["judge_scores"][jid]["style"] for r in evaluated_rows if r["judge_scores"][jid]["style"] is not None]
        intent_vals = [r["judge_scores"][jid]["intent"] for r in evaluated_rows if r["judge_scores"][jid]["intent"] is not None]
        averages[jid] = {
            "style": sum(style_vals) / len(style_vals) if style_vals else 0.0,
            "intent": sum(intent_vals) / len(intent_vals) if intent_vals else 0.0,
            "style_count": len(style_vals),
            "intent_count": len(intent_vals)
        }

    # 2. Agreement rate matrices
    agreements = {}
    judge_names = list(resolved_judges.keys())
    for i in range(len(judge_names)):
        for j in range(i + 1, len(judge_names)):
            j1, j2 = judge_names[i], judge_names[j]
            
            style_agree_matches = 0
            style_total_matches = 0
            intent_agree_matches = 0
            intent_total_matches = 0
            
            for r in evaluated_rows:
                s1 = r["judge_scores"][j1]["style"]
                s2 = r["judge_scores"][j2]["style"]
                if s1 is not None and s2 is not None:
                    style_total_matches += 1
                    if s1 == s2:
                        style_agree_matches += 1
                        
                i1 = r["judge_scores"][j1]["intent"]
                i2 = r["judge_scores"][j2]["intent"]
                if i1 is not None and i2 is not None:
                    intent_total_matches += 1
                    if i1 == i2:
                        intent_agree_matches += 1
            
            agreements[f"{j1}_vs_{j2}"] = {
                "style": style_agree_matches / style_total_matches if style_total_matches else 0.0,
                "intent": intent_agree_matches / intent_total_matches if intent_total_matches else 0.0,
                "style_total": style_total_matches,
                "intent_total": intent_total_matches
            }

    # 3. Average scores per judge grouped by responder model
    by_model = {}
    responder_ids = sorted(list(set(r["model_id"] for r in evaluated_rows)))
    for jid in resolved_judges.keys():
        by_model[jid] = {}
        for rid in responder_ids:
            style_vals = [
                r["judge_scores"][jid]["style"]
                for r in evaluated_rows
                if r["model_id"] == rid and r["judge_scores"][jid]["style"] is not None
            ]
            intent_vals = [
                r["judge_scores"][jid]["intent"]
                for r in evaluated_rows
                if r["model_id"] == rid and r["judge_scores"][jid]["intent"] is not None
            ]
            by_model[jid][rid] = {
                "style": sum(style_vals) / len(style_vals) if style_vals else 0.0,
                "intent": sum(intent_vals) / len(intent_vals) if intent_vals else 0.0,
                "count": len(style_vals)
            }

    payload = {
        "averages": averages,
        "agreements": agreements,
        "by_model": by_model,
        "cells": evaluated_rows
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("\n" + "="*50)
    print("=== JUDGE ABLATION RESULTS ===")
    print("="*50)
    print(f"Average Scores (on {sample_size} cells):")
    print(f"{'Judge':12} | {'Style Score':12} | {'Intent Score':12}")
    print("-"*45)
    for jid, avgs in averages.items():
        print(f"{jid:12} | {avgs['style']:.1%} ({avgs['style_count']}) | {avgs['intent']:.1%} ({avgs['intent_count']})")
    
    print("\nPairwise Agreement Rates:")
    print(f"{'Comparison':20} | {'Style Agreement':15} | {'Intent Agreement':15}")
    print("-"*60)
    for pair, agree in agreements.items():
        print(f"{pair:20} | {agree['style']:.1%} ({agree['style_total']}) | {agree['intent']:.1%} ({agree['intent_total']})")
    print("="*50)
    print(f"Data saved to {out_path}")

if __name__ == "__main__":
    asyncio.run(main())
