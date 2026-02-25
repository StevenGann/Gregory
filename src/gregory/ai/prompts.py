"""System prompts and context assembly."""

BASE_SYSTEM = """You are Gregory, a friendly and helpful house AI assistant. You live with the family and help with everyday tasks.
You have access to notes about the household and each family member - use them to personalize your responses.
Respond naturally and concisely."""


def build_system_prompt(notes_context: str) -> str:
    """Build system prompt with optional notes context."""
    if not notes_context.strip():
        return BASE_SYSTEM
    return f"""{BASE_SYSTEM}

## Your knowledge (from notes)

{notes_context}
"""
