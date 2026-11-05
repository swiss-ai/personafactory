#!/usr/bin/env python
"""Compute persona-bank distributions for the bank figures.

Reads the released bank (one persona per line) and writes bank_stats.json (counts per background
and style feature, the list of ages, and the country -> ISO3 map), consumed by make_figures.py.

Usage:
    python -m personafactory.figures.compute_stats --bank ./data/persona_bank/persona_bank.jsonl \
        --out ./outputs/figures/bank_stats.json
"""
import argparse
import collections
import json
import os

# language label -> canonical language (same normalization used in the paper)
LANG_NORM = {
    "Mandarin Chinese": "Chinese", "Mandarin": "Chinese", "Chinese (Mandarin)": "Chinese",
    "Bangla": "Bengali", "Bangladesh": "Bengali",
    "Filipino": "Filipino/Tagalog", "Tagalog": "Filipino/Tagalog",
    "Filipino (Tagalog)": "Filipino/Tagalog",
    "Slovene": "Slovenian", "Slovenčina": "Slovak",
    "Scottish English": "English", "English (Philippines)": "English",
    "English (Malaysian)": "English",
    "Bahasa Indonesia": "Indonesian", "Bahasa Malaysia": "Malay", "Bahasa Melayu": "Malay",
    "Afaan Oromo": "Oromo", "Portuguese (European)": "Portuguese",
    "Bokmål": "Norwegian", "Norwegian Bokmål": "Norwegian",
    "German (Swiss)": "German", "Dutch (Flemish)": "Dutch", "Flemish": "Dutch",
    "Pakistani Urdu": "Urdu", "Modern Standard Arabic": "Arabic",
    "Lebanese Arabic": "Arabic", "Romansh (Sursilvan)": "Romansh",
    "Sinhalese": "Sinhala", "Burma": "Burmese",
    "Persian (Farsi)": "Persian", "Farsi": "Persian",
    "Luxembourgish (Letzebuergesch)": "Luxembourgish", "Luxembourish": "Luxembourgish",
    " Finnish": "Finnish",
}

# generator model id -> short label
MODEL_LABEL = {
    "google/gemma-4-31B-it": "Gemma 4 31B",
    "mistralai/Ministral-3-14B-Instruct-2512": "Ministral 3 14B",
    "zai-org/GLM-4.7-Flash": "GLM 4.7 Flash",
}

# Bank country name -> ISO 3166-1 alpha-3 code as used by the Natural Earth map
# (ISO_A3_EH / ISO_A3); covers all 81 countries of the seed grid.
COUNTRY_ISO3 = {
    "Switzerland": "CHE", "India": "IND", "China": "CHN", "Germany": "DEU", "UK": "GBR",
    "Japan": "JPN", "France": "FRA", "Pakistan": "PAK", "South Korea": "KOR", "Spain": "ESP",
    "Thailand": "THA", "Vietnam": "VNM", "Indonesia": "IDN", "Philippines": "PHL", "USA": "USA",
    "Italy": "ITA", "Ukraine": "UKR", "Malaysia": "MYS", "Belgium": "BEL", "Portugal": "PRT",
    "Netherlands": "NLD", "Austria": "AUT", "Serbia": "SRB", "Poland": "POL", "Croatia": "HRV",
    "Bangladesh": "BGD", "Canada": "CAN", "Russia": "RUS", "Brazil": "BRA", "Finland": "FIN",
    "Mexico": "MEX", "Sweden": "SWE", "Norway": "NOR", "Denmark": "DNK", "Australia": "AUS",
    "Slovakia": "SVK", "Bulgaria": "BGR", "Greece": "GRC", "Czechia": "CZE", "Romania": "ROU",
    "Hungary": "HUN", "Nigeria": "NGA", "Luxembourg": "LUX", "Sri Lanka": "LKA",
    "Colombia": "COL", "Argentina": "ARG", "Myanmar": "MMR", "Nepal": "NPL", "Turkey": "TUR",
    "South Africa": "ZAF", "Ireland": "IRL", "Taiwan": "TWN", "Latvia": "LVA", "Egypt": "EGY",
    "Bosnia & Herzegovina": "BIH", "North Macedonia": "MKD", "Chile": "CHL", "Estonia": "EST",
    "Iran": "IRN", "Montenegro": "MNE", "Peru": "PER", "New Zealand": "NZL", "Kosovo": "XKX",
    "Iceland": "ISL", "Lithuania": "LTU", "Saudi Arabia": "SAU", "Kenya": "KEN",
    "Ethiopia": "ETH", "Albania": "ALB", "Ghana": "GHA", "Morocco": "MAR", "Slovenia": "SVN",
    "Belarus": "BLR", "Guatemala": "GTM", "Tanzania": "TZA", "Kazakhstan": "KAZ",
    "Israel": "ISR", "Lebanon": "LBN", "UAE": "ARE", "Senegal": "SEN", "Uzbekistan": "UZB",
}


def short_model(m):
    """Short generator label; tolerates a served-name namespace prefix before the public id."""
    m = m or ""
    for full, label in MODEL_LABEL.items():
        if m == full or m.endswith("/" + full):
            return label
    return m.split("/")[-1] or "unknown"


# The style schema offers fixed options but also permits a short free-text value,
# so the raw fields carry case variants and a long tail of bespoke strings. Each
# rule list maps substrings (checked in order) onto the canonical option; anything
# unmatched is counted as "other (free-text)".
STYLE_RULES = {
    "capitalization": [
        ("lowercase", "all lowercase"),
        ("first-word", "first-word only, no final period"),
        ("first word", "first-word only, no final period"),
        ("inconsistent", "inconsistent"),
        ("all-caps", "ALL-CAPS for emphasis"),
        ("all caps", "ALL-CAPS for emphasis"),
        ("standard", "standard"),
    ],
    "punctuation": [
        ("ellipsis", "ellipsis-heavy (...)"),
        ("minimal", "minimal (drops end punctuation)"),
        ("drops end", "minimal (drops end punctuation)"),
        ("excessive", "excessive (!!!/???)"),
        ("emoji", "emoji or line-breaks"),
        ("line-break", "emoji or line-breaks"),
        ("standard", "standard"),
    ],
    "emoji_use": [
        ("kaomoji", "kaomoji/stickers"),
        ("sticker", "kaomoji/stickers"),
        ("emoticon", "emoticons only"),
        ("rare", "rare/functional"),
        ("functional", "rare/functional"),
        ("frequent", "frequent/decorative"),
        ("decorative", "frequent/decorative"),
        ("none", "none"),
    ],
    "typo_tendency": [
        ("clean", "clean/proofread"),
        ("proofread", "clean/proofread"),
        ("occasional", "occasional uncorrected typos"),
        ("phonetic", "phonetic spelling"),
        ("voice-to-text", "voice-to-text/autocorrect"),
        ("autocorrect", "voice-to-text/autocorrect"),
    ],
    "message_structure": [
        ("terse", "terse one-liners"),
        ("one-liner", "terse one-liners"),
        ("fragmented", "fragmented across short lines"),
        ("medium", "medium, complete sentences"),
        ("long", "long/elaborate"),
        ("elaborate", "long/elaborate"),
    ],
}


def canon_style(field, value):
    if value in (None, ""):
        return None
    v = str(value).strip().lower()
    for needle, label in STYLE_RULES[field]:
        if needle in v:
            return label
    return "other (free-text)"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bank", default=os.environ.get("PF_BANK"), required=os.environ.get("PF_BANK") is None,
                    help="persona bank JSONL (default: $PF_BANK)")
    ap.add_argument("--out", default="bank_stats.json", help="output stats JSON")
    args = ap.parse_args()
    iso = COUNTRY_ISO3

    counters = {k: collections.Counter() for k in (
        "country", "region", "gender", "education", "fluency", "ai_stance",
        "occupation", "sector", "language", "generator", "segment",
        "capitalization", "punctuation", "emoji_use", "typo_tendency",
        "message_structure", "code_switching_freq", "sentence_length",
        "question_framing",
    )}
    ages = []
    n = 0

    with open(args.bank) as fh:
        for line in fh:
            p = json.loads(line)
            bg = p.get("background") or {}
            st = p.get("style") or {}
            sk = st.get("chatting_style_structured") or {}
            n += 1

            counters["country"][bg.get("country")] += 1
            counters["region"][bg.get("region")] += 1
            counters["gender"][bg.get("gender")] += 1
            counters["fluency"][bg.get("digital_fluency")] += 1
            counters["ai_stance"][bg.get("ai_stance")] += 1
            counters["occupation"][bg.get("occupation")] += 1
            counters["sector"][bg.get("sector")] += 1
            counters["segment"][bg.get("llm_user_segment")] += 1
            counters["generator"][short_model(p.get("generator_model"))] += 1

            edu = (bg.get("education") or {}).get("level")
            counters["education"][edu] += 1

            lang = bg.get("main_language")
            counters["language"][LANG_NORM.get(lang, lang)] += 1

            try:
                ages.append(int(bg.get("age")))
            except (TypeError, ValueError):
                pass

            for field in STYLE_RULES:
                counters[field][canon_style(field, sk.get(field))] += 1
            counters["code_switching_freq"][st.get("code_switching_freq")] += 1
            counters["sentence_length"][st.get("sentence_length_tendency")] += 1
            counters["question_framing"][st.get("question_framing")] += 1

    def clean(c):
        return {k: v for k, v in c.most_common() if k not in (None, "", "unmarked")}

    stats = {k: clean(v) for k, v in counters.items()}
    stats["_total"] = n
    stats["_ages"] = ages
    stats["_country_iso"] = iso
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump(stats, open(args.out, "w"), ensure_ascii=False)

    print(f"personas: {n}")
    for k in ("country", "region", "occupation", "language", "generator"):
        print(f"  {k}: {len(stats[k])} distinct")
    missing = [c for c in stats["country"] if c not in iso]
    print("countries without ISO3:", missing or "none")


if __name__ == "__main__":
    main()
