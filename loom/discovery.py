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
"""

from collections import defaultdict
from typing import Dict, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .brain import Loom

from .normalizer import normalize

# Confidence levels
CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

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
