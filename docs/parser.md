# Parser Module

## Overview

The parser is Loom's natural language understanding system. It converts raw input text into structured knowledge (subject-relation-object triples) through a coordinated cascade of pattern-matching handlers, without relying on NLP libraries or pre-trained models.

The parser uses **modular pattern recognition** where each module handles a specific category of statements or queries. Pattern checks run in strict priority order defined in `base.py`, so earlier patterns take precedence over later ones. When a pattern matches, the parser stops and returns the extracted knowledge.

## Key Concepts

### Pattern Priority Cascade
- The parser checks patterns in a fixed order: queries, then special handlers, then basic patterns, then relations, then discourse/informational patterns
- First match wins — if query patterns match, relation patterns are skipped
- This prevents misclassification (e.g., "what does X do" as a statement instead of a query)

### Modular Architecture
- `base.py` — Orchestrates the parse pipeline and manages pattern priority
- `constants.py` — Shared word lists and configuration (colors, correction indicators, question patterns)
- `relations.py` — Single source of truth for all 100+ relations with verb forms and metadata
- `queries_*.py` — Specialized query handlers for different question types
- `patterns_*.py` — Statement pattern handlers (basic facts, relations, discourse, informational)
- `handlers.py` — Procedural/correction/clarification handlers

### Relations Database
The `relations.py` module defines every relation in Loom as a `RelationDef` with:
- `relation` — The stored relation name (e.g., "causes", "built", "needs")
- `base_verb` — Base verb form (e.g., "cause")
- `past`, `present_s`, `present_p` — Conjugated forms for pattern matching
- `reverse` — Optional reverse relation (e.g., "built" ↔ "built_by")
- `category` — For organizing relations (e.g., "causation", "possession", "behavior")
- `transitive` — Can chain transitively (e.g., "part_of")

## API / Public Interface

### Parser Class (base.py)

```python
class Parser:
    def __init__(self, loom)
    def parse(self, text: str) -> str
    def parse_paragraph(self, text: str) -> str
    def add_fact_with_context(subject, relation, obj, text, confidence)
    def get_curiosity_prompt() -> str
```

### Pattern Detection & Handling

Each module exports a function to check and handle its patterns:
- `queries_basic.check_question(parser, text) -> Optional[str]`
- `patterns_relations.check_is_statement(parser, text) -> Optional[str]`
- `patterns_basic.check_negation(parser, text) -> Optional[str]`

### Query Engine Integration

For dynamic query handling across all relations:
```python
from query_engine import parse_question, handle_query
q = parse_question("what does X verb?")  # Returns {q_word, subject, verb, relation, direction, object}
response = handle_query(parser, "what are dogs?")
```

## How It Works

### 1. Input Normalization
- Strip whitespace and punctuation
- Detect context (temporal, scope, discourse markers)
- Apply structural extraction (hedging, quantities, comparisons)

### 2. Pattern Cascade

**Phase 1: Query Detection** (stop on first match)
- `queries_basic` — "what is X?", "what does X verb?", "who verbed X?", "can X verb?"
- `queries_complex` — Multi-clause questions, conditional queries
- `queries_knowledge` — Domain-specific questions ("what breathes?", "how do X reproduce?")

**Phase 2: Special Handlers** (stop on first match)
- Correction detection — "no, actually X is Y" (user feedback)
- Clarification requests — "tell me about X" (conversational flow)
- Procedure learning — "to do X: first A, then B" (procedural rules)
- Rule learning — "if X then Y" (conditional rules)

**Phase 3: Basic Patterns** (stop on first match)
- Negation — "X is not Y"
- Analogy — "X looks like Y"
- Color attribution — "X is red"
- Existence — "X exists" (stores as "X is entity")

**Phase 4: Relation Patterns** (stop on first match)
- `patterns_relations` — "X verb Y" (causation, possession, abilities, location, etc.)
- Uses relation definitions from `relations.py` to match any verb form against stored relations
- Handles reversed/passive voice: "X was verbed by Y" → "Y verbed X"

**Phase 5: Discourse & Informational** (stop on first match)
- `patterns_discourse` — Natural conversation learning ("you mean X is Y?")
- `informational` — Complex sentences with multiple relations and modifiers

### 3. Simplification Pre-processing
Before pattern matching, complex sentences are broken into simple ones:
- `SentenceSimplifier` — Basic list decomposition, parallel structures ("X verb A and B" → "X verb A", "X verb B")
- `AdvancedSimplifier` — Encyclopedic sentences, appositives, participial phrases, relative clauses

### 4. Structural Extraction
The `StructuralExtractor` (invoked by parser) detects:
- **Hedging** — "might", "could", "perhaps" → lowers confidence to "low"
- **Quantities** — "5 meters", "1000 kg" → stored in frame system's quantities slot
- **Comparisons** — "faster than X" → extracts extra comparison facts
- **Purpose** — "for Xing" → stores purpose relationships

## Dependencies

### Imports
- `normalizer` — Word normalization (strip articles, underscores for spaces)
- `grammar` — Helper functions (is_plural, format_list, get_verb_form)
- `context_detection` — Temporal/scope extraction
- `simplifier` / `advanced_simplifier` — Sentence simplification
- `structural` — Structural metadata extraction
- `parser.relations` — Verb and relation definitions
- `parser.constants` — Shared word lists

### What Imports the Parser
- `brain.py` — Calls `parser.parse(text)` for each user input
- `query_engine.py` — Uses `parse_question()` for structural query parsing
- `main.py` / `web_app.py` — Entry points that feed text to parser via brain

## Examples

### Statement Processing
**Input:** `"dogs are animals"`
1. Checks: not a query, not negation, not analogy
2. Pattern check: `patterns_relations.check_is_statement()` matches
3. Extracts: subject="dogs", relation="is", object="animals"
4. Stores: `loom.add_fact("dogs", "is", "animals")`

### Passive Voice
**Input:** `"coffee was discovered in Ethiopia"`
1. Advanced simplifier detects passive: "was discovered"
2. Extracts via SVO: subject="Ethiopia", verb="discovered", object="coffee"
3. Stores: `loom.add_fact("ethiopia", "discovered", "coffee")`

### Compound Sentence
**Input:** `"dogs are animals and need food"`
1. Simplifier splits: `["dogs are animals", "dogs need food"]`
2. Each passes through pattern cascade independently
3. Stores two facts: `(dogs, is, animals)` and `(dogs, needs, food)`

### Query Processing
**Input:** `"what does a dog eat?"`
1. Routed to `queries_basic.check_question()`
2. `parse_question()` extracts: q_word="what", subject="dog", verb="eat", relation="eats"
3. `handle_query()` performs forward lookup: `loom.get("dog", "eats")`
4. Returns: "Dogs eat meat" (or similar from knowledge base)

### Complex Encyclopedic Sentence
**Input:** `"Giraffes are tall African animals native to savannas, with long necks that allow them to reach leaves"`
1. Advanced simplifier handles fronted modifier "native to savannas"
2. Extracts participial phrase "with long necks"
3. Breaks into: `["giraffes is tall", "giraffes lives in savannas", "giraffes has long necks", ...]`
4. Each simple statement flows through pattern cascade
