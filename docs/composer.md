# Response Composer (`loom/composer.py`)

Generates fluid natural language responses from Loom's knowledge graph.
Pure symbolic — no ML, no embeddings.

## Public API

### `gather_facts(loom, concept, depth=2)`

Collects everything Loom knows about a concept:

```python
{
    "concept": "elephant",
    "direct": {"is": ["mammal"], "has": ["trunk", "tusks"]},
    "inherited": {"has": ["fur"]},  # from mammal
    "reverse": {},                   # things that reference elephant
    "parents": ["mammal"],
    "children": [],
    "confidence": {("is", "mammal"): "high"},
    "_loom": <loom ref>,             # used by composer for style access
}
```

Tries singular/plural variants via `_resolve_concept()` if the exact concept
isn't found in the knowledge graph.

### `trace_reasoning(loom, subject, relation, obj, max_depth=4)`

Follows multi-hop inference chains. If the fact isn't direct, walks up
category inheritance to find the source:

```python
[
    {"fact": "dogs is mammal", "source": "user"},
    {"fact": "mammal has fur", "source": "user"},
    {"fact": "dogs has fur", "source": "inheritance", "via": "mammal"},
]
```

### `compose_response(loom, question_type, concept, ...)`

Generates a fluid paragraph. `question_type` routes to the appropriate composer:

| Question type | Composer | Handles |
|--------------|----------|---------|
| `what_is` | `_compose_what_is` | "what is X?" |
| `can` | `_compose_can` | "can X do Y?" |
| `why` | `_compose_why` | "why does X Y?" + reasoning chain |
| `where` | `_compose_where` | "where is X found?" |
| `has` | `_compose_has` | "what does X have?" |
| `describe` | `_compose_describe` | "tell me about X" |
| `general` | `_compose_general` | any relation lookup |

### `acknowledge_fact(subject, relation, obj, original_text)`

Varied acknowledgments for learned facts (replaces "Got it, X Y Z"):

- "Noted — rain causes flooding."
- "I'll remember that: dogs are mammals."
- "I see, birds can fly."
- "Understood. Volcanoes can erupt."

Template selection uses deterministic hashing based on content, so the same
fact always gets the same acknowledgment style but different facts vary.

## Template Variation

All composers use hash-based deterministic selection from template pools.
Example for describe openers:

```python
openers = [
    f"{S} is {cats}.",
    f"{S} is classified as {cats}.",
    f"{S} is a kind of {cats}.",
    f"{S} falls under {cats}.",
]
labels = ["is", "is_classified_as", "is_a_kind_of", "falls_under"]
sentences.append(_pick_template(loom, seed, openers, labels))
```

`_pick_template` factors in feedback scores from `StyleLearner`:
- Positive feedback boosts the template's selection priority
- Negative feedback demotes it
- If no feedback exists, falls back to hash-based deterministic choice

## Why symbolic?

No ML. Every sentence is constructible and explainable. The hash seeding
gives natural-feeling variety without randomness — the same concept always
gets the same response style, but different concepts vary organically.
