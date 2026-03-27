"""
Entity Resolution for Loom.

Before creating any new neuron, this module searches existing neurons
to find if there's already one that represents the same concept.

Resolution strategies (in priority order):
1. Exact match - neuron already exists with same normalized name
2. Possessive resolution - "X's Y" -> find what X has related to Y
3. Compound reference - "X Y" -> find X's property matching Y
4. Alias resolution - check "same_as" or "also_known_as" relations
5. Contextual resolution - recent topic has related property
"""

import re
from typing import Optional, Tuple
from .normalizer import normalize


def resolve_to_existing_neuron(
    phrase: str,
    knowledge: dict,
    context: Optional[dict] = None
) -> Tuple[str, str]:
    """
    Resolve a phrase to an existing neuron if possible.

    Args:
        phrase: The phrase to resolve (e.g., "loom's eyes", "the ocean")
        knowledge: The knowledge graph dict
        context: Optional context dict with 'last_subject', 'last_object', etc.

    Returns:
        Tuple of (resolved_name, resolution_type)
        resolution_type is one of: "exact", "possessive", "compound", "alias", "context", "new"
    """
    if not phrase or not phrase.strip():
        return (normalize(phrase), "new")

    phrase = phrase.strip()
    phrase_lower = phrase.lower()

    # Clean up common prefixes
    cleaned = phrase_lower
    for prefix in ["the ", "a ", "an ", "my ", "your ", "their ", "its "]:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]

    # Strategy 1: Exact match
    normalized = normalize(cleaned)
    if normalized in knowledge:
        return (normalized, "exact")

    # Strategy 2: Possessive resolution ("X's Y" -> X has something with Y)
    result = _resolve_possessive(phrase_lower, knowledge)
    if result:
        return (result, "possessive")

    # Strategy 3: Compound reference ("X Y" -> X has something with Y)
    result = _resolve_compound(cleaned, knowledge)
    if result:
        return (result, "compound")

    # Strategy 4: Alias resolution (check same_as relations)
    result = _resolve_alias(normalized, knowledge)
    if result:
        return (result, "alias")

    # Strategy 5: Contextual resolution (recent topic has related property)
    if context:
        result = _resolve_contextual(cleaned, knowledge, context)
        if result:
            return (result, "context")

    # Strategy 6: Partial match - check if this is part of an existing neuron
    result = _resolve_partial_match(cleaned, knowledge)
    if result:
        return (result, "partial")

    # No resolution found - will create new neuron
    return (normalized, "new")


def _resolve_possessive(phrase: str, knowledge: dict) -> Optional[str]:
    """
    Resolve possessive patterns like "X's Y" to existing properties.

    "loom's eyes" -> "blue_eyes" (if loom has blue_eyes)
    "dog's tail" -> "tail" (if dogs has tail)
    """
    # Pattern: "X's Y" (with apostrophe)
    match = re.match(r"^(.+?)'s?\s+(.+)$", phrase)
    if match:
        owner = match.group(1).strip()
        property_hint = match.group(2).strip()
        result = _find_owner_property(owner, property_hint, knowledge)
        if result:
            return result

    return None


def _resolve_compound(phrase: str, knowledge: dict) -> Optional[str]:
    """
    Resolve compound references like "X Y" where X is a known entity.

    "loom eyes" -> "blue_eyes" (if loom has blue_eyes)
    "cat fur" -> "fur" (if cats has fur)
    """
    words = phrase.split()
    if len(words) < 2:
        return None

    # Try first word as owner, rest as property hint
    owner = words[0]
    property_hint = " ".join(words[1:])

    result = _find_owner_property(owner, property_hint, knowledge)
    if result:
        return result

    # Try first N-1 words as owner, last word as property
    if len(words) >= 2:
        owner = " ".join(words[:-1])
        property_hint = words[-1]
        result = _find_owner_property(owner, property_hint, knowledge)
        if result:
            return result

    return None


def _find_owner_property(owner: str, property_hint: str, knowledge: dict) -> Optional[str]:
    """
    Find a property of an owner that matches the hint.

    Args:
        owner: The owner entity (e.g., "loom")
        property_hint: What we're looking for (e.g., "eyes")
        knowledge: The knowledge graph

    Returns:
        The matching property name, or None
    """
    owner_norm = normalize(owner)
    hint_norm = normalize(property_hint)
    hint_words = set(hint_norm.replace("_", " ").split())

    # Check if owner exists
    if owner_norm not in knowledge:
        # Try plural/singular variations
        variations = [owner_norm + "s", owner_norm.rstrip("s")]
        found_owner = None
        for var in variations:
            if var in knowledge:
                found_owner = var
                break
        if not found_owner:
            return None
        owner_norm = found_owner

    owner_relations = knowledge[owner_norm]

    # Property relations to check (ordered by likelihood)
    property_relations = ["has", "has_property", "owns", "possesses", "contains"]

    for relation in property_relations:
        if relation not in owner_relations:
            continue

        for prop in owner_relations[relation]:
            prop_lower = prop.lower()
            prop_words = set(prop_lower.replace("_", " ").split())

            # Check various matching strategies:

            # 1. Property contains the hint word
            # "blue_eyes" contains "eyes"
            if hint_norm in prop_lower:
                return prop

            # 2. Hint contains the property
            # "eyes" in "blue_eyes"
            if prop_lower in hint_norm:
                return prop

            # 3. Word overlap (at least one significant word matches)
            # "eyes" matches with "blue_eyes" because "eyes" is in both
            common_words = hint_words & prop_words
            if common_words and len(common_words) > 0:
                # Make sure we're matching meaningful words (not just "the", "a", etc.)
                meaningful = [w for w in common_words if len(w) > 2]
                if meaningful:
                    return prop

            # 4. Property ends with hint (common pattern)
            # "blue_eyes" ends with "eyes"
            if prop_lower.endswith(hint_norm) or prop_lower.endswith("_" + hint_norm):
                return prop

    # Also check reverse: maybe the property "belongs_to" owner
    for entity, relations in knowledge.items():
        if "belongs_to" in relations:
            if owner_norm in relations["belongs_to"]:
                entity_lower = entity.lower()
                entity_words = set(entity_lower.replace("_", " ").split())

                # Same matching strategies
                if hint_norm in entity_lower:
                    return entity
                if entity_lower in hint_norm:
                    return entity
                common_words = hint_words & entity_words
                if common_words:
                    meaningful = [w for w in common_words if len(w) > 2]
                    if meaningful:
                        return entity

    return None


def _resolve_alias(normalized: str, knowledge: dict) -> Optional[str]:
    """
    Resolve through alias relations (same_as, also_known_as).

    If "automobile" same_as "car", and we're looking for "automobile",
    return "car" (the canonical form).
    """
    # Check if this entity has a same_as pointing to another
    if normalized in knowledge:
        relations = knowledge[normalized]
        for alias_rel in ["same_as", "also_known_as", "equivalent_to"]:
            if alias_rel in relations:
                # Return the first alias (canonical form)
                aliases = relations[alias_rel]
                if aliases:
                    return list(aliases)[0] if isinstance(aliases, set) else aliases[0]

    # Check if another entity has same_as pointing to this
    for entity, relations in knowledge.items():
        for alias_rel in ["same_as", "also_known_as", "equivalent_to"]:
            if alias_rel in relations:
                if normalized in relations[alias_rel]:
                    return entity  # Return the canonical entity

    return None


def _resolve_contextual(phrase: str, knowledge: dict, context: dict) -> Optional[str]:
    """
    Resolve based on conversation context.

    If we're talking about "loom" and mention "eyes",
    resolve to what loom has related to eyes.
    """
    # Get recent subjects from context
    recent_subjects = []
    if "last_subject" in context and context["last_subject"]:
        recent_subjects.append(context["last_subject"])
    if "topics" in context:
        recent_subjects.extend(context["topics"][:3])

    hint_norm = normalize(phrase)

    for subject in recent_subjects:
        subject_norm = normalize(subject)
        if subject_norm in knowledge:
            # Try to find a property matching the phrase
            result = _find_owner_property(subject, phrase, knowledge)
            if result:
                return result

    return None


def _resolve_partial_match(phrase: str, knowledge: dict) -> Optional[str]:
    """
    Resolve through partial string matching.

    If looking for "eyes" and "blue_eyes" exists, return "blue_eyes".
    Only matches if phrase is a significant part of existing neuron.
    """
    phrase_norm = normalize(phrase)

    if len(phrase_norm) < 3:
        return None  # Too short for partial matching

    # Look for neurons that end with this phrase
    candidates = []
    for entity in knowledge.keys():
        entity_lower = entity.lower()

        # Must be a suffix match (not just contains)
        if entity_lower.endswith(phrase_norm) or entity_lower.endswith("_" + phrase_norm):
            # Prefer shorter matches (more specific)
            candidates.append((entity, len(entity)))

    if candidates:
        # Return the shortest match (most specific)
        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]

    return None


# Convenience function for verbose logging
def resolve_with_explanation(
    phrase: str,
    knowledge: dict,
    context: Optional[dict] = None
) -> Tuple[str, str, str]:
    """
    Resolve and return explanation of how resolution happened.

    Returns:
        Tuple of (resolved_name, resolution_type, explanation)
    """
    resolved, res_type = resolve_to_existing_neuron(phrase, knowledge, context)

    explanations = {
        "exact": f"'{phrase}' matches existing neuron '{resolved}'",
        "possessive": f"'{phrase}' resolved to '{resolved}' via possessive relation",
        "compound": f"'{phrase}' resolved to '{resolved}' via compound reference",
        "alias": f"'{phrase}' resolved to '{resolved}' via alias",
        "context": f"'{phrase}' resolved to '{resolved}' from context",
        "partial": f"'{phrase}' partially matched existing neuron '{resolved}'",
        "new": f"'{phrase}' -> new neuron '{resolved}'"
    }

    return (resolved, res_type, explanations.get(res_type, "unknown resolution"))
