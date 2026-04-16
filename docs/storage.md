# Storage Layer

## Overview

The storage layer provides a dual-backend persistence system for Loom's knowledge graph. It abstracts storage details behind a common interface, allowing seamless fallback from MongoDB to JSON files. Both backends support the **Quad + Properties schema**: facts are stored as (subject, relation, object, context) with rich metadata (confidence, temporal scope, source type, conditions, provenance).

## Key Concepts

- **Factory Pattern (`get_storage()`)**: Selects backend automatically; falls back to JSON if MongoDB unavailable.
- **Quad + Properties Schema**: Facts are stored with context and metadata (confidence, temporal, scope, conditions, source type).
- **Instance Isolation**: Multiple Loom instances can coexist in same database/file via `instance_name`.
- **Backward Compatibility**: Supports legacy format (confidence, constraints, provenance) and auto-converts to new format.
- **MongoDB Indexes**: Optimized queries on (instance, subject, relation), (instance, relation, object), and unique fact constraints.
- **JSON Fallback**: Loads/saves to `loom_memory/loom_memory.json`, mimics MongoDB API exactly.
- **Truth Maintenance**: Both backends support cascade retraction (removing fact also removes dependents).

## API / Public Interface

### `get_storage(**kwargs)` → Storage Instance
Factory function. Tries MongoDB first, falls back to JSON.

**Parameters:**
- `use_mongo` (bool, default True): Whether to attempt MongoDB
- `connection_string` (str): MongoDB URI (default `"mongodb://localhost:27017"`)
- `database_name` (str): Database name (default `"loom"`)
- `instance_name` (str): Loom instance name (default `"default"`)
- `memory_file` (str): JSON file path (default `"loom_memory/loom_memory.json"`)

**Returns:**
- `MongoStorage` if available, else `JSONFallbackStorage`

### MongoStorage & JSONFallbackStorage (Identical Interfaces)

**Facts:**
- `add_fact(subject, relation, obj, confidence="high", constraints=None, provenance=None, context=None, properties=None) → bool`
  - Adds fact with Quad + Properties schema
  - Returns False if fact already exists (unique constraint)
  
- `get_facts(subject, relation, context=None) → list[str]`
  - Returns objects for subject-relation pair, optionally filtered by context
  
- `get_facts_with_context(subject, relation) → list[dict]`
  - Returns facts with object, context, and properties metadata
  
- `get_fact_with_metadata(subject, relation, obj, context=None) → dict | None`
  - Returns single fact with all metadata
  
- `get_all_facts_for_subject(subject) → dict`
  - Returns {relation: [objects]} for subject
  
- `get_facts_by_source_type(source_type) → list[dict]`
  - Returns facts filtered by source (USER, INFERENCE, INHERITANCE, etc.)
  
- `get_facts_depending_on(subject, relation, obj) → list[dict]`
  - Returns facts that list this fact as a premise (for cascade retraction)
  
- `get_inferred_facts() → list[dict]`
  - Returns facts with source_type "inference" or "inheritance"
  
- `retract_fact(subject, relation, obj, cascade=False) → dict`
  - Removes fact; if cascade=True, also removes dependent facts
  - Returns {retracted: bool, cascade_count: int, cascaded_facts: list}
  
- `remove_entity(entity) → int`
  - Removes all facts where entity is subject (not object)
  - Returns count removed

**Confidence & Constraints:**
- `get_confidence(subject, relation, obj) → str`
  - Returns confidence level ("high", "medium", "low")
  
- `update_confidence(subject, relation, obj, confidence)`
  - Updates fact confidence
  
- `get_constraints(subject, relation, obj) → list[str]`
  - Returns conditions/constraints on fact
  
- `add_constraint(subject, relation, obj, constraint)`
  - Adds condition to fact

**Knowledge Graph:**
- `get_all_knowledge() → dict`
  - Returns {subject: {relation: [objects]}}
  
- `get_all_nodes() → list[str]`
  - Returns all unique nodes (subjects + objects)
  
- `get_node_count() → int`
  - Returns count of unique nodes
  
- `get_fact_count() → int`
  - Returns total facts stored
  
- `get_subjects_with_relation(relation, obj) → list[str]`
  - Reverse lookup: find subjects that have relation to object

**Procedures:**
- `add_procedure(name, steps)`
  - Stores procedural sequence
  
- `get_procedure(name) → list`
  - Returns steps for procedure
  
- `get_all_procedures() → dict`
  - Returns {name: steps}

**Inferences:**
- `add_inference(subject, relation, obj, depth)`
  - Cache an inferred fact with reasoning depth
  
- `get_inferences() → list`
  - Returns cached inferences as tuples (subject, relation, obj, depth)
  
- `clear_inferences()`
  - Clears inference cache

**Conflicts:**
- `add_conflict(conflict_dict)`
  - Records detected contradiction
  
- `get_conflicts() → list[dict]`
  - Returns all recorded conflicts
  
- `clear_conflicts()`
  - Clears conflict log

**Admin:**
- `forget_all()`
  - Erases all data for this instance
  
- `get_stats() → dict`
  - Returns {nodes, facts, procedures, inferences, conflicts}
  
- `close()` (MongoDB only)
  - Closes MongoDB connection

## How It Works

### Storage Selection

```python
from loom.storage import get_storage

# Automatic selection with fallback
storage = get_storage(use_mongo=True)  # Tries Mongo, falls back to JSON
# OR
storage = get_storage(use_mongo=False)  # JSON only
```

### MongoDB Backend

**Connection:**
- Establishes connection to MongoDB via `MongoClient`
- Tests connection with `ping` command
- Raises error if connection fails after 5-second timeout

**Indexes (auto-created):**
- `idx_subject_relation`: (instance, subject, relation) — fast lookups by subject
- `idx_relation_object`: (instance, relation, object) — reverse lookups
- `idx_unique_fact`: (instance, subject, relation, object, context) — unique constraint
- `idx_object`: (instance, object) — object lookups
- `idx_procedure_name`: (instance, name) — procedure lookups
- `idx_inference_subject`: (instance, subject, relation) — inference cache

**Document Schema:**
```json
{
  "instance": "default",
  "subject": "dog",
  "relation": "is",
  "object": "animal",
  "context": "general",
  "properties": {
    "confidence": "high",
    "temporal": "always",
    "scope": "universal",
    "conditions": [],
    "source_type": "user",
    "created_at": "2026-04-12T...",
    "premises": [],
    "rule_id": null,
    "speaker_id": null
  }
}
```

**Backward Compatibility:**
- Reads both new format (properties) and legacy format (confidence, constraints, provenance)
- Auto-converts on write to new format
- `_normalize_fact()` handles conversion for queries

### JSON Fallback Backend

**File Format:**
```json
{
  "facts": [
    {
      "subject": "dog",
      "relation": "is",
      "object": "animal",
      "context": "general",
      "properties": { ... }
    }
  ],
  "procedures": {
    "procedure_name": ["step1", "step2"]
  },
  "inferences": [["subject", "relation", "object", 2]],
  "conflicts": [],
  "frames": {}
}
```

**Loading:**
- Reads from disk on init
- Auto-converts legacy format (old `knowledge` dict structure)
- Creates default structure if file missing

**Saving:**
- Writes entire `_data` dict to JSON after each mutation
- UTF-8 encoded with 2-space indent
- Preserves all metadata

### Quad + Properties Schema

**Quad (Context):**
- `subject`: Concept name (e.g., "dog")
- `relation`: Relation type (e.g., "is", "can", "causes")
- `object`: Target concept (e.g., "animal")
- `context`: Scope of fact (e.g., "general", "domestic", "scientific")

**Properties (Metadata):**
- `confidence`: "high" | "medium" | "low"
- `temporal`: "always" | "sometimes" | "past" | "future"
- `scope`: "universal" | "typical" | "specific"
- `conditions`: List of constraints (e.g., "only when warm")
- `source_type`: "user" | "inference" | "inheritance" | "clarification" | "system"
- `created_at`: ISO timestamp
- `premises`: List of {subject, relation, object} facts this depends on
- `rule_id`: Optional rule that generated this fact
- `speaker_id`: User who stated this fact
- `derivation_id`: ID of inference that produced this

### Cascade Retraction

When retracting a fact with `cascade=True`:
1. Query `get_facts_depending_on()` to find dependents
2. Recursively retract each dependent
3. Delete the fact itself
4. Return total cascade count

## Dependencies

**Imports:**
- `pymongo.MongoClient` (optional) — MongoDB driver
- `datetime` — Timestamps
- `json` — JSON serialization
- `collections.defaultdict` — Data aggregation
- `os.path` — File checks

**Imported by:**
- `loom.brain.Loom` — Uses `get_storage()` to initialize backend
- `web_app.py` — Persists facts from web interface
- Test suites — Both backends tested with identical interface

## Examples

### Using get_storage()
```python
from loom.storage import get_storage

# Automatic fallback
storage = get_storage()  # MongoDB with fallback to JSON
facts = storage.get_all_knowledge()

# Force JSON
storage = get_storage(use_mongo=False)
storage.add_fact("cat", "is", "animal", confidence="high")
```

### Adding Facts with Metadata
```python
# Simple fact
storage.add_fact("bird", "can", "fly")

# With confidence
storage.add_fact("fish", "lives_in", "water", confidence="high")

# With constraints
storage.add_fact("cats", "are", "animals", 
                 constraints=["typically", "except tigers"],
                 context="domestic")

# With provenance (new format)
storage.add_fact("dog", "can", "bark",
                 properties={
                     "confidence": "high",
                     "temporal": "always",
                     "scope": "universal",
                     "source_type": "user",
                     "speaker_id": "alice"
                 })
```

### Querying Facts
```python
# Get targets
objs = storage.get_facts("dog", "is")  # → ["animal"]

# Get with context and metadata
facts = storage.get_facts_with_context("dog", "can")
# → [{"object": "bark", "context": "general", "properties": {...}}]

# Get by source type
inferred = storage.get_facts_by_source_type("inference")

# Reverse lookup
subjects = storage.get_subjects_with_relation("is", "animal")  # → ["dog", "cat", ...]
```

### Procedures
```python
storage.add_procedure("make_coffee", ["grind beans", "heat water", "brew"])
steps = storage.get_procedure("make_coffee")
```

### Statistics
```python
stats = storage.get_stats()
# {
#   "nodes": 42,
#   "facts": 156,
#   "procedures": 3,
#   "inferences": 8,
#   "conflicts": 0
# }
```

### Cascade Retraction
```python
# Retract with dependents
result = storage.retract_fact("dog", "is", "animal", cascade=True)
# {
#   "retracted": True,
#   "cascade_count": 3,
#   "cascaded_facts": [
#     {"subject": "poodle", "relation": "is", "object": "dog"},
#     ...
#   ]
# }
```
