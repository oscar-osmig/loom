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
from ..structural import StructuralExtractor


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
        self.structural = StructuralExtractor()  # Structural metadata extraction
        self._current_context = None  # Context for current input
        self._current_properties = None  # Properties for current input
        self._structural_result = None  # Current structural extraction result

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

        # Apply structural confidence hint (hedging lowers confidence)
        if confidence is None and self._structural_result:
            sr = self._structural_result
            if sr.confidence == "low":
                confidence = "low"

        self.loom.add_fact(subject, relation, obj,
                          confidence=confidence,
                          context=ctx, properties=props)

    def _store_structural_extras(self):
        """Store extra facts from structural extraction (comparisons, quantities, purposes)."""
        sr = self._structural_result
        if not sr:
            return

        # Store extra facts (comparisons, purposes, superlative categories)
        for subj, rel, obj in sr.extra_facts:
            if subj and rel and obj:
                self.loom.add_fact(subj, rel, obj, confidence="high")

        # Store quantities via frame system (brain.add_fact rejects short
        # numeric objects like "4", so we route through frames directly)
        if sr.quantities and hasattr(self.loom, 'frame_manager'):
            subject = self.last_subject
            clean_words = sr.clean_text.lower().split()
            if clean_words:
                for verb_marker in ["have", "has", "had", "are", "is", "weigh", "weighs"]:
                    if verb_marker in clean_words:
                        idx = clean_words.index(verb_marker)
                        if idx > 0:
                            subject = " ".join(clean_words[:idx])
                            break
                if not subject:
                    subject = clean_words[0]
            if subject:
                from ..normalizer import normalize
                subj_n = normalize(subject)
                for q in sr.quantities:
                    unit = q["unit"]
                    number = q["number"]
                    # Store as frame quantity slot
                    self.loom.frame_manager._fill_slot(
                        subj_n, "quantities",
                        f"{unit}:{number}",
                        potential=False
                    )

        # Route hedged facts to potential tier in frame system
        if sr.confidence == "low" and hasattr(self.loom, 'frame_manager'):
            # The fact was already stored by the parser with low confidence.
            # The frame system will see the low confidence from _input_properties.
            pass

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
        """Check if text is a question or query request (should not be stored as fact)."""
        question_starters = [
            "what", "where", "who", "when", "why", "how", "which",
            "can", "could", "does", "do", "is", "are", "was", "were",
            "will", "would", "should", "have", "has", "did", "in"
        ]
        first_word = t.split()[0] if t.split() else ""
        if "?" in t:
            return True
        if first_word in question_starters:
            return True
        if t.startswith("in what") or t.startswith("in which"):
            return True
        # Query-like imperatives
        query_imperatives = [
            "tell me", "describe ", "explain ", "show me",
            "what do you know", "list ",
        ]
        for qi in query_imperatives:
            if t.startswith(qi):
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
        Surfaces high-priority questions (>= 6.0) at most once every 5 turns.
        Skips during correction/clarification mode.
        """
        self._response_count += 1

        # Don't interrupt corrections or clarifications
        if hasattr(self.loom, 'context') and self.loom.context.mode in ("clarifying", "correcting"):
            return response

        # Gate to at most once every N turns
        if self._response_count % self.curiosity_frequency != 0:
            return response

        if not hasattr(self.loom, 'curiosity'):
            return response

        question = self.loom.curiosity.get_next_question()
        if question and question.priority >= 6.0:
            self.loom.curiosity.mark_asked(question)
            prompt = self.loom.curiosity.format_question_prompt(question)
            return f"{response}\n\nBy the way, I'm curious: {prompt}"

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
            try:
                from ..composer import acknowledge_fact
                ctx = self.loom.context
                s = ctx.last_subject or ""
                r = ctx.last_relation or ""
                o = ctx.last_object or ""
                if s and r:
                    return acknowledge_fact(s, r, o, "; ".join(responses))
            except Exception:
                pass
            return f"Noted: {'; '.join(responses)}."

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
                return self._enrich_acknowledgment(result, t)

        return None

    def _enrich_acknowledgment(self, response: str, original_text: str = "") -> str:
        """Replace bland 'Got it' responses with varied, natural acknowledgments."""
        if not response:
            return response
        # Only transform responses starting with "Got it" or "Noted"
        if not (response.startswith("Got it") or response == "Got it."):
            return response

        # Extract the fact content from "Got it, X rel Y."
        content = response
        for prefix in ["Got it, ", "Got it: ", "Got it — ", "Got it. ", "Got it "]:
            if content.startswith(prefix):
                content = content[len(prefix):]
                break
        content = content.rstrip(".").strip()

        # If content is empty (bare "Got it."), use original text as content
        if not content or content == "Got it":
            content = original_text.strip().rstrip(".") if original_text else ""

        if not content:
            return response

        # Deterministic variety based on content hash
        import hashlib
        seed = int(hashlib.md5(content.encode()).hexdigest()[:8], 16)

        templates = [
            f"Noted — {content}.",
            f"I see, {content}.",
            f"Understood. {content.capitalize() if content[0].islower() else content}.",
            f"Interesting — {content}.",
            f"I'll remember that: {content}.",
            f"Good to know. {content.capitalize() if content[0].islower() else content}.",
        ]

        return templates[seed % len(templates)]

    def parse(self, text: str) -> str:
        """Parse input text and update knowledge. Returns natural language response."""
        original = text
        t = text.lower().strip().rstrip("?.")

        # Observe user input for style learning (only for statements, not questions)
        if not self._is_question(t) and hasattr(self.loom, 'style_learner'):
            try:
                self.loom.style_learner.observe(text)
            except Exception:
                pass

        # Detect and set context for this input (used by add_fact)
        ctx, props = self._detect_context_and_properties(original)
        self.loom._input_context = ctx
        self.loom._input_properties = props

        # --- Structural extraction: strip modifiers, extract metadata ---
        sr = self.structural.extract(original)
        self._structural_result = sr

        # Apply extracted metadata to input properties
        if sr.confidence:
            props["confidence_hint"] = sr.confidence
            self.loom._input_properties = props
        if sr.temporal:
            props["temporal"] = sr.temporal
            self.loom._input_properties = props
        if sr.frequency:
            props["frequency"] = sr.frequency
            self.loom._input_properties = props
        if sr.degree:
            props["degree"] = sr.degree
            self.loom._input_properties = props

        # Use cleaned text (fillers/hedging/temporal stripped)
        if sr.clean_text and sr.clean_text != original:
            t = sr.clean_text.lower().strip().rstrip("?.")

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
            self._check_describe_query,          # "tell me about X", "describe X" — composer-backed
            self._check_why_query,               # "why do/can/is X Y?" — composer-backed
            self._check_composer_query,          # Unified composer-backed query handler (replaces legacy)
            self._check_generic_query,           # Generic SVO fallback (last resort for questions)
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
            self._check_grammar_parser,      # Recursive descent parser for complex sentences
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
                    # Enrich bland acknowledgments with varied phrasing
                    result = self._enrich_acknowledgment(result, text)
                    # Store extra facts from structural extraction
                    self._store_structural_extras()
                    # Optionally add curiosity question to response
                    return self._maybe_add_curiosity(result)

            # Even if no pattern matched, store structural extras (purpose, comparisons)
            self._store_structural_extras()

            # If nothing matched, maybe ask for clarification
            return self._maybe_add_curiosity(self._maybe_ask_clarification(t))
        finally:
            # Clear input context after processing
            self.loom._input_context = None
            self.loom._input_properties = None
            self._structural_result = None

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

    def _check_describe_query(self, t: str) -> str | None:
        """Handle 'tell me about X', 'describe X', 'what do you know about X'.
        Also handles 'tell me more' (continuation on current topic) and
        'tell me more about X'."""
        import re
        from ..composer import gather_facts, compose_response

        # Continuation: "tell me more" with no explicit subject → use current topic
        continuation = re.match(
            r"(?:tell\s+me\s+more|more\s+(?:please|info|details)?|continue|go\s+on|keep\s+going)\s*$",
            t, re.IGNORECASE
        )
        if continuation:
            topic = self.loom.context.current_topic or self.loom.context.last_subject or self.last_subject
            if topic:
                try:
                    facts = gather_facts(self.loom, topic)
                    if facts["direct"] or facts["inherited"]:
                        result = compose_response(self.loom, "describe", topic, facts=facts)
                        if result:
                            self.last_subject = topic
                            self.loom.context.update(subject=topic, relation="is", obj=None)
                            return result
                except Exception:
                    pass
                return f"I'd tell you more about {topic.replace('_', ' ')}, but I don't have additional details yet."
            return "What would you like to know more about?"

        match = re.match(
            r"(?:tell\s+me\s+(?:more\s+)?(?:about|facts\s+(?:about|on))"
            r"|tell\s+me\s+(?:everything|all)\s+(?:about|on)"
            r"|describe|what\s+do\s+you\s+know\s+about"
            r"|what\s+about|explain|show\s+me\s+(?:about)?"
            r"|tell\s+me\s+about)\s+(.+)",
            t, re.IGNORECASE
        )
        if not match:
            return None
        concept = match.group(1).strip().rstrip("?.").strip()
        if concept.lower() in ("you", "yourself", "loom"):
            return None  # Let self-identity handler deal with this
        if not concept or len(concept) < 2:
            return None
        try:
            facts = gather_facts(self.loom, concept)
            if facts["direct"] or facts["inherited"]:
                result = compose_response(self.loom, "describe", concept, facts=facts)
                if result:
                    # Update context so follow-up pronouns resolve correctly
                    resolved = facts.get("concept") or concept
                    self.last_subject = resolved
                    self.loom.context.update(subject=resolved, relation="is", obj=None)
                    return result
        except Exception:
            pass
        # Concept not found — give a helpful response
        display = concept.replace("_", " ")
        return f"I don't know about {display} yet. Teach me by telling me facts about it!"

    def _check_why_query(self, t: str) -> str | None:
        """Handle 'why' questions using reasoning chain tracer."""
        import re
        from ..composer import gather_facts, compose_response
        match = re.match(
            r"why\s+(?:do|does|can|is|are)\s+(.+?)\s+(\w+)\s+(.+)",
            t, re.IGNORECASE
        )
        if not match:
            match = re.match(r"why\s+(?:do|does|can|is|are)\s+(.+)", t, re.IGNORECASE)
            if match:
                concept = match.group(1).strip().rstrip("?.")
                try:
                    return compose_response(self.loom, "why", concept)
                except Exception:
                    pass
            return None
        subj, verb, obj = match.group(1).strip(), match.group(2).strip(), match.group(3).strip().rstrip("?.")
        try:
            return compose_response(self.loom, "why", subj, relation=verb, target=obj)
        except Exception:
            pass
        return None

    def _check_composer_query(self, t: str) -> str | None:
        """
        Unified composer-backed query handler. Routes all major question types
        through the composer for consistent, high-quality responses.
        Replaces the scattered legacy handlers for what/where/can/has queries.
        """
        if not self._is_question(t):
            return None

        import re
        from ..composer import gather_facts, compose_response, _resolve_concept
        from ..normalizer import normalize

        # Strip question marks and trailing punctuation
        q = t.lower().strip().rstrip("?.!")

        # Helper: strip articles and common prefixes from a subject
        def clean_subject(s):
            for prefix in ["the ", "a ", "an ", "some ", "my ", "our "]:
                if s.startswith(prefix):
                    s = s[len(prefix):]
            return s.strip()

        # ── "what is X?" / "what are X?" ──
        m = re.match(r"what\s+(?:is|are)\s+(.+)", q)
        if m:
            concept = clean_subject(m.group(1).strip())
            try:
                facts = gather_facts(self.loom, concept)
                if facts["direct"] or facts["inherited"]:
                    result = compose_response(self.loom, "what_is", concept, facts=facts)
                    if result:
                        self.last_subject = facts["concept"]
                        self.loom.context.update(subject=facts["concept"])
                        return result
            except Exception:
                pass

        # ── "where do/does/can X live/be found?" ──
        m = re.match(r"where\s+(?:do|does|can|is|are)\s+(.+?)\s+(?:live|lives|found|be found|located|stay|come from)", q)
        if not m:
            # Fallback: "where is X?" / "where are X?"
            m = re.match(r"where\s+(?:is|are|do|does|can)\s+(.+)", q)
        if m and q.startswith("where"):
            concept = clean_subject(m.group(1).strip())
            # Strip trailing verbs that might have been captured
            for suffix in [" live", " lives", " found", " be found", " located", " stay"]:
                if concept.endswith(suffix):
                    concept = concept[:-len(suffix)].strip()
            try:
                result = compose_response(self.loom, "where", concept)
                if result:
                    return result
            except Exception:
                pass

        # ── "can X do Y?" ──
        m = re.match(r"can\s+(.+?)\s+(\w+(?:\s+\w+)?)\s*$", q)
        if m:
            concept = clean_subject(m.group(1).strip())
            target = m.group(2).strip()
            try:
                result = compose_response(self.loom, "can", concept, relation="can", target=target)
                if result:
                    return result
            except Exception:
                pass

        # ── "what can X do?" / "what does X have?" / "what does X eat?" ──
        m = re.match(r"what\s+(?:can|does|do)\s+(.+?)\s+(do|have|eat|need|cause|produce|make)\s*$", q)
        if m:
            concept = clean_subject(m.group(1).strip())
            verb = m.group(2).strip()
            if verb == "do":
                # "what can X do?" → describe abilities
                try:
                    facts = gather_facts(self.loom, concept)
                    if facts["direct"] or facts["inherited"]:
                        # Collect abilities
                        from ..composer import _collect_from_rels, _format_list, ABILITY_RELS, _pretty
                        abilities = _collect_from_rels(facts["direct"], ABILITY_RELS, limit=6)
                        if abilities:
                            S = _pretty(facts["concept"]).title()
                            return f"{S} can {_format_list(abilities)}."
                except Exception:
                    pass
            else:
                # Map verb to relation and use general composer
                verb_map = {"have": "has", "eat": "eats", "need": "needs",
                            "cause": "causes", "produce": "produces", "make": "makes"}
                relation = verb_map.get(verb, verb)
                try:
                    result = compose_response(self.loom, "general", concept, relation=relation)
                    if result:
                        return result
                except Exception:
                    pass

        # ── "what does X verb?" (generic) ──
        m = re.match(r"what\s+(?:does|do)\s+(.+?)\s+(\w+)\s*$", q)
        if m:
            concept = clean_subject(m.group(1).strip())
            verb = m.group(2).strip()
            try:
                result = compose_response(self.loom, "general", concept, relation=verb)
                if result:
                    return result
            except Exception:
                pass

        # ── "does X have Y?" / "is X Y?" ──
        m = re.match(r"(?:does|do)\s+(.+?)\s+(have|eat|need)\s+(.+)", q)
        if m:
            concept = clean_subject(m.group(1).strip())
            verb = m.group(2).strip()
            target = m.group(3).strip()
            verb_map = {"have": "has", "eat": "eats", "need": "needs"}
            relation = verb_map.get(verb, verb)
            try:
                c = _resolve_concept(self.loom.knowledge, concept)
                items = self.loom.knowledge.get(c, {}).get(relation, [])
                target_norm = normalize(target)
                for item in items:
                    if target_norm in normalize(item) or normalize(item) in target_norm:
                        return f"Yes, {concept} {verb}s {target.replace('_', ' ')}."
                return f"I don't think {concept} {verb}s {target}."
            except Exception:
                pass

        return None

    def _check_grammar_parser(self, t: str) -> str | None:
        """
        Try spaCy dependency parser for complex sentences, falling back
        to the manual recursive descent parser. Returns None if neither
        can handle it (falls through to regex handlers).
        """
        # Only attempt if sentence has structural complexity
        has_relative = bool(re.search(r"\b(that|which|who)\s+(have|has|can|is|are|was|were|eat|live)", t))
        has_conjoined = " and " in t and (t.count(",") >= 1 or " and " in t.split(" is ")[0] if " is " in t else True)
        has_multiple_clauses = t.count(",") >= 2
        if not (has_relative or has_conjoined or has_multiple_clauses):
            return None
        if self._is_question(t):
            return None

        facts = []

        # Try spaCy first (better quality)
        try:
            from ..spacy_parser import parse as spacy_parse, SPACY_AVAILABLE
            if SPACY_AVAILABLE:
                facts = spacy_parse(t)
        except Exception:
            pass

        # Fallback to manual grammar parser
        if not facts or len(facts) < 2:
            try:
                from ..grammar_parser import parse_and_extract
                manual_facts = parse_and_extract(t)
                if manual_facts and len(manual_facts) >= 2:
                    facts = manual_facts
            except Exception:
                pass

        if not facts or len(facts) < 2:
            return None

        added = 0
        for fact in facts:
            s = fact.subject.strip()
            r = fact.relation.strip()
            o = fact.obj.strip()
            if not s or not r or not o:
                continue
            if len(s) > 50 or len(o) > 50:
                continue
            try:
                existing = self.loom.get(s, r) or []
                if o.lower() not in [e.lower() for e in existing]:
                    self.loom.add_fact(s, r, o)
                    added += 1
            except Exception:
                pass

        if added > 0:
            self.last_subject = facts[0].subject
            self.loom.context.update(
                subject=facts[0].subject,
                relation=facts[0].relation,
                obj=facts[0].obj,
            )
            return f"Got it — learned {added} fact{'s' if added != 1 else ''} from that."
        return None

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
    def _check_generic_query(self, t: str) -> str | None:
        """Generic SVO-based query handler — replaces specialized query functions."""
        if not self._is_question(t):
            return None
        from ..query_engine import handle_query
        return handle_query(self, t)

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
