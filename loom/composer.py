"""
Response Composer — generates fluid natural language from Loom's knowledge graph.

Replaces template-string responses with multi-fact, multi-hop narrative paragraphs.
Pure symbolic — no ML, no embeddings.

Pipeline:
  1. gather_facts(concept) → all known facts about a topic
  2. trace_reasoning(subject, relation, object) → chain of premises
  3. compose_response(question, facts) → natural paragraph
"""

import hashlib
from typing import TYPE_CHECKING, Optional
from .normalizer import normalize

if TYPE_CHECKING:
    from .brain import Loom


def _pick_template(loom: Optional["Loom"], seed: int, templates: list, labels: list = None):
    """
    Pick a template from a list, factoring in style feedback scores.
    Templates with negative feedback are demoted, positive are boosted.
    """
    if not templates:
        return ""
    if not loom or not hasattr(loom, "style_learner") or not labels:
        return templates[seed % len(templates)]

    # Score each template by its feedback
    try:
        scored = []
        for i, tmpl in enumerate(templates):
            label = labels[i] if i < len(labels) else None
            base_score = seed % 100 / 100.0  # Deterministic baseline from seed
            feedback = loom.style_learner.get_template_score(label) if label else 0.0
            # Feedback in [-1, +1] — shift preference but don't override determinism entirely
            adjusted = base_score + feedback * 0.5
            scored.append((adjusted, i, tmpl))
        scored.sort(reverse=True)
        # Pick highest-scored, but use seed-based variance for ties
        return scored[0][2]
    except Exception:
        return templates[seed % len(templates)]

# ── Relation groupings for natural ordering ───────────────────────────

IDENTITY_RELS = {"is", "is_a", "type_of", "kind_of"}
ABILITY_RELS = {"can", "capable_of"}
INABILITY_RELS = {"cannot", "unable_to"}
PROPERTY_RELS = {"has", "has_part", "body_parts", "color"}
LOCATION_RELS = {"lives_in", "found_in", "located_in", "habitat"}
BEHAVIOR_RELS = {"eats", "hunts", "needs", "produces", "makes"}
CAUSAL_RELS = {"causes", "leads_to", "results_in"}
SIMILARITY_RELS = {"similar_to", "looks_like", "related_through"}

# Order sections appear in a composed response
SECTION_ORDER = [
    ("identity", IDENTITY_RELS),
    ("properties", PROPERTY_RELS),
    ("abilities", ABILITY_RELS),
    ("inabilities", INABILITY_RELS),
    ("behavior", BEHAVIOR_RELS),
    ("location", LOCATION_RELS),
    ("causation", CAUSAL_RELS),
    ("similarity", SIMILARITY_RELS),
]

# ── Confidence phrasing ───────────────────────────────────────────────

CONFIDENCE_HEDGE = {
    "high": "",
    "medium": "likely ",
    "low": "possibly ",
}

# ── Connective templates ─────────────────────────────────────────────

IDENTITY_TEMPLATES = [
    "{subject} is {obj}.",
    "{subject} is a type of {obj}.",
]

PROPERTY_INTRO = [
    "{subject} has {props}.",
    "It has {props}.",
]

ABILITY_INTRO = [
    "{subject} can {abilities}.",
    "It can {abilities}.",
]

LOCATION_INTRO = [
    "{subject} is found in {locs}.",
    "It lives in {locs}.",
]


# ══════════════════════════════════════════════════════════════════════
#  Fact Gatherer
# ══════════════════════════════════════════════════════════════════════

def _resolve_concept(knowledge: dict, concept: str) -> str:
    """Try to find the concept in knowledge, trying singular/plural variants."""
    c = normalize(concept)
    if c in knowledge:
        return c
    # Try adding/removing trailing 's'
    if c.endswith("s") and c[:-1] in knowledge:
        return c[:-1]
    if not c.endswith("s") and (c + "s") in knowledge:
        return c + "s"
    # Try adding/removing 'es'
    if c.endswith("es") and c[:-2] in knowledge:
        return c[:-2]
    # Try removing 'ies' → 'y'
    if c.endswith("ies") and (c[:-3] + "y") in knowledge:
        return c[:-3] + "y"
    return c


def gather_facts(loom: "Loom", concept: str, depth: int = 2) -> dict:
    """
    Collect everything Loom knows about a concept.

    Returns:
        {
            "concept": normalized name,
            "direct": {relation: [objects]},        # facts where concept is subject
            "inherited": {relation: [objects]},      # facts from parent categories
            "reverse": {relation: [subjects]},       # facts where concept is object
            "parents": [list of parent categories],
            "children": [list of child instances],
            "confidence": {(relation, object): "high"/"medium"/"low"},
        }
    """
    knowledge = loom.knowledge
    c = _resolve_concept(knowledge, concept)
    result = {
        "concept": c,
        "direct": {},
        "inherited": {},
        "reverse": {},
        "parents": [],
        "children": [],
        "confidence": {},
        "_loom": loom,  # reference for composer to access style_learner
    }

    # Direct facts (concept as subject)
    rels = knowledge.get(c, {})
    for rel, objects in rels.items():
        result["direct"][rel] = list(objects)

    # Track parents for inheritance
    parents = set()
    for rel in IDENTITY_RELS:
        for obj in rels.get(rel, []):
            parents.add(obj)
    result["parents"] = list(parents)

    # Inherited facts from parents (up to depth levels)
    visited = {c}
    frontier = list(parents)
    for _ in range(depth):
        next_frontier = []
        for parent in frontier:
            if parent in visited:
                continue
            visited.add(parent)
            parent_rels = knowledge.get(parent, {})
            for rel, objects in parent_rels.items():
                if rel in IDENTITY_RELS:
                    # Grandparents — add to next frontier
                    for obj in objects:
                        if obj not in visited:
                            next_frontier.append(obj)
                    continue
                # Inherit non-identity relations
                if rel not in result["direct"]:
                    existing = result["inherited"].get(rel, [])
                    for obj in objects:
                        if obj not in existing and obj not in result["direct"].get(rel, []):
                            existing.append(obj)
                            result["confidence"][(rel, obj)] = "low"
                    if existing:
                        result["inherited"][rel] = existing
        frontier = next_frontier

    # Reverse facts (concept as object) — find children, users, etc.
    for entity, entity_rels in knowledge.items():
        if entity == c or entity == "self":
            continue
        for rel, objects in entity_rels.items():
            if c in objects:
                if rel in IDENTITY_RELS:
                    result["children"].append(entity)
                else:
                    rev_list = result["reverse"].get(rel, [])
                    if entity not in rev_list:
                        rev_list.append(entity)
                    result["reverse"][rel] = rev_list

    # Get confidence from storage for direct facts
    try:
        for doc in loom.storage.db.facts.find(
            {"instance": loom.storage.instance_name, "subject": c},
            {"relation": 1, "object": 1, "properties.confidence": 1}
        ):
            rel = doc.get("relation", "")
            obj = doc.get("object", "")
            conf = doc.get("properties", {}).get("confidence", "high")
            result["confidence"][(rel, obj)] = conf
    except Exception:
        pass

    return result


# ══════════════════════════════════════════════════════════════════════
#  Reasoning Chain Tracer
# ══════════════════════════════════════════════════════════════════════

def trace_reasoning(loom: "Loom", subject: str, relation: str, obj: str,
                    max_depth: int = 4) -> list:
    """
    Trace why a fact is true by following inference chains.

    Returns list of reasoning steps:
        [
            {"fact": "dogs is mammal", "source": "user"},
            {"fact": "mammal has fur", "source": "user"},
            {"fact": "dogs has fur", "source": "inheritance", "via": "mammal"},
        ]
    """
    knowledge = loom.knowledge
    s = _resolve_concept(knowledge, subject)
    r = relation.lower().strip()
    o = normalize(obj)

    # Direct fact — no chain needed
    direct = knowledge.get(s, {}).get(r, [])
    if o in direct:
        source = _get_fact_source(loom, s, r, o)
        return [{"fact": f"{_pretty(s)} {r} {_pretty(o)}", "source": source}]

    # Try to find via category inheritance
    chain = []
    parents = []
    for id_rel in IDENTITY_RELS:
        parents.extend(knowledge.get(s, {}).get(id_rel, []))

    visited = {s}
    frontier = [(p, [s]) for p in parents]

    for _ in range(max_depth):
        next_frontier = []
        for node, path in frontier:
            if node in visited:
                continue
            visited.add(node)

            node_rels = knowledge.get(node, {})
            if o in node_rels.get(r, []):
                # Found it — build the chain
                for i, step in enumerate(path):
                    next_step = path[i + 1] if i + 1 < len(path) else node
                    chain.append({
                        "fact": f"{_pretty(step)} is {_pretty(next_step)}",
                        "source": _get_fact_source(loom, step, "is", next_step),
                    })
                chain.append({
                    "fact": f"{_pretty(node)} {r} {_pretty(o)}",
                    "source": _get_fact_source(loom, node, r, o),
                })
                chain.append({
                    "fact": f"{_pretty(s)} {r} {_pretty(o)}",
                    "source": "inheritance",
                    "via": _pretty(node),
                })
                return chain

            # Keep searching up
            for id_rel in IDENTITY_RELS:
                for grandparent in node_rels.get(id_rel, []):
                    if grandparent not in visited:
                        next_frontier.append((grandparent, path + [node]))
        frontier = next_frontier

    return []  # Could not trace


# ══════════════════════════════════════════════════════════════════════
#  Response Composer
# ══════════════════════════════════════════════════════════════════════

def compose_response(loom: "Loom", question_type: str, concept: str,
                     relation: str = None, target: str = None,
                     facts: dict = None) -> Optional[str]:
    """
    Generate a fluid natural language response from gathered facts.

    Args:
        loom: The Loom instance
        question_type: "what_is", "can", "why", "where", "has", "describe", "general"
        concept: The concept being asked about
        relation: Specific relation asked (optional)
        target: Specific target asked about (optional)
        facts: Pre-gathered facts (optional, will gather if not provided)

    Returns:
        Natural language string, or None if nothing to say.
    """
    if facts is None:
        facts = gather_facts(loom, concept)

    direct = facts["direct"]
    inherited = facts["inherited"]
    confidence = facts["confidence"]
    subj = _pretty(facts["concept"])

    if not direct and not inherited:
        return None

    # Route to specific composer based on question type
    if question_type == "what_is":
        return _compose_what_is(subj, facts)
    elif question_type == "can":
        return _compose_can(subj, relation, target, facts)
    elif question_type == "why":
        return _compose_why(loom, subj, facts, relation, target)
    elif question_type == "where":
        return _compose_where(subj, facts)
    elif question_type == "has":
        return _compose_has(subj, facts)
    elif question_type == "describe":
        return _compose_describe(subj, facts)
    else:
        return _compose_general(subj, relation, facts)


# ── Specific composers ────────────────────────────────────────────────

def _compose_what_is(subj: str, facts: dict) -> str:
    """Answer 'what is X?' with identity + supporting context."""
    direct = facts["direct"]
    inherited = facts["inherited"]
    S = subj.title()

    # Identity
    categories = []
    for rel in IDENTITY_RELS:
        categories.extend(direct.get(rel, []))
    categories = [c for c in categories if _pretty(c).lower() != subj.lower()]

    sentences = []

    if categories:
        cats = _format_list([_pretty(c) for c in categories[:4]])
        sentences.append(f"{S} is {cats}.")

    # Supporting details (pick 1-2 to keep it concise)
    props = _collect_from_rels(direct, PROPERTY_RELS, limit=3)
    abilities = _collect_from_rels(direct, ABILITY_RELS, limit=3)
    locs = _collect_from_rels(direct, LOCATION_RELS, limit=2)

    if props and abilities:
        sentences.append(f"It has {_format_list(props)} and can {_format_list(abilities)}.")
    elif props:
        sentences.append(f"It has {_format_list(props)}.")
    elif abilities:
        sentences.append(f"It can {_format_list(abilities)}.")

    if locs:
        sentences.append(f"Found in {_format_list(locs)}.")

    # Inherited knowledge as a bonus
    if not props and not abilities:
        inherited_props = _collect_from_rels(inherited, PROPERTY_RELS, limit=3)
        if inherited_props:
            parent = _pretty(facts["parents"][0]) if facts["parents"] else "its category"
            sentences.append(f"As a {parent}, it likely has {_format_list(inherited_props)}.")

    if not sentences:
        return None

    return " ".join(sentences)


def _compose_can(subj: str, relation: str, target: str, facts: dict) -> str:
    """Answer 'can X do Y?' with yes/no + reasoning."""
    direct = facts["direct"]
    inherited = facts["inherited"]

    target_norm = normalize(target) if target else ""

    # Check direct abilities
    abilities = []
    for rel in ABILITY_RELS:
        abilities.extend(direct.get(rel, []))

    inabilities = []
    for rel in INABILITY_RELS:
        inabilities.extend(direct.get(rel, []))

    # Check for the specific target
    if target_norm:
        for ina in inabilities:
            if target_norm in ina or ina.startswith(target_norm):
                return f"No, {subj} cannot {_pretty(ina)}."

        for ab in abilities:
            if target_norm in ab or ab.startswith(target_norm):
                # Enrich with related abilities
                other = [_pretty(a) for a in abilities if a != ab][:2]
                base = f"Yes, {subj} can {_pretty(ab)}"
                if other:
                    base += f" — and also {_format_list(other)}"
                return base + "."

        # Check inherited
        inherited_abilities = []
        for rel in ABILITY_RELS:
            inherited_abilities.extend(inherited.get(rel, []))
        for ab in inherited_abilities:
            if target_norm in ab or ab.startswith(target_norm):
                parent = facts["parents"][0] if facts["parents"] else "its category"
                return f"Likely yes — as {_pretty(parent)}, {subj} can probably {_pretty(ab)}."

    # No specific target — list abilities
    if abilities:
        return f"{subj.title()} can {_format_list([_pretty(a) for a in abilities[:5]])}."
    return None


def _compose_why(loom: "Loom", subj: str, facts: dict,
                 relation: str = None, target: str = None) -> str:
    """Answer 'why' questions by tracing reasoning chains."""
    if relation and target:
        chain = trace_reasoning(loom, facts["concept"], relation, target)
        if chain:
            steps = []
            for step in chain:
                via = step.get("via", "")
                if via:
                    steps.append(f"therefore {step['fact']}")
                else:
                    steps.append(step["fact"])
            return f"Because {'; '.join(steps)}."

    # General "why" — look for causal relations
    direct = facts["direct"]
    causes = _collect_from_rels(direct, CAUSAL_RELS, limit=3)
    if causes:
        return f"{subj.title()} causes {_format_list(causes)}."

    # Try reasoning from categories
    if facts["parents"]:
        parent = _pretty(facts["parents"][0])
        return f"{subj.title()} is {parent}, which may explain its properties."

    return None


def _compose_where(subj: str, facts: dict) -> str:
    """Answer 'where' questions."""
    locs = _collect_from_rels(facts["direct"], LOCATION_RELS, limit=4)
    if not locs:
        locs = _collect_from_rels(facts["inherited"], LOCATION_RELS, limit=3)
        if locs:
            parent = _pretty(facts["parents"][0]) if facts["parents"] else "its category"
            return f"As {parent}, {subj} is likely found in {_format_list(locs)}."
    if locs:
        return f"{subj.title()} is found in {_format_list(locs)}."
    return None


def _compose_has(subj: str, facts: dict) -> str:
    """Answer 'what does X have?' questions."""
    props = _collect_from_rels(facts["direct"], PROPERTY_RELS, limit=6)
    inherited_props = _collect_from_rels(facts["inherited"], PROPERTY_RELS, limit=4)

    parts = []
    if props:
        parts.append(f"{subj.title()} has {_format_list(props)}")
    if inherited_props:
        parent = _pretty(facts["parents"][0]) if facts["parents"] else "its category"
        parts.append(f"from being {parent}, it also has {_format_list(inherited_props)}")

    if parts:
        return _join_parts(parts) + "."
    return None


def _compose_describe(subj: str, facts: dict) -> str:
    """Full description — used for 'tell me about X'. Varies format naturally."""
    direct = facts["direct"]
    inherited = facts["inherited"]
    S = subj.title()

    # Use concept hash to pick varied templates deterministically
    seed = int(hashlib.md5(subj.encode()).hexdigest()[:8], 16)

    # Collect all data
    categories = []
    for rel in IDENTITY_RELS:
        categories.extend(direct.get(rel, []))
    # Filter self-referential categories (e.g., "vehicle is vehicle")
    categories = [c for c in categories if _pretty(c).lower() != subj.lower()]

    props = _collect_from_rels(direct, PROPERTY_RELS, limit=5)
    abilities = _collect_from_rels(direct, ABILITY_RELS, limit=4)
    inabilities = _collect_from_rels(direct, INABILITY_RELS, limit=2)
    locs = _collect_from_rels(direct, LOCATION_RELS, limit=3)
    children = [_pretty(c) for c in facts["children"][:6]]
    inherited_props = _collect_from_rels(inherited, PROPERTY_RELS, limit=3)
    parent_name = _pretty(facts["parents"][0]) if facts["parents"] else ""

    # Collect behavior items with their relation name
    behavior_items = []
    for rel in BEHAVIOR_RELS:
        for item in direct.get(rel, []):
            behavior_items.append((rel, _pretty(item)))

    # Build sentences (not parts) — each is a complete thought
    sentences = []

    # Try to find the Loom instance for style-aware template selection
    _loom = facts.get("_loom")

    # ── Opening sentence: identity ──
    if categories:
        cats = _format_list([_pretty(c) for c in categories[:3]])
        openers = [
            f"{S} is {cats}.",
            f"{S} is classified as {cats}.",
            f"{S} is a kind of {cats}.",
            f"{S} falls under {cats}.",
        ]
        labels = ["is", "is_classified_as", "is_a_kind_of", "falls_under"]
        sentences.append(_pick_template(_loom, seed, openers, labels))
    elif children:
        # Category with no parents — lead with what it contains
        child_list = _format_list(children[:5])
        openers = [
            f"{S} is a broad category that includes {child_list}.",
            f"There are many types of {subj}, such as {child_list}.",
            f"Some well-known {subj}s include {child_list}.",
            f"{S} encompasses things like {child_list}.",
        ]
        labels = ["broad_category", "types_of", "well_known", "encompasses"]
        sentences.append(_pick_template(_loom, seed, openers, labels))
        children = []  # Don't repeat below

    # ── Properties ──
    if props:
        prop_list = _format_list(props)
        templates = [
            f"It has {prop_list}.",
            f"Notable features include {prop_list}.",
            f"It's characterized by {prop_list}.",
            f"Key traits: {prop_list}.",
        ]
        sentences.append(templates[(seed >> 4) % len(templates)])

    # ── Abilities ──
    if abilities:
        ab_list = _format_list(abilities)
        if inabilities:
            inab_list = _format_list(inabilities)
            sentences.append(f"It can {ab_list}, but cannot {inab_list}.")
        else:
            templates = [
                f"It can {ab_list}.",
                f"It's able to {ab_list}.",
                f"It's known to {ab_list}.",
            ]
            sentences.append(templates[(seed >> 8) % len(templates)])
    elif inabilities:
        sentences.append(f"It cannot {_format_list(inabilities)}.")

    # ── Location ──
    if locs:
        loc_list = _format_list(locs)
        templates = [
            f"It can be found in {loc_list}.",
            f"It's typically found in {loc_list}.",
            f"Its habitat includes {loc_list}.",
            f"You'll find it in {loc_list}.",
        ]
        sentences.append(templates[(seed >> 12) % len(templates)])

    # ── Behavior ──
    if behavior_items:
        rel_name, item = behavior_items[0]
        others = [i for _, i in behavior_items[1:3]]
        if others:
            all_items = _format_list([item] + others)
            sentences.append(f"It {rel_name.replace('_', ' ')}s {all_items}.")
        else:
            sentences.append(f"It {rel_name.replace('_', ' ')}s {item}.")

    # ── Children (only if not already used in opener) ──
    if children and len(sentences) >= 1:
        child_list = _format_list(children[:5])
        templates = [
            f"Examples include {child_list}.",
            f"Some types: {child_list}.",
            f"This includes {child_list}.",
        ]
        sentences.append(templates[(seed >> 16) % len(templates)])

    # ── Inherited knowledge ──
    if inherited_props and not props and parent_name:
        inh_list = _format_list(inherited_props)
        templates = [
            f"As a {parent_name}, it likely has {inh_list}.",
            f"Being a {parent_name}, it probably possesses {inh_list}.",
            f"From its {parent_name} classification, it likely has {inh_list}.",
        ]
        sentences.append(templates[(seed >> 20) % len(templates)])

    if not sentences:
        return None

    # For very sparse concepts (1 sentence), prefix with subject if missing
    if len(sentences) == 1 and not sentences[0].startswith(S):
        # Avoid redundancy like "Weather — there are many types of weather"
        if subj.lower() not in sentences[0].lower():
            sentences[0] = f"{S} — {sentences[0][0].lower()}{sentences[0][1:]}"

    return " ".join(sentences)


def _compose_general(subj: str, relation: str, facts: dict) -> str:
    """Answer a question about a specific relation."""
    direct = facts["direct"]
    inherited = facts["inherited"]

    if relation:
        r = relation.lower().strip()
        items = direct.get(r, [])
        if items:
            return f"{subj.title()} {r.replace('_', ' ')} {_format_list([_pretty(i) for i in items[:6]])}."

        # Try inherited
        items = inherited.get(r, [])
        if items:
            parent = _pretty(facts["parents"][0]) if facts["parents"] else "its category"
            return f"As {parent}, {subj} likely {r.replace('_', ' ')} {_format_list([_pretty(i) for i in items[:4]])}."

    return None


# ══════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════

def _pretty(key: str) -> str:
    """Convert internal key to readable text."""
    return key.replace("_", " ")


def _format_list(items: list) -> str:
    """Natural language list: 'a, b, and c'."""
    if not items:
        return ""
    items = [str(i) for i in items]
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + ", and " + items[-1]


def _join_parts(parts: list) -> str:
    """Join sentence parts with natural connectives."""
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]

    # First part stands alone, rest connected with semicolons or dashes
    result = parts[0]
    for i, part in enumerate(parts[1:], 1):
        # Alternate connectives for variety
        if i == 1:
            result += " — " + part
        elif i == 2:
            result += ", and " + part
        else:
            result += ". Additionally, " + part
    return result


def _collect_from_rels(source: dict, rel_set: set, limit: int = 5) -> list:
    """Collect prettified objects from a set of relations."""
    items = []
    for rel in rel_set:
        for obj in source.get(rel, []):
            p = _pretty(obj)
            if p not in items:
                items.append(p)
            if len(items) >= limit:
                return items
    return items


def _get_fact_source(loom: "Loom", subject: str, relation: str, obj: str) -> str:
    """Get the source type of a fact from storage."""
    try:
        doc = loom.storage.db.facts.find_one(
            {"instance": loom.storage.instance_name,
             "subject": subject, "relation": relation, "object": obj},
            {"properties.source_type": 1}
        )
        if doc:
            return doc.get("properties", {}).get("source_type", "user")
    except Exception:
        pass
    return "user"


# ══════════════════════════════════════════════════════════════════════
#  Statement Acknowledgment — varied responses when learning facts
# ══════════════════════════════════════════════════════════════════════

def acknowledge_fact(subject: str, relation: str, obj: str,
                     original_text: str = "") -> str:
    """
    Generate a varied, natural acknowledgment when Loom learns a new fact.
    Uses the original text to preserve details that normalization might lose.
    """
    s = _pretty(subject).strip()
    r = relation.replace("_", " ").strip()
    o = _pretty(obj).strip()
    seed = int(hashlib.md5(f"{s}{r}{o}".encode()).hexdigest()[:8], 16)

    # Use original text if it's richer than the normalized version
    original = original_text.strip().rstrip(".")
    use_original = len(original) > len(f"{s} {r} {o}") + 5

    if relation in ("is", "is_a", "type_of", "kind_of"):
        templates = [
            f"Understood — {s} is {o}.",
            f"I see, so {s} is {o}.",
            f"Noted: {s} is {o}.",
            f"Got it — {s} is {o}. I'll remember that.",
            f"Interesting, {s} is {o}.",
        ]
    elif relation in ("has", "has_part"):
        templates = [
            f"Noted — {s} has {o}.",
            f"I'll remember that {s} has {o}.",
            f"Good to know: {s} has {o}.",
            f"Recorded — {s} has {o}.",
            f"I see, {s} has {o}.",
        ]
    elif relation in ("can", "capable_of"):
        templates = [
            f"Got it — {s} can {o}.",
            f"Interesting, {s} can {o}.",
            f"Noted: {s} can {o}.",
            f"I'll remember that {s} can {o}.",
            f"So {s} can {o}. Good to know.",
        ]
    elif relation in ("cannot", "unable_to"):
        templates = [
            f"Noted — {s} cannot {o}.",
            f"I see, {s} cannot {o}.",
            f"Understood, {s} cannot {o}.",
        ]
    elif relation in ("causes", "leads_to"):
        templates = [
            f"I see — {s} causes {o}.",
            f"Noted: {s} leads to {o}.",
            f"So {s} causes {o}. That makes sense.",
            f"Understood — {s} results in {o}.",
        ]
    elif relation in ("lives_in", "found_in", "located_in"):
        templates = [
            f"Got it — {s} is found in {o}.",
            f"Noted: {s} lives in {o}.",
            f"I see, {s} is found in {o}.",
        ]
    elif relation in ("eats", "needs", "produces"):
        templates = [
            f"Noted — {s} {r} {o}.",
            f"I'll remember that {s} {r} {o}.",
            f"Good to know: {s} {r} {o}.",
        ]
    else:
        templates = [
            f"Got it — {s} {r} {o}.",
            f"Noted: {s} {r} {o}.",
            f"I'll remember that {s} {r} {o}.",
            f"Understood — {s} {r} {o}.",
            f"Interesting. {s} {r} {o}.",
        ]

    response = templates[seed % len(templates)]

    # If original text had more detail, append it
    if use_original and original.lower() != f"{s} {r} {o}".lower():
        response = response.rstrip(".")
        # Don't repeat if original is very similar
        norm_resp = response.lower().replace("—", "").replace(",", "").strip()
        norm_orig = original.lower().strip()
        if norm_orig not in norm_resp and len(original) > 15:
            response += f' ("{original}.")'
        else:
            response += "."

    return response
