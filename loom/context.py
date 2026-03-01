"""
Context and Topic Tracking for Loom.
Maintains conversational state, tracks topics, and manages dialogue flow.

Based on research:
- Conversation meaning depends on memory
- System must track topic, referents, speaker intention, previous commitments

Enhanced with:
- Improved coreference resolution (Hobbs-style rules)
- Recency-weighted entity tracking
- Semantic fit checking using knowledge graph
- Entity salience scoring
"""

import time
from collections import deque
from typing import Optional, List, Dict, Tuple
import re


# Entity salience weights
SALIENCE_SUBJECT = 3.0      # Subjects are highly salient
SALIENCE_OBJECT = 2.0       # Objects are moderately salient
SALIENCE_MENTIONED = 1.0    # Just mentioned
SALIENCE_DECAY = 0.3        # Decay per turn


class EntityMention:
    """Tracks a mentioned entity with salience."""
    def __init__(self, text: str, role: str, turn: int,
                 is_animate: bool = None, is_plural: bool = False):
        self.text = text
        self.role = role  # 'subject', 'object', 'other'
        self.turn = turn  # When it was mentioned
        self.is_animate = is_animate
        self.is_plural = is_plural
        self.salience = self._compute_initial_salience()

    def _compute_initial_salience(self) -> float:
        if self.role == 'subject':
            return SALIENCE_SUBJECT
        elif self.role == 'object':
            return SALIENCE_OBJECT
        return SALIENCE_MENTIONED

    def decay(self, current_turn: int):
        """Decay salience based on recency."""
        turns_passed = current_turn - self.turn
        self.salience = max(0.1, self.salience - (turns_passed * SALIENCE_DECAY))


class ConversationContext:
    """
    Tracks the current state of conversation.
    Enables pronoun resolution, topic continuity, and contextual understanding.
    """

    def __init__(self, history_size: int = 10):
        # Current topic being discussed
        self.current_topic = None

        # Stack of recent topics (for nested discussions)
        self.topic_stack = deque(maxlen=5)

        # Last mentioned entities for pronoun resolution
        self.last_subject = None
        self.last_object = None
        self.last_relation = None

        # Recent statements for context
        self.recent_statements = deque(maxlen=history_size)

        # Pending clarifications
        self.pending_clarification = None

        # User corrections history
        self.corrections = []

        # Conversation mode
        self.mode = "normal"  # normal, teaching, questioning, correcting

        # Enhanced entity tracking for coreference
        self.entity_mentions: List[EntityMention] = []
        self.current_turn = 0

        # Knowledge graph reference (set by Loom)
        self._knowledge_ref = None

        # Animate entity patterns
        self._animate_patterns = re.compile(
            r'\b(person|people|man|woman|boy|girl|child|children|'
            r'dog|cat|bird|animal|fish|horse|cow|pig|sheep|'
            r'teacher|doctor|student|friend|parent|baby|'
            r'he|she|they|who|someone|anyone|everyone)\b',
            re.IGNORECASE
        )

        # Plural patterns
        self._plural_patterns = re.compile(
            r'\b(\w+s|people|children|they|them|these|those)\b',
            re.IGNORECASE
        )

    def update(self, subject: str = None, relation: str = None, obj: str = None,
               statement_type: str = "statement"):
        """Update context after processing a statement."""
        if subject:
            self.last_subject = subject
            # Update topic if it's a new main subject
            if self._is_topic_change(subject):
                if self.current_topic:
                    self.topic_stack.append(self.current_topic)
                self.current_topic = subject
            # Track entity with salience
            self.add_entity(subject, role='subject')

        if obj:
            self.last_object = obj
            # Track object entity
            self.add_entity(obj, role='object')

        if relation:
            self.last_relation = relation

        # Track statement
        if subject or obj:
            self.recent_statements.append({
                "subject": subject,
                "relation": relation,
                "object": obj,
                "type": statement_type
            })

        # Advance turn for salience decay
        self.next_turn()

    def _is_topic_change(self, subject: str) -> bool:
        """Detect if this is a topic change."""
        if not self.current_topic:
            return True
        # Different subject that's not a pronoun
        if subject.lower() not in ["it", "they", "them", "this", "that", "he", "she"]:
            if subject.lower() != self.current_topic.lower():
                return True
        return False

    def set_knowledge_ref(self, knowledge_graph):
        """Set reference to knowledge graph for semantic checking."""
        self._knowledge_ref = knowledge_graph

    def add_entity(self, text: str, role: str = 'other'):
        """
        Track a mentioned entity with salience scoring.

        Args:
            text: The entity text
            role: 'subject', 'object', or 'other'
        """
        # Decay existing entities
        for entity in self.entity_mentions:
            entity.decay(self.current_turn)

        # Check properties
        is_animate = bool(self._animate_patterns.search(text))
        is_plural = bool(self._plural_patterns.search(text))

        # Add new mention
        mention = EntityMention(
            text=text,
            role=role,
            turn=self.current_turn,
            is_animate=is_animate,
            is_plural=is_plural
        )
        self.entity_mentions.append(mention)

        # Keep only recent mentions (avoid memory bloat)
        if len(self.entity_mentions) > 20:
            # Keep highest salience ones
            self.entity_mentions.sort(key=lambda x: x.salience, reverse=True)
            self.entity_mentions = self.entity_mentions[:15]

    def get_candidates(self, pronoun: str) -> List[EntityMention]:
        """
        Get candidate antecedents for a pronoun based on constraints.

        Implements Hobbs-style constraints:
        - 'he/she' -> animate entities
        - 'it' -> inanimate or unknown
        - 'they/them' -> plural or animate
        """
        candidates = []
        pronoun_lower = pronoun.lower()

        for entity in self.entity_mentions:
            score = entity.salience

            # Apply constraints
            if pronoun_lower in ['he', 'she']:
                # Require animate
                if entity.is_animate is False:
                    continue
                if entity.is_animate is True:
                    score += 1.0  # Bonus for matching

            elif pronoun_lower == 'it':
                # Prefer inanimate
                if entity.is_animate is True:
                    score -= 0.5  # Penalty but don't exclude
                elif entity.is_animate is False:
                    score += 0.5  # Bonus

            elif pronoun_lower in ['they', 'them']:
                # Prefer plural
                if entity.is_plural:
                    score += 1.0

            elif pronoun_lower in ['this', 'these']:
                # Prefer recent
                recency_bonus = max(0, 2.0 - (self.current_turn - entity.turn) * 0.5)
                score += recency_bonus

            candidates.append((entity, score))

        # Sort by score
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in candidates]

    def resolve_with_semantics(self, pronoun: str, verb: str = None) -> Optional[str]:
        """
        Resolve pronoun using semantic fit from knowledge graph.

        Example: "The cat saw the mouse. It ran away."
        - If we know mice run and cats chase, 'it' likely = mouse
        """
        candidates = self.get_candidates(pronoun)

        if not candidates:
            return None

        if len(candidates) == 1:
            return candidates[0].text

        # If we have a verb, check semantic fit
        if verb and self._knowledge_ref:
            for candidate in candidates:
                entity_text = candidate.text.lower().replace(' ', '_')
                # Check if entity can do this action
                abilities = self._knowledge_ref.get(entity_text, {}).get('can', [])
                if verb in abilities or any(verb in a for a in abilities):
                    return candidate.text

        # Default to highest salience
        return candidates[0].text if candidates else None

    def resolve_pronoun(self, text: str) -> str:
        """
        Replace pronouns with their referents using enhanced resolution.

        Uses:
        1. Salience scoring (subjects > objects > others)
        2. Recency weighting
        3. Animacy constraints (he/she vs it)
        4. Semantic fit when possible
        """
        if not self.entity_mentions and not self.last_subject:
            return text

        resolved = text
        pronoun_pattern = re.compile(
            r'\b(he|she|it|they|them|this|that|these|those)\b',
            re.IGNORECASE
        )

        def replace_match(match):
            pronoun = match.group(0)
            pronoun_lower = pronoun.lower()

            # Try enhanced resolution first
            if self.entity_mentions:
                referent = self.resolve_with_semantics(pronoun_lower)
                if referent:
                    # Preserve case
                    if pronoun[0].isupper():
                        return referent.capitalize()
                    return referent

            # Fallback to simple resolution
            fallback = {
                "they": self.last_subject,
                "them": self.last_subject,
                "it": self.last_subject,
                "he": self.last_subject,
                "she": self.last_subject,
                "this": self.last_subject,
                "that": self.last_object or self.last_subject,
                "these": self.last_subject,
                "those": self.last_object or self.last_subject,
            }

            referent = fallback.get(pronoun_lower)
            if referent:
                if pronoun[0].isupper():
                    return referent.capitalize()
                return referent

            return pronoun  # No resolution possible

        resolved = pronoun_pattern.sub(replace_match, text)
        return resolved

    def next_turn(self):
        """Advance to next conversation turn."""
        self.current_turn += 1

    def get_salient_entities(self, limit: int = 5) -> List[Tuple[str, float]]:
        """Get most salient entities currently in context."""
        # Decay all first
        for entity in self.entity_mentions:
            entity.decay(self.current_turn)

        # Sort by salience
        sorted_entities = sorted(
            self.entity_mentions,
            key=lambda x: x.salience,
            reverse=True
        )

        return [(e.text, e.salience) for e in sorted_entities[:limit]]

    def get_context_summary(self) -> dict:
        """Get current context state."""
        return {
            "topic": self.current_topic,
            "last_subject": self.last_subject,
            "last_object": self.last_object,
            "last_relation": self.last_relation,
            "mode": self.mode,
            "pending_clarification": self.pending_clarification,
            "recent_count": len(self.recent_statements)
        }

    def set_clarification(self, question: str, about: str):
        """Set a pending clarification request."""
        self.pending_clarification = {
            "question": question,
            "about": about
        }
        self.mode = "clarifying"

    def clear_clarification(self):
        """Clear pending clarification."""
        self.pending_clarification = None
        self.mode = "normal"

    def add_correction(self, original: str, corrected: str, relation: str = None):
        """Track a user correction."""
        self.corrections.append({
            "original": original,
            "corrected": corrected,
            "relation": relation
        })

    def get_recent_about(self, subject: str, limit: int = 3) -> list:
        """Get recent statements about a subject."""
        results = []
        for stmt in reversed(self.recent_statements):
            if stmt["subject"] and subject.lower() in stmt["subject"].lower():
                results.append(stmt)
                if len(results) >= limit:
                    break
        return results

    def is_follow_up(self, text: str) -> bool:
        """Check if this is a follow-up to previous statement."""
        indicators = [
            "also", "too", "and", "plus", "another", "more",
            "but", "however", "although", "except",
            "because", "since", "so", "therefore",
            "what about", "how about", "and what"
        ]
        text_lower = text.lower()
        return any(text_lower.startswith(ind) or f" {ind} " in text_lower
                   for ind in indicators)

    def detect_mode(self, text: str) -> str:
        """Detect the conversation mode from text."""
        text_lower = text.lower()

        # Correction mode
        if any(w in text_lower for w in ["no,", "wrong", "incorrect", "actually", "not really"]):
            return "correcting"

        # Question mode
        if text.rstrip().endswith("?") or text_lower.startswith(("what", "where", "who", "why", "how", "can", "does", "is", "are")):
            return "questioning"

        # Teaching mode (statements)
        return "teaching"
