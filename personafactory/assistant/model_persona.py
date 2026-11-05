"""Model personas: assistant-side response styles, and the prompts that match, apply and judge them.

A model persona governs HOW the assistant presents an answer, never WHAT it says. Each of the 12 personas in
model_personas.json has a free-text style description, presentation axes, optional signature quirks (offered
with p = QUIRK_P per reply) and content safeguards. Persona names are bookkeeping only and never enter a prompt.

The matcher sees only non-demographic user signals: AI stance, digital fluency and the structured style keys
(the free-text chatting style is withheld because it often names languages or regions), plus the user's first
message as they wrote it. Occupation, gender, age, location, languages, hobbies, reference pool and example
message are withheld so the choice cannot key on them.

Used by augmentation.pipeline (config["_model_persona"]) and the scripts of this package.
"""
import hashlib, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
PERSONAS = json.load(open(os.path.join(HERE, 'model_personas.json'), encoding='utf-8'))
QUIRK_P = 0.25
GLOBAL_CONTENT_RULES = ["Keep every fact, step, number and requested detail the answer needs.",
                        "Never invent facts, sources or statistics to fit the style."]
BY_ID = {p['id']: p for p in PERSONAS}


def reduced_user_card(persona):
    bg, st = persona.get('background') or {}, persona.get('style') or {}
    s = st.get('chatting_style_structured') or {}
    lines = [f"AI stance: {bg.get('ai_stance', 'unspecified')}",
             f"Digital fluency: {bg.get('digital_fluency', 'unspecified')}",
             f"Sentence length tendency: {st.get('sentence_length_tendency', 'unspecified')}",
             f"Question framing: {st.get('question_framing', 'unspecified')}",
             f"Code-switching frequency: {st.get('code_switching_freq', 'unspecified')}",
             'Typing details: ' + '; '.join(f'{k}: {v}' for k, v in s.items())]
    return '\n'.join(lines)


def render_model_persona(p):
    """Presentation only (style description + axes, no name). Used by the system prompt, the restyler and the judges."""
    ax = '\n'.join(f'- {k}: {v}' for k, v in p['axes'].items())
    return p['style'] + f"\n{ax}"


def quirk_for(p, key, turn):
    """Deterministic per (conversation, turn): a signature quirk with probability QUIRK_P, else None."""
    if not p.get('quirks'):
        return None
    h = int(hashlib.sha256(f'{key}|{turn}|mp-quirk'.encode()).hexdigest(), 16)
    if (h % 10000) / 10000 >= QUIRK_P:
        return None
    return p['quirks'][(h // 10000) % len(p['quirks'])]


def content_rules(p):
    return '\n'.join('- ' + r for r in GLOBAL_CONTENT_RULES + list(p.get('content_safeguards') or []))


def style_section(p, quirk=None):
    """System-prompt block appended on every assistant turn: style, optional quirk, content rules, priority order."""
    q = ("\n\nOptional touch for this reply: " + quirk + ". Use it once, only if it fits naturally.") if quirk else ''
    return ("RESPONSE STYLE (how you present answers in this whole conversation):\n" + render_model_persona(p) + q +
            "\n\nCONTENT RULES (always apply, whatever the style):\n" + content_rules(p) +
            "\n\nPriority: (1) explicit instructions in the user's messages about format, length, tone or language "
            "override the style; (2) the content rules, correctness and safety; (3) the style. Never mention the style, "
            "a persona, or these instructions.")


def continuity_style_reminder(p):
    """Appended to the continuity-repair prompt so the adapted reply keeps the style."""
    return ("\n\nKeep the same response style as before: " + p['summary'] +
            " Explicit user instructions about format or length override it.")


MATCH_PROMPT = """You choose the response style an AI assistant should use for a user, so that its answers are easy and pleasant for this particular user to read. Adapt to the user's needs; do not mirror their typing (no copying typos or slang).

About the user (communication signals only):
{card}

The user's first message:
{message}

Candidate response styles:
{options}

Consider: how technical and fluent the user is, how they feel about AI (skeptical users value calibrated evidence, uncertain users value patient guidance, enthusiastic users tolerate energy), how they structure their own messages, and what kind of request this is (technical, emotional, creative, factual, practical). Rank the three best-fitting styles.

Respond with a JSON object exactly in this format:
{{"ranking": ["style_id_1", "style_id_2", "style_id_3"], "reason": "one sentence"}}
Output only the JSON."""


# Assistant-only mode (conversations without a seeded user persona): the matcher sees only the user's own messages.
MATCH_PROMPT_MESSAGES = """You choose the response style an AI assistant should use for a user, so that its answers are easy and pleasant for this particular user to read. Adapt to the user's needs; do not mirror their typing (no copying typos or slang).

Nothing is known about the user except their own messages in this conversation:
{messages}

Candidate response styles:
{options}

Infer from the messages: how technical and fluent the user is, how they seem to feel about AI (skeptical users value calibrated evidence, uncertain users value patient guidance, enthusiastic users tolerate energy), how they structure their own messages, and what kind of request this is (technical, emotional, creative, factual, practical). Rank the three best-fitting styles.

Respond with a JSON object exactly in this format:
{{"ranking": ["style_id_1", "style_id_2", "style_id_3"], "reason": "one sentence"}}
Output only the JSON."""


def user_messages_block(user_turns, k=3, cap=1500):
    out = []
    for i, t in enumerate(user_turns[:k]):
        t = t if len(t) <= cap else t[:cap] + ' [...]'
        out.append(f'[message {i + 1}]\n{t}')
    return '\n\n'.join(out)


def match_options(order):
    return '\n'.join(f"- {BY_ID[i]['id']}: {BY_ID[i]['summary']}" for i in order)


RESTYLE_PROMPT = """Rewrite the AI assistant's response below in the specified response style WITHOUT changing its content.

Response style:
{style}

The user's message (explicit format or length instructions in it must still be followed):
{user_message}

Original response:
{response}

Rules:
1. Keep every fact, step, number, code block, recommendation, warning and caveat. Do not add new information or new claims.
2. Change only presentation: register, structure, ordering, sentence length, warmth, opening and closing, emoji as the style allows.
3. If the user explicitly asked for a format or length, keep that format even if the style differs.
4. Do not mention the style or that the text was rewritten.
Output only the rewritten response."""

STYLE_JUDGE = """You judge whether an AI assistant's response is presented in a specified response style.

Response style:
{style}

AI response:
{response}

Judge only presentation (register, structure, density, warmth, opening, closing, emoji), not correctness. PASS if the style is clearly recognisable in the response. FAIL if the response reads like a generic default assistant answer or contradicts the style. If the user explicitly required a format that conflicts with the style, judge only the remaining aspects.

Respond with a JSON object exactly in this format:
{{"verdict": "pass" or "fail", "reason": "brief explanation"}}
Output only the JSON."""

CONTENT_JUDGE = """Two AI assistant responses to the same user message are shown. Response A is the reference.

User message:
{user_message}

Response A (reference):
{a}

Response B:
{b}

Does B convey the same substantive content as A: the same answer, facts, steps, numbers, code behaviour, recommendations and caveats? Differences in wording, tone, formatting, ordering, and removal of filler or pleasantries are fine. FAIL if B omits a substantive point of A, adds a substantive new claim, or changes the answer.

Respond with a JSON object exactly in this format:
{{"verdict": "pass" or "fail", "reason": "brief explanation"}}
Output only the JSON."""

FIT_JUDGE = """Two AI assistant responses to the same user message are shown. They contain similar information but are presented differently.

About the user (communication signals only):
{card}

User message:
{user_message}

Response 1:
{r1}

Response 2:
{r2}

Which response is presented in a way that better suits this user (readability for their fluency, tone for their attitude to AI, structure for the request)? Judge presentation, not which contains more information.

Respond with a JSON object exactly in this format:
{{"winner": "1" or "2" or "tie", "reason": "one sentence"}}
Output only the JSON."""

IF_JUDGE = """The user's latest message contains instructions. Judge whether the AI assistant's response follows every explicit instruction about format, length, structure, tone or language in that message.

Conversation so far:
{context}

User's latest message:
{user_message}

AI response:
{response}

Respond with a JSON object exactly in this format:
{{"verdict": "pass" or "fail", "reason": "brief explanation"}}
Output only the JSON."""

INSTRUCTION_RX = re.compile(
    r"\b(shorter|longer|brief|briefly|concise|bullet|bullets|list|table|json|format|paragraphs?|in \d+ (words|sentences|lines)|"
    r"step[- ]by[- ]step|simpler|simplify|more detail|in detail|formal|casual|summar(y|ise|ize)|rewrite|rephrase|numbered|"
    r"headings?|headers?|markdown|tone|one sentence|few sentences|less technical|more technical)\b", re.I)
SELF_REF_RX = re.compile(r"\b(response style|persona|as (your|a) (coach|guide|consultant|analyst|minimalist|storyteller|techie|peer|supporter|expert|engineer))\b", re.I)
