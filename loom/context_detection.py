"""
Context detection for Quads + Properties schema.
Detects context, temporal, and scope qualifiers from natural language.
"""

import re

# Context detection patterns
CONTEXT_PATTERNS = {
    "scientific": [
        r"\b(?:scientifically|biologically|chemically|physically)\b",
        r"\b(?:in\s+)?(?:science|biology|chemistry|physics|nature)\b",
        r"\b(?:species|genus|taxonomy|classification)\b",
        r"\b(?:molecule|atom|cell|organism)\b",
    ],
    "domestic": [
        r"\b(?:pet|pets|domestic|domesticated)\b",
        r"\b(?:at\s+home|in\s+the\s+house|indoors)\b",
        r"\b(?:house\s*(?:cat|dog)|indoor\s+(?:cat|dog))\b",
    ],
    "cultural": [
        r"\b(?:in\s+)?(?:\w+\s+)?culture\b",
        r"\b(?:traditionally|culturally)\b",
        r"\b(?:mythology|folklore|legend)\b",
    ],
    "temporal": [
        r"\b(?:in\s+the\s+)?(?:past|history|historically)\b",
        r"\b(?:nowadays|currently|today|modern)\b",
        r"\b(?:in\s+the\s+)?(?:\d{4}s?|century)\b",
    ],
    "geographic": [
        r"\b(?:in\s+)?(?:Africa|Asia|Europe|America|Australia)\b",
        r"\b(?:tropical|arctic|desert|marine|ocean)\b",
    ],
}


def detect_context(text: str) -> str:
    """
    Detect context from natural language cues.

    Returns context string or 'general' if no specific context detected.
    """
    text_lower = text.lower()

    for ctx, patterns in CONTEXT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return ctx

    return "general"


def detect_temporal(text: str) -> str:
    """
    Detect temporal qualifier from text.

    Returns: 'always', 'sometimes', 'past', 'future', 'currently'
    """
    text_lower = text.lower()

    if re.search(r"\b(?:always|invariably|universally)\b", text_lower):
        return "always"
    if re.search(r"\b(?:sometimes|occasionally|often|usually|typically)\b", text_lower):
        return "sometimes"
    if re.search(r"\b(?:used\s+to|formerly|in\s+the\s+past|historically|once)\b", text_lower):
        return "past"
    if re.search(r"\b(?:will|going\s+to|in\s+the\s+future|eventually)\b", text_lower):
        return "future"
    if re.search(r"\b(?:currently|now|nowadays|today|presently)\b", text_lower):
        return "currently"

    return "always"  # Default


def detect_scope(text: str) -> str:
    """
    Detect scope qualifier from text.

    Returns: 'universal', 'typical', 'specific'
    """
    text_lower = text.lower()

    if re.search(r"\b(?:all|every|each|any)\b", text_lower):
        return "universal"
    if re.search(r"\b(?:most|many|typically|usually|generally)\b", text_lower):
        return "typical"
    if re.search(r"\b(?:some|certain|specific|particular|this|that)\b", text_lower):
        return "specific"

    return "universal"  # Default
