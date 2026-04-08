"""
Structural Extraction Layer for Loom.

A systematic pre-processor that extracts metadata from sentences by recognizing
word CATEGORIES (hedging, temporal, comparative, numbers, purpose, frequency,
degree) based on their POSITION in the sentence.

Instead of hardcoding 40+ regex patterns for each speech style, this module:
1. Defines word CATEGORIES (vocabularies of modifier words)
2. Uses POSITION RULES to find them (sentence-initial, pre-adjective, post-verb, etc.)
3. STRIPS modifiers from the sentence and returns clean text + metadata
4. The existing parser handles the clean sentence; metadata enriches the stored facts

This means adding support for a new modifier type only requires:
- Adding words to a category
- Not writing a new regex pattern
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set


# =====================================================================
# Word Categories - vocabularies, not patterns
# =====================================================================

HEDGE_WORDS = {
    "maybe", "perhaps", "probably", "possibly", "apparently",
    "supposedly", "arguably", "presumably", "seemingly",
}

HEDGE_PHRASES = [
    "i think", "i guess", "i believe", "i suppose", "i feel like",
    "it seems", "it seems like", "it appears", "it looks like",
    "as far as i know", "in my opinion", "from what i know",
]

DEGREE_WORDS = {
    "very", "extremely", "quite", "somewhat", "slightly",
    "incredibly", "really", "pretty", "fairly", "highly",
    "remarkably", "unusually", "exceptionally", "particularly",
    "especially", "terribly", "awfully",
    "definitely", "certainly", "absolutely", "undoubtedly",
    "clearly", "obviously", "surely", "truly",
}

FREQUENCY_WORDS = {
    "always", "never", "sometimes", "often", "rarely",
    "usually", "frequently", "occasionally", "seldom",
    "regularly", "constantly", "typically", "generally",
    "normally", "commonly", "hardly",
}

TEMPORAL_WORDS = {
    "yesterday", "today", "tomorrow", "tonight", "nowadays",
    "recently", "currently", "formerly", "previously",
    "eventually", "finally", "initially", "originally",
}

TEMPORAL_PHRASES = [
    "last night", "last week", "last month", "last year",
    "this morning", "this afternoon", "this evening",
    "this week", "this month", "this year",
    "next week", "next month", "next year",
    "at night", "at dawn", "at dusk",
    "in the morning", "in the afternoon", "in the evening",
    "in the winter", "in the summer", "in the spring", "in the fall",
    "in winter", "in summer", "in spring", "in fall",
    "every day", "every night", "every week", "every year",
    "every morning", "every evening",
    "a long time ago", "long ago", "in the past",
    "in the future", "right now", "these days",
]

COMPARATIVE_SUFFIXES = ("er", "ier")  # bigger, happier
SUPERLATIVE_SUFFIXES = ("est", "iest")  # biggest, happiest

COMPARATIVE_WORDS = {
    "more", "less", "better", "worse", "greater", "fewer",
    "larger", "smaller", "bigger", "faster", "slower",
    "stronger", "weaker", "taller", "shorter", "heavier",
    "lighter", "older", "younger", "newer", "wider", "deeper",
    "higher", "lower", "longer", "thicker", "thinner",
    "smarter", "dumber", "louder", "quieter", "brighter",
    "darker", "hotter", "colder", "richer", "poorer",
}

SUPERLATIVE_WORDS = {
    "most", "least", "best", "worst", "greatest",
    "largest", "smallest", "biggest", "fastest", "slowest",
    "strongest", "weakest", "tallest", "shortest", "heaviest",
    "lightest", "oldest", "youngest", "newest", "widest", "deepest",
    "highest", "lowest", "longest", "thickest", "thinnest",
    "smartest", "loudest", "quietest", "brightest",
    "darkest", "hottest", "coldest", "richest", "poorest",
}

PURPOSE_STARTERS = [
    "in order to", "so that", "so as to",
    "used to", "used for", "meant for", "meant to",
    "designed to", "designed for",
    "for the purpose of",
]

# Filler/discourse words to strip from start of sentence
FILLER_STARTS = [
    "you know what", "you know", "so basically", "basically",
    "like seriously", "like", "well", "honestly",
    "actually", "okay so", "ok so", "right so",
    "anyway", "anyways", "look", "listen",
    "i mean", "to be honest", "tbh",
]

# Number word mappings
NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000,
    "million": 1000000, "billion": 1000000000,
    "a dozen": 12, "a hundred": 100, "a thousand": 1000,
}


# =====================================================================
# Metadata structure
# =====================================================================

@dataclass
class ExtractionResult:
    """Result of structural extraction from a sentence."""
    clean_text: str                         # Sentence with modifiers stripped
    original_text: str                      # Original input
    confidence: Optional[str] = None        # "high", "medium", "low" from hedging
    temporal: Optional[str] = None          # Temporal context
    frequency: Optional[str] = None         # Frequency adverb
    degree: Optional[str] = None            # Intensity modifier
    comparison: Optional[Dict] = None       # {"type": "comparative"/"superlative", "target": "cats", "adjective": "bigger"}
    quantities: List[Dict] = field(default_factory=list)   # [{"number": 4, "unit": "legs"}]
    purpose: Optional[str] = None           # Purpose/function
    extra_facts: List[Tuple[str, str, str]] = field(default_factory=list)  # Additional facts to store

    @property
    def has_metadata(self) -> bool:
        return any([
            self.confidence, self.temporal, self.frequency,
            self.degree, self.comparison, self.quantities,
            self.purpose, self.extra_facts,
        ])


# =====================================================================
# Structural Extractor
# =====================================================================

class StructuralExtractor:
    """
    Systematic sentence pre-processor.

    Recognizes word categories by position, extracts metadata,
    and returns a cleaned sentence for the downstream parser.

    Usage:
        extractor = StructuralExtractor()
        result = extractor.extract("maybe dogs are bigger than cats")
        # result.clean_text = "dogs are big"
        # result.confidence = "low"
        # result.comparison = {"type": "comparative", "adjective": "big", "target": "cats"}
    """

    def extract(self, text: str) -> ExtractionResult:
        """Main entry: extract metadata and return cleaned sentence."""
        result = ExtractionResult(
            clean_text=text.strip(),
            original_text=text.strip(),
        )

        # Each extraction step modifies result.clean_text progressively
        # Order matters: strip fillers first, then extract metadata

        self._strip_fillers(result)
        self._extract_hedging(result)
        self._extract_temporal(result)
        self._extract_frequency(result)
        self._extract_degree(result)
        self._extract_comparison(result)
        self._extract_quantities(result)
        self._extract_purpose(result)

        # Final cleanup
        result.clean_text = re.sub(r'\s+', ' ', result.clean_text).strip()
        result.clean_text = re.sub(r'\s+([,.])', r'\1', result.clean_text)

        # Safety: if stripping reduced to <3 words and original had more,
        # keep the original (metadata is still captured, but downstream
        # parser needs enough words to find subject+verb+object)
        clean_words = result.clean_text.split()
        orig_words = result.original_text.split()
        if len(clean_words) < 3 and len(orig_words) >= 3:
            result.clean_text = result.original_text

        return result

    # ------------------------------------------------------------------
    # Extraction steps
    # ------------------------------------------------------------------

    def _strip_fillers(self, result: ExtractionResult):
        """Remove conversational filler from start of sentence."""
        text = result.clean_text.lower()
        for filler in sorted(FILLER_STARTS, key=len, reverse=True):
            if text.startswith(filler):
                # Preserve original casing for the remainder
                result.clean_text = result.clean_text[len(filler):].lstrip(" ,")
                break

    def _extract_hedging(self, result: ExtractionResult):
        """Detect hedging/uncertainty markers -> set confidence."""
        text_lower = result.clean_text.lower()

        # Check phrases first (longer matches)
        for phrase in sorted(HEDGE_PHRASES, key=len, reverse=True):
            if text_lower.startswith(phrase):
                result.confidence = "low"
                result.clean_text = result.clean_text[len(phrase):].lstrip(" ,")
                return
            # Also check mid-sentence: "dogs, i think, are loyal"
            pattern = re.compile(r',?\s*' + re.escape(phrase) + r'\s*,?\s*', re.IGNORECASE)
            if pattern.search(result.clean_text):
                result.confidence = "low"
                result.clean_text = pattern.sub(' ', result.clean_text).strip()
                return

        # Check single words at start
        first_word = text_lower.split()[0] if text_lower.split() else ""
        if first_word in HEDGE_WORDS:
            result.confidence = "low"
            result.clean_text = result.clean_text[len(first_word):].lstrip(" ,")

    def _extract_temporal(self, result: ExtractionResult):
        """Detect temporal markers -> set temporal context."""
        text_lower = result.clean_text.lower()

        # Check phrases first
        for phrase in sorted(TEMPORAL_PHRASES, key=len, reverse=True):
            if phrase in text_lower:
                result.temporal = phrase
                # Remove from text
                pattern = re.compile(r',?\s*' + re.escape(phrase) + r'\s*,?', re.IGNORECASE)
                result.clean_text = pattern.sub('', result.clean_text).strip()
                return

        # Check single words
        words = result.clean_text.lower().split()
        for word in words:
            if word.strip(",.") in TEMPORAL_WORDS:
                result.temporal = word.strip(",.")
                # Only remove if it doesn't break the core sentence
                pattern = re.compile(r'\b' + re.escape(word.strip(",.")) + r'\b', re.IGNORECASE)
                result.clean_text = pattern.sub('', result.clean_text, count=1).strip()
                return

    def _extract_frequency(self, result: ExtractionResult):
        """Detect frequency adverbs -> set frequency."""
        words = result.clean_text.lower().split()
        for word in words:
            clean_word = word.strip(",.")
            if clean_word in FREQUENCY_WORDS:
                result.frequency = clean_word
                # Remove from text
                pattern = re.compile(r'\b' + re.escape(clean_word) + r'\b', re.IGNORECASE)
                result.clean_text = pattern.sub('', result.clean_text, count=1).strip()
                return

    def _extract_degree(self, result: ExtractionResult):
        """Detect degree modifiers (very, extremely) -> set degree."""
        words = result.clean_text.split()
        for i, word in enumerate(words):
            if word.lower().strip(",.") in DEGREE_WORDS:
                result.degree = word.lower().strip(",.")
                # Remove the degree word
                words.pop(i)
                result.clean_text = ' '.join(words)
                return

    def _extract_comparison(self, result: ExtractionResult):
        """Detect comparative/superlative structures -> extract comparison."""
        text_lower = result.clean_text.lower()

        # Pattern: "X [copula] [adverb?] [comparative] than Y"
        comp_match = re.search(
            r'\b(is|are|was|were)\s+(?:\w+\s+)?(\w+(?:er|ier))\s+than\s+(.+?)(?:\s*[.,]|$)',
            text_lower
        )
        if not comp_match:
            # Also check "more/less ADJ than Y"
            comp_match = re.search(
                r'\b(is|are|was|were)\s+(more|less)\s+(\w+)\s+than\s+(.+?)(?:\s*[.,]|$)',
                text_lower
            )
            if comp_match:
                copula = comp_match.group(1)
                modifier = comp_match.group(2)
                adj = comp_match.group(3)
                target = comp_match.group(4).strip()
                # Extract subject (everything before copula)
                subj_end = text_lower.index(copula)
                subject = result.clean_text[:subj_end].strip()

                result.comparison = {
                    "type": "comparative",
                    "adjective": adj,
                    "modifier": modifier,
                    "target": target,
                }
                # Generate extra fact
                result.extra_facts.append(
                    (subject, f"{modifier}_{adj}_than", target)
                )
                # Clean: replace "more ADJ than Y" with just "ADJ"
                clean_pattern = re.compile(
                    r'\b(more|less)\s+\w+\s+than\s+.+?(?:\s*[.,]|$)',
                    re.IGNORECASE
                )
                result.clean_text = clean_pattern.sub(adj, result.clean_text).strip()
                return
        else:
            copula = comp_match.group(1)
            comparative = comp_match.group(2)
            target = comp_match.group(3).strip()
            # Derive base adjective: bigger -> big, faster -> fast
            base_adj = self._base_adjective(comparative)
            # Extract subject
            subj_end = text_lower.index(copula)
            subject = result.clean_text[:subj_end].strip()

            result.comparison = {
                "type": "comparative",
                "adjective": base_adj,
                "comparative": comparative,
                "target": target,
            }
            result.extra_facts.append(
                (subject, f"{comparative}_than", target)
            )
            # Clean: replace "bigger than cats" with base adjective "big"
            clean_pattern = re.compile(
                r'\b\w+(?:er|ier)\s+than\s+.+?(?:\s*[.,]|$)',
                re.IGNORECASE
            )
            result.clean_text = clean_pattern.sub(base_adj, result.clean_text).strip()
            return

        # Pattern: "X [copula] the [superlative] Y"
        sup_match = re.search(
            r'\b(is|are|was|were)\s+the\s+(\w+(?:est|iest))\s+(\w+)',
            text_lower
        )
        if not sup_match:
            sup_match = re.search(
                r'\b(is|are|was|were)\s+the\s+(most|least)\s+(\w+)\s+(\w+)',
                text_lower
            )
            if sup_match:
                copula = sup_match.group(1)
                modifier = sup_match.group(2)
                adj = sup_match.group(3)
                category = sup_match.group(4).strip()
                subj_end = text_lower.index(copula)
                subject = result.clean_text[:subj_end].strip()

                result.comparison = {
                    "type": "superlative",
                    "adjective": adj,
                    "modifier": modifier,
                    "category": category,
                }
                result.extra_facts.append(
                    (subject, "is", category)
                )
                result.extra_facts.append(
                    (subject, f"{modifier}_{adj}_in", category)
                )
                # Clean: "the most ADJ Y" -> "Y" + property ADJ
                clean_pattern = re.compile(
                    r'\bthe\s+(most|least)\s+\w+\s+',
                    re.IGNORECASE
                )
                result.clean_text = clean_pattern.sub('', result.clean_text).strip()
                return
        else:
            copula = sup_match.group(1)
            superlative = sup_match.group(2)
            category = sup_match.group(3).strip()
            base_adj = self._base_adjective(superlative)
            subj_end = text_lower.index(copula)
            subject = result.clean_text[:subj_end].strip()

            result.comparison = {
                "type": "superlative",
                "adjective": base_adj,
                "superlative": superlative,
                "category": category,
            }
            result.extra_facts.append(
                (subject, "is", category)
            )
            result.extra_facts.append(
                (subject, f"{superlative}_among", category)
            )
            # Clean: "the fastest animals" -> "animals" + property fast
            clean_pattern = re.compile(
                r'\bthe\s+\w+(?:est|iest)\s+',
                re.IGNORECASE
            )
            result.clean_text = clean_pattern.sub('', result.clean_text).strip()
            return

    def _extract_quantities(self, result: ExtractionResult):
        """Detect numbers attached to nouns -> extract quantities."""
        # Pattern: "have/has NUMBER NOUN" or "NUMBER NOUN"
        # Examples: "have 4 legs", "has 2 eyes", "weighs 100 kilograms"
        text = result.clean_text

        # Digit numbers: "have 4 legs", "has 200 bones"
        num_matches = list(re.finditer(
            r'\b(\d+)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)\b', text
        ))

        for match in num_matches:
            number = int(match.group(1))
            unit = match.group(2).strip()
            # Skip years (4-digit numbers), ages, etc.
            if number > 1000 and len(match.group(1)) == 4:
                continue
            result.quantities.append({
                "number": number,
                "unit": unit,
            })
            # Replace "4 legs" with "legs" in clean text
            result.clean_text = result.clean_text.replace(
                match.group(0), unit, 1
            )

        # Word numbers: "four legs", "two eyes"
        text_lower = result.clean_text.lower()
        for word, num in sorted(NUMBER_WORDS.items(), key=lambda x: len(x[0]), reverse=True):
            pattern = re.compile(
                r'\b' + re.escape(word) + r'\s+([a-zA-Z]+)\b',
                re.IGNORECASE
            )
            match = pattern.search(result.clean_text)
            if match:
                unit = match.group(1)
                result.quantities.append({
                    "number": num,
                    "unit": unit,
                })
                # Replace "four legs" with "legs"
                result.clean_text = pattern.sub(unit, result.clean_text, count=1)

    def _extract_purpose(self, result: ExtractionResult):
        """Detect purpose/function markers -> extract purpose."""
        text_lower = result.clean_text.lower()

        # Pattern: "X is/are for Y"
        for_match = re.search(
            r'\b(is|are)\s+for\s+(.+?)(?:\s*[.,]|$)',
            text_lower
        )
        if for_match:
            purpose = for_match.group(2).strip()
            result.purpose = purpose

            # Extract subject
            copula = for_match.group(1)
            subj_end = text_lower.index(f"{copula} for")
            subject = result.clean_text[:subj_end].strip()

            result.extra_facts.append(
                (subject, "used_for", purpose)
            )
            # Keep original text so parser can still process the subject
            # The extra_fact stores the purpose relation separately
            return

        # Pattern: "X is/are used to/for Y"
        for phrase in sorted(PURPOSE_STARTERS, key=len, reverse=True):
            pattern = re.compile(
                r'\b' + re.escape(phrase) + r'\s+(.+?)(?:\s*[.,]|$)',
                re.IGNORECASE
            )
            match = pattern.search(result.clean_text)
            if match:
                purpose = match.group(1).strip()
                result.purpose = purpose

                # Extract subject (everything before the purpose phrase)
                start = result.clean_text.lower().index(phrase.lower())
                subject = result.clean_text[:start].strip().rstrip(" .,")

                # Remove verb if trailing: "forks are used to" -> subject="forks are"
                subject = re.sub(r'\s+(is|are|was|were)\s*$', '', subject)

                result.extra_facts.append(
                    (subject, "used_for", purpose)
                )
                # Keep original text so parser can still process
                return

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _base_adjective(self, comparative_or_superlative: str) -> str:
        """Derive base adjective from comparative/superlative form."""
        word = comparative_or_superlative.lower()

        # Irregular forms
        irregulars = {
            "bigger": "big", "biggest": "big",
            "better": "good", "best": "good",
            "worse": "bad", "worst": "bad",
            "more": "much", "most": "much",
            "less": "little", "least": "little",
            "further": "far", "furthest": "far",
            "farther": "far", "farthest": "far",
            "larger": "large", "largest": "large",
            "wider": "wide", "widest": "wide",
            "later": "late", "latest": "late",
            "nicer": "nice", "nicest": "nice",
        }
        if word in irregulars:
            return irregulars[word]

        # Strip -ier/-iest -> -y (happier -> happy)
        if word.endswith("ier"):
            return word[:-3] + "y"
        if word.endswith("iest"):
            return word[:-4] + "y"

        # Strip doubled consonant + er/est (bigger -> big)
        if len(word) > 4 and word[-3] == word[-4] and word.endswith("er"):
            return word[:-3]
        if len(word) > 5 and word[-4] == word[-5] and word.endswith("est"):
            return word[:-4]

        # Strip -er/-est (faster -> fast, fastest -> fast)
        if word.endswith("est"):
            return word[:-3]
        if word.endswith("er"):
            return word[:-2]

        return word
