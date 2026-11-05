"""Main async runner for the per-attribute ablation (baseline + 16 single-attribute conditions x four rewriters).

For each (sample x condition x model) cell:
  1. [non-baseline] Rewrite the user message in the condition persona's voice.
  2. [non-baseline] Score style adoption and intent preservation (LLM judge from the config).
  3. Generate a reply (with or without the persona system prompt).
  4. Score script stability (detect_script comparison, no LLM call).
  5. Append the result row to the output JSONL (checkpoint-safe).

The condition persona is the sample's matched base persona with exactly one attribute overridden
(apply_ablation_override). Base personas come from the optional sample->persona mapping, else from the pipeline's
matcher with embedding fallback, else a hash-selected persona.

Resume: (sample_id, condition, model_id) triples already written without error are skipped; the output file is
appended to, not overwritten.

Inputs:  ablation_config.yaml (models, judge, sample file, persona bank files, optional mapping)
Outputs: results JSONL (one row per cell, with scores.style / scores.intent / scores.script_stability)
Run:     python -m personafactory.evaluation.attribute_ablation.run_ablation --config evaluation/attribute_ablation/ablation_config.yaml
         smoke test: ... --num-samples 5 --models glm --concurrency 5 --output ./outputs/attribute_ablation/smoke.jsonl
"""

import sys
import os
import json
import asyncio
import argparse
import random
from pathlib import Path
import yaml
import aiohttp

from personafactory.augmentation.pipeline import (
    call_api,
    get_persona_characteristics_str,
    get_persona_background_str,
    get_persona_style_str,
    strip_reasoning,
    detect_script,
    should_skip_persona,
    select_persona,
)
from personafactory.augmentation.prompts import ADAPT_USER_PROMPT_TEMPLATE, PERSONA_SYSTEM_PROMPT_TEMPLATE
from personafactory.evaluation.attribute_ablation.conditions import CONDITIONS, NEUTRAL_PERSONA
from personafactory.evaluation.attribute_ablation.metrics import score_style, score_intent, score_script_stability


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _resolve_env(obj):
    """Replace "ENV=VAR" string values with the value of that environment variable."""
    if isinstance(obj, dict):
        return {k: _resolve_env(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env(v) for v in obj]
    if isinstance(obj, str) and obj.startswith("ENV="):
        return os.environ.get(obj[4:], "")
    return obj


def load_config(config_path: str) -> dict:
    with open(config_path, "r") as f:
        return _resolve_env(yaml.safe_load(f))


def load_existing_results(output_path):
    """Return set of (sample_id, condition, model_id) already written successfully.

    A cell is only considered done if its latest attempt produced a non-null
    response AND did not result in an error (e.g., adaptation or generation failures).
    """
    latest_state = {}
    if not os.path.exists(output_path):
        return set()
    
    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                key = (row["sample_id"], row["condition"], row["model_id"])
                latest_state[key] = row
            except (json.JSONDecodeError, KeyError):
                pass
                
    done = set()
    for key, row in latest_state.items():
        if row.get("response") and not row.get("error"):
            done.add(key)
    return done


def apply_ablation_override(base_p: dict, cond_id: str) -> dict | None:
    if cond_id == "baseline":
        return None
        
    import copy
    p = copy.deepcopy(base_p)
    bg = p.setdefault("background", {})
    sty = p.setdefault("style", {})
    
    desc_override = ""
    
    if cond_id == "digital_low":
        bg["digital_fluency"] = "Low"
        desc_override = "Digital fluency: Low"
    elif cond_id == "digital_high":
        bg["digital_fluency"] = "High"
        desc_override = "Digital fluency: High"
    elif cond_id == "sent_short":
        sty["sentence_length_tendency"] = "Short/Fragmented"
        desc_override = "Sentence length: Short/Fragmented"
    elif cond_id == "sent_long":
        sty["sentence_length_tendency"] = "Long/Elaborate"
        desc_override = "Sentence length: Long/Elaborate"
    elif cond_id == "stance_skeptical":
        bg["ai_stance"] = "Skeptical"
        desc_override = "AI stance: Skeptical"
    elif cond_id == "stance_enthusiastic":
        bg["ai_stance"] = "Enthusiastic"
        desc_override = "AI stance: Enthusiastic"
    elif cond_id == "age_young":
        bg["age"] = 20
        desc_override = "Age: 20"
    elif cond_id == "age_old":
        bg["age"] = 68
        desc_override = "Age: 68"
    elif cond_id == "gender_male":
        bg["gender"] = "Male"
        desc_override = "Gender: Male"
    elif cond_id == "gender_female":
        bg["gender"] = "Female"
        desc_override = "Gender: Female"
    elif cond_id == "edu_low":
        bg["education"] = {
            "level": "No formal education",
            "field_of_study": "",
            "institution_type": "None",
        }
        desc_override = "Education: No formal education"
    elif cond_id == "edu_high":
        bg["education"] = {
            "level": "Doctoral degree",
            "field_of_study": "Computer Science",
            "institution_type": "Elite / Research university",
        }
        desc_override = "Education: Doctoral degree in Computer Science"
    elif cond_id == "occ_tech":
        bg["occupation"] = "Software Engineer"
        hobbies = bg.setdefault("hobbies_interests", [])
        if isinstance(hobbies, list):
            bg["hobbies_interests"] = list(set(hobbies + ["Programming", "Open-source projects"]))
        else:
            bg["hobbies_interests"] = ["Programming", "Open-source projects"]
        desc_override = "Occupation: Software Engineer"
    elif cond_id == "occ_manual":
        bg["occupation"] = "Manual laborer"
        hobbies = bg.setdefault("hobbies_interests", [])
        if isinstance(hobbies, list):
            bg["hobbies_interests"] = list(set(hobbies + ["Gardening", "Fishing"]))
        else:
            bg["hobbies_interests"] = ["Gardening", "Fishing"]
        desc_override = "Occupation: Manual laborer"
    elif cond_id == "hobbies_tech":
        hobbies = bg.setdefault("hobbies_interests", [])
        if isinstance(hobbies, list):
            bg["hobbies_interests"] = list(set(hobbies + ["Gaming", "AI tools", "Programming", "Online communities"]))
        else:
            bg["hobbies_interests"] = ["Gaming", "AI tools", "Programming", "Online communities"]
        desc_override = "Hobbies: Gaming and Tech"
    elif cond_id == "hobbies_outdoor":
        hobbies = bg.setdefault("hobbies_interests", [])
        if isinstance(hobbies, list):
            bg["hobbies_interests"] = list(set(hobbies + ["Hiking", "Bird watching", "Gardening", "Camping"]))
        else:
            bg["hobbies_interests"] = ["Hiking", "Bird watching", "Gardening", "Camping"]
        desc_override = "Hobbies: Hiking and Outdoor"

    # Append override notice to character description
    if desc_override:
        orig_desc = p.get("character_description") or p.get("description") or ""
        p["character_description"] = f"{orig_desc} (Override Note: {desc_override})"
        
    return p


# ---------------------------------------------------------------------------
# Per-cell processing
# ---------------------------------------------------------------------------

async def process_cell(
    session,
    sample,
    condition_id,
    persona,
    model_config,
    adapt_gen_cfg,
    gen_cfg,
    judge_gen_cfg,
    judge_model_config=None,
):
    """
    Process one (sample x condition x model) cell and return the result row.
    Never raises; errors are captured in the row with score = None.
    """
    sample_id = sample["sample_id"]
    original_message = sample["original_message"]
    model_id = model_config["id"]

    result: dict = {
        "sample_id": sample_id,
        "condition": condition_id,
        "model_id": model_id,
        "original_message": original_message,
        "adapted_message": None,
        "response": None,
        "scores": {
            "style": None,
            "intent": None,
            "script_stability": None,
        },
        "original_script": detect_script(original_message),
        "response_script": None,
        "persona_used": persona,
        "error": None,
    }

    is_baseline = (persona is None)

    # ------------------------------------------------------------------
    # Step 1: User-message adaptation (non-baseline only)
    # ------------------------------------------------------------------
    if is_baseline:
        adapted_message = original_message
    else:
        if should_skip_persona(original_message):
            # Verbatim / format-strict task: skip adaptation but still generate
            adapted_message = original_message
        else:
            quirk = persona.get("style", {}).get("verbal_quirks", "") if persona else ""
            quirk_inst = f"Apply these linguistic quirks naturally: {quirk}" if quirk else "Match register and writing style."
            adapt_prompt = ADAPT_USER_PROMPT_TEMPLATE.format(
                background=get_persona_background_str(persona),
                writing_style=get_persona_style_str(persona),
                user_message=original_message,
                verbal_quirks_instruction=quirk_inst,
            )
            adapted_text, err = await call_api(
                session, model_config, adapt_gen_cfg,
                [{"role": "user", "content": adapt_prompt}],
                error_prefix=f"ADAPT:{model_id}:{condition_id}:{sample_id}",
                is_judge=False,
            )
            if err or not adapted_text:
                result["error"] = "adaptation_failed: {}".format(err)
                adapted_message = original_message  # fall back to original
            else:
                adapted_message = adapted_text.strip()

    result["adapted_message"] = adapted_message

    # ------------------------------------------------------------------
    # Step 2: LLM judges for style + intent (non-baseline only)
    # ------------------------------------------------------------------
    if not is_baseline and adapted_message != original_message:
        style_judge_cfg = judge_model_config or model_config
        intent_judge_cfg = judge_model_config or model_config
        style_score = await score_style(
            session, style_judge_cfg, judge_gen_cfg,
            adapted_message, persona,
        )
        intent_score = await score_intent(
            session, intent_judge_cfg, judge_gen_cfg,
            original_message, adapted_message,
        )
        result["scores"]["style"] = style_score
        result["scores"]["intent"] = intent_score

    # ------------------------------------------------------------------
    # Step 3: Response generation
    # ------------------------------------------------------------------
    messages = []
    if not is_baseline and persona is not None:
        system_content = PERSONA_SYSTEM_PROMPT_TEMPLATE.format(
            background=get_persona_background_str(persona),
            writing_style=get_persona_style_str(persona),
        )
        messages.append({"role": "system", "content": system_content})

    messages.append({"role": "user", "content": adapted_message})

    response_text, err = await call_api(
        session, model_config, gen_cfg,
        messages,
        error_prefix=f"GEN:{model_id}:{condition_id}:{sample_id}",
        is_judge=False,
    )
    if err or not response_text:
        result["error"] = (result.get("error") or "") + " | generation_failed: {}".format(err)
    else:
        result["response"] = response_text.strip()

    # ------------------------------------------------------------------
    # Step 4: Script stability (no LLM call)
    # ------------------------------------------------------------------
    if result["response"]:
        resp_script = detect_script(result["response"])
        result["response_script"] = resp_script
        result["scores"]["script_stability"] = score_script_stability(
            original_message, result["response"]
        )

    return result


# ---------------------------------------------------------------------------
# Main async pipeline
# ---------------------------------------------------------------------------

async def run_ablation(config: dict, args: argparse.Namespace):
    abl_cfg = config["ablation"]
    output_path = args.output or abl_cfg["output"]
    sample_cache = abl_cfg["sample_cache"]
    num_samples = args.num_samples or abl_cfg["num_samples"]
    concurrency = args.concurrency or abl_cfg["concurrency"]
    model_filter = set(args.models.split(",")) if args.models else None

    adapt_gen_cfg = config["adaptation_generation"]
    gen_cfg = config["generation"]
    judge_gen_cfg = config["judge_generation"]

    # Filter models
    models = [
        m for m in config["models"]
        if model_filter is None or m["id"] in model_filter
    ]
    if not models:
        print("ERROR: No models selected after filter.", file=sys.stderr)
        sys.exit(1)

    # Load the sample file (build it with sample_dataset.py)
    if not os.path.exists(sample_cache):
        sys.exit("Sample file not found at {}; build it with evaluation/attribute_ablation/sample_dataset.py".format(sample_cache))
    with open(sample_cache, "r", encoding="utf-8") as f:
        samples = [json.loads(line) for line in f if line.strip()]
    samples = samples[:num_samples]
    for s in samples:  # sample_dataset.py stores the whole conversation; the ablation rewrites the first user turn
        if not s.get("original_message"):
            s["original_message"] = next((m["content"] for m in s.get("original_messages") or [] if m.get("role") == "user"), "")
    print("Loaded {} samples from {}".format(len(samples), sample_cache))

    # Load all personas from the configured bank files
    all_personas = []
    persona_files = abl_cfg.get("persona_files", [])
    for pf in persona_files:
        pf_path = Path(pf)
        if pf_path.exists():
            with open(pf_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            all_personas.append(json.loads(line.strip()))
                        except Exception:
                            pass
    print("Loaded {} total personas from the persona banks.".format(len(all_personas)))

    # Load sample persona mapping if it exists
    mapping_path = Path(abl_cfg.get("persona_mapping") or "")
    offline_mapping = {}
    if abl_cfg.get("persona_mapping") and mapping_path.exists():
        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                offline_mapping = json.load(f)
            print("Loaded {} offline persona mappings from {}".format(len(offline_mapping), mapping_path))
        except Exception as e:
            print("Warning: Failed to load offline mapping: {}".format(e))

    # Build persona lookup dict
    persona_by_id = {p["id"]: p for p in all_personas if "id" in p}

    # Initialize sentence-transformers for embedding fallback matching (only if needed/not all mapped)
    need_embeddings = False
    for sample in samples:
        s_id = str(sample["sample_id"])
        if s_id not in offline_mapping or offline_mapping[s_id] not in persona_by_id:
            need_embeddings = True
            break

    embedding_model = None
    persona_embeddings = None
    if all_personas and need_embeddings:
        try:
            from sentence_transformers import SentenceTransformer
            print("Encoding personas for embedding fallback matching...")
            embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            persona_texts = [
                p.get("description") or p.get("character_description") or get_persona_characteristics_str(p)
                for p in all_personas
            ]
            persona_embeddings = embedding_model.encode(persona_texts, convert_to_tensor=True)
            print("Done encoding personas.")
        except ImportError:
            print("Warning: sentence-transformers not installed. Embedding fallback disabled.")

    # Configure matching rules
    persona_config = {
        "language_match": True,
        "random_fallback": True,
        "matching": {
            "location_regex": True,
            "topic_keywords": True,
            "embedding_fallback": True,
            "min_embedding_similarity": 0.15,
            "top_k_embedding": 3
        }
    }

    # Match a stable base persona for each sample
    base_personas = {}
    for sample in samples:
        s_id = str(sample["sample_id"])
        base_p = None
        if s_id in offline_mapping and offline_mapping[s_id] in persona_by_id:
            base_p = persona_by_id[offline_mapping[s_id]]
            
        if base_p is None:
            orig_msg = sample["original_message"]
            user_script = detect_script(orig_msg)
            base_p, tier, _ = select_persona(
                orig_msg,
                all_personas,
                persona_config,
                embedding_model=embedding_model,
                persona_embeddings=persona_embeddings,
                user_script=user_script
            )
            if base_p is None:
                if all_personas:
                    import hashlib
                    h = int(hashlib.md5(orig_msg.encode('utf-8')).hexdigest(), 16)
                    base_p = all_personas[h % len(all_personas)]
                else:
                    base_p = NEUTRAL_PERSONA
        base_personas[sample["sample_id"]] = base_p

    # Load already-done cells (for resume)
    done = load_existing_results(output_path)
    print("Already completed: {} cells".format(len(done)))

    # Build work queue: all (sample, condition, model) triples not yet done
    work_items = []
    for sample in samples:
        base_p = base_personas[sample["sample_id"]]
        for cond_id in CONDITIONS.keys():
            for model in models:
                key = (sample["sample_id"], cond_id, model["id"])
                if key not in done:
                    persona = apply_ablation_override(base_p, cond_id)
                    work_items.append((sample, cond_id, persona, model))

    total = len(samples) * len(CONDITIONS) * len(models)
    remaining = len(work_items)
    print(
        "\nWork queue: {} cells remaining "
        "(of {} total = {} samples x {} conditions x {} models)".format(
            remaining, total, len(samples), len(CONDITIONS), len(models)
        )
    )

    if not work_items:
        print("Nothing to do.")
        return

    # Semaphore limits total concurrent cells (not per-model)
    sem = asyncio.Semaphore(concurrency)
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    out_file = open(output_path, "a", encoding="utf-8")
    completed = 0
    errors = 0

    judge_model_config = config.get("judge")

    async def bounded_cell(session, sample, cond_id, persona, model):
        nonlocal completed, errors
        async with sem:
            row = await process_cell(
                session, sample, cond_id, persona, model,
                adapt_gen_cfg, gen_cfg, judge_gen_cfg,
                judge_model_config=judge_model_config,
            )
            return row

    async with aiohttp.ClientSession() as session:
        tasks = [
            asyncio.create_task(
                bounded_cell(session, sample, cond_id, persona, model)
            )
            for sample, cond_id, persona, model in work_items
        ]

        for fut in asyncio.as_completed(tasks):
            row = await fut
            completed += 1
            if row.get("error"):
                errors += 1

            # Write with robustness against stale file handles / OS errors
            write_ok = False
            for attempt in range(3):
                try:
                    out_file.write(json.dumps(row, ensure_ascii=False) + "\n")
                    out_file.flush()
                    write_ok = True
                    break
                except OSError as e:
                    print(f"Warning: Write failed ({e}). Reopening output file...", file=sys.stderr)
                    try:
                        out_file.close()
                    except Exception:
                        pass
                    try:
                        out_file = open(output_path, "a", encoding="utf-8")
                    except Exception as open_err:
                        print(f"Error reopening file: {open_err}", file=sys.stderr)
                    await asyncio.sleep(1.0)
            if not write_ok:
                print("CRITICAL: Failed to write result row to file.", file=sys.stderr)

            # Flush every 10 cells so progress is visible
            if completed % 10 == 0:
                pct = 100 * completed / remaining
                print(
                    "  [{}/{}= {:.1f}%] errors={}".format(completed, remaining, pct, errors),
                    flush=True,
                )

    try:
        out_file.flush()
        out_file.close()
    except Exception:
        pass

    print("\nDone. {} cells written to {} ({} errors).".format(completed, output_path, errors))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run persona ablation study across conditions x models."
    )
    parser.add_argument(
        "--config",
        default=os.path.join(os.path.dirname(__file__), "ablation_config.yaml"),
        help="Path to ablation_config.yaml",
    )
    parser.add_argument("--num-samples", type=int, help="Override num_samples")
    parser.add_argument("--concurrency", type=int, help="Override concurrency")
    parser.add_argument(
        "--models",
        type=str,
        default=None,
        help="Comma-separated model IDs to run (e.g. 'glm,gemma'). Default: all.",
    )
    parser.add_argument("--output", type=str, help="Override output JSONL path")
    args = parser.parse_args()

    config = load_config(args.config)

    print("=== Per-attribute ablation ===")
    print("Config: {}".format(args.config))
    print("Models: {}".format([m['id'] for m in config['models']]))
    print("Conditions: {}".format(len(CONDITIONS)))
    print()

    asyncio.run(run_ablation(config, args))


if __name__ == "__main__":
    main()
