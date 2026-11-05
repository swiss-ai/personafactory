#!/usr/bin/env python3
"""Build the PersonaFactory site (stdlib only).

Sources (src/):
  sections/_head.html   header, hero, findings
  sections/<id>.html    one file per factory station, in ORDER below
  sections/_tail.html   release & citation, footer
  style.css + css/*.css styles (core first, then per-station files in name order)
  data.js               every number, with its table/figure
  js/00-core.js         shared helpers (top-level names are visible to every other script)
  js/NN-*.js            one script per station; each is wrapped in its own IIFE and <script>,
                        so an error in one station cannot break the others

Outputs:
  <out>/index.html      standalone page (GitHub Pages)
  <out>/artifact.html   fragment for a claude.ai Artifact (no doctype/html/head/body)

Usage: python3 build.py [--out DIR]   (default DIR: dist)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "src"
ORDER = ["bank", "augment", "corpus", "eval", "ablations", "downstream", "compare"]

FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
           "%3Cstyle%3E*{fill:%232f4fc9}@media(prefers-color-scheme:dark){*{fill:%239aabff}}%3C/style%3E"
           "%3Ccircle cx='16' cy='10' r='6'/%3E%3Cpath d='M4 29c0-7 5.4-11 12-11s12 4 12 11z'/%3E%3C/svg%3E")

HEAD = f"""<title>PersonaFactory</title>
<link rel="icon" href="{FAVICON}">
<meta name="claude:viewport-fit-sides" content="cover">
<meta name="description" content="PersonaFactory: stylistic user prompt augmentation with a bank of 743,010 synthetic personas and a 1.24M-conversation corpus in 85 languages.">
<script>try{{var t=localStorage.getItem("personafactory-theme");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t);}}catch(e){{}}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Tektur:wght@500..800&family=Chakra+Petch:wght@500;600;700&family=Atkinson+Hyperlegible+Next:ital,wght@0,400..700;1,400&family=Martian+Mono:wdth,wght@87.5,400..600&display=swap">
"""


def page_html():
    parts = [(SRC / "sections" / "_head.html").read_text()]
    for i, sid in enumerate(ORDER):
        html = (SRC / "sections" / f"{sid}.html").read_text()
        cls = "sec" if i % 2 == 0 else "sec alt"   # findings (in _head) is alt, so bank starts plain
        html = re.sub(r'<section class="sec(?: alt)?"', f'<section class="{cls}"', html, count=1)
        parts.append(html)
    tail = (SRC / "sections" / "_tail.html").read_text()
    tail = re.sub(r'<section class="sec(?: alt)?"', '<section class="sec alt"' if len(ORDER) % 2 else '<section class="sec"', tail, count=1)
    parts.append(tail)
    return "\n".join(parts)


def css():
    out = [(SRC / "style.css").read_text()]
    for f in sorted((SRC / "css").glob("*.css")):
        out.append(f"/* ---- {f.name} ---- */\n" + f.read_text())
    return "\n".join(out)


def scripts():
    out = [f"<script>\n{(SRC / 'data.js').read_text()}</script>"]
    for f in sorted((SRC / "js").glob("*.js")):
        code = f.read_text()
        if f.name.startswith("00-"):
            out.append(f"<script>\n{code}</script>")
        else:
            out.append(f"<script>\n/* {f.name} */\n(function(){{\n{code}\n}})();\n</script>")
    return "\n".join(out)


def main():
    out_dir = ROOT / "dist"
    if "--out" in sys.argv:
        out_dir = Path(sys.argv[sys.argv.index("--out") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    style, page, js = css(), page_html(), scripts()
    (out_dir / "artifact.html").write_text(f"{HEAD}<style>\n{style}</style>\n{page}\n{js}\n")
    full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            f'{HEAD}<style>\n{style}</style>\n</head>\n<body>\n{page}\n{js}\n</body>\n</html>\n')
    (out_dir / "index.html").write_text(full)
    print("wrote", out_dir / "index.html", "and", out_dir / "artifact.html", f"({len(full) // 1024} KB)")


if __name__ == "__main__":
    main()
