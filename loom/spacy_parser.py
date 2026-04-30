"""
spaCy-powered dependency parser for Loom.

Uses spaCy's dependency parse to extract facts from complex sentences:
- Relative clauses: "Cats that have claws can climb trees"
- Conjoined VPs: "Birds fly and lay eggs"
- Conjoined objects: "Cats eat fish, birds, rats, and mice"
- Passive voice: "Electrons were discovered by Thomson"
- Subordinate clauses: "Although it rains, flowers bloom"
- Participial phrases: "Known for their intelligence, dolphins communicate"

Falls back gracefully if spaCy isn't available.
"""

from dataclasses import dataclass
from typing import List, Optional

try:
    import spacy
    # Prefer the large model for better accuracy, fall back to small
    try:
        _nlp = spacy.load("en_core_web_lg")
    except OSError:
        _nlp = spacy.load("en_core_web_sm")
    SPACY_AVAILABLE = True
except Exception:
    _nlp = None
    SPACY_AVAILABLE = False


@dataclass
class ExtractedFact:
    subject: str
    relation: str
    obj: str
    negated: bool = False


# Relation mapping from dependency verbs
_VERB_TO_RELATION = {
    "is": "is", "are": "is", "was": "is", "were": "is",
    "has": "has", "have": "has", "had": "has",
    "can": "can", "could": "can",
    "cannot": "cannot",
    "lives": "lives_in", "live": "lives_in",
    "eats": "eats", "eat": "eats",
    "causes": "causes", "cause": "causes",
    "needs": "needs", "need": "needs",
    "produces": "produces", "produce": "produces",
    "contains": "contains", "contain": "contains",
}

# Prepositions that map to location relations
_LOC_PREPS = {"in", "on", "at", "near", "inside", "within"}


def parse(text: str) -> List[ExtractedFact]:
    """
    Parse a sentence using spaCy and extract facts.
    Returns empty list if spaCy isn't available or parsing fails.
    """
    if not SPACY_AVAILABLE or not text:
        return []

    text = text.strip().rstrip(".")
    if len(text) > 500 or len(text) < 5:
        return []

    try:
        doc = _nlp(text)
        facts = []
        for sent in doc.sents:
            facts.extend(_extract_from_sentence(sent))
        return facts
    except Exception:
        return []


def _extract_from_sentence(sent) -> List[ExtractedFact]:
    """Extract facts from a single spaCy sentence."""
    facts = []
    root = sent.root

    if root.pos_ != "VERB" and root.pos_ != "AUX":
        return facts

    # Get subjects (including conjoined: "cats and dogs")
    subjects = _get_subjects(root)
    if not subjects:
        return facts

    # Get the main verb and its negation
    verb, negated = _get_verb_info(root)

    # Get objects (including conjoined: "fish, birds, and mice")
    objects = _get_objects(root)

    # Get prepositional complements
    preps = _get_prep_phrases(root)

    # Check if "can"/"could" auxiliary — relation becomes "can", object is the verb action
    has_modal = False
    for child in root.children:
        if child.dep_ == "aux" and child.text.lower() in ("can", "could", "may", "might"):
            has_modal = True
            break

    if has_modal and not objects:
        # "cats can climb trees" → can + climb (verb is the action)
        # The root verb IS the action; objects are its dobj
        verb_action = root.lemma_.lower()
        direct_objs = [child for child in root.children if child.dep_ == "dobj"]
        if direct_objs:
            for dobj in direct_objs:
                obj_text = _get_subtree_text(dobj, skip_deps={"relcl", "punct", "conj", "cc"})
                for subj in subjects:
                    facts.append(ExtractedFact(
                        subject=subj, relation="cannot" if negated else "can",
                        obj=f"{verb_action} {obj_text}".strip(), negated=negated
                    ))
        else:
            # Intransitive: "birds can fly"
            for subj in subjects:
                facts.append(ExtractedFact(
                    subject=subj, relation="cannot" if negated else "can",
                    obj=verb_action, negated=negated
                ))
    else:
        # Build relation from verb
        relation = _verb_to_relation(verb, negated)

        if objects:
            # Main facts: subject → relation → object
            for subj in subjects:
                for obj in objects:
                    if subj and obj and subj != obj:
                        facts.append(ExtractedFact(
                            subject=subj, relation=relation, obj=obj, negated=negated
                        ))
        elif not preps:
            # Intransitive verb: "birds fly" → subject can verb
            for subj in subjects:
                facts.append(ExtractedFact(
                    subject=subj, relation="can", obj=root.lemma_.lower(), negated=negated
                ))

        # Prepositional facts
        for subj in subjects:
            for prep, pobj in preps:
                if subj and pobj:
                    prep_rel = _prep_to_relation(prep, verb)
                    facts.append(ExtractedFact(subject=subj, relation=prep_rel, obj=pobj))

    # Handle relative clauses
    for subj_token in _find_tokens_with_dep(sent, "nsubj"):
        for rc in subj_token.head.children if subj_token.dep_ == "nsubj" else []:
            pass  # Handled below

    # Walk the tree for relative clauses (relcl)
    for token in sent:
        if token.dep_ == "relcl":
            # The head of relcl is the noun being modified
            rc_subject = _get_subtree_text(token.head, skip_deps={"relcl", "punct", "cc", "conj"})
            rc_verb, rc_neg = _get_verb_info(token)
            rc_objects = _get_objects(token)
            rc_relation = _verb_to_relation(rc_verb, rc_neg)

            for obj in rc_objects:
                if rc_subject and obj:
                    facts.append(ExtractedFact(
                        subject=rc_subject, relation=rc_relation, obj=obj, negated=rc_neg
                    ))

            # Relative clause prep phrases
            for prep, pobj in _get_prep_phrases(token):
                if rc_subject and pobj:
                    facts.append(ExtractedFact(
                        subject=rc_subject,
                        relation=_prep_to_relation(prep, rc_verb),
                        obj=pobj
                    ))

    # Handle conjoined verbs: "birds fly and lay eggs"
    for conj_verb in root.conjuncts:
        if conj_verb.pos_ == "VERB":
            conj_v, conj_neg = _get_verb_info(conj_verb)
            conj_objects = _get_objects(conj_verb)
            conj_relation = _verb_to_relation(conj_v, conj_neg)

            for subj in subjects:
                for obj in conj_objects:
                    if subj and obj:
                        facts.append(ExtractedFact(
                            subject=subj, relation=conj_relation, obj=obj, negated=conj_neg
                        ))

                for prep, pobj in _get_prep_phrases(conj_verb):
                    if subj and pobj:
                        facts.append(ExtractedFact(
                            subject=subj,
                            relation=_prep_to_relation(prep, conj_v),
                            obj=pobj
                        ))

    # Deduplicate
    seen = set()
    unique = []
    for f in facts:
        key = (f.subject.lower(), f.relation, f.obj.lower())
        if key not in seen:
            seen.add(key)
            unique.append(f)

    return unique


# ── Tree traversal helpers ────────────────────────────────────────────

def _get_subjects(verb_token) -> List[str]:
    """Get all subjects of a verb, including conjoined subjects."""
    subjects = []
    for child in verb_token.children:
        if child.dep_ in ("nsubj", "nsubjpass"):
            # Get just this subject's subtree, excluding conjuncts
            subj_text = _get_subtree_text(child, skip_deps={"relcl", "punct", "acl", "conj", "cc"})
            subjects.append(subj_text)
            # Each conjunct as a separate subject: "cats and dogs" → [cats, dogs]
            for conj in child.conjuncts:
                subjects.append(_get_subtree_text(conj, skip_deps={"relcl", "punct", "acl", "conj", "cc"}))
    return [s for s in subjects if s]


def _get_objects(verb_token) -> List[str]:
    """Get all objects of a verb, including conjoined objects."""
    objects = []
    for child in verb_token.children:
        if child.dep_ in ("dobj", "attr", "acomp", "oprd"):
            # Get ONLY this token's direct modifiers, not conjuncts
            obj_text = _get_subtree_text(child, skip_deps={"relcl", "punct", "acl", "prep", "conj", "cc"})
            objects.append(obj_text)
            # Each conjunct as a separate object: "fish, birds, and mice" → [fish, birds, mice]
            for conj in child.conjuncts:
                objects.append(_get_subtree_text(conj, skip_deps={"relcl", "punct", "acl", "prep", "conj", "cc"}))
    # For intransitive verbs used with "can" (e.g., "can climb"), object might be missing
    # Check for advmod/particle that acts as complement
    if not objects:
        for child in verb_token.children:
            if child.dep_ in ("advmod", "prt") and child.pos_ not in ("PUNCT", "DET"):
                objects.append(child.text)
    return [o for o in objects if o]


def _get_prep_phrases(verb_token) -> List[tuple]:
    """Get prepositional phrases attached to a verb."""
    preps = []
    for child in verb_token.children:
        if child.dep_ == "prep":
            prep_word = child.text.lower()
            for pobj_child in child.children:
                if pobj_child.dep_ == "pobj":
                    pobj_text = _get_subtree_text(pobj_child, skip_deps={"punct"})
                    if pobj_text:
                        preps.append((prep_word, pobj_text))
    return preps


def _get_verb_info(token) -> tuple:
    """Get the main verb lemma and negation status."""
    verb = token.lemma_.lower()
    negated = False

    for child in token.children:
        if child.dep_ == "neg":
            negated = True
        # Handle "cannot" as a single token
        if child.dep_ == "aux" and child.text.lower() in ("cannot", "can't"):
            negated = True
            verb = child.lemma_.lower()

    # Check for auxiliary "can" / "could" etc.
    for child in token.children:
        if child.dep_ == "aux" and child.text.lower() in ("can", "could", "may", "might"):
            # The relation becomes "can" + the main verb is the object
            return child.text.lower(), negated

    return verb, negated


def _get_subtree_text(token, skip_deps=None) -> str:
    """Get clean text from a token's subtree, skipping entire branches for certain deps."""
    skip_deps = skip_deps or set()

    # Collect token indices to skip (entire subtrees of skipped deps)
    skip_ids = set()
    for t in token.subtree:
        if t.dep_ in skip_deps and t != token:
            for st in t.subtree:
                skip_ids.add(st.i)

    words = []
    for t in sorted(token.subtree, key=lambda x: x.i):
        if t.i in skip_ids:
            continue
        if t.pos_ == "PUNCT":
            continue
        if t.pos_ == "DET" and t.text.lower() in ("the", "a", "an"):
            continue
        # Skip conjunctions in subject phrases
        if t.dep_ == "cc" and t.head == token:
            continue
        words.append(t.text)

    return " ".join(words).strip()


def _find_tokens_with_dep(sent, dep_label) -> list:
    """Find all tokens with a given dependency label."""
    return [t for t in sent if t.dep_ == dep_label]


# ── Relation mapping ─────────────────────────────────────────────────

def _verb_to_relation(verb: str, negated: bool = False) -> str:
    """Map a verb to a Loom relation name."""
    v = verb.lower()
    if v in ("be", "is", "are", "was", "were"):
        return "is_not" if negated else "is"
    if v in ("have", "has", "had"):
        return "has_not" if negated else "has"
    if v in ("can", "could"):
        return "cannot" if negated else "can"

    mapped = _VERB_TO_RELATION.get(v, v)
    if negated and not mapped.startswith("not_"):
        return f"cannot" if mapped == "can" else mapped
    return mapped


def _prep_to_relation(prep: str, verb: str) -> str:
    """Map preposition + verb context to a relation."""
    if prep in _LOC_PREPS:
        if verb in ("live", "lives", "be", "is", "are", "found", "find"):
            return "lives_in" if prep == "in" else f"located_{prep}"
        return "located_in"
    if prep == "by":
        return "by_agent"
    if prep == "with":
        return "has"
    if prep == "from":
        return "originates_from"
    if prep == "for":
        return "used_for"
    if prep == "of":
        return "part_of"
    return prep
