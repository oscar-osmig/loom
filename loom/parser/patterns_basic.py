"""
Basic pattern methods for the Parser class.
Handles negation, looks, analogy, and same_as patterns.
"""

import re
from ..grammar import is_plural
from .constants import COLORS


def _check_negation(parser, t: str) -> str | None:
    """Handle 'X is not Y' or 'X doesn't have Y' patterns."""
    # Don't match questions - let query handlers process them
    if parser._is_question(t):
        return None

    # Don't match relative clauses like "X that cannot Y"
    # These should be handled by _check_is_statement
    if " that cannot " in t or " that can't " in t or " that can " in t:
        return None

    # "X is not Y" / "X are not Y"
    match = re.match(r"(.+?)\s+(?:is|are)\s+not\s+(.+)", t)
    if match:
        subj, obj = match.groups()
        parser.loom.add_fact(subj, "is_not", obj)
        verb = "are" if is_plural(subj) else "is"
        return f"Understood, {subj} {verb} not {obj}."

    # "X doesn't/don't have Y"
    match = re.match(r"(.+?)\s+(?:doesn't|don't|does not|do not)\s+have\s+(.+)", t)
    if match:
        subj, obj = match.groups()
        parser.loom.add_fact(subj, "has_not", obj)
        verb = "don't" if is_plural(subj) else "doesn't"
        return f"Noted, {subj} {verb} have {obj}."

    # "X can't/cannot Y"
    match = re.match(r"(.+?)\s+(?:can't|cannot|can not)\s+(.+)", t)
    if match:
        subj, action = match.groups()
        parser.loom.add_fact(subj, "cannot", action)
        return f"Got it, {subj} cannot {action}."

    return None


def _check_looks_pattern(parser, t: str) -> str | None:
    """Handle 'X looks like Y' or 'X looks [color]' patterns."""
    if " looks " not in t:
        return None

    parts = t.split(" looks ", 1)
    if len(parts) != 2:
        return None

    subj = parts[0].strip()
    rest = parts[1].strip()

    if rest.startswith("like "):
        y = rest[5:].strip()
        parser.loom.add_fact(subj, "looks_like", y)
        # Copy properties BOTH directions
        parser.loom.copy_properties(subj, y)  # y -> subj
        parser.loom.copy_properties(y, subj)  # subj -> y
        return f"Got it, {subj} looks like {y}."

    if rest in COLORS:
        parser.loom.add_fact(subj, "color", rest)
        return f"Got it, {subj} is {rest}."

    return None


def _check_analogy_pattern(parser, t: str) -> str | None:
    """Handle 'X is/are like Y' patterns."""
    like_patterns = [" is like ", " are like "]
    for pattern in like_patterns:
        if pattern in t:
            parts = t.split(pattern, 1)
            if len(parts) == 2:
                x, y = parts[0].strip(), parts[1].strip()
                for prefix in ["you know ", "well ", "so ", "the ", "a ", "an "]:
                    if x.startswith(prefix):
                        x = x[len(prefix):]
                    if y.startswith(prefix):
                        y = y[len(prefix):]

                # Handle "X color is like Y" -> copy color from X to Y
                if x.endswith(" color"):
                    source = x[:-6].strip()  # Remove " color"
                    color = parser.loom.get(source, "color")
                    if color:
                        parser.loom.add_fact(y, "color", color[0])
                        return f"Got it, {y} is {color[0]} like {source}."
                    else:
                        # Still link them, color might be added later
                        parser.loom.add_fact(source, "looks_like", y)
                        parser.loom.copy_properties(source, y)
                        parser.loom.copy_properties(y, source)
                        return f"I'll remember {source} and {y} are similar."

                parser.loom.add_fact(x, "looks_like", y)
                # Copy properties BOTH directions for analogies
                parser.loom.copy_properties(x, y)  # y -> x
                parser.loom.copy_properties(y, x)  # x -> y
                verb = "are" if is_plural(x) else "is"
                return f"I see, {x} {verb} like {y}."
    return None


def _check_same_as_pattern(parser, t: str) -> str | None:
    """
    Handle 'X have same Y as Z' or 'X has the same Y as Z' patterns.
    Copies property Y from Z to X.
    Examples:
        'cats have same legs as dogs' -> cats get dogs' leg count
        'birds have the same wings as bats' -> copy wing property
    """
    # Patterns to match
    patterns = [
        " have same ", " has same ",
        " have the same ", " has the same ",
        " got same ", " got the same ",
    ]

    for pattern in patterns:
        if pattern not in t or " as " not in t:
            continue

        # Split: "cats have same legs as dogs"
        before_pattern = t.split(pattern)[0].strip()
        after_pattern = t.split(pattern)[1].strip()

        if " as " not in after_pattern:
            continue

        # Extract property and source
        prop_and_source = after_pattern.split(" as ", 1)
        if len(prop_and_source) != 2:
            continue

        prop = prop_and_source[0].strip()  # "legs"
        source = prop_and_source[1].strip()  # "dogs"
        target = before_pattern  # "cats"

        # Clean up
        for prefix in ["the ", "a ", "an "]:
            if target.startswith(prefix):
                target = target[len(prefix):]
            if source.startswith(prefix):
                source = source[len(prefix):]

        # Look up what source has for this property
        # Check common relations: has, color, can, is
        relations_to_check = ["has", "color", "can", "is", "needs", "eats", "lives_in"]

        copied = False
        for rel in relations_to_check:
            source_values = parser.loom.get(source, rel) or []
            for val in source_values:
                # Check if this value relates to the property
                if prop in val or val in prop or prop == rel:
                    parser.loom.add_fact(target, rel, val)
                    copied = True
                    parser.last_subject = target
                    parser.loom.context.update(subject=target, relation=rel, obj=val)
                    # Format response with proper grammar
                    val_display = val.replace("_", " ")
                    if rel == "has":
                        verb = "have" if is_plural(target) else "has"
                        return f"Got it, {target} {verb} {val_display} (same as {source})."
                    elif rel == "can":
                        return f"Got it, {target} can {val_display} (same as {source})."
                    elif rel == "color":
                        verb = "are" if is_plural(target) else "is"
                        return f"Got it, {target} {verb} {val_display} (same as {source})."
                    else:
                        return f"Got it, {target} {rel} {val_display} (same as {source})."

        # If no specific match, just copy all properties from source to target
        if not copied:
            parser.loom.copy_properties(target, source)
            parser.last_subject = target
            return f"Got it, {target} is like {source}."

    return None
