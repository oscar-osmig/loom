"""
Loom Discovery Module - Connection discovery and inference methods.

Contains:
- discover_connections: Find new connections based on shared properties
- _propagate_properties_down: Propagate properties from categories to instances
- find_related_by_context: Find entities related by context
- run_discovery_cycle: Full discovery cycle
- _propagate_inheritance: Propagate inheritance up the category chain
- _add_instance: Track instance membership
- _update_location_facet: Update facet groupings based on location
- get_instances: Get all instances of a category
- get_by_facet: Get entities by facet
- get_category_chain: Get full category chain for an entity

Enhanced with:
- Background pattern scanning for implicit connections
- Co-occurrence tracking between concepts
- Autonomous neuron creation from discovered patterns
- Structural similarity detection
"""

import time
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from .brain import Loom

from .normalizer import normalize

logger = logging.getLogger(__name__)

# Confidence levels
CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

# Minimum pattern support for neuron creation
MIN_PATTERN_SUPPORT = 3

# Minimum confidence for adding discovered relations
MIN_DISCOVERY_CONFIDENCE = 0.6

# Weak neuron thresholds for proactive strengthening
WEAK_NEURON_MAX_CONNECTIONS = 3
WEAK_NEURON_MAX_AVG_WEIGHT = 1.5

# Maximum relations to add per discovery cycle (prevent pollution)
MAX_RELATIONS_PER_CYCLE = 10

# Enable automatic neuron creation from stable patterns
AUTO_CREATE_NEURONS = True


@dataclass
class DiscoveredPattern:
    """A pattern discovered from knowledge analysis."""
    pattern_type: str  # cluster, co_occurrence, bridge, similar
    entities: List[str]
    shared_properties: Dict[str, List[str]]  # relation -> values
    support_count: int = 1
    confidence: float = 0.5
    created_at: float = field(default_factory=time.time)

    def __hash__(self):
        return hash((self.pattern_type, tuple(sorted(self.entities))))


@dataclass
class DiscoveredNeuron:
    """A new neuron suggested by discovery."""
    name: str
    neuron_type: str  # category, bridge, process
    members: List[str]
    properties: Dict[str, List[str]]
    provenance: dict
    confidence: float = 0.5

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

# Relations to propagate down the inheritance chain
PROPAGATE_DOWN = ["can", "has", "has_property", "eats", "needs"]


class DiscoveryMixin:
    """Mixin class providing discovery and inference capabilities for Loom."""

    # ==================== INHERITANCE & FACETS ====================

    def _propagate_inheritance(self: "Loom", subject: str, parent: str, confidence: str):
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

    def _add_instance(self: "Loom", category: str, instance: str):
        """Track that instance is a member of category."""
        # Add reverse relation: category has_instance instance
        existing = self.get(category, "has_instance") or []
        if instance not in existing:
            self.add_fact(category, "has_instance", instance, CONFIDENCE_HIGH, _propagate=False)

    def _update_location_facet(self: "Loom", subject: str, location: str):
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

    def get_instances(self: "Loom", category: str) -> List[str]:
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

    def get_by_facet(self: "Loom", facet: str) -> List[str]:
        """Get all entities in a facet group (e.g., 'aquatic', 'terrestrial')."""
        facet_group = f"{facet}_creatures"
        return self.get(facet_group, "includes") or []

    def get_category_chain(self: "Loom", entity: str) -> List[str]:
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

    def discover_connections(self: "Loom") -> List[Tuple[str, str, str]]:
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

    def _propagate_properties_down(self: "Loom") -> List[Tuple[str, str, str]]:
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

    def find_related_by_context(self: "Loom", entity: str, context: str) -> List[str]:
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

    def run_discovery_cycle(self: "Loom") -> Dict:
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


class ConnectionDiscoveryEngine:
    """
    Enhanced discovery engine that runs in background to find implicit connections.

    Capabilities:
    - Track co-occurrence of entities mentioned together
    - Find property clusters (entities sharing 2+ properties)
    - Detect structural similarities (same relation patterns)
    - Create bridging neurons for connected clusters
    """

    def __init__(self, loom: "Loom"):
        self.loom = loom

        # Track discovered patterns
        self._patterns: Dict[str, DiscoveredPattern] = {}

        # Track co-occurrence counts: (entity1, entity2) -> count
        self._co_occurrence: Dict[Tuple[str, str], int] = defaultdict(int)

        # Track which neurons we've created
        self._created_neurons: Set[str] = set()

        # Pending neuron suggestions
        self._pending_neurons: List[DiscoveredNeuron] = []

        # Statistics
        self._stats = {
            "patterns_found": 0,
            "neurons_created": 0,
            "relations_added": 0,
            "scans_completed": 0
        }

        # Last scan time
        self._last_scan = 0.0

    def track_co_occurrence(self, entities: List[str]):
        """
        Track that these entities appeared together in a statement.
        Called when processing input to learn co-occurrence patterns.
        """
        if len(entities) < 2:
            return

        for i, e1 in enumerate(entities):
            for e2 in entities[i + 1:]:
                pair = tuple(sorted([e1, e2]))
                self._co_occurrence[pair] += 1

    def run_background_discovery(self):
        """
        Run a full background discovery cycle.
        Called periodically from inference loop (every 30 seconds).
        """
        self._last_scan = time.time()
        self._stats["scans_completed"] += 1

        # 1. Find property clusters
        clusters = self._find_property_clusters()

        # 2. Analyze co-occurrence patterns
        co_patterns = self._analyze_co_occurrence()

        # 3. Find structural similarities
        similarities = self._find_structural_similarities()

        # 4. Find transitive gaps (A→B→C but no A→C)
        transitive_gaps = self._find_transitive_gaps()

        # 5. Find missing properties (80%+ of category has it)
        missing_props = self._find_missing_properties()

        # 6. Find lonely neurons (few connections)
        lonely = self._find_lonely_neurons()

        # 7. Find analogies (A:B :: C:?)
        analogies = self._find_analogies()

        # 8. Find path-based similarities
        path_sims = self._find_path_similarities()

        # 9. Create inverse relations
        inverse_relations = self._create_inverse_relations()
        for subj, rel, obj in inverse_relations:
            self._add_discovered_relation(subj, rel, obj, 0.9)

        # 10. Process all discovered patterns
        all_patterns = (clusters + co_patterns + similarities +
                       transitive_gaps + missing_props + lonely +
                       analogies + path_sims)

        for pattern in all_patterns:
            self._process_pattern(pattern)

        # 11. Create neurons from strong patterns
        self._propose_neurons_from_patterns()

        # Update stats
        self._stats["lonely_neurons"] = len(lonely)
        self._stats["transitive_gaps"] = len(transitive_gaps)
        self._stats["missing_properties"] = len(missing_props)
        self._stats["analogies_found"] = len(analogies)

        if self.loom.verbose and all_patterns:
            print(f"       [discovery: {len(all_patterns)} patterns, {len(lonely)} lonely neurons, {len(transitive_gaps)} gaps]")

    def strengthen_weak_neurons(self, brain: "Loom"):
        """
        Find and strengthen weakly-connected neurons.

        A "weak neuron" is an entity with fewer than WEAK_NEURON_MAX_CONNECTIONS
        connections AND average connection weight below WEAK_NEURON_MAX_AVG_WEIGHT.

        For each weak neuron, use spreading activation and shared categories/properties
        to find related concepts and suggest new connections.
        """
        for entity, relations in brain.knowledge.items():
            if entity == "self":
                continue

            # Count total connections (outgoing + incoming)
            outgoing = sum(len(targets) for targets in relations.values())
            incoming = 0
            for other_entity, other_rels in brain.knowledge.items():
                if other_entity == entity:
                    continue
                for targets in other_rels.values():
                    if entity in targets:
                        incoming += 1

            total_connections = outgoing + incoming

            if total_connections >= WEAK_NEURON_MAX_CONNECTIONS:
                continue

            # Check average connection weight
            weights = []
            if hasattr(brain, 'connection_weights'):
                for key, weight in brain.connection_weights.items():
                    if entity in key:
                        weights.append(weight)

            avg_weight = sum(weights) / len(weights) if weights else 0.0

            if weights and avg_weight >= WEAK_NEURON_MAX_AVG_WEIGHT:
                continue

            # This is a weak neuron -- find related concepts to connect it

            # Strategy 1: Find entities sharing the same categories
            entity_categories = set(relations.get("is", []))
            for other_entity, other_rels in brain.knowledge.items():
                if other_entity == entity or other_entity == "self":
                    continue
                other_categories = set(other_rels.get("is", []))
                shared_cats = entity_categories & other_categories
                if shared_cats:
                    self._suggest_connection(entity, other_entity, "similar_to",
                                             0.5 + len(shared_cats) * 0.1,
                                             "weak_neuron_category")

            # Strategy 2: Find entities sharing properties
            entity_props = set()
            for rel in ["has", "can", "has_property"]:
                for val in relations.get(rel, []):
                    entity_props.add((rel, val))

            if entity_props:
                for other_entity, other_rels in brain.knowledge.items():
                    if other_entity == entity or other_entity == "self":
                        continue
                    other_props = set()
                    for rel in ["has", "can", "has_property"]:
                        for val in other_rels.get(rel, []):
                            other_props.add((rel, val))
                    shared_props = entity_props & other_props
                    if shared_props:
                        self._suggest_connection(entity, other_entity, "similar_to",
                                                 0.5 + len(shared_props) * 0.1,
                                                 "weak_neuron_property")

            # Strategy 3: Use spreading activation if available
            if hasattr(brain, 'activation'):
                brain.activation.activate(entity, amount=0.8)
                brain.activation.spread(
                    brain.knowledge,
                    brain.connection_weights if hasattr(brain, 'connection_weights') else None
                )
                coactivated = brain.activation.find_coactivated(min_sources=1)
                for node, level, sources in coactivated:
                    if node != entity and level >= 0.3:
                        self._suggest_connection(entity, node, "related_to",
                                                 min(0.8, level),
                                                 "weak_neuron_activation")

            if brain.verbose:
                print(f"       [weak neuron: {entity} ({total_connections} connections, "
                      f"avg weight {avg_weight:.2f}) — seeking new links]")

    def _suggest_connection(self, entity1: str, entity2: str, relation: str,
                            confidence: float, method: str):
        """Suggest a new connection between two entities from weak neuron strengthening."""
        # Use existing quality checks from _add_discovered_relation
        if not self._is_valid_entity(entity1) or not self._is_valid_entity(entity2):
            return

        existing = self.loom.get(entity1, relation) or []
        if entity2 in existing:
            return

        # Only add if confidence meets threshold
        if confidence < MIN_DISCOVERY_CONFIDENCE:
            return

        provenance = {
            "source_type": "discovery",
            "method": method,
            "confidence": confidence,
            "timestamp": time.time()
        }

        conf_level = CONFIDENCE_HIGH if confidence >= 0.8 else CONFIDENCE_MEDIUM
        self.loom.add_fact(entity1, relation, entity2, confidence=conf_level, provenance=provenance)
        self._stats["relations_added"] += 1

        if self.loom.verbose:
            print(f"       [strengthened: {entity1} {relation} {entity2} "
                  f"(confidence: {confidence:.2f}, via {method})]")

    def _find_property_clusters(self) -> List[DiscoveredPattern]:
        """
        Find clusters of entities sharing 2+ properties.
        Example: cat, dog, lion all have fur and are mammals.
        """
        patterns = []

        # Build property index: (relation, value) -> set of entities
        property_index: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
        property_relations = ["has", "can", "is", "eats", "needs", "lives_in"]

        for entity, relations in self.loom.knowledge.items():
            if entity == "self":
                continue
            for rel in property_relations:
                if rel in relations:
                    for value in relations[rel]:
                        property_index[(rel, value)].add(entity)

        # Build entity property sets
        entity_properties: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)
        for (rel, val), entities in property_index.items():
            for entity in entities:
                entity_properties[entity].add((rel, val))

        # Find pairs sharing 2+ properties
        entities = list(entity_properties.keys())
        for i, e1 in enumerate(entities):
            for e2 in entities[i + 1:]:
                shared = entity_properties[e1] & entity_properties[e2]
                if len(shared) >= 2:
                    shared_props = defaultdict(list)
                    for rel, val in shared:
                        shared_props[rel].append(val)

                    pattern = DiscoveredPattern(
                        pattern_type="cluster",
                        entities=[e1, e2],
                        shared_properties=dict(shared_props),
                        support_count=len(shared),
                        confidence=min(0.8, 0.3 + len(shared) * 0.15)
                    )
                    patterns.append(pattern)

        return patterns

    def _analyze_co_occurrence(self) -> List[DiscoveredPattern]:
        """Find entities that frequently co-occur in statements."""
        patterns = []

        for (e1, e2), count in self._co_occurrence.items():
            if count >= MIN_PATTERN_SUPPORT:
                pattern = DiscoveredPattern(
                    pattern_type="co_occurrence",
                    entities=[e1, e2],
                    shared_properties={},
                    support_count=count,
                    confidence=min(0.9, 0.4 + count * 0.1)
                )
                patterns.append(pattern)

        return patterns

    def _find_structural_similarities(self) -> List[DiscoveredPattern]:
        """
        Find entities with similar relation patterns.
        Entities with same relations suggest similar types.
        """
        patterns = []

        # Build structure signatures
        signatures: Dict[str, Set[str]] = {}
        for entity, relations in self.loom.knowledge.items():
            if entity == "self":
                continue
            sig = frozenset(relations.keys())
            if len(sig) >= 2:
                signatures[entity] = sig

        # Compare signatures
        entities = list(signatures.keys())
        for i, e1 in enumerate(entities):
            for e2 in entities[i + 1:]:
                overlap = signatures[e1] & signatures[e2]
                total = signatures[e1] | signatures[e2]

                if len(total) > 0:
                    jaccard = len(overlap) / len(total)
                    if jaccard >= 0.5 and len(overlap) >= 2:
                        pattern = DiscoveredPattern(
                            pattern_type="structural",
                            entities=[e1, e2],
                            shared_properties={"relations": list(overlap)},
                            support_count=len(overlap),
                            confidence=jaccard
                        )
                        patterns.append(pattern)

        return patterns

    def _find_transitive_gaps(self) -> List[DiscoveredPattern]:
        """
        Find transitive gaps: if A→B and B→C, suggest A→C.
        Works for transitive relations like 'is', 'part_of', 'causes'.
        """
        patterns = []
        transitive_relations = ["is", "part_of", "causes", "leads_to", "contains"]

        for rel in transitive_relations:
            # Build adjacency for this relation
            adjacency: Dict[str, Set[str]] = defaultdict(set)
            for entity, relations in self.loom.knowledge.items():
                if rel in relations:
                    for target in relations[rel]:
                        adjacency[entity].add(target)

            # Find gaps: A→B→C but no A→C
            for a, b_set in adjacency.items():
                for b in b_set:
                    if b in adjacency:
                        for c in adjacency[b]:
                            # Check if A→C is missing
                            if c not in adjacency[a] and a != c:
                                pattern = DiscoveredPattern(
                                    pattern_type="transitive_gap",
                                    entities=[a, c],
                                    shared_properties={
                                        "relation": [rel],
                                        "via": [b]
                                    },
                                    support_count=1,
                                    confidence=0.75
                                )
                                patterns.append(pattern)

        return patterns

    def _find_missing_properties(self) -> List[DiscoveredPattern]:
        """
        Find missing properties: if 80%+ of category members have property X,
        suggest it for members missing X.
        """
        patterns = []
        threshold = 0.7  # 70% of members must have property

        # Get all categories and their instances
        categories: Dict[str, Set[str]] = defaultdict(set)
        for entity, relations in self.loom.knowledge.items():
            if "is" in relations:
                for cat in relations["is"]:
                    categories[cat].add(entity)

        # For each category with 3+ members
        for category, members in categories.items():
            if len(members) < 3:
                continue

            # Count property occurrences across members
            property_counts: Dict[Tuple[str, str], int] = defaultdict(int)
            member_properties: Dict[str, Set[Tuple[str, str]]] = {}

            for member in members:
                member_rels = self.loom.knowledge.get(member, {})
                member_properties[member] = set()

                for rel in ["has", "can", "has_property", "eats", "lives_in"]:
                    if rel in member_rels:
                        for val in member_rels[rel]:
                            prop = (rel, val)
                            property_counts[prop] += 1
                            member_properties[member].add(prop)

            # Find properties present in 70%+ of members
            for prop, count in property_counts.items():
                ratio = count / len(members)
                if ratio >= threshold:
                    # Find members missing this property
                    for member in members:
                        if prop not in member_properties[member]:
                            pattern = DiscoveredPattern(
                                pattern_type="missing_property",
                                entities=[member],
                                shared_properties={
                                    "suggested_relation": [prop[0]],
                                    "suggested_value": [prop[1]],
                                    "category": [category],
                                    "coverage": [f"{ratio:.0%}"]
                                },
                                support_count=count,
                                confidence=ratio
                            )
                            patterns.append(pattern)

        return patterns

    def _find_lonely_neurons(self) -> List[DiscoveredPattern]:
        """
        Find neurons with very few connections (0-2).
        These are candidates for exploration and new connections.
        """
        patterns = []

        for entity, relations in self.loom.knowledge.items():
            if entity == "self":
                continue

            # Count total connections
            connection_count = sum(len(targets) for targets in relations.values())

            # Also count incoming connections
            incoming = 0
            for other_entity, other_rels in self.loom.knowledge.items():
                if other_entity == entity:
                    continue
                for targets in other_rels.values():
                    if entity in targets:
                        incoming += 1

            total_connections = connection_count + incoming

            if total_connections <= 2:
                pattern = DiscoveredPattern(
                    pattern_type="lonely_neuron",
                    entities=[entity],
                    shared_properties={
                        "outgoing": [str(connection_count)],
                        "incoming": [str(incoming)],
                        "total": [str(total_connections)]
                    },
                    support_count=1,
                    confidence=1.0 - (total_connections * 0.3)  # Less connections = higher priority
                )
                patterns.append(pattern)

        return patterns

    def _create_inverse_relations(self) -> List[Tuple[str, str, str]]:
        """
        Create inverse relations automatically.
        e.g., 'cats eat fish' → 'fish eaten_by cats'
        """
        created = []
        inverse_map = {
            "eats": "eaten_by",
            "contains": "contained_in",
            "causes": "caused_by",
            "has": "belongs_to",
            "teaches": "taught_by",
            "creates": "created_by",
            "kills": "killed_by",
            "helps": "helped_by",
            "needs": "needed_by",
            "produces": "produced_by"
        }

        for entity, relations in self.loom.knowledge.items():
            if entity == "self":
                continue

            for rel, targets in relations.items():
                if rel in inverse_map:
                    inverse_rel = inverse_map[rel]
                    for target in targets:
                        # Check if inverse already exists
                        target_rels = self.loom.knowledge.get(target, {})
                        existing = target_rels.get(inverse_rel, [])
                        if entity not in existing:
                            created.append((target, inverse_rel, entity))

        return created

    def _find_analogies(self) -> List[DiscoveredPattern]:
        """
        Find analogy patterns: A:B :: C:?
        If dog:mammal and eagle has similar structure, suggest eagle:bird.
        """
        patterns = []

        # Build entity-category pairs
        entity_categories: Dict[str, List[str]] = {}
        category_members: Dict[str, List[str]] = defaultdict(list)

        for entity, relations in self.loom.knowledge.items():
            if "is" in relations:
                entity_categories[entity] = relations["is"]
                for cat in relations["is"]:
                    category_members[cat].append(entity)

        # Find entities with similar properties but different/missing categories
        for e1, cats1 in entity_categories.items():
            e1_rels = self.loom.knowledge.get(e1, {})

            for e2, e2_rels in self.loom.knowledge.items():
                if e1 == e2 or e2 == "self":
                    continue

                cats2 = entity_categories.get(e2, [])

                # Check if they share properties but have different categories
                shared_props = 0
                for rel in ["can", "has", "eats", "lives_in"]:
                    vals1 = set(e1_rels.get(rel, []))
                    vals2 = set(e2_rels.get(rel, []))
                    shared_props += len(vals1 & vals2)

                if shared_props >= 2:
                    # They're similar - check if e2 is missing a category that e1 has
                    for cat in cats1:
                        if cat not in cats2:
                            # Check if there's an analogous category for e2
                            # by looking at what similar entities are
                            sibling_cats = set()
                            for sibling in category_members.get(cat, []):
                                if sibling != e1:
                                    sibling_rels = self.loom.knowledge.get(sibling, {})
                                    sibling_cats.update(sibling_rels.get("is", []))

                            # Suggest categories that siblings have but e2 doesn't
                            for suggested_cat in sibling_cats:
                                if suggested_cat not in cats2 and suggested_cat != cat:
                                    pattern = DiscoveredPattern(
                                        pattern_type="analogy",
                                        entities=[e2, suggested_cat],
                                        shared_properties={
                                            "similar_to": [e1],
                                            "shared_properties": [str(shared_props)],
                                            "analogy_base": [f"{e1}:{cat}"]
                                        },
                                        support_count=shared_props,
                                        confidence=0.5 + (shared_props * 0.1)
                                    )
                                    patterns.append(pattern)

        return patterns[:20]  # Limit to top 20 to avoid explosion

    def _find_path_similarities(self) -> List[DiscoveredPattern]:
        """
        Find entities connected through similar intermediate nodes.
        If A→X→B and C→X→D, then A~C and B~D might be related.
        """
        patterns = []

        # Build paths through intermediate nodes
        # path_through[intermediate] = [(source, target, relation), ...]
        path_through: Dict[str, List[Tuple[str, str, str]]] = defaultdict(list)

        for entity, relations in self.loom.knowledge.items():
            if entity == "self":
                continue
            for rel, targets in relations.items():
                for target in targets:
                    path_through[target].append((entity, target, rel))

        # Find entities that connect to the same intermediates
        for intermediate, connections in path_through.items():
            if len(connections) < 2:
                continue

            # Group by relation type
            by_relation: Dict[str, List[str]] = defaultdict(list)
            for source, _, rel in connections:
                by_relation[rel].append(source)

            # Entities using same relation to same intermediate are similar
            for rel, sources in by_relation.items():
                if len(sources) >= 2:
                    for i, s1 in enumerate(sources):
                        for s2 in sources[i + 1:]:
                            pattern = DiscoveredPattern(
                                pattern_type="path_similar",
                                entities=[s1, s2],
                                shared_properties={
                                    "via": [intermediate],
                                    "relation": [rel]
                                },
                                support_count=1,
                                confidence=0.6
                            )
                            patterns.append(pattern)

        return patterns[:30]  # Limit results

    def _process_pattern(self, pattern: DiscoveredPattern):
        """Process a discovered pattern - track and possibly create relations."""
        pattern_key = f"{pattern.pattern_type}_{'-'.join(sorted(pattern.entities))}"

        if pattern_key in self._patterns:
            existing = self._patterns[pattern_key]
            existing.support_count += 1
            existing.confidence = min(0.95, existing.confidence + 0.05)
        else:
            self._patterns[pattern_key] = pattern
            self._stats["patterns_found"] += 1

        # If strong enough, suggest relations
        stored = self._patterns[pattern_key]
        if stored.support_count >= MIN_PATTERN_SUPPORT:
            self._suggest_relations(stored)

    def _suggest_relations(self, pattern: DiscoveredPattern):
        """Suggest new relations based on strong patterns (conservative)."""
        # Only suggest relations for very high confidence patterns
        if pattern.confidence < MIN_DISCOVERY_CONFIDENCE:
            return

        if len(pattern.entities) < 1:
            return

        e1 = pattern.entities[0]
        e2 = pattern.entities[1] if len(pattern.entities) > 1 else None

        # Add discovery relations (quality-gated by _add_discovered_relation)
        if pattern.pattern_type == "cluster" and e2:
            self._add_discovered_relation(e1, "similar_to", e2, pattern.confidence)
        elif pattern.pattern_type == "path_similar" and e2:
            self._add_discovered_relation(e1, "related_to", e2, pattern.confidence)
        elif pattern.pattern_type == "co_occurrence" and e2:
            self._add_discovered_relation(e1, "associated_with", e2, pattern.confidence)
        elif pattern.pattern_type == "transitive_gap" and e2:
            self._add_discovered_relation(e1, "related_to", e2, pattern.confidence)

    def _is_valid_entity(self, name: str) -> bool:
        """Check if an entity name is valid (not polluted/malformed)."""
        if not name or len(name) < 2:
            return False
        # Reject names with repeated words (pollution indicator)
        words = name.lower().replace("_", " ").split()
        if len(words) != len(set(words)):
            return False  # Has duplicate words
        # Reject very long names (likely malformed)
        if len(name) > 50:
            return False
        # Reject names with "group" unless it's a simple pattern
        if "group" in name.lower() and name.count("_") > 2:
            return False
        # Reject names with periods or other weird characters
        if "." in name or "," in name:
            return False
        # Reject names that look like sentences
        if len(words) > 5:
            return False
        return True

    def _add_discovered_relation(self, subj: str, rel: str, obj: str, confidence: float):
        """Add a relation discovered by the system (with strict quality control)."""
        # Quality gate: validate entity names
        if not self._is_valid_entity(subj) or not self._is_valid_entity(obj):
            return

        # Quality gate: minimum confidence
        if confidence < MIN_DISCOVERY_CONFIDENCE:
            return

        # Quality gate: prevent pollution - limit relations added per cycle
        if self._stats["relations_added"] >= MAX_RELATIONS_PER_CYCLE:
            return

        # Quality gate: don't add relations to/from "group" entities
        if "group" in subj.lower() or "group" in obj.lower():
            return

        # Quality gate: don't add if already exists
        existing = self.loom.get(subj, rel) or []
        if obj in existing:
            return

        # Quality gate: only add specific relation types
        allowed_relations = {"similar_to", "related_to", "associated_with"}
        if rel not in allowed_relations:
            return

        provenance = {
            "source_type": "discovery",
            "method": "pattern_analysis",
            "confidence": confidence,
            "timestamp": time.time()
        }

        conf_level = CONFIDENCE_HIGH if confidence >= 0.8 else CONFIDENCE_MEDIUM
        self.loom.add_fact(subj, rel, obj, confidence=conf_level, provenance=provenance)
        self._stats["relations_added"] += 1

        if self.loom.verbose:
            print(f"       [discovered: {subj} {rel} {obj}]")

    def _propose_neurons_from_patterns(self):
        """Propose new neurons from strong cluster patterns."""
        # DISABLED: Auto neuron creation was causing pollution
        # Only create neurons when explicitly requested
        if not AUTO_CREATE_NEURONS:
            return

        # Find clusters with 3+ members
        cluster_members: Dict[str, Set[str]] = defaultdict(set)
        cluster_properties: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))

        for pattern_key, pattern in self._patterns.items():
            if pattern.pattern_type == "cluster" and pattern.support_count >= 2:
                prop_key = str(sorted(pattern.shared_properties.items()))
                for entity in pattern.entities:
                    cluster_members[prop_key].add(entity)
                for rel, values in pattern.shared_properties.items():
                    for val in values:
                        cluster_properties[prop_key][rel].add(val)

        # Create neurons for large clusters
        for prop_key, members in cluster_members.items():
            if len(members) >= 3:
                props = cluster_properties[prop_key]

                # Generate name from properties
                name_parts = []
                for rel, values in props.items():
                    if rel in ["has", "can", "is"]:
                        name_parts.extend(list(values)[:1])

                if not name_parts:
                    continue

                neuron_name = "_".join(name_parts[:2]) + "_group"

                if neuron_name in self._created_neurons:
                    continue

                neuron = DiscoveredNeuron(
                    name=neuron_name,
                    neuron_type="category",
                    members=list(members),
                    properties={rel: list(vals) for rel, vals in props.items()},
                    provenance={"source": "cluster_analysis", "members": len(members)},
                    confidence=0.7
                )
                self._pending_neurons.append(neuron)

    def create_pending_neurons(self) -> List[str]:
        """Create pending neurons in knowledge graph. Returns created names."""
        created = []

        for neuron in self._pending_neurons:
            if neuron.name in self._created_neurons:
                continue

            # Add properties to the new neuron
            for rel, values in neuron.properties.items():
                for val in values:
                    self.loom.add_fact(neuron.name, rel, val, confidence=CONFIDENCE_MEDIUM)

            # Link members to the new category
            for member in neuron.members:
                self.loom.add_fact(member, "is", neuron.name, confidence=CONFIDENCE_MEDIUM)

            self._created_neurons.add(neuron.name)
            self._stats["neurons_created"] += 1
            created.append(neuron.name)

            if self.loom.verbose:
                print(f"       [created neuron: {neuron.name} with {len(neuron.members)} members]")

        self._pending_neurons.clear()
        return created

    def get_pending_neurons(self) -> List[DiscoveredNeuron]:
        """Get pending neuron suggestions."""
        return self._pending_neurons.copy()

    def get_statistics(self) -> dict:
        """Get discovery statistics."""
        return {
            **self._stats,
            "pending_neurons": len(self._pending_neurons),
            "co_occurrence_pairs": len(self._co_occurrence),
            "patterns_tracked": len(self._patterns)
        }

    def get_visualization_data(self) -> dict:
        """
        Get discovery data formatted for visualization.
        Returns lonely neurons, suggested connections, clusters, etc.
        """
        # Find lonely neurons
        lonely_neurons = []
        for entity, relations in self.loom.knowledge.items():
            if entity == "self":
                continue
            outgoing = sum(len(targets) for targets in relations.values())
            incoming = 0
            for other_entity, other_rels in self.loom.knowledge.items():
                if other_entity == entity:
                    continue
                for targets in other_rels.values():
                    if entity in targets:
                        incoming += 1
            total = outgoing + incoming
            if total <= 2:
                lonely_neurons.append({
                    "id": entity,
                    "connections": total,
                    "priority": 1.0 - (total * 0.3)
                })

        # Get suggested connections from patterns
        suggested_connections = []
        for pattern_key, pattern in self._patterns.items():
            if pattern.confidence >= 0.5 and len(pattern.entities) >= 2:
                suggested_connections.append({
                    "source": pattern.entities[0],
                    "target": pattern.entities[1],
                    "type": pattern.pattern_type,
                    "confidence": pattern.confidence,
                    "support": pattern.support_count,
                    "properties": pattern.shared_properties
                })

        # Get clusters (groups of similar entities)
        clusters = []
        cluster_groups: Dict[str, Set[str]] = defaultdict(set)
        for pattern_key, pattern in self._patterns.items():
            if pattern.pattern_type == "cluster" and pattern.confidence >= 0.6:
                prop_key = str(sorted(pattern.shared_properties.items()))
                for entity in pattern.entities:
                    cluster_groups[prop_key].add(entity)

        for prop_key, members in cluster_groups.items():
            if len(members) >= 2:
                clusters.append({
                    "members": list(members),
                    "size": len(members)
                })

        # Get transitive gaps
        transitive_gaps = []
        for pattern_key, pattern in self._patterns.items():
            if pattern.pattern_type == "transitive_gap":
                transitive_gaps.append({
                    "source": pattern.entities[0],
                    "target": pattern.entities[1],
                    "via": pattern.shared_properties.get("via", [""])[0],
                    "relation": pattern.shared_properties.get("relation", ["is"])[0],
                    "confidence": pattern.confidence
                })

        # Get missing properties
        missing_properties = []
        for pattern_key, pattern in self._patterns.items():
            if pattern.pattern_type == "missing_property":
                missing_properties.append({
                    "entity": pattern.entities[0],
                    "suggested_relation": pattern.shared_properties.get("suggested_relation", [""])[0],
                    "suggested_value": pattern.shared_properties.get("suggested_value", [""])[0],
                    "category": pattern.shared_properties.get("category", [""])[0],
                    "coverage": pattern.shared_properties.get("coverage", [""])[0],
                    "confidence": pattern.confidence
                })

        return {
            "lonely_neurons": lonely_neurons,
            "suggested_connections": suggested_connections[:50],  # Limit for performance
            "clusters": clusters[:20],
            "transitive_gaps": transitive_gaps[:30],
            "missing_properties": missing_properties[:30],
            "statistics": self.get_statistics()
        }
