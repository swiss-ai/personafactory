"""Sample and stratify source conversations for the per-attribute ablation from:
  1. WildChat-1M (allenai/WildChat-1M), field: conversation (non-toxic; English / non-English quota)
  2. Nemotron IF (nvidia/Nemotron-Instruction-Following-Chat-v1), field: messages
  3. UltraChat 200k (HuggingFaceH4/ultrachat_200k), field: messages

Output JSONL records:
  {"sample_id": 0, "dataset_source": "wildchat" | "nemotron" | "ultrachat", "conversation_id": "...",
   "original_messages": [...], "language": "English", "topic": "code", "is_english": true}
run_ablation.py rewrites the first user turn of original_messages. Gated datasets need HF_TOKEN in the environment.

Run: python -m personafactory.evaluation.attribute_ablation.sample_dataset --num-per-dataset 150 --output ./data/attribute_ablation/samples.jsonl
"""

import os
import re
import json
import random
import argparse

from datasets import load_dataset

_TOPIC_PATTERNS: dict[str, re.Pattern] = {
    "code": re.compile(
        r'\b(code|program|function|script|debug|error|python|javascript|java|sql|'
        r'bash|api|class|variable|algorithm|compiler|syntax|library|framework|github)\b',
        re.IGNORECASE,
    ),
    "science": re.compile(
        r'\b(physics|chemistry|biology|math|equation|theorem|formula|scientific|'
        r'experiment|hypothesis|quantum|molecule|protein|evolution|climate|statistic)\b',
        re.IGNORECASE,
    ),
    "creative": re.compile(
        r'\b(write|story|poem|essay|creative|fiction|character|plot|novel|'
        r'screenplay|dialogue|narrative|imagine|roleplay|fantasy|adventure)\b',
        re.IGNORECASE,
    ),
    "factual": re.compile(
        r'\b(what is|who is|when did|where is|how does|explain|define|history|'
        r'meaning|fact|difference between|compare|why does|capital of|founded)\b',
        re.IGNORECASE,
    ),
}

_TARGET_TOPICS = ["code", "science", "creative", "factual", "other"]


def classify_topic(text: str) -> str:
    for bucket, pattern in _TOPIC_PATTERNS.items():
        if pattern.search(text):
            return bucket
    return "other"


def is_english(lang_field: str | None) -> bool:
    if not lang_field:
        return True
    return lang_field.strip().lower() in ("english", "en", "eng")


def clean_messages(msgs: list) -> list[dict]:
    """Clean and normalize message list to standard [{'role': ..., 'content': ...}] format."""
    cleaned = []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        role = m.get("role", "").strip().lower()
        content = m.get("content", "")
        if not content or not isinstance(content, str):
            continue
        if role in ("user", "assistant", "system"):
            cleaned.append({"role": role, "content": content.strip()})
    return cleaned


def sample_wildchat(num_samples: int, rng: random.Random, non_english_ratio: float = 0.5) -> list[dict]:
    """Stream WildChat-1M and return stratified records with guaranteed non-English quota."""
    num_non_eng = int(num_samples * non_english_ratio)
    num_eng = num_samples - num_non_eng
    print(f"Sampling {num_samples} prompts from allenai/WildChat-1M ({num_eng} English, {num_non_eng} non-English)...", flush=True)
    ds = load_dataset("allenai/WildChat-1M", split="train", streaming=True)

    records_eng = []
    records_non_eng = []

    for row in ds:
        conversation = row.get("conversation", [])
        if not conversation:
            continue
        if row.get("toxic", False):
            continue

        msgs = clean_messages(conversation)
        first_user = next((m["content"] for m in msgs if m["role"] == "user"), None)
        if not first_user:
            continue

        lang = row.get("language", "English")
        eng = is_english(lang)
        topic = classify_topic(first_user)

        rec = {
            "dataset_source": "wildchat",
            "conversation_id": str(row.get("conversation_id", "")),
            "original_messages": msgs,
            "language": lang,
            "topic": topic,
            "is_english": eng,
        }

        if eng and len(records_eng) < num_eng:
            records_eng.append(rec)
        elif not eng and len(records_non_eng) < num_non_eng:
            records_non_eng.append(rec)

        if len(records_eng) >= num_eng and len(records_non_eng) >= num_non_eng:
            break

    records = records_eng + records_non_eng
    rng.shuffle(records)
    return records


def sample_nemotron(num_samples: int, rng: random.Random) -> list[dict]:
    """Stream Nemotron IF and return stratified records."""
    print(f"Sampling {num_samples} prompts from nvidia/Nemotron-Instruction-Following-Chat-v1...", flush=True)
    ds = load_dataset("nvidia/Nemotron-Instruction-Following-Chat-v1", split="chat_if", streaming=True)

    records = []
    for row in ds:
        msgs_raw = row.get("messages", [])
        msgs = clean_messages(msgs_raw)
        first_user = next((m["content"] for m in msgs if m["role"] == "user"), None)
        if not first_user:
            continue

        cid = str(row.get("uuid", f"nemotron_{len(records)}"))
        topic = classify_topic(first_user)

        records.append({
            "dataset_source": "nemotron",
            "conversation_id": cid,
            "original_messages": msgs,
            "language": "English",
            "topic": topic,
            "is_english": True,
        })

        if len(records) >= num_samples:
            break

    rng.shuffle(records)
    return records[:num_samples]


def sample_ultrachat(num_samples: int, rng: random.Random) -> list[dict]:
    """Stream UltraChat 200k and return stratified records."""
    print(f"Sampling {num_samples} prompts from HuggingFaceH4/ultrachat_200k...", flush=True)
    ds = load_dataset("HuggingFaceH4/ultrachat_200k", split="train_sft", streaming=True)

    records = []
    for row in ds:
        msgs_raw = row.get("messages", [])
        msgs = clean_messages(msgs_raw)
        first_user = row.get("prompt") or next((m["content"] for m in msgs if m["role"] == "user"), None)
        if not first_user:
            continue

        cid = str(row.get("prompt_id", f"ultrachat_{len(records)}"))
        topic = classify_topic(first_user)

        records.append({
            "dataset_source": "ultrachat",
            "conversation_id": cid,
            "original_messages": msgs,
            "language": "English",
            "topic": topic,
            "is_english": True,
        })

        if len(records) >= num_samples:
            break

    rng.shuffle(records)
    return records[:num_samples]


def main():
    parser = argparse.ArgumentParser(description="Sample prompts from WildChat, Nemotron, and UltraChat")
    parser.add_argument("--num-per-dataset", type=int, default=150, help="Number of samples to draw per dataset (default: 150)")
    parser.add_argument("--num-wildchat", type=int, default=None, help="Optional custom count for WildChat (default: matches --num-per-dataset)")
    parser.add_argument("--non-english-ratio", type=float, default=0.5, help="Quota ratio of non-English samples for WildChat (default: 0.5)")
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument(
        "--output",
        type=str,
        default="./data/attribute_ablation/samples.jsonl",
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)

    wc_count = args.num_wildchat if args.num_wildchat is not None else args.num_per_dataset
    wc_samples = sample_wildchat(wc_count, rng, non_english_ratio=args.non_english_ratio)
    nemo_samples = sample_nemotron(args.num_per_dataset, rng)
    ultra_samples = sample_ultrachat(args.num_per_dataset, rng)

    combined = wc_samples + nemo_samples + ultra_samples
    rng.shuffle(combined)

    for idx, rec in enumerate(combined):
        rec["sample_id"] = idx

    print(f"\nCollected total {len(combined)} prompts across 3 datasets:", flush=True)
    by_src = {}
    for r in combined:
        src = r["dataset_source"]
        by_src[src] = by_src.get(src, 0) + 1
    for src, cnt in by_src.items():
        print(f"  - {src:12s}: {cnt}", flush=True)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for rec in combined:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\nWrote {len(combined)} samples -> {args.output}", flush=True)


if __name__ == "__main__":
    main()
