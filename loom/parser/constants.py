"""
Constants used by the parser module.

Note: RELATION_PATTERNS is now generated dynamically from relations.py
to maintain a single source of truth for all verb/relation mappings.
"""

# Import dynamically generated relation patterns
from .relations import RELATION_PATTERNS

# Correction indicators
CORRECTION_WORDS = [
    "no,", "no ", "wrong", "incorrect", "actually", "not really",
    "that's not", "thats not", "isn't", "aren't", "doesn't", "don't",
    "wait,", "correction:", "i mean", "sorry,"
]

# Refinement indicators
REFINEMENT_WORDS = [
    "only when", "only if", "except when", "except if", "but not when",
    "but not if", "unless", "as long as", "provided that"
]

# Procedural indicators
PROCEDURAL_START = ["to ", "how to ", "in order to "]
PROCEDURAL_SEQUENCE = ["first", "then", "next", "after that", "finally", "lastly"]

# Recognized colors
COLORS = [
    "blue", "red", "green", "yellow", "orange", "purple",
    "white", "black", "pink", "brown", "gray", "grey",
    "cyan", "magenta", "gold", "silver", "bronze"
]

# Question words and their target relations
QUESTION_PATTERNS = {
    "where": ["located_in", "lives_in", "found_in"],
    "who": ["is", "identity"],
    "what": ["is", "identity"],
    "why": ["causes", "reason"],
    "how": ["method", "causes"],
    "when": ["time", "occurs"],
}
