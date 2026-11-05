#!/usr/bin/env python3
"""Download the verifiable benchmarks of the robustness evaluation into <data-dir> as JSONL (needs internet; run
once before the offline jobs):

  ifeval.jsonl         google/IFEval, train (541 prompts)
  gsm8k.jsonl          openai/gsm8k main, test (1,319)
  mbpp.jsonl           google-research-datasets/mbpp sanitized, test (257)
  mmlu.jsonl           cais/mmlu all, test (14,042)
  arc_challenge.jsonl  allenai/ai2_arc ARC-Challenge, test (1,172)

  python -m personafactory.downstream.eval.fetch_benchmarks --data-dir $PF_DATA_DIR/downstream_eval
"""
import argparse, json, os

SETS = {
    'ifeval': ('google/IFEval', None, 'train'),
    'gsm8k': ('openai/gsm8k', 'main', 'test'),
    'mbpp': ('google-research-datasets/mbpp', 'sanitized', 'test'),
    'mmlu': ('cais/mmlu', 'all', 'test'),
    'arc_challenge': ('allenai/ai2_arc', 'ARC-Challenge', 'test'),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data-dir', required=True)
    a = ap.parse_args()
    from datasets import load_dataset
    os.makedirs(a.data_dir, exist_ok=True)
    for name, (repo, cfg, split) in SETS.items():
        ds = load_dataset(repo, cfg, split=split)
        with open(os.path.join(a.data_dir, f'{name}.jsonl'), 'w', encoding='utf-8') as f:
            for row in ds:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
        print(name, len(ds), flush=True)


if __name__ == '__main__':
    main()
