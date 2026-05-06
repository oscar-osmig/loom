"""
Relation pattern methods for the Parser class.
Handles relation patterns, conditional, becomes, and is_statement.

Uses generic SVO (Subject-Verb-Object) extraction instead of hardcoded
verb lists. Any verb becomes a valid relation — no predefined mapping needed.
"""

import re
from ..grammar import is_plural, is_adjective
from ..svo import extract_svo, extract_multiple_svo
from .constants import COLORS
from .relations import get_relation_for_verb


def _clean_subject(subj: str) -> str:
    """Clean up a subject string."""
    for prefix in ["the ", "a ", "an "]:
        if subj.lower().startswith(prefix):
            subj = subj[len(prefix):]
    for suffix in [" also", " too", " as well"]:
        if subj.lower().endswith(suffix):
            subj = subj[:-len(suffix)].strip()
    return subj.strip()


def _clean_object(obj: str) -> str:
    """Clean up an object string."""
    # Strip discourse markers from start
    for prefix in ["also ", "too ", "as well ", "even "]:
        if obj.lower().startswith(prefix):
            obj = obj[len(prefix):].strip()

    # Truncate at sentence boundaries
    if ". " in obj:
        obj = obj.split(". ")[0].strip()
    if obj.endswith("."):
        obj = obj[:-1].strip()

    # Truncate at discourse markers
    for marker in [", and ", ", but ", ", so ", ", because ", ", which ", ", that ", ", when "]:
        if marker in obj:
            obj = obj.split(marker)[0].strip()

    # Truncate at prepositional phrases that add context but aren't core
    for prep in [" for ", " with ", " about ", " during ", " since ",
                 " after ", " before ", " until ", " near ", " between "]:
        if prep in obj:
            obj = obj.split(prep)[0].strip()

    # Clean trailing filler
    for suffix in [" too", " as well", " also", " very"]:
        if obj.endswith(suffix):
            obj = obj[:-len(suffix)].strip()

    return obj.strip()


def _check_relation_patterns(parser, t: str) -> str | None:
    """
    Handle relation patterns using generic SVO extraction.

    Instead of matching against a hardcoded list of verbs, we detect
    the verb structurally and use it directly as the relation.
    """
    # Skip questions
    if parser._is_question(t):
        return None

    # Skip if contains copula — those are handled by _check_is_statement
    # But NOT "was/were + past participle" which is passive voice (SVO handles that)
    from ..svo import IRREGULAR_PAST
    if " is " in t or " are " in t:
        return None
    # For was/were, only skip if it's NOT followed by a past participle (i.e., it's copula)
    for copula in [" was ", " were "]:
        if copula in t:
            pos = t.find(copula)
            after = t[pos + len(copula):].split()[0] if t[pos + len(copula):].split() else ""
            # If followed by past participle (-ed or irregular), let SVO handle it
            is_participle = (after.endswith("ed") and len(after) > 3) or after in IRREGULAR_PAST
            if is_participle:
                break  # Don't skip — SVO will extract the passive
            else:
                return None  # Copula — let _check_is_statement handle it

    # Handle compound verb phrases that map to specific relations BEFORE generic modals
    import re as _re

    # "X can be found in Y" / "X is found in Y" / "X are found in Y" → found_in
    found_in_match = _re.match(
        r"^(.+?)\s+(?:can\s+be|is|are)\s+found\s+in\s+(.+)$", t
    )
    if found_in_match:
        subj = _clean_subject(found_in_match.group(1))
        locations = found_in_match.group(2)
        if subj and locations:
            # Split "lakes and rivers" into individual locations
            for loc in _re.split(r",\s*(?:and\s+)?|\s+and\s+", locations):
                loc = _clean_object(loc.strip())
                if loc:
                    parser.loom.add_fact(subj, "found_in", loc)
            parser.last_subject = subj
            parser.loom.context.update(subject=subj, relation="found_in", obj=locations)
            return f"Got it, {subj} can be found in {locations}."

    # "X lives in/on Y" / "X live in/on Y" → lives_in
    lives_in_match = _re.match(
        r"^(.+?)\s+lives?\s+(?:in|on)\s+(.+)$", t
    )
    if lives_in_match:
        subj = _clean_subject(lives_in_match.group(1))
        locations = lives_in_match.group(2)
        if subj and locations:
            for loc in _re.split(r",\s*(?:and\s+)?|\s+and\s+", locations):
                loc = _clean_object(loc.strip())
                if loc:
                    parser.loom.add_fact(subj, "lives_in", loc)
            parser.last_subject = subj
            parser.loom.context.update(subject=subj, relation="lives_in", obj=locations)
            return f"Got it, {subj} lives in {locations}."

    # Handle modal verbs: "X can/could/will Y" → store as (X, can, Y)
    modal_match = _re.match(r"^(.+?)\s+(can|could|cannot|can't|will|would|should|must)\s+(.+)$", t)
    if modal_match:
        subj = _clean_subject(modal_match.group(1))
        modal = modal_match.group(2)
        obj = _clean_object(modal_match.group(3))
        if subj and obj:
            relation = "cannot" if modal in ("cannot", "can't") else "can"
            parser.loom.add_fact(subj, relation, obj)
            parser.last_subject = subj
            parser.loom.context.update(subject=subj, relation=relation, obj=obj)
            return f"Got it, {subj} {modal} {obj}."

    # Explicit has/have pattern — catches cases where SVO mis-parses compound subjects
    # e.g., "Sea turtles has shells" (spaCy treats "turtles" as verb)
    has_match = _re.match(
        r"^(.+?)\s+(?:has|have)\s+(.+)$", t, _re.IGNORECASE
    )
    if has_match:
        subj = _clean_subject(has_match.group(1))
        obj = _clean_object(has_match.group(2))
        if subj and obj:
            # Split "X and Y" objects
            for item in _re.split(r",\s*(?:and\s+)?|\s+and\s+", obj):
                item = _clean_object(item.strip())
                if item:
                    parser.loom.add_fact(subj, "has", item)
            parser.last_subject = subj
            parser.loom.context.update(subject=subj, relation="has", obj=obj)
            return f"Got it, {subj} has {obj}."

    # Explicit causation pattern — catches cases where SVO mis-parses ambiguous verbs
    # e.g., "Sharp claws cause better grip" (spaCy treats "claws" as verb)
    cause_match = _re.match(
        r"^(.+?)\s+causes?\s+(.+)$", t, _re.IGNORECASE
    )
    if cause_match:
        subj = _clean_subject(cause_match.group(1))
        obj = _clean_object(cause_match.group(2))
        if subj and obj:
            parser.loom.add_fact(subj, "causes", obj)
            parser.last_subject = subj
            parser.loom.context.update(subject=subj, relation="causes", obj=obj)
            return f"Noted — {subj} causes {obj}."

    # Try SVO extraction (handles both active and passive voice)
    svos = extract_multiple_svo(t)
    if not svos:
        return None

    stored_any = False
    first_subj = None

    for svo in svos:
        subj = _clean_subject(svo["subject"])
        obj = _clean_object(svo["object"])
        relation = svo["relation"]

        if not subj or not obj:
            continue

        # Check if we have a known relation with a reverse mapping
        rel_def = get_relation_for_verb(svo["verb"])
        if rel_def:
            relation = rel_def.relation
            reverse = rel_def.reverse
        else:
            # Use the verb directly as the relation — this is the key change
            reverse = None

        parser.loom.add_fact(subj, relation, obj)

        # Add reverse relation if defined
        if reverse:
            parser.loom.add_fact(obj, reverse, subj)

        # For passive voice with context (e.g., "founded in 1432 by X")
        # store the temporal/location context as additional fact
        if svo.get("context"):
            context = _clean_object(svo["context"])
            if context:
                parser.loom.add_fact(obj, relation + "_context", context)

        if not first_subj:
            first_subj = subj
        stored_any = True

    if stored_any:
        # Track subject for pronoun resolution
        parser.last_subject = first_subj
        parser.loom.context.update(subject=first_subj, relation=svos[0]["relation"], obj=svos[0]["object"])

        verb_display = svos[0]["verb"]
        obj_display = _clean_object(svos[0]["object"])
        return f"Got it, {first_subj} {verb_display} {obj_display}."

    return None


def _check_conditional_pattern(parser, t: str) -> str | None:
    """Handle 'when X, Y' or 'if X then Y' patterns."""
    if not (t.startswith("when ") or t.startswith("if ")):
        return None

    rest = t[3:] if t.startswith("if ") else t[5:]

    for sep in [" then ", ", ", " it "]:
        if sep in rest:
            parts = rest.split(sep, 1)
            if len(parts) == 2:
                x, y = parts[0].strip(), parts[1].strip()
                for word in ["becomes ", "gets ", "is ", "will be ", "it "]:
                    y = y.replace(word, "")
                parser.loom.add_fact(x, "causes", y.strip())
                return f"I understand, {x} leads to {y.strip()}."
    return None


def _check_becomes_pattern(parser, t: str) -> str | None:
    """Handle 'X becomes Y' patterns."""
    if " becomes " not in t:
        return None

    parts = t.split(" becomes ", 1)
    if len(parts) == 2:
        parser.loom.add_fact(parts[0].strip(), "leads_to", parts[1].strip())
        return f"Got it, {parts[0].strip()} transforms into {parts[1].strip()}."
    return None


def _check_is_statement(parser, t: str) -> str | None:
    """Handle 'X is/are/was/were Y' statements, including 'X and Y are Z'."""
    from ..svo import IRREGULAR_PAST

    # Skip questions - they should be handled by query handlers
    if parser._is_question(t):
        return None

    # Find the FIRST occurrence of any copula to split on
    copulas = [" is ", " are ", " was ", " were "]
    best_pos = -1
    verb = None

    for cop in copulas:
        pos = t.find(cop)
        if pos != -1 and (best_pos == -1 or pos < best_pos):
            best_pos = pos
            verb = cop

    if best_pos == -1:
        return None

    split_pos = best_pos

    subj = t[:split_pos].strip()
    obj = t[split_pos + len(verb):].strip()

    if not subj or not obj:
        return None

    # Skip passive voice: "X was/were [past_participle] [by Y]"
    # These should be handled by SVO extraction in _check_relation_patterns
    if verb in (" was ", " were "):
        first_word = obj.split()[0] if obj.split() else ""
        is_passive = (
            (first_word.endswith("ed") and len(first_word) > 3)
            or first_word in IRREGULAR_PAST
        )
        if is_passive:
            return None  # Let _check_relation_patterns handle passive voice

    # Handle "X is made from/of Y" → store as made_of relation
    if verb == " is " and obj.startswith(("made from ", "made of ", "made out of ")):
        for prefix in ["made out of ", "made from ", "made of "]:
            if obj.startswith(prefix):
                material = obj[len(prefix):].strip().rstrip(".")
                if material:
                    parser.loom.add_fact(subj, "made_of", material)
                    parser.last_subject = subj
                    parser.loom.context.update(subject=subj, relation="made_of", obj=material)
                    return f"Got it, {subj} is {prefix}{material}."
                break

    # Handle quantifiers: "some X are Y" -> X can_be Y
    quantifier = None
    for q in ["some ", "many ", "most ", "few ", "several "]:
        if subj.startswith(q):
            quantifier = q.strip()
            subj = subj[len(q):]
            break

    # Clean prefixes from subject
    for prefix in ["the ", "a ", "an ", "so ", "well ", "however, ", "but ", "because "]:
        if subj.startswith(prefix):
            subj = subj[len(prefix):]

    # Clean prefixes from object (both, also, etc.)
    for prefix in ["both ", "also ", "all "]:
        if obj.startswith(prefix):
            obj = obj[len(prefix):]

    # Handle relative clauses: "X are Y that [verb] Z"
    relative_clause_facts = []  # List of (relation, value, negated) tuples

    # Check for "that cannot/can Z" pattern (ability)
    rel_match = re.search(r"\s+that\s+(cannot|can't|can)\s+(.+)$", obj)
    if rel_match:
        can_word = rel_match.group(1)
        ability = rel_match.group(2).strip()
        negated = can_word in ["cannot", "can't"]
        if negated:
            relative_clause_facts.append(("cannot", ability, False))
        else:
            relative_clause_facts.append(("can", ability, False))
        # Remove the relative clause from obj
        obj = obj[:rel_match.start()].strip()

    # Check for "that are food for X" pattern (special case)
    if not relative_clause_facts:
        food_for_rel_match = re.search(r"\s+that\s+(?:is|are)\s+food\s+for\s+(.+)$", obj, re.IGNORECASE)
        if food_for_rel_match:
            food_target = food_for_rel_match.group(1).strip()
            relative_clause_facts.append(("food_for", food_target, False))
            # Remove the relative clause from obj
            obj = obj[:food_for_rel_match.start()].strip()

    # Check for "that [verb] [in/on/...] X" patterns (location, possession, etc.)
    if not relative_clause_facts:
        # Match: "that live in X", "that eat X", "that have X", "that make X", etc.
        rel_verb_match = re.search(r"\s+that\s+(live|lives|eat|eats|have|has|use|uses|need|needs|like|likes|want|wants|make|makes)\s+(?:in\s+)?(.+)$", obj, re.IGNORECASE)
        if rel_verb_match:
            verb_rel = rel_verb_match.group(1).lower()
            rel_obj = rel_verb_match.group(2).strip()
            # Map verb to relation
            verb_map = {
                "live": "lives_in", "lives": "lives_in",
                "eat": "eats", "eats": "eats",
                "have": "has", "has": "has",
                "use": "uses", "uses": "uses",
                "need": "needs", "needs": "needs",
                "like": "likes", "likes": "likes",
                "want": "wants", "wants": "wants",
                "make": "makes", "makes": "makes",
            }
            if verb_rel in verb_map:
                relative_clause_facts.append((verb_map[verb_rel], rel_obj, False))
            # Remove the relative clause from obj
            obj = obj[:rel_verb_match.start()].strip()

    # Handle compound predicates: "X are large and need Y" -> two facts
    # Check if " and " is followed by a verb (compound predicate)
    compound_predicate_match = re.search(r"\s+and\s+(need|have|can|eat|use|live|like|want|require|are|is|do|make|get|become)s?\s+(.+)$", obj, re.IGNORECASE)
    compound_second_fact = None
    if compound_predicate_match:
        verb_cp = compound_predicate_match.group(1).lower()
        second_obj = compound_predicate_match.group(2).strip()
        # Map verb to relation
        verb_to_relation = {
            "need": "needs", "needs": "needs",
            "have": "has", "has": "has",
            "can": "can",
            "eat": "eats", "eats": "eats",
            "use": "uses", "uses": "uses",
            "live": "lives_in", "lives": "lives_in",
            "like": "likes", "likes": "likes",
            "want": "wants", "wants": "wants",
            "require": "requires", "requires": "requires",
            "are": "is", "is": "is",
            "do": "can", "does": "can",
            "make": "makes", "makes": "makes",
            "get": "has", "gets": "has",
            "become": "becomes", "becomes": "becomes",
        }
        if verb_cp in verb_to_relation:
            compound_second_fact = (verb_to_relation[verb_cp], second_obj)
        # Truncate obj to the part before " and verb"
        obj = obj[:compound_predicate_match.start()].strip()

    # Extract causal consequences before truncation: ", so they/X have Y" -> has = Y
    # Use \w+ to match any subject (in case pronoun was resolved to a name)
    causal_consequence = None
    so_match = re.search(r",?\s+so\s+\w+\s+(have|has|can|need|needs|are|is|eat|eats|use|uses)\s+(.+)$", obj, re.IGNORECASE)
    if so_match:
        verb_so = so_match.group(1).lower()
        consequence_obj = so_match.group(2).strip()
        verb_map = {
            "have": "has", "has": "has",
            "can": "can",
            "need": "needs", "needs": "needs",
            "are": "is", "is": "is",
            "eat": "eats", "eats": "eats",
            "use": "uses", "uses": "uses",
        }
        if verb_so in verb_map:
            causal_consequence = (verb_map[verb_so], consequence_obj)
        obj = obj[:so_match.start()].strip()

    # Handle "X with Y" patterns: "mammals with long trunks" -> is: mammals, has: long_trunks
    with_possession = None
    with_match = re.search(r"\s+with\s+(.+)$", obj, re.IGNORECASE)
    if with_match:
        with_obj = with_match.group(1).strip()
        with_possession = with_obj
        obj = obj[:with_match.start()].strip()

    # Truncate object at sentence boundaries (periods)
    if ". " in obj:
        obj = obj.split(". ")[0].strip()
    if obj.endswith("."):
        obj = obj[:-1].strip()

    # Truncate object at discourse markers (but, because, so, etc.)
    for marker in [", but ", " but ", ", because ", " because ", ", so ", " so ",
                   ", and ", ", while ", " while ", ", when ", " when ",
                   ", which ", " which "]:
        if marker in obj:
            obj = obj.split(marker)[0].strip()

    # Handle special "food for X" pattern BEFORE truncation
    food_for_target = None
    food_for_match = re.search(r"^food\s+for\s+(.+)$", obj, re.IGNORECASE)
    if food_for_match:
        food_for_target = food_for_match.group(1).strip()
        obj = "food"  # Keep just "food" as the category

    # Handle "threatened by X" pattern BEFORE truncation
    threatened_by = None
    threatened_match = re.search(r"^threatened\s+by\s+(.+)$", obj, re.IGNORECASE)
    if threatened_match:
        threatened_by = threatened_match.group(1).strip()
        obj = ""  # No category, just the property

    # Handle "home to X" pattern - extract as property, not category
    home_to = None
    home_match = re.search(r"^home\s+to\s+(.+)$", obj, re.IGNORECASE)
    if home_match:
        home_to = home_match.group(1).strip()
        obj = ""  # No category

    # Also truncate at certain words that indicate extra info
    # But NOT for special patterns handled above
    if not food_for_target and not threatened_by and not home_to:
        for word in [" than ", " like ", " unlike ", " from ", " at ", " in ", " on ",
                     " where ", " when ", " beyond ", " through ", " around ", " over "]:
            if word in obj:
                obj = obj.split(word)[0].strip()

    # Handle compound subjects: "X and Y are Z" -> add facts for both X and Y
    subjects = [subj]
    if " and " in subj:
        subjects = [s.strip() for s in subj.split(" and ")]

    # Extract adjectives from object phrase: "intelligent mammals" -> property: intelligent, category: mammals
    # Split object into words and identify adjective(s) and noun(s)
    obj_words = obj.split()
    adjectives = []
    nouns = []

    for word in obj_words:
        word_clean = word.strip().lower()
        if is_adjective(word_clean):
            adjectives.append(word_clean)
        elif word_clean not in ["a", "an", "the", "very", "quite", "really"]:
            nouns.append(word_clean)

    # The main category is the noun(s) - only if there are nouns
    # If only adjectives, we use has_property instead of is
    main_category = " ".join(nouns) if nouns else None

    # Check for "colored X or Y or Z" pattern — extract colors
    color_match = re.match(r'^colored\s+(.+)$', obj, re.IGNORECASE)
    if color_match:
        color_str = color_match.group(1).strip()
        colors = [c.strip() for c in re.split(r'\s+or\s+|,\s*', color_str) if c.strip()]
        for s in subjects:
            if s:
                parser.loom.add_fact(s, "color", " or ".join(colors))
                for c in colors:
                    parser.loom.add_fact(s, "color", c)
        parser.last_subject = subjects[-1] if subjects else subj
        parser.loom.context.update(subject=parser.last_subject, relation="color", obj=color_str)
        return f"Got it, {parser.last_subject} is colored {color_str}."

    # Add facts for each subject
    for s in subjects:
        if not s:
            continue

        if obj in COLORS:
            parser.loom.add_fact(s, "color", obj)
        elif quantifier:
            # Quantified statements: "some cats are friendly" -> cats can_be friendly
            parser.loom.add_fact(s, "can_be", obj)
        else:
            # Add category fact (the noun part) - only if we have actual nouns
            if main_category:
                parser.loom.add_fact(s, "is", main_category)
                # Also add reverse relation for instance lookups
                # "dogs are mammals" -> mammals has_instance dogs
                parser.loom.add_fact(main_category, "has_instance", s)

            # Add property facts for each adjective
            for adj in adjectives:
                parser.loom.add_fact(s, "has_property", adj)

        # Handle relative clause facts: "X are Y that can/cannot Z" or "X are Y that live in Z"
        for rel_relation, rel_value, _ in relative_clause_facts:
            parser.loom.add_fact(s, rel_relation, rel_value)

        # Handle compound predicate: "X are large and need Y"
        if compound_second_fact:
            relation, second_obj = compound_second_fact
            parser.loom.add_fact(s, relation, second_obj)

        # Handle causal consequence: "X are Y, so they have Z"
        if causal_consequence:
            relation, consequence_obj = causal_consequence
            parser.loom.add_fact(s, relation, consequence_obj)

        # Handle "with X" possession: "mammals with long trunks" -> has: long_trunks
        if with_possession:
            parser.loom.add_fact(s, "has", with_possession)

        # Handle "food for X" pattern: "plankton are food for whales" -> food_for: whales
        if food_for_target:
            parser.loom.add_fact(s, "food_for", food_for_target)

        # Handle "threatened by X" pattern: "coral reefs are threatened by pollution"
        if threatened_by:
            parser.loom.add_fact(s, "has_property", "threatened")
            # Handle compound threats: "pollution and climate change"
            if " and " in threatened_by:
                for threat in threatened_by.split(" and "):
                    parser.loom.add_fact(s, "threatened_by", threat.strip())
            else:
                parser.loom.add_fact(s, "threatened_by", threatened_by)

        # Handle "home to X" pattern: "coral reefs are home to thousands of species"
        if home_to:
            parser.loom.add_fact(s, "home_to", home_to)

    # Track last subject for pronoun resolution
    parser.last_subject = subjects[-1] if subjects else subj
    parser.loom.context.update(subject=parser.last_subject, relation="is", obj=obj)

    return "Got it."
