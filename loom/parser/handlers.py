"""
Handler methods for the Parser class.
Handles correction, refinement, procedural patterns, and causal patterns.
"""

import re
from ..normalizer import normalize
from ..grammar import is_plural, is_adjective
from .constants import CORRECTION_WORDS, REFINEMENT_WORDS, PROCEDURAL_START, PROCEDURAL_SEQUENCE


def _check_clarification_response(parser, t: str) -> str | None:
    """Handle response to a pending clarification question."""
    if not parser.loom.context.pending_clarification:
        return None

    # Don't treat questions as clarification responses
    if parser._is_question(t):
        parser.loom.context.clear_clarification()
        return None

    clarification = parser.loom.context.pending_clarification
    about = clarification["about"]

    # User is providing the clarification
    parser.loom.context.clear_clarification()

    # Try to use the response to fill in the missing info
    # For now, store it as additional info about the topic
    if about and t:
        parser.loom.add_fact(about, "is", t)
        parser.loom.context.update(subject=about, obj=t)
        return f"Got it, {about} is {t}."

    return None


def _check_correction(parser, t: str) -> str | None:
    """
    Handle corrections: "no, that's wrong", "actually X is Y"
    Retracts or updates previous facts.
    """
    # Check for correction indicators
    is_correction = False
    for word in CORRECTION_WORDS:
        if t.startswith(word) or f" {word}" in t:
            is_correction = True
            # Remove the correction word
            t = t.replace(word, "").strip()
            break

    if not is_correction:
        return None

    # Pattern: "actually X is Y" or just "X is Y" after correction word
    if " is " in t or " are " in t:
        verb = " is " if " is " in t else " are "
        parts = t.split(verb, 1)
        if len(parts) == 2:
            subj = parts[0].strip()
            obj = parts[1].strip()

            # Clean up
            for prefix in ["the ", "a ", "an ", "that "]:
                if subj.startswith(prefix):
                    subj = subj[len(prefix):]

            # Get what was previously said about this subject
            old_facts = parser.loom.get(subj, "is") or []

            # Retract old conflicting facts
            for old in old_facts:
                if old != normalize(obj):
                    parser.loom.retract_fact(subj, "is", old)
                    parser.loom.context.add_correction(old, obj, "is")

            # Add the corrected fact with attribution
            corrector = getattr(parser.loom, '_session_speaker_id', None) or ''
            parser.loom.add_fact(subj, "is", obj, properties={
                "source_type": "clarification",
                "corrected_by": corrector,
            })
            # Record the correction event
            _record_correction(parser.loom, subj, "is", obj, corrector)
            parser.loom.context.update(subject=subj, obj=obj)
            parser.last_subject = subj

            return f"Corrected. {subj.title()} is {obj}."

    # Pattern: "X can't Y" or "X doesn't Y"
    if " can't " in t or " cannot " in t:
        parts = t.split(" can't " if " can't " in t else " cannot ", 1)
        if len(parts) == 2:
            subj = parts[0].strip()
            action = parts[1].strip()

            corrector = getattr(parser.loom, '_session_speaker_id', None) or ''
            parser.loom.retract_fact(subj, "can", action)
            parser.loom.add_fact(subj, "cannot", action, properties={
                "source_type": "clarification",
                "corrected_by": corrector,
            })
            _record_correction(parser.loom, subj, "cannot", action, corrector)

            return f"Corrected. {subj.title()} cannot {action}."

    # Pattern: "X doesn't have Y"
    if " doesn't have " in t or " don't have " in t:
        pattern = " doesn't have " if " doesn't have " in t else " don't have "
        parts = t.split(pattern, 1)
        if len(parts) == 2:
            subj = parts[0].strip()
            obj = parts[1].strip()

            corrector = getattr(parser.loom, '_session_speaker_id', None) or ''
            parser.loom.retract_fact(subj, "has", obj)
            parser.loom.add_fact(subj, "has_not", obj, properties={
                "source_type": "clarification",
                "corrected_by": corrector,
            })
            _record_correction(parser.loom, subj, "has_not", obj, corrector)

            return f"Corrected. {subj.title()} doesn't have {obj}."

    return None


def _record_correction(loom, subject, relation, obj, corrector):
    """Store a correction event in MongoDB for leaderboard tracking."""
    from datetime import datetime, timezone
    try:
        loom.storage.db.corrections.insert_one({
            "instance": loom.storage.instance_name,
            "subject": subject,
            "relation": relation,
            "object": obj,
            "corrected_by": corrector,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


def _check_refinement(parser, t: str) -> str | None:
    """
    Handle refinements: "only when X", "except if Y", "but not if Z"
    Adds constraints to existing facts.
    """
    for indicator in REFINEMENT_WORDS:
        if indicator in t:
            parts = t.split(indicator, 1)
            if len(parts) == 2:
                main_part = parts[0].strip()
                condition = parts[1].strip()

                # If main_part is empty, use last context
                if not main_part and parser.loom.context.last_subject:
                    subj = parser.loom.context.last_subject
                    rel = parser.loom.context.last_relation or "is"
                    obj = parser.loom.context.last_object

                    if subj and obj:
                        parser.loom.add_constraint(subj, rel, obj, condition)
                        return f"Noted: {subj} {rel} {obj}, {indicator} {condition}."

                # Try to parse main_part
                if " is " in main_part or " are " in main_part:
                    verb = " is " if " is " in main_part else " are "
                    main_parts = main_part.split(verb, 1)
                    if len(main_parts) == 2:
                        subj = main_parts[0].strip()
                        obj = main_parts[1].strip()

                        # Clean up
                        for prefix in ["the ", "a ", "an "]:
                            if subj.startswith(prefix):
                                subj = subj[len(prefix):]

                        parser.loom.add_fact(subj, "is", obj)
                        parser.loom.add_constraint(subj, "is", obj, condition)
                        parser.loom.context.update(subject=subj, relation="is", obj=obj)

                        return f"Got it: {subj} is {obj}, {indicator} {condition}."

                # Pattern: "X can Y only when Z"
                if " can " in main_part:
                    can_parts = main_part.split(" can ", 1)
                    if len(can_parts) == 2:
                        subj = can_parts[0].strip()
                        action = can_parts[1].strip()

                        parser.loom.add_fact(subj, "can", action)
                        parser.loom.add_constraint(subj, "can", action, condition)

                        return f"Got it: {subj} can {action}, {indicator} {condition}."

    return None


def _check_procedural(parser, t: str) -> str | None:
    """
    Handle procedural knowledge: "first X, then Y, finally Z"
    Or: "to do X: first A, then B"
    """
    # Check for procedure definition start: "to X:" or "how to X:"
    for start in PROCEDURAL_START:
        if t.startswith(start):
            rest = t[len(start):].strip()

            # Check if this defines a procedure name
            if ":" in rest:
                name, steps_text = rest.split(":", 1)
                parser.current_procedure = name.strip()
                parser.procedure_buffer = []

                # Parse steps from the rest
                steps = _parse_procedure_steps(parser, steps_text)
                if steps:
                    parser.loom.add_procedure(parser.current_procedure, steps)
                    parser.current_procedure = None
                    return f"Learned procedure '{name.strip()}' with {len(steps)} steps."

                return f"Tell me the steps for '{name.strip()}'."

    # Check for sequence markers
    for marker in PROCEDURAL_SEQUENCE:
        if t.startswith(marker):
            step = t[len(marker):].strip()
            step = step.lstrip(",").strip()

            if parser.current_procedure:
                parser.procedure_buffer.append(step)

                if marker in ["finally", "lastly"]:
                    # End of procedure
                    parser.loom.add_procedure(parser.current_procedure, parser.procedure_buffer)
                    name = parser.current_procedure
                    count = len(parser.procedure_buffer)
                    parser.current_procedure = None
                    parser.procedure_buffer = []
                    return f"Learned procedure '{name}' with {count} steps."

                return f"Step {len(parser.procedure_buffer)}: {step}. What's next?"
            else:
                # Single sequence without procedure name
                parser.procedure_buffer.append(step)
                return f"Noted step: {step}."

    return None


def _parse_procedure_steps(parser, text: str) -> list:
    """Parse procedure steps from text."""
    steps = []

    # Split by sequence markers
    parts = re.split(r'\b(first|then|next|after that|finally|lastly)\b', text, flags=re.IGNORECASE)

    for i, part in enumerate(parts):
        part = part.strip().strip(",").strip()
        if part and part.lower() not in PROCEDURAL_SEQUENCE:
            steps.append(part)

    return steps


def _check_however_pattern(parser, t: str) -> str | None:
    """Handle 'However, X' patterns - strip 'however' and parse the rest."""
    if t.startswith("however, "):
        rest = t[9:].strip()  # "however, " is 9 chars
    elif t.startswith("however "):
        rest = t[8:].strip()  # "however " is 8 chars
    else:
        return None

    if rest.startswith(", "):
        rest = rest[2:]

    # Handle "X are Y that cannot Z" pattern
    # e.g., "penguins are birds that cannot fly"
    match = re.match(r"(.+?)\s+(?:is|are)\s+(.+?)\s+that\s+cannot\s+(.+)", rest)
    if match:
        subj = match.group(1).strip()
        category = match.group(2).strip()
        inability = match.group(3).strip()
        parser.loom.add_fact(subj, "is", category)
        parser.loom.add_fact(subj, "cannot", inability)
        parser.last_subject = subj
        return f"Got it, {subj} are {category} that cannot {inability}."

    # Process the rest as a normal statement
    return parser.parse(rest)


def _check_because_pattern(parser, t: str) -> str | None:
    """Handle 'Because X, Y', 'Since X, Y', or 'X because Y' patterns."""
    # Pattern 1: "because X, Y" or "since X, Y" at the START
    match = re.match(r"(?:because|since)\s+(.+?),\s*(.+)", t, re.IGNORECASE)

    # Pattern 2: "X because Y" - because in the MIDDLE
    if not match and " because " in t:
        parts = t.split(" because ", 1)
        if len(parts) == 2:
            main_statement = parts[0].strip()
            reason = parts[1].strip()

            # Process the main statement first
            # Handle "X is/are Y because Z"
            is_match = re.match(r"(.+?)\s+(is|are)\s+(.+)", main_statement)
            if is_match:
                subj = is_match.group(1).strip()
                verb = is_match.group(2)
                obj = is_match.group(3).strip()

                # Clean up subject
                for prefix in ["the ", "a ", "an "]:
                    if subj.startswith(prefix):
                        subj = subj[len(prefix):]

                # Store the main fact
                if is_adjective(obj.split()[0] if obj else ""):
                    parser.loom.add_fact(subj, "has_property", obj)
                else:
                    parser.loom.add_fact(subj, "is", obj)

                # Store the reason as a property of the subject
                parser.loom.add_fact(subj, "because", reason)

                parser.last_subject = subj
                parser.loom.context.update(subject=subj)

                return f"Got it, {subj} {verb} {obj}."

            # Handle "X verb Y because Z" (other verbs)
            verb_match = re.match(r"(.+?)\s+(use|uses|need|needs|have|has|can|produce|produces)\s+(.+)", main_statement)
            if verb_match:
                subj = verb_match.group(1).strip()
                verb = verb_match.group(2).strip()
                obj = verb_match.group(3).strip()

                # Map verb to relation
                verb_map = {
                    "use": "uses", "uses": "uses",
                    "need": "needs", "needs": "needs",
                    "have": "has", "has": "has",
                    "can": "can",
                    "produce": "produces", "produces": "produces",
                }
                relation = verb_map.get(verb, verb)

                parser.loom.add_fact(subj, relation, obj)
                parser.loom.add_fact(subj, "because", reason)

                parser.last_subject = subj
                return f"Got it, {subj} {verb} {obj}."

            # Fallback: just store the reason connection
            return None

    if not match:
        return None

    cause_part = match.group(1).strip()
    effect_part = match.group(2).strip()

    # Extract the core subject from cause (e.g., "cats are hunters" -> "cats")
    cause_subj = None
    cause_pred = None
    if " are " in cause_part:
        parts = cause_part.split(" are ", 1)
        cause_subj = parts[0].strip()
        cause_pred = parts[1].strip()
    elif " is " in cause_part:
        parts = cause_part.split(" is ", 1)
        cause_subj = parts[0].strip()
        cause_pred = parts[1].strip()

    # Store the cause fact - use has_property for adjectives, is for nouns
    if cause_subj and cause_pred:
        if is_adjective(cause_pred):
            parser.loom.add_fact(cause_subj, "has_property", cause_pred)
        else:
            parser.loom.add_fact(cause_subj, "is", cause_pred)
        parser.last_subject = cause_subj

    # Extract the effect (e.g., "they have sharp claws" -> resolve "they", then add has relation)
    effect_part = effect_part.lower()

    # Resolve "they" to the cause subject
    if effect_part.startswith("they ") and cause_subj:
        effect_part = cause_subj + effect_part[4:]

    # Parse the effect part for "X have/has Y"
    have_match = re.match(r"(.+?)\s+(?:have|has)\s+(.+)", effect_part)
    if have_match:
        subj = have_match.group(1).strip()
        obj = have_match.group(2).strip()
        parser.loom.add_fact(subj, "has", obj)
        return f"Got it, {cause_subj} are {cause_pred}, so {subj} have {obj}."

    # Parse for "X eat/eats Y"
    eat_match = re.match(r"(.+?)\s+(?:eat|eats)\s+(.+)", effect_part)
    if eat_match:
        subj = eat_match.group(1).strip()
        obj = eat_match.group(2).strip()
        parser.loom.add_fact(subj, "eats", obj)
        return f"Got it, because {cause_subj} are {cause_pred}, {subj} eat {obj}."

    # Parse for "X can Y"
    can_match = re.match(r"(.+?)\s+can\s+(.+)", effect_part)
    if can_match:
        subj = can_match.group(1).strip()
        action = can_match.group(2).strip()
        parser.loom.add_fact(subj, "can", action)
        return f"Got it, because {cause_subj} are {cause_pred}, {subj} can {action}."

    # Parse for "X need/needs Y"
    need_match = re.match(r"(.+?)\s+(?:need|needs)\s+(.+)", effect_part)
    if need_match:
        subj = need_match.group(1).strip()
        obj = need_match.group(2).strip()
        parser.loom.add_fact(subj, "needs", obj)
        return f"Got it, because {cause_subj} are {cause_pred}, {subj} need {obj}."

    # Store a general causal relationship
    if cause_pred:
        parser.loom.add_fact(cause_pred, "causes", effect_part)

    return f"Got it, because {cause_part}."
