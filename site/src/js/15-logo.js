/* Logo.
   Header: a factory glyph. Its gear turns with scroll; hover/focus spins it and puffs persona heads
   out of the chimney.
   Title: the "o" of Factory is a gear that drives a thin belt of personas under the word. Scroll turns
   it, hover speeds it up, and the overlay button (click / Enter / Space) drops a new persona from the
   gear onto the belt. Reduced motion: everything static; a click still places a persona. */
const brand = $('.brand'), mteeth = $('.lg-mgear .lg-teeth'), puffs = $('.lg-puffs');
const wrap = $('.lg-title'), word = $('.lg-word'), oChar = $('.lg-o'), line = $('.lg-line'), ogear = $('.lg-ogear'), spin = $('.lg-ogear .lg-spin'), btn = $('.lg-stamp');
if (!brand || !mteeth || !wrap || !word || !oChar || !line || !spin || !btn) return;

// persona silhouette (the favicon shape, 32-unit box): bottom-centre at the origin
const HEAD = { cx: 0, cy: -19, r: 6 };
const BODY = 'M-12 0c0-7 5.4-11 12-11s12 4 12 11z';
function persona(parent, cls){
  const g = S('g', { class: 'lg-p ' + cls }, parent), k = S('g', {}, g);
  S('circle', HEAD, k); S('path', { d: BODY }, k);
  return g;
}

/* ---------- header glyph ---------- */
let brandOn = false, hv = 0, hAng = 0, puffT = 0;
function puff(){
  const g = S('g', { class: 'lg-puff' }, puffs);
  g.style.setProperty('--dx', (8 + Math.random() * 6).toFixed(1) + 'px');
  const k = S('g', { transform: 'scale(.3)' }, g);
  S('circle', HEAD, k); S('path', { d: BODY }, k);
  g.addEventListener('animationend', () => g.remove());
}
function brandSet(on){
  if (on === brandOn) return;
  brandOn = on;
  brand.classList.toggle('is-on', on);
  clearInterval(puffT);
  if (on && !reduce){ puff(); puffT = setInterval(puff, 460); kick(); }
}
brand.addEventListener('pointerenter', e => { if (e.pointerType !== 'touch') brandSet(true); });
brand.addEventListener('pointerleave', () => brandSet(false));
brand.addEventListener('focus', () => { if (brand.matches(':focus-visible')) brandSet(true); });
brand.addEventListener('blur', () => brandSet(false));

/* ---------- title belt ---------- */
let svg, gBelt, rivets, gItems, items = [], W = 0, H = 0, fs = 64, ih = 13, bt = 4, sp = 66, fz = 40, gap = 10;
let gKick = 0, gv = 0, pos = 0, v = 0, hot = false, inView = true, nAuto = 0;
const base = () => fs * 0.24;   // px/s along the belt

function build(){
  fs = parseFloat(getComputedStyle(word).fontSize) || 64;
  W = Math.round(word.getBoundingClientRect().width - fs * 0.04);
  ih = Math.max(8, Math.min(14, fs * 0.2)); bt = Math.max(3, Math.round(fs * 0.08));
  sp = fs * 1.02; fz = sp * 0.55; gap = Math.max(7, fs * 0.16);
  H = Math.ceil(ih + 1 + bt + 1);
  line.style.width = W + 'px'; line.style.height = H + 'px';
  line.replaceChildren();
  svg = S('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}`, focusable: 'false' }, line);
  gBelt = S('g', { class: 'lg-belt' }, svg);
  const y = ih + 1;
  S('rect', { x: 0.5, y: y + 0.5, width: W - 1, height: bt - 1 + 0.01, rx: (bt - 1) / 2, class: 'lg-bar' }, gBelt);
  rivets = S('line', { x1: bt, x2: W - bt, y1: y + bt / 2, y2: y + bt / 2, class: 'lg-riv', 'stroke-width': Math.max(1, bt * 0.34), 'stroke-dasharray': `${(gap * 0.5).toFixed(1)} ${(gap * 0.5).toFixed(1)}` }, gBelt);
  gItems = S('g', {}, svg);
  // keep the relative positions of what is on the belt; seed it if empty
  const old = items; items = [];
  if (old.length && old.W) old.forEach(o => add(o.x * W / old.W, o.cls));
  else for (let x = (pos % sp) - sp; x < W + sp; x += sp) add(x, 'c' + (nAuto++ % 4));
  items.W = W;
  place(); render();
}
function add(x, cls){
  const it = { x, cls, g: persona(gItems, cls), drop: null };
  items.push(it); return it;
}
function advance(d){
  if (!d) return;
  pos += d;
  items.forEach(it => { it.x += d; });
  items = Object.assign(items.filter(it => {
    const out = it.x > W + ih || it.x < -sp * 1.6;
    if (out) it.g.remove();
    return !out;
  }), { W });
  if (!items.length) add(0, 'c' + (nAuto++ % 4));
  let lo = Math.min(...items.map(i => i.x)), hi = Math.max(...items.map(i => i.x));
  while (lo > 0){ lo -= sp; add(lo, 'c' + (nAuto++ % 4)); }
  while (hi < W){ hi += sp; add(hi, 'c' + (nAuto++ % 4)); }
}
function render(t){
  rivets.setAttribute('stroke-dashoffset', (-pos % gap).toFixed(2));
  spin.setAttribute('transform', `rotate(${(((pos / (fs * 0.3)) * 180 / Math.PI + gKick) % 360).toFixed(2)})`);
  const k = ih / 25, yb = ih + 1;
  items.forEach(it => {
    const a = Math.max(0, Math.min(1, it.x / fz, (W - it.x) / fz));
    let y = yb, s = 1, sy = 1;
    if (it.drop){
      const p = Math.min(1, (t - it.drop.t0) / 340);
      y = yb + it.drop.y0 * (1 - p * p);                // falls, accelerating
      s = 0.35 + 0.65 * Math.min(1, p * 1.8);
      if (p >= 1){ const q = Math.min(1, (t - it.drop.t0 - 340) / 160); sy = 1 - 0.22 * Math.sin(q * Math.PI); if (q >= 1) it.drop = null; }
    }
    it.g.setAttribute('transform', `translate(${it.x.toFixed(2)} ${y.toFixed(2)})`);
    it.g.firstChild.setAttribute('transform', `scale(${(k * s * (2 - sy)).toFixed(3)} ${(k * s * sy).toFixed(3)})`);
    it.g.style.opacity = a.toFixed(3);
  });
}

/* overlay button: covers the word and the belt */
function place(){
  const r = wrap.getBoundingClientRect(), a = word.getBoundingClientRect(), b = line.getBoundingClientRect(), o = oChar.getBoundingClientRect();
  // gear over the "o": .6em across, centred on the glyph's x-height
  const d = fs * 0.6;
  Object.assign(ogear.style, { width: d + 'px', height: d + 'px', left: (o.left - r.left + o.width / 2 - d / 2) + 'px', top: (o.top - r.top + o.height / 2 + fs * 0.1 - d / 2) + 'px' });
  Object.assign(btn.style, { left: (a.left - r.left - 10) + 'px', top: (a.top - r.top - 4) + 'px', width: (a.width + 20) + 'px', height: (b.bottom - a.top + 10) + 'px' });
}
btn.hidden = false;
wrap.classList.add('is-live');
btn.title = 'Make a persona';
const setHot = on => { hot = on; wrap.classList.toggle('is-hot', on); kick(); };
btn.addEventListener('pointerenter', e => { if (e.pointerType !== 'touch') setHot(true); });
btn.addEventListener('pointerleave', () => setHot(false));
btn.addEventListener('focus', () => { if (btn.matches(':focus-visible')) setHot(true); });
btn.addEventListener('blur', () => setHot(false));
btn.addEventListener('click', stamp);

function stamp(){
  const lr = line.getBoundingClientRect(), gr = ogear.getBoundingClientRect();
  const gx = gr.left + gr.width / 2 - lr.left, gy = gr.top + gr.height / 2 - lr.top;
  // nearest free spot to the gear between two personas already on the belt
  const xs = items.map(i => i.x).sort((p, q) => p - q), m = ih * 1.3;
  let best = gx, bd = Infinity;
  for (let i = 0; i < xs.length - 1; i++){
    if (xs[i + 1] - xs[i] < 2 * m) continue;
    const c = Math.max(xs[i] + m, Math.min(xs[i + 1] - m, gx));
    if (c < fz || c > W - fz) continue;
    if (Math.abs(c - gx) < bd){ bd = Math.abs(c - gx); best = c; }
  }
  const it = add(best, 'new');
  if (!reduce){
    it.drop = { t0: performance.now(), y0: gy - (ih + 1) + ih * 0.4 };
    gv += 900;   // the gear jolts; the belt keeps its pace so the new persona can be followed
    ogear.classList.remove('is-press'); void ogear.getBoundingClientRect(); ogear.classList.add('is-press');
    kick();
  }
  render(performance.now());
}
ogear.addEventListener('animationend', () => ogear.classList.remove('is-press'));

/* ---------- one loop for both ---------- */
let raf = 0, last = 0, lastSy = scrollY;
function kick(){ if (!raf && !reduce){ last = 0; raf = requestAnimationFrame(tick); } }
function tick(t){
  raf = 0;
  const dt = last ? Math.min(0.05, (t - last) / 1000) : 0; last = t;
  const sy = scrollY, ds = sy - lastSy; lastSy = sy;
  // header gear: scroll angle + hover spin
  hv += ((brandOn ? 300 : 0) - hv) * Math.min(1, dt * 3);
  hAng = (hAng + hv * dt) % 360;
  mteeth.setAttribute('transform', `translate(24.4 19) rotate(${((sy * 0.35 + hAng) % 360).toFixed(2)})`);
  let more = brandOn || hv > 1;
  // title belt: drift, hover speed, scroll, stamp kick
  if (inView){
    v += ((hot ? base() * 2.6 : base()) - v) * Math.min(1, dt * 2.5);
    gKick = (gKick + gv * dt) % 360; gv *= Math.max(0, 1 - dt * 5);
    advance(v * dt + ds * 0.25);
    render(t);
    more = true;
  }
  if (more) raf = requestAnimationFrame(tick);
}

build();
if (document.fonts && document.fonts.ready) document.fonts.ready.then(build);
if ('ResizeObserver' in window){
  let w0 = 0;
  new ResizeObserver(() => { const w = word.getBoundingClientRect().width; if (Math.abs(w - w0) > 0.5){ w0 = w; build(); } else place(); }).observe(wrap);
}
if ('IntersectionObserver' in window)
  new IntersectionObserver(es => { inView = es[es.length - 1].isIntersecting; if (inView) kick(); }).observe(wrap);
if (!reduce){
  addEventListener('scroll', kick, { passive: true });
  kick();
}
