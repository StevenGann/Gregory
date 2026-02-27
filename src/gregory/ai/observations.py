"""Extract and process AI observations from chat responses."""

import re

OBSERVATION_PATTERN = re.compile(
    r"\[OBSERVATION:\s*([^\]]*)\]",
    re.IGNORECASE,
)


def extract_observations(text: str) -> tuple[str, list[str]]:
    """Extract [OBSERVATION: ...] blocks from response text.

    Returns:
        (cleaned_response, list_of_observations)
    """
    observations: list[str] = []
    cleaned = OBSERVATION_PATTERN.sub(
        lambda m: (observations.append(m.group(1).strip()), "")[1],
        text,
    )
    return cleaned.strip(), observations
