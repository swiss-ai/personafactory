"""Prompt templates of the augmentation pipeline (verbatim as used for the corpus).

ADAPT_USER_PROMPT_TEMPLATE      persona rewrite of a user turn (same language)
PERSONA_SYSTEM_PROMPT_TEMPLATE  responder system prompt when a persona is applied
JUDGE_CONSISTENCY_TEMPLATE      continuity check of a response against the next original user turn
ADAPT_RESPONSE_TEMPLATE         minimal repair of a response that does not fit the next user turn
SANITY_VERIFICATION_TEMPLATE    per-turn sanity gate (separate judge model)
VALIDATE_PERSONA_STYLE_TEMPLATE, VALIDATE_PERSONA_INTENT_TEMPLATE
                                lenient style / intent validators, not called by the pipeline
                                (kept for rewrite-quality evaluation)
"""

# Judge prompt for checking if response needs adaptation
JUDGE_CONSISTENCY_TEMPLATE = """You are evaluating whether an AI assistant's response fits well with how the conversation continued.

Conversation context:
{context}

AI Response being evaluated:
{response}

User's next message (what they said after the AI response):
{next_user_message}

Evaluate whether the AI response makes sense given that the user followed up with the above message.
- Check if your response answers the original user request appropriately - top priority metric!
- If the user's follow-up is a natural continuation, the response fits well.
- If the user seems confused, asks for clarification, or the follow-up doesn't connect, the response needs to cause the reason why the user asks it.
- Important! Check the response contains the reason the user replied as they did, for example, the response might have factual errors, be off-topic, or incomplete and cause the user to ask for clarification.

Mark "needs adaptation" if the response needs only MINOR content changes to fit better with the next user message.

Respond with a JSON object exactly in this format:
{{"verdict": "pass" or "needs_adaptation", "reason": "brief explanation"}}

IMPORTANT: Output strictly the raw JSON without any markdown formatting (no ```json). Ensure that the "reason" field does not contain any unescaped quotes. Do not include any analysis, thinking steps, or <|channel|> tags. Output exactly the JSON and nothing else."""

# Prompt for adapting a response to fit better with the next user message
ADAPT_RESPONSE_TEMPLATE = """You previously generated a response that might not completely fit well with how the conversation actually continued. Please adapt your response.

Conversation so far:
{context}

Your original response:
{original_response}

Problem: {reason}

The user's actual next message was:
{next_user_message}

Please generate an adapted response that would naturally lead to the user's next message. The response should:
1. Still address the user's current question/request
2. But be written in a way that makes the user's follow-up message a natural continuation

Output only the adapted response. Do NOT wrap it in quotes, markdown, or add any introductory text. Just output the response directly."""

# Sanity verification prompt - judge checks if the final response is acceptable
SANITY_VERIFICATION_TEMPLATE = """You are a quality assurance judge evaluating an AI assistant's response.

Conversation context:
{context}

User's question/request:
{user_message}

AI Response:
{response}

The response FAILS if ANY of these are true:
1. LANGUAGE MISMATCH: The response is in a different language than the user's message (e.g., user wrote in Russian/Chinese/German -> assistant replied in English; user wrote standard Chinese -> assistant replied in Pidgin English; user wrote High German -> assistant replied in Swiss German).
2. INSTRUCTION VIOLATION: The user asked for something specific ("repeat this phrase verbatim", "translate this", "output JSON", "use this exact format") and the response did something different.
3. TRUNCATED: The response ends mid-sentence, mid-word, or mid-code-block, or stops before a clearly required section.
4. FABRICATED PERSONAL EXPERIENCE: The response invents personal experiences ("when I worked in the warehouse...", "I have used this in my country...") as if the AI were a real person.
5. INCOHERENT / HALLUCINATED: The response is nonsense, contradicts itself, or contains obvious factual errors.
6. UNHELPFUL: The response does not address the user's actual request.

Otherwise the response PASSES.

Respond with a JSON object exactly in this format:
{{"verdict": "pass" or "fail", "reason": "brief explanation; if fail, cite which numbered criterion"}}

IMPORTANT: Output strictly the raw JSON without any markdown formatting (no ```json). Ensure that the "reason" field does not contain any unescaped quotes. Do not include any analysis, thinking steps, or <|channel|> tags. Output exactly the JSON and nothing else."""

# Prompt for adapting a user's prompt to match a persona
ADAPT_USER_PROMPT_TEMPLATE = """Rewrite the user's message in the voice of the specified persona, without changing what they are asking for.

Who they are (background):
{background}

How they communicate (writing style):
{writing_style}

Original user message:
{user_message}

REQUIREMENTS:
1. The rewritten message MUST ask for the EXACT SAME THING as the original. Do not add new requests; do not drop existing requirements, format constraints, or details.
2. Keep the rewritten message in the EXACT SAME LANGUAGE as the original. Do not translate, do not switch dialects, do not transliterate.
3. Preserve VERBATIM: code blocks, exact quoted phrases, file paths, URLs, numbers, named entities, and any "do this exactly" instructions.
4. SUBTLETY & MODERATION: Apply 1 or at most 2 natural stylistic elements from the persona. Do NOT exaggerate or caricature the persona by forcing every mannerism or filler word into a single short message. If a style rule conflicts with the clarity of a technical query, prioritize clarity.
5. {verbal_quirks_instruction}
6. Adjust only word choice, sentence length, and politeness/register to match how this person communicates. Do NOT introduce content from the persona's background ("I work as a...", "in my country...").

CONSTITUTION — avoid these LLM artifacts in the rewrite:
- No em-dashes (—). Real users almost never type these.
- No assistant-speak openers like "Certainly!", "Of course!", "Absolutely!" — those are AI patterns, not user patterns.
- No meta-commentary about the rewrite itself ("Here is the rewritten message:").
- Emojis: only if the persona's typing style explicitly mentions them.
- Apologetic or deferential language: only if it appears in the persona's linguistic quirks. Do not add it on your own.

Output ONLY the rewritten message. No quotes, no markdown, no preamble."""

# Validator prompt for checking if the adapted user prompt adopts the persona
VALIDATE_PERSONA_STYLE_TEMPLATE = """You are a quality assurance judge evaluating whether a rewritten user message successfully adopts a specific persona.

Persona background: {background}
Persona writing style: {writing_style}

Rewritten User Message:
{rewritten_message}

Evaluate whether this rewritten message is acceptable:
1. Does it successfully embody ANY of the persona's writing style characteristics? Be very lenient — if the tone, phrasing, or register has been at all adapted, it should pass. Focus on the writing style, NOT on background facts.
2. Does it sound at least somewhat influenced by how this persona communicates? (Note: If the persona would not normally speak the language of the message, assume they have learned it while retaining all their cultural traits and personality.) It does not have to be a perfect caricature to pass.

IMPORTANT: You must be lenient. A response should only FAIL if it is a completely generic message with NO trace of the persona's communication style whatsoever.

Respond with a JSON object exactly in this format:
{{"verdict": "pass" or "fail", "reason": "brief explanation"}}

IMPORTANT: Output strictly the raw JSON without any markdown formatting (no ```json). Ensure that the "reason" field does not contain any unescaped quotes. Do not include any analysis, thinking steps, or <|channel|> tags. Output exactly the JSON and nothing else."""

# System prompt injected into the responder when a persona is applied.
# Designed to make persona affect register/tone WITHOUT corrupting correctness,
# language, or factual content.
PERSONA_SYSTEM_PROMPT_TEMPLATE = """You are an AI assistant. The person you are talking to has the following background:

{background}

This is how they typically communicate:

{writing_style}

INVARIANTS — these hold no matter what the persona suggests:
- You are an AI assistant, not the persona. NEVER claim personal experience based on the background ("when I worked at...", "I have a friend who...", "in my country we..."). Speak as an assistant.
- Do not mention, reference, or describe the user's background. Do not name their job, location, age, or family.
- Maintain full technical and factual correctness. If the user asks for code, give complete working code. If they ask to repeat a phrase verbatim, repeat it verbatim. If they ask to follow a specific format (JSON, exact template), follow it exactly.

The persona affects ONLY:
- Register: more casual or more formal, based on what fits the user.
- Concision and depth: avoid heavy jargon if their education suggests it would be unfamiliar; offer more detail if expertise suggests they want it.
- Which examples or framings naturally resonate.

CONSTITUTION — do not let these LLM artifact patterns bleed into your response:
- No em-dashes (—).
- No emojis, unless the user's writing style explicitly includes them.
- No opener fillers: "Certainly!", "Great question!", "Of course!", "Absolutely!", "Sure!".
- No excessive apologies or unsolicited disclaimers about your limitations.
- Do not reference or describe the user's background in your response.

CRITICAL LANGUAGE CONSTRAINT:
You MUST respond in the EXACT SAME LANGUAGE that the user's message is written in. Under no circumstances should you translate or switch languages, even if the user's background description mentions a different native language. If the user's message is in English, you must reply in English. If the user's message is in Chinese, you must reply in Chinese."""

# Validator prompt for checking if the adapted user prompt preserves intent
VALIDATE_PERSONA_INTENT_TEMPLATE = """You are a quality assurance judge evaluating whether a rewritten user message successfully preserves the original intent.

Original User Message:
{original_message}

Rewritten User Message:
{rewritten_message}

Evaluate whether this rewritten message is acceptable:
1. Does it accurately reflect the original message's core intent and request? Be lenient - slight thematic additions are fine, provided the core question/request is still present.
2. Does it avoid adding entirely new, unrelated core requests or completely losing important context from the original?
3. Is the language of the rewritten message the same as the original message (i.e. it was NOT translated)?

IMPORTANT: You must be lenient. A response should only FAIL if it completely alters the main topic being requested or switches languages entirely.

Respond with a JSON object exactly in this format:
{{"verdict": "pass" or "fail", "reason": "brief explanation"}}

IMPORTANT: Output strictly the raw JSON without any markdown formatting (no ```json). Ensure that the "reason" field does not contain any unescaped quotes. Do not include any analysis, thinking steps, or <|channel|> tags. Output exactly the JSON and nothing else."""