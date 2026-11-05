/* ======================= PERSONA ASSEMBLY (station 1) ======================= */
// Numbers not in data.js, with their source:
const BANK_X = {
  macroRegions: 13,                 // Table 4: "Countries (Macro-regions) 177 (13)"
  languages: 282,                   // Table 4: "Languages (Dialect labels) 282 (117,670)"
  verdictsStored: 686814,           // Table 4 caption: keep rates computed over 686,814 candidates with stored verdicts
  verdictsMissing: 108929,          // Table 4 caption: remaining 108,929 candidates (95.5 keep rate)
  meanAge: 39.6,                    // Table 4: mean age 39.6 yrs (18-80)
  topCountries: [['Indonesia', 27004], ['China', 26109], ['India', 25947]]  // Figure 3 caption
};

// The seven personas the paper prints in full. Every value below is transcribed from the named figure.
// Fields: [label, value, keys of the readout charts this field explains]. hl: chart key -> [bank category, what the paper says].
// seed.occ: the grid occupation is printed only in Figure 2; the other figures give a job title and sector.
const BK = [
  { id: 'fl', chip: 'Florida', fig: 'Figure 2', tag: 'FL', head: '23 · F · Florida, USA',
    seed: { region: 'North America → USA → Florida', occ: 'Graduate student', sector: 'Education' },
    bg: [ ['Age', '23', ['Age']], ['Gender', 'Female', ['Gender']],
          ['Job title', 'TA and PhD candidate in bilingual education policy (ES/EN), state-funded public university'],
          ['Education', 'Master’s, bilingual education/policy', ['Education']],
          ['Language', 'English native · Floridian Spanish English dialect', ['Main language (top 10)']],
          ['AI stance', 'Skeptical', ['AI stance']], ['Digital fluency', 'High (core segment)', ['Digital fluency']],
          ['Summary', 'Teaching assistant and PhD candidate in bilingual education policy who argues Florida’s politicized curriculum online, and is skeptical of AI because model output reads “too polished”, or worse, “non-Floridian.”'] ],
    st: [ ['Free-text style', 'all-lowercase messages with elliptical punctuation, drops articles, lards sentences with Spanish loanwords or fragmented Spanish verbs (like vamos we’re ready) and almost always ends with a question or backchannel'],
          ['Code-switching', 'High', ['Code-switching']],
          ['Reference pool', 'Education-policy memes on TikTok · Florida education-funding jokes · indie Latin music · Valorant · ESL side hustle'],
          ['Capitalization', 'first-word-only, no final period', ['Capitalization']],
          ['Abbreviations', 'u r k · sometimes xq = porque'],
          ['Emoji', 'Frequent, decorative: 💀 😭 🎉', ['Emoji use']],
          ['Sign-off', 'ok or no? · no logoff'],
          ['Quirks', ['Spells academick when frustrated by Florida’s system', 'reflexive them', 'code-switches mid-sentence, finishes in English', 'occasional uncorrected typos']] ],
    hl: { 'Macro-region': ['North America', 'North America'], 'Occupation (top 10 of 575)': ['Graduate student', 'graduate student'],
          'Age': ['23–27', 'age 23'], 'Gender': ['Female', 'female'], 'Education': ["Master's degree", 'Master’s'],
          'Digital fluency': ['High', 'high'], 'AI stance': ['Skeptical', 'skeptical'], 'Main language (top 10)': ['English', 'English native'],
          'Code-switching': ['High', 'high'], 'Capitalization': ['first-word only', 'first-word-only'], 'Emoji use': ['frequent / decorative', 'frequent, decorative'] } },
  { id: 'vi', chip: 'Vietnam', fig: 'Figure 6', tag: 'VN', head: '24 · M · Vietnam',
    seed: { region: 'Vietnam', sector: 'Manufacturing' },
    bg: [ ['Age', '24', ['Age']], ['Gender', 'Male', ['Gender']], ['Job title', 'Factory line worker'],
          ['Language', 'Vietnamese (main / native)', ['Main language (top 10)']] ],
    st: [ ['Free-text style', 'Lowercase tendency, minimal punctuation, casual particle endings (nhé, á, ah), self-referential pronouns (mk for mình), bulleted prompt structure.', ['Punctuation']],
          ['Code-switching', 'English (technical terms / code-switching)'],
          ['Example message', '“anh có thể giúp mk tìm cách fix máy khi nó bị treo ở step 4 của dòng lắp ráp không ạ?...”'] ],
    hl: { 'Age': ['23–27', 'age 24'], 'Gender': ['Male', 'male'], 'Main language (top 10)': ['Vietnamese', 'Vietnamese'],
          'Punctuation': ['minimal (no punct.)', '“minimal punctuation”'] } },
  { id: 'be', chip: 'Bern', fig: 'Figure 7', tag: 'BE', head: '23 · M · Bern, Switzerland',
    seed: { region: 'Bern, Switzerland', sector: 'Engineering' },
    bg: [ ['Age', '23', ['Age']], ['Gender', 'Male', ['Gender']], ['Job title', 'mechanical CAD designer, machine-tool prototyping firm, freelance subcontracts'],
          ['Education', 'Vocational / Trade training', ['Education']],
          ['Language', 'German (main) · Swiss German (native) · dialect bernische Deutsch', ['Main language (top 10)']] ],
    st: [ ['Free-text style', 'short sentences with minimal punctuation, German contractions leaking into English (e.g., ‘und → &’), adds ‘z.z.’ as placeholder expansions (‘z.Z.’ = ‘zur Zeit’/‘for now’) when unsure, ends with ‘ok’ or ‘no?’ for most questions', ['Punctuation', 'Sentence length']],
          ['Code-switching', 'High', ['Code-switching']],
          ['Quirks', ['replaces German filler words with ‘sä’ (Bern-specific, e.g., ‘sä, ich meen...’)', 'uses ‘düber’ for ‘digital’ or ‘über’-infused tech terms (e.g., ‘düber-lag’ instead of ‘digital lag’)']],
          ['Example message', '“hey. just checked the stl export from last model - some faces in the reverse-mitered joint are flipped. how can i fix that in freeCAD before rendering? z.Z. i’ll try the ‘normal’ toggle, but if that […]”'] ],
    hl: { 'Age': ['23–27', 'age 23'], 'Gender': ['Male', 'male'], 'Education': ['Vocational / trade', 'vocational / trade training'],
          'Main language (top 10)': ['German', 'German'], 'Code-switching': ['High', 'high'],
          'Punctuation': ['minimal (no punct.)', '“minimal punctuation”'], 'Sentence length': ['Short / fragmented', '“short sentences”'] } },
  { id: 'zh', chip: 'Zurich', fig: 'Figure 8', tag: 'ZH', head: '66 · F · Zurich, Switzerland',
    seed: { region: 'Zurich, Switzerland', sector: 'Sales & retail' },
    bg: [ ['Age', '66', ['Age']], ['Gender', 'Female', ['Gender']], ['Job title', 'Part-time checkout operator at a large supermarket chain'],
          ['Education', 'Vocational / Trade training', ['Education']],
          ['Language', 'German (main) · German (native) · dialect Swiss German', ['Main language (top 10)']] ],
    st: [ ['Free-text style', 'Writes in complete sentences with standard capitalization, often using multiple exclamation marks and friendly emojis to show warmth.', ['Capitalization', 'Punctuation']],
          ['Code-switching', 'Low', ['Code-switching']],
          ['Quirks', ['Uses ‘Grüezi’ as a habitual greeting even in text', 'Frequent use of the ‘smiley’ face to soften requests']],
          ['Example message', '“Hallo! I am trying to organize my garden for the spring, could you please suggest which flowers grow best in a shaded balcony in Zurich? [blossom][tulip]”'] ],
    hl: { 'Age': ['65–69', 'age 66'], 'Gender': ['Female', 'female'], 'Education': ['Vocational / trade', 'vocational / trade training'],
          'Main language (top 10)': ['German', 'German'], 'Code-switching': ['Low', 'low'],
          'Capitalization': ['standard', '“standard capitalization”'], 'Punctuation': ['excessive (!!/???)', '“multiple exclamation marks”'] } },
  { id: 'gl', chip: 'Geneva lab', fig: 'Figure 9', tag: 'GE', head: '29 · M · Geneva, Switzerland',
    seed: { region: 'Geneva, Switzerland', sector: 'Healthcare' },
    bg: [ ['Age', '29', ['Age']], ['Gender', 'Male', ['Gender']], ['Job title', 'Senior clinical microbiology lab tech at Geneva University Hospital’s diagnostics division'],
          ['Education', 'Vocational / Trade training', ['Education']],
          ['Language', 'French (main) · French (Swiss) (native) · dialect Genevois', ['Main language (top 10)']] ],
    st: [ ['Free-text style', 'Terse sentences with minimal punctuation, heavy code-switching between French and English, and a tendency to drop final periods unless writing formally. Uses lowercase for informal messages but capitalizes proper nouns (e.g., ‘RStudio’). Ends messages with […]', ['Punctuation']],
          ['Code-switching', 'High', ['Code-switching']],
          ['Quirks', ['Uses ‘labo’ (French labo for ‘lab’) instead of laboratoire in informal context, even when typing in […]', 'When frustrated, substitutes ‘pff’ for ‘putain’ (French profanity) in messages, e.g., ‘pff this serum keeps […]']],
          ['Example message', '“hey chatbot, can u generate a quick workflow for validating rapid COVID Ag tests against PCR in RStudio? like, step-by-step but w/ real data error rates. pff, i’ve got 3 failed batches this week and […]”'] ],
    hl: { 'Age': ['28–32', 'age 29'], 'Gender': ['Male', 'male'], 'Education': ['Vocational / trade', 'vocational / trade training'],
          'Main language (top 10)': ['French', 'French'], 'Code-switching': ['High', 'high'], 'Punctuation': ['minimal (no punct.)', '“minimal punctuation”'] } },
  { id: 'fr', chip: 'Geneva ML ops', fig: 'Figure 10', tag: 'GE', head: '24 · F · Geneva, Switzerland',
    seed: { region: 'Geneva, Switzerland', sector: 'Software & IT' },
    bg: [ ['Age', '24', ['Age']], ['Gender', 'Female', ['Gender']], ['Job title', 'ML ops engineer at a fintech scale-up, fraud detection models'],
          ['Education', 'Master’s degree', ['Education']],
          ['Language', 'French (main) · Swiss French (native) · dialect Genève', ['Main language (top 10)']] ],
    st: [ ['Free-text style', 'Mix of fragmented technical terms, French abbreviations, and a slash of emphatic emojis—no full sentences, all lowercase, ending with ‘?’ even if not a question or ‘!’ if annoyed—sometimes drops articles and prepositions in French when typing fast', ['Capitalization']],
          ['Code-switching', 'Medium', ['Code-switching']],
          ['Quirks', ['Uses ‘je te kiffe’ (roughly ‘I’m stoked’) instead of ‘j’adore’ in informal tech chats', 'Replace ‘pourquoi’ with ‘pq’ or ‘pqoui’ only when confused or frustrated']],
          ['Example message', '“okay mais le dataset pour le modèle fraud déconne encore, tu peux m’aider à checker les false negatives ? genre l’anomaly detection marche pas sur les transactions <5k CHF. et pis faut que je fasse […]”'] ],
    hl: { 'Age': ['23–27', 'age 24'], 'Gender': ['Female', 'female'], 'Education': ["Master's degree", 'Master’s'],
          'Main language (top 10)': ['French', 'French'], 'Code-switching': ['Medium', 'medium'], 'Capitalization': ['all lowercase', '“all lowercase”'] } },
  { id: 'ua', chip: 'Zaporizhzhia', fig: 'Figure 11', tag: 'ZP', head: '22 · F · Zaporizhzhia, Ukraine',
    seed: { region: 'Zaporizhzhia, Ukraine', sector: 'Software & IT' },
    bg: [ ['Age', '22', ['Age']], ['Gender', 'Female', ['Gender']], ['Job title', 'Junior ML engineer at logistics startup building routing AI'],
          ['Education', 'Bachelor’s degree', ['Education']],
          ['Language', 'Ukrainian (main) · Ukrainian (native) · dialect Eastern Ukrainian', ['Main language (top 10)']] ],
    st: [ ['Free-text style', 'Uses lowercase mostly, rarely adds punctuation, mixes English tech terms and Ukrainian slang in one sentence like ‘demo strukhnulo tyznya’ (demo broke earlier week)'],
          ['Code-switching', 'Medium', ['Code-switching']],
          ['Quirks', ['Self-deprecating humor about rookie mistakes: ‘ada dlya mene na inshomu movi slovo ‘debug’ dosylo’ (for me in […]', 'Uses UI/UX jargon like ‘latency’ and ‘user flow’ as everyday adjectives']],
          ['Example message', '“prymyrsya: i need a clean dataset for the new routing model. is there a way to filter out the duplicate coordinates without writing a custom script, or should i just preprocess it in pandas before […]”'] ],
    hl: { 'Age': ['18–22', 'age 22'], 'Gender': ['Female', 'female'], 'Education': ["Bachelor's degree", 'Bachelor’s'],
          'Main language (top 10)': ['Ukrainian', 'Ukrainian'], 'Code-switching': ['Medium', 'medium'] } }
];
window.PF_PERSONAS = BK;   // the hero's spec sheet reads these, so both always agree
const BG_SCHEMA = ['Age', 'Gender', 'Job title', 'Education', 'Language', 'Hobbies', 'AI stance', 'Digital fluency', 'Character'];
const ST_SCHEMA = ['Free-text style', 'Sentence length', 'Question framing', 'Error patterns', 'Code-switching', 'Reference pool', 'Capitalization', 'Punctuation', 'Emoji', 'Abbreviations', 'Typos', 'Structure', 'Sign-off', 'Quirks', 'Example message'];
// readout charts per stage (keys of D.background / D.style)
const SEED_KEYS = ['Macro-region', 'Occupation (top 10 of 575)', 'Generator model'];
const BG_KEYS = ['Age', 'Gender', 'Education', 'Digital fluency', 'AI stance', 'Main language (top 10)'];
const ST_KEYS = ['Capitalization', 'Punctuation', 'Emoji use', 'Typo tendency', 'Message structure', 'Sentence length', 'Code-switching', 'Question framing'];
const TABLE4 = ['Gender', 'Digital fluency', 'AI stance', 'Generator model'];

function el(tag, cls, text, parent){ const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; if (parent) parent.appendChild(n); return n; }
function srcOf(key){ if (D.style[key]) return 'Fig. 5'; return TABLE4.includes(key) ? 'Table 4' : 'Fig. 4'; }
function rowsOf(key){ return D.style[key] || D.background[key].rows; }
function isApprox(key){ return !D.style[key] && !!D.background[key].approx; }

/* one distribution, optionally with this persona's category in orange */
function drawDist(ch, key, hlCat, compact){
  const rows = rowsOf(key);
  if (key === 'Age'){
    const svg = vcols(ch, { rows: rows.map(r => ({ label: r[0], v: r[1], color: r[0] === hlCat ? 'var(--s2)' : 'var(--s1)' })), fmt: v => '≈' + v + 'k personas', yfmt: v => v + 'k', labelRotate: true, height: compact ? 190 : 230 });
    // vcols reserves a fixed 74px for rotated labels; crop the svg to what the short age labels need
    try { const bb = svg.getBBox(), w = svg.viewBox.baseVal.width, h = Math.ceil(bb.y + bb.height + 4);
      if (h > 40 && h < svg.viewBox.baseVal.height){ svg.setAttribute('viewBox', `0 0 ${w} ${h}`); svg.setAttribute('height', h); } } catch (e) {}
    markLabel(svg, hlCat);
    return;
  }
  const occ = key.startsWith('Occupation');
  markLabel(hbars(ch, { rows: rows.map(r => ({ label: r[0], values: [r[1]], colors: r[0] === hlCat ? ['var(--s2)'] : null })),
    series: [{ name: '% of bank', color: 'var(--s1)' }], fmt: occ ? (v => v.toFixed(2) + '%') : pct, ticks: false, barH: compact ? 10 : 12, labelMax: compact ? 150 : 210 }), hlCat);
}
// colour (not bold: bold would outgrow the measured label column) the persona's category label
function markLabel(svg, cat){
  if (!cat || !svg) return;
  svg.querySelectorAll('text').forEach(t => {
    const own = t.firstChild && t.firstChild.nodeType === 3 ? t.firstChild.nodeValue : '';
    const full = t.querySelector('title') ? t.querySelector('title').textContent : own;
    if (full === cat) t.classList.add('hlab');
  });
}
const UNIT = { 'Age': 'personas per age bin (thousands) · mean ' + BANK_X.meanAge + ' years', 'Main language (top 10)': '% of bank · ' + BANK_X.languages + ' languages in total' };
// a readout chart whose labels hbars would cut in a half-width panel spans the full readout (same rule as hbarsCore's label column)
const isLong = (key, gridW) => key !== 'Age' && gridW > 560 && measure(rowsOf(key).map(r => r[0])) > Math.min(150, 0.42 * (gridW - 22) / 2) - 2;

(function assembly(){
  const lineEl = $('#bkLine'), card = $('#bkCard'), out = $('#bkOut'), chips = $('#bkChips');
  let p = BK[0], timers = [];
  const local = [];

  BK.forEach((x, i) => {
    const b = el('button', 'chip', x.chip, chips); b.type = 'button'; b.setAttribute('aria-pressed', i ? 'false' : 'true');
    b.title = 'Persona printed in the paper';
    b.addEventListener('click', () => { $$('.chip', chips).forEach(c => c.setAttribute('aria-pressed', c === b ? 'true' : 'false')); p = x; line.stop(); line.show(line.stage, false); });
  });

  const anim = (node, i, on) => { if (!on || reduce) return node; node.classList.add('in'); node.style.animationDelay = (i * 70) + 'ms'; return node; };

  /* ---------- work piece: the persona card ---------- */
  function field(parent, f, linkKeys, i, on){
    const d = el('div', 'field', null, parent);
    const keys = (f[2] || []).filter(k => linkKeys.includes(k) && p.hl[k] && rowsOf(k).some(r => r[0] === p.hl[k][0]));
    if (keys.length) d.dataset.k = keys.join('|');
    el('span', 'fn' + (keys.length ? ' has' : ''), keys.length ? '●' : '·', d);
    el('span', 'fk', f[0], d);
    const v = el('span', 'fv', null, d);
    if (Array.isArray(f[1])){ const ul = el('ul', 'quirks', null, v); f[1].forEach(q => el('li', null, q, ul)); }
    else v.textContent = f[1];
    return anim(d, i, on);
  }
  function layer(title, sub, on){
    const L = el('div', 'layer', null, card);
    const lh = el('div', 'lh', null, L); el('span', null, title, lh); el('span', null, sub, lh);
    return anim(L, 0, on);
  }
  function missing(L, schema, given){
    const m = schema.filter(k => !given.includes(k) && !(k === 'Character' && given.includes('Summary')));
    if (m.length) el('p', 'missing', 'Not shown in the paper: ' + m.map(s => s.startsWith('AI') ? s : s.toLowerCase()).join(', ') + '.', L);
  }
  function renderCard(s, animate){
    card.replaceChildren();
    const linkKeys = s === 0 ? SEED_KEYS : s === 1 ? BG_KEYS : s === 2 ? ST_KEYS : [];
    const who = el('div', 'who', null, card);
    el('div', 'avatar', p.tag, who);
    const tx = el('div', null, null, who); el('b', null, p.head, tx); el('span', null, 'Persona from the paper', tx);
    // verdict stamps sit on top of the card, where they are seen without scrolling the long card
    if (s >= 3){
      const st = el('div', 'stamps', null, card); anim(st, 0, animate && s === 3);
      el('span', 'stamp ok', 'Judge: kept', st).title = 'Inferred: this persona is in the released bank, which keeps only judge-passed profiles';
      if (s >= 4) anim(el('span', 'stamp bank', 'In the bank · 1 of ' + fmt0(D.bankGate.kept), st), 2, animate && s === 4);
    }

    let L = layer('Seed cell', 'drawn from the grid', animate && s === 0);
    const occKeys = p.hl['Occupation (top 10 of 575)'] ? ['Occupation (top 10 of 575)'] : [];
    field(L, ['Region', p.seed.region, p.hl['Macro-region'] ? ['Macro-region'] : []], linkKeys, 1, animate && s === 0);
    field(L, ['Sector', p.seed.sector], linkKeys, 2, animate && s === 0);
    const o = field(L, ['Occupation', p.seed.occ || 'not printed (job title below)', occKeys], linkKeys, 3, animate && s === 0);
    if (!p.seed.occ) o.classList.add('dim');
    const g = field(L, ['Generator', 'not named in the paper'], linkKeys, 4, animate && s === 0); g.classList.add('dim');
    el('p', 'missing', 'Occupation is drawn independently of region. The seed also fixes age, gender, AI stance and digital fluency.', L);
    if (s < 1) return;

    L = layer('Background layer', 'who they are', animate && s === 1);
    p.bg.forEach((f, i) => field(L, f, linkKeys, i + 1, animate && s === 1));
    missing(L, BG_SCHEMA, p.bg.map(f => f[0]));
    if (s < 2) return;

    L = layer('Style layer', 'how they type', animate && s === 2);
    p.st.forEach((f, i) => field(L, f, linkKeys, i + 1, animate && s === 2));
    missing(L, ST_SCHEMA, p.st.map(f => f[0]));
  }

  /* ---------- readout ---------- */
  function head(parent, title, src, approx, num){
    const h = el('div', 'mh', null, parent);
    el('b', null, title, h);
    const r = el('span', 'tags', null, h);
    if (approx) el('span', 'approx', 'read from figure', r);
    el('span', 'src', src, r);
    return h;
  }
  function mini(grid, key, i, on){
    const m = el('div', 'mini', null, grid); m.dataset.k = key;
    head(m, key, srcOf(key), isApprox(key));
    const ch = el('div', 'chart', null, m);
    const h = p.hl[key];
    const inRows = h && rowsOf(key).some(r => r[0] === h[0]);
    const fn = () => { m.classList.toggle('wide', isLong(key, grid.clientWidth)); drawDist(ch, key, inRows ? h[0] : null, true); };
    local.push(fn); fn();
    if (UNIT[key]) el('div', 'unit', UNIT[key], m);
    const pv = el('p', 'pv' + (inRows ? '' : ' none'), null, m);
    if (inRows){ el('i', null, null, pv); pv.append(p.chip + ': ' + h[1]); }
    else if (h) pv.textContent = p.chip + ': ' + h[1] + ', outside the top 10 shown';
    else if (key === 'Generator model') pv.textContent = 'The paper does not name the generator of this profile.';
    else pv.textContent = 'Not stated for this persona.';
    if (inRows) m.classList.add('has');
    return anim(m, i, on);
  }
  function tiles(parent, items, on){
    const t = el('div', 'tiles', null, parent); t.dataset.n = items.length;
    items.forEach(([v, l], i) => { const d = el('div', null, null, t); el('b', null, v, d); el('small', null, l, d); anim(d, i, on); });
    return t;
  }
  function note(parent, txt){ return el('p', 'rnote', txt, parent); }
  function hlLegend(){ out.appendChild(legend([{ name: 'Whole bank', color: 'var(--s1)' }, { name: 'This persona', color: 'var(--s2)' }])); }

  function renderOut(s, animate){
    out.replaceChildren(); local.length = 0;
    const on = animate;
    if (s === 0){
      el('h4', 'rh', 'Where the seed is drawn from', out);
      tiles(out, [['177', 'countries'], ['599', 'sub-regions'], [String(BANK_X.macroRegions), 'macro-regions'], ['575', 'occupations in 23 sectors']], on);
      hlLegend();
      const g = el('div', 'minis', null, out);
      SEED_KEYS.forEach((k, i) => mini(g, k, i + 1, on));
      note(out, 'Occupations are sampled independently of region: an early version made watchmaker or software engineer the most common Swiss job.');
    } else if (s === 1){
      el('h4', 'rh', 'Background layer across the bank', out);
      hlLegend();
      const g = el('div', 'minis', null, out);
      BG_KEYS.forEach((k, i) => mini(g, k, i + 1, on));
      note(out, 'Digital fluency is matched to the occupation sector. The bank skews younger, more educated and more fluent than a representative population.');
    } else if (s === 2){
      el('h4', 'rh', 'Style layer across the bank', out);
      hlLegend();
      const g = el('div', 'minis', null, out);
      ST_KEYS.forEach((k, i) => mini(g, k, i + 1, on));
      note(out, 'Written in the same pass as the background and conditioned on it. A profile is rejected before judging if it lacks a style description, an example message or the structured keys, or has fewer than two quirks.');
    } else if (s === 3){
      const G = D.bankGate;
      el('h4', 'rh', 'MiniMax-M2.5 judges every profile', out);
      tiles(out, [[fmt1(G.judgeKeep) + '%', 'of candidates kept'], [fmt2(G.realism) + ' / 3', 'mean realism'], ['out of family', 'not one of the generators']], on);
      const m = el('div', 'meters', null, out); anim(m, 1, on);
      head(m, 'Checks passed (% of candidates)', 'Table 4', false);
      G.checks.forEach(c => { const r = el('div', 'meter', null, m); el('span', null, c.name, r); el('span', 'mv', pct(c.v), r); const b = el('div', 'bar', null, r); const f = el('b', null, null, b); f.style.width = c.v + '%'; });
      const gw = el('div', 'mini wide', null, out); anim(gw, 2, on);
      head(gw, 'Generators: share of bank and judge keep rate', 'Table 4', false);
      const ch = el('div', 'chart', null, gw);
      const fn = () => hbars(ch, { rows: G.generators.map(x => ({ label: x.name, values: [x.share, x.keep] })), series: [{ name: 'Share of bank', color: 'var(--s1)' }, { name: 'Judge keep rate', color: 'var(--s3)' }], max: 100, ticks: [0, 25, 50, 75, 100], barH: 11 });
      local.push(fn); fn();
      note(out, 'A two-pass repair corrects implausibly low fluency for technical roles and rewrites age-incoherent job titles before re-judging. Rates are over the ' + fmt0(BANK_X.verdictsStored) + ' candidates with stored verdicts.');
    } else {
      const G = D.bankGate;
      el('h4', 'rh', 'From candidates to the released bank', out);
      const f = el('ol', 'funnel', null, out);
      [[fmt0(G.generated), 'candidates generated', 'Three open generators, near-equal shares', 100],
       [fmt1(G.judgeKeep) + '%', 'kept by the judge', 'MiniMax-M2.5, out of family', null],
       ['−' + fmt0(G.diversityRemoved), 'removed by the diversity filter', 'Near-duplicate descriptions and per-cell caps', null],
       [fmt0(G.kept), 'profiles released', fmt1(G.keepRate) + '% of everything generated', 100 * G.kept / G.generated]]
        .forEach(([v, l, sub, w], i) => {
          const li = el('li', w != null ? 'has-bar' : 'step', null, f);
          const top = el('div', 'ft', null, li); el('b', null, v, top); el('span', null, l, top);
          el('small', null, sub, li);
          if (w != null){ const b = el('div', 'bar', null, li); const fill = el('i', null, null, b); fill.style.width = w + '%'; }
          anim(li, i, on);
        });
      tiles(out, [[String(BANK_X.languages), 'main languages'], [fmt0(D.headline.dialects), 'dialect labels'], [String(BANK_X.meanAge), 'mean age (18–80)']], on);
      // where this persona's stated values sit in the bank (age bins are counts, not shares, so they are left out)
      const mine = Object.entries(p.hl).filter(([k, h]) => k !== 'Age' && rowsOf(k).some(r => r[0] === h[0]));
      const sm = el('div', 'meters mine', null, out); anim(sm, 5, on);
      head(sm, p.chip + ': share of the bank with the same value', 'Table 4, Figs. 4–5', mine.some(([k]) => isApprox(k)));
      mine.forEach(([k, h]) => {
        const v = rowsOf(k).find(r => r[0] === h[0])[1];
        const r = el('div', 'meter', null, sm);
        const lab = el('span', null, null, r); el('span', 'mk', k.replace(/ \(top 10.*\)$/, '') + ' · ', lab); lab.append(h[0]);
        el('span', 'mv', v < 1 ? v.toFixed(2) + '%' : pct(v), r);
        const b = el('div', 'bar', null, r); el('b', null, null, b).style.width = v + '%';
      });
      el('div', 'unit', '% of the ' + fmt0(G.kept) + ' released profiles, 0–100 scale. Only values the paper states for this persona.', sm);
      note(out, 'Largest countries: ' + BANK_X.topCountries.map(c => c[0] + ' ' + fmt0(c[1])).join(', ') + ' profiles.');
    }
    wire();
  }

  function wire(){
    const all = $$('[data-k]', lineEl);
    const lit = keys => all.forEach(x => x.classList.toggle('lit', !!keys && x.dataset.k.split('|').some(k => keys.includes(k))));
    all.forEach(x => {
      if (x.classList.contains('field') || x.classList.contains('has')){
        x.addEventListener('pointerenter', () => lit(x.dataset.k.split('|')));
        x.addEventListener('pointerleave', () => lit(null));
      }
    });
  }

  function render(s, animate){
    timers.forEach(clearTimeout); timers = [];
    renderCard(s, animate); renderOut(s, animate);
    $('#bkSrc').textContent = 'Persona: paper ' + p.fig + ' · bank: Table 4, Figs. 3–5';
  }
  const line = lineCtl(lineEl, { count: 5, render, dur: s => s === 2 ? 3200 : 2400, onStop: () => { timers.forEach(clearTimeout); timers = []; } });
  renders.push(() => local.forEach(f => f()));
})();

/* ---------- Bank at a glance: every distribution, full size ---------- */
(function glance(){
  const grid = $('#bkGrid');
  const local = [];
  function card(title, src, opts = {}){
    const c = el('div', 'card' + (opts.wide ? ' span2' : ''), null, grid);
    const h = el('h3', null, null, c); el('span', null, title, h);
    const r = el('span', 'tags', null, h);
    if (opts.approx) el('span', 'approx', 'read from figure', r);
    el('span', 'src', src, r);
    const ch = el('div', 'chart', null, c);
    if (opts.cap) el('p', 'cap', opts.cap, c);
    return ch;
  }
  const CAPS = { 'Age': 'Adults only (18–80), mean 39.6 years. Bin edges approximate.', 'Occupation (top 10 of 575)': 'Students and technology roles lead.', 'Main language (top 10)': '282 languages and 117,670 free-text dialect labels.', 'Emoji use': 'Frequent decorative emoji is capped near 5% because it would otherwise dominate rewrites.', 'Capitalization': 'Almost a quarter type in all lowercase.', 'Punctuation': 'About two fifths drop end punctuation.' };
  function dist(k){
    const ch = card(k, srcOf(k), { approx: isApprox(k), cap: CAPS[k], wide: k === 'Generator model' });
    const fn = () => { drawDist(ch, k, null, false); el('div', 'unit', k === 'Age' ? 'personas per age bin (thousands)' : '% of bank', ch); };
    local.push(fn); fn();
  }
  function view(v){
    grid.replaceChildren(); local.length = 0;
    grid.className = 'grid ' + (v === 'style' ? 'g3' : 'g2');   // two columns where labels are long
    if (v === 'seed') SEED_KEYS.forEach(dist);
    else if (v === 'background'){
      // tall charts pair up; the three short Table 4 splits share one card so no card is left half empty
      ['Age', 'Education', 'Main language (top 10)'].forEach(dist);
      const ch = card('Gender, digital fluency, AI stance', 'Table 4', {});
      const fn = () => { ch.replaceChildren(); ['Gender', 'Digital fluency', 'AI stance'].forEach(k => {
        el('div', 'subk', k, ch); const d = el('div', null, null, ch); drawDist(d, k, null, false); });
        el('div', 'unit', '% of bank', ch); };
      local.push(fn); fn();
    }
    else if (v === 'style') ST_KEYS.forEach(dist);
    else {
      const G = D.bankGate;
      const ch1 = card('Generators: share of bank and judge keep rate', 'Table 4', { wide: true, cap: 'Three open-weight models, chosen to balance geographic and multilingual strengths. Keep rates are over the ' + fmt0(BANK_X.verdictsStored) + ' candidates with stored verdicts.' });
      const f1 = () => hbars(ch1, { rows: G.generators.map(g => ({ label: g.name, values: [g.share, g.keep] })), series: [{ name: 'Share of bank', color: 'var(--s1)' }, { name: 'Judge keep rate', color: 'var(--s3)' }], max: 100, ticks: [0, 25, 50, 75, 100], barH: 12 });
      local.push(f1); f1();
      const ch2 = card('Judge checks (MiniMax-M2.5)', 'Table 4', { cap: 'Mean realism is ' + fmt2(G.realism) + ' of 3. Pass rates are over the ' + fmt0(BANK_X.verdictsStored) + ' candidates with stored verdicts.' });
      const f2 = () => hbars(ch2, { rows: G.checks.map(g => ({ label: g.name, values: [g.v] })), series: [{ name: 'pass rate', color: 'var(--s1)' }], max: 100, ticks: [0, 50, 100], barH: 12, unit: '% of candidates passing' });
      local.push(f2); f2();
      const ch3 = card('From candidates to bank', 'Table 4', { cap: 'The judge keeps ' + fmt1(G.judgeKeep) + '%. A diversity filter (near-duplicate descriptions, per-cell caps) then removes ' + fmt0(G.diversityRemoved) + '. ' + fmt1(G.keepRate) + '% of candidates are released.' });
      const f3 = () => hbars(ch3, { rows: [{ label: 'Generated', values: [G.generated] }, { label: 'Released', values: [G.kept] }], series: [{ name: 'profiles', color: 'var(--s1)' }], fmt: fmt0, ticks: false, barH: 16, unit: 'profiles' });
      local.push(f3); f3();
    }
  }
  segCtl('#bkSeg', view);
  view('seed');
  renders.push(() => local.forEach(f => f()));
})();
