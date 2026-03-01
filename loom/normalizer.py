"""
Text normalization and formatting utilities.
Converts natural language to internal keys and back to readable text.
"""

import re

# Words to strip during normalization (only at word boundaries)
REMOVE_WORDS = [
    "the ", "a ", "an ", "of the ", "of ",
    "it ", "is ", "are ", "was ", "were ",
    "gets ", "get ", "becomes ", "become ",
    "very ", "really ", "then ",
]

# Words to remove only at START of string (to avoid "also" -> "al")
REMOVE_AT_START = ["so "]

# Words that indicate incomplete/malformed entities (should not be in entity names)
INVALID_ENTITY_WORDS = [
    "that", "which", "who", "whom", "whose", "where", "when",
    "what", "why", "how", "can", "cannot", "could", "would",
    "should", "will", "do", "does", "did", "have", "has", "had",
]

# Words that shouldn't have 's' stripped
PROTECTED_WORDS = [
    # Common words ending in 's'
    "grass", "glass", "class", "less", "mess", "boss", "loss",
    "things", "always", "sometimes", "perhaps", "yes", "no",
    # Body parts (plural form is common)
    "legs", "wings", "fins", "gills", "scales", "feathers", "whiskers",
    "eyes", "ears", "claws", "paws", "tails", "horns", "tusks",
    "hands", "feet", "teeth", "arms",
    # Animals (keep plural forms)
    "dogs", "cats", "birds", "fish", "wolves", "leaves", "knives",
    "dolphins", "whales", "horses", "cows", "pigs", "sheep",
    "lions", "tigers", "bears", "foxes", "deer", "mice", "geese",
    "elephants", "giraffes", "monkeys", "snakes", "frogs", "bees",
    "butterflies", "flies", "spiders", "ants", "wolves", "calves",
    # Common nouns
    "trees", "flowers", "plants", "rocks", "clouds", "stars",
    "cars", "planes", "trains", "buses", "houses", "buildings",
    "humans", "persons", "peoples", "kids", "babies", "friends",
    # Categories and classifications
    "mammals", "animals", "reptiles", "amphibians", "insects", "predators",
    "hunters", "herbivores", "carnivores", "omnivores", "vertebrates",
    "creatures", "species", "organisms",
]

# Common adjectives/states for formatting
ADJECTIVES = [
    "wet", "dry", "hot", "cold", "muddy", "dirty", "clean",
    "big", "small", "fast", "slow", "happy", "sad",
    "blue", "red", "green", "yellow", "orange", "purple", "white", "black"
]

# Verb-like words that get "it X-s" formatting
VERB_LIKE = ["rain", "snow", "wind", "storm", "flood", "fire"]


def normalize(text: str) -> str:
    """
    Convert natural language to internal key format.
    'the rain makes the ground wet' -> 'rain'
    'the ground is wet' -> 'ground_wet'
    """
    s = str(text).lower().strip()

    # Remove filler words (use word boundaries to avoid partial matches)
    # e.g., "it " should not match inside "fruit "
    for word in REMOVE_WORDS:
        word_clean = word.strip()
        # Match whole word followed by optional space
        pattern = r'\b' + re.escape(word_clean) + r'\b\s*'
        s = re.sub(pattern, '', s)

    # Remove words only at start (avoids "also" -> "al")
    for word in REMOVE_AT_START:
        if s.startswith(word):
            s = s[len(word):]

    # Handle special phrases
    s = s.replace("ocean water", "ocean_water").replace("water ocean", "ocean_water")
    s = s.strip()

    # Simple verb/noun normalization
    words = s.split()

    # Truncate at invalid entity words (relative clause markers, etc.)
    # This prevents "penguin birds that" from becoming "penguin_birds_that"
    truncated = []
    for w in words:
        if w in INVALID_ENTITY_WORDS:
            break  # Stop at first invalid word
        truncated.append(w)
    words = truncated if truncated else words[:1]  # Keep at least one word

    normalized = []
    for w in words:
        # Handle underscore-joined compound words (already normalized)
        # e.g., "four_legs" should stay as "four_legs"
        if "_" in w:
            normalized.append(w)
            continue

        # Don't strip 's' from protected words
        if w in PROTECTED_WORDS:
            normalized.append(w)
            continue

        # Don't strip 's' from words ending in 'ves' (wolves, leaves, etc.)
        if w.endswith("ves"):
            normalized.append(w)
            continue

        # Don't strip 's' from words ending in 'ies' (butterflies, etc.)
        if w.endswith("ies"):
            normalized.append(w)
            continue

        # Don't strip 's' from words ending in 'gs' (legs, dogs, etc.)
        if w.endswith("gs"):
            normalized.append(w)
            continue

        # "rains" -> "rain" (but protect certain patterns)
        if w.endswith("s") and len(w) > 3:
            # Don't strip if second-to-last char is s, i, or u
            if w[-2] not in "siu":
                w = w[:-1]

        normalized.append(w)

    return "_".join(normalized).strip("_")


def prettify(text: str) -> str:
    """Convert internal key back to readable English."""
    s = text.replace("_", " ")
    words = s.split()

    if not words:
        return s

    # Single word - return as is
    if len(words) == 1:
        return words[0]

    # Multi-word: check if last word is an adjective
    if words[-1] in ADJECTIVES:
        return f"the {' '.join(words[:-1])} is {words[-1]}"

    return s


def prettify_effect(text: str) -> str:
    """Format an effect/result for natural language output."""
    s = text.replace("_", " ")
    words = s.split()

    if not words:
        return s

    # Single adjective: "muddy" -> "it gets muddy"
    if len(words) == 1 and words[0] in ADJECTIVES:
        return f"it gets {words[0]}"

    # "ground wet" -> "the ground gets wet"
    if len(words) >= 2 and words[-1] in ADJECTIVES:
        return f"the {' '.join(words[:-1])} gets {words[-1]}"

    return s


def prettify_cause(text: str) -> str:
    """Format a cause/trigger for natural language output."""
    s = text.replace("_", " ")
    words = s.split()

    if not words:
        return s

    # Verb-like single word: "rain" -> "it rains"
    if len(words) == 1 and words[0] in VERB_LIKE:
        return f"it {words[0]}s"

    # "ground wet" -> "the ground is wet"
    if len(words) >= 2 and words[-1] in ADJECTIVES:
        return f"the {' '.join(words[:-1])} is {words[-1]}"

    return s
