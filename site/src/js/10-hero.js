/* Hero: the factory floor. Two serpentine lines in one SVG.
   Line A (left → right): seed cell → background → style → judge → persona bank.
   Line B (right → left): the bank's personas meet seed logs → match → rewrite → regenerate → sanity gate → corpus.
   Every persona and prompt on the belts is a real record from the released dataset (swiss-ai/PersonaFactory). */
const PERSONAS = [
  { id: 'fl', who: '27 · M · Florida, US', job: 'Freight train operations lead', style: 'fixin’ to · we · no final period' },
  { id: 'zh', who: '35 · M · Zurich, CH', job: 'Pediatric speech therapist', style: '?? · oder? · okay?' },
  { id: 'ge', who: '52 · F · Geneva, CH', job: 'Regional courier supervisor', style: 'Salut · stp · n’avons' },
  { id: 'sk', who: '36 · M · Bratislava, SK', job: 'Finance transformation consultant', style: 'No, … · Dúfam na pomoc. Čau.' },
  { id: 'ua', who: '35 · M · Zaporizhzhia, UA', job: 'Business insurance specialist', style: 'no final period · ладно' },
  { id: 'vi', who: '35 · F · Ho Chi Minh City, VN', job: 'Senior payroll analyst', style: 'nè · Cảm ơn nhé :)' }
];
// seed prompt → augmented first turn, from the released chats subset (seed dataset in src)
const CONVS = [
  { ini: 'FL', who: 'Florida persona', tier: 'embedding', src: 'UltraChat', seed: 'What are some essential items that someone should pack for a camping trip…', aug: 'We fixin\' to head out and need to know what the essential items are for a camping trip…' },
  { ini: 'ZH', who: 'Zurich persona', tier: 'cross-lingual', src: 'UltraChat', seed: 'Can you explain the mechanisms behind various sleep disorders…', aug: 'Chasch mer erkläre, wie s\' mit dene verschiedene Schlafstörige funktioniert… ?? okay?' },
  { ini: 'GE', who: 'Geneva persona', tier: 'cross-lingual', src: 'Nemotron', seed: 'I keep running into a query timeout error in our database layer…', aug: 'Salut, j\'ai systématiquement une erreur de timeout de requête…' },
  { ini: 'BA', who: 'Bratislava persona', tier: 'cross-lingual', src: 'Nemotron', seed: 'I’m launching a television network dedicated entirely to animated shows…', aug: 'Ahoj, spúšťam TV stanicu s focusom na animované seriály…' },
  { ini: 'ZP', who: 'Zaporizhzhia persona', tier: 'cross-lingual', src: 'Nemotron', seed: 'I have two tables in a SQL database: `People` with columns…', aug: 'маю дві таблиці в sql: `People` з колонками…' },
  { ini: 'VN', who: 'Ho Chi Minh City persona', tier: 'cross-lingual', src: 'UltraChat', seed: 'How can data analytics be used to improve public health outcomes…', aug: 'Làm thế nào nè để sử dụng phân tích dữ liệu…' }
];

(function factory(){
  const svg = $('#factory');
  const CW = 196, CH = 64, PITCH = 220, N = 4, LOOP = PITCH * N, SPEED = 0.05;
  const defs = S('defs', {}, svg);
  const mk = S('marker', { id: 'arr', viewBox: '0 0 10 10', refX: 5, refY: 5, markerWidth: 6, markerHeight: 6, orient: 'auto-start-reverse' }, defs);
  S('path', { d: 'M0,0 L10,5 L0,10 z', fill: 'var(--pf)' }, mk);
  const bg = S('g', {}, svg);
  const label = (txt, x, y) => T(txt, { x, y, style: 'font:600 11px var(--f-mono);letter-spacing:.08em;fill:var(--machine-ink)' }, bg);
  const box = (x, y, w, h, l1, l2) => {
    S('rect', { x, y, width: w, height: h, rx: 6, fill: 'var(--surface)' }, bg);
    T(fit(l1, w - 24, 13), { x: x + 12, y: y + 20, style: 'font:600 13px var(--f-sans);fill:var(--ink)' }, bg);
    T(fit(l2, w - 24, 10.5), { x: x + 12, y: y + 37, style: 'font:10.5px var(--f-sans);fill:var(--faint)' }, bg);
  };
  const store = (x, y, title, value, sub, w = 136, vs = 26) => {
    for (let k = 4; k >= 0; k--) S('rect', { x: x + k * 3.5, y: y + k * 4, width: w, height: 86, rx: 6, fill: 'var(--surface)', stroke: 'var(--pf)', 'stroke-width': 1.2 }, bg);
    T(title, { x: x + 12, y: y + 26, style: 'font:800 14px var(--f-display);letter-spacing:-.02em;fill:var(--ink)' }, bg);
    T(value, { x: x + 12, y: y + 58, style: `font:800 ${vs}px var(--f-display);letter-spacing:-.04em;fill:var(--pf)` }, bg);
    T(fit(sub, w - 24, 11), { x: x + 12, y: y + 76, style: 'font:11px var(--f-sans);fill:var(--faint)' }, bg);
  };
  const pipe = (d, arrow = true) => S('path', { d, fill: 'none', stroke: 'var(--pf)', 'stroke-width': 1.5, 'marker-end': arrow ? 'url(#arr)' : null }, bg);
  const feed = d => S('path', { d, fill: 'none', stroke: 'var(--faint)', 'stroke-width': 1.2, 'stroke-dasharray': '3 4' }, bg);

  function line(cfg){
    const { beltY, x0, x1, dir, stations, items, stageOf, rejectEvery, rejectLabel } = cfg;
    const g = S('g', {}, svg);
    S('rect', { x: x0, y: beltY, width: x1 - x0, height: 16, rx: 8, fill: 'var(--belt)' }, g);
    const dash = S('line', { x1: x0 + 8, x2: x1 - 8, y1: beltY + 8, y2: beltY + 8, stroke: 'var(--belt-2)', 'stroke-width': 3, 'stroke-dasharray': '10 12' }, g);
    for (let x = x0 + 14; x < x1; x += 64) S('circle', { cx: x, cy: beltY + 8, r: 3.5, fill: 'var(--belt-2)' }, g);
    S('rect', { x: x0 + 20, y: beltY + 16, width: 6, height: 34, fill: 'var(--belt)' }, g);
    S('rect', { x: x1 - 26, y: beltY + 16, width: 6, height: 34, fill: 'var(--belt)' }, g);
    const top = beltY - 226, presses = [];
    stations.forEach(s => {
      const x = s.cx - s.w / 2;
      S('rect', { x, y: top, width: s.w, height: 86, rx: 6, fill: s.dark ? 'var(--ink)' : 'var(--surface)' }, g);
      S('rect', { x, y: top, width: s.w, height: 5, rx: 2, fill: 'var(--machine)' }, g);
      T(s.k, { x: x + 14, y: top + 34, style: `font:800 19px var(--f-display);letter-spacing:-.02em;fill:${s.dark ? 'var(--paper)' : 'var(--ink)'}` }, g);
      T(fit(s.s1, s.w - 28, 11), { x: x + 14, y: top + 56, style: `font:11px var(--f-sans);fill:${s.dark ? 'var(--paper)' : 'var(--ink-2)'}` }, g);
      T(fit(s.s2, s.w - 28, 11), { x: x + 14, y: top + 72, style: `font:11px var(--f-sans);fill:${s.dark ? 'var(--paper)' : 'var(--ink-2)'};opacity:.8` }, g);
      S('rect', { x: s.cx - 3, y: top + 86, width: 6, height: 52, fill: 'var(--ink-2)' }, g);
      presses.push(S('rect', { x: s.cx - 24, y: top + 136, width: 48, height: 8, rx: 2, fill: 'var(--ink-2)' }, g));
    });
    // rejected cards drop off the belt just after the last station
    const last = stations[stations.length - 1];
    const jx = last.cx + dir * 46;
    const lx = dir > 0 ? jx + 34 : jx + 14;
    if (rejectLabel) T(rejectLabel[0], { x: lx, y: beltY + 44, 'text-anchor': 'start', style: 'font:600 11px var(--f-sans);fill:var(--ink-2)' }, g);
    if (rejectLabel) T(rejectLabel[1], { x: lx, y: beltY + 59, 'text-anchor': 'start', style: 'font:11px var(--f-sans);fill:var(--faint)' }, g);

    const START = dir > 0 ? x0 + 8 : x1 - 8 - CW;
    const SPAN = dir > 0 ? (x1 - 30 - CW) - START : START - (x0 + 30);
    const cardsG = S('g', {}, svg);
    const cards = [];
    for (let i = 0; i < N; i++){
      const c = S('g', {}, cardsG);
      const rect = S('rect', { width: CW, height: CH, rx: 6, fill: 'var(--surface)', stroke: 'var(--rule-2)', 'stroke-width': 1.2 }, c);
      // icon: an unformed outline at the seed, a person once it has a background, accent once it has a style
      const ib = S('rect', { x: 8, y: 8, width: 28, height: 28, rx: 5 }, c);
      const person = S('g', {}, c);
      S('circle', { cx: 22, cy: 18.5, r: 4.8 }, person);
      S('path', { d: 'M13 34.6c0-5.4 4-8.6 9-8.6s9 3.2 9 8.6z' }, person);
      const bubble = S('path', { d: 'M14.5 14.5h15a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-8.5l-4.5 3.6v-3.6h-2a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2z', fill: 'none', stroke: 'var(--faint)', 'stroke-width': 1.4 }, c);
      const badge = S('g', { opacity: 0 }, c);
      S('circle', { cx: 35, cy: 9.5, r: 6.2, fill: 'var(--good)', stroke: 'var(--surface)', 'stroke-width': 1.6 }, badge);
      S('path', { d: 'M32.2 9.7l1.9 1.9 3.5-3.7', fill: 'none', stroke: 'var(--on-strong)', 'stroke-width': 1.5, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, badge);
      const ini = { ib, person, bubble, badge };
      c.style.cursor = cfg.onPick ? 'pointer' : '';
      const l1 = T('', { x: 44, y: 19, style: 'font:600 11px var(--f-sans);fill:var(--ink)' }, c);
      const l2 = T('', { x: 44, y: 33, style: 'font:10.5px var(--f-sans);fill:var(--faint)' }, c);
      const l3 = T('', { x: 9, y: 54, style: 'font:500 10px var(--f-mono);fill:var(--pf)' }, c);
      const stamp = S('g', { opacity: 0 }, c);
      S('rect', { x: CW - 42, y: 41, width: 36, height: 16, rx: 3, fill: 'none', stroke: 'var(--good)', 'stroke-width': 1.5, transform: `rotate(-8 ${CW - 24} 49)` }, stamp);
      T('PASS', { x: CW - 24, y: 53, 'text-anchor': 'middle', transform: `rotate(-8 ${CW - 24} 49)`, style: 'font:700 9.5px var(--f-mono);fill:var(--good);letter-spacing:.06em' }, stamp);
      const tag = S('g', { opacity: 0 }, c);   // marks the card the spec sheet is following
      S('rect', { x: 0, y: -13, width: 64, height: 13, rx: 2, fill: 'var(--machine)' }, tag);
      T('SPEC SHEET', { x: 6, y: -3.4, style: 'font:700 8.5px var(--f-mono);letter-spacing:.08em;fill:var(--paper)' }, tag);
      const card = { g: c, rect, ini, l1, l2, l3, stamp, tag, p: 0, item: i, reject: false, dy: 0, st: -1 };
      if (cfg.onPick) c.addEventListener('click', () => cfg.onPick(card));
      cards.push(card);
    }
    const xOf = c => START + dir * c.p;
    function fitEl(el, txt, maxW){
      el.textContent = txt;
      if (!txt) return;
      try {
        if (el.getComputedTextLength() <= maxW) return;
        let t = txt;
        while (t.length > 3){ t = t.slice(0, -1); el.textContent = t.trimEnd() + '…'; if (el.getComputedTextLength() <= maxW) return; }
      } catch (e){ el.textContent = fit(txt, maxW, 11); }
    }
    // the web fonts can arrive after the first frame: refit every card once they are in
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => cards.forEach(c => { c.st = -1; setStage(c); }));
    function setStage(c){
      const cx = xOf(c) + CW / 2;
      const st = stations.filter(s => dir > 0 ? cx >= s.cx : cx <= s.cx).length;
      if (c.st === st) return;
      c.st = st;
      const v = stageOf(items[c.item % items.length], st);
      const I = c.ini, set = (el, a) => Object.entries(a).forEach(([k, val]) => val == null ? el.removeAttribute(k) : el.setAttribute(k, val));
      const look = v.icon;   // 'seed' | 'chat' | 'bg' | 'style'
      set(I.ib, look === 'seed' ? { fill: 'none', stroke: 'var(--faint)', 'stroke-width': 1.2, 'stroke-dasharray': '3 3' }
              : look === 'chat' ? { fill: 'none', stroke: 'var(--rule-2)', 'stroke-width': 1.2, 'stroke-dasharray': null }
              : { fill: look === 'style' ? 'var(--pf)' : 'var(--ink)', stroke: null, 'stroke-dasharray': null });
      I.person.setAttribute('opacity', look === 'chat' ? 0 : 1);
      set(I.person, look === 'seed' ? { fill: 'none', stroke: 'var(--faint)', 'stroke-width': 1.2, 'stroke-dasharray': '2 2' } : { fill: 'var(--paper)', stroke: null, 'stroke-dasharray': null });
      I.bubble.setAttribute('opacity', look === 'chat' ? 1 : 0);
      I.badge.setAttribute('opacity', v.badge && !c.reject ? 1 : 0);
      const done = st >= stations.length;
      // fit each line to the card with its real rendered font (the style line is monospace and wider than the body
      // font), and keep the style line clear of the PASS stamp once the card is through
      fitEl(c.l1, v.l1, CW - 52); fitEl(c.l2, v.l2, CW - 52); fitEl(c.l3, v.l3 || '', done && !c.reject ? CW - 60 : CW - 18);
      c.rect.setAttribute('stroke', done && !c.reject ? 'var(--good)' : v.ready ? 'var(--pf)' : 'var(--rule-2)');
      c.stamp.setAttribute('opacity', done && !c.reject ? 1 : 0);
      if (cfg.onStage) cfg.onStage(c, st);
    }
    function place(c, press){
      const x = xOf(c);
      let dy = 0;
      if (press) stations.forEach(s => { const d = Math.abs(x + CW / 2 - s.cx); if (d < 26) dy = (26 - d) / 26 * 4; });
      const op = Math.max(0, Math.min(c.p / 30 + 0.001, (SPAN + 40 - c.p) / 40, 1 - c.dy / 60, 1));
      c.g.setAttribute('opacity', c.p > SPAN + 40 ? 0 : op.toFixed(2));
      c.g.setAttribute('transform', `translate(${x.toFixed(1)},${(beltY - CH - 2 + dy + c.dy).toFixed(1)})`);
    }
    let next = N, off = 0;
    // resting frame: cards one pitch apart, each just past a station
    cards.forEach((c, i) => { const s0 = stations[0].cx - CW / 2 + dir * 30; c.p = (s0 - START) * dir + (N - 2 - i) * PITCH; c.item = i; c.reject = false; setStage(c); place(c, false); });
    const tick = function(dt){
      off -= dir * dt * SPEED; dash.setAttribute('stroke-dashoffset', off.toFixed(1));
      cards.forEach(c => {
        c.p += dt * SPEED;
        const cx = xOf(c) + CW / 2;
        if (c.reject && (dir > 0 ? cx > last.cx + 40 : cx < last.cx - 40)) c.dy += dt * 0.12;
        if (c.p > LOOP || c.dy > 60){ c.p -= LOOP; c.item = next++; c.dy = 0; c.reject = c.item % rejectEvery === rejectEvery - 2; c.st = -1; if (cfg.onRecycle) cfg.onRecycle(c); }
        setStage(c); place(c, true);
      });
      presses.forEach((pr, i) => pr.setAttribute('transform', cards.some(c => Math.abs(xOf(c) + CW / 2 - stations[i].cx) < 26) ? 'translate(0,6)' : ''));
    };
    tick.cards = cards; tick.items = items; tick.span = SPAN;
    return tick;
  }

  let tracked = null;   // the card the spec sheet follows
  /* ---- line A: build personas ----
     Seed grid, judge keep rate (95.5%) and 4.5% rejected: Section 3 and Appendix A, Table 4. */
  label('SEED GRID', 18, 22);
  [['177 countries', '599 sub-regions'], ['575 occupations', '23 sectors'], ['3 generators', 'Gemma · Ministral · GLM']].forEach((h, i) => {
    const y = 32 + i * 58; box(16, y, 180, 48, h[0], h[1]);
    feed(`M196 ${y + 24} C 230 ${y + 24}, 214 212, 246 212`);
  });
  store(958, 30, 'PERSONA BANK', D.headline.personas.toLocaleString('en-US'), 'profiles released');
  const tickA = line({
    beltY: 252, x0: 214, x1: 1018, dir: 1,
    stations: [
      { cx: 384, w: 186, k: 'BACKGROUND', s1: 'age · region · job', s2: 'language · AI stance' },
      { cx: 604, w: 186, k: 'STYLE', s1: 'caps · punctuation · emoji', s2: 'typos · quirks · example' },
      { cx: 824, w: 186, k: 'JUDGE', s1: 'MiniMax-M2.5', s2: 'out-of-family, 95.5% kept', dark: true }
    ],
    items: PERSONAS, rejectEvery: 9, rejectLabel: null,
    stageOf: (P, st) => ({ icon: st >= 2 ? 'style' : st >= 1 ? 'bg' : 'seed', badge: st >= 3, l1: st >= 1 ? P.who : 'seed cell', l2: st >= 1 ? P.job : P.who.split('·').pop().trim(), l3: st >= 2 ? P.style : '', ready: st >= 2 }),
    onStage: (c, st) => { if (c === tracked) spec(c, st); },
    onRecycle: c => { if (c === tracked) follow(newest()); },
    onPick: c => follow(c)
  });
  pipe('M1012 248 V 124');

  /* ---- line B: augment conversations ----
     Sanity pass 78.9% (21.1% fail) of 1,606,837 that reached the gate: Section 6, Table 3 and Appendix G.1, Table 24. */
  label('SEED LOGS', 1000, 330);
  box(998, 338, 110, 48, 'Chat logs', '3 open datasets');
  feed('M1053 386 V 470 C 1053 520, 1060 550, 1058 572');
  // personas leave the bank and drop down to the matcher
  pipe('M1098 124 C 1114 124, 1114 160, 1114 200 V 404 C 1114 420, 1100 420, 1040 420');
  T('personas', { x: 1105, y: 240, transform: 'rotate(90 1105 240)', 'text-anchor': 'middle', style: 'font:600 10.5px var(--f-mono);letter-spacing:.06em;fill:var(--pf)' }, bg);
  // released corpus after dedup and final filters (Section 6, Table 3): 1,237,976
  store(14, 380, 'CORPUS', D.headline.conversations.toLocaleString('en-US'), 'conversations', 152, 21);
  const tickB = line({
    beltY: 602, x0: 108, x1: 1078, dir: -1,
    stations: [
      { cx: 940, w: 176, k: 'MATCH', s1: 'language-matched or', s2: 'cross-lingual persona' },
      { cx: 726, w: 176, k: 'REWRITE', s1: 'user turns re-voiced', s2: 'request held fixed' },
      { cx: 512, w: 176, k: 'REGENERATE', s1: 'assistant turns', s2: 'continuity judge' },
      { cx: 298, w: 176, k: 'SANITY GATE', s1: 'six failure classes', s2: '78.9% pass', dark: true }
    ],
    items: CONVS, rejectEvery: 5, rejectLabel: null,
    stageOf: (C, st) => ({
      icon: st >= 2 ? 'style' : st >= 1 ? 'bg' : 'chat', badge: st >= 4,
      l1: st >= 1 ? `${C.who} · ${C.tier}` : `seed prompt · ${C.src}`,
      l2: st >= 2 ? C.aug : C.seed,
      l3: st >= 3 ? 'reply regenerated' : st >= 2 ? 'rewritten in persona voice' : '',
      ready: st >= 2
    })
  });
  pipe('M124 598 V 490');

  /* ---- persona spec sheet: follows one card on line A and fills in station by station ---- */
  const sheet = $('#pspec');
  const newest = () => tickA.cards.filter(c => !c.reject).reduce((a, c) => (c.p < a.p ? c : a));
  const rec = c => { const P = PERSONAS[c.item % PERSONAS.length]; return (window.PF_PERSONAS || []).find(r => r.id === P.id); };
  const esc = v => String(v).replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[ch]);
  const short = v => { v = Array.isArray(v) ? v[0] : v; v = String(v).replace(/^“|”$/g, ''); return v.length > 96 ? v.slice(0, 94).replace(/\s+\S*$/, '') + '…' : v; };
  const pick = (rows, keys, n) => keys.map(k => rows.find(r => r[0] === k)).filter(Boolean).slice(0, n);
  function spec(c, st){
    if (!sheet) return;
    const R = rec(c), P = PERSONAS[c.item % PERSONAS.length];
    if (!R) { setTimeout(() => { if (c === tracked) spec(c, c.st); }, 60); return; }   // bank records load with a later script
    $('#psHead', sheet).textContent = R.head;
    $('#psFig', sheet).textContent = '';
    const cols = [
      [['Region', R.seed.region], R.seed.occ ? ['Occupation', R.seed.occ] : ['Sector', R.seed.sector], ['Generator', 'one of three open models']],
      pick(R.bg, ['Age', 'Gender', 'Job title', 'Language', 'AI stance', 'Education'], 4),
      pick(R.st, ['Capitalization', 'Emoji', 'Code-switching', 'Quirks', 'Example message'], 3),
      [['Checks', 'coherence · location and user plausibility · stereotype safety'], ['Judge', 'MiniMax-M2.5, out of family'], ['Outcome', 'released in the bank']]
    ];
    $$('.pspec-col', sheet).forEach((col, i) => {
      const on = st >= i, was = col.dataset.on === '1';
      col.dataset.on = on ? '1' : '0';
      col.classList.toggle('on', on);
      col.classList.toggle('flash', on && !was && !reduce);
      $('dl', col).innerHTML = cols[i].map(([k, v]) => `<dt>${esc(k)}</dt><dd>${on ? esc(short(v)) : '<span class="pend"></span>'}</dd>`).join('');
    });
    const done = st >= 3;
    sheet.classList.toggle('done', done);
    $('#psState', sheet).textContent = done ? 'Filed in the bank' : st === 0 ? 'Seed cell drawn, waiting for the background station' : st === 1 ? 'Background added, waiting for the style station' : 'Style added, waiting for the judge';
  }
  function follow(c){
    if (tracked) tracked.tag.setAttribute('opacity', 0);
    tracked = c; c.tag.setAttribute('opacity', 1);
    spec(c, c.st);
  }
  // The sheet refills as cards move. Its height must not change, or everything below it jumps while the
  // reader is further down the page: reserve the height of the tallest fully filled persona.
  const colsEl = sheet && $('.pspec-cols', sheet);
  function lock(){
    if (!colsEl || !window.PF_PERSONAS) return false;
    colsEl.style.minHeight = '';
    let m = 0;
    PERSONAS.forEach((_, i) => { spec({ item: i }, 3); m = Math.max(m, colsEl.offsetHeight); });
    colsEl.style.minHeight = m + 'px';
    if (tracked) spec(tracked, tracked.st);
    return true;
  }
  (function tryLock(){ if (!lock()) setTimeout(tryLock, 60); })();
  let lockT = 0, lockW = innerWidth;
  addEventListener('resize', () => { if (innerWidth === lockW) return; lockW = innerWidth; clearTimeout(lockT); lockT = setTimeout(lock, 150); });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => lock());
  // at rest, follow the card furthest along that has not been rejected
  follow(tickA.cards.filter(c => !c.reject && c.p <= tickA.span).reduce((a, c) => (c.p > a.p ? c : a)));
  const nx = $('#psNext');
  if (nx) nx.addEventListener('click', () => {
    const order = tickA.cards.filter(c => c.p <= tickA.span + 20).sort((a, b) => b.p - a.p);
    follow(order[(order.indexOf(tracked) + 1) % order.length]);
  });

  let paused = reduce, last = 0;
  function frame(t){
    const dt = last ? Math.min(50, t - last) : 16; last = t;
    if (!paused){ tickA(dt); tickB(dt); }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  const pb = $('#factoryPause');
  const sync = () => { pb.setAttribute('aria-pressed', paused ? 'true' : 'false'); pb.textContent = paused ? 'Play' : 'Pause'; };
  sync();
  pb.addEventListener('click', () => { paused = !paused; sync(); });
})();
