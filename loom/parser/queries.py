"""
Query methods for the Parser class.
Handles all _check_*_query methods for answering questions.

This module re-exports all query functions from the split modules:
- queries_basic.py: Basic queries (name, color, where, who, etc.)
- queries_complex.py: Complex queries (can, are/is, why, causes, etc.)
- queries_knowledge.py: Knowledge queries (reproduce, classification, etc.)
"""

# Basic queries
from .queries_basic import (
    _check_name_query,
    _check_color_query,
    _check_where_query,
    _check_what_lives_query,
    _check_who_query,
    _check_what_has_query,
    _check_what_verb_query,
    _check_how_many_query,
    _check_made_of_query,
    _check_part_of_query,
    _check_what_does_query,
)

# Complex queries
from .queries_complex import (
    _check_can_query,
    _check_are_is_query,
    _check_why_query,
    _check_what_causes_query,
    _check_effect_query,
    _check_lay_eggs_query,
    _check_which_query,
    _check_difference_query,
)

# Knowledge queries
from .queries_knowledge import (
    _check_reproduce_query,
    _check_classification_query,
    _check_examples_query,
    _check_breathing_query,
    _check_backbone_query,
    _check_feeding_query,
    _check_how_query,
    _check_found_in_query,
    _check_characteristics_query,
    _check_differ_query,
    _check_what_query,
)

# Export all query functions
__all__ = [
    # Basic queries
    "_check_name_query",
    "_check_color_query",
    "_check_where_query",
    "_check_what_lives_query",
    "_check_who_query",
    "_check_what_has_query",
    "_check_what_verb_query",
    "_check_how_many_query",
    "_check_made_of_query",
    "_check_part_of_query",
    "_check_what_does_query",
    # Complex queries
    "_check_can_query",
    "_check_are_is_query",
    "_check_why_query",
    "_check_what_causes_query",
    "_check_effect_query",
    "_check_lay_eggs_query",
    "_check_which_query",
    "_check_difference_query",
    # Knowledge queries
    "_check_reproduce_query",
    "_check_classification_query",
    "_check_examples_query",
    "_check_breathing_query",
    "_check_backbone_query",
    "_check_feeding_query",
    "_check_how_query",
    "_check_found_in_query",
    "_check_characteristics_query",
    "_check_differ_query",
    "_check_what_query",
]
