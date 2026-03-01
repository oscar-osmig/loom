"""
Discourse pattern methods for the Parser class.
Handles discourse patterns and learning from conversation.
"""

from ..discourse import find_discourse_markers


def _check_discourse_patterns(parser, t: str) -> str | None:
    """
    Handle natural speech patterns using discourse markers.
    Humans use words like 'also', 'because', 'similarly' to signal relationships.
    """
    # Skip questions - they should be handled by query methods
    question_words = ["what", "where", "who", "when", "why", "how", "can", "does", "do", "is", "are"]
    first_word = t.split()[0] if t.split() else ""
    if first_word in question_words:
        return None

    markers = find_discourse_markers(t)
    if not markers:
        return None

    for marker_info in markers:
        marker = marker_info["marker"]
        category = marker_info["category"]
        pos = marker_info["start"]

        before = t[:pos].strip()
        after = t[marker_info["end"]:].strip()

        # Clean common prefixes
        for prefix in ["and ", "but ", "well ", "oh ", "so ", "yeah "]:
            if before.startswith(prefix):
                before = before[len(prefix):]
            if after.startswith(prefix):
                after = after[len(prefix):]

        if not after:
            continue

        # Handle ADDITIVE markers (also, too, as well, in addition)
        if category == "additive":
            # "birds also have feet" -> birds has feet
            # "cats can also climb" -> cats can climb
            # "they can also do tricks" -> [last_subject] can do tricks

            # Get subject from before the marker
            subj = before.strip()
            rest = after.strip()

            # Clean subject
            for suffix in [" also", " too", " as well", " can", " could"]:
                if subj.endswith(suffix):
                    subj = subj[:-len(suffix)].strip()
            for prefix in ["the ", "a ", "an "]:
                if subj.startswith(prefix):
                    subj = subj[len(prefix):]

            # Handle "can also do X" pattern
            if rest.startswith("do "):
                obj = rest[3:].strip()  # Remove "do "
                if subj and obj:
                    parser.loom.add_fact(subj, "can", obj)
                    parser.last_subject = subj
                    return f"Got it, {subj} can {obj}."

            # Find the verb in rest and extract relation + object
            verbs_map = {
                "have": "has", "has": "has", "had": "has",
                "can": "can", "could": "can",
                "eat": "eats", "eats": "eats",
                "like": "likes", "likes": "likes",
                "need": "needs", "needs": "needs",
                "is": "is", "are": "is",
            }

            # Action verbs that mean "can [verb]"
            action_verbs = ["see", "climb", "jump", "swim", "fly", "run", "walk", "talk"]

            for verb_d, relation in verbs_map.items():
                if rest.startswith(f"{verb_d} ") or rest == verb_d:
                    obj = rest[len(verb_d):].strip() if rest.startswith(f"{verb_d} ") else ""
                    if not obj:
                        obj = verb_d
                    if subj and obj:
                        parser.loom.add_fact(subj, relation, obj)
                        parser.last_subject = subj
                        return f"Got it, {subj} {relation} {obj}."
                    break

            # Check for action verbs
            for verb_a in action_verbs:
                if rest.startswith(verb_a):
                    obj = rest
                    if subj:
                        parser.loom.add_fact(subj, "can", obj)
                        parser.last_subject = subj
                        return f"Got it, {subj} can {obj}."
                    break

        # Handle CAUSAL markers (because, so, therefore)
        elif category == "causal":
            if marker in ["because", "since", "due to", "owing to"]:
                # "X because Y" -> Y causes X
                # Clean "of" from "because of"
                cause = after.strip()
                if cause.startswith("of "):
                    cause = cause[3:].strip()
                effect = before.strip()
                # Clean verb from effect
                for v in [" happens", " occurs", " is", " are"]:
                    if effect.endswith(v):
                        effect = effect[:-len(v)].strip()
                if cause and effect:
                    parser.loom.add_fact(cause, "causes", effect)
                    return f"I see, {cause} causes {effect}."
            elif marker in ["so", "therefore", "thus", "hence", "as a result"]:
                # "X so Y" -> X causes Y
                if before and after:
                    parser.loom.add_fact(before, "causes", after)
                    return f"I understand, {before} leads to {after}."

        # Handle SIMILARITY markers (like, similarly, same as)
        elif category == "similarity":
            if before and after:
                # Clean up
                for prefix in ["the ", "a ", "an "]:
                    if before.startswith(prefix):
                        before = before[len(prefix):]
                    if after.startswith(prefix):
                        after = after[len(prefix):]
                parser.loom.add_fact(before, "is_like", after)
                parser.loom.copy_properties(before, after)
                parser.loom.copy_properties(after, before)
                return f"Got it, {before} is similar to {after}."

        # Handle CONTRASTIVE markers (but, however, unlike)
        elif category == "contrastive":
            if marker in ["unlike", "different from", "not like"]:
                if before and after:
                    parser.loom.add_fact(before, "differs_from", after)
                    return f"Noted, {before} is different from {after}."

        # Handle EXAMPLE markers (for example, such as)
        elif category == "example":
            if before and after:
                # "mammals such as dogs" -> dogs is mammals
                parser.loom.add_fact(after, "is", before)
                return f"Got it, {after} is an example of {before}."

    return None


def _learn_from_conversation(parser, t: str) -> str | None:
    """
    Fallback: Try to extract any knowledge from natural conversation.
    Uses flexible pattern matching to learn from how people naturally talk.
    Based on Hebbian learning: concepts mentioned together form connections.
    """
    # NEVER store questions as facts
    if parser._is_question(t):
        return None

    # Try to find any subject-verb-object pattern
    words = t.split()
    if len(words) < 3:
        return None

    # Common conversational verbs to look for
    verbs = [
        "is", "are", "was", "were", "has", "have", "had",
        "likes", "like", "wants", "want", "needs", "need",
        "eats", "eat", "lives", "live", "uses", "use",
        "makes", "make", "does", "do", "can", "will",
        "loves", "love", "hates", "hate", "knows", "know"
    ]

    for i, word in enumerate(words):
        if word in verbs and i > 0:
            subj = " ".join(words[:i])
            obj = " ".join(words[i+1:])

            if subj and obj:
                # Map verb to relation
                relation = word
                if word in ["is", "are", "was", "were"]:
                    relation = "is"
                elif word in ["has", "have", "had"]:
                    relation = "has"
                elif word in ["likes", "like"]:
                    relation = "likes"
                elif word in ["wants", "want"]:
                    relation = "wants"
                elif word in ["needs", "need"]:
                    relation = "needs"
                elif word in ["eats", "eat"]:
                    relation = "eats"
                elif word in ["lives", "live"]:
                    relation = "lives_in"
                elif word in ["uses", "use"]:
                    relation = "uses"
                elif word in ["makes", "make"]:
                    relation = "causes"
                elif word in ["loves", "love"]:
                    relation = "loves"
                elif word in ["hates", "hate"]:
                    relation = "hates"
                elif word in ["knows", "know"]:
                    relation = "knows"

                # Clean up subject - remove discourse markers and articles
                for prefix in ["the ", "a ", "an ", "i think ", "i know ", "did you know "]:
                    if subj.lower().startswith(prefix):
                        subj = subj[len(prefix):]
                for suffix in [" also", " too", " as well"]:
                    if subj.lower().endswith(suffix):
                        subj = subj[:-len(suffix)].strip()

                if subj and obj:
                    parser.loom.add_fact(subj, relation, obj)
                    return f"Interesting, I'll remember that about {subj}."

    return None
