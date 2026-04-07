"""
SVO (Subject-Verb-Object) Extractor for Loom.

Extracts structured triples from natural language WITHOUT requiring
a hardcoded list of known verbs. Uses structural and morphological
heuristics to identify verbs by their position and form.

The verb itself becomes the relation — no predefined mapping needed.
"""

import re
from typing import Optional, Tuple, List


# ─── Structural words (not content verbs) ───
# These are function words that provide sentence structure.
# They're closed classes in English — unlike content verbs, they DON'T grow.

AUXILIARIES = {
    "is", "are", "was", "were", "be", "been", "being",
    "am", "has", "have", "had", "having",
    "do", "does", "did",
    "can", "could", "will", "would", "shall", "should",
    "may", "might", "must",
}

DETERMINERS = {
    "the", "a", "an", "this", "that", "these", "those",
    "my", "your", "his", "her", "its", "our", "their",
    "some", "any", "no", "every", "each", "all", "both",
    "few", "several", "many", "much", "most",
}

PREPOSITIONS = {
    "in", "on", "at", "to", "for", "with", "by", "from",
    "of", "about", "into", "through", "during", "before",
    "after", "above", "below", "between", "under", "over",
    "among", "along", "across", "around", "behind", "beside",
    "beyond", "inside", "outside", "upon", "within", "without",
    "throughout", "toward", "towards", "against", "until",
    "onto", "past", "near", "off",
}

CONJUNCTIONS = {"and", "or", "but", "nor", "yet", "so"}

PRONOUNS = {
    "i", "me", "you", "he", "him", "she", "her", "it",
    "we", "us", "they", "them", "who", "whom", "what",
    "which", "that", "this", "these", "those",
    "myself", "yourself", "himself", "herself", "itself",
    "ourselves", "themselves",
}

ADVERBS = {
    "very", "really", "quite", "also", "too", "always",
    "never", "often", "sometimes", "usually", "already",
    "still", "just", "only", "even", "not", "well",
    "approximately", "extremely", "incredibly",
}

# Words that are NEVER content verbs (combined non-verb set)
NON_VERBS = DETERMINERS | PREPOSITIONS | CONJUNCTIONS | ADVERBS | {
    "not", "then", "there", "here", "where", "when", "how",
    "why", "what", "who", "whom", "which", "if", "because",
    "although", "though", "while", "since", "unless", "until",
    "whether", "however", "therefore", "thus", "hence",
    "moreover", "furthermore", "nevertheless", "nonetheless",
    "meanwhile", "otherwise", "instead", "rather", "than",
}

# Passive voice markers
PASSIVE_MARKERS = {"by"}

# Common irregular past tenses that don't end in -ed
# These can't be detected by morphology alone
IRREGULAR_PAST = {
    "began", "begun", "became", "broke", "brought", "built", "bought",
    "came", "caught", "chose", "did", "drew", "drove", "ate", "fell",
    "felt", "flew", "forgot", "found", "gave", "got", "grew", "held",
    "hid", "hit", "kept", "knew", "led", "left", "lost", "made",
    "met", "paid", "put", "ran", "rang", "rose", "said", "sat",
    "saw", "sent", "set", "shook", "shot", "showed", "shut", "sang",
    "sank", "slept", "spoke", "spent", "stood", "stole", "struck",
    "swam", "swept", "swung", "taught", "thought", "threw", "told",
    "took", "understood", "woke", "won", "wore", "wrote",
}


def _looks_like_verb(word: str, position: int, words: List[str]) -> bool:
    """
    Determine if a word looks like a verb based on morphology and position.

    Heuristics:
    - Ends in -s (third person singular): "exports", "celebrates"
    - Ends in -ed (past tense): "founded", "exported"
    - Ends in -ing (progressive): "exporting"
    - Follows a noun/pronoun (positional)
    - Is NOT in the non-verb set
    """
    w = word.lower()

    # Definitely not a verb
    if w in NON_VERBS:
        return False

    # Must be at least 2 chars
    if len(w) < 2:
        return False

    # Position 0 is rarely a verb in declarative sentences
    # (it would be imperative mood, which Loom doesn't typically handle)
    if position == 0:
        return False

    # Check if this is a known irregular past tense
    if w in IRREGULAR_PAST:
        return True

    # Check if this is a known verb from the relations database.
    # This is NOT hardcoding — it's using the existing knowledge as a hint.
    # The morphological checks below still catch unknown verbs.
    try:
        from .parser.relations import RELATION_BY_ANY_VERB
        if w in RELATION_BY_ANY_VERB:
            return True
        # Also check "verb + preposition" phrases: "live in", "feed on", etc.
        if position + 1 < len(words):
            phrase = f"{w} {words[position + 1].lower()}"
            if phrase in RELATION_BY_ANY_VERB:
                return True
    except ImportError:
        pass

    # Check productive verb suffixes: -ate, -ize/-ise, -ify
    # "automate", "originate", "organize", "simplify"
    # These are almost always verbs in English.
    if len(w) > 4 and w.endswith(("ate", "ize", "ise", "ify")):
        # Exclude some common non-verb -ate words
        non_verb_ate = {"climate", "imate", "private", "state", "gate", "plate",
                        "late", "fate", "mate", "date", "rate", "estate",
                        "chocolate", "candidate", "senate", "pirate", "primate"}
        if w not in non_verb_ate:
            return True

    # Check morphological verb indicators
    # -ed ending (past tense) but not adjective-like words
    if w.endswith("ed") and len(w) > 3:
        # Exclude common -ed adjectives when preceded by "is/are"
        if position > 0 and words[position - 1].lower() in ("is", "are", "was", "were"):
            return False  # "is located" - "located" is participle/adj here
        return True

    # -ing ending (progressive)
    if w.endswith("ing") and len(w) > 4:
        return True

    # -es ending (third person: "teaches", "reaches", but not "clothes", "species")
    if w.endswith("es") and len(w) > 3:
        # Common non-verb -es words
        non_verb_es = {
            "species", "series", "clothes", "glasses", "dishes",
            "places", "pieces", "sometimes", "tides", "types",
            "movies", "stories", "bodies", "ones", "sides",
            "values", "homes", "states", "miles", "rules",
            "lighthouses", "bridges", "languages", "sentences",
        }
        if w in non_verb_es:
            return False
        return True

    # -s ending (third person singular: "exports", "flows")
    # This is the trickiest — many nouns end in -s too (plurals)
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        # If previous word looks like a subject (noun/pronoun/proper noun),
        # and the word is not likely a plural noun, treat as verb
        if position > 0:
            prev = words[position - 1].lower()
            # After a determiner or adjective, -s words are nouns
            if prev in DETERMINERS or prev in ADVERBS:
                return False
            # After a proper noun or common noun, -s might be verb
            # Check if next word exists and looks like start of object
            if position + 1 < len(words):
                next_w = words[position + 1].lower()
                # Verb if followed by determiner, noun, or preposition
                if next_w in DETERMINERS or next_w in PREPOSITIONS:
                    return True
                # Verb if followed by what looks like a noun (not another verb indicator)
                if next_w not in AUXILIARIES and next_w not in NON_VERBS:
                    return True

    return False


def _is_auxiliary_verb(word: str) -> bool:
    """Check if word is an auxiliary/linking verb."""
    return word.lower() in AUXILIARIES


def _normalize_verb_to_relation(verb: str) -> str:
    """
    Convert a verb form to a normalized relation name.

    "exports" -> "exports"
    "exported" -> "exported"
    "was founded" -> "founded"
    "celebrates" -> "celebrates"

    The verb IS the relation — no mapping table needed.
    We just clean it up slightly.
    """
    v = verb.lower().strip()

    # Remove auxiliary prefixes: "was founded" -> "founded"
    for aux in ["was ", "were ", "is ", "are ", "has ", "have ", "had ",
                "has been ", "have been ", "had been "]:
        if v.startswith(aux):
            v = v[len(aux):]
            break

    # Replace spaces with underscores for multi-word verbs
    v = v.replace(" ", "_")

    return v


def extract_svo(text: str) -> Optional[dict]:
    """
    Extract Subject-Verb-Object from a sentence.

    Returns dict with:
        subject: str
        verb: str (raw verb as found)
        relation: str (normalized for storage)
        object: str
        passive: bool (was this passive voice?)
        auxiliary: str or None (e.g., "was" in "was founded by")

    Returns None if no SVO pattern found.
    """
    t = text.strip().rstrip(".")
    words = t.split()

    if len(words) < 3:
        return None

    # ─── Strategy 1: Auxiliary + past participle (passive/past) ───
    # "X was founded by Y" -> founded(Y, X)
    # "X was founded in 1432 by Y" -> founded(Y, X) + temporal context
    # "X was elected in 2024" -> elected(X, in_2024)
    for i, w in enumerate(words):
        if w.lower() in ("was", "were", "is", "are", "has", "have", "had") and i > 0:
            # Check if next word is a past participle (-ed, irregular)
            if i + 1 < len(words):
                next_w = words[i + 1].lower()
                # Check if next word is a past participle:
                # 1. Regular: ends in -ed ("founded", "elected")
                # 2. Irregular: known past tense from relations DB ("built", "begun")
                is_participle = (next_w.endswith("ed") and len(next_w) > 3 and next_w not in NON_VERBS)
                if not is_participle:
                    # Check irregular past participles
                    if next_w in IRREGULAR_PAST:
                        is_participle = True
                if not is_participle:
                    try:
                        from .parser.relations import RELATION_BY_ANY_VERB
                        if next_w in RELATION_BY_ANY_VERB:
                            is_participle = True
                    except ImportError:
                        pass
                if is_participle:
                    subject = " ".join(words[:i])
                    verb_word = next_w
                    rest = " ".join(words[i + 2:])

                    # Check for passive "by" anywhere in rest (not just at start)
                    # "founded in 1432 by explorer Tomas" -> agent is after "by"
                    by_match = re.search(r'\bby\s+(.+)$', rest, re.IGNORECASE)
                    if by_match:
                        agent = by_match.group(1).strip()
                        # Everything before "by" is context (temporal, location, etc.)
                        before_by = rest[:by_match.start()].strip()
                        if agent:
                            result = {
                                "subject": agent,
                                "verb": verb_word,
                                "relation": _normalize_verb_to_relation(verb_word),
                                "object": subject,
                                "passive": True,
                                "auxiliary": w.lower(),
                            }
                            if before_by:
                                result["context"] = before_by
                            return result

                    # Active past: "X was established in 1789"
                    if rest:
                        return {
                            "subject": subject,
                            "verb": f"{w.lower()} {verb_word}",
                            "relation": _normalize_verb_to_relation(verb_word),
                            "object": rest,
                            "passive": False,
                            "auxiliary": w.lower(),
                        }

    # ─── Strategy 2: Content verb detection by morphology ───
    # "Valdoria exports coffee" -> exports(Valdoria, coffee)
    for i, w in enumerate(words):
        if _looks_like_verb(w, i, words):
            subject = " ".join(words[:i])
            verb_word = w.lower()
            obj = " ".join(words[i + 1:])

            # Handle verb + preposition combos: "flows through" -> "flows_through"
            if obj:
                obj_words = obj.split()
                if obj_words and obj_words[0].lower() in PREPOSITIONS:
                    prep = obj_words[0].lower()
                    verb_word = f"{verb_word}_{prep}"
                    obj = " ".join(obj_words[1:])

            if subject and obj:
                return {
                    "subject": subject,
                    "verb": w.lower(),
                    "relation": _normalize_verb_to_relation(verb_word),
                    "object": obj,
                    "passive": False,
                    "auxiliary": None,
                }

    return None


def extract_multiple_svo(text: str) -> List[dict]:
    """
    Extract multiple SVO triples from compound sentences.

    "Valdoria exports coffee and silver" -> two triples
    "X exports A and imports B" -> two triples
    """
    results = []

    # First try the whole sentence
    svo = extract_svo(text)
    if not svo:
        return results

    # Check if the object contains "and" (compound object)
    obj = svo["object"]
    if " and " in obj:
        parts = [p.strip() for p in obj.split(" and ")]
        for part in parts:
            if part:
                results.append({
                    **svo,
                    "object": part,
                })
    else:
        results.append(svo)

    return results
