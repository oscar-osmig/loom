"""
Unified relation definitions - Single source of truth for all relations in Loom.

This module defines all relations with their verb forms, patterns, and metadata.
Other modules should import from here rather than hardcoding verb mappings.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RelationDef:
    """Definition of a relation with all its forms and metadata."""
    relation: str                    # Stored relation name (e.g., "built")
    base_verb: str                   # Base verb form (e.g., "build")
    past: str                        # Past tense (e.g., "built")
    present_s: str                   # Present singular (e.g., "builds")
    present_p: str                   # Present plural (e.g., "build")
    reverse: Optional[str] = None   # Reverse relation (e.g., "built_by")
    category: str = "action"         # Category for grouping
    transitive: bool = False         # Can chain transitively?


# =============================================================================
# RELATION DEFINITIONS - The single source of truth
# =============================================================================

RELATION_DEFS = [
    # -------------------------------------------------------------------------
    # CAUSATION
    # -------------------------------------------------------------------------
    RelationDef("causes", "cause", "caused", "causes", "cause", None, "causation"),
    RelationDef("leads_to", "lead to", "led to", "leads to", "lead to", None, "causation"),
    RelationDef("creates", "create", "created", "creates", "create", "created_by", "causation"),
    RelationDef("produces", "produce", "produced", "produces", "produce", None, "causation"),
    RelationDef("results_in", "result in", "resulted in", "results in", "result in", None, "causation"),
    RelationDef("reduces", "reduce", "reduced", "reduces", "reduce", None, "causation"),
    RelationDef("contributes_to", "contribute to", "contributed to", "contributes to", "contribute to", None, "causation"),
    RelationDef("makes", "make", "made", "makes", "make", None, "causation"),

    # -------------------------------------------------------------------------
    # POSSESSION / ATTRIBUTES
    # -------------------------------------------------------------------------
    RelationDef("has", "have", "had", "has", "have", "belongs_to", "possession"),
    RelationDef("owns", "own", "owned", "owns", "own", "owned_by", "possession"),
    RelationDef("contains", "contain", "contained", "contains", "contain", "inside", "possession"),
    RelationDef("carries", "carry", "carried", "carries", "carry", None, "possession"),
    RelationDef("includes", "include", "included", "includes", "include", "included_in", "possession"),

    # -------------------------------------------------------------------------
    # ABILITIES
    # -------------------------------------------------------------------------
    RelationDef("can", "can", "could", "can", "can", None, "ability"),

    # -------------------------------------------------------------------------
    # LOCATION
    # -------------------------------------------------------------------------
    RelationDef("lives_in", "live in", "lived in", "lives in", "live in", "home_of", "location"),
    RelationDef("located_in", "located in", "was located in", "is located in", "are located in", "location_of", "location"),
    RelationDef("found_in", "found in", "was found in", "is found in", "are found in", "contains", "location"),
    RelationDef("common_in", "common in", "was common in", "is common in", "are common in", "commonly_has", "location"),
    RelationDef("native_to", "native to", "was native to", "is native to", "are native to", "native_habitat_of", "location"),

    # -------------------------------------------------------------------------
    # PART-OF / HIERARCHY
    # -------------------------------------------------------------------------
    RelationDef("part_of", "part of", "was part of", "is part of", "are part of", "has_part", "hierarchy", True),
    RelationDef("belongs_to", "belong to", "belonged to", "belongs to", "belong to", "has", "hierarchy"),

    # -------------------------------------------------------------------------
    # NEEDS / WANTS
    # -------------------------------------------------------------------------
    RelationDef("needs", "need", "needed", "needs", "need", "needed_by", "needs"),
    RelationDef("wants", "want", "wanted", "wants", "want", "wanted_by", "needs"),
    RelationDef("requires", "require", "required", "requires", "require", "required_by", "needs"),

    # -------------------------------------------------------------------------
    # HARM / HELP
    # -------------------------------------------------------------------------
    RelationDef("harms", "harm", "harmed", "harms", "harm", "harmed_by", "interaction"),
    RelationDef("damages", "damage", "damaged", "damages", "damage", "damaged_by", "interaction"),
    RelationDef("hurts", "hurt", "hurt", "hurts", "hurt", "hurt_by", "interaction"),
    RelationDef("kills", "kill", "killed", "kills", "kill", "killed_by", "interaction"),
    RelationDef("helps", "help", "helped", "helps", "help", "helped_by", "interaction"),
    RelationDef("affects", "affect", "affected", "affects", "affect", "affected_by", "interaction"),
    RelationDef("protects", "protect", "protected", "protects", "protect", "protected_by", "interaction"),

    # -------------------------------------------------------------------------
    # ECOLOGICAL / ENVIRONMENTAL
    # -------------------------------------------------------------------------
    RelationDef("nourishes", "nourish", "nourished", "nourishes", "nourish", "nourished_by", "ecological"),
    RelationDef("sustains", "sustain", "sustained", "sustains", "sustain", "sustained_by", "ecological"),
    RelationDef("shelters", "shelter", "sheltered", "shelters", "shelter", "sheltered_by", "ecological"),
    RelationDef("inhabits", "inhabit", "inhabited", "inhabits", "inhabit", "inhabited_by", "ecological"),
    RelationDef("thrives_in", "thrive in", "thrived in", "thrives in", "thrive in", "supports", "ecological"),
    RelationDef("feeds_on", "feed on", "fed on", "feeds on", "feed on", "food_for", "ecological"),
    RelationDef("preys_on", "prey on", "preyed on", "preys on", "prey on", "preyed_upon_by", "ecological"),
    RelationDef("pollinates", "pollinate", "pollinated", "pollinates", "pollinate", "pollinated_by", "ecological"),

    # -------------------------------------------------------------------------
    # MOVEMENT / PHYSICAL
    # -------------------------------------------------------------------------
    RelationDef("powers", "power", "powered", "powers", "power", "powered_by", "physical"),
    RelationDef("pumps", "pump", "pumped", "pumps", "pump", "pumped_by", "physical"),
    RelationDef("moves", "move", "moved", "moves", "move", "moved_by", "physical"),
    RelationDef("pulls", "pull", "pulled", "pulls", "pull", "pulled_by", "physical"),
    RelationDef("orbits", "orbit", "orbited", "orbits", "orbit", "orbited_by", "physical"),
    RelationDef("runs_on", "run on", "ran on", "runs on", "run on", None, "physical"),
    RelationDef("flows_to", "flow to", "flowed to", "flows to", "flow to", None, "physical"),

    # -------------------------------------------------------------------------
    # MEASUREMENT / CONTROL
    # -------------------------------------------------------------------------
    RelationDef("measures", "measure", "measured", "measures", "measure", "measured_by", "control"),
    RelationDef("controls", "control", "controlled", "controls", "control", "controlled_by", "control"),

    # -------------------------------------------------------------------------
    # CONSUMPTION / PREFERENCE
    # -------------------------------------------------------------------------
    RelationDef("eats", "eat", "ate", "eats", "eat", "eaten_by", "consumption"),
    RelationDef("drinks", "drink", "drank", "drinks", "drink", "drunk_by", "consumption"),
    RelationDef("uses", "use", "used", "uses", "use", "used_by", "consumption"),
    RelationDef("likes", "like", "liked", "likes", "like", "liked_by", "preference"),
    RelationDef("loves", "love", "loved", "loves", "love", "loved_by", "preference"),
    RelationDef("hates", "hate", "hated", "hates", "hate", "hated_by", "preference"),
    RelationDef("fears", "fear", "feared", "fears", "fear", "feared_by", "preference"),

    # -------------------------------------------------------------------------
    # COMPOSITION
    # -------------------------------------------------------------------------
    RelationDef("made_of", "made of", "was made of", "is made of", "are made of", "material_for", "composition"),
    RelationDef("consists_of", "consist of", "consisted of", "consists of", "consist of", "part_of", "composition"),

    # -------------------------------------------------------------------------
    # COMPARISON
    # -------------------------------------------------------------------------
    RelationDef("bigger_than", "bigger than", "was bigger than", "is bigger than", "are bigger than", "smaller_than", "comparison"),
    RelationDef("smaller_than", "smaller than", "was smaller than", "is smaller than", "are smaller than", "bigger_than", "comparison"),
    RelationDef("faster_than", "faster than", "was faster than", "is faster than", "are faster than", "slower_than", "comparison"),
    RelationDef("slower_than", "slower than", "was slower than", "is slower than", "are slower than", "faster_than", "comparison"),
    RelationDef("stronger_than", "stronger than", "was stronger than", "is stronger than", "are stronger than", "weaker_than", "comparison"),
    RelationDef("taller_than", "taller than", "was taller than", "is taller than", "are taller than", "shorter_than", "comparison"),
    RelationDef("shorter_than", "shorter than", "was shorter than", "is shorter than", "are shorter than", "taller_than", "comparison"),
    RelationDef("more_efficient_than", "more efficient than", "was more efficient than", "is more efficient than", "are more efficient than", "less_efficient_than", "comparison"),
    RelationDef("differs_from", "differ from", "differed from", "differs from", "differ from", None, "comparison"),

    # -------------------------------------------------------------------------
    # TEMPORAL
    # -------------------------------------------------------------------------
    RelationDef("before", "before", "was before", "is before", "are before", "after", "temporal"),
    RelationDef("after", "after", "was after", "is after", "are after", "before", "temporal"),

    # -------------------------------------------------------------------------
    # COMMUNICATION / RELATIONSHIPS
    # -------------------------------------------------------------------------
    RelationDef("communicates_using", "communicate using", "communicated using", "communicates using", "communicate using", None, "communication"),
    RelationDef("communicates_with", "communicate with", "communicated with", "communicates with", "communicate with", None, "communication"),
    RelationDef("connects", "connect", "connected", "connects", "connect", "connected_by", "communication"),
    RelationDef("related_to", "related to", "was related to", "is related to", "are related to", "related_to", "communication"),

    # -------------------------------------------------------------------------
    # BEHAVIORS / ACTIVITIES
    # -------------------------------------------------------------------------
    RelationDef("sleeps", "sleep", "slept", "sleeps", "sleep", None, "behavior"),
    RelationDef("runs", "run", "ran", "runs", "run", None, "behavior"),
    RelationDef("walks", "walk", "walked", "walks", "walk", None, "behavior"),
    RelationDef("swims", "swim", "swam", "swims", "swim", None, "behavior"),
    RelationDef("flies", "fly", "flew", "flies", "fly", None, "behavior"),
    RelationDef("hunts", "hunt", "hunted", "hunts", "hunt", None, "behavior"),
    RelationDef("climbs", "climb", "climbed", "climbs", "climb", None, "behavior"),
    RelationDef("hides", "hide", "hid", "hides", "hide", None, "behavior"),
    RelationDef("plays", "play", "played", "plays", "play", "played_by", "behavior"),
    RelationDef("lays", "lay", "laid", "lays", "lay", None, "behavior"),
    RelationDef("lays_eggs_on", "lay eggs on", "laid eggs on", "lays eggs on", "lay eggs on", None, "behavior"),
    RelationDef("breathes", "breathe", "breathed", "breathes", "breathe", None, "behavior"),
    RelationDef("provides", "provide", "provided", "provides", "provide", "provided_by", "behavior"),
    RelationDef("provides_energy_for", "provide energy for", "provided energy for", "provides energy for", "provide energy for", None, "behavior"),

    # -------------------------------------------------------------------------
    # FORMATION / NATURAL
    # -------------------------------------------------------------------------
    RelationDef("forms_over", "form over", "formed over", "forms over", "form over", None, "formation"),
    RelationDef("forms_in", "form in", "formed in", "forms in", "form in", None, "formation"),
    RelationDef("essential_for", "essential for", "was essential for", "is essential for", "are essential for", "requires", "formation"),

    # -------------------------------------------------------------------------
    # CREATION / CONSTRUCTION (Historical)
    # -------------------------------------------------------------------------
    RelationDef("built", "build", "built", "builds", "build", "built_by", "creation"),
    RelationDef("constructed", "construct", "constructed", "constructs", "construct", "constructed_by", "creation"),
    RelationDef("developed", "develop", "developed", "develops", "develop", "developed_by", "creation"),
    RelationDef("created", "create", "created", "creates", "create", "created_by", "creation"),
    RelationDef("invented", "invent", "invented", "invents", "invent", "invented_by", "creation"),
    RelationDef("discovered", "discover", "discovered", "discovers", "discover", "discovered_by", "creation"),
    RelationDef("established", "establish", "established", "establishes", "establish", "established_by", "creation"),
    RelationDef("founded", "found", "founded", "founds", "found", "founded_by", "creation"),

    # -------------------------------------------------------------------------
    # STUDY / LEARNING
    # -------------------------------------------------------------------------
    RelationDef("studied", "study", "studied", "studies", "study", None, "learning"),
    RelationDef("learned", "learn", "learned", "learns", "learn", None, "learning"),
    RelationDef("taught", "teach", "taught", "teaches", "teach", None, "learning"),
    RelationDef("trained", "train", "trained", "trains", "train", None, "learning"),

    # -------------------------------------------------------------------------
    # HISTORICAL ACTIONS
    # -------------------------------------------------------------------------
    RelationDef("conquered", "conquer", "conquered", "conquers", "conquer", "conquered_by", "historical"),
    RelationDef("ruled", "rule", "ruled", "rules", "rule", "ruled_by", "historical"),
    RelationDef("dominated", "dominate", "dominated", "dominates", "dominate", "dominated_by", "historical"),
    RelationDef("invaded", "invade", "invaded", "invades", "invade", "invaded_by", "historical"),
    RelationDef("flooded", "flood", "flooded", "floods", "flood", None, "historical"),
    RelationDef("erupted", "erupt", "erupted", "erupts", "erupt", None, "historical"),

    # -------------------------------------------------------------------------
    # TRANSFORMATION
    # -------------------------------------------------------------------------
    RelationDef("evolved_into", "evolve", "evolved", "evolves", "evolve", None, "transformation"),
    RelationDef("transformed_into", "transform", "transformed", "transforms", "transform", None, "transformation"),
    RelationDef("changed_into", "change", "changed", "changes", "change", None, "transformation"),

    # -------------------------------------------------------------------------
    # TRADE / CONNECTION
    # -------------------------------------------------------------------------
    RelationDef("traded_with", "trade with", "traded with", "trades with", "trade with", None, "trade"),
    RelationDef("connected", "connect", "connected", "connects", "connect", "connected_by", "trade"),

    # -------------------------------------------------------------------------
    # WRITING / COMMUNICATION
    # -------------------------------------------------------------------------
    RelationDef("wrote", "write", "wrote", "writes", "write", "written_by", "writing"),
    RelationDef("recorded", "record", "recorded", "records", "record", None, "writing"),

    # -------------------------------------------------------------------------
    # WORSHIP / BELIEF
    # -------------------------------------------------------------------------
    RelationDef("worshipped", "worship", "worshipped", "worships", "worship", "worshipped_by", "belief"),
    RelationDef("believed_in", "believe in", "believed in", "believes in", "believe in", None, "belief"),
    RelationDef("honored", "honor", "honored", "honors", "honor", "honored_by", "belief"),

    # -------------------------------------------------------------------------
    # HOSTED / PERFORMED
    # -------------------------------------------------------------------------
    RelationDef("hosted", "host", "hosted", "hosts", "host", "hosted_by", "event"),
    RelationDef("performed", "perform", "performed", "performs", "perform", "performed_by", "event"),

    # -------------------------------------------------------------------------
    # SPECIAL ABILITIES
    # -------------------------------------------------------------------------
    RelationDef("immune_to", "immune to", "was immune to", "is immune to", "are immune to", None, "ability"),
    RelationDef("can_regenerate", "regenerate", "regenerated", "regenerates", "regenerate", None, "ability"),
    RelationDef("can_detect", "detect", "detected", "detects", "detect", None, "ability"),

    # -------------------------------------------------------------------------
    # BODY / BIOLOGICAL FUNCTIONS
    # -------------------------------------------------------------------------
    RelationDef("breaks_down", "break down", "broke down", "breaks down", "break down", "broken_down_by", "biological"),
    RelationDef("exchanges", "exchange", "exchanged", "exchanges", "exchange", "exchanged_by", "biological"),
    RelationDef("filters", "filter", "filtered", "filters", "filter", "filtered_by", "biological"),
    RelationDef("absorbs", "absorb", "absorbed", "absorbs", "absorb", "absorbed_by", "biological"),
    RelationDef("delivers", "deliver", "delivered", "delivers", "deliver", "delivered_by", "biological"),
    RelationDef("removes", "remove", "removed", "removes", "remove", "removed_by", "biological"),
    RelationDef("supports", "support", "supported", "supports", "support", "supported_by", "biological"),
    RelationDef("prevents", "prevent", "prevented", "prevents", "prevent", "prevented_by", "biological"),
    RelationDef("strengthens", "strengthen", "strengthened", "strengthens", "strengthen", "strengthened_by", "biological"),
    RelationDef("coordinates", "coordinate", "coordinated", "coordinates", "coordinate", "coordinated_by", "biological"),
    RelationDef("maintains", "maintain", "maintained", "maintains", "maintain", "maintained_by", "biological"),
    RelationDef("transmits", "transmit", "transmitted", "transmits", "transmit", "transmitted_by", "biological"),
    RelationDef("stores", "store", "stored", "stores", "store", "stored_by", "biological"),
    RelationDef("regulates", "regulate", "regulated", "regulates", "regulate", "regulated_by", "biological"),
    RelationDef("converts", "convert", "converted", "converts", "convert", "converted_by", "biological"),
    RelationDef("eliminates", "eliminate", "eliminated", "eliminates", "eliminate", "eliminated_by", "biological"),
    RelationDef("contracts", "contract", "contracted", "contracts", "contract", None, "biological"),
    RelationDef("expands", "expand", "expanded", "expands", "expand", None, "biological"),
    RelationDef("increases", "increase", "increased", "increases", "increase", None, "biological"),
    RelationDef("decreases", "decrease", "decreased", "decreases", "decrease", None, "biological"),
    RelationDef("circulates", "circulate", "circulated", "circulates", "circulate", "circulated_by", "biological"),
    RelationDef("beats", "beat", "beat", "beats", "beat", None, "biological"),
    RelationDef("transports", "transport", "transported", "transports", "transport", "transported_by", "biological"),
    RelationDef("transfers", "transfer", "transferred", "transfers", "transfer", "transferred_by", "biological"),
    RelationDef("forms", "form", "formed", "forms", "form", "formed_by", "biological"),
    RelationDef("releases", "release", "released", "releases", "release", "released_by", "biological"),
    RelationDef("generates", "generate", "generated", "generates", "generate", "generated_by", "biological"),

    # -------------------------------------------------------------------------
    # CONTAINMENT / HOUSING
    # -------------------------------------------------------------------------
    RelationDef("housed", "house", "housed", "houses", "house", "housed_by", "containment"),
    RelationDef("contained", "contain", "contained", "contains", "contain", "contained_by", "containment"),
    RelationDef("preserved", "preserve", "preserved", "preserves", "preserve", "preserved_by", "containment"),

    # -------------------------------------------------------------------------
    # POWER / TRANSFORMATION
    # -------------------------------------------------------------------------
    RelationDef("powered", "power", "powered", "powers", "power", "powered_by", "power"),
    RelationDef("transforms", "transform", "transformed", "transforms", "transform", "transformed_by", "power"),
]


# =============================================================================
# LOOKUP STRUCTURES - Generated from RELATION_DEFS
# =============================================================================

# Map relation name -> RelationDef
RELATION_BY_NAME = {r.relation: r for r in RELATION_DEFS}

# Map base verb -> RelationDef
RELATION_BY_VERB = {r.base_verb: r for r in RELATION_DEFS}

# Map any verb form -> RelationDef
RELATION_BY_ANY_VERB = {}
for r in RELATION_DEFS:
    for verb in [r.base_verb, r.past, r.present_s, r.present_p]:
        if verb and verb not in RELATION_BY_ANY_VERB:
            RELATION_BY_ANY_VERB[verb] = r


def get_relation_for_verb(verb: str) -> Optional[RelationDef]:
    """Get the relation definition for any verb form."""
    return RELATION_BY_ANY_VERB.get(verb.lower())


def get_relation_by_name(relation: str) -> Optional[RelationDef]:
    """Get the relation definition by stored relation name."""
    return RELATION_BY_NAME.get(relation)


def get_past_tense(verb: str) -> str:
    """Get past tense for a verb, or return verb unchanged if not found."""
    rel = get_relation_for_verb(verb)
    return rel.past if rel else verb


def get_stored_relation(verb: str) -> str:
    """Get the stored relation name for a verb, or return verb unchanged."""
    rel = get_relation_for_verb(verb)
    return rel.relation if rel else verb


# =============================================================================
# PATTERN GENERATION - Generate RELATION_PATTERNS from definitions
# =============================================================================

def generate_relation_patterns() -> list:
    """
    Generate RELATION_PATTERNS list from RELATION_DEFS.
    Returns list of tuples: (pattern, relation, reverse_relation)
    """
    patterns = []

    for r in RELATION_DEFS:
        # Generate patterns for different verb forms
        # Present singular: " builds "
        if r.present_s:
            patterns.append((f" {r.present_s} ", r.relation, r.reverse))

        # Present plural: " build "
        if r.present_p and r.present_p != r.present_s:
            patterns.append((f" {r.present_p} ", r.relation, r.reverse))

        # Past tense: " built "
        if r.past and r.past not in [r.present_s, r.present_p]:
            patterns.append((f" {r.past} ", r.relation, r.reverse))

    return patterns


# Generate the patterns list
RELATION_PATTERNS = generate_relation_patterns()


# =============================================================================
# QUERY HELPERS - For dynamic query handling
# =============================================================================

def get_all_queryable_verbs() -> list:
    """Get all base verbs that can be used in queries."""
    return [r.base_verb for r in RELATION_DEFS]


def get_verb_to_relation_map() -> dict:
    """
    Get mapping of all verb forms to (relation, past_tense) tuples.
    Used by query handlers for "what did X verb?" patterns.
    """
    verb_map = {}
    for r in RELATION_DEFS:
        entry = (r.relation, r.past)
        # Map base verb
        verb_map[r.base_verb] = entry
        # Map past tense (if different)
        if r.past != r.base_verb:
            verb_map[r.past] = entry
        # Map present forms (less common in queries but included)
        if r.present_s not in verb_map:
            verb_map[r.present_s] = entry
        if r.present_p not in verb_map:
            verb_map[r.present_p] = entry
    return verb_map


def get_present_tense_verb_map() -> dict:
    """
    Get mapping of base verbs to stored relations.
    Used by query handlers for "what do X verb?" patterns.
    """
    return {r.base_verb: r.relation for r in RELATION_DEFS}


# Pre-compute commonly used maps
VERB_TO_RELATION_MAP = get_verb_to_relation_map()
PRESENT_VERB_MAP = get_present_tense_verb_map()
