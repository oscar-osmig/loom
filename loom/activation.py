"""
Spreading Activation Network for Loom.
Implements Collins & Loftus spreading activation model.

When a concept is activated, activation spreads to connected nodes with decay.
Co-activation (multiple sources activating same node) signals strong connections.
"""

import time
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional


class ActivationNetwork:
    """
    Manages spreading activation across the knowledge graph.
    Mimics biological neural activation patterns.
    """

    def __init__(self, decay_rate: float = 0.15, spread_factor: float = 0.5,
                 activation_threshold: float = 0.1, max_activation: float = 2.0,
                 priming_window: float = 10.0):
        """
        Initialize activation network.

        Args:
            decay_rate: How fast activation decays (0-1)
            spread_factor: How much activation spreads to neighbors (0-1)
            activation_threshold: Minimum activation to spread
            max_activation: Cap on activation level
            priming_window: Seconds to keep priming active
        """
        self.decay_rate = decay_rate
        self.spread_factor = spread_factor
        self.activation_threshold = activation_threshold
        self.max_activation = max_activation
        self.priming_window = priming_window

        # Current activation levels: node -> level
        self.activations: Dict[str, float] = defaultdict(float)

        # Track activation sources for co-activation detection
        # node -> set of source nodes that activated it
        self.activation_sources: Dict[str, Set[str]] = defaultdict(set)

        # Timestamps for priming: node -> last activation time
        self.activation_times: Dict[str, float] = {}

        # Track activation history for patterns
        self.activation_history: List[Tuple[str, float, float]] = []  # (node, level, time)

    def activate(self, node: str, amount: float = 1.0, source: str = None):
        """
        Activate a node with given amount.

        Args:
            node: Node to activate
            amount: Activation amount (default 1.0)
            source: Source node that caused this activation (for co-activation tracking)
        """
        current = self.activations[node]
        new_level = min(current + amount, self.max_activation)
        self.activations[node] = new_level

        # Track source for co-activation
        if source:
            self.activation_sources[node].add(source)

        # Update timing
        now = time.time()
        self.activation_times[node] = now
        self.activation_history.append((node, new_level, now))

        # Trim history to last 100 entries
        if len(self.activation_history) > 100:
            self.activation_history = self.activation_history[-100:]

    def spread(self, knowledge_graph: Dict[str, Dict[str, List[str]]],
               connection_weights: Dict[Tuple[str, str, str], float] = None):
        """
        Spread activation to connected nodes.

        Args:
            knowledge_graph: The knowledge structure {node: {relation: [targets]}}
            connection_weights: Optional weights for connections (subj, rel, obj) -> weight
        """
        if connection_weights is None:
            connection_weights = {}

        new_activations: Dict[str, float] = defaultdict(float)
        new_sources: Dict[str, Set[str]] = defaultdict(set)

        for node, level in list(self.activations.items()):
            if level < self.activation_threshold:
                continue

            # Get all connections from this node
            node_relations = knowledge_graph.get(node, {})
            for relation, targets in node_relations.items():
                for target in targets:
                    # Get connection weight (default 1.0)
                    weight = connection_weights.get((node, relation, target), 1.0)

                    # Calculate spread amount
                    spread_amount = level * self.spread_factor * weight

                    # Accumulate activation
                    new_activations[target] += spread_amount
                    new_sources[target].add(node)

        # Apply new activations
        for target, amount in new_activations.items():
            self.activate(target, amount)
            self.activation_sources[target].update(new_sources[target])

    def decay(self):
        """Apply decay to all activations."""
        nodes_to_remove = []

        for node in list(self.activations.keys()):
            self.activations[node] *= (1 - self.decay_rate)

            # Remove if below threshold
            if self.activations[node] < 0.01:
                nodes_to_remove.append(node)

        for node in nodes_to_remove:
            del self.activations[node]
            if node in self.activation_sources:
                del self.activation_sources[node]

    def find_coactivated(self, min_sources: int = 2,
                         min_activation: float = 0.3) -> List[Tuple[str, float, Set[str]]]:
        """
        Find nodes receiving activation from multiple sources.
        These are candidates for new connections.

        Args:
            min_sources: Minimum number of sources required
            min_activation: Minimum activation level

        Returns:
            List of (node, activation_level, sources) tuples
        """
        coactivated = []

        for node, level in self.activations.items():
            sources = self.activation_sources.get(node, set())
            if len(sources) >= min_sources and level >= min_activation:
                coactivated.append((node, level, sources.copy()))

        # Sort by activation level (strongest first)
        coactivated.sort(key=lambda x: x[1], reverse=True)
        return coactivated

    def is_primed(self, node: str) -> bool:
        """Check if a node is currently primed (recently activated)."""
        if node not in self.activation_times:
            return False

        elapsed = time.time() - self.activation_times[node]
        return elapsed < self.priming_window

    def get_primed_nodes(self) -> List[str]:
        """Get all currently primed nodes."""
        now = time.time()
        return [
            node for node, timestamp in self.activation_times.items()
            if now - timestamp < self.priming_window
        ]

    def get_activation(self, node: str) -> float:
        """Get current activation level of a node."""
        return self.activations.get(node, 0.0)

    def get_top_activated(self, limit: int = 10) -> List[Tuple[str, float]]:
        """Get the most activated nodes."""
        sorted_nodes = sorted(
            self.activations.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_nodes[:limit]

    def clear(self):
        """Clear all activations."""
        self.activations.clear()
        self.activation_sources.clear()
        self.activation_times.clear()

    def process_input(self, entities: List[str], knowledge_graph: Dict,
                      connection_weights: Dict = None) -> List[Tuple[str, float, Set[str]]]:
        """
        Process a set of input entities through activation spreading.

        This is the main entry point for processing new input.

        Args:
            entities: List of entity/concept names from parsed input
            knowledge_graph: The knowledge structure
            connection_weights: Optional connection weights

        Returns:
            List of co-activated nodes (candidates for new connections)
        """
        # First, decay existing activations
        self.decay()

        # Activate all input entities
        for entity in entities:
            self.activate(entity, amount=1.0)

        # Spread activation (multiple rounds for deeper spread)
        for _ in range(2):
            self.spread(knowledge_graph, connection_weights)

        # Find co-activated nodes
        return self.find_coactivated()

    def suggest_connections(self, subject: str, obj: str,
                            knowledge_graph: Dict) -> List[Tuple[str, str]]:
        """
        Suggest potential connections based on co-activation patterns.

        When both subject and object activate the same intermediate node,
        that suggests a meaningful connection through that concept.

        Args:
            subject: Subject of the new fact
            obj: Object of the new fact
            knowledge_graph: The knowledge structure

        Returns:
            List of (intermediate_node, suggested_relation) tuples
        """
        suggestions = []

        # Activate both subject and object
        self.activate(subject, amount=1.0)
        self.activate(obj, amount=1.0)

        # Spread
        self.spread(knowledge_graph)

        # Find co-activated nodes
        coactivated = self.find_coactivated(min_sources=2)

        for node, level, sources in coactivated:
            # Both subject and object contributed to this node's activation
            if subject in sources and obj in sources:
                # Determine relation type based on the intermediate node
                relation = self._infer_relation_from_node(node, knowledge_graph)
                if relation:
                    suggestions.append((node, relation))

        return suggestions

    def _infer_relation_from_node(self, node: str,
                                   knowledge_graph: Dict) -> Optional[str]:
        """Infer what relation a co-activated node suggests."""
        node_data = knowledge_graph.get(node, {})

        # Check what relations this node has
        if "is" in node_data:
            return "shares_category"
        if "has" in node_data:
            return "shares_property"
        if "can" in node_data:
            return "shares_ability"
        if "causes" in node_data or "leads_to" in node_data:
            return "causal_link"

        return "related_through"

    def get_state(self) -> Dict:
        """Get current state for debugging/visualization."""
        return {
            "activations": dict(self.activations),
            "sources": {k: list(v) for k, v in self.activation_sources.items()},
            "primed": self.get_primed_nodes(),
            "top_activated": self.get_top_activated(5)
        }
