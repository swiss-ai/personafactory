# personafactory.figures

Scripts that render the data figures of the paper as vector PDFs, all in one house style
(`style.py`: single-hue purple ramp, Inter font, recessive grid). Run from the repository root.
Rendering needs only `matplotlib` and `numpy`.

## Output -> paper figure

| PDF | paper figure (label) | location in the paper | script | input |
|---|---|---|---|---|
| `fig_persona_map.pdf` | personas per country (`fig:bank_map`) | Appendix, Full Persona Bank Coverage | `make_figures.py` | `bank_stats.json`, `world.geojson` |
| `fig_persona_background.pdf` | background-layer distributions (`fig:bank_background`) | Appendix, Full Persona Bank Coverage | `make_figures.py` | `bank_stats.json` |
| `fig_persona_style.pdf` | style-layer distributions (`fig:bank_style`) | Appendix, Full Persona Bank Coverage | `make_figures.py` | `bank_stats.json` |
| `fig_stacked_languages_regions.pdf` | top languages and macro-regions of the corpus (`fig:app_lang_region_dist`) | Appendix, Stylized Corpus Details | `make_results_figures.py` | `corpus_dist.json` |
| `fig_ab_rejudge.pdf` | structured vs flat A/B, external re-judging (`fig:ab-rejudge`) | Appendix, Evaluation Details | `make_results_figures.py` | values of `tab:ab-rejudge` (in code) |
| `fig_format_tradeoff.pdf` | style vs intent across persona formats (`fig:format-tradeoff`) | Appendix, Comparison to Other Persona Representations | `make_results_figures.py` | values of `tab:formats-main` (in code) |
| `fig_format_neutral_rejudge.pdf` | format-neutral re-judging and real personas (`fig:format-neutral`) | Appendix, Comparison to Other Persona Representations | `make_results_figures.py` | persona-format comparison results JSON |
| `fig_sft_lc.pdf` | raw vs length-controlled win rates after SFT (`fig:mp-sft-lc`) | Appendix, Assistant-Side Model Personas | `make_results_figures.py` | values of `tab:mp-sft-judge` (in code) |
| `fig_ablation_heatmap.pdf` | per-condition ablation grid (`fig:abl_heatmap`) | Appendix, Per-attribute Augmentation Analysis | `make_ablation_figures.py` | `ablation_stats.json` |
| `fig_ablation_models.pdf` | ablation per rewriter model (`fig:abl_models`) | Appendix, Per-attribute Augmentation Analysis | `make_ablation_figures.py` | `ablation_stats.json` |

The pipeline overview and the augmentation example (`persona_factory_main.pdf`,
`persona_factory_example.pdf`) are drawn by hand and are not produced by code.

## Commands

```bash
OUT=./outputs/figures

# persona bank (map, background, style); the bank is the persona_bank subset of swiss-ai/PersonaFactory as JSONL
python -m personafactory.figures.compute_stats --bank $PF_BANK --out $OUT/bank_stats.json
python -m personafactory.figures.make_figures --stats $OUT/bank_stats.json --world figures/world.geojson --out-dir $OUT

# attribute ablation (ablation_stats.json is written by
#   python -m personafactory.evaluation.attribute_ablation.summarize --results ... --figure-stats $OUT/ablation_stats.json)
python -m personafactory.figures.make_ablation_figures --stats $OUT/ablation_stats.json --out-dir $OUT

# corpus and evaluation results
python -m personafactory.figures.make_results_figures --out-dir $OUT \
    --corpus-dist <corpus_dist.json> --format-results ./outputs/format_comparison/results_neutral.json
```

`make_results_figures.py` skips a JSON-backed figure whose input is not given; `--only` selects
figures (`stacked tradeoff ab sft neutral`).

## Input formats

- `bank_stats.json` (from `compute_stats.py`): per-feature counts (`country`, `region`, `gender`,
  `education`, `fluency`, `ai_stance`, `occupation`, `language`, `generator`, style keys, ...),
  `_total`, `_ages` (list), `_country_iso` (country -> ISO3).
- `corpus_dist.json` (`release/stats/corpus_distribution.py`): `{"sources": {source: n},
  "languages": {language: {source: n}}, "regions": {macro_region: {source: n}}}`, where
  `languages` counts non-English conversations by detected language.
- persona-format results JSON: per judge (`minimax`, `qwen36`, `muse`): `style_neutral[cond]`
  = `{pct, lo, hi}` for `personahub`, `synthpai`, `personafactory`; `pairwise_neutral[cond]` and
  `pairwise_free[native_personahub | native_synthpai]` each with `pf_decisive = {pct, lo, hi}`
  (95% Wilson intervals).
- `ablation_stats.json`: written by `evaluation.attribute_ablation.summarize --figure-stats`.

## Map and font

`world.geojson` is the Natural Earth 1:110m Admin 0 countries layer (`ne_110m_admin_0_countries`,
public domain, https://www.naturalearthdata.com) converted to GeoJSON; countries are matched on
`ISO_A3_EH` / `ISO_A3`.

The paper figures use the Inter typeface (SIL Open Font License), which is not included here.
Download it from https://rsms.me/inter/ (or Google Fonts) and either put the `Inter-*.ttf` files
into `figures/fonts/`, point `PF_FONT_DIR` at them, or install Inter system-wide. Without Inter
the scripts fall back to DejaVu Sans; layout and colours are unchanged, only glyph metrics differ.

Code: [github.com/swiss-ai/personafactory](https://github.com/swiss-ai/personafactory); data: [huggingface.co/datasets/swiss-ai/PersonaFactory](https://huggingface.co/datasets/swiss-ai/PersonaFactory).
