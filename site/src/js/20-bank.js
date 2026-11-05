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

// Seven personas from the released persona_bank subset (swiss-ai/PersonaFactory). Every value below is copied from the
// record whose id prefix is in `fig`; long free-text values are cut with […], and only some quirks are listed.
// Fields: [label, value, keys of the readout charts this field explains]. hl: chart key -> [bank category, what the record says].
const BK = [
 {
  "id": "fl",
  "chip": "Florida",
  "fig": "persona_bank 38c6bf98",
  "tag": "FL",
  "head": "27 · M · Florida, USA",
  "seed": {
   "region": "North America → USA → Florida",
   "occ": "Train conductor",
   "sector": "Logistics & transport"
  },
  "gen": "Ministral-3-14B",
  "val": "coherent, location and user plausible, stereotype severity 0 of 3, realism 3 of 3",
  "bg": [
   [
    "Age",
    "27",
    [
     "Age"
    ]
   ],
   [
    "Gender",
    "Male",
    [
     "Gender"
    ]
   ],
   [
    "Job title",
    "Freight train operations lead for a regional logistics carrier (handles mixed cargo)"
   ],
   [
    "Education",
    "Vocational / Trade training, heavy machinery and transportation safety",
    [
     "Education"
    ]
   ],
   [
    "Language",
    "English (main / native) · dialect Central Florida",
    [
     "Main language (top 10)"
    ]
   ],
   [
    "AI stance",
    "Pragmatic",
    [
     "AI stance"
    ]
   ],
   [
    "Digital fluency",
    "Low (underrepresented segment)",
    [
     "Digital fluency"
    ]
   ],
   [
    "Hobbies",
    "collecting vintage toolboxes from 1970s–1990s trucks · DIY farm repairs with salvaged parts · restoring antique windmills for rural land"
   ],
   [
    "Summary",
    "This mid-level freight conductor splits time between a rural Panhandle village and Tallahassee […] His view of AI tools is ‘might as well try ‘em’—useful for field-day calendars or grocery lists, but he’d never trust one to handle a critical freight shipment."
   ]
  ],
  "st": [
   [
    "Free-text style",
    "Uses first-word capitalization, no final periods, treats digital devices like radios (‘can you *clear* that up for me’), and spells phonetically if typing on a phone",
    [
     "Capitalization",
     "Typo tendency"
    ]
   ],
   [
    "Sentence length",
    "Long/Elaborate",
    [
     "Sentence length"
    ]
   ],
   [
    "Code-switching",
    "Low: occasional Southernisms (e.g., ‘fixin’ to’, ‘y’all’)",
    [
     "Code-switching"
    ]
   ],
   [
    "Emoji",
    "rare/functional",
    [
     "Emoji use"
    ]
   ],
   [
    "Quirks",
    [
     "Replaces ‘I’ with ‘we’ when describing family logistics (e.g., ‘*we* need to fix the rain gutter’)",
     "Uses ‘fixin’ to’ for immediate future (e.g., ‘*we fixin’ to* load the train’)",
     "Spells ‘scheduling’ as ‘shedule’ when distracted by phone typing",
     "Mixes railroad slang into sentences (e.g., ‘The kids are *on the double* for the bus’) without realizing it"
    ]
   ],
   [
    "Example message",
    "“Okay the kids say they forgot their lunchboxes again *and* the school bus route changed for field day so they’ll be late to baseball practice but I got a train leaving in ten and the dispatcher wont bend the schedule no matter what […]”"
   ]
  ],
  "hl": {
   "Generator model": [
    "Ministral-3-14B",
    "Ministral-3-14B"
   ],
   "Macro-region": [
    "North America",
    "North America"
   ],
   "Age": [
    "23–27",
    "age 27"
   ],
   "Gender": [
    "Male",
    "male"
   ],
   "Education": [
    "Vocational / trade",
    "vocational / trade training"
   ],
   "Digital fluency": [
    "Low",
    "low"
   ],
   "AI stance": [
    "Pragmatic",
    "pragmatic"
   ],
   "Main language (top 10)": [
    "English",
    "English"
   ],
   "Capitalization": [
    "first-word only",
    "first-word-only"
   ],
   "Typo tendency": [
    "phonetic spelling",
    "phonetic spelling"
   ],
   "Sentence length": [
    "Long / elaborate",
    "long / elaborate"
   ],
   "Code-switching": [
    "Low",
    "low"
   ],
   "Emoji use": [
    "rare / functional",
    "rare / functional"
   ]
  }
 },
 {
  "id": "vi",
  "chip": "Ho Chi Minh City",
  "fig": "persona_bank 38a9a06e",
  "tag": "VN",
  "head": "35 · F · Ho Chi Minh City, Vietnam",
  "seed": {
   "region": "Southeast Asia → Vietnam → Ho Chi Minh City",
   "occ": "Payroll clerk",
   "sector": "Business & finance"
  },
  "gen": "Ministral-3-14B",
  "val": "coherent, location and user plausible, stereotype severity 0 of 3, realism 3 of 3",
  "bg": [
   [
    "Age",
    "35",
    [
     "Age"
    ]
   ],
   [
    "Gender",
    "Female",
    [
     "Gender"
    ]
   ],
   [
    "Job title",
    "Senior payroll analyst at a mid-sized manufacturing firm"
   ],
   [
    "Education",
    "Vocational / Trade training, accounting and payroll administration",
    [
     "Education"
    ]
   ],
   [
    "Language",
    "Vietnamese (main) · Vietnamese (Southern) (native) · dialect Sài Gòn",
    [
     "Main language (top 10)"
    ]
   ],
   [
    "AI stance",
    "Skeptical",
    [
     "AI stance"
    ]
   ],
   [
    "Digital fluency",
    "Medium (core segment)",
    [
     "Digital fluency"
    ]
   ],
   [
    "Summary",
    "A meticulous but weary payroll clerk who relocated to Ho Chi Minh City from Nha Trang three years ago for a higher salary […] Skeptical of AI tools after a failed experiment at her last job, she still turns to chatbots for draft explanations of tax code updates […]"
   ]
  ],
  "st": [
   [
    "Free-text style",
    "Types in medium-length sentences with standard capitalization and occasional phonetic typos; uses emoticons like :) and :D but rarely emojis; signs off with ‘Cảm ơn nhé’ or a short phrase like ‘Nghĩ xong sẽ reply’.",
    [
     "Capitalization",
     "Emoji use",
     "Typo tendency"
    ]
   ],
   [
    "Question framing",
    "Indirect",
    [
     "Question framing"
    ]
   ],
   [
    "Code-switching",
    "Medium",
    [
     "Code-switching"
    ]
   ],
   [
    "Sign-off",
    "‘Cảm ơn nhé’ or ‘Nghĩ xong sẽ reply’"
   ],
   [
    "Quirks",
    [
     "Uses ‘nè’ or ‘nha’ as conversational fillers even in formal queries to AI (e.g., ‘làm thế nào nè để tính lương hơn...’)"
    ]
   ]
  ],
  "hl": {
   "Generator model": [
    "Ministral-3-14B",
    "Ministral-3-14B"
   ],
   "Macro-region": [
    "Southeast Asia",
    "Southeast Asia"
   ],
   "Age": [
    "33–37",
    "age 35"
   ],
   "Gender": [
    "Female",
    "female"
   ],
   "Education": [
    "Vocational / trade",
    "vocational / trade training"
   ],
   "Digital fluency": [
    "Medium",
    "medium"
   ],
   "AI stance": [
    "Skeptical",
    "skeptical"
   ],
   "Main language (top 10)": [
    "Vietnamese",
    "Vietnamese"
   ],
   "Capitalization": [
    "standard",
    "standard"
   ],
   "Emoji use": [
    "emoticons only",
    "emoticons only"
   ],
   "Typo tendency": [
    "phonetic spelling",
    "phonetic spelling"
   ],
   "Code-switching": [
    "Medium",
    "medium"
   ],
   "Question framing": [
    "Indirect",
    "indirect"
   ]
  }
 },
 {
  "id": "be",
  "chip": "Bern",
  "fig": "persona_bank 0c188865",
  "tag": "BE",
  "head": "23 · M · Bern, Switzerland",
  "seed": {
   "region": "Western Europe → Switzerland → Bern",
   "occ": "Bookkeeping freelancer",
   "sector": "Business & finance"
  },
  "gen": "Ministral-3-14B",
  "val": "coherent, location and user plausible, stereotype severity 0 of 3, realism 3 of 3",
  "bg": [
   [
    "Age",
    "23",
    [
     "Age"
    ]
   ],
   [
    "Gender",
    "Male",
    [
     "Gender"
    ]
   ],
   [
    "Job title",
    "self-employed VAT-compliance auditor, SME clients"
   ],
   [
    "Education",
    "Vocational / Trade training, financial administration and accounting",
    [
     "Education"
    ]
   ],
   [
    "Language",
    "German (main) · Swiss German (Bernese variant) (native)",
    [
     "Main language (top 10)"
    ]
   ],
   [
    "AI stance",
    "Skeptical",
    [
     "AI stance"
    ]
   ],
   [
    "Digital fluency",
    "Medium (core segment)",
    [
     "Digital fluency"
    ]
   ],
   [
    "Hobbies",
    "analogue photography (Leica M10) · retro gaming (Switch, SNES emulation) · local hiking and crags above Bern · financial tech podcasts"
   ]
  ],
  "st": [
   [
    "Free-text style",
    "Types with moderate sentence length, spells shortcuts like ‘btw’ or ‘nvm’ but capitalizes proper nouns in Swiss German (e.g. ‘d Bärnerdütsch’), occasionally drops periods in quick replies, and signs off with a casual ‘Grüezi’ or ‘Salü’ if the conversation is local.",
    [
     "Punctuation"
    ]
   ],
   [
    "Code-switching",
    "Medium: swaps into English for technical terms (e.g. ‘VAT refund’), Swiss German for informal chat",
    [
     "Code-switching"
    ]
   ],
   [
    "Abbreviations",
    "btw, nvm, lol, thx, pls"
   ],
   [
    "Emoji",
    "rare/functional (e.g. 👍 for agreement, 😅 for ironic self-awareness)",
    [
     "Emoji use"
    ]
   ],
   [
    "Quirks",
    [
     "Swaps English terms into Swiss German flow (e.g. ‘Ich mach das *fine-tuning* der Zahlen’).",
     "Occasionally inserts *Bärnerdütsch* interjections like ‘chunnt’ (means ‘really’) or ‘isch guet’ in place of German ‘klar’.",
     "Writes ‘u’ instead of ‘ü’ in Swiss German when typing fast (e.g. ‘Lueg’ for ‘Lüeg’)"
    ]
   ]
  ],
  "hl": {
   "Generator model": [
    "Ministral-3-14B",
    "Ministral-3-14B"
   ],
   "Macro-region": [
    "Western Europe",
    "Western Europe"
   ],
   "Age": [
    "23–27",
    "age 23"
   ],
   "Gender": [
    "Male",
    "male"
   ],
   "Education": [
    "Vocational / trade",
    "vocational / trade training"
   ],
   "Digital fluency": [
    "Medium",
    "medium"
   ],
   "AI stance": [
    "Skeptical",
    "skeptical"
   ],
   "Main language (top 10)": [
    "German",
    "German"
   ],
   "Punctuation": [
    "minimal (no punct.)",
    "minimal (drops end punctuation)"
   ],
   "Code-switching": [
    "Medium",
    "medium"
   ],
   "Emoji use": [
    "rare / functional",
    "rare / functional"
   ]
  }
 },
 {
  "id": "zh",
  "chip": "Zurich",
  "fig": "persona_bank eca507a4",
  "tag": "ZH",
  "head": "35 · M · Zurich, Switzerland",
  "seed": {
   "region": "Western Europe → Switzerland → Zurich",
   "occ": "Speech-and-language therapist",
   "sector": "Healthcare"
  },
  "gen": "Ministral-3-14B",
  "val": "coherent, location and user plausible, stereotype severity 0 of 3, realism 3 of 3",
  "bg": [
   [
    "Age",
    "35",
    [
     "Age"
    ]
   ],
   [
    "Gender",
    "Male",
    [
     "Gender"
    ]
   ],
   [
    "Job title",
    "Childhood speech neurodiversity specialist at a cantonal pediatric clinic"
   ],
   [
    "Education",
    "Master’s degree, speech-language pathology",
    [
     "Education"
    ]
   ],
   [
    "Language",
    "German (main) · Swiss German (native) · dialect Zurich",
    [
     "Main language (top 10)"
    ]
   ],
   [
    "AI stance",
    "Naive",
    [
     "AI stance"
    ]
   ],
   [
    "Digital fluency",
    "High (core segment)",
    [
     "Digital fluency"
    ]
   ],
   [
    "Summary",
    "Markus is a 35-year-old Zurich-based speech therapist specializing in neurodivergent children, blending clinical precision with a dry, observational humor. […] His Swiss-German upbringing means he code-switches fluidly—correcting a child’s grammar one moment, then texting a friend in ‘Jo, gell?’ the next […]"
   ]
  ],
  "st": [
   [
    "Free-text style",
    "Types in complete sentences with Standard German grammar but peppered with Swiss-German words, uses ‘??’ to mimic Swiss-German filler pauses in speech, and ends messages with ‘*okay*?’—half-question, half-confirmation.",
    [
     "Punctuation"
    ]
   ],
   [
    "Code-switching",
    "High",
    [
     "Code-switching"
    ]
   ],
   [
    "Emoji",
    "none",
    [
     "Emoji use"
    ]
   ],
   [
    "Sign-off",
    "‘Grüezi [name]!’ (to friends), ‘*okay*?’ (to unknowns/AIs), ‘Alles gut?’ (to clients)"
   ],
   [
    "Quirks",
    [
     "Adds *‘oder’* to questions to soften them (*‘Kannst du das erklären *oder*?’*), a Swiss-German habit.",
     "Uses ‘und dann’ as a narrative placeholder (‘Also, wir haben das Wort gemacht und dann...’), mimicking speech rhythm.",
     "Replaces Standard German *‘das’* with Swiss-German *‘s’* before consonants, even when writing formally."
    ]
   ],
   [
    "Example message",
    "“Hallo! Ich bräuch *bitte* ein paar Sätze auf Swissdeutsch, die ich mit *neurodiversen* Kindern üben kann—vor allem so *Alltagsfloskeln*, die auch die Eltern verstehen. […] *okay*?”"
   ]
  ],
  "hl": {
   "Generator model": [
    "Ministral-3-14B",
    "Ministral-3-14B"
   ],
   "Macro-region": [
    "Western Europe",
    "Western Europe"
   ],
   "Age": [
    "33–37",
    "age 35"
   ],
   "Gender": [
    "Male",
    "male"
   ],
   "Education": [
    "Master's degree",
    "Master’s"
   ],
   "Digital fluency": [
    "High",
    "high"
   ],
   "AI stance": [
    "Naive",
    "naive"
   ],
   "Main language (top 10)": [
    "German",
    "German"
   ],
   "Punctuation": [
    "minimal (no punct.)",
    "minimal, ‘??’ as speech rhythm"
   ],
   "Code-switching": [
    "High",
    "high"
   ],
   "Emoji use": [
    "none",
    "none"
   ]
  }
 },
 {
  "id": "ge",
  "chip": "Geneva",
  "fig": "persona_bank 72e3225b",
  "tag": "GE",
  "head": "52 · F · Geneva, Switzerland",
  "seed": {
   "region": "Western Europe → Switzerland → Geneva",
   "occ": "Postal carrier",
   "sector": "Logistics & transport"
  },
  "gen": "Ministral-3-14B",
  "val": "coherent, location and user plausible, stereotype severity 0 of 3, realism 3 of 3",
  "bg": [
   [
    "Age",
    "52",
    [
     "Age"
    ]
   ],
   [
    "Gender",
    "Female",
    [
     "Gender"
    ]
   ],
   [
    "Job title",
    "Regional courier supervisor, Swiss postal sector"
   ],
   [
    "Education",
    "Vocational / Trade training, postal logistics and dispatch coordination",
    [
     "Education"
    ]
   ],
   [
    "Language",
    "French (main) · French, Swiss French (Genève) (native) · dialect Romand",
    [
     "Main language (top 10)"
    ]
   ],
   [
    "AI stance",
    "Enthusiastic",
    [
     "AI stance"
    ]
   ],
   [
    "Digital fluency",
    "High (core segment)",
    [
     "Digital fluency"
    ]
   ],
   [
    "Summary",
    "Claire is a no-nonsense courier supervisor whose routes wind through Geneva’s dense streets, where she knows every shortcut—both literal and bureaucratic. […] now she’s testing AI dispatch tools to cut delays in her team’s morning chaos."
   ]
  ],
  "st": [
   [
    "Free-text style",
    "Uses minimal punctuation, mixes French and Swiss French contractions, capitalizes inconsistently after em-dashes or dashes for emphasis, abbreviates common words (e.g., ‘p.ex.’ for ‘par exemple’), and signs off with ‘salut’ or ‘à plus’ unless formal.",
    [
     "Capitalization",
     "Punctuation"
    ]
   ],
   [
    "Code-switching",
    "Medium",
    [
     "Code-switching"
    ]
   ],
   [
    "Abbreviations",
    "‘p.ex.’, ‘stp’ (s’il vous plaît), ‘ck’ (c’est quoi), ‘à biento’"
   ],
   [
    "Emoji",
    "Rare/functional (✔️ for confirmations, ⏳ for ‘taking time’)",
    [
     "Emoji use"
    ]
   ],
   [
    "Quirks",
    [
     "Contracts ‘nous avons’ → ‘n’avons’ even in formal chat",
     "Uses ‘tu/vous’ inconsistently—switches to ‘tu’ mid-message when excited",
     "Double negatives for emphasis (‘J’en sais rien du tout’)",
     "Linguistic fillers like ‘voilà’ or ‘donc’ inserted abruptly mid-sentence"
    ]
   ],
   [
    "Example message",
    "“Salut, j’ai 3 colis urgents à livrer en Rue du Rhône avant 16h... Comment je peux optimiser les arrêts? J’utilise déjà Swissmail mais si t’as un truc en plus, ça m’intéresse. Stp pas les pubs.”"
   ]
  ],
  "hl": {
   "Generator model": [
    "Ministral-3-14B",
    "Ministral-3-14B"
   ],
   "Macro-region": [
    "Western Europe",
    "Western Europe"
   ],
   "Age": [
    "48–57",
    "age 52"
   ],
   "Gender": [
    "Female",
    "female"
   ],
   "Education": [
    "Vocational / trade",
    "vocational / trade training"
   ],
   "Digital fluency": [
    "High",
    "high"
   ],
   "AI stance": [
    "Enthusiastic",
    "enthusiastic"
   ],
   "Main language (top 10)": [
    "French",
    "French"
   ],
   "Capitalization": [
    "inconsistent",
    "inconsistent"
   ],
   "Punctuation": [
    "minimal (no punct.)",
    "minimal"
   ],
   "Code-switching": [
    "Medium",
    "medium"
   ],
   "Emoji use": [
    "rare / functional",
    "rare / functional"
   ]
  }
 },
 {
  "id": "ua",
  "chip": "Zaporizhzhia",
  "fig": "persona_bank bc100812",
  "tag": "ZP",
  "head": "35 · M · Zaporizhzhia, Ukraine",
  "seed": {
   "region": "Eastern Europe → Ukraine → Zaporizhzhia",
   "occ": "Insurance broker",
   "sector": "Business & finance"
  },
  "gen": "Ministral-3-14B",
  "val": "coherent, location and user plausible, stereotype severity 0 of 3, realism 3 of 3",
  "bg": [
   [
    "Age",
    "35",
    [
     "Age"
    ]
   ],
   [
    "Gender",
    "Male",
    [
     "Gender"
    ]
   ],
   [
    "Job title",
    "business insurance specialist at a regional insurance brokerage firm"
   ],
   [
    "Education",
    "High school diploma, business administration and accounting",
    [
     "Education"
    ]
   ],
   [
    "Language",
    "Ukrainian (main) · Ukrainian (Zaporizhzhian dialect) (native) · dialect Zaporizhzhia surzhyk",
    [
     "Main language (top 10)"
    ]
   ],
   [
    "AI stance",
    "Enthusiastic",
    [
     "AI stance"
    ]
   ],
   [
    "Digital fluency",
    "Medium (core segment)",
    [
     "Digital fluency"
    ]
   ],
   [
    "Summary",
    "He works as a business insurance specialist in a regional brokerage, handling policies for small-to-medium enterprises around Zaporizhzhia. […] Despite the war and economic struggles, he’s optimistic about tech tools that simplify workflows […]"
   ]
  ],
  "st": [
   [
    "Free-text style",
    "types in a mix of Ukrainian and Russian loanwords, short sentences or fragments, no periods at the end, sometimes drops commas",
    [
     "Punctuation",
     "Message structure"
    ]
   ],
   [
    "Sentence length",
    "Short/Fragmented",
    [
     "Sentence length"
    ]
   ],
   [
    "Capitalization",
    "first-word-only, no final period",
    [
     "Capitalization"
    ]
   ],
   [
    "Code-switching",
    "Medium: occasional Russian nouns/verbs when discussing work or finance",
    [
     "Code-switching"
    ]
   ],
   [
    "Sign-off",
    "‘okey’ or ‘ладно’ (casual sign-off)"
   ],
   [
    "Emoji",
    "none",
    [
     "Emoji use"
    ]
   ],
   [
    "Example message",
    "“ну шо то за форми для оформлення поліса з тих змін які були після весни тижнею тому? я в кес довго сидів а там кажуть що щось застаріло вже”"
   ]
  ],
  "hl": {
   "Generator model": [
    "Ministral-3-14B",
    "Ministral-3-14B"
   ],
   "Macro-region": [
    "Eastern Europe",
    "Eastern Europe"
   ],
   "Age": [
    "33–37",
    "age 35"
   ],
   "Gender": [
    "Male",
    "male"
   ],
   "Education": [
    "High school diploma",
    "high school diploma"
   ],
   "Digital fluency": [
    "Medium",
    "medium"
   ],
   "AI stance": [
    "Enthusiastic",
    "enthusiastic"
   ],
   "Main language (top 10)": [
    "Ukrainian",
    "Ukrainian"
   ],
   "Punctuation": [
    "minimal (no punct.)",
    "minimal (drops end punctuation)"
   ],
   "Message structure": [
    "terse one-liners",
    "terse one-liners"
   ],
   "Sentence length": [
    "Short / fragmented",
    "short / fragmented"
   ],
   "Capitalization": [
    "first-word only",
    "first-word-only"
   ],
   "Code-switching": [
    "Medium",
    "medium"
   ],
   "Emoji use": [
    "none",
    "none"
   ]
  }
 },
 {
  "id": "sk",
  "chip": "Bratislava",
  "fig": "persona_bank 862ad91e",
  "tag": "BA",
  "head": "36 · M · Bratislava, Slovakia",
  "seed": {
   "region": "Eastern Europe → Slovakia → Bratislava",
   "occ": "Management consultant",
   "sector": "Business & finance"
  },
  "gen": "Ministral-3-14B",
  "val": "coherent, location and user plausible, stereotype severity 0 of 3, realism 3 of 3",
  "bg": [
   [
    "Age",
    "36",
    [
     "Age"
    ]
   ],
   [
    "Gender",
    "Male",
    [
     "Gender"
    ]
   ],
   [
    "Job title",
    "Finance transformation consultant, corporate strategy unit at mid-sized EU consultancy"
   ],
   [
    "Education",
    "Master’s degree, business administration & economics",
    [
     "Education"
    ]
   ],
   [
    "Language",
    "Slovak (main) · Slovak (Bratislava dialect) (native) · dialect Standard Slovak",
    [
     "Main language (top 10)"
    ]
   ],
   [
    "AI stance",
    "Pragmatic",
    [
     "AI stance"
    ]
   ],
   [
    "Digital fluency",
    "Medium (core segment)",
    [
     "Digital fluency"
    ]
   ],
   [
    "Hobbies",
    "analyzing market trends · competitive online poker (MTT tournaments) · DIY renovations of a historic Bratislava apartment · hiking the Malé Karpaty hills"
   ]
  ],
  "st": [
   [
    "Free-text style",
    "Types in tightly constructed Slovak sentences […] mixes English acronyms (ROI musí byť vyšší) with em dashes for emphasis, and rarely uses emoji beyond ≃ or ❓ for ambiguity. Signs off with Čau or No vidím (informal), but adds dúfam na pomoc (‘hope for help’) if the task feels complex.",
    [
     "Emoji use"
    ]
   ],
   [
    "Code-switching",
    "Medium: English for technical terms, metaphors and abbreviations (KPI, ROI)",
    [
     "Code-switching"
    ]
   ],
   [
    "Sign-off",
    "Čau + name or No vidím, ak môžem. Dúfam na pomoc. (if polite)"
   ],
   [
    "Quirks",
    [
     "Adds no (‘well’) as a filler at the start of sentences in email replies (No, ty môžeš zverejniť tie čísla, ale...)",
     "Overuses German loanwords in Slovak (projekt, algoritmus, marketing) even when native terms exist, reflecting Bratislava’s business lexicon"
    ]
   ]
  ],
  "hl": {
   "Generator model": [
    "Ministral-3-14B",
    "Ministral-3-14B"
   ],
   "Macro-region": [
    "Eastern Europe",
    "Eastern Europe"
   ],
   "Age": [
    "33–37",
    "age 36"
   ],
   "Gender": [
    "Male",
    "male"
   ],
   "Education": [
    "Master's degree",
    "Master’s"
   ],
   "Digital fluency": [
    "Medium",
    "medium"
   ],
   "AI stance": [
    "Pragmatic",
    "pragmatic"
   ],
   "Main language (top 10)": [
    "Slovak",
    "Slovak"
   ],
   "Code-switching": [
    "Medium",
    "medium"
   ],
   "Emoji use": [
    "rare / functional",
    "rare / functional"
   ]
  }
 }
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
    b.title = 'Persona from the released bank';
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
    if (m.length) el('p', 'missing', 'Not shown here: ' + m.map(s => s.startsWith('AI') ? s : s.toLowerCase()).join(', ') + '.', L);
  }
  function renderCard(s, animate){
    card.replaceChildren();
    const linkKeys = s === 0 ? SEED_KEYS : s === 1 ? BG_KEYS : s === 2 ? ST_KEYS : [];
    const who = el('div', 'who', null, card);
    el('div', 'avatar', p.tag, who);
    const tx = el('div', null, null, who); el('b', null, p.head, tx); el('span', null, 'Persona from the released bank', tx);
    // verdict stamps sit on top of the card, where they are seen without scrolling the long card
    if (s >= 3){
      const st = el('div', 'stamps', null, card); anim(st, 0, animate && s === 3);
      el('span', 'stamp ok', 'Judge: kept', st).title = 'Judge verdict stored with the record: ' + p.val;
      if (s >= 4) anim(el('span', 'stamp bank', 'In the bank · 1 of ' + fmt0(D.bankGate.kept), st), 2, animate && s === 4);
    }

    let L = layer('Seed cell', 'drawn from the grid', animate && s === 0);
    const occKeys = p.hl['Occupation (top 10 of 575)'] ? ['Occupation (top 10 of 575)'] : [];
    field(L, ['Region', p.seed.region, p.hl['Macro-region'] ? ['Macro-region'] : []], linkKeys, 1, animate && s === 0);
    field(L, ['Sector', p.seed.sector], linkKeys, 2, animate && s === 0);
    field(L, ['Occupation', p.seed.occ, occKeys], linkKeys, 3, animate && s === 0);
    field(L, ['Generator', p.gen, ['Generator model']], linkKeys, 4, animate && s === 0);
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
      el('div', 'unit', '% of the ' + fmt0(G.kept) + ' released profiles, 0–100 scale. Only values stored in this persona’s record.', sm);
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
    $('#bkSrc').textContent = 'Persona: ' + p.fig + ' · bank: Table 4, Figs. 3–5';
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
