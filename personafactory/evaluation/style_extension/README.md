# personafactory.evaluation.style_extension

A/B evaluation of the style extension (paper appendix, persona-format comparison: "Calibration against real
users", `tab:style-calibration`, `fig:style-calibration`). Existing personas from Nemotron-Personas and PersonaHub
are converted to the bank format with a generated style layer (`persona_bank/extend_style.py`), and the same seed
turns are rewritten three ways, changing only the persona text that the rewriter and responder see:

| arm | persona text |
|---|---|
| A | the raw source record, no writing style |
| B | our converted background, no writing style |
| C | converted background + generated style layer |

Three judges then compare the rewrites with each other and with the real WildChat message they came from:
`MiniMax-M2.5` (the pipeline judge), `Qwen3.6-35B-A3B` and `Muse-Glimmer-30B`.

Run every command from the repository root as `python -m personafactory.evaluation.style_extension.<module>`.
`scripts/examples/style_extension.sh` submits the whole chain (extension, judge, A/B, all judges, figure) with the
settings below; Slurm templates: `scripts/slurm/style_extension_*.sbatch`.

## Steps

| step | module | input | output |
|---|---|---|---|
| 1. extend personas | `persona_bank.extend_style` prep / gen / collect | Nemotron-Personas, PersonaHub | `RUN/raw/persona_bank_extend.jsonl` |
| 2. judge personas | `persona_bank.judge_shards`, `persona_bank.validate_personas` | step 1 | `RUN/judge_out/*.jsonl` |
| 3. A/B inputs | `prep.py` | judge-kept personas, seed shards | `DIR/personas.jsonl`, `pairs_{free,multilingual}.jsonl`, `assign.jsonl` |
| 4. rewrite, arms A / B / C | `generate.py` | step 3 | `DIR/gen/{arm}-{mode}.jsonl` |
| 5. judge items | `items.py single`, `pairwise`, `rejudge`, `external` | `DIR/gen` | `DIR/judge/items*/NNN.jsonl`, `DIR/judge/items_ext/all.jsonl` |
| 6. judge | `judge_client.py` | item shards | `DIR/judge/results*/`, `DIR/judge_<label>/results/` |
| 7. aggregate | `aggregate.py` | gen + results | `DIR/report.json`, `DIR/report_<label>.json` |
| 8. figure | `plot.py` | `report.json` + gen | `DIR/figs/style_ab_calibration.{png,pdf}` |

## Settings

- Personas: 160 records from each of the 12 Nemotron-Personas country releases and 220 PersonaHub records (2,140
  sources); extension with Gemma 4 31B (temperature 0.8, 16 shards); judged like the bank (MiniMax-M2.5,
  two-pass repair, 8 shards).
- Seeds: one English seed conversation per judge-kept persona from the augmentation seed shards
  (`augmentation.prepare_seeds`, files `<mode>-<source>-NNNN.jsonl`), WildChat / UltraChat / Nemotron in turn.
  English personas run in the free mode; all others in the multilingual mode with their main language as target
  (literal translation, then restyle).
- Rewriting: the augmentation pipeline (`augmentation.pipeline.process_conversation` with the production settings
  of `augmentation.run_augmentation`), Gemma 4 31B as rewriter, translator and responder, MiniMax-M2.5 as per-turn
  sanity judge. Only conversations with status `pass` are judged.
- Judge items (`items.py`):
  - `intent` (every arm and user turn) and `style` (arm C): the corpus judge templates
    (`augmentation.prompts.VALIDATE_PERSONA_INTENT_TEMPLATE` / `VALIDATE_PERSONA_STYLE_TEMPLATE`);
  - `identify`: which of four people (converted backgrounds, same source release and mode) wrote the first turn;
  - `pair_real` / `pair_fit`: which of two arms' first turns reads more like a real person / fits the person
    better, every comparison judged in both orders;
  - `calib_real`: the real English WildChat turn against each arm's rewrite of it, both orders.
  A win requires the same choice in both orders; a flip counts as a draw.
- MiniMax-M2.5 (SGLang TP4 / EP4, context 16k): temperature 0.1, `--max-tokens 2048` for the single items, then
  the unparsable ones again with 6000 (`items.py rejudge`), 6000 for the both-orders items; one retry at 4096 on an
  unparsable answer.
- External judges: `Qwen/Qwen3.6-35B-A3B-FP8` (vLLM, qwen3 reasoning parser) and Muse-Glimmer-30B (a vLLM build that
  supports it), temperature 0.1, `--max-tokens 8192`, on the calibration, identify and both-orders items
  (`items.py external`).

## Commands

```bash
RUN=$PF_DATA_DIR/style_extension; DIR=$PF_OUT_DIR/style_extension
python -m personafactory.persona_bank.extend_style prep --out $RUN --per_country 160 --personahub 220
python -m personafactory.persona_bank.extend_style gen --out $RUN --base_url http://HOST:8000/v1 \
    --shard_count 16 --shard_index $i --concurrency 48            # i = 0..15
python -m personafactory.persona_bank.extend_style collect --out $RUN
python -m personafactory.persona_bank.judge_shards split --raw_dir $RUN/raw --judge_in $RUN/judge_in --nsh 8
python -m personafactory.persona_bank.validate_personas --input $RUN/judge_in/shard_000$i.jsonl \
    --output $RUN/judge_out/val_000$i.jsonl --base-url http://HOST:30000/v1 --concurrency 32   # i = 0..7

python -m personafactory.evaluation.style_extension.prep --run $RUN --seeds $PF_SEEDS_DIR --out $DIR
for arm in A B C; do
  python -m personafactory.evaluation.style_extension.generate --arm $arm --dir $DIR \
      --gemma http://HOST:8000/v1 http://HOST:8001/v1 --gemma-model google/gemma-4-31B-it \
      --minimax http://HOST2:30000/v1 --minimax-model MiniMaxAI/MiniMax-M2.5 --lid-model $PF_LID_MODEL --concurrency 120
done
python -m personafactory.evaluation.style_extension.items single --dir $DIR            # 8 shards
python -m personafactory.evaluation.style_extension.judge_client --shards $DIR/judge/items/*.jsonl \
    --outdir $DIR/judge/results --urls http://HOST2:30000/v1 --model MiniMaxAI/MiniMax-M2.5 --max-tokens 2048
python -m personafactory.evaluation.style_extension.items rejudge --dir $DIR --shards 16
python -m personafactory.evaluation.style_extension.judge_client --shards $DIR/judge/items_rejudge/*.jsonl \
    --outdir $DIR/judge/results_rejudge --urls http://HOST2:30000/v1 --model MiniMaxAI/MiniMax-M2.5 --max-tokens 6000
python -m personafactory.evaluation.style_extension.items pairwise --dir $DIR --shards 16
python -m personafactory.evaluation.style_extension.judge_client --shards $DIR/judge/items_pair2/*.jsonl \
    --outdir $DIR/judge/results_pair2 --urls http://HOST2:30000/v1 --model MiniMaxAI/MiniMax-M2.5 --max-tokens 6000
python -m personafactory.evaluation.style_extension.aggregate --dir $DIR                # -> report.json

python -m personafactory.evaluation.style_extension.items external --dir $DIR
python -m personafactory.evaluation.style_extension.judge_client --shards $DIR/judge/items_ext/all.jsonl \
    --outdir $DIR/judge_qwen36/results --urls http://HOST3:8000/v1 --model Qwen/Qwen3.6-35B-A3B-FP8 \
    --max-tokens 8192 --concurrency 800
python -m personafactory.evaluation.style_extension.aggregate --dir $DIR --judge judge_qwen36 --out report_qwen36.json
# same for Muse-Glimmer-30B: --outdir $DIR/judge_muse/results ... ; --judge judge_muse --out report_muse.json
python -m personafactory.evaluation.style_extension.plot --dir $DIR
```

## Outputs

`report.json` / `report_<label>.json` (`aggregate.py`):

- `yield`: conversation status per arm and the share of user turns left unchanged;
- `intent`, `style_C`: judge pass rates (with 95% Wilson intervals), overall and by mode;
- `identify`: accuracy of picking the true author among four candidates (chance 25%), by mode and source release;
- `pairwise_both_orders`: `pair_real/AC`, `pair_fit/BC`, ... and `calib_real/RA`, `RB`, `RC` with wins, draws,
  missing and the share won by the first-shown message; the calibration rows are the paper table;
- `surface_first_turn`: typing features of the first user turn per arm (lowercase start, no final punctuation,
  emoji, ellipsis, repeated !/?, length) with the real WildChat turns as reference.

The figure shows (a) the MiniMax-M2.5 calibration verdicts and (b) typing-feature rates of real users and the three
arms on the English WildChat seeds where all three arms passed.
