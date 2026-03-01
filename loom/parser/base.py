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

# Import constants
from .constants import (
    CORRECTION_WORDS, REFINEMENT_WORDS, PROCEDURAL_START, PROCEDURAL_SEQUENCE,
    COLORS, RELATION_PATTERNS, QUESTION_PATTERNS
)


class Parser:
    """Parses natural language input into knowledge threads."""

    def __init__(self, loom):
        self.loom = loom
        self.last_subject = None  # Track for pronoun resolution
        self.procedure_buffer = []  # Buffer for multi-step procedures
        self.current_procedure = None  # Name of procedure being defined

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

    def _check_made_of_query(self, t: str) -> str | None:
        from .queries import _check_made_of_query
        return _check_made_of_query(self, t)

    def _check_part_of_query(self, t: str) -> str | None:
        from .queries import _check_part_of_query
        return _check_part_of_query(self, t)

    def _check_what_does_query(self, t: str) -> str | None:
        from .queries import _check_what_does_query
        return _check_what_does_query(self, t)

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

    def _check_discourse_patterns(self, t: str) -> str | None:
        from .patterns import _check_discourse_patterns
        return _check_discourse_patterns(self, t)

    def _learn_from_conversation(self, t: str) -> str | None:
        from .patterns import _learn_from_conversation
        return _learn_from_conversation(self, t)
