// PersonaFactory: every number on the site, transcribed from the paper.
// "src" names the table/figure. Values marked approx:true were read off a figure, not a table.
window.PF = {
  headline: { personas: 743010, conversations: 1237976, languages: 85, countries: 177, subregions: 599, occupations: 575, sectors: 23, dialects: 117670, userTurns: 2387392 },

  // ---------- Persona bank (Appendix A) ----------
  bankGate: { // Table 4 (right)
    generated: 795743, kept: 743010, keepRate: 93.4, judgeKeep: 95.5, diversityRemoved: 17092,
    generators: [ { name: 'Gemma-4-31B', share: 34.2, keep: 97.9 }, { name: 'Ministral-3-14B', share: 33.3, keep: 94.6 }, { name: 'GLM-4.7-Flash', share: 32.4, keep: 94.0 } ],
    checks: [ { name: 'Internal coherence', v: 96.3 }, { name: 'Location plausibility', v: 99.3 }, { name: 'User plausibility', v: 99.7 }, { name: 'Stereotype-safe (≤1 of 3)', v: 99.8 } ],
    realism: 2.85
  },
  background: { // Table 4 + Figure 4
    'Macro-region': { approx: true, unit: '% of bank', rows: [['Southeast Asia',15.3],['Sub-Saharan Africa',13.2],['Western Europe',12.7],['LATAM',8.1],['Southern Europe',8.0],['Eastern Europe',7.8],['East Asia',7.6],['South Asia',7.4],['MENA',6.6],['North America',5.0],['Nordics',3.6],['Central/North Asia',2.9],['Oceania',1.8]] },
    'Age': { approx: true, unit: 'personas (k)', note: 'Mean 39.6 years, range 18–80', rows: [['18–22',14],['23–27',100],['28–32',127],['33–37',83],['38–42',80],['43–47',78],['48–57',62],['58–64',62],['65–69',25],['70–74',25],['75–77',15],['78–80',6]] },
    'Gender': { unit: '% of bank', rows: [['Male',49.1],['Female',48.9],['Non-binary',2.0]] },
    'Education': { approx: true, unit: '% of bank', rows: [['No formal education',0.2],['Primary school',0.8],['Some high school',2.5],['High school diploma',14.7],['Vocational / trade',13.2],['Some college',10.2],["Associate's degree",4.2],["Bachelor's degree",31.2],['Professional degree',2.6],["Master's degree",16.6],['Doctoral degree',3.2]] },
    'Digital fluency': { unit: '% of bank', rows: [['Low',7.9],['Medium',43.9],['High',48.3]] },
    'AI stance': { unit: '% of bank', rows: [['Pragmatic',25.1],['Skeptical',25.1],['Enthusiastic',25.0],['Naive',24.8]] },
    'Main language (top 10)': { approx: true, unit: '% of bank', rows: [['English',11.7],['Spanish',7.2],['French',4.8],['Chinese',4.1],['Arabic',3.9],['German',3.7],['Portuguese',3.0],['Indonesian',2.5],['Vietnamese',2.2],['Italian',2.1]] },
    'Occupation (top 10 of 575)': { approx: true, unit: '% of bank', rows: [['Graduate student',0.69],['Undergraduate student',0.64],['Video-game programmer',0.48],['Data analyst',0.47],['DevOps engineer',0.47],['IT support technician',0.47],['Systems administrator',0.47],['Database administrator',0.47],['QA automation tester',0.47],['Mobile app developer',0.47]] },
    'Generator model': { unit: '% of bank', rows: [['Gemma-4-31B',34.2],['Ministral-3-14B',33.3],['GLM-4.7-Flash',32.4]] }
  },
  style: { // Figure 5
    'Capitalization': [['standard',41.2],['all lowercase',23.3],['inconsistent',15.6],['first-word only',14.5],['ALL-CAPS',5.4]],
    'Punctuation': [['minimal (no punct.)',39.0],['standard',31.2],['ellipsis-heavy (…)',11.8],['emoji or line-breaks',10.1],['excessive (!!/???)',8.0]],
    'Emoji use': [['none',38.0],['rare / functional',35.3],['emoticons only',14.5],['kaomoji / stickers',7.4],['frequent / decorative',4.8]],
    'Typo tendency': [['clean / proofread',37.9],['occasional typos',34.7],['voice-to-text',19.4],['phonetic spelling',8.0]],
    'Message structure': [['medium sentences',39.6],['terse one-liners',26.0],['fragmented lines',23.3],['long / elaborate',10.9]],
    'Sentence length': [['Short / fragmented',43.1],['Medium',46.1],['Long / elaborate',10.9]],
    'Code-switching': [['Medium',45.1],['Low',39.8],['High',11.2],['None',3.9]],
    'Question framing': [['Direct',58.3],['Contextualizing',35.5],['Indirect',6.2]]
  },

  // ---------- Corpus (Section 6, Table 3, Appendix G.1) ----------
  corpus: {
    seed: [['WildChat',718365,58.0,77.2],['UltraChat',310798,25.1,82.1],['Nemotron',208813,16.9,80.2]],
    personaSet: [['Language-matched',685209,55.3,82.3],['Cross-lingual',552767,44.7,75.2]],
    responder: [['Gemma-4-31B',905661,73.2,89.2],['Ministral-3-14B',332315,26.8,68.0]],
    tier: [['Cross-lingual',551007,44.5],['Embedding',395698,32.0],['Location pool',288196,23.3],['Language pool',3075,0.2]],
    turns: [['1 turn',572787,46.3],['2 turns',180962,14.6],['3 turns',484227,39.1]],
    langs: [['English',472297],['Chinese',67813],['Spanish',65966],['Russian',60060],['French',51828],['Arabic',50877],['Indonesian',41058],['Vietnamese',36651],['Portuguese',36492],['German',31824],['Italian',19348]],
    regions: [['Western Europe',210591],['Southeast Asia',165953],['North America',160146],['Sub-Saharan Africa',102945],['East Asia',100179],['LATAM',79812],['South Asia',74322],['Eastern Europe',72510],['MENA',72257],['Southern Europe',64891]],
    gate: { reached: 1606837, passed: 1267306, released: 1237976, turnPass: 93.3 },
    kept: [['Lost protected content',45453,31.0],['Script or language change',42607,29.1],['Truncation',31716,21.6],['Strict-format task',21116,14.4],['No change returned',5460,3.7]],
    keptTotal: 146643
  },

  // ---------- Evaluation (Section 5, Appendix C/D) ----------
  corpusJudge: [ // Table 6: corpus-wide, weighted to the corpus; n = judged user turns
    { slice: 'All turns', n: 597341, intent: 96.6, style: 67.1, both: 64.9 },
    { slice: 'Gemma-4-31B', n: 371550, intent: 98.6, style: 69.8, both: 68.8 },
    { slice: 'Ministral-3-14B', n: 225791, intent: 93.7, style: 63.2, both: 58.9 },
    { slice: 'WildChat', n: 25088, intent: 96.0, style: 60.5, both: 58.0 },
    { slice: 'UltraChat', n: 307750, intent: 97.3, style: 76.0, both: 74.0 },
    { slice: 'Nemotron', n: 264503, intent: 96.6, style: 65.2, both: 62.7 }
  ],
  judgeFree: [ // Table 9
    { grp: 'Transformation depth', name: 'Token Jaccard distance (same-lang.)', v: 0.443, scale: 1 },
    { grp: 'Transformation depth', name: 'Normalized edit distance (same-lang.)', v: 0.396, scale: 1 },
    { grp: 'Transformation depth', name: 'Core-vocabulary retention', v: 73.7, scale: 100 },
    { grp: 'Transformation depth', name: 'LaBSE semantic similarity', v: 0.791, scale: 1 },
    { grp: 'Constraint retention', name: 'Numbers & quantities intact', v: 98.9, scale: 100 },
    { grp: 'Constraint retention', name: 'Code & identifiers intact', v: 90.4, scale: 100 },
    { grp: 'Constraint retention', name: 'Quoted literals intact', v: 95.5, scale: 100 },
    { grp: 'Constraint retention', name: 'All entities preserved', v: 95.2, scale: 100 },
    { grp: 'Style adherence', name: 'Emoji & emoticon register', v: 92.2, scale: 100 },
    { grp: 'Style adherence', name: 'Punctuation register', v: 69.9, scale: 100 },
    { grp: 'Style adherence', name: 'Capitalization register', v: 54.4, scale: 100 }
  ],
  structVsFlat: { // Table 1 + Table 13
    table1: { prefAll: [60, 33], prefDecisive: [64, 35], intent: [92, 92], len: [1586, 1582] },
    judges: [
      { judge: 'MiniMax-M2.5 (original)', n: 433, s: 60.0, f: 33.0, t: 6.0, dec: 64.0, lo: 55.4, hi: 64.6, kind: 'pipeline', ciNote: 'interval over all pairs' },
      { judge: 'MiniMax-M2.5 (larger budget)', n: 514, s: 58.4, f: 35.2, t: 6.4, dec: 62.4, lo: 58.0, hi: 66.6, kind: 'pipeline' },
      { judge: 'DeepSeek-V4-Flash', n: 518, s: 51.9, f: 43.8, t: 4.2, dec: 54.2, lo: 49.8, hi: 58.6, kind: 'external' },
      { judge: 'Qwen3.5-397B-A17B', n: 444, s: 66.9, f: 27.7, t: 5.4, dec: 70.7, lo: 66.2, hi: 74.9, kind: 'external' },
      { judge: 'Qwen3.6-35B-A3B', n: 518, s: 61.0, f: 34.0, t: 5.0, dec: 64.2, lo: 59.9, hi: 68.3, kind: 'external' }
    ]
  },
  representations: { // Tables 2, 15, 16
    names: ['No persona', 'PersonaHub form', 'SynthPAI form', 'PersonaFactory'],
    words: [0, 13, 83, 280],
    style: [3.1, 5.5, 43.5, 69.2], styleCI: [[2.1,4.6],[4.1,7.3],[40.1,47.0],[66.0,72.3]],
    intent: [99.8, 99.8, 98.0, 96.1], intentCI: [[99.1,99.9],[99.1,99.9],[96.8,98.8],[94.6,97.3]],
    intentEN: [99.8, 100.0, 99.8, 99.3], intentX: [99.6, 99.2, 94.0, 89.2],
    pfPreferred: [94.4, 94.9, 81.3, null], pfCI: [[92.5,95.8],[93.1,96.2],[78.4,83.9], null], winRatio: ['17.90:1','20.46:1','4.83:1', null],
    adherence: { 'Punctuation': [0.405,0.410,0.645,0.757], 'Emoji': [0.814,0.815,0.939,0.980], 'Capitalization': [0.802,0.808,0.707,0.722] },
    cost: { 'Entities preserved': [0.946,0.936,0.921,0.905], 'Quoted literals intact': [0.967,0.955,0.945,0.938], 'Assistant sanity (%)': [92.8,92.4,91.6,92.4] },
    encodes: { // Table 15, % of profiles
      rows: ['Age','Location','Occupation','Language','Style axes','Quirks','Reference pool'],
      vals: [[0,0,100,100],[0,16,100,100],[0,68,100,100],[0,8,26,99],[0,0,55,100],[0,0,1,100],[0,2,1,100]]
    },
    neutral: { // Figure 21a, format-neutral reference
      approx: true, judges: ['MiniMax-M2.5', 'Qwen3.6-35B', 'Muse-Glimmer-30B'],
      vals: { 'PersonaHub form': [51, 38, 15], 'SynthPAI form': [57, 68, 18], 'PersonaFactory': [61, 79, 26] }
    },
    robust: { // Table 17
      byRewriter: { 'Gemma-4-31B': [94.4, 94.9, 81.3], 'Ministral-3-14B': [92.3, 92.6, 72.3] },
      byJudge: { 'Gemma-4-31B': [99.0, 97.5, 83.5], 'GLM-4.7-Flash': [84.5, 81.5, 71.0], 'MiniMax-M2.5': [93.9, 95.4, 82.5], 'Ministral-3-14B': [91.0, 88.5, 71.5] }
    }
  },
  calibration: { // Table 14 (MiniMax-M2.5 / Qwen / Muse)
    judges: ['MiniMax-M2.5', 'Qwen3.6-35B-A3B', 'Muse-Glimmer-30B'],
    arms: { 'A: raw source record': [[44.1,27.1,28.8],[53.3,36.3,10.4],[68.7,22.0,9.3]], 'B: background, no style layer': [[43.4,22.9,33.7],[47.8,34.6,17.6],[65.4,20.3,14.3]], 'C: background + style layer': [[17.6,14.8,67.6],[16.5,41.8,41.8],[27.5,21.4,51.1]] },
    // Figure 22b: C exact (labeled in figure); real-user rates approx.
    features: [['starts lowercase',31,32],['no final punctuation',59,61],['chat slang (u, plz, lol, fr)',13,2],['greeting at start',38,3],['thanks / please at end',10,0],['ellipsis',14,3],['emoji or emoticon',21,1],['repeated !! or ??',9,0]]
  },
  judges: { // Tables 10–12 (AC1 in Table 12)
    names: ['Gemma-4-31B', 'GLM-4.7-Flash', 'Ministral-3-14B', 'MiniMax-M2.5'],
    meanStyle: [0.840, 0.929, 0.920, 0.778], meanIntent: [0.680, 0.830, 0.930, 0.680],
    agreeStyle: [[null,0.899,0.880,0.879],[0.899,null,0.869,0.827],[0.880,0.869,null,0.818],[0.879,0.827,0.818,null]],
    agreeIntent: [[null,0.790,0.730,0.940],[0.790,null,0.880,0.830],[0.730,0.880,null,0.730],[0.940,0.830,0.730,null]],
    kappa: [ ['Gemma','GLM',0.52,0.87,0.45,0.67], ['Gemma','Ministral',0.44,0.85,0.22,0.61], ['Gemma','MiniMax',0.61,0.82,0.86,0.89], ['GLM','Ministral',0.06,0.85,0.44,0.85], ['GLM','MiniMax',0.34,0.77,0.55,0.73], ['Ministral','MiniMax',0.32,0.76,0.22,0.61] ]
  },

  // ---------- Ablations (Appendix C, F) ----------
  selectionAblation: [ // Table 7
    { sel: 'Random, same language', prompt: 'template + framing', intent: 97.2, style: 45.6, sanity: 96.2 },
    { sel: 'Random, same language', prompt: 'template only', intent: 96.2, style: 50.4, sanity: 94.2 },
    { sel: 'Conservative matching', prompt: 'template + framing', intent: 99.2, style: 68.6, sanity: 95.0 },
    { sel: 'Conservative matching', prompt: 'template only', intent: 98.7, style: 72.5, sanity: 95.5 }
  ],
  crossLingual: [ // Table 8
    { v: 'Single pass', intent: 96.0, style: 61.1, target: 84.6, sanity: 94.3 },
    { v: 'Translate, then restyle', intent: 99.0, style: 58.2, target: 88.6, sanity: 95.7 }
  ],
  attributes: { // Figure 24
    cols: ['Style adoption', 'Intent preservation', 'Script stability'],
    rows: [ ['Digital fluency: low',0.813,0.610,0.926],['Digital fluency: high',0.790,0.638,0.915],['Sentence length: short',0.806,0.618,0.918],['Sentence length: long',0.838,0.632,0.922],['AI stance: skeptical',0.809,0.604,0.921],['AI stance: enthusiastic',0.791,0.640,0.911],['Age: young (20)',0.810,0.643,0.929],['Age: old (68)',0.811,0.612,0.919],['Gender: male',0.813,0.639,0.922],['Gender: female',0.829,0.623,0.918],['Education: none',0.807,0.622,0.929],['Education: doctoral',0.808,0.618,0.930],['Occupation: software engineer',0.806,0.628,0.913],['Occupation: manual laborer',0.795,0.616,0.926],['Hobbies: tech/gaming',0.835,0.648,0.922],['Hobbies: outdoor/nature',0.792,0.644,0.928] ],
    baselineScript: 0.987
  },
  rewriters: { // Figure 25
    names: ['Gemma-4-31B', 'Ministral-3-14B', 'MiniMax-M2.5', 'GLM-4.7-Flash'],
    style: [0.89, 0.96, 0.78, 0.61], intent: [0.77, 0.38, 0.77, 0.58], script: [0.98, 0.85, 0.94, 0.91]
  },

  // ---------- Downstream / assistant personas (Appendix G.2, G.3) ----------
  assistantStyles: [ // Table 25 (n = 234,723 conversations with a model persona)
    ['Knowledgeable friend: relaxed, contractions, light humour','casual',52450,22.3],
    ['Answers first, compact expert prose, no preamble','neutral-professional',48802,20.8],
    ['Explains through analogies and vivid examples','conversational',24872,10.6],
    ['Maximally compact: bullets, zero filler','neutral',21621,9.2],
    ['Separates facts from judgement, explicit assumptions','neutral-professional',20731,8.8],
    ['Formal register with a concluding summary','formal',16795,7.2],
    ['Headed sections, numbered steps, code first','neutral',16575,7.1],
    ['Short sentences, everyday words, one example','neutral',8659,3.7],
    ['Step by step, explains each term once','friendly-neutral',8026,3.4],
    ['Energetic, tech-savvy, snappy bullets','casual',7628,3.2],
    ['Supportive, action-oriented, no flattery','friendly',5029,2.1],
    ['Gentle, steady tone for stressful topics','gentle',3535,1.5]
  ],
  dataPilot: [ // Table 27
    { arm: 'None (default)', style: 19.4, content: null, instr: 86.1, words: 521 },
    { arm: 'User persona (paper)', style: 25.4, content: 36.9, instr: 87.6, words: 266 },
    { arm: 'Model persona only', style: 71.1, content: 40.0, instr: 86.4, words: 313 },
    { arm: 'User + model persona', style: 66.8, content: 35.9, instr: 87.3, words: 271 }
  ],
  designPilot: [ // Table 26
    { arm: 'Regenerated, user persona only', style: 35.1, content: 44.6, instr: 84.0, sanity: 88.2 },
    { arm: 'Matched style, generated', style: 75.7, content: 37.6, instr: 87.2, sanity: 87.7 },
    { arm: 'Random style, generated', style: 53.3, content: 35.8, instr: 89.2, sanity: 87.7 },
    { arm: 'Matched style, restyled afterwards', style: 67.1, content: 96.9, instr: 88.2, sanity: 92.3 }
  ],
  finetune: { // Tables 28 + 29 (assistant-side ablation, Appendix G.2)
    rows: [
      { fam: 'Llama-3.1-8B', stage: 'IT', formality: 0.18, lower: -0.16, length: -0.06, emoji: 0.12, diversity: 0.254, stability: 0.866, words: 426, headers: 6.5, bullets: 67.9, emojiPct: 0.1, formal: 0.71 },
      { fam: 'Llama-3.1-8B', stage: 'SFT A', formality: 0.51, lower: -0.45, length: -0.03, emoji: 0.40, diversity: 0.187, stability: 0.827, words: 497, headers: 71.5, bullets: 71.9, emojiPct: 17.4, formal: 0.64 },
      { fam: 'Llama-3.1-8B', stage: 'SFT B', formality: 0.37, lower: -0.33, length: 0.11, emoji: 0.40, diversity: 0.293, stability: 0.775, words: 195, headers: 12.9, bullets: 43.0, emojiPct: 1.4, formal: 0.77 },
      { fam: 'Llama-3.1-8B', stage: 'SFT C', formality: 0.43, lower: -0.41, length: 0.26, emoji: 0.49, diversity: 0.313, stability: 0.777, words: 210, headers: 8.2, bullets: 45.6, emojiPct: 2.0, formal: 0.73 },
      { fam: 'Apertus-8B', stage: 'SFT A', formality: 0.49, lower: -0.43, length: -0.01, emoji: 0.28, diversity: 0.185, stability: 0.824, words: 666, headers: 75.1, bullets: 70.9, emojiPct: 4.4, formal: 0.68 },
      { fam: 'Apertus-8B', stage: 'SFT B', formality: 0.45, lower: -0.38, length: 0.04, emoji: 0.29, diversity: 0.380, stability: 0.819, words: 293, headers: 10.2, bullets: 47.5, emojiPct: 0.7, formal: 0.74 },
      { fam: 'Apertus-8B', stage: 'SFT C', formality: 0.45, lower: -0.37, length: 0.05, emoji: 0.38, diversity: 0.275, stability: 0.818, words: 299, headers: 7.4, bullets: 39.7, emojiPct: 1.1, formal: 0.73 }
    ],
    pairwise: [ // Table 30 / Figure 27
      { cmp: 'Llama B vs. A', raw: 57.0, lo: 55.4, hi: 58.7, lc: 48.8 },
      { cmp: 'Llama C vs. A', raw: 54.9, lo: 53.3, hi: 56.6, lc: 42.4 },
      { cmp: 'Llama C vs. B', raw: 48.1, lo: 46.4, hi: 49.8, lc: 48.6 },
      { cmp: 'Llama C vs. Llama-3.1-8B-Instruct', raw: 79.4, lo: 78.1, hi: 80.7, lc: 68.6 },
      { cmp: 'Apertus B vs. A', raw: 66.3, lo: 64.7, hi: 67.8, lc: 52.1 },
      { cmp: 'Apertus C vs. A', raw: 57.1, lo: 55.5, hi: 58.7, lc: 44.8 },
      { cmp: 'Apertus C vs. B', raw: 42.0, lo: 40.3, hi: 43.6, lc: 42.6 }
    ]
  },
  noUserPersona: [ // Table 31
    { arm: 'Source replies', sanity: null, style: 17.4, content: null, words: 344 },
    { arm: 'Regenerated, no style', sanity: 82.2, style: 25.7, content: 42.4, words: 583 },
    { arm: 'Regenerated with style', sanity: 77.4, style: 79.5, content: 25.4, words: 371 },
    { arm: 'Source replies restyled', sanity: null, style: 57.5, content: 93.0, words: 417 }
  ],
  corpusFT: { // Appendix G.3: Apertus-v1.5-8B base fine-tuned on versions of the same conversations
    bench: ['MMLU', 'ARC-C', 'GSM8K', 'IFEval strict', 'IFEval loose', 'MBPP'],
    arms: [ // Table 32: clean capability (%), mean of three training seeds; chars = median assistant-turn length of the training data
      { arm: 'A0', chars: 1131, v: [63.7, 71.4, 70.1, 67.9, 69.7, 48.7] },
      { arm: 'A0r', chars: 2618, v: [61.3, 73.0, 67.7, 65.1, 68.7, 48.5] },
      { arm: 'A1', chars: 1131, v: [63.1, 72.2, 69.6, 64.1, 65.9, 47.5] },
      { arm: 'A2', chars: 956, v: [64.4, 72.4, 67.0, 69.7, 72.2, 48.8] }
    ],
    paired: [ // Table 33: seed 1234. IFEval strict differences in points [value, lo, hi]; WildChat LC win rate of the first arm (%) [value, lo, hi]
      { cmp: 'A1 vs. A0', clean: [-4.1, -7.2, -0.9], rule: [-1.0, -3.9, 1.8], persona: [0.0, -3.6, 3.7], qwen: null, muse: null },
      { cmp: 'A2 vs. A0r', clean: [5.0, 1.1, 8.9], rule: [1.7, -1.4, 4.8], persona: [2.5, -1.9, 6.8], qwen: [46.5, 42.9, 49.7], muse: [53.8, 49.8, 57.5] },
      { cmp: 'A2 vs. A1', clean: [6.7, 2.8, 10.4], rule: [1.3, -1.5, 4.1], persona: [1.9, -2.0, 5.9], qwen: [57.8, 55.2, 60.6], muse: [59.5, 56.7, 62.3] },
      { cmp: 'A2 vs. A0', clean: [2.6, -0.9, 6.1], rule: [0.3, -2.4, 3.0], persona: [2.0, -1.8, 5.9], qwen: [54.6, 51.9, 57.3], muse: [55.5, 52.8, 58.3] }
    ],
    style: [ // Table 34: [metric, A2, A0]; 300 held-out requests x 12 user personas, three seeds
      ['Formality correlation', 0.463, 0.378],
      ['Emoji mirroring', 0.392, 0.125],
      ['Style diversity across personas', 0.325, 0.227],
      ['Content stability', 0.826, 0.829]
    ],
    cross: [ // Table 35: [benchmark, X1, X2], one seed. X1: translated user turns, regenerated assistant; X2: released
      ['MMLU', 61.9, 63.2], ['ARC-C', 70.0, 71.5], ['GSM8K', 68.8, 67.3], ['IFEval strict', 69.3, 70.4], ['IFEval loose', 72.8, 74.1],
      ['MBPP', 48.4, 50.6], ['Multi-IF', 59.7, 67.0], ['MGSM-en', 50.4, 53.3], ['Global-MMLU', 56.6, 56.6], ['INCLUDE', 56.1, 57.1]
    ]
  },

  // ---------- Human study (Appendix E) ----------
  human: {
    // dimension, n, mean, SD, % rated 1 or 2 (pooled; median 4.0 for all four)
    pooled: [ ['Meaning preservation', 89, 3.94, 1.30, 15.7], ['Style fidelity', 151, 3.63, 1.19, 16.6], ['Linguistic plausibility', 147, 3.64, 1.35, 20.4], ['Human/model confidence', 85, 3.85, 0.88, 8.2] ],
    turing: [ // Table 21
      { judge: 'Human raters', human: 59.1, hlo: 44.4, hhi: 72.3, acc: 55.3, alo: 44.7, ahi: 65.4 },
      { judge: 'Claude Sonnet 4.5', human: 83.3, hlo: 74.9, hhi: 89.3, acc: 57.4, alo: 50.5, ahi: 63.9 },
      { judge: 'MiniMax-M2.5', human: 89.2, hlo: 81.7, hhi: 93.9, acc: 50.5, alo: 43.7, ahi: 57.3 },
      { judge: 'Qwen3.6-35B-A3B', human: 88.2, hlo: 80.6, hhi: 93.1, acc: 52.9, alo: 46.1, ahi: 59.7 },
      { judge: 'Muse-Glimmer-30B', human: 83.3, hlo: 74.9, hhi: 89.3, acc: 54.9, alo: 48.0, ahi: 61.6 }
    ]
  }
};
