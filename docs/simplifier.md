# Simplifier Modules

## Overview

**Sentence Simplifier (simplifier.py)** handles straightforward compound sentences by decomposing them into simple subject-verb-object statements. Works on sentence-level patterns common in direct narrative.

**Advanced Simplifier (advanced_simplifier.py)** decomposes complex encyclopedic sentences (the kind found in Wikipedia, textbooks) into atomic facts. Handles participial phrases, appositives, relative clauses, and other complex structures that occur in formal/reference writing.

Both simplifiers are invoked by the parser **before** pattern matching, so complex input becomes multiple simple statements that flow through the standard parse pipeline.

## Key Concepts

### Simplifier: Basic Decomposition Patterns

The basic simplifier handles sentence structures common in everyday speech and writing:

1. **Compound Verbs** — "X verb1 Y and verb2 Z" → ["X verb1 Y", "X verb2 Z"]
2. **List Objects** — "X verb A, B, and C" → ["X verb A", "X verb B", "X verb C"]
3. **Parallel Structure** — "A verb1 X, B verb2 Y" → ["A verb1 X", "B verb2 Y"]
4. **Contrast** — "some X verb A, others verb B" → ["some X verb A", "some X verb B"]
5. **Colon Lists** — "X: A, B, C" or "X verb: A, B, C" → ["X A", "X B", "X C"]

Patterns are tried in order; first match wins.

### Advanced Simplifier: Encyclopedic Decomposition

The advanced simplifier handles complex formal sentence structures by extracting facts from different parts:

1. **Participial Phrases** — "known for X", "giving Y", "made of Z"
2. **Fronted Modifiers** — "Native to X, ...", "Despite Y, ...", "As Z, ..."
3. **Appositives** — "X—which is Y—", "X, the Z, is W"
4. **Relative Clauses** — "X that verb Y", "X which verb Y"
5. **Compound Predicates** — Same subject, multiple verbs
6. **Purpose Clauses** — "to verb X", "for verbing Y"
7. **With-attributes** — "with X and Y" → "X has X", "X has Y"
8. **Pronoun Sentences** — "They verb X", "Its property is Y"

Patterns are applied sequentially (not just first match) so one sentence can yield multiple facts.

### Verb Detection

Both simplifiers need to identify verbs to split sentences correctly. Instead of a hardcoded list:

- **simplifier.py** — Dynamically imports all verbs from `relations.RELATION_DEFS` at init
- **advanced_simplifier.py** — Maintains hardcoded list of common verbs (for performance)

Both handle:
- Regular verbs: "walk", "walks", "walked", "walking"
- Irregular verbs: "go", "goes", "went", "going"
- Multi-word verbs: "live in" (stored as "live_in")

## API / Public Interface

### SentenceSimplifier (simplifier.py)

```python
class SentenceSimplifier:
    def __init__(self)
    def simplify(sentence: str) -> List[str]
    def simplify_paragraph(text: str) -> List[str]
    def process_for_loom(text: str) -> List[dict]
```

**simplify(sentence)** — Returns list of simple sentences (or [original] if no simplification found)

**simplify_paragraph(text)** — Splits on sentence boundaries, simplifies each, returns all simple statements

**process_for_loom(text)** — Returns structured list of dicts with `text`, `original` flag, and `relation_hint`

### AdvancedSimplifier (advanced_simplifier.py)

```python
class AdvancedSimplifier:
    def __init__(self)
    def simplify(sentence: str) -> List[str]
```

**simplify(sentence)** — Returns list of simple facts extracted from complex sentence. Returns [original] if can't parse (for parser to handle).

### Helper Methods (both)

```python
def _extract_subject(clause: str) -> Optional[str]
```
Finds the subject by locating the first verb and returning everything before it.

```python
def _expand_lists(fact: str) -> List[str]
```
(Advanced only) Expands comma-separated lists: "X has A, B, C" → ["X has A", "X has B", "X has C"]

```python
def _clean_results(facts: List[str]) -> List[str]
```
(Advanced only) Removes duplicates, empty strings, and malformed facts.

## How It Works

### Simplifier: Pattern Matching Pipeline

**Input Processing:**
```python
sentence = sentence.strip()
# Try simplification patterns in order
1. _simplify_compound_verbs(sentence)    # X verb1 Y and verb2 Z
2. _simplify_parallel_structure(sentence) # A verb X, B verb Y, C verb Z
3. _simplify_list_pattern(sentence)       # X verb A, B, and C
4. _simplify_contrast_pattern(sentence)   # some X verb A, others verb B
5. _simplify_colon_list(sentence)         # X: A, B, C
# If nothing matches, return [sentence]
```

### Simplifier: Compound Verb Example

**Input:** `"Ancient Egypt developed papermaking and invented gunpowder"`

1. Find "and" position
2. Split before/after "and": 
   - before = "Ancient Egypt developed papermaking"
   - after = "invented gunpowder"
3. Check if after starts with verb → "invented" is a verb ✓
4. Extract subject from before: subject = "Ancient Egypt" (before first verb)
5. Generate:
   - stmt1 = "Ancient Egypt developed papermaking"
   - stmt2 = "Ancient Egypt invented gunpowder"
6. Recursively simplify each (in case of nested patterns)
7. Return both

### Simplifier: List Pattern Example

**Input:** `"dogs need food, water, and shelter"`

1. Match regex: `(.+?) (need) (.+?), and (.+)`
   - subject = "dogs"
   - verb = "need"
   - items_before = "food, water"
   - last_item = "shelter"
2. Check that last_item doesn't contain a verb (would be compound, not list)
3. Split items_before by comma: ["food", "water"]
4. Combine with last_item: ["food", "water", "shelter"]
5. Generate for each:
   - "dogs need food"
   - "dogs need water"
   - "dogs need shelter"

### Advanced Simplifier: Sequential Processing

The advanced simplifier applies transformations sequentially (not just trying patterns):

```python
def simplify(sentence):
    results = []
    
    # Step 1: Extract facts from sentence start (fronted modifiers)
    sentence, fronted_facts = _extract_fronted_modifiers(sentence)
    results.extend(fronted_facts)
    
    # Step 2: Extract facts from appositives/dashes
    sentence, appositive_facts = _extract_appositives(sentence)
    results.extend(appositive_facts)
    
    # Step 3: Extract participial phrases
    sentence, participial_facts = _extract_participial_phrases(sentence)
    results.extend(participial_facts)
    
    # Step 4: Extract relative clauses
    sentence, relative_facts = _extract_relative_clauses(sentence)
    results.extend(relative_facts)
    
    # Step 5: Extract main clause
    main_facts = _extract_main_clause(sentence)
    results.extend(main_facts)
    
    # Step 6-7: Expand lists and clean
    expanded = [item for fact in results for item in _expand_lists(fact)]
    cleaned = _clean_results(expanded)
    
    return cleaned
```

### Advanced Simplifier: Fronted Modifier Example

**Input:** `"Native to Africa, giraffes are tall animals with long necks"`

1. Match `^Native to (.+?), (.+)` → modifier="Africa", remaining="giraffes are tall animals with long necks"
2. Extract subject from remaining: "giraffes"
3. Generate facts:
   - "giraffes is native to Africa"
   - "giraffes lives in Africa" (automatic inference)
4. Extract "with X" attributes:
   - "giraffes has long necks"
5. Continue with remaining: "giraffes are tall animals"
6. Final results: all extracted facts

### Advanced Simplifier: Pronoun Resolution

**Input:** `"They communicate using vocalizations and body language"`

1. Detect "They" as pronoun (doesn't match normal subject extraction)
2. Topic resolution (context-dependent, defaults to "giraffes" in animal text)
3. Rewrite and continue:
   - "giraffes communicate using vocalizations"
   - "giraffes communicate using body language"

### Advanced Simplifier: Encyclopedic Sentence Detection

Some sentences are too complex and should be passed through to the parser unchanged:

```python
encyclopedic_patterns = [
    # "X are Y that come in variety of Z"
    r'.+\s+(?:is|are)\s+.+\s+that\s+come\s+in\s+(?:an?\s+)?(?:\w+\s+)?variety\s+of',
    # "Some X, like A and B, are known for"
    r'(?:some|many|most)\s+.+,\s*(?:like|such\s+as)\s+.+,\s*(?:are|is)\s+(?:known|admired|famous)\s+for',
    # More patterns...
]

if matches_encyclopedic(sentence):
    return [sentence]  # Let parser handle via informational patterns
```

These patterns are handled by specialized informational handlers in the parser instead.

## Dependencies

### simplifier.py Imports
- `re` — Regex for pattern matching
- `typing` — Type hints
- `parser.relations` — RELATION_DEFS (list of all verb forms)

### advanced_simplifier.py Imports
- `re` — Regex for pattern matching
- `typing` — Type hints
- (No external imports; uses hardcoded verb list for performance)

### What Imports These Modules
- `parser/base.py` — Creates `SentenceSimplifier()` and `AdvancedSimplifier()` instances
- Calls `simplify(sentence)` before pattern matching in `parse()` method
- Simplifiers are part of the parser pipeline, not used elsewhere

## Examples

### Simplifier: Compound Verbs
```
Input: "Greece built temples and produced philosophers"
simplify() →
[
  "Greece built temples",
  "Greece produced philosophers"
]
```

### Simplifier: List Objects
```
Input: "cats need food, water, and shelter"
simplify() →
[
  "cats need food",
  "cats need water",
  "cats need shelter"
]
```

### Simplifier: Parallel Structure
```
Input: "Dogs are loyal, cats are independent, birds are free"
simplify() →
[
  "Dogs are loyal",
  "cats are independent",
  "birds are free"
]
```

### Advanced Simplifier: Fronted Modifier + With-Attributes
```
Input: "Native to Africa, with long necks and legs, giraffes reach high leaves"
simplify() →
[
  "giraffes is native to Africa",
  "giraffes lives in Africa",
  "giraffes has long necks",
  "giraffes has long legs",
  "giraffes reach high leaves"
]
```

### Advanced Simplifier: Despite Pattern
```
Input: "Despite their height, which can exceed 18 feet, they are graceful animals"
simplify() →
[
  "giraffes has great height",
  "giraffes height can exceed 18 feet",
  "giraffes is graceful"
]
```

### Advanced Simplifier: Encyclopedic Sentence (Passed Through)
```
Input: "Elephants are large African animals that come in a variety of sizes"
simplify() →
[
  "Elephants are large African animals that come in a variety of sizes"
]
# Returns unchanged; informational patterns will extract facts
```
