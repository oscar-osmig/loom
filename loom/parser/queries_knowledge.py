"""
Knowledge query methods for the Parser class.
Handles domain-specific knowledge queries about biology, classification, and characteristics.
"""

import re
from ..normalizer import normalize, prettify
from ..grammar import is_plural, format_list, singularize, pluralize


# Bridge relations that indicate related categories
BRIDGE_RELATIONS = ["equivalent_to", "overlaps_with", "similar_to", "subset_of"]


def _get_category_instances(parser, category: str) -> list:
    """
    Get all instances of a category, including instances from bridged categories.

    Bridge behavior (logically sound):
    - equivalent_to: These are synonyms, share ALL instances (bidirectional)
    - subset_of: A subset_of B means A's instances are also B's instances
      - When querying A: return A's instances only
      - When querying B: return B's instances + all subset categories' instances
    - overlaps_with: Categories share SOME instances, but not all
      - Only include instances that actually belong to BOTH categories
    - similar_to: Weak connection, don't auto-include instances

    Args:
        parser: The Parser instance
        category: The category to look up

    Returns:
        List of instance names
    """
    instances = set()
    checked_categories = set()

    def get_direct_instances(cat: str) -> set:
        """Get direct instances of a single category (no bridging)."""
        result = set()

        # Direct has_instance
        direct = parser.loom.get(cat, "has_instance") or []
        result.update(direct)

        # Try singular/plural variants
        singular = singularize(cat)
        plural = pluralize(cat)
        for variant in [singular, plural]:
            if variant != cat:
                variant_instances = parser.loom.get(variant, "has_instance") or []
                result.update(variant_instances)

        # Check entities where entity "is" this category
        cat_norm = normalize(cat)
        for entity in parser.loom.knowledge.keys():
            if entity == "self":
                continue
            is_targets = parser.loom.get(entity, "is") or []
            for target in is_targets:
                if normalize(target) == cat_norm:
                    result.add(entity)
                    break

        return result

    def collect_instances(cat: str, depth: int = 0):
        """Recursively collect instances from a category and its bridges."""
        if cat in checked_categories or depth > 2:
            return
        checked_categories.add(cat)

        # Get direct instances of this category
        direct = get_direct_instances(cat)
        instances.update(direct)

        # Handle equivalent_to (synonyms): include all instances
        equiv_cats = parser.loom.get(cat, "equivalent_to") or []
        for equiv_cat in equiv_cats:
            if equiv_cat not in checked_categories:
                collect_instances(equiv_cat, depth + 1)

        # Handle subset_of: if other categories are subsets of this one,
        # include their instances (since A ⊂ B means A's instances are B's instances)
        # We need to find categories where X subset_of this_category
        for other_cat in parser.loom.knowledge.keys():
            subset_targets = parser.loom.get(other_cat, "subset_of") or []
            if cat in subset_targets and other_cat not in checked_categories:
                # other_cat is a subset of cat, include its instances
                other_instances = get_direct_instances(other_cat)
                instances.update(other_instances)
                checked_categories.add(other_cat)

        # Handle overlaps_with: ONLY include the SHARED instances
        # (instances that belong to BOTH categories)
        overlap_cats = parser.loom.get(cat, "overlaps_with") or []
        for overlap_cat in overlap_cats:
            if overlap_cat not in checked_categories:
                overlap_instances = get_direct_instances(overlap_cat)
                # Find instances that are in BOTH categories
                shared = direct & overlap_instances
                instances.update(shared)
                # Don't add overlap_cat to checked_categories so we can still
                # process it directly if needed

        # similar_to: Don't auto-include instances (too weak a connection)
        # The user can query the similar category directly if interested

    # Start collection from the original category
    collect_instances(category)

    return list(instances)


def _check_reproduce_query(parser, t: str) -> str | None:
    """Handle 'how do X reproduce?' questions."""
    patterns = [
        r"how\s+(?:do|does)\s+(?:most\s+)?(.+?)\s+reproduce",
        r"how\s+(?:do|does)\s+(.+?)\s+(?:reproduce|breed|have\s+babies)",
    ]

    subj = None
    for pattern in patterns:
        match = re.match(pattern, t, re.IGNORECASE)
        if match:
            subj = match.group(1).strip()
            break

    if not subj:
        return None

    # Check can for reproduction
    abilities = parser.loom.get(subj, "can") or []
    for a in abilities:
        if "reproduce" in a:
            return f"{subj.title()} can {a.replace('_', ' ')}."

    return f"I don't know how {subj} reproduce."


def _check_classification_query(parser, t: str) -> str | None:
    """Handle 'what groups are X classified into?' queries."""
    patterns = [
        r"what\s+(?:are\s+)?(?:the\s+)?(?:major\s+)?groups?\s+(?:that\s+)?(.+?)\s+(?:are\s+)?classified\s+into",
        r"what\s+(?:are\s+)?(?:the\s+)?(?:major\s+)?groups?\s+of\s+(.+)",
        r"how\s+(?:are|is)\s+(.+?)\s+classified",
        r"what\s+types?\s+of\s+(.+?)\s+(?:are\s+there|exist)",
    ]

    subj = None
    for pattern in patterns:
        match = re.match(pattern, t, re.IGNORECASE)
        if match:
            subj = match.group(1).strip()
            break

    if not subj:
        return None

    # Look for includes_group facts (try singular/plural)
    groups = parser._try_get(subj, "includes_group")
    if groups:
        display = [g.replace("_", " ") for g in groups]
        return f"{subj.title()} are classified into {format_list(display)}."

    return f"I don't know what groups {subj} are classified into."


def _check_examples_query(parser, t: str) -> str | None:
    """Handle 'what are examples of X?' queries."""
    from ..normalizer import normalize, prettify

    patterns = [
        r"what\s+(?:are\s+)?(?:two|some|a\s+few)\s+examples?\s+of\s+(.+)",  # Moved first - more specific
        r"what\s+(?:are\s+)?(?:some\s+)?(?:examples?\s+of|types?\s+of)\s+(.+)",
        r"(?:give|name|list)\s+(?:some\s+)?examples?\s+of\s+(.+)",
    ]

    subj = None
    for pattern in patterns:
        match = re.match(pattern, t, re.IGNORECASE)
        if match:
            subj = match.group(1).strip()
            # Clean trailing phrases
            subj = re.sub(r'\s+mentioned.*$', '', subj).strip()
            subj = re.sub(r'\s+in\s+the\s+paragraph.*$', '', subj).strip()
            break

    if not subj:
        return None

    category = normalize(subj)
    examples = []

    # 1. Check "example" relation
    example_facts = parser._try_get(subj, "example")
    if example_facts:
        examples.extend(example_facts)

    # 2. Get instances using the helper (includes bridged categories)
    instances = _get_category_instances(parser, subj)
    for inst in instances:
        if inst not in examples:
            examples.append(inst)

    if examples:
        display = [prettify(e).replace("_", " ") for e in examples]
        return f"Examples of {subj}: {format_list(display)}."

    return f"I don't know any examples of {subj}."


def _check_breathing_query(parser, t: str) -> str | None:
    """Handle 'how do X breathe?' queries."""
    patterns = [
        r"how\s+(?:do|does)\s+(.+?)\s+breathe",
        r"what\s+(?:do|does)\s+(.+?)\s+use\s+to\s+breathe",
        r"how\s+(?:do|does)\s+(.+?)\s+(?:get|extract)\s+oxygen",
    ]

    subj = None
    for pattern in patterns:
        match = re.match(pattern, t, re.IGNORECASE)
        if match:
            subj = match.group(1).strip()
            break

    if not subj:
        return None

    # Look for breathing facts (try singular/plural)
    breathes_with = parser._try_get(subj, "breathes_with")
    uses = parser._try_get(subj, "uses")
    uses_to = parser._try_get(subj, "uses_to")

    if breathes_with:
        return f"{subj.title()} breathe using {breathes_with[0].replace('_', ' ')}."

    # Check uses_to for breathing-related
    for u in uses_to:
        if "oxygen" in u or "breathe" in u:
            return f"{subj.title()} {u.replace('_', ' ')}."

    if uses:
        for u in uses:
            if "gill" in u or "lung" in u:
                return f"{subj.title()} use {u.replace('_', ' ')} to breathe."

    return f"I don't know how {subj} breathe."


def _check_backbone_query(parser, t: str) -> str | None:
    """Handle 'do X have backbones?' queries."""
    # Only handle questions
    if not parser._is_question(t):
        return None

    # Special case for vertebrate/invertebrate question
    if "vertebrate" in t.lower() and "invertebrate" in t.lower():
        inv_has_not = parser._try_get("invertebrates", "has_not")
        if inv_has_not:
            return f"Invertebrates do not have {inv_has_not[0].replace('_', ' ')}, while vertebrates do."
        return "Invertebrates do not have backbones, while vertebrates do."

    match = re.match(r"(?:do|does)\s+(.+?)\s+have\s+(.+)", t, re.IGNORECASE)
    if match:
        subj = match.group(1).strip()
        obj = match.group(2).strip().rstrip('?')

        # Check has_not (try singular/plural)
        has_not = parser._try_get(subj, "has_not")
        for item in has_not:
            if obj.lower() in item.lower():
                return f"No, {subj} do not have {obj}."

        # Check has
        has_items = parser._try_get(subj, "has")
        for item in has_items:
            if obj.lower() in item.lower():
                return f"Yes, {subj} have {obj}."

        return f"I don't know if {subj} have {obj}."

    return None


def _check_feeding_query(parser, t: str) -> str | None:
    """Handle 'how do X feed their young?' queries."""
    patterns = [
        r"how\s+(?:do|does)\s+(.+?)\s+feed\s+(?:their|its)\s+young",
        r"what\s+(?:do|does)\s+(.+?)\s+feed\s+(?:their|its)\s+young",
        r"how\s+(?:do|does)\s+(.+?)\s+(?:typically\s+)?feed\s+(?:their|its)\s+young",
    ]

    subj = None
    for pattern in patterns:
        match = re.match(pattern, t, re.IGNORECASE)
        if match:
            subj = match.group(1).strip()
            break

    if not subj:
        return None

    # Look for feeding facts (try singular/plural)
    feeds_with = parser._try_get(subj, "feeds_young_with")
    if feeds_with:
        return f"{subj.title()} feed their young with {feeds_with[0].replace('_', ' ')}."

    return f"I don't know how {subj} feed their young."


def _check_how_query(parser, t: str) -> str | None:
    """Handle 'how do X verb?' queries about methods/processes."""
    if not t.startswith("how"):
        return None

    # Pattern: "how do X reproduce/get/survive/etc"
    match = re.match(r"how\s+(?:do|does|can)\s+(.+?)\s+(reproduce|get|survive|move|eat|breathe|live|grow|find|make|produce|obtain)", t)
    if match:
        subj = match.group(1).strip()
        verb = match.group(2).strip()

        # Look for related facts about the subject
        # Check "can" relations for abilities
        abilities = parser.loom.get(subj, "can") or []
        for ability in abilities:
            if verb in ability or ability.startswith(verb):
                return f"{subj.title()} can {ability.replace('_', ' ')}."

        # Check for method/process facts
        methods = parser.loom.get(subj, "method") or []
        if methods:
            return f"{subj.title()} {verb} by {methods[0].replace('_', ' ')}."

        # Check for needs/uses
        needs = parser.loom.get(subj, "needs") or []
        uses = parser.loom.get(subj, "uses") or []
        if verb in ["get", "obtain"] and (needs or uses):
            items = needs + uses
            return f"{subj.title()} {verb}s {items[0].replace('_', ' ')}."

        return f"I don't know how {subj} {verb}."

    return None


def _check_found_in_query(parser, t: str) -> str | None:
    """Handle location-related questions flexibly."""
    # Multiple patterns for location questions
    patterns = [
        r"what\s+(?:environments?|places?|locations?)\s+can\s+(.+?)\s+be\s+found\s+in",
        r"where\s+(?:can|are|is)\s+(.+?)\s+(?:be\s+)?found",
        r"where\s+(?:do|does)\s+(.+?)\s+live",
        r"in\s+what\s+(?:environments?|places?)\s+(?:can|are|do)\s+(.+?)\s+(?:be\s+)?(?:found|live)",
    ]

    subj = None
    for pattern in patterns:
        match = re.match(pattern, t, re.IGNORECASE)
        if match:
            subj = match.group(1).strip()
            break

    if not subj:
        return None

    # Look for location facts
    locations = parser.loom.get(subj, "found_in") or []
    locations += parser.loom.get(subj, "lives_in") or []
    locations += parser.loom.get(subj, "located_in") or []

    if locations:
        display = [loc.replace("_", " ") for loc in locations]
        return f"{subj.title()} can be found in {format_list(display)}."
    else:
        return f"I don't know where {subj} can be found."


def _check_characteristics_query(parser, t: str) -> str | None:
    """Handle 'what characteristics/traits do X have/share?' questions."""
    patterns = [
        r"what\s+(?:are\s+)?(?:some\s+)?(?:characteristics?|traits?|properties|features?|similarities)\s+(?:that\s+)?(?:all\s+)?(.+?)\s+(?:share|have)",
        r"what\s+do\s+(?:all\s+)?(.+?)\s+(?:share|have\s+in\s+common)",
        r"what\s+(?:characteristics?|traits?)\s+(?:do|does)\s+(.+?)\s+have",
    ]

    subj = None
    for pattern in patterns:
        match = re.match(pattern, t, re.IGNORECASE)
        if match:
            subj = match.group(1).strip()
            break

    if not subj:
        return None

    # Gather all characteristics
    characteristics = []

    # Check has_property
    props = parser.loom.get(subj, "has_property") or []
    for p in props:
        characteristics.append(f"are {p.replace('_', ' ')}")

    # Check has
    has_items = parser.loom.get(subj, "has") or []
    for h in has_items:
        characteristics.append(f"have {h.replace('_', ' ')}")

    # Check can
    abilities = parser.loom.get(subj, "can") or []
    for a in abilities:
        characteristics.append(f"can {a.replace('_', ' ')}")

    # Check needs
    needs = parser.loom.get(subj, "needs") or []
    for n in needs:
        characteristics.append(f"need {n.replace('_', ' ')}")

    if characteristics:
        return f"{subj.title()} {', '.join(characteristics[:5])}."
    else:
        return f"I don't know what characteristics {subj} have."


def _check_differ_query(parser, t: str) -> str | None:
    """Handle 'in what ways do X differ?' questions."""
    patterns = [
        r"in\s+what\s+ways?\s+(?:can|do|does)\s+(.+?)\s+differ",
        r"how\s+(?:can|do|does)\s+(.+?)\s+differ",
        r"what\s+(?:are\s+)?(?:the\s+)?differences?\s+(?:between|among)\s+(.+)",
    ]

    subj = None
    for pattern in patterns:
        match = re.match(pattern, t, re.IGNORECASE)
        if match:
            subj = match.group(1).strip()
            break

    if not subj:
        return None

    # Look for varies_in facts
    variations = parser.loom.get(subj, "varies_in") or []

    if variations:
        display = [v.replace("_", " ") for v in variations]
        return f"{subj.title()} differ in {format_list(display)}."
    else:
        return f"I don't know in what ways {subj} differ."


def _check_what_query(parser, t: str) -> str | None:
    """Handle 'what is X?' or 'what are X?' or 'what X are Y?' queries."""
    if not t.startswith("what "):
        return None

    # Check for "what X is/are Y?" pattern (reverse lookup)
    # e.g., "what animals are predators?" -> find entities that are predators
    # e.g., "what animal is intelligent?" -> find entities that have property intelligent
    match = re.match(r"what\s+(\w+)\s+(?:is|are)\s+(?:a\s+)?(\w+)", t)
    if match:
        context_category, target = match.groups()
        target_norm = normalize(target)
        results = []

        for node, relations in parser.loom.knowledge.items():
            # Check if entity matches the target category
            if "is" in relations:
                for cat in relations["is"]:
                    if target_norm in normalize(cat) or normalize(cat) in target_norm:
                        results.append(prettify(node))
                        break

            # Also check if entity has the target as a property
            if "has_property" in relations and node not in [r.lower() for r in results]:
                for prop in relations["has_property"]:
                    if target_norm in normalize(prop) or normalize(prop) in target_norm:
                        results.append(prettify(node))
                        break

        if results:
            parser.last_subject = results[0] if len(results) == 1 else target
            verb = "is" if len(results) == 1 else "are"
            if len(results) == 1:
                return f"{results[0].title()} {verb} {target}."
            else:
                return f"{format_list([r.title() for r in results])} are {target}."
        else:
            return f"I don't know what {context_category} is {target}."

    subj = None
    if " is " in t:
        subj = t.split(" is ", 1)[-1].strip()
    elif " are " in t:
        subj = t.split(" are ", 1)[-1].strip()

    if not subj:
        return None

    # Track subject for pronoun resolution
    parser.last_subject = subj
    parser.loom.context.update(subject=subj)

    # FIRST: Check for "is" relations (what category is this?)
    # e.g., "what are cats?" -> cats are mammals
    # This takes priority because users usually ask "what are X?" to learn ABOUT X
    facts = parser.loom.get(subj, "is")
    if facts:
        # Build a rich response including all categories
        verb = "are" if is_plural(subj) else "is"
        # Return all facts, not just the first one
        categories = [f.replace("_", " ") for f in facts]

        # Check for cannot abilities to add context
        cannot = parser.loom.get(subj, "cannot") or []
        can = parser.loom.get(subj, "can") or []

        if len(categories) == 1:
            category_str = categories[0]
        else:
            category_str = format_list(categories)

        if cannot:
            inability = cannot[0].replace("_", " ")
            return f"{subj.title()} {verb} {category_str} that cannot {inability}."
        elif can:
            ability = can[0].replace("_", " ")
            return f"{subj.title()} {verb} {category_str} that can {ability}."
        else:
            return f"{subj.title()} {verb} {category_str}."

    # Check for properties as an alternative to "is" relations
    properties = parser.loom.get(subj, "has_property") or []
    if properties:
        verb = "are" if is_plural(subj) else "is"
        prop_display = [p.replace("_", " ") for p in properties]
        return f"{subj.title()} {verb} {format_list(prop_display)}."

    # Check if it differs from something (comparative relation)
    differs = parser.loom.get(subj, "differs_from") or []
    if differs:
        verb = "are" if is_plural(subj) else "is"
        return f"{subj.title()} {verb} different from {format_list(differs)}."

    # FALLBACK: Check if subj is a category with instances (reverse lookup)
    # e.g., "what are mammals?" -> find all X where X is mammals (dogs, cats)
    # Only used when the subject has no direct "is" relation
    instances = _get_category_instances(parser, subj)
    if instances:
        # Found instances - this is a category, return the instances
        instance_names = [prettify(i) for i in instances]
        if len(instance_names) == 1:
            return f"{instance_names[0].title()} is a {subj}."
        else:
            return f"{format_list([n.title() for n in instance_names])} are {subj}."

    parser.loom.add_fact(subj, "has_open_question", "identity")

    # Create curiosity node for unknown concept
    if hasattr(parser.loom, 'curiosity_nodes'):
        parser.loom.curiosity_nodes.create_node(subj, context=f"User asked: what are {subj}?")
        # Try to explore and generate hypotheses
        parser.loom.curiosity_nodes.explore_node(subj)
        hypotheses = parser.loom.curiosity_nodes.generate_hypotheses(subj)

        if hypotheses:
            # Return best guess
            best = hypotheses[0]
            rel_display = best['relation'].replace('_', ' ')
            obj_display = best['object'].replace('_', ' ')
            return (f"I don't know about '{subj}' yet, but based on similar concepts, "
                    f"it might {rel_display} {obj_display}. Can you tell me more?")

    verb = "are" if is_plural(subj) else "is"
    return f"I don't know what {subj} {verb} yet. Can you tell me?"
