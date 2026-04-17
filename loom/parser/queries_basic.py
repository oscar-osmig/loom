"""
Basic query methods for the Parser class.
Handles simple question-answering queries.
"""

import re
from ..normalizer import normalize, prettify
from ..grammar import is_plural, format_list


def _check_name_query(parser, t: str) -> str | None:
    """Handle 'what is your name?' queries."""
    if any(x in t for x in ["name", "called"]) and any(x in t for x in ["your", "what"]):
        return f"I am {parser.loom.name}."
    return None


def _check_self_identity_query(parser, t: str) -> str | None:
    """Handle 'what are you?' or 'who are you?' queries about Loom itself."""

    # "tell me about yourself" / "describe yourself" - general background
    if re.search(r"tell\s+me\s+(?:more\s+)?about\s+you|describe\s+you", t):
        return (
            "I am a symbolic knowledge system inspired by how the brain forms connections. "
            "I learn facts from conversation and weave them into a web of linked concepts."
        )

    # "how do you work?" - explain mechanism
    if re.search(r"how\s+do\s+you\s+work", t):
        return (
            "I create neurons (concepts) and synapses (connections) from what you tell me. "
            "When concepts are used together, their connections strengthen - inspired by Hebbian learning."
        )

    # "what exactly are you?" - precise definition
    if re.search(r"what\s+(?:exactly|really)\s+are\s+you|what\s+are\s+you\s+(?:exactly|really)", t):
        return (
            "I am a symbolic reasoning system - no machine learning, neural networks, or embeddings. "
            "Just concepts, relationships, and logical inference."
        )

    # "explain yourself" - technical explanation
    if re.search(r"explain\s+(?:what\s+)?you", t):
        return (
            "I store knowledge as triples: subject, relation, object. "
            "I can infer new facts through transitive reasoning and answer questions from what I've learned."
        )

    # Short version: "what are you?" / "who are you?"
    if re.match(r"(?:what|who)\s+(?:are|is)\s+you\b", t):
        return f"I am {parser.loom.name}, a knowledge system that learns through conversation."

    # Match "what can you do?" / "what do you do?"
    if re.match(r"what\s+(?:can|do)\s+you\s+do", t):
        can_facts = parser.loom.get("loom", "can") or []
        if can_facts:
            abilities = format_list([x.replace("_", " ") for x in can_facts])
            return f"I can {abilities}."
        return "I can learn from conversation, remember facts, and answer questions."

    return None


def _check_color_query(parser, t: str) -> str | None:
    """Handle 'what color is X?' queries."""
    if "what color" not in t:
        return None

    subj = t.split("what color")[-1]
    for v in [" is ", " are ", " does ", " do "]:
        subj = subj.replace(v, " ")
    subj = subj.strip()

    color = parser.loom.get(subj, "color")
    if color:
        verb = "are" if is_plural(subj) else "is"
        return f"{subj.title()} {verb} {color[0]}."
    else:
        parser.loom.add_fact(subj, "has_open_question", "color")
        return f"I don't know the color of {subj} yet. What color is it?"


def _check_where_query(parser, t: str) -> str | None:
    """Handle 'where is X?' or 'where do X live?' or 'where can X be found?' queries."""
    if not t.startswith("where"):
        # Also handle "X can be found where?" style but that's rare
        return None

    # Extract subject — strip common question patterns
    subj = re.sub(r"where (is|are|do|does|can|did|would)?\s*", "", t).strip()
    subj = re.sub(r"\s*(live|lives|located|found|be found|stay|run|runs).*", "", subj).strip()

    if not subj:
        return None

    # Check various location relations (try singular/plural)
    for rel in ["located_in", "lives_in", "found_in", "can_live", "can_live_in", "runs_on"]:
        loc = parser._try_get(subj, rel)
        if loc:
            loc_str = format_list([l.replace('_', ' ') for l in loc])
            if rel == "lives_in":
                verb = "live" if is_plural(subj) else "lives"
                return f"{subj.title()} {verb} in {loc_str}."
            elif rel in ["can_live", "can_live_in"]:
                return f"{subj.title()} can live in {loc_str}."
            elif rel == "runs_on":
                verb = "run" if is_plural(subj) else "runs"
                return f"{subj.title()} {verb} on {loc_str}."
            else:
                verb = "are" if is_plural(subj) else "is"
                return f"{subj.title()} {verb} found in {loc_str}."

    parser.loom.add_fact(subj, "has_open_question", "location")
    return f"I don't know where {subj} is. Where can it be found?"


def _check_what_lives_query(parser, t: str) -> str | None:
    """Handle 'what X live in Y?' queries - find entities by location."""
    # Match "what animals live in the ocean" or "what lives in water"
    match = re.match(r"what\s+(\w+)?\s*(?:live|lives|living)\s+(?:in|on)\s+(?:the\s+)?(.+)", t)
    if not match:
        return None

    category = match.group(1)  # e.g., "animals" (may be None)
    location = match.group(2).strip()  # e.g., "ocean"

    results = []

    # Search for entities that live in this location
    for node, relations in parser.loom.knowledge.items():
        if node == "self":
            continue

        # Check if entity lives in the specified location
        entity_locations = relations.get("lives_in", [])
        location_match = False
        for loc in entity_locations:
            if normalize(location) in normalize(loc) or normalize(loc) in normalize(location):
                location_match = True
                break

        if not location_match:
            continue

        # If a category was specified, check if entity belongs to it
        if category:
            entity_cats = relations.get("is", [])
            category_match = False
            for cat in entity_cats:
                if normalize(category) in normalize(cat) or normalize(cat) in normalize(category):
                    category_match = True
                    break
            if not category_match:
                continue

        results.append(prettify(node))

    if results:
        if len(results) == 1:
            return f"{results[0].title()} lives in {location}."
        else:
            return f"{format_list([r.title() for r in results])} live in {location}."
    else:
        category_str = f" {category}" if category else ""
        return f"I don't know what{category_str} lives in {location}."


def _check_who_query(parser, t: str) -> str | None:
    """Handle 'who is X?' and 'who verb X?' queries (e.g., 'who built the pyramids?')."""
    from .relations import VERB_TO_RELATION_MAP, get_relation_for_verb

    if not t.startswith("who"):
        return None

    # Pattern 1: "who verb X?" (e.g., "who built the pyramids?", "who invented gunpowder?")
    verbs = "|".join(VERB_TO_RELATION_MAP.keys())
    match = re.match(rf"who\s+({verbs})\s+(?:the\s+)?(.+)", t)
    if match:
        verb = match.group(1).lower()
        obj = match.group(2).strip().rstrip('?')

        # Get relation from verb
        rel_def = get_relation_for_verb(verb)
        relation = rel_def.relation if rel_def else verb
        past_tense = rel_def.past if rel_def else verb

        # Reverse lookup: find entities where relation -> obj
        obj_norm = normalize(obj)
        results = []
        for entity, relations in parser.loom.knowledge.items():
            if entity == "self":
                continue
            rel_values = relations.get(relation, [])
            for val in rel_values:
                if normalize(val) == obj_norm or obj_norm in normalize(val):
                    results.append(prettify(entity))
                    break

        if results:
            if len(results) == 1:
                return f"{results[0].title()} {past_tense} {obj}."
            else:
                return f"{format_list([r.title() for r in results])} {past_tense} {obj}."
        else:
            return f"I don't know who {past_tense} {obj}."

    # Pattern 2: "who is/are X?" (identity query)
    subj = re.sub(r"who (is|are|was|were)?\s*", "", t).strip()
    if not subj:
        return None

    facts = parser.loom.get(subj, "is")
    if facts:
        return f"{subj.title()} is {facts[0]}."

    parser.loom.add_fact(subj, "has_open_question", "identity")
    return f"I don't know who {subj} is. Can you tell me?"


def _check_what_has_query(parser, t: str) -> str | None:
    """Handle 'what does X have?' or 'does X have Y?' or 'do X verb Y?' or 'did X verb Y?' queries."""
    from .relations import VERB_TO_RELATION_MAP, get_relation_for_verb

    # Build regex from all known verbs
    verbs = "|".join(VERB_TO_RELATION_MAP.keys())

    # Pattern 1: "did X verb Y?" (past tense yes/no)
    match = re.match(rf"did\s+(?:the\s+)?(.+?)\s+({verbs})\s+(?:the\s+)?(.+)", t)
    if match:
        subj = match.group(1).strip()
        verb = match.group(2).lower()
        obj = match.group(3).strip().rstrip('?')

        # Look up relation from unified definitions
        rel_def = get_relation_for_verb(verb)
        relation = rel_def.relation if rel_def else verb
        past_tense = rel_def.past if rel_def else verb

        # Try with "ancient_" prefix for historical entities
        things = parser._try_get(subj, relation)
        if not things:
            things = parser._try_get(f"ancient_{subj}", relation)

        # Check if the object matches any stored facts
        obj_norm = normalize(obj)
        for thing in things:
            if obj_norm in normalize(thing) or normalize(thing) in obj_norm:
                return f"Yes, {subj.title()} {past_tense} {obj}."

        return f"I don't know if {subj} {past_tense} {obj}."

    # Pattern 2: "do/does X verb Y?" (present tense yes/no)
    match = re.match(rf"do(?:es)?\s+(.+?)\s+({verbs})\s+(.+)", t)
    if match:
        subj = match.group(1).strip()
        verb = match.group(2).lower()
        obj = match.group(3).strip()

        # Look up relation from unified definitions
        rel_def = get_relation_for_verb(verb)
        relation = rel_def.relation if rel_def else verb

        things = parser._try_get(subj, relation)

        # Check if the object matches any stored facts
        obj_norm = normalize(obj)
        for thing in things:
            if obj_norm in normalize(thing) or normalize(thing) in obj_norm:
                verb_display = verb if is_plural(subj) else (verb + "s" if not verb.endswith("s") else verb)
                return f"Yes, {subj} {verb_display} {obj}."

        verb_display = verb if is_plural(subj) else (verb + "s" if not verb.endswith("s") else verb)
        return f"I don't know if {subj} {verb_display} {obj}."

    # Pattern 3: "is/are X phrase Y?" (e.g., "Are giraffes native to Africa?")
    # Build phrases from present_s/present_p that start with "is " or "are "
    from .relations import RELATION_DEFS
    phrase_patterns = []
    for r in RELATION_DEFS:
        # Extract phrase after "is " or "are "
        if r.present_s and r.present_s.startswith("is "):
            phrase = r.present_s[3:]  # Remove "is "
            phrase_patterns.append((phrase, r.relation))
        if r.present_p and r.present_p.startswith("are "):
            phrase = r.present_p[4:]  # Remove "are "
            if (phrase, r.relation) not in phrase_patterns:
                phrase_patterns.append((phrase, r.relation))

    # Sort by length (longest first) to match more specific phrases first
    phrase_patterns.sort(key=lambda x: len(x[0]), reverse=True)

    for phrase, relation in phrase_patterns:
        # Match "is/are X phrase Y?"
        pattern = rf"(?:is|are)\s+(?:the\s+)?(.+?)\s+{re.escape(phrase)}\s+(?:the\s+)?(.+)"
        match = re.match(pattern, t, re.IGNORECASE)
        if match:
            subj = match.group(1).strip()
            obj = match.group(2).strip().rstrip('?')

            things = parser._try_get(subj, relation)

            # Check if the object matches any stored facts
            obj_norm = normalize(obj)
            for thing in things:
                if obj_norm in normalize(thing) or normalize(thing) in obj_norm:
                    verb_form = "is" if not is_plural(subj) else "are"
                    return f"Yes, {subj} {verb_form} {phrase} {obj}."

            verb_form = "is" if not is_plural(subj) else "are"
            return f"I don't know if {subj} {verb_form} {phrase} {obj}."

    # "what does X have?"
    match = re.match(r"what do(?:es)?\s+(.+?)\s+have", t)
    if match:
        subj = match.group(1)
        # Use _try_get to handle singular/plural variations
        things = parser._try_get(subj, "has")
        if things:
            verb = "have" if is_plural(subj) else "has"
            # Replace underscores with spaces for display
            display = [x.replace("_", " ") for x in things]
            return f"{subj.title()} {verb} {format_list(display)}."
        else:
            parser.loom.add_fact(subj, "has_open_question", "possessions")
            return f"I don't know what {subj} has yet."

    return None


def _check_what_verb_query(parser, t: str) -> str | None:
    """Handle 'what do X verb?' queries for many common verbs."""
    from .relations import PRESENT_VERB_MAP, get_relation_for_verb

    # Build regex from all known base verbs
    verbs = "|".join(PRESENT_VERB_MAP.keys())
    match = re.match(rf"what do(?:es)?\s+(.+?)\s+({verbs})", t)
    if match:
        subj = match.group(1).strip()
        verb = match.group(2).lower()

        # Look up relation from unified definitions
        rel_def = get_relation_for_verb(verb)
        relation = rel_def.relation if rel_def else verb

        things = parser.loom.get(subj, relation)
        if things:
            # Replace underscores with spaces for display
            display = [x.replace("_", " ") for x in things]
            return f"{subj.title()} {verb} {format_list(display)}."
        else:
            return f"I don't know what {subj} {verb}."

    return None


def _check_how_many_query(parser, t: str) -> str | None:
    """Handle 'how many X does Y have?' queries."""
    match = re.match(r"how many\s+(\w+)\s+(?:does|do)\s+(?:a\s+|an\s+|the\s+)?(\w+)\s+have", t)
    if match:
        thing, subj = match.groups()
        # Check "has" relation for counts
        has_items = parser.loom.get(subj, "has") or []
        for item in has_items:
            # Look for numeric patterns like "four_legs" or "two_eyes"
            if thing in item or item.endswith(thing):
                return f"{subj.title()} has {item.replace('_', ' ')}."

        return f"I don't know how many {thing} {subj} has."
    return None


def _check_how_tall_query(parser, t: str) -> str | None:
    """Handle 'how tall is/are X?' and 'how tall can X be/get?' queries."""
    # Match "how tall is/are X" or "how tall can X be/get"
    match = re.match(r"how tall\s+(?:is|are|can)\s+(?:a\s+|an\s+|the\s+)?(\w+)(?:\s+(?:be|get))?", t)
    if not match:
        return None

    subj = match.group(1)
    subj_norm = normalize(subj)

    # Check for height-related properties
    # 1. Check if subject "has" anything with height/tall
    has_items = parser.loom.get(subj, "has") or []
    for item in has_items:
        if 'height' in item.lower() or 'tall' in item.lower():
            # Found height property, check if it has more details
            item_details = parser.loom.get(item, "can") or []
            if item_details:
                detail_str = format_list([d.replace('_', ' ') for d in item_details])
                return f"{subj.title()}'s {item.replace('_', ' ')} can {detail_str}."
            return f"{subj.title()} has {item.replace('_', ' ')}."

    # 2. Check direct "height" relation
    height = parser.loom.get(subj, "height") or []
    if height:
        return f"{subj.title()}'s height is {format_list(height)}."

    # 3. Check "is" relation for tall
    is_props = parser.loom.get(subj, "is") or []
    for prop in is_props:
        if 'tall' in prop.lower():
            return f"{subj.title()} is {prop.replace('_', ' ')}."

    return f"I don't know how tall {subj} is."


def _check_made_of_query(parser, t: str) -> str | None:
    """Handle 'what is X made of?' queries."""
    match = re.match(r"what\s+(?:is|are)\s+(?:a\s+|an\s+|the\s+)?(\w+)\s+made\s+(?:of|from)", t)
    if match:
        subj = match.group(1)
        materials = parser.loom.get(subj, "made_of") or []
        if materials:
            return f"{subj.title()} is made of {format_list(materials)}."
        return f"I don't know what {subj} is made of."
    return None


def _check_part_of_query(parser, t: str) -> str | None:
    """Handle 'what is X part of?' or 'is X part of Y?' queries."""
    # "what is X part of?"
    match = re.match(r"what\s+(?:is|are)\s+(?:a\s+|an\s+|the\s+)?(\w+)\s+part\s+of", t)
    if match:
        subj = match.group(1)
        wholes = parser.loom.get(subj, "part_of") or []
        if wholes:
            return f"{subj.title()} is part of {format_list(wholes)}."
        return f"I don't know what {subj} is part of."

    # "is X part of Y?"
    match = re.match(r"(?:is|are)\s+(?:a\s+|an\s+|the\s+)?(\w+)\s+part\s+of\s+(?:a\s+|an\s+|the\s+)?(\w+)", t)
    if match:
        part, whole = match.groups()
        parts = parser.loom.get(part, "part_of") or []
        if normalize(whole) in [normalize(p) for p in parts]:
            return f"Yes, {part} is part of {whole}."
        return f"I don't know if {part} is part of {whole}."

    return None


def _check_what_does_query(parser, t: str) -> str | None:
    """Handle 'what does X verb?' queries — works with ANY verb, not just known ones."""
    from .relations import get_relation_for_verb

    # Match "what does/do X verb [preposition]?" with any verb
    match = re.match(r"what do(?:es)?\s+(.+?)\s+(\w+)(?:\s+(\w+))?\s*\??$", t)
    if not match:
        return None

    subj = match.group(1).strip()
    verb = match.group(2).strip()
    prep = match.group(3)  # Optional preposition (e.g., "live in")

    # Skip if verb is "do" (handled by _check_what_do_generic_query)
    if verb == "do":
        return None

    # Build the relation to look up
    rel_def = get_relation_for_verb(verb)
    if rel_def:
        relation = rel_def.relation
    else:
        # Use the verb directly — matches how SVO stores it
        # Also try with -s suffix (third person: "exports")
        relation = verb

    # Try the relation as-is, then with -s (third person form)
    things = parser.loom.get(subj, relation)
    if not things and not relation.endswith("s"):
        things = parser.loom.get(subj, relation + "s")
        if things:
            relation = relation + "s"

    # Also try with preposition attached (e.g., "flow" + "through" -> "flows_through")
    if not things and prep:
        things = parser.loom.get(subj, f"{relation}_{prep}")
        if not things:
            things = parser.loom.get(subj, f"{relation}s_{prep}")

    if things:
        verb_form = verb if is_plural(subj) else verb + "s"
        display = [x.replace("_", " ") for x in things]
        return f"{subj.title()} {verb_form} {format_list(display)}."
    else:
        parser.loom.add_fact(subj, "has_open_question", relation)
        verb_form = verb if is_plural(subj) else verb + "s"
        return f"I don't know what {subj} {verb_form} yet."


def _check_what_do_generic_query(parser, t: str) -> str | None:
    """Handle 'what do X do?' or 'what does X do?' queries - find any action relation."""
    match = re.match(r"what do(?:es)?\s+(.+?)\s+do\s*\??$", t)
    if not match:
        return None

    subj = match.group(1).strip()

    # Check common action relations
    action_relations = [
        ("moves", "move"),
        ("helps", "help"),
        ("causes", "cause"),
        ("produces", "produce"),
        ("provides", "provide"),
        ("protects", "protect"),
        ("carries", "carry"),
        ("controls", "control"),
        ("eats", "eat"),
        ("makes", "make"),
        ("creates", "create"),
        ("pumps", "pump"),
        ("plays", "play"),
    ]

    for relation, verb in action_relations:
        things = parser.loom.get(subj, relation)
        if things:
            display = [x.replace("_", " ") for x in things]
            verb_form = verb if is_plural(subj) else verb + "s"
            return f"{subj.title()} {verb_form} {format_list(display)}."

    return f"I don't know what {subj} does."


# ==================== REVERSE QUERIES ====================
# These find entities by their properties (reverse lookups)

def _check_what_has_reverse_query(parser, t: str) -> str | None:
    """Handle 'what has X?' queries - find entities with property X."""
    # Pattern: "what has wings" or "what has fur"
    match = re.match(r"what\s+(?:has|have)\s+(.+)", t)
    if not match:
        return None

    target_property = normalize(match.group(1).strip())

    # Search for entities that have this property
    results = []
    for entity, relations in parser.loom.knowledge.items():
        if entity == "self":
            continue
        has_items = relations.get("has", [])
        for item in has_items:
            if normalize(item) == target_property or target_property in normalize(item):
                results.append(prettify(entity))
                break

    if results:
        prop_display = target_property.replace("_", " ")
        if len(results) == 1:
            return f"{results[0].title()} has {prop_display}."
        else:
            return f"{format_list([r.title() for r in results])} have {prop_display}."
    else:
        return f"I don't know what has {target_property.replace('_', ' ')}."


def _check_what_eats_reverse_query(parser, t: str) -> str | None:
    """Handle 'what eats X?' queries - find entities that eat X."""
    match = re.match(r"what\s+(?:eats?|consumes?)\s+(.+)", t)
    if not match:
        return None

    target_food = normalize(match.group(1).strip())

    results = []
    for entity, relations in parser.loom.knowledge.items():
        if entity == "self":
            continue
        eats_items = relations.get("eats", [])
        for item in eats_items:
            if normalize(item) == target_food or target_food in normalize(item):
                results.append(prettify(entity))
                break

    if results:
        food_display = target_food.replace("_", " ")
        if len(results) == 1:
            return f"{results[0].title()} eats {food_display}."
        else:
            return f"{format_list([r.title() for r in results])} eat {food_display}."
    else:
        return f"I don't know what eats {target_food.replace('_', ' ')}."


def _check_what_can_reverse_query(parser, t: str) -> str | None:
    """Handle 'what can X?' queries - find entities with ability X."""
    match = re.match(r"what\s+can\s+(.+)", t)
    if not match:
        return None

    captured = match.group(1).strip()
    # Skip "what can X do?" patterns - those are handled by _check_can_query
    if captured.endswith(' do') or ' do ' in captured:
        return None

    ability = normalize(captured)

    results = []
    for entity, relations in parser.loom.knowledge.items():
        if entity == "self":
            continue
        can_items = relations.get("can", [])
        for item in can_items:
            if normalize(item) == ability or ability in normalize(item):
                results.append(prettify(entity))
                break

    if results:
        ability_display = ability.replace("_", " ")
        if len(results) == 1:
            return f"{results[0].title()} can {ability_display}."
        else:
            return f"{format_list([r.title() for r in results])} can {ability_display}."
    else:
        return f"I don't know what can {ability.replace('_', ' ')}."


def _check_what_is_reverse_query(parser, t: str) -> str | None:
    """Handle 'what is a X?' to find instances - e.g., 'what is a mammal?'"""
    match = re.match(r"what\s+(?:is|are)\s+(?:a|an)\s+(.+)", t)
    if not match:
        return None

    category = normalize(match.group(1).strip())

    # Find instances of this category
    results = []
    for entity, relations in parser.loom.knowledge.items():
        if entity == "self":
            continue
        is_items = relations.get("is", [])
        for item in is_items:
            if normalize(item) == category or category in normalize(item):
                results.append(prettify(entity))
                break

    if results:
        cat_display = category.replace("_", " ")
        if len(results) == 1:
            return f"{results[0].title()} is a {cat_display}."
        else:
            return f"{format_list([r.title() for r in results])} are {cat_display}s."
    else:
        return f"I don't know any {category.replace('_', ' ')}s."


def _check_what_needs_reverse_query(parser, t: str) -> str | None:
    """Handle 'what needs X?' queries - find entities that need X."""
    match = re.match(r"what\s+(?:needs?|requires?)\s+(.+)", t)
    if not match:
        return None

    target = normalize(match.group(1).strip())

    results = []
    for entity, relations in parser.loom.knowledge.items():
        if entity == "self":
            continue
        needs_items = relations.get("needs", [])
        for item in needs_items:
            if normalize(item) == target or target in normalize(item):
                results.append(prettify(entity))
                break

    if results:
        target_display = target.replace("_", " ")
        if len(results) == 1:
            return f"{results[0].title()} needs {target_display}."
        else:
            return f"{format_list([r.title() for r in results])} need {target_display}."
    else:
        return f"I don't know what needs {target.replace('_', ' ')}."


def _check_what_did_query(parser, t: str) -> str | None:
    """Handle 'what did X verb?' queries for past-tense actions (historical events)."""
    from .relations import VERB_TO_RELATION_MAP, get_relation_for_verb

    # Build regex pattern from all known verbs
    verbs = "|".join(VERB_TO_RELATION_MAP.keys())
    match = re.match(rf"what did\s+(?:the\s+)?(.+?)\s+({verbs})\b", t)
    if match:
        subj = match.group(1).strip()
        verb = match.group(2).lower()

        # Look up relation and past tense from unified definitions
        rel_def = get_relation_for_verb(verb)
        if rel_def:
            relation = rel_def.relation
            past_tense = rel_def.past
        else:
            relation = verb
            past_tense = verb

        # Try to get facts with this relation
        things = parser._try_get(subj, relation)

        # If not found, try with "ancient_" prefix (common for historical entities)
        if not things:
            things = parser._try_get(f"ancient_{subj}", relation)

        if things:
            # Replace underscores with spaces for display
            display = [x.replace("_", " ") for x in things]
            # Use past tense in response
            return f"{subj.title()} {past_tense} {format_list(display)}."
        else:
            return f"I don't know what {subj} {past_tense}."

    return None


def _check_what_verb_reverse_query(parser, t: str) -> str | None:
    """Handle reverse lookup queries like 'what provides X?', 'what built X?', 'what filters X?'."""
    from .relations import VERB_TO_RELATION_MAP, get_relation_for_verb

    # Build dynamic pattern from all known verbs
    verbs = "|".join(sorted(VERB_TO_RELATION_MAP.keys(), key=len, reverse=True))
    match = re.match(rf"what\s+({verbs})\s+(?:the\s+)?(.+)", t, re.IGNORECASE)

    if not match:
        return None

    verb = match.group(1).lower()
    target = match.group(2).strip().rstrip('?')
    target_norm = normalize(target)

    # Get relation from verb
    rel_def = get_relation_for_verb(verb)
    if not rel_def:
        return None

    relation = rel_def.relation
    present_s = rel_def.present_s or verb
    past = rel_def.past or verb

    # Reverse lookup: find entities where relation -> target
    results = []
    for entity, relations in parser.loom.knowledge.items():
        if entity == "self":
            continue

        items = relations.get(relation, [])
        for item in items:
            item_norm = normalize(item)
            if target_norm == item_norm or target_norm in item_norm or item_norm in target_norm:
                results.append(prettify(entity))
                break

    if results:
        # Use appropriate verb form
        verb_display = present_s if len(results) == 1 else (rel_def.present_p or verb)
        target_display = target.replace('_', ' ')
        if len(results) == 1:
            return f"{results[0].title()} {verb_display} {target_display}."
        else:
            return f"{format_list([r.title() for r in results])} {verb_display} {target_display}."

    return None
