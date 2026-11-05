#!/usr/bin/env python3
"""Generate one response per probe for a checkpoint with vLLM (one node, tensor parallel 4 by default).

Greedy decoding so that differences between arms are not sampling noise. The chat template is the checkpoint's
own (TRL outputs carry the Llama-3.1-Instruct template borrowed at training time).
Writes <out-dir>/<tag>.jsonl with {probe_id, model, response, finish}.

Run from the repo root:
  python -m personafactory.sft_ablation.gen_responses --model outputs/sft_ablation/models/llama_A_default --tag llama_A_default
"""
import argparse, json, os
from vllm import LLM, SamplingParams

OUT_ROOT = os.path.join(os.environ.get('PF_OUT_DIR', './outputs'), 'sft_ablation')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--model', required=True, help='HF checkpoint directory or model id')
    ap.add_argument('--tag', required=True, help='model name used in the output file and by the metrics/judge')
    ap.add_argument('--probes', default=os.path.join(OUT_ROOT, 'probes', 'probes.jsonl'))
    ap.add_argument('--out', default=os.path.join(OUT_ROOT, 'responses'))
    ap.add_argument('--tp', type=int, default=4, help='tensor parallel size')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    probes = [json.loads(l) for l in open(a.probes, encoding='utf-8')]
    probes = [p for p in probes if p['user_message']]
    llm = LLM(model=a.model, tensor_parallel_size=a.tp, max_model_len=8192, gpu_memory_utilization=0.9)
    sp = SamplingParams(temperature=0.0, max_tokens=2048)
    outs = llm.chat([[{'role': 'user', 'content': p['user_message']}] for p in probes], sp)
    with open(os.path.join(a.out, f'{a.tag}.jsonl'), 'w', encoding='utf-8') as fh:
        for p, o in zip(probes, outs):
            fh.write(json.dumps({'probe_id': p['probe_id'], 'model': a.tag, 'response': o.outputs[0].text,
                                 'finish': o.outputs[0].finish_reason}, ensure_ascii=False) + '\n')
    print('wrote', len(probes), 'responses for', a.tag)


if __name__ == '__main__':  # vLLM spawns worker processes
    main()
