"""
Inference engine for Loom.
Weaves new threads through hypothetical syllogism and background reasoning.

Enhanced with:
- Immediate activation-based inference
- Co-activation pattern detection
- Hebbian connection strengthening during inference
- Provenance tracking for inferred facts
"""

import threading
import time
from typing import List, Set, Tuple, Optional
from datetime import datetime
import uuid

from .normalizer import prettify_cause, prettify_effect


# Relations that support transitive chaining (P->Q, Q->R => P->R)
TRANSITIVE_RELATIONS = ["looks_like", "is", "causes", "leads_to", "part_of"]

# Relations that suggest category membership (for property inheritance)
CATEGORY_RELATIONS = ["is", "is_a", "type_of", "kind_of"]

# Relations where properties should propagate
PROPERTY_RELATIONS = ["has", "can", "color", "size", "shape"]

# Category bridging relations
BRIDGE_RELATIONS = ["equivalent_to", "overlaps_with", "subset_of", "similar_to"]


class InferenceEngine:
    """
    Handles background reasoning and transitive inference.

    Enhanced with activation-based immediate inference for faster
    connection discovery during conversation.
    """

    def __init__(self, loom):
        self.loom = loom
        self.inferences = []  # Track inferred facts
        self.running = True
        self._thread = None

        # Track recently inferred to avoid duplicates
        self._recent_inferences: Set[Tuple[str, str, str]] = set()

    def _create_provenance(self, source_type: str, premises: List[dict],
                           rule_id: str = None) -> dict:
        """
        Create provenance metadata for an inferred fact.

        Args:
            source_type: Type of source ("inference", "inheritance", etc.)
            premises: List of premise dicts with subject, relation, object
            rule_id: Identifier for the inference rule used

        Returns:
            Provenance dict ready for storage
        """
        return {
            "source_type": source_type,
            "premises": premises,
            "rule_id": rule_id,
            "created_at": datetime.utcnow().isoformat(),
            "speaker_id": None,
            "derivation_id": str(uuid.uuid4())[:8],
        }

    def start(self):
        """Start the background inference thread."""
        self._thread = threading.Thread(target=self._background_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the background inference thread."""
        self.running = False

    def process_immediate(self, subject: str, relation: str, obj: str):
        """
        Process inference immediately when a fact is added.

        Enhanced with:
        - Activation-based co-activation detection
        - Hebbian connection strengthening
        - Property inheritance through categories
        - Co-occurrence tracking for background discovery
        """
        # Track co-occurrence for background discovery
        if hasattr(self.loom, 'discovery_engine'):
            self.loom.discovery_engine.track_co_occurrence([subject, obj])

        # Activate both subject and object in the activation network
        if hasattr(self.loom, 'activation'):
            self.loom.activation.activate(subject, amount=1.0)
            self.loom.activation.activate(obj, amount=1.0)

            # Spread activation to find connections
            self.loom.activation.spread(
                self.loom.knowledge,
                self.loom.connection_weights if hasattr(self.loom, 'connection_weights') else None
            )

            # Check for co-activated nodes (potential new connections)
            coactivated = self.loom.activation.find_coactivated(min_sources=2)
            self._process_coactivation(subject, obj, coactivated)

        # Strengthen the direct connection (Hebbian learning)
        if hasattr(self.loom, 'strengthen_connection'):
            self.loom.strengthen_connection(subject, relation, obj)

        # Quick property propagation for analogies
        if relation == "looks_like":
            self.loom.copy_properties(subject, obj)
            self.loom.copy_properties(obj, subject)

        # Property inheritance through category membership
        if relation in CATEGORY_RELATIONS:
            self._inherit_properties(subject, obj)

        # Quick syllogism check for transitive relations
        if relation in TRANSITIVE_RELATIONS:
            self._check_chain_from(subject, relation)
            # Also check nodes pointing to subject
            for node in list(self.loom.knowledge.keys()):
                targets = self.loom.get(node, relation) or []
                if subject in targets:
                    self._check_chain_from(node, relation)

    def _process_coactivation(self, subject: str, obj: str,
                               coactivated: List[Tuple[str, float, Set[str]]]):
        """
        Process co-activated nodes to discover implicit connections.

        When subject and object both activate a third node, this suggests
        they share a relationship through that concept.
        """
        for node, level, sources in coactivated:
            # Skip if it's one of our original nodes
            if node in (subject, obj):
                continue

            # Check if both subject and object contributed
            if subject in sources and obj in sources:
                # This node is co-activated by both - they share something
                inference_key = (subject, "shares", node)

                if inference_key not in self._recent_inferences:
                    self._recent_inferences.add(inference_key)

                    # Strengthen connections through this node
                    if hasattr(self.loom, 'strengthen_connection'):
                        self.loom.strengthen_connection(subject, "related_through", node)
                        self.loom.strengthen_connection(obj, "related_through", node)

                    if self.loom.verbose:
                        print(f"       [co-activation: {subject} & {obj} share {node}]")

        # Limit recent inferences cache
        if len(self._recent_inferences) > 500:
            # Clear older half
            self._recent_inferences = set(list(self._recent_inferences)[-250:])

    def _inherit_properties(self, instance: str, category: str):
        """
        Inherit properties from category to instance.

        Example: If dogs is mammals, and mammals has fur,
        then dogs should inherit has fur.
        """
        category_facts = self.loom.knowledge.get(category, {})

        for relation in PROPERTY_RELATIONS:
            if relation in category_facts:
                for value in category_facts[relation]:
                    # Check if instance already has this
                    existing = self.loom.get(instance, relation) or []
                    if value not in existing:
                        # Create provenance tracking the inheritance
                        provenance = self._create_provenance(
                            source_type="inheritance",
                            premises=[
                                {"subject": instance, "relation": "is", "object": category},
                                {"subject": category, "relation": relation, "object": value}
                            ],
                            rule_id="property_inheritance"
                        )

                        # Inherit with medium confidence
                        self.loom.add_fact(instance, relation, value,
                                          confidence="medium", _save=True,
                                          provenance=provenance)
                        self.inferences.append((instance, relation, value, 1))

                        if self.loom.verbose:
                            print(f"       [inherited: {instance} {relation} {value} from {category}]")

    def _background_loop(self):
        """
        Main background processing loop.

        Enhanced with:
        - Connection weight decay (Hebbian pruning)
        - Deeper transitive inference
        - Pattern consolidation
        - Curiosity engine question generation
        """
        cycle_count = 0

        while self.running:
            time.sleep(3)
            cycle_count += 1

            # Decay activations periodically
            if hasattr(self.loom, 'activation'):
                self.loom.activation.decay()

            # Decay connection weights every 10 cycles (30 seconds)
            if cycle_count % 10 == 0 and hasattr(self.loom, 'decay_all_connections'):
                self.loom.decay_all_connections(elapsed_threshold=120.0)

            # Run curiosity engine every 5 cycles (15 seconds)
            if cycle_count % 5 == 0 and hasattr(self.loom, 'curiosity'):
                self.loom.curiosity.run_cycle()

            # Cleanup expired curiosity nodes every 20 cycles (60 seconds)
            if cycle_count % 20 == 0 and hasattr(self.loom, 'curiosity_nodes'):
                expired = self.loom.curiosity_nodes.cleanup_expired()
                if expired and self.loom.verbose:
                    print(f"       [curiosity cleanup: {expired} nodes expired]")

            # Run forward chaining every 3 cycles (9 seconds)
            if cycle_count % 3 == 0 and hasattr(self.loom, 'rule_engine'):
                derived = self.loom.rule_engine.run_forward_chain(max_iterations=3)
                if derived and self.loom.verbose:
                    print(f"       [forward chain: {len(derived)} facts derived]")

            # Run connection discovery every 10 cycles (30 seconds)
            if cycle_count % 10 == 0 and hasattr(self.loom, 'discovery_engine'):
                self.loom.discovery_engine.run_background_discovery()
                # Auto-create neurons from strong patterns
                created = self.loom.discovery_engine.create_pending_neurons()
                if created and self.loom.verbose:
                    print(f"       [discovery: created {len(created)} new neurons]")

            # Detect category bridges every 4 cycles (12 seconds)
            if cycle_count % 4 == 0:
                bridges = self.detect_category_bridges()
                if bridges and self.loom.verbose:
                    print(f"       [bridges: created {len(bridges)} category connections]")

            if not self.loom.recent:
                continue

            batch = self.loom.recent[:]
            self.loom.recent.clear()

            for subj, rel, obj in batch:
                # Apply transitive chaining (hypothetical syllogism)
                if rel in TRANSITIVE_RELATIONS:
                    self._apply_syllogism(subj, rel)

                # Copy properties across analogy links
                if rel in ("looks_like", "color", "is"):
                    self._propagate_properties(subj)

                # Deep property inheritance for category membership
                if rel in CATEGORY_RELATIONS:
                    self._deep_inherit(subj, rel)

    def _propagate_properties(self, subject: str):
        """Copy properties across looks_like relationships."""
        for other in list(self.loom.knowledge.keys()):
            if other != subject:
                if (self.loom.get(other, "looks_like") == [subject] or
                        self.loom.get(subject, "looks_like") == [other]):
                    self.loom.copy_properties(other, subject)
                    self.loom.copy_properties(subject, other)

                    # Strengthen the connection
                    if hasattr(self.loom, 'strengthen_connection'):
                        self.loom.strengthen_connection(subject, "looks_like", other, 0.1)

    def _deep_inherit(self, instance: str, relation: str, depth: int = 0, max_depth: int = 3):
        """
        Recursively inherit properties through category chains.

        Example: poodle is dog, dog is mammal, mammal has fur
        -> poodle inherits has fur
        """
        if depth >= max_depth:
            return

        # Get what instance is a member of
        categories = self.loom.get(instance, relation) or []

        for category in categories:
            # Inherit properties from this category
            self._inherit_properties(instance, category)

            # Recursively check parent categories
            self._deep_inherit(category, relation, depth + 1, max_depth)

    def transitive_chain(self, start: str, relation: str,
                         visited: set = None, depth: int = 0,
                         max_depth: int = 5) -> list:
        """
        Hypothetical Syllogism: If P->Q and Q->R, then P->R.
        Follows chains up to max_depth to avoid infinite loops.
        Returns list of (target, depth) tuples.
        """
        if visited is None:
            visited = set()
        if depth >= max_depth or start in visited:
            return []

        visited.add(start)
        reachable = []

        direct = self.loom.get(start, relation) or []
        for target in direct:
            if target not in visited:
                reachable.append((target, depth + 1))
                # Recurse to find indirect connections
                indirect = self.transitive_chain(
                    target, relation, visited.copy(), depth + 1, max_depth
                )
                reachable.extend(indirect)

        return reachable

    def _apply_syllogism(self, subject: str, relation: str):
        """
        Apply hypothetical syllogism and create inferred connections.
        If A->B and B->C, create A->C (marked as inferred).
        """
        if relation not in TRANSITIVE_RELATIONS:
            return

        # Check chain FROM this subject
        self._check_chain_from(subject, relation)

        # Also check all nodes that point TO this subject
        # (they might now have longer chains)
        for node in list(self.loom.knowledge.keys()):
            targets = self.loom.get(node, relation) or []
            if subject in targets:
                self._check_chain_from(node, relation)

    def _check_chain_from(self, subject: str, relation: str):
        """Check and record transitive inferences from a subject."""
        chain = self.transitive_chain(subject, relation)
        direct = self.loom.get(subject, relation) or []

        for target, depth in chain:
            if depth > 1 and target not in direct:
                # Check if we already have this inference
                existing = self.loom.get(subject, relation) or []
                if target not in existing:
                    # Build the chain of premises for provenance
                    premises = self._build_chain_premises(subject, relation, target)

                    provenance = self._create_provenance(
                        source_type="inference",
                        premises=premises,
                        rule_id="transitive_chain"
                    )

                    self.inferences.append((subject, relation, target, depth))
                    if self.loom.verbose:
                        subj_pretty = prettify_cause(subject)
                        targ_pretty = prettify_effect(target)
                        print(f"       [inferred: {subj_pretty} ~> {targ_pretty}]")
                    self.loom.add_fact(subject, relation, target,
                                       confidence="medium", provenance=provenance)
                    self.loom.copy_properties(subject, target)

    def _build_chain_premises(self, start: str, relation: str, end: str) -> List[dict]:
        """
        Build the list of premises that form the transitive chain.
        For A->B->C, returns [{A,rel,B}, {B,rel,C}]
        """
        premises = []
        current = start

        # Simple BFS to find the path
        visited = {start}
        parent = {start: None}
        queue = [start]

        while queue:
            node = queue.pop(0)
            if node == end:
                break

            targets = self.loom.get(node, relation) or []
            for t in targets:
                if t not in visited:
                    visited.add(t)
                    parent[t] = node
                    queue.append(t)

        # Reconstruct path and build premises
        if end in parent:
            path = []
            current = end
            while parent.get(current) is not None:
                path.append(current)
                current = parent[current]
            path.append(start)
            path.reverse()

            for i in range(len(path) - 1):
                premises.append({
                    "subject": path[i],
                    "relation": relation,
                    "object": path[i + 1]
                })

        return premises

    def get_inferences(self) -> list:
        """Return all inferred facts."""
        return self.inferences.copy()

    def find_analogies(self, concept: str) -> List[Tuple[str, float]]:
        """
        Find concepts analogous to the given concept based on shared properties.

        Uses co-activation patterns and property overlap.
        """
        analogies = []
        concept_data = self.loom.knowledge.get(concept, {})

        if not concept_data:
            return analogies

        # Get concept's properties
        concept_props = set()
        for rel in PROPERTY_RELATIONS:
            if rel in concept_data:
                for val in concept_data[rel]:
                    concept_props.add((rel, val))

        if not concept_props:
            return analogies

        # Compare with other concepts
        for other, other_data in self.loom.knowledge.items():
            if other == concept:
                continue

            other_props = set()
            for rel in PROPERTY_RELATIONS:
                if rel in other_data:
                    for val in other_data[rel]:
                        other_props.add((rel, val))

            if not other_props:
                continue

            # Calculate similarity (Jaccard)
            intersection = len(concept_props & other_props)
            union = len(concept_props | other_props)

            if union > 0 and intersection > 0:
                similarity = intersection / union
                if similarity >= 0.3:  # Threshold for analogy
                    analogies.append((other, similarity))

        # Sort by similarity
        analogies.sort(key=lambda x: x[1], reverse=True)
        return analogies[:5]

    def infer_from_analogy(self, concept: str) -> List[Tuple[str, str, str]]:
        """
        Infer new facts about a concept based on analogous concepts.

        If A is similar to B, and B has property P, maybe A has P too.
        """
        new_facts = []
        analogies = self.find_analogies(concept)

        concept_data = self.loom.knowledge.get(concept, {})

        for analog, similarity in analogies:
            analog_data = self.loom.knowledge.get(analog, {})

            # Check what the analog has that concept doesn't
            for rel in PROPERTY_RELATIONS:
                analog_vals = set(analog_data.get(rel, []))
                concept_vals = set(concept_data.get(rel, []))

                # Properties analog has that concept doesn't
                missing = analog_vals - concept_vals

                for val in missing:
                    # Only infer if similarity is high enough
                    if similarity >= 0.5:
                        new_facts.append((concept, rel, val))

                        if self.loom.verbose:
                            print(f"       [analogy inference: {concept} {rel} {val} "
                                  f"(from {analog}, sim={similarity:.2f})]")

        return new_facts

    def consolidate_knowledge(self):
        """
        Background consolidation - find patterns and strengthen connections.

        Called periodically to:
        1. Find frequently co-occurring concepts
        2. Strengthen reliable inferences
        3. Prune weak connections
        """
        # Find concepts that frequently appear together
        co_occurrence = {}

        for node, relations in self.loom.knowledge.items():
            for rel, targets in relations.items():
                for target in targets:
                    pair = tuple(sorted([node, target]))
                    co_occurrence[pair] = co_occurrence.get(pair, 0) + 1

        # Strengthen frequently co-occurring concepts
        for (a, b), count in co_occurrence.items():
            if count >= 3:  # Threshold
                if hasattr(self.loom, 'strengthen_connection'):
                    self.loom.strengthen_connection(a, "frequently_with", b, 0.1 * count)

    def detect_category_bridges(self) -> List[Tuple[str, str, str]]:
        """
        Detect categories that should be connected because they share instances.

        Logic:
        1. Find all categories (entities that have incoming "is" relations)
        2. For each entity, collect all categories it belongs to (transitively)
        3. Group entities by the categories they belong to
        4. Compare category pairs:
           - If same instances: equivalent_to (synonyms)
           - If A's instances ⊂ B's instances: A subset_of B
           - If partial overlap: overlaps_with

        Returns list of (category1, relation, category2) bridges created.
        """
        bridges_created = []

        # Step 1: Build entity -> categories mapping (with transitive closure)
        entity_to_categories = {}

        for entity in list(self.loom.knowledge.keys()):
            # Get all categories this entity belongs to
            categories = self._get_all_categories(entity)
            if categories:
                entity_to_categories[entity] = categories

        # Step 2: Build category -> instances mapping
        category_to_instances = {}
        for entity, categories in entity_to_categories.items():
            for cat in categories:
                if cat not in category_to_instances:
                    category_to_instances[cat] = set()
                category_to_instances[cat].add(entity)

        # Step 3: Compare categories pairwise
        categories = list(category_to_instances.keys())

        for i, cat1 in enumerate(categories):
            for cat2 in categories[i+1:]:
                instances1 = category_to_instances[cat1]
                instances2 = category_to_instances[cat2]

                # Skip if no shared instances
                shared = instances1 & instances2
                if not shared:
                    continue

                # Skip if already connected via bridge relation
                if self._already_bridged(cat1, cat2):
                    continue

                # Determine the logical relationship
                relation, direction = self._determine_bridge_relation(
                    cat1, instances1, cat2, instances2, shared
                )

                if relation:
                    # Create the bridge
                    if direction == "forward":
                        self._add_bridge(cat1, relation, cat2)
                        bridges_created.append((cat1, relation, cat2))
                    else:
                        self._add_bridge(cat2, relation, cat1)
                        bridges_created.append((cat2, relation, cat1))

        return bridges_created

    def _get_all_categories(self, entity: str, visited: Set[str] = None) -> Set[str]:
        """
        Get all categories an entity belongs to, following transitive "is" chains.

        Example: If poodle is dog, dog is mammal, mammal is animal,
        returns {dog, mammal, animal}
        """
        if visited is None:
            visited = set()

        if entity in visited:
            return set()
        visited.add(entity)

        categories = set()

        # Get direct "is" targets
        direct = self.loom.get(entity, "is") or []

        for cat in direct:
            categories.add(cat)
            # Recursively get parent categories
            parent_cats = self._get_all_categories(cat, visited.copy())
            categories.update(parent_cats)

        return categories

    def _already_bridged(self, cat1: str, cat2: str) -> bool:
        """Check if two categories are already connected via a bridge relation."""
        for rel in BRIDGE_RELATIONS:
            # Check both directions
            targets1 = self.loom.get(cat1, rel) or []
            if cat2 in targets1:
                return True
            targets2 = self.loom.get(cat2, rel) or []
            if cat1 in targets2:
                return True
        return False

    def _determine_bridge_relation(
        self, cat1: str, instances1: Set[str],
        cat2: str, instances2: Set[str],
        shared: Set[str]
    ) -> Tuple[Optional[str], str]:
        """
        Determine the logical relationship between two categories.

        Returns (relation_name, direction) where direction is "forward" or "reverse".

        Logic:
        - equivalent_to: Same instances (synonyms, e.g., "ocean animals" = "aquatic creatures")
        - subset_of: All instances of one are in the other (e.g., "dogs" ⊂ "mammals")
        - overlaps_with: Partial overlap (e.g., "pets" ∩ "mammals")
        - similar_to: Weaker connection for conceptual similarity

        Confidence thresholds:
        - For equivalent_to: Require exact match
        - For subset_of: Require complete containment
        - For overlaps_with: Require >= 50% overlap
        - For similar_to: Any shared instance (weakest)
        """
        # Calculate overlap ratios
        overlap_ratio_1 = len(shared) / len(instances1) if instances1 else 0
        overlap_ratio_2 = len(shared) / len(instances2) if instances2 else 0

        # Check for equivalence (same instances = synonyms)
        if instances1 == instances2:
            return "equivalent_to", "forward"

        # Check for subset relationship (one is subcategory of other)
        if instances1 < instances2:  # cat1 ⊂ cat2 (proper subset)
            # All instances of cat1 are also instances of cat2
            # This means cat1 is more specific than cat2
            # Example: "dogs" subset_of "mammals"
            return "subset_of", "forward"

        if instances2 < instances1:  # cat2 ⊂ cat1
            return "subset_of", "reverse"

        # Check for significant overlap (not subset, but substantial)
        min_overlap = min(overlap_ratio_1, overlap_ratio_2)
        max_overlap = max(overlap_ratio_1, overlap_ratio_2)

        if min_overlap >= 0.5:
            # Strong overlap - they're closely related
            return "overlaps_with", "forward"
        elif min_overlap >= 0.25 or len(shared) >= 2:
            # Moderate overlap - they're similar
            return "similar_to", "forward"
        elif len(shared) >= 1 and max_overlap >= 0.5:
            # At least one category has significant overlap
            return "similar_to", "forward"

        # Very weak overlap - don't create a bridge
        return None, ""

    def _add_bridge(self, cat1: str, relation: str, cat2: str):
        """Add a bridging connection between categories."""
        # Create provenance for the bridge
        provenance = self._create_provenance(
            source_type="inference",
            premises=[
                {"subject": "shared_instances", "relation": "between", "object": f"{cat1},{cat2}"}
            ],
            rule_id="category_bridge"
        )

        # Add the bridge fact
        self.loom.add_fact(cat1, relation, cat2, confidence="medium", provenance=provenance)

        # For symmetric relations, add reverse
        if relation in ["equivalent_to", "overlaps_with", "similar_to"]:
            self.loom.add_fact(cat2, relation, cat1, confidence="medium", provenance=provenance)

        if self.loom.verbose:
            print(f"       [bridge: {cat1} {relation} {cat2}]")
