#!/usr/bin/env python3
"""Canonical persona languages.

Two label tables:
  CORE_LANGUAGES / CORE_ALIASES   bounded language labels used for the persona-pair set
                                  (augmentation.prepare_pairs.canonical_label, strict matching)
  LANGUAGES / ALIASES             the core tables plus the languages and spellings that occur in the full persona
                                  bank (Europe, South-East Asia, Africa, South Asia), with dialect -> base mappings

resolve(persona) -> {'target', 'base', 'basis', 'lid_verifiable', 'native_base', 'main_base'}
  target          language name used in the translation prompt: canonical label of native_language, else of
                  main_language. Varieties the tables know (Swiss German, Cantonese, ...) stay as they are.
  base            the language the LID can report for that target (dialect -> base language); used by the
                  cross-lingual language check and for language-matched prompt/persona matching.
  lid_verifiable  base is a label that fastText lid.176 (common.lid.ISO_NAMES) or Lingua can return.
The persona's own dialect field is not touched and still reaches the persona prompt.

Report over a bank (CPU):
  python -m personafactory.common.lang_canon --bank $PF_BANK --out ./outputs/lang_report.json
"""
import argparse, collections, difflib, functools, json, re

from personafactory.common import lid

CORE_LANGUAGES = '''English|German|French|Italian|Spanish|Portuguese|Ukrainian|Bulgarian|Russian|Belarusian|Polish|Czech|Slovak|Slovenian|Croatian|Serbian|Bosnian|Montenegrin|Macedonian|Albanian|Greek|Dutch|Danish|Swedish|Norwegian|Finnish|Estonian|Latvian|Lithuanian|Icelandic|Romanian|Hungarian|Turkish|Arabic|Hebrew|Persian|Urdu|Hindi|Bengali|Marathi|Punjabi|Gujarati|Tamil|Telugu|Kannada|Malayalam|Odia|Assamese|Sindhi|Pashto|Nepali|Sinhala|Burmese|Thai|Vietnamese|Lao|Khmer|Indonesian|Malay|Javanese|Sundanese|Filipino|Tagalog|Cebuano|Korean|Japanese|Mandarin Chinese|Cantonese|Hakka|Hokkien|Teochew|Tibetan|Uyghur|Mongolian|Kazakh|Uzbek|Tajik|Kyrgyz|Azerbaijani|Georgian|Armenian|Kurdish|Amharic|Oromo|Tigrinya|Somali|Swahili|Hausa|Yoruba|Igbo|Zulu|Xhosa|Afrikaans|Twi|Akan|Wolof|Luxembourgish|Romansh|Irish|Welsh|Scottish Gaelic|Catalan|Basque|Galician|Maltese|Maori|Fijian|Samoan'''.split('|')
EXTRA_LANGUAGES = '''Tetum|Ilocano|Hiligaynon|Waray|Bikol|Kapampangan|Pangasinan|Minangkabau|Balinese|Madurese|Acehnese|Buginese|Banjar|Batak|Betawi|Sasak|Shan|Karen|Mon|Kachin|Chin|Rakhine|Hmong|Tatar|Bashkir|Chechen|Ossetian|Yiddish|Romani|Faroese|Frisian|Sami|Sorbian|Kashubian|Silesian|Rusyn|Gagauz|Occitan|Asturian|Aragonese|Corsican|Sardinian|Friulian|Neapolitan|Venetian|Sicilian|Ladin|Low German|Limburgish|Alsatian|Bavarian|Walloon|Breton|Scots|Manx|Cornish|Aromanian|Esperanto|Latin|Turkmen|Karakalpak|Dari|Balochi|Saraiki|Kashmiri|Konkani|Tulu|Bhojpuri|Maithili|Awadhi|Rajasthani|Chhattisgarhi|Haryanvi|Dogri|Santali|Manipuri|Mizo|Khasi|Garo|Bodo|Dhivehi|Dzongkha|Kinyarwanda|Kirundi|Luganda|Lingala|Kikuyu|Luo|Shona|Ndebele|Sesotho|Setswana|Tsonga|Swati|Venda|Chichewa|Bemba|Malagasy|Fula|Bambara|Mandinka|Soninke|Ewe|Ga|Fante|Krio|Kanuri|Tamazight|Kabyle|Tigre|Sidamo|Wolaytta|Afar|Haitian Creole|Papiamento|Guarani|Quechua|Aymara|Nahuatl|Mapudungun|Tok Pisin|Bislama|Tongan|Hawaiian|Chamorro|Marshallese|Palauan|Zhuang|Wu Chinese|Min Nan|Moroccan Arabic|Lebanese Arabic|Swiss German|Norwegian Bokmål|Norwegian Nynorsk|Serbo-Croatian|Roman Urdu|Kikongo|Tshiluba|Sango|Kituba'''.split('|')
LANGUAGES = list(dict.fromkeys(CORE_LANGUAGES + EXTRA_LANGUAGES))

_CORE_ALIAS_UPDATE = {'chinese': 'Mandarin Chinese', 'mandarin': 'Mandarin Chinese',
    'standard chinese': 'Mandarin Chinese', 'chinese mandarin': 'Mandarin Chinese',
    'chinese, mandarin': 'Mandarin Chinese', 'traditional chinese': 'Mandarin Chinese',
    'farsi': 'Persian', 'bangla': 'Bengali', 'slovene': 'Slovenian', 'panjabi': 'Punjabi',
    'sinhalese': 'Sinhala', 'bahasa indonesia': 'Indonesian', 'bahasa indonesian': 'Indonesian',
    'bahasa malaysia': 'Malay', 'bahasa melayu': 'Malay', 'filipino (tagalog)': 'Filipino',
    'afaan oromo': 'Oromo', 'afaan oromoo': 'Oromo', 'afan oromo': 'Oromo',
    'amarigna': 'Amharic', 'burma': 'Burmese', 'burmes': 'Burmese', 'bamar': 'Burmese',
    'bokmål': 'Norwegian Bokmål', 'norwegian bokmål': 'Norwegian Bokmål',
    'bokmål norwegian': 'Norwegian Bokmål', 'nynorsk': 'Norwegian Nynorsk', 'norsk': 'Norwegian',
    'deutsch': 'German', 'schweizerdeutsch': 'Swiss German', 'swiss german': 'Swiss German',
    'swiss-german': 'Swiss German', 'darija': 'Moroccan Arabic', 'lebanese arabic': 'Lebanese Arabic',
    'flemish': 'Dutch', 'română': 'Romanian', 'român': 'Romanian', 'slovenčina': 'Slovak',
    'português': 'Portuguese', 'luxembourgesch': 'Luxembourgish', 'luxembourish': 'Luxembourgish',
    'binisaya': 'Cebuano', 'urdū': 'Urdu', 'serbo-croatian': 'Serbo-Croatian',
    'roman urdu': 'Roman Urdu', 'scottish english': 'English', 'irish english': 'English',
    'isizulu': 'Zulu', 'isixhosa': 'Xhosa', 'bisaya': 'Cebuano', 'français': 'French',
    'tatar': 'Tatar', 'kikuyu': 'Kikuyu', 'scots': 'Scots', 'breton': 'Breton',
    'walloon': 'Walloon', 'sicilian': 'Sicilian', 'shan': 'Shan', 'karen': 'Karen',
    'saraiki': 'Saraiki', 'balochi': 'Balochi', 'ilokano': 'Ilocano', 'ilocano': 'Ilocano'}
CORE_ALIASES = {v.casefold(): v for v in CORE_LANGUAGES}
CORE_ALIASES.update(_CORE_ALIAS_UPDATE)

ALIASES = {v.casefold(): v for v in LANGUAGES}
ALIASES.update(_CORE_ALIAS_UPDATE)
ALIASES.update({'moldovan': 'Romanian', 'moldavian': 'Romanian', 'castilian': 'Spanish', 'español': 'Spanish',
    'italiano': 'Italian', 'nederlands': 'Dutch', 'svenska': 'Swedish', 'dansk': 'Danish', 'suomi': 'Finnish',
    'magyar': 'Hungarian', 'polski': 'Polish', 'čeština': 'Czech', 'hrvatski': 'Croatian', 'srpski': 'Serbian',
    'bahasa': 'Indonesian', 'tiếng việt': 'Vietnamese', 'khmer (cambodian)': 'Khmer', 'cambodian': 'Khmer',
    'laotian': 'Lao', 'myanmar': 'Burmese', 'burmese (myanmar)': 'Burmese', 'tetun': 'Tetum',
    'hiligaynon (ilonggo)': 'Hiligaynon', 'ilonggo': 'Hiligaynon', 'waray-waray': 'Waray', 'bicolano': 'Bikol',
    'kapampangan (pampanga)': 'Kapampangan', 'taglish': 'Filipino', 'pilipino': 'Filipino',
    'singlish': 'English', 'manglish': 'English', 'nigerian pidgin': 'English', 'pidgin english': 'English',
    'hinglish': 'Hindi', 'putonghua': 'Mandarin Chinese', 'simplified chinese': 'Mandarin Chinese',
    'taiwanese mandarin': 'Mandarin Chinese', 'taiwanese hokkien': 'Hokkien', 'taiwanese': 'Hokkien',
    'yue': 'Cantonese', 'shanghainese': 'Wu Chinese', 'minnan': 'Min Nan', 'hokkienese': 'Hokkien',
    'brazilian portuguese': 'Portuguese', 'european portuguese': 'Portuguese', 'québécois': 'French',
    'quebec french': 'French', 'canadian french': 'French', 'swiss french': 'French', 'belgian french': 'French',
    'austrian german': 'German', 'standard german': 'German', 'high german': 'German', 'hochdeutsch': 'German',
    'modern standard arabic': 'Arabic', 'msa': 'Arabic', 'gulf arabic': 'Arabic', 'egyptian arabic': 'Arabic',
    'levantine arabic': 'Arabic', 'sudanese arabic': 'Arabic', 'iraqi arabic': 'Arabic', 'syrian arabic': 'Arabic',
    'tunisian arabic': 'Arabic', 'algerian arabic': 'Arabic', 'libyan arabic': 'Arabic', 'yemeni arabic': 'Arabic',
    'hassaniya': 'Arabic', 'kurmanji': 'Kurdish', 'sorani': 'Kurdish', 'pashtu': 'Pashto', 'pushto': 'Pashto',
    'oriya': 'Odia', 'meitei': 'Manipuri', 'meiteilon': 'Manipuri', 'divehi': 'Dhivehi', 'nepalese': 'Nepali',
    'sesotho sa leboa': 'Sesotho', 'sepedi': 'Sesotho', 'northern sotho': 'Sesotho', 'southern sotho': 'Sesotho',
    'tswana': 'Setswana', 'sotho': 'Sesotho', 'nyanja': 'Chichewa', 'chewa': 'Chichewa', 'kiswahili': 'Swahili',
    'ganda': 'Luganda', 'rwanda': 'Kinyarwanda', 'rundi': 'Kirundi', 'fulfulde': 'Fula', 'pulaar': 'Fula',
    'fulani': 'Fula', 'asante twi': 'Twi', 'akuapem twi': 'Twi', 'fanti': 'Fante', 'berber': 'Tamazight',
    'amazigh': 'Tamazight', 'tamazight (berber)': 'Tamazight', 'haitian': 'Haitian Creole', 'kreyòl': 'Haitian Creole',
    'west frisian': 'Frisian', 'northern sami': 'Sami', 'irish gaelic': 'Irish', 'gaeilge': 'Irish',
    'gaelic': 'Scottish Gaelic', 'cymraeg': 'Welsh', 'euskara': 'Basque', 'galego': 'Galician', 'català': 'Catalan',
    'valencian': 'Catalan', 'catalan (valencian)': 'Catalan', 'lëtzebuergesch': 'Luxembourgish',
    'rumantsch': 'Romansh', 'romanche': 'Romansh', 'malti': 'Maltese', 'shqip': 'Albanian', 'gheg albanian': 'Albanian',
    'tosk albanian': 'Albanian', 'македонски': 'Macedonian', 'български': 'Bulgarian', 'русский': 'Russian',
    'українська': 'Ukrainian', 'беларуская': 'Belarusian', 'ελληνικά': 'Greek', 'cypriot greek': 'Greek',
    'türkçe': 'Turkish', 'azeri': 'Azerbaijani', 'kazakh (qazaq)': 'Kazakh', 'qazaq': 'Kazakh',
    'tajiki': 'Tajik', 'kirghiz': 'Kyrgyz', 'uighur': 'Uyghur', 'bahasa melayu brunei': 'Malay',
    'malaysian': 'Malay', 'brunei malay': 'Malay', 'jawa': 'Javanese', 'sunda': 'Sundanese', 'minang': 'Minangkabau',
    'bugis': 'Buginese', 'aceh': 'Acehnese', 'bali': 'Balinese', 'madura': 'Madurese', 'thai (central)': 'Thai',
    'isan': 'Lao', 'isaan': 'Lao', 'northern thai': 'Thai', 'southern thai': 'Thai', 'vietnamese (northern)': 'Vietnamese',
    'hebrew (ivrit)': 'Hebrew', 'ivrit': 'Hebrew'})

# target -> base language the LID can report (dialect -> base)
BASE = {'Mandarin Chinese': 'Chinese', 'Cantonese': 'Chinese', 'Hakka': 'Chinese', 'Hokkien': 'Chinese',
        'Teochew': 'Chinese', 'Wu Chinese': 'Chinese', 'Min Nan': 'Chinese', 'Swiss German': 'German',
        'Norwegian Bokmål': 'Norwegian', 'Norwegian Nynorsk': 'Norwegian', 'Filipino': 'Tagalog',
        'Moroccan Arabic': 'Arabic', 'Lebanese Arabic': 'Arabic', 'Roman Urdu': 'Urdu', 'Serbo-Croatian': 'Serbian',
        'Twi': 'Akan', 'Fante': 'Akan', 'Setswana': 'Tswana', 'Sesotho': 'Sotho', 'Luganda': 'Ganda',
        'Slovenian': 'Slovenian', 'Alsatian': 'German', 'Bavarian': 'German', 'Scots': 'English'}

try:
    import lingua
    _LINGUA = {lid.norm(l.name) for l in lingua.Language.all()}
except Exception:
    _LINGUA = set()
LID_LABELS = set(lid.ISO_NAMES.values()) | _LINGUA | {'Slovenian', 'Norwegian', 'Chinese', 'Tagalog'}
_FUZZY_KEYS = sorted(k for k in ALIASES if len(k) >= 4)


def _match(text, aliases):
    """Whole-word alias hits in text as (start, -length, target), sorted."""
    matches = []
    for alias, target in aliases.items():
        m = re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', text)
        if m:
            matches.append((m.start(), -len(alias), target))
    matches.sort()
    return matches


@functools.lru_cache(maxsize=30000)
def canonical_label_core(value):
    """Strict resolution on the core tables: exact alias, alias before a parenthetical, or one recognised
    language (possibly with a geographic qualifier); competing languages stay unresolved (None)."""
    if not isinstance(value, str) or len(value) > 300 or '\n' in value:
        return None
    text = value.strip().casefold()
    if text in CORE_ALIASES:
        return CORE_ALIASES[text]
    primary = text.split('(', 1)[0].strip()  # a parenthetical only qualifies the language
    if primary in CORE_ALIASES:
        return CORE_ALIASES[primary]
    matches = _match(text, CORE_ALIASES)
    if matches:
        first = matches[0]
        nonnested = [m for m in matches if m[0] >= first[0] - first[1]]
        if all(m[2] == first[2] for m in nonnested):
            return first[2]
    return None


@functools.lru_cache(maxsize=200000)
def canonical_label(value):
    """canonical_label_core semantics on the full tables, plus: several named languages resolve to the first one
    when the others are its own varieties, and a fuzzy fallback for misspellings."""
    if not isinstance(value, str) or len(value) > 300 or '\n' in value:
        return None
    text = value.strip().casefold()
    if not text:
        return None
    if text in ALIASES:
        return ALIASES[text]
    primary = text.split('(', 1)[0].strip()
    if primary in ALIASES:
        return ALIASES[primary]
    matches = _match(text, ALIASES)
    if matches:
        first = matches[0]
        nonnested = [m for m in matches if m[0] >= first[0] - first[1]]
        if all(m[2] == first[2] for m in nonnested):
            return first[2]
        bases = {BASE.get(m[2], m[2]) for m in nonnested + [first]}
        if len(bases) == 1:
            return first[2]
        return None
    # fuzzy fallback for misspellings ("Mandinand Chinese", "Portugese"): whole string, then each word
    for cand in [primary] + [w for w in re.split(r'[\s,/;-]+', primary) if len(w) >= 4]:
        hit = difflib.get_close_matches(cand, _FUZZY_KEYS, n=1, cutoff=0.84)
        if hit:
            return ALIASES[hit[0]]
    return None


def base_of(label):
    """LID-level base language for a canonical label (or a raw detector label)."""
    if not label:
        return None
    if label in BASE:
        return BASE[label]
    return lid.norm(label)


def lid_verifiable(label):
    return base_of(label) in LID_LABELS


def resolve(persona):
    bg = persona.get('background') or {}
    nat, main = canonical_label(bg.get('native_language')), canonical_label(bg.get('main_language'))
    target = nat or main
    return {'target': target, 'base': base_of(target), 'basis': 'native' if nat else 'main' if main else 'unresolved',
            'lid_verifiable': bool(target) and lid_verifiable(target),
            'native_base': base_of(nat), 'main_base': base_of(main)}


def report(bank_path, out_path):
    c = collections.Counter()
    tgt, unres, unver, raw_nat, raw_main = (collections.Counter() for _ in range(5))
    for l in open(bank_path, encoding='utf-8'):
        p = json.loads(l)
        r = resolve(p)
        bg = p.get('background') or {}
        raw_nat[str(bg.get('native_language'))] += 1
        raw_main[str(bg.get('main_language'))] += 1
        c['rows'] += 1
        c['basis/' + r['basis']] += 1
        if r['target']:
            tgt[r['target']] += 1
            c['lid_verifiable/' + str(r['lid_verifiable'])] += 1
            if not r['lid_verifiable']:
                unver[r['target']] += 1
            c['english_target/' + str(r['base'] == 'English')] += 1
            c['cross_lingual_eligible'] += r['base'] != 'English'
        else:
            unres[f"{bg.get('native_language')} | {bg.get('main_language')}"] += 1
        c['speaks_english_native_or_main'] += 'English' in (r['native_base'], r['main_base'])
    out = {'counts': dict(c), 'targets': tgt.most_common(), 'not_lid_verifiable': unver.most_common(),
           'unresolved_top200': unres.most_common(200), 'distinct_raw_native': len(raw_nat),
           'distinct_raw_main': len(raw_main), 'raw_main_top100': raw_main.most_common(100)}
    json.dump(out, open(out_path, 'w'), indent=1, ensure_ascii=False)
    print(json.dumps(out['counts'], indent=1))


if __name__ == '__main__':
    import os
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--bank', default=os.environ.get('PF_BANK'), required='PF_BANK' not in os.environ)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    report(a.bank, a.out)
