"""Very small prompt moderation layer: blocklist plus artist-imitation heuristics."""
import re
from typing import Tuple

BLOCKED_TERMS = (
    "explicit sexual",
    "hate speech",
    "self harm",
)

PROTECTED_ARTIST_PATTERN = re.compile(
    r"\b(in the (exact )?(style|voice) of|sounds exactly like)\b", re.IGNORECASE
)

MAX_PROMPT_LENGTH = 2000


def review_prompt(text: str) -> Tuple[str, str]:
    """Return ``(state, reason)`` where state is ``allowed`` or ``blocked``."""
    lowered = text.lower()
    for term in BLOCKED_TERMS:
        if term in lowered:
            return "blocked", f"blocked term: {term}"
    if PROTECTED_ARTIST_PATTERN.search(text):
        return "blocked", "artist imitation"
    return "allowed", ""
