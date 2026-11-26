/* ======================= COMPARE: other persona datasets, and the style extension ======================= */
// Every number on this station. Paper sources are kept here only; the page does not show them.
const CMP = {
  // Section 3 (743,010 personas; 177 countries), Section 6 / Table 3 (1,237,976 conversations), Abstract (85 languages)
  pf: { personas: 743010, countries: 177, convs: 1237976, langs: 85 },
  // Appendix D, Design: "across all 200,000 released PersonaHub personas, only 1.4% mention any writing cue at all"
  ph: { released: 200000, cue: 1.4 },
  // Appendix D, format-neutral paragraph: "Real SynthPAI profiles, whose hand-written style descriptions cover 300 English-speaking Reddit users"
  sp: { profiles: 300 },
  // Table 2 (800 paired prompts; only the profile format changes); CIs from Table 16. intentX: Table 16, cross-lingual intent.
  fmt: {
    names: ['No persona', 'PersonaHub form', 'SynthPAI form', 'PersonaFactory'],
    words: [0, 13, 83, 280],
    style: [3.1, 5.5, 43.5, 69.2], styleCI: [[2.1, 4.6], [4.1, 7.3], [40.1, 47.0], [66.0, 72.3]],
    intent: [99.8, 99.8, 98.0, 96.1], intentCI: [[99.1, 99.9], [99.1, 99.9], [96.8, 98.8], [94.6, 97.3]],
    intentX: [99.6, 99.2, 94.0, 89.2],
    pfPref: [94.4, 94.9, 81.3], pfCI: [[92.5, 95.8], [93.1, 96.2], [78.4, 83.9]]
  },
  // Appendix D, "Matched content and length": SynthPAI-style free text with the same facts and length; structured form keeps the
  // request +5.0 points [2.1, 7.6] (Gemma-4-31B), pairwise style share 50.2 to 51.3% (on par), reads more naturally (+5.6 / +6.0)
  match: { request: 5.0 },
  // Appendix D, "Quirk probability and marker cap": cap of 2 realized chat markers per turn; capped rewrites as natural as the
  // SynthPAI format while adopting 7 to 11 points more style; corpus generated without the explicit cap, 97.3% of user turns
  // contain at most two of the six markers; cap becomes the default in the released code
  cap: { gain: [7, 11], corpusAtMost: 97.3 },  // "two" markers and "six" marker kinds are written out in the copy
  // Table 15: % of N = 555 profiles whose attribute survives into the block the rewriter sees; columns PersonaHub form, SynthPAI form, PersonaFactory
  enc: { n: 555, rows: [['Age', [0, 100, 100]], ['Location', [16, 100, 100]], ['Occupation', [68, 100, 100]], ['Language', [8, 26, 99]], ['Style axes', [0, 55, 100]], ['Quirks', [0, 1, 100]], ['Reference pool', [2, 1, 100]]] },
  // Appendix D, Calibration against real users: 2,140 converted records, 182 English WildChat seeds passing in all three arms
  conv: { records: 2140, seeds: 182 },
  // Table 14: [real message wins, draw, rewrite wins] per judge, % of seeds
  arms: {
    judges: ['MiniMax-M2.5', 'Qwen3.6-35B-A3B', 'Muse-Glimmer-30B'],
    A: [[44.1, 27.1, 28.8], [53.3, 36.3, 10.4], [68.7, 22.0, 9.3]],
    B: [[43.4, 22.9, 33.7], [47.8, 34.6, 17.6], [65.4, 20.3, 14.3]],
    C: [[17.6, 14.8, 67.6], [16.5, 41.8, 41.8], [27.5, 21.4, 51.1]]
  },
  // Appendix G.2, "Conversations without a user persona" + Table 31. null = n/a or reference.
  reply: {
    n: 1000, turns: 2570, fallback: 35,
    rows: [ // [label, long label, sanity pass, style adopted, same content, median words]
      ['Source replies', 'Source replies, unchanged', null, 17.4, null, 344],
      ['Regenerated, no style', 'Regenerated, no style', 82.2, 25.7, 42.4, 583],
      ['Regenerated with style', 'Regenerated with style', 77.4, 79.5, 25.4, 371],
      ['Source restyled', 'Source replies restyled', null, 57.5, 93.0, 417]
    ]
  },
  // Same paragraph: 200 single-turn conversations with a checkable system constraint; compliance %
  sys: { n: 200, none: 86, below: 58, last: 66 }
};

(function compare(){
  const root = $('#cmpLine'), L = $('#cLeft'), R = $('#cRight');
  if (!root) return;
  const C_STY = 'var(--s1)', C_INT = 'var(--s3)', C_SAME = 'var(--s2)';
  const JC = ['var(--s1)', 'var(--s2)', 'var(--s3)'];
  const mk = (tag, cls, txt, parent) => { const n = document.createElement(tag); if (cls) n.className = cls; if (txt != null) n.textContent = txt; if (parent) parent.appendChild(n); return n; };
  const head = (k, title, lead) => { mk('div', 'pk', k ? 'Step ' + k : 'Summary', L); mk('h3', null, title, L); if (lead) mk('p', 'pl', lead, L); };
  const spec = rows => { const d = mk('dl', 'spec', null, L); rows.forEach(([k, v]) => { const r = mk('div', null, null, d); mk('dt', null, k, r); mk('dd', null, v, r); }); return d; };
  const finding = (txt, label = 'Finding') => { const f = mk('div', 'cfind', null, L); mk('b', null, label, f); mk('p', null, txt, f); return f; };
  const block = (title, parent = R) => { const b = mk('div', 'rblock', null, parent); const h = mk('div', 'rh', null, b); mk('span', 'rt', title, h); return mk('div', 'chart', null, b); };
  const cap = (txt, parent = R) => mk('p', 'cap', txt, parent);
  const tabs = (parent, items, cur, onChange, label) => {
    const g = mk('div', 'seg', null, parent); g.setAttribute('role', 'group'); g.setAttribute('aria-label', label);
    items.forEach(([v, l]) => { const b = mk('button', null, l, g); b.type = 'button'; b.dataset.v = v; b.setAttribute('aria-pressed', v === cur ? 'true' : 'false'); });
    g.addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; $$('button', g).forEach(x => x.setAttribute('aria-pressed', x === b ? 'true' : 'false')); onChange(b.dataset.v); });
    return g;
  };
  const fade = (nodes, animate, step = 170, start = 60) => { if (!animate || reduce) return; nodes.forEach((n, i) => { n.classList.add('pre'); setTimeout(() => n.classList.remove('pre'), start + step * i); }); };
  const big = (items, parent) => { const g = mk('div', 'bigs', null, parent); items.forEach(([v, l]) => { const d = mk('div', null, null, g); mk('b', null, v, d); mk('span', null, l, d); }); return g; };

  /* ---------- 1: other datasets ---------- */
  const DSETS = [
    { name: 'PersonaHub', by: 'Ge et al., 2025', what: 'One or two sentences of free text about who the person is. Used to vary synthetic training data.', size: `${fmt0(CMP.ph.released)} released personas. ${CMP.ph.cue}% of them mention any writing cue.` },
    { name: 'Nemotron-Personas', by: 'Meyer & Corneil, 2025', what: 'Synthetic personas aligned to real-world distributions (the USA release). The paper does not list its fields. Its records are the input to steps 3 and 4.', size: null },
    { name: 'SynthPAI', by: 'Yukhymenko et al., 2024', what: 'Structured profiles with a free-text writing style and a verbatim example. Built to seed agents that write Reddit threads, where users talk to each other rather than to an AI.', size: `${CMP.sp.profiles} hand-written style profiles of English-speaking Reddit users.` },
    { name: 'PersonaFactory', by: 'this work', what: 'A background layer and a separate style layer: seven typing keys, two to four quirks, a reference pool and an example message. Written for chat with an AI.', size: `${fmt0(CMP.pf.personas)} personas from ${CMP.pf.countries} countries; ${fmt0(CMP.pf.convs)} conversations in ${CMP.pf.langs} languages.`, pf: true }
  ];
  function s1(animate){
    head(1, 'Four persona datasets', 'What each format gives the rewriter to work with.');
    const ul = mk('ul', 'dsets', null, L);
    DSETS.forEach(d => {
      const li = mk('li', d.pf ? 'is-pf' : null, null, ul);
      const t = mk('div', 'dt', null, li); mk('b', null, d.name, t); mk('span', null, d.by, t);
      mk('p', null, d.what, li);
      if (d.size) mk('p', 'dsz', d.size, li);
    });
    const fd = finding('Only PersonaFactory has a slot for each typing habit. SynthPAI describes style in a paragraph, and PersonaHub almost never mentions it.');
    fade([...ul.children, fd], animate, 220);

    const c = block('What reaches the rewriter');
    const tw = mk('div', 'ftwrap', null, c);
    const t = mk('table', 'ftab', null, tw);
    const hr = mk('tr', null, null, mk('thead', null, null, t));
    mk('th', null, 'Field', hr); [['Persona', 'Hub'], ['Synth', 'PAI'], ['Persona', 'Factory']].forEach(([a, b]) => { const th = mk('th', 'n', null, hr); th.append(a); th.appendChild(document.createElement('wbr')); th.append(b); });
    const tb = mk('tbody', null, null, t);
    const grp = txt => { const tr = mk('tr', 'grp', null, tb); const td = mk('td', null, txt, tr); td.colSpan = 4; };
    const COLS = ['PersonaHub form', 'SynthPAI form', 'PersonaFactory'];
    const pctRow = (label, vals, note) => {
      const tr = mk('tr', null, null, tb); mk('td', 'fk', label, tr);
      vals.forEach((v, j) => {
        const td = mk('td', 'n', null, tr);
        const w = mk('span', 'cell', null, td); mk('span', 'cv', v + '%', w);
        const m = mk('span', 'm', null, w); const f = mk('i', null, null, m); f.style.width = v + '%';
        bind(td, [{ v: v + '%', l: label + ' · ' + COLS[j] }, { l: note || `share of ${CMP.enc.n} profiles whose ${label.toLowerCase()} survives in this format` }]);
      });
    };
    const txtRow = (label, vals, notes) => {
      const tr = mk('tr', null, null, tb); mk('td', 'fk', label, tr);
      vals.forEach((v, j) => { const td = mk('td', 'n', null, tr); mk('span', v === '–' ? 'cv no' : 'cv', v, td); bind(td, [{ v, l: label + ' · ' + COLS[j] }, { l: notes[j] }]); });
    };
    const E = Object.fromEntries(CMP.enc.rows);
    grp('Who they are');
    ['Age', 'Location', 'Occupation', 'Language'].forEach(k => pctRow(k, E[k]));
    grp('How they type');
    txtRow('Style in prose', ['–', 'yes', 'yes'], [`no style field; ${CMP.ph.cue}% of released personas mention any writing cue`, 'free-text writing-style description', 'free-text style sentence, kept consistent with the keys']);
    txtRow('Typing keys', ['–', '–', '7'], ['no slot', 'no slot for per-axis keys', 'capitalization, punctuation, emoji, abbreviations, typos, message structure, sign-offs']);
    txtRow('Example message', ['–', 'yes', 'yes'], ['none', 'verbatim example', 'a message the persona would usually type']);
    ['Style axes', 'Quirks', 'Reference pool'].forEach(k => pctRow(k, E[k]));
    grp('Size of one profile');
    txtRow('Words', ['13', '83', '280'], ['one third-person sentence', 'attribute block plus a style paragraph', 'background and style layers']);
    mk('div', 'unit', `Bars: share of ${CMP.enc.n} profiles whose value survives when the same persona is written in each dataset’s format. A dash means the format has no place for it.`, c);
    cap('Age, location and occupation survive in the SynthPAI and PersonaFactory formats, while the PersonaHub sentence drops age and most locations. Typing habits get through only when the format has a field for them.');
    fade([c.parentNode, R.lastChild], animate, 240, 400);
  }

  /* ---------- 2: same prompt, different profile ---------- */
  function dumbbell(c){
    const F = CMP.fmt, w = W(c), rowH = 42, top = 4, bottom = 22;
    const lw = Math.min(Math.ceil(measure(F.names)) + 10, Math.floor(w * 0.34));
    const pad = Math.ceil(measure(['100.0%'], 11.5)) + 12;
    const x0 = lw + 12, x1 = w - pad, sx = v => x0 + (x1 - x0) * v / 100;
    const h = top + F.names.length * rowH + bottom;
    const svg = svgFor(c, w, h);
    const g = S('g', { class: 'grid' }, svg);
    [0, 25, 50, 75, 100].forEach(t => { S('line', { x1: sx(t), x2: sx(t), y1: top, y2: h - bottom + 2 }, g); T(t + '%', { x: sx(t), y: h - 6, 'text-anchor': 'middle', class: 'muted' }, svg); });
    F.names.forEach((n, i) => {
      const y0 = top + i * rowH, cy = y0 + rowH / 2;
      const lab = T(fit(n, lw - 2), { x: lw, y: cy - 2, 'text-anchor': 'end' }, svg); if (n === 'PersonaFactory') lab.setAttribute('font-weight', '600');
      T(F.words[i] + ' words', { x: lw, y: cy + 12, 'text-anchor': 'end', class: 'muted' }, svg);
      S('line', { x1: sx(F.style[i]), x2: sx(F.intent[i]), y1: cy, y2: cy, stroke: 'var(--rule-2)', 'stroke-width': 3, 'stroke-linecap': 'round' }, svg);
      [[F.style[i], F.styleCI[i], C_STY], [F.intent[i], F.intentCI[i], C_INT]].forEach(([v, ci, col]) => {
        S('line', { x1: sx(ci[0]), x2: sx(ci[1]), y1: cy, y2: cy, stroke: col, 'stroke-width': 2, 'stroke-linecap': 'round' }, svg);
        S('circle', { cx: sx(v), cy, r: 6, fill: col, stroke: 'var(--surface)', 'stroke-width': 2 }, svg);
      });
      T(fmt1(F.style[i]) + '%', { x: sx(F.styleCI[i][1]) + 9, y: cy - 8, class: 'val', style: 'font-size:11.5px' }, svg);
      T(fmt1(F.intent[i]) + '%', { x: sx(F.intentCI[i][1]) + 8, y: cy + 4, class: 'val', style: 'font-size:11.5px' }, svg);
      const tip = [{ v: n, l: F.words[i] + ' words in the profile block' }, { c: C_STY, v: fmt1(F.style[i]) + '%', l: `style adopted (95% CI ${fmt1(F.styleCI[i][0])}–${fmt1(F.styleCI[i][1])})` }, { c: C_INT, v: fmt1(F.intent[i]) + '%', l: `intent kept (95% CI ${fmt1(F.intentCI[i][0])}–${fmt1(F.intentCI[i][1])}); ${fmt1(F.intentX[i])}% on cross-lingual prompts` }];
      if (i < 3) tip.push({ v: fmt1(F.pfPref[i]) + '%', l: 'of pairs where the judge prefers the PersonaFactory rewrite' });
      bind(S('rect', { class: 'hit', x: 0, y: y0, width: w, height: rowH }, svg), tip);
    });
  }
  function s2(animate){
    head(2, 'Same prompt, four profile formats', 'One persona is written out in each dataset’s format and used to rewrite the same prompt. Only the profile block changes.');
    const sp = spec([
      ['Sample', '800 paired prompts from the corpus, each with the persona the pipeline matched to it'],
      ['Held fixed', 'Persona content, Gemma-4-31B rewriter, MiniMax-M2.5 judge, decoding, prompt scaffold'],
      ['Changed', 'The profile block: 0, 13, 83 or 280 words'],
      ['Scope', 'Only the format is tested. Every condition renders our own profiles, so no PersonaHub or SynthPAI content enters the released data.']
    ]);
    const fd = finding('The PersonaHub sentence changes the text about as much as the other formats, yet style adoption only rises from 3.1% to 5.5%. In a separate test, real SynthPAI profiles, hand-written for 300 Reddit users, were the only ones on par with PersonaFactory.');
    const cv = finding(`Part of the gap to the SynthPAI form is content, since it carries less style information. When the same facts are written as free text of the same length, the structured version is on par in style, keeps the request ${fmt1(CMP.match.request)} points more often and reads more naturally.`, 'Caveat');
    fade([...sp.children, fd, cv], animate);
    const c = block('Sounds like the persona, keeps the request');
    c.appendChild(legend([{ name: 'Style adopted', color: C_STY, kind: 'dot' }, { name: 'Intent kept', color: C_INT, kind: 'dot' }]));
    const holder = mk('div', null, null, c);
    dumbbell(holder);
    mk('div', 'unit', '% of rewrites, N = 800 paired prompts. Whiskers: 95% Wilson intervals.', c);
    const bg = big(CMP.fmt.pfPref.map((v, i) => [fmt1(v) + '%', 'the judge picks the PersonaFactory rewrite over ' + ['no persona', 'the PersonaHub form', 'the SynthPAI form'][i]]), R);
    cap(`Style adoption rises with how much a format says about typing. Intent drops by about four points, almost all of it on cross-lingual prompts (${fmt1(CMP.fmt.intentX[3])}% there). External judges also rate the rewrites somewhat less natural than those without a persona. With a cap of two chat markers per turn, PersonaFactory rewrites read as naturally as SynthPAI-form ones and still adopt ${CMP.cap.gain[0]} to ${CMP.cap.gain[1]} points more style.`);
    fade([c.parentNode, bg, R.lastChild], animate, 240, 400);
    return () => dumbbell(holder);
  }

  /* ---------- 3 + 4: convert a record, add a style layer ---------- */
  const BG_FIELDS = ['Age', 'Gender', 'Region', 'Occupation and sector', 'Education', 'Native language and dialect', 'Hobbies', 'AI stance', 'Digital fluency'];
  const ST_FIELDS = ['Sentence length', 'Question framing', 'Native-language errors', 'Code-switching', 'Reference pool', 'Capitalization', 'Punctuation', 'Emoji', 'Abbreviations', 'Typos', 'Message structure', 'Sign-offs', '2–4 quirks', 'Example message'];
  function workpiece(stage, animate){
    const wp = mk('div', 'wp', null, L);
    const box = (tag, title, sub, on) => { const b = mk('div', 'wbox' + (on ? ' on' : ''), null, wp); const h = mk('div', 'wh', null, b); mk('span', 'wt', tag, h); mk('b', null, title, h); mk('span', 'ws', sub, h); return b; };
    const a = box('A', 'Raw source record', 'as released', true);
    mk('p', 'wn', 'The record from Nemotron-Personas or PersonaHub, passed to the rewriter unchanged.', a);
    mk('div', 'arrow', null, wp).setAttribute('aria-hidden', 'true');
    const b = box('B', 'Converted background', 'who they are', true);
    const bl = mk('ul', 'fl', null, b); const bItems = BG_FIELDS.map(f => mk('li', null, f, bl));
    mk('div', 'arrow', null, wp).setAttribute('aria-hidden', 'true');
    const c = box('C', 'Generated style layer', 'how they type', stage >= 3);
    const cl = mk('ul', 'fl st', null, c); const cItems = ST_FIELDS.map(f => mk('li', null, f, cl));
    if (stage < 3) mk('p', 'wn', 'Not added yet.', c);
    mk('p', 'wnote', 'Field names only. The paper does not print a converted record, so none is shown.', L);
    if (animate && !reduce){
      const items = stage === 2 ? bItems : cItems;
      items.forEach((n, i) => { n.classList.add('pre'); setTimeout(() => n.classList.remove('pre'), 120 + 70 * i); });
    }
    return wp;
  }
  let armView = 'rw';
  function armsChart(c, upto){
    const A = CMP.arms, idx = armView === 'rw' ? 2 : 0, keys = ['A', 'B', 'C'];
    const XL = [['A', 'raw record'], ['B', 'converted'], ['C', '+ style layer']];
    const w = W(c), left = 36, right = 52, top = 14, bottom = 42, h = 250;
    const colW = (w - left - right) / 3, sx = i => left + colW * (i + 0.5), sy = v => top + (h - top - bottom) * (1 - v / 80);
    const svg = svgFor(c, w, h);
    const g = S('g', { class: 'grid' }, svg);
    [0, 20, 40, 60, 80].forEach(t => { S('line', { x1: left, x2: w - right + 8, y1: sy(t), y2: sy(t) }, g); T(t + '%', { x: left - 6, y: sy(t) + 4, 'text-anchor': 'end', class: 'muted' }, svg); });
    XL.forEach(([k, l], i) => {
      const on = i <= upto;
      T(k, { x: sx(i), y: h - bottom + 17, 'text-anchor': 'middle', style: 'font-weight:600', class: on ? null : 'muted' }, svg);
      T(on ? l : 'next step', { x: sx(i), y: h - bottom + 31, 'text-anchor': 'middle', class: 'muted' }, svg);
      if (!on) S('rect', { x: sx(i) - colW / 2 + 6, y: top, width: colW - 12, height: h - top - bottom, rx: 6, fill: 'none', stroke: 'var(--rule-2)', 'stroke-dasharray': '4 4' }, svg);
    });
    const ends = [];
    A.judges.forEach((j, k) => {
      const vals = keys.slice(0, upto + 1).map(a => A[a][k][idx]);
      S('path', { d: vals.map((v, i) => (i ? 'L' : 'M') + sx(i) + ',' + sy(v)).join(''), fill: 'none', stroke: JC[k], 'stroke-width': 2.2, 'stroke-linejoin': 'round' }, svg);
      vals.forEach((v, i) => S('circle', { cx: sx(i), cy: sy(v), r: 5, fill: JC[k], stroke: 'var(--surface)', 'stroke-width': 2 }, svg));
      ends.push({ y: sy(vals[vals.length - 1]), v: vals[vals.length - 1] });
    });
    // end labels, pushed apart so they never overlap
    const order = ends.map((e, k) => k).sort((a, b) => ends[a].y - ends[b].y);
    let prev = -Infinity; order.forEach(k => { const y = Math.max(ends[k].y, prev + 14); ends[k].ly = y; prev = y; });
    order.forEach(k => T(fmt1(ends[k].v) + '%', { x: sx(upto) + 10, y: ends[k].ly + 4, class: 'val', style: 'font-size:11.5px' }, svg));
    for (let i = 0; i <= upto; i++){
      const tip = [{ v: XL[i][0] + ' · ' + XL[i][1], l: armView === 'rw' ? 'rewrite picked over the real message' : 'real message picked over the rewrite' }];
      A.judges.forEach((j, k) => { const r = A[keys[i]][k]; tip.push({ c: JC[k], v: fmt1(r[idx]) + '%', l: `${j} (draw ${fmt1(r[1])}%)` }); });
      bind(S('rect', { class: 'hit', x: sx(i) - colW / 2, y: top, width: colW, height: h - top - bottom }, svg), tip);
    }
  }
  function calibrationReadout(stage, animate){
    const tb = tabs(R, [['rw', 'Rewrite picked'], ['real', 'Real message picked']], armView, v => { armView = v; draw(); }, 'Which pick to show');
    const c = block('“Which reads more like a real person typed it?”');
    const cp = cap('');
    const draw = () => {
      c.replaceChildren(legend(CMP.arms.judges.map((j, k) => ({ name: j, color: JC[k], kind: 'dot' }))));
      armsChart(mk('div', null, null, c), stage === 2 ? 1 : 2);
      mk('div', 'unit', `% of ${CMP.conv.seeds} English WildChat seeds. A pick counts only if the judge makes it in both orders; the rest are draws.`, c);
      const A = CMP.arms, span = (arm, k) => { const v = arm.map(r => r[k]); return fmt1(Math.min(...v)) + '–' + fmt1(Math.max(...v)) + '%'; };
      if (stage === 2) cp.textContent = armView === 'rw'
        ? `After conversion, every judge picks the rewrite a few points more often (MiniMax-M2.5: ${fmt1(A.A[0][2])}% → ${fmt1(A.B[0][2])}%). The real message still wins more often.`
        : `The real message still wins in ${span(A.B, 0)} of seeds with the converted background, close to its ${span(A.A, 0)} against the raw record.`;
      else cp.textContent = armView === 'rw'
        ? 'With the style layer, every judge picks the rewrite more often than the real message. The paper reads this as more casual typing and not as closer realism: greetings, chat slang and emoji appear several times more often than in real user messages.'
        : `The real message now wins in only ${span(A.C, 0)} of seeds, down from ${span(A.B, 0)} without the style layer.`;
    };
    draw();
    fade([tb, c.parentNode, cp], animate, 220, 400);
    return draw;
  }
  function s3(animate){
    head(3, 'Convert a record', `Records from Nemotron-Personas and PersonaHub are rewritten into PersonaFactory’s background fields. No style yet.`);
    const wp = workpiece(2, animate);
    const sp = spec([
      ['Sample', `${fmt0(CMP.conv.records)} converted records; the ${CMP.conv.seeds} English WildChat seeds that pass in all three arms`],
      ['Test', 'Each rewrite is paired with the real message it came from. Three judges pick the one that reads more like a real person.']
    ]);
    const fd = finding('Conversion on its own helps a little. Every judge still prefers the real message more often than the rewrite.');
    fade([wp, ...sp.children, fd], animate, 160);
    return calibrationReadout(2, animate);
  }
  function s4(animate){
    head(4, 'Add a style layer', 'A style layer is generated from the converted background, the same way as for PersonaFactory’s own personas.');
    const wp = workpiece(3, animate);
    const cw = CMP.arms.C.map(r => r[2]);
    const fd = finding(`With the style layer, the rewrite beats the real message under all three judges. It is picked in ${fmt1(Math.min(...cw))}% to ${fmt1(Math.max(...cw))}% of seeds, against at most ${fmt1(Math.max(...CMP.arms.B.map(r => r[2])))}% without it.`);
    fade([wp, fd], animate, 200);
    return calibrationReadout(3, animate);
  }

  /* ---------- 5: restyle replies ---------- */
  let rpView = 'rates';
  function s5(animate){
    head(5, 'Restyle the assistant side', 'Conversation data without user personas can still get a styled assistant side. The pipeline picks a reply style from the user’s own messages and regenerates the replies in that style.');
    const wp = mk('div', 'wp conv', null, L);
    const turn = (who, title, sub, on) => { const b = mk('div', 'wbox ' + who + (on ? ' on' : ''), null, wp); const h = mk('div', 'wh', null, b); mk('span', 'wt', { user: 'U', bot: 'AI', gate: 'QC' }[who], h); mk('b', null, title, h); mk('span', 'ws', sub, h); return b; };
    turn('user', 'User turns 1–3', 'kept as they are; the matcher reads only these', false);
    turn('bot', 'Assistant turns', 'regenerated with the style section as the only system prompt', true);
    turn('gate', 'Continuity loop and sanity gate', 'the same checks as the main pipeline', true);
    const sp = spec([
      ['Sample', `${fmt0(CMP.reply.n)} UltraChat and Nemotron conversations, ${fmt0(CMP.reply.turns)} assistant turns`],
      ['Matching', 'Found a style for every conversation']
    ]);
    const S_ = CMP.sys;
    const fd = finding(`Conversations that carry their own system prompt are left alone. In a test on ${S_.n} single-turn conversations whose system prompt sets a checkable format rule, compliance was ${S_.none}% without a style and ${S_.below}% with one, or ${S_.last}% when the system prompt was moved after the style.`, 'Limit');
    fade([...wp.children, ...sp.children, fd], animate, 160);

    const tb = tabs(R, [['rates', 'Rates'], ['len', 'Reply length']], rpView, v => { rpView = v; draw(); }, 'View');
    const c = block('Assistant replies, four ways');
    const cp = cap('');
    const RW = CMP.reply.rows;
    const draw = () => {
      c.replaceChildren();
      if (rpView === 'rates'){
        hbars(c, { rows: RW.map(r => ({ label: r[0], values: [r[3], r[2], r[4]], tip: () => [{ l: 'median ' + r[5] + ' words' }, ...(r[2] == null ? [{ l: 'sanity pass: not applicable' }] : []), ...(r[4] == null ? [{ l: 'same content: ' + (r[0] === 'Source replies' ? 'this is the reference' : 'n/a') }] : [])] })), series: [{ name: 'Style adopted', color: C_STY }, { name: 'Sanity pass', color: C_INT }, { name: 'Same content as source', color: C_SAME }], max: 100, ticks: [0, 25, 50, 75, 100], barH: 10, gapIn: 3, labelMax: 150 });
        mk('div', 'unit', '% of assistant turns. Missing bar: not applicable, or the source itself is the reference. Content is compared on the first assistant turn.', c);
        cp.textContent = `Regenerating with a style lifts adoption from ${fmt1(RW[1][3])}% to ${fmt1(RW[2][3])}% at a cost of about five points of sanity pass. Restyling the original replies keeps their content (${fmt1(RW[3][4])}%) but adopts less style. It falls back to the original reply on ${CMP.reply.fallback}% of turns because a protected span was lost.`;
      } else {
        hbars(c, { rows: RW.map(r => ({ label: r[0], values: [r[5]] })), series: [{ name: 'Median words', color: C_STY }], max: 600, ticks: [0, 200, 400, 600], fmt: v => fmt0(v), barH: 14, labelMax: 150, unit: 'Median words per assistant reply' });
        cp.textContent = `Regenerating without a style makes replies much longer (${RW[1][5]} median words against ${RW[0][5]} in the source). With a style they come back close to the source length (${RW[2][5]}).`;
      }
    };
    draw();
    fade([tb, c.parentNode, cp], animate, 220, 400);
    return draw;
  }

  /* ---------- 6: upgrade path ---------- */
  function s6(animate){
    head(0, 'Upgrade path', 'Two ways to give an existing dataset a style layer.');
    const routes = mk('div', 'routes', null, L);
    const route = (title, steps) => { const d = mk('div', 'route', null, routes); mk('b', null, title, d); const ol = mk('ol', null, null, d); steps.forEach(s => mk('li', null, s, ol)); return d; };
    route('A persona dataset (PersonaHub, Nemotron-Personas, …)', ['Convert each record into the background fields.', 'Generate a style layer from that background.', 'Use the personas to rewrite real prompts with the request held fixed.']);
    route('A conversation dataset with no user personas', ['Pick a reply style from the first three user messages.', 'Regenerate the assistant turns in that style.', 'Skip conversations that bring their own system prompt.']);
    const K = CMP.cap;
    const fd = finding(`Rewrites still use greetings, slang and emoji more often than real users. A cap of two chat markers per turn reduces this and will be the default in the released code. The corpus was generated without that cap, and ${fmt1(K.corpusAtMost)}% of its user turns use at most two of the six markers. Matching real-user rates exactly is left to later versions.`, 'Still open');
    fade([...routes.children, fd], animate, 220);
    const A = CMP.arms, RW = CMP.reply.rows, F = CMP.fmt;
    const ROWS = [
      ['Other datasets', { v: CMP.ph.cue + '%' }, `of ${fmt0(CMP.ph.released)} released PersonaHub personas mention any writing cue`],
      ['Same prompt, new profile', { up: fmt1(F.style[3]) + '%' }, `style adopted with the PersonaFactory profile, against ${fmt1(F.style[2])}% for the SynthPAI form and ${fmt1(F.style[1])}% for PersonaHub’s`],
      ['Convert a record', { from: fmt1(A.A[0][2]), up: fmt1(A.B[0][2]) + '%' }, 'rewrite picked over the real message, raw record against converted background (MiniMax-M2.5)'],
      ['Add a style layer', { up: fmt1(A.C[0][2]) + '%' }, `rewrite picked with the style layer; ${fmt1(A.C[1][2])}% and ${fmt1(A.C[2][2])}% with the other two judges`],
      ['Restyle replies', { from: fmt1(RW[1][3]), up: fmt1(RW[2][3]) + '%' }, 'style adoption on the assistant side, at a cost of about five points of sanity pass']
    ];
    const ol = mk('ol', 'sheet', null, R);
    ROWS.forEach((r, i) => {
      const li = mk('li', null, null, ol);
      const b = mk('button', null, null, li); b.type = 'button';
      mk('span', 'sn', String(i + 1), b);
      const t = mk('span', 'st', null, b); mk('b', null, r[0], t);
      // improvements in green: the result of each step, and in a before → after pair only the after value
      const sv = mk('span', 'sv', null, b), x = r[1];
      if (x.from) { mk('span', 'from', x.from, sv); sv.append(' → '); }
      mk('span', x.up ? 'up' : null, x.up || x.v, sv);
      mk('span', 'sd', r[2], b);
      b.addEventListener('click', () => { line.stop(); line.show(i, false); root.scrollIntoView({ block: 'start', behavior: reduce ? 'auto' : 'smooth' }); });
    });
    cap('Open a line to see the step behind it.');
    fade([...ol.children, R.lastChild], animate, 160, 300);
  }

  let redraw = null;
  const STAGES = [s1, s2, s3, s4, s5, s6];
  function render(s, animate){
    L.replaceChildren(); R.replaceChildren();
    redraw = STAGES[s](animate) || null;
  }
  const line = lineCtl(root, { count: STAGES.length, render, dur: s => s === 5 ? 1800 : 2800 });
  // redraw the SVG charts only when the station's width changes (height changes from other stations are ignored)
  let lastW = root.clientWidth;
  reg(() => { const w = root.clientWidth; if (w === lastW) return; lastW = w; if (redraw) redraw(); });
})();
