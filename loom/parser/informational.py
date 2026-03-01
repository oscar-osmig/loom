"""
Informational pattern methods for the Parser class.
Handles complex encyclopedic sentences and contrast patterns.
"""

import re
from ..grammar import is_adjective


def _check_informational_pattern(parser, t: str) -> str | None:
    """
    Handle complex informational/encyclopedic sentences.
    Examples:
    - "Animals are living organisms found in nearly every environment"
    - "All animals share certain characteristics: they are multicellular, need energy"
    - "Most animals can move at some stage of life and reproduce sexually"
    """
    # Skip questions
    if parser._is_question(t):
        return None

    # Pattern 1: "X are Y found in Z" (or "from A to B")
    # e.g., "Animals are living organisms found in nearly every environment on Earth, from deep oceans to high mountains"
    match = re.match(r"(.+?)\s+(?:is|are)\s+(.+?)\s+found\s+in\s+(.+)", t)
    if match:
        subj = match.group(1).strip()
        category = match.group(2).strip()
        locations_str = match.group(3).strip()

        # Clean subject
        for prefix in ["the ", "a ", "an ", "all "]:
            if subj.lower().startswith(prefix):
                subj = subj[len(prefix):]

        # Add category fact
        parser.loom.add_fact(subj, "is", category)

        # Extract locations from "X, from A to B" or just "X"
        from_to_match = re.search(r",?\s*from\s+(.+?)\s+to\s+(.+?)(?:\.|$)", locations_str)
        if from_to_match:
            loc1 = from_to_match.group(1).strip()
            loc2 = from_to_match.group(2).strip()
            parser.loom.add_fact(subj, "found_in", loc1)
            parser.loom.add_fact(subj, "found_in", loc2)
        else:
            # Just add the whole location string
            parser.loom.add_fact(subj, "found_in", locations_str)

        parser.last_subject = subj
        return "Got it."

    # Pattern 2: "All X share Y: A, B, C" or "X share: A, B, C"
    # e.g., "All animals share certain similarities: they are multicellular, need energy..."
    match = re.match(r"(?:all\s+)?(.+?)\s+share\s+(?:.+?):\s*(.+)", t, re.IGNORECASE)
    if match:
        subj = match.group(1).strip()
        properties_str = match.group(2).strip()

        # Resolve "they" to subject
        properties_str = re.sub(r'\bthey\b', subj, properties_str, flags=re.IGNORECASE)

        # Split on commas and "and"
        parts = re.split(r',\s*(?:and\s+)?|\s+and\s+', properties_str)
        facts_added = 0

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # "are multicellular" -> has_property: multicellular
            are_match = re.match(r"(?:are|is)\s+(.+)", part)
            if are_match:
                prop = are_match.group(1).strip()
                parser.loom.add_fact(subj, "has_property", prop)
                facts_added += 1
                continue

            # "need energy" -> needs: energy
            need_match = re.match(r"need(?:s)?\s+(.+)", part)
            if need_match:
                obj = need_match.group(1).strip()
                # Clean parentheticals
                obj = re.sub(r'\s*\([^)]*\)', '', obj).strip()
                parser.loom.add_fact(subj, "needs", obj)
                facts_added += 1
                continue

            # "can respond to stimuli" -> can: respond to stimuli
            can_match = re.match(r"can\s+(.+)", part)
            if can_match:
                ability = can_match.group(1).strip()
                parser.loom.add_fact(subj, "can", ability)
                facts_added += 1
                continue

            # "have specialized cells" -> has: specialized cells
            have_match = re.match(r"have\s+(.+)", part)
            if have_match:
                obj = have_match.group(1).strip()
                parser.loom.add_fact(subj, "has", obj)
                facts_added += 1
                continue

        if facts_added > 0:
            parser.last_subject = subj
            return "Got it."

    # Pattern 3: "Most X can Y and Z" (quantified abilities)
    # e.g., "Most animals can move at some stage of life and reproduce sexually"
    match = re.match(r"(?:most|many|some|all)\s+(.+?)\s+can\s+(.+)", t, re.IGNORECASE)
    if match:
        subj = match.group(1).strip()
        abilities_str = match.group(2).strip()

        # Split on "and"
        abilities = re.split(r'\s+and\s+', abilities_str)
        for ability in abilities:
            ability = ability.strip()
            # Clean trailing clauses
            ability = re.sub(r',.*$', '', ability).strip()
            if ability:
                parser.loom.add_fact(subj, "can", ability)

        parser.last_subject = subj
        return "Got it."

    # Pattern 4: "For example, X are Y and have Z"
    # e.g., "For example, mammals are warm-blooded and have hair or fur"
    match = re.match(r"for\s+example,?\s+(.+?)\s+(?:is|are)\s+(.+)", t, re.IGNORECASE)
    if match:
        subj = match.group(1).strip()
        rest = match.group(2).strip()

        # Split on "and have" or "and"
        and_have_match = re.search(r"\s+and\s+have\s+(.+)$", rest)
        if and_have_match:
            possession = and_have_match.group(1).strip()
            category = rest[:and_have_match.start()].strip()
            parser.loom.add_fact(subj, "is", category)
            parser.loom.add_fact(subj, "has", possession)
        else:
            parser.loom.add_fact(subj, "is", rest)

        parser.last_subject = subj
        return "Got it."

    # Pattern 5: "X differ in A, B, and C" or "X differ greatly in A"
    match = re.match(r"(.+?)\s+differ(?:s)?\s+(?:greatly\s+)?in\s+(.+)", t, re.IGNORECASE)
    if match:
        subj = match.group(1).strip()
        differences_str = match.group(2).strip()

        # Clean prefix
        for prefix in ["the ", "a ", "an ", "however, "]:
            if subj.lower().startswith(prefix):
                subj = subj[len(prefix):]

        # Split on commas and "and"
        diffs = re.split(r',\s*(?:and\s+)?|\s+and\s+', differences_str)
        for diff in diffs:
            diff = diff.strip().rstrip('.')
            if diff:
                parser.loom.add_fact(subj, "varies_in", diff)

        parser.last_subject = subj
        return "Got it."

    # Pattern 6: "X are classified into Y such as A, B, C"
    # e.g., "Animals are classified into major groups such as mammals, birds, reptiles"
    match = re.match(r"(.+?)\s+(?:is|are)\s+classified\s+into\s+(.+?)\s+such\s+as\s+(.+)", t, re.IGNORECASE)
    if match:
        subj = match.group(1).strip()
        group_type = match.group(2).strip()
        items_str = match.group(3).strip()

        # Store the classification
        parser.loom.add_fact(subj, "classified_into", group_type)

        # Extract the list items
        items = re.split(r',\s*(?:and\s+)?|\s+and\s+', items_str)
        for item in items:
            item = item.strip().rstrip('.')
            if item:
                parser.loom.add_fact(subj, "includes_group", item)
                parser.loom.add_fact(item, "is_type_of", subj)

        parser.last_subject = subj
        return "Got it."

    # Pattern 7: "X, like A and B, do/do not have Y" or "X, such as A, ..."
    # e.g., "Invertebrates, like insects and spiders, do not have backbones"
    match = re.match(r"(.+?),\s*(?:like|such\s+as)\s+(.+?),\s*(.+)", t, re.IGNORECASE)
    if match:
        subj = match.group(1).strip()
        examples_str = match.group(2).strip()
        predicate = match.group(3).strip()

        # Extract examples
        examples = re.split(r'\s+and\s+', examples_str)
        for ex in examples:
            ex = ex.strip()
            if ex:
                parser.loom.add_fact(subj, "example", ex)
                parser.loom.add_fact(ex, "is", subj)

        # Parse the predicate
        # "do not have Y" -> has_not: Y
        not_have_match = re.match(r"do\s+not\s+have\s+(.+)", predicate, re.IGNORECASE)
        if not_have_match:
            obj = not_have_match.group(1).strip()
            # Clean "while X do" suffix
            obj = re.sub(r',?\s*while\s+.+$', '', obj).strip()
            parser.loom.add_fact(subj, "has_not", obj)
            parser.last_subject = subj
            return "Got it."

        # "have Y, while Z do not" -> contrast between has and has_not
        have_while_match = re.match(r"have\s+(.+?),\s*while\s+(.+?),\s*(?:like|such\s+as)\s+(.+?),\s*do\s+not", predicate, re.IGNORECASE)
        if have_while_match:
            obj = have_while_match.group(1).strip()
            contrast_subj = have_while_match.group(2).strip()
            contrast_examples = have_while_match.group(3).strip()

            # Positive: subject has obj
            parser.loom.add_fact(subj, "has", obj)

            # Negative: contrast subject does not have obj
            parser.loom.add_fact(contrast_subj, "has_not", obj)

            # Extract examples for contrast subject
            c_examples = re.split(r'\s+and\s+', contrast_examples)
            for ex in c_examples:
                ex = ex.strip()
                if ex:
                    parser.loom.add_fact(contrast_subj, "example", ex)
                    parser.loom.add_fact(ex, "is", contrast_subj)

            parser.last_subject = contrast_subj
            return "Got it."

        # "have Y" -> has: Y (simple case)
        have_match = re.match(r"have\s+(.+)", predicate, re.IGNORECASE)
        if have_match:
            obj = have_match.group(1).strip()
            # Clean "while X" suffix if present
            obj = re.sub(r',?\s*while\s+.+$', '', obj).strip()
            parser.loom.add_fact(subj, "has", obj)
            parser.last_subject = subj
            return "Got it."

    # Pattern 8a: "X give birth to Y and feed them Z" (reproduction with feeding - no adverb)
    # e.g., "Mammals give birth to live young and feed them milk"
    match = re.match(r"(.+?)\s+give\s+birth\s+to\s+(.+?)\s+and\s+feed\s+(?:them|their\s+young)\s+(.+)", t, re.IGNORECASE)
    if match:
        subj = match.group(1).strip()
        offspring = match.group(2).strip()
        food = match.group(3).strip()
        food = re.sub(r',.*$', '', food).strip()
        parser.loom.add_fact(subj, "gives_birth_to", offspring)
        parser.loom.add_fact(subj, "reproduction", "live birth")
        parser.loom.add_fact(subj, "feeds_young_with", food)
        parser.last_subject = subj
        return "Got it."

    # Pattern 8b: "X and Y lay eggs" (compound subject with lay eggs)
    # e.g., "Birds and most reptiles lay eggs"
    match = re.match(r"(.+?)\s+and\s+(?:most\s+)?(.+?)\s+lay\s+eggs?", t, re.IGNORECASE)
    if match:
        subj1 = match.group(1).strip()
        subj2 = match.group(2).strip()
        for subj in [subj1, subj2]:
            parser.loom.add_fact(subj, "reproduction", "eggs")
            parser.loom.add_fact(subj, "lays", "eggs")
            parser.loom.add_fact(subj, "produces", "eggs")
        parser.last_subject = subj2
        return "Got it."

    # Pattern 8: "X usually/typically verb Y" (reproduction, feeding, etc.)
    # e.g., "Mammals usually give birth to live young and feed them milk"
    match = re.match(r"(.+?)\s+(?:usually|typically|often|generally)\s+(.+)", t, re.IGNORECASE)
    if match:
        subj = match.group(1).strip()
        action_str = match.group(2).strip()

        # "give birth to X and feed them Y" - try with feeding first
        birth_feed_match = re.match(r"give\s+birth\s+to\s+(.+?)\s+and\s+feed\s+(?:them|their\s+young)\s+(.+)", action_str, re.IGNORECASE)
        if birth_feed_match:
            offspring = birth_feed_match.group(1).strip()
            food = birth_feed_match.group(2).strip()
            food = re.sub(r',.*$', '', food).strip()
            parser.loom.add_fact(subj, "gives_birth_to", offspring)
            parser.loom.add_fact(subj, "reproduction", "live birth")
            parser.loom.add_fact(subj, "feeds_young_with", food)
            parser.last_subject = subj
            return "Got it."

        # "give birth to X" without feeding
        birth_match = re.match(r"give\s+birth\s+to\s+(.+?)(?:,|\s*$)", action_str, re.IGNORECASE)
        if birth_match:
            offspring = birth_match.group(1).strip()
            parser.loom.add_fact(subj, "gives_birth_to", offspring)
            parser.loom.add_fact(subj, "reproduction", "live birth")
            parser.last_subject = subj
            return "Got it."

        # "lay eggs"
        lay_match = re.match(r"lay\s+eggs?", action_str, re.IGNORECASE)
        if lay_match:
            parser.loom.add_fact(subj, "reproduction", "eggs")
            parser.loom.add_fact(subj, "lays", "eggs")
            parser.last_subject = subj
            return "Got it."

    # Pattern 9: "X, such as Y, can/do Z" (ability with example)
    # e.g., "Amphibians, such as frogs, can live both in water and on land"
    match = re.match(r"(.+?),\s*such\s+as\s+(.+?),\s*(?:can|do|does)\s+(.+)", t, re.IGNORECASE)
    if match:
        subj = match.group(1).strip()
        example = match.group(2).strip()
        ability = match.group(3).strip()

        parser.loom.add_fact(subj, "example", example)
        parser.loom.add_fact(example, "is", subj)

        # "live both in water and on land"
        live_match = re.match(r"live\s+(?:both\s+)?in\s+(.+)", ability, re.IGNORECASE)
        if live_match:
            locations = live_match.group(1).strip()
            # Split on "and"
            locs = re.split(r'\s+and\s+(?:on\s+|in\s+)?', locations)
            for loc in locs:
                loc = loc.strip()
                loc = re.sub(r'\s+and\s+often.*$', '', loc).strip()
                if loc:
                    parser.loom.add_fact(subj, "can_live_in", loc)
            parser.last_subject = subj
            return "Got it."

        # Generic ability
        ability = re.sub(r'\s+and\s+often.*$', '', ability).strip()
        parser.loom.add_fact(subj, "can", ability)
        parser.last_subject = subj
        return "Got it."

    # Pattern 10: "X use Y to Z" (mechanism/tool)
    # e.g., "Fish use gills to extract oxygen from water"
    match = re.match(r"(.+?)\s+use(?:s)?\s+(.+?)\s+to\s+(.+)", t, re.IGNORECASE)
    if match:
        subj = match.group(1).strip()
        tool = match.group(2).strip()
        purpose = match.group(3).strip()

        # Clean "while X" suffix
        purpose = re.sub(r',?\s*while\s+.+$', '', purpose).strip()

        parser.loom.add_fact(subj, "uses", tool)
        parser.loom.add_fact(subj, "uses_to", f"{tool} to {purpose}")

        # Special handling for breathing
        if "oxygen" in purpose or "breathe" in purpose or "gills" in tool:
            parser.loom.add_fact(subj, "breathes_with", tool)

        parser.last_subject = subj
        return "Got it."

    # Pattern 11: Definition patterns with em-dash "X—Y eat/do Z"
    # e.g., "herbivores eat plants, carnivores eat other animals"
    # Split on em-dash first
    if "—" in t or "–" in t or " - " in t:
        # Split on dashes
        parts = re.split(r'[—–]|\s+-\s+', t)
        if len(parts) >= 2:
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                # Try to parse each part as "X eat Y" or "X do Y"
                _parse_definition_clause(parser, part)
            return "Got it."

    # Pattern 12: "X also vary in Y"
    match = re.match(r"(.+?)\s+also\s+vary\s+in\s+(.+)", t, re.IGNORECASE)
    if match:
        subj = match.group(1).strip()
        aspect = match.group(2).strip()
        aspect = re.sub(r'[—–].*$', '', aspect).strip()
        parser.loom.add_fact(subj, "varies_in", aspect)
        parser.last_subject = subj
        return "Got it."

    # Pattern 13: "all X depend on Y"
    match = re.match(r"(?:all\s+)?(.+?)\s+depend(?:s)?\s+on\s+(.+)", t, re.IGNORECASE)
    if match:
        subj = match.group(1).strip()
        dependency = match.group(2).strip()
        dependency = re.sub(r'\s+to\s+.+$', '', dependency).strip()
        parser.loom.add_fact(subj, "depends_on", dependency)
        parser.last_subject = subj
        return "Got it."

    return None


def _parse_definition_clause(parser, clause: str):
    """Parse definition clauses like 'herbivores eat plants'."""
    clause = clause.strip().rstrip('.')

    # "X eat Y"
    match = re.match(r"(\w+)\s+eat(?:s)?\s+(.+)", clause, re.IGNORECASE)
    if match:
        subj = match.group(1).strip()
        obj = match.group(2).strip()
        # Clean trailing clauses
        obj = re.split(r',\s*', obj)[0].strip()
        parser.loom.add_fact(subj, "eats", obj)
        parser.loom.add_fact(subj, "diet_type", subj)
        return

    # "X do Y" or "X are Y"
    match = re.match(r"(\w+)\s+(?:do|are|is)\s+(.+)", clause, re.IGNORECASE)
    if match:
        subj = match.group(1).strip()
        obj = match.group(2).strip()
        parser.loom.add_fact(subj, "does", obj)


def _check_contrast_pattern(parser, t: str) -> str | None:
    """
    Handle contrast patterns: "X are A, while/whereas Y are B"
    Examples:
    - "Mammals are warm-blooded and have hair, while reptiles are cold-blooded and have scales"
    - "Birds lay eggs and have feathers, whereas fish live in water and breathe through gills"
    """
    # Skip questions
    if parser._is_question(t):
        return None

    # Pattern: "X are/have A, while/whereas Y are/have B, and Z are/have C"
    contrast_match = re.search(r"(.+?),?\s+(?:while|whereas)\s+(.+)", t, re.IGNORECASE)
    if not contrast_match:
        return None

    first_part = contrast_match.group(1).strip()
    rest = contrast_match.group(2).strip()

    # Split rest on ", and" to handle three-way contrasts
    # "carnivores eat meat, and omnivores eat both" -> ["carnivores eat meat", "omnivores eat both"]
    parts = re.split(r',\s+and\s+', rest, flags=re.IGNORECASE)

    facts_added = 0

    # Parse first part: "X are A and have B" or "X lay eggs and have feathers"
    first_parsed = _parse_subject_predicates(parser, first_part)
    if first_parsed:
        subj, predicates = first_parsed
        for rel, obj in predicates:
            parser.loom.add_fact(subj, rel, obj)
            facts_added += 1

    # Parse remaining parts
    for part in parts:
        part = part.strip()
        if part:
            parsed = _parse_subject_predicates(parser, part)
            if parsed:
                subj, predicates = parsed
                for rel, obj in predicates:
                    parser.loom.add_fact(subj, rel, obj)
                    facts_added += 1

    if facts_added > 0:
        return f"Got it, {first_part}, while {rest.split(',')[0]}."

    return None


def _parse_subject_predicates(parser, text: str) -> tuple | None:
    """
    Parse "X are A and have B" style phrases.
    Returns (subject, [(relation, object), ...]) or None.
    """
    # Try to find subject and predicates
    # Pattern: "X are/is A" or "X have/has B" or "X verb B"

    # Match "X are/is Y" - including eat/eats
    match = re.match(r"(.+?)\s+(are|is|have|has|can|lay|live|breathe|eat|eats)\s+(.+)", text, re.IGNORECASE)
    if not match:
        return None

    subj = match.group(1).strip()
    first_verb = match.group(2).lower()
    rest = match.group(3).strip()

    # Clean subject
    for prefix in ["the ", "a ", "an ", "for example, "]:
        if subj.lower().startswith(prefix):
            subj = subj[len(prefix):]

    predicates = []

    # Map verbs to relations
    verb_to_relation = {
        "are": "has_property", "is": "has_property",
        "have": "has", "has": "has",
        "can": "can",
        "lay": "produces", "lays": "produces",
        "live": "lives_in", "lives": "lives_in",
        "breathe": "breathes_through", "breathes": "breathes_through",
        "eat": "eats", "eats": "eats",
    }

    # Split on "and verb" patterns
    parts = re.split(r"\s+and\s+(?=(?:are|is|have|has|can|lay|live|breathe|eat|eats)\s)", rest, flags=re.IGNORECASE)

    # First part uses the first verb
    first_obj = parts[0].strip()
    rel = verb_to_relation.get(first_verb, "is")
    # For "are warm-blooded", use has_property
    if first_verb in ["are", "is"] and is_adjective(first_obj.split()[0] if first_obj.split() else ""):
        rel = "has_property"
    predicates.append((rel, first_obj))

    # Handle additional "and verb X" parts
    for part in parts[1:]:
        part = part.strip()
        # Match "verb X"
        verb_match = re.match(r"(are|is|have|has|can|lay|live|breathe|eat|eats)\s+(.+)", part, re.IGNORECASE)
        if verb_match:
            verb = verb_match.group(1).lower()
            obj = verb_match.group(2).strip()
            rel = verb_to_relation.get(verb, "is")
            if verb in ["are", "is"] and is_adjective(obj.split()[0] if obj.split() else ""):
                rel = "has_property"
            predicates.append((rel, obj))

    return (subj, predicates) if predicates else None
