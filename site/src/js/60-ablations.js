/* ======================= ABLATIONS: tuning the machine ======================= */
// Numbers used here that are not in data.js:
const AB_T6 = { convs: 400, turns: 960, ci: 3.2 };   // Table 6 caption: 400 conversations per arm, about 960 judged user turns, 95% intervals at most ±3.2 points
const AB_T7 = { convs: 300, turns: 730, ci: 3.6 };   // Table 7 caption: 300 conversations per variant, about 730 judged user turns, 95% intervals at most ±3.6 points
const AB_F = { sources: 194, rewrites: 12845, gens: 4 }; // Appendix F setup: up to 194 source messages, 12,845 valid rewrites, 4 generators
const AB_FAM = [ // Table 22: family means over four generators [family, style, intent, script]
  ['Digital fluency', 0.801, 0.624, 0.921], ['Sentence length', 0.822, 0.625, 0.920], ['AI stance', 0.800, 0.622, 0.916], ['Age', 0.810, 0.627, 0.924],
  ['Gender', 0.821, 0.631, 0.920], ['Education', 0.808, 0.620, 0.929], ['Occupation', 0.801, 0.622, 0.920], ['Hobbies', 0.814, 0.646, 0.925]
];

function el(tag, cls, text, parent){ const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; if (parent) parent.appendChild(n); return n; }
function approxTag(parent){ el('span', 'approx', 'read from figure', parent); }

(function tuning(){
  const lineEl = $('#abLine'), panel = $('#abPanel'), out = $('#abRead');
  const T6 = D.selectionAblation, X = D.crossLingual, RW = D.rewriters, A = D.attributes;
  const SEL = { cons: 'Conservative matching', rand: 'Random, same language' };
  const PR = { tpl: 'Template only', frame: 'Template + system framing' };
  const t6 = (sel, pr) => T6.find(r => r.sel === SEL[sel] && r.prompt === (pr === 'tpl' ? 'template only' : 'template + framing'));
  const other = { cons: 'rand', rand: 'cons', tpl: 'frame', frame: 'tpl' };
  const attrLabel = i => i < 0 ? 'No persona (baseline)' : A.rows[i][0];
  const PIPE = { sel: 'cons', pr: 'tpl', xl: 1, rw: 0, at: 0 };
  const st = { ...PIPE };

  const pctF = v => fmt1(v) + '%', ptsD = d => (d > 0 ? '+' : d < 0 ? '−' : '±') + fmt1(Math.abs(d)) + ' pts';
  const scD = n => d => (d > 0 ? '+' : d < 0 ? '−' : '±') + Math.abs(d).toFixed(n);

  /* ---------- the five knobs ----------
     opts: [{v, l, d, tag?}]  pipe: value the pipeline ships with
     read(): { cur: label, alt: label, mets: [{name, v, a, altName?, max, fmt, dfmt, ci?}] } */
  const K = [
    { key: 'sel', name: 'Persona selection', src: 'Table 6', what: 'Which persona re-voices the turn.',
      opts: [{ v: 'cons', l: SEL.cons, d: 'Location, then top-1 embedding, then language pool' }, { v: 'rand', l: SEL.rand, d: 'Any persona that shares the prompt’s language' }],
      held: `Gemma-4-31B rewriter, same judge and sanity gate. ${AB_T6.convs} conversations per arm, about ${AB_T6.turns} judged turns.`,
      note: 'Conservative matching adds 22 to 23 points of style and keeps intent slightly better. A plausible persona gives the rewriter something concrete to express.',
      head: 'Style',
      read(){ const c = t6(st.sel, st.pr), a = t6(other[st.sel], st.pr); return { cur: SEL[st.sel], alt: SEL[other[st.sel]], ctx: 'Rewrite prompt: ' + PR[st.pr].toLowerCase(), mets: t6mets(c, a) }; } },
    { key: 'pr', name: 'Rewrite prompt', src: 'Table 6', what: 'How the rewrite instruction reaches the model.',
      opts: [{ v: 'tpl', l: PR.tpl, d: 'The rewrite template as a single user message' }, { v: 'frame', l: PR.frame, d: 'Same template inside a system prompt that frames the rewriter as a generic text-transformation component' }],
      held: `Gemma-4-31B rewriter, same judge and sanity gate. ${AB_T6.convs} conversations per arm, about ${AB_T6.turns} judged turns.`,
      note: 'The extra framing costs 4 to 5 points of style in both selection settings, so the pipeline uses the template alone.',
      head: 'Style',
      read(){ const c = t6(st.sel, st.pr), a = t6(st.sel, other[st.pr]); return { cur: PR[st.pr], alt: PR[other[st.pr]], ctx: 'Persona selection: ' + SEL[st.sel].toLowerCase(), mets: t6mets(c, a) }; } },
    { key: 'xl', name: 'Cross-lingual strategy', src: 'Table 7', what: 'How a turn moves into the persona’s language.',
      opts: [{ v: 1, l: 'Translate, then restyle', d: 'Literal translation first, then the same-language rewrite' }, { v: 0, l: 'Single pass', d: 'Re-voiced directly into the persona’s language' }],
      held: `same ${AB_T7.convs} conversations, personas and rewriter (Gemma-4-31B). Intent is judged against the literal translation. Target language is checked with fastText.`,
      note: 'Two steps keep the request and reach the target language more often, at a small cost in style. A rewrite in the wrong language defeats the purpose of the cross-lingual mode, so the pipeline uses two steps.',
      head: 'Target language',
      read(){ const c = X[st.xl], a = X[1 - st.xl]; const m = (name, k) => ({ name, v: c[k], a: a[k], max: 100, fmt: pctF, dfmt: ptsD, ci: AB_T7.ci });
        return { cur: c.v, alt: a.v, mets: [m('Target language', 'target'), m('Intent', 'intent'), m('Style', 'style'), m('Sanity pass', 'sanity')] }; } },
    { key: 'rw', name: 'Rewriter', src: 'Fig. 25', approx: true, what: 'Which model rewrites the user turns.',
      opts: RW.names.map((n, i) => ({ v: i, l: n, d: ['Production rewriter, the balanced choice', 'Production rewriter, restyles most', 'Production judge', 'Extra persona generator'][i] })),
      held: `the same 16 single-attribute conditions for every rewriter.`,
      note: 'Ministral adopts the most style but keeps the least intent and script. Gemma is the balanced choice.',
      head: 'Intent',
      read(){ const a = st.rw === 0 ? 1 : 0; const m = (name, k) => ({ name, v: RW[k][st.rw], a: RW[k][a], max: 1, fmt: fmt2, dfmt: scD(2) });
        return { cur: RW.names[st.rw], alt: RW.names[a], mets: [m('Style adoption', 'style'), m('Intent preservation', 'intent'), m('Script stability', 'script')] }; } },
    { key: 'at', name: 'One persona attribute', src: 'Fig. 24', what: 'Vary exactly one attribute of the persona.',
      held: `Up to ${AB_F.sources} source messages, ${AB_F.gens} rewriters, ${fmt0(AB_F.rewrites)} valid rewrites. Scores averaged over the rewriters.`,
      note: 'Rows barely move. Family means for style stay between 0.80 and 0.82, and every family loses 0.06 to 0.07 of script stability. The paper treats these numbers as a measurement and does not rank the attributes.',
      head: 'Script',
      read(){
        const i = st.at, base = A.baselineScript;
        if (i < 0) return { cur: attrLabel(-1), alt: null, mets: [
          { name: 'Style adoption', v: null, na: 'n/a: no rewrite to judge', max: 1, fmt: fmt3 },
          { name: 'Intent preservation', v: null, na: 'n/a: no rewrite to judge', max: 1, fmt: fmt3 },
          { name: 'Script stability', v: base, a: null, max: 1, fmt: fmt3, sub: 'Ceiling for every condition' } ] };
        const r = A.rows[i], s = A.rows[i ^ 1];
        return { cur: r[0], alt: s[0] + '; script: no-persona baseline', mets: [
          { name: 'Style adoption', v: r[1], a: s[1], altName: s[0], max: 1, fmt: fmt3, dfmt: scD(3) },
          { name: 'Intent preservation', v: r[2], a: s[2], altName: s[0], max: 1, fmt: fmt3, dfmt: scD(3) },
          { name: 'Script stability', v: r[3], a: base, altName: 'no-persona baseline', max: 1, fmt: fmt3, dfmt: scD(3) } ] };
      } }
  ];
  function t6mets(c, a){ const m = (name, k) => ({ name, v: c[k], a: a[k], max: 100, fmt: pctF, dfmt: ptsD, ci: AB_T6.ci }); return [m('Style', 'style'), m('Intent', 'intent'), m('Sanity pass', 'sanity')]; }
  const headDelta = k => { const r = K[k].read(); const m = r.mets.find(x => x.name.startsWith(K[k].head)) || r.mets[0]; if (m.v == null || m.a == null) return null; return { name: K[k].head.toLowerCase(), d: m.v - m.a, txt: m.dfmt(m.v - m.a), ns: m.ci != null && Math.abs(m.v - m.a) < m.ci }; };
  const posLabel = k => { const key = K[k].key; if (key === 'at') return attrLabel(st.at); const o = K[k].opts.find(o => o.v === st[key]); return o.l; };
  const atPipe = k => K[k].key === 'at' ? null : st[K[k].key] === PIPE[K[k].key];

  /* ---------- key in the top bar ---------- */
  const key = $('#abKey');
  const k1 = el('span', 'kitem', null, key); el('i', 'pdot', null, k1); k1.append('Pipeline setting');
  const k2 = el('span', 'kitem', null, key); el('span', 'dl up', '+', k2); el('span', 'dl dn', '−', k2); k2.append('Change vs the tick');
  const k3 = el('span', 'kitem', null, key); el('span', 'dl ns', '±', k3); k3.append('Smaller than the 95% interval');

  /* ---------- control panel ---------- */
  let cur = 4, running = false, flips = [];
  function setKnob(k, v){ st[K[k].key] = v; renderPanel(cur); update(); }
  function optBtn(parent, k, o){
    const b = el('button', 'opt' + (o.v === PIPE[K[k].key] ? ' isp' : ''), null, parent); b.type = 'button';
    b.setAttribute('aria-pressed', st[K[k].key] === o.v ? 'true' : 'false');
    const t = el('span', 'ol', null, b); if (o.v === PIPE[K[k].key]) el('i', 'pdot', null, t); t.append(o.l);
    if (o.d) el('span', 'od', o.d, b);
    b.addEventListener('click', () => { lineStop(); setKnob(k, o.v); });
    return b;
  }
  function attrSwitch(parent){
    const g = el('div', 'atsw', null, parent);
    const base = el('button', 'opt base', null, g); base.type = 'button'; base.setAttribute('aria-pressed', st.at < 0 ? 'true' : 'false');
    el('span', 'ol', 'No persona (baseline)', base);
    base.addEventListener('click', () => { lineStop(); setKnob(4, -1); });
    for (let f = 0; f < A.rows.length; f += 2){
      const row = el('div', 'atrow', null, g);
      el('span', 'af', A.rows[f][0].split(': ')[0], row);
      [f, f + 1].forEach(i => { const b = el('button', 'opt sm', null, row); b.type = 'button'; b.textContent = A.rows[i][0].split(': ')[1].replace('/', '/\u200b'); b.setAttribute('aria-pressed', st.at === i ? 'true' : 'false'); b.setAttribute('aria-label', A.rows[i][0]); b.addEventListener('click', () => { lineStop(); setKnob(4, i); }); });
    }
  }
  function renderPanel(s){
    panel.replaceChildren();
    el('div', 'ph', 'Control panel', panel);
    K.forEach((kn, k) => {
      const box = el('div', 'knob' + (k === s ? ' on' : '') + (running && k > s ? ' later' : ''), null, panel);
      const h = el('button', 'kh', null, box); h.type = 'button'; h.setAttribute('aria-expanded', k === s ? 'true' : 'false');
      el('span', 'kn', String(k + 1), h);
      const tt = el('span', 'kt', null, h); el('b', null, kn.name, tt);
      const pos = el('span', 'kp', null, tt); if (atPipe(k)) el('i', 'pdot', null, pos); pos.append(posLabel(k));
      const hd = headDelta(k);
      if (hd) { const d = el('span', 'kd', null, h); el('small', null, hd.name, d); el('span', 'dl ' + (hd.ns ? 'ns' : hd.d > 0 ? 'up' : hd.d < 0 ? 'dn' : 'ns'), hd.txt, d); }
      h.addEventListener('click', () => { lineStop(); line.show(k, false); });
      if (k !== s) return;
      const b = el('div', 'kb', null, box);
      el('p', 'kq', kn.what, b);
      if (kn.key === 'at') attrSwitch(b);
      else { const sw = el('div', 'sw' + (kn.opts.length > 2 ? ' four' : ''), null, b); sw.setAttribute('role', 'group'); sw.setAttribute('aria-label', kn.name); kn.opts.forEach(o => optBtn(sw, k, o)); }
      el('p', 'kf', kn.key === 'at' ? 'This probe has no pipeline setting. ' + kn.held : 'Held fixed: ' + kn.held, b);
    });
  }

  /* ---------- readout ---------- */
  let gauges = [], extra = null, redraw = null;
  function gauge(parent, m){
    const g = el('div', 'gauge', null, parent);
    const gh = el('div', 'gh', null, g);
    el('span', 'gn', m.name, gh);
    const gv = el('span', 'gv', null, gh); const dl = el('span', 'dl', null, gh);
    const tr = el('div', 'gt', null, g); const fill = el('b', null, null, tr); const tick = el('i', null, null, tr);
    const gs = el('div', 'gs', null, g);
    const tipRows = []; bind(g, tipRows);
    return { g, gv, dl, fill, tick, gs, tipRows };
  }
  function fillGauges(r, first){
    r.mets.forEach((m, i) => {
      const G = gauges[i]; if (!G) return;
      if (m.v == null){ G.gv.textContent = 'n/a'; G.dl.textContent = ''; G.dl.className = 'dl'; G.fill.style.width = '0'; G.tick.style.opacity = 0; G.gs.textContent = m.na; G.g.classList.add('na'); return; }
      G.g.classList.remove('na');
      G.gv.textContent = m.fmt(m.v);
      const w = (100 * m.v / m.max) + '%';
      if (first){ G.fill.style.width = '0'; requestAnimationFrame(() => requestAnimationFrame(() => { G.fill.style.width = w; })); } else G.fill.style.width = w;
      if (m.a == null){ G.tick.style.opacity = 0; G.dl.textContent = ''; G.dl.className = 'dl'; G.gs.textContent = m.sub || ''; return; }
      G.tick.style.opacity = 1; G.tick.style.left = `calc(${100 * m.a / m.max}% - 1px)`;
      const d = m.v - m.a, ns = m.ci != null && Math.abs(d) < m.ci;
      G.dl.textContent = m.dfmt(d); G.dl.className = 'dl ' + (ns || Math.abs(d) < 1e-9 ? 'ns' : d > 0 ? 'up' : 'dn');
      G.dl.title = ns ? `Smaller than the ±${m.ci}-point 95% interval` : '';
      G.gs.textContent = 'vs ' + (m.altName || r.alt) + ': ' + m.fmt(m.a);
      G.tipRows.splice(0, G.tipRows.length, { v: m.fmt(m.v), l: m.name + ' · ' + r.cur, c: 'var(--s1)' }, { v: m.fmt(m.a), l: m.name + ' · ' + (m.altName || r.alt), c: 'var(--ink)' });
      G.g.setAttribute('aria-label', G.tipRows.map(t => t.l + ' ' + t.v).join(', '));
    });
  }
  function legendFor(r){
    const items = [{ name: 'Selected: ' + r.cur, color: 'var(--s1)' }];
    if (r.alt) items.push({ name: 'Tick: ' + r.alt, color: 'var(--ink)', kind: 'line' });
    const lg = legend(items); lg.classList.add('glg');
    const tickI = lg.querySelectorAll('i')[1]; if (tickI) tickI.className = 'vtick';
    return lg;
  }
  function headOf(s){
    const kn = K[s];
    const h = el('div', 'rhd', null);
    el('h3', 'rh', 'Readout', h);
    const src = el('span', 'src', null, h); if (kn.approx) approxTag(src); src.append(' ' + kn.src);
    return h;
  }
  function buildRead(s, animate){
    out.replaceChildren(); gauges = []; extra = null; redraw = null;
    const kn = K[s], r = kn.read();
    out.appendChild(headOf(s));
    const lgSlot = el('div', 'lgslot', null, out); lgSlot.appendChild(legendFor(r));
    const gw = el('div', 'gauges' + (r.mets.length === 4 ? ' g4' : ''), null, out);
    r.mets.forEach(m => gauges.push(gauge(gw, m)));
    fillGauges(r, animate);
    if (s <= 1) extra = matrix(out);
    if (s === 2) extra = xlPair(out);
    if (s === 3) extra = rwTable(out);
    if (s === 4) extra = attrHeat(out);
    el('p', 'rnote', kn.note, out);
    $('#abSrc').textContent = 'Source: paper ' + kn.src + (s <= 1 ? ' · ' + AB_T6.convs + ' conversations per arm' : s === 2 ? ' · ' + AB_T7.convs + ' conversations per variant' : s === 4 ? ' · Table 22 · ' + fmt0(AB_F.rewrites) + ' rewrites' : '');
    if (animate) $$('.rhd, .lgslot, .gauges, .mx, .rwt, .hwrap, .rnote', out).forEach((n, i) => { n.classList.add('in'); n.style.animationDelay = (i * 70) + 'ms'; });
  }
  function update(){
    const r = K[cur].read();
    const lgSlot = $('.lgslot', out); if (lgSlot) lgSlot.replaceChildren(legendFor(r));
    fillGauges(r, false);
    if (extra) extra();
  }

  /* 2x2 of Table 6 */
  function matrix(parent){
    const wrap = el('div', 'mx', null, parent);
    const hd = el('div', 'mxt', null, wrap); el('span', null, 'All four arms, style adoption', hd); el('span', 'src', 'Table 6', hd);
    const g = el('div', 'mxg', null, wrap);
    el('span', 'mxh corner', '', g);
    ['tpl', 'frame'].forEach(p => el('span', 'mxh', PR[p], g));
    const cells = [];
    ['cons', 'rand'].forEach(sel => {
      el('span', 'mxr', SEL[sel], g);
      ['tpl', 'frame'].forEach(pr => {
        const row = t6(sel, pr);
        const b = el('button', 'mxc', null, g); b.type = 'button';
        const big = el('b', null, null, b); if (sel === PIPE.sel && pr === PIPE.pr) el('i', 'pdot', null, big); big.append(pctF(row.style));
        el('small', null, `intent ${fmt1(row.intent)} · sanity ${fmt1(row.sanity)}`, b);
        b.setAttribute('aria-label', `${SEL[sel]}, ${PR[pr]}: style ${pctF(row.style)}, intent ${pctF(row.intent)}, sanity ${pctF(row.sanity)}`);
        b.addEventListener('click', () => { lineStop(); st.sel = sel; st.pr = pr; renderPanel(cur); update(); });
        cells.push({ b, sel, pr });
      });
    });
    const paint = () => cells.forEach(c => {
      const isCur = c.sel === st.sel && c.pr === st.pr;
      const isAlt = cur === 0 ? (c.pr === st.pr && c.sel !== st.sel) : (c.sel === st.sel && c.pr !== st.pr);
      c.b.classList.toggle('cur', isCur); c.b.classList.toggle('alt', isAlt); c.b.setAttribute('aria-pressed', isCur ? 'true' : 'false');
    });
    paint();
    const lg = legend([{ name: 'Selected arm', color: 'var(--s1)' }, { name: 'Compared arm', color: 'transparent', outline: true }]); lg.classList.add('mxlg');
    const dashed = lg.querySelectorAll('i')[1]; if (dashed) dashed.className = 'dash';
    wrap.appendChild(lg);
    return paint;
  }
  /* both variants of Table 7 */
  function xlPair(parent){
    const wrap = el('div', 'mx', null, parent);
    const hd = el('div', 'mxt', null, wrap); el('span', null, 'Both variants, target language', hd); el('span', 'src', 'Table 7', hd);
    const g = el('div', 'mxg two', null, wrap);
    const cells = [1, 0].map(v => {
      const row = X[v];
      const b = el('button', 'mxc', null, g); b.type = 'button';
      el('span', 'mxn', row.v, b);
      const big = el('b', null, null, b); if (v === PIPE.xl) el('i', 'pdot', null, big); big.append(pctF(row.target));
      el('small', null, `intent ${fmt1(row.intent)} · style ${fmt1(row.style)} · sanity ${fmt1(row.sanity)}`, b);
      b.setAttribute('aria-label', `${row.v}: target language ${pctF(row.target)}, intent ${pctF(row.intent)}, style ${pctF(row.style)}, sanity ${pctF(row.sanity)}`);
      b.addEventListener('click', () => { lineStop(); st.xl = v; renderPanel(cur); update(); });
      return { b, v };
    });
    const paint = () => cells.forEach(c => { const on = c.v === st.xl; c.b.classList.toggle('cur', on); c.b.classList.toggle('alt', !on); c.b.setAttribute('aria-pressed', on ? 'true' : 'false'); });
    paint();
    const lg = legend([{ name: 'Selected variant', color: 'var(--s1)' }, { name: 'Compared variant', color: 'transparent', outline: true }]); lg.classList.add('mxlg');
    const dashed = lg.querySelectorAll('i')[1]; if (dashed) dashed.className = 'dash';
    wrap.appendChild(lg);
    return paint;
  }
  /* all four rewriters (Fig. 25) */
  function rwTable(parent){
    const wrap = el('div', 'rwt', null, parent);
    const hd = el('div', 'mxt', null, wrap); el('span', null, 'All four rewriters', hd); const sc = el('span', 'src', null, hd); approxTag(sc); sc.append(' Fig. 25');
    const tw = el('div', 'tblwrap', null, wrap);
    table(tw, ['Rewriter', 'Style', 'Intent', 'Script'], RW.names.map((n, i) => [n, fmt2(RW.style[i]), fmt2(RW.intent[i]), fmt2(RW.script[i])]), [1, 2, 3]);
    const trs = $$('tbody tr', tw);
    trs.forEach((tr, i) => { tr.tabIndex = 0; tr.setAttribute('role', 'button'); tr.setAttribute('aria-label', 'Select ' + RW.names[i]); const go = () => { lineStop(); st.rw = i; renderPanel(cur); update(); }; tr.addEventListener('click', go); tr.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } }); if (i === PIPE.rw) { const td = tr.firstChild; td.textContent = ''; el('i', 'pdot', null, td); td.append(RW.names[i]); } });
    const paint = () => trs.forEach((tr, i) => { tr.classList.toggle('cur', i === st.rw); tr.classList.toggle('alt', i === (st.rw === 0 ? 1 : 0)); });
    paint();
    const lg = legend([{ name: 'Selected rewriter', color: 'var(--s1)' }, { name: 'Compared rewriter', color: 'var(--ink)' }]); lg.classList.add('rwlg');
    wrap.appendChild(lg);
    return paint;
  }
  /* full 16 x 3 grid (Fig. 24), selected condition outlined */
  function attrHeat(parent){
    const wrap = el('div', 'hwrap', null, parent);
    const hd = el('div', 'mxt', null, wrap); el('span', null, 'Every condition on one 0 to 1 scale', hd); el('span', 'src', 'Fig. 24', hd);
    const sc = el('div', 'scale', null, wrap); el('span', 'sl', 'Score', sc); el('span', null, '0', sc); el('i', null, null, sc); el('span', null, '1', sc);
    const ch = el('div', 'chart', null, wrap);
    const rows = ['No persona (baseline)'].concat(A.rows.map(r => r[0]));
    const m = [[null, null, A.baselineScript]].concat(A.rows.map(r => r.slice(1)));
    const lg = legend([{ name: 'Selected condition', color: 'transparent' }]); lg.classList.add('hlg');
    sc.appendChild(lg);
    // Own grid instead of heat(): heat() caps labels at 40% of the width, which cut every long label on phones.
    const draw = () => {
      const w = W(ch), narrow = w < 520;
      const cols = narrow ? [['Style'], ['Intent'], ['Script']] : [['Style', 'adoption'], ['Intent', 'preservation'], ['Script', 'stability']];
      const full = ['Style adoption', 'Intent preservation', 'Script stability'];
      const cw = Math.min(150, Math.max(narrow ? 40 : 64, (w - Math.ceil(measure(rows)) - 12) / 3));
      const lw = w - 3 * cw, headH = narrow ? 22 : 34, cellH = 22;
      const svg = svgFor(ch, w, headH + rows.length * cellH + 2);
      cols.forEach((c, j) => c.forEach((ln, k) => T(ln, { x: lw + cw * j + cw / 2, y: headH - 8 - (c.length - 1 - k) * 13, 'text-anchor': 'middle', class: 'muted' }, svg)));
      rows.forEach((r, ri) => {
        const y = headH + ri * cellH, i = ri - 1;
        const rl = T(fit(r, lw - 10), { x: lw - 8, y: y + cellH / 2 + 4, 'text-anchor': 'end', class: ri === st.at + 1 ? 'hlab' : null }, svg);
        if (rl.textContent !== r){ const tt = S('title', {}, rl); tt.textContent = r; }
        const go = () => { lineStop(); st.at = i; renderPanel(cur); update(); };
        m[ri].forEach((v, j) => {
          const x = lw + cw * j;
          if (v == null){ S('rect', { x: x + 1, y: y + 1, width: cw - 2, height: cellH - 2, rx: 3, fill: 'var(--tint)' }, svg); T('n/a', { x: x + cw / 2, y: y + cellH / 2 + 4, 'text-anchor': 'middle', class: 'muted' }, svg); return; }
          const rc = S('rect', { x: x + 1, y: y + 1, width: cw - 2, height: cellH - 2, rx: 3, fill: `color-mix(in oklab, var(--seq-hi) ${Math.round(v * 100)}%, var(--seq-lo))` }, svg);
          T(fmt3(v), { x: x + cw / 2, y: y + cellH / 2 + 4, 'text-anchor': 'middle', class: v > 0.55 ? 'on' : 'val', 'pointer-events': 'none' }, svg);
          bind(rc, [{ v: fmt3(v), l: r + ' · ' + full[j] }]);
          rc.style.cursor = 'pointer'; rc.addEventListener('click', go);
          rc.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
        });
      });
      const sy = headH + (st.at + 1) * cellH;
      S('rect', { class: 'sel', x: lw - 0.5, y: sy - 0.5, width: 3 * cw + 1, height: cellH + 1, rx: 4 }, svg);
    };
    redraw = draw; draw();
    return draw;
  }

  /* ---------- the line ---------- */
  function lineStop(){ flips.forEach(clearTimeout); flips = []; if (running){ running = false; lineEl.classList.remove('running'); } }
  // While the line runs, each knob starts away from the pipeline setting and is flipped onto it.
  const RUN_FROM = [{ sel: 'rand' }, { pr: 'frame' }, { xl: 0 }, null, { at: -1 }];
  const RUN_SEQ = [3, 2, 1, 0]; // rewriter knob sweeps GLM → MiniMax → Ministral → Gemma
  function render(s, animate){
    flips.forEach(clearTimeout); flips = [];
    cur = s; running = !!animate; lineEl.classList.toggle('running', running);
    if (animate){
      if (s === 0) Object.assign(st, PIPE);
      if (s === 3){ st.rw = RUN_SEQ[0]; RUN_SEQ.slice(1).forEach((v, i) => flips.push(setTimeout(() => { st.rw = v; renderPanel(cur); update(); }, 700 + i * 650))); }
      else { const from = RUN_FROM[s]; const k = Object.keys(from)[0]; const to = PIPE[k]; st[k] = from[k]; flips.push(setTimeout(() => { st[k] = s === 4 ? PIPE.at : to; renderPanel(cur); update(); }, 1000)); }
    }
    renderPanel(s);
    buildRead(s, animate);
  }
  // "Show all" returns every knob to the pipeline setting before the core shows the last stage.
  $('[data-all]', lineEl).addEventListener('click', () => Object.assign(st, PIPE), true);
  const line = lineCtl(lineEl, { count: 5, render, dur: s => s === 3 ? 3300 : 2500, onStop: lineStop });
  reg(() => { if (redraw) redraw(); });
})();

/* ---------- supporting cards ---------- */
(function spread(){
  const RW = D.rewriters;
  const AX = [['Style adoption', 'style', 1], ['Intent preservation', 'intent', 2], ['Script stability', 'script', 3]];
  const box = $('#abSpread');
  box.appendChild(legend([{ name: '8 attribute families', color: 'var(--s1)', kind: 'dot' }, { name: '4 rewriters', color: 'var(--s2)', kind: 'dot' }]));
  const ch = el('div', null, null, box);
  reg(() => {
    const w = W(ch);
    const lw = Math.ceil(measure(['families', 'rewriters'], 11.5)) + 10, rw = Math.ceil(measure(['0.000', 'range'], 11.5)) + 8;
    // Axis starts at 0.3 (lowest value is 0.38) so close rewriters do not overlap on phones.
    const D0 = 0.3, x0 = lw + 8, x1 = w - rw - 6, sx = v => x0 + (x1 - x0) * (v - D0) / (1 - D0);
    const grpH = w > 440 ? 84 : 70, sp = w > 440 ? 26 : 22, top = 4, h = top + AX.length * grpH + 20;
    const svg = svgFor(ch, w, h);
    const g = S('g', { class: 'grid' }, svg);
    [0.4, 0.6, 0.8, 1].forEach(t => { S('line', { x1: sx(t), x2: sx(t), y1: top, y2: h - 20 }, g); T(t.toFixed(1), { x: sx(t), y: h - 5, 'text-anchor': 'middle', class: 'muted' }, svg); });
    T('range', { x: w - 2, y: top + 13, 'text-anchor': 'end', class: 'muted' }, svg);
    AX.forEach(([name, k, fi], a) => {
      const y = top + a * grpH;
      T(name, { x: 0, y: y + 13, class: 'axn' }, svg);
      const strips = [['families', AB_FAM.map(f => [f[0], f[fi]]), 'var(--s1)', 4], ['rewriters', RW.names.map((n, i) => [n, RW[k][i]]), 'var(--s2)', 5.5]];
      strips.forEach(([lab, pts, col, r], j) => {
        const cy = y + 32 + j * sp;
        T(lab, { x: lw, y: cy + 4, 'text-anchor': 'end', class: 'muted' }, svg);
        const vs = pts.map(p => p[1]), lo = Math.min(...vs), hi = Math.max(...vs);
        S('line', { x1: sx(lo), x2: sx(hi), y1: cy, y2: cy, stroke: col, 'stroke-width': 2, 'stroke-opacity': 0.45 }, svg);
        pts.forEach(([n, v]) => { const c = S('circle', { cx: sx(v), cy, r, fill: col, stroke: 'var(--surface)', 'stroke-width': 1.5 }, svg); bind(c, [{ v: (j ? fmt2 : fmt3)(v), l: name + ' · ' + n, c: col }]); });
        T((hi - lo).toFixed(j ? 2 : 3), { x: w - 2, y: cy + 4, 'text-anchor': 'end', class: j ? 'rgv' : 'muted' }, svg);
      });
    });
  });
  const fam = $('#abFam');
  table(fam, ['Attribute family', 'Style', 'Intent', 'Script'], AB_FAM.map(f => [f[0], fmt3(f[1]), fmt3(f[2]), fmt3(f[3])]).concat([['No persona (baseline)', 'n/a', 'n/a', fmt3(D.attributes.baselineScript)]]), [1, 2, 3]);
  const last = $$('tbody tr', fam).pop(); if (last) last.className = 'base';
})();
