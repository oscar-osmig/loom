"""
Parser module for Loom.
Handles natural language input and extracts structured knowledge threads.
Learns from any conversation pattern using discourse analysis.

Enhanced with:
- Correction patterns (no, wrong, actually)
- Refinement patterns (only when, except, but not if)
- Procedural patterns (first, then, finally)
- Clarification logic
"""

import re
from .normalizer import normalize, prettify, prettify_cause, prettify_effect
from .grammar import format_what_response, is_plural, get_verb_form, pluralize, format_list, is_adjective
from .discourse import find_discourse_markers, DISCOURSE_MARKERS

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


class Parser:
    """Parses natural language input into knowledge threads."""

    def __init__(self, loom):
        self.loom = loom
        self.last_subject = None  # Track for pronoun resolution
        self.procedure_buffer = []  # Buffer for multi-step procedures
        self.current_procedure = None  # Name of procedure being defined

    def _try_get(self, subject: str, relation: str) -> list:
        """Try to get facts, attempting both singular and plural forms."""
        from .grammar import singularize, pluralize

        result = self.loom.get(subject, relation) or []
        if result:
            return result

        # Try singular form
        singular = singularize(subject)
        if singular != subject:
            result = self.loom.get(singular, relation) or []
            if result:
                return result

        # Try plural form
        plural = pluralize(subject)
        if plural != subject:
            result = self.loom.get(plural, relation) or []
            if result:
                return result

        # Try without trailing 's'
        if subject.endswith('s'):
            result = self.loom.get(subject[:-1], relation) or []
            if result:
                return result

        return []

    def _find_entity(self, subject: str) -> str | None:
        """Find an entity in knowledge, trying singular/plural forms."""
        from .grammar import singularize, pluralize

        if subject in self.loom.knowledge:
            return subject

        singular = singularize(subject)
        if singular in self.loom.knowledge:
            return singular

        plural = pluralize(subject)
        if plural in self.loom.knowledge:
            return plural

        if subject.endswith('s') and subject[:-1] in self.loom.knowledge:
            return subject[:-1]

        return None

    def parse(self, text: str) -> str:
        """Parse input text and update knowledge. Returns natural language response."""
        original = text
        t = text.lower().strip().rstrip("?.")

        # Update context mode
        self.loom.context.mode = self.loom.context.detect_mode(text)

        # Resolve pronouns - handle both start of sentence and in queries
        words = t.split()
        resolved_subject = self.loom.context.last_subject or self.last_subject

        if resolved_subject:
            # Pronoun at start of sentence
            if words and words[0] in ["they", "them", "it", "he", "she", "this", "that"]:
                t = resolved_subject + " " + " ".join(words[1:])
            # Pronoun in query patterns like "what do they need" (but NOT in object position like "feed them milk")
            elif " they " in t and not re.search(r"feed\s+they", t):
                t = t.replace(" they ", f" {resolved_subject} ")
            # Only replace "them" at start of phrases, not when it's an object (like "feed them")
            elif " them" in t and t.startswith("them "):
                t = t.replace("them ", f"{resolved_subject} ", 1)
            elif " it " in t and len(t.split(" it ")) == 2:  # Only single "it" to avoid false matches
                # Don't replace "it" if it's in "give birth to X and feed it"
                if not re.search(r"(feed|give)\s+it\b", t):
                    t = t.replace(" it ", f" {resolved_subject} ")

        # Check patterns in priority order
        checks = [
            self._check_clarification_response,  # Handle pending clarifications
            self._check_correction,              # "no, that's wrong"
            self._check_refinement,              # "only when...", "except..."
            self._check_procedural,              # "first...", "then..."
            self._check_however_pattern,         # "However, X" - early to avoid negation match
            self._check_because_pattern,         # "Because X, Y" - early for causal sentences
            self._check_informational_pattern,   # Complex encyclopedic sentences - early!
            self._check_contrast_pattern,        # "X are A, while Y are B" - early!
            self._check_name_query,
            self._check_negation,
            self._check_color_query,
            self._check_where_query,
            self._check_what_lives_query,
            self._check_who_query,
            self._check_how_many_query,
            self._check_made_of_query,
            self._check_part_of_query,
            self._check_what_has_query,
            self._check_what_does_query,
            self._check_what_verb_query,         # "what do X drink/eat/need?" queries
            self._check_found_in_query,          # "what X can Y be found in?" - BEFORE can_query!
            self._check_can_query,
            self._check_are_is_query,            # "are X Y?" / "is X Y?"
            self._check_why_query,
            self._check_what_causes_query,       # "what causes X?"
            self._check_effect_query,
            self._check_lay_eggs_query,          # "which animals lay eggs?" - BEFORE which_query!
            self._check_which_query,             # "which X has Y?" queries
            self._check_difference_query,        # "what is the difference/how are X different" - before how_query
            self._check_reproduce_query,         # "how do X reproduce?" - before how_query
            self._check_classification_query,    # "what groups are X classified into?"
            self._check_examples_query,          # "what are examples of X?"
            self._check_breathing_query,         # "how do X breathe?"
            self._check_backbone_query,          # "do X have backbones?"
            self._check_feeding_query,           # "how do X feed their young?"
            self._check_how_query,               # "how do X verb?" queries
            self._check_characteristics_query,   # "what characteristics do X share?"
            self._check_differ_query,            # "in what ways do X differ?"
            self._check_what_query,
            self._check_looks_pattern,
            self._check_analogy_pattern,
            self._check_same_as_pattern,
            self._check_relation_patterns,
            self._check_conditional_pattern,
            self._check_becomes_pattern,
            self._check_is_statement,
            self._check_discourse_patterns,  # Natural speech patterns
            self._learn_from_conversation,   # Fallback: try to learn something
        ]

        for check in checks:
            result = check(t)
            if result:
                return result

        # If nothing matched, maybe ask for clarification
        return self._maybe_ask_clarification(t)

    # ==================== CORRECTION & REFINEMENT ====================

    def _check_clarification_response(self, t: str) -> str | None:
        """Handle response to a pending clarification question."""
        if not self.loom.context.pending_clarification:
            return None

        clarification = self.loom.context.pending_clarification
        about = clarification["about"]

        # User is providing the clarification
        self.loom.context.clear_clarification()

        # Try to use the response to fill in the missing info
        # For now, store it as additional info about the topic
        if about and t:
            self.loom.add_fact(about, "is", t)
            self.loom.context.update(subject=about, obj=t)
            return f"Got it, {about} is {t}."

        return None

    def _check_correction(self, t: str) -> str | None:
        """
        Handle corrections: "no, that's wrong", "actually X is Y"
        Retracts or updates previous facts.
        """
        # Check for correction indicators
        is_correction = False
        for word in CORRECTION_WORDS:
            if t.startswith(word) or f" {word}" in t:
                is_correction = True
                # Remove the correction word
                t = t.replace(word, "").strip()
                break

        if not is_correction:
            return None

        # Pattern: "actually X is Y" or just "X is Y" after correction word
        if " is " in t or " are " in t:
            verb = " is " if " is " in t else " are "
            parts = t.split(verb, 1)
            if len(parts) == 2:
                subj = parts[0].strip()
                obj = parts[1].strip()

                # Clean up
                for prefix in ["the ", "a ", "an ", "that "]:
                    if subj.startswith(prefix):
                        subj = subj[len(prefix):]

                # Get what was previously said about this subject
                old_facts = self.loom.get(subj, "is") or []

                # Retract old conflicting facts
                for old in old_facts:
                    if old != normalize(obj):
                        self.loom.retract_fact(subj, "is", old)
                        self.loom.context.add_correction(old, obj, "is")

                # Add the new fact
                self.loom.add_fact(subj, "is", obj)
                self.loom.context.update(subject=subj, obj=obj)
                self.last_subject = subj

                return f"Corrected. {subj.title()} is {obj}."

        # Pattern: "X can't Y" or "X doesn't Y"
        if " can't " in t or " cannot " in t:
            parts = t.split(" can't " if " can't " in t else " cannot ", 1)
            if len(parts) == 2:
                subj = parts[0].strip()
                action = parts[1].strip()

                # Retract "can" if it exists
                self.loom.retract_fact(subj, "can", action)
                self.loom.add_fact(subj, "cannot", action)

                return f"Corrected. {subj.title()} cannot {action}."

        # Pattern: "X doesn't have Y"
        if " doesn't have " in t or " don't have " in t:
            pattern = " doesn't have " if " doesn't have " in t else " don't have "
            parts = t.split(pattern, 1)
            if len(parts) == 2:
                subj = parts[0].strip()
                obj = parts[1].strip()

                self.loom.retract_fact(subj, "has", obj)
                self.loom.add_fact(subj, "has_not", obj)

                return f"Corrected. {subj.title()} doesn't have {obj}."

        return None

    def _check_refinement(self, t: str) -> str | None:
        """
        Handle refinements: "only when X", "except if Y", "but not if Z"
        Adds constraints to existing facts.
        """
        for indicator in REFINEMENT_WORDS:
            if indicator in t:
                parts = t.split(indicator, 1)
                if len(parts) == 2:
                    main_part = parts[0].strip()
                    condition = parts[1].strip()

                    # If main_part is empty, use last context
                    if not main_part and self.loom.context.last_subject:
                        subj = self.loom.context.last_subject
                        rel = self.loom.context.last_relation or "is"
                        obj = self.loom.context.last_object

                        if subj and obj:
                            self.loom.add_constraint(subj, rel, obj, condition)
                            return f"Noted: {subj} {rel} {obj}, {indicator} {condition}."

                    # Try to parse main_part
                    if " is " in main_part or " are " in main_part:
                        verb = " is " if " is " in main_part else " are "
                        main_parts = main_part.split(verb, 1)
                        if len(main_parts) == 2:
                            subj = main_parts[0].strip()
                            obj = main_parts[1].strip()

                            # Clean up
                            for prefix in ["the ", "a ", "an "]:
                                if subj.startswith(prefix):
                                    subj = subj[len(prefix):]

                            self.loom.add_fact(subj, "is", obj)
                            self.loom.add_constraint(subj, "is", obj, condition)
                            self.loom.context.update(subject=subj, relation="is", obj=obj)

                            return f"Got it: {subj} is {obj}, {indicator} {condition}."

                    # Pattern: "X can Y only when Z"
                    if " can " in main_part:
                        can_parts = main_part.split(" can ", 1)
                        if len(can_parts) == 2:
                            subj = can_parts[0].strip()
                            action = can_parts[1].strip()

                            self.loom.add_fact(subj, "can", action)
                            self.loom.add_constraint(subj, "can", action, condition)

                            return f"Got it: {subj} can {action}, {indicator} {condition}."

        return None

    def _check_procedural(self, t: str) -> str | None:
        """
        Handle procedural knowledge: "first X, then Y, finally Z"
        Or: "to do X: first A, then B"
        """
        # Check for procedure definition start: "to X:" or "how to X:"
        for start in PROCEDURAL_START:
            if t.startswith(start):
                rest = t[len(start):].strip()

                # Check if this defines a procedure name
                if ":" in rest:
                    name, steps_text = rest.split(":", 1)
                    self.current_procedure = name.strip()
                    self.procedure_buffer = []

                    # Parse steps from the rest
                    steps = self._parse_procedure_steps(steps_text)
                    if steps:
                        self.loom.add_procedure(self.current_procedure, steps)
                        self.current_procedure = None
                        return f"Learned procedure '{name.strip()}' with {len(steps)} steps."

                    return f"Tell me the steps for '{name.strip()}'."

        # Check for sequence markers
        for marker in PROCEDURAL_SEQUENCE:
            if t.startswith(marker):
                step = t[len(marker):].strip()
                step = step.lstrip(",").strip()

                if self.current_procedure:
                    self.procedure_buffer.append(step)

                    if marker in ["finally", "lastly"]:
                        # End of procedure
                        self.loom.add_procedure(self.current_procedure, self.procedure_buffer)
                        name = self.current_procedure
                        count = len(self.procedure_buffer)
                        self.current_procedure = None
                        self.procedure_buffer = []
                        return f"Learned procedure '{name}' with {count} steps."

                    return f"Step {len(self.procedure_buffer)}: {step}. What's next?"
                else:
                    # Single sequence without procedure name
                    self.procedure_buffer.append(step)
                    return f"Noted step: {step}."

        return None

    def _parse_procedure_steps(self, text: str) -> list:
        """Parse procedure steps from text."""
        steps = []

        # Split by sequence markers
        parts = re.split(r'\b(first|then|next|after that|finally|lastly)\b', text, flags=re.IGNORECASE)

        for i, part in enumerate(parts):
            part = part.strip().strip(",").strip()
            if part and part.lower() not in PROCEDURAL_SEQUENCE:
                steps.append(part)

        return steps

    def _maybe_ask_clarification(self, t: str) -> str:
        """
        If we couldn't understand, maybe ask for clarification.
        """
        # If it's a question we couldn't answer, say so
        if self._is_question(t):
            return f"I don't have enough information to answer that question."

        # Don't ask too often - only for certain patterns
        words = t.split()

        if len(words) < 2:
            return "I'm listening. Tell me more."

        # If there's a subject but unclear relation
        if len(words) >= 2 and len(words) <= 4:
            potential_subject = words[0]
            self.loom.context.set_clarification(
                f"What about {potential_subject}?",
                potential_subject
            )
            return f"I heard '{t}'. What would you like to tell me about {potential_subject}?"

        return "I'm listening. Tell me more, and I'll try to connect the threads."

    # ==================== QUERIES ====================

    def _check_name_query(self, t: str) -> str | None:
        """Handle 'what is your name?' queries."""
        if any(x in t for x in ["name", "called"]) and any(x in t for x in ["your", "what"]):
            return f"I am {self.loom.name}."
        return None

    def _check_color_query(self, t: str) -> str | None:
        """Handle 'what color is X?' queries."""
        if "what color" not in t:
            return None

        subj = t.split("what color")[-1]
        for v in [" is ", " are ", " does ", " do "]:
            subj = subj.replace(v, " ")
        subj = subj.strip()

        color = self.loom.get(subj, "color")
        if color:
            verb = "are" if is_plural(subj) else "is"
            return f"{subj.title()} {verb} {color[0]}."
        else:
            self.loom.add_fact(subj, "has_open_question", "color")
            return f"I don't know the color of {subj} yet. What color is it?"

    def _check_where_query(self, t: str) -> str | None:
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
            loc = self._try_get(subj, rel)
            if loc:
                verb = "are" if is_plural(subj) else "is"
                if rel in ["can_live", "can_live_in"]:
                    verb = "can live"
                    return f"{subj.title()} {verb} in {format_list([l.replace('_', ' ') for l in loc])}."
                return f"{subj.title()} {verb} in {loc[0]}."

        self.loom.add_fact(subj, "has_open_question", "location")
        return f"I don't know where {subj} is. Where can it be found?"

    def _check_what_lives_query(self, t: str) -> str | None:
        """Handle 'what X live in Y?' queries - find entities by location."""
        # Match "what animals live in the ocean" or "what lives in water"
        match = re.match(r"what\s+(\w+)?\s*(?:live|lives|living)\s+(?:in|on)\s+(?:the\s+)?(.+)", t)
        if not match:
            return None

        category = match.group(1)  # e.g., "animals" (may be None)
        location = match.group(2).strip()  # e.g., "ocean"

        results = []

        # Search for entities that live in this location
        for node, relations in self.loom.knowledge.items():
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

    def _check_who_query(self, t: str) -> str | None:
        """Handle 'who is X?' queries."""
        if not t.startswith("who"):
            return None

        subj = re.sub(r"who (is|are|was|were)?\s*", "", t).strip()
        if not subj:
            return None

        facts = self.loom.get(subj, "is")
        if facts:
            return f"{subj.title()} is {facts[0]}."

        self.loom.add_fact(subj, "has_open_question", "identity")
        return f"I don't know who {subj} is. Can you tell me?"

    def _check_what_has_query(self, t: str) -> str | None:
        """Handle 'what does X have?' or 'does X have Y?' queries."""
        # "does X have Y?"
        match = re.match(r"do(?:es)?\s+(.+?)\s+have\s+(.+)", t)
        if match:
            subj, obj = match.groups()
            things = self.loom.get(subj, "has")
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
            things = self.loom.get(subj, "has")
            if things:
                verb = "have" if is_plural(subj) else "has"
                # Replace underscores with spaces for display
                display = [x.replace("_", " ") for x in things]
                return f"{subj.title()} {verb} {format_list(display)}."
            else:
                self.loom.add_fact(subj, "has_open_question", "possessions")
                return f"I don't know what {subj} has yet."

        return None

    def _check_what_verb_query(self, t: str) -> str | None:
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

            things = self.loom.get(subj, relation)
            if things:
                # Replace underscores with spaces for display
                display = [x.replace("_", " ") for x in things]
                return f"{subj.title()} {verb} {format_list(display)}."
            else:
                return f"I don't know what {subj} {verb}."

        return None

    def _check_how_many_query(self, t: str) -> str | None:
        """Handle 'how many X does Y have?' queries."""
        match = re.match(r"how many\s+(\w+)\s+(?:does|do)\s+(?:a\s+|an\s+|the\s+)?(\w+)\s+have", t)
        if match:
            thing, subj = match.groups()
            # Check "has" relation for counts
            has_items = self.loom.get(subj, "has") or []
            for item in has_items:
                # Look for numeric patterns like "four_legs" or "two_eyes"
                if thing in item or item.endswith(thing):
                    return f"{subj.title()} has {item.replace('_', ' ')}."

            return f"I don't know how many {thing} {subj} has."
        return None

    def _check_made_of_query(self, t: str) -> str | None:
        """Handle 'what is X made of?' queries."""
        match = re.match(r"what\s+(?:is|are)\s+(?:a\s+|an\s+|the\s+)?(\w+)\s+made\s+(?:of|from)", t)
        if match:
            subj = match.group(1)
            materials = self.loom.get(subj, "made_of") or []
            if materials:
                return f"{subj.title()} is made of {format_list(materials)}."
            return f"I don't know what {subj} is made of."
        return None

    def _check_part_of_query(self, t: str) -> str | None:
        """Handle 'what is X part of?' or 'is X part of Y?' queries."""
        # "what is X part of?"
        match = re.match(r"what\s+(?:is|are)\s+(?:a\s+|an\s+|the\s+)?(\w+)\s+part\s+of", t)
        if match:
            subj = match.group(1)
            wholes = self.loom.get(subj, "part_of") or []
            if wholes:
                return f"{subj.title()} is part of {format_list(wholes)}."
            return f"I don't know what {subj} is part of."

        # "is X part of Y?"
        match = re.match(r"(?:is|are)\s+(?:a\s+|an\s+|the\s+)?(\w+)\s+part\s+of\s+(?:a\s+|an\s+|the\s+)?(\w+)", t)
        if match:
            part, whole = match.groups()
            parts = self.loom.get(part, "part_of") or []
            if normalize(whole) in [normalize(p) for p in parts]:
                return f"Yes, {part} is part of {whole}."
            return f"I don't know if {part} is part of {whole}."

        return None

    def _check_what_does_query(self, t: str) -> str | None:
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
            things = self.loom.get(subj, relation)

            if things:
                verb_form = verb if is_plural(subj) else verb + "s"
                # Replace underscores with spaces for display
                display = [x.replace("_", " ") for x in things]
                return f"{subj.title()} {verb_form} {format_list(display)}."
            else:
                self.loom.add_fact(subj, "has_open_question", relation)
                verb_form = verb if is_plural(subj) else verb + "s"
                return f"I don't know what {subj} {verb_form} yet."

        return None

    def _check_can_query(self, t: str) -> str | None:
        """Handle 'can X do Y?' or 'what can X do?' or 'what X can Y?' queries."""
        # "what X can't/cannot Y?" - e.g., "what birds can't fly?"
        # Handle different apostrophe characters: ' (straight) and ' (curly)
        match = re.match(r"what\s+(\w+)\s+(?:can[''']t|cannot|can not)\s+(\w+)", t)
        if match:
            category, ability = match.groups()
            # Search for entities that are of category X and cannot do Y
            results = []
            for node, relations in self.loom.knowledge.items():
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
            for node, relations in self.loom.knowledge.items():
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
            abilities = self.loom.get(subj, "can")
            if abilities:
                # Replace underscores for display
                display = [a.replace("_", " ") for a in abilities]
                return f"{subj.title()} can {format_list(display)}."
            else:
                # Check for cannot
                cannot = self.loom.get(subj, "cannot")
                if cannot:
                    display = [a.replace("_", " ") for a in cannot]
                    return f"I know {subj} cannot {format_list(display)}."
                self.loom.add_fact(subj, "has_open_question", "abilities")
                return f"I don't know what {subj} can do yet."

        # "can X do Y?" or "can X Y?"
        match = re.match(r"can\s+(.+?)\s+(\w+)(?:\s|$)", t)
        if match:
            subj, action = match.groups()

            # First check "cannot"
            cannot = self.loom.get(subj, "cannot") or []
            for inability in cannot:
                if action in inability or inability.startswith(action):
                    return f"No, {subj} cannot {inability.replace('_', ' ')}."

            # Then check "can"
            abilities = self.loom.get(subj, "can") or []
            if abilities:
                for ability in abilities:
                    if action in ability or ability.startswith(action):
                        return f"Yes, {subj} can {ability.replace('_', ' ')}."
                abilities_display = [a.replace('_', ' ') for a in abilities]
                return f"I know {subj} can {format_list(abilities_display)}, but I'm not sure about {action}."

            # Neither can nor cannot found
            self.loom.add_fact(subj, "has_open_question", "abilities")
            return f"I don't know if {subj} can {action}."

        return None

    def _check_are_is_query(self, t: str) -> str | None:
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
        self.last_subject = subj
        self.loom.context.update(subject=subj)

        obj_norm = normalize(obj)
        verb = "are" if is_plural(subj) else "is"

        # Check if subj is obj (category)
        facts = self.loom.get(subj, "is") or []
        for fact in facts:
            if obj_norm in normalize(fact) or normalize(fact) in obj_norm:
                return f"Yes, {subj} {verb} {obj}."

        # Check has_property relation (for adjectives like "intelligent", "dangerous")
        properties = self.loom.get(subj, "has_property") or []
        for prop in properties:
            if obj_norm in normalize(prop) or normalize(prop) in obj_norm:
                return f"Yes, {subj} {verb} {obj}."

        # Check can_be relation (for quantified facts: "some cats are friendly")
        can_be = self.loom.get(subj, "can_be") or []
        for possibility in can_be:
            if obj_norm in normalize(possibility) or normalize(possibility) in obj_norm:
                return f"Yes, some {subj} {verb} {obj}."

        # Check negative
        negatives = self.loom.get(subj, "is_not") or []
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

    def _check_why_query(self, t: str) -> str | None:
        """Handle 'why does X happen?' or 'why X need Y?' queries."""
        if not t.startswith("why"):
            return None

        # Pattern: "why X need/needs Y" or "why do X need Y"
        need_match = re.match(r"why (?:do |does )?(\w+) (?:need|needs?) (.+)", t)
        if need_match:
            subj = need_match.group(1).strip()
            needed_thing = need_match.group(2).strip()

            # Check if we know what this subject needs
            needs = self.loom.get(subj, "needs") or []
            properties = self.loom.get(subj, "has_property") or []
            categories = self.loom.get(subj, "is") or []

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
        self.last_subject = subj
        self.loom.context.update(subject=subj)

        # Look for causes (reverse lookup)
        # Check if anything causes this subject
        for node in self.loom.knowledge:
            causes = self.loom.get(node, "causes")
            if causes and normalize(subj) in [normalize(c) for c in causes]:
                return f"Because {node} causes it."

        self.loom.add_fact(subj, "has_open_question", "reason")
        return f"I don't know why {subj}. What's the reason?"

    def _check_however_pattern(self, t: str) -> str | None:
        """Handle 'However, X' patterns - strip 'however' and parse the rest."""
        if t.startswith("however, "):
            rest = t[9:].strip()  # "however, " is 9 chars
        elif t.startswith("however "):
            rest = t[8:].strip()  # "however " is 8 chars
        else:
            return None

        if rest.startswith(", "):
            rest = rest[2:]

        # Handle "X are Y that cannot Z" pattern
        # e.g., "penguins are birds that cannot fly"
        match = re.match(r"(.+?)\s+(?:is|are)\s+(.+?)\s+that\s+cannot\s+(.+)", rest)
        if match:
            subj = match.group(1).strip()
            category = match.group(2).strip()
            inability = match.group(3).strip()
            self.loom.add_fact(subj, "is", category)
            self.loom.add_fact(subj, "cannot", inability)
            self.last_subject = subj
            return f"Got it, {subj} are {category} that cannot {inability}."

        # Process the rest as a normal statement
        return self.parse(rest)

    def _check_because_pattern(self, t: str) -> str | None:
        """Handle 'Because X, Y' or 'Since X, Y' patterns."""
        # Match "because X, Y" or "since X, Y"
        match = re.match(r"(?:because|since)\s+(.+?),\s*(.+)", t, re.IGNORECASE)
        if not match:
            return None

        cause_part = match.group(1).strip()
        effect_part = match.group(2).strip()

        # Extract the core subject from cause (e.g., "cats are hunters" -> "cats")
        cause_subj = None
        cause_pred = None
        if " are " in cause_part:
            parts = cause_part.split(" are ", 1)
            cause_subj = parts[0].strip()
            cause_pred = parts[1].strip()
        elif " is " in cause_part:
            parts = cause_part.split(" is ", 1)
            cause_subj = parts[0].strip()
            cause_pred = parts[1].strip()

        # Store the cause fact - use has_property for adjectives, is for nouns
        if cause_subj and cause_pred:
            if is_adjective(cause_pred):
                self.loom.add_fact(cause_subj, "has_property", cause_pred)
            else:
                self.loom.add_fact(cause_subj, "is", cause_pred)
            self.last_subject = cause_subj

        # Extract the effect (e.g., "they have sharp claws" -> resolve "they", then add has relation)
        effect_part = effect_part.lower()

        # Resolve "they" to the cause subject
        if effect_part.startswith("they ") and cause_subj:
            effect_part = cause_subj + effect_part[4:]

        # Parse the effect part for "X have/has Y"
        have_match = re.match(r"(.+?)\s+(?:have|has)\s+(.+)", effect_part)
        if have_match:
            subj = have_match.group(1).strip()
            obj = have_match.group(2).strip()
            self.loom.add_fact(subj, "has", obj)
            return f"Got it, {cause_subj} are {cause_pred}, so {subj} have {obj}."

        # Parse for "X eat/eats Y"
        eat_match = re.match(r"(.+?)\s+(?:eat|eats)\s+(.+)", effect_part)
        if eat_match:
            subj = eat_match.group(1).strip()
            obj = eat_match.group(2).strip()
            self.loom.add_fact(subj, "eats", obj)
            return f"Got it, because {cause_subj} are {cause_pred}, {subj} eat {obj}."

        # Parse for "X can Y"
        can_match = re.match(r"(.+?)\s+can\s+(.+)", effect_part)
        if can_match:
            subj = can_match.group(1).strip()
            action = can_match.group(2).strip()
            self.loom.add_fact(subj, "can", action)
            return f"Got it, because {cause_subj} are {cause_pred}, {subj} can {action}."

        # Parse for "X need/needs Y"
        need_match = re.match(r"(.+?)\s+(?:need|needs)\s+(.+)", effect_part)
        if need_match:
            subj = need_match.group(1).strip()
            obj = need_match.group(2).strip()
            self.loom.add_fact(subj, "needs", obj)
            return f"Got it, because {cause_subj} are {cause_pred}, {subj} need {obj}."

        # Store a general causal relationship
        if cause_pred:
            self.loom.add_fact(cause_pred, "causes", effect_part)

        return f"Got it, because {cause_part}."

    def _check_what_causes_query(self, t: str) -> str | None:
        """Handle 'what causes X?' queries."""
        # Match "what causes X" or "what cause X"
        match = re.match(r"what\s+causes?\s+(.+)", t)
        if not match:
            return None

        effect = match.group(1).strip()
        effect_norm = normalize(effect)

        # Search for what causes this effect
        causes = []
        for node, relations in self.loom.knowledge.items():
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

    def _check_effect_query(self, t: str) -> str | None:
        """Handle 'what happens when X?' queries."""
        if "what happens" not in t:
            return None

        subj = None
        if "when " in t:
            subj = t.split("when ")[-1].strip()

        if not subj:
            return None

        effects = self.loom.get(subj, "causes")
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
            self.loom.add_fact(subj, "has_open_question", "effects")
            return f"I don't know what happens when {subj}. What occurs?"

    def _check_what_query(self, t: str) -> str | None:
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

            for node, relations in self.loom.knowledge.items():
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
                self.last_subject = results[0] if len(results) == 1 else target
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
        self.last_subject = subj
        self.loom.context.update(subject=subj)

        facts = self.loom.get(subj, "is")
        if facts:
            # Build a rich response including abilities
            verb = "are" if is_plural(subj) else "is"
            category = facts[0].replace("_", " ")

            # Check for cannot abilities to add context
            cannot = self.loom.get(subj, "cannot") or []
            can = self.loom.get(subj, "can") or []

            if cannot:
                inability = cannot[0].replace("_", " ")
                return f"{subj.title()} {verb} {category} that cannot {inability}."
            elif can:
                ability = can[0].replace("_", " ")
                return f"{subj.title()} {verb} {category} that can {ability}."
            else:
                return format_what_response(subj, facts[0])
        else:
            self.loom.add_fact(subj, "has_open_question", "identity")
            verb = "are" if is_plural(subj) else "is"
            return f"I don't know what {subj} {verb} yet. Can you tell me?"

    def _check_which_query(self, t: str) -> str | None:
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
            for node, relations in self.loom.knowledge.items():
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
            for node, relations in self.loom.knowledge.items():
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

    def _check_how_query(self, t: str) -> str | None:
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
            abilities = self.loom.get(subj, "can") or []
            for ability in abilities:
                if verb in ability or ability.startswith(verb):
                    return f"{subj.title()} can {ability.replace('_', ' ')}."

            # Check for method/process facts
            methods = self.loom.get(subj, "method") or []
            if methods:
                return f"{subj.title()} {verb} by {methods[0].replace('_', ' ')}."

            # Check for needs/uses
            needs = self.loom.get(subj, "needs") or []
            uses = self.loom.get(subj, "uses") or []
            if verb in ["get", "obtain"] and (needs or uses):
                items = needs + uses
                return f"{subj.title()} {verb}s {items[0].replace('_', ' ')}."

            return f"I don't know how {subj} {verb}."

        return None

    def _check_found_in_query(self, t: str) -> str | None:
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
        locations = self.loom.get(subj, "found_in") or []
        locations += self.loom.get(subj, "lives_in") or []
        locations += self.loom.get(subj, "located_in") or []

        if locations:
            display = [loc.replace("_", " ") for loc in locations]
            return f"{subj.title()} can be found in {format_list(display)}."
        else:
            return f"I don't know where {subj} can be found."

    def _check_characteristics_query(self, t: str) -> str | None:
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
        props = self.loom.get(subj, "has_property") or []
        for p in props:
            characteristics.append(f"are {p.replace('_', ' ')}")

        # Check has
        has_items = self.loom.get(subj, "has") or []
        for h in has_items:
            characteristics.append(f"have {h.replace('_', ' ')}")

        # Check can
        abilities = self.loom.get(subj, "can") or []
        for a in abilities:
            characteristics.append(f"can {a.replace('_', ' ')}")

        # Check needs
        needs = self.loom.get(subj, "needs") or []
        for n in needs:
            characteristics.append(f"need {n.replace('_', ' ')}")

        if characteristics:
            return f"{subj.title()} {', '.join(characteristics[:5])}."
        else:
            return f"I don't know what characteristics {subj} have."

    def _check_differ_query(self, t: str) -> str | None:
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
        variations = self.loom.get(subj, "varies_in") or []

        if variations:
            display = [v.replace("_", " ") for v in variations]
            return f"{subj.title()} differ in {format_list(display)}."
        else:
            return f"I don't know in what ways {subj} differ."

    def _check_reproduce_query(self, t: str) -> str | None:
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
        abilities = self.loom.get(subj, "can") or []
        for a in abilities:
            if "reproduce" in a:
                return f"{subj.title()} can {a.replace('_', ' ')}."

        return f"I don't know how {subj} reproduce."

    def _check_classification_query(self, t: str) -> str | None:
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
        groups = self._try_get(subj, "includes_group")
        if groups:
            display = [g.replace("_", " ") for g in groups]
            return f"{subj.title()} are classified into {format_list(display)}."

        return f"I don't know what groups {subj} are classified into."

    def _check_examples_query(self, t: str) -> str | None:
        """Handle 'what are examples of X?' queries."""
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

        # Look for example facts (try singular/plural)
        examples = self._try_get(subj, "example")
        if examples:
            display = [e.replace("_", " ") for e in examples]
            return f"Examples of {subj}: {format_list(display)}."

        return f"I don't know any examples of {subj}."

    def _check_lay_eggs_query(self, t: str) -> str | None:
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
                for entity, relations in self.loom.knowledge.items():
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

    def _check_breathing_query(self, t: str) -> str | None:
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
        breathes_with = self._try_get(subj, "breathes_with")
        uses = self._try_get(subj, "uses")
        uses_to = self._try_get(subj, "uses_to")

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

    def _check_backbone_query(self, t: str) -> str | None:
        """Handle 'do X have backbones?' queries."""
        # Only handle questions
        if not self._is_question(t):
            return None

        # Special case for vertebrate/invertebrate question
        if "vertebrate" in t.lower() and "invertebrate" in t.lower():
            inv_has_not = self._try_get("invertebrates", "has_not")
            if inv_has_not:
                return f"Invertebrates do not have {inv_has_not[0].replace('_', ' ')}, while vertebrates do."
            return "Invertebrates do not have backbones, while vertebrates do."

        match = re.match(r"(?:do|does)\s+(.+?)\s+have\s+(.+)", t, re.IGNORECASE)
        if match:
            subj = match.group(1).strip()
            obj = match.group(2).strip().rstrip('?')

            # Check has_not (try singular/plural)
            has_not = self._try_get(subj, "has_not")
            for item in has_not:
                if obj.lower() in item.lower():
                    return f"No, {subj} do not have {obj}."

            # Check has
            has_items = self._try_get(subj, "has")
            for item in has_items:
                if obj.lower() in item.lower():
                    return f"Yes, {subj} have {obj}."

            return f"I don't know if {subj} have {obj}."

        return None

    def _check_feeding_query(self, t: str) -> str | None:
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
        feeds_with = self._try_get(subj, "feeds_young_with")
        if feeds_with:
            return f"{subj.title()} feed their young with {feeds_with[0].replace('_', ' ')}."

        return f"I don't know how {subj} feed their young."

    def _check_difference_query(self, t: str) -> str | None:
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
        props1 = self._try_get(subj1, "has_property")
        props2 = self._try_get(subj2, "has_property")
        for p in props1:
            if p not in props2:
                differences.append(f"{subj1} are {p.replace('_', ' ')}")
        for p in props2:
            if p not in props1:
                differences.append(f"{subj2} are {p.replace('_', ' ')}")

        # Compare has
        has1 = self._try_get(subj1, "has")
        has2 = self._try_get(subj2, "has")
        for h in has1:
            if h not in has2:
                differences.append(f"{subj1} have {h.replace('_', ' ')}")
        for h in has2:
            if h not in has1:
                differences.append(f"{subj2} have {h.replace('_', ' ')}")

        # Compare produces
        prod1 = self._try_get(subj1, "produces")
        prod2 = self._try_get(subj2, "produces")
        for p in prod1:
            if p not in prod2:
                differences.append(f"{subj1} lay {p.replace('_', ' ')}")

        # Compare lives_in
        loc1 = self._try_get(subj1, "lives_in")
        loc2 = self._try_get(subj2, "lives_in")
        for l in loc1:
            if l not in loc2:
                differences.append(f"{subj1} live {l.replace('_', ' ')}")
        for l in loc2:
            if l not in loc1:
                differences.append(f"{subj2} live {l.replace('_', ' ')}")

        # Compare breathes_through
        br1 = self._try_get(subj1, "breathes_through")
        br2 = self._try_get(subj2, "breathes_through")
        for b in br2:
            if b not in br1:
                differences.append(f"{subj2} breathe {b.replace('_', ' ')}")

        if differences:
            return f"Differences: {'; '.join(differences[:4])}."
        else:
            return f"I don't know the differences between {subj1} and {subj2}."

    def _check_informational_pattern(self, t: str) -> str | None:
        """
        Handle complex informational/encyclopedic sentences.
        Examples:
        - "Animals are living organisms found in nearly every environment"
        - "All animals share certain characteristics: they are multicellular, need energy"
        - "Most animals can move at some stage of life and reproduce sexually"
        """
        # Skip questions
        if self._is_question(t):
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
            self.loom.add_fact(subj, "is", category)

            # Extract locations from "X, from A to B" or just "X"
            from_to_match = re.search(r",?\s*from\s+(.+?)\s+to\s+(.+?)(?:\.|$)", locations_str)
            if from_to_match:
                loc1 = from_to_match.group(1).strip()
                loc2 = from_to_match.group(2).strip()
                self.loom.add_fact(subj, "found_in", loc1)
                self.loom.add_fact(subj, "found_in", loc2)
            else:
                # Just add the whole location string
                self.loom.add_fact(subj, "found_in", locations_str)

            self.last_subject = subj
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
                    self.loom.add_fact(subj, "has_property", prop)
                    facts_added += 1
                    continue

                # "need energy" -> needs: energy
                need_match = re.match(r"need(?:s)?\s+(.+)", part)
                if need_match:
                    obj = need_match.group(1).strip()
                    # Clean parentheticals
                    obj = re.sub(r'\s*\([^)]*\)', '', obj).strip()
                    self.loom.add_fact(subj, "needs", obj)
                    facts_added += 1
                    continue

                # "can respond to stimuli" -> can: respond to stimuli
                can_match = re.match(r"can\s+(.+)", part)
                if can_match:
                    ability = can_match.group(1).strip()
                    self.loom.add_fact(subj, "can", ability)
                    facts_added += 1
                    continue

                # "have specialized cells" -> has: specialized cells
                have_match = re.match(r"have\s+(.+)", part)
                if have_match:
                    obj = have_match.group(1).strip()
                    self.loom.add_fact(subj, "has", obj)
                    facts_added += 1
                    continue

            if facts_added > 0:
                self.last_subject = subj
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
                    self.loom.add_fact(subj, "can", ability)

            self.last_subject = subj
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
                self.loom.add_fact(subj, "is", category)
                self.loom.add_fact(subj, "has", possession)
            else:
                self.loom.add_fact(subj, "is", rest)

            self.last_subject = subj
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
                    self.loom.add_fact(subj, "varies_in", diff)

            self.last_subject = subj
            return "Got it."

        # Pattern 6: "X are classified into Y such as A, B, C"
        # e.g., "Animals are classified into major groups such as mammals, birds, reptiles"
        match = re.match(r"(.+?)\s+(?:is|are)\s+classified\s+into\s+(.+?)\s+such\s+as\s+(.+)", t, re.IGNORECASE)
        if match:
            subj = match.group(1).strip()
            group_type = match.group(2).strip()
            items_str = match.group(3).strip()

            # Store the classification
            self.loom.add_fact(subj, "classified_into", group_type)

            # Extract the list items
            items = re.split(r',\s*(?:and\s+)?|\s+and\s+', items_str)
            for item in items:
                item = item.strip().rstrip('.')
                if item:
                    self.loom.add_fact(subj, "includes_group", item)
                    self.loom.add_fact(item, "is_type_of", subj)

            self.last_subject = subj
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
                    self.loom.add_fact(subj, "example", ex)
                    self.loom.add_fact(ex, "is", subj)

            # Parse the predicate
            # "do not have Y" -> has_not: Y
            not_have_match = re.match(r"do\s+not\s+have\s+(.+)", predicate, re.IGNORECASE)
            if not_have_match:
                obj = not_have_match.group(1).strip()
                # Clean "while X do" suffix
                obj = re.sub(r',?\s*while\s+.+$', '', obj).strip()
                self.loom.add_fact(subj, "has_not", obj)
                self.last_subject = subj
                return "Got it."

            # "have Y, while Z do not" -> contrast between has and has_not
            have_while_match = re.match(r"have\s+(.+?),\s*while\s+(.+?),\s*(?:like|such\s+as)\s+(.+?),\s*do\s+not", predicate, re.IGNORECASE)
            if have_while_match:
                obj = have_while_match.group(1).strip()
                contrast_subj = have_while_match.group(2).strip()
                contrast_examples = have_while_match.group(3).strip()

                # Positive: subject has obj
                self.loom.add_fact(subj, "has", obj)

                # Negative: contrast subject does not have obj
                self.loom.add_fact(contrast_subj, "has_not", obj)

                # Extract examples for contrast subject
                c_examples = re.split(r'\s+and\s+', contrast_examples)
                for ex in c_examples:
                    ex = ex.strip()
                    if ex:
                        self.loom.add_fact(contrast_subj, "example", ex)
                        self.loom.add_fact(ex, "is", contrast_subj)

                self.last_subject = contrast_subj
                return "Got it."

            # "have Y" -> has: Y (simple case)
            have_match = re.match(r"have\s+(.+)", predicate, re.IGNORECASE)
            if have_match:
                obj = have_match.group(1).strip()
                # Clean "while X" suffix if present
                obj = re.sub(r',?\s*while\s+.+$', '', obj).strip()
                self.loom.add_fact(subj, "has", obj)
                self.last_subject = subj
                return "Got it."

        # Pattern 8a: "X give birth to Y and feed them Z" (reproduction with feeding - no adverb)
        # e.g., "Mammals give birth to live young and feed them milk"
        match = re.match(r"(.+?)\s+give\s+birth\s+to\s+(.+?)\s+and\s+feed\s+(?:them|their\s+young)\s+(.+)", t, re.IGNORECASE)
        if match:
            subj = match.group(1).strip()
            offspring = match.group(2).strip()
            food = match.group(3).strip()
            food = re.sub(r',.*$', '', food).strip()
            self.loom.add_fact(subj, "gives_birth_to", offspring)
            self.loom.add_fact(subj, "reproduction", "live birth")
            self.loom.add_fact(subj, "feeds_young_with", food)
            self.last_subject = subj
            return "Got it."

        # Pattern 8b: "X and Y lay eggs" (compound subject with lay eggs)
        # e.g., "Birds and most reptiles lay eggs"
        match = re.match(r"(.+?)\s+and\s+(?:most\s+)?(.+?)\s+lay\s+eggs?", t, re.IGNORECASE)
        if match:
            subj1 = match.group(1).strip()
            subj2 = match.group(2).strip()
            for subj in [subj1, subj2]:
                self.loom.add_fact(subj, "reproduction", "eggs")
                self.loom.add_fact(subj, "lays", "eggs")
                self.loom.add_fact(subj, "produces", "eggs")
            self.last_subject = subj2
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
                self.loom.add_fact(subj, "gives_birth_to", offspring)
                self.loom.add_fact(subj, "reproduction", "live birth")
                self.loom.add_fact(subj, "feeds_young_with", food)
                self.last_subject = subj
                return "Got it."

            # "give birth to X" without feeding
            birth_match = re.match(r"give\s+birth\s+to\s+(.+?)(?:,|\s*$)", action_str, re.IGNORECASE)
            if birth_match:
                offspring = birth_match.group(1).strip()
                self.loom.add_fact(subj, "gives_birth_to", offspring)
                self.loom.add_fact(subj, "reproduction", "live birth")
                self.last_subject = subj
                return "Got it."

            # "lay eggs"
            lay_match = re.match(r"lay\s+eggs?", action_str, re.IGNORECASE)
            if lay_match:
                self.loom.add_fact(subj, "reproduction", "eggs")
                self.loom.add_fact(subj, "lays", "eggs")
                self.last_subject = subj
                return "Got it."

        # Pattern 9: "X, such as Y, can/do Z" (ability with example)
        # e.g., "Amphibians, such as frogs, can live both in water and on land"
        match = re.match(r"(.+?),\s*such\s+as\s+(.+?),\s*(?:can|do|does)\s+(.+)", t, re.IGNORECASE)
        if match:
            subj = match.group(1).strip()
            example = match.group(2).strip()
            ability = match.group(3).strip()

            self.loom.add_fact(subj, "example", example)
            self.loom.add_fact(example, "is", subj)

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
                        self.loom.add_fact(subj, "can_live_in", loc)
                self.last_subject = subj
                return "Got it."

            # Generic ability
            ability = re.sub(r'\s+and\s+often.*$', '', ability).strip()
            self.loom.add_fact(subj, "can", ability)
            self.last_subject = subj
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

            self.loom.add_fact(subj, "uses", tool)
            self.loom.add_fact(subj, "uses_to", f"{tool} to {purpose}")

            # Special handling for breathing
            if "oxygen" in purpose or "breathe" in purpose or "gills" in tool:
                self.loom.add_fact(subj, "breathes_with", tool)

            self.last_subject = subj
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
                    self._parse_definition_clause(part)
                return "Got it."

        # Pattern 12: "X also vary in Y"
        match = re.match(r"(.+?)\s+also\s+vary\s+in\s+(.+)", t, re.IGNORECASE)
        if match:
            subj = match.group(1).strip()
            aspect = match.group(2).strip()
            aspect = re.sub(r'[—–].*$', '', aspect).strip()
            self.loom.add_fact(subj, "varies_in", aspect)
            self.last_subject = subj
            return "Got it."

        # Pattern 13: "all X depend on Y"
        match = re.match(r"(?:all\s+)?(.+?)\s+depend(?:s)?\s+on\s+(.+)", t, re.IGNORECASE)
        if match:
            subj = match.group(1).strip()
            dependency = match.group(2).strip()
            dependency = re.sub(r'\s+to\s+.+$', '', dependency).strip()
            self.loom.add_fact(subj, "depends_on", dependency)
            self.last_subject = subj
            return "Got it."

        return None

    def _parse_definition_clause(self, clause: str):
        """Parse definition clauses like 'herbivores eat plants'."""
        clause = clause.strip().rstrip('.')

        # "X eat Y"
        match = re.match(r"(\w+)\s+eat(?:s)?\s+(.+)", clause, re.IGNORECASE)
        if match:
            subj = match.group(1).strip()
            obj = match.group(2).strip()
            # Clean trailing clauses
            obj = re.split(r',\s*', obj)[0].strip()
            self.loom.add_fact(subj, "eats", obj)
            self.loom.add_fact(subj, "diet_type", subj)
            return

        # "X do Y" or "X are Y"
        match = re.match(r"(\w+)\s+(?:do|are|is)\s+(.+)", clause, re.IGNORECASE)
        if match:
            subj = match.group(1).strip()
            obj = match.group(2).strip()
            self.loom.add_fact(subj, "does", obj)

    def _check_contrast_pattern(self, t: str) -> str | None:
        """
        Handle contrast patterns: "X are A, while/whereas Y are B"
        Examples:
        - "Mammals are warm-blooded and have hair, while reptiles are cold-blooded and have scales"
        - "Birds lay eggs and have feathers, whereas fish live in water and breathe through gills"
        """
        # Skip questions
        if self._is_question(t):
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
        first_parsed = self._parse_subject_predicates(first_part)
        if first_parsed:
            subj, predicates = first_parsed
            for rel, obj in predicates:
                self.loom.add_fact(subj, rel, obj)
                facts_added += 1

        # Parse remaining parts
        for part in parts:
            part = part.strip()
            if part:
                parsed = self._parse_subject_predicates(part)
                if parsed:
                    subj, predicates = parsed
                    for rel, obj in predicates:
                        self.loom.add_fact(subj, rel, obj)
                        facts_added += 1

        if facts_added > 0:
            return f"Got it, {first_part}, while {rest.split(',')[0]}."

        return None

    def _parse_subject_predicates(self, text: str) -> tuple | None:
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

    # ==================== STATEMENTS ====================

    def _check_negation(self, t: str) -> str | None:
        """Handle 'X is not Y' or 'X doesn't have Y' patterns."""
        # Don't match questions - let query handlers process them
        if self._is_question(t):
            return None

        # Don't match relative clauses like "X that cannot Y"
        # These should be handled by _check_is_statement
        if " that cannot " in t or " that can't " in t or " that can " in t:
            return None

        # "X is not Y" / "X are not Y"
        match = re.match(r"(.+?)\s+(?:is|are)\s+not\s+(.+)", t)
        if match:
            subj, obj = match.groups()
            self.loom.add_fact(subj, "is_not", obj)
            verb = "are" if is_plural(subj) else "is"
            return f"Understood, {subj} {verb} not {obj}."

        # "X doesn't/don't have Y"
        match = re.match(r"(.+?)\s+(?:doesn't|don't|does not|do not)\s+have\s+(.+)", t)
        if match:
            subj, obj = match.groups()
            self.loom.add_fact(subj, "has_not", obj)
            verb = "don't" if is_plural(subj) else "doesn't"
            return f"Noted, {subj} {verb} have {obj}."

        # "X can't/cannot Y"
        match = re.match(r"(.+?)\s+(?:can't|cannot|can not)\s+(.+)", t)
        if match:
            subj, action = match.groups()
            self.loom.add_fact(subj, "cannot", action)
            return f"Got it, {subj} cannot {action}."

        return None

    def _check_looks_pattern(self, t: str) -> str | None:
        """Handle 'X looks like Y' or 'X looks [color]' patterns."""
        if " looks " not in t:
            return None

        parts = t.split(" looks ", 1)
        if len(parts) != 2:
            return None

        subj = parts[0].strip()
        rest = parts[1].strip()

        if rest.startswith("like "):
            y = rest[5:].strip()
            self.loom.add_fact(subj, "looks_like", y)
            # Copy properties BOTH directions
            self.loom.copy_properties(subj, y)  # y -> subj
            self.loom.copy_properties(y, subj)  # subj -> y
            return f"Got it, {subj} looks like {y}."

        if rest in COLORS:
            self.loom.add_fact(subj, "color", rest)
            return f"Got it, {subj} is {rest}."

        return None

    def _check_analogy_pattern(self, t: str) -> str | None:
        """Handle 'X is/are like Y' patterns."""
        like_patterns = [" is like ", " are like "]
        for pattern in like_patterns:
            if pattern in t:
                parts = t.split(pattern, 1)
                if len(parts) == 2:
                    x, y = parts[0].strip(), parts[1].strip()
                    for prefix in ["you know ", "well ", "so ", "the ", "a ", "an "]:
                        if x.startswith(prefix):
                            x = x[len(prefix):]
                        if y.startswith(prefix):
                            y = y[len(prefix):]

                    # Handle "X color is like Y" -> copy color from X to Y
                    if x.endswith(" color"):
                        source = x[:-6].strip()  # Remove " color"
                        color = self.loom.get(source, "color")
                        if color:
                            self.loom.add_fact(y, "color", color[0])
                            return f"Got it, {y} is {color[0]} like {source}."
                        else:
                            # Still link them, color might be added later
                            self.loom.add_fact(source, "looks_like", y)
                            self.loom.copy_properties(source, y)
                            self.loom.copy_properties(y, source)
                            return f"I'll remember {source} and {y} are similar."

                    self.loom.add_fact(x, "looks_like", y)
                    # Copy properties BOTH directions for analogies
                    self.loom.copy_properties(x, y)  # y -> x
                    self.loom.copy_properties(y, x)  # x -> y
                    verb = "are" if is_plural(x) else "is"
                    return f"I see, {x} {verb} like {y}."
        return None

    def _check_same_as_pattern(self, t: str) -> str | None:
        """
        Handle 'X have same Y as Z' or 'X has the same Y as Z' patterns.
        Copies property Y from Z to X.
        Examples:
            'cats have same legs as dogs' -> cats get dogs' leg count
            'birds have the same wings as bats' -> copy wing property
        """
        # Patterns to match
        patterns = [
            " have same ", " has same ",
            " have the same ", " has the same ",
            " got same ", " got the same ",
        ]

        for pattern in patterns:
            if pattern not in t or " as " not in t:
                continue

            # Split: "cats have same legs as dogs"
            before_pattern = t.split(pattern)[0].strip()
            after_pattern = t.split(pattern)[1].strip()

            if " as " not in after_pattern:
                continue

            # Extract property and source
            prop_and_source = after_pattern.split(" as ", 1)
            if len(prop_and_source) != 2:
                continue

            prop = prop_and_source[0].strip()  # "legs"
            source = prop_and_source[1].strip()  # "dogs"
            target = before_pattern  # "cats"

            # Clean up
            for prefix in ["the ", "a ", "an "]:
                if target.startswith(prefix):
                    target = target[len(prefix):]
                if source.startswith(prefix):
                    source = source[len(prefix):]

            # Look up what source has for this property
            # Check common relations: has, color, can, is
            relations_to_check = ["has", "color", "can", "is", "needs", "eats", "lives_in"]

            copied = False
            for rel in relations_to_check:
                source_values = self.loom.get(source, rel) or []
                for val in source_values:
                    # Check if this value relates to the property
                    if prop in val or val in prop or prop == rel:
                        self.loom.add_fact(target, rel, val)
                        copied = True
                        self.last_subject = target
                        self.loom.context.update(subject=target, relation=rel, obj=val)
                        # Format response with proper grammar
                        val_display = val.replace("_", " ")
                        if rel == "has":
                            verb = "have" if is_plural(target) else "has"
                            return f"Got it, {target} {verb} {val_display} (same as {source})."
                        elif rel == "can":
                            return f"Got it, {target} can {val_display} (same as {source})."
                        elif rel == "color":
                            verb = "are" if is_plural(target) else "is"
                            return f"Got it, {target} {verb} {val_display} (same as {source})."
                        else:
                            return f"Got it, {target} {rel} {val_display} (same as {source})."

            # If no specific match, just copy all properties from source to target
            if not copied:
                self.loom.copy_properties(target, source)
                self.last_subject = target
                return f"Got it, {target} is like {source}."

        return None

    def _check_relation_patterns(self, t: str) -> str | None:
        """Handle all relation patterns (has, can, lives_in, etc.)."""
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
                        self.loom.add_fact(second_subj, "can", second_action)
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
                            self.loom.add_fact(subj, verb_map[second_verb], second_obj)
                        # Truncate to just the first part
                        obj = obj[:compound_match.start()].strip()

                    # Truncate object at discourse markers
                    for marker in [", and ", ", but ", ", so ", ", because ", ", which ", ", that ", ", when "]:
                        if marker in obj:
                            obj = obj.split(marker)[0].strip()

                    # Truncate at prepositions that add extra info
                    for prep in [" from ", " to ", " for ", " with ", " on ", " at "]:
                        if prep in obj:
                            obj = obj.split(prep)[0].strip()

                    # Clean trailing "too" or similar
                    for suffix in [" too", " as well", " also", " very"]:
                        if obj.endswith(suffix):
                            obj = obj[:-len(suffix)].strip()

                    self.loom.add_fact(subj, relation, obj)

                    # Add reverse relation if defined
                    if reverse:
                        self.loom.add_fact(obj, reverse, subj)

                    # Track subject for pronoun resolution
                    self.last_subject = subj
                    self.loom.context.update(subject=subj, relation=relation, obj=obj)

                    # Natural response
                    return f"Got it, {subj} {phrase.strip()} {obj}."

        return None

    def _check_conditional_pattern(self, t: str) -> str | None:
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
                    self.loom.add_fact(x, "causes", y.strip())
                    return f"I understand, {x} leads to {y.strip()}."
        return None

    def _check_becomes_pattern(self, t: str) -> str | None:
        """Handle 'X becomes Y' patterns."""
        if " becomes " not in t:
            return None

        parts = t.split(" becomes ", 1)
        if len(parts) == 2:
            self.loom.add_fact(parts[0].strip(), "leads_to", parts[1].strip())
            return f"Got it, {parts[0].strip()} transforms into {parts[1].strip()}."
        return None

    def _check_is_statement(self, t: str) -> str | None:
        """Handle 'X is/are Y' statements, including 'X and Y are Z'."""
        verb = None
        if " is " in t:
            verb = " is "
        elif " are " in t:
            verb = " are "

        if not verb:
            return None

        parts = t.split(verb, 1)
        if len(parts) != 2:
            return None

        subj = parts[0].strip()
        obj = parts[1].strip()

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

        # Check for "that [verb] [in/on/...] X" patterns (location, possession, etc.)
        if not relative_clause_facts:
            # Match: "that live in X", "that eat X", "that have X", etc.
            rel_verb_match = re.search(r"\s+that\s+(live|lives|eat|eats|have|has|use|uses|need|needs|like|likes|want|wants)\s+(?:in\s+)?(.+)$", obj, re.IGNORECASE)
            if rel_verb_match:
                verb = rel_verb_match.group(1).lower()
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
                }
                if verb in verb_map:
                    relative_clause_facts.append((verb_map[verb], rel_obj, False))
                # Remove the relative clause from obj
                obj = obj[:rel_verb_match.start()].strip()

        # Handle compound predicates: "X are large and need Y" -> two facts
        # Check if " and " is followed by a verb (compound predicate)
        compound_predicate_match = re.search(r"\s+and\s+(need|have|can|eat|use|live|like|want|require|are|is|do|make|get|become)s?\s+(.+)$", obj, re.IGNORECASE)
        compound_second_fact = None
        if compound_predicate_match:
            verb = compound_predicate_match.group(1).lower()
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
                "make": "causes", "makes": "causes",
                "get": "has", "gets": "has",
                "become": "becomes", "becomes": "becomes",
            }
            if verb in verb_to_relation:
                compound_second_fact = (verb_to_relation[verb], second_obj)
            # Truncate obj to the part before " and verb"
            obj = obj[:compound_predicate_match.start()].strip()

        # Extract causal consequences before truncation: ", so they/X have Y" -> has = Y
        # Use \w+ to match any subject (in case pronoun was resolved to a name)
        causal_consequence = None
        so_match = re.search(r",?\s+so\s+\w+\s+(have|has|can|need|needs|are|is|eat|eats|use|uses)\s+(.+)$", obj, re.IGNORECASE)
        if so_match:
            verb = so_match.group(1).lower()
            consequence_obj = so_match.group(2).strip()
            verb_map = {
                "have": "has", "has": "has",
                "can": "can",
                "need": "needs", "needs": "needs",
                "are": "is", "is": "is",
                "eat": "eats", "eats": "eats",
                "use": "uses", "uses": "uses",
            }
            if verb in verb_map:
                causal_consequence = (verb_map[verb], consequence_obj)
            obj = obj[:so_match.start()].strip()

        # Handle "X with Y" patterns: "mammals with long trunks" -> is: mammals, has: long_trunks
        with_possession = None
        with_match = re.search(r"\s+with\s+(.+)$", obj, re.IGNORECASE)
        if with_match:
            with_obj = with_match.group(1).strip()
            with_possession = with_obj
            obj = obj[:with_match.start()].strip()

        # Truncate object at discourse markers (but, because, so, etc.)
        for marker in [", but ", " but ", ", because ", " because ", ", so ", " so ",
                       ", and ", ", while ", " while ", ", when ", " when ",
                       ", which ", " which "]:
            if marker in obj:
                obj = obj.split(marker)[0].strip()

        # Also truncate at certain words that indicate extra info
        for word in [" than ", " like ", " unlike ", " from ", " to ", " for "]:
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
                self.loom.add_fact(s, "color", obj)
            elif quantifier:
                # Quantified statements: "some cats are friendly" -> cats can_be friendly
                self.loom.add_fact(s, "can_be", obj)
            else:
                # Add category fact (the noun part) - only if we have actual nouns
                if main_category:
                    self.loom.add_fact(s, "is", main_category)

                # Add property facts for each adjective
                for adj in adjectives:
                    self.loom.add_fact(s, "has_property", adj)

            # Handle relative clause facts: "X are Y that can/cannot Z" or "X are Y that live in Z"
            for rel_relation, rel_value, _ in relative_clause_facts:
                self.loom.add_fact(s, rel_relation, rel_value)

            # Handle compound predicate: "X are large and need Y"
            if compound_second_fact:
                relation, second_obj = compound_second_fact
                self.loom.add_fact(s, relation, second_obj)

            # Handle causal consequence: "X are Y, so they have Z"
            if causal_consequence:
                relation, consequence_obj = causal_consequence
                self.loom.add_fact(s, relation, consequence_obj)

            # Handle "with X" possession: "mammals with long trunks" -> has: long_trunks
            if with_possession:
                self.loom.add_fact(s, "has", with_possession)

        # Track last subject for pronoun resolution
        self.last_subject = subjects[-1] if subjects else subj
        self.loom.context.update(subject=self.last_subject, relation="is", obj=obj)

        return "Got it."

    def _check_discourse_patterns(self, t: str) -> str | None:
        """
        Handle natural speech patterns using discourse markers.
        Humans use words like 'also', 'because', 'similarly' to signal relationships.
        """
        # Skip questions - they should be handled by query methods
        question_words = ["what", "where", "who", "when", "why", "how", "can", "does", "do", "is", "are"]
        first_word = t.split()[0] if t.split() else ""
        if first_word in question_words:
            return None

        markers = find_discourse_markers(t)
        if not markers:
            return None

        for marker_info in markers:
            marker = marker_info["marker"]
            category = marker_info["category"]
            pos = marker_info["start"]

            before = t[:pos].strip()
            after = t[marker_info["end"]:].strip()

            # Clean common prefixes
            for prefix in ["and ", "but ", "well ", "oh ", "so ", "yeah "]:
                if before.startswith(prefix):
                    before = before[len(prefix):]
                if after.startswith(prefix):
                    after = after[len(prefix):]

            if not after:
                continue

            # Handle ADDITIVE markers (also, too, as well, in addition)
            if category == "additive":
                # "birds also have feet" -> birds has feet
                # "cats can also climb" -> cats can climb
                # "they can also do tricks" -> [last_subject] can do tricks

                # Get subject from before the marker
                subj = before.strip()
                rest = after.strip()

                # Clean subject
                for suffix in [" also", " too", " as well", " can", " could"]:
                    if subj.endswith(suffix):
                        subj = subj[:-len(suffix)].strip()
                for prefix in ["the ", "a ", "an "]:
                    if subj.startswith(prefix):
                        subj = subj[len(prefix):]

                # Handle "can also do X" pattern
                if rest.startswith("do "):
                    obj = rest[3:].strip()  # Remove "do "
                    if subj and obj:
                        self.loom.add_fact(subj, "can", obj)
                        self.last_subject = subj
                        return f"Got it, {subj} can {obj}."

                # Find the verb in rest and extract relation + object
                verbs_map = {
                    "have": "has", "has": "has", "had": "has",
                    "can": "can", "could": "can",
                    "eat": "eats", "eats": "eats",
                    "like": "likes", "likes": "likes",
                    "need": "needs", "needs": "needs",
                    "is": "is", "are": "is",
                }

                # Action verbs that mean "can [verb]"
                action_verbs = ["see", "climb", "jump", "swim", "fly", "run", "walk", "talk"]

                for verb, relation in verbs_map.items():
                    if rest.startswith(f"{verb} ") or rest == verb:
                        obj = rest[len(verb):].strip() if rest.startswith(f"{verb} ") else ""
                        if not obj:
                            obj = verb
                        if subj and obj:
                            self.loom.add_fact(subj, relation, obj)
                            self.last_subject = subj
                            return f"Got it, {subj} {relation} {obj}."
                        break

                # Check for action verbs
                for verb in action_verbs:
                    if rest.startswith(verb):
                        obj = rest
                        if subj:
                            self.loom.add_fact(subj, "can", obj)
                            self.last_subject = subj
                            return f"Got it, {subj} can {obj}."
                        break

            # Handle CAUSAL markers (because, so, therefore)
            elif category == "causal":
                if marker in ["because", "since", "due to", "owing to"]:
                    # "X because Y" -> Y causes X
                    # Clean "of" from "because of"
                    cause = after.strip()
                    if cause.startswith("of "):
                        cause = cause[3:].strip()
                    effect = before.strip()
                    # Clean verb from effect
                    for v in [" happens", " occurs", " is", " are"]:
                        if effect.endswith(v):
                            effect = effect[:-len(v)].strip()
                    if cause and effect:
                        self.loom.add_fact(cause, "causes", effect)
                        return f"I see, {cause} causes {effect}."
                elif marker in ["so", "therefore", "thus", "hence", "as a result"]:
                    # "X so Y" -> X causes Y
                    if before and after:
                        self.loom.add_fact(before, "causes", after)
                        return f"I understand, {before} leads to {after}."

            # Handle SIMILARITY markers (like, similarly, same as)
            elif category == "similarity":
                if before and after:
                    # Clean up
                    for prefix in ["the ", "a ", "an "]:
                        if before.startswith(prefix):
                            before = before[len(prefix):]
                        if after.startswith(prefix):
                            after = after[len(prefix):]
                    self.loom.add_fact(before, "is_like", after)
                    self.loom.copy_properties(before, after)
                    self.loom.copy_properties(after, before)
                    return f"Got it, {before} is similar to {after}."

            # Handle CONTRASTIVE markers (but, however, unlike)
            elif category == "contrastive":
                if marker in ["unlike", "different from", "not like"]:
                    if before and after:
                        self.loom.add_fact(before, "differs_from", after)
                        return f"Noted, {before} is different from {after}."

            # Handle EXAMPLE markers (for example, such as)
            elif category == "example":
                if before and after:
                    # "mammals such as dogs" -> dogs is mammals
                    self.loom.add_fact(after, "is", before)
                    return f"Got it, {after} is an example of {before}."

        return None

    def _is_question(self, t: str) -> bool:
        """Check if text is a question (should not be stored as fact)."""
        question_starters = [
            "what", "where", "who", "when", "why", "how", "which",
            "can", "could", "does", "do", "is", "are", "was", "were",
            "will", "would", "should", "have", "has", "did", "in"
        ]
        first_word = t.split()[0] if t.split() else ""
        # Check for "?" or question starter words
        if "?" in t:
            return True
        if first_word in question_starters:
            return True
        # Check for "in what" style questions
        if t.startswith("in what") or t.startswith("in which"):
            return True
        return False

    def _learn_from_conversation(self, t: str) -> str | None:
        """
        Fallback: Try to extract any knowledge from natural conversation.
        Uses flexible pattern matching to learn from how people naturally talk.
        Based on Hebbian learning: concepts mentioned together form connections.
        """
        # NEVER store questions as facts
        if self._is_question(t):
            return None

        # Try to find any subject-verb-object pattern
        words = t.split()
        if len(words) < 3:
            return None

        # Common conversational verbs to look for
        verbs = [
            "is", "are", "was", "were", "has", "have", "had",
            "likes", "like", "wants", "want", "needs", "need",
            "eats", "eat", "lives", "live", "uses", "use",
            "makes", "make", "does", "do", "can", "will",
            "loves", "love", "hates", "hate", "knows", "know"
        ]

        for i, word in enumerate(words):
            if word in verbs and i > 0:
                subj = " ".join(words[:i])
                obj = " ".join(words[i+1:])

                if subj and obj:
                    # Map verb to relation
                    relation = word
                    if word in ["is", "are", "was", "were"]:
                        relation = "is"
                    elif word in ["has", "have", "had"]:
                        relation = "has"
                    elif word in ["likes", "like"]:
                        relation = "likes"
                    elif word in ["wants", "want"]:
                        relation = "wants"
                    elif word in ["needs", "need"]:
                        relation = "needs"
                    elif word in ["eats", "eat"]:
                        relation = "eats"
                    elif word in ["lives", "live"]:
                        relation = "lives_in"
                    elif word in ["uses", "use"]:
                        relation = "uses"
                    elif word in ["makes", "make"]:
                        relation = "causes"
                    elif word in ["loves", "love"]:
                        relation = "loves"
                    elif word in ["hates", "hate"]:
                        relation = "hates"
                    elif word in ["knows", "know"]:
                        relation = "knows"

                    # Clean up subject - remove discourse markers and articles
                    for prefix in ["the ", "a ", "an ", "i think ", "i know ", "did you know "]:
                        if subj.lower().startswith(prefix):
                            subj = subj[len(prefix):]
                    for suffix in [" also", " too", " as well"]:
                        if subj.lower().endswith(suffix):
                            subj = subj[:-len(suffix)].strip()

                    if subj and obj:
                        self.loom.add_fact(subj, relation, obj)
                        return f"Interesting, I'll remember that about {subj}."

        return None
