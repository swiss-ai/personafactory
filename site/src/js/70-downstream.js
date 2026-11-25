/* ======================= ASSISTANT LINE + TRAINING BAY ======================= */
// Paper numbers and prompt text used here that are not in data.js (all from Appendix G.2 unless noted).
const DSX = {
  styleN: 234723,                       // Table 25 caption: released corpus with a model persona, n = 234,723 conversations
  structure: [                          // Table 25 "Structure" column, same order as D.assistantStyles
    'conversational prose', 'prose', 'flowing prose', 'tight bullets or one short paragraph',
    'labeled parts (established, assumptions, how to check)', 'paragraphs with topic sentences',
    'short headers, numbered steps, tables where comparisons appear', 'short paragraphs, occasional simple bullets',
    'short paragraphs or numbered steps', 'snappy bullets and short code snippets', 'short paragraphs and action lists',
    'short prose paragraphs'
  ],
  axes: ['register', 'structure', 'density', 'warmth', 'explanation', 'jargon', 'certainty', 'emoji'], // Section 6 / G.2
  touchShare: 25.0,                     // G.2: signature touch offered with p = 0.25, 25.0% of released assistant turns
  names: { without: 68.8, with: 66.4, fitLo: 47.6, fitHi: 50.8, redone: 52 }, // G.2 "Style set": names removed from prompts
  matchVsRandom: [60.0, 39.9],          // G.2 design pilots: pairwise fit, matched vs random style
  matchVsUser: [49.7, 50.1],            // G.2 design pilots: matched style vs user-persona-only reply
  design: { convs: 604, turns: 1489, instr: 94 },          // Table 26 caption / text
  pilot: { convs: 1000, noise: 59.6, pair: [['the default', 61, 39], ['model persona only', 58, 41], ['user persona only', 49, 51]] }, // Table 27 caption / text
  noUser: { convs: 1000, turns: 2570, fallback: 35 },      // Table 31 text
  sysPrompt: { n: 200, rows: [['No style', 86], ['Style placed below the system prompt', 58], ['System prompt placed last, as an override', 66]] }, // G.2 text after Table 31
  train: { perArm: '100k', lr: '1e-5', batch: 128, requests: 300, voices: 12 }, // G.2 downstream ablation
  pairN: 'about 3,500',                 // Table 30 caption: decisive comparisons per pair
  contractions: [1.75, 0.92, 0.47, 0.95, 0.71, 0.52, 0.96], // Table 29 "Contractions / 100 words", row order of D.finetune.rows
  // Appendix G.3, downstream fine-tuning on the released corpus (tables are D.corpusFT)
  corpus: { convs: 79817, xConvs: 40528, heldOut: 5, maxTok: 3800, seq: 4096, wild: 1000, keep: 99.6, sd: 1.6, requests: 300, voices: 12 }, // G.3 Setup / Evaluation, Table 32-34 captions
  seeds: { a2a1: [5.7, 1.9, 9.6], a2a0r: [4.6, 1.1, 8.2], a1a0: [-3.8, -6.7, -0.9], a2a1Judge: [57.3, 60.0], a2a0Judge: [54.6, 57.5] }, // G.3 Results: over three training seeds
  strict: { ifeval: [0.3, -2.2, 2.8], judge: [53.8, 57.4] },  // G.3 "Strict subset"
  crossLC: { muse: [52.1, 48.0, 55.9], qwen: [44.3, 40.7, 47.9] } // G.3 "Cross-lingual conversations": WildChat LC win rate of X2
};
// The Florida persona from Assembly, used to show what the matcher keeps.
const DS_CARD = {   // persona_bank 38c6bf98 (the Florida persona in Assembly) and its released conversation chats 74e8c8fd
  ini: 'FL', name: '27 · M · Florida, USA', blurb: 'Full profile in, reduced card out.',
  seen: [['AI stance', 'Pragmatic'], ['Digital fluency', 'Low'], ['Sentence length', 'Long/Elaborate'], ['Code-switching', 'Low: occasional Southernisms (‘fixin’ to’, ‘y’all’)']],
  keys: [['Capitalization', 'first-word-only'], ['Typo tendency', 'phonetic spelling'], ['Emoji', 'rare/functional']],
  withheld: [['Occupation', 'Train conductor, logistics & transport: freight train operations lead for a regional logistics carrier (handles mixed cargo)'], ['Gender', 'M'], ['Age', '27'], ['Location', 'North America → USA → Florida'], ['Languages', 'English (main / native) · dialect Central Florida'], ['Free-text style', 'Uses first-word capitalization, no final periods, treats digital devices like radios (‘can you *clear* that up for me’)…']],
  first: "We fixin' to head out and need to know what the essential items are for a camping trip and how we can prioritize that packing list based on the activity shedule"
};

(function downstream(){
  const line = $('#dsLine'), left = $('#dsLeft'), right = $('#dsRight');
  const E = (tag, cls, txt) => { const n = document.createElement(tag); if (cls) n.className = cls; if (txt != null) n.textContent = txt; return n; };
  const put = (p, ...kids) => { kids.forEach(k => { if (k != null && k !== false) p.appendChild(typeof k === 'string' ? document.createTextNode(k) : k); }); return p; };
  const srcTag = t => E('span', 'src', t);
  const head = (title, src) => put(E('div', 'rhd'), E('h4', 'rh', title), src ? srcTag(src) : null);
  const ph = t => E('div', 'ph', t);
  let draws = [];
  reg(() => draws.forEach(f => f()));
  const draw = f => { draws.push(f); f(); };
  let anim = false, delay = 0;
  // stagger pieces in while the line runs
  const step = (n, gap = 110) => { if (anim){ n.classList.add('in'); n.style.animationDelay = (delay += gap) + 'ms'; } return n; };

  // underline tabs built locally (several can exist across re-renders)
  function tabs(items, cur, onChange, label){
    const g = E('div', 'seg'); g.setAttribute('role', 'group'); g.setAttribute('aria-label', label);
    items.forEach(([v, l]) => { const b = E('button', null, l); b.type = 'button'; b.setAttribute('aria-pressed', v === cur ? 'true' : 'false');
      b.addEventListener('click', () => { $$('button', g).forEach(x => x.setAttribute('aria-pressed', x === b ? 'true' : 'false')); onChange(v); }); g.appendChild(b); });
    return g;
  }

  /* ---------- the bench: 7 models, one colour per arm ---------- */
  const ARM = { 'IT': 'var(--faint)', 'SFT A': 'var(--q2)', 'SFT B': 'var(--q3)', 'SFT C': 'var(--q4)' };
  const ARM_NAME = { 'IT': 'Llama-3.1-8B-Instruct', 'SFT A': 'A · no system prompt', 'SFT B': 'B · user persona', 'SFT C': 'C · user + model persona' };
  const benchLegend = () => legend(Object.keys(ARM).map(k => ({ name: k === 'IT' ? 'Instruct (no SFT)' : ARM_NAME[k], color: ARM[k] })));
  const FAMS = ['Llama-3.1-8B', 'Apertus-8B'];
  const stageLab = r => r.stage === 'IT' ? 'Instruct' : r.stage;
  function benchChart(el, { get, fmt, lo, hi, ticks, tfmt = String, what }){
    const rows = D.finetune.rows;
    const w = W(el);
    const lw = Math.ceil(measure(rows.map(stageLab))) + 10;
    const valW = Math.ceil(measure(rows.map(r => fmt(get(r))))) + 10;
    const rowH = 24, famH = 22, top = 2, bottom = 22;
    const h = top + FAMS.length * famH + rows.length * rowH + 8 + bottom;
    const x0 = lw + 6 + (lo < 0 ? valW : 0), x1 = w - (hi > 0 ? valW : 16);
    const sx = v => x0 + (x1 - x0) * (v - lo) / (hi - lo);
    const svg = svgFor(el, w, h);
    const yEnd = h - bottom;
    const g = S('g', { class: 'grid' }, svg);
    ticks.forEach(t => { S('line', { x1: sx(t), x2: sx(t), y1: top, y2: yEnd }, g); T(tfmt(t), { x: sx(t), y: h - 6, 'text-anchor': 'middle', class: 'muted' }, svg); });
    if (lo < 0) S('line', { class: 'axis', x1: sx(0), x2: sx(0), y1: top, y2: yEnd }, svg);
    let y = top;
    FAMS.forEach((fm, fi) => {
      if (fi) y += 8;
      T(fm, { x: 0, y: y + 15, class: 'fam' }, svg);
      y += famH;
      rows.forEach((r, i) => {
        if (r.fam !== fm) return;
        const v = get(r), c = ARM[r.stage];
        T(stageLab(r), { x: lw, y: y + rowH / 2 + 4, 'text-anchor': 'end', class: 'muted' }, svg);
        const a = sx(Math.min(0, v)), b = sx(Math.max(0, v)), bh = rowH - 8;
        if (v < 0){ const r4 = Math.min(4, (b - a) / 2); S('path', { d: `M${b},${y + 4}H${a + r4}Q${a},${y + 4} ${a},${y + 4 + r4}V${y + 4 + bh - r4}Q${a},${y + 4 + bh} ${a + r4},${y + 4 + bh}H${b}Z`, fill: c }, svg); }
        else S('path', { d: hbarPath(a, y + 4, b - a, bh), fill: c }, svg);
        T(fmt(v), { x: v < 0 ? a - 5 : b + 5, y: y + rowH / 2 + 4, 'text-anchor': v < 0 ? 'end' : 'start', class: 'val' }, svg);
        const hit = S('rect', { class: 'hit', x: lw, y, width: w - lw, height: rowH }, svg);
        bind(hit, [{ c, v: fmt(v), l: `${fm} ${r.stage === 'IT' ? 'Instruct' : r.stage} · ${what}` }]);
        y += rowH;
      });
    });
    return svg;
  }
  function bench(finding, swatch = true){
    const wrap = E('div', 'bench' + (swatch ? '' : ' nosw'));
    put(wrap, ph('Models under test'));
    FAMS.forEach(fm => {
      const f = put(E('div', 'bfam'), E('b', null, fm));
      D.finetune.rows.filter(r => r.fam === fm).forEach(r => {
        const it = E('div', 'bm'); const sw = E('i'); if (swatch) sw.style.background = ARM[r.stage];
        put(it, sw, E('span', 'bk', stageLab(r)), E('span', 'bv', r.stage === 'IT' ? 'released instruct model, no SFT here' : ARM_NAME[r.stage].slice(4)));
        f.appendChild(it);
      });
      wrap.appendChild(step(f));
    });
    if (finding) wrap.appendChild(step(put(E('div', 'find'), E('span', 'fh', 'Finding'), E('p', null, finding))));
    wrap.appendChild(step(E('p', 'caveat', 'One seed per arm, a single judge (MiniMax-M2.5), no capability benchmarks in this ablation. The arms share the user side, so they compare assistant conditioning only.')));
    return wrap;
  }

  /* ---------- per-column bar matrix for the pilots (Tables 26, 27, 31) ---------- */
  function mtx({ cols, rows, best = [] }){
    const m = E('div', 'mtx'); m.style.setProperty('--n', cols.length);
    const hd = put(E('div', 'mrow head'), E('span', 'mlab', ''));
    cols.forEach(c => hd.appendChild(E('span', 'mh', c.l)));
    m.appendChild(hd);
    const bestV = {};
    best.forEach(k => { bestV[k] = Math.max(...rows.map(r => r.v[k]).filter(v => v != null)); });
    rows.forEach(r => {
      const row = put(E('div', 'mrow' + (r.rel ? ' rel' : '')), put(E('span', 'mlab', r.label), r.rel ? E('em', null, r.rel) : null));
      cols.forEach(c => {
        const v = r.v[c.k];
        const cell = put(E('div', 'mc'), E('span', 'mk', c.l));
        const val = E('span', 'mv' + (best.includes(c.k) && v === bestV[c.k] ? ' best' : ''), v == null ? (c.nul || 'n/a') : c.fmt(v));
        if (v == null) val.classList.add('na');
        const tr = E('span', 'mt'); const b = E('b'); b.style.width = v == null ? '0' : Math.max(1, 100 * v / c.max) + '%'; tr.appendChild(b);
        put(cell, val, tr);
        if (v != null) bind(cell, [{ v: c.fmt(v), l: r.label + ' · ' + c.l, c: 'var(--s1)' }]);
        row.appendChild(cell);
      });
      m.appendChild(step(row, 70));
    });
    return m;
  }
  const P = v => fmt1(v) + '%';

  /* ---------- stages ---------- */
  let pilotTab = 'design', ftTab = 'formality', rfTab = 'words';
  const ST = [];

  // 1 · reduced user card
  ST[0] = {
    how: 'Struck-out fields never reach the matcher. Values are from the Florida persona in Assembly.',
    src: 'Source: paper App. G.2 · released persona 38c6bf98 · App. B.1',
    left(){
      const c = DS_CARD;
      put(left, ph('Work piece · the Florida persona'));
      const who = put(E('div', 'who'), E('div', 'avatar', c.ini), put(E('div'), E('b', null, c.name), E('span', null, c.blurb)));
      left.appendChild(who);
      const field = ([k, v], cls) => { const d = put(E('div', 'rf ' + (cls || '')), E('span', 'rk', k), E('span', 'rv' + (v == null ? ' nv' : ''), v == null ? 'not given' : v)); return d; };
      const sees = put(E('div', 'grp see'), put(E('div', 'gh'), E('span', null, 'Matcher sees'), E('span', null, 'communication signals')));
      c.seen.forEach(f => sees.appendChild(field(f)));
      sees.appendChild(put(E('div', 'gsub'), 'Structured typing keys ', E('span', null, '(' + c.keys.length + ' of 7 shown)')));
      c.keys.forEach(f => sees.appendChild(field(f)));
      left.appendChild(sees);
      const wh = put(E('div', 'grp wh'), put(E('div', 'gh'), E('span', null, 'Withheld'), E('span', null, 'demographics and free text')));
      c.withheld.forEach((f, i) => {
        const d = field(f, 'cut');
        if (anim){ d.classList.remove('cut'); setTimeout(() => d.classList.add('cut'), 500 + i * 160); }
        d.setAttribute('aria-label', f[0] + ': withheld from the matcher');
        wh.appendChild(d);
      });
      left.appendChild(wh);
    },
    right(){
      put(right, head('What the matcher is given', 'App. B.1 matching prompt'));
      const pb = E('div', 'pbox');
      put(pb, step(E('div', 'pl', 'About the user (communication signals only):')));
      const chips = E('div', 'slots');
      ['AI stance', 'Digital fluency', 'Sentence length', 'Question framing', 'Code-switching', 'Typing keys'].forEach(k => chips.appendChild(E('span', 'slot', k)));
      pb.appendChild(step(chips));
      put(pb, step(E('div', 'pl', 'The user’s first message:')));
      const msg = put(E('div', 'msg user'), put(E('div', 'mh'), E('span', null, 'persona-augmented prompt')), E('div', null, DS_CARD.first));
      pb.appendChild(step(msg));
      put(pb, step(E('div', 'pl', 'Candidate response styles:')));
      pb.appendChild(step(E('div', 'pv', '12 styles, shuffled into a new order for every conversation')));
      right.appendChild(pb);
      right.appendChild(step(E('p', 'rnote', 'Occupation, gender, age, location and languages are withheld so the choice cannot rest on demographics. The free-text style is withheld too, because it often names a language or region.')));
    }
  };

  // 2 · style matching
  ST[1] = {
    how: `Bar length is each style’s share of the ${fmt0(DSX.styleN)} released conversations with a model persona. Hover a row for its structure.`,
    src: 'Source: paper Table 25 · App. G.2',
    left(){
      put(left, ph('Matcher · MiniMax-M2.5'));
      left.appendChild(step(put(E('blockquote', 'quote'), 'You choose the response style an AI assistant should use for a user, so that its answers are easy and pleasant for this particular user to read. Adapt to the user’s needs; do not mirror their typing (no copying typos or slang).', E('span', 'src', 'App. B.1, verbatim'))));
      const ol = E('ol', 'flow');
      [['Reduced card and first message in', 'demographics already removed'], ['12 candidate styles, shuffled', 'a new random order per conversation'], ['Top-ranked style kept', 'for every assistant turn of the conversation'], ['Nothing stored', 'neither the style nor the match is in the training example']].forEach(([a, b]) => ol.appendChild(step(put(E('li'), E('b', null, a), E('span', null, b)))));
      left.appendChild(ol);
      const n = DSX.names;
      left.appendChild(step(put(E('div', 'fact'), E('b', null, 'Style names never reach a prompt. '), `Removing them left adoption unchanged within noise (${fmt1(n.without)}% without, ${fmt1(n.with)}% with, 1,000-conversation pilot). ${n.redone} released conversations in which a reply named its own style were regenerated.`)));
    },
    right(){
      put(right, head('How often each style was matched', 'Table 25'));
      const list = E('div', 'slist');
      const mx = D.assistantStyles[0][3];
      D.assistantStyles.forEach((s, i) => {
        const r = put(E('div', 'sl'), E('span', 'sn', String(i + 1)), put(E('span', 'sd'), E('span', 'st', s[0]), E('span', 'sr', s[1])));
        const tr = E('span', 'sb'); const b = E('b'); b.style.width = (100 * s[3] / mx) + '%'; tr.appendChild(b);
        put(r, tr, E('span', 'sv', P(s[3])));
        bind(r, [{ v: P(s[3]), l: s[0], c: 'var(--s1)' }, { l: fmt0(s[2]) + ' conversations' }, { l: 'register: ' + s[1] }, { l: 'structure: ' + DSX.structure[i] }]);
        list.appendChild(step(r, 45));
      });
      right.appendChild(list);
      right.appendChild(E('div', 'unit', `% of ${fmt0(DSX.styleN)} conversations. The top two styles cover 43%, the rarest 1.5%.`));
      const pil = E('div', 'pilot');
      put(pil, put(E('div', 'mxt'), E('span', null, 'Does matching carry signal?'), srcTag('App. G.2 design pilot')));
      pil.appendChild(legend([{ name: 'Matched style', color: 'var(--s1)' }, { name: 'Random style', color: 'var(--s2)' }]));
      const [a, b] = DSX.matchVsRandom;
      const sp = E('div', 'split');
      [[a, 'var(--s1)', 'Matched style'], [b, 'var(--s2)', 'Random style']].forEach(([v, c, l]) => { const seg = E('span', null, fmt1(v)); seg.style.width = v + '%'; seg.style.background = c; bind(seg, [{ v: fmt1(v) + '%', l: l + ' judged the better fit', c }]); sp.appendChild(seg); });
      pil.appendChild(sp);
      pil.appendChild(E('div', 'unit', `Pairwise share of wins on which reply suits the user better, ${DSX.design.convs} conversations.`));
      right.appendChild(step(pil));
    }
  };

  // 3 · regeneration with style
  ST[2] = {
    how: 'Each column has its own bar scale. Bold marks the best value per column where the paper bolds it.',
    src: 'Source: paper App. B.1 · Tables 26, 27, 31',
    left(){
      put(left, ph('Responder system prompt, every turn'));
      const stack = E('div', 'stack');
      stack.appendChild(step(put(E('div', 'blk base'), E('b', null, 'Persona-conditioned system prompt'), E('span', null, 'the paper’s prompt for regenerating assistant turns'))));
      const st = put(E('div', 'blk add'), put(E('div', 'bh'), E('code', null, '+ RESPONSE STYLE'), E('span', null, 'one of 12')), E('div', 'mono', '{free-text style description}'));
      const ax = E('div', 'axes'); DSX.axes.forEach(a => ax.appendChild(E('span', null, a))); st.appendChild(ax);
      stack.appendChild(step(st));
      stack.appendChild(step(put(E('div', 'blk add touch'), put(E('div', 'bh'), E('code', null, '+ Optional touch for this reply'), E('span', 'pp', 'p = 0.25')), E('span', null, `Use it once, only if it fits naturally. Ends up in ${fmt1(DSX.touchShare)}% of released assistant turns.`))));
      stack.appendChild(step(put(E('div', 'blk add'), put(E('div', 'bh'), E('code', null, '+ CONTENT RULES'), E('span', null, 'any style')), E('span', null, 'Keep every fact, step, number and requested detail the answer needs. Never invent facts, sources or statistics to fit the style.'))));
      const pr = put(E('div', 'blk prio'), put(E('div', 'bh'), E('code', null, 'Priority'), E('span', null, 'highest first')));
      const ol = E('ol');
      ['Explicit user instructions about format, length, tone or language', 'Content rules, correctness and safety', 'The style'].forEach(t => ol.appendChild(E('li', null, t)));
      pr.appendChild(ol);
      pr.appendChild(E('span', 'fine', 'Never mention the style, a persona, or these instructions.'));
      stack.appendChild(step(pr));
      left.appendChild(stack);
    },
    right(){
      const hd = head('Pilots behind the setup', null);
      right.appendChild(hd);
      const body = E('div', 'pbody');
      right.appendChild(tabs([['design', 'Design pilot'], ['data', 'Data-level pilot'], ['nouser', 'No user persona']], pilotTab, v => { pilotTab = v; fill(); }, 'Pilot'));
      right.appendChild(body);
      const fill = () => {
        body.replaceChildren();
        const pc = { k: 'style', l: 'Style adoption', max: 100, fmt: P };
        if (pilotTab === 'design'){
          const best = ['style', 'content', 'instr', 'sanity'];
          put(body, put(E('div', 'mxt'), E('span', null, 'Four ways to produce the assistant side, %'), srcTag('Table 26')));
          body.appendChild(mtx({ best, cols: [pc, { k: 'content', l: 'Same content', max: 100, fmt: P }, { k: 'instr', l: 'Instruction compliance', max: 100, fmt: P }, { k: 'sanity', l: 'Sanity pass', max: 100, fmt: P }],
            rows: D.designPilot.map(r => ({ label: r.arm, rel: r.arm === 'Matched style, generated' ? 'release' : null, v: r })) }));
          body.appendChild(step(E('p', 'rnote', 'Generating with the matched style gives the highest adoption. Restyling a finished reply keeps its content (96.9%), which suits data whose answers must not change.')));
          body.appendChild(E('div', 'unit', `${DSX.design.convs} conversations, ${fmt0(DSX.design.turns)} assistant turns, earlier style set without signature touches. Instruction compliance on ${DSX.design.instr} later turns (±10 pts). Same content is measured against the user-persona-only reply.`));
        } else if (pilotTab === 'data'){
          put(body, put(E('div', 'mxt'), E('span', null, 'Assistant conditioning, user turns fixed'), srcTag('Table 27')));
          body.appendChild(mtx({ cols: [pc, { k: 'content', l: 'Same content', max: 100, fmt: P, nul: 'ref.' }, { k: 'instr', l: 'Instruction compliance', max: 100, fmt: P }, { k: 'words', l: 'Median words', max: 600, fmt: fmt0 }],
            rows: D.dataPilot.map(r => ({ label: r.arm, rel: r.arm === 'User + model persona' ? 'release' : null, v: r })) }));
          const pw = put(E('div', 'pw'), E('span', 'pwh', 'User + model persona, judged better fit vs'));
          DSX.pilot.pair.forEach(([who, a, b]) => pw.appendChild(put(E('span', 'pwi'), E('b', null, `${a} : ${b}`), ' ' + who)));
          body.appendChild(step(pw));
          body.appendChild(step(E('p', 'rnote', 'The model persona makes the intended style recognizable without lowering instruction compliance. The user persona halves reply length.')));
          body.appendChild(E('div', 'unit', `${fmt0(DSX.pilot.convs)} conversations, about 2,500 assistant turns. Same content is against the default reply; two default samples agree ${fmt1(DSX.pilot.noise)}% of the time.`));
        } else {
          put(body, put(E('div', 'mxt'), E('span', null, 'Restyling an existing dataset, no user persona'), srcTag('Table 31')));
          body.appendChild(mtx({ best: ['sanity', 'style', 'content'], cols: [{ k: 'sanity', l: 'Sanity pass', max: 100, fmt: P }, pc, { k: 'content', l: 'Same content', max: 100, fmt: P, nul: 'ref.' }, { k: 'words', l: 'Median words', max: 600, fmt: fmt0 }],
            rows: D.noUserPersona.map(r => ({ label: r.arm, v: r })) }));
          body.appendChild(step(E('p', 'rnote', `Here the style section is the only system prompt. Adoption rises from 25.7% to 79.5% at a cost of about five points of sanity pass. Restyling falls back to the source reply on ${DSX.noUser.fallback}% of turns.`)));
          const lim = E('div', 'pilot');
          put(lim, put(E('div', 'mxt'), E('span', null, 'Source system prompt obeyed, %'), srcTag('App. G.2')));
          const ms = E('div', 'meters');
          DSX.sysPrompt.rows.forEach(([l, v]) => { const m = put(E('div', 'meter'), E('span', null, l), E('span', 'mv', v + '%')); const bar = E('div', 'bar'); const b = E('b'); b.style.width = v + '%'; bar.appendChild(b); m.appendChild(bar); ms.appendChild(m); });
          lim.appendChild(ms);
          lim.appendChild(E('div', 'unit', `${DSX.sysPrompt.n} single-turn conversations with a checkable constraint. The style competes with explicit constraints even when told to yield, so conversations with a system prompt stay unaugmented.`));
          body.appendChild(step(lim));
        }
      };
      fill();
    }
  };

  // 4 · fine-tuning arms
  ST[3] = {
    how: 'All three arms share the same user turns. Only the system prompt behind the assistant side differs.',
    src: 'Source: paper App. G.2',
    left(){
      put(left, ph('Three arms, same user turns'));
      const lanes = E('div', 'lanes');
      [['SFT A', 'A', 'No assistant system prompt', []], ['SFT B', 'B', 'User persona', ['user persona']], ['SFT C', 'C', 'User persona + model persona', ['user persona', 'matched style']]].forEach(([k, l, t, slots]) => {
        const ln = E('div', 'lane'); ln.style.setProperty('--c', ARM[k]);
        const sl = E('div', 'lslots');
        if (!slots.length) sl.appendChild(E('span', 'lslot none', 'empty'));
        slots.forEach(s => sl.appendChild(E('span', 'lslot', s)));
        put(ln, E('span', 'll', l), put(E('div', 'lt'), put(E('div', 'lth'), E('b', null, t), k === 'SFT C' ? E('em', null, 'as released') : null), sl), E('span', 'ln', DSX.train.perArm));
        lanes.appendChild(step(ln, 160));
      });
      left.appendChild(lanes);
      left.appendChild(step(E('p', 'caveat', `Each arm: the same ${DSX.train.perArm} conversations, assistant side regenerated under its own system prompt. The colors follow the arms through the next stages.`)));
    },
    right(){
      put(right, head('Training and evaluation', 'App. G.2'));
      const dl = E('dl', 'spec');
      [['Llama-3.1-8B', 'full fine-tuning · 1 epoch · learning rate 1e-5 · global batch 128'], ['Apertus-8B', 'base model (2509 release) · same budget · packed multi-turn sequences · loss on every assistant turn'], ['Data', `${DSX.train.perArm} conversations per arm`], ['Probes', `${DSX.train.requests} held-out requests × ${DSX.train.voices} user personas`], ['Decoding', 'greedy']].forEach(([k, v]) => put(dl, E('dt', null, k), E('dd', null, v)));
      right.appendChild(step(dl));
      const fl = E('div', 'evflow');
      const dots = (n, cls) => { const d = E('span', 'dots ' + cls); for (let i = 0; i < n; i++) d.appendChild(E('i')); return d; };
      put(fl, put(E('div', 'ev'), E('b', null, '1 request'), E('span', null, 'content fixed')), E('span', 'arr', '→'),
        put(E('div', 'ev'), dots(12, 'u'), E('span', null, '12 user voices')), E('span', 'arr', '→'),
        put(E('div', 'ev'), E('b', null, 'model'), E('span', null, 'one arm')), E('span', 'arr', '→'),
        put(E('div', 'ev'), dots(12, 'r'), E('span', null, '12 replies')));
      right.appendChild(step(fl));
      right.appendChild(step(E('p', 'unit', 'The 12 personas span digital fluency, AI stance, capitalization, message length and typos, so only the user’s voice changes.')));
      const ms = E('ul', 'measures');
      [['Within-request correlation', 'a user-message feature against the same feature in the reply', 'Stage 5'], ['Style diversity', 'mean pairwise distance of the 12 replies in a style embedding', 'Stage 5'], ['Content stability', 'LaBSE similarity to the reply to the unstyled request', 'Stage 5'], ['Reply features', 'length, headers, bullets, emoji, formality, contractions', 'Stage 6'], ['Pairwise judge', 'which reply is presented better for the user, raw and length-controlled', 'Stage 7']].forEach(([a, b, s]) => ms.appendChild(step(put(E('li'), E('b', null, a), E('span', null, b), E('em', null, s)), 70)));
      right.appendChild(ms);
    }
  };

  // 5 · adaptation (Table 28)
  const FT = [
    ['formality', 'Formality', 'Formality → formality', [0, 0.6], [0, 0.2, 0.4, 0.6], 'Correlation between user and reply formality within one request. Every fine-tuned model follows the user far more than Instruct.'],
    ['lower', 'Lowercase', 'Lowercase → formality', [-0.5, 0], [-0.4, -0.2, 0], 'Lowercase users should get less formal replies, so further left is stronger adaptation.'],
    ['length', 'Length', 'Length → length', [-0.1, 0.3], [-0.1, 0, 0.1, 0.2, 0.3], 'Only the conditioned arms start to match reply length to message length. Llama C adapts most (0.26).'],
    ['emoji', 'Emoji', 'Emoji → emoji', [0, 0.6], [0, 0.2, 0.4, 0.6], 'Llama C mirrors emoji use most (0.49).'],
    ['diversity', 'Style diversity', 'Style diversity', [0, 0.4], [0, 0.1, 0.2, 0.3, 0.4], 'Mean pairwise style distance between the 12 replies to one request. SFT A is the least diverse in both families.'],
    ['stability', 'Content stability', 'Content stability', [0, 1], [0, 0.25, 0.5, 0.75, 1], 'LaBSE similarity to the reply given to the unstyled request.']
  ];
  ST[4] = {
    how: 'Pick a measure above the chart. Hover or focus a bar for the exact value.',
    src: 'Source: paper Table 28',
    left(){ left.appendChild(bench('Every model fine-tuned on persona-styled conversations tracks the user’s formality and emoji use far more than Llama-3.1-8B-Instruct, in both families.')); },
    right(){
      put(right, head('Does the reply follow the user?', 'Table 28'));
      right.appendChild(tabs(FT.map(f => [f[0], f[1]]), ftTab, v => { ftTab = v; drawFT(); }, 'Measure'));
      right.appendChild(benchLegend());
      const ch = E('div', 'chart'); right.appendChild(step(ch));
      const cap = E('p', 'cap'); right.appendChild(cap);
      const drawFT = () => { const f = FT.find(x => x[0] === ftTab); benchChart(ch, { get: r => r[f[0]], fmt: f[0] === 'diversity' || f[0] === 'stability' ? fmt3 : fmt2, lo: f[3][0], hi: f[3][1], ticks: f[4], tfmt: t => f[0] === 'stability' ? String(t) : t.toFixed(1), what: f[2] }); cap.textContent = f[5]; };
      draw(drawFT);
    }
  };

  // 6 · reply features (Table 29)
  const contr = new Map(D.finetune.rows.map((r, i) => [r, DSX.contractions[i]]));
  const RF = [
    ['words', 'Median words', r => r.words, fmt0, [0, 700], [0, 200, 400, 600], String, 'Median reply length in words. SFT A writes the longest replies in both families.'],
    ['headers', 'Headers', r => r.headers, P, [0, 100], [0, 25, 50, 75, 100], t => t + '%', 'Share of replies with Markdown headers. SFT A uses them in about three quarters.'],
    ['bullets', 'Bullets', r => r.bullets, P, [0, 100], [0, 25, 50, 75, 100], t => t + '%', 'Share of replies with bullet points.'],
    ['emojiPct', 'Emoji', r => r.emojiPct, P, [0, 20], [0, 5, 10, 15, 20], t => t + '%', 'Share of replies with at least one emoji.'],
    ['formal', 'Formality', r => r.formal, fmt2, [0, 1], [0, 0.25, 0.5, 0.75, 1], String, 'Mean score of a formality classifier, 0 to 1.'],
    ['contr', 'Contractions', r => contr.get(r), fmt2, [0, 2], [0, 0.5, 1, 1.5, 2], String, 'Contractions per 100 words.']
  ];
  ST[5] = {
    how: 'Judge-free counts over the replies to the style probes. Hover or focus a bar for the exact value.',
    src: 'Source: paper Table 29',
    left(){ left.appendChild(bench('Without assistant conditioning (A), the models inherit the teacher’s defaults: replies two to two and a half times longer, headers in about three quarters of them.')); },
    right(){
      put(right, head('What the replies look like', 'Table 29'));
      right.appendChild(tabs(RF.map(f => [f[0], f[1]]), rfTab, v => { rfTab = v; drawRF(); }, 'Reply feature'));
      right.appendChild(benchLegend());
      const ch = E('div', 'chart'); right.appendChild(step(ch));
      const cap = E('p', 'cap'); right.appendChild(cap);
      const drawRF = () => { const f = RF.find(x => x[0] === rfTab); benchChart(ch, { get: f[2], fmt: f[3], lo: f[4][0], hi: f[4][1], ticks: f[5], tfmt: f[6], what: f[1] }); cap.textContent = f[7]; };
      draw(drawRF);
    }
  };

  // 7 · pairwise judge (Table 30)
  const shortCmp = c => c.replace('Llama-3.1-8B-Instruct', 'Instruct');
  ST[6] = {
    how: 'Win rate of the first model in each pair. 50% is parity. Hover or focus a row for the values.',
    src: 'Source: paper Table 30 · Fig. 27',
    left(){ left.appendChild(bench('The judge prefers the shorter B and C replies over A, but the preference disappears or reverses once reply length is controlled. Llama C still beats Llama-3.1-8B-Instruct at equal length (68.6%).', false)); },
    right(){
      put(right, head('Which reply does the judge prefer?', 'Table 30 · Fig. 27'));
      right.appendChild(legend([{ name: 'Raw win rate', color: 'var(--s1)', kind: 'dot' }, { name: '95% interval', color: 'var(--s1)', kind: 'line' }, { name: 'Length-controlled', color: 'var(--s2)', kind: 'dot' }]));
      const ch = E('div', 'chart'); right.appendChild(step(ch));
      draw(() => forest(ch, { rows: D.finetune.pairwise.map(p => ({ label: shortCmp(p.cmp), v: p.raw, lo: p.lo, hi: p.hi, color: 'var(--s1)', v2: p.lc, color2: 'var(--s2)', tip: [{ l: p.cmp }, { c: 'var(--s1)', v: fmt1(p.raw) + '%', l: `raw (95% CI ${fmt1(p.lo)}–${fmt1(p.hi)})` }, { c: 'var(--s2)', v: fmt1(p.lc) + '%', l: 'length-controlled' }] })), min: 35, max: 85, ref: 50, refLabel: 'parity', ticks: [40, 50, 60, 70, 80], rowH: 30, labelMax: 200 }));
      right.appendChild(E('p', 'cap', `A: no system prompt. B: user persona. C: user + model persona. Instruct is Llama-3.1-8B-Instruct. ${DSX.pairN[0].toUpperCase() + DSX.pairN.slice(1)} decisive comparisons per pair.`));
      right.appendChild(E('p', 'cap', 'B and C replies are about half as long as A, so the equal-length estimate is an extrapolation.'));
      right.appendChild(E('p', 'rnote', 'The comparison with Llama-3.1-8B-Instruct is context only. The controlled comparison with the original training data follows in stages 8 to 10.'));
      const det = put(E('details', 'tbl'), E('summary', null, 'Show values'));
      const tw = E('div', 'tblwrap'); det.appendChild(tw);
      table(tw, ['Comparison', 'Raw win', '95% CI', 'LC win'], D.finetune.pairwise.map(p => [p.cmp, fmt1(p.raw), `${fmt1(p.lo)}–${fmt1(p.hi)}`, fmt1(p.lc)]), [1, 2, 3]);
      right.appendChild(det);
    }
  };

  /* ---------- released-corpus study (Appendix G.3): Apertus-v1.5-8B base on versions of the same conversations ---------- */
  const C = D.corpusFT, CX = DSX.corpus;
  // A0 is the reference (original data), so it takes the neutral ink; the released arms take the station violet.
  const CARM = {
    A0: { c: 'var(--ink-2)', n: 'original', d: 'the original seed conversation' },
    A0r: { c: 'var(--s3)', n: 'regenerated, no persona', d: 'original user turns, assistant regenerated with no persona' },
    A1: { c: 'var(--s2)', n: 'styled user, original assistant', d: 'persona-styled user turns, original assistant turns' },
    A2: { c: 'var(--s1)', n: 'released', d: 'styled user turns, assistant regenerated for that user' },
    X1: { c: 'var(--s3)', n: 'translated', d: 'user turns translated persona-blind, assistant regenerated with no persona' },
    X2: { c: 'var(--s1)', n: 'released cross-lingual', d: 'styled user turns, assistant regenerated for that user' }
  };
  const JUDGE = [['qwen', 'Qwen3.6-35B-A3B', 'var(--s1)'], ['muse', 'Muse-Glimmer-30B', 'var(--s2)']];
  const sgn = v => (v > 0 ? '+' : v < 0 ? '−' : '') + fmt1(Math.abs(v));
  const ivl = (lo, hi) => `${sgn(lo)} to ${sgn(hi)}`;
  const tsg = t => (t > 0 ? '+' : t < 0 ? '−' : '') + Math.abs(t);
  const armLab = k => `${k} · ${CARM[k].n}`;
  const armLegend = keys => legend(keys.map(k => ({ name: armLab(k), color: CARM[k].c })));

  function cbench(finding, caveat, swatch = true){
    const wrap = E('div', 'bench' + (swatch ? '' : ' nosw'));
    put(wrap, ph('Arms under test'));
    [['Language-matched', ['A0', 'A0r', 'A1', 'A2']], ['Cross-lingual', ['X1', 'X2']]].forEach(([t, ks]) => {
      const f = put(E('div', 'bfam'), E('b', null, t));
      ks.forEach(k => { const sw = E('i'); if (swatch) sw.style.background = CARM[k].c; f.appendChild(put(E('div', 'bm'), sw, E('span', 'bk', k), E('span', 'bv', CARM[k].n))); });
      wrap.appendChild(step(f));
    });
    if (finding) wrap.appendChild(step(put(E('div', 'find'), E('span', 'fh', 'Finding'), E('p', null, finding))));
    if (caveat) wrap.appendChild(step(E('p', 'caveat', caveat)));
    return wrap;
  }

  // Interval plot with one or more estimates per row: rows [{ label, pts: [{ name, color, v, lo, hi }] }]
  function ciChart(el, { rows, min, max, ref, refLabel, ticks, fmt = sgn, tfmt = String, unit = '' }){
    const w = W(el);
    const lw = Math.min(150, Math.ceil(measure(rows.map(r => r.label))) + 8, w * 0.36);
    const top = refLabel ? 18 : 6, bottom = 24, gap = 15;
    const hs = rows.map(r => Math.max(30, r.pts.length * gap + 14));
    const h = top + hs.reduce((a, b) => a + b, 0) + bottom;
    const x0 = lw + 12, x1 = w - 12;
    const sx = v => x0 + (x1 - x0) * (v - min) / (max - min);
    const svg = svgFor(el, w, h);
    const g = S('g', { class: 'grid' }, svg);
    ticks.forEach(t => { S('line', { x1: sx(t), x2: sx(t), y1: top - 2, y2: h - bottom }, g); T(tfmt(t), { x: sx(t), y: h - 6, 'text-anchor': 'middle', class: 'muted' }, svg); });
    if (ref != null){ S('line', { class: 'ref', x1: sx(ref), x2: sx(ref), y1: top - 6, y2: h - bottom }, svg); if (refLabel) T(refLabel, { x: sx(ref), y: 11, 'text-anchor': 'middle', class: 'muted' }, svg); }
    let y = top;
    rows.forEach((r, i) => {
      const rh = hs[i], n = r.pts.length, y0 = y + rh / 2 - (n - 1) * gap / 2;
      if (i) S('line', { class: 'sep', x1: 0, x2: w, y1: y, y2: y }, svg);
      T(fit(r.label, lw - 2), { x: lw, y: y + rh / 2 + 4, 'text-anchor': 'end' }, svg);
      r.pts.forEach((p, j) => {
        const cy = y0 + j * gap;
        S('line', { x1: sx(p.lo), x2: sx(p.hi), y1: cy, y2: cy, stroke: p.color, 'stroke-width': 2, 'stroke-linecap': 'round' }, svg);
        S('circle', { cx: sx(p.v), cy, r: 5.5, fill: p.color, stroke: 'var(--surface)', 'stroke-width': 2 }, svg);
      });
      const hit = S('rect', { class: 'hit', x: 0, y, width: w, height: rh }, svg);
      bind(hit, [{ l: r.label }, ...r.pts.map(p => ({ c: p.color, v: fmt(p.v) + unit, l: `${p.name} (95% interval ${fmt(p.lo)} to ${fmt(p.hi)})` }))]);
      y += rh;
    });
    return svg;
  }

  // 8 · corpus arms (G.3 setup)
  ST[7] = {
    how: 'The arms hold the same conversations and differ only in which side was restyled or regenerated. Hover a cell for its reply length.',
    src: 'Source: paper App. G.3 · Table 32',
    left(){
      put(left, ph('Four arms, same conversations'));
      const mx = Math.max(...C.arms.map(a => a.chars));
      const grid = E('div', 'cgrid');
      put(grid, E('span', 'cgh'), E('span', 'cgh', 'Original assistant'), E('span', 'cgh', 'Regenerated assistant'));
      const cell = k => {
        const a = C.arms.find(x => x.arm === k), ar = CARM[k];
        const c = E('div', 'cg' + (k === 'A2' ? ' rel' : '')); c.style.setProperty('--c', ar.c);
        const bar = E('span', 'cgb'); const b = E('b'); b.style.width = (100 * a.chars / mx) + '%'; bar.appendChild(b);
        put(c, put(E('div', 'cgt'), E('span', 'll', k), k === 'A2' ? E('em', null, 'as released') : null), E('span', 'cgn', ar.n), bar, E('span', 'cgv', fmt0(a.chars) + ' chars'));
        bind(c, [{ c: ar.c, v: fmt0(a.chars) + ' characters', l: `${k} · median assistant turn in the training data` }, { l: ar.d }]);
        return step(c, 140);
      };
      put(grid, E('span', 'cgr', 'Original user'), cell('A0'), cell('A0r'), E('span', 'cgr', 'Styled user'), cell('A1'), cell('A2'));
      left.appendChild(grid);
      left.appendChild(step(E('p', 'caveat', `Each arm: the same ${fmt0(CX.convs)} language-matched conversations from the training split, with ${CX.heldOut}% of personas held out for evaluation. Conversations whose A0r regeneration failed the sanity gate, or that exceed ${fmt0(CX.maxTok)} tokens in any arm, are removed from all arms.`)));
      put(left, ph('Cross-lingual pair'));
      const lanes = E('div', 'lanes x');
      ['X1', 'X2'].forEach(k => {
        const ln = E('div', 'lane'); ln.style.setProperty('--c', CARM[k].c);
        put(ln, E('span', 'll', k), put(E('div', 'lt'), put(E('div', 'lth'), E('b', null, k === 'X1' ? 'Translated user turns' : 'Released cross-lingual conversation'), k === 'X2' ? E('em', null, 'as released') : null), E('span', 'lsub', CARM[k].d)), null);
        lanes.appendChild(step(ln, 140));
      });
      left.appendChild(lanes);
      left.appendChild(step(E('p', 'caveat', `${fmt0(CX.xConvs)} conversations built from the same English seeds and target personas, one training seed.`)));
    },
    right(){
      put(right, head('Training and evaluation', 'App. G.3'));
      const dl = E('dl', 'spec');
      [['Base model', 'Apertus-v1.5-8B base'], ['Training', `Megatron-LM · 1 epoch · packed ${fmt0(CX.seq)}-token sequences · loss on every assistant turn`], ['Optimizer', 'global batch 128 · learning rate 1e-5 decayed to 1e-6, cosine after 3% warmup'], ['Seeds', 'three per language-matched arm, one per cross-lingual arm']].forEach(([k, v]) => put(dl, E('dt', null, k), E('dd', null, v)));
      right.appendChild(step(dl));
      const pt = E('div', 'pilot');
      put(pt, put(E('div', 'mxt'), E('span', null, 'How benchmark prompts are made messy')));
      const rowOf = (t, items) => { const r = put(E('div', 'prow'), E('span', 'prh', t)); const s = E('div', 'slots'); items.forEach(x => s.appendChild(E('span', 'slot', x))); r.appendChild(s); return r; };
      pt.appendChild(rowOf('Rule-based', ['lowercasing', 'punctuation removal', 'light typos', 'heavy typos', 'abbreviations', 'terse', 'combined']));
      pt.appendChild(rowOf('Persona rewrite', ['three held-out personas', 'Gemma-4-31B rewriter', `kept if the task is unchanged (${fmt1(CX.keep)}%)`]));
      right.appendChild(step(pt));
      const ms = E('ul', 'measures');
      [['Clean capability', 'lm-evaluation-harness, thinking disabled', 'Stage 9'],
       ['Robustness', 'drop from the clean to a perturbed prompt on IFEval, GSM8K and MBPP', 'Stage 10'],
       ['Real prompts', `${fmt0(CX.wild)} WildChat first turns no arm was trained on (half English), two external judges, both reply orders, length-controlled`, 'Stage 10'],
       ['Reply style', `${CX.requests} held-out requests × ${CX.voices} user personas, A2 against A0`, 'Stage 10']].forEach(([a, b, s]) => ms.appendChild(step(put(E('li'), E('b', null, a), E('span', null, b), E('em', null, s)), 70)));
      right.appendChild(ms);
    }
  };

  // 9 · capability (Tables 32, 35)
  let capTab = 'lm', h2hTab = 'wild';
  ST[8] = {
    how: 'Pick the language-matched or cross-lingual arms above the chart. Hover or focus a bar for the exact value.',
    src: 'Source: paper Tables 32, 35',
    left(){ left.appendChild(cbench('Trained on the released conversations (A2), the model is on par with training on the original data (A0) on every benchmark except GSM8K, where it is 3.1 points behind, and it scores highest on IFEval.', `One base model. Language-matched arms: mean of three training seeds, standard deviation at most ${fmt1(CX.sd)} points. Cross-lingual arms: one seed.`)); },
    right(){
      put(right, head('Capability after fine-tuning', 'Tables 32, 35'));
      right.appendChild(tabs([['lm', 'Language-matched'], ['x', 'Cross-lingual']], capTab, v => { capTab = v; fill(); }, 'Arm set'));
      const body = E('div', 'pbody'); right.appendChild(body);
      const fill = () => {
        body.replaceChildren(); draws = draws.filter(f => !f.cap);
        const ch = E('div', 'chart'); body.appendChild(ch);
        if (capTab === 'lm'){
          const ks = C.arms.map(a => a.arm), a0 = C.arms[0];
          const f = () => hbars(ch, { series: ks.map(k => ({ name: armLab(k), color: CARM[k].c })), max: 80, ticks: [0, 20, 40, 60, 80], barH: 9, gapIn: 2, labelMax: 110,
            rows: C.bench.map((b, i) => ({ label: b, values: C.arms.map(a => a.v[i]), tip: j => j ? [{ l: `${sgn(C.arms[j].v[i] - a0.v[i])} points vs. A0` }] : [{ l: 'reference: the original data' }] })) });
          f.cap = 1; draw(f);
          body.appendChild(E('p', 'cap', 'Accuracy in %, lm-evaluation-harness with thinking disabled.'));
          body.appendChild(step(E('p', 'rnote', 'Against the original data, A2 gains 1.8 points of IFEval strict accuracy and loses 3.1 on GSM8K. Styled user turns with the original replies (A1) score lowest on IFEval.')));
        } else {
          const f = () => hbars(ch, { series: ['X1', 'X2'].map(k => ({ name: armLab(k), color: CARM[k].c })), max: 80, ticks: [0, 20, 40, 60, 80], barH: 10, gapIn: 2, labelMax: 110,
            rows: C.cross.map(([b, x1, x2]) => ({ label: b, values: [x1, x2], tip: j => j ? [{ l: `${sgn(x2 - x1)} points vs. X1` }] : [] })) });
          f.cap = 1; draw(f);
          body.appendChild(E('p', 'cap', 'Accuracy in %, one training seed. Multi-IF: prompt-level strict accuracy. INCLUDE covers 44 languages.'));
          body.appendChild(step(E('p', 'rnote', 'X2 is ahead on most benchmarks, with the largest gain on multilingual instruction following (Multi-IF, 7.3 points), and behind on GSM8K.')));
          const m = DSX.crossLC.muse, q = DSX.crossLC.qwen;
          body.appendChild(step(E('p', 'unit', `On WildChat prompts, X2 replies are half as long as X1 replies. Both judges prefer X2 on raw votes, but at equal length Muse is at parity (${fmt1(m[0])}%, interval ${fmt1(m[1])} to ${fmt1(m[2])}) and Qwen3.6 prefers X1 (${fmt1(q[0])}%, interval ${fmt1(q[1])} to ${fmt1(q[2])}), so this comparison is inconclusive.`)));
        }
      };
      fill();
    }
  };

  // 10 · head to head (Tables 33, 34)
  const H2H = {
    wild: { l: 'Real prompts', h: 'Which reply do external judges prefer?' },
    ifeval: { l: 'IFEval', h: 'Instruction following, arm against arm' },
    robust: { l: 'Robustness', h: 'Does an arm lose more on messy prompts?' },
    style: { l: 'Reply style', h: 'Does the reply follow the user?' }
  };
  ST[9] = {
    how: 'Pick a comparison above the chart. On the interval charts, dots are estimates and lines 95% intervals. Hover or focus a row for the values.',
    src: 'Source: paper Tables 33, 34 · App. G.3',
    left(){
      const s = DSX.seeds;
      left.appendChild(cbench('Styled user turns help only together with assistant turns written for them. A1 loses IFEval accuracy against the original data, A2 clearly beats A1, and on real prompts both external judges prefer A2 over A1 and over A0 at equal reply length.',
        `Charts show training seed 1234 with intervals over items. Over three seeds, both judges prefer A2 over A1 (${fmt1(s.a2a1Judge[0])} to ${fmt1(s.a2a1Judge[1])}%) and over A0 (${fmt1(s.a2a0Judge[0])} to ${fmt1(s.a2a0Judge[1])}%) at equal length for every seed. One base model.`, false));
      const st = DSX.strict;
      left.appendChild(step(put(E('div', 'fact'), E('b', null, 'Strict subset. '), `Retraining A2 only on conversations in which every user turn is labelled as the same request, at equal size and with three seeds, leaves every benchmark unchanged (IFEval ${sgn(st.ifeval[0])}, interval ${ivl(st.ifeval[1], st.ifeval[2])}), and the preference over the original data remains (${fmt1(st.judge[0])} to ${fmt1(st.judge[1])}%).`)));
    },
    right(){
      const hd = E('h4', 'rh', H2H[h2hTab].h);
      put(right, put(E('div', 'rhd'), hd, srcTag('Tables 33, 34')));
      right.appendChild(tabs(Object.keys(H2H).map(k => [k, H2H[k].l]), h2hTab, v => { h2hTab = v; hd.textContent = H2H[v].h; fill(); }, 'Comparison'));
      const body = E('div', 'pbody'); right.appendChild(body);
      const fill = () => {
        body.replaceChildren(); draws = draws.filter(f => !f.h2h);
        const ch = E('div', 'chart');
        const reg2 = f => { f.h2h = 1; draw(f); };
        const pt = (name, color, a) => ({ name, color, v: a[0], lo: a[1], hi: a[2] });
        if (h2hTab === 'wild'){
          body.appendChild(legend([...JUDGE.map(([, n, c]) => ({ name: n, color: c, kind: 'dot' })), { name: '95% interval', color: 'var(--ink-2)', kind: 'line' }]));
          body.appendChild(ch);
          reg2(() => ciChart(ch, { rows: C.paired.filter(p => p.qwen).map(p => ({ label: p.cmp, pts: JUDGE.map(([k, n, c]) => pt(n, c, p[k])) })), min: 40, max: 65, ref: 50, refLabel: 'parity', ticks: [40, 45, 50, 55, 60, 65], fmt: fmt1, unit: '%' }));
          body.appendChild(E('p', 'cap', `Length-controlled win rate of the first arm, in %, on ${fmt0(CX.wild)} WildChat first turns, each pair judged in both orders. 50% is parity. No judge result is reported for A1 against A0.`));
          body.appendChild(step(E('p', 'rnote', 'A0r replies are more than twice as long, so the comparison with A0r rests on the length correction, and the two judges disagree on it.')));
        } else if (h2hTab === 'ifeval'){
          body.appendChild(legend([{ name: 'Difference, first arm minus second', color: 'var(--s1)', kind: 'dot' }, { name: '95% interval', color: 'var(--s1)', kind: 'line' }]));
          body.appendChild(ch);
          reg2(() => ciChart(ch, { rows: C.paired.map(p => ({ label: p.cmp, pts: [pt('IFEval strict, clean prompts', 'var(--s1)', p.clean)] })), min: -8, max: 12, ref: 0, refLabel: 'no difference', ticks: [-8, -4, 0, 4, 8, 12], tfmt: tsg, unit: ' points' }));
          body.appendChild(E('p', 'cap', 'IFEval strict accuracy on clean prompts, difference in points, scored with the authors’ own IFEval checker.'));
          const s = DSX.seeds;
          body.appendChild(step(E('p', 'rnote', `Over three training seeds (lm-evaluation-harness, intervals over items and seeds): A2 against A1 ${sgn(s.a2a1[0])} (${ivl(s.a2a1[1], s.a2a1[2])}), A2 against A0r ${sgn(s.a2a0r[0])} (${ivl(s.a2a0r[1], s.a2a0r[2])}), A1 against A0 ${sgn(s.a1a0[0])} (${ivl(s.a1a0[1], s.a1a0[2])}).`)));
        } else if (h2hTab === 'robust'){
          const RB = [['rule', 'Rule-based noise', 'var(--s1)'], ['persona', 'Persona rewrites', 'var(--s2)']];
          body.appendChild(legend([...RB.map(([, n, c]) => ({ name: n, color: c, kind: 'dot' })), { name: '95% interval', color: 'var(--ink-2)', kind: 'line' }]));
          body.appendChild(ch);
          reg2(() => ciChart(ch, { rows: C.paired.map(p => ({ label: p.cmp, pts: RB.map(([k, n, c]) => pt(n, c, p[k])) })), min: -8, max: 8, ref: 0, refLabel: 'no difference', ticks: [-8, -4, 0, 4, 8], tfmt: tsg, unit: ' points' }));
          body.appendChild(E('p', 'cap', 'Difference in the IFEval robustness gap (clean minus perturbed accuracy), in points. Positive: the first arm loses more.'));
          body.appendChild(step(E('p', 'rnote', 'No gap difference between arms excludes zero, so none of the arms measurably changes robustness to messy prompts. Persona rewrites cost every arm more than rule-based noise.')));
        } else {
          body.appendChild(ch);
          reg2(() => hbars(ch, { series: ['A2', 'A0'].map(k => ({ name: armLab(k), color: CARM[k].c })), max: 1, ticks: [0, 0.25, 0.5, 0.75, 1], fmt: fmt3, barH: 12, gapIn: 3, labelMax: 150,
            rows: C.style.map(([m, a2, a0]) => ({ label: m.replace(' across personas', ''), values: [a2, a0], tip: () => [{ l: m }] })) }));
          body.appendChild(E('p', 'cap', `${CX.requests} held-out requests from ${CX.voices} user personas, three training seeds. Style diversity is measured across the personas.`));
          const [f, e, d, c] = C.style;
          body.appendChild(step(E('p', 'rnote', `Without explicit steering, A2 adapts its reply style to the user more closely: emoji mirroring rises from ${fmt3(e[2])} to ${fmt3(e[1])}, formality correlation from ${fmt3(f[2])} to ${fmt3(f[1])}, and style diversity across personas from ${fmt3(d[2])} to ${fmt3(d[1])}. Content stays as stable (${fmt3(c[1])} against ${fmt3(c[2])}).`)));
        }
        const det = put(E('details', 'tbl'), E('summary', null, 'Show values'));
        const tw = E('div', 'tblwrap'); det.appendChild(tw);
        const iv = a => a ? `${sgn(a[0])} (${ivl(a[1], a[2])})` : '–';
        const wr = a => a ? `${fmt1(a[0])} (${fmt1(a[1])}–${fmt1(a[2])})` : '–';
        if (h2hTab === 'style') table(tw, ['Metric', 'A2', 'A0'], C.style.map(([m, a2, a0]) => [m, fmt3(a2), fmt3(a0)]), [1, 2]);
        else table(tw, ['Comparison', 'IFEval clean', 'Rule-based gap', 'Persona gap', 'Qwen3.6 LC win', 'Muse LC win'], C.paired.map(p => [p.cmp, iv(p.clean), iv(p.rule), iv(p.persona), wr(p.qwen), wr(p.muse)]), [1, 2, 3, 4, 5]);
        body.appendChild(det);
      };
      fill();
    }
  };

  /* ---------- line control ---------- */
  const phaseBtns = $$('#dsPhase button');
  function render(s, animate){
    anim = animate && !reduce; delay = 0; draws = [];
    left.replaceChildren(); right.replaceChildren();
    line.dataset.stage = s;
    ST[s].left(); delay = 0; ST[s].right();
    $('#dsHow').textContent = ST[s].how;
    $('#dsSrc').textContent = ST[s].src;
    phaseBtns.forEach(b => b.setAttribute('aria-pressed', (s >= 3) === (b.dataset.p === '3') ? 'true' : 'false'));
  }
  const ctl = lineCtl(line, { count: 10, render, dur: s => [3000, 2600, 2800, 2400, 2200, 2200, 2400, 2600, 2400, 2600][s] });
  phaseBtns.forEach(b => b.addEventListener('click', () => { ctl.stop(); ctl.show(+b.dataset.p, false); }));
})();
