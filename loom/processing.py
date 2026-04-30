"""
Loom Processing Module - Activation-based processing and Hebbian strengthening.

Contains:
- HebbianMixin: Connection weight management (strengthen, weaken, decay)
- ProcessingMixin: Text and paragraph processing with activation
"""

import time
import re
from typing import List, Dict, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .brain import Loom

from .normalizer import normalize
from .simplifier import SentenceSimplifier
from .advanced_simplifier import AdvancedSimplifier

# Hebbian learning constants
INITIAL_WEIGHT = 1.0          # Starting connection strength
STRENGTHENING_FACTOR = 0.2    # How much to strengthen on co-activation
DECAY_FACTOR = 0.05           # How much to decay unused connections
MAX_WEIGHT = 5.0              # Maximum connection strength
MIN_WEIGHT = 0.1              # Minimum before pruning


class HebbianMixin:
    """Mixin class providing Hebbian learning capabilities for Loom."""

    def get_connection_weight(self: "Loom", subject: str, relation: str, obj: str) -> float:
        """Get the strength of a connection."""
        key = (normalize(subject), relation.lower(), normalize(obj))
        if key in getattr(self, 'dormant_connections', set()):
            return 0.0
        return self.connection_weights.get(key, INITIAL_WEIGHT)

    def _get_recent_avg_weight(self: "Loom", n: int = 20) -> float:
        """
        Compute average weight of the N most recently strengthened connections.
        Used as the BCM sliding threshold to prevent runaway LTP.
        """
        if not self.connection_times:
            return INITIAL_WEIGHT
        dormant = getattr(self, 'dormant_connections', set())
        recent = sorted(
            ((k, t) for k, t in self.connection_times.items() if k not in dormant),
            key=lambda x: x[1], reverse=True
        )[:n]
        if not recent:
            return INITIAL_WEIGHT
        weights = [self.connection_weights.get(key, INITIAL_WEIGHT) for key, _ in recent]
        return sum(weights) / len(weights)

    def reactivate_connection(self: "Loom", key: Tuple[str, str, str]):
        dormant = getattr(self, 'dormant_connections', None)
        if dormant is None:
            self.dormant_connections = set()
            return
        if key in dormant:
            dormant.discard(key)
            self.connection_weights[key] = INITIAL_WEIGHT
            self.connection_times[key] = time.time()
            if self.verbose:
                print(f"       [reactivated connection: {key[0]} ~> {key[1]} ~> {key[2]}]")

    def strengthen_connection(self: "Loom", subject: str, relation: str, obj: str,
                              amount: float = STRENGTHENING_FACTOR):
        """
        Strengthen a connection (Hebbian: cells that fire together wire together).
        Uses BCM-style sliding threshold: strong connections get dampened (LTD-like),
        weak/new connections get boosted (LTP), preventing runaway dominant pathways.
        """
        key = (normalize(subject), relation.lower(), normalize(obj))
        if key in getattr(self, 'dormant_connections', set()):
            self.reactivate_connection(key)
        current = self.connection_weights.get(key, INITIAL_WEIGHT)

        # BCM sliding threshold based on recent activity
        threshold = self._get_recent_avg_weight() * 0.8
        if current > threshold:
            effective_amount = amount * 0.5   # LTD-like dampening for already-strong connections
        else:
            effective_amount = amount * 1.5   # LTP boost for weak/new connections

        new_weight = min(current + effective_amount, MAX_WEIGHT)
        self.connection_weights[key] = new_weight
        self.connection_times[key] = time.time()

        if self.verbose:
            print(f"       [strengthened: {subject} ~> {relation} ~> {obj} = {new_weight:.2f}]")

    def weaken_connection(self: "Loom", subject: str, relation: str, obj: str,
                          amount: float = DECAY_FACTOR):
        """Weaken a connection (decay from disuse)."""
        key = (normalize(subject), relation.lower(), normalize(obj))
        if key in getattr(self, 'dormant_connections', set()):
            return
        current = self.connection_weights.get(key, INITIAL_WEIGHT)
        new_weight = max(current - amount, MIN_WEIGHT)

        if new_weight <= MIN_WEIGHT:
            if key in self.connection_weights:
                self.connection_weights[key] = MIN_WEIGHT
                if not hasattr(self, 'dormant_connections'):
                    self.dormant_connections = set()
                self.dormant_connections.add(key)
                if self.verbose:
                    print(f"       [dormant: {subject} ~> {relation} ~> {obj}]")
        else:
            self.connection_weights[key] = new_weight

    def decay_all_connections(self: "Loom", elapsed_threshold: float = 60.0):
        """
        Decay connections that haven't been activated recently.
        Mimics biological synaptic pruning.
        """
        now = time.time()
        to_decay = []

        for key, last_time in list(self.connection_times.items()):
            elapsed = now - last_time
            if elapsed > elapsed_threshold:
                to_decay.append(key)

        for key in to_decay:
            subject, relation, obj = key
            self.weaken_connection(subject, relation, obj)

    def get_strong_connections(self: "Loom", threshold: float = 2.0) -> List[Tuple[str, str, str, float]]:
        """Get connections above a strength threshold."""
        dormant = getattr(self, 'dormant_connections', set())
        strong = []
        for key, weight in self.connection_weights.items():
            if key in dormant:
                continue
            if weight >= threshold:
                subject, relation, obj = key
                strong.append((subject, relation, obj, weight))
        # Sort by weight descending
        strong.sort(key=lambda x: x[3], reverse=True)
        return strong

    def show_weights(self: "Loom", min_weight: float = 1.5):
        """Display strong connection weights."""
        print("\n  +-- Connection Weights -------------------------+")
        strong = self.get_strong_connections(min_weight)
        if not strong:
            print(f"  |  No connections above {min_weight}")
        else:
            for subj, rel, obj, weight in strong[:10]:
                print(f"  |  {subj} ~{rel}~> {obj}: {weight:.2f}")
        print("  +-----------------------------------------------+\n")


class ProcessingMixin:
    """Mixin class providing text processing capabilities for Loom."""

    def process_with_activation(self: "Loom", text: str, already_simplified: bool = False) -> str:
        """
        Process input using spreading activation for faster connections.
        Activates mentioned concepts and spreads to find related knowledge.
        Uses AdvancedSimplifier to break complex sentences into atomic facts.

        Args:
            text: The text to process
            already_simplified: If True, skip simplification (text is already atomic)
        """
        # If already simplified, just parse directly
        if already_simplified:
            response = self.parser.parse(text)
        else:
            # Initialize advanced simplifier (cache it for reuse)
            if not hasattr(self, '_advanced_simplifier'):
                self._advanced_simplifier = AdvancedSimplifier()

            # Simplify complex sentences into atomic facts
            simplified = self._advanced_simplifier.simplify(text)

            # Process each simplified statement
            responses = []
            for statement in simplified:
                statement = statement.strip()
                if statement:
                    response = self.parser.parse(statement)
                    responses.append(response)

            # Combine responses (use first successful one for display)
            if responses:
                response = responses[0]
                if len(responses) > 1:
                    learned_count = sum(1 for r in responses if 'Got it' in r)
                    if learned_count > 1:
                        response = f"Learned {learned_count} facts from that."
            else:
                response = self.parser.parse(text)

        # Extract entities from the text (simplified - parser should provide these)
        entities = self._extract_entities(text)

        # Track access for concept reinforcement on known entities
        for entity in entities:
            normalized = normalize(entity)
            if normalized in self.knowledge:
                self._track_access(normalized)

        # Process through activation network
        coactivated = self.activation.process_input(
            entities,
            self.knowledge,
            self.connection_weights
        )

        # Check for potential new connections from co-activation
        for node, level, sources in coactivated:
            if len(sources) >= 2:
                sources_list = list(sources)
                # Strengthen connections between co-activated concepts
                for i, src in enumerate(sources_list):
                    for other_src in sources_list[i+1:]:
                        self.strengthen_connection(src, "related_to", other_src)

                if self.verbose:
                    print(f"       [co-activated: {node} from {sources}]")

        return response

    def _extract_entities(self: "Loom", text: str) -> List[str]:
        """Extract entity names from text for activation."""
        # Remove common words and extract potential concepts
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'can', 'to', 'of', 'in',
            'for', 'on', 'with', 'at', 'by', 'from', 'and', 'but', 'or',
            'not', 'it', 'its', 'they', 'them', 'this', 'that', 'what',
            'which', 'who', 'how', 'when', 'where', 'why'
        }

        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        entities = [w for w in words if w not in stop_words and len(w) > 2]

        # Also check for known concepts in our knowledge graph
        known = []
        for entity in entities:
            normalized = normalize(entity)
            if normalized in self.knowledge:
                known.append(normalized)

        # Return known concepts first, then unknown
        return list(set(known + entities))

    def process_paragraph(self: "Loom", text: str) -> Dict:
        """
        Process a paragraph or multi-sentence text.
        Splits into CHUNKS (not just sentences) and processes each one.
        Chunks handle clause-level splitting (e.g., "but" clauses).
        Uses SentenceSimplifier to break compound sentences into simple statements.

        Returns:
            Dict with processing results including facts added and connections made
        """
        result = {
            'chunks_processed': 0,
            'facts_added': 0,
            'connections_made': 0,
            'theme': None,
            'responses': []
        }

        # Initialize advanced simplifier (cache it for reuse)
        if not hasattr(self, '_advanced_simplifier'):
            self._advanced_simplifier = AdvancedSimplifier()

        # Get theme from chunker but use sentence-level splitting for better parsing
        # (The chunker over-splits creating fragments like "and gentle demeanor")
        chunked = self.chunker.process_for_knowledge(text)
        result['theme'] = chunked['theme']

        # Split into sentences instead of chunks for cleaner parsing
        chunks = self.chunker.split_sentences(text)

        # Activate theme concept strongly
        if chunked['theme']:
            self.activation.activate(normalize(chunked['theme']), amount=2.0)
            self.activation.add_topic_concept(normalize(chunked['theme']))

        # Process each chunk
        prev_entities = []
        for chunk_text in chunks:
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue

            # Simplify complex sentences into atomic facts
            # e.g., "Native to Africa, giraffes have long necks" ->
            #       ["giraffes is native to Africa", "giraffes have long necks"]
            simplified_statements = self._advanced_simplifier.simplify(chunk_text)

            # Process each simplified statement
            for statement in simplified_statements:
                statement = statement.strip()
                if not statement:
                    continue

                result['chunks_processed'] += 1

                # Clear clarification context to prevent carry-over between chunks
                if hasattr(self, 'context'):
                    self.context.clear_clarification()

                # Set last_subject to theme for pronoun resolution
                if chunked['theme'] and hasattr(self, 'parser'):
                    self.parser.last_subject = chunked['theme']

                # Process the statement using parser (already simplified, skip re-simplification)
                response = self.process_with_activation(statement, already_simplified=True)
                result['responses'].append(response)

            # Extract entities from this chunk
            current_entities = self._extract_entities(chunk_text)

            # Strengthen connections between consecutive chunks' entities
            for prev_ent in prev_entities:
                for curr_ent in current_entities:
                    if prev_ent != curr_ent:
                        self.strengthen_connection(prev_ent, "discourse_link", curr_ent)
                        result['connections_made'] += 1

            prev_entities = current_entities

        # Count facts added (approximate from responses)
        result['facts_added'] = sum(1 for r in result['responses'] if 'Got it' in r)

        # Decay old activations
        self.activation.decay()

        return result

    def _map_discourse_to_relation(self: "Loom", discourse_type: str) -> str:
        """Map discourse relation types to knowledge graph relations."""
        mapping = {
            'causal': 'causes',
            'temporal': 'followed_by',
            'contrast': 'differs_from',
            'elaboration': 'related_to',
            'example': 'example_of',
            'condition': 'requires',
            'similarity': 'similar_to',
            'conclusion': 'leads_to'
        }
        return mapping.get(discourse_type, 'related_to')

    def process_text(self: "Loom", text: str) -> str:
        """
        Smart text processing - automatically detects if single statement or paragraph.
        """
        # Check if it's a multi-sentence text
        sentences = self.chunker.split_sentences(text)

        if len(sentences) > 1:
            # Process as paragraph
            result = self.process_paragraph(text)
            if result['responses']:
                # Return summary response
                return f"Processed {result['chunks_processed']} chunks, " \
                       f"added {result['facts_added']} facts. " \
                       f"Theme: {result['theme'] or 'general'}"
            return "Processed text."
        else:
            # Single statement - use activation-enhanced processing
            return self.process_with_activation(text)

    def show_activation(self: "Loom"):
        """Display current activation state."""
        state = self.activation.get_state()
        print("\n  +-- Activation State ---------------------------+")
        print(f"  |  Primed nodes: {len(state['primed'])}")
        for node in state['primed'][:5]:
            level = self.activation.get_activation(node)
            print(f"  |    - {node}: {level:.2f}")
        print("  |")
        print(f"  |  Top activated:")
        for node, level in state['top_activated']:
            print(f"  |    - {node}: {level:.2f}")
        print("  +-----------------------------------------------+\n")
