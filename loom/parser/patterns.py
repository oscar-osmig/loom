"""
Pattern methods for the Parser class.
Handles negation, looks, analogy, same_as, relation patterns,
conditional, becomes, is_statement, discourse patterns, and learn_from_conversation.

This module re-exports all pattern functions from the split modules:
- patterns_basic.py: Negation, looks, analogy, same_as patterns
- patterns_relations.py: Relation patterns, conditional, becomes, is_statement
- patterns_discourse.py: Discourse patterns and learning from conversation
"""

# Basic patterns
from .patterns_basic import (
    _check_negation,
    _check_looks_pattern,
    _check_analogy_pattern,
    _check_same_as_pattern,
)

# Relation patterns
from .patterns_relations import (
    _check_relation_patterns,
    _check_conditional_pattern,
    _check_becomes_pattern,
    _check_is_statement,
)

# Discourse patterns
from .patterns_discourse import (
    _check_implicit_continuation,
    _check_list_learning,
    _check_pronoun_reference,
    _check_discourse_patterns,
    _learn_from_conversation,
    _check_first_person_statement,
    _check_chit_chat,
)

# Export all pattern functions
__all__ = [
    # Basic patterns
    "_check_negation",
    "_check_looks_pattern",
    "_check_analogy_pattern",
    "_check_same_as_pattern",
    # Relation patterns
    "_check_relation_patterns",
    "_check_conditional_pattern",
    "_check_becomes_pattern",
    "_check_is_statement",
    # Discourse patterns
    "_check_implicit_continuation",
    "_check_list_learning",
    "_check_pronoun_reference",
    "_check_discourse_patterns",
    "_learn_from_conversation",
    "_check_first_person_statement",
    "_check_chit_chat",
]
