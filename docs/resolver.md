# Entity Resolution & Normalization

## Overview

Before creating a new neuron, the resolver searches the knowledge graph to find if an existing neuron already represents the same concept. It implements a priority chain of 7 strategies (exact → possessive → compound → alias → contextual → partial → new) to map natural language phrases to existing entities. The normalizer converts text to internal key format, and the grammar module handles conjugation and pluralization.

## Key Concepts

**Entity Resolution**: Multi-strategy lookup to avoid duplicate neurons. A user says "the cat's eyes" → resolver finds "blue_eyes" (if the cat owns blue_eyes) and links to it instead of creating a new "cat_eyes" neuron.

**Resolution Priority**: Strategies are tried in order; the first match wins. Exact matches (normalized text exists as-is) are fastest; partial matches (suffix matching with safe prefixes) are slowest.

**Specificity Rule**: The resolver avoids merging when the user's phrase is *more specific* than the stored property. Example: "blue_eyes" exists; user says "festival of tides" → don't merge (hint is more specific).

**Normalization**: Converts natural language to internal keys by stripping articles, filler words, and handling plurals. "the rain makes the ground wet" → "rain"; "the ground is wet" → "ground_wet".

**Grammar Utilities**: Handle irregular plurals (child → children), adjective detection (avoid pluralizing "happy"), verb conjugation (is/are based on subject), and article selection (a/an).

## API / Public Interface

### resolver.py

**`resolve_to_existing_neuron(phrase: str, knowledge: dict, context: dict = None) -> Tuple[str, str]`**
- **Args**: Phrase to resolve, knowledge graph dict, optional context (with `last_subject`, `topics`)
- **Returns**: `(resolved_name, resolution_type)` where type is one of: "exact", "possessive", "compound", "alias", "context", "partial", "new"
- **Priority order**: Exact → Possessive → Compound → Alias → Contextual → Partial → New

**`resolve_with_explanation(phrase: str, knowledge: dict, context: dict = None) -> Tuple[str, str, str]`**
- **Returns**: `(resolved_name, resolution_type, explanation_text)`
- Useful for verbose output during debugging

**Internal helpers** (private):
- `_resolve_possessive(phrase, knowledge)`: Match "X's Y" patterns
- `_resolve_compound(phrase, knowledge)`: Match "X Y" where X is known
- `_find_owner_property(owner, property_hint, knowledge)`: Core lookup (searches `has`, `has_property`, `owns`, `possesses`, `contains` relations)
- `_resolve_alias(normalized, knowledge)`: Follow `same_as`, `also_known_as`, `equivalent_to` relations
- `_resolve_contextual(phrase, knowledge, context)`: Use recent subjects from context
- `_resolve_partial_match(phrase, knowledge)`: Suffix matching with safe modifier prefixes

### normalizer.py

**`normalize(text: str) -> str`**
- Converts natural language to internal key format
- Strips articles (the, a, an), filler words (is, are, of, etc.), and verb tense
- Handles plurals intelligently (protects irregular plurals and body parts: dogs → dogs, child → child, leaves → leaves)
- Truncates at invalid entity words (relative clause markers: that, which, who, etc.)
- Example: "the rain makes the ground wet" → "rain"

**`prettify(text: str) -> str`**
- Converts internal key back to readable English
- Single word: returned as-is
- Multi-word ending in adjective: "ground_wet" → "the ground is wet"
- Example: "blue_eyes" → "blue eyes"

**`prettify_effect(text: str) -> str`**
- Format effect/result for natural language output
- Adjective: "wet" → "it gets wet"
- "ground_wet" → "the ground gets wet"

**`prettify_cause(text: str) -> str`**
- Format cause/trigger for natural language output
- Verb-like word: "rain" → "it rains"
- "ground_wet" → "the ground is wet"

**`resolve_possessive(phrase: str, knowledge: dict) -> str`** (legacy)
- Resolves possessive references; falls back to normalization if no match
- Also handles "X Y" compound references

### grammar.py

**`is_adjective(word: str) -> bool`**: Check against `COMMON_ADJECTIVES` dict or common adjective endings (-ed, -ing, -ful, -less, -ous, -ive, -able, -ible, -al, -ic, -ary, -ory, -ant, -ent).

**`is_plural(word: str) -> bool`**: Check against irregular plurals, plural pronouns (they, us), or common plural endings. Special case: words like "fish", "deer", "sheep" (same singular/plural).

**`get_verb_form(subject: str, base_verb: str) -> str`**: Conjugate verb based on subject plurality.
- "crocodiles" + "is" → "are"
- "iguana" + "have" → "has"

**`get_article(word: str) -> str`**: Return "a" or "an" based on word's initial sound. Handles special cases: "university" → "a", "hour" → "an".

**`pluralize(word: str) -> str`**: Convert singular to plural (irregular rules first, then regular: -y → -ies, -s/-sh/-ch/-x/-z → -es, -f/-fe → -ves, else +s).

**`singularize(word: str) -> str`**: Convert plural to singular.

**`format_response(subject: str, verb: str, obj: str) -> str`**: Build grammatically correct statement.
- "crocodiles", "is", "reptile" → "Crocodiles are reptiles."

**`format_list(items: list) -> str`**: Format list with Oxford comma.
- 1 item: "X"
- 2 items: "X and Y"
- 3+ items: "X, Y, and Z"

**`format_what_response(subject: str, obj: str) -> str`**: Format "what is X" response with proper grammar and article.

## How It Works

### Resolution Pipeline

1. **Clean phrase**: Remove articles (the, a, an, my, your, etc.)
2. **Exact match**: Normalize phrase; check if it exists in knowledge directly
3. **Possessive resolution**: Match "X's Y" pattern; find property of X matching Y hint
4. **Compound reference**: Match "X Y" (multi-word); find property of X matching Y
5. **Alias resolution**: Follow `same_as` / `also_known_as` chains to canonical form
6. **Contextual resolution**: Use recent topic subjects; try to find matching property
7. **Partial match**: Suffix match with safe prefixes (only safe adjectives: big, blue, etc.)
8. **New**: Return normalized phrase; will create new neuron

### Specificity Rule in `_find_owner_property()`

When matching "eyes" hint against "blue_eyes" property:
- Count meaningful words (len > 2) in both
- Only merge if hint has ≤ meaningful words than property
- Example: "festival of tides" (3 words) vs "festival" (1 word) → don't merge (hint is more specific)

### Normalization Steps

1. Lowercase and trim
2. Remove filler words: "the ", "is ", "of ", etc. (word boundaries)
3. Remove start-only words: "so " (avoids "also" → "al")
4. Handle special phrases: "ocean water" → "ocean_water"
5. Truncate at invalid words (that, which, who, etc.)
6. For each word:
   - Keep underscored compounds as-is
   - Protect certain words from singularization (dogs, leaves, eyes, etc.)
   - Singularize regular plurals (cats → cat) unless protected
7. Join with underscores; strip trailing underscores

## Dependencies

- **normalizer.py imports**: `re`, `typing`
- **resolver.py imports**: `re`, `typing`, `normalizer` (for `normalize()` function)
- **grammar.py imports**: None (standalone)
- **Used by**: `parser/base.py`, `brain.py`, `inference.py` (all use `resolve_to_existing_neuron()` before creating neurons)

## Examples

### Exact Match
```python
from loom.resolver import resolve_to_existing_neuron

knowledge = {"blue_eyes": {}}
resolved, type_ = resolve_to_existing_neuron("blue eyes", knowledge)
# resolved = "blue_eyes", type_ = "exact"
```

### Possessive Resolution
```python
knowledge = {
    "loom": {"has": ["blue_eyes", "big_heart"]},
    "blue_eyes": {}
}
resolved, type_ = resolve_to_existing_neuron("loom's eyes", knowledge)
# resolved = "blue_eyes", type_ = "possessive"
```

### Compound Reference
```python
knowledge = {
    "loom": {"has": ["blue_eyes"]},
    "blue_eyes": {}
}
resolved, type_ = resolve_to_existing_neuron("loom eyes", knowledge)
# resolved = "blue_eyes", type_ = "compound"
```

### Normalization
```python
from loom.normalizer import normalize, prettify

normalize("the rain makes the ground wet")  # → "rain"
normalize("the ground is wet")               # → "ground_wet"
prettify("ground_wet")                       # → "ground wet"
prettify_effect("ground_wet")                # → "the ground gets wet"
```

### Grammar
```python
from loom.grammar import pluralize, get_verb_form, format_response

pluralize("child")                           # → "children"
get_verb_form("crocodiles", "is")           # → "are"
format_response("crocodiles", "is", "reptile")  # → "Crocodiles are reptiles."
```
