"""
Generic Query Engine for Loom.

Replaces 40+ hardcoded query handlers with a single structural approach.
Parses questions using the same SVO logic used for statements, then
maps question words to lookup strategies.

Question types:
  "what does X verb?"       → get(X, verb) → return object
  "who verbed X?"           → reverse lookup: find Y where Y --verb--> X
  "where does X verb?"      → get(X, verb) → return location
  "what is X?"              → get(X, is) or get(X, has_property)
  "can X verb?"             → get(X, can) → check if verb is in results
  "is X Y?"                 → get(X, is) → check if Y matches
  "does X verb Y?"          → get(X, verb) → check if Y matches (yes/no)
"""

import re
from typing import Optional, List, Tuple
from .normalizer import normalize, prettify
from .grammar import is_plural, format_list
from .svo import AUXILIARIES, NON_VERBS, PREPOSITIONS
from .parser.relations import get_relation_for_verb


# ─── Question structure parsing ───

def parse_question(text: str) -> Optional[dict]:
    """
    Parse a question into its structural components.

    Returns dict with:
        q_word: str — what/who/where/when/how/can/is/does (the question type)
        subject: str — what we're asking about
        verb: str — the action/relation being asked about (if any)
        object: str — additional object (for yes/no questions)
        direction: str — "forward" (get object) or "reverse" (find subject)
    """
    t = text.lower().strip().rstrip("?.")

    # ─── "what is X made from/of?" ───
    # "what is cheese made from?" → subject=cheese, relation=made_of
    m = re.match(r"what\s+(?:is|are)\s+(.+?)\s+made\s+(?:from|of|out of)\s*$", t)
    if m:
        return {
            "q_word": "what",
            "subject": m.group(1).strip(),
            "verb": "made",
            "relation": "made_of",
            "object": None,
            "direction": "forward",
        }

    # ─── "what is/are X?" ───
    # "what is valdoria?" → subject=valdoria, look up is/has_property
    m = re.match(r"what\s+(?:is|are)\s+(.+)\s*$", t)
    if m:
        subj = m.group(1).strip()
        return {
            "q_word": "what_is",
            "subject": subj,
            "verb": "is",
            "relation": "is",
            "object": None,
            "direction": "forward",
        }

    # ─── "what does/do X verb [prep]?" ───
    # "what does the internet connect?" → subject=the internet, verb=connect
    # Use GREEDY subject (.+) and the LAST word as the verb.
    m = re.match(r"what\s+(?:does|do)\s+(.+)\s+(\w+)(?:\s+(\w+))?\s*$", t)
    if m:
        subj, verb, prep = m.group(1).strip(), m.group(2), m.group(3)
        if verb == "do":
            return None  # "what does X do?" needs special handling
        relation = verb
        if prep and prep in PREPOSITIONS:
            relation = f"{verb}_{prep}"
        return {
            "q_word": "what",
            "subject": subj,
            "verb": verb,
            "relation": relation,
            "object": None,
            "direction": "forward",
        }

    # ─── "what did X verb?" ───
    m = re.match(r"what\s+did\s+(.+?)\s+(\w+)\s*$", t)
    if m:
        subj, verb = m.group(1), m.group(2)
        return {
            "q_word": "what",
            "subject": subj,
            "verb": verb,
            "relation": verb,
            "object": None,
            "direction": "forward",
        }

    # ─── "who is/are X?" ───
    # "who is the president of valdoria?" → look up who X is
    m = re.match(r"who\s+(?:is|are|was|were)\s+(.+)\s*$", t)
    if m:
        return {
            "q_word": "who",
            "subject": m.group(1),
            "verb": "is",
            "relation": "is",
            "object": None,
            "direction": "forward",
        }

    # ─── "who verbed X?" ───
    # "who founded valdoria?" → verb=founded, object=valdoria, direction=reverse
    m = re.match(r"who\s+(\w+)\s+(.+)\s*$", t)
    if m:
        verb, obj = m.group(1), m.group(2)
        return {
            "q_word": "who",
            "subject": None,
            "verb": verb,
            "relation": verb,
            "object": obj,
            "direction": "reverse",
        }

    # ─── "where did X verb?" ───
    # "where did golf originate?" → subject=golf, verb=originate
    m = re.match(r"where\s+did\s+(.+?)\s+(\w+)\s*$", t)
    if m:
        subj, verb = m.group(1), m.group(2)
        return {
            "q_word": "where",
            "subject": subj,
            "verb": verb,
            "relation": verb,
            "object": None,
            "direction": "forward",
        }

    # ─── "where does X verb [prep]?" ───
    # "where does the alune river flow through?" → subject=the alune river, verb=flow
    m = re.match(r"where\s+(?:does|do)\s+(.+?)\s+(\w+)(?:\s+(\w+))?\s*$", t)
    if m:
        subj, verb, prep = m.group(1), m.group(2), m.group(3)
        relation = verb
        if prep and prep in PREPOSITIONS:
            relation = f"{verb}_{prep}"
        return {
            "q_word": "where",
            "subject": subj,
            "verb": verb,
            "relation": relation,
            "object": None,
            "direction": "forward",
        }

    # ─── "when does X verb?" ───
    m = re.match(r"when\s+(?:does|do|did)\s+(.+?)\s+(\w+)\s*$", t)
    if m:
        return {
            "q_word": "when",
            "subject": m.group(1),
            "verb": m.group(2),
            "relation": m.group(2),
            "object": None,
            "direction": "forward",
        }

    # ─── "how does X verb [rest]?" ───
    m = re.match(r"how\s+(?:does|do|can)\s+(.+?)\s+(\w+)(?:\s+(.+))?\s*$", t)
    if m:
        subj, verb = m.group(1), m.group(2)
        rest = m.group(3) or ""
        return {
            "q_word": "how",
            "subject": subj,
            "verb": verb,
            "relation": verb,
            "object": rest.strip() if rest else None,
            "direction": "forward",
        }

    # ─── "can X verb Y?" ───
    m = re.match(r"can\s+(.+?)\s+(\w+)(?:\s+(.+))?\s*$", t)
    if m:
        subj, verb = m.group(1), m.group(2)
        obj = m.group(3)
        return {
            "q_word": "can",
            "subject": subj,
            "verb": verb,
            "relation": "can",
            "object": obj.strip() if obj else verb,
            "direction": "yesno",
        }

    # ─── "does X verb Y?" / "do X verb Y?" ───
    # "does bluetooth enable wireless communication?" → subject=bluetooth, verb=enable, object=wireless communication
    # Strategy: try to find the verb by checking each word from the end backward
    m = re.match(r"(?:does|do)\s+(.+)\s*$", t)
    if m:
        rest = m.group(1).strip()
        words = rest.split()
        if len(words) >= 3:
            # Try splitting at each position to find a valid verb
            # Check from position 1 onwards (at least 1 word for subject)
            for i in range(1, len(words) - 1):
                candidate_verb = words[i]
                # A verb should not be a determiner/preposition
                if candidate_verb in NON_VERBS or candidate_verb in PREPOSITIONS:
                    continue
                # Accept if it's a known relation or looks like a verb
                try:
                    from .parser.relations import RELATION_BY_ANY_VERB
                    is_known = candidate_verb in RELATION_BY_ANY_VERB
                except ImportError:
                    is_known = False
                # Accept: known verbs, morphological verbs, or base-form verbs
                # (words ending in -ate, -ify, -ize, -ect, -ble, -ude are often verbs)
                verb_endings = ("s", "ed", "ing", "es", "ate", "ify", "ize", "ise",
                                "ect", "ble", "ude", "ose", "ive", "orm")
                if is_known or candidate_verb.endswith(verb_endings):
                    subj = " ".join(words[:i])
                    verb = candidate_verb
                    obj = " ".join(words[i+1:])
                    return {
                        "q_word": "does",
                        "subject": subj,
                        "verb": verb,
                        "relation": verb,
                        "object": obj,
                        "direction": "yesno",
                    }

    # ─── "is X Y?" / "are X Y?" ───
    # "is mount velar a volcano?" → subject=mount velar, object=volcano
    # Use "a/an" as the split point if present
    m = re.match(r"(?:is|are)\s+(.+?)\s+(?:a|an)\s+(.+)\s*$", t)
    if m:
        subj, obj = m.group(1), m.group(2)
        return {
            "q_word": "is",
            "subject": subj,
            "verb": "is",
            "relation": "is",
            "object": obj,
            "direction": "yesno",
        }
    # Without "a/an": "is mount velar inactive?" → split on last word
    m = re.match(r"(?:is|are)\s+(.+?)\s+(\w+)\s*$", t)
    if m:
        subj, obj = m.group(1), m.group(2)
        return {
            "q_word": "is",
            "subject": subj,
            "verb": "is",
            "relation": "is",
            "object": obj,
            "direction": "yesno",
        }

    # ─── "what verbs X?" (reverse) ───
    # "what celebrates the ocean?" → verb=celebrates, object=ocean
    m = re.match(r"what\s+(\w+(?:es|ed|s))\s+(.+)\s*$", t)
    if m:
        verb, obj = m.group(1), m.group(2)
        if verb not in ("is", "are", "was", "were", "does", "do", "has", "have"):
            return {
                "q_word": "what",
                "subject": None,
                "verb": verb,
                "relation": verb,
                "object": obj,
                "direction": "reverse",
            }

    return None


# ─── Lookup strategies ───

def _try_subject_variants(subject: str) -> List[str]:
    """Generate singular/plural variants of a subject."""
    variants = [subject]
    # Try adding/removing trailing 's' for singular/plural
    if subject.endswith("s") and len(subject) > 3:
        variants.append(subject[:-1])  # dogs -> dog
    else:
        variants.append(subject + "s")  # dog -> dogs
    # Strip leading articles
    for prefix in ["the ", "a ", "an "]:
        if subject.startswith(prefix):
            base = subject[len(prefix):]
            if base not in variants:
                variants.append(base)
            if base.endswith("s") and len(base) > 3:
                variants.append(base[:-1])
            else:
                variants.append(base + "s")
    return variants


def _try_relation_variants(loom, subject: str, relation: str) -> Tuple[Optional[list], str]:
    """
    Try multiple subject AND relation variants to find stored facts.
    Returns (results, matched_relation).
    """
    from .svo import IRREGULAR_PAST

    # Irregular present → past mapping for common verbs
    IRREGULAR_MAP = {
        "begin": "began", "become": "became", "break": "broke",
        "bring": "brought", "build": "built", "buy": "bought",
        "come": "came", "catch": "caught", "choose": "chose",
        "do": "did", "draw": "drew", "drive": "drove", "eat": "ate",
        "fall": "fell", "feel": "felt", "fly": "flew", "forget": "forgot",
        "find": "found", "give": "gave", "get": "got", "grow": "grew",
        "hold": "held", "hide": "hid", "keep": "kept", "know": "knew",
        "lead": "led", "leave": "left", "lose": "lost", "make": "made",
        "meet": "met", "pay": "paid", "run": "ran", "ring": "rang",
        "rise": "rose", "say": "said", "see": "saw", "send": "sent",
        "shake": "shook", "shoot": "shot", "show": "showed",
        "sing": "sang", "sink": "sank", "sleep": "slept",
        "speak": "spoke", "spend": "spent", "stand": "stood",
        "steal": "stole", "strike": "struck", "swim": "swam",
        "sweep": "swept", "swing": "swung", "teach": "taught",
        "think": "thought", "throw": "threw", "tell": "told",
        "take": "took", "understand": "understood", "wake": "woke",
        "win": "won", "wear": "wore", "write": "wrote",
        "originate": "originated", "automate": "automated",
    }
    # Also build reverse: past → present
    IRREGULAR_REVERSE = {v: k for k, v in IRREGULAR_MAP.items()}

    # Build relation variants
    rel_variants = [relation]
    rel_def = get_relation_for_verb(relation)
    if rel_def:
        rel_variants.insert(0, rel_def.relation)
    if not relation.endswith("s"):
        rel_variants.append(relation + "s")
    if relation.endswith("s") and len(relation) > 3:
        rel_variants.append(relation[:-1])
    if not relation.endswith("ed"):
        rel_variants.append(relation + "ed")
    if relation.endswith("ed") and len(relation) > 4:
        rel_variants.append(relation[:-2])
    # Irregular past tense: "begin" → "began", "originate" → "originated"
    if relation in IRREGULAR_MAP:
        rel_variants.append(IRREGULAR_MAP[relation])
    if relation in IRREGULAR_REVERSE:
        rel_variants.append(IRREGULAR_REVERSE[relation])
    # Try verb + preposition variants (common for location-storing patterns)
    # "begin" → "began_in", "originate" → "originated_in", etc.
    base_variants = list(rel_variants)  # snapshot before suffixing
    for suffix in ["_in", "_on", "_at", "_to", "_from", "_through"]:
        for base in base_variants:
            variant = base + suffix
            if variant not in rel_variants:
                rel_variants.append(variant)

    # Build subject variants (singular/plural)
    subj_variants = _try_subject_variants(subject)

    # Try all combinations
    for subj in subj_variants:
        for rel in rel_variants:
            result = loom.get(subj, rel)
            if result:
                return result, rel

    return None, relation


def _reverse_lookup(loom, relation: str, target: str) -> list:
    """
    Reverse lookup: find all subjects X where X --relation--> target.
    """
    target_norm = normalize(target)
    results = []

    # Check if there's a reverse relation defined
    rel_def = get_relation_for_verb(relation)

    # Try the reverse relation first (more efficient)
    if rel_def and rel_def.reverse:
        reverse_results = loom.get(target, rel_def.reverse)
        if reverse_results:
            return reverse_results

    # Fallback: scan all knowledge for matching relations
    relation_variants = {relation}
    if rel_def:
        relation_variants.add(rel_def.relation)
    if not relation.endswith("s"):
        relation_variants.add(relation + "s")
    if relation.endswith("s") and len(relation) > 3:
        relation_variants.add(relation[:-1])
    if not relation.endswith("ed"):
        relation_variants.add(relation + "ed")
    if relation.endswith("ed") and len(relation) > 4:
        relation_variants.add(relation[:-2])

    for entity, relations in loom.knowledge.items():
        for rel_variant in relation_variants:
            if rel_variant in relations:
                objects = relations[rel_variant]
                obj_list = list(objects) if not isinstance(objects, list) else objects
                for obj in obj_list:
                    obj_norm = normalize(obj)
                    # Match if exact, substring, or shared prefix
                    if (obj_norm == target_norm
                            or target_norm in obj_norm
                            or obj_norm in target_norm
                            or obj_norm.startswith(target_norm + "_")
                            or target_norm.startswith(obj_norm + "_")):
                        results.append(entity)
                        break

    return results


def _handle_what_is(loom, subject: str) -> Optional[str]:
    """
    Handle "what is X?" queries by checking multiple relation types.
    Mirrors the logic from _check_what_query but works generically.
    """
    # Strip leading articles
    subj = subject
    for prefix in ["the ", "a ", "an "]:
        if subj.lower().startswith(prefix):
            subj = subj[len(prefix):]

    # Helper: try subject variants + adjective stripping for "Adj Noun of X" patterns
    def _try_stripped(relation):
        # Try subject as-is and singular/plural variants
        for variant in _try_subject_variants(subj):
            result = loom.get(variant, relation)
            if result:
                return result, variant

        # Try stripping a leading adjective
        subj_norm = normalize(subj)
        words = subj.split()
        if len(words) >= 3:
            candidate = " ".join(words[1:])
            cand_norm = normalize(candidate)
            if "_" in cand_norm and cand_norm != subj_norm:
                for variant in _try_subject_variants(candidate):
                    result = loom.get(variant, relation)
                    if result:
                        return result, variant
        return None, subj

    # 1. Check "is" relation (category)
    facts, matched_subj = _try_stripped("is")
    if facts:
        verb = "are" if is_plural(matched_subj) else "is"
        categories = [f.replace("_", " ") for f in facts]
        return f"{matched_subj.title()} {verb} {format_list(categories)}."

    # 2. Check has_instance (reverse: "what is the dish of X?" → find instances)
    if "of" in subj.split():
        instances, matched_subj = _try_stripped("has_instance")
        if instances:
            verb = "are" if is_plural(matched_subj) else "is"
            display = [i.replace("_", " ") for i in instances]
            return f"{format_list([d.title() for d in display])} {verb} the {matched_subj}."

    # 3. Check properties
    props, matched_subj = _try_stripped("has_property")
    props = props or []
    if props:
        verb = "are" if is_plural(matched_subj) else "is"
        display = [p.replace("_", " ") for p in props]
        return f"{matched_subj.title()} {verb} {format_list(display)}."

    # 4. Check any action relations (describe by what it does)
    subj_norm = normalize(subj)
    if subj_norm in loom.knowledge:
        relations = loom.knowledge[subj_norm]
        skip_rels = {"has_instance", "belongs_to", "has_open_question",
                     "has_property", "is", "differs_from"}
        for rel, objs in relations.items():
            if rel in skip_rels or rel.endswith("_by") or rel.endswith("_of"):
                continue
            if objs:
                obj_list = list(objs) if not isinstance(objs, list) else objs
                obj_display = [o.replace("_", " ") for o in obj_list]
                rel_display = rel.replace("_", " ")
                return f"{subj.title()} {rel_display} {format_list(obj_display)}."

    return None


# ─── Main query handler ───

def handle_query(parser, text: str) -> Optional[str]:
    """
    Generic query handler that replaces specialized query functions.

    Parses the question structurally and maps to the right lookup strategy.
    Returns a natural language answer, or None if it can't handle the question.
    """
    q = parse_question(text)
    if not q:
        return None

    subject = q["subject"]
    relation = q["relation"]
    verb = q["verb"]
    obj = q["object"]
    direction = q["direction"]
    q_word = q["q_word"]

    loom = parser.loom

    # ─── "what is X?" — the most common query type ───
    if q_word == "what_is" and subject:
        return _handle_what_is(loom, subject)

    # ─── Forward lookup: get(subject, relation) ───
    if direction == "forward" and subject:
        # "who is X?" → look up is relation
        if q_word == "who" and relation == "is":
            return _handle_what_is(loom, subject)

        results, matched_rel = _try_relation_variants(loom, subject, relation)

        if results:
            display = [r.replace("_", " ") for r in results]
            verb_display = verb
            if not is_plural(subject):
                if not verb.endswith("s"):
                    verb_display = verb + "s"

            return f"{subject.title()} {verb_display} {format_list(display)}."

        # Forward lookup failed — try location-specific relations for "where"
        if q_word == "where":
            for loc_rel in ["lives_in", "located_in", "found_in",
                            f"{verb}_in", f"{verb}s_in"]:
                for subj_v in _try_subject_variants(subject):
                    result = loom.get(subj_v, loc_rel)
                    if result:
                        display = [r.replace("_", " ") for r in result]
                        return f"{subject.title()} {verb}s in {format_list(display)}."

    # ─── Reverse lookup: find X where X --relation--> object ───
    if direction == "reverse" and obj:
        agents = _reverse_lookup(loom, relation, obj)

        if agents:
            display = [a.replace("_", " ") for a in agents]
            verb_past = verb
            # Try to get past tense
            rel_def = get_relation_for_verb(verb)
            if rel_def:
                verb_past = rel_def.past

            if q_word == "who":
                return f"{format_list([d.title() for d in display])} {verb_past} {obj}."
            elif q_word == "what":
                return f"{format_list([d.title() for d in display])} {verb_past} {obj}."

    # ─── Yes/No questions ───
    if direction == "yesno" and subject and obj:
        if q_word == "can":
            obj_norm = normalize(obj)
            # Try subject variants for singular/plural
            for subj_v in _try_subject_variants(subject):
                abilities = loom.get(subj_v, "can") or []
                for ability in abilities:
                    if obj_norm in normalize(ability) or normalize(ability) in obj_norm:
                        return f"Yes, {subject} can {obj}."
                cannot = loom.get(subj_v, "cannot") or []
                for inability in cannot:
                    if obj_norm in normalize(inability):
                        return f"No, {subject} cannot {obj}."
            return None  # Let specialized handler try

        elif q_word == "is":
            # "is X Y?" → check if X is Y
            obj_norm = normalize(obj)
            for subj_v in _try_subject_variants(subject):
                categories = loom.get(subj_v, "is") or []
                for cat in categories:
                    if obj_norm in normalize(cat) or normalize(cat) in obj_norm:
                        verb_form = "are" if is_plural(subject) else "is"
                        return f"Yes, {subject} {verb_form} {obj}."
                props = loom.get(subj_v, "has_property") or []
                for prop in props:
                    if obj_norm in normalize(prop):
                        return f"Yes, {subject} is {obj}."
            return None  # Let specialized handler try

        elif q_word == "does":
            results, _ = _try_relation_variants(loom, subject, relation)
            if results:
                obj_norm = normalize(obj)
                for r in results:
                    if obj_norm in normalize(r) or normalize(r) in obj_norm:
                        return f"Yes, {subject} {verb}s {obj}."
                # Has the relation but not with this object
                display = [r.replace("_", " ") for r in results]
                return f"{subject.title()} {verb}s {format_list(display)}, but not {obj}."

    return None
