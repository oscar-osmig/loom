"""
Relation pattern methods for the Parser class.
Handles relation patterns, conditional, becomes, and is_statement.
"""

import re
from ..grammar import is_plural, is_adjective
from .constants import COLORS, RELATION_PATTERNS


def _check_relation_patterns(parser, t: str) -> str | None:
    """Handle all relation patterns (has, can, lives_in, etc.)."""
    # Skip questions - they should be handled by query handlers
    if parser._is_question(t):
        return None

    for phrase, relation, reverse in RELATION_PATTERNS:
        if phrase in t:
            # Skip if this is part of a relative clause "that [verb]"
            # e.g., "birds that can fly" or "dolphins that live in the ocean"
            # should be handled by _check_is_statement
            if " that" + phrase in t:
                continue

            parts = t.split(phrase, 1)
            if len(parts) == 2:
                subj = parts[0].strip()
                obj = parts[1].strip()

                # Skip if subject contains "is/are" - this is an "is/are" statement
                # e.g., "dolphins are mammals that live in the ocean" should be
                # handled by _check_is_statement, not split on "live in"
                if " is " in subj or " are " in subj:
                    continue

                # Skip if subject contains another relation verb that should match first
                # e.g., "penguins live in cold regions and can swim" should match "live in" first
                relation_verbs = [" live in ", " lives in ", " have ", " has ", " eat ", " eats ",
                                  " drink ", " drinks ", " need ", " needs ", " use ", " uses "]
                skip = False
                for verb in relation_verbs:
                    if verb in subj and verb != phrase:
                        skip = True
                        break
                if skip:
                    continue

                # Clean up subject
                for prefix in ["the ", "a ", "an "]:
                    if subj.startswith(prefix):
                        subj = subj[len(prefix):]
                for suffix in [" also", " too", " as well"]:
                    if subj.endswith(suffix):
                        subj = subj[:-len(suffix)].strip()

                # Clean up object - strip discourse markers
                for prefix in ["also ", "too ", "as well ", "even "]:
                    if obj.startswith(prefix):
                        obj = obj[len(prefix):].strip()

                # Handle "X can Y, and Z can Y too" pattern
                # e.g., "eagles can fly very high, and sparrows can fly too"
                and_match = re.search(r",?\s+and\s+(\w+)\s+can\s+(.+?)(?:\s+too)?$", obj)
                if and_match and relation == "can":
                    second_subj = and_match.group(1).strip()
                    second_action = and_match.group(2).strip()
                    # Clean the action
                    for suffix in [" too", " as well", " also"]:
                        if second_action.endswith(suffix):
                            second_action = second_action[:-len(suffix)].strip()
                    parser.loom.add_fact(second_subj, "can", second_action)
                    # Truncate original object
                    obj = obj[:and_match.start()].strip()

                # Handle compound predicates: "X and can/eat/live Y" -> split into two facts
                # e.g., "sharp teeth and can swim fast" -> has: sharp teeth, can: swim fast
                compound_match = re.search(r"\s+and\s+(can|could|eat|eats|live|lives|need|needs|have|has|drink|drinks|use|uses)\s+(.+)$", obj, re.IGNORECASE)
                if compound_match:
                    second_verb = compound_match.group(1).lower()
                    second_obj = compound_match.group(2).strip()
                    # Map verb to relation
                    verb_map = {
                        "can": "can", "could": "can",
                        "eat": "eats", "eats": "eats",
                        "live": "lives_in", "lives": "lives_in",
                        "need": "needs", "needs": "needs",
                        "have": "has", "has": "has",
                        "drink": "drinks", "drinks": "drinks",
                        "use": "uses", "uses": "uses",
                    }
                    if second_verb in verb_map:
                        parser.loom.add_fact(subj, verb_map[second_verb], second_obj)
                    # Truncate to just the first part
                    obj = obj[:compound_match.start()].strip()

                # Truncate object at sentence boundaries (periods followed by space or end)
                # This prevents "live in water. they breathe" from capturing everything
                if ". " in obj:
                    obj = obj.split(". ")[0].strip()
                # Also truncate at period at end
                if obj.endswith("."):
                    obj = obj[:-1].strip()

                # Truncate object at discourse markers
                for marker in [", and ", ", but ", ", so ", ", because ", ", which ", ", that ", ", when "]:
                    if marker in obj:
                        obj = obj.split(marker)[0].strip()

                # Truncate at prepositions and location markers
                for prep in [" from ", " to ", " for ", " with ", " on ", " at ",
                             " in ", " along ", " across ", " through ", " over ",
                             " under ", " between ", " around ", " during "]:
                    if prep in obj:
                        # Don't truncate "to" in these patterns:
                        if prep == " to ":
                            preserve_patterns = [
                                " up to ", " immune to ", " related to ",
                                "going to ", "trying to ", "wanting to ",
                                "able to ", "used to ", "need to ", "have to ",
                                "going to the ", "going to a ",
                            ]
                            if any(p in obj or obj.startswith(p.strip()) for p in preserve_patterns):
                                continue
                        # Don't truncate "in" for "live in" patterns (already handled by relation)
                        if prep == " in " and obj.startswith("in "):
                            continue
                        obj = obj.split(prep)[0].strip()

                # Clean leading quantifiers/determiners: "one of the X" -> "X"
                quantifier_patterns = [
                    "one of the most ", "one of the ", "some of the ",
                    "many of the ", "most of the ", "all of the ",
                    "part of the ", "members of the ",
                ]
                for qp in quantifier_patterns:
                    if obj.startswith(qp):
                        obj = obj[len(qp):]
                        break

                # Clean trailing "too" or similar
                for suffix in [" too", " as well", " also", " very"]:
                    if obj.endswith(suffix):
                        obj = obj[:-len(suffix)].strip()

                parser.loom.add_fact(subj, relation, obj)

                # Add reverse relation if defined
                if reverse:
                    parser.loom.add_fact(obj, reverse, subj)

                # Track subject for pronoun resolution
                parser.last_subject = subj
                parser.loom.context.update(subject=subj, relation=relation, obj=obj)

                # Natural response
                return f"Got it, {subj} {phrase.strip()} {obj}."

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
    """Handle 'X is/are Y' statements, including 'X and Y are Z'."""
    # Skip questions - they should be handled by query handlers
    if parser._is_question(t):
        return None

    # Find the FIRST occurrence of "is" or "are" to split on
    is_pos = t.find(" is ")
    are_pos = t.find(" are ")

    if is_pos == -1 and are_pos == -1:
        return None

    # Use whichever comes first (or the one that exists)
    if is_pos == -1:
        verb = " are "
        split_pos = are_pos
    elif are_pos == -1:
        verb = " is "
        split_pos = is_pos
    else:
        # Both exist - use the one that comes first
        if is_pos < are_pos:
            verb = " is "
            split_pos = is_pos
        else:
            verb = " are "
            split_pos = are_pos

    subj = t[:split_pos].strip()
    obj = t[split_pos + len(verb):].strip()

    if not subj or not obj:
        return None

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
