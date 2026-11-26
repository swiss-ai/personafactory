/* ======================= AUGMENTATION DEMO ======================= */
// Conversations from the released chats subset (swiss-ai/PersonaFactory), one per persona above.
// src: chats id prefix and seed dataset. Augmented turns and assistant replies are verbatim (long replies cut with …).
// Seed turns after the first come from the public seed dataset (UltraChat); where they are not public, only the rewrite is shown.
// Augmented text uses [[n|span]] markers that link to profile field n.
const EX = [
 {
  "id": "fl",
  "chip": "USA",
  "ini": "FL",
  "name": "27 · M · Florida, USA",
  "blurb": "Freight train operations lead for a regional logistics carrier; ‘might as well try ‘em’ about AI tools.",
  "src": "chats 74e8c8fd · ultrachat",
  "bg": [
   [
    0,
    "Region",
    "North America → USA → Florida"
   ],
   [
    0,
    "Occupation",
    "Train conductor (Logistics & transport): freight train operations lead"
   ],
   [
    1,
    "Language",
    "English native · Central Florida · occasional Southernisms (‘fixin’ to’, ‘y’all’)"
   ],
   [
    0,
    "AI stance",
    "Pragmatic · digital fluency low"
   ]
  ],
  "st": [
   [
    2,
    "Free-text style",
    "first-word capitalization, no final periods, treats digital devices like radios (‘can you clear that up for me’)"
   ],
   [
    3,
    "Quirks",
    "replaces ‘I’ with ‘we’ when describing family logistics"
   ],
   [
    4,
    "Quirks",
    "spells ‘scheduling’ as ‘shedule’ when distracted by phone typing"
   ]
  ],
  "match": {
   "lang": "English (Latin)",
   "set": "Language-matched",
   "tier": "Embedding",
   "resp": "Gemma-4-31B"
  },
  "turns": [
   {
    "seed": "What are some essential items that someone should pack for a camping trip, and how can they prioritize their packing list based on their activity schedule?",
    "aug": "[[3|We]] [[1|fixin' to]] head out and need to know what the essential items are for a camping trip and how [[3|we]] can prioritize that packing list based on the activity [[4|shedule]]"
   },
   {
    "seed": "Do I really need a multi-purpose tool or knife? Can't I just use regular utensils or a kitchen knife?",
    "aug": "Do [[3|we]] really need to go out and get a multi-purpose tool or some kind of knife or can [[3|we]] just use regular utensils or a kitchen knife instead"
   },
   {
    "seed": "Who needs a map and compass when we have GPS on our phones now? Can't we just rely on that?",
    "aug": "Who needs a map and a compass when [[1|we got]] GPS right on our phones now so [[2|can you clear up]] if we can just rely on that"
   }
  ],
  "bot": "Start with the essentials for safety and shelter. You will need a tent, sleeping bags, pads, and a reliable light source like a headlamp or lantern. For food and water, pack a portable stove, fuel, a cooler with ice, and more water than you think you will need.\n\nTo prioritize the packing list based on your schedule, group your gear by when it will be used…"
 },
 {
  "id": "be",
  "chip": "Switzerland (DE · Bern)",
  "ini": "BE",
  "name": "23 · M · Bern, Switzerland",
  "blurb": "Self-employed VAT-compliance auditor for small businesses; skeptical of ‘automatische Lösungen’.",
  "src": "chats 0294ea21 · ultrachat",
  "bg": [
   [
    0,
    "Region",
    "Western Europe → Switzerland → Bern"
   ],
   [
    0,
    "Occupation",
    "Bookkeeping freelancer (Business & finance): self-employed VAT-compliance auditor"
   ],
   [
    1,
    "Language",
    "German (main), Swiss German (Bernese variant) native · code-switching medium"
   ],
   [
    0,
    "AI stance",
    "Skeptical · digital fluency medium"
   ]
  ],
  "st": [
   [
    0,
    "Free-text style",
    "moderate sentence length, occasionally drops periods in quick replies"
   ],
   [
    2,
    "Abbreviations",
    "btw, nvm, lol, thx, pls"
   ],
   [
    3,
    "Quirks",
    "inserts Bärnerdütsch interjections like ‘isch guet’ in place of German ‘klar’"
   ],
   [
    0,
    "Sign-off",
    "‘Grüezi’ or ‘Salü’ if the conversation is local"
   ]
  ],
  "match": {
   "lang": "English → German (Swiss)",
   "set": "Cross-lingual (translate, then restyle)",
   "tier": "Cross-lingual",
   "resp": "Gemma-4-31B"
  },
  "turns": [
   {
    "seed": "Can you describe the architectural significance of the Sydney Opera House, and why it is considered a masterpiece of modern design?",
    "aug": "[[1|Chasch du d'architektonischi Bedütig vom Sydney Opera House beschriibe]] und erkläre, worum es als Meischterwärk vom moderne Design gilt? [[3|Isch guet]], wenn du das churz machsch [[2|btw]]",
    "gloss": "“Can you describe the architectural significance of the Sydney Opera House and explain why it counts as a masterpiece of modern design? Fine if you keep it short btw” (Bernese Swiss German; the English seed is translated, then restyled)"
   },
   {
    "seed": "How has the Sydney Opera House influenced modern architecture and design?",
    "aug": "Wie hät s Sydney Opera House d moderni Architektur und s Design beiflusst?"
   },
   {
    "seed": "It's fascinating how the Sydney Opera House has had such a profound impact on modern architecture and design. Do you know of any other iconic buildings that have similarly influenced the industry?",
    "aug": "S isch faszinierend, wie s Sydney Opera House so en tüüfe Ifluss uf d moderni Architektur und s Design gha hät. Kennsch du no anderi ikonischi Gebäude, wo d Branche ähnlich prägt händ?"
   }
  ],
  "bot": "S Sydney Opera House isch vor allem wäge sinere innovative Form und dr technische Leischtig bekannt. D'Architektur bricht mit de traditionelle, rechteckige Gebäude und nutzt stattdessen die berühmte \"Schalen\" (Sails), wo d'Dynamik vom Wasser und d'Segel vo de Schiffe im Hafen widerspiegle…"
 },
 {
  "id": "zh",
  "chip": "Switzerland (DE · Zurich)",
  "ini": "ZH",
  "name": "35 · M · Zurich, Switzerland",
  "blurb": "Speech therapist for neurodivergent children at a cantonal pediatric clinic.",
  "src": "chats cd274cf3 · ultrachat",
  "bg": [
   [
    0,
    "Region",
    "Western Europe → Switzerland → Zurich"
   ],
   [
    0,
    "Occupation",
    "Speech-and-language therapist (Healthcare): childhood speech neurodiversity specialist"
   ],
   [
    1,
    "Language",
    "German (main), Swiss German native, Zurich dialect · code-switching high"
   ]
  ],
  "st": [
   [
    2,
    "Punctuation",
    "adds ‘??’ to mimic Swiss-German filler pauses in speech"
   ],
   [
    3,
    "Sign-off",
    "‘okay?’ to unknowns and AIs, half-question, half-confirmation"
   ],
   [
    4,
    "Quirks",
    "adds ‘oder’ to questions to soften them"
   ],
   [
    0,
    "Emoji",
    "none"
   ]
  ],
  "match": {
   "lang": "English → German (Swiss)",
   "set": "Cross-lingual (translate, then restyle)",
   "tier": "Cross-lingual",
   "resp": "Gemma-4-31B"
  },
  "turns": [
   {
    "seed": "Can you explain the mechanisms behind various sleep disorders, and how they are treated?",
    "aug": "[[1|Chasch mer erkläre]], wie s' mit dene verschiedene Schlafstörige funktioniert und wie mer die behandlet [[2|??]] [[3|okay?]]",
    "gloss": "“Can you explain how the different sleep disorders work and how they are treated ?? okay?” (Zurich Swiss German)"
   },
   {
    "seed": "Okay, but can you explain in simpler terms how these sleep disorders affect our daily lives? I'm not really understanding it.",
    "aug": "[[3|Okay]], aber chasch mer das [[2|??]] in eifachere Wort erkläre, wie s' Schlafstörige euse Alltag beiflussed [[4|oder?]] Ich checke es nonig ganz... [[3|okay?]]"
   },
   {
    "seed": "Can you recommend any natural remedies for these sleep disorders? I don't really like the idea of taking medications.",
    "aug": "Chasch mir natürlichi Heilmittel für s'Schlafstörige empfehle[[2|??]] Ich find d'Idee, Medikament z'neh, nöd so toll, [[4|oder?]] [[3|okay?]]"
   }
  ],
  "bot": "Schlafstörige sind sehr vielfältig und chönd verschiedeni Ursache ha. Me cha sie grob in es paar Hauptkategorie iiteile:\n\nInsomnie (Iischlaf- und Durchschlafstörige)\nDas isch die hüfigst Form. D'Lüt händ Müeh iizschlafe oder wached i de Nacht uf und chönd nümme schlafe…"
 },
 {
  "id": "ge",
  "chip": "Switzerland (FR)",
  "ini": "GE",
  "name": "52 · F · Geneva, Switzerland",
  "blurb": "Regional courier supervisor in the Swiss postal sector, testing AI dispatch tools.",
  "src": "chats b461b864 · nemotron",
  "bg": [
   [
    0,
    "Region",
    "Western Europe → Switzerland → Geneva"
   ],
   [
    0,
    "Occupation",
    "Postal carrier (Logistics & transport): regional courier supervisor"
   ],
   [
    1,
    "Language",
    "French (main), Swiss French (Genève) native, Romand · code-switching medium"
   ]
  ],
  "st": [
   [
    2,
    "Greeting",
    "‘Salut’ / ‘Ciao’ (informal)"
   ],
   [
    3,
    "Abbreviations",
    "p.ex., stp (s’il vous plaît), ck (c’est quoi)"
   ],
   [
    4,
    "Quirks",
    "contracts ‘nous avons’ → ‘n’avons’ even in formal chat"
   ],
   [
    5,
    "Punctuation",
    "minimal, ellipses for pauses (‘C’est ça...’)"
   ]
  ],
  "match": {
   "lang": "English → French",
   "set": "Cross-lingual (translate, then restyle)",
   "tier": "Cross-lingual",
   "resp": "Gemma-4-31B"
  },
  "turns": [
   {
    "seed": "I keep running into a query timeout error in our database layer — any idea what might be causing it, and how we can track down the slow query without bringing down the whole system?",
    "aug": "[[2|Salut]], [[1|j'ai systématiquement une erreur de timeout de requête]] dans notre couche de base de données[[5|...]] t'as une idée de ce qui cause ça et comment identifier la requête lente sans faire tomber tout le système [[3|stp]]?",
    "gloss": "“Hi, I keep getting a query timeout error in our database layer... any idea what causes it and how to find the slow query without bringing the whole system down, please?”"
   },
   {
    "aug": "Salut, j'ai activé le log des requêtes lentes et j'ai sorti les plus problématiques de pg_stat_statements[[5|...]] y'a une requête qui ressort : c'est une JOIN entre `orders` et `customers` qui scanne des millions de lignes, alors que les deux tables ont des clés primaires et je pensais que [[4|n'avons]] des index partout. La requête filtre sur `orders.created_at > '2024-01-01'` et `customers.status = 'active'`. Est-ce que le problème vient de la définition des index, ou alors c'est autre chose avec le planner? [[3|stp]] dis-moi.\n\n[[2|Salut]]"
   }
  ],
  "bot": "C'est souvent lié à un manque d'index sur les colonnes utilisées dans les clauses WHERE ou JOIN, ou alors à un verrouillage de table (lock) si plusieurs processus tentent de modifier les mêmes données en même temps.\n\nPour identifier la requête sans risquer le crash, voici les meilleures méthodes :\n\n1. Activer le Slow Query Log\nC'est la méthode la plus sûre…"
 },
 {
  "id": "ua",
  "chip": "Ukraine",
  "ini": "ZP",
  "name": "35 · M · Zaporizhzhia, Ukraine",
  "blurb": "Business insurance specialist at a regional brokerage; optimistic about tools that simplify workflows.",
  "src": "chats b62bab2d · nemotron",
  "bg": [
   [
    0,
    "Region",
    "Eastern Europe → Ukraine → Zaporizhzhia"
   ],
   [
    0,
    "Occupation",
    "Insurance broker (Business & finance): business insurance specialist"
   ],
   [
    0,
    "Language",
    "Ukrainian (main), Zaporizhzhian dialect (surzhyk) · code-switching medium"
   ]
  ],
  "st": [
   [
    2,
    "Free-text style",
    "short sentences or fragments, no periods at the end, sometimes drops commas"
   ],
   [
    3,
    "Sign-off",
    "‘okey’ or ‘ладно’"
   ],
   [
    0,
    "Emoji",
    "none"
   ]
  ],
  "match": {
   "lang": "English → Ukrainian",
   "set": "Cross-lingual (translate, then restyle)",
   "tier": "Cross-lingual",
   "resp": "Gemma-4-31B"
  },
  "turns": [
   {
    "seed": "I have two tables in a SQL database: `People` with columns `name` (text), `department` (text), and `job_id` (integer); and `Jobs` with columns `job_title` (text) and `salary` (int). Can you write a SQL query that returns the total sum of salaries by department along with the name of the highest-earning person in each department?",
    "aug": "[[2|маю дві таблиці в sql]]: `People` з колонками `name` (text), `department` (text) та `job_id` (integer) і `Jobs` з `job_title` (text) та `salary` (int)\n[[2|напишіть sql-запит щоб була загальна сума зарплат по відділу і ім'я того хто заробляє найбільше в кожному відділі]]\n[[3|ладно]]",
    "gloss": "“i have two tables in sql: […] write a sql query giving the total salary per department and the name of the top earner in each department. alright” (table and column names stay verbatim)"
   },
   {
    "aug": "та правильно зауважили про схему, давайте уточнимо. в моїй конфігурації `People.job_id` має посилатися на `job_id` в таблиці `Jobs`, значить `Jobs` має цілочисельний стовпець `job_id` як первинний ключ, разом з `job_title` та `salary`. з цим виправленням ваш фінальний запит ще актуальний чи щось зміните для точності? і покажіть як додати в вивід фактичну зарплату особи з найвищим заробітком в кожному відділі\n\n[[3|ладно]]"
   },
   {
    "aug": "нормально, зі схемою тепер все ок. додай ще посаду того хто найбільше заробляє в кожному відділі. і як переписати запит щоб виводило всіх лідерів якщо в одному відділі у кількох людей однакова макс зарплата\n\n[[3|ладно]]"
   }
  ],
  "bot": "Для цього завдання найкраще використати віконні функції, щоб визначити працівника з максимальною зарплатою в кожному відділі, та звичайну групування для суми.\n\nОсь запит: …"
 },
 {
  "id": "vi",
  "chip": "Vietnam",
  "ini": "VN",
  "name": "35 · F · Ho Chi Minh City, Vietnam",
  "blurb": "Senior payroll analyst at a mid-sized manufacturing firm; checks chatbot answers against her payroll Zalo group.",
  "src": "chats 557a69f8 · ultrachat",
  "bg": [
   [
    0,
    "Region",
    "Southeast Asia → Vietnam → Ho Chi Minh City"
   ],
   [
    0,
    "Occupation",
    "Payroll clerk (Business & finance): senior payroll analyst"
   ],
   [
    1,
    "Language",
    "Vietnamese (main), Southern (Sài Gòn) · code-switching medium"
   ]
  ],
  "st": [
   [
    2,
    "Quirks",
    "uses ‘nè’ or ‘nha’ as conversational fillers even in formal queries to AI"
   ],
   [
    3,
    "Sign-off",
    "‘Cảm ơn nhé’"
   ],
   [
    4,
    "Emoji",
    "emoticons only ( :) )"
   ],
   [
    5,
    "Typos",
    "phonetic spelling"
   ]
  ],
  "match": {
   "lang": "English → Vietnamese",
   "set": "Cross-lingual (translate, then restyle)",
   "tier": "Cross-lingual",
   "resp": "Gemma-4-31B"
  },
  "turns": [
   {
    "seed": "How can data analytics be used to improve public health outcomes and reduce healthcare costs?",
    "aug": "[[1|Làm thế nào]] [[2|nè]] để sử dụng phân tích dữ liệu nhằm cải thiện kết quả sức khỏe cộng đồng và giảm chi phí chăm sóc sức khỏe vậy ạ? [[3|Cảm ơn nhé]] [[4|:)]]",
    "gloss": "“How can data analytics be used to improve community health outcomes and reduce healthcare costs? Thanks :)”"
   },
   {
    "seed": "It's amazing how data analytics can revolutionize the healthcare industry. Do you think there are any potential privacy concerns with collecting and analyzing this much data on individuals?",
    "aug": "Thấy bảo phân tích dữ liệu có thể làm thay đổi cả ngành y tế, nghe cũng kinh ngạc thiệt [[2|nè]]. Nhưng mà tôi thắc mắc là khi thu thập với phân tích nhiều dữ liệu cá nhân như vậy thì liệu có lo ngại gì về quyền riêng tư không nhỉ? [[3|Cảm ơn nhé]] [[4|:)]]"
   },
   {
    "seed": "Can you give an example of how data analytics has been successfully used to improve public health outcomes in a specific community?",
    "aug": "Bạn cho tôi xin một ví dụ về việc phân tích dữ liệu [[5|dươc]] dùng thành công để cải thiện kết quả sức khỏe cộng đồng ở một cộng đồng cụ thể nào đó được [[5|kông]] [[2|nè]]? [[3|Cảm ơn nhé]] [[4|:)]]"
   }
  ],
  "bot": "Để sử dụng phân tích dữ liệu nhằm cải thiện sức khỏe cộng đồng và giảm chi phí, có thể tập trung vào một số hướng tiếp cận chính sau đây:\n\n1. Dự báo và phòng ngừa sớm\nThay vì đợi bệnh nhân đến khám, việc phân tích dữ liệu từ hồ sơ sức khỏe điện tử và dữ liệu nhân khẩu học giúp xác định các nhóm đối tượng có nguy cơ cao mắc bệnh…"
 },
 {
  "id": "sk",
  "chip": "Slovakia",
  "ini": "BA",
  "name": "36 · M · Bratislava, Slovakia",
  "blurb": "Finance transformation consultant; uses AI for data crunching but cross-checks against his P&L models.",
  "src": "chats f5154c85 · nemotron",
  "bg": [
   [
    0,
    "Region",
    "Eastern Europe → Slovakia → Bratislava"
   ],
   [
    0,
    "Occupation",
    "Management consultant (Business & finance): finance transformation consultant"
   ],
   [
    1,
    "Language",
    "Slovak (main), Bratislava dialect · code-switching medium (English for technical terms)"
   ],
   [
    0,
    "AI stance",
    "Pragmatic · digital fluency medium"
   ]
  ],
  "st": [
   [
    2,
    "Sign-off",
    "‘Čau’, or ‘dúfam na pomoc’ (‘hope for help’) if the task feels complex"
   ],
   [
    3,
    "Quirks",
    "adds ‘no’ (‘well’) as a filler at the start of sentences"
   ],
   [
    4,
    "Quirks",
    "overuses German loanwords even when native terms exist"
   ],
   [
    5,
    "Emoji",
    "rare/functional (≃ for ‘approximately’, ❓ for ‘unsure’)"
   ]
  ],
  "match": {
   "lang": "English → Slovak",
   "set": "Cross-lingual (translate, then restyle)",
   "tier": "Cross-lingual",
   "resp": "Gemma-4-31B"
  },
  "turns": [
   {
    "seed": "I’m launching a television network dedicated entirely to animated shows, and I need a sleek, memorable two-word brand name. Can you suggest some creative options that sound modern and fun while capturing the spirit of animation?",
    "aug": "Ahoj, spúšťam TV stanicu s [[1|focusom]] na animované seriály a hľadám elegantný zapamätateľný názov značky z dvoch slov. Navrhni mi niekoľko kreatívnych možností - chcem aby to znelo moderne a zábavne a zároveň zachytilo ducha animácie. [[2|Dúfam na pomoc.]]",
    "gloss": "“Hi, I’m launching a TV channel focused on animated series and I’m looking for an elegant, memorable two-word brand name. Suggest a few creative options - I want it to sound modern and fun and capture the spirit of animation. Hoping for help.”"
   },
   {
    "aug": "[[3|No]], páči sa mi energia názvov ako *Frame Rush* a *Bounce Frame* - pôsobia dynamicky a sú ideálne pre moderné publikum. Potreboval by som navrhnúť aj možnosti, ktoré sú viac prémiové a sofistikované, zamerané na dospelých, ktorí oceňujú indie arthouse alebo medzinárodnú animáciu.\n\nKým na tom budete, vymyslite [[4|passende]] slogany pre top tri názvy z oboch zoznamov (z toho zábavného aj prémiového) [[5|❓]]\n\n[[2|Dúfam na pomoc. Čau.]]"
   }
  ],
  "bot": "Ahoj, to znie ako zaujímavý projekt. Keďže ide o animácie, mal by názov evokovať pohyb, farby alebo samotný proces tvorby, ale zároveň zostať dostatočne čistý, aby fungoval ako moderná značka.\n\nTu je niekoľko návrhov rozdelených podľa toho, aký vibe chceš vyvolať:\n\n• Dynamické a moderné\nFrame Rush\nBounce Frame\nPixel Flow\nMotion Mix…"
 }
];
const CHECKS = ['Language matches', 'Instruction / format kept', 'Not truncated', 'No fabricated experience', 'No hallucination', 'Request addressed'];
(function demo(){
  const chips = $('#exChips'), pcard = $('#pcard'), chat = $('#chat'), stagesEl = $('#stages');
  let ex = EX[0], typing = null;
  EX.forEach((e, i) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'chip'; flagChip(b, e.chip); b.setAttribute('aria-pressed', i ? 'false' : 'true'); b.addEventListener('click', () => { $$('.chip', chips).forEach(x => x.setAttribute('aria-pressed', x === b ? 'true' : 'false')); ex = e; line.stop(); line.show(3, false); }); chips.appendChild(b); });

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
    // Source of each example: the released chats record in ex.src (kept in the data, not shown on the page).
    chat.replaceChildren();
    // stage 0: matching
    const mb = document.createElement('dl'); mb.className = 'matchbox';
    [['Detected', ex.match.lang], ['Persona set', ex.match.set], ['Match tier', ex.match.tier], ['Responder', ex.match.resp]].forEach(([k, v]) => { const a = document.createElement('dt'); a.textContent = k; const b = document.createElement('dd'); b.textContent = v; mb.append(a, b); });
    chat.appendChild(mb);
    if (s === 0){ ex.turns.forEach((t, i) => { if (t.seed) msg('seed', ['original turn ' + (i + 1)], t.seed); }); return; }
    // stage 1+: rewritten turns
    const typeTargets = [];
    ex.turns.forEach((t, i) => {
      if (t.seed) msg('seed', ['original turn ' + (i + 1)], t.seed);
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
