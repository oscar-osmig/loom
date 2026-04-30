"""
Curiosity Engine for Loom.
Generates high-value questions to strengthen the knowledge graph.

The engine identifies:
1. Open questions (has_open_question facts)
2. Contradictions needing resolution
3. Chain gaps (missing causal/relational bridges)
4. Low-confidence, high-centrality entities

Also manages CuriosityNodes - special "?_<topic>" nodes created when Loom
encounters unknown concepts. These nodes:
- Track activation level (how strongly we want to know about this)
- Have timeout for cleanup (don't clutter knowledge indefinitely)
- Store hypotheses as linked_facts before resolution
- Use spreading activation to discover related concepts

Questions are ranked by expected utility and surfaced to the user.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Set, Dict, TYPE_CHECKING
from enum import Enum
from collections import defaultdict
import time

if TYPE_CHECKING:
    from .brain import Loom


# ==================== CURIOSITY NODES ====================

class CuriosityNodeStatus(Enum):
    """Lifecycle status of a curiosity node."""
    ACTIVE = "active"           # Just created, actively seeking info
    EXPLORING = "exploring"     # Spreading activation in progress
    HYPOTHESIZING = "hypothesizing"  # Generating hypotheses
    RESOLVED = "resolved"       # Answer found, ready for cleanup
    EXPIRED = "expired"         # Timed out without resolution


@dataclass
class CuriosityNode:
    """
    A special node representing an unknown concept Loom wants to learn about.

    Named with ?_<topic> format in the knowledge graph.

    Lifecycle:
    1. Creation - When unknown concept encountered
    2. Exploration - Spreading activation finds related concepts
    3. Hypothesizing - Generate possible facts based on similar concepts
    4. Resolution - User confirms or provides answer
    5. Cleanup - Remove node or convert to real knowledge
    """
    topic: str                          # The unknown concept (without ?_ prefix)
    activation: float = 1.0             # How strongly we want to know (0.0-1.0)
    timeout: float = 300.0              # Seconds before expiry (default 5 min)
    created_at: float = field(default_factory=time.time)
    attempts: int = 0                   # How many times we've tried to resolve
    max_attempts: int = 5               # Give up after this many failed attempts
    linked_facts: List[dict] = field(default_factory=list)  # Hypotheses
    status: CuriosityNodeStatus = CuriosityNodeStatus.ACTIVE
    related_concepts: Set[str] = field(default_factory=set)  # From spreading activation
    source_context: str = ""            # What triggered this curiosity
    status_changed_at: float = field(default_factory=time.time)  # When status last changed

    @property
    def node_name(self) -> str:
        """Get the ?_<topic> node name."""
        return f"?_{self.topic}"

    @property
    def age(self) -> float:
        """Seconds since creation."""
        return time.time() - self.created_at

    @property
    def is_expired(self) -> bool:
        """Check if node has timed out."""
        return self.age > self.timeout or self.attempts >= self.max_attempts

    def decay_activation(self, rate: float = 0.1):
        """Reduce activation over time."""
        self.activation = max(0.0, self.activation - rate)

    def boost_activation(self, amount: float = 0.2):
        """Boost activation when concept is mentioned again."""
        self.activation = min(1.0, self.activation + amount)

    def add_hypothesis(self, relation: str, value: str, confidence: float = 0.5):
        """Add a hypothesized fact about this concept."""
        self.linked_facts.append({
            "relation": relation,
            "value": value,
            "confidence": confidence,
            "created_at": time.time()
        })

    def get_best_hypothesis(self) -> Optional[dict]:
        """Get highest confidence hypothesis."""
        if not self.linked_facts:
            return None
        return max(self.linked_facts, key=lambda h: h.get("confidence", 0))


class CuriosityNodeManager:
    """
    Manages the lifecycle of curiosity nodes.

    Responsibilities:
    - Create nodes for unknown concepts
    - Run exploration via spreading activation
    - Generate hypotheses from similar concepts
    - Clean up expired/resolved nodes
    - Convert resolved nodes to real knowledge
    """

    def __init__(self, loom: "Loom"):
        self.loom = loom
        self._nodes: Dict[str, CuriosityNode] = {}  # topic -> node
        self._last_cleanup = time.time()
        self._cleanup_interval = 60.0  # Check for expired nodes every minute

    def create_node(self, topic: str, context: str = "") -> CuriosityNode:
        """
        Create a curiosity node for an unknown concept.

        Args:
            topic: The unknown concept name
            context: What triggered this curiosity (e.g., "user asked about X")

        Returns:
            The created CuriosityNode
        """
        # Normalize topic
        topic_normalized = topic.lower().strip().replace(" ", "_")

        # If node already exists, boost its activation
        if topic_normalized in self._nodes:
            existing = self._nodes[topic_normalized]
            existing.boost_activation()
            existing.attempts += 1
            if self.loom.verbose:
                print(f"       [curiosity boosted: ?_{topic_normalized} ({existing.activation:.2f})]")
            return existing

        # Create new node
        node = CuriosityNode(
            topic=topic_normalized,
            source_context=context
        )
        self._nodes[topic_normalized] = node

        # Add to knowledge graph as ?_<topic>
        self.loom.storage.add_fact(
            node.node_name, "is", "curiosity_node", "low",
            context="curiosity",
            properties={"source_type": "curiosity", "topic": topic_normalized}
        )
        self.loom._invalidate_cache()

        if self.loom.verbose:
            print(f"       [curiosity created: ?_{topic_normalized}]")

        return node

    def explore_node(self, topic: str) -> List[str]:
        """
        Use spreading activation to find concepts related to the unknown topic.

        Returns list of related concept names.
        """
        if topic not in self._nodes:
            return []

        node = self._nodes[topic]
        node.status = CuriosityNodeStatus.EXPLORING
        node.status_changed_at = time.time()

        related = []

        # Check if any existing concepts contain this topic as substring
        for entity in self.loom.knowledge.keys():
            if entity.startswith("?_"):
                continue  # Skip other curiosity nodes
            if topic in entity or entity in topic:
                related.append(entity)
                node.related_concepts.add(entity)

        # Use activation network to find primed concepts
        if hasattr(self.loom, 'activation'):
            # Activate the topic
            self.loom.activation.activate(topic, amount=1.0)

            # Get concepts that get activated
            for entity in self.loom.knowledge.keys():
                if entity.startswith("?_"):
                    continue
                activation_level = self.loom.activation.get_activation(entity)
                if activation_level > 0.3:  # Threshold for relevance
                    related.append(entity)
                    node.related_concepts.add(entity)

        # Deduplicate
        related = list(set(related))

        if self.loom.verbose and related:
            print(f"       [curiosity explored: ?_{topic} -> {related[:5]}...]")

        return related

    def generate_hypotheses(self, topic: str) -> List[dict]:
        """
        Generate hypotheses about the unknown concept based on similar concepts.

        Returns list of hypothesized facts.
        """
        if topic not in self._nodes:
            return []

        node = self._nodes[topic]
        node.status = CuriosityNodeStatus.HYPOTHESIZING
        node.status_changed_at = time.time()

        # First explore if not done
        if not node.related_concepts:
            self.explore_node(topic)

        hypotheses = []

        # Look at related concepts for patterns
        property_counts = defaultdict(lambda: defaultdict(int))  # rel -> value -> count

        for related in node.related_concepts:
            related_facts = self.loom.knowledge.get(related, {})
            for relation, values in related_facts.items():
                if relation in ["is", "has", "can", "color", "lives_in", "eats"]:
                    for value in values:
                        property_counts[relation][value] += 1

        # Create hypotheses from common patterns
        for relation, value_counts in property_counts.items():
            for value, count in value_counts.items():
                if count >= 2:  # At least 2 related concepts share this property
                    confidence = min(0.9, count * 0.2)  # Higher count = higher confidence
                    node.add_hypothesis(relation, value, confidence)
                    hypotheses.append({
                        "subject": node.node_name,
                        "relation": relation,
                        "object": value,
                        "confidence": confidence
                    })

        if self.loom.verbose and hypotheses:
            print(f"       [curiosity hypotheses: ?_{topic} has {len(hypotheses)} guesses]")

        return hypotheses

    def resolve_node(self, topic: str, facts: List[dict] = None) -> bool:
        """
        Resolve a curiosity node with actual knowledge.

        Args:
            topic: The topic to resolve
            facts: Optional list of facts to add (each dict has subject, relation, object)

        Returns:
            True if resolved, False if node not found
        """
        if topic not in self._nodes:
            return False

        node = self._nodes[topic]
        node.status = CuriosityNodeStatus.RESOLVED

        # If facts provided, add them to knowledge
        if facts:
            for fact in facts:
                self.loom.add_fact(
                    fact.get("subject", topic),
                    fact["relation"],
                    fact["object"],
                    confidence="high"  # User-confirmed
                )

        # Remove curiosity node from knowledge graph
        self.loom.storage.retract_fact(node.node_name, "is", "curiosity_node")
        self.loom._invalidate_cache()

        # Remove from manager
        del self._nodes[topic]

        if self.loom.verbose:
            print(f"       [curiosity resolved: ?_{topic}]")

        return True

    def resolve_from_knowledge(self, brain) -> int:
        """
        Resolve curiosity nodes whose questions are now answered by
        existing knowledge in the brain.

        Iterates all ACTIVE nodes and checks whether the brain has facts
        about the node's concept. If facts exist, the curiosity is satisfied
        and the node is marked RESOLVED.

        Args:
            brain: The Loom brain instance to check knowledge against.

        Returns:
            Number of nodes resolved.
        """
        resolved_count = 0
        to_resolve = []

        for topic, node in self._nodes.items():
            if node.status != CuriosityNodeStatus.ACTIVE:
                continue

            # Check if the brain now has facts about this concept
            concept_facts = brain.knowledge.get(topic, {})
            if not concept_facts:
                continue

            # Check if there are meaningful relations (not just curiosity_node marker)
            meaningful = {r: v for r, v in concept_facts.items()
                         if r != "is" or v != ["curiosity_node"]}
            if meaningful:
                to_resolve.append(topic)

        for topic in to_resolve:
            node = self._nodes[topic]
            node.status = CuriosityNodeStatus.RESOLVED
            node.status_changed_at = time.time()

            # Remove curiosity node marker from knowledge graph
            self.loom.storage.retract_fact(node.node_name, "is", "curiosity_node")
            del self._nodes[topic]
            resolved_count += 1

            if self.loom.verbose:
                print(f"       [curiosity resolved from knowledge: ?_{topic}]")

        if resolved_count:
            self.loom._invalidate_cache()

        return resolved_count

    def cleanup_expired(self) -> int:
        """
        Remove expired curiosity nodes and unstick stalled ones.

        - Expired nodes (timed out or max attempts) are removed.
        - Nodes stuck in EXPLORING for >10 minutes are moved back to ACTIVE.
        - Nodes stuck in HYPOTHESIZING for >30 minutes are moved back to ACTIVE.

        Returns number of nodes cleaned up (expired only).
        """
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return 0

        self._last_cleanup = now
        expired = []

        for topic, node in self._nodes.items():
            # Decay activation
            node.decay_activation(rate=0.05)

            if node.is_expired:
                expired.append(topic)
                node.status = CuriosityNodeStatus.EXPIRED
                continue

            # Unstick nodes that have been EXPLORING too long (>10 minutes)
            if (node.status == CuriosityNodeStatus.EXPLORING and
                    now - node.status_changed_at > 600):
                node.status = CuriosityNodeStatus.ACTIVE
                node.status_changed_at = now
                if self.loom.verbose:
                    print(f"       [curiosity unstuck: ?_{topic} EXPLORING -> ACTIVE]")

            # Unstick nodes that have been HYPOTHESIZING too long (>30 minutes)
            if (node.status == CuriosityNodeStatus.HYPOTHESIZING and
                    now - node.status_changed_at > 1800):
                node.status = CuriosityNodeStatus.ACTIVE
                node.status_changed_at = now
                if self.loom.verbose:
                    print(f"       [curiosity unstuck: ?_{topic} HYPOTHESIZING -> ACTIVE]")

        # Remove expired nodes
        for topic in expired:
            node = self._nodes[topic]
            # Remove from knowledge graph
            self.loom.storage.retract_fact(node.node_name, "is", "curiosity_node")
            del self._nodes[topic]

            if self.loom.verbose:
                print(f"       [curiosity expired: ?_{topic}]")

        if expired:
            self.loom._invalidate_cache()

        return len(expired)

    def get_node(self, topic: str) -> Optional[CuriosityNode]:
        """Get a curiosity node by topic."""
        return self._nodes.get(topic.lower().strip().replace(" ", "_"))

    def get_all_nodes(self) -> List[CuriosityNode]:
        """Get all active curiosity nodes."""
        return list(self._nodes.values())

    def get_active_topics(self) -> List[str]:
        """Get list of topics we're curious about."""
        return [node.topic for node in self._nodes.values()
                if node.status in (CuriosityNodeStatus.ACTIVE, CuriosityNodeStatus.EXPLORING)]

    def has_curiosity(self, topic: str) -> bool:
        """Check if we have a curiosity node for a topic."""
        return topic.lower().strip().replace(" ", "_") in self._nodes

    def format_curiosity_question(self, topic: str) -> Optional[str]:
        """Format a question about the curiosity topic."""
        node = self.get_node(topic)
        if not node:
            return None

        # Get best hypothesis if any
        hypothesis = node.get_best_hypothesis()

        if hypothesis:
            return f"I think {topic} might {hypothesis['relation']} {hypothesis['value']}. Is that right?"
        else:
            return f"I don't know about '{topic}'. Can you tell me about it?"


class QuestionType(Enum):
    """Types of questions the curiosity engine can generate."""
    OPEN_QUESTION = "open_question"           # Existing has_open_question fact
    CONTRADICTION = "contradiction"            # Conflicting facts need resolution
    CHAIN_GAP = "chain_gap"                   # Missing link in causal chain
    CONFIRM_INFERENCE = "confirm_inference"   # Verify an inferred fact
    LOW_CONFIDENCE = "low_confidence"         # Strengthen weak knowledge
    MISSING_PROPERTY = "missing_property"     # Entity missing expected property
    CAUSAL_ORIGIN = "causal_origin"          # What causes X?
    CAUSAL_EFFECT = "causal_effect"          # What does X cause?
    CONFIRM_RULE = "confirm_rule"            # Confirm a candidate rule


@dataclass
class Question:
    """A generated question with metadata."""
    text: str
    question_type: QuestionType
    priority: float = 0.0  # Higher = more important
    related_facts: List[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def __hash__(self):
        return hash(self.text)

    def __eq__(self, other):
        if not isinstance(other, Question):
            return False
        return self.text == other.text


class QuestionGenerator:
    """
    Generates questions to strengthen the knowledge graph.

    Runs in background cycles to identify gaps, contradictions,
    and opportunities for knowledge expansion.
    """

    def __init__(self, loom: "Loom"):
        self.loom = loom
        self._question_queue: List[Question] = []
        self._asked_questions: Set[str] = set()  # Track asked to avoid repeats
        self._last_cycle = 0.0

        # Weights for question priority scoring
        self.weights = {
            QuestionType.CONTRADICTION: 10.0,      # Highest priority
            QuestionType.CONFIRM_RULE: 6.0,        # Confirm candidate rules
            QuestionType.CONFIRM_INFERENCE: 5.0,   # Verify inferences
            QuestionType.CHAIN_GAP: 4.0,           # Fill causal gaps
            QuestionType.LOW_CONFIDENCE: 3.0,      # Strengthen weak facts
            QuestionType.OPEN_QUESTION: 3.0,       # Address open questions
            QuestionType.CAUSAL_ORIGIN: 2.0,       # Explore causes
            QuestionType.CAUSAL_EFFECT: 2.0,       # Explore effects
            QuestionType.MISSING_PROPERTY: 1.0,    # Fill missing properties
        }

    def run_cycle(self):
        """
        Run a full question generation cycle.
        Called periodically from the background loop.
        """
        self._last_cycle = time.time()

        # Collect questions from various sources
        questions = []

        # 1. Open questions from knowledge graph
        questions.extend(self._collect_open_questions())

        # 2. Contradiction-based questions
        questions.extend(self._collect_contradiction_questions())

        # 3. Chain gap questions
        questions.extend(self._collect_chain_gap_questions())

        # 4. Inference confirmation questions
        questions.extend(self._collect_inference_questions())

        # 5. Low confidence questions
        questions.extend(self._collect_low_confidence_questions())

        # 6. Missing property questions
        questions.extend(self._collect_missing_property_questions())

        # 7. Causal exploration questions
        questions.extend(self._collect_causal_questions())

        # 8. Rule confirmation questions
        questions.extend(self._collect_rule_questions())

        # Filter out already-asked questions
        new_questions = [q for q in questions if q.text not in self._asked_questions]

        # Score and rank questions
        for q in new_questions:
            q.priority = self._calculate_priority(q)

        # Sort by priority (descending)
        new_questions.sort(key=lambda q: q.priority, reverse=True)

        # Update queue (keep top N)
        self._question_queue = new_questions[:20]

        if self.loom.verbose and new_questions:
            print(f"       [curiosity: {len(new_questions)} questions generated]")

    def get_next_question(self) -> Optional[Question]:
        """Get the highest priority question."""
        if not self._question_queue:
            return None
        return self._question_queue[0]

    def get_top_questions(self, n: int = 3) -> List[Question]:
        """Get top N questions by priority."""
        return self._question_queue[:n]

    def mark_asked(self, question: Question):
        """Mark a question as asked (avoid repeating)."""
        self._asked_questions.add(question.text)
        if question in self._question_queue:
            self._question_queue.remove(question)

    def mark_answered(self, question: Question):
        """Mark a question as answered."""
        self.mark_asked(question)

    # ==================== QUESTION COLLECTORS ====================

    def _collect_open_questions(self) -> List[Question]:
        """Collect questions from has_open_question facts."""
        questions = []

        for subject, relations in self.loom.knowledge.items():
            if "has_open_question" in relations:
                for question_text in relations["has_open_question"]:
                    questions.append(Question(
                        text=question_text,
                        question_type=QuestionType.OPEN_QUESTION,
                        related_facts=[{"subject": subject, "relation": "has_open_question", "object": question_text}]
                    ))

        return questions

    def _collect_contradiction_questions(self) -> List[Question]:
        """Generate questions to resolve contradictions."""
        questions = []
        conflicts = self.loom.storage.get_conflicts()

        for conflict in conflicts:
            fact1 = conflict.get("fact1", "")
            fact2 = conflict.get("fact2", "")

            question_text = f"There's a conflict: '{fact1}' vs '{fact2}'. Which is correct?"
            questions.append(Question(
                text=question_text,
                question_type=QuestionType.CONTRADICTION,
                related_facts=[conflict]
            ))

        return questions

    def _collect_chain_gap_questions(self) -> List[Question]:
        """Find gaps in causal/relational chains."""
        questions = []
        causal_relations = ["causes", "leads_to", "results_in"]

        # Build a graph of causal relationships
        causal_graph = defaultdict(set)
        for subject, relations in self.loom.knowledge.items():
            for rel in causal_relations:
                if rel in relations:
                    for obj in relations[rel]:
                        causal_graph[subject].add(obj)

        # Find nodes with incoming but no outgoing (potential gaps)
        all_effects = set()
        for effects in causal_graph.values():
            all_effects.update(effects)

        # Effects that don't cause anything else (dead ends)
        for effect in all_effects:
            if effect not in causal_graph or not causal_graph[effect]:
                # Check if this is truly a terminal effect or a gap
                if self._is_likely_intermediate(effect):
                    question_text = f"What does {effect} cause or lead to?"
                    questions.append(Question(
                        text=question_text,
                        question_type=QuestionType.CHAIN_GAP,
                        related_facts=[{"subject": effect, "relation": "causes", "object": "?"}]
                    ))

        # Causes with no known origin
        all_causes = set(causal_graph.keys())
        caused_by_something = set()
        for effects in causal_graph.values():
            caused_by_something.update(effects)

        root_causes = all_causes - caused_by_something
        for cause in root_causes:
            if self._is_likely_has_cause(cause):
                question_text = f"What causes {cause}?"
                questions.append(Question(
                    text=question_text,
                    question_type=QuestionType.CAUSAL_ORIGIN,
                    related_facts=[{"subject": "?", "relation": "causes", "object": cause}]
                ))

        return questions[:5]  # Limit to avoid overwhelming

    def _collect_inference_questions(self) -> List[Question]:
        """Generate questions to confirm inferred facts."""
        questions = []

        # Get inferred facts from storage
        inferred = self.loom.storage.get_inferred_facts()

        for fact in inferred:
            subject = fact.get("subject", "")
            relation = fact.get("relation", "")
            obj = fact.get("object", "")
            confidence = fact.get("confidence", "medium")

            # Only ask about medium/low confidence inferences
            if confidence != "high":
                # Format with readable text (replace underscores)
                subj_display = subject.replace("_", " ")
                obj_display = obj.replace("_", " ")
                rel_display = relation.replace("_", " ")

                # Format the question based on relation type
                if relation == "causes":
                    question_text = f"I inferred that {subj_display} causes {obj_display}. Is this correct?"
                elif relation == "is":
                    question_text = f"I inferred that {subj_display} is a type of {obj_display}. Is this correct?"
                elif relation == "has":
                    question_text = f"I inferred that {subj_display} has {obj_display}. Is this correct?"
                else:
                    question_text = f"I inferred: {subj_display} {rel_display} {obj_display}. Is this correct?"

                questions.append(Question(
                    text=question_text,
                    question_type=QuestionType.CONFIRM_INFERENCE,
                    related_facts=[fact]
                ))

        return questions[:3]  # Limit confirmation questions

    def _collect_low_confidence_questions(self) -> List[Question]:
        """Find low-confidence facts that could be strengthened."""
        questions = []

        for subject, relations in self.loom.knowledge.items():
            for relation, objects in relations.items():
                for obj in objects:
                    confidence = self.loom.storage.get_confidence(subject, relation, obj)
                    if confidence == "low":
                        question_text = f"Can you confirm: {subject} {relation} {obj}?"
                        questions.append(Question(
                            text=question_text,
                            question_type=QuestionType.LOW_CONFIDENCE,
                            related_facts=[{"subject": subject, "relation": relation, "object": obj}]
                        ))

        return questions[:3]

    def _collect_missing_property_questions(self) -> List[Question]:
        """Find entities missing properties their category has."""
        questions = []
        property_relations = ["has", "can", "color", "lives_in", "eats"]

        for entity, relations in self.loom.knowledge.items():
            # Get entity's categories
            categories = relations.get("is", []) + relations.get("is_a", [])

            for category in categories:
                category_data = self.loom.knowledge.get(category, {})

                for prop_rel in property_relations:
                    category_props = set(category_data.get(prop_rel, []))
                    entity_props = set(relations.get(prop_rel, []))

                    # Properties the category has but entity doesn't
                    missing = category_props - entity_props

                    for prop in missing:
                        # Format question with proper grammar
                        prop_display = prop.replace("_", " ")
                        entity_display = entity.replace("_", " ")
                        category_display = category.replace("_", " ")
                        question_text = f"Do {entity_display} {prop_rel.replace('_', ' ')} {prop_display}? (Like {category_display})"
                        questions.append(Question(
                            text=question_text,
                            question_type=QuestionType.MISSING_PROPERTY,
                            related_facts=[
                                {"subject": entity, "relation": "is", "object": category},
                                {"subject": category, "relation": prop_rel, "object": prop}
                            ]
                        ))

        return questions[:3]

    def _collect_causal_questions(self) -> List[Question]:
        """Generate questions exploring causal relationships."""
        questions = []

        # Find entities that appear in many relations (high centrality)
        entity_counts = defaultdict(int)
        for subject, relations in self.loom.knowledge.items():
            entity_counts[subject] += len(relations)
            for rel, objects in relations.items():
                for obj in objects:
                    entity_counts[obj] += 1

        # Sort by centrality
        central_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        for entity, count in central_entities:
            entity_data = self.loom.knowledge.get(entity, {})

            # If no known causes, ask
            if "causes" not in entity_data and "caused_by" not in entity_data:
                has_effects = any(rel in entity_data for rel in ["causes", "leads_to"])
                if not has_effects:
                    question_text = f"What effects does {entity} have? What does it cause?"
                    questions.append(Question(
                        text=question_text,
                        question_type=QuestionType.CAUSAL_EFFECT,
                        related_facts=[{"subject": entity, "relation": "causes", "object": "?"}]
                    ))

        return questions[:2]

    def _collect_rule_questions(self) -> List[Question]:
        """Generate questions to confirm candidate rules."""
        questions = []

        # Check if rule memory is available
        if not hasattr(self.loom, 'rule_memory') or self.loom.rule_memory is None:
            return questions

        # Get candidate rules awaiting confirmation
        candidate_rules = self.loom.rule_memory.get_candidate_rules()

        for rule in candidate_rules:
            # Format the rule for human readability
            premises_str = " and ".join(
                f"{p.subject_var.replace('?', '')} {p.relation} {p.object_var.replace('?', '')}"
                for p in rule.premises
            )
            conclusion_str = f"{rule.conclusion.subject_var.replace('?', '')} {rule.conclusion.relation} {rule.conclusion.object_var.replace('?', '')}"

            # Replace variable names for readability
            premises_str = premises_str.replace("X1", "something").replace("X2", "something else")
            conclusion_str = conclusion_str.replace("X1", "it").replace("X2", "it")

            question_text = (
                f"I noticed a pattern: when {premises_str}, "
                f"then {conclusion_str}. Is this a valid rule?"
            )

            questions.append(Question(
                text=question_text,
                question_type=QuestionType.CONFIRM_RULE,
                related_facts=[{
                    "rule_id": rule.rule_id,
                    "premises": [str(p) for p in rule.premises],
                    "conclusion": str(rule.conclusion),
                    "support_count": rule.support_count
                }]
            ))

        return questions[:3]  # Limit rule questions

    # ==================== UTILITY METHODS ====================

    def _calculate_priority(self, question: Question) -> float:
        """Calculate question priority based on type and context."""
        base_priority = self.weights.get(question.question_type, 1.0)

        # Boost for recency of related facts
        recency_boost = 0.0
        for fact in question.related_facts:
            if isinstance(fact, dict):
                subj = fact.get("subject", "")
                if subj in [f[0] for f in self.loom.recent[-10:]]:
                    recency_boost += 1.0

        # Boost for high-centrality entities
        centrality_boost = 0.0
        for fact in question.related_facts:
            if isinstance(fact, dict):
                subj = fact.get("subject", "")
                obj = fact.get("object", "")
                for entity in [subj, obj]:
                    if entity and entity in self.loom.knowledge:
                        centrality_boost += len(self.loom.knowledge[entity]) * 0.1

        # Spaced repetition: boost priority for facts not seen recently
        staleness_boost = 0.0
        if hasattr(self.loom, 'connection_times'):
            now = time.time()
            for fact in question.related_facts:
                if not isinstance(fact, dict):
                    continue
                subj = fact.get("subject", "")
                rel = fact.get("relation", "")
                obj = fact.get("object", "")
                if subj and rel and obj:
                    key = (subj, rel, obj)
                    last_used = self.loom.connection_times.get(key)
                    if last_used is not None:
                        age = now - last_used
                        if age > 3600:
                            staleness_boost += 2.0
                        elif age > 600:
                            staleness_boost += 1.0

        return base_priority + recency_boost + min(centrality_boost, 2.0) + min(staleness_boost, 4.0)

    def _is_likely_intermediate(self, entity: str) -> bool:
        """Check if entity is likely an intermediate in a causal chain."""
        # Entities that are states/conditions are likely intermediate
        state_indicators = ["wet", "hot", "cold", "dry", "broken", "active", "full", "empty"]
        entity_lower = entity.lower()
        return any(ind in entity_lower for ind in state_indicators)

    def _is_likely_has_cause(self, entity: str) -> bool:
        """Check if entity likely has a cause we should ask about."""
        # Most things have causes, but skip basic concepts
        skip_patterns = ["self", "system", "loom"]
        entity_lower = entity.lower()
        return not any(pat in entity_lower for pat in skip_patterns)

    def get_queue_size(self) -> int:
        """Get number of questions in queue."""
        return len(self._question_queue)

    def clear_queue(self):
        """Clear all pending questions."""
        self._question_queue.clear()

    def format_question_prompt(self, question: Question) -> str:
        """Format a question for display to user."""
        type_emoji = {
            QuestionType.CONTRADICTION: "[!]",
            QuestionType.CONFIRM_RULE: "[R]",
            QuestionType.CONFIRM_INFERENCE: "[?]",
            QuestionType.CHAIN_GAP: "[~]",
            QuestionType.LOW_CONFIDENCE: "[?]",
            QuestionType.OPEN_QUESTION: "[Q]",
            QuestionType.CAUSAL_ORIGIN: "[<]",
            QuestionType.CAUSAL_EFFECT: "[>]",
            QuestionType.MISSING_PROPERTY: "[+]",
        }
        prefix = type_emoji.get(question.question_type, "[?]")
        return f"{prefix} {question.text}"
