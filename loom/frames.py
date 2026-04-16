"""
Frame-Based Knowledge Layer for Loom.

Provides structured attribute slots for concepts with two-tier certainty:
- confirmed: definite facts ("cats are orange")
- potential: possible facts ("cats can be orange")

Detects shared-value bridges between concepts, computes similarity
(weighting confirmed > potential), and propagates category membership
to similar concepts (emergent categorization).

Architecture:
- AttributeSlot: Two-tier value store (confirmed + potential)
- ConceptFrame: A concept with typed AttributeSlots
- AttributeBridge: A link between two concepts sharing attribute values
- ConceptCluster: An emergent category grouping similar concepts
- FrameManager: Orchestrates frame lifecycle, similarity, bridges, and propagation
"""

import time
from dataclasses import dataclass, field
from typing import Dict, Set, List, Tuple, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .brain import Loom

from .normalizer import normalize
from .grammar import is_adjective
from .parser.constants import COLORS

# --- Relation-to-attribute mapping ---

RELATION_TO_ATTRIBUTE = {
    "color": "color",
    "is_color": "color",
    "size": "size",
    "lives_in": "habitat",
    "is_in": "habitat",
    "found_in": "habitat",
    "live_in": "habitat",
    "habitat_type": "habitat",
    "eats": "diet",
    "diet": "diet",
    "hunts": "diet",
    "can": "abilities",
    "has": "body_parts",
    "has_property": "traits",
    "needs": "needs",
    "makes": "produces",
    "communicates_via": "behaviors",
    "pollinates": "behaviors",
    "orbits": "behaviors",
}

# Known color values
COLOR_SET = set(c.lower() for c in COLORS)

# Known size words
SIZE_WORDS = {
    "large", "small", "big", "tiny", "huge", "enormous", "giant",
    "tall", "short", "medium", "little", "massive", "miniature",
    "heavy", "light", "lightweight",
}

# Known habitat words
HABITAT_WORDS = {
    "forest", "ocean", "sea", "river", "lake", "desert", "jungle",
    "mountain", "savanna", "arctic", "tundra", "swamp", "grassland",
    "urban", "rural", "tropical", "aquatic", "terrestrial", "underground",
}

# Default empty slots created for every new concept
DEFAULT_SLOTS = ["color", "size", "habitat", "diet", "abilities", "body_parts", "traits"]

# Relations that indicate category membership (not attribute values)
CATEGORY_RELATIONS = {"is", "is_a", "type_of", "kind_of"}

# Modal verbs that express possibility (not certainty)
POSSIBILITY_MODALS = {"can", "could", "may", "might"}

# Skip these subjects/objects -- internal or system-level
SKIP_CONCEPTS = {"self", "loom", "it", "they", "them", "this", "that"}

# Similarity weights for two-tier comparison
CONFIRMED_WEIGHT = 1.0   # Shared confirmed values
POTENTIAL_WEIGHT = 0.5    # Shared potential values
CROSS_TIER_WEIGHT = 0.3   # One confirmed + one potential

# Minimum similarity threshold for category propagation
PROPAGATION_THRESHOLD = 0.4

# Minimum members for a cluster to form
MIN_CLUSTER_SIZE = 2


# --- Data structures ---

@dataclass
class AttributeSlot:
    """Two-tier attribute slot: confirmed (definite) and potential (possible)."""
    confirmed: Set[str] = field(default_factory=set)
    potential: Set[str] = field(default_factory=set)

    @property
    def all_values(self) -> Set[str]:
        """All values regardless of tier."""
        return self.confirmed | self.potential

    @property
    def is_empty(self) -> bool:
        return not self.confirmed and not self.potential

    def __len__(self) -> int:
        return len(self.confirmed) + len(self.potential)


@dataclass
class ConceptFrame:
    """Frame-based representation of a concept with typed attribute slots."""
    concept: str
    slots: Dict[str, AttributeSlot] = field(default_factory=dict)
    categories: Set[str] = field(default_factory=set)
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    def total_values(self) -> int:
        """Total number of attribute values across all slots."""
        return sum(len(s) for s in self.slots.values())


@dataclass
class AttributeBridge:
    """A bridge between two concepts based on shared attribute values."""
    concept_a: str
    concept_b: str
    attribute: str
    shared_confirmed: Set[str] = field(default_factory=set)
    shared_potential: Set[str] = field(default_factory=set)
    shared_cross: Set[str] = field(default_factory=set)
    strength: float = 0.0


@dataclass
class ConceptCluster:
    """A cluster of similar concepts with a shared category label."""
    category: str
    members: Set[str] = field(default_factory=set)
    prototype: Dict[str, Set[str]] = field(default_factory=dict)
    confidence: float = 0.0
    created_at: float = field(default_factory=time.time)


# --- FrameManager ---

class FrameManager:
    """
    Manages concept frames with two-tier attribute slots (confirmed/potential).

    Operates as a reactive layer on top of brain.add_fact(). Routes facts
    to confirmed or potential tier based on how they were stated:
    - "cats are orange" -> confirmed color
    - "cats can be orange" -> potential color
    - Later "cats are orange" promotes potential to confirmed

    Background cycles recompute bridges, similarity, and propagate categories.
    """

    def __init__(self, loom: "Loom"):
        self.loom = loom
        self._frames: Dict[str, ConceptFrame] = {}
        self._bridges: List[AttributeBridge] = []
        self._clusters: Dict[str, ConceptCluster] = {}
        self._similarity_cache: Dict[Tuple[str, str], float] = {}
        self._cache_dirty: bool = False
        self._pending_propagations: List[Tuple[str, str, str, float]] = []
        self._dirty_concepts: Set[str] = set()

    # ------------------------------------------------------------------
    # Frame lifecycle
    # ------------------------------------------------------------------

    def get_or_create_frame(self, concept: str) -> ConceptFrame:
        """Get existing frame or create one with empty default slots."""
        if concept in self._frames:
            return self._frames[concept]

        frame = ConceptFrame(
            concept=concept,
            slots={slot: AttributeSlot() for slot in DEFAULT_SLOTS},
        )
        self._frames[concept] = frame
        return frame

    def on_fact_added(self, subject: str, relation: str, obj: str, confidence: str):
        """
        Called from brain.add_fact() after a fact is stored.
        Routes the fact to the appropriate frame slot and tier.

        Facts with confidence="low" (from hedging like "maybe", "I think")
        go to the potential tier instead of confirmed.
        """
        # Skip system/internal concepts
        if subject in SKIP_CONCEPTS or not subject or not obj:
            return

        # Skip reverse/instance relations
        if relation in ("belongs_to", "has_instance", "is_color_of",
                        "provided_by", "orbited_by", "damaged_by",
                        "pollinated_by", "helped_by", "eaten_by"):
            return

        # Low confidence facts (from hedging) go to potential tier
        is_hedged = (confidence == "low")

        # Handle "is" specially: category vs trait
        if relation in CATEGORY_RELATIONS:
            self._handle_is_relation(subject, obj, potential=is_hedged)
            return

        # Detect possibility: "can" + "be X" -> potential attribute
        if relation == "can":
            handled = self._handle_can_relation(subject, obj)
            if handled:
                return
            # Not a "can be" pattern -> confirmed ability (unless hedged)
            self._fill_slot(subject, "abilities", obj, potential=is_hedged)
            return

        # Other possibility modals (could, may, might)
        if relation in POSSIBILITY_MODALS and relation != "can":
            handled = self._handle_can_relation(subject, obj)
            if handled:
                return

        # Route through relation-to-attribute mapping
        attribute = self._resolve_attribute(relation, obj)
        if attribute:
            self._fill_slot(subject, attribute, obj, potential=is_hedged)

    def _handle_can_relation(self, subject: str, obj: str) -> bool:
        """
        Handle "can be X" patterns. Returns True if handled as possibility.
        Parser stores "can be orange" as either:
          - can: "be orange" (with space)
          - can: "be_orange" (with underscore)
        """
        # Normalize: check for "be " or "be_" prefix
        value = None
        if obj.startswith("be "):
            value = obj[3:].strip()
        elif obj.startswith("be_"):
            value = obj[3:].strip("_").replace("_", " ")

        if not value:
            return False

        # Classify the value to find the right attribute slot
        attribute = self._classify_value(value)
        # Normalize value back for storage
        value_normalized = value.replace(" ", "_")
        self._fill_slot(subject, attribute, value_normalized, potential=True)
        return True

    def _classify_value(self, value: str) -> str:
        """Classify an attribute value to determine its slot type."""
        val_lower = value.lower().replace("_", " ").strip()

        if val_lower in COLOR_SET:
            return "color"
        if val_lower in SIZE_WORDS:
            return "size"
        if val_lower in HABITAT_WORDS:
            return "habitat"
        if is_adjective(val_lower.split()[0] if val_lower else ""):
            return "traits"
        # Default: traits for adjective-like values from "can be X"
        return "traits"

    def _handle_is_relation(self, subject: str, obj: str, potential: bool = False):
        """Handle 'is' relation: category vs trait, with potential promotion."""
        classification = self._classify_is_relation(obj)

        frame = self.get_or_create_frame(subject)
        frame.last_updated = time.time()

        if classification == "category":
            if potential:
                # Hedged category: don't propagate, just note it
                self._fill_slot(subject, "traits", obj, potential=True)
            else:
                frame.categories.add(obj)
                self._dirty_concepts.add(subject)
                self._cache_dirty = True
                self.propagate_category(subject, obj)
        elif classification == "color":
            self._fill_slot(subject, "color", obj, potential=potential)
        else:
            self._fill_slot(subject, "traits", obj, potential=potential)

    def _classify_is_relation(self, obj: str) -> str:
        """
        Determine if 'X is obj' means category, trait, or color.
        Returns "category", "traits", or "color".
        """
        obj_clean = obj.replace("_", " ").lower().strip()

        # Check colors first
        if obj_clean in COLOR_SET:
            return "color"

        # Check if it's an adjective
        first_word = obj_clean.split()[0] if obj_clean else ""
        if is_adjective(first_word):
            return "traits"

        # Check if object already exists as a concept with instances
        knowledge = self.loom.knowledge
        if obj in knowledge:
            obj_rels = knowledge[obj]
            if isinstance(obj_rels, dict) and "has_instance" in obj_rels:
                return "category"

        # Check known trait words
        trait_words = {
            "fast", "slow", "large", "small", "big", "tall", "short",
            "heavy", "light", "strong", "weak", "smart", "intelligent",
            "loyal", "independent", "social", "dangerous", "safe",
            "beautiful", "ugly", "loud", "quiet", "gentle", "fierce",
            "important", "rare", "common", "wild", "domestic", "friendly",
        }
        if obj_clean in trait_words:
            return "traits"

        # Check size
        if obj_clean in SIZE_WORDS:
            return "traits"

        # Default: treat as category
        return "category"

    def _resolve_attribute(self, relation: str, obj: str) -> Optional[str]:
        """Map a relation+object to an attribute type."""
        if relation in RELATION_TO_ATTRIBUTE:
            attr = RELATION_TO_ATTRIBUTE[relation]
            # Special case: if mapped to "traits" but value is a color, use "color"
            if attr == "traits" and obj.lower().replace("_", "") in COLOR_SET:
                return "color"
            return attr

        # Unknown relation -> create dynamic slot if meaningful
        if len(relation) > 2 and "_" not in relation[:3]:
            return relation

        return None

    def _fill_slot(self, concept: str, attribute: str, value: str,
                   potential: bool = False):
        """
        Fill a specific attribute slot on a concept's frame.

        Args:
            concept: The concept name
            attribute: The attribute type (color, size, etc.)
            value: The value to add
            potential: If True, add to potential tier; if False, add to confirmed
                       and promote from potential if it was there
        """
        frame = self.get_or_create_frame(concept)

        if attribute not in frame.slots:
            frame.slots[attribute] = AttributeSlot()

        slot = frame.slots[attribute]
        changed = False

        if potential:
            # Add to potential tier (only if not already confirmed)
            if value not in slot.confirmed and value not in slot.potential:
                slot.potential.add(value)
                changed = True
                if self.loom.verbose:
                    print(f"       [frame: {concept}.{attribute} ~? {value}]")
        else:
            # Add to confirmed tier
            if value not in slot.confirmed:
                slot.confirmed.add(value)
                changed = True
                # Promote: remove from potential if it was there
                if value in slot.potential:
                    slot.potential.discard(value)
                    if self.loom.verbose:
                        print(f"       [frame: {concept}.{attribute} PROMOTED {value}]")
                elif self.loom.verbose:
                    print(f"       [frame: {concept}.{attribute} += {value}]")

        if changed:
            frame.last_updated = time.time()
            self._dirty_concepts.add(concept)
            self._cache_dirty = True

        # Cleanup: if slot is completely empty and not a default slot, remove it
        if slot.is_empty and attribute not in DEFAULT_SLOTS:
            del frame.slots[attribute]

    # ------------------------------------------------------------------
    # Similarity & bridges
    # ------------------------------------------------------------------

    def compute_similarity(self, concept_a: str, concept_b: str) -> float:
        """
        Compute weighted similarity between two concept frames.
        Uses two-tier weighting:
        - Shared confirmed values: weight 1.0
        - Shared potential values: weight 0.5
        - Cross-tier overlap (one confirmed, one potential): weight 0.3
        """
        key = tuple(sorted((concept_a, concept_b)))
        if not self._cache_dirty and key in self._similarity_cache:
            return self._similarity_cache[key]

        frame_a = self._frames.get(concept_a)
        frame_b = self._frames.get(concept_b)

        if not frame_a or not frame_b:
            return 0.0

        total_weight = 0.0
        total_score = 0.0

        all_attrs = set(frame_a.slots.keys()) | set(frame_b.slots.keys())

        for attr in all_attrs:
            slot_a = frame_a.slots.get(attr)
            slot_b = frame_b.slots.get(attr)

            if not slot_a or not slot_b:
                continue
            if slot_a.is_empty and slot_b.is_empty:
                continue

            # Compute tier-aware overlap
            conf_a, conf_b = slot_a.confirmed, slot_b.confirmed
            pot_a, pot_b = slot_a.potential, slot_b.potential

            # All unique values across both frames for this attribute
            all_vals = conf_a | pot_a | conf_b | pot_b
            if not all_vals:
                continue

            # Score each shared value based on tier
            attr_score = 0.0
            for val in all_vals:
                in_a_conf = val in conf_a
                in_a_pot = val in pot_a
                in_b_conf = val in conf_b
                in_b_pot = val in pot_b

                in_a = in_a_conf or in_a_pot
                in_b = in_b_conf or in_b_pot

                if in_a and in_b:
                    # Both have it -- weight depends on tier
                    if in_a_conf and in_b_conf:
                        attr_score += CONFIRMED_WEIGHT
                    elif in_a_pot and in_b_pot:
                        attr_score += POTENTIAL_WEIGHT
                    else:
                        attr_score += CROSS_TIER_WEIGHT

            # Normalize by total possible (all values at full weight)
            max_score = len(all_vals) * CONFIRMED_WEIGHT
            if max_score > 0:
                slot_similarity = attr_score / max_score
                weight = len(all_vals)
                total_score += slot_similarity * weight
                total_weight += weight

        similarity = total_score / total_weight if total_weight > 0 else 0.0

        # Factor in shared categories (bonus)
        if frame_a.categories and frame_b.categories:
            cat_overlap = len(frame_a.categories & frame_b.categories)
            cat_union = len(frame_a.categories | frame_b.categories)
            if cat_union > 0:
                cat_sim = cat_overlap / cat_union
                similarity = 0.7 * similarity + 0.3 * cat_sim

        self._similarity_cache[key] = similarity
        return similarity

    def get_similar_concepts(self, concept: str, threshold: float = 0.3) -> List[Tuple[str, float]]:
        """Get concepts similar to the given one, sorted by similarity descending."""
        results = []
        for other in self._frames:
            if other == concept or other in SKIP_CONCEPTS:
                continue
            sim = self.compute_similarity(concept, other)
            if sim >= threshold:
                results.append((other, sim))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _recompute_bridges(self):
        """Scan frame pairs for shared attribute values and create bridges."""
        self._bridges.clear()
        concepts = [c for c in self._frames if c not in SKIP_CONCEPTS]

        for i, ca in enumerate(concepts):
            frame_a = self._frames[ca]
            for cb in concepts[i + 1:]:
                frame_b = self._frames[cb]

                all_attrs = set(frame_a.slots.keys()) & set(frame_b.slots.keys())
                for attr in all_attrs:
                    slot_a = frame_a.slots.get(attr)
                    slot_b = frame_b.slots.get(attr)
                    if not slot_a or not slot_b:
                        continue

                    # Find shared values at each tier level
                    shared_conf = slot_a.confirmed & slot_b.confirmed
                    shared_pot = slot_a.potential & slot_b.potential
                    shared_cross = (
                        (slot_a.confirmed & slot_b.potential) |
                        (slot_a.potential & slot_b.confirmed)
                    )

                    if shared_conf or shared_pot or shared_cross:
                        # Compute strength with tier weighting
                        all_vals = slot_a.all_values | slot_b.all_values
                        score = (len(shared_conf) * CONFIRMED_WEIGHT +
                                 len(shared_pot) * POTENTIAL_WEIGHT +
                                 len(shared_cross) * CROSS_TIER_WEIGHT)
                        max_score = len(all_vals) * CONFIRMED_WEIGHT
                        strength = score / max_score if max_score > 0 else 0.0

                        bridge = AttributeBridge(
                            concept_a=ca,
                            concept_b=cb,
                            attribute=attr,
                            shared_confirmed=shared_conf.copy(),
                            shared_potential=shared_pot.copy(),
                            shared_cross=shared_cross.copy(),
                            strength=strength,
                        )
                        self._bridges.append(bridge)

    def get_bridges_for(self, concept: str) -> List[AttributeBridge]:
        """Get all bridges involving a concept."""
        return [b for b in self._bridges
                if b.concept_a == concept or b.concept_b == concept]

    # ------------------------------------------------------------------
    # Category propagation
    # ------------------------------------------------------------------

    def propagate_category(self, subject: str, category: str):
        """
        When 'subject is category' is learned, find similar concepts
        that lack this category and queue propagation.
        """
        similar = self.get_similar_concepts(subject, threshold=PROPAGATION_THRESHOLD)

        for other_concept, sim in similar:
            other_frame = self._frames.get(other_concept)
            if not other_frame:
                continue

            if category in other_frame.categories:
                continue

            already_queued = any(
                s == other_concept and o == category
                for s, r, o, c in self._pending_propagations
            )
            if already_queued:
                continue

            self._pending_propagations.append(
                (other_concept, "is", category, sim)
            )

            if self.loom.verbose:
                print(f"       [frame: queued {other_concept} -> is -> {category} "
                      f"(sim={sim:.2f} with {subject})]")

    def apply_pending_propagations(self) -> List[Tuple[str, str, str]]:
        """Apply pending category propagations via loom.add_fact()."""
        applied = []
        pending = self._pending_propagations[:]
        self._pending_propagations.clear()

        for subject, relation, obj, sim in pending:
            frame = self._frames.get(subject)
            if frame and obj in frame.categories:
                continue

            provenance = {
                "source_type": "frame_inference",
                "rule_id": "frame_category_propagation",
                "premises": [
                    {"type": "similarity", "similarity": round(sim, 3)},
                ],
            }

            self.loom.add_fact(
                subject, relation, obj,
                confidence="medium",
                provenance=provenance,
                _propagate=True,
            )
            applied.append((subject, relation, obj))

            if self.loom.verbose:
                print(f"       [frame: inferred {subject} is {obj} "
                      f"(similarity={sim:.2f})]")

        return applied

    # ------------------------------------------------------------------
    # Clusters
    # ------------------------------------------------------------------

    def update_clusters(self):
        """Build clusters from category memberships across all frames."""
        cat_members: Dict[str, Set[str]] = {}
        for concept, frame in self._frames.items():
            if concept in SKIP_CONCEPTS:
                continue
            for cat in frame.categories:
                if cat not in cat_members:
                    cat_members[cat] = set()
                cat_members[cat].add(concept)

        for category, members in cat_members.items():
            if len(members) < MIN_CLUSTER_SIZE:
                self._clusters.pop(category, None)
                continue

            prototype = self._compute_prototype(members)
            confidence = min(1.0, len(members) * 0.2)

            if category in self._clusters:
                cluster = self._clusters[category]
                cluster.members = members.copy()
                cluster.prototype = prototype
                cluster.confidence = confidence
            else:
                self._clusters[category] = ConceptCluster(
                    category=category,
                    members=members.copy(),
                    prototype=prototype,
                    confidence=confidence,
                )

    def _compute_prototype(self, members: Set[str]) -> Dict[str, Set[str]]:
        """Compute prototype: confirmed values present in >50% of members."""
        if not members:
            return {}

        threshold = len(members) / 2.0
        attr_counts: Dict[str, Dict[str, int]] = {}

        for concept in members:
            frame = self._frames.get(concept)
            if not frame:
                continue
            for attr, slot in frame.slots.items():
                if attr not in attr_counts:
                    attr_counts[attr] = {}
                # Only confirmed values count for prototypes
                for val in slot.confirmed:
                    attr_counts[attr][val] = attr_counts[attr].get(val, 0) + 1

        prototype = {}
        for attr, val_counts in attr_counts.items():
            common = {v for v, count in val_counts.items() if count >= threshold}
            if common:
                prototype[attr] = common

        return prototype

    def get_cluster(self, category: str) -> Optional[ConceptCluster]:
        """Get cluster for a category."""
        return self._clusters.get(normalize(category))

    def get_prototype(self, category: str) -> Dict[str, Set[str]]:
        """Get prototype attributes for a category."""
        cluster = self._clusters.get(normalize(category))
        return cluster.prototype if cluster else {}

    # ------------------------------------------------------------------
    # Background cycle
    # ------------------------------------------------------------------

    def run_background_cycle(self) -> List[Tuple[str, str, str]]:
        """
        Called from inference engine's background loop.
        Recomputes bridges, similarity, clusters, and applies propagations.
        Also cleans up empty dynamic slots.
        """
        if not self._cache_dirty and not self._pending_propagations:
            return []

        # Recompute bridges
        self._recompute_bridges()

        # Invalidate similarity cache for dirty concepts
        if self._dirty_concepts:
            keys_to_remove = [
                k for k in self._similarity_cache
                if k[0] in self._dirty_concepts or k[1] in self._dirty_concepts
            ]
            for k in keys_to_remove:
                del self._similarity_cache[k]
            self._dirty_concepts.clear()

        self._cache_dirty = False

        # Cleanup empty dynamic slots
        self._cleanup_empty_slots()

        # Update clusters
        self.update_clusters()

        # Write strong frame similarities back to the knowledge graph
        self._write_similarity_facts()

        # Apply pending propagations
        applied = self.apply_pending_propagations()

        return applied

    def _write_similarity_facts(self):
        """
        For concept pairs with frame similarity >= 0.7, persist a similar_to
        fact in the knowledge graph so the inference and curiosity engines see it.
        Only writes facts that don't already exist.
        """
        SIMILARITY_THRESHOLD = 0.7
        concepts = [c for c in self._frames if c not in SKIP_CONCEPTS]

        for i, ca in enumerate(concepts):
            for cb in concepts[i + 1:]:
                sim = self.compute_similarity(ca, cb)
                if sim < SIMILARITY_THRESHOLD:
                    continue

                # Check both directions to avoid duplicates
                existing_a = self.loom.get(ca, "similar_to") or []
                if cb in existing_a:
                    continue
                existing_b = self.loom.get(cb, "similar_to") or []
                if ca in existing_b:
                    continue

                provenance = {
                    "source_type": "inference",
                    "rule_id": "frame_similarity",
                    "premises": [
                        {"type": "frame_similarity", "similarity": round(sim, 3)},
                    ],
                }

                self.loom.add_fact(
                    ca, "similar_to", cb,
                    confidence="medium",
                    provenance=provenance,
                )
                # similar_to is symmetric
                self.loom.add_fact(
                    cb, "similar_to", ca,
                    confidence="medium",
                    provenance=provenance,
                )

                if self.loom.verbose:
                    print(f"       [frame: {ca} similar_to {cb} (sim={sim:.2f})]")

    def _cleanup_empty_slots(self):
        """Remove empty non-default slots from all frames."""
        for frame in self._frames.values():
            to_remove = [
                attr for attr, slot in frame.slots.items()
                if slot.is_empty and attr not in DEFAULT_SLOTS
            ]
            for attr in to_remove:
                del frame.slots[attr]

    # ------------------------------------------------------------------
    # Hydration (rebuild from existing knowledge)
    # ------------------------------------------------------------------

    def hydrate_from_knowledge(self):
        """Rebuild frames from existing knowledge triples on startup."""
        knowledge = self.loom.knowledge
        for subject, relations in knowledge.items():
            if subject in SKIP_CONCEPTS:
                continue
            if not isinstance(relations, dict):
                continue
            for relation, objects in relations.items():
                obj_list = objects if isinstance(objects, list) else [objects]
                for obj in obj_list:
                    self.on_fact_added(subject, relation, str(obj), "high")

        self._recompute_bridges()
        self.update_clusters()
        self._cache_dirty = False
        self._dirty_concepts.clear()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize frame data for JSON storage."""
        frames = {}
        for concept, frame in self._frames.items():
            slots = {}
            for attr, slot in frame.slots.items():
                if not slot.is_empty:
                    slots[attr] = {
                        "confirmed": list(slot.confirmed),
                        "potential": list(slot.potential),
                    }
            frames[concept] = {
                "slots": slots,
                "categories": list(frame.categories),
                "created_at": frame.created_at,
                "last_updated": frame.last_updated,
            }

        clusters = {}
        for cat, cluster in self._clusters.items():
            clusters[cat] = {
                "members": list(cluster.members),
                "prototype": {k: list(v) for k, v in cluster.prototype.items()},
                "confidence": cluster.confidence,
            }

        return {"frames": frames, "clusters": clusters}

    def from_dict(self, data: dict):
        """Load frame data from JSON."""
        if not data:
            return

        for concept, fdata in data.get("frames", {}).items():
            frame = self.get_or_create_frame(concept)
            for attr, sdata in fdata.get("slots", {}).items():
                if attr not in frame.slots:
                    frame.slots[attr] = AttributeSlot()
                if isinstance(sdata, dict):
                    frame.slots[attr].confirmed = set(sdata.get("confirmed", []))
                    frame.slots[attr].potential = set(sdata.get("potential", []))
                elif isinstance(sdata, list):
                    # Legacy format: flat list -> all confirmed
                    frame.slots[attr].confirmed = set(sdata)
            frame.categories = set(fdata.get("categories", []))
            frame.created_at = fdata.get("created_at", time.time())
            frame.last_updated = fdata.get("last_updated", time.time())

        for cat, cdata in data.get("clusters", {}).items():
            self._clusters[cat] = ConceptCluster(
                category=cat,
                members=set(cdata.get("members", [])),
                prototype={k: set(v) for k, v in cdata.get("prototype", {}).items()},
                confidence=cdata.get("confidence", 0.0),
            )

    def reset(self):
        """Clear all frame data."""
        self._frames.clear()
        self._bridges.clear()
        self._clusters.clear()
        self._similarity_cache.clear()
        self._pending_propagations.clear()
        self._dirty_concepts.clear()
        self._cache_dirty = False

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def format_frame(self, concept: str) -> str:
        """Format a concept frame for display."""
        frame = self._frames.get(normalize(concept))
        if not frame:
            return f"No frame for '{concept}'."

        lines = [f"[{concept}]"]

        if frame.categories:
            lines.append(f"  is: {', '.join(sorted(frame.categories))}")

        for attr in sorted(frame.slots.keys()):
            slot = frame.slots[attr]
            parts = []
            if slot.confirmed:
                parts.extend(sorted(slot.confirmed))
            if slot.potential:
                for v in sorted(slot.potential):
                    parts.append(f"?{v}")
            if parts:
                lines.append(f"  {attr}: {', '.join(parts)}")

        return "\n".join(lines)

    def format_bridges(self, concept: str = None) -> str:
        """Format bridges for display."""
        bridges = self.get_bridges_for(concept) if concept else self._bridges

        if not bridges:
            target = f" for '{concept}'" if concept else ""
            return f"No bridges{target}."

        lines = ["Bridges:"]
        for b in sorted(bridges, key=lambda x: x.strength, reverse=True):
            vals = []
            for v in sorted(b.shared_confirmed):
                vals.append(v)
            for v in sorted(b.shared_potential):
                vals.append(f"?{v}")
            for v in sorted(b.shared_cross):
                vals.append(f"~{v}")
            lines.append(
                f"  {b.concept_a} <> {b.concept_b} "
                f"[{b.attribute}: {', '.join(vals)}] "
                f"({b.strength:.0%})"
            )
        return "\n".join(lines)

    def format_clusters(self) -> str:
        """Format clusters for display."""
        if not self._clusters:
            return "No clusters yet."

        lines = ["Clusters:"]
        for cat, cluster in sorted(self._clusters.items()):
            members = ", ".join(sorted(cluster.members))
            lines.append(f"  {cat}: {{{members}}}")
            if cluster.prototype:
                proto = []
                for attr, vals in sorted(cluster.prototype.items()):
                    proto.append(f"{attr}={','.join(sorted(vals))}")
                lines.append(f"    proto: {'; '.join(proto)}")
        return "\n".join(lines)
