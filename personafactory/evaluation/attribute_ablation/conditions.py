"""Neutral base persona and the 17-condition single-attribute ablation matrix (baseline + 16 conditions in 8 families).

Each non-baseline condition varies exactly one attribute. CONDITIONS holds clones of NEUTRAL_PERSONA with only the
target field(s) modified; run_ablation.py applies the same single-attribute overrides to a matched real persona
(apply_ablation_override), and uses this module for the condition ids, families and labels.
The occ_tech / occ_manual pair is the only exception: occupation is paired with one coherent hobby so the persona
is plausible.

Run `python -m personafactory.evaluation.attribute_ablation.conditions` to print the matrix.
"""

import copy

# ---------------------------------------------------------------------------
# Neutral base persona
# ---------------------------------------------------------------------------
# Maximally non-committal:  US English speaker, age 35, medium everything,
# Pragmatic AI stance, office worker, no distinctive quirks.
NEUTRAL_PERSONA = {
    "background": {
        "region": "North America",
        "country": "United States",
        "sub_region": "Midwest",
        "occupation": "Office worker",
        "education": {
            "level": "Some college",
            "field_of_study": "General Studies",
            "institution_type": "Community college",
        },
        "age": 35,
        "native_language": "English",
        "dialect": "",
        "hobbies_interests": ["Reading", "Cooking"],
        "gender": "Male",
        "ai_stance": "Pragmatic",
        "digital_fluency": "Medium",
    },
    "style": {
        "sentence_length_tendency": "Medium",
        "question_framing": "Direct",
        "native_language_error_patterns": "",
        "code_switching_freq": "Low",
        "code_switching_type": "",
        "reference_pool": [],
        "typing_style": "Standard punctuation and capitalisation.",
        "linguistic_quirks": [],
    },
    "character_description": (
        "An average American office worker in their mid-thirties with no strong "
        "stylistic tendencies or distinctive communication patterns."
    ),
}


def _deep_merge(base, overrides):
    """Recursively merge `overrides` into a deep copy of `base`."""
    result = copy.deepcopy(base)
    for key, val in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


def _patch(overrides):
    """Deep-clone NEUTRAL_PERSONA and apply nested overrides."""
    return _deep_merge(NEUTRAL_PERSONA, overrides)


# ---------------------------------------------------------------------------
# 17-condition matrix
# None = baseline (no persona injected at all)
# ---------------------------------------------------------------------------
CONDITIONS = {
    # --- Baseline -----------------------------------------------------------
    "baseline": None,

    # --- digital_fluency (BackgroundLayer) ----------------------------------
    "digital_low":  _patch({"background": {"digital_fluency": "Low"}}),
    "digital_high": _patch({"background": {"digital_fluency": "High"}}),

    # --- sentence_length_tendency (StyleLayer) ------------------------------
    "sent_short": _patch({"style": {"sentence_length_tendency": "Short/Fragmented"}}),
    "sent_long":  _patch({"style": {"sentence_length_tendency": "Long/Elaborate"}}),

    # --- ai_stance (BackgroundLayer) ----------------------------------------
    "stance_skeptical":    _patch({"background": {"ai_stance": "Skeptical"}}),
    "stance_enthusiastic": _patch({"background": {"ai_stance": "Enthusiastic"}}),

    # --- age (BackgroundLayer) ----------------------------------------------
    "age_young": _patch({"background": {"age": 20}}),
    "age_old":   _patch({"background": {"age": 68}}),

    # --- gender (BackgroundLayer) -------------------------------------------
    "gender_male":   _patch({"background": {"gender": "Male"}}),
    "gender_female": _patch({"background": {"gender": "Female"}}),

    # --- education (BackgroundLayer.education) ------------------------------
    "edu_low": _patch({
        "background": {
            "education": {
                "level": "No formal education",
                "field_of_study": "",
                "institution_type": "None",
            }
        }
    }),
    "edu_high": _patch({
        "background": {
            "education": {
                "level": "Doctoral degree",
                "field_of_study": "Computer Science",
                "institution_type": "Elite / Research university",
            }
        }
    }),

    # --- occupation (BackgroundLayer) - paired with one coherent hobby ------
    "occ_tech": _patch({
        "background": {
            "occupation": "Software Engineer",
            "hobbies_interests": ["Programming", "Open-source projects", "Reading"],
        }
    }),
    "occ_manual": _patch({
        "background": {
            "occupation": "Manual laborer",
            "hobbies_interests": ["Gardening", "Fishing", "Cooking"],
        }
    }),

    # --- hobbies_interests (BackgroundLayer) --------------------------------
    "hobbies_tech":    _patch({
        "background": {
            "hobbies_interests": ["Gaming", "AI tools", "Programming", "Online communities"],
        }
    }),
    "hobbies_outdoor": _patch({
        "background": {
            "hobbies_interests": ["Hiking", "Bird watching", "Gardening", "Camping"],
        }
    }),
}

# Attribute family groupings (the eight families of the per-attribute table).
CONDITION_FAMILIES = {
    "baseline": ["baseline"],
    "digital_fluency": ["digital_low", "digital_high"],
    "sentence_length": ["sent_short", "sent_long"],
    "ai_stance": ["stance_skeptical", "stance_enthusiastic"],
    "age": ["age_young", "age_old"],
    "gender": ["gender_male", "gender_female"],
    "education": ["edu_low", "edu_high"],
    "occupation": ["occ_tech", "occ_manual"],
    "hobbies": ["hobbies_tech", "hobbies_outdoor"],
}

# Human-readable labels.
CONDITION_LABELS = {
    "baseline":            "Baseline (no persona)",
    "digital_low":         "Digital fluency: Low",
    "digital_high":        "Digital fluency: High",
    "sent_short":          "Sentence length: Short/Fragmented",
    "sent_long":           "Sentence length: Long/Elaborate",
    "stance_skeptical":    "AI stance: Skeptical",
    "stance_enthusiastic": "AI stance: Enthusiastic",
    "age_young":           "Age: Young (20)",
    "age_old":             "Age: Old (68)",
    "gender_male":         "Gender: Male",
    "gender_female":       "Gender: Female",
    "edu_low":             "Education: No formal",
    "edu_high":            "Education: Doctoral",
    "occ_tech":            "Occupation: Software Engineer",
    "occ_manual":          "Occupation: Manual laborer",
    "hobbies_tech":        "Hobbies: Tech/Gaming",
    "hobbies_outdoor":     "Hobbies: Outdoor/Nature",
}


if __name__ == "__main__":
    print("Total conditions: {}".format(len(CONDITIONS)))
    print()
    for cid, persona in CONDITIONS.items():
        label = CONDITION_LABELS.get(cid, cid)
        if persona is None:
            print("  [{}] {}  ->  No persona".format(cid, label))
        else:
            bg = persona["background"]
            sty = persona["style"]
            print(
                "  [{cid}] {label}\n"
                "    digital_fluency={df}, ai_stance={ai}, age={age}, "
                "gender={g}, edu={edu}, occ={occ}, "
                "sent={sent}, hobbies={h}".format(
                    cid=cid, label=label,
                    df=bg["digital_fluency"], ai=bg["ai_stance"],
                    age=bg["age"], g=bg["gender"],
                    edu=bg["education"]["level"],
                    occ=bg["occupation"],
                    sent=sty["sentence_length_tendency"],
                    h=bg["hobbies_interests"],
                )
            )
    print()
    print("Condition families:")
    for family, members in CONDITION_FAMILIES.items():
        print("  {}: {}".format(family, members))
