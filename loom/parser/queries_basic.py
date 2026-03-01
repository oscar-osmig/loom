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
    """Handle 'where is X?' or 'where do X live?' queries."""
    if not t.startswith("where"):
        return None

    # Extract subject
    subj = re.sub(r"where (is|are|do|does|can|did)?\s*", "", t).strip()
    subj = re.sub(r"\s*(live|located|found|stay).*", "", subj).strip()

    if not subj:
        return None

    # Check various location relations (try singular/plural)
    for rel in ["located_in", "lives_in", "found_in", "can_live", "can_live_in"]:
        loc = parser._try_get(subj, rel)
        if loc:
            verb = "are" if is_plural(subj) else "is"
            if rel in ["can_live", "can_live_in"]:
                verb = "can live"
                return f"{subj.title()} {verb} in {format_list([l.replace('_', ' ') for l in loc])}."
            return f"{subj.title()} {verb} in {loc[0]}."

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
    """Handle 'who is X?' queries."""
    if not t.startswith("who"):
        return None

    subj = re.sub(r"who (is|are|was|were)?\s*", "", t).strip()
    if not subj:
        return None

    facts = parser.loom.get(subj, "is")
    if facts:
        return f"{subj.title()} is {facts[0]}."

    parser.loom.add_fact(subj, "has_open_question", "identity")
    return f"I don't know who {subj} is. Can you tell me?"


def _check_what_has_query(parser, t: str) -> str | None:
    """Handle 'what does X have?' or 'does X have Y?' queries."""
    # "does X have Y?"
    match = re.match(r"do(?:es)?\s+(.+?)\s+have\s+(.+)", t)
    if match:
        subj, obj = match.groups()
        things = parser.loom.get(subj, "has")
        if things and normalize(obj) in [normalize(x) for x in things]:
            verb = "have" if is_plural(subj) else "has"
            return f"Yes, {subj} {verb} {obj}."
        else:
            verb = "have" if is_plural(subj) else "has"
            return f"I don't know if {subj} {verb} {obj}."

    # "what does X have?"
    match = re.match(r"what do(?:es)?\s+(.+?)\s+have", t)
    if match:
        subj = match.group(1)
        things = parser.loom.get(subj, "has")
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
    """Handle 'what do X drink/eat/need/use?' queries."""
    # Map verbs to relations
    verb_map = {
        "drink": "drinks", "drinks": "drinks",
        "eat": "eats", "eats": "eats",
        "need": "needs", "needs": "needs",
        "use": "uses", "uses": "uses",
        "like": "likes", "likes": "likes",
        "want": "wants", "wants": "wants",
    }

    match = re.match(r"what do(?:es)?\s+(.+?)\s+(drink|drinks|eat|eats|need|needs|use|uses|like|likes|want|wants)", t)
    if match:
        subj = match.group(1).strip()
        verb = match.group(2).lower()
        relation = verb_map.get(verb, verb)

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
    """Handle 'what does X eat/like/need/cause?' queries."""
    # Pattern: "what do(es) X verb?"
    match = re.match(r"what do(?:es)?\s+(.+?)\s+(eat|like|love|need|want|use|fear|cause)", t)
    if match:
        subj, verb = match.groups()
        # Map verb to relation
        relation_map = {
            "eat": "eats", "like": "likes", "love": "loves",
            "need": "needs", "want": "wants", "use": "uses",
            "fear": "fears", "cause": "causes"
        }
        relation = relation_map.get(verb, verb)
        things = parser.loom.get(subj, relation)

        if things:
            verb_form = verb if is_plural(subj) else verb + "s"
            # Replace underscores with spaces for display
            display = [x.replace("_", " ") for x in things]
            return f"{subj.title()} {verb_form} {format_list(display)}."
        else:
            parser.loom.add_fact(subj, "has_open_question", relation)
            verb_form = verb if is_plural(subj) else verb + "s"
            return f"I don't know what {subj} {verb_form} yet."

    return None
