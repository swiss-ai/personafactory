#!/usr/bin/env python3
"""Megatron-style source JSONL and preparation config per arm for the Apertus-8B runs.

Uses the same 100k conversations as the TRL runs (conversation_ids.json from build_sft_data.py), one full
multi-turn conversation per row, in the schema of prepare_multiturn.py: family_id = conversation id (split key),
language = detected text language, response_mode = training_role = 'chat'.
Also writes <out-dir>/<arm>_config.json, the pinned config prepare_multiturn.py consumes (source path and SHA256,
tokenizer, family split, one 'chat' dataset bin) plus the training recipe used in the paper for reference.

Inputs:  assistant-regeneration directories per arm, the released corpus (--release-dir, for text_language),
         conversation_ids.json, and the Apertus-8B SFT tokenizer directory (--tokenizer; see README).
Outputs: <out-dir>/<arm>_source.jsonl, <out-dir>/<arm>_config.json, <out-dir>/sources_sha256.json.

Run from the repo root:
  python -m personafactory.sft_ablation.apertus.build_sources --release-dir data/release --tokenizer PATH/apertus_sft_tokenizer \
      --arm-dir A_default=outputs/assistant/A_default --arm-dir B_user_persona=outputs/assistant/B_user_persona \
      --arm-dir C_user_persona_model_persona=outputs/assistant/C_user_persona_model_persona
"""
import argparse, glob, hashlib, json, os

ARMS = ('A_default', 'B_user_persona', 'C_user_persona_model_persona')
OUT_ROOT = os.path.join(os.environ.get('PF_OUT_DIR', './outputs'), 'sft_ablation')

# Recipe of the paper's Apertus-8B runs (external Megatron trainer); recorded in the config for reference only.
TRAINING = {'global_batch_size': 128, 'learning_rate': 1e-05, 'min_learning_rate': 1e-06, 'lr_decay_style': 'cosine',
            'warmup_fraction': 0.03, 'weight_decay': 0.0, 'micro_batch_size': 1, 'seq_length': 4096,
            'tensor_parallel_size': 4, 'pipeline_parallel_size': 1, 'packing_strategy': 'bfd', 'max_docs_per_bin': 8,
            'epochs': 1, 'seed': 1234, 'train_weights': {'chat': 1.0}}


def config_for(name, src, sha, tokenizer):
    return {'run_name': f'apertus_8b_base_sft_{name}',
            'dataset_bins': {'chat': ['chat']},
            'model': {'hf_checkpoint': tokenizer, 'training_start': 'base'},
            'source': {'jsonl': src, 'sha256': sha, 'require_validation_per_bin': True, 'split_key': 'family_id',
                       'split_seed': 'pf_apertus_sft_family_split', 'stratification': 'language',
                       'validation_fraction': 0.02},
            'tokenization': {'add_generation_prompt': False, 'enable_thinking': False},
            'training': TRAINING}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--arm-dir', action='append', required=True, metavar='ARM=DIR',
                    help=f'assistant-regeneration output directory per arm; arms: {", ".join(ARMS)}')
    ap.add_argument('--release-dir', required=True, help='released corpus directory (*.jsonl)')
    ap.add_argument('--ids', default=os.path.join(OUT_ROOT, 'sft_data', 'conversation_ids.json'))
    ap.add_argument('--tokenizer', required=True, help='Apertus-8B SFT tokenizer directory (chat template + SFT markers)')
    ap.add_argument('--out-dir', default=os.path.join(OUT_ROOT, 'megatron'))
    a = ap.parse_args()
    arm_dirs = dict(x.split('=', 1) for x in a.arm_dir)
    if set(arm_dirs) != set(ARMS):
        raise SystemExit(f'need exactly one --arm-dir for each of {ARMS}, got {sorted(arm_dirs)}')
    os.makedirs(a.out_dir, exist_ok=True)
    ids = json.load(open(a.ids))['ids']
    want = set(ids)
    lang = {}
    for fp in glob.glob(os.path.join(a.release_dir, '*.jsonl')):
        for l in open(fp, encoding='utf-8'):
            r = json.loads(l)
            if r['id'] in want:
                lang[r['id']] = r.get('text_language') or 'Unknown'
    shas = {}
    for name in ARMS:
        conv = {}
        for fp in glob.glob(os.path.join(arm_dirs[name], '*.jsonl')):
            for l in open(fp, encoding='utf-8'):
                x = json.loads(l)
                if x['id'] in want and x.get('status') == 'pass':
                    conv[x['id']] = x['conversation']
        fp = os.path.abspath(os.path.join(a.out_dir, name + '_source.jsonl'))
        with open(fp, 'w', encoding='utf-8') as fh:
            for i in ids:
                fh.write(json.dumps({'id': i, 'family_id': i, 'language': lang.get(i, 'Unknown'), 'response_mode': 'chat',
                                     'training_role': 'chat', 'messages': [{'role': m['role'], 'content': m['content']} for m in conv[i]]},
                                    ensure_ascii=False) + '\n')
        shas[name] = hashlib.sha256(open(fp, 'rb').read()).hexdigest()
        json.dump(config_for(name, fp, shas[name], a.tokenizer),
                  open(os.path.join(a.out_dir, name + '_config.json'), 'w'), indent=1, sort_keys=True)
    json.dump(shas, open(os.path.join(a.out_dir, 'sources_sha256.json'), 'w'), indent=1)
    print(json.dumps(shas, indent=1))


if __name__ == '__main__':
    main()
