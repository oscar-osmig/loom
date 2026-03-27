"""
Sentence Simplifier for Loom.
Breaks complex sentences into simple, parseable statements.

Handles patterns like:
- "X developed A and invented B" -> ["X developed A", "X invented B"]
- "X need A, B, and C" -> ["X need A", "X need B", "X need C"]
- "A have X, B have Y" -> ["A have X", "B have Y"]
- "Some X do A, others do B" -> ["some X do A", "other X do B"]
"""

import re
from typing import List, Optional


class SentenceSimplifier:
    """
    Simplifies complex sentences into simple subject-verb-object statements.
    """

    def __init__(self):
        # Import verbs from unified relations (single source of truth)
        try:
            from .parser.relations import RELATION_DEFS
            # Build set of all verb forms, including first words of multi-word verbs
            self.all_verbs = set()
            for r in RELATION_DEFS:
                for v in [r.base_verb, r.past, r.present_s, r.present_p]:
                    if v:
                        self.all_verbs.add(v)
                        # Also add first word of multi-word verbs
                        # e.g., "traded with" -> also add "traded"
                        if ' ' in v:
                            first_word = v.split()[0]
                            self.all_verbs.add(first_word)
            # Remove empty strings
            self.all_verbs = {v for v in self.all_verbs if v}
        except ImportError:
            # Fallback if relations not available
            self.all_verbs = {
                'need', 'needs', 'have', 'has', 'want', 'wants',
                'eat', 'eats', 'use', 'uses', 'like', 'likes',
                'require', 'requires', 'include', 'includes',
                'contain', 'contains', 'are', 'is', 'can', 'could',
                'built', 'build', 'builds', 'constructed', 'construct',
                'developed', 'develop', 'develops', 'invented', 'invent',
                'created', 'create', 'creates', 'discovered', 'discover',
                'established', 'establish', 'conquered', 'conquer',
                'studied', 'study', 'studies', 'worshipped', 'worship',
                'hosted', 'host', 'hosts', 'produced', 'produce', 'produces',
                'traded', 'trade', 'trades', 'ruled', 'rule', 'rules',
            }

        # Build regex pattern for verbs (sorted by length descending to match longer first)
        sorted_verbs = sorted(self.all_verbs, key=len, reverse=True)
        self.verb_pattern = '|'.join(re.escape(v) for v in sorted_verbs)

    def simplify(self, sentence: str) -> List[str]:
        """
        Main entry: simplify a complex sentence into simple statements.
        """
        sentence = sentence.strip()
        if not sentence:
            return []

        results = []

        # First, try compound verb pattern (X verb1 Y and verb2 Z)
        simplified = self._simplify_compound_verbs(sentence)
        if simplified and len(simplified) > 1:
            return simplified

        # Try parallel structure (multiple subject-verb pairs)
        simplified = self._simplify_parallel_structure(sentence)
        if simplified and len(simplified) > 1:
            return simplified

        # Try list pattern (single subject, multiple objects)
        simplified = self._simplify_list_pattern(sentence)
        if simplified and len(simplified) > 1:
            return simplified

        # Try contrast pattern
        simplified = self._simplify_contrast_pattern(sentence)
        if simplified and len(simplified) > 1:
            return simplified

        # Try colon list
        simplified = self._simplify_colon_list(sentence)
        if simplified and len(simplified) > 1:
            return simplified

        # No simplification found, return original
        return [sentence]

    def _simplify_compound_verbs(self, sentence: str) -> List[str] | None:
        """
        Simplify: "X verb1 Y and verb2 Z" -> ["X verb1 Y", "X verb2 Z"]

        Handles sentences like:
        - "Ancient China developed papermaking and invented gunpowder"
        - "The Egyptians worshipped many gods and constructed temples"
        - "Greeks built temples and produced playwrights"
        """
        # Pattern: subject + verb1 + object1 + "and" + verb2 + object2
        # We need to find where "and" separates two verb phrases

        # First, find all verbs in the sentence
        lower = sentence.lower()

        # Find "and" positions
        and_positions = [m.start() for m in re.finditer(r'\s+and\s+', lower)]

        if not and_positions:
            return None

        for and_pos in and_positions:
            before_and = sentence[:and_pos].strip()
            after_and = sentence[and_pos:].strip()

            # Remove "and " from the start
            after_and = re.sub(r'^and\s+', '', after_and, flags=re.IGNORECASE)

            # Check if after_and starts with a verb
            after_and_lower = after_and.lower()
            starts_with_verb = False
            matched_verb = None

            for verb in sorted(self.all_verbs, key=len, reverse=True):
                if after_and_lower.startswith(verb + ' ') or after_and_lower == verb:
                    starts_with_verb = True
                    matched_verb = verb
                    break

            if starts_with_verb:
                # Find the subject from before_and
                # The subject is everything before the first verb
                subject = self._extract_subject(before_and)

                if subject:
                    # Create two statements
                    stmt1 = before_and
                    stmt2 = f"{subject} {after_and}"

                    # Recursively simplify in case there are more compound verbs
                    results = []
                    for s in self.simplify(stmt1):
                        results.append(s)
                    for s in self.simplify(stmt2):
                        results.append(s)

                    return results

        return None

    def _extract_subject(self, clause: str) -> str | None:
        """
        Extract the subject from a clause by finding everything before the first verb.
        """
        lower = clause.lower()

        # Find the first verb in the clause
        earliest_pos = len(clause)
        earliest_verb = None

        for verb in self.all_verbs:
            # Look for verb as a word (with word boundaries)
            pattern = rf'\b{re.escape(verb)}\b'
            match = re.search(pattern, lower)
            if match and match.start() < earliest_pos:
                earliest_pos = match.start()
                earliest_verb = verb

        if earliest_verb and earliest_pos > 0:
            subject = clause[:earliest_pos].strip()
            # Clean up subject
            subject = re.sub(r'^(the|a|an)\s+', '', subject, flags=re.IGNORECASE)
            return subject

        return None

    def _simplify_list_pattern(self, sentence: str) -> List[str] | None:
        """
        Simplify: "X verb A, B, and C" -> ["X verb A", "X verb B", "X verb C"]
        """
        # Pattern: subject + verb + list of objects
        pattern = rf'^(.+?)\s+({self.verb_pattern})\s+(.+?)(?:,\s*and\s+|\s+and\s+)(.+)$'
        match = re.match(pattern, sentence, re.IGNORECASE)

        if match:
            subject = match.group(1).strip()
            verb_used = match.group(2).strip()
            items_before = match.group(3).strip()
            last_item = match.group(4).strip()

            # Check if last_item contains a verb (would be compound, not list)
            last_item_lower = last_item.lower()
            for verb in self.all_verbs:
                if re.search(rf'\b{re.escape(verb)}\b', last_item_lower):
                    # This might be compound verbs, not a list
                    return None

            # Split items_before by comma
            items = [i.strip() for i in items_before.split(',') if i.strip()]
            items.append(last_item)

            # Generate simple sentences
            return [f"{subject} {verb_used} {item}" for item in items]

        return None

    def _simplify_parallel_structure(self, sentence: str) -> List[str] | None:
        """
        Simplify: "A have X, B have Y, and C have Z" -> individual statements
        """
        # Split on comma and 'and'
        parts = re.split(r',\s*(?:and\s+)?|\s+and\s+', sentence)
        if len(parts) < 2:
            return None

        # Check if each part has a subject-verb structure
        simple_sentences = []
        verb_count = 0

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Check if part has a verb
            has_verb = False
            for verb in self.all_verbs:
                pattern = rf'\b{re.escape(verb)}\b'
                if re.search(pattern, part.lower()):
                    has_verb = True
                    verb_count += 1
                    break

            if has_verb:
                simple_sentences.append(part)
            elif simple_sentences:
                # This part might be a continuation
                return None

        # Need at least 2 parts with verbs to be parallel
        if verb_count >= 2 and len(simple_sentences) >= 2:
            return simple_sentences

        return None

    def _simplify_contrast_pattern(self, sentence: str) -> List[str] | None:
        """
        Simplify: "Some animals walk, others fly" -> individual statements
        """
        match = re.match(
            r'some\s+(\w+)\s+(\w+)\s+(.+?),?\s*(?:and\s+|while\s+)?others?\s+(\w+)(?:\s+(.+))?',
            sentence, re.IGNORECASE
        )
        if match:
            category = match.group(1)
            verb1 = match.group(2)
            obj1 = match.group(3).strip().rstrip(',')
            verb2 = match.group(4)
            obj2 = match.group(5).strip() if match.group(5) else ""

            results = [f"some {category} {verb1} {obj1}"]
            if obj2:
                results.append(f"some {category} {verb2} {obj2}")
            else:
                results.append(f"some {category} {verb2}")
            return results

        return None

    def _simplify_colon_list(self, sentence: str) -> List[str] | None:
        """
        Simplify: "X: A, B, C" or "X have: A, B, C"
        """
        match = re.match(r'^(.+?):\s*(.+)$', sentence)
        if match:
            prefix = match.group(1).strip()
            list_part = match.group(2).strip()

            # Split list
            items = re.split(r',\s*(?:and\s+)?', list_part)
            items = [i.strip() for i in items if i.strip()]

            if len(items) > 1:
                # Try to extract verb from prefix
                for verb in self.all_verbs:
                    if prefix.lower().endswith(f' {verb}'):
                        subject = prefix[:-len(verb)-1].strip()
                        return [f"{subject} {verb} {item}" for item in items]

                # Just append items to prefix
                return [f"{prefix} {item}" for item in items]

        return None

    def simplify_paragraph(self, text: str) -> List[str]:
        """
        Simplify an entire paragraph into simple statements.
        """
        sentences = re.split(r'(?<=[.!?])\s+', text)

        all_simplified = []
        for sentence in sentences:
            sentence = sentence.strip().rstrip('.!?')
            if sentence:
                simplified = self.simplify(sentence)
                all_simplified.extend(simplified)

        return all_simplified

    def process_for_loom(self, text: str) -> List[dict]:
        """
        Process text and return structured data for Loom processing.
        """
        results = []
        simplified = self.simplify_paragraph(text)

        for stmt in simplified:
            relation_hint = self._detect_relation_hint(stmt)
            results.append({
                'text': stmt,
                'original': stmt == text,
                'relation_hint': relation_hint
            })

        return results

    def _detect_relation_hint(self, sentence: str) -> Optional[str]:
        """Detect what kind of relation this sentence expresses."""
        lower = sentence.lower()

        # Check against known relation verbs
        hints = [
            ('needs', [' need ', ' needs ']),
            ('has', [' have ', ' has ']),
            ('eats', [' eat ', ' eats ']),
            ('can', [' can ']),
            ('is', [' is ', ' are ']),
            ('causes', [' cause ', ' causes ']),
            ('built', [' built ', ' build ']),
            ('developed', [' developed ', ' develop ']),
            ('created', [' created ', ' create ']),
        ]

        for hint, patterns in hints:
            for p in patterns:
                if p in lower:
                    return hint

        return None
