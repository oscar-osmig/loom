"""
Discourse pattern methods for the Parser class.
Handles discourse patterns and learning from conversation.

Enhanced with:
- Implicit subject continuation (". Very X." -> subject is X)
- List learning ("X, Y, and Z are W" -> multiple relations)
- Better pronoun resolution
- Context-aware relation extraction
"""

from ..discourse import find_discourse_markers


def _check_implicit_continuation(parser, t: str) -> str | None:
    """
    Handle implicit subject continuation.
    When a sentence doesn't have an explicit subject, use the last mentioned entity.

    Examples:
    - "Very protective." -> [last_subject] is protective
    - "Can swim fast." -> [last_subject] can swim_fast
    - "Also eats fish." -> [last_subject] eats fish
    """
    words = t.split()
    if not words:
        return None

    first_word = words[0].lower()

    # Skip if starts with a typical subject indicator
    subject_starters = ["the", "a", "an", "this", "that", "these", "those", "my", "your", "his", "her", "its", "our", "their"]
    if first_word in subject_starters:
        return None

    # Skip if it's a question
    if parser._is_question(t):
        return None

    # Check for implicit continuation patterns
    last_subj = getattr(parser, 'last_subject', None)
    if not last_subj:
        # Try to get from context
        if hasattr(parser, 'loom') and hasattr(parser.loom, 'context'):
            ctx = parser.loom.context.get_salient_entities(1)
            if ctx:
                last_subj = ctx[0][0]  # Extract entity name from (name, salience) tuple

    if not last_subj:
        return None

    # Pattern: "Very X." or "Quite X." -> last_subject is X
    if first_word in ["very", "quite", "really", "extremely", "incredibly"]:
        if len(words) >= 2:
            property_val = "_".join(words[1:]).rstrip(".")
            parser.loom.add_fact(last_subj, "is", property_val)
            return f"Got it, {last_subj} is {property_val.replace('_', ' ')}."

    # Pattern: "Can X." -> last_subject can X
    if first_word == "can" and len(words) >= 2:
        ability = "_".join(words[1:]).rstrip(".")
        parser.loom.add_fact(last_subj, "can", ability)
        return f"Got it, {last_subj} can {ability.replace('_', ' ')}."

    # Pattern: "Also X." -> last_subject [relation] X
    if first_word == "also" and len(words) >= 2:
        rest = " ".join(words[1:])
        # Try to parse the rest as a relation
        for verb, rel in [("has", "has"), ("have", "has"), ("eats", "eats"),
                          ("eat", "eats"), ("is", "is"), ("are", "is"),
                          ("can", "can"), ("lives", "lives_in"), ("needs", "needs")]:
            if rest.lower().startswith(f"{verb} "):
                obj = rest[len(verb)+1:].strip().rstrip(".")
                parser.loom.add_fact(last_subj, rel, obj)
                return f"Got it, {last_subj} {rel} {obj}."

    return None


def _check_list_learning(parser, t: str) -> str | None:
    """
    Handle list patterns that create multiple relations.

    Examples:
    - "Dogs, cats, and lions are mammals" -> dogs is mammals, cats is mammals, lions is mammals
    - "Fish need water, oxygen, and food" -> fish needs water, fish needs oxygen, fish needs food
    """
    # Skip questions
    if parser._is_question(t):
        return None

    # Pattern: "X, Y, and Z are/is W"
    import re

    # Match "A, B, and C are/is X" pattern - more robust version
    # Split on ", " and "and" to extract list items
    list_subject_pattern = r'^([^,]+),\s*([^,]+),?\s+and\s+(\w+)\s+(are|is)\s+(.+)$'
    match = re.match(list_subject_pattern, t, re.IGNORECASE)

    if match:
        items = [match.group(1).strip(), match.group(2).strip(), match.group(3).strip()]
        relation = "is"
        obj = match.group(5).strip().rstrip(".")

        # Clean articles from items
        clean_items = []
        for item in items:
            for prefix in ["the ", "a ", "an "]:
                if item.lower().startswith(prefix):
                    item = item[len(prefix):]
            clean_items.append(item)

        for item in clean_items:
            parser.loom.add_fact(item, relation, obj)

        parser.last_subject = clean_items[-1]  # Last item becomes last_subject
        return f"Got it, {', '.join(clean_items)} are all {obj}."

    # Pattern: "X need/needs/have/has A, B, and C"
    list_object_pattern = r'^(.+?)\s+(need|needs|have|has|eat|eats|can)\s+(.+?),\s*(.+?),?\s+and\s+(.+)$'
    match = re.match(list_object_pattern, t, re.IGNORECASE)

    if match:
        subject = match.group(1).strip()
        verb = match.group(2).lower()
        items = [match.group(3).strip(), match.group(4).strip(), match.group(5).strip().rstrip(".")]

        # Map verb to relation
        verb_map = {"need": "needs", "needs": "needs", "have": "has", "has": "has",
                    "eat": "eats", "eats": "eats", "can": "can"}
        relation = verb_map.get(verb, verb)

        # Clean subject
        for prefix in ["the ", "a ", "an "]:
            if subject.lower().startswith(prefix):
                subject = subject[len(prefix):]

        for item in items:
            parser.loom.add_fact(subject, relation, item)

        parser.last_subject = subject
        return f"Got it, {subject} {relation} {', '.join(items)}."

    return None


def _check_pronoun_reference(parser, t: str) -> str | None:
    """
    Handle pronoun references to continue talking about the same subject.

    Examples:
    - "They are very fast." -> [last_subject] is very_fast
    - "It can fly." -> [last_subject] can fly
    """
    words = t.split()
    if not words:
        return None

    first_word = words[0].lower()

    # Check for pronouns
    pronouns = ["they", "it", "he", "she", "these", "those"]
    if first_word not in pronouns:
        return None

    # Get last subject
    last_subj = getattr(parser, 'last_subject', None)
    if not last_subj:
        if hasattr(parser, 'loom') and hasattr(parser.loom, 'context'):
            ctx = parser.loom.context.get_salient_entities(1)
            if ctx:
                last_subj = ctx[0][0]  # Extract entity name from (name, salience) tuple

    if not last_subj:
        return None

    # Replace pronoun with last subject and re-parse
    rest = " ".join(words[1:])
    new_text = f"{last_subj} {rest}"

    # Don't recurse infinitely
    if getattr(parser, '_in_pronoun_resolution', False):
        return None

    parser._in_pronoun_resolution = True
    try:
        # Try to parse the modified text
        result = parser.parse(new_text)
        if result and not result.startswith("I don't"):
            return result
    finally:
        parser._in_pronoun_resolution = False

    return None


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
                    relation = "makes"
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


def _check_first_person_statement(parser, t: str) -> str | None:
    """
    Handle first-person statements about the user.

    Examples:
    - "I live in New York" -> (user, lives_in, new_york)
    - "I like cats" -> (user, likes, cats)
    - "My name is John" -> (user, name_is, john)
    - "I have a dog" -> (user, has, dog)
    """
    import re

    text = t.strip()
    text_lower = text.lower()

    # Skip questions
    if parser._is_question(text):
        return None

    # Pattern: "My name is X"
    match = re.match(r"my\s+name\s+is\s+(.+)", text_lower)
    if match:
        name = match.group(1).strip().rstrip(".")
        parser.loom.add_fact("user", "name_is", name)
        parser.loom.context.add_entity("user", role='subject')
        return f"Nice to meet you, {name.title()}!"

    # Pattern: "I am X" / "I'm X"
    match = re.match(r"i(?:'m|\s+am)\s+(.+)", text_lower)
    if match:
        rest = match.group(1).strip().rstrip(".")

        # "I am a teacher" -> user is teacher
        rest_clean = re.sub(r"^an?\s+", "", rest)

        # Check for location: "I am in New York"
        loc_match = re.match(r"(?:in|at|from)\s+(.+)", rest_clean)
        if loc_match:
            location = loc_match.group(1).strip().replace(" ", "_")
            parser.loom.add_fact("user", "located_in", location)
            return f"Got it, you're in {loc_match.group(1).strip()}."

        # Otherwise it's an attribute
        parser.loom.add_fact("user", "is", rest_clean.replace(" ", "_"))
        return f"Got it, you are {rest_clean}."

    # Pattern: "I live in X"
    match = re.match(r"i\s+live\s+(?:in|at)\s+(.+)", text_lower)
    if match:
        location = match.group(1).strip().rstrip(".").replace(" ", "_")
        parser.loom.add_fact("user", "lives_in", location)
        return f"Got it, you live in {match.group(1).strip().rstrip('.')}."

    # Pattern: "I have X"
    match = re.match(r"i\s+have\s+(.+)", text_lower)
    if match:
        thing = match.group(1).strip().rstrip(".")
        # Remove articles
        thing = re.sub(r"^an?\s+", "", thing).replace(" ", "_")
        parser.loom.add_fact("user", "has", thing)
        return f"Got it, you have {match.group(1).strip().rstrip('.')}."

    # Pattern: "I like/love/hate X"
    match = re.match(r"i\s+(like|love|hate|enjoy|prefer)\s+(.+)", text_lower)
    if match:
        verb = match.group(1)
        thing = match.group(2).strip().rstrip(".").replace(" ", "_")
        relation = verb + "s"  # like -> likes
        parser.loom.add_fact("user", relation, thing)

        responses = {
            "like": f"Good to know you like {match.group(2).strip().rstrip('.')}!",
            "love": f"That's great that you love {match.group(2).strip().rstrip('.')}!",
            "hate": f"Noted, you don't like {match.group(2).strip().rstrip('.')}.",
            "enjoy": f"Nice, you enjoy {match.group(2).strip().rstrip('.')}!",
            "prefer": f"Got it, you prefer {match.group(2).strip().rstrip('.')}.",
        }
        return responses.get(verb, "Got it.")

    # Pattern: "I want/need X"
    match = re.match(r"i\s+(want|need)\s+(.+)", text_lower)
    if match:
        verb = match.group(1)
        thing = match.group(2).strip().rstrip(".")
        # Remove articles and "to"
        thing = re.sub(r"^(?:to|an?)\s+", "", thing).replace(" ", "_")
        relation = verb + "s"
        parser.loom.add_fact("user", relation, thing)
        return f"Got it, you {verb} {match.group(2).strip().rstrip('.')}."

    # Pattern: "I can X" / "I know how to X"
    match = re.match(r"i\s+(?:can|know\s+how\s+to)\s+(.+)", text_lower)
    if match:
        ability = match.group(1).strip().rstrip(".").replace(" ", "_")
        parser.loom.add_fact("user", "can", ability)
        return f"Great, you can {match.group(1).strip().rstrip('.')}!"

    # Pattern: "I think X" / "I believe X" (opinion)
    match = re.match(r"i\s+(think|believe|feel)\s+(?:that\s+)?(.+)", text_lower)
    if match:
        opinion = match.group(2).strip().rstrip(".")
        parser.loom.add_fact("user", "believes", opinion.replace(" ", "_"))
        # Try to also parse the statement as a fact
        return f"I see, that's your view on it."

    # Pattern: "I work at/for X"
    match = re.match(r"i\s+work\s+(?:at|for)\s+(.+)", text_lower)
    if match:
        workplace = match.group(1).strip().rstrip(".").replace(" ", "_")
        parser.loom.add_fact("user", "works_at", workplace)
        return f"Got it, you work at {match.group(1).strip().rstrip('.')}."

    return None


def _check_chit_chat(parser, t: str) -> str | None:
    """
    Handle conversational chit-chat that doesn't teach facts.

    Examples:
    - "Hello" -> friendly response
    - "How are you?" -> status response
    - "Thank you" -> acknowledgment
    """
    text_lower = t.lower().strip()

    # Greetings
    greetings = ["hello", "hi", "hey", "greetings", "good morning",
                 "good afternoon", "good evening", "howdy"]
    for greeting in greetings:
        if text_lower.startswith(greeting):
            return f"Hello! How can I help you learn something today?"

    # How are you?
    if "how are you" in text_lower or "how's it going" in text_lower:
        return "I'm doing well, ready to learn! What would you like to teach me?"

    # Thanks
    if text_lower in ["thanks", "thank you", "thx", "ty"]:
        return "You're welcome!"

    # Goodbye
    if text_lower in ["bye", "goodbye", "see you", "later", "cya"]:
        return "Goodbye! Come back when you have more to teach me."

    # Compliments
    if any(w in text_lower for w in ["good job", "well done", "nice", "great"]):
        return "Thank you! I'm always learning."

    # Apologies
    if text_lower.startswith(("sorry", "my bad", "oops")):
        return "No problem! What would you like to correct?"

    return None
