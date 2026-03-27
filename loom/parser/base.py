"""
Base Parser class for Loom.
Handles natural language input and extracts structured knowledge threads.

This module contains the core Parser class with:
- Initialization and main parsing logic
- Helper methods (_try_get, _find_entity, _is_question, _maybe_ask_clarification)
- The parse() method that coordinates all pattern checks
"""

import re
from ..normalizer import normalize, prettify, prettify_cause, prettify_effect
from ..grammar import format_what_response, is_plural, get_verb_form, pluralize, format_list, is_adjective
from ..context_detection import detect_context, detect_temporal, detect_scope

# Import constants
from .constants import (
    CORRECTION_WORDS, REFINEMENT_WORDS, PROCEDURAL_START, PROCEDURAL_SEQUENCE,
    COLORS, RELATION_PATTERNS, QUESTION_PATTERNS
)


from ..simplifier import SentenceSimplifier
from ..advanced_simplifier import AdvancedSimplifier


class Parser:
    """Parses natural language input into knowledge threads."""

    def __init__(self, loom):
        self.loom = loom
        self.last_subject = None  # Track for pronoun resolution
        self.procedure_buffer = []  # Buffer for multi-step procedures
        self.current_procedure = None  # Name of procedure being defined
        self._response_count = 0  # Track responses for curiosity timing
        self.curiosity_frequency = 5  # Show curiosity question every N responses
        self.simplifier = SentenceSimplifier()  # For basic simplification
        self.advanced_simplifier = AdvancedSimplifier()  # For complex sentences
        self._current_context = None  # Context for current input
        self._current_properties = None  # Properties for current input

    def _detect_context_and_properties(self, text: str) -> tuple:
        """
        Detect context and properties from the input text.

        Returns:
            (context: str, properties: dict)
        """
        ctx = detect_context(text)
        props = {
            "temporal": detect_temporal(text),
            "scope": detect_scope(text),
            "source_type": "user"
        }
        return ctx, props

    def add_fact_with_context(self, subject: str, relation: str, obj: str,
                               text: str = None, confidence: str = None):
        """
        Add a fact with automatically detected context and properties.

        Args:
            subject: The subject of the fact
            relation: The relation type
            obj: The object of the fact
            text: Original text for context detection (optional)
            confidence: Confidence level (optional)
        """
        ctx = None
        props = None

        if text:
            ctx, props = self._detect_context_and_properties(text)

        self.loom.add_fact(subject, relation, obj,
                          confidence=confidence,
                          context=ctx, properties=props)

    def _try_get(self, subject: str, relation: str) -> list:
        """Try to get facts, attempting both singular and plural forms."""
        from ..grammar import singularize, pluralize

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
        from ..grammar import singularize, pluralize

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

    def _maybe_ask_clarification(self, t: str) -> str:
        """
        If we couldn't understand, maybe ask for clarification.
        Also creates curiosity nodes for unknown concepts.
        """
        words = t.split()

        # If it's a question we couldn't answer, create curiosity about the subject
        if self._is_question(t):
            # Try to extract what they're asking about
            unknown_subject = self._extract_question_subject(t)
            if unknown_subject and hasattr(self.loom, 'curiosity_nodes'):
                # Check if we know about this subject
                entity = self._find_entity(unknown_subject)
                if not entity:
                    # Create curiosity node for unknown concept
                    self.loom.curiosity_nodes.create_node(
                        unknown_subject,
                        context=f"User asked: {t}"
                    )
                    # Try to explore and generate hypotheses
                    self.loom.curiosity_nodes.explore_node(unknown_subject)
                    hypotheses = self.loom.curiosity_nodes.generate_hypotheses(unknown_subject)

                    if hypotheses:
                        # Return best guess
                        best = hypotheses[0]
                        return (f"I don't know about '{unknown_subject}' yet, "
                                f"but based on similar concepts, it might {best['relation']} {best['object']}. "
                                f"Can you tell me more?")
                    else:
                        return f"I don't know about '{unknown_subject}'. Can you tell me about it?"

            return f"I don't have enough information to answer that question."

        # Don't ask too often - only for certain patterns
        if len(words) < 2:
            return "I'm listening. Tell me more."

        # If there's a subject but unclear relation
        if len(words) >= 2 and len(words) <= 4:
            potential_subject = words[0]

            # Check if we know about this subject
            entity = self._find_entity(potential_subject)
            if not entity and hasattr(self.loom, 'curiosity_nodes'):
                # Create curiosity node for unknown concept
                self.loom.curiosity_nodes.create_node(
                    potential_subject,
                    context=f"User mentioned: {t}"
                )

            self.loom.context.set_clarification(
                f"What about {potential_subject}?",
                potential_subject
            )
            return f"I heard '{t}'. What would you like to tell me about {potential_subject}?"

        return "I'm listening. Tell me more, and I'll try to connect the threads."

    def _extract_question_subject(self, t: str) -> str | None:
        """Extract the main subject from a question."""
        import re

        # Common question patterns
        patterns = [
            r"what (?:is|are) (\w+)",
            r"what do (\w+) (?:eat|have|need|do)",
            r"where do (\w+) live",
            r"can (\w+) (\w+)",
            r"do (\w+) have",
            r"how do (\w+)",
            r"tell me about (\w+)",
            r"what about (\w+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, t, re.IGNORECASE)
            if match:
                subject = match.group(1).lower().strip()
                # Filter out common words that aren't subjects
                if subject not in ["the", "a", "an", "some", "any", "all", "you", "i", "we"]:
                    return subject

        return None

    def _maybe_add_curiosity(self, response: str) -> str:
        """
        Optionally append a curiosity question to the response.
        Currently disabled - answers should be direct without interruptions.
        Curiosity questions can still be accessed via get_curiosity_prompt().
        """
        # Disabled: return response directly without adding curiosity prompts
        return response

    def get_curiosity_prompt(self) -> str | None:
        """
        Get a standalone curiosity prompt without marking it asked.
        Useful for CLI prompts or explicit question requests.
        """
        if not hasattr(self.loom, 'curiosity'):
            return None

        question = self.loom.curiosity.get_next_question()
        if question:
            return self.loom.curiosity.format_question_prompt(question)
        return None

    def _try_simplify_and_process(self, text: str) -> str | None:
        """
        Try to simplify a complex sentence and process each part.
        Returns combined response or None if simplification didn't help.
        """
        # Use AdvancedSimplifier for better handling of "including" and other patterns
        simplified = self.advanced_simplifier.simplify(text.strip().rstrip("?."))

        # Only use if we got multiple simpler statements
        if len(simplified) <= 1:
            return None

        responses = []
        for stmt in simplified:
            # Process each simplified statement
            response = self._parse_single(stmt)
            if response and "I'm listening" not in response:
                # Extract just the confirmation part
                if "Got it" in response:
                    responses.append(stmt)

        if responses:
            return f"Got it: {'; '.join(responses)}."

        return None

    def _parse_single(self, t: str) -> str | None:
        """Parse a single simple statement. Used by both parse() and _try_simplify_and_process()."""
        # Run through all pattern checks
        checks = [
            self._check_informational_pattern,  # Complex sentences with pronouns, including, etc.
            self._check_negation,
            self._check_relation_patterns,
            self._check_is_statement,
        ]

        for check in checks:
            result = check(t)
            if result:
                return result

        return None

    def parse(self, text: str) -> str:
        """Parse input text and update knowledge. Returns natural language response."""
        original = text
        t = text.lower().strip().rstrip("?.")

        # Detect and set context for this input (used by add_fact)
        ctx, props = self._detect_context_and_properties(original)
        self.loom._input_context = ctx
        self.loom._input_properties = props

        # Check for if-then rules FIRST (before any preprocessing)
        if t.startswith('if ') and ' then ' in t:
            result = self._check_if_then_rule(t)
            if result:
                return self._maybe_add_curiosity(result)

        # Update context mode
        self.loom.context.mode = self.loom.context.detect_mode(text)

        # Resolve pronouns EARLY - before simplifier runs
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

        # Strip leading discourse connectors (but, however, also, etc.)
        # These come from chunking "X but Y" into separate chunks
        discourse_starters = [
            'but ', 'however ', 'although ', 'though ', 'yet ',
            'also ', 'additionally ', 'furthermore ', 'moreover ',
            'nevertheless ', 'nonetheless ', 'instead ', 'rather ',
            'therefore ', 'thus ', 'hence ', 'so ', 'consequently ',
            'meanwhile ', 'otherwise ', 'similarly ', 'likewise ',
            'in contrast ', 'on the other hand ', 'in addition ',
        ]
        for starter in discourse_starters:
            if t.startswith(starter):
                t = t[len(starter):].strip()
                break

        # Try simplification for complex statements (not questions)
        # Now uses preprocessed text with pronouns resolved and discourse markers stripped
        # BUT skip simplification for sentences with special patterns that should NOT be split
        special_patterns = [
            " threatened by ", " protected by ", " caused by ", " surrounded by ",
            " eaten by ", " used by ", " found by ", " made by ", " covered by ",
            " food for ", " home to ", " habitat for ", " shelter for ",
            " lay eggs on ", " lays eggs on ", " lay eggs in ", " lays eggs in ",
            " protect ", " protects ", " from predators", " from enemies",
        ]
        has_special_pattern = any(pattern in t.lower() for pattern in special_patterns)

        # Also skip simplification for list subject patterns ("X, Y, and Z are W")
        # These should be handled by _check_list_learning instead
        list_subject_match = re.match(r'^[^,]+,\s*[^,]+,?\s+and\s+\w+\s+(are|is)\s+', t, re.IGNORECASE)
        if list_subject_match:
            has_special_pattern = True

        if not self._is_question(t) and (',' in t or ' and ' in t) and not has_special_pattern:
            simplified_response = self._try_simplify_and_process(t)
            if simplified_response:
                return self._maybe_add_curiosity(simplified_response)

        # Check patterns in priority order
        checks = [
            self._check_clarification_response,  # Handle pending clarifications
            self._check_correction,              # "no, that's wrong"
            self._check_refinement,              # "only when...", "except..."
            self._check_procedural,              # "first...", "then..."
            self._check_however_pattern,         # "However, X" - early to avoid negation match
            self._check_because_pattern,         # "Because X, Y" - early for causal sentences
            self._check_if_then_rule,            # "if X then Y" - explicit rule learning
            self._check_informational_pattern,   # Complex encyclopedic sentences - early!
            self._check_contrast_pattern,        # "X are A, while Y are B" - early!
            self._check_name_query,
            self._check_self_identity_query,     # "what are you?" - self-identity query
            self._check_negation,
            self._check_color_query,
            self._check_where_lay_eggs_query,    # "where do X lay eggs?" - BEFORE where_query!
            self._check_where_query,
            self._check_what_lives_query,
            self._check_who_query,
            self._check_how_many_query,
            self._check_made_of_query,
            self._check_part_of_query,
            self._check_what_has_query,
            self._check_what_does_query,
            self._check_what_verb_query,         # "what do X drink/eat/need?" queries
            self._check_what_did_query,          # "what did X build/create?" - past tense
            self._check_what_do_generic_query,   # "what do X do?" - generic action lookup
            self._check_what_has_reverse_query,  # "what has X?" - reverse lookup
            self._check_what_eats_reverse_query, # "what eats X?" - reverse lookup
            self._check_what_detect_query,       # "what can X detect?" - BEFORE what_can_reverse!
            self._check_what_regenerate_query,   # "what can X regenerate?" - BEFORE what_can_reverse!
            self._check_what_can_reverse_query,  # "what can X?" - reverse lookup
            self._check_what_is_reverse_query,   # "what is a X?" - find instances
            self._check_examples_query,          # "examples of X" - find instances
            self._check_what_needs_reverse_query, # "what needs X?" - reverse lookup
            self._check_what_verb_reverse_query, # "what provides/powers/pulls X?" - reverse lookup
            self._check_found_in_query,          # "what X can Y be found in?" - BEFORE can_query!
            self._check_can_query,
            self._check_are_is_query,            # "are X Y?" / "is X Y?"
            self._check_why_query,
            self._check_what_causes_query,       # "what causes X?"
            self._check_effect_query,
            self._check_lay_eggs_query,          # "which animals lay eggs?" - BEFORE which_query!
            self._check_food_for_query,          # "what is food for X?"
            self._check_protects_query,          # "what protects X?"
            self._check_threatened_by_query,     # "what threatens X?"
            self._check_how_communicate_query,   # "how do X communicate?" - BEFORE how_query!
            self._check_how_long_query,          # "how long can X grow?" - BEFORE how_query!
            self._check_temporal_query,          # "what do X do in winter?" - temporal queries
            self._check_currently_query,         # "what is X currently?" - current state queries
            self._check_what_provide_query,      # "what do X provide?"
            self._check_how_many_query,          # "how many X do Y have?" - BEFORE how_query!
            self._check_how_tall_query,          # "how tall is/are X?" - BEFORE how_query!
            self._check_related_to_query,        # "what are X related to?"
            self._check_immune_to_query,         # "what are X immune to?"
            self._check_superlative_reverse_query, # "what are the largest X?" reverse lookup
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
            self._check_chit_chat,           # "Hello", "Thanks" -> conversational responses
            self._check_first_person_statement,  # "I live in X" -> user facts
            self._check_looks_pattern,
            self._check_analogy_pattern,
            self._check_same_as_pattern,
            self._check_list_learning,       # "X, Y, and Z are W" -> multiple relations - BEFORE is_statement!
            self._check_relation_patterns,
            self._check_conditional_pattern,
            self._check_becomes_pattern,
            self._check_is_statement,
            self._check_implicit_continuation,  # "Very X." -> last_subject is X
            self._check_pronoun_reference,   # "They are X" -> resolve pronoun
            self._check_discourse_patterns,  # Natural speech patterns
            self._learn_from_conversation,   # Fallback: try to learn something
        ]

        try:
            for check in checks:
                result = check(t)
                if result:
                    # Optionally add curiosity question to response
                    return self._maybe_add_curiosity(result)

            # If nothing matched, maybe ask for clarification
            return self._maybe_add_curiosity(self._maybe_ask_clarification(t))
        finally:
            # Clear input context after processing
            self.loom._input_context = None
            self.loom._input_properties = None

    # Import handler methods from other modules
    # These are bound to the class in __init__.py

    # Handlers (from handlers.py)
    def _check_clarification_response(self, t: str) -> str | None:
        from .handlers import _check_clarification_response
        return _check_clarification_response(self, t)

    def _check_correction(self, t: str) -> str | None:
        from .handlers import _check_correction
        return _check_correction(self, t)

    def _check_refinement(self, t: str) -> str | None:
        from .handlers import _check_refinement
        return _check_refinement(self, t)

    def _check_procedural(self, t: str) -> str | None:
        from .handlers import _check_procedural
        return _check_procedural(self, t)

    def _parse_procedure_steps(self, text: str) -> list:
        from .handlers import _parse_procedure_steps
        return _parse_procedure_steps(self, text)

    def _check_however_pattern(self, t: str) -> str | None:
        from .handlers import _check_however_pattern
        return _check_however_pattern(self, t)

    def _check_because_pattern(self, t: str) -> str | None:
        from .handlers import _check_because_pattern
        return _check_because_pattern(self, t)

    # Queries (from queries.py)
    def _check_name_query(self, t: str) -> str | None:
        from .queries import _check_name_query
        return _check_name_query(self, t)

    def _check_self_identity_query(self, t: str) -> str | None:
        from .queries import _check_self_identity_query
        return _check_self_identity_query(self, t)

    def _check_color_query(self, t: str) -> str | None:
        from .queries import _check_color_query
        return _check_color_query(self, t)

    def _check_where_query(self, t: str) -> str | None:
        from .queries import _check_where_query
        return _check_where_query(self, t)

    def _check_what_lives_query(self, t: str) -> str | None:
        from .queries import _check_what_lives_query
        return _check_what_lives_query(self, t)

    def _check_who_query(self, t: str) -> str | None:
        from .queries import _check_who_query
        return _check_who_query(self, t)

    def _check_what_has_query(self, t: str) -> str | None:
        from .queries import _check_what_has_query
        return _check_what_has_query(self, t)

    def _check_what_verb_query(self, t: str) -> str | None:
        from .queries import _check_what_verb_query
        return _check_what_verb_query(self, t)

    def _check_how_many_query(self, t: str) -> str | None:
        from .queries import _check_how_many_query
        return _check_how_many_query(self, t)

    def _check_how_tall_query(self, t: str) -> str | None:
        from .queries import _check_how_tall_query
        return _check_how_tall_query(self, t)

    def _check_made_of_query(self, t: str) -> str | None:
        from .queries import _check_made_of_query
        return _check_made_of_query(self, t)

    def _check_part_of_query(self, t: str) -> str | None:
        from .queries import _check_part_of_query
        return _check_part_of_query(self, t)

    def _check_what_does_query(self, t: str) -> str | None:
        from .queries import _check_what_does_query
        return _check_what_does_query(self, t)

    def _check_what_do_generic_query(self, t: str) -> str | None:
        from .queries import _check_what_do_generic_query
        return _check_what_do_generic_query(self, t)

    def _check_what_did_query(self, t: str) -> str | None:
        from .queries import _check_what_did_query
        return _check_what_did_query(self, t)

    # Reverse queries (find entities by properties)
    def _check_what_has_reverse_query(self, t: str) -> str | None:
        from .queries import _check_what_has_reverse_query
        return _check_what_has_reverse_query(self, t)

    def _check_what_eats_reverse_query(self, t: str) -> str | None:
        from .queries import _check_what_eats_reverse_query
        return _check_what_eats_reverse_query(self, t)

    def _check_what_can_reverse_query(self, t: str) -> str | None:
        from .queries import _check_what_can_reverse_query
        return _check_what_can_reverse_query(self, t)

    def _check_what_is_reverse_query(self, t: str) -> str | None:
        from .queries import _check_what_is_reverse_query
        return _check_what_is_reverse_query(self, t)

    def _check_examples_query(self, t: str) -> str | None:
        from .queries import _check_examples_query
        return _check_examples_query(self, t)

    def _check_what_needs_reverse_query(self, t: str) -> str | None:
        from .queries import _check_what_needs_reverse_query
        return _check_what_needs_reverse_query(self, t)

    def _check_what_verb_reverse_query(self, t: str) -> str | None:
        from .queries import _check_what_verb_reverse_query
        return _check_what_verb_reverse_query(self, t)

    def _check_can_query(self, t: str) -> str | None:
        from .queries import _check_can_query
        return _check_can_query(self, t)

    def _check_are_is_query(self, t: str) -> str | None:
        from .queries import _check_are_is_query
        return _check_are_is_query(self, t)

    def _check_why_query(self, t: str) -> str | None:
        from .queries import _check_why_query
        return _check_why_query(self, t)

    def _check_what_causes_query(self, t: str) -> str | None:
        from .queries import _check_what_causes_query
        return _check_what_causes_query(self, t)

    def _check_effect_query(self, t: str) -> str | None:
        from .queries import _check_effect_query
        return _check_effect_query(self, t)

    def _check_lay_eggs_query(self, t: str) -> str | None:
        from .queries import _check_lay_eggs_query
        return _check_lay_eggs_query(self, t)

    def _check_which_query(self, t: str) -> str | None:
        from .queries import _check_which_query
        return _check_which_query(self, t)

    def _check_difference_query(self, t: str) -> str | None:
        from .queries import _check_difference_query
        return _check_difference_query(self, t)

    def _check_food_for_query(self, t: str) -> str | None:
        from .queries import _check_food_for_query
        return _check_food_for_query(self, t)

    def _check_protects_query(self, t: str) -> str | None:
        from .queries import _check_protects_query
        return _check_protects_query(self, t)

    def _check_where_lay_eggs_query(self, t: str) -> str | None:
        from .queries import _check_where_lay_eggs_query
        return _check_where_lay_eggs_query(self, t)

    def _check_threatened_by_query(self, t: str) -> str | None:
        from .queries import _check_threatened_by_query
        return _check_threatened_by_query(self, t)

    def _check_how_communicate_query(self, t: str) -> str | None:
        from .queries import _check_how_communicate_query
        return _check_how_communicate_query(self, t)

    def _check_what_detect_query(self, t: str) -> str | None:
        from .queries import _check_what_detect_query
        return _check_what_detect_query(self, t)

    def _check_what_provide_query(self, t: str) -> str | None:
        from .queries import _check_what_provide_query
        return _check_what_provide_query(self, t)

    def _check_how_many_query(self, t: str) -> str | None:
        from .queries import _check_how_many_query
        return _check_how_many_query(self, t)

    def _check_related_to_query(self, t: str) -> str | None:
        from .queries import _check_related_to_query
        return _check_related_to_query(self, t)

    def _check_what_regenerate_query(self, t: str) -> str | None:
        from .queries import _check_what_regenerate_query
        return _check_what_regenerate_query(self, t)

    def _check_immune_to_query(self, t: str) -> str | None:
        from .queries import _check_immune_to_query
        return _check_immune_to_query(self, t)

    def _check_superlative_reverse_query(self, t: str) -> str | None:
        from .queries import _check_superlative_reverse_query
        return _check_superlative_reverse_query(self, t)

    def _check_how_long_query(self, t: str) -> str | None:
        from .queries import _check_how_long_query
        return _check_how_long_query(self, t)

    def _check_temporal_query(self, t: str) -> str | None:
        from .queries import _check_temporal_query
        return _check_temporal_query(self, t)

    def _check_currently_query(self, t: str) -> str | None:
        from .queries import _check_currently_query
        return _check_currently_query(self, t)

    def _check_reproduce_query(self, t: str) -> str | None:
        from .queries import _check_reproduce_query
        return _check_reproduce_query(self, t)

    def _check_classification_query(self, t: str) -> str | None:
        from .queries import _check_classification_query
        return _check_classification_query(self, t)

    def _check_examples_query(self, t: str) -> str | None:
        from .queries import _check_examples_query
        return _check_examples_query(self, t)

    def _check_breathing_query(self, t: str) -> str | None:
        from .queries import _check_breathing_query
        return _check_breathing_query(self, t)

    def _check_backbone_query(self, t: str) -> str | None:
        from .queries import _check_backbone_query
        return _check_backbone_query(self, t)

    def _check_feeding_query(self, t: str) -> str | None:
        from .queries import _check_feeding_query
        return _check_feeding_query(self, t)

    def _check_how_query(self, t: str) -> str | None:
        from .queries import _check_how_query
        return _check_how_query(self, t)

    def _check_found_in_query(self, t: str) -> str | None:
        from .queries import _check_found_in_query
        return _check_found_in_query(self, t)

    def _check_characteristics_query(self, t: str) -> str | None:
        from .queries import _check_characteristics_query
        return _check_characteristics_query(self, t)

    def _check_differ_query(self, t: str) -> str | None:
        from .queries import _check_differ_query
        return _check_differ_query(self, t)

    def _check_what_query(self, t: str) -> str | None:
        from .queries import _check_what_query
        return _check_what_query(self, t)

    # Informational patterns (from informational.py)
    def _check_informational_pattern(self, t: str) -> str | None:
        from .informational import _check_informational_pattern
        return _check_informational_pattern(self, t)

    def _check_contrast_pattern(self, t: str) -> str | None:
        from .informational import _check_contrast_pattern
        return _check_contrast_pattern(self, t)

    def _parse_definition_clause(self, clause: str):
        from .informational import _parse_definition_clause
        return _parse_definition_clause(self, clause)

    def _parse_subject_predicates(self, text: str) -> tuple | None:
        from .informational import _parse_subject_predicates
        return _parse_subject_predicates(self, text)

    # Other patterns (from patterns.py)
    def _check_negation(self, t: str) -> str | None:
        from .patterns import _check_negation
        return _check_negation(self, t)

    def _check_looks_pattern(self, t: str) -> str | None:
        from .patterns import _check_looks_pattern
        return _check_looks_pattern(self, t)

    def _check_analogy_pattern(self, t: str) -> str | None:
        from .patterns import _check_analogy_pattern
        return _check_analogy_pattern(self, t)

    def _check_same_as_pattern(self, t: str) -> str | None:
        from .patterns import _check_same_as_pattern
        return _check_same_as_pattern(self, t)

    def _check_relation_patterns(self, t: str) -> str | None:
        from .patterns import _check_relation_patterns
        return _check_relation_patterns(self, t)

    def _check_conditional_pattern(self, t: str) -> str | None:
        from .patterns import _check_conditional_pattern
        return _check_conditional_pattern(self, t)

    def _check_becomes_pattern(self, t: str) -> str | None:
        from .patterns import _check_becomes_pattern
        return _check_becomes_pattern(self, t)

    def _check_is_statement(self, t: str) -> str | None:
        from .patterns import _check_is_statement
        return _check_is_statement(self, t)

    def _check_list_learning(self, t: str) -> str | None:
        from .patterns import _check_list_learning
        return _check_list_learning(self, t)

    def _check_implicit_continuation(self, t: str) -> str | None:
        from .patterns import _check_implicit_continuation
        return _check_implicit_continuation(self, t)

    def _check_pronoun_reference(self, t: str) -> str | None:
        from .patterns import _check_pronoun_reference
        return _check_pronoun_reference(self, t)

    def _check_discourse_patterns(self, t: str) -> str | None:
        from .patterns import _check_discourse_patterns
        return _check_discourse_patterns(self, t)

    def _learn_from_conversation(self, t: str) -> str | None:
        from .patterns import _learn_from_conversation
        return _learn_from_conversation(self, t)

    def _check_first_person_statement(self, t: str) -> str | None:
        from .patterns import _check_first_person_statement
        return _check_first_person_statement(self, t)

    def _check_chit_chat(self, t: str) -> str | None:
        from .patterns import _check_chit_chat
        return _check_chit_chat(self, t)

    def _check_if_then_rule(self, t: str) -> str | None:
        """Handle explicit if-then rule statements."""
        import re

        # Pattern: if <conditions> then <conclusion>
        match = re.match(
            r"if\s+(.+?)\s+then\s+(.+)",
            t, re.IGNORECASE
        )

        if not match:
            return None

        # Check if we have a rule memory
        if not hasattr(self.loom, 'rule_memory') or self.loom.rule_memory is None:
            return None

        # Let the rule memory parse and learn the rule
        rule = self.loom.rule_memory.learn_from_if_then(t)

        if rule:
            from ..grammar import format_list
            premises_str = " and ".join(str(p) for p in rule.premises)
            conclusion_str = str(rule.conclusion)
            return f"Got it. I've learned a rule: if {premises_str}, then {conclusion_str}. (Rule is pending confirmation)"

        return None
