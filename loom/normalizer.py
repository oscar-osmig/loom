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
    "humans", "persons", "peoples", "kids", "babies", "friends", "pets",
    # Ocean/nature terms
    "reefs", "beaches", "anemones", "oceans", "ecosystems", "spaces",
    "bones", "arms", "tentacles", "species", "predators",
    # Body parts and sounds
    "hearts", "lungs", "brains", "limbs", "clicks", "whistles", "songs",
    "stings", "cells",
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

        # Don't strip 's' from words ending in 'es' after ch, sh, x, s, z
        # (beaches, spaces, boxes, gases, buzzes)
        if w.endswith("es") and len(w) > 3:
            if w[-3] in "chxsz" or w.endswith("shes"):
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


def resolve_possessive(phrase: str, knowledge: dict) -> str:
    """
    Resolve possessive references to existing properties.

    "loom's eyes" -> "blue_eyes" (if loom has blue_eyes)
    "loom eyes" -> "blue_eyes" (if loom has blue_eyes)

    Args:
        phrase: The phrase to resolve (e.g., "loom's eyes")
        knowledge: The knowledge graph dict

    Returns:
        The resolved entity name, or the original normalized phrase if no resolution found
    """
    phrase = phrase.lower().strip()

    # Pattern 1: "X's Y" (possessive with apostrophe)
    match = re.match(r"^(.+?)'s?\s+(.+)$", phrase)
    if match:
        owner = match.group(1).strip()
        property_name = match.group(2).strip()
        resolved = _find_property(owner, property_name, knowledge)
        if resolved:
            return resolved

    # Pattern 2: "X Y" where X is a known entity (compound reference)
    # Only try this if phrase has multiple words
    words = phrase.split()
    if len(words) >= 2:
        # Try first word as owner
        owner = words[0]
        property_name = " ".join(words[1:])
        resolved = _find_property(owner, property_name, knowledge)
        if resolved:
            return resolved

    # No resolution found, return normalized phrase
    return normalize(phrase)


def _find_property(owner: str, property_hint: str, knowledge: dict) -> str | None:
    """
    Find a property of an owner that matches the hint.

    "loom", "eyes" -> "blue_eyes" (if loom --[has]--> blue_eyes)
    """
    owner_norm = normalize(owner)
    hint_norm = normalize(property_hint)

    # Check if owner exists in knowledge
    if owner_norm not in knowledge:
        return None

    owner_relations = knowledge[owner_norm]

    # Look in "has" relations first (most common for properties)
    for relation in ["has", "has_property", "owns", "possesses"]:
        if relation in owner_relations:
            for prop in owner_relations[relation]:
                prop_lower = prop.lower()
                # Check if property contains the hint
                # "blue_eyes" contains "eyes"
                if hint_norm in prop_lower or prop_lower.endswith(hint_norm):
                    return prop
                # Also check without underscores
                if hint_norm in prop_lower.replace("_", " "):
                    return prop

    # Also check reverse: maybe the property "belongs_to" owner
    for entity, relations in knowledge.items():
        if "belongs_to" in relations:
            if owner_norm in relations["belongs_to"]:
                entity_lower = entity.lower()
                if hint_norm in entity_lower or entity_lower.endswith(hint_norm):
                    return entity

    return None
