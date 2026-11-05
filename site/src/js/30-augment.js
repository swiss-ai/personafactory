/* ======================= AUGMENTATION DEMO ======================= */
// Augmented text uses [[n|span]] markers that link to profile field n.
const EX = [
  { id: 'fl', chip: 'Florida · English', ini: 'MR', name: '23 · F · Florida, USA', blurb: 'TA and PhD candidate in bilingual education policy; skeptical of AI because model output reads “too polished”.', src: 'Figure 2',
    bg: [ [1,'Region','North America → USA → Florida'], [2,'Occupation','Graduate student, education sector: TA and PhD candidate in bilingual education policy (ESL/ML), public university'], [0,'Education','Master’s, bilingual education / policy'], [0,'Language','English native · Floridian Spanish English · high code-switching'], [0,'AI stance','Skeptical · digital fluency high'], [0,'References','Education-policy memes on TikTok · indie Latin music · Valorant'] ],
    st: [ [6,'Free-text style','all-lowercase messages with elliptical punctuation, drops articles, Spanish loanwords, almost always ends with a question or backchannel'], [4,'Abbreviations','u r k · sometimes xq = porque'], [5,'Emoji rule','Frequent, decorative: 💀 😭 🎉'], [3,'Sign-off','ok or no? · capitalization first-word-only, no final period'], [0,'Quirks','spells “academick” when frustrated · code-switches mid-sentence'] ],
    match: { lang: 'English (Latin)', set: 'Language-matched', tier: 'Location: “San Antonio”, Texas → US personas', resp: 'Gemma-4-31B' },
    turns: [ { seed: 'Can you give me some recommendations for other parks in San Antonio that are worth visiting?', aug: '[[6|yo just curious if]] [[4|u]] can hook me up with some other parks in san antonio that’re actually worth the trip [[3|no?]] like the ones that don’t feel like they got approved by some [[1|florida]] [[2|education bureaucrat]] just to check a box [[5|😭]]' } ],
    bot: 'ok so skipping the ones that feel like a checkbox: Hardberger Park has the land bridge and actual woods, the Japanese Tea Garden is a quiet one, and Mission Reach along the river is great on a bike…', botIllustrative: true
  },
  { id: 'be', chip: 'Bern · Swiss German', ini: 'AD', name: '23 · M · Bern, Switzerland', blurb: 'Mechanical CAD designer at a machine-tool prototyping firm, freelance subcontracts.', src: 'Figure 7 · Nemotron 234625',
    bg: [ [1,'Region','Bern, Switzerland'], [0,'Occupation','Mechanical CAD designer (Engineering sector)'], [0,'Education','Vocational / trade training'], [2,'Language','German (main), Swiss German native, Bernese dialect · code-switching high'] ],
    st: [ [3,'Free-text style','short sentences, minimal punctuation, German contractions leaking in (‘und → &’)'], [4,'Sign-off','ends with ‘ok’ or ‘no?’ for most questions'], [0,'Quirks','‘sä’ as filler; ‘düber’ for digital terms'], [0,'Example','“hey. just checked the stl export from last model - some faces in the reverse-mitered joint are flipped…”'] ],
    match: { lang: 'German (Latin)', set: 'Language-matched', tier: 'Location pool', resp: 'Gemma-4-31B' },
    turns: [ { seed: 'Hallo, ich bin Andreas Dim. Kannst du Deutsch sprechen?', aug: '[[3|hallo, bin andreas dim.]] [[2|chasch]] du deutsch spreche, [[4|ok?]]', gloss: '“hello, i’m andreas dim. can you speak german, ok?” (chasch is Bernese for kannst; the request is unchanged)' },
             { seed: 'Das ist toll, Nemotron! Kannst du mir helfen, einen Brief auf Deutsch zu verfassen? Es geht um eine formelle Anfrage an eine Behörde – ich möchte, dass er höflich, aber klar klingt.', aug: '[[3|cool, Nemotron.]] hilfst du mir bsp. einen brief auf deutsch zu schreiben? formelle anfrage an eine behörde - soll höflich [[3|&]] klar klingen. [[4|ok?]]' } ],
    bot: 'Hallo Andreas. Ja, ich kann Deutsch sprechen. Wie kann ich dir helfen, ok?'
  },
  { id: 'zh', chip: 'Zurich · verbatim guard', ini: 'RG', name: '66 · F · Zurich, Switzerland', blurb: 'Part-time checkout operator at a large supermarket chain.', src: 'Figure 8 · UltraChat 3168',
    bg: [ [0,'Region','Zurich, Switzerland'], [0,'Occupation','Checkout operator (Sales & retail)'], [0,'Language','German (main), Swiss German dialect · code-switching low'] ],
    st: [ [1,'Free-text style','complete sentences, standard capitalization, often multiple exclamation marks and friendly emojis'], [2,'Quirks','uses ‘Grüezi’ as a habitual greeting even in text'], [3,'Quirks','frequent smiley to soften requests'] ],
    match: { lang: 'English (Latin)', set: 'Cross-lingual (register only)', tier: 'Cross-lingual', resp: 'Gemma-4-31B' },
    turns: [ { seed: 'All 25 houses in Dadagaun village, Nepal, were destroyed by the quake. Jenny reports on rescue work in Nepal - April Aid agencies used helicopters to get help and supplies to people who live in […]', aug: 'All 25 houses in Dadagaun village, Nepal, were destroyed by the quake. Jenny reports on rescue work in Nepal - April Aid agencies used helicopters to get help and supplies to people who live in […]', guard: true },
             { seed: 'Can you provide me with some more information on how the earthquake affected the people of Nepal and how the country is recovering from the disaster?', aug: '[[2|Grüezi!]] I have been thinking about the earthquake in Nepal, and I was wondering if you could provide me with some more information on how it affected the people there and how the country is recovering from the disaster[[1|???]] [[3|🙂🙏]]' } ],
    bot: 'Grüezi! Based on the text provided, here is more information regarding the impact on the people and the recovery efforts in Nepal: Impact on the People. Loss of Life and Injury: nearly 9,000 people died and nearly 22,000 were injured…'
  },
  { id: 'gl', chip: 'Geneva · code-switching', ini: 'LB', name: '29 · M · Geneva, Switzerland', blurb: 'Senior clinical microbiology lab tech at Geneva University Hospital’s diagnostics division.', src: 'Figure 9 · Nemotron 116857',
    bg: [ [0,'Region','Geneva, Switzerland'], [0,'Occupation','Clinical microbiology lab tech (Healthcare)'], [1,'Language','French (main), Swiss French native, Genevois · code-switching high'] ],
    st: [ [2,'Free-text style','terse, minimal punctuation, heavy French/English switching, lowercase for informal messages'], [3,'Quirks','‘labo’ instead of laboratoire, even in English'], [4,'Quirks','substitutes ‘pff’ when frustrated'], [5,'Sign-off','ends messages with a short French sign-off'] ],
    match: { lang: 'English (Latin)', set: 'Cross-lingual', tier: 'Cross-lingual', resp: 'Ministral-3-14B' },
    turns: [ { seed: 'Hey, I was just rewatching that old vet show from the early 2000s — the one with the quirky small-town clinic and the way the staff always ended up in the middle of bizarre animal emergencies. Do you remember that? I’m curious — what’s the most unexpected thing you’ve ever seen a pet do?', aug: '[[2|hey was just rewatching]] that old vet show again - ya know the one with dr. stone’s [[3|labo]] disasters and the goat that got into the ultrasound gel. [[1|ouais]] but like what’s the wildest pet behavior u’ve seen? not the “cat in the sink” stuff but the [[4|*pff*]] “why did i just find a parrot with a pipette in its beak” level of chaos. [[5|à+]]' } ],
    bot: 'ouais, i’ve got some trop wild ones from labo gossip circles - though nothing beats the time a lab tech in Lyon (don’t ask how i know this) found a macaque in the PCR hood…', botWarn: 'The paper keeps this sanity-gate miss on purpose. The reply claims first-person experience, which the fabricated-experience class should have caught.'
  },
  { id: 'fr', chip: 'Geneva · cross-lingual FR', ini: 'CM', name: '24 · F · Geneva, Switzerland', blurb: 'ML ops engineer at a fintech scale-up, working on fraud-detection models.', src: 'Figure 10 · UltraChat 1042',
    bg: [ [0,'Region','Geneva, Switzerland'], [4,'Occupation','ML ops engineer, fraud detection (Software & IT)'], [1,'Language','French (main), Swiss French native · code-switching medium'] ],
    st: [ [2,'Free-text style','fragmented technical terms, French abbreviations, all lowercase, ends with ‘?’ even if not a question'], [3,'Quirks','‘pq’ / ‘pqoui’ for pourquoi when confused'], [5,'Quirks','‘je te kiffe’ instead of ‘j’adore’ in informal chats'] ],
    match: { lang: 'English → French', set: 'Cross-lingual (translate, then restyle)', tier: 'Cross-lingual', resp: 'Ministral-3-14B' },
    turns: [ { seed: 'How can loved ones support someone experiencing empty nest syndrome and their mental health?', aug: '[[1|comment les proches peuvent aider]] [[2|qqun]] en crise du nid vide et son mental sain [[3|pq]] ça c’est vraiment une galère, tu as des conseils ou des ressources [[3|pq]] je veux pas merder là-dessus [[2|?]]', gloss: '“how can loved ones support someone in an empty-nest crisis and their mental health, because that is really tough, do you have advice or resources, because i don’t want to mess this up?”' },
             { seed: 'I think I’ll try to plan some fun activities with my loved one to help them feel better. Do you have any specific activity ideas?', aug: 'salut je [[5|kiffe]] l’idée d’organiser qqch p notre bien-aimé·e p l’aider à décompresser t’as des idées d’activités sympas à proposer ? genre [[3|pqoui]] j’ai rien sous la main là.' },
             { seed: 'I think a weekend getaway sounds like a great idea! Do you have any recommendations for a nice and relaxing destination?', aug: 'un w-e relax [[5|kifferait]] bien ouais tu connais des coins sympa [[3|pq]] là j’ai aucune idée genre un endroit où on peut décompresser sans stress [[4|(trop d’API first en ce moment pour que ça soit un trip tech)]]' } ],
    bot: 'voici une liste structurée avec des pistes concrètes, adaptées à un soutien sans bienveillance toxique (le pire dans ces cas). tout est classé par type d’aide, avec des ressources en français/CH/UE…'
  },
  { id: 'ua', chip: 'Zaporizhzhia · Ukrainian', ini: 'OK', name: '22 · F · Zaporizhzhia, Ukraine', blurb: 'Junior ML engineer at a logistics startup building routing AI.', src: 'Figure 11 · Nemotron 240612',
    bg: [ [0,'Region','Zaporizhzhia, Ukraine'], [3,'Occupation','Junior ML engineer, routing AI (Software & IT)'], [1,'Language','Ukrainian (main), Eastern Ukrainian · code-switching medium'] ],
    st: [ [2,'Free-text style','lowercase mostly, rarely punctuates, mixes English tech terms and Ukrainian slang in one sentence'], [4,'Quirks','UI/UX jargon like ‘latency’ and ‘user flow’ as everyday words'] ],
    match: { lang: 'English → Ukrainian (romanised)', set: 'Cross-lingual', tier: 'Cross-lingual', resp: 'Ministral-3-14B' },
    turns: [ { seed: 'Hi, I’m planning a low-cost trip to Albania from August 7 to 18, 2023, and I need help putting together a realistic itinerary that includes affordable flight options. Can you suggest the best budget airlines, cheapest entry points, and a day-by-day plan that covers must-see spots without breaking the bank?', aug: '[[1|planyu povtorne:]] [[2|low-cost trip]] do albanii z 7 po 18 avqusta, 2023, shchoby vstanovyt realnyy [[2|itinerary]] z uchetam [[2|budget flightov]]. mozhlyvo posoradyt deshevi shliakhy, cherez kakyi aeroport lepshe priletat, i [[2|day-bi-day plan]] z must-see spravdzheno bez zbytochnykh vytrat [[3|rekyuemnts:]] 1. budget airlines dlya marshrutu 2. cheapest entry point (aeroport/port) do albanii 3. day-by-day plan (12 dney) z obov’yazkovymy lokatsiyamy […]', gloss: '“planning again: a low-cost trip to Albania from 7 to 18 August 2023… which cheap routes, which airport is better to fly into, and a day-by-day plan of must-sees without excess spending”' } ],
    bot: 'отлично, давайте розберемось з бюджетним маршрутом до Албанії на 7 - 18 серпня 2023 року з акцентом на реальний itinerary, дешеві перельоти та ефективний маршрут без зайвих витрат. 1. Бюджетні авіакомпанії для маршруту…'
  },
  { id: 'vi', chip: 'Vietnam · Vietnamese', ini: 'TN', name: '24 · M · Vietnam', blurb: 'Factory line worker in manufacturing.', src: 'Figure 6 · UltraChat 74264',
    bg: [ [0,'Region','Vietnam'], [4,'Occupation','Factory line worker (Manufacturing)'], [1,'Language','Vietnamese (main / native), English technical terms'] ],
    st: [ [2,'Free-text style','lowercase tendency, minimal punctuation, casual particle endings (nhé, á, ah)'], [3,'Structure','bulleted prompt structure'], [5,'Quirks','mk for mình (self-reference)'] ],
    match: { lang: 'English → Vietnamese', set: 'Cross-lingual', tier: 'Cross-lingual', resp: 'Gemma-4-31B' },
    turns: [ { seed: 'Write a free verse poem that delves into the intricacies of the cosmos, discussing the mysteries of dark matter and black holes, the birth and death of stars, and the infinite expanse of space. Use vivid imagery and descriptive language to convey the sheer scale and majesty of the universe, while also exploring the complexities of our place within it.', aug: '[[1|viết 1 bài thơ tự do]] mà khám phá những bí ẩn của vũ trụ [[2|nhé]]\n[[3|cụ thể phải nhắc đến:\n1.]] dark matter và black holes (chỉ cần nói đc tính chất của nó là đủ)\n[[3|2.]] sự ra đời và chết của những vì sao (những hình ảnh sống động)\n[[3|3.]] vẻ vô tận của không gian...\ngiống như khi [[4|xem video DIY sửa phone]] mà có cảm giác ’đẹp quá’ vậy', gloss: '“write a free verse poem exploring the mysteries of the universe, specifically mentioning: 1. dark matter and black holes… 2. birth and death of stars (vivid imagery)… like the ‘so beautiful’ feeling when watching a phone repair DIY video”' },
             { seed: 'Wow, the poem you generated is truly mesmerizing… Would it be possible for you to add some information on how the concept of dark matter was first hypothesized…', aug: 'thế bài thơ của anh hay quá [[2|á]], hình ảnh còn sống động như mình đang bay trong vũ trụ vậy đấy [[2|ah]]. anh có thể cho [[5|mk]] thêm về dark matter không?...' } ],
    bot: 'The model acknowledges the user in natural Vietnamese and explains the cosmology while matching the interactive context.', botSummary: true
  }
];
const CHECKS = ['Language matches', 'Instruction / format kept', 'Not truncated', 'No fabricated experience', 'No hallucination', 'Request addressed'];
(function demo(){
  const chips = $('#exChips'), pcard = $('#pcard'), chat = $('#chat'), stagesEl = $('#stages');
  let ex = EX[0], typing = null;
  EX.forEach((e, i) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'chip'; b.textContent = e.chip; b.setAttribute('aria-pressed', i ? 'false' : 'true'); b.addEventListener('click', () => { $$('.chip', chips).forEach(x => x.setAttribute('aria-pressed', x === b ? 'true' : 'false')); ex = e; line.stop(); line.show(3, false); }); chips.appendChild(b); });

  function fieldRow(f){
    const d = document.createElement('div'); d.className = 'field'; if (f[0]) d.dataset.f = f[0];
    const n = document.createElement('span'); n.className = 'fn' + (f[0] ? ' has' : ''); n.textContent = f[0] || '·'; d.appendChild(n);
    const k = document.createElement('span'); k.className = 'fk'; k.textContent = f[1]; d.appendChild(k);
    const v = document.createElement('span'); v.className = 'fv'; v.textContent = f[2]; d.appendChild(v);
    return d;
  }
  function renderCard(){
    pcard.replaceChildren();
    const who = document.createElement('div'); who.className = 'who';
    const av = document.createElement('div'); av.className = 'avatar'; av.textContent = ex.ini; who.appendChild(av);
    const tx = document.createElement('div'); const b = document.createElement('b'); b.textContent = ex.name; const s = document.createElement('span'); s.textContent = ex.blurb; tx.append(b, s); who.appendChild(tx);
    pcard.appendChild(who);
    [['Background layer', 'who they are', ex.bg], ['Style layer', 'how they type', ex.st]].forEach(([h, sub, rows]) => {
      const L = document.createElement('div'); L.className = 'layer';
      const lh = document.createElement('div'); lh.className = 'lh'; const a = document.createElement('span'); a.textContent = h; const c = document.createElement('span'); c.textContent = sub; lh.append(a, c); L.appendChild(lh);
      rows.forEach(f => L.appendChild(fieldRow(f)));
      pcard.appendChild(L);
    });
  }
  // parse [[n|text]] into nodes
  function richNodes(str, limit){
    const out = []; let count = 0; const re = /\[\[(\d)\|([\s\S]*?)\]\]/g; let last = 0, m;
    const push = (txt, n) => {
      if (limit != null && count >= limit) return;
      let t = txt; if (limit != null && count + t.length > limit) t = t.slice(0, limit - count); count += t.length;
      if (n){ const mk = document.createElement('mark'); mk.dataset.f = n; mk.textContent = t; if (t.length === txt.length){ const sup = document.createElement('sup'); sup.textContent = n; mk.appendChild(sup); } out.push(mk); }
      else out.push(document.createTextNode(t));
    };
    while ((m = re.exec(str))){ push(str.slice(last, m.index)); push(m[2], m[1]); last = re.lastIndex; }
    push(str.slice(last));
    return { nodes: out, total: str.replace(re, '$2').length };
  }
  function msg(cls, head, body){
    const d = document.createElement('div'); d.className = 'msg ' + cls;
    if (head){ const h = document.createElement('div'); h.className = 'mh'; head.forEach(x => { const s = document.createElement('span'); s.textContent = x; h.appendChild(s); }); d.appendChild(h); }
    const p = document.createElement('div'); p.style.whiteSpace = 'pre-line'; if (typeof body === 'string') p.textContent = body; else p.append(...body); d.appendChild(p);
    chat.appendChild(d); return p;
  }
  function render(s, animate){
    stage = s;
    renderCard();
    // Source of each example: the paper figure in ex.src (kept in the data, not shown on the page).
    chat.replaceChildren();
    // stage 0: matching
    const mb = document.createElement('dl'); mb.className = 'matchbox';
    [['Detected', ex.match.lang], ['Persona set', ex.match.set], ['Match tier', ex.match.tier], ['Responder', ex.match.resp]].forEach(([k, v]) => { const a = document.createElement('dt'); a.textContent = k; const b = document.createElement('dd'); b.textContent = v; mb.append(a, b); });
    chat.appendChild(mb);
    if (s === 0){ ex.turns.forEach((t, i) => msg('seed', ['original turn ' + (i + 1)], t.seed)); return; }
    // stage 1+: rewritten turns
    const typeTargets = [];
    ex.turns.forEach((t, i) => {
      msg('seed', ['original turn ' + (i + 1)], t.seed);
      const head = [t.guard ? 'kept verbatim by the guard' : 'persona-augmented turn ' + (i + 1)];
      const body = msg('user', head, []);
      typeTargets.push({ body, str: t.aug });
      if (t.gloss){ const g = document.createElement('div'); g.className = 'msg gloss'; g.textContent = 'Gloss: ' + t.gloss; chat.appendChild(g); }
    });
    const after = () => {
      if (s >= 2){
        const head = ['assistant, regenerated', ex.match.resp];
        if (ex.botSummary) head.push('summary from paper');
        if (ex.botIllustrative) head.push('illustrative');
        msg('bot', head, ex.bot + (ex.botSummary || ex.botIllustrative ? '' : ''));
        if (ex.botWarn){ const w = document.createElement('div'); w.className = 'warn'; w.textContent = ex.botWarn; chat.appendChild(w); }
      }
      if (s >= 3){
        const ck = document.createElement('ul'); ck.className = 'checks';
        CHECKS.forEach((c, i) => { const d = document.createElement('li'); d.textContent = c; ck.appendChild(d); if (animate && !reduce) setTimeout(() => d.classList.add('ok'), 180 * (i + 1)); else d.classList.add('ok'); });
        chat.appendChild(ck);
        const v = document.createElement('div'); v.className = 'verdict'; v.textContent = 'Sanity gate: pass, conversation kept';
        if (animate && !reduce){ v.style.opacity = 0; setTimeout(() => v.style.opacity = 1, 180 * 7); }
        chat.appendChild(v);
      }
      wireHL();
    };
    if (animate && s === 1 && !reduce){
      let k = 0;
      const run = () => {
        if (k >= typeTargets.length){ after(); return; }
        const tt = typeTargets[k]; const total = richNodes(tt.str).total; let n = 0;
        const caret = document.createElement('span'); caret.className = 'caret';
        typing = setInterval(() => { n = Math.min(total, n + 3); tt.body.replaceChildren(...richNodes(tt.str, n).nodes); if (n < total) tt.body.appendChild(caret); else { clearInterval(typing); typing = null; k++; run(); } }, 18);
      };
      run();
    } else { typeTargets.forEach(tt => tt.body.replaceChildren(...richNodes(tt.str).nodes)); after(); }
  }
  function wireHL(){
    const lit = n => { $$('[data-f]', $('#demo')).forEach(x => x.classList.toggle('lit', n != null && x.dataset.f === n)); };
    $$('[data-f]', $('#demo')).forEach(x => { x.addEventListener('pointerenter', () => lit(x.dataset.f)); x.addEventListener('pointerleave', () => lit(null)); });
  }
  function stop(){ clearInterval(typing); typing = null; }
  const line = lineCtl($('#demo'), { count: 4, render, onStop: stop, dur: s => s === 1 ? 2600 + ex.turns.reduce((a, t) => a + t.aug.length, 0) * 6 : 1700 });
})();
