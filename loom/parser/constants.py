"""
Constants used by the parser module.
"""

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

# Relation patterns: (phrase, relation_name, reverse_relation)
RELATION_PATTERNS = [
    # Causation
    (" causes ", "causes", None),
    (" cause ", "causes", None),
    (" leads to ", "leads_to", None),
    (" lead to ", "leads_to", None),
    (" makes ", "causes", None),
    (" make ", "causes", None),
    (" creates ", "causes", None),
    (" create ", "causes", None),
    (" produces ", "causes", None),
    (" produce ", "causes", None),
    (" results in ", "causes", None),
    (" result in ", "causes", None),
    # Possession / Attributes
    (" has ", "has", "belongs_to"),
    (" have ", "has", "belongs_to"),
    (" owns ", "owns", "owned_by"),
    (" own ", "owns", "owned_by"),
    (" contains ", "contains", "inside"),
    (" contain ", "contains", "inside"),
    # Abilities
    (" can ", "can", None),
    (" could ", "can", None),
    (" is able to ", "can", None),
    (" are able to ", "can", None),
    # Location
    (" lives in ", "lives_in", "home_of"),
    (" live in ", "lives_in", "home_of"),
    (" is located in ", "located_in", "location_of"),
    (" are located in ", "located_in", "location_of"),
    (" is found in ", "found_in", "contains"),
    (" are found in ", "found_in", "contains"),
    (" is in ", "located_in", "contains"),
    (" are in ", "located_in", "contains"),
    # Part-of
    (" is part of ", "part_of", "has_part"),
    (" are part of ", "part_of", "has_part"),
    (" belongs to ", "belongs_to", "has"),
    (" belong to ", "belongs_to", "has"),
    # Needs / Wants
    (" needs ", "needs", "needed_by"),
    (" need ", "needs", "needed_by"),
    (" wants ", "wants", "wanted_by"),
    (" want ", "wants", "wanted_by"),
    (" requires ", "requires", "required_by"),
    (" require ", "requires", "required_by"),
    # Actions / Behaviors
    (" eats ", "eats", "eaten_by"),
    (" eat ", "eats", "eaten_by"),
    (" likes ", "likes", "liked_by"),
    (" like ", "likes", "liked_by"),
    (" loves ", "loves", "loved_by"),
    (" love ", "loves", "loved_by"),
    (" hates ", "hates", "hated_by"),
    (" hate ", "hates", "hated_by"),
    (" fears ", "fears", "feared_by"),
    (" fear ", "fears", "feared_by"),
    (" uses ", "uses", "used_by"),
    (" use ", "uses", "used_by"),
    (" drinks ", "drinks", "drunk_by"),
    (" drink ", "drinks", "drunk_by"),
    # Made of
    (" is made of ", "made_of", "material_for"),
    (" are made of ", "made_of", "material_for"),
    (" consists of ", "consists_of", "part_of"),
    (" consist of ", "consists_of", "part_of"),
    # Comparatives
    (" is bigger than ", "bigger_than", "smaller_than"),
    (" is larger than ", "bigger_than", "smaller_than"),
    (" is smaller than ", "smaller_than", "bigger_than"),
    (" is faster than ", "faster_than", "slower_than"),
    (" is slower than ", "slower_than", "faster_than"),
    (" is stronger than ", "stronger_than", "weaker_than"),
    (" is taller than ", "taller_than", "shorter_than"),
    (" is shorter than ", "shorter_than", "taller_than"),
    # Temporal
    (" happens before ", "before", "after"),
    (" comes before ", "before", "after"),
    (" happens after ", "after", "before"),
    (" comes after ", "after", "before"),
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
