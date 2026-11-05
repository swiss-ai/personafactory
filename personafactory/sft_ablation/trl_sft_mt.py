#!/usr/bin/env python
"""Multi-turn SFT with TRL SFTTrainer (full fine-tuning, FSDP via accelerate) for the assistant-side ablation.

Rows are {"messages": [...]} ending with an assistant turn (build_sft_data.py writes one row per assistant
turn, so every assistant turn is trained on). Everything before the last assistant turn is the prompt, rendered
with the chat template and masked from the loss; the last assistant turn is the completion.
Recipe: 1 epoch, lr 1e-5 cosine, 3% warmup, no weight decay, max length 4096, global batch 128.

Base checkpoints have no chat template; --template-model borrows one (the paper used the Llama-3.1-8B-Instruct
template for Llama-3.1-8B).

Launch (one process per GPU; the global batch is nodes x 4 GPUs x per-device-bs x grad-accum):
  accelerate launch --config_file sft_ablation/accelerate_fsdp2_llama.yaml \
      --num_machines $NNODES --num_processes $((NNODES*4)) --machine_rank $NODE_RANK \
      --main_process_ip $MASTER_ADDR --main_process_port 29501 \
      -m sft_ablation.trl_sft_mt --model PATH/Llama-3.1-8B --template-model PATH/Llama-3.1-8B-Instruct \
      --data outputs/sft_ablation/sft_data/A_default/train.jsonl --output outputs/sft_ablation/models/llama_A_default

Environment options:
  WARM_ONLY=1       build the dataset caches (render, filter, tokenize) and exit before training. Useful for wide
                    multi-node runs: run it once on one node first so all ranks later read the finished cache.
  TRL_DATA_CACHE    datasets cache directory (default ./.cache/trl_sft_datasets, must be shared by all ranks).
  DATA_MAP_PROC, DATASET_NUM_PROC   worker processes for the map/filter and TRL tokenization steps.
  USE_FA2           1 (default) flash-attention-2, 0 SDPA (the paper runs used USE_FA2=0).
  GC_ON=1           gradient checkpointing.
  SAVE_STRATEGY     TRL save strategy (default "no"; "epoch" keeps an intermediate checkpoint).
"""
import argparse, os
import sys
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer


def load_pairs(path, tok, max_samples=None):
    """Memory-mapped load (load_dataset keeps an Arrow cache on disk shared by every rank, instead of a full
    in-RAM copy per rank), then render the chat template ourselves and hand TRL plain prompt/completion strings.

    With message lists, TRL tokenizes the prompt and prompt+completion separately and checks that the first is a
    prefix of the second; for some chat templates (e.g. Apertus) the generation prompt is not a clean prefix and
    that path is very slow. Pre-rendering removes the ambiguity for every model family.
    """
    cache_dir = os.getenv("TRL_DATA_CACHE", os.path.join(".cache", "trl_sft_datasets"))
    ds = load_dataset("json", data_files=path, split="train", cache_dir=cache_dir)
    if max_samples:
        ds = ds.select(range(min(max_samples, len(ds))))
    procs = int(os.getenv("DATA_MAP_PROC", "4"))
    eos = tok.eos_token or ""

    def render(row):
        msgs = row["messages"]
        history = [{"role": m["role"], "content": m["content"]} for m in msgs[:-1]]
        assistant = msgs[-1]["content"]
        try:
            prompt_text = tok.apply_chat_template(
                history, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        except TypeError:  # template takes no enable_thinking kwarg
            prompt_text = tok.apply_chat_template(
                history, tokenize=False, add_generation_prompt=True)
        return {"prompt": prompt_text, "completion": assistant + eos}

    ds = ds.map(render, remove_columns=ds.column_names, num_proc=procs,
                desc="rendering chat template")
    return ds.filter(lambda row: bool(row["prompt"]) and bool(row["completion"]),
                     num_proc=procs, desc="dropping empty rows")


def sanitise_generation_config(model):
    """Drop sampling fields that make `save_pretrained` reject the config.

    Some checkpoints ship `do_sample=False` alongside `temperature`/`top_p`, which raises
    `ValueError: GenerationConfig is invalid` at save time; check it before training ends.
    Nulling the sampling fields keeps greedy decoding rather than silently switching the saved model to sampling.
    """
    config = getattr(model, "generation_config", None)
    if config is None:
        return
    try:
        config.validate()
        return
    except Exception as exc:
        print("[trl_sft] generation_config invalid (%s); dropping sampling fields" % exc, flush=True)
    for field in ("temperature", "top_p", "top_k", "typical_p", "epsilon_cutoff", "eta_cutoff"):
        if getattr(config, field, None) is not None:
            setattr(config, field, None)
    try:
        config.validate()
    except Exception as exc:
        from transformers import GenerationConfig
        print("[trl_sft] still invalid (%s); using a default GenerationConfig" % exc, flush=True)
        model.generation_config = GenerationConfig(
            bos_token_id=getattr(config, "bos_token_id", None),
            eos_token_id=getattr(config, "eos_token_id", None),
            pad_token_id=getattr(config, "pad_token_id", None),
        )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--template-model", default="",
                    help="borrow chat_template from here if --model has none (base models)")
    ap.add_argument("--data", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--max-len", type=int, default=4096)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--per-device-bs", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--max-samples", type=int, default=0)
    args = ap.parse_args()

    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tok.chat_template is None:
        src = args.template_model or args.model
        ttok = AutoTokenizer.from_pretrained(src, trust_remote_code=True)
        if ttok.chat_template is None:
            raise SystemExit(f"no chat_template on {args.model} or template-model {src}")
        tok.chat_template = ttok.chat_template
        print(f"[trl_sft] borrowed chat_template from {src}", flush=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    ds = load_pairs(args.data, tok, max_samples=args.max_samples or None)
    print(f"[trl_sft] {len(ds)} training pairs; model={args.model}", flush=True)

    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype="bfloat16", trust_remote_code=True,
        attn_implementation="flash_attention_2" if os.getenv("USE_FA2", "1") == "1" else "sdpa",
    )
    model.config.use_cache = False  # required with gradient checkpointing

    cfg = SFTConfig(
        output_dir=args.output,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_steps=0.03,   # float warmup_steps is a ratio in recent transformers
        weight_decay=0.0,
        max_grad_norm=1.0,
        per_device_train_batch_size=args.per_device_bs,
        gradient_accumulation_steps=args.grad_accum,
        # gradient checkpointing off by default: FSDP full-shard fits 8B full fine-tuning on 96 GB GPUs.
        gradient_checkpointing=os.getenv("GC_ON", "0") == "1",
        bf16=True,
        max_length=args.max_len,
        completion_only_loss=True,     # mask the prompt
        packing=False,
        logging_steps=10,
        save_strategy=os.getenv("SAVE_STRATEGY", "no"),
        ddp_timeout=7200,             # long timeout so the FSDP save-gather does not trip the watchdog
        report_to="none",
        seed=1234,
        dataset_num_proc=int(os.getenv("DATASET_NUM_PROC", "2")),
    )

    trainer = SFTTrainer(model=model, args=cfg, train_dataset=ds, processing_class=tok)
    if os.getenv("WARM_ONLY", "0") == "1":
        # SFTTrainer.__init__ has already run every datasets map (render, filter, tokenize) into the
        # fingerprinted cache; stop here so a later multi-node run reads the finished cache.
        print("[trl_sft] WARM_ONLY: dataset caches built, exiting before training", flush=True)
        return
    sanitise_generation_config(model)
    trainer.train()
    sanitise_generation_config(trainer.model)
    trainer.save_model(args.output)
    tok.save_pretrained(args.output)
    print(f"[trl_sft] DONE -> {args.output}", flush=True)


if __name__ == "__main__":
    # print the failing rank's traceback explicitly (torch elastic may not record it)
    try:
        main()
    except BaseException:
        import traceback
        rank = os.environ.get("RANK", os.environ.get("LOCAL_RANK", "?"))
        print("[trl_sft][rank %s] FATAL" % rank, file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise
