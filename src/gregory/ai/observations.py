"""Extract and process AI observations from chat responses."""

import re
from dataclasses import dataclass

OBSERVATION_PATTERN = re.compile(r"\[OBSERVATION:\s*([^\]]*)\]", re.IGNORECASE)
GREGORY_NOTE_PATTERN = re.compile(r"\[GREGORY_NOTE:\s*([^\]]*)\]", re.IGNORECASE)
HOUSEHOLD_NOTE_PATTERN = re.compile(r"\[HOUSEHOLD_NOTE:\s*([^\]]*)\]", re.IGNORECASE)
# [NOTE:entity_id: content] e.g. [NOTE:dog: loves treats]
ENTITY_NOTE_PATTERN = re.compile(
    r"\[NOTE:\s*([a-zA-Z0-9_-]+):\s*([^\]]*)\]",
    re.IGNORECASE,
)


@dataclass
class Observation:
    """A single observation with target and content."""

    target: str  # "user", "gregory", "household", or entity_id
    content: str


def extract_observations(text: str) -> tuple[str, list[Observation]]:
    """Extract observation blocks from response text.

    [OBSERVATION: x] -> user
    [GREGORY_NOTE: x] -> gregory
    [HOUSEHOLD_NOTE: x] -> household
    [NOTE:entity: x] -> entity

    Returns:
        (cleaned_response, list_of_observations)
    """
    observations: list[Observation] = []

    def repl_obs(m):
        observations.append(Observation("user", m.group(1).strip()))
        return ""

    def repl_gregory(m):
        observations.append(Observation("gregory", m.group(1).strip()))
        return ""

    def repl_household(m):
        observations.append(Observation("household", m.group(1).strip()))
        return ""

    def repl_entity(m):
        observations.append(Observation(m.group(1).strip().lower(), m.group(2).strip()))
        return ""

    cleaned = OBSERVATION_PATTERN.sub(repl_obs, text)
    cleaned = GREGORY_NOTE_PATTERN.sub(repl_gregory, cleaned)
    cleaned = HOUSEHOLD_NOTE_PATTERN.sub(repl_household, cleaned)
    cleaned = ENTITY_NOTE_PATTERN.sub(repl_entity, cleaned)
    return cleaned.strip(), observations
