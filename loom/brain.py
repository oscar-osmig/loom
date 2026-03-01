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

import time
from collections import defaultdict
from typing import List, Dict, Tuple, Optional

from .normalizer import normalize, prettify, prettify_cause, prettify_effect
from .inference import InferenceEngine
from .parser import Parser
from .visualizer import visualize_graph, visualize_node, visualize_compact
from .context import ConversationContext
from .storage import get_storage, MongoStorage
from .activation import ActivationNetwork
from .chunker import TextChunker

# Confidence levels
CONFIDENCE_HIGH = "high"      # Directly stated by user
CONFIDENCE_MEDIUM = "medium"  # Inferred from patterns
CONFIDENCE_LOW = "low"        # Weak inference or old

# Hebbian learning constants
INITIAL_WEIGHT = 1.0          # Starting connection strength
STRENGTHENING_FACTOR = 0.2    # How much to strengthen on co-activation
DECAY_FACTOR = 0.05           # How much to decay unused connections
MAX_WEIGHT = 5.0              # Maximum connection strength
MIN_WEIGHT = 0.1              # Minimum before pruning

# Property-based facets for automatic grouping
LOCATION_FACETS = {
    "ocean": "aquatic",
    "sea": "aquatic",
    "water": "aquatic",
    "river": "aquatic",
    "lake": "aquatic",
    "land": "terrestrial",
    "forest": "terrestrial",
    "jungle": "terrestrial",
    "desert": "terrestrial",
    "savanna": "terrestrial",
    "sky": "aerial",
    "air": "aerial",
}

# Relations that should trigger inheritance propagation
INHERITABLE_RELATIONS = ["is", "is_a", "type_of", "kind_of"]

# Relations to propagate down the inheritance chain
PROPAGATE_DOWN = ["can", "has", "has_property", "eats", "needs"]


class Loom:
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

    # ==================== INHERITANCE & FACETS ====================

    def _propagate_inheritance(self, subject: str, parent: str, confidence: str):
        """
        Propagate inheritance up the category chain.
        If subject is parent, and parent is grandparent, then subject is grandparent.
        """
        # Get what the parent is (its categories)
        parent_categories = self.get(parent, "is") or []

        for grandparent in parent_categories:
            # Check if subject already has this category
            existing = self.get(subject, "is") or []
            if grandparent not in existing:
                # Add inherited category (with lower confidence)
                inherited_confidence = CONFIDENCE_MEDIUM if confidence == CONFIDENCE_HIGH else CONFIDENCE_LOW
                self.add_fact(subject, "is", grandparent, inherited_confidence, _propagate=False)
                if self.verbose:
                    print(f"       [inherited: {subject} is {grandparent} (via {parent})]")

    def _add_instance(self, category: str, instance: str):
        """Track that instance is a member of category."""
        # Add reverse relation: category has_instance instance
        existing = self.get(category, "has_instance") or []
        if instance not in existing:
            self.add_fact(category, "has_instance", instance, CONFIDENCE_HIGH, _propagate=False)

    def _update_location_facet(self, subject: str, location: str):
        """Update facet groupings based on location."""
        location_lower = location.lower()

        # Check if location maps to a facet
        facet = None
        for loc_key, facet_name in LOCATION_FACETS.items():
            if loc_key in location_lower:
                facet = facet_name
                break

        if facet:
            # Add subject to the facet group
            facet_group = f"{facet}_creatures"
            existing = self.get(facet_group, "includes") or []
            if subject not in existing:
                self.add_fact(facet_group, "includes", subject, CONFIDENCE_MEDIUM, _propagate=False)
                # Also add reverse
                self.add_fact(subject, "habitat_type", facet, CONFIDENCE_MEDIUM, _propagate=False)
                if self.verbose:
                    print(f"       [facet: {subject} -> {facet_group}]")

    def get_instances(self, category: str) -> List[str]:
        """Get all instances of a category (including inherited)."""
        instances = set()
        category_norm = normalize(category)

        # Direct instances
        direct = self.get(category_norm, "has_instance") or []
        instances.update(direct)

        # Check all entities to find those that inherit this category
        for entity, relations in self.knowledge.items():
            if "is" in relations:
                if category_norm in relations["is"]:
                    instances.add(entity)

        return list(instances)

    def get_by_facet(self, facet: str) -> List[str]:
        """Get all entities in a facet group (e.g., 'aquatic', 'terrestrial')."""
        facet_group = f"{facet}_creatures"
        return self.get(facet_group, "includes") or []

    def get_category_chain(self, entity: str) -> List[str]:
        """Get the full category chain for an entity (inheritance path)."""
        chain = []
        entity_norm = normalize(entity)
        categories = self.get(entity_norm, "is") or []

        for cat in categories:
            if cat not in chain:
                chain.append(cat)
                # Recursively get parent categories
                parent_chain = self.get_category_chain(cat)
                for parent in parent_chain:
                    if parent not in chain:
                        chain.append(parent)

        return chain

    # ==================== CONNECTION DISCOVERY ====================

    def discover_connections(self) -> List[Tuple[str, str, str]]:
        """
        Discover new connections between entities based on shared properties.
        Returns list of new connections discovered.
        """
        discovered = []

        # Group entities by shared properties
        property_groups = defaultdict(set)  # property -> set of entities

        for entity, relations in self.knowledge.items():
            if entity == "self":
                continue

            # Group by categories
            for cat in relations.get("is", []):
                property_groups[f"is:{cat}"].add(entity)

            # Group by properties
            for prop in relations.get("has_property", []):
                property_groups[f"prop:{prop}"].add(entity)

            # Group by location
            for loc in relations.get("lives_in", []):
                property_groups[f"loc:{loc}"].add(entity)

            # Group by abilities
            for ability in relations.get("can", []):
                property_groups[f"can:{ability}"].add(entity)

            # Group by inabilities
            for inability in relations.get("cannot", []):
                property_groups[f"cannot:{inability}"].add(entity)

        # Find entities with multiple shared properties -> they're similar
        similarity_scores = defaultdict(int)  # (entity1, entity2) -> score

        for prop, entities in property_groups.items():
            if len(entities) >= 2:
                entities_list = list(entities)
                for i, e1 in enumerate(entities_list):
                    for e2 in entities_list[i+1:]:
                        key = tuple(sorted([e1, e2]))
                        similarity_scores[key] += 1

        # Create "similar_to" connections for highly similar pairs
        for (e1, e2), score in similarity_scores.items():
            if score >= 2:  # At least 2 shared properties
                # Check if already connected
                existing = self.get(e1, "similar_to") or []
                if e2 not in existing:
                    self.add_fact(e1, "similar_to", e2, CONFIDENCE_MEDIUM, _propagate=False)
                    self.add_fact(e2, "similar_to", e1, CONFIDENCE_MEDIUM, _propagate=False)
                    discovered.append((e1, "similar_to", e2))
                    if self.verbose:
                        print(f"       [discovered: {e1} similar_to {e2} (score: {score})]")

        # Propagate inherited properties down the chain
        discovered.extend(self._propagate_properties_down())

        return discovered

    def _propagate_properties_down(self) -> List[Tuple[str, str, str]]:
        """
        Propagate properties from categories to instances.
        If 'mammals' can 'breathe_air' and 'dolphins' is 'mammals',
        then 'dolphins' can 'breathe_air'.
        Respects conflicts: won't propagate 'can X' if entity has 'cannot X'.
        """
        propagated = []

        # Conflicting relation pairs
        conflict_pairs = {
            "can": "cannot",
            "cannot": "can",
            "has": "has_not",
            "has_not": "has",
            "is": "is_not",
            "is_not": "is",
        }

        for entity, relations in self.knowledge.items():
            if entity == "self":
                continue

            # Get categories this entity belongs to
            categories = relations.get("is", [])

            for category in categories:
                cat_relations = self.knowledge.get(category, {})

                # Propagate inheritable relations
                for rel in PROPAGATE_DOWN:
                    cat_values = cat_relations.get(rel, [])
                    entity_values = relations.get(rel, [])

                    # Get conflicting relation values
                    conflict_rel = conflict_pairs.get(rel)
                    conflict_values = relations.get(conflict_rel, []) if conflict_rel else []

                    for value in cat_values:
                        # Skip if already has this value
                        if value in entity_values:
                            continue

                        # Skip if has conflicting value (e.g., "cannot fly" blocks "can fly")
                        if value in conflict_values:
                            if self.verbose:
                                print(f"       [blocked: {entity} {rel} {value} (conflicts with {conflict_rel})]")
                            continue

                        self.add_fact(entity, rel, value, CONFIDENCE_LOW, _propagate=False)
                        propagated.append((entity, rel, value))
                        if self.verbose:
                            print(f"       [propagated: {entity} {rel} {value} (from {category})]")

        return propagated

    def find_related_by_context(self, entity: str, context: str) -> List[str]:
        """
        Find entities related to the given entity filtered by context.
        E.g., find_related_by_context("animals", "aquatic") returns aquatic animals.
        """
        entity_norm = normalize(entity)
        context_norm = normalize(context)
        results = []

        # Get instances of entity
        instances = self.get_instances(entity_norm)

        for instance in instances:
            inst_relations = self.knowledge.get(instance, {})

            # Check if instance matches the context
            matches_context = False

            # Check habitat type
            if context_norm in inst_relations.get("habitat_type", []):
                matches_context = True

            # Check location
            for loc in inst_relations.get("lives_in", []):
                if context_norm in loc or loc in context_norm:
                    matches_context = True

            # Check properties
            if context_norm in inst_relations.get("has_property", []):
                matches_context = True

            # Check abilities
            if context_norm in inst_relations.get("can", []):
                matches_context = True

            if matches_context:
                results.append(instance)

        return results

    def run_discovery_cycle(self) -> Dict:
        """
        Run a full discovery cycle: find new connections, propagate inheritance.
        Call this periodically or after adding new facts.
        """
        result = {
            "connections_discovered": 0,
            "properties_propagated": 0,
            "categories_linked": 0
        }

        # Discover similar entities
        discovered = self.discover_connections()
        result["connections_discovered"] = len([d for d in discovered if d[1] == "similar_to"])
        result["properties_propagated"] = len([d for d in discovered if d[1] != "similar_to"])

        # Strengthen connections between related concepts
        for e1, rel, e2 in discovered:
            self.strengthen_connection(e1, rel, e2)

        return result

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

    # ==================== HEBBIAN STRENGTHENING ====================

    def get_connection_weight(self, subject: str, relation: str, obj: str) -> float:
        """Get the strength of a connection."""
        key = (normalize(subject), relation.lower(), normalize(obj))
        return self.connection_weights.get(key, INITIAL_WEIGHT)

    def strengthen_connection(self, subject: str, relation: str, obj: str,
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

    def weaken_connection(self, subject: str, relation: str, obj: str,
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

    def decay_all_connections(self, elapsed_threshold: float = 60.0):
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

    def get_strong_connections(self, threshold: float = 2.0) -> List[Tuple[str, str, str, float]]:
        """Get connections above a strength threshold."""
        strong = []
        for key, weight in self.connection_weights.items():
            if weight >= threshold:
                subject, relation, obj = key
                strong.append((subject, relation, obj, weight))
        # Sort by weight descending
        strong.sort(key=lambda x: x[3], reverse=True)
        return strong

    # ==================== ACTIVATION-BASED PROCESSING ====================

    def process_with_activation(self, text: str) -> str:
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

    def _extract_entities(self, text: str) -> List[str]:
        """Extract entity names from text for activation."""
        import re
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

    # ==================== PARAGRAPH PROCESSING ====================

    def process_paragraph(self, text: str) -> Dict:
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

    def _map_discourse_to_relation(self, discourse_type: str) -> str:
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

    def process_text(self, text: str) -> str:
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

    # ==================== ACTIVATION UTILITIES ====================

    def show_activation(self):
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

    def show_weights(self, min_weight: float = 1.5):
        """Display strong connection weights."""
        print("\n  +-- Connection Weights -------------------------+")
        strong = self.get_strong_connections(min_weight)
        if not strong:
            print(f"  |  No connections above {min_weight}")
        else:
            for subj, rel, obj, weight in strong[:10]:
                print(f"  |  {subj} ~{rel}~> {obj}: {weight:.2f}")
        print("  +-----------------------------------------------+\n")

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

    # ==================== TRAINING METHODS ====================

    def train(self, source) -> int:
        """
        Train Loom with knowledge from various sources.

        Args:
            source: Can be one of:
                - str: Pack name ("animals", "nature", "science", "geography")
                       or file path (.json, .txt)
                - list of tuples: [("dogs", "is", "animals"), ...]
                - list of dicts: [{"subject": "dogs", "relation": "is", "object": "animals"}, ...]
                - list of strings: ["dogs are animals", "cats can meow", ...]

        Returns:
            Number of facts added.

        Examples:
            loom.train("animals")  # Load animals pack
            loom.train("data.json")  # Load from JSON file
            loom.train([("dogs", "is", "mammals"), ("cats", "can", "meow")])
            loom.train(["dogs are mammals", "cats can meow"])
        """
        if isinstance(source, str):
            # Check if it's a pack name or file path
            from .trainer import KNOWLEDGE_PACKS, train as train_pack, train_from_file
            if source in KNOWLEDGE_PACKS:
                count, _ = train_pack(self, source)
                return count
            else:
                # Assume it's a file path
                count, _ = train_from_file(self, source)
                return count

        elif isinstance(source, list):
            if not source:
                return 0

            # Detect format from first item
            first = source[0]

            if isinstance(first, tuple) and len(first) >= 3:
                # List of tuples: [(subj, rel, obj), ...]
                return self.train_facts(source)

            elif isinstance(first, dict):
                # List of dicts: [{"subject": ..., "relation": ..., "object": ...}, ...]
                return self.train_dicts(source)

            elif isinstance(first, str):
                # List of natural language statements
                return self.train_statements(source)

        return 0

    def train_facts(self, facts: list) -> int:
        """
        Train from a list of (subject, relation, object) tuples.

        Args:
            facts: List of tuples like [("dogs", "is", "animals"), ...]

        Returns:
            Number of facts added.
        """
        count = 0
        for fact in facts:
            if len(fact) >= 3:
                subj, rel, obj = fact[0], fact[1], fact[2]
                existing = self.get(subj, rel) or []
                if obj.lower() not in [e.lower() for e in existing]:
                    self.add_fact(subj, rel, obj)
                    count += 1
        return count

    def train_dicts(self, facts: list) -> int:
        """
        Train from a list of dictionaries.

        Args:
            facts: List of dicts like [{"subject": "dogs", "relation": "is", "object": "animals"}, ...]
                   Also accepts short forms: {"s": ..., "r": ..., "o": ...}

        Returns:
            Number of facts added.
        """
        count = 0
        for item in facts:
            subj = item.get('subject', item.get('s', ''))
            rel = item.get('relation', item.get('r', ''))
            obj = item.get('object', item.get('o', ''))

            if subj and rel and obj:
                existing = self.get(subj, rel) or []
                if obj.lower() not in [e.lower() for e in existing]:
                    self.add_fact(subj, rel, obj)
                    count += 1
        return count

    def train_statements(self, statements: list, silent: bool = True) -> int:
        """
        Train from natural language statements.

        Args:
            statements: List of strings like ["dogs are animals", "cats can meow"]
            silent: If True, don't print responses (default True for bulk training)

        Returns:
            Number of statements processed.
        """
        count = 0
        for stmt in statements:
            if stmt and stmt.strip():
                response = self.process(stmt.strip())
                if not silent and self.verbose:
                    print(f"  {stmt} -> {response}")
                count += 1
        return count

    def train_batch(self, facts: list, batch_size: int = 100) -> int:
        """
        Train from a large list of facts in batches (more efficient for MongoDB).

        Args:
            facts: List of (subject, relation, object) tuples
            batch_size: Number of facts per batch

        Returns:
            Number of facts added.
        """
        count = 0
        for i in range(0, len(facts), batch_size):
            batch = facts[i:i + batch_size]
            count += self.train_facts(batch)
        return count

    @staticmethod
    def available_packs() -> list:
        """Return list of available knowledge packs."""
        from .trainer import list_packs
        return list_packs()
