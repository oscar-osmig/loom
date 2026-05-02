# Brain

## Overview

The Loom class (`loom/brain.py`) is the core knowledge system—a directed knowledge graph that stores facts as triples (subject, relation, object) with confidence levels, context, and metadata. It manages fact addition/retraction, storage persistence, confidence consolidation, and integrates inference, activation networks, and knowledge discovery subsystems.

## Key Concepts

- **Triple Store**: Facts are stored as `(subject, relation, object)` with confidence levels (high/medium/low)
- **Quad + Properties**: Extended beyond basic triples with context and a properties dict (temporal scope, source type, premises, speaker, etc.)
- **Knowledge Cache**: In-memory cache synchronized with persistent storage for fast access
- **Hebbian Strengthening**: Connection weights increase when facts are used or repeated
- **Confidence Consolidation**: Repeated mentions elevate confidence (low→medium→high)
- **Entity Resolution**: Automatic normalization and alias mapping to reduce duplicate neurons
- **Dormant Neurons**: Low-quality neurons are marked dormant instead of deleted, preserving data for potential reactivation
- **Access Tracking**: Per-entity access counts and timestamps drive Hebbian boosts and core concept promotion
- **Staleness Decay**: Unused concepts gradually lose confidence over time (never deleted)

## API / Public Interface

### Core Query & Storage

- `get(subject, relation, context=None, temporal=None, include_dormant=False)` → `list | None`
  - Retrieve targets for a subject-relation pair, optionally filtered by context or temporal scope
  - `temporal` can be: "always", "currently", "past", "future", "sometimes"
  - `include_dormant`: If False (default), dormant entities are filtered from results

- `add_fact(subject, relation, obj, confidence=None, _save=True, _propagate=True, provenance=None, context=None, properties=None)` → `None`
  - Add a fact to the knowledge graph; validates entity names, checks for conflicts, stores with metadata
  - Auto-determines confidence from provenance source_type if not specified
  - Triggers immediate inference and inheritance propagation if requested

- `retract_fact(subject, relation, obj, cascade=True)` → `dict`
  - Remove a fact; optionally cascade-retract dependent inferred facts
  - Returns `{"retracted": bool, "cascade_count": int}`, plus `old_properties`, `old_context`, `old_object` when the fact existed (for correction provenance chain)

- `get_with_properties(subject, relation, include_dormant=False)` → `list | None`
  - Get facts with their context and full properties dict (Quad + Properties schema)
  - `include_dormant`: If False (default), dormant entities are filtered from results

- `get_fact_metadata(subject, relation, obj, context=None, include_dormant=False)` → `dict | None`
  - Retrieve full metadata for a specific fact
  - `include_dormant`: If False (default), returns None if subject or object is dormant

### Confidence & Temporal

- `get_confidence(subject, relation, obj)` → `str`
  - Get confidence level for a fact

- `update_confidence(subject, relation, obj, confidence)` → `None`
  - Update confidence level (after consolidation or correction)

- `get_current_facts(subject, relation)` → `list | None`
  - Get facts currently true (filters "past" and "future" scoped facts)

- `get_past_facts(subject, relation)` → `list | None`
  - Get facts that were true in the past

- `get_future_facts(subject, relation)` → `list | None`
  - Get facts that will be true in the future

- `detect_temporal_conflicts(subject=None)` → `list`
  - Find temporal inconsistencies (e.g., "can" vs "cannot" at overlapping times)

- `get_temporal_summary(subject)` → `dict`
  - Summarize all facts organized by temporal scope

### Constraints & Procedures

- `add_constraint(subject, relation, obj, condition)` → `None`
  - Add a conditional constraint to a fact ("only if X")

- `get_constraints(subject, relation, obj)` → `list`
  - Get constraints for a fact

- `add_procedure(name, steps)` → `None`
  - Add a procedural knowledge sequence

- `get_procedure(name)` → `list`
  - Get steps for a named procedure

### Visualization & Display

- `show_knowledge()` → `None`
  - Display full knowledge graph as ASCII neural network visualization

- `show_neuron(node_name)` → `None`
  - Display a single neuron and its direct connections

- `show_compact()` → `None`
  - Show compact list of all neurons

- `show_inferences()` → `None`
  - Display inferred facts from syllogistic reasoning

- `trace_chain(start, relation)` → `None`
  - Show the full reasoning chain from a starting node

### Connection Weights (Hebbian)

- `strengthen_connection(subject, relation, obj, amount=0.1)` → `None`
  - Increase weight on a connection (cells that fire together wire together)

- `decay_all_connections(elapsed_threshold=120.0)` → `None`
  - Reduce weights on unused connections (synaptic pruning)

### Dormant Neuron System

- `cleanup_junk_neurons()` → `int`
  - Marks low-quality neurons as dormant instead of deleting them (preserving data for reactivation)
  - Skips `core_concepts` (entities with 20+ accesses)
  - Returns count of newly dormant neurons

- `reactivate_entity(entity)` → `None`
  - Removes entity from `dormant_entities` and restores its connections from `dormant_connections`

- Instance attributes:
  - `dormant_connections: set` — connections marked dormant by cleanup
  - `dormant_entities: set` — entities marked dormant by cleanup

- Auto-reactivation: `add_fact()` automatically reactivates dormant subjects and objects when new facts reference them

### Access Tracking

- `_track_access(entity)` → `None` (internal)
  - Increments access count and updates last-accessed timestamp
  - Every 5 accesses, boosts the entity's connections by 0.1 (Hebbian strengthening)
  - 20+ accesses promotes the entity to a core concept (immune to cleanup and staleness decay)

- `get_access_count(entity)` → `int`
  - Return the access count for an entity

- `get_most_accessed(n=10)` → `List[Tuple[str, int]]`
  - Return the top-n most accessed entities with their counts

- Instance attributes:
  - `access_counts: Dict[str, int]` — per-entity access counts
  - `last_accessed: Dict[str, float]` — per-entity last-access timestamps
  - `core_concepts: set` — entities with 20+ accesses (immune to cleanup and staleness decay)

### Staleness Decay

- `_decay_stale_concepts()` → `None` (internal)
  - Concepts unused for 24+ hours lose one confidence level (high→medium→low)
  - Never deletes facts — only reduces confidence
  - Skips core concepts and system entities

### Text Processing

- `process(text)` → `str`
  - Main entry point: routes to paragraph processing or sentence processing based on text length

- `process_with_activation(text)` → `str`
  - Process single sentence with spreading activation and immediate inference

- `process_text(text)` → `str`
  - Process multi-sentence paragraph with chunking and discourse relation detection

### Property Copying

- `copy_properties(target, source)` → `None`
  - Copy copyable relations (color, is, can, has, eats, lives_in, needs) from source to target

### Full Reset

- `forget_all()` → `None`
  - Clears all knowledge and resets all state: storage, cache, dormant sets, access tracking, core concepts, and staleness tracking

## How It Works

### Fact Addition Flow

1. **Resolution**: Subject and object are resolved to existing neurons via fuzzy matching or coreference
2. **Dormant Reactivation**: If subject or object is dormant, automatically reactivated before proceeding
3. **Validation**: Entity names are checked against pollution rules (reject fragments, malformed compounds, etc.)
4. **Conflict Detection**: Checks for contradictions (is vs is_not, can vs cannot)
5. **Confidence Determination**: If not explicit, inferred from provenance source_type or defaults to high
6. **Duplicate Check**: If fact already exists, consolidate confidence instead of adding
7. **Storage**: Persisted with context, properties, and metadata via storage backend
8. **Cache Invalidation**: Knowledge cache marked dirty for next access
9. **Inference Trigger**: Immediate inference runs (transitive chains, property inheritance) if requested
10. **Inheritance Propagation**: For "is" relations, properties inherited from parent category

### Confidence Consolidation

Repeated mentions strengthen confidence:
- **low** + any → **medium** (fact confirmed once)
- **medium** + any → **high** (fact confirmed twice)
- **high** + any → **high** (already max)

### Temporal Filtering

Facts store a temporal scope (always, currently, past, future, sometimes):
- **"always"** matches any temporal query (universal truth)
- **"currently"** matches "currently" query, also inherits "always" facts
- **"past"** only matches "past" queries
- **"future"** only matches "future" queries

### Dormant Neuron Lifecycle

1. **Cleanup** (`cleanup_junk_neurons`): Low-quality neurons (reverse-only links, few connections) are moved to `dormant_entities` / `dormant_connections` instead of being deleted. Core concepts are never marked dormant.
2. **Filtering**: `get()`, `get_with_properties()`, and `get_fact_metadata()` skip dormant entities by default (`include_dormant=False`). The `knowledge` property also filters dormant entities from the cache.
3. **Reactivation**: Dormant entities are automatically reactivated when new facts reference them (via `add_fact`), or manually via `reactivate_entity()`.

### Access Tracking & Core Concepts

- Every call to `get()` increments the access count for the queried entity via `_track_access()`.
- Every 5 accesses, the entity's connections receive a 0.1 Hebbian boost.
- At 20+ accesses, the entity is promoted to a **core concept** — immune to dormant cleanup and staleness decay.

### Staleness Decay

- `_decay_stale_concepts()` runs periodically and demotes confidence for concepts unused for 24+ hours (high→medium→low).
- Facts are never deleted by staleness — only their confidence is reduced.
- Core concepts (20+ accesses), system entities, and entities with 10+ accesses are exempt.

## Dependencies

### Imports (Downstream)
- `activation.py` — ActivationNetwork for spreading activation and co-activation detection
- `inference.py` — InferenceEngine for transitive chaining and property inheritance
- `parser/` — Parser for extracting relations from text
- `context.py` — ConversationContext for coreference and topic tracking
- `frames.py` — FrameManager for attribute slots (confirmed/potential tiers)
- `storage/` — Storage backends (MongoDB or JSON fallback)
- `chunker.py` — TextChunker for multi-sentence processing
- `discovery.py` — ConnectionDiscoveryEngine for background pattern learning
- `rules.py` — RuleEngine for forward chaining
- `curiosity.py` — QuestionGenerator and CuriosityNodeManager

### What Imports Brain
- `main.py` — CLI entry point
- `web_app.py` — Flask web API
- All subsystems (parser, inference, activation, etc.) hold a reference to Loom

## Examples

### Adding and Querying Facts

```python
loom = Loom(verbose=True)

# Add facts
loom.add_fact("dogs", "is", "animals")
loom.add_fact("dogs", "color", "brown")
loom.add_fact("fido", "is", "dog")

# Query
print(loom.get("dogs", "is"))  # → ["animals"]
print(loom.get("fido", "is"))  # → ["dog"] (direct), inherits ["animals"] through inference

# Consolidate confidence
loom.add_fact("dogs", "is", "animals")  # Second mention
conf = loom.get_confidence("dogs", "is", "animals")
print(conf)  # → "high" (consolidated from repeated mention)
```

### Temporal Facts

```python
# Current state
loom.add_fact("leaves", "color", "green", properties={"temporal": "currently"})

# Past state
loom.add_fact("leaves", "color", "brown", properties={"temporal": "past"})

# Query by temporal scope
current = loom.get_current_facts("leaves", "color")  # → ["green"]
past = loom.get_past_facts("leaves", "color")        # → ["brown"]
```

### Connection Weights

```python
# Strengthen a frequently-used connection
loom.strengthen_connection("dogs", "eats", "meat", amount=0.5)

# Periodically decay weak connections (called by inference background thread)
loom.decay_all_connections(elapsed_threshold=120.0)
```

### Conflict Detection

```python
# Add conflicting facts
loom.add_fact("penguin", "can", "fly")
loom.add_fact("penguin", "cannot", "fly")

# Check stored conflicts
print(loom.conflicts)  # → [{"type": "contradiction", "fact1": ..., "fact2": ...}]
```

### Dormant Neurons & Access Tracking

```python
# Cleanup marks junk neurons as dormant (not deleted)
count = loom.cleanup_junk_neurons()
print(count)  # → 3 (newly dormant neurons)

# Dormant entities are hidden from queries by default
print(loom.get("junk_entity", "is"))  # → None (dormant, filtered out)
print(loom.get("junk_entity", "is", include_dormant=True))  # → ["something"] (still there)

# Adding a fact about a dormant entity reactivates it
loom.add_fact("junk_entity", "is", "useful_thing")  # auto-reactivates

# Access tracking — frequent queries promote to core concept
for _ in range(20):
    loom.get("dogs", "is")
print(loom.get_access_count("dogs"))  # → 20+
print("dogs" in loom.core_concepts)   # → True (immune to cleanup and staleness)

# Top accessed entities
top = loom.get_most_accessed(n=5)
print(top)  # → [("dogs", 25), ("cats", 12), ...]
```

### Retraction with Provenance

```python
# Retract returns old data for correction provenance chain
result = loom.retract_fact("dogs", "color", "black")
print(result)
# → {"retracted": True, "cascade_count": 0,
#     "old_properties": {"temporal": "always"}, "old_context": None, "old_object": "black"}
```
