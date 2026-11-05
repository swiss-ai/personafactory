# personafactory.sft_ablation: SFT ablation of assistant-side conditioning

Does the way the assistant replies are generated matter once a model is fine-tuned on the corpus? The user turns
are identical in all three arms; only the assistant replies differ:

| arm | assistant replies generated with |
|---|---|
| `A_default` | no system prompt |
| `B_user_persona` | the user-persona system prompt (paper method) |
| `C_user_persona_model_persona` | B plus a matched model persona (as in the release) |

Two base models are fine-tuned on the same 100k conversations per arm (Llama-3.1-8B with TRL, Apertus-8B with a
Megatron trainer) and evaluated on a style-perturbation probe set (300 held-out requests x 12 user personas + the
unstyled original, greedy decoding), against `meta-llama/Llama-3.1-8B-Instruct` as reference.
Results are in the appendix section "Assistant-Side Model Personas" (downstream fine-tuning ablation).

All commands run from the repository root. Outputs default to `$PF_OUT_DIR/sft_ablation/` (`PF_OUT_DIR`
defaults to `./outputs`); the persona bank path defaults to `$PF_BANK`. Model paths are always arguments.

## Inputs

- the persona bank (`--bank` / `PF_BANK`) and the prepared source pairs with a `split` field (`--pairs-glob`),
  both from the augmentation pipeline;
- the pipeline's release directory of the persona-pair record set (`--release-dir`, `*.jsonl` with `id`, `split`,
  `source_text`, `text_language`; `split` is the pipeline's seed-disjoint split, which the published Hugging Face
  dataset does not carry);
- the assistant side regenerated in the three arms by the `assistant` package, one directory of JSONL per arm
  with `{id, status, conversation}` records (`status == "pass"` = passed the sanity gate).

## Pipeline

### 1. Probes (`build_probes.py`)

Serve the rewriter (the paper used `google/gemma-4-31B-it`) behind an OpenAI-compatible endpoint, then:

```bash
python -m personafactory.sft_ablation.build_probes --rewriter-url http://HOST:8000/v1 --rewriter-model gemma \
    --bank data/persona_bank.jsonl --pairs-glob 'data/prepared/pairs/*.jsonl'
```

Writes `probes/probes.jsonl` (3,900 rows: 300 requests x (12 personas + control); failed rewrites have
`user_message: null` and are skipped downstream) and `probes/probe_personas.json`.

### 2. SFT data (`build_sft_data.py`)

```bash
python -m personafactory.sft_ablation.build_sft_data --release-dir data/release \
    --arm-dir A_default=outputs/assistant/A_default \
    --arm-dir B_user_persona=outputs/assistant/B_user_persona \
    --arm-dir C_user_persona_model_persona=outputs/assistant/C_user_persona_model_persona
```

Keeps conversations that pass the sanity gate in all three arms, are in the train split and do not share a
request with the probes, and picks the same 100k in every arm. Writes `sft_data/<arm>/train.jsonl` (one row per
assistant turn; 231,282 rows per arm in the paper), `sft_data/conversation_ids.json` and `sft_data/stats.json`.

### 3a. Llama-3.1-8B, TRL (`trl_sft_mt.py`)

Full fine-tuning, FSDP2, one epoch, lr 1e-5 cosine (3% warmup), max length 4096, prompt masked,
global batch 128 (paper: 32 nodes x 4 GPUs x per-device batch 1 x grad-accum 1). Per arm, on every node:

```bash
export USE_FA2=0            # the paper runs used SDPA attention
accelerate launch --config_file sft_ablation/accelerate_fsdp2_llama.yaml \
    --num_machines $NNODES --num_processes $((NNODES * 4)) --machine_rank $NODE_RANK \
    --main_process_ip $MASTER_ADDR --main_process_port 29501 \
    -m personafactory.sft_ablation.trl_sft_mt \
    --model PATH/Llama-3.1-8B --template-model PATH/Llama-3.1-8B-Instruct \
    --data outputs/sft_ablation/sft_data/A_default/train.jsonl \
    --output outputs/sft_ablation/models/llama_A_default \
    --per-device-bs 1 --grad-accum $((128 / (NNODES * 4)))
```

For wide multi-node runs, first run the same command once on a single node with `WARM_ONLY=1`: it builds the
tokenized dataset cache (`TRL_DATA_CACHE`, on a filesystem shared by all nodes) and exits, so the full run
reads a finished cache instead of every rank building it at once. Multi-node runs need the cluster's own NCCL /
network settings (not included here).

### 3b. Apertus-8B, Megatron (`apertus/`)

The Apertus-8B runs used Megatron-LM with Apertus support, with the same recipe as the downstream fine-tuning
experiments (`personafactory/downstream/README.md`, `downstream/megatron/` and `scripts/slurm/downstream_megatron_*`,
with the Apertus-8B architecture of that checkpoint instead of Apertus-v1.5-8B). The data preparation of this
ablation:

```bash
python -m personafactory.sft_ablation.apertus.build_sources --release-dir data/release --tokenizer PATH/apertus_sft_tokenizer \
    --arm-dir A_default=outputs/assistant/A_default \
    --arm-dir B_user_persona=outputs/assistant/B_user_persona \
    --arm-dir C_user_persona_model_persona=outputs/assistant/C_user_persona_model_persona
# per arm (megatron.core must be importable):
python -m personafactory.sft_ablation.apertus.prepare_multiturn --config outputs/sft_ablation/megatron/A_default_config.json \
    --output-root outputs/sft_ablation/megatron/A_default_dataset --workers 32
```

`build_sources.py` writes one full multi-turn conversation per row (same 100k conversation ids as the TRL runs)
and the pinned per-arm config; `prepare_multiturn.py` renders each conversation with the tokenizer's chat
template, validates the assistant regions and writes Megatron IndexedDataset `.bin/.idx` files (98% train /
2% validation, split by conversation, stratified by language) plus `per_split_data_args.json`.
The tokenizer directory is the Apertus-8B-Instruct tokenizer (its `chat_template.jinja`, with thinking
disabled) whose `tokenizer_config.json` additionally defines `sft_assistant_begin_sequence` and `sft_eot_token`
(the token-id lists that open and close an assistant turn); the weights are the Apertus-8B base checkpoint.

Training recipe (one run per arm): full multi-turn documents with loss on every assistant turn (prompt loss
weight 0), sequence length 4096 with best-fit-decreasing packing (at most 8 documents per packed sequence),
tensor parallel 4, pipeline parallel 1, global batch 128, micro batch 1, lr 1e-5 cosine to 1e-6 with 3% warmup,
weight decay 0, gradient clipping 1.0, bf16, seed 1234, one epoch; the final checkpoint is exported to Hugging
Face format for generation.

### 4. Probe responses (`gen_responses.py`)

One vLLM run per model (tensor parallel 4, greedy, max 2048 new tokens):

```bash
python -m personafactory.sft_ablation.gen_responses --model outputs/sft_ablation/models/llama_A_default --tag llama_A_default
python -m personafactory.sft_ablation.gen_responses --model PATH/Llama-3.1-8B-Instruct --tag ref_Llama-3.1-8B-Instruct
```

Repeat for every arm and for the three Apertus exports (e.g. `--tag apertus_B_user_persona`).
Writes `responses/<tag>.jsonl`.

### 5. Style metrics (`style_metrics.py`)

```bash
python -m personafactory.sft_ablation.style_metrics
```

Scores every `responses/*.jsonl` with the formality ranker (`s-nlp/roberta-base-formality-ranker`), the style
embedding (`AnnaWegmann/Style-Embedding`) and LaBSE (GPU if available). Writes `style_metrics.json`:
`point1_sensitivity_r`, `point1_style_diversity`, `point1_content_stability_labse` feed Table `tab:mp-sft-adapt`;
`point2_style_features_mean` (median words, % with headers / bullets / emoji, formality, contractions per
100 words) feeds Table `tab:mp-sft-features`.

### 6. Pairwise judge with length control (`judge_lc.py`)

Serve the judge (the paper used `MiniMaxAI/MiniMax-M2.5`, served name `MiniMax-M2.5`; override with
`PF_JUDGE_MODEL`) on one or more OpenAI-compatible endpoints, then:

```bash
python -m personafactory.sft_ablation.judge_lc --judge-urls http://HOST1:30000/v1,http://HOST2:30000/v1 --pairs \
llama_B_user_persona:llama_A_default,llama_C_user_persona_model_persona:llama_A_default,\
llama_C_user_persona_model_persona:llama_B_user_persona,llama_C_user_persona_model_persona:ref_Llama-3.1-8B-Instruct,\
apertus_B_user_persona:apertus_A_default,apertus_C_user_persona_model_persona:apertus_A_default,\
apertus_C_user_persona_model_persona:apertus_B_user_persona
```

Writes `judge_lc_verdicts.jsonl` (resumable) and `judge_lc.json` (per pair: decisive count, ties, raw win % of
the first model with 95% interval, LC win %, median log length ratio), which feed Table `tab:mp-sft-judge` and
Figure `fig:mp-sft-lc`.

## Files

| file | role |
|---|---|
| `build_probes.py` | style-perturbation probe set |
| `build_sft_data.py` | per-arm SFT rows (TRL) and the shared conversation ids |
| `trl_sft_mt.py`, `accelerate_fsdp2_llama.yaml` | multi-turn TRL SFT (Llama-3.1-8B) |
| `apertus/build_sources.py`, `apertus/prepare_multiturn.py` | Megatron data preparation (Apertus-8B) |
| `gen_responses.py` | vLLM greedy generation on the probes |
| `style_metrics.py` | within-request correlations, style diversity, content stability, judge-free features |
| `judge_lc.py` | pairwise fit judge and length-controlled win rate |

Dependencies: `aiohttp`, `datasets`, `transformers`, `trl`, `accelerate`, `vllm`, `torch`, `safetensors`,
`huggingface_hub`, `numpy`, `scikit-learn`; `megatron-core` for `prepare_multiturn.py`.

Code: [github.com/swiss-ai/personafactory](https://github.com/swiss-ai/personafactory); data: [huggingface.co/datasets/swiss-ai/PersonaFactory](https://huggingface.co/datasets/swiss-ai/PersonaFactory).
