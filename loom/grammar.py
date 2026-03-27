"""
Grammar module for Loom.
Handles conjugation, pluralization, and natural language formatting.
"""

# Irregular plural nouns
IRREGULAR_PLURALS = {
    "child": "children",
    "person": "people",
    "man": "men",
    "woman": "women",
    "foot": "feet",
    "tooth": "teeth",
    "mouse": "mice",
    "goose": "geese",
    "ox": "oxen",
    "fish": "fish",
    "sheep": "sheep",
    "deer": "deer",
    "species": "species",
    "series": "series",
}

# Reverse lookup for singular forms
IRREGULAR_SINGULARS = {v: k for k, v in IRREGULAR_PLURALS.items()}

# Common adjective endings that should NOT be pluralized
ADJECTIVE_ENDINGS = (
    "ed",      # domesticated, interested
    "ing",     # interesting, exciting
    "ful",     # beautiful, wonderful
    "less",    # homeless, careless
    "ous",     # dangerous, famous
    "ive",     # active, creative
    "able",    # comfortable, capable
    "ible",    # possible, visible
    "al",      # natural, emotional
    "ic",      # specific, scientific
    "ary",     # primary, secondary
    "ory",     # mandatory, satisfactory
    "ant",     # important, elegant
    "ent",     # different, excellent
)

# Common adjectives that don't have standard endings
COMMON_ADJECTIVES = {
    # Size
    "large", "big", "small", "tiny", "huge", "giant", "little", "tall", "short",
    # Speed/Intensity
    "fast", "slow", "quick", "rapid",
    # Temperature
    "hot", "cold", "warm", "cool",
    # Quality
    "good", "bad", "great", "poor", "nice", "fine",
    # Age
    "old", "young", "new", "ancient",
    # Color (basic)
    "red", "blue", "green", "yellow", "black", "white", "gray", "grey", "brown", "pink", "orange", "purple",
    # Traits
    "loyal", "smart", "wise", "brave", "calm", "wild", "tame", "fierce", "gentle", "kind", "mean",
    # Physical
    "strong", "weak", "hard", "soft", "wet", "dry", "clean", "dirty",
    # State
    "free", "safe", "happy", "sad", "angry", "scared", "hungry", "thirsty", "tired",
}


def is_adjective(word: str) -> bool:
    """Check if a word is likely an adjective (should not be pluralized)."""
    word = word.lower().strip()

    # Check common adjectives list
    if word in COMMON_ADJECTIVES:
        return True

    # Check common adjective endings
    for ending in ADJECTIVE_ENDINGS:
        if word.endswith(ending):
            return True

    return False


def is_plural(word: str) -> bool:
    """Check if a word is likely plural."""
    word = word.lower().strip()

    # Plural pronouns
    if word in ["they", "them", "we", "us", "these", "those"]:
        return True

    # Check irregular plurals
    if word in IRREGULAR_PLURALS.values():
        return True

    # Words that are same in singular/plural - treat as plural in general context
    # (e.g., "fish live in water" vs "a fish lives in water")
    same_singular_plural = [
        "fish", "sheep", "deer", "moose", "salmon", "trout", "shrimp",
        "clownfish", "jellyfish", "starfish", "swordfish", "crayfish",
        "octopus", "squid", "cod", "bass", "tuna", "carp", "pike",
    ]
    if word in same_singular_plural:
        return True

    # Common plural endings
    if word.endswith("s") and not word.endswith("ss"):
        # But not words that naturally end in 's'
        if word not in ["this", "is", "was", "has", "does", "goes"]:
            return True

    return False


def get_verb_form(subject: str, base_verb: str) -> str:
    """
    Get the correct verb form based on subject.
    'crocodiles' + 'is' -> 'are'
    'iguana' + 'is' -> 'is'
    """
    if is_plural(subject):
        # Plural subjects use base form
        if base_verb == "is":
            return "are"
        elif base_verb == "was":
            return "were"
        elif base_verb == "has":
            return "have"
        elif base_verb.endswith("s") and len(base_verb) > 2:
            # "runs" -> "run" for plural
            return base_verb[:-1]
    else:
        # Singular subjects
        if base_verb == "are":
            return "is"
        elif base_verb == "were":
            return "was"
        elif base_verb == "have":
            return "has"

    return base_verb


def get_article(word: str) -> str:
    """Get the appropriate article (a/an) for a word."""
    word = word.lower().strip()
    vowels = "aeiou"

    # Special cases
    if word.startswith("uni") or word.startswith("eu"):
        return "a"  # "a university", "a European"
    if word.startswith("hour") or word.startswith("honest"):
        return "an"

    if word[0] in vowels:
        return "an"
    return "a"


def pluralize(word: str) -> str:
    """Convert a singular noun to plural."""
    word = word.lower().strip()

    # Check irregular
    if word in IRREGULAR_PLURALS:
        return IRREGULAR_PLURALS[word]

    # Already plural
    if is_plural(word):
        return word

    # Rules for regular plurals
    if word.endswith("y") and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    elif word.endswith(("s", "sh", "ch", "x", "z")):
        return word + "es"
    elif word.endswith("f"):
        return word[:-1] + "ves"
    elif word.endswith("fe"):
        return word[:-2] + "ves"
    else:
        return word + "s"


def singularize(word: str) -> str:
    """Convert a plural noun to singular."""
    word = word.lower().strip()

    # Check irregular
    if word in IRREGULAR_SINGULARS:
        return IRREGULAR_SINGULARS[word]

    # Rules for regular singulars
    if word.endswith("ies"):
        return word[:-3] + "y"
    elif word.endswith("ves"):
        return word[:-3] + "f"
    elif word.endswith("es") and word[-4:-2] in ("sh", "ch"):
        return word[:-2]
    elif word.endswith("es"):
        return word[:-2]
    elif word.endswith("s") and not word.endswith("ss"):
        return word[:-1]

    return word


def format_response(subject: str, verb: str, obj: str) -> str:
    """
    Format a complete response with proper grammar.
    'crocodiles', 'is', 'reptile' -> 'Crocodiles are reptiles.'
    """
    # Get correct verb form
    correct_verb = get_verb_form(subject, verb)

    # Match object plurality to subject - but don't pluralize adjectives
    if is_plural(subject) and not is_plural(obj) and not is_adjective(obj):
        obj = pluralize(obj)
    elif not is_plural(subject) and is_plural(obj) and not is_adjective(obj):
        obj = singularize(obj)

    # Capitalize subject
    subject = subject.strip().title() if subject[0].islower() else subject

    return f"{subject} {correct_verb} {obj}."


def format_list(items: list) -> str:
    """
    Format a list with proper grammar.
    1 item:  "X"
    2 items: "X and Y"
    3+ items: "X, Y, and Z" (Oxford comma)
    """
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + ", and " + items[-1]


def format_what_response(subject: str, obj: str) -> str:
    """Format a 'what is X' response with proper grammar."""
    # Replace underscores with spaces for display
    obj = obj.replace("_", " ")

    verb = "are" if is_plural(subject) else "is"

    # Match object plurality - but don't pluralize adjectives
    if is_plural(subject) and not is_plural(obj) and not is_adjective(obj):
        obj = pluralize(obj)

    # Add article for singular nouns (not adjectives)
    if not is_plural(obj) and not is_adjective(obj):
        obj = f"{get_article(obj)} {obj}"

    subject = subject.strip().title()

    return f"{subject} {verb} {obj}."
