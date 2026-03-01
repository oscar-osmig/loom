"""
Complex query methods for the Parser class.
Handles more complex question-answering queries involving abilities, comparisons, and causality.
"""

import re
from ..normalizer import normalize, prettify, prettify_cause, prettify_effect
from ..grammar import is_plural, format_list, is_adjective


def _check_can_query(parser, t: str) -> str | None:
    """Handle 'can X do Y?' or 'what can X do?' or 'what X can Y?' queries."""
    # "what X can't/cannot Y?" - e.g., "what birds can't fly?"
    # Handle different apostrophe characters: ' (straight) and ' (curly)
    match = re.match(r"what\s+(\w+)\s+(?:can[''']t|cannot|can not)\s+(\w+)", t)
    if match:
        category, ability = match.groups()
        # Search for entities that are of category X and cannot do Y
        results = []
        for node, relations in parser.loom.knowledge.items():
            # Check if node is of the category
            is_category = False
            if "is" in relations:
                for cat in relations["is"]:
                    if normalize(category) in normalize(cat) or normalize(cat) in normalize(category):
                        is_category = True
                        break
            # Check if node cannot do the ability
            has_inability = False
            if "cannot" in relations:
                for ab in relations["cannot"]:
                    if normalize(ability) in normalize(ab) or normalize(ab) in normalize(ability):
                        has_inability = True
                        break
            if is_category and has_inability:
                results.append(prettify(node))

        if results:
            if len(results) == 1:
                return f"{results[0].title()} cannot {ability}."
            else:
                return f"{format_list([r.title() for r in results])} cannot {ability}."
        else:
            return f"I don't know what {category} cannot {ability}."

    # "what X can Y?" - e.g., "what bird can soar?"
    match = re.match(r"what\s+(\w+)\s+can\s+(\w+)", t)
    if match:
        category, ability = match.groups()
        # Search for entities that are of category X and can do Y
        results = []
        for node, relations in parser.loom.knowledge.items():
            # Check if node is of the category
            is_category = False
            if "is" in relations:
                for cat in relations["is"]:
                    if normalize(category) in normalize(cat) or normalize(cat) in normalize(category):
                        is_category = True
                        break
            # Check if node can do the ability
            has_ability = False
            if "can" in relations:
                for ab in relations["can"]:
                    if normalize(ability) in normalize(ab) or normalize(ab) in normalize(ability):
                        has_ability = True
                        break
            if is_category and has_ability:
                results.append(prettify(node))

        if results:
            if len(results) == 1:
                return f"{results[0].title()} can {ability}."
            else:
                return f"{format_list([r.title() for r in results])} can {ability}."
        else:
            return f"I don't know what {category} can {ability}."

    # "what can X do?"
    match = re.match(r"what can\s+(.+?)\s+do", t)
    if match:
        subj = match.group(1)
        abilities = parser.loom.get(subj, "can")
        if abilities:
            # Replace underscores for display
            display = [a.replace("_", " ") for a in abilities]
            return f"{subj.title()} can {format_list(display)}."
        else:
            # Check for cannot
            cannot = parser.loom.get(subj, "cannot")
            if cannot:
                display = [a.replace("_", " ") for a in cannot]
                return f"I know {subj} cannot {format_list(display)}."
            parser.loom.add_fact(subj, "has_open_question", "abilities")
            return f"I don't know what {subj} can do yet."

    # "can X do Y?" or "can X Y?"
    match = re.match(r"can\s+(.+?)\s+(\w+)(?:\s|$)", t)
    if match:
        subj, action = match.groups()

        # First check "cannot"
        cannot = parser.loom.get(subj, "cannot") or []
        for inability in cannot:
            if action in inability or inability.startswith(action):
                return f"No, {subj} cannot {inability.replace('_', ' ')}."

        # Then check "can"
        abilities = parser.loom.get(subj, "can") or []
        if abilities:
            for ability in abilities:
                if action in ability or ability.startswith(action):
                    return f"Yes, {subj} can {ability.replace('_', ' ')}."
            abilities_display = [a.replace('_', ' ') for a in abilities]
            return f"I know {subj} can {format_list(abilities_display)}, but I'm not sure about {action}."

        # Neither can nor cannot found
        parser.loom.add_fact(subj, "has_open_question", "abilities")
        return f"I don't know if {subj} can {action}."

    return None


def _check_are_is_query(parser, t: str) -> str | None:
    """Handle 'are X Y?' or 'is X Y?' queries."""
    # Match "are cats hunters" or "is the sky blue"
    match = re.match(r"(?:are|is)\s+(.+?)\s+(\w+)$", t)
    if not match:
        return None

    subj, obj = match.groups()
    subj = subj.strip()
    obj = obj.strip()

    # Clean subject
    for prefix in ["the ", "a ", "an "]:
        if subj.startswith(prefix):
            subj = subj[len(prefix):]

    # Track subject for pronoun resolution
    parser.last_subject = subj
    parser.loom.context.update(subject=subj)

    obj_norm = normalize(obj)
    verb = "are" if is_plural(subj) else "is"

    # Check if subj is obj (category)
    facts = parser.loom.get(subj, "is") or []
    for fact in facts:
        if obj_norm in normalize(fact) or normalize(fact) in obj_norm:
            return f"Yes, {subj} {verb} {obj}."

    # Check has_property relation (for adjectives like "intelligent", "dangerous")
    properties = parser.loom.get(subj, "has_property") or []
    for prop in properties:
        if obj_norm in normalize(prop) or normalize(prop) in obj_norm:
            return f"Yes, {subj} {verb} {obj}."

    # Check can_be relation (for quantified facts: "some cats are friendly")
    can_be = parser.loom.get(subj, "can_be") or []
    for possibility in can_be:
        if obj_norm in normalize(possibility) or normalize(possibility) in obj_norm:
            return f"Yes, some {subj} {verb} {obj}."

    # Check negative
    negatives = parser.loom.get(subj, "is_not") or []
    for neg in negatives:
        if obj_norm in normalize(neg):
            return f"No, {subj} {verb} not {obj}."

    # CLOSED WORLD ASSUMPTION: If we know about the entity but don't have this property,
    # assume the answer is NO and provide context about what we DO know
    if facts or properties:
        # We know something about this entity, so apply CWA
        context_info = []
        # Add what we know about the entity
        if properties:
            context_info.extend([p.replace("_", " ") for p in properties[:2]])
        if facts:
            context_info.extend([f.replace("_", " ") for f in facts[:1]])

        if context_info:
            context_str = format_list(context_info)
            return f"No, but {subj} {verb} {context_str}."
        else:
            return f"No, {subj} {verb} not {obj}."

    return f"I don't know if {subj} {verb} {obj}."


def _check_why_query(parser, t: str) -> str | None:
    """Handle 'why does X happen?' or 'why X need Y?' queries."""
    if not t.startswith("why"):
        return None

    # Pattern: "why X need/needs Y" or "why do X need Y"
    need_match = re.match(r"why (?:do |does )?(\w+) (?:need|needs?) (.+)", t)
    if need_match:
        subj = need_match.group(1).strip()
        needed_thing = need_match.group(2).strip()

        # Check if we know what this subject needs
        needs = parser.loom.get(subj, "needs") or []
        properties = parser.loom.get(subj, "has_property") or []
        categories = parser.loom.get(subj, "is") or []

        if needs or properties:
            # We have information to answer
            if properties:
                prop = properties[0].replace("_", " ")
                return f"Because {subj} are {prop}, so they need {needed_thing}."
            elif categories:
                # Check if any category looks like an adjective (property)
                for cat in categories:
                    if is_adjective(cat):
                        return f"Because {subj} are {cat.replace('_', ' ')}, so they need {needed_thing}."
                cat = categories[0].replace("_", " ")
                return f"Because {subj} are {cat}."

        return f"I don't know why {subj} need {needed_thing}."

    # Extract what we're asking about
    subj = re.sub(r"why (do|does|is|are|did)?\s*", "", t).strip()
    subj = re.sub(r"\s*(happen|occur|exist).*", "", subj).strip()

    if not subj:
        return None

    # Track subject for pronoun resolution
    parser.last_subject = subj
    parser.loom.context.update(subject=subj)

    # Look for causes (reverse lookup)
    # Check if anything causes this subject
    for node in parser.loom.knowledge:
        causes = parser.loom.get(node, "causes")
        if causes and normalize(subj) in [normalize(c) for c in causes]:
            return f"Because {node} causes it."

    parser.loom.add_fact(subj, "has_open_question", "reason")
    return f"I don't know why {subj}. What's the reason?"


def _check_what_causes_query(parser, t: str) -> str | None:
    """Handle 'what causes X?' queries."""
    # Match "what causes X" or "what cause X"
    match = re.match(r"what\s+causes?\s+(.+)", t)
    if not match:
        return None

    effect = match.group(1).strip()
    effect_norm = normalize(effect)

    # Search for what causes this effect
    causes = []
    for node, relations in parser.loom.knowledge.items():
        if "causes" in relations:
            if effect_norm in relations["causes"] or effect in relations["causes"]:
                causes.append(node)

    if causes:
        # Use prettify (not prettify_cause) for simple noun formatting
        causes_pretty = [prettify(c) for c in causes[:3]]
        effect_pretty = prettify(effect)
        if len(causes) == 1:
            return f"{causes_pretty[0].capitalize()} causes {effect_pretty}."
        else:
            result = f"{', '.join(causes_pretty[:-1])} and {causes_pretty[-1]} cause {effect_pretty}."
            if len(causes) > 3:
                result += f" (+{len(causes) - 3} more)"
            return result
    else:
        return f"I don't know what causes {prettify(effect)} yet."


def _check_effect_query(parser, t: str) -> str | None:
    """Handle 'what happens when X?' queries."""
    if "what happens" not in t:
        return None

    subj = None
    if "when " in t:
        subj = t.split("when ")[-1].strip()

    if not subj:
        return None

    effects = parser.loom.get(subj, "causes")
    if effects:
        cause_pretty = prettify_cause(normalize(subj))
        # Only show first 3 direct effects to avoid chain explosion
        display_effects = effects[:3]
        effects_pretty = [prettify_effect(e) for e in display_effects]
        result = f"When {cause_pretty}, {' and '.join(effects_pretty)}."
        if len(effects) > 3:
            result += f" (+{len(effects) - 3} more)"
        return result
    else:
        parser.loom.add_fact(subj, "has_open_question", "effects")
        return f"I don't know what happens when {subj}. What occurs?"


def _check_lay_eggs_query(parser, t: str) -> str | None:
    """Handle 'which animals lay eggs?' queries."""
    patterns = [
        r"which\s+(?:animals?|groups?)\s+(?:usually\s+)?lay\s+eggs",
        r"what\s+(?:animals?|groups?)\s+lay\s+eggs",
        r"which\s+(?:animals?|groups?)\s+reproduce\s+(?:by|with)\s+eggs",
    ]

    for pattern in patterns:
        match = re.match(pattern, t, re.IGNORECASE)
        if match:
            # Search for entities that lay eggs
            results = []
            for entity, relations in parser.loom.knowledge.items():
                if entity == "self":
                    continue
                # Check for produces: eggs, lays: eggs, or reproduction: eggs
                if "produces" in relations and "eggs" in relations["produces"]:
                    results.append(entity)
                elif "lays" in relations and "eggs" in relations["lays"]:
                    results.append(entity)
                elif "reproduction" in relations and "eggs" in relations["reproduction"]:
                    results.append(entity)

            if results:
                display = [r.replace("_", " ").title() for r in results]
                return f"{format_list(display)} lay eggs."
            else:
                return "I don't know which animals lay eggs."

    return None


def _check_which_query(parser, t: str) -> str | None:
    """Handle 'which X has/have Y?' or 'which X is/are Y?' queries."""
    if not t.startswith("which"):
        return None

    # Pattern: "which group/type of X has Y" - find entities that have Y
    match = re.match(r"which\s+(?:group|type|kind)?\s*(?:of\s+)?(.+?)\s+(?:has|have)\s+(.+)", t)
    if match:
        category = match.group(1).strip()
        property_sought = match.group(2).strip()
        property_norm = normalize(property_sought)

        # Search for entities that have this property
        results = []
        for node, relations in parser.loom.knowledge.items():
            if node == "self":
                continue

            # Check if node has the property in "has" relation
            has_property = False
            if "has" in relations:
                for prop in relations["has"]:
                    prop_lower = prop.lower().replace("_", " ")
                    sought_lower = property_sought.lower()
                    if sought_lower in prop_lower or prop_lower in sought_lower:
                        has_property = True
                        break

            # Also check has_property for adjectives
            if not has_property and "has_property" in relations:
                for prop in relations["has_property"]:
                    prop_lower = prop.lower().replace("_", " ")
                    sought_lower = property_sought.lower()
                    if sought_lower in prop_lower or prop_lower in sought_lower:
                        has_property = True
                        break

            if has_property:
                results.append(prettify(node))

        if results:
            return f"{format_list([r.title() for r in results])} have {property_sought}."
        else:
            return f"I don't know which {category} has {property_sought}."

    # Pattern: "which X is/are Y" - find entities of type X that are Y
    match = re.match(r"which\s+(.+?)\s+(?:is|are)\s+(.+)", t)
    if match:
        category = match.group(1).strip()
        property_sought = match.group(2).strip()
        property_norm = normalize(property_sought)

        results = []
        for node, relations in parser.loom.knowledge.items():
            if node == "self":
                continue
            # Check if node is of the category
            is_category = False
            if "is" in relations:
                for cat in relations["is"]:
                    if normalize(category) in normalize(cat) or normalize(cat) in normalize(category):
                        is_category = True
                        break
            # Check if node has this property
            has_property = False
            if "has_property" in relations:
                for prop in relations["has_property"]:
                    if property_norm in normalize(prop) or normalize(prop) in property_norm:
                        has_property = True
                        break
            # Also check "is" for the property
            if "is" in relations:
                for prop in relations["is"]:
                    if property_norm in normalize(prop) or normalize(prop) in property_norm:
                        has_property = True
                        break
            if is_category and has_property:
                results.append(prettify(node))

        if results:
            verb = "are" if len(results) > 1 else "is"
            return f"{format_list([r.title() for r in results])} {verb} {property_sought}."
        else:
            return f"I don't know which {category} is {property_sought}."

    return f"I don't have enough information to answer that question."


def _check_difference_query(parser, t: str) -> str | None:
    """Handle 'what is the difference between X and Y?' or 'how are X different from Y?' queries."""
    # Pattern 1: "what is the difference between X and Y"
    match = re.match(r"what\s+(?:is|are)\s+(?:the\s+)?(?:difference|differences)\s+between\s+(.+?)\s+and\s+(.+)", t)

    # Pattern 2: "how are X different from Y"
    if not match:
        match = re.match(r"how\s+(?:is|are)\s+(.+?)\s+different\s+from\s+(.+)", t)

    if not match:
        return None

    subj1 = match.group(1).strip()
    subj2 = match.group(2).strip()

    differences = []

    # Compare has_property (try singular/plural)
    props1 = parser._try_get(subj1, "has_property")
    props2 = parser._try_get(subj2, "has_property")
    for p in props1:
        if p not in props2:
            differences.append(f"{subj1} are {p.replace('_', ' ')}")
    for p in props2:
        if p not in props1:
            differences.append(f"{subj2} are {p.replace('_', ' ')}")

    # Compare has
    has1 = parser._try_get(subj1, "has")
    has2 = parser._try_get(subj2, "has")
    for h in has1:
        if h not in has2:
            differences.append(f"{subj1} have {h.replace('_', ' ')}")
    for h in has2:
        if h not in has1:
            differences.append(f"{subj2} have {h.replace('_', ' ')}")

    # Compare produces
    prod1 = parser._try_get(subj1, "produces")
    prod2 = parser._try_get(subj2, "produces")
    for p in prod1:
        if p not in prod2:
            differences.append(f"{subj1} lay {p.replace('_', ' ')}")

    # Compare lives_in
    loc1 = parser._try_get(subj1, "lives_in")
    loc2 = parser._try_get(subj2, "lives_in")
    for l in loc1:
        if l not in loc2:
            differences.append(f"{subj1} live {l.replace('_', ' ')}")
    for l in loc2:
        if l not in loc1:
            differences.append(f"{subj2} live {l.replace('_', ' ')}")

    # Compare breathes_through
    br1 = parser._try_get(subj1, "breathes_through")
    br2 = parser._try_get(subj2, "breathes_through")
    for b in br2:
        if b not in br1:
            differences.append(f"{subj2} breathe {b.replace('_', ' ')}")

    if differences:
        return f"Differences: {'; '.join(differences[:4])}."
    else:
        return f"I don't know the differences between {subj1} and {subj2}."
