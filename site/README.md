# PersonaFactory project page

Static, single-page site for the paper. No framework and no chart library: hand-built SVG charts in vanilla JS, Google Fonts as the only external resource.

## Build

```bash
python3 build.py            # writes dist/index.html (standalone page) and dist/artifact.html (fragment)
python3 build.py --out DIR  # write somewhere else
```

`dist/index.html` is self-contained and can be served as is (e.g. GitHub Pages).

## Layout

```
build.py              assembles the page from src/
src/data.js           every number shown on the page (window.PF), with its paper source in comments
src/style.css         theme tokens (light/dark) and shared components
src/css/<id>.css      per-section styles, scoped under #<id>
src/js/00-core.js     shared helpers (charts, tooltips, stage control)
src/js/NN-*.js        one script per section, each wrapped in its own IIFE by build.py
src/sections/*.html   section markup; _head.html (header, hero, findings) and _tail.html (citation)
tools/preview.js      Playwright check of one section in light/dark/phone (console errors, overflow, missing legends)
```

Section order is `ORDER` in `build.py`.

## Check a section

```bash
node tools/preview.js dist/index.html corpus /tmp/preview
```
