"""Pydantic schema of one persona profile (background layer + style layer).

The JSON schema of `Persona` (base grid) or `PersonaExtended` (extended grid and style extension) is
embedded in the generation prompt and used for guided decoding; use `json_schema()` to get it.
"""
import json

from pydantic import BaseModel, Field
from typing import Literal, List, Optional

class Education(BaseModel):
    level: Literal[
        "No formal education",
        "Primary school",
        "Some high school",
        "High school diploma",
        "Vocational / Trade training",
        "Some college",
        "Associate's degree",
        "Bachelor's degree",
        "Master's degree",
        "Doctoral degree",
        "Professional degree",
    ]
    field_of_study: str = ""  # empty string if not applicable (e.g. no formal education)
    institution_type: Literal[
        "None",
        "Public school",
        "Private school",
        "Vocational / Trade school",
        "Community college",
        "Public university",
        "Private university",
        "Elite / Research university",
        "Online / Distance learning",
    ] = "None"

class BackgroundLayer(BaseModel):
    region: str
    country: str
    sub_region: str
    occupation: str  # actual profession, seeded from the curated list (e.g. "diesel mechanic")
    sector: str = ""  # coarse sector grouping for balancing / analysis (e.g. "Skilled trades")
    job_title: str = ""  # concrete detail: seniority + specialisation + employer/context
    education: Education
    age: int = Field(ge=18, le=80)
    main_language: str = ""   # STANDARD canonical language name only (e.g. "German", "Mandarin Chinese", "Romansh"), no qualifiers/parentheses
    native_language: str      # fuller value the model chose (may note the specific variety)
    dialect: str              # CONCISE variant/region label only (e.g. "Austrian", "Odesa surzhyk"), not a description
    hobbies_interests: List[str]
    gender: Literal["Male", "Female", "Non-binary"]
    ai_stance: Literal["Pragmatic", "Skeptical", "Enthusiastic", "Naive"]
    digital_fluency: Literal["High", "Medium", "Low"]
    llm_user_segment: str = "core"  # "core" (plausible LLM user) | "underrepresented" (low-fluency minority; route to simple prompts downstream)

class ChattingStyle(BaseModel):
    # This docstring becomes the pydantic "description" in the JSON schema embedded in the generation prompt.
    """Structured decomposition of chatting/typing behaviour.

    Generated IN ADDITION to the flat one-sentence `chatting_style` so downstream
    augmentation can later be compared: structured keys vs. free text. Values are
    free strings; the generation prompt suggests a canonical vocabulary for the
    categorical axes.
    """
    capitalization: str = ""       # Standard | all lowercase | first-word-only (no final period) | inconsistent | ALL-CAPS emphasis
    punctuation: str = ""          # standard | minimal | ellipsis-heavy | excessive | emoji/line-breaks as punctuation
    emoji_use: str = ""            # none | rare/functional | frequent/decorative | emoticons only | kaomoji/stickers
    abbreviation_habits: str = ""  # concrete shortcuts actually used, or "None"
    message_structure: str = ""    # terse one-liners | medium complete | long/elaborate | fragmented across lines
    typo_tendency: str = ""        # clean | occasional uncorrected | phonetic | voice-to-text/autocorrect artifacts
    greeting_signoff: str = ""     # how they open/close a message, or "None"

class StyleLayer(BaseModel):
    sentence_length_tendency: Literal["Short/Fragmented", "Medium", "Long/Elaborate"]
    question_framing: Literal["Direct", "Indirect", "Contextualizing"]
    native_language_error_patterns: str
    code_switching_freq: Literal["None", "Low", "Medium", "High"]
    code_switching_type: str
    reference_pool: List[str]
    chatting_style: str  # flat one-sentence description (free-text representation)
    chatting_style_structured: Optional[ChattingStyle] = None  # structured representation
    example_message: str = ""  # verbatim sample of a short message this persona would actually type
    chatbot_language_pref: str = ""  # how they'd address an AI chatbot (e.g. "English for coding, Ukrainian for everyday")
    linguistic_quirks: List[str]

class Persona(BaseModel):
    id: str
    generator_model: str
    background: BackgroundLayer
    style: StyleLayer
    character_description: str


# ---------------------------------------------------------------------------
# Extended grid (generate_bank.py --grid extended) and style extension (extend_style.py). The classes above
# are unchanged, so the base-grid prompt and guided-decoding schema are not affected. The two additional
# background fields are seeded and overwritten after generation like the other seeded fields; their defaults
# keep base-grid rows valid under the extended model. The released bank does not keep them
# (assemble_bank.py drops them).
# ---------------------------------------------------------------------------
class BackgroundLayerExtended(BackgroundLayer):
    settlement_type: str = ""  # seeded: Major city | Suburb or commuter town | Mid-size town | Small town | Village or rural area | Peri-urban fringe of the city
    life_stage: str = ""       # seeded household / life-stage label (e.g. "Parent of teenagers", "Retired")


class PersonaExtended(Persona):
    background: BackgroundLayerExtended


# Optional renaming of the extended classes in the JSON schema that is embedded in the prompt and used for guided
# decoding (empty: the class names are used as they are).
_SCHEMA_NAMES = {}


def json_schema(model=Persona):
    """JSON schema of `model` exactly as embedded in the generation prompts."""
    schema = model.model_json_schema()
    if model is not PersonaExtended:
        return schema
    text = json.dumps(schema)
    for ours, released in _SCHEMA_NAMES.items():
        text = text.replace(f'"{ours}"', f'"{released}"').replace(f'/{ours}"', f'/{released}"')
    return json.loads(text)
