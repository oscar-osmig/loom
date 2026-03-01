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
        return self.connection_weights.get(key, INITIAL_WEIGHT)

    def strengthen_connection(self: "Loom", subject: str, relation: str, obj: str,
                              amount: float = STRENGTHENING_FACTOR):
        """
        Strengthen a connection (Hebbian: cells that fire together wire together).
        Called when a connection is activated or co-activated.
        """
        key = (normalize(subject), relation.lower(), normalize(obj))
        current = self.connection_weights.get(key, INITIAL_WEIGHT)
        new_weight = min(current + amount, MAX_WEIGHT)
        self.connection_weights[key] = new_weight
        self.connection_times[key] = time.time()

        if self.verbose:
            print(f"       [strengthened: {subject} ~> {relation} ~> {obj} = {new_weight:.2f}]")

    def weaken_connection(self: "Loom", subject: str, relation: str, obj: str,
                          amount: float = DECAY_FACTOR):
        """Weaken a connection (decay from disuse)."""
        key = (normalize(subject), relation.lower(), normalize(obj))
        current = self.connection_weights.get(key, INITIAL_WEIGHT)
        new_weight = max(current - amount, MIN_WEIGHT)

        if new_weight <= MIN_WEIGHT:
            # Prune very weak connections
            if key in self.connection_weights:
                del self.connection_weights[key]
                if self.verbose:
                    print(f"       [pruned: {subject} ~> {relation} ~> {obj}]")
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
        strong = []
        for key, weight in self.connection_weights.items():
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

    def process_with_activation(self: "Loom", text: str) -> str:
        """
        Process input using spreading activation for faster connections.
        Activates mentioned concepts and spreads to find related knowledge.
        """
        # First, get standard parse result
        response = self.parser.parse(text)

        # Extract entities from the text (simplified - parser should provide these)
        entities = self._extract_entities(text)

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
        Splits into sentences and processes each one.

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

        # Split into sentences
        sentences = self.chunker.split_sentences(text)
        result['chunks_processed'] = len(sentences)

        # Detect theme
        chunked = self.chunker.process_for_knowledge(text)
        result['theme'] = chunked['theme']

        # Activate theme concept strongly
        if chunked['theme']:
            self.activation.activate(normalize(chunked['theme']), amount=2.0)

        # Process each sentence
        prev_entities = []
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Process the sentence using standard parser
            response = self.process_with_activation(sentence)
            result['responses'].append(response)

            # Extract entities from this sentence
            current_entities = self._extract_entities(sentence)

            # Strengthen connections between consecutive sentences' entities
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
