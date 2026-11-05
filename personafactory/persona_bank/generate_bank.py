"""Generate the persona bank: one structured profile per call, sampled from the seed grid.

Each worker walks a (sharded) list of (region, country, sub_region) locations. For every slot it
samples an occupation (region-independent, AI-usage weighted), gender, age, AI stance and a
sector-coherent digital fluency, then asks one generator model for a full two-layer profile
(background + style) under guided-JSON decoding against the Persona schema. Output is appended
and flushed per profile, and a re-run only fills the remaining per-location deficit (resumable).

Two seed grids:
  base      201 locations in 81 countries, 211 occupations (the grid defined in this file);
            per-location targets = --coverage_per_location x region weight x sub-region scale.
  extended  599 locations in 177 countries, 575 occupations and up to five more seed axes
            (settlement, education level, life stage, home language, typing style), defined in
            grid_extended.py; with --target_total the per-location targets come from per-country
            quotas (optionally restricted to some target blocks with --block_totals).

Inputs:  an OpenAI-compatible endpoint serving the generator (--base_url / PF_BASE_URL,
         key in PF_API_KEY).
Outputs: <output_dir>/persona_bank_<model>[.shardIIofNN].jsonl, plus a per-call log
         <output_dir>/persona_bank_<model>[.shardIIofNN].attempts.jsonl.

Examples (one shard of one generator; the settings of every shard are in README.md):
    python -m personafactory.persona_bank.generate_bank --model_name google/gemma-4-31B-it \
        --base_url http://localhost:8000/v1 --coverage_per_location 88 \
        --shard_count 80 --shard_index 0 --seed 1000 --output_dir ./data/persona_bank/base
    python -m personafactory.persona_bank.generate_bank --grid extended --model_name google/gemma-4-31B-it \
        --base_url http://localhost:8000/v1 --target_total 590000 --n_generators 3 --shard_by slot \
        --shard_count 1920 --shard_index 0 --seed 31000 --temperature 0.9 \
        --output_dir ./data/persona_bank/extended
"""
import os
import json
import uuid
import argparse
import random
import collections
import threading
import time
from openai import OpenAI
try:  # optional: read PF_* variables from a local .env file
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from personafactory.persona_bank.schema import Persona, json_schema  # ChattingStyle is nested inside StyleLayer

# OpenAI-compatible endpoint of the served generator (override per model with --base_url).
API_BASE_URL = os.environ.get("PF_BASE_URL", "http://localhost:8000/v1")

# Generator pool. MiniMax is deliberately EXCLUDED because it is the downstream
# judge; keeping it out of generation preserves generator != judge. When the
# served model name differs from the public id, pass it via --model_name.
DEFAULT_MODELS = [
    "google/gemma-4-31B-it",
    "zai-org/GLM-4.7-Flash",
    "mistralai/Ministral-3-14B-Instruct-2512",
]

GENDERS = ["Male", "Female", "Non-binary"]
AI_STANCES = ["Pragmatic", "Skeptical", "Enthusiastic", "Naive"]
DIGITAL_FLUENCIES = ["High", "Medium", "Low"]

# Digital fluency is sampled COHERENTLY with the occupation's sector (not uniformly)
# and skewed toward Medium/High, so the bank mostly represents plausible LLM users.
# Hybrid target: a realistic-user majority + a tagged low-fluency minority.
# weights = (High, Medium, Low)
SECTOR_FLUENCY_WEIGHTS = {
    "Software & IT":             (0.80, 0.18, 0.02),
    "Engineering":               (0.60, 0.35, 0.05),
    "Business & finance":        (0.55, 0.38, 0.07),
    "Creative & media":          (0.55, 0.38, 0.07),
    "Education":                 (0.45, 0.45, 0.10),
    "Healthcare":                (0.40, 0.48, 0.12),
    "Public & civil service":    (0.35, 0.50, 0.15),
    "Sales & retail":            (0.30, 0.50, 0.20),
    "Logistics & transport":     (0.25, 0.50, 0.25),
    "Hospitality":               (0.25, 0.50, 0.25),
    "Skilled trades":            (0.22, 0.50, 0.28),
    "Personal services":         (0.25, 0.50, 0.25),
    "Manufacturing":             (0.20, 0.50, 0.30),
    "Agriculture & environment": (0.18, 0.45, 0.37),
    "Maritime":                  (0.20, 0.45, 0.35),
    "Extractive":                (0.20, 0.50, 0.30),
}
DEFAULT_FLUENCY_WEIGHTS = (0.35, 0.45, 0.20)


def sample_fluency(sector):
    """Coherent, realism-skewed digital fluency for a given sector."""
    w = SECTOR_FLUENCY_WEIGHTS.get(sector, DEFAULT_FLUENCY_WEIGHTS)
    return random.choices(DIGITAL_FLUENCIES, weights=w, k=1)[0]

# ===========================================================================
# Realism priors for the seeded background attributes.
# ===========================================================================
# (1) Gender: country/region-conditioned. Non-binary is a low-single-digit share in the most
# progressive societies and effectively absent (culturally/legally) elsewhere; a uniform share
# would be unrealistic.
NB_BASE = {"Nordics": .05, "North America": .05, "Oceania": .05, "Western Europe": .04,
           "Southern Europe": .02, "Eastern Europe": .01, "LATAM": .02, "East Asia": .015,
           "Southeast Asia": .015, "South Asia": .01, "Sub-Saharan Africa": .01,
           "MENA": .003, "Central & North Asia": .005}
NB_COUNTRY = {c: .003 for c in ("Saudi Arabia", "UAE", "Qatar", "Kuwait", "Iran", "Egypt",
              "Pakistan", "Bangladesh", "Russia", "Nigeria", "Afghanistan", "Iraq", "Yemen", "Oman")}
def sample_gender(region, country):
    nb = NB_COUNTRY.get(country, NB_BASE.get(region, .01))
    r = random.random()
    if r < nb:
        return "Non-binary"
    return "Male" if r < nb + (1 - nb) / 2 else "Female"

# (2) Occupation: sample weighted by AI-usage propensity (target = the LLM-user population, not the
# general workforce). Non-zero floor keeps a realistic long tail (some locksmiths do use AI).
SECTOR_AI_PROPENSITY = {
    "Software & IT": 10.0, "Creative & media": 7.0, "Business & finance": 6.0, "Education": 6.0,
    "Engineering": 5.0, "Healthcare": 3.0, "Public & civil service": 3.0, "Sales & retail": 2.5,
    "Hospitality": 1.5, "Personal services": 1.5, "Logistics & transport": 1.2,
    "Skilled trades": 1.0, "Manufacturing": 1.0, "Agriculture & environment": 0.8,
    "Maritime": 0.8, "Extractive": 0.7,
}
DEFAULT_PROPENSITY = 1.5
STUDENT_BOOST = 6.0   # students exist but are ~1%; they're heavy AI users -> boost their share
def occupation_weight(profession, sector):
    w = SECTOR_AI_PROPENSITY.get(sector, DEFAULT_PROPENSITY)
    if "student" in profession.lower():
        w *= STUDENT_BOOST
    return w
def sample_occupation(region, country, sub_region):
    pairs = allowed_occupations(region, country, sub_region)   # [(profession, sector), ...]
    weights = [occupation_weight(p, s) for p, s in pairs]
    return random.choices(pairs, weights=weights, k=1)[0]

# (3) Sub-region language/dialect conditioning (west/central/east Ukrainian gradient).
# Only the eastern/southern branch samples its weight.
SUBREGION_LANG_INFLUENCE = {   # (country, sub_region) -> (band, P(surzhyk branch))
    ("Ukraine", "Lviv"): ("ua_west", 0.02), ("Ukraine", "Ivano-Frankivsk"): ("ua_west", 0.02),
    ("Ukraine", "Ternopil"): ("ua_west", 0.02),
    ("Ukraine", "Kyiv"): ("ua_central", 0.15), ("Ukraine", "Vinnytsia"): ("ua_central", 0.15),
    ("Ukraine", "Kharkiv"): ("ua_east", 0.45), ("Ukraine", "Dnipro"): ("ua_east", 0.45),
    ("Ukraine", "Zaporizhzhia"): ("ua_east", 0.45), ("Ukraine", "Odesa"): ("ua_east", 0.45),
}
_BAND_RULES = {
    "ua_west": ("Western Ukrainian (Galician / Carpathian / Polish-influenced). Ukrainian-dominant; "
                "effectively NO Russian — if Russian appears at all, only as something consciously "
                "avoided. The dialect label MUST reference western Ukraine, never 'Eastern Ukrainian'."),
    "ua_central": ("Central Ukrainian, standard literary Ukrainian; mostly Ukrainian with some urban "
                   "bilingualism. The dialect label must reference central Ukraine."),
    "ua_east": ("Eastern/Southern Ukrainian; realistic surzhyk is fine — Ukrainian speech with "
                "OCCASIONAL Russian words / light code-switching. native_language stays Ukrainian; "
                "Russian is only a secondary code-switch layer, never the described default."),
    "ua_east_min": ("Eastern/Southern Ukrainian. native_language is Ukrainian; THIS speaker uses "
                    "mostly standard Ukrainian with only minimal Russian influence. The dialect label "
                    "must reference eastern/southern Ukraine, not Russia."),
}
def lang_influence_rule(country, sub_region):
    spec = SUBREGION_LANG_INFLUENCE.get((country, sub_region))
    if not spec:
        return ""
    band, weight = spec
    if band == "ua_east":
        band = "ua_east" if random.random() < weight else "ua_east_min"
    return _BAND_RULES.get(band, "")

# (4) Per-sub-region coverage scale: lets us expand a country's sub-region grid (finer east/west
# gradient) WITHOUT inflating its total persona count. Default 1.0.
SUBREGION_COVERAGE_SCALE = {sr: 1/3 for sr in    # 9 Ukrainian sub-regions share the quota of 3
    ("Lviv", "Ivano-Frankivsk", "Ternopil", "Kyiv", "Vinnytsia", "Kharkiv", "Dnipro", "Zaporizhzhia", "Odesa")}

# ---------------------------------------------------------------------------
# Occupations: ACTUAL professions, not areas of proficiency.
#
# Each entry is (profession, sector, gate):
#   * `profession` is a concrete real job stored in `occupation`.
#   * `sector`     is a coarse grouping kept only for balancing / analysis.
#   * `gate`       is None for professions plausible ANYWHERE, or a tag for the
#                  handful that are *physically / economically* place-bound.
#
# Design choices driven by review feedback:
#   1. Professions are concrete ("diesel mechanic"), not fields ("Skilled trades").
#   2. Occupation is sampled INDEPENDENTLY of region: a person from a farming
#      sub-region is just as likely to be a QA tester as a farmer. This removes
#      the demographic stereotype of mapping each region to its cliché industry.
#      Region shapes language / culture / references, NOT the choice of job.
#   3. Only genuinely place-bound jobs are gated (you cannot be a deep-sea fisher
#      in a landlocked desert). Gating is about physical possibility, not cliché.
# ---------------------------------------------------------------------------
OCCUPATIONS = [
    # Healthcare
    ("General practitioner", "Healthcare", None),
    ("Pediatric ICU nurse", "Healthcare", None),
    ("Operating-theatre nurse", "Healthcare", None),
    ("Midwife", "Healthcare", None),
    ("Emergency paramedic", "Healthcare", None),
    ("General dentist", "Healthcare", None),
    ("Dental hygienist", "Healthcare", None),
    ("Physiotherapist", "Healthcare", None),
    ("Community pharmacist", "Healthcare", None),
    ("Radiographer", "Healthcare", None),
    ("Clinical psychologist", "Healthcare", None),
    ("Veterinarian", "Healthcare", None),
    ("Optometrist", "Healthcare", None),
    ("Elderly-care assistant", "Healthcare", None),
    ("Medical laboratory technician", "Healthcare", None),
    ("Orthopedic surgeon", "Healthcare", None),
    ("Occupational therapist", "Healthcare", None),
    ("Speech-and-language therapist", "Healthcare", None),
    # Software & IT
    ("Backend developer", "Software & IT", None),
    ("Frontend developer", "Software & IT", None),
    ("Mobile app developer", "Software & IT", None),
    ("Full-stack developer", "Software & IT", None),
    ("DevOps engineer", "Software & IT", None),
    ("Data scientist", "Software & IT", None),
    ("Data analyst", "Software & IT", None),
    ("Machine-learning engineer", "Software & IT", None),
    ("QA automation tester", "Software & IT", None),
    ("IT support technician", "Software & IT", None),
    ("Systems administrator", "Software & IT", None),
    ("Network engineer", "Software & IT", None),
    ("Cybersecurity analyst", "Software & IT", None),
    ("Database administrator", "Software & IT", None),
    ("Cloud infrastructure engineer", "Software & IT", None),
    ("Embedded-systems engineer", "Software & IT", None),
    ("Video-game programmer", "Software & IT", None),
    ("Technical writer", "Software & IT", None),
    # Engineering
    ("Civil engineer", "Engineering", None),
    ("Structural engineer", "Engineering", None),
    ("Mechanical engineer", "Engineering", None),
    ("Electrical engineer", "Engineering", None),
    ("Chemical process engineer", "Engineering", None),
    ("Industrial designer", "Engineering", None),
    ("CAD draughtsperson", "Engineering", None),
    ("Land surveyor", "Engineering", None),
    ("Quality-control inspector", "Engineering", None),
    ("HVAC engineer", "Engineering", None),
    ("Robotics technician", "Engineering", None),
    ("Biomedical engineer", "Engineering", None),
    ("Environmental consultant", "Engineering", None),
    ("Aerospace maintenance technician", "Engineering", None),
    # Skilled trades
    ("Electrician", "Skilled trades", None),
    ("Plumber", "Skilled trades", None),
    ("Carpenter", "Skilled trades", None),
    ("Welder", "Skilled trades", None),
    ("Auto mechanic", "Skilled trades", None),
    ("Diesel mechanic", "Skilled trades", None),
    ("CNC machinist", "Skilled trades", None),
    ("Bricklayer", "Skilled trades", None),
    ("House painter and decorator", "Skilled trades", None),
    ("Roofer", "Skilled trades", None),
    ("Locksmith", "Skilled trades", None),
    ("Appliance repair technician", "Skilled trades", None),
    ("Elevator installer", "Skilled trades", None),
    ("Glazier", "Skilled trades", None),
    ("Cabinet maker", "Skilled trades", None),
    ("Tiler", "Skilled trades", None),
    # Education
    ("Primary-school teacher", "Education", None),
    ("High-school mathematics teacher", "Education", None),
    ("High-school chemistry teacher", "Education", None),
    ("Special-needs teacher", "Education", None),
    ("University lecturer", "Education", None),
    ("Postdoctoral researcher", "Education", None),
    ("Kindergarten teacher", "Education", None),
    ("Private language tutor", "Education", None),
    ("Vocational trade instructor", "Education", None),
    ("School guidance counsellor", "Education", None),
    # Business & finance
    ("Chartered accountant", "Business & finance", None),
    ("Bookkeeper", "Business & finance", None),
    ("Tax advisor", "Business & finance", None),
    ("External auditor", "Business & finance", None),
    ("Financial analyst", "Business & finance", None),
    ("Bank teller", "Business & finance", None),
    ("Insurance broker", "Business & finance", None),
    ("Mortgage advisor", "Business & finance", None),
    ("HR recruiter", "Business & finance", None),
    ("HR manager", "Business & finance", None),
    ("Office administrator", "Business & finance", None),
    ("Executive assistant", "Business & finance", None),
    ("Project manager", "Business & finance", None),
    ("Management consultant", "Business & finance", None),
    ("Procurement officer", "Business & finance", None),
    ("Payroll clerk", "Business & finance", None),
    # Sales & retail
    ("Retail sales assistant", "Sales & retail", None),
    ("Store manager", "Sales & retail", None),
    ("Supermarket cashier", "Sales & retail", None),
    ("Real-estate agent", "Sales & retail", None),
    ("Car salesperson", "Sales & retail", None),
    ("Pharmaceutical sales rep", "Sales & retail", None),
    ("Call-centre agent", "Sales & retail", None),
    ("Customer-support specialist", "Sales & retail", None),
    ("Bank branch manager", "Sales & retail", None),
    ("Market-stall trader", "Sales & retail", None),
    ("E-commerce shop owner", "Sales & retail", None),
    ("Visual merchandiser", "Sales & retail", None),
    ("Telesales agent", "Sales & retail", None),
    # Hospitality
    ("Line cook", "Hospitality", None),
    ("Pastry chef", "Hospitality", None),
    ("Head chef", "Hospitality", None),
    ("Waiter", "Hospitality", None),
    ("Bartender", "Hospitality", None),
    ("Barista", "Hospitality", None),
    ("Hotel receptionist", "Hospitality", None),
    ("Hotel housekeeper", "Hospitality", None),
    ("Restaurant manager", "Hospitality", None),
    ("Catering coordinator", "Hospitality", None),
    ("Fast-food crew member", "Hospitality", None),
    # Creative & media
    ("Graphic designer", "Creative & media", None),
    ("UX/UI designer", "Creative & media", None),
    ("Freelance illustrator", "Creative & media", None),
    ("Wedding photographer", "Creative & media", None),
    ("Videographer", "Creative & media", None),
    ("Video editor", "Creative & media", None),
    ("Newspaper journalist", "Creative & media", None),
    ("Advertising copywriter", "Creative & media", None),
    ("Social-media content creator", "Creative & media", None),
    ("2D animator", "Creative & media", None),
    ("Architect", "Creative & media", None),
    ("Interior designer", "Creative & media", None),
    ("Fashion designer", "Creative & media", None),
    ("Sound engineer", "Creative & media", None),
    ("Session musician", "Creative & media", None),
    ("Podcast producer", "Creative & media", None),
    # Logistics & transport
    ("Long-haul truck driver", "Logistics & transport", None),
    ("Bicycle courier", "Logistics & transport", None),
    ("City bus driver", "Logistics & transport", None),
    ("Rideshare driver", "Logistics & transport", None),
    ("Warehouse operative", "Logistics & transport", None),
    ("Forklift operator", "Logistics & transport", None),
    ("Logistics coordinator", "Logistics & transport", None),
    ("Supply-chain analyst", "Logistics & transport", None),
    ("Train conductor", "Logistics & transport", None),
    ("Air-traffic controller", "Logistics & transport", None),
    ("Delivery dispatcher", "Logistics & transport", None),
    ("Postal carrier", "Logistics & transport", None),
    # Public & civil service
    ("Police officer", "Public & civil service", None),
    ("Firefighter", "Public & civil service", None),
    ("Army sergeant", "Public & civil service", None),
    ("Border-control officer", "Public & civil service", None),
    ("Municipal civil servant", "Public & civil service", None),
    ("Urban planner", "Public & civil service", None),
    ("Social worker", "Public & civil service", None),
    ("Public librarian", "Public & civil service", None),
    ("Tax inspector", "Public & civil service", None),
    ("Immigration caseworker", "Public & civil service", None),
    ("Court clerk", "Public & civil service", None),
    ("Environmental health officer", "Public & civil service", None),
    # Agriculture & environment (general, NOT region-locked)
    ("Crop farmer", "Agriculture & environment", None),
    ("Livestock farmer", "Agriculture & environment", None),
    ("Dairy farmer", "Agriculture & environment", None),
    ("Agronomist", "Agriculture & environment", None),
    ("Forestry worker", "Agriculture & environment", None),
    ("National-park ranger", "Agriculture & environment", None),
    ("Beekeeper", "Agriculture & environment", None),
    ("Landscape gardener", "Agriculture & environment", None),
    ("Agricultural-machinery operator", "Agriculture & environment", None),
    ("Greenhouse grower", "Agriculture & environment", None),
    # Manufacturing
    ("Factory line worker", "Manufacturing", None),
    ("Machine operator", "Manufacturing", None),
    ("Industrial electrician", "Manufacturing", None),
    ("Food-processing worker", "Manufacturing", None),
    ("Assembly technician", "Manufacturing", None),
    ("Production-line inspector", "Manufacturing", None),
    ("Tool-and-die maker", "Manufacturing", None),
    ("Plant maintenance fitter", "Manufacturing", None),
    ("Packaging operator", "Manufacturing", None),
    # Personal services
    ("Hairdresser", "Personal services", None),
    ("Barber", "Personal services", None),
    ("Beautician", "Personal services", None),
    ("Massage therapist", "Personal services", None),
    ("Personal trainer", "Personal services", None),
    ("Yoga instructor", "Personal services", None),
    ("Childminder", "Personal services", None),
    ("Live-in caregiver", "Personal services", None),
    ("Office cleaner", "Personal services", None),
    ("Funeral director", "Personal services", None),
    ("Bespoke tailor", "Personal services", None),
    ("Dry-cleaning operator", "Personal services", None),
    # Freelance / misc knowledge work
    ("Freelance translator", "Creative & media", None),
    ("Freelance copy-editor", "Creative & media", None),
    ("Bookkeeping freelancer", "Business & finance", None),
    ("Small-business owner", "Sales & retail", None),
    ("Undergraduate student", "Education", None),
    ("Graduate student", "Education", None),
    # ---- Place-bound (physically / economically gated) ----
    ("Commercial fisher", "Maritime", "coastal"),
    ("Aquaculture farm worker", "Maritime", "coastal"),
    ("Merchant-navy sailor", "Maritime", "coastal"),
    ("Scuba-diving instructor", "Maritime", "tropical_coast"),
    ("Mountain guide", "Agriculture & environment", "alpine"),
    ("Ski instructor", "Personal services", "alpine"),
    ("Underground miner", "Extractive", "mining"),
    ("Oil-rig roughneck", "Extractive", "oil_gas"),
    ("Rice-paddy farmer", "Agriculture & environment", "rice"),
    ("Tea-plantation worker", "Agriculture & environment", "plantation"),
    ("Coffee grower", "Agriculture & environment", "plantation"),
    ("Vineyard worker", "Agriculture & environment", "wine"),
    ("Winemaker", "Agriculture & environment", "wine"),
    ("Desert livestock herder", "Agriculture & environment", "arid"),
    ("Garment-factory worker", "Manufacturing", "textile_hub"),
    ("Film-production crew member", "Creative & media", "media_hub"),
    ("Investment banker", "Business & finance", "finance_hub"),
    ("Port crane operator", "Logistics & transport", "port"),
]

# tag -> tokens (country / sub_region / region names) where a gated occupation fits.
GATE_TAGS = {
    "coastal": {
        "Japan", "Philippines", "Indonesia", "Vietnam", "Thailand", "Malaysia",
        "Norway", "Portugal", "Greece", "Spain", "Italy", "Chile", "Peru", "Brazil",
        "Nigeria", "Kenya", "South Africa", "Tanzania", "Senegal", "Australia",
        "New Zealand", "UK", "Ireland", "Morocco", "Turkey", "Sri Lanka",
        "Bangladesh", "Denmark", "Netherlands", "Taiwan", "South Korea", "Mexico",
        "Colombia", "Croatia", "Slovenia", "Montenegro", "Albania", "Bulgaria",
        "Iceland", "Estonia", "Latvia", "Lithuania",
    },
    "tropical_coast": {
        "Philippines", "Indonesia", "Thailand", "Malaysia", "Sri Lanka",
        "Tanzania", "Brazil", "Mexico",
    },
    "alpine": {
        "Switzerland", "Austria", "Nepal", "Valais", "Grisons", "Bern", "Ticino",
        "Tyrol", "Bavaria", "Auvergne-Rhône-Alpes",
    },
    "mining": {
        "South Africa", "Australia", "Chile", "Peru", "Russia", "Kazakhstan",
        "Poland", "China", "India", "Ghana",
    },
    "oil_gas": {
        "Saudi Arabia", "UAE", "Iran", "Russia", "Nigeria", "Kazakhstan", "Norway",
    },
    "rice": {
        "Vietnam", "Thailand", "Indonesia", "India", "Bangladesh", "Philippines",
        "China", "Myanmar", "Sri Lanka", "Mekong Delta", "Isan", "Red River Delta",
    },
    "plantation": {
        "Kenya", "Sri Lanka", "India", "Vietnam", "Indonesia", "Ethiopia",
        "Colombia", "Brazil", "Tanzania",
    },
    "wine": {
        "France", "Italy", "Spain", "Portugal", "Chile", "Argentina",
        "South Africa", "Australia", "Germany", "Greece", "Croatia", "Slovenia",
        "Bulgaria", "Serbia", "North Macedonia", "Luxembourg", "Slovakia",
    },
    "arid": {
        "Saudi Arabia", "UAE", "Egypt", "Morocco", "Iran", "Kazakhstan", "Uzbekistan",
    },
    "textile_hub": {
        "Bangladesh", "Vietnam", "India", "Turkey", "China", "Pakistan", "Indonesia",
    },
    "media_hub": {
        "Maharashtra", "Lagos", "California", "New York", "Metro Manila",
        "Île-de-France",
    },
    "finance_hub": {
        "New York", "Zurich", "Geneva", "UK", "UAE", "Hesse", "Tokyo",
    },
    "port": {
        "Netherlands", "China", "UAE", "Belgium",
    },
}


def allowed_occupations(region, country, sub_region):
    """Return (profession, sector) pairs eligible for this location: all
    ungated professions plus any gated ones whose tag matches the location."""
    out = []
    for profession, sector, gate in OCCUPATIONS:
        if gate is None:
            out.append((profession, sector))
        else:
            tokens = GATE_TAGS.get(gate, set())
            if country in tokens or sub_region in tokens or region in tokens:
                out.append((profession, sector))
    return out


# ---------------------------------------------------------------------------
# Geographic grid: ~200 sub-regions across 13 macro-regions.
# Covers Europe (incl. the Nordics), MENA, North America (incl. Canada), East Asia
# (incl. South Korea), Africa, LATAM, South & SE Asia, Central Asia and Oceania.
# Southern Europe (Italy, Greece + the Balkans) is its own block; Russia sits in
# Central & North Asia. Switzerland keeps full depth.
# ---------------------------------------------------------------------------
GLOBAL_SEEDS = {
    "North America": {
        "USA": ["California", "Texas", "New York", "Florida", "Midwest",
                "Appalachia", "Pacific Northwest", "Deep South"],
        "Canada": ["Ontario", "Quebec", "British Columbia", "Alberta",
                   "Atlantic Canada"],
        "Mexico": ["Mexico City", "Jalisco", "Yucatan", "Nuevo Leon"],
    },
    "LATAM": {
        "Brazil": ["Sao Paulo", "Rio de Janeiro", "Northeast", "Amazonas",
                   "Minas Gerais"],
        "Colombia": ["Bogota", "Antioquia", "Caribbean Coast"],
        "Argentina": ["Buenos Aires", "Cordoba", "Patagonia"],
        "Chile": ["Santiago", "Valparaiso"],
        "Peru": ["Lima", "Cusco"],
        "Guatemala": ["Guatemala City"],
    },
    "Western Europe": {
        "Switzerland": ["Zurich", "Geneva", "Ticino", "Vaud", "Bern", "Valais",
                        "Grisons"],  # full depth
        "Germany": ["Bavaria", "Berlin", "North Rhine-Westphalia", "Hesse"],
        "France": ["Île-de-France", "Provence", "Brittany",
                   "Auvergne-Rhône-Alpes"],
        "Spain": ["Andalusia", "Catalonia", "Madrid"],
        "Portugal": ["Lisbon", "Porto"],
        "Netherlands": ["North Holland", "North Brabant"],
        "Belgium": ["Flanders", "Wallonia"],
        "Austria": ["Vienna", "Tyrol"],
        "Ireland": ["Dublin"],
        "UK": ["London", "Scotland", "Wales", "Northern England"],
        "Luxembourg": ["Luxembourg City"],
    },
    "Southern Europe": {
        "Italy": ["Lombardy", "Lazio", "Sicily", "Veneto"],
        "Greece": ["Attica", "Crete"],
        "Croatia": ["Zagreb", "Dalmatia", "Istria"],
        "Slovenia": ["Ljubljana"],
        "Bosnia & Herzegovina": ["Sarajevo"],
        "Serbia": ["Belgrade", "Vojvodina", "Niš"],
        "Montenegro": ["Podgorica"],
        "North Macedonia": ["Skopje"],
        "Albania": ["Tirana"],
        "Kosovo": ["Pristina"],
        "Bulgaria": ["Sofia", "Plovdiv"],
    },
    "Nordics": {
        "Sweden": ["Stockholm", "Skåne"],
        "Norway": ["Oslo", "Western Norway"],
        "Denmark": ["Copenhagen", "Jutland"],
        "Finland": ["Helsinki", "Lapland"],
        "Iceland": ["Reykjavík"],
    },
    "Eastern Europe": {
        "Poland": ["Masovia", "Silesia", "Lesser Poland"],
        "Czechia": ["Prague", "Moravia"],
        "Slovakia": ["Bratislava", "Košice"],
        "Hungary": ["Budapest", "Great Hungarian Plain"],
        "Romania": ["Bucharest", "Transylvania"],
        "Ukraine": ["Lviv", "Ivano-Frankivsk", "Ternopil", "Kyiv", "Vinnytsia",
                    "Kharkiv", "Dnipro", "Zaporizhzhia", "Odesa"],  # west/central/east gradient
        "Belarus": ["Minsk"],
        "Estonia": ["Tallinn"],
        "Latvia": ["Riga"],
        "Lithuania": ["Vilnius"],
    },
    "MENA": {
        "Turkey": ["Istanbul", "Anatolia", "Aegean Coast"],
        "Egypt": ["Cairo", "Nile Delta"],
        "Morocco": ["Casablanca", "Marrakesh"],
        "Saudi Arabia": ["Riyadh", "Jeddah"],
        "UAE": ["Dubai"],
        "Iran": ["Tehran", "Isfahan"],
        "Israel": ["Tel Aviv"],
        "Lebanon": ["Beirut"],
    },
    "Sub-Saharan Africa": {
        "Nigeria": ["Lagos", "Kano", "Rivers"],
        "Kenya": ["Nairobi", "Rift Valley"],
        "South Africa": ["Johannesburg", "Cape Town", "KwaZulu-Natal"],
        "Ethiopia": ["Addis Ababa", "Oromia"],
        "Ghana": ["Accra", "Ashanti"],
        "Tanzania": ["Dar es Salaam"],
        "Senegal": ["Dakar"],
    },
    "East Asia": {
        "China": ["Guangdong", "Beijing", "Sichuan", "Shanghai", "Yunnan",
                  "Zhejiang"],
        "Japan": ["Tokyo", "Kansai", "Hokkaido", "Kyushu"],
        "South Korea": ["Seoul", "Busan", "Jeolla"],
        "Taiwan": ["Taipei"],
    },
    "South Asia": {
        "India": ["Maharashtra", "Uttar Pradesh", "Tamil Nadu", "West Bengal",
                  "Karnataka", "Punjab"],
        "Pakistan": ["Punjab", "Sindh", "Khyber Pakhtunkhwa"],
        "Bangladesh": ["Dhaka", "Chittagong"],
        "Sri Lanka": ["Colombo"],
        "Nepal": ["Kathmandu"],
    },
    "Southeast Asia": {
        "Vietnam": ["Mekong Delta", "Red River Delta", "Central Highlands"],
        "Thailand": ["Isan", "Central Thailand", "Southern Thailand"],
        "Indonesia": ["Java", "Sumatra", "Sulawesi"],
        "Philippines": ["Metro Manila", "Central Visayas", "Mindanao"],
        "Malaysia": ["Kuala Lumpur", "Sabah"],
        "Myanmar": ["Yangon"],
    },
    "Central & North Asia": {
        "Kazakhstan": ["Almaty"],
        "Uzbekistan": ["Tashkent"],
        "Russia": ["Moscow", "St. Petersburg", "Siberia", "Caucasus", "Tatarstan"],
    },
    "Oceania": {
        "Australia": ["New South Wales", "Queensland", "Western Australia",
                      "Victoria"],
        "New Zealand": ["Auckland", "South Island"],
    },
}


# Region emphasis for the bank: Europe + East/South/Southeast Asia are the
# primary target populations; other regions are represented more lightly.
# Effective personas per location = base coverage x this weight.
REGION_WEIGHTS = {
    "Western Europe": 3,
    "Southern Europe": 2,
    "Nordics": 2,
    "Eastern Europe": 2,
    "East Asia": 3,
    "South Asia": 3,
    "Southeast Asia": 3,
    "North America": 1,
    "LATAM": 1,
    "MENA": 1,
    "Sub-Saharan Africa": 1,
    "Central & North Asia": 1,
    "Oceania": 1,
}


# Seed age instead of letting the model default young. Occupation-aware so it stays
# coherent (students young; everyone else on an older-skewed adult curve). Hard floor 18.
# With ~8% students adding young mass, the non-student weights below land the bank near
# 18-29 ~35% / 30-44 ~32% / 45-59 ~26% / 60-72 ~7% overall (18-29 slightly above 30-44).
def sample_age(occupation):
    occ = (occupation or "").lower()
    if "student" in occ:
        if "undergrad" in occ or "undergraduate" in occ:
            return random.randint(18, 24)
        return random.randint(21, 28)                 # graduate / postgraduate
    lo, hi = random.choices(
        [(22, 29), (30, 44), (45, 59), (60, 72)],
        weights=[29, 35, 28, 8], k=1)[0]
    return random.randint(lo, hi)


# Rule text shared by the joint generation prompt (build_prompt) and the style-extension prompt
# (persona_bank.extend_style).
AGE_COHERENCE_RULE = 'AGE COHERENCE (mandatory, applies to the WHOLE persona): every cultural, technological, and media reference ANYWHERE — reference_pool, linguistic_quirks, example_message, character_description — must belong to the world THIS person\'s age cohort actually grew up in and uses NOW. Someone in their teens/20s/30s references contemporary, currently-live culture (the apps, platforms, creators, games, streamers, music, memes and slang of their own generation and today) — NOT obsolete technology (floppy disks, VHS, cassettes, dial-up, rotary phones, fax machines, typewriters, disk drives), NOT bygone decades or Cold-War / Soviet / "old-country" nostalgia, and NOT their parents\'/grandparents\' world presented as their own. Only genuinely older personas (roughly 50+) carry firsthand older-era references, and only where it fits. Never reach for a dated or nostalgic reference as shorthand for a nationality — that is caricature, not realism. Every reference must also be internally coherent (no mislabelled objects, e.g. calling a smartphone "headphones").'
LANGUAGE_FIELDS_RULE = '- LANGUAGE fields (keep a clean hierarchy — do NOT be verbose): "main_language" = the primary language as a STANDARD canonical name ONLY, with no parentheses, script notes, "variant"/"accent", or region qualifiers (e.g. "German", "French", "Mandarin Chinese", "Romansh", "English", "Ukrainian"). "native_language" is the same language and may append the specific variety only if it matters, but stays short. "dialect" = a CONCISE variant or region label, at most ~4 words, with NO example words, phrases, or sentences (e.g. "Austrian", "Swiss", "Odesa surzhyk", "Galician", "Kansai-ben"), or "Standard" if there is no notable dialect. Never put a description or examples in the dialect field.'


def list_rules(extra):
    """Specificity / no-name / example-language rules (extended grid and style extension)."""
    list_extra = ("\n- SPECIFICITY (applies to hobbies_interests, reference_pool and linguistic_quirks): every "
                  "item must be a short, specific, self-contained phrase grounded in THIS person (their place, age, "
                  "job, life stage, settlement). Do not fall back on interchangeable defaults (e.g. 'urban "
                  "gardening', 'urban exploration', 'digital illustration', 'short-form video trends', 'Spotify', "
                  "'Discord servers') unless they are genuinely central to this person. Never output a field name, "
                  "a placeholder, or a one-word item as a quirk."
                  "\n- NO PERSONAL NAME: character_description refers to the person by role and context only "
                  "(no first or last name); the bank otherwise collapses onto a few stock names per country.")
    # example_message is written in the persona's main language (without this rule, most example messages of
    # non-English personas came out in English)
    _ml = (f'"{extra["home_language"]}"' if extra.get("home_language") else "the main_language you chose")
    list_extra += (f"\n- EXAMPLE LANGUAGE: write example_message in the persona's main language ({_ml}), in the "
                   "script people normally use for it when chatting (code-switched words are fine where "
                   "code_switching_freq allows). Do NOT write it in English unless main_language is English. "
                   "chatbot_language_pref must be consistent with this example.")
    return list_extra


def style_layer_rules(style_extra="", list_extra=""):
    return f"""STYLE layer — exactly how they write.{style_extra}{list_extra}
- "chatting_style": ONE concrete sentence describing how THIS person types in an informal chat — capitalization, punctuation, abbreviations, sentence completeness. Ground it in their age, education, and digital fluency. No generic template, no flowery adjectives. (This is the original free-text description.)
- "chatting_style_structured": the SAME behaviour broken into keys. For each key pick the option that fits (or write a short specific value):
    - capitalization: Standard | all lowercase | first-word-only, no final period | inconsistent | ALL-CAPS for emphasis
    - punctuation: standard | minimal (drops end punctuation) | ellipsis-heavy (...) | excessive (!!!/???) | emoji or line-breaks instead of punctuation
    - emoji_use: none | rare/functional | frequent/decorative | emoticons only ( :) ) | kaomoji/stickers
    - abbreviation_habits: the concrete abbreviations/shortcuts they actually use, or "None"
    - message_structure: terse one-liners | medium, complete sentences | long/elaborate | fragmented across several short lines
    - typo_tendency: clean/proofread | occasional uncorrected typos | phonetic spelling | voice-to-text/autocorrect artifacts
    - greeting_signoff: how they open/close a message, or "None"
  The structured keys MUST be consistent with the free-text "chatting_style" sentence.
- "example_message": a realistic 1-2 sentence VERBATIM example of a casual message this exact persona would send to an AI chat assistant (a question or request they'd actually have). It must READ like something they'd really type — reflecting their chatting_style, quirks, native-language influence, and code-switching. Write the message itself, NOT a description of it, and do NOT make it sound like an AI assistant.
- "chatbot_language_pref": how THIS person would address an AI chatbot. Non-native-English speakers with High/Medium digital fluency often use English for technical/professional tasks (efficiency, vocabulary) but their native language for everyday/personal ones; low-fluency or strongly local personas use their native language throughout. A short phrase, e.g. "English for coding, Ukrainian for everyday" or "always Arabic".
- "reference_pool": 3-6 cultural touchstones this person actually draws on — media, tools, sayings, communities, shared references. EACH must be coherent (no mislabelled objects, e.g. do NOT call a smartphone "headphones") and must fit their AGE COHORT: a person in their teens/20s references the apps, creators, games, music and memes THEY grew up with (2010s-2020s), not their parents'/grandparents' era. Only personas old enough (roughly 50+) carry firsthand older-era references, and only where it genuinely fits. Do NOT default to Soviet / Cold-War / "old country" nostalgia (or any bygone-era cliché) to signal a nationality — that is a lazy anachronistic stereotype; use living, contemporary, locally-current culture instead.
- "linguistic_quirks": 2-4 specific, observable text habits. EACH must be individually earned by this person's profession, personality, and culture. If a quirk would plausibly apply to most people of their region, gender, or education bracket, it is a stereotype — choose something more specific and personal. Aim for variety across personas.
- "character_description": 3-5 sentences on who they are, their work, life context, and outlook. Background facts and personality only — do NOT describe how they type (that belongs in the style layer)."""


def build_prompt(region, country, sub_region, occupation, sector, gender, age,
                 ai_stance, digital_fluency, code_switching_none=False, extra=None, schema_model=None):
    """`extra` (extended grid only) carries the additional seed axes; with extra=None and schema_model=None
    this is the base-grid prompt."""
    schema_json = json_schema(schema_model or Persona)
    seed_extra, style_extra, list_extra = "", "", ""
    job_examples = ('"Electrician" -> "self-employed electrician, solar-panel installs"; "Chartered accountant" -> '
                    '"tax accountant at a mid-size firm, SME clients"; "Backend developer" -> "backend developer, '
                    'payments API at a logistics firm"; "Rideshare driver" -> "part-time ride-hailing driver, '
                    'family-owned compact car"')
    if extra:
        if extra.get("settlement"):
            seed_extra += (f"\n- Settlement type: {extra['settlement']} (where they live within {sub_region}; "
                           "let it shape commute, services, local references and daily life)")
        if extra.get("education_level"):
            seed_extra += (f"\n- Education level: {extra['education_level']} (use EXACTLY this value for "
                           "education.level; choose field_of_study and institution_type consistent with it, "
                           "with the age and with the profession)")
        if extra.get("life_stage"):
            seed_extra += (f"\n- Life stage / household: {extra['life_stage']} (reflect it in character_description, "
                           "hobbies_interests and in what they would ask an AI assistant)")
        if extra.get("home_language"):
            seed_extra += (f"\n- Home language: {extra['home_language']} (main_language MUST be "
                           f"\"{extra['home_language']}\"; native_language, dialect, code-switching, quirks and "
                           "example_message must be consistent with it)")
        if extra.get("job_examples"):
            job_examples = extra["job_examples"] + " (illustrations of the FORMAT only: never reuse these titles)"
        if extra.get("style_seed_block"):
            style_extra = extra["style_seed_block"]
        list_extra = list_rules(extra)

    cs_constraint = ""
    if code_switching_none:
        cs_constraint = (
            "\n- Code-Switching Constraint: None. You MUST set code_switching_freq "
            "to \"None\" and code_switching_type to \"None\". Do NOT insert foreign "
            "loanwords, particles, or code-switching in style rules, quirks, or the "
            "example message."
        )

    _lang_rule = lang_influence_rule(country, sub_region)   # sub-region language/dialect conditioning
    _anti_caricature = (" Any Russian/surzhyk influence is a purely SPOKEN lexical/phonetic dialect feature — "
        "NOT a personality, a political theme, or nostalgia. Do NOT invent Soviet/USSR nostalgia, fondness for "
        "Russian TV/pop-culture, 'de-Russification struggle', Chernobyl/Donbas war-story tropes, or old-Soviet "
        "objects as this person's cultural world. A young Ukrainian references CURRENT Ukrainian culture "
        "(contemporary creators, music, games, apps, memes) — de-Russification is simply the unremarkable default here."
        if country == "Ukraine" else "")
    lang_block = (f"\n- LANGUAGE / DIALECT ({sub_region}): {_lang_rule}{_anti_caricature}" if _lang_rule else "")

    return f"""You are an expert sociologist and character designer. Generate ONE highly realistic persona as a single valid JSON object.

Seed constraints (use EXACTLY these values, do not change them):
- Macro Region: {region}
- Country: {country}
- Sub-region: {sub_region}
- Profession: {occupation} (sector: {sector})
- Gender: {gender}
- Age: {age} (use EXACTLY this age; make occupation seniority, education, and life-stage consistent with it)
- AI Stance: {ai_stance}
- Digital Fluency: {digital_fluency}{cs_constraint}{seed_extra}

Fill every field in the JSON schema below so the whole persona is jointly coherent and culturally accurate.

{AGE_COHERENCE_RULE}

BACKGROUND layer — demographic and cultural facts. Use the exact seeded values above.
- The profession is FIXED as "{occupation}". Do NOT change it and do NOT swap it for whatever industry {country}/{sub_region} is stereotypically famous for. A person from a farming region can be a QA tester; a person from a coastal city can be an accountant. Location shapes their language, culture, and references — not their choice of job.
- "job_title": make "{occupation}" concrete with a SHORT specific title — a sub-specialty and the type of employer (self-employed, small local business, large company, public sector, gig/freelance). Keep it to a brief phrase, **max ~12 words** — NOT a sentence or a paragraph, and do NOT narrate day-to-day tasks here (that belongs in character_description). Detail must come from the WORK, not from regional cliché. **Do NOT name specific real brands, companies, apps, platforms, or vehicle makes/models** — describe them generically instead (e.g. "a ride-hailing app" not "Yandex.Go" or "Uber"; "an older compact sedan" not "2016 Hyundai Accent"; "a large e-commerce firm" not "Amazon"). Naming a real brand risks geographic/factual contradictions (e.g. a service that isn't available in the persona's country). Seniority MUST be consistent with age: do NOT use "Senior"/"Head"/"Lead"/"Chief" or "N years of experience" unless the age plausibly supports it — someone in their 20s is junior/early-career, not a senior overseeing a team. Examples: {job_examples}.{lang_block}
{LANGUAGE_FIELDS_RULE}

{style_layer_rules(style_extra, list_extra)}

Strict JSON schema:
{json.dumps(schema_json, indent=2)}

Output ONLY the JSON object, starting with {{ and ending with }}. No markdown wrappers, no explanations."""


# Schema-constrained ("guided") decoding: force the model to emit a valid Persona
# JSON instance. Fixes malformed JSON (Ministral) and schema-echo / bad enums (GLM);
# built once and reused across all calls.
PERSONA_JSON_SCHEMA = Persona.model_json_schema()


# Per-call bookkeeping: outcome of the LAST generate_joint_persona call, read by main() and written
# to the <output>.attempts.jsonl sidecar (reject cause, token usage, latency). Does not change behaviour.
class _PerThreadDict(threading.local):
    """dict-like and per thread, so concurrent callers (persona_bank.extend_style) do not overwrite each other's
    bookkeeping; single-threaded use behaves like a plain dict."""
    def __init__(self):
        self.d = {}

    def __getattr__(self, name):
        return getattr(self.d, name)

    def __getitem__(self, k):
        return self.d[k]

    def __setitem__(self, k, v):
        self.d[k] = v

    def __iter__(self):
        return iter(self.d)


LAST_ATTEMPT = _PerThreadDict()


def _reject(reason, msg):
    LAST_ATTEMPT["reason"] = reason
    print(f"  -> Rejected: {msg}")
    return None


def generate_joint_persona(client, model_name, region, country, sub_region,
                           occupation, sector, gender, age, ai_stance, digital_fluency,
                           segment="core", temperature=0.8, code_switching_none=False,
                           extra=None, schema_model=None, style_seed_max_mismatch=1, max_tokens=8000,
                           prompt=None, seeded=None):
    """`prompt` and `seeded` are used by persona_bank.extend_style: a ready prompt, and the background fields
    to enforce after generation (instead of the grid seeds passed as positional arguments)."""
    if prompt is None:
        prompt = build_prompt(region, country, sub_region, occupation, sector, gender, age,
                              ai_stance, digital_fluency, code_switching_none,
                              extra=extra, schema_model=schema_model)
    model_cls = schema_model or Persona
    schema_for_call = PERSONA_JSON_SCHEMA if schema_model is None else json_schema(schema_model)
    LAST_ATTEMPT.clear()
    LAST_ATTEMPT.update(reason="ok", t0=time.time())
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_schema",
                             "json_schema": {"name": "persona",
                                             "schema": schema_for_call}},
        )
        LAST_ATTEMPT["t1"] = time.time()
        u = getattr(response, "usage", None)
        if u is not None:
            LAST_ATTEMPT["prompt_tokens"] = getattr(u, "prompt_tokens", None)
            LAST_ATTEMPT["completion_tokens"] = getattr(u, "completion_tokens", None)
        LAST_ATTEMPT["finish_reason"] = getattr(response.choices[0], "finish_reason", None)
        content = response.choices[0].message.content
        if not content:
            reasoning = getattr(response.choices[0].message, "reasoning_content", "")
            content = reasoning.strip() if reasoning else None
            if not content:
                LAST_ATTEMPT["reason"] = "empty_response"
                return None

        # Strip reasoning/thinking blocks that may contain draft braces
        if "</think>" in content:
            content = content.split("</think>")[-1]
        if "```json" in content:
            content = content.split("```json")[-1]
        content = content.replace("```", "").strip()

        start_idx = content.find("{")
        end_idx = content.rfind("}")
        if start_idx == -1 or end_idx == -1:
            return _reject("parse_no_json", "no JSON structure found.")

        try:
            data = json.loads(content[start_idx:end_idx + 1])
        except json.JSONDecodeError as e:
            return _reject("parse_bad_json", f"invalid JSON ({e}).")

        # Reject schema echoes / structurally broken responses
        if "$defs" in data or "properties" in data:
            return _reject("schema_echo", "model returned the schema instead of a persona.")
        if not all(k in data for k in ("background", "style", "character_description")):
            return _reject("schema_missing_keys", f"missing top-level keys, got {list(data.keys())[:6]}")

        data["id"] = str(uuid.uuid4())
        data["generator_model"] = model_name

        # Never let the model change the experimental assignment (seeded fields).
        # job_title is model-generated, so it is intentionally NOT overwritten.
        bg = data["background"]
        if seeded is not None:
            bg.update(seeded)
        else:
            bg["region"] = region
            bg["country"] = country
            bg["sub_region"] = sub_region
            bg["occupation"] = occupation
            bg["sector"] = sector
            bg["gender"] = gender
            bg["ai_stance"] = ai_stance
            bg["digital_fluency"] = digital_fluency
            bg["llm_user_segment"] = segment
        if extra:   # extended grid: the additional seeded axes are enforced like the other seeds
            if extra.get("settlement"):
                bg["settlement_type"] = extra["settlement"]
            if extra.get("life_stage"):
                bg["life_stage"] = extra["life_stage"]
            if extra.get("education_level") and isinstance(bg.get("education"), dict):
                bg["education"]["level"] = extra["education_level"]

        try:
            persona = model_cls(**data)
        except Exception as e:   # pydantic ValidationError (wrong types / missing nested fields)
            return _reject("schema_validation", f"schema validation failed ({type(e).__name__}: {str(e)[:160]}).")
        dumped = persona.model_dump()

        # Fail-fast: reject degenerate personas (missing the style fields the pipeline relies on)
        style = dumped.get("style", {})
        chatting_style = (style.get("chatting_style") or "").strip()
        quirks = style.get("linguistic_quirks") or []
        job_title = (dumped["background"].get("job_title") or "").strip()
        example_message = (style.get("example_message") or "").strip()
        structured = style.get("chatting_style_structured") or {}
        structured_ok = any(
            (structured.get(k) or "").strip()
            for k in ("capitalization", "punctuation", "message_structure")
        )
        if not chatting_style or len(quirks) < 2:
            return _reject("degenerate_style",
                           f"degenerate style (chatting_style={bool(chatting_style)}, quirks={len(quirks)})")
        if not job_title:
            return _reject("empty_job_title", "empty job_title.")
        if not example_message:
            return _reject("empty_example_message", "empty example_message.")
        if not structured_ok:
            return _reject("empty_structured", "empty chatting_style_structured.")

        if extra:   # extended grid: extra quality guards + seed adherence bookkeeping
            from personafactory.persona_bank.style_norm import text_norm, canon_style, canon_language
            ok_quirks = [q for q in quirks if len(text_norm(q).split()) >= 3]
            if len(ok_quirks) < 2:
                return _reject("degenerate_quirks", "degenerate linguistic_quirks (field names / one-word items).")
            dumped["style"]["linguistic_quirks"] = ok_quirks
            for key in ("reference_pool", "hobbies_interests"):
                holder = dumped["style"] if key == "reference_pool" else dumped["background"]
                holder[key] = [x for x in (holder.get(key) or []) if text_norm(x)]
            meta = {}
            if extra.get("style_seed_canon"):
                got = canon_style(structured)
                mism = [k for k, a, b in zip(("capitalization", "punctuation", "emoji_use", "abbreviation_habits",
                                              "message_structure", "typo_tendency", "greeting_signoff"),
                                             got, extra["style_seed_canon"]) if a != b]
                meta["style_seed_mismatch"] = mism
                LAST_ATTEMPT["style_seed_mismatch"] = mism
                if len(mism) > style_seed_max_mismatch:
                    return _reject("style_seed_mismatch", f"typing-style seed not followed ({', '.join(mism)}).")
            if extra.get("home_language"):
                meta["home_language_followed"] = (canon_language(dumped["background"].get("main_language"))
                                                  == canon_language(extra["home_language"]))
            dumped["_seed_meta"] = meta

        return dumped

    except Exception as e:
        LAST_ATTEMPT["reason"] = f"api_error:{type(e).__name__}"
        LAST_ATTEMPT.setdefault("t1", time.time())
        print(f"  -> Error generating persona: {e}")
        return None


def load_existing(path):
    """Resume support: count personas already present per (country, sub_region)
    and collect character_description signatures to skip exact duplicates.
    Keying by (country, sub_region) avoids collisions like India/Punjab vs
    Pakistan/Punjab sharing a quota bucket."""
    counts = collections.Counter()
    seen_desc = set()
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                b = d.get("background", {})
                counts[(b.get("country"), b.get("sub_region"))] += 1
                desc = (d.get("character_description") or "").strip().lower()
                if desc:
                    seen_desc.add(desc)
    return counts, seen_desc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage_per_location", type=int, default=3,
                        help="Base grid: base personas per (country, sub-region) per model, multiplied by the region weight "
                             "(the released bank used 88).")
    parser.add_argument("--model_name", type=str, default="all",
                        help="Specific served model name, or 'all' for the default 3 generators (sequential).")
    parser.add_argument("--base_url", type=str, default=API_BASE_URL,
                        help="OpenAI-compatible base URL for the served model.")
    parser.add_argument("--seed", type=int, default=1337,
                        help="Base RNG seed. Each model in a run is offset by its index for reproducible-but-distinct streams.")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--limit", type=int, default=0,
                        help="Cap personas generated this run per model (0 = no cap). Handy for smoke tests.")
    parser.add_argument("--force_code_switching_none", action="store_true",
                        help="Force code_switching_freq/type to 'None'.")
    parser.add_argument("--shard_count", type=int, default=1,
                        help="Total parallel shards splitting the location grid (client-side concurrency).")
    parser.add_argument("--shard_index", type=int, default=0,
                        help="This shard's index in [0, shard_count). Each shard handles a disjoint subset of sub-regions and writes its own output file.")
    parser.add_argument("--grid", choices=["base", "extended"], default="base",
                        help="Seed grid: base (201 locations, 211 occupations, defined in this file) or extended "
                             "(599 locations, 575 occupations and additional seed axes, grid_extended.py).")
    parser.add_argument("--seed_axes", type=str, default="auto",
                        help="Comma list of additional seed axes for --grid extended: settlement,education,life_stage,"
                             "home_language,style. 'auto' = all five on the extended grid, none on the base grid; "
                             "'none' disables them.")
    parser.add_argument("--style_seed_max_mismatch", type=int, default=1,
                        help="Extended grid: reject (and retry once) when more than this many of the 7 structured "
                             "typing keys do not match the pre-sampled typing-style seed.")
    parser.add_argument("--target_total", type=int, default=0,
                        help="Raw profiles over all generators. Extended grid: per-location targets from the "
                             "per-country quotas (grid_extended.location_generator_targets). Base grid: derive "
                             "--coverage_per_location so that n_generators x weighted grid ~ this many.")
    parser.add_argument("--n_generators", type=int, default=3,
                        help="Number of generator models sharing --target_total.")
    parser.add_argument("--shard_by", choices=["location", "slot"], default="location",
                        help="location (default): each shard owns whole sub-regions (at most #locations useful "
                             "shards). slot: the global slot list (locations in grid order, each repeated by its target) "
                             "is dealt round-robin to shards, so every shard gets a slice of every location; needed for "
                             "more than ~600 shards and for balanced shards in quota mode.")
    parser.add_argument("--max_tokens", type=int, default=0,
                        help="Completion cap per call. 0 = 8000 on the base grid and 4096 on the extended grid "
                             "(valid profiles almost always need fewer than 2,100 tokens; the lower cap stops runaway "
                             "generations early).")
    parser.add_argument("--block_totals", type=str, default="",
                        help="Extended grid: restrict generation to some target blocks with raw totals, e.g. "
                             "'Europe:55000,Southeast_Asia:55000' ('_' for spaces; 'Europe' = the four European "
                             "blocks; grid_extended.block_generator_targets). Locations outside these blocks get 0; "
                             "--target_total must equal the sum.")
    parser.add_argument("--generator_index", type=int, default=-1,
                        help="Extended grid with --target_total: which generator slot of --n_generators this process "
                             "fills (0-based). -1 = position of --model_name in the default order (Gemma 0, "
                             "Ministral 1, GLM 2).")
    parser.add_argument("--output_dir", type=str,
                        default=os.path.join(os.environ.get("PF_DATA_DIR", "./data"), "persona_bank"),
                        help="Directory for the per-model (sharded) bank files.")
    args = parser.parse_args()

    # Self-served OpenAI-compatible endpoints accept any key; set PF_API_KEY if yours needs one.
    api_key = os.environ.get("PF_API_KEY", "EMPTY")

    client = OpenAI(api_key=api_key, base_url=args.base_url)

    # ---- grid selection ----
    GX = None
    if args.grid == "extended":
        from personafactory.persona_bank import grid_extended as GX
        from personafactory.persona_bank.schema import PersonaExtended
    seed_grid = GX.GLOBAL_SEEDS_EXTENDED if GX else GLOBAL_SEEDS
    region_w = GX.REGION_WEIGHTS_EXTENDED if GX else REGION_WEIGHTS

    def loc_scale(country, sr):
        return GX.location_scale(country, sr) if GX else SUBREGION_COVERAGE_SCALE.get(sr, 1.0)

    # extended grid + --target_total: per-location targets from the country-quota scheme (grid_extended)
    quota_mode = bool(GX) and args.target_total > 0
    if args.block_totals:
        bt = sum(int(x.rsplit(":", 1)[1]) for x in args.block_totals.split(","))
        if not quota_mode or bt != args.target_total:
            parser.error(f"--block_totals sums to {bt}; needs --grid extended and --target_total {bt}")
        print(f"block totals: {args.block_totals}")

    gen_order = ["google/gemma-4-31B-it", "mistralai/Ministral-3-14B-Instruct-2512", "zai-org/GLM-4.7-Flash"]
    gen_idx = args.generator_index
    if gen_idx < 0:
        base = {m.split("/")[-1].lower(): i for i, m in enumerate(gen_order)}
        gen_idx = base.get(args.model_name.split("/")[-1].lower(), 0)
    gen_idx = gen_idx % max(1, args.n_generators)

    def loc_target_for(region, country, sr):
        if quota_mode and args.block_totals:   # only the requested target blocks
            return GX.block_generator_targets(args.block_totals, args.n_generators)[(country, sr)][gen_idx]
        if quota_mode:   # integer per-generator split that sums exactly to --target_total
            return GX.location_generator_targets(args.target_total, args.n_generators)[(country, sr)][gen_idx]
        return round(coverage * region_w.get(region, 1) * loc_scale(country, sr))

    axes = set()
    if GX and args.seed_axes == "auto":
        axes = {"settlement", "education", "life_stage", "home_language", "style"}
    elif args.seed_axes not in ("auto", "none", ""):
        axes = {a.strip() for a in args.seed_axes.split(",") if a.strip()}
        if axes and not GX:
            parser.error("--seed_axes requires --grid extended")

    all_locations = [
        (r, c, sr)
        for r, countries in seed_grid.items()
        for c, sub_regions in countries.items()
        for sr in sub_regions
    ]
    if args.target_total > 0 and not GX:
        W = sum(region_w.get(r, 1) * loc_scale(c, sr) for r, c, sr in all_locations)
        args.coverage_per_location = max(1, round(args.target_total / (args.n_generators * W)))
        print(f"target_total {args.target_total}: weighted grid W={W:.1f} -> coverage_per_location "
              f"{args.coverage_per_location} per generator")
    coverage = args.coverage_per_location
    slot_quota = None
    if args.shard_count > 1 and args.shard_by == "slot":
        S, sidx = args.shard_count, args.shard_index

        def _f(n):   # number of x in [0, n) with x % S == sidx
            return max(0, (n - sidx + S - 1) // S)
        slot_quota, j0 = {}, 0
        for (r, c, sr) in all_locations:
            t = loc_target_for(r, c, sr)
            slot_quota[(c, sr)] = _f(j0 + t) - _f(j0)
            j0 += t
        all_locations = [loc for loc in all_locations if slot_quota[(loc[1], loc[2])] > 0]
        print(f"Shard {sidx}/{S} (by slot): {len(all_locations)} sub-regions, {sum(slot_quota.values())} slots "
              f"of {j0}.")
    elif args.shard_count > 1:
        all_locations = [loc for i, loc in enumerate(all_locations)
                         if i % args.shard_count == args.shard_index]
        print(f"Shard {args.shard_index}/{args.shard_count}: {len(all_locations)} sub-regions.")
    if quota_mode:
        print(f"target_total {args.target_total}: country-quota targets (grid_extended.location_quotas), "
              f"split over {args.n_generators} generators; this run fills generator slot {gen_idx}")
    weighted_total = sum(loc_target_for(r, c, sr) for r, c, sr in all_locations)
    print(f"Grid: {len(all_locations)} sub-regions | base coverage {coverage} | "
          f"region-weighted target ~{weighted_total} personas per model.")
    occ_list = GX.OCCUPATIONS_EXTENDED if GX else OCCUPATIONS
    print(f"Occupations: {len(occ_list)} professions "
          f"({sum(1 for _, _, g in occ_list if g is None)} universal, "
          f"{sum(1 for _, _, g in occ_list if g)} gated). Grid: {args.grid}; seed axes: {sorted(axes) or 'none'}")

    models_to_run = DEFAULT_MODELS if args.model_name == "all" else [args.model_name]

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    for model_idx, model_name in enumerate(models_to_run):
        random.seed(args.seed + model_idx)  # reproducible, distinct per model

        clean_name = model_name.split("/")[-1]
        shard_sfx = f".shard{args.shard_index:02d}of{args.shard_count:02d}" if args.shard_count > 1 else ""
        output_file = os.path.join(output_dir, f"persona_bank_{clean_name}{shard_sfx}.jsonl")
        print(f"\n=== Generating with {model_name} -> {output_file} ===")

        counts, seen_desc = load_existing(output_file)
        if sum(counts.values()):
            print(f"  Resume: {sum(counts.values())} personas already present; filling deficit only.")

        # Build the worklist from the REMAINING deficit per location (resume-safe:
        # no overproduction on restart), then shuffle deterministically.
        worklist = []
        for (region, country, sub_region) in all_locations:
            loc_target = (slot_quota[(country, sub_region)] if slot_quota is not None
                          else loc_target_for(region, country, sub_region))
            need = loc_target - counts[(country, sub_region)]
            worklist.extend([(region, country, sub_region)] * max(0, need))
        random.shuffle(worklist)
        if args.limit > 0:
            worklist = worklist[:args.limit]

        total = len(worklist)
        print(f"  To generate this run: {total}")

        successful, failed, dupes = 0, 0, 0
        att_fh = open(output_file[:-len(".jsonl")] + ".attempts.jsonl", "a")   # one row per API call
        with open(output_file, "a") as f:
            for i, (region, country, sub_region) in enumerate(worklist, 1):
                if GX is None:
                    occupation, sector = sample_occupation(region, country, sub_region)   # AI-usage weighted
                    gender = sample_gender(region, country)                                # culture-conditioned
                    age = sample_age(occupation)                                           # seeded, older-skewed, 18+
                    ai_stance = random.choice(AI_STANCES)
                    digital_fluency = sample_fluency(sector)
                else:   # extended grid: same sampling order, extended samplers
                    occupation, sector = GX.sample_occupation_extended(region, country, sub_region)
                    gender = sample_gender(region, country)
                    age = GX.sample_age_extended(occupation)
                    ai_stance = random.choice(AI_STANCES)
                    digital_fluency = GX.sample_fluency_extended(occupation, sector)
                segment = "underrepresented" if digital_fluency == "Low" else "core"
                extra = None
                if GX is not None:
                    extra = {"job_examples": GX.job_title_examples(3)}
                    if "settlement" in axes:
                        extra["settlement"] = GX.sample_settlement(country, sub_region, sector, occupation)
                    if "education" in axes:
                        extra["education_level"] = GX.sample_education_level(occupation, sector, age, region)
                    if "life_stage" in axes:
                        extra["life_stage"] = GX.sample_life_stage(age, occupation, region)
                    if "home_language" in axes:
                        extra["home_language"] = GX.sample_home_language(country, sub_region)
                    if "style" in axes:
                        sseed = GX.sample_style_seed(age, digital_fluency, region)
                        extra["style_seed"] = sseed
                        extra["style_seed_canon"] = GX.style_seed_canonical(sseed)
                        extra["style_seed_block"] = GX.style_seed_block(sseed)

                cs_log = " | CS:None" if args.force_code_switching_none else ""
                print(f"  [{i}/{total}] {country} ({sub_region}) | {occupation} | age {age} | "
                      f"{gender} | {ai_stance} | {digital_fluency}{cs_log}")

                persona = None
                slot_id = str(uuid.uuid4())
                attempts = []
                for attempt in range(2):  # one retry on transient failure
                    persona = generate_joint_persona(
                        client, model_name, region, country, sub_region,
                        occupation, sector, gender, age, ai_stance, digital_fluency,
                        segment=segment,
                        temperature=args.temperature,
                        code_switching_none=args.force_code_switching_none,
                        extra=extra,
                        schema_model=PersonaExtended if GX is not None else None,
                        style_seed_max_mismatch=args.style_seed_max_mismatch,
                        max_tokens=args.max_tokens or (4096 if GX is not None else 8000),
                    )
                    a = dict(LAST_ATTEMPT)
                    a = {"slot": slot_id, "attempt": attempt, "model": model_name, "region": region,
                         "country": country, "sub_region": sub_region, "occupation": occupation,
                         "reason": a.get("reason"), "prompt_tokens": a.get("prompt_tokens"),
                         "completion_tokens": a.get("completion_tokens"), "finish_reason": a.get("finish_reason"),
                         "t0": a.get("t0"), "t1": a.get("t1"), "style_seed_mismatch": a.get("style_seed_mismatch")}
                    attempts.append(a)
                    att_fh.write(json.dumps(a) + "\n")
                    att_fh.flush()
                    if persona:
                        break

                if not persona:
                    failed += 1
                    continue

                desc = (persona.get("character_description") or "").strip().lower()
                if desc and desc in seen_desc:
                    dupes += 1
                    print("  -> Skipped: duplicate character_description.")
                    att_fh.write(json.dumps({"slot": slot_id, "attempt": -1, "model": model_name,
                                             "reason": "dup_description_exact"}) + "\n")
                    continue
                if desc:
                    seen_desc.add(desc)

                persona["gen_meta"] = {
                    "temperature": args.temperature,
                    "seed": args.seed + model_idx,
                    "coverage_target": coverage,
                }
                if quota_mode:   # coverage_per_location is unused in quota mode
                    persona["gen_meta"]["coverage_target"] = (f"quota:{args.target_total}/g{gen_idx}:"
                                                              f"{loc_target_for(region, country, sub_region)}")
                if GX is not None:   # bookkeeping: calls and tokens spent on this profile
                    persona["gen_meta"].update({
                        "attempts": len(attempts),
                        "reject_reasons": [a["reason"] for a in attempts if a["reason"] != "ok"],
                        "prompt_tokens": sum(a["prompt_tokens"] or 0 for a in attempts),
                        "completion_tokens": sum(a["completion_tokens"] or 0 for a in attempts),
                        "t_done": attempts[-1]["t1"],
                    })
                if GX is not None:
                    seed_meta = persona.pop("_seed_meta", {})
                    persona["gen_meta"].update({
                        "grid": GX.GRID_TAG,
                        "seed_axes": {k: extra.get(k) for k in ("settlement", "education_level", "life_stage",
                                                                "home_language", "style_seed") if extra.get(k)},
                        **seed_meta,
                    })
                f.write(json.dumps(persona) + "\n")
                f.flush()
                successful += 1

        att_fh.close()
        print(f"  Done {clean_name}: +{successful} written, {failed} failed, "
              f"{dupes} duplicates skipped -> {output_file}")

    print("\nGeneration complete.")


if __name__ == "__main__":
    main()
