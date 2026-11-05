"""Extended seed grid of the persona bank (used with `generate_bank.py --grid extended`).

The base grid (GLOBAL_SEEDS / OCCUPATIONS / samplers in generate_bank.py) is reused unchanged and
extended: 599 locations in 177 countries (the 201 base locations first), 575 occupations in 23
sectors (the 211 base occupations first), per-country quotas, and five additional seed axes.

Contents
  GLOBAL_SEEDS_EXTENDED, REGION_WEIGHTS_EXTENDED, SUBREGION_COVERAGE_SCALE_EXTENDED   locations + target weights
  HOME_LANGUAGE_SEEDS                                                       sampled home-language seed
  OCCUPATIONS_EXTENDED, GATE_TAGS_EXTENDED, SECTOR_SHARE_EXTENDED                       575 occupations
  sample_occupation_extended, sample_age_extended, sample_fluency_extended              occupation-aware samplers
  sample_education_level, sample_settlement, sample_life_stage              additional seed axes
  country_quotas, location_generator_targets, block_generator_targets       per-location targets
  sample_style_seed                                                         pre-sampled typing style
"""
import copy
import functools
import itertools
import random

from personafactory.persona_bank import generate_bank as _base   # base grid, reused unchanged

# Value of gen_meta.grid in profiles generated on this grid.
GRID_TAG = "extended"

# ===========================================================================
# 1. Locations
# ===========================================================================
# New sub-regions are appended after the base ones, so the 201 base locations keep their
# order. Countries not in the base grid are marked "# new".
_NEW_SUBREGIONS = {
    "North America": {
        "USA": ["New England", "Southwest", "Mountain West", "Hawaii"],  # Puerto Rico: own LATAM entry (below)
        "Canada": ["Prairies", "Nunavut"],
        "Mexico": ["Oaxaca", "Chiapas", "Baja California", "Puebla"],
    },
    "LATAM": {
        "Brazil": ["Rio Grande do Sul", "Parana", "Federal District", "Para", "Bahia"],
        "Colombia": ["Valle del Cauca", "Santander"],
        "Argentina": ["Mendoza", "Tucuman"],
        "Chile": ["Biobio", "Antofagasta"],
        "Peru": ["Arequipa", "Puno", "Loreto"],
        "Guatemala": ["Western Highlands"],
        "Venezuela": ["Caracas", "Zulia"],                                  # new
        "Ecuador": ["Quito", "Guayaquil"],                                  # new
        "Bolivia": ["La Paz", "Santa Cruz", "Cochabamba"],                  # new
        "Paraguay": ["Asuncion", "Eastern Paraguay"],                       # new
        "Uruguay": ["Montevideo"],                                          # new
        "Cuba": ["Havana"],                                                 # new
        "Dominican Republic": ["Santo Domingo"],                            # new
        "Haiti": ["Port-au-Prince"],                                        # new
        "Costa Rica": ["San Jose"],                                         # new
        "Panama": ["Panama City"],                                          # new
        "Honduras": ["Tegucigalpa"],                                        # new
        "El Salvador": ["San Salvador"],                                    # new
        "Jamaica": ["Kingston"],                                            # new
        "Trinidad and Tobago": ["Port of Spain"],                           # new
    },
    "Western Europe": {
        "Switzerland": ["Basel", "Fribourg"],
        "Germany": ["Saxony", "Hamburg", "Baden-Württemberg", "Lower Saxony"],
        "France": ["Alsace", "Occitania", "Hauts-de-France", "Corsica", "Réunion"],
        "Spain": ["Basque Country", "Galicia", "Valencia", "Canary Islands"],
        "Portugal": ["Alentejo", "Madeira"],
        "Netherlands": ["Friesland", "South Holland"],
        "Belgium": ["Brussels"],
        "Austria": ["Styria", "Upper Austria"],
        "Ireland": ["Galway", "Cork"],
        "UK": ["Northern Ireland", "Midlands", "South West England", "Scottish Highlands and Islands"],
    },
    "Southern Europe": {
        "Italy": ["Campania", "Piedmont", "Emilia-Romagna", "Sardinia", "Apulia", "South Tyrol"],
        "Greece": ["Central Macedonia", "Peloponnese"],
        "Slovenia": ["Maribor"],
        "Bosnia & Herzegovina": ["Banja Luka", "Mostar"],
        "North Macedonia": ["Tetovo"],
        "Albania": ["Shkoder", "Vlore"],
        "Kosovo": ["Prizren"],
        "Bulgaria": ["Varna"],
        "Malta": ["Malta"],                                                 # new
        "Cyprus": ["Nicosia", "Limassol"],                                  # new
    },
    "Nordics": {
        "Sweden": ["Gothenburg", "Norrland"],
        "Norway": ["Northern Norway", "Trondelag"],
        "Denmark": ["Funen", "Faroe Islands", "Greenland"],
        "Finland": ["Tampere", "Ostrobothnia"],
        "Iceland": ["Akureyri"],
    },
    "Eastern Europe": {
        "Poland": ["Greater Poland", "Pomerania", "Podlaskie"],
        "Czechia": ["Bohemia"],
        "Slovakia": ["Zilina"],
        "Hungary": ["Southern Transdanubia"],
        "Romania": ["Moldavia", "Banat", "Dobruja"],
        "Ukraine": ["Zakarpattia", "Poltava", "Chernihiv"],
        "Belarus": ["Gomel", "Grodno"],
        "Estonia": ["Tartu", "Ida-Viru"],
        "Latvia": ["Latgale"],
        "Lithuania": ["Kaunas"],
        "Moldova": ["Chisinau", "Gagauzia"],                                # new
    },
    "MENA": {
        "Turkey": ["Southeastern Anatolia", "Black Sea Region", "Ankara"],
        "Egypt": ["Alexandria", "Upper Egypt"],
        "Morocco": ["Rabat", "Souss", "Rif", "Fes"],
        "Saudi Arabia": ["Eastern Province"],
        "UAE": ["Abu Dhabi", "Sharjah"],
        "Iran": ["East Azerbaijan", "Khorasan", "Gilan"],
        "Israel": ["Jerusalem", "Haifa"],
        "Lebanon": ["Tripoli"],
        "Algeria": ["Algiers", "Oran", "Kabylie"],                          # new
        "Tunisia": ["Tunis", "Sfax"],                                       # new
        "Jordan": ["Amman", "Irbid"],                                       # new
        "Iraq": ["Baghdad", "Basra", "Kurdistan Region"],                   # new
        "Kuwait": ["Kuwait City"],                                          # new
        "Qatar": ["Doha"],                                                  # new
        "Oman": ["Muscat"],                                                 # new
        "Bahrain": ["Manama"],                                              # new
    },
    "Sub-Saharan Africa": {
        "Nigeria": ["Oyo", "Enugu", "Abuja", "Kaduna"],
        "Kenya": ["Mombasa", "Kisumu"],
        "South Africa": ["Eastern Cape", "Limpopo", "Free State"],
        "Ethiopia": ["Amhara", "Tigray", "Sidama", "Somali Region"],
        "Ghana": ["Northern Region", "Volta"],
        "Tanzania": ["Arusha", "Zanzibar", "Mwanza"],
        "Senegal": ["Thies", "Casamance"],
        "Uganda": ["Kampala", "Gulu"],                                      # new
        "Rwanda": ["Kigali"],                                               # new
        "DR Congo": ["Kinshasa", "Lubumbashi"],                             # new
        "Cameroon": ["Douala", "Yaounde", "Bamenda"],                       # new
        "Cote d'Ivoire": ["Abidjan"],                                       # new
        "Zimbabwe": ["Harare", "Bulawayo"],                                 # new
        "Zambia": ["Lusaka"],                                               # new
        "Mozambique": ["Maputo"],                                           # new
        "Angola": ["Luanda"],                                               # new
        "Madagascar": ["Antananarivo"],                                     # new
        "Botswana": ["Gaborone"],                                           # new
        "Namibia": ["Windhoek"],                                            # new
        "Mali": ["Bamako"],                                                 # new
        "Burkina Faso": ["Ouagadougou"],                                    # new
        "Benin": ["Cotonou"],                                               # new
        "Malawi": ["Lilongwe"],                                             # new
    },
    "East Asia": {
        "China": ["Hubei", "Shandong", "Liaoning", "Fujian", "Guangxi", "Chongqing", "Jiangsu"],
        "Japan": ["Okinawa", "Tohoku", "Chubu", "Chugoku"],
        "South Korea": ["Gyeonggi", "Daegu", "Jeju"],
        "Taiwan": ["Kaohsiung", "Taichung"],
        "Hong Kong": ["Hong Kong"],                                         # new
        "Mongolia": ["Ulaanbaatar", "Rural Mongolia"],                      # new
    },
    "South Asia": {
        "India": ["Kerala", "Telangana", "Andhra Pradesh", "Gujarat", "Delhi", "Bihar", "Odisha",
                  "Assam", "Rajasthan", "Madhya Pradesh"],
        "Pakistan": ["Balochistan", "Islamabad"],
        "Bangladesh": ["Sylhet", "Rajshahi", "Khulna"],
        "Sri Lanka": ["Jaffna", "Kandy"],
        "Nepal": ["Pokhara", "Madhesh"],
        "Bhutan": ["Thimphu"],                                              # new
        "Maldives": ["Male"],                                               # new
    },
    "Southeast Asia": {
        "Vietnam": ["Hanoi", "Ho Chi Minh City", "Da Nang"],
        "Thailand": ["Northern Thailand"],
        "Indonesia": ["Jakarta", "West Java", "Bali", "Kalimantan", "Nusa Tenggara"],
        "Philippines": ["Ilocos", "Western Visayas", "Calabarzon"],
        "Malaysia": ["Penang", "Sarawak", "Johor", "Kelantan"],
        "Myanmar": ["Mandalay", "Shan State"],
        "Singapore": ["Singapore"],                                         # new
        "Cambodia": ["Phnom Penh", "Siem Reap"],                            # new
        "Laos": ["Vientiane"],                                              # new
        "Timor-Leste": ["Dili"],                                            # new
    },
    "Central & North Asia": {
        "Kazakhstan": ["Astana", "Shymkent"],
        "Uzbekistan": ["Samarkand", "Fergana Valley"],
        "Russia": ["Far East", "Bashkortostan", "Sakha", "Volga", "Urals"],
        "Kyrgyzstan": ["Bishkek", "Osh"],                                   # new
        "Tajikistan": ["Dushanbe"],                                         # new
        "Turkmenistan": ["Ashgabat"],                                       # new
        "Georgia": ["Tbilisi", "Batumi"],                                   # new (Caucasus kept in this block)
        "Armenia": ["Yerevan", "Gyumri"],                                   # new
        "Azerbaijan": ["Baku", "Ganja"],                                    # new
    },
    "Oceania": {
        "Australia": ["South Australia", "Tasmania", "Northern Territory"],
        "New Zealand": ["Wellington", "Northland"],
        "Fiji": ["Suva"],                                                   # new
        "Papua New Guinea": ["Port Moresby"],                               # new
        "Samoa": ["Apia"],                                                  # new
    },
}


# ---------------------------------------------------------------------------
# 1b. Additional Sub-Saharan Africa / Latin America and Caribbean locations (38 more countries and more
# sub-regions). Kept as a separate block for readability; merged into _NEW_SUBREGIONS before the grid is
# built. Every dependent table (home-language seeds, coverage scales, urban shares, city sub-regions,
# gate tags) has a matching "Africa / Latin America" block right after its own definition below.
# ---------------------------------------------------------------------------
_EXT_SUBREGIONS = {
    "Sub-Saharan Africa": {
        # new countries
        "Sudan": ["Khartoum", "Port Sudan", "Gezira"],
        "South Sudan": ["Juba"],
        "Somalia": ["Mogadishu", "Hargeisa", "Garowe"],
        "Niger": ["Niamey", "Zinder", "Agadez"],
        "Chad": ["N'Djamena", "Moundou"],
        "Guinea": ["Conakry", "Labe", "Kankan"],
        "Sierra Leone": ["Freetown", "Bo", "Makeni"],
        "Liberia": ["Monrovia", "Bong County"],
        "Togo": ["Lome", "Kara"],
        "Gabon": ["Libreville"],
        "Republic of the Congo": ["Brazzaville", "Pointe-Noire"],
        "Burundi": ["Bujumbura", "Gitega"],
        "Eritrea": ["Asmara", "Massawa"],
        "Mauritania": ["Nouakchott", "Nouadhibou"],
        "Gambia": ["Greater Banjul", "Upper River Region"],
        "Mauritius": ["Port Louis"],
        "Lesotho": ["Maseru", "Lesotho Highlands"],
        "Eswatini": ["Mbabane", "Manzini"],
        "Cabo Verde": ["Praia", "Mindelo"],
        "Djibouti": ["Djibouti City"],
        "Guinea-Bissau": ["Bissau"],
        "Equatorial Guinea": ["Malabo"],
        "Central African Republic": ["Bangui"],
        "Comoros": ["Moroni"],
        "Seychelles": ["Victoria"],
        "Sao Tome and Principe": ["Sao Tome"],
        # more sub-regions for countries of the block above
        "Senegal": ["Saint-Louis"],
        "Mali": ["Mopti"],
        "Burkina Faso": ["Bobo-Dioulasso"],
        "Cameroon": ["Garoua"],
        "DR Congo": ["Kasai"],
        "Mozambique": ["Nampula", "Beira"],
        "Angola": ["Huambo"],
        "Uganda": ["Mbarara"],
        "Zambia": ["Copperbelt"],
        "Malawi": ["Blantyre"],
        "Madagascar": ["Toamasina"],
    },
    "MENA": {
        "Libya": ["Tripoli", "Benghazi"],
    },
    "LATAM": {
        # new countries / territories
        "Nicaragua": ["Managua", "Leon", "North Caribbean Coast"],
        "Puerto Rico": ["San Juan", "Ponce"],
        "Belize": ["Belize City", "Cayo"],
        "Guyana": ["Georgetown", "Rupununi"],
        "Suriname": ["Paramaribo"],
        "Barbados": ["Bridgetown"],
        "Bahamas": ["Nassau"],
        "Saint Lucia": ["Castries"],
        "Dominica": ["Roseau"],
        "Curacao": ["Willemstad"],
        "Aruba": ["Oranjestad"],
        # more sub-regions where the block above has one or two
        "Venezuela": ["Lara", "Bolivar", "Merida"],
        "Ecuador": ["Cuenca", "Chimborazo", "Manabi"],
        "Cuba": ["Santiago de Cuba", "Camaguey"],
        "Uruguay": ["Salto", "Maldonado"],
        "Dominican Republic": ["Santiago de los Caballeros", "Punta Cana"],
        "Haiti": ["Cap-Haitien", "Les Cayes"],
        "Costa Rica": ["Guanacaste", "Limon"],
        "Panama": ["Chiriqui", "Colon"],
        "Honduras": ["San Pedro Sula", "La Ceiba"],
        "El Salvador": ["Santa Ana", "San Miguel"],
        "Guatemala": ["Alta Verapaz", "Peten", "Huehuetenango"],
        "Jamaica": ["Montego Bay"],
        "Trinidad and Tobago": ["San Fernando"],
        "Chile": ["Araucania"],
        "Colombia": ["Cauca", "La Guajira"],
        "Peru": ["Ayacucho"],
        "Argentina": ["Jujuy"],
        "Bolivia": ["Potosi"],
    },
    "North America": {
        # Mexico sits in North America (as in the base grid); it gets more sub-regions and a LATAM-level weight
        # through SUBREGION_COVERAGE_SCALE_EXTENDED (see below).
        "Mexico": ["Veracruz", "Guerrero", "Sonora", "Michoacan"],
    },
}
EXT_NEW_COUNTRIES = ["Sudan", "South Sudan", "Somalia", "Niger", "Chad", "Guinea", "Sierra Leone", "Liberia",
                     "Togo", "Gabon", "Republic of the Congo", "Burundi", "Eritrea", "Mauritania", "Gambia",
                     "Mauritius", "Lesotho", "Eswatini", "Cabo Verde", "Djibouti", "Guinea-Bissau",
                     "Equatorial Guinea", "Central African Republic", "Comoros", "Seychelles",
                     "Sao Tome and Principe", "Libya", "Nicaragua", "Puerto Rico", "Belize", "Guyana", "Suriname",
                     "Barbados", "Bahamas", "Saint Lucia", "Dominica", "Curacao", "Aruba"]
for _r, _cs in _EXT_SUBREGIONS.items():
    for _c, _ss in _cs.items():
        _NEW_SUBREGIONS.setdefault(_r, {}).setdefault(_c, [])
        _NEW_SUBREGIONS[_r][_c] += [x for x in _ss if x not in _NEW_SUBREGIONS[_r][_c]]


def _merge_grid():
    g = copy.deepcopy(_base.GLOBAL_SEEDS)
    for region, countries in _NEW_SUBREGIONS.items():
        for country, subs in countries.items():
            cur = g[region].setdefault(country, [])
            for s in subs:
                if s not in cur:
                    cur.append(s)
    return g


GLOBAL_SEEDS_EXTENDED = _merge_grid()

# Region emphasis (used only without --target_total). Europe and East/South/Southeast Asia stay primary,
# but the thin regions get more weight per location than in the base grid (where they have 1), so their
# share grows both through more locations and through a higher weight. Effective per-location target =
# coverage x region weight x sub-region scale (same formula as the base grid).
REGION_WEIGHTS_EXTENDED = {
    "Western Europe": 2.5,
    "Southern Europe": 2,
    "Nordics": 2,
    "Eastern Europe": 2,
    "East Asia": 3,
    "South Asia": 3,
    "Southeast Asia": 3,
    "North America": 1.25,
    "LATAM": 2.0,
    "MENA": 1.5,
    "Sub-Saharan Africa": 2.25,
    "Central & North Asia": 1.5,
    "Oceania": 1.25,
}

# Per-sub-region scale: keeps large multi-sub-region countries from dominating after the expansion.
SUBREGION_COVERAGE_SCALE_EXTENDED = {}
SUBREGION_COVERAGE_SCALE_EXTENDED.update({("Ukraine", s): 1 / 3 for s in GLOBAL_SEEDS_EXTENDED["Eastern Europe"]["Ukraine"]})
SUBREGION_COVERAGE_SCALE_EXTENDED.update({("Switzerland", s): 0.8 for s in GLOBAL_SEEDS_EXTENDED["Western Europe"]["Switzerland"]})
SUBREGION_COVERAGE_SCALE_EXTENDED.update({("India", s): 0.6 for s in GLOBAL_SEEDS_EXTENDED["South Asia"]["India"]})
SUBREGION_COVERAGE_SCALE_EXTENDED.update({("China", s): 0.6 for s in GLOBAL_SEEDS_EXTENDED["East Asia"]["China"]})
SUBREGION_COVERAGE_SCALE_EXTENDED.update({("USA", s): 0.8 for s in GLOBAL_SEEDS_EXTENDED["North America"]["USA"]})
SUBREGION_COVERAGE_SCALE_EXTENDED.update({("Russia", s): 0.8 for s in GLOBAL_SEEDS_EXTENDED["Central & North Asia"]["Russia"]})
SUBREGION_COVERAGE_SCALE_EXTENDED.update({("Indonesia", s): 0.8 for s in GLOBAL_SEEDS_EXTENDED["Southeast Asia"]["Indonesia"]})
# small populations / very small language communities: half weight
for _k in [("Denmark", "Faroe Islands"), ("Denmark", "Greenland"), ("Canada", "Nunavut"), ("Samoa", "Apia"),
           ("Maldives", "Male"), ("Bhutan", "Thimphu"), ("Timor-Leste", "Dili"), ("Bahrain", "Manama"),
           ("Iceland", "Akureyri"), ("Moldova", "Gagauzia"), ("Fiji", "Suva")]:
    SUBREGION_COVERAGE_SCALE_EXTENDED[_k] = 0.5


# Africa / Latin America: Mexico (filed under North America) gets the LATAM weight (2.0 / 1.25 = 1.6);
# very small states get half weight, small ones 0.75.
SUBREGION_COVERAGE_SCALE_EXTENDED.update({("Mexico", s): 1.6 for s in GLOBAL_SEEDS_EXTENDED["North America"]["Mexico"]})
for _k in [("Cabo Verde", "Praia"), ("Cabo Verde", "Mindelo"), ("Comoros", "Moroni"), ("Seychelles", "Victoria"),
           ("Sao Tome and Principe", "Sao Tome"), ("Djibouti", "Djibouti City"), ("Barbados", "Bridgetown"),
           ("Bahamas", "Nassau"), ("Saint Lucia", "Castries"), ("Dominica", "Roseau"), ("Curacao", "Willemstad"),
           ("Aruba", "Oranjestad"), ("Belize", "Cayo"), ("Guyana", "Rupununi"), ("Lesotho", "Lesotho Highlands"),
           ("Equatorial Guinea", "Malabo"), ("Mauritius", "Port Louis")]:
    SUBREGION_COVERAGE_SCALE_EXTENDED[_k] = 0.5
for _k in [("Belize", "Belize City"), ("Guyana", "Georgetown"), ("Suriname", "Paramaribo"), ("Gambia", "Greater Banjul"),
           ("Gambia", "Upper River Region"), ("Eswatini", "Mbabane"), ("Eswatini", "Manzini"), ("Lesotho", "Maseru"),
           ("Gabon", "Libreville"), ("Guinea-Bissau", "Bissau"), ("Trinidad and Tobago", "San Fernando")]:
    SUBREGION_COVERAGE_SCALE_EXTENDED[_k] = 0.75


def location_scale(country, sub_region):
    return SUBREGION_COVERAGE_SCALE_EXTENDED.get((country, sub_region), 1.0)



# ---------------------------------------------------------------------------
# 1c. Explicit target shares with per-country quotas
# ---------------------------------------------------------------------------
# Region weights cannot express "Sub-Saharan Africa ~17%", per-country floors or a per-country cap,
# so with `generate_bank.py --grid extended --target_total N` the per-location targets come from quotas:
#   1. each target block gets TARGET_BLOCK_SHARE x N (blocks = macro-regions, except that Mexico,
#      filed under North America, is counted in "Latin America & Caribbean");
#   2. inside a block the total is split across countries in proportion to sqrt(population) x
#      COUNTRY_EMPHASIS, with a floor per country (COUNTRY_FLOOR, default 800) and a global cap of
#      COUNTRY_CAP_SHARE x N, solved by water-filling (fixed floors / caps, re-split the rest);
#   3. a country quota is split across its sub-regions in proportion to location_scale().
# The stored `background.region` is unchanged (Mexico stays "North America").
TARGET_BLOCK_SHARE = {
    "Sub-Saharan Africa": 17.0, "MENA": 8.5, "Latin America & Caribbean": 12.0, "North America": 4.0,
    "Western Europe": 9.5, "Southern Europe": 6.5, "Eastern Europe": 6.5, "Nordics": 3.0,
    "East Asia": 8.5, "South Asia": 8.5, "Southeast Asia": 10.5, "Central & North Asia": 3.5, "Oceania": 2.0,
}
BLOCK_OVERRIDE = {"Mexico": "Latin America & Caribbean"}


def target_block(region, country):
    if country in BLOCK_OVERRIDE:
        return BLOCK_OVERRIDE[country]
    return "Latin America & Caribbean" if region == "LATAM" else region


# Approximate 2024 population in millions (UN WPP / World Bank, rounded); only the square root is used.
POPULATION_M = {
    "USA": 340, "Canada": 40, "Mexico": 130,
    "Brazil": 212, "Colombia": 53, "Argentina": 46, "Chile": 20, "Peru": 34, "Guatemala": 18, "Venezuela": 28,
    "Ecuador": 18, "Bolivia": 12.4, "Paraguay": 6.9, "Uruguay": 3.4, "Cuba": 11, "Dominican Republic": 11.4,
    "Haiti": 11.8, "Costa Rica": 5.2, "Panama": 4.5, "Honduras": 10.6, "El Salvador": 6.3, "Jamaica": 2.8,
    "Trinidad and Tobago": 1.5, "Nicaragua": 7.0, "Puerto Rico": 3.2, "Belize": 0.41, "Guyana": 0.83,
    "Suriname": 0.63, "Barbados": 0.28, "Bahamas": 0.41, "Saint Lucia": 0.18, "Dominica": 0.07,
    "Curacao": 0.15, "Aruba": 0.11,
    "Switzerland": 9.0, "Germany": 84, "France": 68, "Spain": 48, "Portugal": 10.6, "Netherlands": 18,
    "Belgium": 11.8, "Austria": 9.1, "Ireland": 5.3, "UK": 69, "Luxembourg": 0.67,
    "Italy": 59, "Greece": 10.4, "Croatia": 3.9, "Slovenia": 2.1, "Bosnia & Herzegovina": 3.2, "Serbia": 6.6,
    "Montenegro": 0.62, "North Macedonia": 1.8, "Albania": 2.7, "Kosovo": 1.6, "Bulgaria": 6.4, "Malta": 0.54,
    "Cyprus": 1.3,
    "Sweden": 10.6, "Norway": 5.6, "Denmark": 6.0, "Finland": 5.6, "Iceland": 0.39,
    "Poland": 37, "Czechia": 10.9, "Slovakia": 5.4, "Hungary": 9.6, "Romania": 19, "Ukraine": 37, "Belarus": 9.1,
    "Estonia": 1.4, "Latvia": 1.9, "Lithuania": 2.9, "Moldova": 2.4,
    "Turkey": 86, "Egypt": 114, "Morocco": 38, "Saudi Arabia": 33, "UAE": 10, "Iran": 90, "Israel": 9.9,
    "Lebanon": 5.8, "Algeria": 46, "Tunisia": 12.3, "Jordan": 11.5, "Iraq": 46, "Kuwait": 4.9, "Qatar": 2.7,
    "Oman": 5.3, "Bahrain": 1.6, "Libya": 7.4,
    "Nigeria": 230, "Kenya": 56, "South Africa": 63, "Ethiopia": 130, "Ghana": 34, "Tanzania": 68, "Senegal": 18.5,
    "Uganda": 50, "Rwanda": 14, "DR Congo": 109, "Cameroon": 29, "Cote d'Ivoire": 31.9, "Zimbabwe": 16.6,
    "Zambia": 21, "Mozambique": 34.6, "Angola": 37.9, "Madagascar": 31.9, "Botswana": 2.5, "Namibia": 3.0,
    "Mali": 24, "Burkina Faso": 23.5, "Benin": 14.5, "Malawi": 21.6, "Sudan": 50, "South Sudan": 11.9,
    "Somalia": 19, "Niger": 27, "Chad": 20, "Guinea": 14.8, "Sierra Leone": 8.6, "Liberia": 5.6, "Togo": 9.5,
    "Gabon": 2.5, "Republic of the Congo": 6.3, "Burundi": 14, "Eritrea": 3.7, "Mauritania": 5.2, "Gambia": 2.8,
    "Mauritius": 1.27, "Lesotho": 2.3, "Eswatini": 1.2, "Cabo Verde": 0.52, "Djibouti": 1.15,
    "Guinea-Bissau": 2.2, "Equatorial Guinea": 1.9, "Central African Republic": 5.9, "Comoros": 0.87,
    "Seychelles": 0.13, "Sao Tome and Principe": 0.23,
    "China": 1410, "Japan": 124, "South Korea": 51.7, "Taiwan": 23.4, "Hong Kong": 7.5, "Mongolia": 3.5,
    "India": 1440, "Pakistan": 245, "Bangladesh": 173, "Sri Lanka": 22, "Nepal": 30, "Bhutan": 0.79,
    "Maldives": 0.52,
    "Vietnam": 101, "Thailand": 72, "Indonesia": 281, "Philippines": 116, "Malaysia": 35, "Myanmar": 54,
    "Singapore": 5.9, "Cambodia": 17.6, "Laos": 7.7, "Timor-Leste": 1.4,
    "Kazakhstan": 20.6, "Uzbekistan": 36.4, "Russia": 144, "Kyrgyzstan": 7.2, "Tajikistan": 10.6,
    "Turkmenistan": 7.4, "Georgia": 3.7, "Armenia": 3.0, "Azerbaijan": 10.2,
    "Australia": 27, "New Zealand": 5.3, "Fiji": 0.93, "Papua New Guinea": 10.3, "Samoa": 0.22,
}
# Deliberate emphasis on top of sqrt(population): Switzerland stays a focus country (as in the base grid).
COUNTRY_EMPHASIS = {"Switzerland": 2.0}
COUNTRY_FLOOR_DEFAULT = 800
COUNTRY_FLOOR = {   # populous countries get a higher floor than the default
    "Nigeria": 10000, "Ethiopia": 7000, "DR Congo": 6500, "Egypt": 7000, "Tanzania": 5000, "Kenya": 5000,
    "Sudan": 4000, "South Africa": 5000, "Uganda": 4000, "Brazil": 12000, "Mexico": 12000, "Colombia": 6000,
}
COUNTRY_CAP_SHARE = 0.04
# The floors above are absolute numbers calibrated for a total of FLOOR_REF_TOTAL; for any other total
# they are scaled by total / FLOOR_REF_TOTAL, so small runs reproduce the same shares.
FLOOR_REF_TOTAL = 580000


def _country_regions():
    out = {}
    for r, cs in GLOBAL_SEEDS_EXTENDED.items():
        for c in cs:
            out[c] = r
    return out


@functools.lru_cache(maxsize=None)
def country_quotas(total):
    """Raw profiles per country (all generators together) for a total of `total`."""
    reg = _country_regions()
    blocks = {}
    for c, r in reg.items():
        blocks.setdefault(target_block(r, c), []).append(c)
    assert abs(sum(TARGET_BLOCK_SHARE.values()) - 100) < 1e-6, "block shares must sum to 100"
    cap = COUNTRY_CAP_SHARE * total
    quotas = {}
    for b, cs in blocks.items():
        remaining = TARGET_BLOCK_SHARE[b] / 100 * total
        free = list(cs)
        w = {c: (POPULATION_M[c] ** 0.5) * COUNTRY_EMPHASIS.get(c, 1.0) for c in cs}
        fixed = {}
        while True:
            sw = sum(w[c] for c in free)
            alloc = {c: remaining * w[c] / sw for c in free}
            newly = {}
            for c in free:
                floor = COUNTRY_FLOOR.get(c, COUNTRY_FLOOR_DEFAULT) * total / FLOOR_REF_TOTAL
                if alloc[c] < floor:
                    newly[c] = floor
                elif alloc[c] > cap:
                    newly[c] = cap
            if not newly:
                fixed.update(alloc)
                break
            for c, v in newly.items():
                fixed[c] = v
                remaining -= v
                free.remove(c)
            if not free:
                break
        quotas.update(fixed)
    return {c: int(round(v)) for c, v in quotas.items()}


@functools.lru_cache(maxsize=None)
def location_quotas(total):
    """Raw profiles per (country, sub_region) (all generators together)."""
    cq = country_quotas(total)
    out = {}
    for r, cs in GLOBAL_SEEDS_EXTENDED.items():
        for c, subs in cs.items():
            ws = [location_scale(c, s) for s in subs]
            for s, w in zip(subs, ws):
                out[(c, s)] = cq[c] * w / sum(ws)
    return out


@functools.lru_cache(maxsize=None)
def location_generator_targets(total, n_gen):
    """Integer raw targets per (country, sub_region) and generator: {(c, s): [t_0, ..., t_{n_gen-1}]}.

    Location totals are rounded by largest remainder so they sum exactly to `total` (per-location
    round(q / n_gen) loses or adds mass when q is small, e.g. in a small test run); each location's total is
    then split across the generators as evenly as possible, with the leftover units rotated over the
    generators by location index so every generator gets about total / n_gen."""
    lq = location_quotas(total)
    keys = list(lq)
    base = {k: int(lq[k]) for k in keys}
    rest = int(round(total)) - sum(base.values())
    for k in sorted(keys, key=lambda k: (-(lq[k] - base[k]), keys.index(k)))[:max(0, rest)]:
        base[k] += 1
    out, rot = {}, 0
    for k in keys:
        n = base[k]
        t = [n // n_gen] * n_gen
        for j in range(n % n_gen):
            t[(rot + j) % n_gen] += 1
        rot = (rot + n % n_gen) % n_gen
        out[k] = t
    return out


# Raw targets for a subset of target blocks only (generate_bank.py --block_totals). Inside each block the split
# over countries and sub-regions follows the quotas at FLOOR_REF_TOTAL (location_quotas), rescaled to the
# requested block total. "Europe" expands to the four European blocks in proportion to TARGET_BLOCK_SHARE.
BLOCK_GROUPS = {"Europe": ("Western Europe", "Southern Europe", "Eastern Europe", "Nordics")}


@functools.lru_cache(maxsize=None)
def block_generator_targets(block_totals, n_gen):
    """block_totals: "Europe:55000,Southeast Asia:55000" -> {(c, s): [t_0, ..., t_{n_gen-1}]} (0 outside)."""
    want = {}
    for part in block_totals.split(","):
        name, n = part.rsplit(":", 1)
        name, n = name.strip().replace("_", " "), int(n)   # "_" for spaces (shell-safe)
        members = BLOCK_GROUPS.get(name, (name,))
        assert all(m in TARGET_BLOCK_SHARE for m in members), f"unknown block {name}"
        tot = sum(TARGET_BLOCK_SHARE[m] for m in members)
        for m in members:
            want[m] = want.get(m, 0) + n * TARGET_BLOCK_SHARE[m] / tot
    reg = _country_regions()
    lq = location_quotas(FLOOR_REF_TOTAL)
    keys = list(lq)
    blk = {k: target_block(reg[k[0]], k[0]) for k in keys}
    bsum = {}
    for k in keys:
        bsum[blk[k]] = bsum.get(blk[k], 0) + lq[k]
    q = {k: (lq[k] * want[blk[k]] / bsum[blk[k]] if blk[k] in want else 0.0) for k in keys}
    base = {k: int(q[k]) for k in keys}
    rest = int(round(sum(want.values()))) - sum(base.values())
    for k in sorted(keys, key=lambda k: (-(q[k] - base[k]), keys.index(k)))[:max(0, rest)]:
        base[k] += 1
    out, rot = {}, 0
    for k in keys:
        n = base[k]
        t = [n // n_gen] * n_gen
        for j in range(n % n_gen):
            t[(rot + j) % n_gen] += 1
        rot = (rot + n % n_gen) % n_gen
        out[k] = t
    return out


def all_locations_extended():
    return [(r, c, s) for r, cs in GLOBAL_SEEDS_EXTENDED.items() for c, ss in cs.items() for s in ss]


# Home-language seed: for multilingual locations the generator is told which language this person
# mainly uses (sampled), so the bank covers regional languages instead of collapsing to English or the
# national language (on the base grid, English is the main_language of 99.6% of South African, 98.7% of
# Nigerian, 99.2% of Ghanaian and 91% of Kenyan profiles). Locations not listed get no language seed (the
# model picks the language, as on the base grid).
HOME_LANGUAGE_SEEDS = {
    # Sub-Saharan Africa
    ("Nigeria", "Lagos"): [("Yoruba", .35), ("English", .35), ("Nigerian Pidgin", .2), ("Igbo", .1)],
    ("Nigeria", "Kano"): [("Hausa", .65), ("English", .2), ("Nigerian Pidgin", .15)],
    ("Nigeria", "Rivers"): [("English", .4), ("Nigerian Pidgin", .35), ("Igbo", .15), ("Ijaw", .1)],
    ("Nigeria", "Oyo"): [("Yoruba", .65), ("English", .35)],
    ("Nigeria", "Enugu"): [("Igbo", .65), ("English", .35)],
    ("Nigeria", "Abuja"): [("English", .5), ("Hausa", .2), ("Nigerian Pidgin", .15), ("Yoruba", .075), ("Igbo", .075)],
    ("Nigeria", "Kaduna"): [("Hausa", .6), ("English", .4)],
    ("Kenya", "Nairobi"): [("Swahili", .45), ("English", .4), ("Sheng", .15)],
    ("Kenya", "Rift Valley"): [("Swahili", .45), ("Kalenjin", .3), ("English", .25)],
    ("Kenya", "Mombasa"): [("Swahili", .75), ("English", .25)],
    ("Kenya", "Kisumu"): [("Luo", .4), ("Swahili", .35), ("English", .25)],
    ("South Africa", "Johannesburg"): [("English", .3), ("Zulu", .3), ("Sesotho", .15), ("Afrikaans", .1), ("Setswana", .15)],
    ("South Africa", "Cape Town"): [("Afrikaans", .4), ("English", .35), ("Xhosa", .25)],
    ("South Africa", "KwaZulu-Natal"): [("Zulu", .7), ("English", .3)],
    ("South Africa", "Eastern Cape"): [("Xhosa", .75), ("English", .15), ("Afrikaans", .1)],
    ("South Africa", "Limpopo"): [("Sepedi", .5), ("Tshivenda", .2), ("Xitsonga", .2), ("English", .1)],
    ("South Africa", "Free State"): [("Sesotho", .65), ("Afrikaans", .2), ("English", .15)],
    ("Ghana", "Accra"): [("Twi", .4), ("English", .4), ("Ga", .2)],
    ("Ghana", "Ashanti"): [("Twi", .7), ("English", .3)],
    ("Ghana", "Northern Region"): [("Dagbani", .6), ("English", .4)],
    ("Ghana", "Volta"): [("Ewe", .7), ("English", .3)],
    ("Ethiopia", "Addis Ababa"): [("Amharic", .75), ("English", .1), ("Oromo", .15)],
    ("Ethiopia", "Oromia"): [("Oromo", .8), ("Amharic", .2)],
    ("Ethiopia", "Amhara"): [("Amharic", 1.0)],
    ("Ethiopia", "Tigray"): [("Tigrinya", 1.0)],
    ("Ethiopia", "Sidama"): [("Sidamo", .6), ("Amharic", .4)],
    ("Ethiopia", "Somali Region"): [("Somali", .9), ("Amharic", .1)],
    ("Tanzania", "Dar es Salaam"): [("Swahili", .85), ("English", .15)],
    ("Tanzania", "Arusha"): [("Swahili", .9), ("English", .1)],
    ("Tanzania", "Zanzibar"): [("Swahili", 1.0)],
    ("Tanzania", "Mwanza"): [("Swahili", .7), ("Sukuma", .3)],
    ("Senegal", "Dakar"): [("Wolof", .65), ("French", .35)],
    ("Senegal", "Thies"): [("Wolof", .7), ("French", .3)],
    ("Senegal", "Casamance"): [("Jola", .4), ("French", .3), ("Wolof", .3)],
    ("Uganda", "Kampala"): [("Luganda", .55), ("English", .45)],
    ("Uganda", "Gulu"): [("Acholi", .65), ("English", .35)],
    ("Rwanda", "Kigali"): [("Kinyarwanda", .75), ("English", .15), ("French", .1)],
    ("DR Congo", "Kinshasa"): [("Lingala", .6), ("French", .4)],
    ("DR Congo", "Lubumbashi"): [("Swahili", .6), ("French", .4)],
    ("Cameroon", "Douala"): [("French", .7), ("Cameroonian Pidgin", .2), ("Duala", .1)],
    ("Cameroon", "Yaounde"): [("French", .8), ("Ewondo", .2)],
    ("Cameroon", "Bamenda"): [("English", .5), ("Cameroonian Pidgin", .5)],
    ("Cote d'Ivoire", "Abidjan"): [("French", .8), ("Dyula", .2)],
    ("Zimbabwe", "Harare"): [("Shona", .65), ("English", .35)],
    ("Zimbabwe", "Bulawayo"): [("Ndebele", .65), ("English", .35)],
    ("Zambia", "Lusaka"): [("Nyanja", .45), ("Bemba", .25), ("English", .3)],
    ("Mozambique", "Maputo"): [("Portuguese", .7), ("Changana", .3)],
    ("Angola", "Luanda"): [("Portuguese", .9), ("Kimbundu", .1)],
    ("Madagascar", "Antananarivo"): [("Malagasy", .8), ("French", .2)],
    ("Botswana", "Gaborone"): [("Setswana", .65), ("English", .35)],
    ("Namibia", "Windhoek"): [("Oshiwambo", .35), ("Afrikaans", .25), ("English", .3), ("Damara/Nama", .1)],
    ("Mali", "Bamako"): [("Bambara", .75), ("French", .25)],
    ("Burkina Faso", "Ouagadougou"): [("Moore", .6), ("French", .4)],
    ("Benin", "Cotonou"): [("Fon", .55), ("French", .45)],
    ("Malawi", "Lilongwe"): [("Chichewa", .75), ("English", .25)],
    # South Asia
    ("India", "Maharashtra"): [("Marathi", .45), ("Hindi", .3), ("English", .25)],
    ("India", "Uttar Pradesh"): [("Hindi", .75), ("Bhojpuri", .1), ("Urdu", .1), ("English", .05)],
    ("India", "Tamil Nadu"): [("Tamil", .8), ("English", .2)],
    ("India", "West Bengal"): [("Bengali", .8), ("English", .1), ("Hindi", .1)],
    ("India", "Karnataka"): [("Kannada", .55), ("English", .3), ("Hindi", .15)],
    ("India", "Punjab"): [("Punjabi", .8), ("Hindi", .15), ("English", .05)],
    ("India", "Kerala"): [("Malayalam", .85), ("English", .15)],
    ("India", "Telangana"): [("Telugu", .65), ("Urdu", .15), ("English", .2)],
    ("India", "Andhra Pradesh"): [("Telugu", .9), ("English", .1)],
    ("India", "Gujarat"): [("Gujarati", .85), ("Hindi", .1), ("English", .05)],
    ("India", "Delhi"): [("Hindi", .65), ("English", .25), ("Punjabi", .1)],
    ("India", "Bihar"): [("Hindi", .5), ("Bhojpuri", .25), ("Maithili", .25)],
    ("India", "Odisha"): [("Odia", .85), ("Hindi", .1), ("English", .05)],
    ("India", "Assam"): [("Assamese", .75), ("Bengali", .15), ("English", .1)],
    ("India", "Rajasthan"): [("Hindi", .6), ("Rajasthani", .4)],
    ("India", "Madhya Pradesh"): [("Hindi", 1.0)],
    ("Pakistan", "Punjab"): [("Punjabi", .5), ("Urdu", .4), ("English", .1)],
    ("Pakistan", "Sindh"): [("Sindhi", .45), ("Urdu", .45), ("English", .1)],
    ("Pakistan", "Khyber Pakhtunkhwa"): [("Pashto", .75), ("Urdu", .25)],
    ("Pakistan", "Balochistan"): [("Balochi", .45), ("Pashto", .3), ("Urdu", .25)],
    ("Pakistan", "Islamabad"): [("Urdu", .6), ("English", .3), ("Punjabi", .1)],
    ("Bangladesh", "Sylhet"): [("Bengali", .55), ("Sylheti", .45)],
    ("Bangladesh", "Chittagong"): [("Bengali", .6), ("Chittagonian", .4)],
    ("Sri Lanka", "Colombo"): [("Sinhala", .55), ("Tamil", .2), ("English", .25)],
    ("Sri Lanka", "Jaffna"): [("Tamil", 1.0)],
    ("Sri Lanka", "Kandy"): [("Sinhala", .8), ("Tamil", .2)],
    ("Nepal", "Madhesh"): [("Maithili", .55), ("Bhojpuri", .2), ("Nepali", .25)],
    ("Nepal", "Kathmandu"): [("Nepali", .8), ("Newari", .2)],
    ("Bhutan", "Thimphu"): [("Dzongkha", .7), ("English", .3)],
    ("Maldives", "Male"): [("Dhivehi", .8), ("English", .2)],
    # Southeast Asia
    ("Philippines", "Metro Manila"): [("Filipino", .7), ("English", .3)],
    ("Philippines", "Central Visayas"): [("Cebuano", .75), ("English", .15), ("Filipino", .1)],
    ("Philippines", "Mindanao"): [("Cebuano", .55), ("Filipino", .2), ("Maguindanao", .1), ("English", .15)],
    ("Philippines", "Ilocos"): [("Ilocano", .7), ("Filipino", .2), ("English", .1)],
    ("Philippines", "Western Visayas"): [("Hiligaynon", .75), ("Filipino", .15), ("English", .1)],
    ("Philippines", "Calabarzon"): [("Filipino", .85), ("English", .15)],
    ("Malaysia", "Kuala Lumpur"): [("Malay", .45), ("English", .25), ("Mandarin Chinese", .15), ("Tamil", .1), ("Cantonese", .05)],
    ("Malaysia", "Penang"): [("Hokkien", .35), ("Malay", .35), ("English", .2), ("Tamil", .1)],
    ("Malaysia", "Sabah"): [("Malay", .6), ("Kadazandusun", .2), ("English", .2)],
    ("Malaysia", "Sarawak"): [("Malay", .5), ("Iban", .3), ("English", .2)],
    ("Malaysia", "Johor"): [("Malay", .75), ("Mandarin Chinese", .15), ("English", .1)],
    ("Malaysia", "Kelantan"): [("Malay", 1.0)],
    ("Indonesia", "Java"): [("Javanese", .5), ("Indonesian", .5)],
    ("Indonesia", "West Java"): [("Sundanese", .6), ("Indonesian", .4)],
    ("Indonesia", "Bali"): [("Balinese", .5), ("Indonesian", .5)],
    ("Indonesia", "Sulawesi"): [("Indonesian", .6), ("Buginese", .25), ("Makassarese", .15)],
    ("Indonesia", "Sumatra"): [("Indonesian", .5), ("Minangkabau", .2), ("Batak", .15), ("Acehnese", .15)],
    ("Singapore", "Singapore"): [("English", .5), ("Mandarin Chinese", .3), ("Malay", .1), ("Tamil", .1)],
    ("Myanmar", "Shan State"): [("Shan", .6), ("Burmese", .4)],
    ("Thailand", "Isan"): [("Thai", .5), ("Isan", .5)],
    ("Thailand", "Northern Thailand"): [("Thai", .6), ("Northern Thai", .4)],
    ("Thailand", "Southern Thailand"): [("Thai", .8), ("Malay", .2)],
    ("Timor-Leste", "Dili"): [("Tetum", .8), ("Portuguese", .2)],
    # East Asia
    ("China", "Guangdong"): [("Mandarin Chinese", .5), ("Cantonese", .5)],
    ("China", "Fujian"): [("Mandarin Chinese", .7), ("Hokkien", .3)],
    ("China", "Shanghai"): [("Mandarin Chinese", .85), ("Shanghainese", .15)],
    ("Hong Kong", "Hong Kong"): [("Cantonese", .85), ("English", .15)],
    ("Taiwan", "Kaohsiung"): [("Mandarin Chinese", .6), ("Taiwanese Hokkien", .4)],
    ("Japan", "Okinawa"): [("Japanese", 1.0)],
    # Europe
    ("Spain", "Catalonia"): [("Catalan", .6), ("Spanish", .4)],
    ("Spain", "Basque Country"): [("Spanish", .6), ("Basque", .4)],
    ("Spain", "Galicia"): [("Galician", .55), ("Spanish", .45)],
    ("Spain", "Valencia"): [("Spanish", .65), ("Valencian", .35)],
    ("Belgium", "Brussels"): [("French", .7), ("Dutch", .15), ("English", .15)],
    ("Netherlands", "Friesland"): [("Dutch", .6), ("West Frisian", .4)],
    ("Switzerland", "Grisons"): [("German", .6), ("Romansh", .25), ("Italian", .15)],
    ("Switzerland", "Fribourg"): [("French", .65), ("German", .35)],
    ("Switzerland", "Bern"): [("German", .9), ("French", .1)],
    ("Switzerland", "Valais"): [("French", .65), ("German", .35)],
    ("Italy", "South Tyrol"): [("German", .65), ("Italian", .3), ("Ladin", .05)],
    ("Italy", "Sardinia"): [("Italian", .75), ("Sardinian", .25)],
    ("UK", "Wales"): [("English", .7), ("Welsh", .3)],
    ("UK", "Scottish Highlands and Islands"): [("English", .8), ("Scottish Gaelic", .2)],
    ("Ireland", "Galway"): [("English", .7), ("Irish", .3)],
    ("France", "Alsace"): [("French", .85), ("Alsatian", .15)],
    ("France", "Corsica"): [("French", .8), ("Corsican", .2)],
    ("France", "Réunion"): [("Réunion Creole", .55), ("French", .45)],
    ("Finland", "Ostrobothnia"): [("Swedish", .5), ("Finnish", .5)],
    ("Finland", "Lapland"): [("Finnish", .9), ("Northern Sami", .1)],
    ("Norway", "Northern Norway"): [("Norwegian", .85), ("Northern Sami", .15)],
    ("Sweden", "Norrland"): [("Swedish", .9), ("Northern Sami", .05), ("Meankieli", .05)],
    ("Denmark", "Faroe Islands"): [("Faroese", 1.0)],
    ("Denmark", "Greenland"): [("Greenlandic", .8), ("Danish", .2)],
    ("Estonia", "Ida-Viru"): [("Russian", .7), ("Estonian", .3)],
    ("Latvia", "Latgale"): [("Latvian", .5), ("Latgalian", .2), ("Russian", .3)],
    ("Latvia", "Riga"): [("Latvian", .6), ("Russian", .4)],
    ("Ukraine", "Zakarpattia"): [("Ukrainian", .8), ("Hungarian", .2)],
    ("Moldova", "Chisinau"): [("Romanian", .75), ("Russian", .25)],
    ("Moldova", "Gagauzia"): [("Gagauz", .5), ("Russian", .5)],
    ("North Macedonia", "Tetovo"): [("Albanian", .7), ("Macedonian", .3)],
    ("Poland", "Pomerania"): [("Polish", .85), ("Kashubian", .15)],
    ("Belarus", "Minsk"): [("Russian", .65), ("Belarusian", .35)],
    ("Belarus", "Grodno"): [("Belarusian", .4), ("Russian", .5), ("Polish", .1)],
    ("Malta", "Malta"): [("Maltese", .75), ("English", .25)],
    ("Cyprus", "Nicosia"): [("Greek", .9), ("English", .1)],
    # MENA / Caucasus / Central Asia
    ("Morocco", "Souss"): [("Tashelhit", .55), ("Moroccan Arabic", .45)],
    ("Morocco", "Rif"): [("Tarifit", .6), ("Moroccan Arabic", .4)],
    ("Algeria", "Kabylie"): [("Kabyle", .7), ("Algerian Arabic", .2), ("French", .1)],
    ("Algeria", "Algiers"): [("Algerian Arabic", .7), ("French", .3)],
    ("Iran", "East Azerbaijan"): [("Azerbaijani", .7), ("Persian", .3)],
    ("Iran", "Gilan"): [("Persian", .6), ("Gilaki", .4)],
    ("Iraq", "Kurdistan Region"): [("Kurdish (Sorani)", .8), ("Arabic", .2)],
    ("Turkey", "Southeastern Anatolia"): [("Kurdish (Kurmanji)", .5), ("Turkish", .5)],
    ("Israel", "Haifa"): [("Hebrew", .6), ("Arabic", .4)],
    ("Israel", "Jerusalem"): [("Hebrew", .65), ("Arabic", .35)],
    ("Kazakhstan", "Almaty"): [("Kazakh", .45), ("Russian", .55)],
    ("Kazakhstan", "Astana"): [("Kazakh", .55), ("Russian", .45)],
    ("Kazakhstan", "Shymkent"): [("Kazakh", .8), ("Uzbek", .1), ("Russian", .1)],
    ("Uzbekistan", "Tashkent"): [("Uzbek", .7), ("Russian", .3)],
    ("Uzbekistan", "Samarkand"): [("Uzbek", .5), ("Tajik", .5)],
    ("Kyrgyzstan", "Bishkek"): [("Kyrgyz", .5), ("Russian", .5)],
    ("Kyrgyzstan", "Osh"): [("Kyrgyz", .6), ("Uzbek", .4)],
    ("Russia", "Tatarstan"): [("Russian", .6), ("Tatar", .4)],
    ("Russia", "Bashkortostan"): [("Russian", .6), ("Bashkir", .25), ("Tatar", .15)],
    ("Russia", "Sakha"): [("Russian", .5), ("Yakut", .5)],
    ("Russia", "Caucasus"): [("Russian", .5), ("Chechen", .2), ("Avar", .15), ("Ossetian", .15)],
    ("Georgia", "Batumi"): [("Georgian", 1.0)],
    # Americas / Oceania
    ("USA", "Southwest"): [("English", .6), ("Spanish", .3), ("Navajo", .1)],
    ("USA", "Hawaii"): [("English", .85), ("Hawaiian Pidgin", .15)],
    ("USA", "California"): [("English", .7), ("Spanish", .2), ("Tagalog", .05), ("Vietnamese", .05)],
    ("USA", "Texas"): [("English", .7), ("Spanish", .3)],
    ("USA", "Florida"): [("English", .7), ("Spanish", .25), ("Haitian Creole", .05)],
    ("USA", "New York"): [("English", .8), ("Spanish", .15), ("Mandarin Chinese", .05)],
    ("Canada", "Nunavut"): [("Inuktitut", .6), ("English", .4)],
    ("Canada", "Quebec"): [("French", .85), ("English", .15)],
    ("Mexico", "Oaxaca"): [("Spanish", .65), ("Zapotec", .2), ("Mixtec", .15)],
    ("Mexico", "Chiapas"): [("Spanish", .6), ("Tzotzil", .2), ("Tzeltal", .2)],
    ("Mexico", "Yucatan"): [("Spanish", .7), ("Yucatec Maya", .3)],
    ("Guatemala", "Western Highlands"): [("K'iche'", .5), ("Spanish", .5)],
    ("Peru", "Cusco"): [("Spanish", .55), ("Quechua", .45)],
    ("Peru", "Puno"): [("Spanish", .4), ("Quechua", .3), ("Aymara", .3)],
    ("Bolivia", "La Paz"): [("Spanish", .65), ("Aymara", .35)],
    ("Bolivia", "Cochabamba"): [("Spanish", .65), ("Quechua", .35)],
    ("Paraguay", "Asuncion"): [("Spanish", .55), ("Guarani", .45)],
    ("Paraguay", "Eastern Paraguay"): [("Guarani", .65), ("Spanish", .35)],
    ("Haiti", "Port-au-Prince"): [("Haitian Creole", .8), ("French", .2)],
    ("Jamaica", "Kingston"): [("Jamaican Patois", .55), ("English", .45)],
    ("New Zealand", "Northland"): [("English", .7), ("Maori", .3)],
    ("Australia", "Northern Territory"): [("English", .8), ("Kriol", .1), ("Yolngu Matha", .1)],
    ("Fiji", "Suva"): [("Fijian", .45), ("Fiji Hindi", .3), ("English", .25)],
    ("Papua New Guinea", "Port Moresby"): [("Tok Pisin", .6), ("English", .3), ("Hiri Motu", .1)],
    ("Samoa", "Apia"): [("Samoan", .85), ("English", .15)],
}


# Africa / Latin America: home-language seeds for the locations of block 1b
HOME_LANGUAGE_SEEDS.update({
    ("Sudan", "Khartoum"): [("Sudanese Arabic", .9), ("English", .1)],
    ("Sudan", "Port Sudan"): [("Sudanese Arabic", .7), ("Beja", .3)],
    ("Sudan", "Gezira"): [("Sudanese Arabic", 1.0)],
    ("South Sudan", "Juba"): [("Juba Arabic", .4), ("English", .3), ("Dinka", .2), ("Nuer", .1)],
    ("Somalia", "Mogadishu"): [("Somali", .9), ("Arabic", .1)],
    ("Somalia", "Hargeisa"): [("Somali", .9), ("English", .1)],
    ("Somalia", "Garowe"): [("Somali", 1.0)],
    ("Niger", "Niamey"): [("Zarma", .4), ("Hausa", .35), ("French", .25)],
    ("Niger", "Zinder"): [("Hausa", .85), ("French", .15)],
    ("Niger", "Agadez"): [("Tamasheq", .5), ("Hausa", .3), ("French", .2)],
    ("Chad", "N'Djamena"): [("Chadian Arabic", .6), ("French", .3), ("Sara", .1)],
    ("Chad", "Moundou"): [("Sara", .6), ("Chadian Arabic", .2), ("French", .2)],
    ("Guinea", "Conakry"): [("Susu", .4), ("French", .35), ("Pular", .25)],
    ("Guinea", "Labe"): [("Pular", .85), ("French", .15)],
    ("Guinea", "Kankan"): [("Maninka", .85), ("French", .15)],
    ("Sierra Leone", "Freetown"): [("Krio", .7), ("English", .3)],
    ("Sierra Leone", "Bo"): [("Mende", .6), ("Krio", .3), ("English", .1)],
    ("Sierra Leone", "Makeni"): [("Temne", .6), ("Krio", .3), ("English", .1)],
    ("Liberia", "Monrovia"): [("Liberian English", .75), ("Kpelle", .15), ("Bassa", .1)],
    ("Liberia", "Bong County"): [("Kpelle", .7), ("Liberian English", .3)],
    ("Togo", "Lome"): [("Ewe", .6), ("French", .4)],
    ("Togo", "Kara"): [("Kabiye", .7), ("French", .3)],
    ("Gabon", "Libreville"): [("French", .8), ("Fang", .2)],
    ("Republic of the Congo", "Brazzaville"): [("Lingala", .45), ("French", .4), ("Kituba", .15)],
    ("Republic of the Congo", "Pointe-Noire"): [("Kituba", .5), ("French", .5)],
    ("Burundi", "Bujumbura"): [("Kirundi", .7), ("French", .2), ("Swahili", .1)],
    ("Burundi", "Gitega"): [("Kirundi", .95), ("French", .05)],
    ("Eritrea", "Asmara"): [("Tigrinya", .85), ("Arabic", .1), ("English", .05)],
    ("Eritrea", "Massawa"): [("Tigre", .5), ("Tigrinya", .3), ("Arabic", .2)],
    ("Mauritania", "Nouakchott"): [("Hassaniya Arabic", .7), ("Pulaar", .15), ("French", .15)],
    ("Mauritania", "Nouadhibou"): [("Hassaniya Arabic", .8), ("French", .2)],
    ("Gambia", "Greater Banjul"): [("Mandinka", .4), ("Wolof", .35), ("English", .25)],
    ("Gambia", "Upper River Region"): [("Fula", .5), ("Mandinka", .4), ("English", .1)],
    ("Mauritius", "Port Louis"): [("Mauritian Creole", .8), ("English", .1), ("French", .1)],
    ("Lesotho", "Maseru"): [("Sesotho", .85), ("English", .15)],
    ("Lesotho", "Lesotho Highlands"): [("Sesotho", 1.0)],
    ("Eswatini", "Mbabane"): [("siSwati", .8), ("English", .2)],
    ("Eswatini", "Manzini"): [("siSwati", .85), ("English", .15)],
    ("Cabo Verde", "Praia"): [("Cape Verdean Creole", .85), ("Portuguese", .15)],
    ("Cabo Verde", "Mindelo"): [("Cape Verdean Creole", .85), ("Portuguese", .15)],
    ("Djibouti", "Djibouti City"): [("Somali", .5), ("Afar", .2), ("French", .2), ("Arabic", .1)],
    ("Guinea-Bissau", "Bissau"): [("Guinea-Bissau Creole", .7), ("Portuguese", .2), ("Balanta", .1)],
    ("Equatorial Guinea", "Malabo"): [("Spanish", .6), ("Fang", .3), ("Bube", .1)],
    ("Central African Republic", "Bangui"): [("Sango", .8), ("French", .2)],
    ("Comoros", "Moroni"): [("Comorian", .85), ("French", .15)],
    ("Seychelles", "Victoria"): [("Seychellois Creole", .8), ("English", .2)],
    ("Sao Tome and Principe", "Sao Tome"): [("Portuguese", .6), ("Forro", .4)],
    ("Senegal", "Saint-Louis"): [("Wolof", .5), ("Pulaar", .35), ("French", .15)],
    ("Mali", "Mopti"): [("Fula", .5), ("Bambara", .3), ("French", .2)],
    ("Burkina Faso", "Bobo-Dioulasso"): [("Dyula", .65), ("French", .35)],
    ("Cameroon", "Garoua"): [("Fula", .6), ("French", .3), ("Cameroonian Pidgin", .1)],
    ("DR Congo", "Kasai"): [("Tshiluba", .7), ("French", .3)],
    ("Mozambique", "Nampula"): [("Makhuwa", .6), ("Portuguese", .4)],
    ("Mozambique", "Beira"): [("Portuguese", .6), ("Sena", .4)],
    ("Angola", "Huambo"): [("Umbundu", .5), ("Portuguese", .5)],
    ("Uganda", "Mbarara"): [("Runyankole", .7), ("English", .3)],
    ("Zambia", "Copperbelt"): [("Bemba", .7), ("English", .3)],
    ("Malawi", "Blantyre"): [("Chichewa", .6), ("Yao", .2), ("English", .2)],
    ("Madagascar", "Toamasina"): [("Malagasy", .85), ("French", .15)],
    # MENA
    ("Libya", "Tripoli"): [("Libyan Arabic", .9), ("Tamazight", .1)],
    ("Libya", "Benghazi"): [("Libyan Arabic", 1.0)],
    # Latin America and Caribbean
    ("Nicaragua", "Managua"): [("Spanish", 1.0)],
    ("Nicaragua", "Leon"): [("Spanish", 1.0)],
    ("Nicaragua", "North Caribbean Coast"): [("Miskito", .4), ("Spanish", .35), ("Nicaraguan Creole English", .25)],
    ("Puerto Rico", "San Juan"): [("Spanish", .75), ("English", .25)],
    ("Puerto Rico", "Ponce"): [("Spanish", .9), ("English", .1)],
    ("Belize", "Belize City"): [("Belizean Kriol", .5), ("English", .3), ("Spanish", .2)],
    ("Belize", "Cayo"): [("Spanish", .5), ("Belizean Kriol", .2), ("English", .2), ("Q'eqchi'", .1)],
    ("Guyana", "Georgetown"): [("Guyanese Creole", .7), ("English", .3)],
    ("Guyana", "Rupununi"): [("Guyanese Creole", .4), ("Wapishana", .3), ("Makushi", .3)],
    ("Suriname", "Paramaribo"): [("Dutch", .45), ("Sranan Tongo", .35), ("Sarnami Hindustani", .15), ("Javanese", .05)],
    ("Barbados", "Bridgetown"): [("Bajan Creole", .6), ("English", .4)],
    ("Bahamas", "Nassau"): [("English", .8), ("Bahamian Creole", .2)],
    ("Saint Lucia", "Castries"): [("Saint Lucian Creole", .55), ("English", .45)],
    ("Dominica", "Roseau"): [("English", .5), ("Dominican Creole French", .5)],
    ("Curacao", "Willemstad"): [("Papiamento", .8), ("Dutch", .1), ("English", .1)],
    ("Aruba", "Oranjestad"): [("Papiamento", .75), ("Dutch", .15), ("Spanish", .1)],
    ("Venezuela", "Zulia"): [("Spanish", .85), ("Wayuunaiki", .15)],
    ("Venezuela", "Bolivar"): [("Spanish", .9), ("Pemon", .1)],
    ("Ecuador", "Quito"): [("Spanish", .9), ("Kichwa", .1)],
    ("Ecuador", "Chimborazo"): [("Spanish", .55), ("Kichwa", .45)],
    ("Cuba", "Havana"): [("Spanish", 1.0)],
    ("Dominican Republic", "Santo Domingo"): [("Spanish", 1.0)],
    ("Haiti", "Cap-Haitien"): [("Haitian Creole", .9), ("French", .1)],
    ("Haiti", "Les Cayes"): [("Haitian Creole", .95), ("French", .05)],
    ("Costa Rica", "Limon"): [("Spanish", .7), ("Limonese Creole", .3)],
    ("Panama", "Chiriqui"): [("Spanish", .8), ("Ngabere", .2)],
    ("Honduras", "La Ceiba"): [("Spanish", .8), ("Garifuna", .2)],
    ("Guatemala", "Alta Verapaz"): [("Q'eqchi'", .6), ("Spanish", .4)],
    ("Guatemala", "Huehuetenango"): [("Mam", .5), ("Spanish", .5)],
    ("Guatemala", "Peten"): [("Spanish", .85), ("Q'eqchi'", .15)],
    ("Chile", "Araucania"): [("Spanish", .75), ("Mapudungun", .25)],
    ("Chile", "Santiago"): [("Spanish", .95), ("Mapudungun", .05)],
    ("Colombia", "Cauca"): [("Spanish", .8), ("Nasa Yuwe", .1), ("Misak", .1)],
    ("Colombia", "La Guajira"): [("Spanish", .6), ("Wayuunaiki", .4)],
    ("Peru", "Ayacucho"): [("Quechua", .5), ("Spanish", .5)],
    ("Peru", "Loreto"): [("Spanish", .85), ("Shipibo-Konibo", .15)],
    ("Argentina", "Jujuy"): [("Spanish", .85), ("Quechua", .15)],
    ("Bolivia", "Potosi"): [("Quechua", .55), ("Spanish", .45)],
    ("Bolivia", "Santa Cruz"): [("Spanish", .9), ("Guarani", .1)],
    ("Brazil", "Amazonas"): [("Portuguese", .9), ("Nheengatu", .1)],
    ("Mexico", "Veracruz"): [("Spanish", .85), ("Nahuatl", .1), ("Totonac", .05)],
    ("Mexico", "Guerrero"): [("Spanish", .75), ("Nahuatl", .1), ("Mixtec", .1), ("Tlapanec", .05)],
    ("Mexico", "Sonora"): [("Spanish", .9), ("Yaqui", .1)],
    ("Mexico", "Michoacan"): [("Spanish", .85), ("Purepecha", .15)],
    ("Mexico", "Puebla"): [("Spanish", .85), ("Nahuatl", .15)],
})


def sample_home_language(country, sub_region):
    opts = HOME_LANGUAGE_SEEDS.get((country, sub_region))
    if not opts:
        return None
    langs, w = zip(*opts)
    return random.choices(langs, weights=w, k=1)[0]


# ===========================================================================
# 2. Occupations (original 211 + additions, ~500 total)
# ===========================================================================
# (profession, sector, gate). New sectors: Legal, Science & research, Energy & utilities,
# Informal & gig work, Care & domestic work, Not in paid work, Community & nonprofit.
_NEW_OCCUPATIONS = [
    # Healthcare
    ("Hospital resident doctor", "Healthcare", None),
    ("Cardiologist", "Healthcare", None),
    ("Psychiatrist", "Healthcare", None),
    ("Anesthesiologist", "Healthcare", None),
    ("Oncology nurse", "Healthcare", None),
    ("Community health worker", "Healthcare", None),
    ("Home-care nurse", "Healthcare", None),
    ("Pharmacy technician", "Healthcare", None),
    ("Dietitian", "Healthcare", None),
    ("Medical receptionist", "Healthcare", None),
    ("Hospital porter", "Healthcare", None),
    ("Sonographer", "Healthcare", None),
    ("Audiologist", "Healthcare", None),
    ("Chiropractor", "Healthcare", None),
    ("Traditional medicine practitioner", "Healthcare", None),
    ("Public-health officer", "Healthcare", None),
    ("Mental-health counsellor", "Healthcare", None),
    ("Hospice nurse", "Healthcare", None),
    ("Ambulance driver", "Healthcare", None),
    ("Phlebotomist", "Healthcare", None),
    ("Prosthetics technician", "Healthcare", None),
    ("Veterinary nurse", "Healthcare", None),
    ("Medical coder", "Healthcare", None),
    # Software & IT
    ("Site reliability engineer", "Software & IT", None),
    ("Software product manager", "Software & IT", None),
    ("Scrum master", "Software & IT", None),
    ("Data engineer", "Software & IT", None),
    ("AI research engineer", "Software & IT", None),
    ("Game designer", "Software & IT", None),
    ("Blockchain developer", "Software & IT", None),
    ("ERP consultant", "Software & IT", None),
    ("Freelance web developer", "Software & IT", None),
    ("Computer repair shop technician", "Software & IT", None),
    ("Penetration tester", "Software & IT", None),
    ("Solutions architect", "Software & IT", None),
    ("Localization engineer", "Software & IT", None),
    ("IT helpdesk agent", "Software & IT", None),
    ("Salesforce administrator", "Software & IT", None),
    ("Low-code app builder", "Software & IT", None),
    # Engineering
    ("Petroleum engineer", "Engineering", "oil_gas"),
    ("Mining engineer", "Engineering", "mining"),
    ("Renewable-energy engineer", "Engineering", None),
    ("Telecommunications technician", "Engineering", None),
    ("Railway engineer", "Engineering", None),
    ("Water-treatment engineer", "Engineering", None),
    ("Naval architect", "Engineering", "coastal"),
    ("Automotive engineer", "Engineering", None),
    ("Construction site manager", "Engineering", None),
    ("Quantity surveyor", "Engineering", None),
    ("Electronics technician", "Engineering", None),
    ("Drone survey pilot", "Engineering", None),
    ("Geotechnical engineer", "Engineering", None),
    ("Building-services engineer", "Engineering", None),
    # Skilled trades
    ("Scaffolder", "Skilled trades", None),
    ("Plasterer", "Skilled trades", None),
    ("Stonemason", "Skilled trades", None),
    ("Upholsterer", "Skilled trades", None),
    ("Goldsmith", "Skilled trades", None),
    ("Watch repairer", "Skilled trades", None),
    ("Cobbler", "Skilled trades", None),
    ("Motorcycle mechanic", "Skilled trades", None),
    ("Auto-body painter", "Skilled trades", None),
    ("Solar-panel installer", "Skilled trades", None),
    ("Pipefitter", "Skilled trades", None),
    ("Metalworker", "Skilled trades", None),
    ("Boat builder", "Skilled trades", "coastal"),
    ("Electric-vehicle technician", "Skilled trades", None),
    ("Apprentice electrician", "Skilled trades", None),
    ("Apprentice carpenter", "Skilled trades", None),
    ("Apprentice mechanic", "Skilled trades", None),
    ("Piano tuner", "Skilled trades", None),
    # Education: staff
    ("Secondary-school English teacher", "Education", None),
    ("Secondary-school history teacher", "Education", None),
    ("Physical-education teacher", "Education", None),
    ("Music teacher", "Education", None),
    ("Art teacher", "Education", None),
    ("Early-childhood educator", "Education", None),
    ("Teaching assistant", "Education", None),
    ("School principal", "Education", None),
    ("Adult-literacy instructor", "Education", None),
    ("Online tutor", "Education", None),
    ("Coding bootcamp instructor", "Education", None),
    ("University professor", "Education", None),
    ("Test-prep tutor", "Education", None),
    ("School administrator", "Education", None),
    ("Instructional designer", "Education", None),
    ("Second-language teacher for migrants", "Education", None),
    # Education: students by field / track
    ("Undergraduate student, computer science", "Education", None),
    ("Undergraduate student, medicine", "Education", None),
    ("Undergraduate student, law", "Education", None),
    ("Undergraduate student, nursing", "Education", None),
    ("Undergraduate student, business administration", "Education", None),
    ("Undergraduate student, engineering", "Education", None),
    ("Undergraduate student, economics", "Education", None),
    ("Undergraduate student, psychology", "Education", None),
    ("Undergraduate student, education", "Education", None),
    ("Undergraduate student, fine arts", "Education", None),
    ("Undergraduate student, languages and literature", "Education", None),
    ("Undergraduate student, biology", "Education", None),
    ("Undergraduate student, architecture", "Education", None),
    ("Undergraduate student, agriculture", "Education", None),
    ("Undergraduate student, journalism", "Education", None),
    ("Undergraduate student, mathematics", "Education", None),
    ("Undergraduate student, political science", "Education", None),
    ("Undergraduate student, pharmacy", "Education", None),
    ("Undergraduate student, tourism and hospitality", "Education", None),
    ("Undergraduate student, accounting", "Education", None),
    ("Undergraduate student, history", "Education", None),
    ("Undergraduate student, physics", "Education", None),
    ("Master's student, data science", "Education", None),
    ("Master's student, public health", "Education", None),
    ("Master's student, engineering", "Education", None),
    ("Master's student, international relations", "Education", None),
    ("MBA student", "Education", None),
    ("PhD student, physics", "Education", None),
    ("PhD student, social sciences", "Education", None),
    ("PhD student, biomedical sciences", "Education", None),
    ("PhD student, humanities", "Education", None),
    ("PhD student, computer science", "Education", None),
    ("Medical student in clinical rotations", "Education", None),
    ("Vocational student, electrical installation", "Education", None),
    ("Vocational student, hairdressing", "Education", None),
    ("Vocational student, culinary arts", "Education", None),
    ("Vocational student, automotive technology", "Education", None),
    ("Nursing-school student", "Education", None),
    ("Adult learner in evening classes", "Education", None),
    ("Career switcher in an online course", "Education", None),
    ("School leaver on a gap year", "Education", None),
    # Business & finance
    ("Credit analyst", "Business & finance", None),
    ("Microfinance loan officer", "Business & finance", None),
    ("Actuary", "Business & finance", None),
    ("Compliance officer", "Business & finance", None),
    ("Marketing manager", "Business & finance", None),
    ("Digital marketing specialist", "Business & finance", None),
    ("SEO specialist", "Business & finance", None),
    ("Brand manager", "Business & finance", None),
    ("Operations manager", "Business & finance", None),
    ("Business analyst", "Business & finance", None),
    ("Startup founder", "Business & finance", None),
    ("Venture-capital analyst", "Business & finance", "finance_hub"),
    ("Stockbroker", "Business & finance", None),
    ("Accounts-payable clerk", "Business & finance", None),
    ("Data-entry clerk", "Business & finance", None),
    ("Corporate receptionist", "Business & finance", None),
    ("Customs broker", "Business & finance", None),
    ("Public-relations officer", "Business & finance", None),
    ("Market-research analyst", "Business & finance", None),
    ("Insurance claims adjuster", "Business & finance", None),
    ("Freelance virtual assistant", "Business & finance", None),
    ("Franchise owner", "Business & finance", None),
    # Legal (new sector)
    ("Corporate lawyer", "Legal", None),
    ("Criminal defence lawyer", "Legal", None),
    ("Family lawyer", "Legal", None),
    ("Immigration lawyer", "Legal", None),
    ("Paralegal", "Legal", None),
    ("Notary", "Legal", None),
    ("Judge", "Legal", None),
    ("Legal secretary", "Legal", None),
    ("In-house counsel", "Legal", None),
    ("Patent attorney", "Legal", None),
    ("Court interpreter", "Legal", None),
    ("Legal-aid caseworker", "Legal", None),
    # Science & research (new sector)
    ("Research biologist", "Science & research", None),
    ("Laboratory chemist", "Science & research", None),
    ("Physicist", "Science & research", None),
    ("Climate scientist", "Science & research", None),
    ("Statistician", "Science & research", None),
    ("Research economist", "Science & research", None),
    ("Archaeologist", "Science & research", None),
    ("Marine biologist", "Science & research", "coastal"),
    ("Research assistant", "Science & research", None),
    ("Field ecologist", "Science & research", None),
    ("Astronomer", "Science & research", None),
    ("Food scientist", "Science & research", None),
    ("Social-science researcher", "Science & research", None),
    ("Clinical-trial coordinator", "Science & research", None),
    # Sales & retail
    ("B2B sales representative", "Sales & retail", None),
    ("Phone shop salesperson", "Sales & retail", None),
    ("Bookshop owner", "Sales & retail", None),
    ("Florist", "Sales & retail", None),
    ("Butcher", "Sales & retail", None),
    ("Grocery shop owner", "Sales & retail", None),
    ("Electronics store salesperson", "Sales & retail", None),
    ("Fashion boutique owner", "Sales & retail", None),
    ("Online marketplace reseller", "Sales & retail", None),
    ("Petrol-station attendant", "Sales & retail", None),
    ("Pharmacy shop assistant", "Sales & retail", None),
    ("Furniture store salesperson", "Sales & retail", None),
    ("Optician shop assistant", "Sales & retail", None),
    # Hospitality
    ("Tour guide", "Hospitality", None),
    ("Hotel manager", "Hospitality", None),
    ("Hostel owner", "Hospitality", None),
    ("Sommelier", "Hospitality", "wine"),
    ("Food-truck owner", "Hospitality", None),
    ("Kitchen porter", "Hospitality", None),
    ("Event planner", "Hospitality", None),
    ("Travel agent", "Hospitality", None),
    ("Cruise-ship crew member", "Hospitality", "coastal"),
    ("Bakery owner", "Hospitality", None),
    ("Coffee-shop owner", "Hospitality", None),
    ("Holiday-rental host", "Hospitality", None),
    # Creative & media
    ("Radio presenter", "Creative & media", None),
    ("TV news producer", "Creative & media", None),
    ("Novelist", "Creative & media", None),
    ("Spoken-word poet", "Creative & media", None),
    ("Stand-up comedian", "Creative & media", None),
    ("Theatre actor", "Creative & media", None),
    ("Professional dancer", "Creative & media", None),
    ("DJ", "Creative & media", None),
    ("Museum curator", "Creative & media", None),
    ("Book editor", "Creative & media", None),
    ("Game streamer", "Creative & media", None),
    ("Educational video creator", "Creative & media", None),
    ("Photojournalist", "Creative & media", None),
    ("Comic artist", "Creative & media", None),
    ("3D artist", "Creative & media", None),
    ("Motion designer", "Creative & media", None),
    ("Subtitler", "Creative & media", None),
    ("Voice actor", "Creative & media", None),
    ("Art restorer", "Creative & media", None),
    ("Calligrapher", "Creative & media", None),
    ("Music producer", "Creative & media", None),
    # Logistics & transport
    ("Airline pilot", "Logistics & transport", None),
    ("Flight attendant", "Logistics & transport", None),
    ("Taxi driver", "Logistics & transport", None),
    ("Ship captain", "Logistics & transport", "coastal"),
    ("Freight forwarder", "Logistics & transport", None),
    ("Last-mile delivery van driver", "Logistics & transport", None),
    ("Airport ground-crew worker", "Logistics & transport", None),
    ("Tram driver", "Logistics & transport", None),
    ("Fleet manager", "Logistics & transport", None),
    ("Inventory controller", "Logistics & transport", None),
    ("Railway signal operator", "Logistics & transport", None),
    ("School-bus driver", "Logistics & transport", None),
    # Public & civil service
    ("Diplomat", "Public & civil service", None),
    ("Local councillor", "Public & civil service", None),
    ("Parliamentary aide", "Public & civil service", None),
    ("Prison officer", "Public & civil service", None),
    ("Customs officer", "Public & civil service", None),
    ("Coast-guard officer", "Public & civil service", "coastal"),
    ("Military officer", "Public & civil service", None),
    ("Statistics-office analyst", "Public & civil service", None),
    ("Welfare-office clerk", "Public & civil service", None),
    ("Forensic investigator", "Public & civil service", None),
    ("Emergency dispatcher", "Public & civil service", None),
    ("Park maintenance worker", "Public & civil service", None),
    ("Municipal waste collector", "Public & civil service", None),
    ("Traffic warden", "Public & civil service", None),
    # Agriculture & environment
    ("Smallholder farmer", "Agriculture & environment", None),
    ("Poultry farmer", "Agriculture & environment", None),
    ("Fruit-orchard grower", "Agriculture & environment", None),
    ("Organic market gardener", "Agriculture & environment", None),
    ("Inland fish farmer", "Agriculture & environment", None),
    ("Agricultural extension officer", "Agriculture & environment", None),
    ("Horse trainer", "Agriculture & environment", None),
    ("Shepherd", "Agriculture & environment", None),
    ("Cocoa farmer", "Agriculture & environment", "cocoa"),
    ("Olive grower", "Agriculture & environment", "olive"),
    ("Conservation officer", "Agriculture & environment", None),
    ("Seasonal farm worker", "Agriculture & environment", None),
    ("Tree-nursery worker", "Agriculture & environment", None),
    # Manufacturing
    ("Electronics assembly worker", "Manufacturing", None),
    ("Semiconductor fab technician", "Manufacturing", "semiconductor"),
    ("Automotive plant worker", "Manufacturing", None),
    ("Steelworker", "Manufacturing", None),
    ("Brewery worker", "Manufacturing", None),
    ("Pharmaceutical production technician", "Manufacturing", None),
    ("Textile machine operator", "Manufacturing", None),
    ("Furniture factory worker", "Manufacturing", None),
    ("Food-safety quality technician", "Manufacturing", None),
    ("3D-printing technician", "Manufacturing", None),
    ("Chemical plant operator", "Manufacturing", None),
    ("Recycling-plant sorter", "Manufacturing", None),
    # Personal services
    ("Nail technician", "Personal services", None),
    ("Tattoo artist", "Personal services", None),
    ("Driving instructor", "Personal services", None),
    ("Wedding planner", "Personal services", None),
    ("Pet groomer", "Personal services", None),
    ("Life coach", "Personal services", None),
    ("Astrologer", "Personal services", None),
    ("Laundry-shop owner", "Personal services", None),
    ("Security guard", "Personal services", None),
    ("Building concierge", "Personal services", None),
    ("Makeup artist", "Personal services", None),
    ("Martial-arts instructor", "Personal services", None),
    ("Studio portrait photographer", "Personal services", None),
    ("Swimming instructor", "Personal services", None),
    # Maritime / Extractive
    ("Ferry deckhand", "Maritime", "coastal"),
    ("Harbour pilot", "Maritime", "coastal"),
    ("Marine engineer", "Maritime", "coastal"),
    ("Quarry worker", "Extractive", None),
    ("Artisanal gold miner", "Extractive", "mining"),
    ("Gas-plant operator", "Extractive", "oil_gas"),
    ("Mining equipment operator", "Extractive", "mining"),
    # Energy & utilities (new sector)
    ("Power-plant operator", "Energy & utilities", None),
    ("Wind-turbine technician", "Energy & utilities", None),
    ("Electricity lineworker", "Energy & utilities", None),
    ("Water-utility technician", "Energy & utilities", None),
    ("Solar-farm technician", "Energy & utilities", None),
    ("Energy analyst", "Energy & utilities", None),
    ("Meter reader", "Energy & utilities", None),
    ("Nuclear-plant technician", "Energy & utilities", "nuclear"),
    # Informal & gig work (new sector)
    ("Food-delivery rider", "Informal & gig work", None),
    ("Motorcycle-taxi rider", "Informal & gig work", "motorbike_taxi"),
    ("Street-food vendor", "Informal & gig work", None),
    ("Market fruit-and-vegetable vendor", "Informal & gig work", None),
    ("Construction day labourer", "Informal & gig work", None),
    ("Remote data annotator", "Informal & gig work", None),
    ("Contract content moderator", "Informal & gig work", None),
    ("Handyman doing odd jobs", "Informal & gig work", None),
    ("Informal phone repairer", "Informal & gig work", None),
    ("Mobile-money agent", "Informal & gig work", "mobile_money"),
    ("Street hawker", "Informal & gig work", None),
    ("Waste picker", "Informal & gig work", None),
    ("Multi-app delivery and ride-hail driver", "Informal & gig work", None),
    ("Car-wash attendant", "Informal & gig work", None),
    ("Online micro-task worker", "Informal & gig work", None),
    ("Busker", "Informal & gig work", None),
    ("Auto-rickshaw driver", "Informal & gig work", "rickshaw"),
    ("Jeepney driver", "Informal & gig work", "jeepney"),
    ("Minibus-taxi driver", "Informal & gig work", "minibus_taxi"),
    ("Home-based seamstress", "Informal & gig work", None),
    ("Freelance event photographer", "Informal & gig work", None),
    ("Social-commerce seller", "Informal & gig work", None),
    # Care & domestic work (new sector)
    ("Domestic worker", "Care & domestic work", None),
    ("Nanny", "Care & domestic work", None),
    ("Au pair", "Care & domestic work", None),
    ("Home-care aide for the elderly", "Care & domestic work", None),
    ("Disability support worker", "Care & domestic work", None),
    ("House cleaner", "Care & domestic work", None),
    ("Personal-care assistant", "Care & domestic work", None),
    ("Daycare assistant", "Care & domestic work", None),
    ("Private household cook", "Care & domestic work", None),
    ("Night-shift care-home worker", "Care & domestic work", None),
    # Not in paid work (new sector)
    ("Retired teacher", "Not in paid work", None),
    ("Retired engineer", "Not in paid work", None),
    ("Retired nurse", "Not in paid work", None),
    ("Retired civil servant", "Not in paid work", None),
    ("Retired small-business owner", "Not in paid work", None),
    ("Retired factory worker", "Not in paid work", None),
    ("Retired farmer", "Not in paid work", None),
    ("Retired military officer", "Not in paid work", None),
    ("Retired doctor", "Not in paid work", None),
    ("Retired accountant", "Not in paid work", None),
    ("Retired IT professional", "Not in paid work", None),
    ("Retired shopkeeper", "Not in paid work", None),
    ("Homemaker", "Not in paid work", None),
    ("Stay-at-home parent", "Not in paid work", None),
    ("Job seeker after a layoff", "Not in paid work", None),
    ("Recent graduate looking for work", "Not in paid work", None),
    ("Parent returning to work after a career break", "Not in paid work", None),
    ("Unpaid carer for a family member", "Not in paid work", None),
    # Community & nonprofit (new sector)
    ("NGO programme officer", "Community & nonprofit", None),
    ("Imam", "Community & nonprofit", None),
    ("Parish priest", "Community & nonprofit", None),
    ("Pastor", "Community & nonprofit", None),
    ("Rabbi", "Community & nonprofit", None),
    ("Community organizer", "Community & nonprofit", None),
    ("Humanitarian aid worker", "Community & nonprofit", None),
    ("Volunteer coordinator", "Community & nonprofit", None),
    ("Fundraising manager", "Community & nonprofit", None),
    ("Trade-union representative", "Community & nonprofit", None),
    ("Youth worker", "Community & nonprofit", None),
    ("Refugee resettlement caseworker", "Community & nonprofit", None),
]

OCCUPATIONS_EXTENDED = list(_base.OCCUPATIONS) + [o for o in _NEW_OCCUPATIONS
                                             if o[0] not in {x[0] for x in _base.OCCUPATIONS}]


def _tags(*xs):
    return set(xs)


# Gate tags: original tags extended to the new locations + new tags for the new gated occupations.
GATE_TAGS_EXTENDED = {k: set(v) for k, v in _base.GATE_TAGS.items()}
GATE_TAGS_EXTENDED["coastal"] |= _tags(
    "California", "Florida", "Pacific Northwest", "New England", "Hawaii", "Puerto Rico", "Texas", "Deep South",
    "British Columbia", "Atlantic Canada", "Quebec", "Nunavut", "Brittany", "Provence", "Corsica", "Réunion",
    "Hauts-de-France", "Occitania", "Hamburg", "Lower Saxony", "Kerala", "Tamil Nadu", "West Bengal", "Maharashtra",
    "Gujarat", "Odisha", "Andhra Pradesh", "Guangdong", "Fujian", "Shandong", "Zhejiang", "Shanghai", "Liaoning",
    "Guangxi", "Jiangsu", "Sindh", "Balochistan", "Alexandria", "Far East", "Pomerania", "Gothenburg", "Sweden",
    "Finland", "Belgium", "Cuba", "Dominican Republic", "Haiti", "Jamaica", "Trinidad and Tobago", "Venezuela",
    "Ecuador", "Uruguay", "Panama", "Costa Rica", "Honduras", "El Salvador", "Cameroon", "Cote d'Ivoire", "Ghana",
    "Mozambique", "Angola", "Madagascar", "Cambodia", "Singapore", "Timor-Leste", "Fiji", "Papua New Guinea",
    "Samoa", "Cyprus", "Malta", "Haifa", "Lebanon", "Oman", "Qatar", "Bahrain", "Kuwait", "Jeddah",
    "Eastern Province", "UAE", "Batumi", "Maldives", "Myanmar", "Hong Kong", "Algeria", "Tunisia", "Benin",
    "Namibia", "Basra", "Faroe Islands", "Greenland", "Gilan", "Black Sea Region", "Aegean Coast", "Busan", "Jeju",
    "Okinawa", "Kyushu", "Hokkaido", "Tohoku", "Valparaiso", "Biobio", "Lima", "Caribbean Coast", "Bahia",
    "Rio de Janeiro", "Sao Paulo", "Mombasa", "Dar es Salaam", "Zanzibar", "Lagos", "Rivers", "Dakar", "Casamance",
    "KwaZulu-Natal", "Cape Town", "Eastern Cape", "Northland", "Tasmania", "Queensland", "Northern Territory",
    "Penang", "Sarawak", "Johor", "Kelantan", "Sabah", "Bali", "Da Nang", "Ho Chi Minh City", "Canary Islands",
    "Galicia", "Valencia", "Basque Country", "Madeira", "Sardinia", "Apulia", "Campania", "Sicily", "Dalmatia",
    "Istria", "Varna", "Vlore", "Scottish Highlands and Islands", "Northern Ireland", "Galway", "Cork",
    "Western Norway", "Northern Norway", "Trondelag", "Friesland", "South Holland", "North Holland",
)
GATE_TAGS_EXTENDED["tropical_coast"] |= _tags(
    "Hawaii", "Puerto Rico", "Cuba", "Dominican Republic", "Jamaica", "Costa Rica", "Panama", "Fiji", "Samoa",
    "Maldives", "Bali", "Zanzibar", "Mombasa", "Okinawa", "Réunion", "Timor-Leste", "Madagascar", "Mozambique",
    "Sri Lanka", "Kerala", "Cambodia", "Papua New Guinea", "Caribbean Coast", "Bahia", "Yucatan")
GATE_TAGS_EXTENDED["alpine"] |= _tags("South Tyrol", "Styria", "Upper Austria", "Fribourg", "Kyrgyzstan", "Tajikistan",
                                  "Georgia", "Bhutan", "Mendoza", "Northern Norway", "Sichuan", "Yunnan")
GATE_TAGS_EXTENDED["mining"] |= _tags("DR Congo", "Zambia", "Mongolia", "Bolivia", "Zimbabwe", "Botswana", "Namibia",
                                  "Mali", "Burkina Faso", "Western Australia", "Antofagasta", "Urals", "Sakha",
                                  "Far East", "Kyrgyzstan", "Shanxi", "Limpopo", "Tanzania", "Papua New Guinea",
                                  "Jharkhand", "Odisha", "Kalimantan")
GATE_TAGS_EXTENDED["oil_gas"] |= _tags("Iraq", "Kuwait", "Qatar", "Oman", "Bahrain", "Algeria", "Angola", "Azerbaijan",
                                   "Venezuela", "Alberta", "Texas", "Eastern Province", "Turkmenistan", "Basra",
                                   "Zulia", "Rivers", "Bashkortostan", "Tatarstan", "Trinidad and Tobago")
GATE_TAGS_EXTENDED["rice"] |= _tags("Cambodia", "Laos", "Tohoku", "Jeolla", "Madhesh", "Madagascar", "Kerala",
                                "Andhra Pradesh", "Telangana", "Odisha", "Assam", "Bihar", "Hunan", "Guangxi",
                                "West Java", "Bali", "Ilocos", "Western Visayas", "Northern Thailand", "Kelantan")
GATE_TAGS_EXTENDED["plantation"] |= _tags("Uganda", "Rwanda", "Cameroon", "Cote d'Ivoire", "Malawi", "Assam", "Kerala",
                                      "Ecuador", "Costa Rica", "Guatemala", "Honduras", "Papua New Guinea",
                                      "Western Highlands", "Sidama", "Kandy", "Yunnan", "Fujian")
GATE_TAGS_EXTENDED["wine"] |= _tags("Georgia", "Armenia", "Moldova", "Mendoza", "Cyprus", "Hungary", "Austria",
                                "Romania", "Lebanon", "Baden-Württemberg", "Alsace", "Occitania", "Piedmont",
                                "Peloponnese", "Rio Grande do Sul", "Uruguay", "New Zealand", "South Australia")
GATE_TAGS_EXTENDED["arid"] |= _tags("Algeria", "Jordan", "Iraq", "Kuwait", "Qatar", "Oman", "Mongolia", "Turkmenistan",
                                "Rajasthan", "Balochistan", "Somali Region", "Mali", "Burkina Faso", "Namibia",
                                "Botswana", "Northern Territory", "Antofagasta", "Southwest")
GATE_TAGS_EXTENDED["textile_hub"] |= _tags("Cambodia", "Sri Lanka", "Ethiopia", "Morocco", "Tamil Nadu", "Gujarat", "Jiangsu")
GATE_TAGS_EXTENDED["media_hub"] |= _tags("Seoul", "Hong Kong", "Mexico City", "Cairo", "Istanbul", "London", "Tokyo",
                                     "Telangana", "Tamil Nadu", "Sao Paulo", "Berlin", "Kerala", "Ontario", "Kansai")
GATE_TAGS_EXTENDED["finance_hub"] |= _tags("Singapore", "Hong Kong", "Shanghai", "Luxembourg City", "Ontario", "Maharashtra",
                                       "Qatar", "Sao Paulo", "Johannesburg", "Seoul", "Île-de-France", "New South Wales",
                                       "Bahrain", "North Holland", "Abu Dhabi")
GATE_TAGS_EXTENDED["port"] |= _tags("Singapore", "Hamburg", "Busan", "Shanghai", "Guangdong", "South Holland", "Attica",
                                "Valencia", "KwaZulu-Natal", "Mombasa", "Lagos", "Colombo", "Jeddah", "Panama",
                                "Valparaiso", "Sao Paulo", "Chittagong", "Sindh", "Dar es Salaam", "Far East",
                                "Pomerania", "Haifa", "Alexandria", "Basra", "Lima", "Caribbean Coast", "Shandong",
                                "Zhejiang", "Liaoning", "Fujian", "Hong Kong", "Kaohsiung", "Gujarat", "Abidjan",
                                "Douala", "Cotonou", "Maputo", "Luanda", "Gothenburg", "Johor", "Penang")
GATE_TAGS_EXTENDED.update({
    "cocoa": _tags("Ghana", "Cote d'Ivoire", "Nigeria", "Cameroon", "Ecuador", "Indonesia", "Brazil", "Sulawesi",
                   "Bahia", "Peru", "Dominican Republic"),
    "olive": _tags("Spain", "Italy", "Greece", "Tunisia", "Morocco", "Turkey", "Portugal", "Algeria", "Lebanon",
                   "Jordan", "Israel", "Croatia", "Cyprus", "Albania", "Provence", "Corsica"),
    "semiconductor": _tags("Taiwan", "South Korea", "Japan", "China", "Malaysia", "Singapore", "Penang", "Saxony",
                           "California", "Southwest", "Vietnam", "Philippines", "Israel"),
    "nuclear": _tags("France", "USA", "Japan", "South Korea", "China", "Russia", "Ukraine", "Finland", "Sweden",
                     "Czechia", "Slovakia", "Hungary", "Belgium", "Switzerland", "Spain", "UK", "Canada", "India",
                     "Pakistan", "Argentina", "Brazil", "South Africa", "UAE", "Romania", "Bulgaria", "Slovenia",
                     "Armenia", "Iran", "Belarus"),
    "motorbike_taxi": _tags("Nigeria", "Uganda", "Kenya", "Rwanda", "Tanzania", "Cameroon", "Benin", "Burkina Faso",
                            "Mali", "DR Congo", "Thailand", "Vietnam", "Indonesia", "Cambodia", "Laos", "Philippines",
                            "Colombia", "Dominican Republic", "Haiti", "Brazil", "Malawi", "Ghana", "Cote d'Ivoire"),
    "mobile_money": _tags("Kenya", "Tanzania", "Uganda", "Ghana", "Rwanda", "Zambia", "Zimbabwe", "Cameroon",
                          "Cote d'Ivoire", "Senegal", "Mali", "Burkina Faso", "Benin", "Mozambique", "DR Congo",
                          "Malawi", "Bangladesh", "Pakistan", "Nigeria", "Ethiopia", "Madagascar"),
    "rickshaw": _tags("India", "Pakistan", "Bangladesh", "Sri Lanka", "Nepal", "Egypt", "Thailand", "Cambodia",
                      "Peru", "Guatemala", "Ethiopia"),
    "jeepney": _tags("Philippines"),
    "minibus_taxi": _tags("South Africa", "Kenya", "Nigeria", "Ghana", "Zimbabwe", "Zambia", "Botswana", "Namibia",
                          "Uganda", "Tanzania", "Senegal", "Mozambique", "Malawi", "Haiti", "Jamaica",
                          "Kyrgyzstan", "Kazakhstan", "Uzbekistan", "Georgia", "Armenia", "Azerbaijan", "Russia",
                          "Ukraine", "Belarus", "Moldova", "Mongolia", "Tajikistan"),
})

# Africa / Latin America: gate tags for the locations of block 1b
GATE_TAGS_EXTENDED["coastal"] |= _tags(
    "Port Sudan", "Somalia", "Mauritania", "Guinea", "Sierra Leone", "Liberia", "Togo", "Gabon", "Pointe-Noire",
    "Massawa", "Gambia", "Mauritius", "Cabo Verde", "Djibouti", "Guinea-Bissau", "Equatorial Guinea", "Comoros",
    "Seychelles", "Sao Tome and Principe", "Libya", "Nicaragua", "Puerto Rico", "Belize", "Guyana", "Suriname",
    "Barbados", "Bahamas", "Saint Lucia", "Dominica", "Curacao", "Aruba", "Montego Bay", "San Fernando",
    "Santiago de Cuba", "Veracruz", "Guerrero", "Sonora", "Manabi", "La Guajira", "Colon", "Limon", "La Ceiba",
    "Punta Cana", "Guanacaste", "Beira", "Nampula", "Toamasina", "Saint-Louis", "Maldonado")
GATE_TAGS_EXTENDED["tropical_coast"] |= _tags(
    "Mauritius", "Seychelles", "Comoros", "Cabo Verde", "Sao Tome and Principe", "Barbados", "Bahamas", "Saint Lucia",
    "Curacao", "Aruba", "Dominica", "Belize", "Montego Bay", "Guanacaste", "Limon", "La Ceiba", "Punta Cana",
    "North Caribbean Coast", "Veracruz", "Guerrero", "Toamasina", "Beira")
GATE_TAGS_EXTENDED["mining"] |= _tags("Guinea", "Sierra Leone", "Liberia", "Niger", "Mauritania", "Gabon", "Guyana",
                                  "Suriname", "Eritrea", "Sudan", "Potosi", "Copperbelt", "Bolivar", "Sonora",
                                  "Lesotho", "Kasai", "Central African Republic")
GATE_TAGS_EXTENDED["oil_gas"] |= _tags("Libya", "Sudan", "South Sudan", "Chad", "Gabon", "Republic of the Congo",
                                   "Equatorial Guinea", "Guyana", "Suriname", "Niger", "Veracruz")
GATE_TAGS_EXTENDED["plantation"] |= _tags("Liberia", "Burundi", "Togo", "Sierra Leone", "Guinea", "Sao Tome and Principe",
                                      "Belize", "Saint Lucia", "Dominica", "Mauritius", "Eswatini", "Nicaragua",
                                      "Huehuetenango", "Alta Verapaz", "Cauca", "Veracruz", "Chiriqui", "Mbarara")
GATE_TAGS_EXTENDED["cocoa"] |= _tags("Togo", "Sierra Leone", "Liberia", "Sao Tome and Principe", "Equatorial Guinea",
                                 "Republic of the Congo", "Nicaragua", "Venezuela")
GATE_TAGS_EXTENDED["rice"] |= _tags("Guinea", "Sierra Leone", "Gambia", "Guinea-Bissau", "Liberia", "Mopti", "Toamasina",
                                "Guyana", "Suriname")
GATE_TAGS_EXTENDED["arid"] |= _tags("Sudan", "Niger", "Chad", "Mauritania", "Somalia", "Djibouti", "Eritrea", "Libya",
                                "Sonora", "La Guajira", "Jujuy")
GATE_TAGS_EXTENDED["olive"] |= _tags("Libya")
GATE_TAGS_EXTENDED["port"] |= _tags("Port Sudan", "Djibouti City", "Lome", "Pointe-Noire", "Conakry", "Freetown",
                                "Monrovia", "Port Louis", "Colon", "Willemstad", "Veracruz", "Beira", "Nouadhibou")
GATE_TAGS_EXTENDED["finance_hub"] |= _tags("Port Louis", "Nassau", "Panama City")
GATE_TAGS_EXTENDED["motorbike_taxi"] |= _tags("Togo", "Sierra Leone", "Liberia", "Guinea", "Niger", "Chad", "Burundi",
                                          "South Sudan", "Republic of the Congo", "Central African Republic",
                                          "Guinea-Bissau", "Gabon", "Equatorial Guinea", "Comoros")
GATE_TAGS_EXTENDED["mobile_money"] |= _tags("Somalia", "Sierra Leone", "Liberia", "Guinea", "Togo", "Niger", "Chad",
                                        "Burundi", "Gabon", "Republic of the Congo", "Gambia", "Lesotho", "Eswatini",
                                        "Guinea-Bissau", "Central African Republic", "Mauritania", "South Sudan",
                                        "Djibouti", "Sudan", "Haiti")
GATE_TAGS_EXTENDED["minibus_taxi"] |= _tags("Lesotho", "Eswatini", "Sierra Leone", "Gambia", "Guinea", "Togo", "Burundi",
                                        "Somalia", "Sudan", "Djibouti", "Dominican Republic", "Guatemala", "Honduras",
                                        "El Salvador", "Nicaragua", "Liberia", "Mauritania")
GATE_TAGS_EXTENDED["rickshaw"] |= _tags("Sudan", "Somalia", "Djibouti")


@functools.lru_cache(maxsize=None)
def allowed_occupations_extended(region, country, sub_region):
    """Same rule as the base allowed_occupations (ungated + gate tag matches country/sub-region/region); cached."""
    out = []
    for profession, sector, gate in OCCUPATIONS_EXTENDED:
        if gate is None:
            out.append((profession, sector))
        else:
            tokens = GATE_TAGS_EXTENDED.get(gate, set())
            if country in tokens or sub_region in tokens or region in tokens:
                out.append((profession, sector))
    return tuple(out)


# Target share of each sector in the sampled stream (before gating). The base grid samples each occupation
# with weight = sector AI propensity, so sector shares depend on how many occupations a sector has
# (base-grid profiles: Software & IT 22.1%, Education 15.4%, Creative & media 15.4%, Business 12.7%, ...,
# Extractive 0.01%). With 575 occupations that coupling would let the long lists drive the mix, so the
# extended grid fixes sector shares explicitly and splits each share evenly across the sector's
# occupations. Shares still skew toward heavy LLM-user sectors, but less than on the base grid.
SECTOR_SHARE_EXTENDED = {
    "Software & IT": 14.0, "Education": 15.0, "Creative & media": 9.0, "Business & finance": 10.0,
    "Engineering": 6.0, "Healthcare": 7.0, "Public & civil service": 4.0, "Sales & retail": 4.5,
    "Personal services": 3.0, "Hospitality": 3.0, "Skilled trades": 3.0, "Logistics & transport": 3.0,
    "Manufacturing": 2.5, "Agriculture & environment": 2.5, "Maritime": 0.5, "Extractive": 0.4,
    "Legal": 2.0, "Science & research": 2.5, "Energy & utilities": 1.0, "Informal & gig work": 4.0,
    "Care & domestic work": 2.0, "Not in paid work": 5.0, "Community & nonprofit": 1.1,
}
# Within Education, students (any occupation containing "student", "learner", "gap year") get this
# share of the sector (base-grid profiles: 8.3k students = 54% of Education).
STUDENT_SHARE_OF_EDUCATION = 0.55


def _is_student(name):
    n = name.lower()
    return "student" in n or "learner" in n or "gap year" in n or "career switcher" in n


def _occ_weights():
    by_sector = {}
    for prof, sec, _ in OCCUPATIONS_EXTENDED:
        by_sector.setdefault(sec, []).append(prof)
    w = {}
    for sec, profs in by_sector.items():
        share = SECTOR_SHARE_EXTENDED.get(sec, 1.0)
        if sec == "Education":
            studs = [p for p in profs if _is_student(p)]
            staff = [p for p in profs if not _is_student(p)]
            for p in studs:
                w[p] = share * STUDENT_SHARE_OF_EDUCATION / len(studs)
            for p in staff:
                w[p] = share * (1 - STUDENT_SHARE_OF_EDUCATION) / len(staff)
        else:
            for p in profs:
                w[p] = share / len(profs)
    return w


OCC_WEIGHTS_EXTENDED = _occ_weights()


@functools.lru_cache(maxsize=None)
def _occ_cum_weights(region, country, sub_region):
    pairs = allowed_occupations_extended(region, country, sub_region)
    return pairs, list(itertools.accumulate(OCC_WEIGHTS_EXTENDED[p] for p, _ in pairs))


def sample_occupation_extended(region, country, sub_region):
    pairs, cum = _occ_cum_weights(region, country, sub_region)
    return random.choices(pairs, cum_weights=cum, k=1)[0]


# ---------------------------------------------------------------------------
# Digital fluency: base sector table + the new sectors, plus per-occupation overrides.
# ---------------------------------------------------------------------------
SECTOR_FLUENCY_WEIGHTS_EXTENDED = dict(_base.SECTOR_FLUENCY_WEIGHTS)
SECTOR_FLUENCY_WEIGHTS_EXTENDED.update({
    "Legal": (0.50, 0.43, 0.07),
    "Science & research": (0.75, 0.23, 0.02),
    "Energy & utilities": (0.40, 0.48, 0.12),
    "Informal & gig work": (0.22, 0.50, 0.28),
    "Care & domestic work": (0.15, 0.50, 0.35),
    "Not in paid work": (0.20, 0.45, 0.35),
    "Community & nonprofit": (0.35, 0.50, 0.15),
})
OCC_FLUENCY_OVERRIDE = {
    "Retired IT professional": (0.80, 0.18, 0.02),
    "Retired engineer": (0.45, 0.45, 0.10),
    "Retired doctor": (0.40, 0.48, 0.12),
    "Retired accountant": (0.40, 0.48, 0.12),
    "Retired teacher": (0.30, 0.52, 0.18),
    "Recent graduate looking for work": (0.55, 0.40, 0.05),
    "Job seeker after a layoff": (0.35, 0.50, 0.15),
    "Remote data annotator": (0.60, 0.38, 0.02),
    "Contract content moderator": (0.60, 0.38, 0.02),
    "Online micro-task worker": (0.55, 0.40, 0.05),
    "Social-commerce seller": (0.45, 0.45, 0.10),
    "Freelance virtual assistant": (0.65, 0.33, 0.02),
    "Career switcher in an online course": (0.50, 0.45, 0.05),
}


def sample_fluency_extended(occupation, sector):
    w = OCC_FLUENCY_OVERRIDE.get(occupation) or SECTOR_FLUENCY_WEIGHTS_EXTENDED.get(sector, _base.DEFAULT_FLUENCY_WEIGHTS)
    return random.choices(_base.DIGITAL_FLUENCIES, weights=w, k=1)[0]


# ---------------------------------------------------------------------------
# Age: base curve (students young, others 22-72 older-skewed) + explicit ranges for new occupation
# groups and minimum ages for senior / long-training roles. Schema allows 18-80.
# ---------------------------------------------------------------------------
AGE_RANGE = {}
for _p, _s, _ in OCCUPATIONS_EXTENDED:
    _n = _p.lower()
    if _n.startswith("retired"):
        AGE_RANGE[_p] = (60, 80)
    elif _n.startswith("undergraduate student"):
        AGE_RANGE[_p] = (18, 24)
    elif _n.startswith("master's student") or _n == "mba student":
        AGE_RANGE[_p] = (22, 32)
    elif _n.startswith("phd student"):
        AGE_RANGE[_p] = (24, 35)
    elif _n.startswith("vocational student") or _n == "nursing-school student":
        AGE_RANGE[_p] = (18, 23)
    elif _n.startswith("apprentice"):
        AGE_RANGE[_p] = (18, 24)
AGE_RANGE.update({
    "Retired military officer": (50, 80), "Medical student in clinical rotations": (21, 28),
    "Adult learner in evening classes": (25, 60), "Career switcher in an online course": (26, 50),
    "School leaver on a gap year": (18, 20), "Au pair": (18, 27), "Recent graduate looking for work": (21, 28),
    "Job seeker after a layoff": (25, 62), "Stay-at-home parent": (22, 48), "Homemaker": (22, 72),
    "Parent returning to work after a career break": (28, 50), "Unpaid carer for a family member": (25, 72),
    "Hospital resident doctor": (24, 33), "Food-delivery rider": (18, 50), "Bicycle courier": (18, 45),
    "Fast-food crew member": (18, 45), "Game streamer": (18, 40), "Busker": (18, 70),
    "Seasonal farm worker": (18, 60), "Teaching assistant": (19, 65), "Research assistant": (21, 35),
    "Online tutor": (19, 65), "Daycare assistant": (18, 60), "Kitchen porter": (18, 60),
})
MIN_AGE = {
    "Judge": 35, "Orthopedic surgeon": 30, "Cardiologist": 31, "Psychiatrist": 30, "Anesthesiologist": 30,
    "University professor": 32, "University lecturer": 27, "School principal": 35, "Airline pilot": 23,
    "Diplomat": 25, "Ship captain": 30, "Harbour pilot": 30, "Head chef": 24, "Postdoctoral researcher": 26,
    "General practitioner": 26, "Clinical psychologist": 26, "Chartered accountant": 23, "Notary": 28,
    "Patent attorney": 27, "Corporate lawyer": 24, "Criminal defence lawyer": 24, "Family lawyer": 24,
    "Immigration lawyer": 24, "In-house counsel": 26, "Bank branch manager": 27, "HR manager": 26,
    "Store manager": 22, "Restaurant manager": 23, "Hotel manager": 26, "Management consultant": 22,
    "Investment banker": 22, "Funeral director": 25, "Military officer": 22, "Army sergeant": 23,
    "Imam": 25, "Parish priest": 27, "Pastor": 25, "Rabbi": 26, "Local councillor": 25,
    "Air-traffic controller": 23, "Architect": 24, "Midwife": 22, "Veterinarian": 24, "General dentist": 24,
    "Community pharmacist": 23, "Actuary": 23, "Marine engineer": 22, "Physicist": 26, "Astronomer": 27,
    "Climate scientist": 26, "Research economist": 26, "Museum curator": 26, "Operations manager": 26,
    "Marketing manager": 25, "Fleet manager": 26, "Construction site manager": 26, "Solutions architect": 27,
    "Fundraising manager": 25, "Franchise owner": 24,
}


def sample_age_extended(occupation):
    rng = AGE_RANGE.get(occupation)
    if rng:
        return random.randint(*rng)
    lo_min = MIN_AGE.get(occupation, 18)
    for _ in range(50):
        a = _base.sample_age(occupation)
        if a >= lo_min:
            return a
    return max(lo_min, _base.sample_age(occupation))


# ===========================================================================
# 3. New seed axes
# ===========================================================================
# ---- 3a. Education level (values are exactly the schema's Education.level literals) ----
EDU_LEVELS = ["No formal education", "Primary school", "Some high school", "High school diploma",
              "Vocational / Trade training", "Some college", "Associate's degree", "Bachelor's degree",
              "Master's degree", "Doctoral degree", "Professional degree"]
EDU_BANDS = {   # weights in EDU_LEVELS order
    "low":          [4, 15, 22, 30, 12, 9, 2, 5, 1, 0, 0],
    "mixed":        [1, 4, 10, 30, 22, 12, 6, 12, 3, 0, 0],
    "vocational":   [0, 1, 4, 22, 55, 8, 6, 4, 0, 0, 0],
    "secondary":    [0, 2, 8, 42, 18, 14, 6, 9, 1, 0, 0],
    "tech":         [0, 0, 0, 2, 8, 9, 7, 50, 22, 2, 0],   # no "some high school"; the judge rejects engineers without a degree
    "tertiary":     [0, 0, 0, 2, 4, 4, 5, 57, 24, 2, 2],
    "advanced":     [0, 0, 0, 0, 0, 0, 0, 15, 50, 35, 0],
    "doctoral":     [0, 0, 0, 0, 0, 0, 0, 0, 15, 85, 0],
    "professional": [0, 0, 0, 0, 0, 0, 0, 3, 12, 15, 70],
    "student_ug":   [0, 0, 0, 5, 0, 90, 5, 0, 0, 0, 0],   # "high school" for an undergraduate reads as incoherent to the judge
    "postgrad":     [0, 0, 0, 0, 0, 0, 0, 0, 60, 40, 0],  # lecturers / clinical psychologists
    "phd_holder":   [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],    # postdocs
    "student_grad": [0, 0, 0, 0, 0, 0, 0, 75, 25, 0, 0],
    "student_phd":  [0, 0, 0, 0, 0, 0, 0, 10, 90, 0, 0],
    "student_voc":  [0, 0, 15, 70, 15, 0, 0, 0, 0, 0, 0],
}
SECTOR_EDU_BAND = {
    "Software & IT": "tech", "Engineering": "tech", "Healthcare": "tertiary", "Education": "tertiary",
    "Business & finance": "tertiary", "Sales & retail": "secondary", "Hospitality": "secondary",
    "Creative & media": "tertiary", "Logistics & transport": "secondary", "Public & civil service": "tertiary",
    "Agriculture & environment": "mixed", "Manufacturing": "vocational", "Personal services": "vocational",
    "Skilled trades": "vocational", "Maritime": "vocational", "Extractive": "mixed", "Legal": "professional",
    "Science & research": "advanced", "Energy & utilities": "vocational", "Informal & gig work": "low",
    "Care & domestic work": "low", "Not in paid work": "mixed", "Community & nonprofit": "tertiary",
}
OCC_EDU_BAND = {}
for _p in ["General practitioner", "General dentist", "Veterinarian", "Community pharmacist", "Orthopedic surgeon",
           "Cardiologist", "Psychiatrist", "Anesthesiologist", "Hospital resident doctor", "Retired doctor",
           "Optometrist", "Chiropractor"]:
    OCC_EDU_BAND[_p] = "professional"
for _p in ["Elderly-care assistant", "Hospital porter", "Medical receptionist", "Ambulance driver", "Phlebotomist",
           "Pharmacy technician", "Medical laboratory technician", "Dental hygienist", "Community health worker",
           "Veterinary nurse", "Prosthetics technician", "Medical coder", "Traditional medicine practitioner"]:
    OCC_EDU_BAND[_p] = "vocational"
for _p in ["University lecturer", "Postdoctoral researcher", "University professor", "Clinical psychologist",
           "AI research engineer", "Actuary"]:
    OCC_EDU_BAND[_p] = "doctoral" if _p in ("Postdoctoral researcher", "University professor") else "advanced"
# A postdoc holds a doctorate by definition (the doctoral band would give 15% Master's); lecturers and
# clinical psychologists need a postgraduate degree; research assistants are graduates, not "secondary".
OCC_EDU_BAND["University lecturer"] = OCC_EDU_BAND["Clinical psychologist"] = "postgrad"
OCC_EDU_BAND["Postdoctoral researcher"] = "phd_holder"
for _p in ["Bank teller", "Office administrator", "Payroll clerk", "Bookkeeper", "Accounts-payable clerk",
           "Data-entry clerk", "Corporate receptionist", "Freelance virtual assistant", "Executive assistant",
           "IT support technician", "IT helpdesk agent", "Computer repair shop technician", "Teaching assistant",
           "Paralegal", "Legal secretary", "Court clerk", "Police officer", "Firefighter", "Army sergeant",
           "Border-control officer", "Prison officer", "Customs officer", "Park maintenance worker",
           "Municipal waste collector", "Traffic warden", "Emergency dispatcher", "Welfare-office clerk",
           "Research assistant", "Social-media content creator", "Game streamer", "DJ", "Busker", "Session musician",
           "Stand-up comedian", "Professional dancer", "Visual merchandiser", "Small-business owner",
           "E-commerce shop owner", "Startup founder", "Franchise owner", "Market-stall trader", "Security guard"]:
    OCC_EDU_BAND[_p] = "secondary"
for _p in ["Corporate lawyer", "Criminal defence lawyer", "Family lawyer", "Immigration lawyer", "Notary", "Judge",
           "In-house counsel", "Patent attorney"]:
    OCC_EDU_BAND[_p] = "professional"
OCC_EDU_BAND.update({"Research assistant": "tertiary", "Court interpreter": "tertiary", "Legal-aid caseworker": "tertiary",
                     "Retired teacher": "tertiary", "Retired engineer": "tech", "Retired nurse": "tertiary",
                     "Retired civil servant": "secondary", "Retired small-business owner": "secondary",
                     "Retired factory worker": "low", "Retired farmer": "low", "Retired military officer": "secondary",
                     "Retired accountant": "tertiary", "Retired IT professional": "tech",
                     "Retired shopkeeper": "secondary", "Homemaker": "mixed", "Stay-at-home parent": "mixed",
                     "Recent graduate looking for work": "tertiary", "Remote data annotator": "secondary",
                     "Contract content moderator": "secondary", "Online micro-task worker": "secondary",
                     "Agronomist": "tertiary", "Agricultural extension officer": "tertiary",
                     "Conservation officer": "tertiary", "National-park ranger": "secondary",
                     "Imam": "secondary", "Pastor": "secondary", "Youth worker": "secondary",
                     "Airline pilot": "tertiary", "Air-traffic controller": "tertiary", "Supply-chain analyst": "tertiary",
                     "Logistics coordinator": "tertiary", "Freight forwarder": "secondary", "Fleet manager": "secondary",
                     "Tour guide": "secondary", "Hotel manager": "tertiary", "Event planner": "secondary",
                     "Tax inspector": "tertiary", "Urban planner": "advanced", "Diplomat": "advanced",
                     "Statistics-office analyst": "tertiary", "Forensic investigator": "tertiary",
                     "Energy analyst": "tertiary", "Nuclear-plant technician": "tech", "Power-plant operator": "vocational",
                     "Petroleum engineer": "tech", "Mining engineer": "tech", "Naval architect": "tech",
                     "Marine engineer": "tech", "Semiconductor fab technician": "tech",
                     "Pharmaceutical production technician": "vocational", "Freelance translator": "tertiary",
                     "Architect": "advanced", "Museum curator": "advanced", "Art restorer": "tertiary"})


def edu_band(occupation, sector):
    n = occupation.lower()
    if n.startswith(("undergraduate student", "medical student")) or occupation == "Undergraduate student":
        return "student_ug"
    if n.startswith("phd student"):
        return "student_phd"
    if n.startswith(("master's student", "mba student")) or occupation == "Graduate student":
        return "student_grad"
    if n.startswith(("vocational student", "nursing-school student", "school leaver")):
        return "student_voc"
    if n.startswith("apprentice"):
        return "student_voc"
    if n in ("adult learner in evening classes", "career switcher in an online course"):
        return "mixed"
    return OCC_EDU_BAND.get(occupation) or SECTOR_EDU_BAND.get(sector, "mixed")


# minimum plausible age for holding a level
_LEVEL_MIN_AGE = {"Associate's degree": 20, "Bachelor's degree": 21, "Master's degree": 23,
                  "Professional degree": 24, "Doctoral degree": 26}
# lower attainment for the open bands where tertiary access is lower; higher where it is near-universal
_REGION_EDU_SHIFT = {"Sub-Saharan Africa": -1, "South Asia": -1, "Southeast Asia": 0, "LATAM": 0, "MENA": 0,
                     "Central & North Asia": 0, "East Asia": 1, "Nordics": 1, "Western Europe": 1,
                     "North America": 1, "Oceania": 1, "Southern Europe": 0, "Eastern Europe": 1}


def sample_education_level(occupation, sector, age, region):
    band = edu_band(occupation, sector)
    w = list(EDU_BANDS[band])
    if band in ("low", "mixed", "secondary", "vocational"):
        shift = _REGION_EDU_SHIFT.get(region, 0)
        for i in range(len(w)):
            if shift < 0 and i <= 3:
                w[i] *= 1.5
            if shift > 0 and i <= 2:
                w[i] *= 0.5
    for i, lvl in enumerate(EDU_LEVELS):
        if age < _LEVEL_MIN_AGE.get(lvl, 0):
            w[i] = 0
    if sum(w) == 0:
        w = [0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0]
    return random.choices(EDU_LEVELS, weights=w, k=1)[0]


# ---- 3b. Urban / rural setting ----
SETTLEMENTS = ["Major city", "Suburb or commuter town", "Mid-size town", "Small town", "Village or rural area"]
# Approximate urban population share (UN WUP / World Bank, rounded). Unlisted countries: 0.6.
URBAN_SHARE = {
    "USA": .83, "Canada": .82, "Mexico": .81, "Brazil": .88, "Colombia": .82, "Argentina": .92, "Chile": .88,
    "Peru": .79, "Guatemala": .53, "Venezuela": .88, "Ecuador": .65, "Bolivia": .71, "Paraguay": .63,
    "Uruguay": .96, "Cuba": .77, "Dominican Republic": .84, "Haiti": .59, "Costa Rica": .82, "Panama": .69,
    "Honduras": .60, "El Salvador": .75, "Jamaica": .57, "Trinidad and Tobago": .53, "Switzerland": .74,
    "Germany": .78, "France": .82, "Spain": .81, "Portugal": .67, "Netherlands": .93, "Belgium": .98,
    "Austria": .59, "Ireland": .64, "UK": .84, "Luxembourg": .92, "Italy": .72, "Greece": .80, "Croatia": .58,
    "Slovenia": .56, "Bosnia & Herzegovina": .50, "Serbia": .57, "Montenegro": .68, "North Macedonia": .59,
    "Albania": .64, "Kosovo": .50, "Bulgaria": .77, "Malta": .95, "Cyprus": .67, "Sweden": .89, "Norway": .84,
    "Denmark": .88, "Finland": .86, "Iceland": .94, "Poland": .60, "Czechia": .74, "Slovakia": .54,
    "Hungary": .73, "Romania": .55, "Ukraine": .70, "Belarus": .80, "Estonia": .70, "Latvia": .69,
    "Lithuania": .69, "Moldova": .43, "Turkey": .77, "Egypt": .43, "Morocco": .65, "Saudi Arabia": .85,
    "UAE": .88, "Iran": .77, "Israel": .93, "Lebanon": .89, "Algeria": .75, "Tunisia": .70, "Jordan": .92,
    "Iraq": .71, "Kuwait": 1.0, "Qatar": .99, "Oman": .88, "Bahrain": .90, "Nigeria": .54, "Kenya": .29,
    "South Africa": .68, "Ethiopia": .23, "Ghana": .59, "Tanzania": .37, "Senegal": .49, "Uganda": .26,
    "Rwanda": .18, "DR Congo": .47, "Cameroon": .59, "Cote d'Ivoire": .53, "Zimbabwe": .32, "Zambia": .46,
    "Mozambique": .38, "Angola": .68, "Madagascar": .40, "Botswana": .72, "Namibia": .54, "Mali": .46,
    "Burkina Faso": .32, "Benin": .49, "Malawi": .18, "China": .65, "Japan": .92, "South Korea": .81,
    "Taiwan": .80, "Hong Kong": 1.0, "Mongolia": .69, "India": .36, "Pakistan": .38, "Bangladesh": .40,
    "Sri Lanka": .19, "Nepal": .22, "Bhutan": .44, "Maldives": .41, "Vietnam": .39, "Thailand": .53,
    "Indonesia": .58, "Philippines": .48, "Malaysia": .78, "Myanmar": .32, "Singapore": 1.0, "Cambodia": .26,
    "Laos": .38, "Timor-Leste": .33, "Kazakhstan": .58, "Uzbekistan": .51, "Russia": .75, "Kyrgyzstan": .38,
    "Tajikistan": .28, "Turkmenistan": .54, "Georgia": .61, "Armenia": .64, "Azerbaijan": .57,
    "Australia": .87, "New Zealand": .87, "Fiji": .58, "Papua New Guinea": .14, "Samoa": .17,
}
# Sub-regions that are themselves a city or city-state: only city / suburb settings make sense.
CITY_SUBREGIONS = {
    "New York", "Mexico City", "Sao Paulo", "Rio de Janeiro", "Bogota", "Buenos Aires", "Santiago", "Lima",
    "Guatemala City", "Caracas", "Quito", "Guayaquil", "La Paz", "Asuncion", "Montevideo", "Havana",
    "Santo Domingo", "Port-au-Prince", "San Jose", "Panama City", "Tegucigalpa", "San Salvador", "Kingston",
    "Port of Spain", "Zurich", "Geneva", "Basel", "Berlin", "Hamburg", "Île-de-France", "Madrid", "Lisbon",
    "Porto", "Brussels", "Vienna", "Dublin", "London", "Luxembourg City", "Zagreb", "Ljubljana", "Maribor",
    "Sarajevo", "Belgrade", "Niš", "Podgorica", "Skopje", "Tirana", "Pristina", "Sofia", "Varna", "Plovdiv",
    "Nicosia", "Limassol", "Stockholm", "Gothenburg", "Oslo", "Copenhagen", "Helsinki", "Tampere", "Reykjavík",
    "Akureyri", "Prague", "Bratislava", "Košice", "Budapest", "Bucharest", "Minsk", "Tallinn", "Tartu", "Riga",
    "Vilnius", "Kaunas", "Chisinau", "Istanbul", "Ankara", "Cairo", "Alexandria", "Casablanca", "Rabat",
    "Marrakesh", "Fes", "Riyadh", "Jeddah", "Dubai", "Abu Dhabi", "Sharjah", "Tehran", "Isfahan", "Tel Aviv",
    "Jerusalem", "Haifa", "Beirut", "Tripoli", "Algiers", "Oran", "Tunis", "Sfax", "Amman", "Irbid", "Baghdad",
    "Basra", "Kuwait City", "Doha", "Muscat", "Manama", "Lagos", "Abuja", "Nairobi", "Mombasa", "Kisumu",
    "Johannesburg", "Cape Town", "Addis Ababa", "Accra", "Dar es Salaam", "Dakar", "Kampala", "Kigali",
    "Kinshasa", "Lubumbashi", "Douala", "Yaounde", "Abidjan", "Harare", "Bulawayo", "Lusaka", "Maputo",
    "Luanda", "Antananarivo", "Gaborone", "Windhoek", "Bamako", "Ouagadougou", "Cotonou", "Lilongwe",
    "Beijing", "Shanghai", "Chongqing", "Tokyo", "Seoul", "Busan", "Daegu", "Taipei", "Kaohsiung", "Taichung",
    "Hong Kong", "Ulaanbaatar", "Delhi", "Dhaka", "Colombo", "Kathmandu", "Islamabad", "Thimphu", "Male",
    "Hanoi", "Ho Chi Minh City", "Da Nang", "Jakarta", "Metro Manila", "Kuala Lumpur", "Penang", "Yangon",
    "Mandalay", "Singapore", "Phnom Penh", "Vientiane", "Dili", "Almaty", "Astana", "Shymkent", "Tashkent",
    "Samarkand", "Moscow", "St. Petersburg", "Bishkek", "Osh", "Dushanbe", "Ashgabat", "Tbilisi", "Batumi",
    "Yerevan", "Gyumri", "Baku", "Ganja", "Auckland", "Wellington", "Suva", "Port Moresby", "Apia", "Kyiv",
    "Lviv", "Kharkiv", "Dnipro", "Odesa", "Zaporizhzhia", "Malta",
}
# Africa / Latin America: urban shares (UN WUP / World Bank, rounded) and city sub-regions for block 1b
URBAN_SHARE.update({
    "Sudan": .36, "South Sudan": .21, "Somalia": .48, "Niger": .17, "Chad": .24, "Guinea": .38, "Sierra Leone": .44,
    "Liberia": .53, "Togo": .44, "Gabon": .91, "Republic of the Congo": .69, "Burundi": .15, "Eritrea": .43,
    "Mauritania": .57, "Gambia": .64, "Mauritius": .41, "Lesotho": .30, "Eswatini": .25, "Cabo Verde": .68,
    "Djibouti": .78, "Guinea-Bissau": .45, "Equatorial Guinea": .74, "Central African Republic": .43,
    "Comoros": .30, "Seychelles": .58, "Sao Tome and Principe": .76, "Libya": .81, "Nicaragua": .60,
    "Puerto Rico": .94, "Belize": .46, "Guyana": .27, "Suriname": .66, "Barbados": .31, "Bahamas": .83,
    "Saint Lucia": .19, "Dominica": .72, "Curacao": .89, "Aruba": .44,
})
CITY_SUBREGIONS |= {
    "Khartoum", "Port Sudan", "Juba", "Mogadishu", "Hargeisa", "Garowe", "Niamey", "N'Djamena", "Conakry",
    "Freetown", "Monrovia", "Lome", "Libreville", "Brazzaville", "Pointe-Noire", "Bujumbura", "Asmara",
    "Nouakchott", "Nouadhibou", "Greater Banjul", "Port Louis", "Maseru", "Mbabane", "Manzini", "Praia", "Mindelo",
    "Djibouti City", "Bissau", "Malabo", "Bangui", "Moroni", "Victoria", "Sao Tome", "Benghazi", "Managua",
    "San Juan", "Belize City", "Georgetown", "Paramaribo", "Bridgetown", "Nassau", "Castries", "Roseau",
    "Willemstad", "Oranjestad", "Santiago de los Caballeros", "Cap-Haitien", "Santiago de Cuba", "San Pedro Sula",
    "Cuenca", "Montego Bay", "San Fernando", "Bobo-Dioulasso", "Garoua",
}

_RURAL_SECTORS = {"Agriculture & environment": 3.0, "Extractive": 2.0, "Maritime": 1.5}
_CITY_SECTORS = {"Software & IT": 1.6, "Business & finance": 1.5, "Legal": 1.6, "Science & research": 1.5,
                 "Creative & media": 1.4}


def sample_settlement(country, sub_region, sector, occupation):
    if sub_region in CITY_SUBREGIONS:
        opts = ["Major city", "Suburb or commuter town"]
        w = [0.65, 0.35]
        if sector == "Agriculture & environment":
            opts.append("Peri-urban fringe of the city")
            w = [0.2, 0.3, 0.5]
        return random.choices(opts, weights=w, k=1)[0]
    u = URBAN_SHARE.get(country, 0.6)
    w = [u * .40, u * .25, u * .35, (1 - u) * .45, (1 - u) * .55]
    if sector in _RURAL_SECTORS:
        f = _RURAL_SECTORS[sector]
        w = [w[0] / f, w[1], w[2], w[3] * f, w[4] * f]
    elif sector in _CITY_SECTORS:
        f = _CITY_SECTORS[sector]
        w = [w[0] * f, w[1] * f, w[2], w[3] / f, w[4] / f]
    if occupation in ("Retired farmer", "Shepherd", "Smallholder farmer", "Desert livestock herder"):
        w = [0.02, 0.03, 0.10, 0.30, 0.55]
    return random.choices(SETTLEMENTS, weights=w, k=1)[0]


# ---- 3c. Life stage ----
# (label, min_age, max_age, base weight)
LIFE_STAGES = [
    ("Student, lives with parents or family", 18, 26, 3.0),
    ("Student, lives in a shared flat or dorm", 18, 30, 2.5),
    ("Young adult, single, lives alone or with flatmates", 20, 36, 3.0),
    ("Young adult, still lives with parents", 18, 34, 2.5),
    ("In a relationship, no children", 22, 50, 3.0),
    ("Newly married or recently moved in with a partner", 23, 40, 2.0),
    ("Parent of a baby or toddler", 22, 46, 2.5),
    ("Parent of school-age children", 27, 55, 3.5),
    ("Parent of teenagers", 35, 62, 2.5),
    ("Single parent", 22, 58, 1.3),
    ("Divorced or separated, rebuilding routines", 30, 70, 1.0),
    ("Caring for an elderly or ill family member", 30, 72, 1.2),
    ("Empty nester, children have moved out", 45, 75, 2.0),
    ("Grandparent who helps with grandchildren", 50, 80, 1.5),
    ("Widowed, lives alone", 55, 80, 0.8),
    ("Recently relocated to a new city or country for work or study", 20, 50, 1.2),
    ("Approaching retirement", 55, 67, 1.5),
    ("Retired", 60, 80, 2.5),
    ("Long-term partner, child-free by choice", 30, 65, 1.0),
    ("Shares a multigenerational household", 18, 80, 0.8),
]
_LIVE_WITH_PARENTS_MULT = {"Southern Europe": 1.8, "South Asia": 2.0, "MENA": 2.0, "East Asia": 1.5,
                           "Southeast Asia": 1.6, "LATAM": 1.5, "Eastern Europe": 1.4, "Nordics": 0.4,
                           "Western Europe": 0.7, "North America": 0.8, "Oceania": 0.8}


def sample_life_stage(age, occupation, region):
    n = occupation.lower()
    cands, w = [], []
    for label, lo, hi, base in LIFE_STAGES:
        if not (lo <= age <= hi):
            continue
        if label.startswith("Student") and not (_is_student(occupation) or "apprentice" in n):
            continue
        if label == "Retired" and not n.startswith("retired") and age < 66:
            continue
        if n.startswith("retired") and label not in ("Retired", "Grandparent who helps with grandchildren",
                                                     "Widowed, lives alone", "Empty nester, children have moved out",
                                                     "Caring for an elderly or ill family member",
                                                     "Shares a multigenerational household",
                                                     "Divorced or separated, rebuilding routines"):
            continue
        b = base
        if "lives with parents" in label or "multigenerational" in label:
            b *= _LIVE_WITH_PARENTS_MULT.get(region, 1.0)
        if _is_student(occupation) and label.startswith("Student"):
            b *= 4
        if occupation in ("Stay-at-home parent", "Parent returning to work after a career break") and \
                not label.startswith(("Parent", "Single parent")):
            continue
        if occupation == "Unpaid carer for a family member" and label != "Caring for an elderly or ill family member":
            b *= 0.1
        cands.append(label)
        w.append(b)
    if not cands:
        return "In a relationship, no children" if age >= 22 else "Young adult, still lives with parents"
    return random.choices(cands, weights=w, k=1)[0]


# ---- 3d. Pre-sampled typing-style seed ----
# Canonical values (the same vocabulary as the generation prompt / style_norm.canon_style). Target
# marginals are flatter than in the base-grid profiles (where 'Standard' capitalization 55.0%, 'rare/functional'
# emoji 65.9% and 'medium complete' structure 71.6% dominated, and 37.5% of profiles fell into the 10
# most common 7-key combinations). Frequent/decorative emoji is held at the 5% that emoji rebalancing
# keeps for base-grid profiles, so extended-grid profiles do not need that step.
STYLE_SEED_TARGET = {
    "capitalization": {"Standard": .40, "all lowercase": .22, "first-word-only, no final period": .15,
                       "inconsistent": .17, "ALL-CAPS for emphasis": .06},
    "punctuation": {"standard": .34, "minimal (drops end punctuation)": .32, "ellipsis-heavy (...)": .13,
                    "excessive (!!!/???)": .09, "line-breaks instead of punctuation": .12},
    "emoji_use": {"none": .38, "rare/functional": .32, "frequent/decorative": .05, "emoticons only ( :) )": .15,
                  "kaomoji/stickers": .10},
    "message_structure": {"terse one-liners": .27, "medium, complete sentences": .35, "long/elaborate": .13,
                          "fragmented across several short lines": .25},
    "typo_tendency": {"clean/proofread": .36, "occasional uncorrected typos": .34, "phonetic spelling": .10,
                      "voice-to-text/autocorrect artifacts": .20},
    "abbreviation_habits": {"none": .35, "some": .65},
    "greeting_signoff": {"none": .55, "some": .45},
}


def _adjust(dist, mult):
    d = {k: v * mult.get(k, 1.0) for k, v in dist.items()}
    s = sum(d.values())
    return {k: v / s for k, v in d.items()}


def sample_style_seed(age, fluency, region):
    """Sample one canonical value per structured typing key, softly conditioned on age, digital
    fluency and region (kaomoji mainly East/Southeast Asia, lowercase skewed young, voice-to-text and
    proofread text skewed older, phonetic spelling and typos skewed low fluency)."""
    seed = {}
    for key, dist in STYLE_SEED_TARGET.items():
        m = {}
        if key == "capitalization":
            if age >= 55:
                m = {"Standard": 1.8, "all lowercase": .35, "first-word-only, no final period": .8, "ALL-CAPS for emphasis": 1.3}
            elif age < 30:
                m = {"all lowercase": 1.6, "Standard": .7}
        elif key == "emoji_use":
            m = {"kaomoji/stickers": 3.0 if region in ("East Asia", "Southeast Asia") else .35}
            if age >= 55:
                m.update({"emoticons only ( :) )": 1.6, "frequent/decorative": .6})
        elif key == "typo_tendency":
            if fluency == "Low":
                m = {"phonetic spelling": 2.2, "voice-to-text/autocorrect artifacts": 1.8, "clean/proofread": .45}
            elif fluency == "High":
                m = {"clean/proofread": 1.3, "phonetic spelling": .5}
            if age >= 55:
                m["voice-to-text/autocorrect artifacts"] = m.get("voice-to-text/autocorrect artifacts", 1) * 1.6
        elif key == "message_structure":
            if fluency == "Low":
                m = {"long/elaborate": .4, "terse one-liners": 1.5}
            if age >= 55:
                m["long/elaborate"] = m.get("long/elaborate", 1) * 1.5
        elif key == "abbreviation_habits" and age >= 60:
            m = {"some": .6}
        d = _adjust(dist, m)
        seed[key] = random.choices(list(d), weights=list(d.values()), k=1)[0]
    # light coherence rules
    if seed["emoji_use"] == "none" and seed["punctuation"] == "line-breaks instead of punctuation":
        pass  # line-breaks without emoji is fine
    if seed["capitalization"] == "ALL-CAPS for emphasis" and seed["message_structure"] == "long/elaborate" and age < 40:
        seed["message_structure"] = "medium, complete sentences"
    return seed


STYLE_SEED_KEYS = ("capitalization", "punctuation", "emoji_use", "abbreviation_habits",
                   "message_structure", "typo_tendency", "greeting_signoff")


def style_seed_canonical(seed):
    """Map the seed to the canonical buckets of style_norm.canon_style (for adherence checks)."""
    from personafactory.persona_bank.style_norm import canon_style
    s = dict(seed)
    s["abbreviation_habits"] = "None" if seed["abbreviation_habits"] == "none" else "uses some"
    s["greeting_signoff"] = "None" if seed["greeting_signoff"] == "none" else "has one"
    return canon_style(s)


# ===========================================================================
# 4. Prompt helpers
# ===========================================================================
# Rotating job_title examples. The base prompt uses four fixed examples, and 367 base-grid profiles copied
# "Tax accountant at a mid-size firm, SME clients" (plus 149 copies of the backend example).
JOB_TITLE_EXAMPLES = [
    ('"Electrician"', '"self-employed electrician, solar-panel installs"'),
    ('"Chartered accountant"', '"tax accountant at a mid-size firm, SME clients"'),
    ('"Backend developer"', '"backend developer, payments API at a logistics firm"'),
    ('"Rideshare driver"', '"part-time ride-hailing driver, family-owned compact car"'),
    ('"Nanny"', '"live-out nanny for two school-age kids, weekday afternoons"'),
    ('"Retired teacher"', '"retired primary teacher, volunteers at the local library"'),
    ('"Undergraduate student, nursing"', '"second-year nursing student, public university"'),
    ('"Street-food vendor"', '"grilled-corn stand owner near a bus terminal"'),
    ('"Civil engineer"', '"site engineer on municipal drainage projects"'),
    ('"Hairdresser"', '"salon hairdresser, colour specialist, rents a chair"'),
    ('"Data analyst"', '"junior data analyst, retail pricing team"'),
    ('"Social worker"', '"child-protection social worker, county office"'),
    ('"Farmer"', '"smallholder growing maize and beans on leased land"'),
    ('"Pharmacist"', '"pharmacist at an independent neighbourhood pharmacy"'),
    ('"Warehouse operative"', '"night-shift picker at a grocery distribution centre"'),
    ('"Graphic designer"', '"freelance designer, packaging for small food brands"'),
]


def job_title_examples(k=3):
    ex = random.sample(JOB_TITLE_EXAMPLES, k)
    return "; ".join(f"{a} -> {b}" for a, b in ex)


def style_seed_block(seed):
    abbr = ("uses a few concrete abbreviations or shortcuts (name them in abbreviation_habits)"
            if seed["abbreviation_habits"] == "some" else '"None"')
    greet = ("has a habitual greeting and/or sign-off (write it in greeting_signoff)"
             if seed["greeting_signoff"] == "some" else '"None"')
    return (
        "\n- TYPING-STYLE SEED (mandatory; build the whole style layer around it):"
        f"\n    capitalization = {seed['capitalization']}"
        f"\n    punctuation = {seed['punctuation']}"
        f"\n    emoji_use = {seed['emoji_use']}"
        f"\n    abbreviation_habits = {abbr}"
        f"\n    message_structure = {seed['message_structure']}"
        f"\n    typo_tendency = {seed['typo_tendency']}"
        f"\n    greeting_signoff = {greet}"
        "\n  These seeded values override the free choice offered in the chatting_style_structured list below. "
        "Start each chatting_style_structured value with the seeded canonical value (you may add a short "
        "specific detail after it, e.g. \"occasional uncorrected typos (doubled letters)\"). chatting_style, "
        "linguistic_quirks and example_message MUST visibly follow this seed."
    )
