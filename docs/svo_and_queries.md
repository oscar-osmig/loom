# SVO (Subject-Verb-Object) Extraction & Query Engine

## Overview

**SVO (svo.py)** extracts structured subject-verb-object triples from natural language without a predefined verb list. Uses morphological heuristics (word endings, position) and structural analysis to identify verbs and their arguments.

**Query Engine (query_engine.py)** parses questions structurally (without NLP) and maps them to lookup strategies. Replaces 40+ hardcoded query handlers with a single generic approach that works across all relations.

Both modules work together: SVO handles statement extraction, query engine handles question understanding.

## Key Concepts

### SVO: Verb Detection Without a Hardcoded List

Instead of checking if a word is in a known-verbs list, SVO uses morphological heuristics:

**Morphological Markers:**
- **-ed ending** — Past tense ("founded", "exported")
- **-s/-es ending** — Third person singular ("exports", "teaches")
- **-ing ending** — Progressive ("exporting", "celebrating")
- **Irregular past** — Hardcoded list of common verbs ("built", "broke", "ate")
- **Productive suffixes** — Words ending in -ate, -ize, -ify are almost always verbs

**Structural Heuristics:**
- **Position** — Verbs come after the subject, before or with the object
- **Context** — Follows a noun/pronoun, precedes a determiner/noun/preposition
- **Exclusion** — NOT in the NON_VERBS set (determiners, prepositions, conjunctions, adverbs)

**Known Verbs Hint:**
- If a word matches `RELATION_BY_ANY_VERB`, treat it as a verb (optional hint, not required)
- Also checks "verb + preposition" phrases: "live in", "feed on", "flows to"

### SVO: Passive Voice Handling

Detects auxiliary + past participle pattern:
- **"X was founded by Y"** → Inverts to active: founded(Y, X)
- **"X was established in 1789"** → Extracts as: established(X, in 1789)
- Looks for "by" anywhere in the clause to identify the agent

### Query Engine: Generic Question Structure

Questions are parsed into a normalized structure (q_word, subject, verb, relation, direction, object) that works across all question types:

**Direction:**
- **forward** — `loom.get(subject, relation)` — "what does X verb?"
- **reverse** — Find X where X --verb--> object — "who verbed Y?"
- **yesno** — Confirmation query — "can X verb Y?", "is X Y?"

**Question Word (q_word):**
- **what** — Object lookup ("what does X verb?" → objects)
- **who** — Identity lookup or reverse ("who is X?", "who verbed Y?")
- **where** — Location lookup ("where does X live?")
- **when** — Temporal lookup
- **how** — Method/manner lookup
- **can** — Ability confirmation
- **is/does** — Yes/no questions ("is X Y?", "does X verb Y?")

### Relation Variant Tolerance

The query engine tries multiple forms of relations to handle tense variations:

- **"find" → "finds", "finds", "finding", "found", "find", "find_in", "find_in", ...**
- Maps irregular past tense ("began" ↔ "begin")
- Appends location suffixes ("_in", "_on", "_at")
- This allows queries with any verb tense to find stored facts

## API / Public Interface

### svo.py: SVO Extraction

```python
def extract_svo(text: str) -> Optional[dict]
```
Returns dict with:
- `subject` — The subject (string)
- `verb` — Raw verb as found
- `relation` — Normalized verb for storage (underscores for multi-word verbs)
- `object` — The object
- `passive` — bool (was this passive voice?)
- `auxiliary` — Linking verb if any ("was", "is", etc.)
- `context` — Optional context (e.g., temporal info from passive "by" clauses)

```python
def extract_multiple_svo(text: str) -> List[dict]
```
Handles compound objects: "X verbs A and B" → two triples with same subject/verb, different objects.

### svo.py: Helper Functions

```python
def _looks_like_verb(word: str, position: int, words: List[str]) -> bool
```
Determines if a word is morphologically a verb (checks endings, position, non-verb exclusion).

```python
def _normalize_verb_to_relation(verb: str) -> str
```
Converts verb form to normalized relation name:
- "was founded" → "founded"
- "celebrates" → "celebrates"
- "live in" → "live_in" (spaces become underscores)

### query_engine.py: Question Parsing

```python
def parse_question(text: str) -> Optional[dict]
```
Returns dict with:
- `q_word` — Question type ("what", "who", "where", "how", "can", "is", "does", etc.)
- `subject` — What we're asking about
- `verb` — The action/relation
- `relation` — Normalized relation for lookup
- `object` — Additional object (for "does X verb Y?" or "who verbed X?")
- `direction` — "forward" (lookup object), "reverse" (find subject), or "yesno" (confirmation)

### query_engine.py: Query Handling

```python
def handle_query(parser, text: str) -> Optional[str]
```
Returns a natural language answer string, or None if unanswerable.

Implements strategies for:
- `"what is X?"` → Checks is/has_property/has_instance relations
- Forward lookup (subject + relation) → Returns objects
- Reverse lookup (relation + object) → Finds subjects
- Yes/no confirmation (can, is, does questions) → Yes/No + rationale

### query_engine.py: Helper Functions

```python
def _try_relation_variants(loom, subject, relation) -> Tuple[Optional[list], str]
```
Tries multiple subject AND relation variants to find stored facts. Returns (results, matched_relation).

```python
def _reverse_lookup(loom, relation, target) -> list
```
Finds all subjects X where X --relation--> target. Uses reverse relations when available, falls back to full scan.

```python
def _try_subject_variants(subject: str) -> List[str]
```
Generates singular/plural/article variants: "the dog" → "dog", "dogs", "the dog", "the dogs"

## How It Works

### SVO Extraction Pipeline

**1. Passive Voice Detection (First Strategy)**
```
Input: "X was founded by Y"
└─ Look for: auxiliary + past participle
   - Finds "was" (auxiliary)
   - Next word "founded" ends in -ed → past participle
   - Extracts subject="X", verb="founded", object="Y"
   - Looks for "by" in remaining text → inverts to Y founded X
```

**2. Content Verb Detection (Second Strategy)**
```
Input: "dogs eat meat"
└─ For each word, check _looks_like_verb():
   - "eat" at position 1
   - Not in NON_VERBS, ends in -s (3rd person)
   - After "dogs" (noun), before "meat" (noun)
   - → Identified as verb
   - Extracts: subject="dogs", verb="eat", object="meat"
```

**3. Verb + Preposition Handling**
```
Input: "Valdoria exports to France"
└─ Detected verb="exports"
   - Next word "to" is a preposition
   - Combines: verb="exports_to", object="France"
```

### Query Engine Pipeline

**1. Question Parsing**
```
Input: "what does a dog eat?"
└─ Regex matches "what does (.+) (\w+)"
   - subject="a dog", verb="eat", relation="eats"
   - direction="forward" (looking for object)
   - q_word="what"
```

**2. Variant Generation**
```
subject="a dog" → ["a dog", "dog", "dogs", "a dogs"]
relation="eats" → ["eats", "eat", "eaten", "eats_in", "eats_on", ...]
```

**3. Forward Lookup**
```
For each (subject_variant, relation_variant):
  results = loom.get(subject_variant, relation_variant)
  if results → found!
```

**4. Response Generation**
```
results = ["meat", "plants"]
q_word="what", subject="dog"
→ "Dogs eat meat and plants."
```

### Reverse Lookup Example

**Input:** `"who founded Valdoria?"`

1. Parse: relation="founded", object="valdoria", direction="reverse"
2. Check reverse relation defined in `relations.py` → "founded_by"
3. Try: `loom.get("valdoria", "founded_by")` → gets agent(s)
4. Response: "X founded Valdoria." (where X comes from the reverse relation)

## Dependencies

### svo.py Imports
- `re` — Regex for pattern matching
- `typing` — Type hints
- `parser.relations` — Optional: RELATION_BY_ANY_VERB lookup (hint, not required)

### query_engine.py Imports
- `re` — Regex for question patterns
- `normalizer` — normalize(), prettify() for display
- `grammar` — is_plural(), format_list() for grammar
- `svo` — AUXILIARIES, NON_VERBS, PREPOSITIONS sets
- `parser.relations` — get_relation_for_verb(), get_relation_by_name()
- `brain` — loom.get(), loom.knowledge access

### What Imports These Modules
- `parser/base.py` — Uses `extract_svo()` for statement extraction
- `parser/queries_*.py` — Use both `parse_question()` and `handle_query()`
- `brain.py` — Calls `extract_svo()` as part of parsing
- `query_engine` is the main entry point called by query handlers

## Examples

### SVO: Basic Statement
```
Input: "cats eat fish"
extract_svo() →
{
  "subject": "cats",
  "verb": "eat",
  "relation": "eats",
  "object": "fish",
  "passive": False,
  "auxiliary": None
}
```

### SVO: Passive Voice
```
Input: "coffee was discovered in Ethiopia"
extract_svo() →
{
  "subject": "ethiopia",
  "verb": "discovered",
  "relation": "discovered",
  "object": "coffee",
  "passive": True,
  "auxiliary": "was",
  "context": "in Ethiopia"
}
```

### SVO: Verb + Preposition
```
Input: "birds migrate to Africa"
extract_svo() →
{
  "subject": "birds",
  "verb": "migrate",
  "relation": "migrate_to",
  "object": "Africa",
  "passive": False,
  "auxiliary": None
}
```

### Query: Forward Lookup
```
Input: "what does a spider have?"
parse_question() → 
{
  "q_word": "what",
  "subject": "spider",
  "verb": "have",
  "relation": "has",
  "object": None,
  "direction": "forward"
}

handle_query() →
_try_relation_variants(loom, "spider", "has")
→ Returns ["eight legs", "web"]
→ Response: "A spider has eight legs and a web."
```

### Query: Reverse Lookup
```
Input: "who invented the telescope?"
parse_question() →
{
  "q_word": "who",
  "subject": None,
  "verb": "invented",
  "relation": "invented",
  "object": "telescope",
  "direction": "reverse"
}

handle_query() →
_reverse_lookup(loom, "invented", "telescope")
→ Checks reverse relation "invented_by" for "telescope"
→ Returns ["Galileo"]
→ Response: "Galileo invented the telescope."
```

### Query: Yes/No
```
Input: "can dogs swim?"
parse_question() →
{
  "q_word": "can",
  "subject": "dogs",
  "verb": "swim",
  "relation": "can",
  "object": "swim",
  "direction": "yesno"
}

handle_query() →
Results = loom.get("dog", "can") or []
→ Check if "swim" matches any ability
→ Response: "Yes, dogs can swim."
```
