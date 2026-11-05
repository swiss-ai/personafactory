'use strict';
/* Shared core: top-level names here are visible to every section script. */
const D = window.PF;
const $ = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => [...r.querySelectorAll(s)];
const NS = 'http://www.w3.org/2000/svg';
const fmt0 = v => Math.round(v).toLocaleString('en-US');
const fmt1 = v => (Math.round(v*10)/10).toFixed(1);
const fmt2 = v => v.toFixed(2);
const fmt3 = v => v.toFixed(3);
const pct = v => fmt1(v) + '%';
const compact = v => v >= 1e6 ? (v/1e6).toFixed(2).replace(/\.?0+$/,'') + 'M' : v >= 1e3 ? Math.round(v/1e3) + 'k' : String(v);
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ---------- theme: system -> light -> dark ---------- */
const root = document.documentElement;
const THEME_KEY = 'personafactory-theme';
const HALF = 'M12 3a9 9 0 0 1 0 18z';
const THEME_ICON = { light: ['c4', 'M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4L6 18M18 6l1.4-1.4'], dark: ['M20.5 13.5A8.5 8.5 0 1 1 10.5 3.5a6.6 6.6 0 0 0 10 10z'], system: ['c9', HALF] };
const themeBtn = $('#theme-btn');
function storedTheme(){ try { const t = localStorage.getItem(THEME_KEY); return t === 'light' || t === 'dark' ? t : 'system'; } catch(e){ return 'system'; } }
function applyTheme(t){
  if (t === 'system') root.removeAttribute('data-theme'); else root.setAttribute('data-theme', t);
  try { if (t === 'system') localStorage.removeItem(THEME_KEY); else localStorage.setItem(THEME_KEY, t); } catch(e){}
  const svg = document.createElementNS(NS, 'svg');
  [['viewBox','0 0 24 24'],['fill','none'],['stroke','currentColor'],['stroke-width','2'],['stroke-linecap','round'],['aria-hidden','true']].forEach(([k,v]) => svg.setAttribute(k, v));
  THEME_ICON[t].forEach(d => { if (d[0] === 'c'){ const c = document.createElementNS(NS, 'circle'); c.setAttribute('cx', 12); c.setAttribute('cy', 12); c.setAttribute('r', d.slice(1)); svg.appendChild(c); } else { const p = document.createElementNS(NS, 'path'); p.setAttribute('d', d); if (d === HALF){ p.setAttribute('fill', 'currentColor'); p.setAttribute('stroke', 'none'); } svg.appendChild(p); } });
  themeBtn.replaceChildren(svg);
  const label = { system: 'System', light: 'Light', dark: 'Dark' }[t] + (t === 'system' ? (matchMedia('(prefers-color-scheme: dark)').matches ? ' (dark)' : ' (light)') : '');
  themeBtn.setAttribute('aria-label', 'Color theme: ' + label + '. Click to change.'); themeBtn.title = 'Theme: ' + label;
}
let curTheme = storedTheme(); applyTheme(curTheme);
themeBtn.addEventListener('click', () => { const o = ['system', 'light', 'dark']; curTheme = o[(o.indexOf(curTheme) + 1) % 3]; applyTheme(curTheme); });
const head = $('.site-head');
const onScroll = () => head.classList.toggle('is-stuck', scrollY > 8);
addEventListener('scroll', onScroll, { passive: true }); onScroll();

/* ---------- tooltip ---------- */
const tip = $('#tip');
function showTip(e, rows){
  tip.replaceChildren();
  rows.forEach(r => {
    const d = document.createElement('div'); d.className = 'row';
    if (r.c) { const i = document.createElement('i'); i.style.background = r.c; d.appendChild(i); }
    if (r.v != null) { const v = document.createElement('span'); v.className = 'tv'; v.textContent = r.v; d.appendChild(v); }
    if (r.l) { const l = document.createElement('span'); l.className = 'tl'; l.textContent = r.l; d.appendChild(l); }
    tip.appendChild(d);
  });
  tip.style.opacity = 1; moveTip(e);
}
function moveTip(e){
  let x, y;
  if (e.clientX != null && e.type !== 'focus') { x = e.clientX; y = e.clientY; }
  else { const b = e.target.getBoundingClientRect(); x = b.left + b.width/2; y = b.top; }
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let left = x + 14, top = y - h - 10;
  if (left + w > innerWidth - 8) left = x - w - 14;
  if (top < 8) top = y + 16;
  tip.style.left = Math.max(8, left) + 'px'; tip.style.top = top + 'px';
}
function hideTip(){ tip.style.opacity = 0; }
function bind(node, rows){
  node.classList.add('mark');
  node.setAttribute('tabindex', '0');
  node.addEventListener('pointerenter', e => showTip(e, rows));
  node.addEventListener('pointermove', moveTip);
  node.addEventListener('pointerleave', hideTip);
  node.addEventListener('focus', e => showTip(e, rows));
  node.addEventListener('blur', hideTip);
  const aria = rows.map(r => [r.l, r.v].filter(Boolean).join(' ')).join(', ');
  node.setAttribute('aria-label', aria);
}

/* ---------- SVG helpers ---------- */
function S(tag, attrs, parent){ const n = document.createElementNS(NS, tag); for (const k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]); if (parent) parent.appendChild(n); return n; }
function T(txt, attrs, parent){ const n = S('text', attrs, parent); n.textContent = txt; return n; }
function svgFor(el, w, h){ el.replaceChildren(); const s = S('svg', { class: 'viz', viewBox: `0 0 ${w} ${h}`, width: w, height: h, role: 'img' }, el); return s; }
// bar path with 4px rounded data-end, square at baseline (horizontal)
function hbarPath(x0, y, len, h){ const r = Math.min(4, Math.abs(len)/2, h/2); if (len <= 0) return `M${x0},${y}h0v${h}h0z`; const x1 = x0 + len; return `M${x0},${y}H${x1-r}Q${x1},${y} ${x1},${y+r}V${y+h-r}Q${x1},${y+h} ${x1-r},${y+h}H${x0}Z`; }
function vbarPath(x, yBase, w, len){ const r = Math.min(4, len/2, w/2); const yt = yBase - len; if (len <= 0) return `M${x},${yBase}h${w}v0h${-w}z`; return `M${x},${yBase}V${yt+r}Q${x},${yt} ${x+r},${yt}H${x+w-r}Q${x+w},${yt} ${x+w},${yt+r}V${yBase}Z`; }
// canvas text width must use the same face as svg.viz text (the body font)
function measure(txts, size=12.5){ const c = measure.c || (measure.c = document.createElement('canvas').getContext('2d')); c.font = `${size}px ${'"Atkinson Hyperlegible Next", system-ui, sans-serif'}`; return Math.max(0, ...txts.map(t => c.measureText(t).width)); }
function fit(txt, maxW, size=12.5){ if (measure([txt], size) <= maxW) return txt; let t = txt; while (t.length > 3 && measure([t + '…'], size) > maxW) t = t.slice(0, -1); return t.trimEnd() + '…'; }
function niceTicks(max, n=4){ const raw = max / n; const mag = Math.pow(10, Math.floor(Math.log10(raw))); const step = [1,2,2.5,5,10].map(m => m*mag).find(s => s >= raw); const out = []; for (let v = 0; v <= max + 1e-9; v += step) out.push(+v.toFixed(6)); return out; }

const renders = [];
function reg(fn){ renders.push(fn); fn(); }
let rT; const ro = new ResizeObserver(() => { clearTimeout(rT); rT = setTimeout(() => renders.forEach(f => f()), 120); });
ro.observe(document.body);
const W = el => Math.max(260, Math.floor(el.clientWidth));

/* Horizontal bars. rows: [{label, values:[...], tip?, colors?, bold?}], series: [{name,color}]
   With 2+ series a legend is drawn above the bars automatically (pass legend: false if the card already has one).
   unit: optional short caption under the axis for single-series charts (e.g. '% of bank'). */
function hbars(el, opts){
  const svg = hbarsCore(el, opts);
  const { series, legend: lg = true, unit } = opts;
  if (series.length > 1 && lg) el.insertBefore(legend(series.map(s => ({ name: s.name, color: s.color }))), svg);
  if (unit){ const u = document.createElement('div'); u.className = 'unit'; u.textContent = unit; el.appendChild(u); }
  return svg;
}
function hbarsCore(el, { rows, series, max, fmt = pct, ticks, labelMax = 210, barH = 14, gapIn = 3, sub, ref, valueLabels = 'all' }){
  const w = W(el);
  const lw = Math.min(labelMax, Math.ceil(measure(rows.map(r => r.label))) + 8, w * 0.42);
  const ns = series.length;
  const groupH = ns * barH + (ns - 1) * gapIn;
  const rowH = groupH + (ns > 1 ? 14 : 10);
  const top = 6, bottom = ticks === false ? 4 : 22;
  const h = top + rows.length * rowH + bottom;
  const valW = Math.ceil(measure(rows.flatMap(r => r.values.filter(v => v != null).map(fmt)))) + 10;
  const x0 = lw + 6, x1 = w - valW;
  const mx = max ?? Math.max(...rows.flatMap(r => r.values.filter(v => v != null)));
  const sx = v => x0 + (x1 - x0) * v / mx;
  const svg = svgFor(el, w, h);
  if (ticks !== false){
    const g = S('g', { class: 'grid' }, svg);
    (ticks || niceTicks(mx)).forEach(t => { S('line', { x1: sx(t), x2: sx(t), y1: top - 2, y2: h - bottom + 2 }, g); T(fmt === pct ? t + '%' : String(t), { x: sx(t), y: h - 6, 'text-anchor': 'middle', class: 'muted' }, svg); });
  }
  if (ref != null){ S('line', { class: 'ref', x1: sx(ref.v), x2: sx(ref.v), y1: top - 4, y2: h - bottom + 2 }, svg); if (ref.label) T(ref.label, { x: sx(ref.v) + 4, y: top + 6, class: 'muted' }, svg); }
  rows.forEach((r, i) => {
    const y = top + i * rowH + (rowH - groupH) / 2;
    const lab = T(fit(r.label, lw - 2), { x: lw, y: y + groupH / 2 + 4, 'text-anchor': 'end' }, svg);
    if (lab.textContent !== r.label){ const tt = S('title', {}, lab); tt.textContent = r.label; }
    if (r.bold) lab.setAttribute('font-weight', '600');
    r.values.forEach((v, j) => {
      if (v == null) return;
      const by = y + j * (barH + gapIn);
      const p = S('path', { d: hbarPath(x0, by, sx(v) - x0, barH), fill: r.colors ? r.colors[j] : series[j].color }, svg);
      const hit = S('rect', { class: 'hit', x: x0, y: by - gapIn/2, width: Math.max(sx(v) - x0, 0) + valW, height: barH + gapIn }, svg);
      const rowsT = [{ v: fmt(v), l: (ns > 1 ? series[j].name + ' · ' : '') + r.label, c: r.colors ? r.colors[j] : series[j].color }];
      if (r.tip) rowsT.push(...r.tip(j));
      bind(hit, rowsT);
      if (valueLabels === 'all' || (valueLabels === 'last' && j === ns - 1)) T(fmt(v), { x: sx(v) + 5, y: by + barH / 2 + 4, class: 'val' }, svg);
    });
  });
  return svg;
}

/* Vertical columns. */
function vcols(el, { rows, color = 'var(--s1)', fmt = v => String(v), height = 190, yfmt, labelRotate = false, ticks }){
  const w = W(el);
  const left = 34, right = 6, top = 16;
  const bottom = labelRotate ? 74 : 24;
  const h = height;
  const mx = Math.max(...rows.map(r => r.v));
  const tk = ticks || niceTicks(mx, 4);
  const top_ = tk[tk.length - 1];
  const sy = v => h - bottom - (h - bottom - top) * v / top_;
  const svg = svgFor(el, w, h);
  const g = S('g', { class: 'grid' }, svg);
  tk.forEach(t => { S('line', { x1: left, x2: w - right, y1: sy(t), y2: sy(t) }, g); T((yfmt || String)(t), { x: left - 6, y: sy(t) + 4, 'text-anchor': 'end', class: 'muted' }, svg); });
  const band = (w - left - right) / rows.length;
  const bw = Math.min(24, band - 2);
  rows.forEach((r, i) => {
    const cx = left + band * i + band / 2;
    S('path', { d: vbarPath(cx - bw / 2, sy(0), bw, sy(0) - sy(r.v)), fill: r.color || color }, svg);
    const hit = S('rect', { class: 'hit', x: left + band * i, y: top, width: band, height: h - bottom - top }, svg);
    bind(hit, [{ v: fmt(r.v), l: r.label, c: r.color || color }]);
    if (labelRotate){ T(r.label, { x: cx, y: sy(0) + 10, transform: `rotate(-38 ${cx} ${sy(0) + 10})`, 'text-anchor': 'end', class: 'muted' }, svg); }
    else T(r.label, { x: cx, y: h - 6, 'text-anchor': 'middle', class: 'muted' }, svg);
  });
  return svg;
}

/* Forest / dot-interval plot. rows:[{label, v, lo, hi, color, v2?, color2?}] */
function forest(el, { rows, min, max, ref, refLabel, fmt = v => fmt1(v) + '%', ticks, labelMax = 230, rowH = 30, extra }){
  const w = W(el);
  const lw = Math.min(labelMax, Math.ceil(measure(rows.map(r => r.label))) + 8, w * 0.44);
  const top = refLabel ? 18 : 6, bottom = 24;
  const h = top + rows.length * rowH + bottom;
  const x0 = lw + 10, x1 = w - 12;
  const sx = v => x0 + (x1 - x0) * (v - min) / (max - min);
  const svg = svgFor(el, w, h);
  const g = S('g', { class: 'grid' }, svg);
  (ticks || []).forEach(t => { S('line', { x1: sx(t), x2: sx(t), y1: top - 2, y2: h - bottom }, g); T(String(t), { x: sx(t), y: h - 6, 'text-anchor': 'middle', class: 'muted' }, svg); });
  if (ref != null){ S('line', { class: 'ref', x1: sx(ref), x2: sx(ref), y1: top - 6, y2: h - bottom }, svg); if (refLabel) T(refLabel, { x: sx(ref), y: 11, 'text-anchor': 'middle', class: 'muted' }, svg); }
  rows.forEach((r, i) => {
    const cy = top + i * rowH + rowH / 2;
    T(fit(r.label, lw - 2), { x: lw, y: cy + 4, 'text-anchor': 'end' }, svg);
    if (r.lo != null) S('line', { x1: sx(r.lo), x2: sx(r.hi), y1: cy, y2: cy, stroke: r.color, 'stroke-width': 2, 'stroke-linecap': 'round' }, svg);
    if (r.v2 != null){ S('line', { x1: sx(r.v), x2: sx(r.v2), y1: cy, y2: cy, stroke: 'var(--rule)', 'stroke-width': 2 }, svg); S('circle', { cx: sx(r.v2), cy, r: 5, fill: r.color2, stroke: 'var(--surface)', 'stroke-width': 2 }, svg); }
    S('circle', { cx: sx(r.v), cy, r: 5.5, fill: r.color, stroke: 'var(--surface)', 'stroke-width': 2 }, svg);
    const hit = S('rect', { class: 'hit', x: x0, y: cy - rowH / 2, width: x1 - x0, height: rowH }, svg);
    bind(hit, r.tip || [{ v: fmt(r.v), l: r.label + (r.lo != null ? ` (95% CI ${fmt1(r.lo)}–${fmt1(r.hi)})` : ''), c: r.color }]);
  });
  return svg;
}

/* Heat table. rows: labels, cols: labels, m[i][j] (null = n/a) */
function heat(el, { rows, cols, m, min, max, fmt = fmt2, cellH = 30, labelMax = 200, colW, tipLabel }){
  const w = W(el);
  const lw = Math.min(labelMax, Math.ceil(measure(rows)) + 10, w * 0.4);
  const headH = 34;
  const cw = colW ? Math.min(colW, (w - lw) / cols.length) : (w - lw) / cols.length;
  const h = headH + rows.length * cellH + 2;
  const svg = svgFor(el, w, h);
  cols.forEach((c, j) => {
    const lines = String(c).split('\n');
    lines.forEach((ln, k) => T(ln, { x: lw + cw * j + cw / 2, y: headH - 8 - (lines.length - 1 - k) * 13, 'text-anchor': 'middle', class: 'muted' }, svg));
  });
  rows.forEach((r, i) => {
    const y = headH + i * cellH;
    const rl = T(fit(r, lw - 10), { x: lw - 8, y: y + cellH / 2 + 4, 'text-anchor': 'end' }, svg);
    if (rl.textContent !== r){ const tt = S('title', {}, rl); tt.textContent = r; }
    cols.forEach((c, j) => {
      const v = m[i][j];
      const x = lw + cw * j;
      if (v == null){ S('rect', { x: x + 1, y: y + 1, width: cw - 2, height: cellH - 2, rx: 3, fill: 'var(--tint)' }, svg); T('n/a', { x: x + cw / 2, y: y + cellH / 2 + 4, 'text-anchor': 'middle', class: 'muted' }, svg); return; }
      const p = Math.max(0, Math.min(1, (v - min) / (max - min)));
      const rect = S('rect', { x: x + 1, y: y + 1, width: cw - 2, height: cellH - 2, rx: 3, fill: `color-mix(in oklab, var(--seq-hi) ${Math.round(p * 100)}%, var(--seq-lo))` }, svg);
      T(fmt(v), { x: x + cw / 2, y: y + cellH / 2 + 4, 'text-anchor': 'middle', class: p > 0.55 ? 'on' : 'val' }, svg);
      bind(rect, [{ v: fmt(v), l: (tipLabel ? tipLabel(r, c) : r + ' · ' + String(c).replace('\n', ' ')) }]);
    });
  });
  return svg;
}

/* 100% stacked horizontal bars. rows:[{label, parts:[..]}], segs:[{name,color,textOn}] */
function stack100(el, { rows, segs, fmt = v => fmt1(v), rowH = 34, barH = 22, labelMax = 220, ref }){
  const w = W(el);
  const lw = Math.min(labelMax, Math.ceil(measure(rows.map(r => r.label))) + 10, w * 0.42);
  const top = 4, h = top + rows.length * rowH + 4;
  const x0 = lw, x1 = w - 2;
  const svg = svgFor(el, w, h);
  rows.forEach((r, i) => {
    const y = top + i * rowH + (rowH - barH) / 2;
    T(fit(r.label, lw - 10), { x: lw - 8, y: y + barH / 2 + 4, 'text-anchor': 'end' }, svg);
    const tot = r.parts.reduce((a, b) => a + b, 0);
    let x = x0;
    r.parts.forEach((v, j) => {
      const len = (x1 - x0) * v / tot;
      const seg = S('rect', { x: x + (j ? 1 : 0), y, width: Math.max(0, len - (j ? 1 : 0) - (j < r.parts.length - 1 ? 1 : 0)), height: barH, rx: 3, fill: segs[j].color }, svg);
      const label = fmt(v);
      if (len > measure([label]) + 12) T(label, { x: x + len / 2, y: y + barH / 2 + 4, 'text-anchor': 'middle', class: segs[j].textOn ? 'on' : 'val' }, svg);
      bind(seg, [{ v: fmt(v) + '%', l: segs[j].name + ' · ' + r.label, c: segs[j].color }]);
      x += len;
    });
  });
  if (ref != null){ S('line', { class: 'ref', x1: x0 + (x1 - x0) * ref, x2: x0 + (x1 - x0) * ref, y1: 0, y2: h }, svg); }
  return svg;
}

function table(el, head, rows, numCols = []){
  const t = document.createElement('table');
  const tr = document.createElement('tr');
  head.forEach((h, i) => { const th = document.createElement('th'); th.textContent = h; if (numCols.includes(i)) th.className = 'n'; tr.appendChild(th); });
  const thead = document.createElement('thead'); thead.appendChild(tr); t.appendChild(thead);
  const tb = document.createElement('tbody');
  rows.forEach(r => { const tr = document.createElement('tr'); r.forEach((c, i) => { const td = document.createElement('td'); td.textContent = c == null ? '–' : c; if (numCols.includes(i)) td.className = 'n'; tr.appendChild(td); }); tb.appendChild(tr); });
  t.appendChild(tb); el.replaceChildren(t);
}
function segCtl(sel, onChange){
  const g = $(sel); let val = $('[aria-pressed="true"]', g)?.dataset.v;
  g.addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; $$('button', g).forEach(x => x.setAttribute('aria-pressed', x === b ? 'true' : 'false')); val = b.dataset.v; onChange(val); });
  return () => val;
}
function fillSeg(sel, items){ const g = $(sel); items.forEach((it, i) => { const b = document.createElement('button'); b.type = 'button'; b.dataset.v = it.v; b.textContent = it.l; b.setAttribute('aria-pressed', i ? 'false' : 'true'); g.appendChild(b); }); }


/* ---------- station line: the shared stepper used by every factory station ----------
   Markup inside `root`: .stages > button.stage[data-s="0..n-1"] (each with span.k number + span.t title),
   optional button[data-play] ("Run the line") and button[data-all] ("Show all").
   render(s, animate) draws stage s; animate is true while the line is running (may animate in).
   dur(s) returns how long stage s stays on screen while the line runs (ms).
   Returns { show(s, animate), stop(), play(), stage }. */
function lineCtl(root, { count, render, dur = () => 1800, onStop, start }){
  const stages = $$('.stage', root), playBtn = $('[data-play]', root), allBtn = $('[data-all]', root);
  const idle = playBtn ? playBtn.textContent : '';
  let timer = null, cur = start ?? count - 1;
  function mark(s, animate){ stages.forEach((b, i) => { b.classList.toggle('done', i < s || (i === s && !animate)); b.classList.toggle('cur', i === s && animate); b.setAttribute('aria-current', i === s ? 'step' : 'false'); }); }
  function show(s, animate){ cur = s; mark(s, !!animate); render(s, !!animate); }
  function stop(){ clearTimeout(timer); timer = null; if (onStop) onStop(); if (playBtn) playBtn.textContent = idle; }
  function play(){
    stop(); if (playBtn) playBtn.textContent = 'Running';
    let s = 0;
    const step = () => { show(s, !reduce); timer = setTimeout(() => { if (s < count - 1){ s++; step(); } else { if (playBtn) playBtn.textContent = 'Run again'; show(count - 1, false); } }, reduce ? 900 : dur(s)); };
    step();
  }
  stages.forEach(b => b.addEventListener('click', () => { stop(); show(+b.dataset.s, false); }));
  if (playBtn) playBtn.addEventListener('click', play);
  if (allBtn) allBtn.addEventListener('click', () => { stop(); show(count - 1, false); });
  show(cur, false);
  return { show, stop, play, get stage(){ return cur; } };
}

/* ---------- legend(items): returns a .legend element. items: [{ name, color, kind: 'bar' | 'line' | 'dot', outline? }] ---------- */
function legend(items){
  const lg = document.createElement('div'); lg.className = 'legend';
  items.forEach(it => { const sp = document.createElement('span'); const i = document.createElement('i'); i.style.background = it.color; if (it.kind === 'line') i.className = 'line'; if (it.kind === 'dot') i.style.borderRadius = '50%'; if (it.outline) i.style.outline = '1px solid var(--rule-2)'; sp.append(i, document.createTextNode(it.name)); lg.appendChild(sp); });
  return lg;
}
