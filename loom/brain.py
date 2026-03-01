"""
Loom - Core knowledge storage and management.
Weaves threads of knowledge into a connected tapestry.

Enhanced with:
- Confidence levels (high/medium/low)
- Fact retraction and correction
- Constraints (conditions on facts)
- Procedural knowledge (sequences)
- Conflict detection
- MongoDB storage backend (with JSON fallback)
- Spreading activation network (Collins & Loftus model)
- Hebbian connection strengthening
- Text chunking for paragraph processing
- Transitive inheritance (category chains)
- Faceted classification (property-based groupings)
- Automatic connection discovery
"""

from typing import Dict, Tuple

from .normalizer import normalize, prettify_cause, prettify_effect
from .inference import InferenceEngine
from .parser import Parser
from .visualizer import visualize_graph, visualize_node, visualize_compact
from .context import ConversationContext
from .storage import get_storage, MongoStorage
from .activation import ActivationNetwork
from .chunker import TextChunker
from .training import TrainingMixin
from .discovery import DiscoveryMixin
from .processing import HebbianMixin, ProcessingMixin

# Confidence levels
CONFIDENCE_HIGH = "high"      # Directly stated by user
CONFIDENCE_MEDIUM = "medium"  # Inferred from patterns
CONFIDENCE_LOW = "low"        # Weak inference or old

# Relations that should trigger inheritance propagation
INHERITABLE_RELATIONS = ["is", "is_a", "type_of", "kind_of"]


class Loom(TrainingMixin, DiscoveryMixin, HebbianMixin, ProcessingMixin):
    """
    The main knowledge system.
    Stores facts as a directed graph and manages inference.
    """

    def __init__(self, name: str = "loom", verbose: bool = False,
                 use_mongo: bool = True, mongo_uri: str = "mongodb://localhost:27017",
                 database_name: str = "loom", memory_file: str = "loom_memory.json"):
        self.name = name
        self.verbose = verbose  # Show debug output when True

        # Initialize storage backend (MongoDB or JSON fallback)
        self.storage = get_storage(
            use_mongo=use_mongo,
            connection_string=mongo_uri,
            database_name=database_name,
            instance_name=name,
            memory_file=memory_file
        )

        # Track actual storage type (may have fallen back to JSON)
        self.use_mongo = isinstance(self.storage, MongoStorage)

        # In-memory cache for fast access (synced with storage)
        self._knowledge_cache = None
        self._cache_dirty = True

        # Runtime state (not persisted)
        self.conflicts = []  # Current session conflicts
        self.pending = {}  # Open questions
        self.recent = []  # Recent facts for background processing

        # Conversation context
        self.context = ConversationContext()

        # Spreading activation network (Collins & Loftus model)
        self.activation = ActivationNetwork(
            decay_rate=0.15,
            spread_factor=0.5,
            priming_window=10.0
        )

        # Connection weights for Hebbian strengthening
        # Key: (subject, relation, object) -> weight
        self.connection_weights: Dict[Tuple[str, str, str], float] = {}

        # Track last activation time for each connection (for decay)
        self.connection_times: Dict[Tuple[str, str, str], float] = {}

        # Text chunker for paragraph processing
        self.chunker = TextChunker()

        # Initialize with self-knowledge
        self.add_fact("self", "name_is", self.name, _save=True)

        # Create parser and inference engine
        self.parser = Parser(self)
        self.inference = InferenceEngine(self)
        self.inference.start()

    @property
    def knowledge(self) -> dict:
        """Get knowledge graph (cached from storage)."""
        if self._cache_dirty or self._knowledge_cache is None:
            self._knowledge_cache = self.storage.get_all_knowledge()
            self._cache_dirty = False
        return self._knowledge_cache

    def _invalidate_cache(self):
        """Mark cache as needing refresh."""
        self._cache_dirty = True

    def add_fact(self, subject: str, relation: str, obj: str,
                 confidence: str = CONFIDENCE_HIGH, _save: bool = True,
                 _propagate: bool = True):
        """Add a fact to the knowledge graph with confidence level."""
        s = normalize(subject)
        r = relation.lower().strip()
        o = normalize(obj)

        # Check for conflicts before adding
        if _save:
            conflict = self._check_conflict(s, r, o)
            if conflict:
                self.conflicts.append(conflict)
                self.storage.add_conflict(conflict)
                if self.verbose:
                    print(f"       [conflict detected: {conflict}]")

        # Add to storage
        added = self.storage.add_fact(s, r, o, confidence)

        if added:
            self._invalidate_cache()
            self.recent.append((s, r, o))

            if self.verbose:
                print(f"       [woven: {s} ~> {r} ~> {o} ({confidence})]")

            # Run immediate inference for important relations
            if _save and hasattr(self, 'inference'):
                self.inference.process_immediate(s, r, o)

            # Propagate inheritance for "is" relations
            if _propagate and r in INHERITABLE_RELATIONS:
                self._propagate_inheritance(s, o, confidence)
                # Track reverse: object has instance subject
                self._add_instance(o, s)

            # Update facets for location-based groupings
            if _propagate and r == "lives_in":
                self._update_location_facet(s, o)

        # Bidirectional link for colors
        if r == "color":
            self.add_fact(obj, "is_color_of", subject, confidence, _save, _propagate=False)

    def retract_fact(self, subject: str, relation: str, obj: str):
        """Remove a fact from the knowledge graph."""
        s = normalize(subject)
        r = relation.lower().strip()
        o = normalize(obj)

        removed = self.storage.retract_fact(s, r, o)

        if removed:
            self._invalidate_cache()
            if self.verbose:
                print(f"       [unwoven: {s} ~> {r} ~> {o}]")

        return removed

    def add_constraint(self, subject: str, relation: str, obj: str, condition: str):
        """Add a constraint/condition to a fact."""
        s = normalize(subject)
        r = relation.lower().strip()
        o = normalize(obj)
        c = normalize(condition)

        self.storage.add_constraint(s, r, o, c)
        if self.verbose:
            print(f"       [constraint: {s} ~> {r} ~> {o} ONLY IF {c}]")

    def get_constraints(self, subject: str, relation: str, obj: str) -> list:
        """Get constraints for a fact."""
        s = normalize(subject)
        r = relation.lower().strip()
        o = normalize(obj)
        return self.storage.get_constraints(s, r, o)

    def add_procedure(self, name: str, steps: list):
        """Add a procedural sequence."""
        n = normalize(name)
        self.storage.add_procedure(n, steps)
        if self.verbose:
            print(f"       [procedure: {n} with {len(steps)} steps]")

    def get_procedure(self, name: str) -> list:
        """Get steps for a procedure."""
        return self.storage.get_procedure(normalize(name))

    def _check_conflict(self, subject: str, relation: str, obj: str) -> dict | None:
        """Check if new fact conflicts with existing knowledge."""
        # Check for direct contradiction (is vs is_not)
        if relation == "is":
            negations = self.get(subject, "is_not") or []
            if obj in negations:
                return {
                    "type": "contradiction",
                    "fact1": f"{subject} is {obj}",
                    "fact2": f"{subject} is_not {obj}"
                }
        elif relation == "is_not":
            positives = self.get(subject, "is") or []
            if obj in positives:
                return {
                    "type": "contradiction",
                    "fact1": f"{subject} is_not {obj}",
                    "fact2": f"{subject} is {obj}"
                }

        # Check for can vs cannot
        if relation == "can":
            cannots = self.get(subject, "cannot") or []
            if obj in cannots:
                return {
                    "type": "contradiction",
                    "fact1": f"{subject} can {obj}",
                    "fact2": f"{subject} cannot {obj}"
                }
        elif relation == "cannot":
            cans = self.get(subject, "can") or []
            if obj in cans:
                return {
                    "type": "contradiction",
                    "fact1": f"{subject} cannot {obj}",
                    "fact2": f"{subject} can {obj}"
                }

        return None

    def get_confidence(self, subject: str, relation: str, obj: str) -> str:
        """Get confidence level for a fact."""
        s = normalize(subject)
        r = relation.lower().strip()
        o = normalize(obj)
        return self.storage.get_confidence(s, r, o)

    def update_confidence(self, subject: str, relation: str, obj: str, confidence: str):
        """Update confidence level for a fact."""
        s = normalize(subject)
        r = relation.lower().strip()
        o = normalize(obj)
        self.storage.update_confidence(s, r, o, confidence)

    def get(self, subject: str, relation: str) -> list | None:
        """Get targets for a subject-relation pair."""
        results = self.storage.get_facts(normalize(subject), relation.lower().strip())
        return results if results else None

    def copy_properties(self, target: str, source: str):
        """Copy properties from source to target (Hebbian-style linking)."""
        source_norm = normalize(source)
        # Relations that should be copied between similar things
        copyable = ("color", "is", "can", "has", "eats", "lives_in", "needs")
        source_facts = self.storage.get_all_facts_for_subject(source_norm)
        for rel, values in source_facts.items():
            if rel in copyable:
                for v in values:
                    existing = self.get(target, rel) or []
                    if v not in existing:
                        self.add_fact(target, rel, v)

    def process(self, text: str) -> str:
        """Process user input and return response."""
        return self.parser.parse(text)

    def show_knowledge(self):
        """Display current knowledge as neural network visualization."""
        print(visualize_graph(dict(self.knowledge)))

    def show_neuron(self, node_name: str):
        """Display a single neuron and its connections."""
        print(visualize_node(dict(self.knowledge), node_name))

    def show_compact(self):
        """Display compact view of all neurons."""
        print(visualize_compact(dict(self.knowledge)))

    def show_inferences(self):
        """Display inferred facts."""
        print("\n  +-- Inferred Threads (Syllogism) ---------------+")
        inferences = self.inference.get_inferences()
        if not inferences:
            print("  |  No inferences woven yet.")
        else:
            for subj, rel, obj, depth in inferences:
                s = prettify_cause(subj)
                o = prettify_effect(obj)
                print(f"  |  When {s}, {o}")
                print(f"  |    (woven via {depth}-step chain)")
        print("  +-----------------------------------------------+\n")

    def trace_chain(self, start: str, relation: str):
        """Show the full reasoning chain from start via relation."""
        start_pretty = prettify_cause(normalize(start))
        print(f"\n  +-- Thread: {start_pretty} ({relation}) --------+")

        chain = self.inference.transitive_chain(normalize(start), relation)
        if not chain:
            print(f"  |  No {relation} threads found.")
        else:
            direct = self.get(start, relation) or []
            for d in direct:
                d_pretty = prettify_effect(d)
                print(f"  |  ~> {d_pretty} (direct)")
            for target, depth in chain:
                if target not in direct:
                    t_pretty = prettify_effect(target)
                    print(f"  |  ~> {t_pretty} (inferred, {depth} steps)")
        print("  +-----------------------------------------------+\n")

    def forget_all(self):
        """Clear all knowledge from storage."""
        self.storage.forget_all()
        self._invalidate_cache()
        self.conflicts = []
        self.recent = []
        if hasattr(self, 'inference'):
            self.inference.inferences = []
            self.storage.clear_inferences()
        if hasattr(self, 'context'):
            self.context = ConversationContext()
        # Re-add self-knowledge
        self.add_fact("self", "name_is", self.name)

    def show_conflicts(self):
        """Display detected conflicts."""
        print("\n  +-- Detected Conflicts -------------------------+")
        conflicts = self.storage.get_conflicts()
        if not conflicts:
            print("  |  No conflicts detected.")
        else:
            for conflict in conflicts:
                print(f"  |  {conflict['type'].upper()}:")
                print(f"  |    - {conflict['fact1']}")
                print(f"  |    - {conflict['fact2']}")
        print("  +-----------------------------------------------+\n")

    def show_procedures(self):
        """Display stored procedures."""
        print("\n  +-- Procedures ---------------------------------+")
        procedures = self.storage.get_all_procedures()
        if not procedures:
            print("  |  No procedures stored.")
        else:
            for name, steps in procedures.items():
                print(f"  |  {name}:")
                for i, step in enumerate(steps, 1):
                    print(f"  |    {i}. {step}")
        print("  +-----------------------------------------------+\n")

    def get_stats(self) -> dict:
        """Get storage statistics."""
        return self.storage.get_stats()

    def close(self):
        """Close storage connection."""
        self.storage.close()
