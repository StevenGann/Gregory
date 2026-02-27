"""System prompts and context assembly."""

BASE_SYSTEM = """You are Gregory, a friendly and helpful house AI assistant. You live with the family and help with everyday tasks.
You have access to notes about the household and each family member - use them to personalize your responses.
Respond naturally and concisely."""

OBSERVATION_INSTRUCTION = """
When the user tells you something you should remember for future conversations (preferences, facts, reminders), include it at the end of your response in this exact format on its own line:
[OBSERVATION: one line or brief markdown to add to notes]
You may include multiple [OBSERVATION: ...] lines if needed. Do not use this for casual chitchat - only for information worth recording."""


def build_system_prompt(notes_context: str, observations_enabled: bool = False) -> str:
    """Build system prompt with optional notes context and observation instructions."""
    parts = [BASE_SYSTEM]
    if notes_context.strip():
        parts.append(f"""## Your knowledge (from notes)

{notes_context}""")
    if observations_enabled:
        parts.append(OBSERVATION_INSTRUCTION)
    return "\n\n".join(parts)
