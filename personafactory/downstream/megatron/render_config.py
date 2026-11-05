#!/usr/bin/env python3
"""Render the Megatron-LM run config of one downstream arm.

Combines apertus_v15_8b_sft.json (architecture, tokenization, hyperparameters, family-split settings) with the arm's
source JSONL (path and sha256; prepare_dataset.py re-hashes it and refuses to run if it changed) and the run-local
tokenizer view. The paper used a 1% family-level validation split for the language-matched arms and 3% for the
cross-lingual arms (so that 40k conversations still give one full validation batch).

    python -m personafactory.downstream.megatron.render_config --arm A2 \
        --source $PF_OUT_DIR/downstream/data_paired/A2_source.jsonl --work-root $ARM_ROOT \
        --tokenizer-view $WORK_ROOT/tokenizer_sft_view --output $ARM_ROOT/config.json
"""
import argparse, hashlib, json
from pathlib import Path

DEFAULT_TEMPLATE = Path(__file__).resolve().parent / 'apertus_v15_8b_sft.json'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--template', default=str(DEFAULT_TEMPLATE))
    ap.add_argument('--arm', required=True, help='arm name (A0, A1, A0r, A2, X1, X2)')
    ap.add_argument('--source', required=True, help='<arm>_source.jsonl')
    ap.add_argument('--work-root', required=True, help='per-arm work root')
    ap.add_argument('--tokenizer-view', required=True, help='tokenizer view from tokenizer_view.py')
    ap.add_argument('--validation-fraction', type=float, default=None, help='default: template value (0.01)')
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    out = Path(a.output)
    if out.exists():
        raise FileExistsError(f'refusing to overwrite {out}')
    c = json.load(open(a.template))
    c.pop('_comment', None)
    c['run_name'] = c['run_name'].format(arm=a.arm)
    c['work_root'] = a.work_root
    c['model']['hf_checkpoint'] = a.tokenizer_view
    c['source'].update({'jsonl': a.source, 'sha256': hashlib.sha256(open(a.source, 'rb').read()).hexdigest()})
    if a.validation_fraction is not None:
        c['source']['validation_fraction'] = a.validation_fraction
    out.parent.mkdir(parents=True, exist_ok=True)
    # sorted keys: the prepare step iterates dataset_bins in file order
    out.write_text(json.dumps(c, indent=1, sort_keys=True) + '\n')
    print(out, c['run_name'], c['source']['validation_fraction'])


if __name__ == '__main__':
    main()
