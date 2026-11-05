/* ======================= CORPUS: the production line, seed logs to release ======================= */
// Numbers used here that are not in data.js:
// Table 23 (App. G.1): conversations that reached the sanity gate and passed it, by slice. [label, reached, passed, pass %]
const T23 = {
  responder: [['Gemma-4-31B', 823676, 734927, 89.2], ['Ministral-3-14B', 783161, 532379, 68.0]],
  seed: [['WildChat', 959084, 740485, 77.2], ['UltraChat-200k', 384191, 315508, 82.1], ['Nemotron IF', 263562, 211313, 80.2]],
  set: [['Language-matched', 838034, 689348, 82.3], ['Cross-lingual', 768803, 577958, 75.2]],
  all: ['Overall', 1606837, 1267306, 78.9]
};
const BANK_EN = 19.6;     // Section 4: native-English personas are 19.6% of the bank (cross-lingual mode samples from all of it)
const TIMED_OUT = 0.2;    // App. G.1: share of kept turns that are rewriter time-outs
const MIN_COS = 0.15;     // App. G.1: embedding tier threshold (all-MiniLM-L6-v2)
const P_QUIRK = 0.25;     // Section 4: quirks fire with p = 0.25 per turn
const LEN_GUARD = 50;     // Section 4: rewrites under 50% of the original length are rejected
const ADAPT = 2;          // Section 4: continuity adaptation loop, up to 2 iterations

(function corpus(){
  const C = D.corpus;
  const root = $('#corpusLine'), flowEl = $('#cFlow'), piece = $('#cPiece'), rd = $('#cRead'), srcEl = $('#cSrc');
  // seed sets: colour, reached the gate (Table 23), passed (Table 23), released (Table 3)
  const SEEDS = T23.seed.map((r, i) => ({ name: ['WildChat', 'UltraChat', 'Nemotron'][i], full: r[0], color: ['var(--s1)', 'var(--s2)', 'var(--s3)'][i], reached: r[1], passed: r[2], rate: r[3], released: C.seed[i][1], share: C.seed[i][2] }));
  const REACHED = T23.all[1], PASSED = T23.all[2], RELEASED = C.gate.released;
  const TURNS = D.headline.userTurns, KEPT = C.keptTotal;
  const EN = C.langs.find(r => r[0] === 'English')[1];
  $('#cLegend').appendChild(legend(SEEDS.map(s => ({ name: s.full + ' seeds', color: s.color }))));

  let cur = 6, running = false, redraw = null;
  const el = (tag, cls, txt, parent) => { const n = document.createElement(tag); if (cls) n.className = cls; if (txt != null) n.textContent = txt; if (parent) parent.appendChild(n); return n; };
  const head = (k, title, lead) => { el('div', 'pk', 'Station ' + k, piece); el('h3', null, title, piece); if (lead) el('p', 'pl', lead, piece); };
  const kv = (rows, parent) => { const d = el('dl', 'kv', null, parent); rows.forEach(([k, v]) => { el('dt', null, k, d); el('dd', null, v, d); }); return d; };
  const block = (title, src, parent) => { const b = el('div', 'rblock', null, parent); const h = el('div', 'rh', null, b); el('span', null, title, h); if (src != null) el('span', 'src', src, h); const c = el('div', 'chart', null, b); return c; };
  const big = (items, parent) => { const g = el('div', 'bigs', null, parent); items.forEach(([v, l]) => { const d = el('div', null, null, g); el('b', null, v, d); el('span', null, l, d); }); return g; };
  const fade = (nodes, animate, step = 160) => { if (!animate || reduce) return; nodes.forEach((n, i) => { n.classList.add('pre'); setTimeout(() => n.classList.remove('pre'), 60 + step * i); }); };

  /* ---------- the persistent flow ribbon ---------- */
  const METRIC = [
    [fmt0(REACHED), 'reach the gate', '1.61M'],
    ['85', 'languages', '85'],
    ['3 tiers', '+ cross-lingual', '3+1'],
    ['≈94%', 'turns re-voiced', '94%'],
    ['≤ ' + ADAPT, 'adaptation rounds', '≤' + ADAPT],
    [fmt1(T23.all[3]) + '%', 'pass · ' + fmt0(PASSED), '78.9%'],
    [fmt0(RELEASED), 'conversations', '1.24M']
  ];
  function drawFlow(){
    const w = W(flowEl), n = 7, cw = w / n, cx = i => cw * (i + 0.5);
    const compact = w < 720;
    const y0 = compact ? 40 : 52, H = compact ? 40 : 58;
    const h = y0 + H + (compact ? 36 : 54);
    const k = H / REACHED;
    const ss = t => t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t);
    const g0 = cx(5) - cw * 0.34, g1 = cx(5) + cw * 0.2, r0 = cx(6) - cw * 0.34, r1 = cx(6) + cw * 0.08;
    const val = (s, x) => x <= g0 ? s.reached : x <= g1 ? s.reached + (s.passed - s.reached) * ss((x - g0) / (g1 - g0)) : x <= r0 ? s.passed : s.passed + (s.released - s.passed) * ss((x - r0) / (r1 - r0));
    const svg = svgFor(flowEl, w, h);
    svg.setAttribute('aria-label', 'Ribbon of conversations through seven stations: ' + fmt0(REACHED) + ' reach the sanity gate, ' + fmt0(PASSED) + ' pass, ' + fmt0(RELEASED) + ' are released.');
    for (let i = 0; i < n; i++) S('rect', { class: 'colhl', 'data-c': i, x: i * cw + 2, y: 1, width: cw - 4, height: h - 2, rx: 6 }, svg);
    // strands, one polygon per seed set per column
    for (let i = 0; i < n; i++){
      const xa = i * cw - (i ? 0.5 : 0), xb = Math.min(w - 2, (i + 1) * cw + 0.5);
      const xs = []; for (let x = xa; x < xb; x += 3) xs.push(x); xs.push(xb);
      let acc = xs.map(() => 0);
      const g = S('g', { 'data-c': i, class: 'seg' }, svg);
      SEEDS.forEach(s => {
        const top = xs.map((x, j) => y0 + acc[j] * k);
        acc = acc.map((a, j) => a + val(s, xs[j]));
        const bot = xs.map((x, j) => y0 + acc[j] * k);
        const d = 'M' + xs.map((x, j) => x.toFixed(1) + ',' + top[j].toFixed(1)).join('L') + 'L' + xs.map((x, j) => x.toFixed(1) + ',' + bot[j].toFixed(1)).reverse().join('L') + 'Z';
        S('path', { d, fill: s.color }, g);
      });
    }
    // station boundaries cut through the ribbon
    for (let i = 1; i < n; i++) S('line', { class: 'cut', x1: i * cw, x2: i * cw, y1: y0 - 3, y2: y0 + H + 3 }, svg);
    // per-column metric
    for (let i = 0; i < n; i++){
      const m = METRIC[i];
      const g = S('g', { 'data-c': i, class: 'met' }, svg);
      const vs = compact ? 12.5 : 15.5;
      const tw = measure([compact ? m[2] : m[0]], vs) * 1.12;
      const x = Math.max(tw / 2 + 2, Math.min(cx(i), w - tw / 2 - 2));
      if (compact) T(String(i + 1), { x: cx(i), y: 12, 'text-anchor': 'middle', class: 'muted' }, g);
      T(compact ? m[2] : m[0], { x, y: compact ? 29 : 22, 'text-anchor': 'middle', class: 'mv', style: 'font-size:' + vs + 'px' }, g);
      if (!compact){ const cap = fit(m[1], cw - 8, 11.5); const cwid = measure([cap], 11.5); T(cap, { x: Math.max(cwid / 2 + 2, Math.min(cx(i), w - cwid / 2 - 2)), y: 39, 'text-anchor': 'middle', class: 'muted' }, g); }
    }
    // drops at the gate and at release
    [[5, REACHED - PASSED, 'fail the gate', g0 + (g1 - g0) * 0.5], [6, PASSED - RELEASED, 'filtered', r0 + (r1 - r0) * 0.5]].forEach(([i, v, l, x]) => {
      const g = S('g', { 'data-c': i, class: 'drop' }, svg);
      const by = y0 + H * (i === 5 ? (REACHED + PASSED) / 2 / REACHED : (PASSED + RELEASED) / 2 / REACHED) + 3;
      S('path', { d: `M${x},${by}V${y0 + H + 10}`, class: 'dline' }, g);
      S('path', { d: `M${x - 3.5},${y0 + H + 6}L${x},${y0 + H + 11}L${x + 3.5},${y0 + H + 6}`, class: 'dline' }, g);
      const lines = compact ? ['−' + compact_(v)] : ['−' + fmt0(v), l];
      lines.forEach((txt, j) => { const tw = measure([txt], 11.5); T(txt, { x: Math.max(tw / 2 + 2, Math.min(x, w - tw / 2 - 2)), y: y0 + H + 25 + j * 16, 'text-anchor': 'middle', class: j ? 'muted' : 'muted dv' }, g); });
    });
    for (let i = 0; i < n; i++){
      const r = S('rect', { class: 'hitc', x: i * cw, y: 0, width: cw, height: h }, svg);
      const t = S('title', {}, r); t.textContent = 'Station ' + (i + 1) + ': ' + $$('.stage .t', root)[i].textContent;
      r.addEventListener('click', () => { line.stop(); line.show(i, false); });
    }
    paintFlow();
  }
  const compact_ = v => v >= 1e5 ? Math.round(v / 1e3) + 'k' : (v / 1e3).toFixed(0) + 'k';
  function paintFlow(){
    $$('[data-c]', flowEl).forEach(n => { const c = +n.dataset.c; n.classList.toggle('later', c > cur); n.classList.toggle('now', c === cur); });
    flowEl.classList.toggle('running', running);
  }

  /* ---------- stage 1: seed logs ---------- */
  function s1(animate){
    head(1, 'Seed logs in', 'Conversations from three widely used chat datasets enter the line. Each keeps its request and turn order. User turns get re-voiced and assistant turns regenerated.');
    const list = el('ul', 'seeds', null, piece);
    const names = ['WildChat', 'UltraChat-200k', 'Nemotron Instruction-Following'];
    const notes = ['Zhao et al., 2024', 'Ding et al., 2023; Tunstall et al., 2023', 'NVIDIA, 2025a; Nathawani et al., 2025; NVIDIA, 2025b. Longer prompts, often with multi-step instructions or constraints.'];
    SEEDS.forEach((s, i) => { const li = el('li', null, null, list); const sw = el('i', null, null, li); sw.style.background = s.color; const d = el('div', null, null, li); el('b', null, names[i], d); el('span', null, notes[i], d); });
    fade([...list.children], animate);
    const c = block('Conversations that reach the sanity gate', 'Table 23', rd);
    const draw = () => hbars(c, { rows: SEEDS.map(s => ({ label: s.full, values: [s.reached], colors: [s.color], tip: () => [{ l: fmt1(s.reached / REACHED * 100) + '% of all that reach the gate' }] })), series: [{ name: 'conversations', color: 'var(--s1)' }], fmt: fmt0, ticks: false, barH: 18, unit: 'Conversations, total ' + fmt0(REACHED) });
    el('p', 'cap', 'WildChat supplies ' + fmt1(SEEDS[0].reached / REACHED * 100) + '% of what reaches the gate. Colors match the ribbon.', rd);
    // Source: paper Section 6, Table 23
    return draw;
  }

  /* ---------- stage 2: language and script ---------- */
  let withEn = false;
  function s2(animate){
    head(2, 'Language & script detection', 'The first user turn is classified before any persona is chosen. Language decides which personas are allowed.');
    const steps = el('ol', 'steps', null, piece);
    [['Script', 'Deterministic Unicode-block classifier (CJK, Cyrillic, Arabic, …).'], ['Language', 'Confidence-thresholded detector (Lingua).'], ['Eligible pool', 'Non-Latin script: native speakers of that script. Other Latin: the detected language. English: the wider English-speaking pool.']].forEach(([k, v]) => { const li = el('li', null, null, steps); el('b', null, k, li); el('span', null, v, li); });
    fade([...steps.children], animate);
    big([['85', 'languages in the release'], [fmt1(EN / RELEASED * 100) + '%', 'open in English (' + fmt0(EN) + ')']], piece);
    const top = el('div', 'rtools', null, rd);
    const b = el('button', 'ctl', 'Include English', top); b.type = 'button'; b.setAttribute('aria-pressed', withEn);
    const c = block(withEn ? 'Top languages of released conversations' : 'Top 10 non-English languages', 'Fig. 26a', rd);
    b.addEventListener('click', () => { withEn = !withEn; b.setAttribute('aria-pressed', withEn); $('.rh span', c.parentNode).textContent = withEn ? 'Top languages of released conversations' : 'Top 10 non-English languages'; draw(); });
    const draw = () => hbars(c, { rows: C.langs.filter(r => withEn || r[0] !== 'English').map(r => ({ label: r[0], values: [r[1]] })), series: [{ name: 'conversations', color: 'var(--s1)' }], fmt: compact, ticks: false, barH: 12, unit: 'Released conversations, by detected language of the first user turn' });
    el('p', 'cap', 'The other ' + fmt1(100 - EN / RELEASED * 100) + '% span 84 languages. These counts use fastText with a Lingua fallback.', rd);
    // Source: paper Section 4, App. G.1, Fig. 26a
    return draw;
  }

  /* ---------- stage 3: persona matching cascade ---------- */
  const tierN = k => C.tier.find(r => r[0] === k);
  const TIERS = [
    { id: 'loc', n: '1', name: 'Location', what: 'The prompt names a place. Matched to sub-region, country, native language and dialect.', row: tierN('Location pool') },
    { id: 'emb', n: '2', name: 'Semantic embedding', what: 'all-MiniLM-L6-v2 on the first user message and each persona; top-1 if cosine ≥ ' + MIN_COS + '.', row: tierN('Embedding') },
    { id: 'pool', n: '3', name: 'Language pool', what: 'Fallback: any persona who speaks the prompt’s language.', row: tierN('Language pool') },
    { id: 'none', n: '–', name: 'No compatible persona', what: 'The original turn ships verbatim.' }
  ];
  const XL = { id: 'xl', n: 'CL', name: 'Cross-lingual mode', what: 'A separate run. Skips the cascade and samples one persona uniformly from the whole bank, where native-English personas are ' + BANK_EN + '%.', row: tierN('Cross-lingual') };
  const CASES = [
    { id: 'loc', l: 'Names a place', d: 'The prompt names a place (the paper’s example: “in Berlin”). Regular expressions pull it out and the first tier matches it.' },
    { id: 'emb', l: 'Topic fits', d: 'No place named. The prompt falls to the embedding tier, which pairs it with a persona whose occupation or interests fit the topic.' },
    { id: 'pool', l: 'Language only', d: 'No place and no persona above cosine ' + MIN_COS + '. The language pool still guarantees a speaker of the prompt’s language.' },
    { id: 'none', l: 'No compatible persona', d: 'No tier finds a compatible persona. Nothing is rewritten and the turn ships as it was.' },
    { id: 'xl', l: 'Cross-lingual run', d: 'The cascade is skipped. In the paper’s example, a Geneva persona re-voices an English UltraChat prompt in French.' }
  ];
  let caseId = 'emb', tokTimers = [];
  function s3(animate){
    head(3, 'Persona matching', 'A conversation falls through the tiers until one finds a compatible persona. The first hit wins.');
    const chips = el('div', 'chips', null, piece); chips.setAttribute('role', 'group'); chips.setAttribute('aria-label', 'Case');
    const desc = el('p', 'cdesc', null, piece);
    const casc = el('div', 'casc', null, piece);
    const start = el('div', 'cstart', null, casc); el('span', 'tn', '', start); el('span', null, 'Seed conversation, language detected', start);
    const ladder = el('div', 'ladder', null, casc);
    const row = (t, parent) => {
      const d = el('div', 'tier' + (t.id === 'none' ? ' out' : '') + (t.id === 'xl' ? ' xl' : ''), null, parent); d.dataset.t = t.id;
      el('span', 'tn', t.n, d);
      const b = el('div', 'tb', null, d);
      const h = el('div', 'th', null, b); el('b', null, t.name, h); el('span', 'tv', '', h);
      el('span', 'tw', t.what, b);
      if (t.row){ const m = el('div', 'tm', null, b); const bar = el('span', 'bar', null, m); const f = el('i', null, null, bar); f.style.width = Math.max(0.6, t.row[2]) + '%'; el('span', 'tval', fmt1(t.row[2]) + '% · ' + fmt0(t.row[1]), m); m.title = fmt0(t.row[1]) + ' released conversations, ' + fmt1(t.row[2]) + '% of the release'; }
      return d;
    };
    TIERS.forEach(t => row(t, ladder));
    row(XL, casc);
    el('div', 'unit', 'Bars: share of released conversations matched this way', casc);
    const tok = el('span', 'tok', null, casc); tok.setAttribute('aria-hidden', 'true');
    const posOf = node => { const a = $('.tn', node).getBoundingClientRect(), b = casc.getBoundingClientRect(); return [a.left - b.left + a.width / 2 - 6, a.top - b.top + a.height / 2 - 6]; };
    const place = (node, inst) => { const [x, y] = posOf(node); tok.style.transition = inst ? 'none' : ''; tok.style.transform = `translate(${x}px, ${y}px)`; };
    function runCase(animated){
      tokTimers.forEach(clearTimeout); tokTimers = [];
      const c = CASES.find(x => x.id === caseId);
      desc.textContent = c.d;
      $$('.chip', chips).forEach(b => b.setAttribute('aria-pressed', b.dataset.v === caseId));
      const tiers = $$('.tier', casc);
      tiers.forEach(t => { t.classList.remove('hit', 'miss'); $('.tv', t).textContent = ''; });
      const order = caseId === 'xl' ? [] : TIERS.slice(0, TIERS.findIndex(t => t.id === caseId)).map(t => t.id);
      const target = tiers.find(t => t.dataset.t === caseId);
      const finish = () => { target.classList.add('hit'); $('.tv', target).textContent = caseId === 'none' ? 'verbatim' : caseId === 'xl' ? 'sampled' : 'match'; };
      const miss = id => { const t = tiers.find(x => x.dataset.t === id); t.classList.add('miss'); $('.tv', t).textContent = 'no match'; };
      if (!animated || reduce){ order.forEach(miss); place(target, true); finish(); return; }
      place(start, true); void tok.offsetWidth;
      let k = 0;
      const step = () => {
        if (k < order.length){ const id = order[k++]; place(tiers.find(x => x.dataset.t === id)); tokTimers.push(setTimeout(() => { miss(id); step(); }, 380)); }
        else { place(target); tokTimers.push(setTimeout(finish, 360)); }
      };
      tokTimers.push(setTimeout(step, 120));
    }
    CASES.forEach(c => { const b = el('button', 'chip', c.l, chips); b.type = 'button'; b.dataset.v = c.id; b.addEventListener('click', () => { caseId = c.id; runCase(true); }); });
    runCase(animate);
    const c = block('Persona set of released conversations', 'Table 3', rd);
    const drawSet = () => hbars(c, { rows: C.personaSet.map(r => ({ label: r[0], values: [r[2]], tip: () => [{ l: fmt0(r[1]) + ' conversations' }] })), series: [{ name: 'share of release', color: 'var(--s1)' }], max: 100, ticks: [0, 25, 50, 75, 100], barH: 16, unit: '% of released conversations' });
    el('p', 'cap', 'Without the cross-lingual mode the language-matched set would stay almost entirely English. In that set, the embedding tier makes most matches.', rd);
    const facts = el('div', 'rblock', null, rd); el('div', 'rh', null, facts).appendChild(document.createTextNode('Eligibility rules'));
    kv([['Language-matched', 'The persona natively speaks the prompt’s language and script.'], ['Cross-lingual', 'Any persona. The prompt’s language is ignored.'], ['Format guard', 'Exact-format prompts (verbatim, code, translation, strict JSON or quoted output) skip the rewrite.']], facts);
    // Source: paper Section 4, App. G.1, Table 3
    return () => { drawSet(); place($('.tier.hit', casc) || start, true); };
  }

  /* ---------- stage 4: rewrite and guards ---------- */
  function s4(animate){
    head(4, 'Rewrite & guards', 'Each eligible user turn is re-voiced by the matched persona under guards that protect the request.');
    const steps = el('ol', 'steps', null, piece);
    [['Mask', 'Quotes, code, URLs and numbers are masked, then restored. A rewrite that loses one is retried.'], ['Rewrite', 'Same intent, subtle persona traits. Quirks fire with p = ' + P_QUIRK + ' per turn.'], ['Cross-lingual', 'Translate the turn literally first, then restyle it in that language.'], ['Length guard', 'A rewrite under ' + LEN_GUARD + '% of the original length is rejected.'], ['Fallback', 'If any guard fails, the original turn ships verbatim.']].forEach(([k, v]) => { const li = el('li', null, null, steps); el('b', null, k, li); el('span', null, v, li); });
    fade([...steps.children], animate);
    const sp = block(fmt0(TURNS) + ' released user turns', 'App. G.1', rd).parentNode; sp.classList.add('split'); sp.lastChild.remove();
    const rv = TURNS - KEPT;
    const bar = el('div', 'sbar', null, sp); const a = el('i', 'a', null, bar); a.style.width = (rv / TURNS * 100) + '%'; const b = el('i', 'b', null, bar); b.style.width = (KEPT / TURNS * 100) + '%';
    bind(a, [{ v: '≈94%', l: 'of released user turns re-voiced', c: 'var(--s1)' }]); bind(b, [{ v: fmt0(KEPT), l: 'user turns kept verbatim on purpose', c: 'var(--faint)' }]);
    sp.appendChild(legend([{ name: 'Re-voiced, about 94%', color: 'var(--s1)' }, { name: 'Kept verbatim, ' + fmt0(KEPT), color: 'var(--faint)' }]));
    const c = block('Why ' + fmt0(KEPT) + ' turns were kept verbatim', 'App. G.1', rd);
    c.classList.add('meters');
    const kmax = Math.max(...C.kept.map(k => k[1]));
    C.kept.forEach(k => { const m = el('div', 'meter', null, c); el('span', null, k[0], m); el('span', 'mv', fmt0(k[1]) + ' · ' + fmt1(k[2]) + '%', m); const b = el('span', 'bar', null, m); el('b', null, null, b).style.width = (k[1] / kmax * 100) + '%'; });
    el('div', 'unit', 'Kept user turns and share of them, by reason. Another ' + TIMED_OUT + '% are rewriter time-outs.', c.parentNode);
    const draw = () => {};
    el('p', 'cap', 'A broken request or a switch of language is worse than an unstyled turn, so these turns are kept as they were.', rd);
    // Source: paper Section 4, App. G.1
    return draw;
  }

  /* ---------- stage 5: assistant regeneration ---------- */
  function s5(animate){
    head(5, 'Assistant regeneration', 'Every assistant reply is regenerated for the new user turn, and checked against where the real conversation went next.');
    const loop = el('ol', 'loop', null, piece);
    const items = [
      ['Regenerate', 'The responder answers the restyled turn. The persona is passed as a system prompt. It shapes the reply and is never stored.'],
      ['Continuity judge', 'For non-final turns: does the reply still lead to the real next user message from the log?'],
      ['Adapt', 'If not, the reply is rewritten, up to ' + ADAPT + ' rounds.', true],
      ['Hand over', 'If the judge still flags it after the last round, the last version goes on to the sanity gate.']
    ];
    items.forEach(([k, v, back]) => { const li = el('li', back ? 'back' : null, null, loop); el('b', null, k, li); el('span', null, v, li); if (back){ const r = el('span', 'ret', '↺ back to the judge', li); r.setAttribute('aria-hidden', 'true'); } });
    fade([...loop.children], animate, 260);
    const c = block('Conversations that reach the gate, by responder', 'Table 23', rd);
    const draw = () => hbars(c, { rows: T23.responder.map(r => ({ label: r[0], values: [r[1]], tip: () => [{ l: fmt1(r[1] / REACHED * 100) + '% of all that reach the gate' }] })), series: [{ name: 'conversations', color: 'var(--s1)' }], fmt: fmt0, ticks: false, barH: 18, unit: 'Conversations' });
    el('p', 'cap', 'Gemma-4-31B and Ministral-3-14B each answer about half. The stored example holds only the user and assistant turns.', rd);
    // Source: paper Section 4, Table 23
    return draw;
  }

  /* ---------- stage 6: sanity gate ---------- */
  function s6(animate){
    head(6, 'Sanity gate', 'A final judge screens each whole conversation for six failure classes. Verdicts are stored as metadata flags.');
    const ul = el('ul', 'fails', null, piece);
    ['Language mismatch (language-matched set)', 'Instruction or format violation', 'Truncation', 'Fabricated personal experience', 'Incoherence or hallucination', 'Request not addressed'].forEach(t => el('li', null, t, ul));
    fade([...ul.children], animate, 120);
    big([[fmt0(PASSED), 'of ' + fmt0(REACHED) + ' pass (' + fmt1(T23.all[3]) + '%)'], ['≈74%', 'of dropped conversations are Ministral-3-14B’s']], piece);
    const groups = [['Responder', T23.responder], ['Seed set', T23.seed], ['Persona set', T23.set]];
    const c = block('Sanity pass rate by slice', 'Table 23', rd);
    // grouped bars on one shared scale, so the dashed overall line lines up across groups
    const draw = () => {
      const w = W(c), barH = 13, rowH = 22, gh = 22, top = 18, bottom = 22;
      const lw = Math.min(Math.ceil(measure(groups.flatMap(g => g[1].map(r => r[0])))) + 10, w * 0.4);
      const valW = Math.ceil(measure(['100.0%'])) + 8;
      const x0 = lw + 6, x1 = w - valW, sx = v => x0 + (x1 - x0) * v / 100;
      const h = top + groups.reduce((a, g) => a + gh + g[1].length * rowH, 0) + bottom;
      const svg = svgFor(c, w, h);
      const gg = S('g', { class: 'grid' }, svg);
      [0, 25, 50, 75, 100].forEach(t => { S('line', { x1: sx(t), x2: sx(t), y1: top, y2: h - bottom + 2 }, gg); T(t + '%', { x: sx(t), y: h - 6, 'text-anchor': 'middle', class: 'muted' }, svg); });
      S('line', { class: 'ref', x1: sx(T23.all[3]), x2: sx(T23.all[3]), y1: top - 4, y2: h - bottom + 2 }, svg);
      let y = top;
      groups.forEach(([g, rows]) => {
        T(g, { x: 0, y: y + 15, class: 'grp' }, svg); y += gh;
        rows.forEach(r => {
          const by = y + (rowH - barH) / 2;
          T(fit(r[0], lw - 2), { x: lw, y: by + barH / 2 + 4, 'text-anchor': 'end' }, svg);
          S('path', { d: hbarPath(x0, by, sx(r[3]) - x0, barH), fill: 'var(--s1)' }, svg);
          T(fmt1(r[3]) + '%', { x: sx(r[3]) + 5, y: by + barH / 2 + 4, class: 'val' }, svg);
          bind(S('rect', { class: 'hit', x: x0, y: y, width: x1 - x0 + valW, height: rowH }, svg), [{ v: fmt1(r[3]) + '%', l: r[0] + ' · ' + fmt0(r[2]) + ' of ' + fmt0(r[1]) + ' pass', c: 'var(--s1)' }]);
          y += rowH;
        });
      });
      const rl ='overall ' + fmt1(T23.all[3]) + '%';
      T(rl, { x: Math.min(sx(T23.all[3]), w - measure([rl], 11.5) / 2 - 2), y: 10, 'text-anchor': 'middle', class: 'muted' }, svg);
      const u = document.createElement('div'); u.className = 'unit'; u.textContent = 'Conversation-level sanity pass rate over the ' + fmt0(REACHED) + ' that reach the gate'; c.appendChild(u);
    };
    el('p', 'cap', 'Most drops come down to the responder. The seed set matters much less, and cross-lingual conversations pass slightly less often.', rd);
    // Source: paper Section 4, App. G.1, Table 23
    return draw;
  }

  /* ---------- stage 7: release ---------- */
  const COMP = [
    { v: 'seed', l: 'Seed set', src: 'Table 3', cap: 'WildChat supplies 58% of the release. Pass rates are close across seed sets (77–82%).' },
    { v: 'personaSet', l: 'Persona set', src: 'Table 3', cap: 'Cross-lingual conversations pass the gate less often (75.2% vs 82.3%) and are kept anyway.' },
    { v: 'responder', l: 'Responder', src: 'Table 3', cap: 'Ministral answers in high-resource cross-lingual conversations were regenerated with Gemma and ship under Gemma.' },
    { v: 'tier', l: 'Match tier', src: 'Table 3', cap: 'Location, embedding and language pool are the language-matched cascade. Cross-lingual is the separate mode.' },
    { v: 'turns', l: 'User turns', src: 'Table 3', cap: fmt0(TURNS) + ' user turns, 1.93 per conversation.' },
    { v: 'regions', l: 'Macro-region', src: 'Fig. 26b', cap: 'Top 10 of 13 persona macro-regions. UltraChat and Nemotron supply most Western European and North American conversations.' }
  ];
  let comp = 'seed';
  function s7(animate){
    head(7, 'Release', 'Conversations that pass the gate are deduplicated before release.');
    const steps = el('ol', 'steps', null, piece);
    [['Deduplicate', 'Repeated conversations are removed.']].forEach(([k, v]) => { const li = el('li', null, null, steps); el('b', null, k, li); el('span', null, v, li); });
    fade([...steps.children], animate);
    big([[fmt0(RELEASED), 'conversations, ' + fmt0(PASSED - RELEASED) + ' fewer than passed the gate'], [fmt0(TURNS), 'user turns, 1.93 per conversation']], piece);
    const seg = el('div', 'seg', null, rd); seg.id = 'cCompSeg'; seg.setAttribute('role', 'group'); seg.setAttribute('aria-label', 'Breakdown');
    COMP.forEach(o => { const b = el('button', null, o.l, seg); b.type = 'button'; b.dataset.v = o.v; b.setAttribute('aria-pressed', o.v === comp); });
    const c = block('', '', rd);
    const cap = el('p', 'cap', null, rd);
    const det = el('details', 'tbl', null, rd); el('summary', null, 'Data table', det); const tw = el('div', 'tblwrap', null, det);
    function draw(){
      const o = COMP.find(x => x.v === comp);
      const hd = c.parentNode.querySelector('.rh');
      hd.firstChild.textContent = o.v === 'regions' ? 'Persona macro-regions, top 10' : 'Released conversations by ' + o.l.toLowerCase();
      hd.lastChild.textContent = o.src;
      cap.textContent = o.cap;
      if (o.v === 'regions'){
        hbars(c, { rows: C.regions.map(r => ({ label: r[0], values: [r[1]] })), series: [{ name: 'conversations', color: 'var(--s1)' }], fmt: compact, ticks: false, barH: 12, unit: 'Released conversations' });
        table(tw, ['Macro-region', 'Released'], C.regions.map(r => [r[0], fmt0(r[1])]), [1]);
        return;
      }
      const rows = C[o.v], pass = rows[0].length > 3;
      hbars(c, { rows: rows.map(r => ({ label: r[0], values: pass ? [r[2], r[3]] : [r[2]], tip: () => [{ l: fmt0(r[1]) + ' conversations released' }] })), series: pass ? [{ name: 'Share of release', color: 'var(--q4)' }, { name: 'Sanity pass rate', color: 'var(--q2)' }] : [{ name: 'Share of release', color: 'var(--s1)' }], max: 100, ticks: [0, 25, 50, 75, 100], barH: 13, unit: pass ? 'Share of released conversations and conversation-level sanity pass rate, %' : '% of released conversations' });
      table(tw, pass ? ['Slice', 'Released', 'Share %', 'Pass %'] : ['Slice', 'Released', 'Share %'], rows.map(r => pass ? [r[0], fmt0(r[1]), fmt1(r[2]), fmt1(r[3])] : [r[0], fmt0(r[1]), fmt1(r[2])]), pass ? [1, 2, 3] : [1, 2]);
    }
    segCtl('#cCompSeg', v => { comp = v; draw(); });
    // Source: paper Section 6, App. G.1, Table 3, Table 23
    return draw;
  }

  const STAGES = [s1, s2, s3, s4, s5, s6, s7];
  function render(s, animate){
    cur = s; running = !!animate;
    tokTimers.forEach(clearTimeout); tokTimers = [];
    piece.replaceChildren(); rd.replaceChildren();
    root.dataset.stage = s;
    redraw = STAGES[s](animate);
    redraw();
    paintFlow();
  }
  const line = lineCtl(root, { count: 7, render, dur: s => s === 2 ? 2900 : s === 4 ? 2300 : 2000, onStop: () => { running = false; paintFlow(); } });
  reg(() => { drawFlow(); if (redraw) redraw(); });
})();
