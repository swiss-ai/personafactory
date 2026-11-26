/* ======================= QUALITY CONTROL: six inspections on the line ======================= */
// Numbers used here that are not in data.js:
const T6_CI = 0.6;                            // Table 6 caption: 95% intervals within ±0.6 points
const T6_DESIGN = { persona: 552654, sample: 44687, sampleConvs: 24570 }; // App. C: every user turn of model-persona conversations + a uniform random sample of the rest
// App. C, Strict intent label: four-way label on every user turn (MiniMax-M2.5, never sees the persona)
const STRICT = {
  n: 2371618, labels: [['Same request', 74.0], ['Added content', 18.5], ['Dropped content', 4.1], ['Scope change', 3.5]],
  audit: { n: 4903, k4: 0.59, k2: 0.63 },     // second external judge, Qwen3.6-35B-A3B
  core: 97.2,                                 // both judges: core request preserved, % of turns
  lenient: 91.5,                              // the Table 6 intent template passes this % of the turns the strict label flags
  human: { n: 100, kAnn: 0.60, kJudge: [0.60, 0.41], dis: 9, stricter: 8, core: 92 } // two blind annotators (same request vs drift)
};
const T9_LEN = { rows: [['Short', 1.00], ['Medium', 1.02], ['Long', 1.56]], rho: 0.22 }; // Table 9: length ratio by persona verbosity, per-item Spearman rho
// App. C, Reference rows for the judge-free metrics: same 800 seeds as Table 2, Gemma-4-31B, same order as D.representations.names
// [label, values, scale, dir]: dir -1 = lower means further from the seed
const C_REF = [['LaBSE similarity', [0.969, 0.948, 0.924, 0.899], 1, -1], ['Core vocabulary', [91.7, 86.7, 85.3, 81.5], 100, -1], ['Normalized edit distance', [0.109, 0.195, 0.221, 0.284], 1, 1], ['Punctuation register', [40.5, 41.0, 64.5, 75.8], 100, 1]];
const T13_INTENT = [[92, 92], [92.3, 92.5], [92.4, 92.6], [92.7, 93.5], [92.4, 92.6]];  // Table 13: intent % [flat, structured], same judge order as D.structVsFlat.judges
const CAP_DEC = { off: [62.0, 65.1], on: [54.9, 58.1] };  // App. D, marker cap: structured share of decisive verdicts, three judges, without / with the cap
const T16_WORST = [94.0, 94.6, 76.8];         // Table 16: PF preferred, worst case (every unparsed comparison given to the competitor)
const T17_RATIO = { 'Gemma-4-31B': ['17.90:1', '20.46:1', '4.83:1'], 'Ministral-3-14B': ['12.70:1', '13.55:1', '2.64:1'] }; // Table 17: win ratios
const PH_CUE = 1.4;                           // App. D: share of the 200,000 released PersonaHub personas that mention any writing cue (%)
const NATURAL = [7, 12];                      // App. D, Naturalness: external judges rate PF rewrites 7–12 points less natural than unconditioned ones
const MATCHED = [50.2, 51.3];                 // App. D, Matched content and length: structured share of pairwise style verdicts when content and length are equal
const CAP_STYLE = [7, 11];                    // App. D, marker cap: as natural as SynthPAI-form rewrites with 7–11 points more style
const AGREE_PRIMARY = [0.81, 0.93];           // App. D: item-level agreement of the four re-judges with the primary judge
// Fig. 21b, read from the figure (no values printed): PF preferred, % of decisive verdicts [point, lo, hi] per judge (MiniMax, Qwen3.6, Muse)
const F21B = [
  ['vs. PersonaHub form', [[65, 61, 68], [76, 73, 79], [72, 69, 75]]],
  ['vs. SynthPAI form', [[56, 53, 60], [59, 55, 62], [59, 55, 62]]],
  ['vs. real PersonaHub', [[75, 72, 78], [75, 72, 78], [78, 75, 81]]],
  ['vs. real SynthPAI', [[53, 50, 57], [47, 43, 50], [48, 45, 52]]]
];
// Fig. 22b, read from the figure: real WildChat users, % of first user turns, same order as D.calibration.features.
// Replaces the real-user column in data.js, which put the first two rates below the style-layer rates (the figure shows them just above).
const F22B_REAL = [32, 61, 2, 3, 0, 3, 1, 0];
// The Florida persona's style layer (released persona_bank 4cb592cc; the paper's Figure 2 persona)
const FIG2 = {
  flat: 'Uses all-lowercase messages with elliptical punctuation, drops articles, and lards sentences with Spanish loanwords or fragmented Spanish verbs (like ‘vamos we’re ready’) and almost always ends with a question or backchannel (‘right?’ or ‘no?’).',
  keys: [['Capitalization', 'first-word-only, no final period'], ['Abbreviations', '‘u’ for ‘you’, ‘r’ for ‘are’, ‘k’ for ‘okay’, sometimes ‘xq’ = ‘porque’'], ['Emoji', 'none'], ['Sign-off', '‘ok’ or ‘no?’ (with no logoff)'], ['Typos', 'occasional uncorrected typos (e.g. ‘supposted’ for ‘supposed’)']],
  marks: ['u', 'ur', 'no?']
};
// Human study (App. E). Pooled ratings and Part C rates live in D.human (Tables 18, 21).
const HS = { forms: 60, items: 40, perPart: 10, subs: 11, langs: 'nine', scripts: 'three', evals: 476 };  // App. E.1, E.4, E.6
const H_MEDIAN = 4.0;                                             // Table 18: median of every pooled dimension
// Table 20: Part C answers [human-like, AI-like]; skips left out. Shares: 59.1 (Table 20) and 71 (App. E.5: 29/41).
const T20_C = [{ label: 'Verified rewrites', parts: [26, 18], tot: 44, pct: ['59.1', '40.9'] }, { label: 'Real chat messages', parts: [29, 12], tot: 41, pct: ['71', null] }];
const T21_SET = { texts: 68, rewrites: 34, chat: 34, humanJudged: 85 }; // Table 21 caption, App. E.4
// App. E.7: example items from the English form, verbatim. Part B slashes mark line breaks.
const H_EX = {
  A: [
    { o: 'What role can technology play in facilitating Urdu language learning outside of South Asia?', r: 'hep i was wondering what role technology can play in helping people learn Urdu outside south asia' },
    { o: 'Write a Python program that takes two lists as input and determines if the first list is a subset of the second list. The program should output either “True” or “False”, depending on whether the first list is a subset of the second list. Ensure that your program uses appropriate variable names, follows PEP 8 guidelines for style, and includes relevant comments to explain the logic of the code.', r: 'can u write a python program that takes two lists as input and determines if the first list is a subset of the second list? it just needs to output “True” or “False” depending on whether it is a subset :) please make sure it uses appropriate variable names, follows pep 8 guidelines for style, and includes relevant comments to explain the logic of the code.' }
  ],
  B: [
    { d: 'Writes in all lowercase with minimal punctuation and occasional technical shorthand, reflecting a fast-paced digital native style.', m: 'can you do a deep dive review on that new ergo keyboard you used / focus on the features and how the comfort holds up during long sessions / need info on the adjustments and customization options and how they improve the experience / also talk about the build quality and form factor plus any extras like wrist rests or touchpads / give some examples of specific tasks you did and how it performed / make it detailed enough to show the strengths and limits so people know if it’s worth the investment' },
    { d: 'She types like she is writing a formal letter, using full capitalization and ending every sentence with a period, often adding polite pleasantries.', m: 'Hello. I have been thinking about how populations continue to grow even after birth rates slow down, and I came across the term demographic momentum. It would be lovely if you could explain how demographic momentum works in current global trends, especially with changes in technology and healthcare. Could you please provide some examples of where it is having a big impact? Thank you.' }
  ],
  D: [
    'can u check why this script is throwing a timeout error? looks like a network glitch machan',
    'bro, my bike brake is making noise again. is there any way to fix it with basic tools?'
  ]
};

(function quality(){
  const root = $('#evalLine'), piece = $('#qPiece'), rd = $('#qRead'), srcEl = $('#qSrc');
  const C_INT = 'var(--s3)', C_STY = 'var(--s1)', C_BOTH = 'var(--s2)';
  const AXES = [{ name: 'Intent kept', color: C_INT }, { name: 'Style adopted', color: C_STY }, { name: 'Both', color: C_BOTH }];
  { const k = $('#qKey'); k.append('Two verdicts per rewrite: '); el0('b', 'intent', k); k.append(' kept and '); el0('b', 'style', k); k.append(' adopted'); }

  let redraw = null;
  function el0(tag, txt, parent){ const n = document.createElement(tag); n.textContent = txt; parent.appendChild(n); return n; }
  const el = (tag, cls, txt, parent) => { const n = document.createElement(tag); if (cls) n.className = cls; if (txt != null) n.textContent = txt; if (parent) parent.appendChild(n); return n; };
  const head = (k, title, lead) => { el('div', 'pk', k ? 'Inspection ' + k : 'Sign-off', piece); el('h3', null, title, piece); if (lead) el('p', 'pl', lead, piece); };
  const spec = rows => { const d = el('dl', 'spec', null, piece); rows.forEach(([k, v]) => { const r = el('div', null, null, d); el('dt', null, k, r); el('dd', null, v, r); }); return d; };
  const big = items => { const g = el('div', 'bigs', null, piece); items.forEach(([v, l, c]) => { const d = el('div', null, null, g); if (c) d.style.borderTopColor = c; el('b', null, v, d); el('span', null, l, d); }); return g; };
  const finding = txt => { const f = el('div', 'qfind', null, piece); el('b', null, 'Finding', f); el('p', null, txt, f); return f; };
  const block = (title, src, parent = rd, approx) => {
    const b = el('div', 'rblock', null, parent); const h = el('div', 'rh', null, b); el('span', 'rt', title, h);
    const tags = el('span', 'rtags', null, h); if (approx) el('span', 'approx', 'read from figure', tags); if (src) el('span', 'src', src, tags);
    const c = el('div', 'chart', null, b); return c;
  };
  const cap = (txt, parent = rd) => el('p', 'cap', txt, parent);
  const tabs = (parent, items, cur, onChange, label) => {
    const g = el('div', 'seg', null, parent); g.setAttribute('role', 'group'); g.setAttribute('aria-label', label);
    items.forEach(([v, l]) => { const b = el('button', null, l, g); b.type = 'button'; b.dataset.v = v; b.setAttribute('aria-pressed', v === cur ? 'true' : 'false'); });
    g.addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; $$('button', g).forEach(x => x.setAttribute('aria-pressed', x === b ? 'true' : 'false')); onChange(b.dataset.v); });
    return g;
  };
  const fade = (nodes, animate, step = 170, start = 60) => { if (!animate || reduce) return; nodes.forEach((n, i) => { n.classList.add('pre'); setTimeout(() => n.classList.remove('pre'), start + step * i); }); };
  const sizeTxt = (t, s) => measure([t], s);

  /* ---------- charts drawn here ---------- */
  // Grouped horizontal bars: groups [[title|null, rows:[{label, values, bold?, tip?}]]], one bar per series
  function gbars(c, { groups, series, max = 100, fmt = v => fmt1(v) + '%', barH = 10, gap = 3, ticks = [0, 25, 50, 75, 100] }){
    const w = W(c), ns = series.length, gh = 22, groupH = ns * barH + (ns - 1) * gap, rowH = groupH + 12, top = 2, bottom = 22;
    const lw = Math.min(Math.ceil(measure(groups.flatMap(g => g[1].map(r => r.label)))) + 10, Math.floor(w * 0.36));
    const valW = Math.ceil(measure(['100.0%'], 11.5)) + 8;
    const x0 = lw + 6, x1 = w - valW, sx = v => x0 + (x1 - x0) * v / max;
    const h = top + groups.reduce((a, g) => a + (g[0] ? gh : 0) + g[1].length * rowH, 0) + bottom;
    const svg = svgFor(c, w, h);
    const gg = S('g', { class: 'grid' }, svg);
    ticks.forEach(t => { S('line', { x1: sx(t), x2: sx(t), y1: top, y2: h - bottom + 2 }, gg); T(t + '%', { x: sx(t), y: h - 6, 'text-anchor': 'middle', class: 'muted' }, svg); });
    let y = top;
    groups.forEach(([g, rows]) => {
      if (g){ T(g, { x: 0, y: y + 15, class: 'grp' }, svg); y += gh; }
      rows.forEach(r => {
        const by0 = y + (rowH - groupH) / 2;
        const lab = T(fit(r.label, lw - 4), { x: lw, y: by0 + groupH / 2 + 4, 'text-anchor': 'end' }, svg);
        if (r.bold) lab.setAttribute('font-weight', '600');
        r.values.forEach((v, j) => {
          const by = by0 + j * (barH + gap);
          S('path', { d: hbarPath(x0, by, sx(v) - x0, barH), fill: series[j].color }, svg);
          T(fmt(v), { x: sx(v) + 4, y: by + barH / 2 + 4, class: 'val', style: 'font-size:11.5px' }, svg);
          const tip = [{ v: fmt(v), l: series[j].name + ' · ' + r.label, c: series[j].color }]; if (r.tip) tip.push(...r.tip);
          bind(S('rect', { class: 'hit', x: x0, y: by - gap / 2, width: x1 - x0 + valW, height: barH + gap }, svg), tip);
        });
        y += rowH;
      });
    });
    return svg;
  }

  // Dot plot with optional 95% intervals. rows: [{label, pts:[{v, lo, hi, s}]}]; series: [{name, color}].
  // mode 'stack': each point on its own sub-line; mode 'pair': points share one line, joined by a rule.
  // A series with ring:true is drawn as an open ring on top, so it stays visible when two points coincide.
  // A point with hollow:true is drawn as an open circle (no interval reported).
  function dots(c, { rows, series, min, max, ticks, ref, refLabel, fmt = v => fmt1(v) + '%', mode = 'stack', sub = 13, labels = true, approx = false, labelFrac = 0.4 }){
    const w = W(c), ns = series.length;
    const lines = mode === 'stack' ? Math.max(...rows.map(r => r.pts.length)) : 1;
    const rowH = mode === 'stack' ? lines * sub + 14 : 28;
    const top = refLabel ? 20 : 4, bottom = 22;
    const lw = Math.min(Math.ceil(measure(rows.map(r => r.label))) + 10, Math.floor(w * labelFrac));
    const pad = labels ? Math.ceil(measure(['00.0%'], 11.5)) + 10 : 10;
    const x0 = lw + 8 + (mode === 'pair' && labels ? pad - 6 : 0), x1 = w - pad;
    const sx = v => x0 + (x1 - x0) * (Math.max(min, Math.min(max, v)) - min) / (max - min);
    const h = top + rows.length * rowH + bottom;
    const svg = svgFor(c, w, h);
    const gg = S('g', { class: 'grid' }, svg);
    (ticks || []).forEach(t => { S('line', { x1: sx(t), x2: sx(t), y1: top - 2, y2: h - bottom }, gg); T(String(t), { x: sx(t), y: h - 6, 'text-anchor': 'middle', class: 'muted' }, svg); });
    if (ref != null){ S('line', { class: 'ref', x1: sx(ref), x2: sx(ref), y1: top - 4, y2: h - bottom }, svg); if (refLabel) T(refLabel, { x: sx(ref), y: 12, 'text-anchor': 'middle', class: 'muted' }, svg); }
    const pre = approx ? '≈' : '';
    rows.forEach((r, i) => {
      const y0 = top + i * rowH;
      const cy0 = y0 + rowH / 2;
      const lab = T(fit(r.label, lw - 4), { x: lw, y: cy0 + 4, 'text-anchor': 'end' }, svg);
      if (lab.textContent !== r.label) S('title', {}, lab).textContent = r.label;
      if (i) S('line', { x1: 0, x2: w, y1: y0, y2: y0, stroke: 'var(--rule)', 'stroke-width': 1 }, svg);
      if (mode === 'pair'){
        const vs = r.pts.map(p => p.v);
        S('line', { x1: sx(Math.min(...vs)), x2: sx(Math.max(...vs)), y1: cy0, y2: cy0, stroke: 'var(--rule-2)', 'stroke-width': 2 }, svg);
      }
      const order = r.pts.map((p, k) => k).sort((a, b) => (series[r.pts[a].s ?? a].ring ? 1 : 0) - (series[r.pts[b].s ?? b].ring ? 1 : 0));
      order.forEach(k => {
        const p = r.pts[k], s = series[p.s ?? k];
        const cy = mode === 'stack' ? y0 + 7 + k * sub + sub / 2 : cy0;
        const rad = mode === 'stack' && lines > 1 ? 4.5 : 5.5;
        if (p.lo != null) S('line', { x1: sx(p.lo), x2: sx(p.hi), y1: cy, y2: cy, stroke: s.color, 'stroke-width': 2, 'stroke-linecap': 'round' }, svg);
        if (s.ring || p.hollow) S('circle', { cx: sx(p.v), cy, r: s.ring ? rad + 1.5 : rad, fill: 'none', stroke: s.color, 'stroke-width': 2.2 }, svg);
        else S('circle', { cx: sx(p.v), cy, r: rad, fill: s.color, stroke: 'var(--surface)', 'stroke-width': 1.5 }, svg);
      });
      r.pts.forEach((p, k) => {
        const s = series[p.s ?? k];
        const cy = mode === 'stack' ? y0 + 7 + k * sub + sub / 2 : cy0;
        if (labels){
          const txt = pre + fmt(p.v);
          if (mode === 'pair'){
            const o = r.pts[1 - k];
            const right = !o || p.v > o.v || (p.v === o.v && k === 1);
            T(txt, { x: right ? sx(p.v) + 11 : sx(p.v) - 11, y: cy + 4, 'text-anchor': right ? 'start' : 'end', class: 'val', style: 'font-size:11.5px' }, svg);
          } else {
            const xr = sx(p.hi ?? p.v) + (p.hollow ? 10 : 6);
            T(txt, { x: xr, y: cy + 4, class: 'val', style: 'font-size:11.5px' }, svg);
          }
        }
        const tip = [{ c: s.color, v: pre + fmt(p.v), l: s.name + ' · ' + r.label + (p.lo != null ? ` (95% CI ${fmt1(p.lo)}–${fmt1(p.hi)})` : '') }];
        if (p.tip) tip.push(...p.tip);
        bind(S('rect', { class: 'hit', x: x0 - 6, y: mode === 'stack' ? cy - sub / 2 : y0, width: x1 - x0 + 12, height: mode === 'stack' ? sub : rowH }, svg), tip);
      });
    });
    return svg;
  }

  /* ---------- 1: corpus-scale LLM judge ---------- */
  let cjView = 'rates';
  const STRICT_SEGS = [{ color: 'var(--s3)' }, { color: 'var(--s1)' }, { color: 'var(--s2)' }, { color: 'var(--faint)' }];
  function s1(animate){
    head(1, 'Corpus-scale LLM judge', 'An out-of-family judge gives sampled user turns two separate pass/fail verdicts, and every user turn of the release a stricter four-way intent label.');
    const sp = spec([
      ['Sample', `All ${fmt0(T6_DESIGN.persona)} user turns of conversations with a model persona, plus ${fmt0(T6_DESIGN.sample)} turns from ${fmt0(T6_DESIGN.sampleConvs)} randomly sampled other conversations. Rates are weighted to the corpus.`],
      ['Inspector', 'MiniMax-M2.5, a reasoning model that is not one of the production rewriters'],
      ['Intent passes', 'Same request, no added task or invented content, same language. Cross-lingual turns are judged against their translation.'],
      ['Style passes', 'Takes on the persona’s tone, vocabulary, register or typing habits. Only a generic rewrite fails.'],
      ['Strict label', 'The same judge compares each user turn with its seed turn, without seeing the persona, and labels it same request, added content, dropped content or scope change. Translated turns are compared with the English source.']
    ]);
    const all = D.corpusJudge[0];
    const bg = big([[fmt1(all.intent) + '%', 'intent kept', C_INT], [fmt1(all.style) + '%', 'style adopted', C_STY], [fmt1(all.both) + '%', 'pass both', C_BOTH]]);
    const cg = D.corpusJudge.find(r => r.slice === 'Gemma-4-31B'), cm = D.corpusJudge.find(r => r.slice === 'Ministral-3-14B');
    const fd = finding(`Gemma-4-31B, the larger rewriter, passes both checks ${fmt1(cg.both - cm.both)} points more often than Ministral-3-14B (${fmt1(cg.both)}% vs ${fmt1(cm.both)}%). Under the strict label, ${fmt1(STRICT.labels[0][1])}% of turns keep the exact request and ${fmt1(STRICT.core)}% keep the core request.`);
    fade([...sp.children, bg, fd], animate);
    const tb = tabs(rd, [['rates', 'Pass rates'], ['strict', 'Strict intent label']], cjView, v => { cjView = v; draw(); }, 'View');
    const body = el('div', 'rbody', null, rd);
    const draw = () => {
      body.replaceChildren();
      if (cjView === 'rates'){
        const c = block('Pass rates by subset', 'Table 6', body);
        const rows = D.corpusJudge;
        const row = r => ({ label: r.slice, bold: r.slice === 'All turns', values: [r.intent, r.style, r.both], tip: [{ l: fmt0(r.n) + ' judged turns' }] });
        const by = names => rows.filter(r => names.includes(r.slice)).map(row);
        c.appendChild(legend(AXES));
        gbars(el('div', null, null, c), { groups: [[null, by(['All turns'])], ['By rewriter', by(['Gemma-4-31B', 'Ministral-3-14B'])], ['By seed set', by(['WildChat', 'UltraChat', 'Nemotron'])]], series: AXES });
        el('div', 'unit', '% of user turns, weighted to the corpus. 95% intervals within ±' + T6_CI + ' points.', c);
        cap('Open-ended UltraChat leaves more room for style (76.0%) than Nemotron’s denser, often technical instructions (65.2%). Real WildChat prompts are restyled least often (60.5% style).', body);
        const det = el('details', 'tbl', null, body); el('summary', null, 'Data table', det); const tw = el('div', 'tblwrap', null, det);
        table(tw, ['Subset', 'Judged turns', 'Intent %', 'Style %', 'Both %'], rows.map(r => [r.slice, fmt0(r.n), fmt1(r.intent), fmt1(r.style), fmt1(r.both)]), [1, 2, 3, 4]);
      } else {
        const H2 = STRICT.human;
        const c = block('Strict intent label, every user turn', 'App. C', body);
        hbars(c, { rows: STRICT.labels.map(([l, v], i) => ({ label: l, values: [v], colors: [STRICT_SEGS[i].color], bold: i === 0 })), series: [{ name: '% of user turns', color: STRICT_SEGS[0].color }], max: 100, ticks: [0, 25, 50, 75, 100], barH: 16, unit: `% of ${fmt0(STRICT.n)} labeled user turns. Core request kept in ${fmt1(STRICT.core)}% under both judges.` });
        const c2 = block('Agreement on the strict label', 'App. C', body);
        const qTip = () => [{ l: `Qwen3.6-35B-A3B on ${fmt0(STRICT.audit.n)} turns` }], aTip = () => [{ l: `${H2.n} turns, same request vs drift` }];
        hbars(c2, { rows: [
          { label: 'Second judge, four-way', values: [STRICT.audit.k4], tip: qTip },
          { label: 'Second judge, two-way', values: [STRICT.audit.k2], tip: qTip },
          { label: 'Judge vs one annotator', values: [H2.kJudge[0]], tip: aTip },
          { label: 'Judge vs the other', values: [H2.kJudge[1]], tip: aTip },
          { label: 'Annotator vs annotator', values: [H2.kAnn], tip: aTip }
        ], series: [{ name: 'Cohen’s κ', color: 'var(--s3)' }], max: 1, ticks: [0, 0.25, 0.5, 0.75, 1], fmt: fmt2, barH: 14, unit: `Cohen’s κ. Two-way: same request vs drift. Second judge: ${fmt0(STRICT.audit.n)} turns. Two annotators: ${H2.n} turns, blind to the persona, the rewriter and the judge’s label.` });
        cap(`In the ${H2.dis} turns where the two annotators agree with each other but not with the judge, the judge is the stricter side ${H2.stricter} times, so the drift rates are, if anything, conservative. The annotators find the core request kept in ${H2.core} of ${H2.n} turns. The lenient intent check passes ${fmt1(STRICT.lenient)}% of the turns this label flags. Every released turn carries the label. We recommend training on the strict subset, the conversations in which every user turn keeps the same request; retraining on it changes no downstream result.`, body);
      }
    };
    fade([tb, body], animate, 200, 300);
    // Source: paper Section 5, App. C, Table 6, Strict intent label, Human check of the strict judge
    return draw;
  }

  /* ---------- 2: judge-free metrics ---------- */
  function s2(animate){
    head(2, 'Judge-free metrics', 'Deterministic checks over the full corpus. No model is involved.');
    const sp = spec([
      ['Sample', 'Every rewritten user turn in the corpus, against its original'],
      ['Inspector', 'None. String, entity and embedding checks.'],
      ['Depth', 'How much of the surface changed, and whether the meaning survived (LaBSE similarity)'],
      ['Retention', 'Numbers, code, identifiers and quoted literals still intact'],
      ['Adherence', 'Each marker checked against the persona’s tier, e.g. emoji: none, rare, frequent or kaomoji'],
      ['Reference', 'The same metrics on 800 seeds rewritten with no persona, the PersonaHub form, the SynthPAI form and ours']
    ]);
    const jf = n => D.judgeFree.find(m => m.name.startsWith(n)).v;
    const fd = finding(`Rewrites change much of the surface (edit distance ${fmt3(jf('Normalized edit'))}) yet keep most core vocabulary (${fmt1(jf('Core'))}%) and the meaning (LaBSE ${fmt3(jf('LaBSE'))}). Emoji rules are met in ${fmt1(jf('Emoji'))}% of turns, punctuation and capitalization rules only moderately.`);
    fade([...sp.children, fd], animate);
    const grid = el('div', 'qgrid', null, rd);
    const groups = ['Transformation depth', 'Constraint retention', 'Style adherence'];
    const blocks = groups.map(g => {
      const c = block(g, 'Table 9', grid); c.classList.add('meters');
      D.judgeFree.filter(m => m.grp === g).forEach(m => {
        const d = el('div', 'meter', null, c);
        el('span', null, m.name, d);
        el('span', 'mv', m.scale === 1 ? fmt3(m.v) : fmt1(m.v) + '%', d);
        const bar = el('span', 'bar', null, d); el('b', null, null, bar).style.width = (m.v / m.scale * 100) + '%';
      });
      el('div', 'unit', g === 'Transformation depth' ? 'Distances and similarity in [0, 1]; retention in %' : g === 'Constraint retention' ? '% of turns with the item intact' : '% of turns meeting the persona’s tier', c.parentNode);
      return c.parentNode;
    });
    const lc = block('Length ratio by persona verbosity', 'Table 9', grid);
    const lcap = cap('Messages grow for personas who write long ones but barely shrink for those who write short ones.');
    const rc = block('Each step up in style information', 'App. C', rd);
    const rcap = cap('Richer style formats move the text further from the seed and follow the persona’s punctuation more closely. Ours changes the text most and adheres best.');
    const draw = () => {
      hbars(lc, { rows: T9_LEN.rows.map(r => ({ label: r[0], values: [r[1]] })), series: [{ name: 'length ratio', color: 'var(--s1)' }], max: 2, fmt: v => v.toFixed(2) + '×', ticks: [0, 0.5, 1, 1.5, 2], barH: 14, unit: 'Rewrite length ÷ original, median. Per-item ρ = ' + T9_LEN.rho + '.' });
      rowHeat(rc, C_REF);
    };
    fade([...blocks, lc.parentNode, lcap, rc.parentNode, rcap], animate, 200, 300);
    // Source: paper Section 5, App. C, Table 9, Reference rows for the judge-free metrics
    return draw;
  }

  // Heat table colored within each row (rows have different scales). rows: [[label, values, scale, dir]]
  function rowHeat(c, rows){
    const w = W(c), narrow = w < 520;
    const cols = narrow ? ['No\npersona', 'Persona-\nHub', 'Synth-\nPAI', 'Persona-\nFactory'] : ['No persona', 'PersonaHub\nform', 'SynthPAI\nform', 'PersonaFactory'];
    const labs = rows.map(r => (narrow ? r[0].replace('Normalized edit distance', 'Edit distance').replace(' register', '') : r[0]) + (r[2] === 100 ? ' (%)' : ''));
    const lw = Math.min(Math.ceil(measure(labs)) + 12, Math.floor(w * 0.38)), headH = 34, cellH = 28;
    const cw = (w - lw) / cols.length, h = headH + rows.length * cellH + 2;
    const svg = svgFor(c, w, h);
    cols.forEach((t, j) => { const ln = t.split('\n'); ln.forEach((s, k) => T(s, { x: lw + cw * j + cw / 2, y: headH - 8 - (ln.length - 1 - k) * 13, 'text-anchor': 'middle', class: 'muted' }, svg)); });
    rows.forEach(([lab, vals, scale, dir], i) => {
      const y = headH + i * cellH, lo = Math.min(...vals), hi = Math.max(...vals);
      const rl = T(fit(labs[i], lw - 10), { x: lw - 8, y: y + cellH / 2 + 4, 'text-anchor': 'end' }, svg);
      if (rl.textContent !== labs[i]) S('title', {}, rl).textContent = labs[i];
      vals.forEach((v, j) => {
        const p = (dir < 0 ? hi - v : v - lo) / (hi - lo || 1), x = lw + cw * j;
        const txt = scale === 1 ? fmt3(v) : fmt1(v);
        const r = S('rect', { x: x + 1, y: y + 1, width: cw - 2, height: cellH - 2, rx: 3, fill: `color-mix(in oklab, var(--seq-hi) ${Math.round(15 + p * 85)}%, var(--seq-lo))` }, svg);
        T(txt, { x: x + cw / 2, y: y + cellH / 2 + 4, 'text-anchor': 'middle', class: p > 0.5 ? 'on' : 'val' }, svg);
        bind(r, [{ v: txt + (scale === 1 ? '' : '%'), l: lab + ' · ' + D.representations.names[j] }]);
      });
    });
    el('div', 'unit', 'Same 800 seeds, persona and rewriter (Gemma-4-31B). Stronger color = further from the seed, or closer to the persona’s punctuation; scaled within each row.', c);
  }

  /* ---------- 3: structured vs flat ---------- */
  function s3(animate){
    head(3, 'Structured vs flat style', 'Same rewriter, persona and token budget. Only the style representation changes.');
    const sp = spec([
      ['Sample', '553 real user messages, 518 after the judge-passing stage'],
      ['Inspector', 'MiniMax-M2.5, A/B order randomized. Re-judged by DeepSeek-V4-Flash, Qwen3.5-397B-A17B and Qwen3.6-35B-A3B.'],
      ['Pass', 'The judge picks the rewrite that better matches the persona’s style. Intent is checked per rewrite.']
    ]);
    const wp = el('div', 'wp', null, piece);
    const wh = el('div', 'wph', null, wp); el('span', null, 'The two style formats', wh); el('span', 'src', 'Figure 2 persona', wh);
    const fl = el('div', 'rep flat', null, wp);
    const fh = el('div', 'reph', null, fl); el('b', null, 'Flat', fh); el('span', null, 'one or two free-text style sentences', fh);
    el('p', 'flattxt', FIG2.flat, fl);
    const st = el('div', 'rep struct', null, wp);
    const sh = el('div', 'reph', null, st); el('b', null, 'Structured', sh); el('span', null, 'per-axis style keys', sh);
    const kv = el('dl', 'keys', null, st); FIG2.keys.forEach(([k, v]) => { el('dt', null, k, kv); el('dd', null, v, kv); });
    const mk = el('p', 'marks', 'Keyed markers in the Florida rewrite: ', wp); FIG2.marks.forEach((m, i) => { if (i) mk.appendChild(document.createTextNode(' · ')); el('mark', null, m, mk); });
    const fd = finding('Every judge prefers the structured keys. The pipeline judge picks them in 60% of pairs and the flat description in 33%. Intent and length do not change.');
    fade([...sp.children, fl, st, mk, fd], animate, 190);
    const SV = D.structVsFlat;
    const short0 = j => j.replace('MiniMax-M2.5 (original)', 'MiniMax-M2.5, original').replace('MiniMax-M2.5 (larger budget)', 'MiniMax-M2.5, larger budget');
    const c1 = block('Which rewrite matches the persona better?', 'Tables 1, 13');
    const c2 = block('Structured share of decisive verdicts', 'Fig. 20');
    const c3 = block('Intent kept, measured per rewrite', 'Table 13');
    const cp = cap('Mean rewrite length: ' + fmt0(SV.table1.len[0]) + ' characters structured, ' + fmt0(SV.table1.len[1]) + ' flat. The external judges agree on direction: clearly for both Qwen models, narrowly for DeepSeek-V4-Flash, whose interval touches parity. With at most two chat markers per turn, three judges still prefer the structured layer, by a smaller margin (' + CAP_DEC.on[0] + '–' + CAP_DEC.on[1] + '% of decisive verdicts, against ' + fmt1(CAP_DEC.off[0]) + '–' + CAP_DEC.off[1] + '% without the cap).');
    const draw = () => {
      const nar = W(c1) < 480;
      const short = j => nar ? j.replace('MiniMax-M2.5 (original)', 'MiniMax, original').replace('MiniMax-M2.5 (larger budget)', 'MiniMax, rerun').replace(/^(Qwen3\.\d-\d+B).*/, '$1') : short0(j);
      c1.replaceChildren(legend([{ name: 'Structured preferred', color: 'var(--s1)' }, { name: 'Tie', color: 'var(--rule-2)' }, { name: 'Flat preferred', color: 'var(--s2)' }]));
      stack100(el('div', null, null, c1), { rows: SV.judges.map(j => ({ label: short(j.judge), parts: [j.s, j.t, j.f] })), segs: [{ name: 'Structured preferred', color: 'var(--s1)', textOn: true }, { name: 'Tie', color: 'var(--rule-2)' }, { name: 'Flat preferred', color: 'var(--s2)', textOn: true }], labelMax: 210, rowH: 30, barH: 20 });
      el('div', 'unit', '% of parsed verdicts', c1);
      c2.replaceChildren(legend([{ name: 'Pipeline judge', color: 'var(--s1)', kind: 'dot' }, { name: 'External judge', color: 'var(--s3)', kind: 'dot' }]));
      dots(el('div', null, null, c2), { rows: SV.judges.map(j => ({ label: nar ? short(j.judge) : `${short(j.judge)} (n=${j.n})`, pts: [j.n === 433 ? { v: j.dec, hollow: true, s: 0, tip: [{ l: j.judge + ', ' + j.n + ' parsed verdicts. No interval reported.' }] } : { v: j.dec, lo: j.lo, hi: j.hi, s: j.kind === 'pipeline' ? 0 : 1, tip: [{ l: j.judge + ', ' + j.n + ' parsed verdicts' }] }] })), series: [{ name: 'Pipeline judge', color: 'var(--s1)' }, { name: 'External judge', color: 'var(--s3)' }], min: 40, max: 80, ticks: [40, 50, 60, 70, 80], ref: 50, refLabel: 'parity' });
      el('div', 'unit', '% of decisive verdicts (ties excluded), 95% Wilson intervals. Open dot: original pass, no interval reported.', c2);
      const lg3 = legend([{ name: 'Flat', color: 'transparent', kind: 'dot' }, { name: 'Structured', color: 'var(--s1)', kind: 'dot' }]); lg3.querySelector('i').style.boxShadow = 'inset 0 0 0 2px var(--s2)'; c3.replaceChildren(lg3);
      dots(el('div', null, null, c3), { rows: SV.judges.map((j, i) => ({ label: short(j.judge), pts: [{ v: T13_INTENT[i][0], s: 0 }, { v: T13_INTENT[i][1], s: 1 }] })), series: [{ name: 'Flat', color: 'var(--s2)', ring: true }, { name: 'Structured', color: 'var(--s1)' }], min: 80, max: 100, ticks: [80, 85, 90, 95, 100], mode: 'pair', fmt: v => (Number.isInteger(v) ? String(v) : fmt1(v)) + '%' });
      el('div', 'unit', '% of rewrites that keep the request. Ring: flat. Dot: structured.', c3);
    };
    fade([c1.parentNode, c2.parentNode, c3.parentNode, cp], animate, 220, 400);
    // Source: paper Section 5, App. C, D (marker cap), Tables 1, 13, Fig. 20
    return draw;
  }

  /* ---------- 4: other persona formats ---------- */
  const R = D.representations;
  const FMT_COL = ['var(--rule-2)', 'var(--q1)', 'var(--q2)', 'var(--q4)'];
  let repTab = 'dose', repSub = 'all', pfView = 'main';
  function s4(animate){
    head(4, 'Other persona formats', 'The same profile is serialized four ways and used to rewrite the same prompt.');
    const sp = spec([
      ['Sample', '800 paired prompts from the corpus with their matched personas, stratified by persona set and seed source'],
      ['Held fixed', 'Persona content, Gemma-4-31B rewriter, decoding, prompt scaffold'],
      ['Inspector', 'MiniMax-M2.5: style and intent verdicts, plus a pairwise style preference in random order']
    ]);
    const lad = el('ol', 'fmts', null, piece);
    const what = ['Baseline: the rewriter gets no persona.', `One third-person sentence. Only ${PH_CUE}% of real PersonaHub personas mention any writing cue.`, 'Attribute block plus a free-text writing style with a verbatim example. No per-axis keys.', 'Background and style layers, with per-axis style keys.'];
    R.names.forEach((n, i) => {
      const li = el('li', null, null, lad);
      const t = el('div', 'ft', null, li); el('b', null, n, t); el('span', null, R.words[i] + ' words', t);
      const bar = el('span', 'fbar', null, li); const f = el('i', null, null, bar); f.style.width = Math.max(1, R.words[i] / 280 * 100) + '%'; f.style.background = FMT_COL[i];
      el('span', 'fw', what[i], li);
    });
    const fd = finding('Style adoption rises with how much a format says about typing, from 3.1% to 69.2%. Intent drops about four points, almost all of it on cross-lingual prompts.');
    fade([...sp.children, ...lad.children, fd], animate, 160);
    const tb = tabs(rd, [['dose', 'Dose-response'], ['enc', 'What each carries'], ['pf', 'PF preferred'], ['neutral', 'Format-neutral'], ['cost', 'Adherence & cost']], repTab, v => { repTab = v; draw(); }, 'View');
    const body = el('div', 'rbody', null, rd);
    const draw = () => {
      body.replaceChildren();
      if (repTab === 'dose'){
        const sub = tabs(body, [['all', 'Intent: all'], ['en', 'English'], ['x', 'Cross-lingual']], repSub, v => { repSub = v; draw(); }, 'Intent subset'); sub.classList.add('sub');
        const c = block('Style and intent by representation', 'Table 2 · Fig. 23', body);
        drawDose(c);
        cap(repSub === 'x' ? 'On cross-lingual prompts, intent falls to 89.2% with the richest format. Most of the intent cost is here.' : repSub === 'en' ? 'In English, intent barely moves: 99.3% with PersonaFactory.' : 'Style rises at every step. The PersonaHub form changes the text about as much as the others, yet lifts style only from 3.1% to 5.5%.', body);
      } else if (repTab === 'enc'){
        const c = block('Share of profiles whose attribute reaches the rewriter', 'Table 15', body);
        const narrow = W(c) < 520;
        heat(c, { rows: R.encodes.rows, cols: narrow ? ['No\npersona', 'Persona-\nHub', 'Synth-\nPAI', 'Persona-\nFactory'] : ['No persona', 'PersonaHub\nform', 'SynthPAI\nform', 'PersonaFactory'], m: R.encodes.vals, min: 0, max: 100, fmt: v => String(v), cellH: 28, labelMax: 120 });
        el('div', 'unit', '% of N = 555 profiles. Stronger color = more profiles carry it.', c);
        cap('Quirks and a reference pool reach the rewriter only with PersonaFactory (100% against 2% or less). SynthPAI carries style axes for 55% of profiles.', body);
      } else if (repTab === 'pf'){
        const sub = tabs(body, [['main', 'Main (95% CI)'], ['rewriter', 'By rewriter'], ['judge', 'By judge']], pfView, v => { pfView = v; draw(); }, 'Robustness view'); sub.classList.add('sub');
        const opp = ['No persona', 'PersonaHub form', 'SynthPAI form'];
        if (pfView === 'main'){
          const c = block('PersonaFactory rewrite preferred, by opponent', 'Tables 2, 16', body);
          c.appendChild(legend([{ name: 'PF preferred, 95% CI', color: 'var(--s1)', kind: 'dot' }, { name: 'Worst case', color: 'var(--faint)', kind: 'dot' }]));
          dots(el('div', null, null, c), { rows: opp.map((o, i) => ({ label: 'vs. ' + o, pts: [{ v: R.pfPreferred[i], lo: R.pfCI[i][0], hi: R.pfCI[i][1], s: 0, tip: [{ l: 'win ratio ' + R.winRatio[i] }] }, { v: T16_WORST[i], s: 1, tip: [{ l: 'every unparsed comparison given to the competitor' }] }] })), series: [{ name: 'PF preferred', color: 'var(--s1)' }, { name: 'Worst case', color: 'var(--faint)' }], min: 50, max: 100, ticks: [50, 60, 70, 80, 90, 100], ref: 50, refLabel: 'parity', sub: 15 });
          el('div', 'unit', '% of pairs where the judge prefers the PersonaFactory rewrite', c);
          cap('Win ratios 17.90:1, 20.46:1 and 4.83:1. Worst case: every unparsed comparison counted for the competitor. The SynthPAI form also carries less style information. Rendered with the same content and length, the structured form ties on style (' + MATCHED[0] + '–' + MATCHED[1] + '% of pairs) but keeps the request more often and reads more naturally.', body);
        } else if (pfView === 'rewriter'){
          const c = block('PF preferred with each rewriter', 'Table 17', body);
          const keys = Object.keys(R.robust.byRewriter);
          hbars(c, { rows: opp.map((o, i) => ({ label: 'vs. ' + o, values: keys.map(k => R.robust.byRewriter[k][i]), tip: j => [{ l: 'win ratio ' + T17_RATIO[keys[j]][i] }] })), series: keys.map((k, i) => ({ name: k + ' rewriter', color: ['var(--s1)', 'var(--s2)'][i] })), max: 100, ticks: [0, 25, 50, 75, 100], ref: { v: 50 }, barH: 12, gapIn: 3, unit: '% of pairs, MiniMax-M2.5 judge' });
          cap('The ranking holds with Ministral-3-14B. Against the SynthPAI form the margin narrows from 4.83:1 to 2.64:1.', body);
        } else {
          const c = block('PF preferred under four judges', 'Table 17', body);
          const keys = Object.keys(R.robust.byJudge);
          heat(c, { rows: keys, cols: W(c) < 520 ? ['vs. no\npersona', 'vs. Persona-\nHub', 'vs. Synth-\nPAI'] : ['vs. no persona', 'vs. PersonaHub form', 'vs. SynthPAI form'], m: keys.map(k => R.robust.byJudge[k]), min: 50, max: 100, fmt: v => fmt1(v), cellH: 32, labelMax: 130, tipLabel: (r, col) => r + ' judge · ' + col.replace('\n', ' ') });
          el('div', 'unit', '% of pairs, 200-item subset, Gemma-4-31B rewriter. Stronger color = stronger preference.', c);
          cap(`Every judge prefers PersonaFactory against every format. Rates span fifteen points across judges. Item-level agreement with the primary judge: ${AGREE_PRIMARY[0]}–${AGREE_PRIMARY[1]}.`, body);
        }
      } else if (repTab === 'neutral'){
        const N = R.neutral; const keys = Object.keys(N.vals);
        const c = block('Style adoption against a format-neutral reference', 'Fig. 21a', body, true);
        hbars(c, { rows: N.judges.map((j, i) => ({ label: j, values: keys.map(k => N.vals[k][i]) })), series: keys.map((k, i) => ({ name: k, color: FMT_COL[i + 1] })), max: 100, ticks: [0, 25, 50, 75, 100], fmt: v => '≈' + v + '%', barH: 12, gapIn: 4, unit: '% of rewrites. Judges see only style attribute values, no example phrasing.' });
        const c2 = block('PF preferred, including real personas', 'Fig. 21b', body, true);
        const JS = [{ name: 'MiniMax-M2.5', color: 'var(--s1)' }, { name: 'Qwen3.6-35B', color: 'var(--s2)' }, { name: 'Muse-Glimmer-30B', color: 'var(--s3)' }];
        c2.appendChild(legend(JS.map(j => ({ name: j.name, color: j.color, kind: 'dot' }))));
        dots(el('div', null, null, c2), { rows: F21B.map(([l, p]) => ({ label: l, pts: p.map((q, k) => ({ v: q[0], lo: q[1], hi: q[2], s: k })) })), series: JS, min: 40, max: 85, ticks: [40, 50, 60, 70, 80], ref: 50, refLabel: 'parity', fmt: v => v + '%', approx: true, labels: false });
        el('div', 'unit', '% of decisive verdicts, 95% Wilson intervals. Real-persona pairs are judged reference-free.', c2);
        cap('PersonaFactory still leads when judges see only the style attribute values. Real SynthPAI profiles, hand-written for 300 English Reddit users, do about as well.', body);
      } else {
        const c = block('Style adherence, judge-free', 'Table 16', body);
        const cols = W(c) < 520 ? ['No\npersona', 'Persona-\nHub', 'Synth-\nPAI', 'Persona-\nFactory'] : ['No persona', 'PersonaHub\nform', 'SynthPAI\nform', 'PersonaFactory'];
        const A = R.adherence;
        heat(c, { rows: Object.keys(A), cols, m: Object.values(A), min: 0.3, max: 1, fmt: fmt3, cellH: 28, labelMax: 130 });
        el('div', 'unit', 'Share of rewrites matching the persona’s tier, in [0, 1]. Color scale 0.3 to 1.', c);
        const c2 = block('Cost: content kept intact', 'Table 16', body);
        const K = R.cost; const rows = Object.keys(K);
        const kept = rows.filter(r => !/sanity/.test(r));
        heat(c2, { rows: kept.map(r => r.replace('Quoted literals intact', 'Quoted literals')), cols, m: kept.map(r => K[r]), min: 0.85, max: 1, fmt: fmt3, cellH: 28, labelMax: 130 });
        const san = K['Assistant sanity (%)'];
        el('div', 'unit', `Share of rewrites with the item intact, in [0, 1]. Color scale 0.85 to 1. Assistant sanity stays at ${fmt1(Math.min(...san))}–${fmt1(Math.max(...san))}%.`, c2);
        cap(`Punctuation adherence rises from 0.405 to 0.757; entity retention falls by four points. External judges rate PersonaFactory rewrites ${NATURAL[0]} to ${NATURAL[1]} points less natural. With at most two chat markers per turn, they read as naturally as SynthPAI-form rewrites and keep ${CAP_STYLE[0]} to ${CAP_STYLE[1]} points more style.`, body);
      }
    };
    function drawDose(c){
      c.replaceChildren(legend([{ name: 'Style adopted', color: C_STY }, { name: 'Intent kept' + (repSub === 'en' ? ' (English)' : repSub === 'x' ? ' (cross-lingual)' : ''), color: C_INT }]));
      const box = el('div', null, null, c);
      const w = W(box), left = 38, right = 12, top = 26;
      const colW = (w - left - right) / 4;
      const two = measure(R.names, 11.5) + 8 > colW;
      const bottom = two ? 56 : 42, h = 250;
      const svg = svgFor(box, w, h);
      const sx = i => left + colW * (i + 0.5), sy = v => top + (h - top - bottom) * (1 - v / 100);
      const g = S('g', { class: 'grid' }, svg);
      [0, 25, 50, 75, 100].forEach(t => { S('line', { x1: left, x2: w - right, y1: sy(t), y2: sy(t) }, g); T(t + '%', { x: left - 6, y: sy(t) + 4, 'text-anchor': 'end', class: 'muted' }, svg); });
      R.names.forEach((n, i) => {
        const parts = two ? (n === 'PersonaFactory' ? ['Persona-', 'Factory'] : n.split(' ')) : [n];
        parts.forEach((p, k) => T(p, { x: sx(i), y: h - bottom + 16 + k * 13, 'text-anchor': 'middle', style: 'font-size:11.5px' }, svg));
        T(R.words[i] + ' words', { x: sx(i), y: h - bottom + 16 + parts.length * 13, 'text-anchor': 'middle', class: 'muted' }, svg);
      });
      const intent = repSub === 'all' ? R.intent : repSub === 'en' ? R.intentEN : R.intentX;
      const L = [{ vals: R.style, ci: R.styleCI, color: C_STY, lab: 'side' }, { vals: intent, ci: repSub === 'all' ? R.intentCI : null, color: C_INT, lab: 'above' }];
      L.forEach(l => {
        S('path', { d: l.vals.map((v, i) => (i ? 'L' : 'M') + sx(i) + ',' + sy(v)).join(''), fill: 'none', stroke: l.color, 'stroke-width': 2, 'stroke-linejoin': 'round' }, svg);
        l.vals.forEach((v, i) => {
          if (l.ci) S('line', { x1: sx(i), x2: sx(i), y1: sy(l.ci[i][0]), y2: sy(l.ci[i][1]), stroke: l.color, 'stroke-width': 2 }, svg);
          S('circle', { cx: sx(i), cy: sy(v), r: 5, fill: l.color, stroke: 'var(--surface)', 'stroke-width': 2 }, svg);
          if (l.lab === 'above') T(fmt1(v), { x: sx(i), y: sy(v) - 10, 'text-anchor': 'middle', class: 'val', style: 'font-size:11.5px' }, svg);
          else T(fmt1(v), { x: sx(i) - 9, y: sy(v) - 5, 'text-anchor': 'end', class: 'val', style: 'font-size:11.5px' }, svg);
        });
      });
      R.names.forEach((n, i) => bind(S('rect', { class: 'hit', x: sx(i) - colW / 2, y: top, width: colW, height: h - top - bottom }, svg), [{ v: n, l: R.words[i] + ' words' }, { c: C_STY, v: fmt1(R.style[i]) + '%', l: 'style adopted' }, { c: C_INT, v: fmt1(intent[i]) + '%', l: 'intent kept' + (repSub === 'en' ? ', English' : repSub === 'x' ? ', cross-lingual' : '') }]));
      el('div', 'unit', '% of rewrites, N = 800 paired items' + (repSub === 'all' ? ', 95% Wilson intervals' : ''), c);
    }
    fade([tb, body], animate, 220, 500);
    // Source: paper Section 5, App. D, Tables 2, 15–17, Figs. 21, 23
    return draw;
  }

  /* ---------- 5: calibration against real users ---------- */
  const CAL = D.calibration;
  let calJ = 0;
  function s5(animate){
    head(5, 'Calibration against real users', 'Each rewrite is paired with the real WildChat message it came from.');
    const sp = spec([
      ['Sample', '2,140 Nemotron-Personas and PersonaHub records converted to our format; the 182 English WildChat seeds that pass in all three arms'],
      ['Arms', 'A: raw source record · B: converted background, no style layer · C: background with the style layer'],
      ['Inspectors', 'MiniMax-M2.5, Qwen3.6-35B-A3B, Muse-Glimmer-30B'],
      ['Question', '“Which reads more like something a real person typed?” Asked in both orders: a win needs the same choice twice, a flip is a draw.']
    ]);
    const fd = finding('With the style layer, every judge prefers the rewrite to the real message. The rewrites overuse greetings, slang and emoji, so a win mostly means more casual typing.');
    fade([...sp.children, fd], animate);
    const tb = tabs(rd, CAL.judges.map((j, i) => [String(i), j]), String(calJ), v => { calJ = +v; draw(); }, 'Judge');
    const c1 = block('“Which reads more like a real person?”', 'Table 14');
    const c2 = block('Typing features vs real users', 'Fig. 22b', rd, true);
    const cp = cap('Lowercase starts and dropped final punctuation match real-user rates. Greetings, chat slang, emoji, ellipses and repeated punctuation appear several times more often than real users type them. A cap of two chat markers per turn addresses this; exact calibration is future work.');
    const ARM = { 'A: raw source record': 'Real vs A, raw record', 'B: background, no style layer': 'Real vs B, no style', 'C: background + style layer': 'Real vs C, + style' };
    const draw = () => {
      c1.replaceChildren(legend([{ name: 'Real message wins', color: 'var(--faint)' }, { name: 'Draw (flips with order)', color: 'var(--rule-2)' }, { name: 'Rewrite wins', color: 'var(--s1)' }]));
      stack100(el('div', null, null, c1), { rows: Object.entries(CAL.arms).map(([k, v]) => ({ label: ARM[k] || k, parts: v[calJ] })), segs: [{ name: 'Real message wins', color: 'var(--faint)', textOn: true }, { name: 'Draw', color: 'var(--rule-2)' }, { name: 'Rewrite wins', color: 'var(--s1)', textOn: true }], labelMax: 180, ref: 0.5 });
      el('div', 'unit', '% of 182 seeds, ' + CAL.judges[calJ] + ' judge. Dashed line: half.', c1);
      const lg = legend([{ name: 'Real WildChat users', color: 'transparent', kind: 'dot' }, { name: 'C: background + style layer', color: 'var(--s1)', kind: 'dot' }]); lg.querySelector('i').style.boxShadow = 'inset 0 0 0 2px var(--ink-2)'; c2.replaceChildren(lg);
      const nar = W(c2) < 480;
      dots(el('div', null, null, c2), { rows: CAL.features.map((f, i) => ({ label: nar ? f[0].replace(/ \(.*\)/, '').replace('thanks / please at end', 'thanks / please') : f[0], pts: [{ v: F22B_REAL[i], s: 0, tip: [{ l: f[0] }] }, { v: f[1], s: 1 }] })), series: [{ name: 'Real WildChat users', color: 'var(--ink-2)', ring: true }, { name: 'Background + style', color: 'var(--s1)' }], min: 0, max: 70, ticks: [0, 20, 40, 60], mode: 'pair', fmt: v => (v < 1 ? '<1' : String(v)) + '%' });
      el('div', 'unit', '% of first user turns, same 182 English seeds. Ring: real users. Dot: rewrite with the style layer.', c2);
    };
    fade([tb, c1.parentNode, c2.parentNode, cp], animate, 220, 400);
    // Source: paper App. D, Table 14, Fig. 22
    return draw;
  }

  /* ---------- 6: judge robustness ---------- */
  const J = D.judges, JS4 = ['Gemma', 'GLM', 'Ministral', 'MiniMax'];
  let agV = 'style', agM = 'raw';
  function s6(animate){
    head(6, 'Judge robustness', 'Do the verdicts depend on which judge gives them?');
    const sp = spec([
      ['Sample', '100 stratified persona rewrites, spanning the 16 single-attribute conditions'],
      ['Inspectors', 'Gemma-4-31B, GLM-4.7-Flash, Ministral-3-14B, MiniMax-M2.5, each giving a style and an intent verdict'],
      ['Measured', 'Pass rate per judge, raw agreement per pair, then Cohen’s κ and Gwet’s AC1 to correct for chance']
    ]);
    const fd = finding('Judges differ in how strict they are but agree on direction. MiniMax-M2.5 is the strictest on style and is not a production rewriter, so it serves as the pipeline judge. Every pair that includes it reaches κ\u00a0≥\u00a00.32 on style.');
    fade([...sp.children, fd], animate);
    const c1 = block('Judge severity', 'Table 10');
    const ctl = el('div', 'rtools', null, rd);
    tabs(ctl, [['style', 'Style verdict'], ['intent', 'Intent verdict']], agV, v => { agV = v; drawAg(); }, 'Verdict');
    tabs(ctl, [['raw', 'Raw'], ['kappa', 'Cohen’s κ'], ['ac1', 'Gwet’s AC1']], agM, v => { agM = v; drawAg(); }, 'Measure');
    const c2 = block('Pairwise agreement', 'Tables 11, 12');
    const cp = cap('');
    const drawAg = () => {
      let m;
      if (agM === 'raw') m = agV === 'style' ? J.agreeStyle : J.agreeIntent;
      else { m = JS4.map(() => JS4.map(() => null)); J.kappa.forEach(k => { const a = JS4.indexOf(k[0]), b = JS4.indexOf(k[1]); const v = agM === 'kappa' ? (agV === 'style' ? k[2] : k[4]) : (agV === 'style' ? k[3] : k[5]); m[a][b] = v; m[b][a] = v; }); }
      const nm = agM === 'raw' ? 'raw agreement' : agM === 'kappa' ? 'Cohen’s κ' : 'Gwet’s AC1';
      heat(c2, { rows: JS4, cols: JS4, m, min: agM === 'kappa' ? 0 : 0.5, max: 1, fmt: v => agM === 'raw' ? v.toFixed(3) : v.toFixed(2), cellH: 32, labelMax: 90, tipLabel: (r, c) => `${r} – ${c} · ${nm} (${agV})` });
      el('div', 'unit', nm[0].toUpperCase() + nm.slice(1) + ' on the ' + agV + ' verdict, ' + (agV === 'style' ? 99 : 100) + ' items. Stronger color = more agreement.', c2);
      $$('text', c2).forEach(t => { if (t.textContent === 'n/a') t.textContent = '–'; });
      cp.textContent = agM === 'raw' ? 'Share of identical verdicts. High pass rates inflate raw agreement.' : agM === 'kappa' ? 'Every pair with MiniMax reaches κ ≥ 0.32 on style and ≥ 0.22 on intent. GLM–Ministral style κ is 0.06 because both pass over 92% of items.' : 'AC1 corrects for the prevalence effect of lenient judges. With it, GLM–Ministral rises to 0.85 on style.';
    };
    const draw = () => {
      hbars(c1, { rows: J.names.map((n, i) => ({ label: n, values: [J.meanStyle[i], J.meanIntent[i]] })), series: [{ name: 'Mean style pass', color: C_STY }, { name: 'Mean intent pass', color: C_INT }], max: 1, ticks: [0, 0.25, 0.5, 0.75, 1], fmt: fmt3, barH: 12, gapIn: 4, unit: 'Share of passing verdicts on the same 100 rewrites' });
      drawAg();
    };
    fade([c1.parentNode, ctl, c2.parentNode, cp], animate, 220, 400);
    // Source: paper Section 5, App. C, Tables 10–12
    return draw;
  }

  /* ---------- 7: QC sheet ---------- */
  function s7(animate){
    head(0, 'QC sheet', 'One line per inspection. Open a line to see the evidence.');
    const sp = spec([
      ['Pipeline judge', 'MiniMax-M2.5, strictest on style and not a production rewriter'],
      ['External judges', 'DeepSeek-V4-Flash, Qwen3.5-397B-A17B, Qwen3.6-35B-A3B, Muse-Glimmer-30B'],
      ['Cross-check', 'Gemma-4-31B, GLM-4.7-Flash, Ministral-3-14B'],
      ['No judge', 'Deterministic surface, entity and marker checks'],
      ['People', 'AI experts rating samples in languages they know well; two blind annotators checking the strict intent label']
    ]);
    const fd = finding('Judges and human raters agree that rewrites keep the request and sound like the persona. A strict label finds the exact request in about three of four turns and the core request in nearly all. Calibration is still open: rewrites use chat markers more often than real users do.');
    fade([...sp.children, fd], animate);
    const all = D.corpusJudge[0], SV = D.structVsFlat.table1, JF = n => D.judgeFree.find(m => m.name.startsWith(n)).v;
    const ROWS = [
      ['LLM judge', [[fmt1(all.intent) + '%', 'up'], [' · '], [fmt1(all.style) + '%', 'up']], 'intent kept · style adopted, weighted to the corpus; ' + fmt1(STRICT.labels[0][1]) + '% keep the exact request under the strict label', 'Table 6'],
      ['Judge-free', [[fmt1(JF('Numbers')) + '%', 'up']], 'numbers intact; all entities kept in ' + fmt1(JF('All entities')) + '% of turns', 'Table 9'],
      ['Structured vs flat', [[String(SV.prefAll[0]), 'up'], [' : '], [String(SV.prefAll[1]), 'from']], '% of pairs preferring structured vs flat; intent equal at ' + SV.intent[0] + '%', 'Tables 1, 13'],
      ['Other formats', [[fmt1(R.pfPreferred[2]) + '%', 'up']], 'PersonaFactory preferred over the SynthPAI form; ' + fmt1(R.pfPreferred[0]) + '–' + fmt1(R.pfPreferred[1]) + '% over the others', 'Tables 2, 17'],
      ['Real users', [[fmt1(CAL.arms['C: background + style layer'][0][2]) + '%', 'up']], 'rewrite with the style layer judged more real than the real message (MiniMax-M2.5)', 'Table 14'],
      ['Judge robustness', [['κ ≥ 0.32']], 'style agreement of every judge with the pipeline judge', 'Table 12'],
      ['Human raters', [[fmt1(D.human.turing[0].human) + '%', 'up']], 'of rewrites taken for human-written in a blind test; meaning, style and plausibility get a median of 4 out of 5', 'Tables 18, 21']
    ];
    const ul = el('ol', 'sheet', null, rd);
    ROWS.forEach((r, i) => {
      const at = i < 6 ? i : 7;   // the human row opens the last stage
      const li = el('li', null, null, ul);
      const b = el('button', null, null, li); b.type = 'button';
      el('span', 'sn', String(i + 1), b);
      const t = el('span', 'st', null, b); el('b', null, r[0], t); el('span', 'src', r[3], t);
      // quality wins in green; the comparison side of a pair in grey
      const sv = el('span', 'sv', null, b);
      r[1].forEach(([txt, cls]) => cls ? el('span', cls, txt, sv) : sv.append(txt));
      el('span', 'sd', r[2], b);
      b.setAttribute('aria-label', `Open inspection ${i + 1}, ${r[0]}: ${sv.textContent}, ${r[2]}`);
      b.addEventListener('click', () => { line.stop(); if (at === 7) hSub = 'all'; line.show(at, false); });
    });
    fade([...ul.children], animate, 140, 300);
    // Source: paper Section 5, App. C, D, E
    return () => {};
  }

  /* ---------- 8: human raters (App. E, interim) ---------- */
  const H = D.human;
  const P = { A: H.pooled[0], B: H.pooled[1], D: H.pooled[2], C: H.pooled[3] };
  const C_MEAN = 'var(--s1)', C_MED = 'var(--s3)', C_LOW = 'var(--rule-2)', C_HUM = 'var(--s2)', C_ACC = 'var(--s1)', C_AI = 'var(--s3)';
  const hi3 = p => 100 - p[4];   // share rated 3 to 5 (complement of the 1-2 share)
  const llm = () => H.turing.slice(1).map(t => t.human);
  const itemSel = { A: 0, B: 0, D: 0 };
  let hSub = 'all';
  const boldLabel = (c, prefix) => $$('svg text', c).forEach(t => { if (t.textContent.startsWith(prefix)) t.setAttribute('font-weight', '600'); });
  const pfind = (txt, parent) => { const f = el('div', 'qfind', null, parent); el('b', null, 'Finding', f); el('p', null, txt, f); return f; };
  const hbigs = items => { const g = el('div', 'bigs', null, rd); items.forEach(([v, l, c]) => { const d = el('div', null, null, g); if (c) d.style.borderTopColor = c; el('b', null, v, d); el('span', null, l, d); }); return g; };
  const unit = (c, txt) => el('div', 'unit', txt, c);

  // the form item as raters see it
  function hform(parent, title){ const f = el('div', 'hform', null, parent); el('div', 'hfh', title, f); return el('div', 'hfb', null, f); }
  function hscale(parent, lo, hi, mean, animate, label = 'mean rating'){
    const s = el('div', 'hscale', null, parent);
    s.setAttribute('role', 'img'); s.setAttribute('aria-label', `Scale 1 (${lo}) to 5 (${hi}); ${label} ${fmt2(mean)}`);
    const row = el('div', 'sq', null, s); [1, 2, 3, 4, 5].forEach(k => el('span', null, String(k), row));
    const pin = el('div', 'pin', null, s); el('i', null, null, pin); el('span', null, label + ' ' + fmt2(mean), pin);
    const pos = v => `${((v - 0.5) / 5) * 100}%`;
    if (animate && !reduce){ pin.style.left = pos(1); pin.style.opacity = 0; requestAnimationFrame(() => requestAnimationFrame(() => { pin.style.left = pos(mean); pin.style.opacity = 1; })); }
    else pin.style.left = pos(mean);
    const an = el('div', 'anch', null, s); el('span', null, '1 · ' + lo, an); el('span', null, '5 · ' + hi, an);
    return s;
  }
  function itemTabs(fb, part, n, draw){
    if (n < 2) return;
    const t = tabs(fb, Array.from({ length: n }, (_, i) => [String(i), 'Example ' + (i + 1)]), String(itemSel[part]), v => { itemSel[part] = +v; draw(); }, 'Example item');
    t.classList.add('sub');
  }
  function hq(fb, txt){ const d = el('p', 'hq', null, fb); el('b', null, 'Question ', d); d.append(txt); return d; }
  function htb(fb, label, txt, cls){ const d = el('div', 'htb ' + cls, null, fb); el('div', 'tl', label, d); const p = el('div', 'tt', null, d); if (Array.isArray(txt)) txt.forEach(t => el('span', 'ln', t, p)); else p.textContent = txt; return d; }

  // readout charts
  function partBigs(p){ return hbigs([['4 of 5', 'median rating'], [fmt2(p[2]), `mean of ${p[1]} ratings`], [pct(hi3(p)), 'rated 3 or higher']]); }
  function pooledChart(c, cur){
    const rows = [['A · Meaning', 'A'], ['B · Style', 'B'], ['D · Plausibility', 'D'], ['C · Confidence', 'C']].map(([l, k]) => {
      const p = P[k];
      return { label: l, v: p[2], v2: H_MEDIAN, color: C_MEAN, color2: C_MED,
        tip: [{ l: p[0] }, { c: C_MEAN, v: fmt2(p[2]), l: `mean of ${p[1]} ratings` }, { c: C_MED, v: fmt1(H_MEDIAN), l: 'median' }] };
    });
    forest(c, { rows, min: 1, max: 5, ticks: [1, 2, 3, 4, 5], rowH: 30, labelMax: 150 });
    if (cur) boldLabel(c, cur + ' ·');
    c.insertBefore(legend([{ name: 'Mean', color: C_MEAN, kind: 'dot' }, { name: 'Median', color: C_MED, kind: 'dot' }]), c.firstChild);
    unit(c, 'Pooled ratings on the 1–5 scale. The current part is in bold.');
  }
  function shareChart(c, cur){
    const narrow = W(c) < 420;
    const names = { A: 'Meaning', B: 'Style', D: 'Plausibility' };
    const rows = ['A', 'B', 'D'].map(k => ({ label: narrow ? names[k] : `${k} · ${names[k]}`, parts: [hi3(P[k]), P[k][4]] }));
    const segs = [{ name: 'Rated 3 to 5', color: C_MEAN, textOn: true }, { name: 'Rated 1 or 2', color: C_LOW }];
    const svg = stack100(c, { rows, segs, fmt: v => fmt1(v), labelMax: 150 });
    c.insertBefore(legend(segs.map(s => ({ name: s.name, color: s.color }))), svg);
    if (cur) boldLabel(c, narrow ? names[cur] : cur + ' ·');
    unit(c, 'Share of pooled ratings, in %.' + (cur ? ' The current part is in bold.' : ''));
  }
  function humanChart(c){
    const rows = H.turing.map((r, i) => ({ label: r.judge, values: [r.human], bold: i === 0, tip: () => [{ l: `95% interval ${fmt1(r.hlo)}–${fmt1(r.hhi)}%` }] }));
    hbars(c, { rows, series: [{ name: 'Rewrites taken for human-written', color: C_HUM }], max: 100, ticks: [0, 25, 50, 75, 100], barH: 16, labelMax: 150,
      unit: 'Share of verified corpus rewrites labeled human-written.' });
  }
  function countChart(c){
    const segs = [{ name: 'Human-like', color: C_HUM }, { name: 'AI-like', color: C_AI }];
    const w = W(c), barH = 26, rowH = 36, top = 4, h = top + T20_C.length * rowH;
    const lw = Math.min(Math.ceil(measure(T20_C.map(r => r.label))) + 10, Math.floor(w * 0.38));
    const svg = svgFor(c, w, h);
    T20_C.forEach((r, i) => {
      const y = top + i * rowH + (rowH - barH) / 2;
      T(fit(r.label, lw - 8), { x: lw - 8, y: y + barH / 2 + 4, 'text-anchor': 'end' }, svg);
      const sx = v => (w - lw - 2) * v / r.tot;
      let x = lw;
      r.parts.forEach((v, j) => {
        const len = sx(v), p = r.pct[j];
        const rect = S('rect', { x: x + (j ? 1 : 0), y, width: Math.max(0, len - 1), height: barH, rx: 3, fill: segs[j].color }, svg);
        const lab = p ? `${v} · ${p}%` : String(v);
        if (len > measure([lab]) + 14) T(lab, { x: x + len / 2, y: y + barH / 2 + 4, 'text-anchor': 'middle', class: 'on' }, svg);
        bind(rect, [{ c: segs[j].color, v: String(v), l: segs[j].name + (p ? ` (${p}%)` : '') }, { l: `of ${r.tot} answered judgments · ${r.label.toLowerCase()}` }]);
        x += len;
      });
    });
    c.insertBefore(legend(segs.map(s => ({ name: s.name, color: s.color }))), svg);
    unit(c, `Rater answers, skips left out: ${T20_C[0].tot} on texts verified as corpus rewrites, ${T20_C[1].tot} on WildChat user messages.`);
  }
  function judgeChart(c){
    const rows = H.turing, w = W(c);
    const lw = Math.min(Math.ceil(measure(rows.map(r => r.judge))) + 18, Math.floor(w * 0.4));
    const valW = Math.ceil(measure(['00.0'], 11.5)) + 18;
    const rowH = 38, sep = 8, top = 8, bottom = 24, min = 40, max = 100;
    const x0 = lw + 8, x1 = w - valW - 6, sx = v => x0 + (x1 - x0) * (v - min) / (max - min);
    const h = top + rows.length * rowH + sep + bottom;
    const svg = svgFor(c, w, h);
    const gg = S('g', { class: 'grid' }, svg);
    ((x1 - x0) / 6 < 40 ? [40, 60, 80, 100] : [40, 50, 60, 70, 80, 90, 100]).forEach(t => { S('line', { x1: sx(t), x2: sx(t), y1: top - 2, y2: h - bottom }, gg); T(t + '%', { x: sx(t), y: h - 6, 'text-anchor': 'middle', class: 'muted' }, svg); });
    S('line', { class: 'ref', x1: sx(50), x2: sx(50), y1: top - 4, y2: h - bottom }, svg);
    rows.forEach((r, i) => {
      const y0 = top + i * rowH + (i ? sep : 0), cy = y0 + rowH / 2;
      if (i === 1) S('line', { x1: 0, x2: w, y1: y0 - sep / 2, y2: y0 - sep / 2, stroke: 'var(--rule-2)', 'stroke-width': 1 }, svg);
      const lab = T(fit(r.judge, lw - 4), { x: lw, y: cy + 4, 'text-anchor': 'end' }, svg);
      if (i === 0) lab.setAttribute('font-weight', '600');
      [[r.human, r.hlo, r.hhi, C_HUM, -7], [r.acc, r.alo, r.ahi, C_ACC, 7]].forEach(([v, lo, hi, col, dy]) => {
        S('line', { x1: sx(lo), x2: sx(hi), y1: cy + dy, y2: cy + dy, stroke: col, 'stroke-width': 2, 'stroke-linecap': 'round' }, svg);
        S('circle', { cx: sx(v), cy: cy + dy, r: 4.5, fill: col, stroke: 'var(--surface)', 'stroke-width': 1.5 }, svg);
        S('circle', { cx: w - valW + 6, cy: cy + dy, r: 3, fill: col }, svg);
        T(fmt1(v), { x: w - 2, y: cy + dy + 4, 'text-anchor': 'end', class: 'val', style: 'font-size:11.5px' }, svg);
      });
      bind(S('rect', { class: 'hit', x: 0, y: y0, width: w, height: rowH }, svg), [
        { l: r.judge + (i ? ' · 3 answers per text' : ` · ${T21_SET.humanJudged} answered judgments`) },
        { c: C_HUM, v: fmt1(r.human) + '%', l: `rewrites taken for human-written [${fmt1(r.hlo)}, ${fmt1(r.hhi)}]` },
        { c: C_ACC, v: fmt1(r.acc) + '%', l: `accuracy [${fmt1(r.alo)}, ${fmt1(r.ahi)}]` }]);
    });
    const lg = legend([{ name: 'Rewrites taken for human', color: C_HUM, kind: 'dot' }, { name: 'Accuracy', color: C_ACC, kind: 'dot' }, { name: 'Chance, 50%', color: 'var(--faint)', kind: 'line' }]);
    lg.lastChild.firstChild.classList.add('dash'); c.insertBefore(lg, svg);
    unit(c, `${T21_SET.texts} texts: ${T21_SET.rewrites} verified rewrites, ${T21_SET.chat} chat-log messages. Lines: 95% intervals.`);
  }

  // one pane per sub-tab: fills the left box and the readout, returns the chart draw
  const HPANE = {
    all(box, animate){
      el('p', 'pl', 'Each form has four parts. Each part is scored on its own, and there is no combined score.', box);
      const sp = el('dl', 'spec', null, box);
      [['Forms', `${HS.forms} languages, one form each, up to ${HS.items} items (${HS.perPart} per part)`],
       ['Raters', 'AI experts who volunteer, unpaid, and rate only languages they know well'],
       ['Scales', '1 to 5 for meaning, style and plausibility, plus a confidence rating in Part C'],
       ['So far', `${HS.subs} submissions in ${HS.langs} languages and ${HS.scripts} scripts, ${HS.evals} item evaluations. Collection is still running.`]].forEach(([k, v]) => { const r = el('div', null, null, sp); el('dt', null, k, r); el('dd', null, v, r); });
      const fd = pfind(`Raters give meaning, style and plausibility a median of 4 out of 5. In the blind test they thought a person wrote ${Math.round(H.turing[0].human)}% of the rewrites.`, box);
      fade([...sp.children, fd], animate);
      const bg = hbigs([['4 of 5', 'median for meaning, style and plausibility', C_MEAN], [fmt1(H.turing[0].human) + '%', 'of rewrites taken for human-written by raters', C_HUM], [Math.round(Math.min(...llm())) + '–' + Math.round(Math.max(...llm())) + '%', 'taken for human-written by four LLM judges']]);
      const c1 = block('How the ratings fall');
      const c2 = block('Rewrites taken for human-written');
      fade([bg, c1.parentNode, c2.parentNode], animate, 200, 300);
      return () => { shareChart(c1); humanChart(c2); };
    },
    A(box, animate){
      el('p', 'pl', 'An original message next to its persona rewrite. Does the rewrite still ask for the same thing?', box);
      const fb = hform(box, 'Part A: meaning preservation');
      const body = el('div', 'hitem', null, fb);
      const draw = () => { body.replaceChildren(); const x = H_EX.A[itemSel.A]; htb(body, 'Original', x.o, 'orig'); htb(body, 'Rewrite', x.r, 'rew'); };
      itemTabs(fb, 'A', H_EX.A.length, draw); fb.appendChild(body); draw();
      hq(fb, 'Does the rewrite preserve the meaning of the original?');
      hscale(fb, 'meaning changed', 'meaning fully preserved', P.A[2], animate);
      const fd = pfind(`Raters find that rewrites keep the request, with a median of 4 of 5 and a mean of ${fmt2(P.A[2])}. Meaning gets the highest mean of the three rated parts.`, box);
      fade([fb.parentNode, fd], animate);
      return partRead('A', animate);
    },
    B(box, animate){
      el('p', 'pl', 'A persona’s style description from the bank next to a message rewritten for that persona. Does the message match, without turning into a caricature?', box);
      const fb = hform(box, 'Part B: style fidelity');
      const body = el('div', 'hitem', null, fb);
      const draw = () => { body.replaceChildren(); const x = H_EX.B[itemSel.B]; htb(body, 'Style description', x.d, 'desc'); htb(body, 'Message', x.m.split(' / '), 'rew'); };
      itemTabs(fb, 'B', H_EX.B.length, draw); fb.appendChild(body); draw();
      hq(fb, 'How well does the message match the described style, without caricature?');
      hscale(fb, 'poor match / stereotyped', 'faithful and plausible', P.B[2], animate);
      const fd = pfind(`Raters find that messages follow the style they were given, with a median of 4 of 5 over ${P.B[1]} ratings.`, box);
      fade([fb.parentNode, fd], animate);
      return partRead('B', animate);
    },
    C(box, animate){
      el('p', 'pl', 'Raters see only the text and decide whether a person or a model wrote it. Half the messages on each form are corpus rewrites; the other half come from a real chat log.', box);
      const fb = hform(box, 'Part C: human or model');
      const om = el('div', 'homit', null, fb);
      el('b', null, 'No examples shown. ', om); om.append('Part C items stay hidden while the study is running.');
      hq(fb, 'Was this text written by a real human being?');
      const ol = el('ol', 'hopts', null, fb);
      [['Yes', 'this text appears as authentic and readable as typical messages written by real users.'], ['No', 'parts of this text seem unusual, such as odd wording or synthetic text patterns, suggesting it might be AI-generated.'], ['Skip this item.', '']].forEach(([a, b]) => { const li = el('li', null, null, ol); el('b', null, a + (b ? ': ' : ''), li); if (b) li.append(b); });
      el('p', 'hq sm', 'Follow-up: How confident are you?', fb);
      hscale(fb, 'guessing', 'very confident', P.C[2], animate, 'mean confidence');
      const fd = pfind(`Raters took ${fmt1(H.turing[0].human)}% of the rewrites for human-written and identified the source correctly ${fmt1(H.turing[0].acc)}% of the time, only slightly better than chance. Real chat messages were taken for human-written in ${T20_C[1].pct[0]}% of answers. The LLM judges took even more rewrites for human-written.`, box);
      fade([fb.parentNode, fd], animate);
      const bg = hbigs([[fmt1(H.turing[0].human) + '%', 'of rewrites taken for human-written', C_HUM], [fmt1(H.turing[0].acc) + '%', 'rater accuracy (chance is 50%)', C_ACC], [fmt1(Math.min(...llm())) + '–' + fmt1(Math.max(...llm())) + '%', 'taken for human-written by LLM judges']]);
      const c1 = block('Rater answers: rewrites and real messages');
      const c2 = block('People vs four LLM judges');
      fade([bg, c1.parentNode, c2.parentNode], animate, 200, 300);
      return () => { countChart(c1); judgeChart(c2); };
    },
    D(box, animate){
      el('p', 'pl', 'Would a real speaker of this language variety write this message?', box);
      const fb = hform(box, 'Part D: linguistic plausibility');
      const body = el('div', 'hitem', null, fb);
      const draw = () => { body.replaceChildren(); htb(body, 'Message', H_EX.D[itemSel.D], 'rew'); };
      itemTabs(fb, 'D', H_EX.D.length, draw); fb.appendChild(body); draw();
      hq(fb, 'Is this plausible as something a real speaker would write?');
      hscale(fb, 'implausible / caricature', 'fully plausible', P.D[2], animate);
      const rp = el('div', 'hrep', null, fb); el('span', 'tl', 'Report', rp); ['No issue', 'Personal information', 'Offensive content'].forEach(t => el('span', 'opt', t, rp));
      const fd = pfind(`Native and fluent speakers find the messages plausible, with a median of 4 of 5 over ${P.D[1]} ratings.`, box);
      fade([fb.parentNode, fd], animate);
      return partRead('D', animate);
    }
  };
  function partRead(k, animate){
    const bg = partBigs(P[k]);
    const c1 = block('All four parts');
    const c2 = block('How the ratings fall');
    fade([bg, c1.parentNode, c2.parentNode], animate, 200, 300);
    return () => { pooledChart(c1, k); shareChart(c2, k); };
  }
  function s8(animate){
    head('by people', 'Human raters', `People who work in AI read corpus samples in languages they know well and rate them. These are interim numbers from ${HS.subs} submissions.`);
    const tb = tabs(piece, [['all', 'Overview'], ['A', 'Meaning'], ['B', 'Style'], ['C', 'Human or model'], ['D', 'Plausibility']], hSub, v => { hSub = v; pane(false); drawPane(); }, 'Study part');
    tb.classList.add('hsub');
    const box = el('div', 'hpane', null, piece);
    let drawPane = () => {};
    const pane = anim => { box.replaceChildren(); rd.replaceChildren(); drawPane = HPANE[hSub](box, anim); };
    pane(animate);
    // Source: paper Section 5, App. E, Tables 18, 20, 21, E.5, E.6
    return () => drawPane();
  }

  const STAGES = [s1, s2, s3, s4, s5, s6, s7, s8];
  function render(s, animate){
    piece.replaceChildren(); rd.replaceChildren();
    root.dataset.stage = s;
    root.classList.toggle('running', !!animate);
    redraw = STAGES[s](animate);
    redraw();
  }
  // At rest, and on "Show all", the line shows the QC sheet; the human stage is the last one on the run.
  const SHEET = 6, HUMANS = 7, HASH = '#eval-humans';
  root.addEventListener('click', e => { if (e.target.closest('[data-all]')){ e.stopPropagation(); line.stop(); line.show(SHEET, false); } }, true);
  const atHumans = () => location.hash === HASH;
  if (atHumans()) hSub = 'all';
  const line = lineCtl(root, { count: STAGES.length, start: atHumans() ? HUMANS : SHEET, render, dur: s => s === SHEET ? 1800 : s === 3 ? 3000 : s === HUMANS ? 2600 : 2500, onStop: () => root.classList.remove('running') });
  addEventListener('hashchange', () => { if (atHumans()){ line.stop(); hSub = 'all'; line.show(HUMANS, false); } });
  reg(() => { if (redraw) redraw(); });
})();
