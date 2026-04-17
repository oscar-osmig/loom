"""
Style Learner — extracts writing patterns from user input and tracks
feedback on Loom's responses. Pure symbolic — no ML, no embeddings.

Learns three things:
  1. Sentence templates — structural patterns like "Unlike X, Y does Z"
  2. Opener preferences — "is classified as" vs "is a kind of" vs "is"
  3. Ordering preferences — for a topic, which relations come first

Templates are stored in MongoDB and used by the composer with confidence
weighting based on positive/negative feedback.
"""

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .brain import Loom


# ── Structural markers ────────────────────────────────────────────────

# Openers: how sentences start
OPENER_PATTERNS = [
    (r"^unlike\s+(\w+)", "contrast_opener"),
    (r"^most\s+(\w+)", "quantifier_most"),
    (r"^some\s+(\w+)", "quantifier_some"),
    (r"^all\s+(\w+)", "quantifier_all"),
    (r"^despite\s+(\w+)", "despite_opener"),
    (r"^although\s+(\w+)", "although_opener"),
    (r"^while\s+(\w+)", "while_opener"),
    (r"^in\s+(\w+)", "locative_opener"),
    (r"^during\s+(\w+)", "temporal_opener"),
    (r"^when\s+(\w+)", "when_opener"),
    (r"^if\s+(\w+)", "conditional_opener"),
    (r"^because\s+(\w+)", "causal_opener"),
]

# Connectives: how clauses join
CONNECTIVE_PATTERNS = [
    (r",\s+but\s+", "contrast_but"),
    (r",\s+which\s+", "relative_which"),
    (r",\s+that\s+", "relative_that"),
    (r",\s+however,\s+", "however"),
    (r",\s+therefore,?\s+", "therefore"),
    (r",\s+so\s+that\s+", "purpose"),
    (r",\s+because\s+", "causal"),
    (r",\s+and\s+also\s+", "also"),
    (r";\s+", "semicolon"),
    (r"\s+—\s+", "em_dash"),
]

# Relation ordering — which relations appear first in descriptions
RELATION_ORDER_KEYWORDS = {
    "is": ["is", "are", "was", "were"],
    "has": ["has", "have", "had", "with"],
    "can": ["can", "could", "able to"],
    "lives_in": ["lives in", "found in", "located in"],
    "eats": ["eats", "feeds on", "consumes"],
    "causes": ["causes", "leads to", "results in"],
}


class StyleLearner:
    """Learns writing style from user input and response feedback."""

    def __init__(self, loom: "Loom"):
        self.loom = loom
        self._cache_templates = None
        self._cache_time = 0

    # ══════════════════════════════════════════════════════════════════
    #  Learning from user input (extract templates)
    # ══════════════════════════════════════════════════════════════════

    def observe(self, text: str) -> None:
        """Analyze a user sentence and extract structural patterns."""
        if not text or len(text) < 15 or len(text) > 500:
            return

        t = text.lower().strip().rstrip(".?!")
        patterns_seen = []

        # Detect opener patterns
        for regex, label in OPENER_PATTERNS:
            if re.match(regex, t):
                patterns_seen.append(("opener", label))
                break

        # Detect connective patterns
        for regex, label in CONNECTIVE_PATTERNS:
            if re.search(regex, t):
                patterns_seen.append(("connective", label))

        # Extract sentence template — replace words with placeholders
        template = self._extract_template(t)
        if template:
            patterns_seen.append(("template", template))

        # Store patterns
        for kind, value in patterns_seen:
            self._increment_pattern(kind, value)

    def _extract_template(self, text: str) -> Optional[str]:
        """Extract a reusable template from a sentence.

        Example: "Unlike birds, mammals nurse their young" →
                 "unlike [X], [Y] [VERB] [Z]"
        """
        words = text.split()
        if len(words) < 4 or len(words) > 20:
            return None

        # Known structural words to preserve
        structure_words = {
            "is", "are", "was", "were", "be", "been",
            "has", "have", "had",
            "can", "could", "will", "would", "should",
            "do", "does", "did",
            "but", "and", "or", "so", "yet",
            "if", "when", "while", "because", "although",
            "unlike", "despite", "instead",
            "the", "a", "an",
            "in", "on", "at", "to", "from", "with", "by",
            "which", "that", "who", "whose", "whom",
            "however", "therefore", "also",
            "not", "no", "never",
            "most", "some", "all", "many", "few",
        }

        result = []
        slot_count = 0
        structure_count = 0
        for w in words:
            wl = re.sub(r"[^a-z]", "", w.lower())
            if wl in structure_words or not wl:
                result.append(w)
                if wl:  # Don't count empty strings (punctuation-only)
                    structure_count += 1
            else:
                slot_count += 1
                if slot_count > 6:
                    return None
                result.append(f"[{slot_count}]")

        template = " ".join(result)

        # Quality gate: must have meaningful structure
        # - At least 2 content slots (something to vary)
        # - At least 2 structural words preserved (otherwise it's just slot soup)
        # - Structural words must be non-trivial (not just "the" or "a")
        trivial = {"the", "a", "an"}
        meaningful_structure = sum(1 for w in result if not w.startswith("[")
                                   and re.sub(r"[^a-z]", "", w.lower()) not in trivial
                                   and re.sub(r"[^a-z]", "", w.lower()) != "")
        if slot_count < 2 or slot_count > 5 or meaningful_structure < 1:
            return None
        # Reject templates that are just consecutive slots with no structure between
        if re.fullmatch(r"(\[\d+\]\s*)+", template.strip()):
            return None

        return template

    def _increment_pattern(self, kind: str, value: str) -> None:
        """Record a pattern observation in MongoDB."""
        try:
            self.loom.storage.db.style_patterns.update_one(
                {
                    "instance": self.loom.storage.instance_name,
                    "kind": kind,
                    "value": value,
                },
                {
                    "$inc": {"count": 1},
                    "$set": {"last_seen": datetime.now(timezone.utc).isoformat()},
                    "$setOnInsert": {
                        "first_seen": datetime.now(timezone.utc).isoformat(),
                        "likes": 0,
                        "dislikes": 0,
                    },
                },
                upsert=True,
            )
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════
    #  Learning from response feedback
    # ══════════════════════════════════════════════════════════════════

    def record(self, input_text: str, response_text: str, rating: str) -> None:
        """Update template effectiveness based on feedback."""
        if not response_text or rating not in ("like", "dislike"):
            return

        # Detect which patterns appeared in the response
        t = response_text.lower().strip().rstrip(".?!")

        field = "likes" if rating == "like" else "dislikes"

        for regex, label in OPENER_PATTERNS:
            if re.match(regex, t):
                self._bump_feedback("opener", label, field)
                break

        for regex, label in CONNECTIVE_PATTERNS:
            if re.search(regex, t):
                self._bump_feedback("connective", label, field)

        # Also rate composer templates by checking common phrasings
        template_phrases = {
            "is_classified_as": "is classified as",
            "is_a_kind_of": "is a kind of",
            "falls_under": "falls under",
            "encompasses": "encompasses things like",
            "types_of": "types of",
            "notable_features": "notable features include",
            "characterized_by": "characterized by",
            "key_traits": "key traits",
            "known_to": "known to",
            "able_to": "able to",
        }
        for label, phrase in template_phrases.items():
            if phrase in t:
                self._bump_feedback("composer_template", label, field)

    def _bump_feedback(self, kind: str, value: str, field: str) -> None:
        """Increment like or dislike counter for a pattern."""
        try:
            self.loom.storage.db.style_patterns.update_one(
                {
                    "instance": self.loom.storage.instance_name,
                    "kind": kind,
                    "value": value,
                },
                {
                    "$inc": {field: 1},
                    "$setOnInsert": {"count": 0, "likes": 0, "dislikes": 0},
                },
                upsert=True,
            )
            self._cache_templates = None  # Invalidate cache
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════
    #  Reading learned style (used by composer)
    # ══════════════════════════════════════════════════════════════════

    def get_template_score(self, label: str) -> float:
        """
        Return a score in [-1, +1] for a composer template label.
        Positive = users like it, negative = users dislike it.
        """
        try:
            doc = self.loom.storage.db.style_patterns.find_one(
                {
                    "instance": self.loom.storage.instance_name,
                    "kind": "composer_template",
                    "value": label,
                }
            )
            if not doc:
                return 0.0
            likes = doc.get("likes", 0)
            dislikes = doc.get("dislikes", 0)
            total = likes + dislikes
            if total == 0:
                return 0.0
            return (likes - dislikes) / total
        except Exception:
            return 0.0

    def get_top_patterns(self, kind: str, limit: int = 5) -> list:
        """Return top patterns of a given kind, ordered by frequency + feedback."""
        try:
            cursor = self.loom.storage.db.style_patterns.find({
                "instance": self.loom.storage.instance_name,
                "kind": kind,
            })
            patterns = []
            for doc in cursor:
                score = doc.get("count", 0) + (doc.get("likes", 0) * 2) - doc.get("dislikes", 0)
                patterns.append((doc.get("value"), score, doc))
            patterns.sort(key=lambda x: x[1], reverse=True)
            return patterns[:limit]
        except Exception:
            return []

    def get_stats(self) -> dict:
        """Summary of learned style."""
        try:
            total = self.loom.storage.db.style_patterns.count_documents({
                "instance": self.loom.storage.instance_name
            })
            templates_learned = self.loom.storage.db.style_patterns.count_documents({
                "instance": self.loom.storage.instance_name,
                "kind": "template",
            })
            openers = self.loom.storage.db.style_patterns.count_documents({
                "instance": self.loom.storage.instance_name,
                "kind": "opener",
            })
            feedback_received = self.loom.storage.db.feedback.count_documents({
                "instance": self.loom.storage.instance_name
            })
            return {
                "total_patterns": total,
                "templates_learned": templates_learned,
                "openers_learned": openers,
                "feedback_received": feedback_received,
            }
        except Exception:
            return {
                "total_patterns": 0,
                "templates_learned": 0,
                "openers_learned": 0,
                "feedback_received": 0,
            }
