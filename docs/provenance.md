# Provenance Tracking

## Overview

Provenance tracking records the origin and dependencies of facts in the knowledge base. Every fact is tagged with its source type (USER, INFERENCE, CLARIFICATION, INHERITANCE, SYSTEM), the premises it depends on, and derivation metadata. This enables safe retraction: when a fact is removed, the dependency graph identifies and invalidates dependent facts.

**Key Principle:** Traceability without embeddings—every inference is auditable.

## Key Concepts

**SourceType:** Enum classifying how a fact was added:
- **USER:** Directly stated by user in conversation
- **INFERENCE:** Derived by inference engine from rules
- **CLARIFICATION:** Added via clarification dialogue (user correction)
- **INHERITANCE:** Propagated from parent category (frame system)
- **SYSTEM:** System-generated (e.g., self-knowledge)

**Premise:** A reference to a fact that a derived fact depends on. Stored as (subject, relation, object) triple.

**Derivation ID:** Short UUID (8 chars) assigned to each derived fact for tracking related derivations across inference chains.

**Dependency Graph:** Tree mapping facts to:
- **Dependents:** Facts that depend on this fact (cascade invalidation on retraction)
- **Dependencies:** Facts this fact depends on (premise tracking)

**Safe Retraction:** When a fact is retracted:
1. Look up fact in dependency graph
2. Find all dependents (transitive closure)
3. Retract all dependents first
4. Only then retract the fact itself

**Confidence Mapping:** Default confidence levels derived from source type:
- USER & CLARIFICATION → high
- INFERENCE & INHERITANCE → medium
- SYSTEM → low

## API / Public Interface

### SourceType

**Enum Values:**
- `USER` - Directly stated by user
- `INFERENCE` - Derived by inference engine
- `CLARIFICATION` - User clarification/correction
- `INHERITANCE` - Propagated from category
- `SYSTEM` - System-generated

### FactReference

**Initialization:**
- `FactReference(subject, relation, object)` - Create reference to a triple

**Methods:**
- `to_dict()` → dict - Serialize for storage
- `from_dict(d)` → FactReference - Deserialize from dict

**Properties:**
- `subject: str`
- `relation: str`
- `object: str`

**Equality & Hashing:**
- Implements `__hash__` and `__eq__` for use in sets/dicts

### Provenance

**Initialization:**
- `Provenance(source_type=USER, premises=[], rule_id=None, created_at=None, speaker_id=None, derivation_id=None)`

**Factory Methods (class methods):**
- `user(speaker_id=None)` → Provenance - Create USER-sourced provenance
- `inference(premises, rule_id)` → Provenance - Create INFERENCE-sourced with premises
- `inheritance(parent_fact)` → Provenance - Create INHERITANCE-sourced with parent
- `system()` → Provenance - Create SYSTEM-sourced provenance

**Serialization:**
- `to_dict()` → dict - Convert to JSON-serializable dict
- `from_dict(d)` → Provenance - Reconstruct from dict

**Properties:**
- `source_type: SourceType` - How the fact was added
- `premises: List[FactReference]` - Dependencies (for inferred facts)
- `rule_id: Optional[str]` - Rule ID if derived from rule firing
- `created_at: datetime` - Timestamp of creation
- `speaker_id: Optional[str]` - User ID if USER-sourced
- `derivation_id: str` - Short UUID for tracking derivation chains

### DependencyGraph

**Initialization:**
- `DependencyGraph()` - Create empty dependency graph

**Building Dependencies:**
- `add_dependency(fact, depends_on)` - Record that fact depends on depends_on
- `add_dependencies(fact, premises)` - Record that fact depends on all premises

**Querying Dependencies:**
- `get_dependents(fact)` → Set[FactReference] - Direct dependents only
- `get_all_dependents(fact)` → Set[FactReference] - Transitive closure (all facts that depend)
- `get_dependencies(fact)` → Set[FactReference] - All facts this fact depends on

**Maintenance:**
- `remove_fact(fact)` - Remove fact and update all dependency links

### Helper Functions

**confidence_for_source(source_type)** → str
- Returns default confidence level: "high" for USER/CLARIFICATION, "medium" for INFERENCE/INHERITANCE, "low" for SYSTEM

## How It Works

**Recording Provenance on Fact Addition:**
1. When parser calls brain.add_fact(), confidence is determined
2. Provenance created based on source context:
   - Direct user input → SourceType.USER
   - From rule firing → SourceType.INFERENCE with premises and rule_id
   - From frame propagation → SourceType.INHERITANCE with parent fact
   - From system → SourceType.SYSTEM
3. Provenance attached to fact in knowledge base

**Dependency Tracking:**
1. During inference, when rule derives fact from premises:
   a. Create FactReferences for all premises
   b. Create Provenance with source_type=INFERENCE, premises list, rule_id
   c. Call dependency_graph.add_dependencies(fact, premises)
2. Dependency graph stores bidirectional links:
   - Fact X.depends_on = {Premise Y, Premise Z}
   - Premise Y.dependents = {Fact X}

**Safe Retraction:**
1. User retracts fact X
2. DependencyGraph.get_all_dependents(X) finds all facts depending on X
3. For each dependent, recursively find its dependents
4. Build retraction order (dependents first)
5. Retract each fact in order
6. Final: remove X and all its links from graph

**Derivation ID Tracking:**
1. When rule derives fact, assign unique short UUID (8 chars)
2. Multiple facts from same rule firing share same derivation_id
3. Enables grouping related inferences ("all facts from this derivation step")
4. Useful for debugging and "explain this derivation chain"

**Serialization:**
- Provenance.to_dict() stores source_type as string, created_at as ISO string
- FactReferences serialized as triples
- Supports JSON storage (MongoDB or file)
- from_dict() reconstructs exact state on load

## Dependencies

**Imports:**
- dataclasses, typing, enum, datetime, uuid

**Imported By:**
- brain.py - Attaches provenance to facts via add_fact()
- rules.py & rule_engine.py - Create inference provenance on rule firing
- frames.py - Create inheritance provenance on category propagation
- storage/ - Serialize/deserialize provenance when persisting

**Relations with Other Systems:**
- **Brain:** Fact provenance set at add_fact() time
- **Rules:** Rule firing creates INFERENCE-sourced provenance
- **Frames:** Category propagation creates INHERITANCE provenance
- **Inference:** May use provenance to decide retraction order
- **Storage:** Provenance serialized in JSON/Mongo docs

## Correction Provenance

When a fact is corrected, the full correction chain is preserved so that every revision is traceable back to the original statement.

### Correction History

Corrected facts accumulate a `correction_history` list in their properties. Each entry records who made the correction, what the original value was, and when it happened. This list grows with each successive correction, forming a complete audit trail.

### Original Speaker Tracking

When a fact is corrected, the `original_speaker_id` from the retracted fact is carried forward onto the corrected fact's properties. This means the system always knows who first stated the fact, even after multiple corrections by different users.

### `_build_correction_properties(retract_result, corrected_by)`

Helper function in `handlers.py` that constructs the correction metadata for a replacement fact. It takes the result dict from `retract_fact()` (which includes `old_properties`, `old_context`, `old_object`) and the ID of the correcting user, then builds properties containing:

- **`original_speaker_id`** — extracted from the retracted fact's `speaker_id`
- **`corrected_by`** — the user who made this correction
- **`original_value`** — the old object value that was replaced
- **`correction_history`** — accumulated list of all prior corrections (carried forward from the retracted fact's existing history, plus the new correction entry)

### Full Correction Chain Example

```
1. Alice teaches: "dogs are reptiles"
   → properties: {speaker_id: "alice", source_type: "user"}

2. Bob corrects: "actually, dogs are mammals"
   → retract_fact("dogs", "is", "reptiles") returns old_properties with speaker_id="alice"
   → _build_correction_properties(retract_result, corrected_by="bob")
   → new fact properties: {
       original_speaker_id: "alice",
       corrected_by: "bob",
       original_value: "reptiles",
       source_type: "clarification",
       correction_history: [
         {original_value: "reptiles", corrected_by: "bob", original_speaker: "alice", timestamp: "..."}
       ]
     }

3. Carol re-corrects: "dogs are canines"
   → retract_fact("dogs", "is", "mammals") returns old_properties with correction_history
   → correction_history grows:
     [
       {original_value: "reptiles", corrected_by: "bob", original_speaker: "alice", timestamp: "..."},
       {original_value: "mammals", corrected_by: "carol", original_speaker: "alice", timestamp: "..."}
     ]
```

## Examples

**User-stated fact provenance:**
```python
prov = Provenance.user(speaker_id="alice")
brain.add_fact("dogs", "are", "animals", 
               confidence="high", 
               provenance=prov)
# Stored: {source_type: USER, speaker_id: alice, created_at: 2026-04-12T...}
```

**Inference-based provenance:**
```python
premises = [
    FactReference("dog", "is", "mammal"),
    FactReference("dog", "has", "fur"),
]
prov = Provenance.inference(premises, rule_id="rule_5")

brain.add_fact("dog", "is", "warm_blooded",
               confidence="medium",
               provenance=prov)
# Stored: {source_type: INFERENCE, rule_id: rule_5, 
#          premises: [{subject: dog, relation: is, object: mammal}, ...]}
```

**Dependency graph for safe retraction:**
```python
graph = DependencyGraph()

# Build: premise1 → inferred_fact1 → inferred_fact2
premise = FactReference("dogs", "is", "mammals")
fact1 = FactReference("dogs", "is", "warm_blooded")
fact2 = FactReference("dogs", "have", "spines")

graph.add_dependency(fact1, premise)
graph.add_dependency(fact2, fact1)

# Retracting premise:
dependents = graph.get_all_dependents(premise)
# Returns: {fact1, fact2} (transitive closure)
# 
# Retraction order: fact2 → fact1 → premise
```

**Inheritance provenance (frame system):**
```python
# Category propagation creates INHERITANCE provenance
parent = FactReference("dogs", "is", "mammals")
prov = Provenance.inheritance(parent)

brain.add_fact("wolves", "is", "mammals",
               confidence="medium",
               provenance=prov)
# Marked as derived from parent fact for truth maintenance
```

**Confidence mapping from source:**
```python
conf_user = confidence_for_source(SourceType.USER)
# "high"

conf_inferred = confidence_for_source(SourceType.INFERENCE)
# "medium"

conf_system = confidence_for_source(SourceType.SYSTEM)
# "low"
```

**Serialization and restoration:**
```python
prov = Provenance.inference(
    premises=[FactReference("X", "is", "mammal")],
    rule_id="rule_10"
)

# Store to JSON:
stored = prov.to_dict()
# {source_type: "inference", rule_id: "rule_10", 
#  premises: [{subject: X, relation: is, object: mammal}], ...}

# Restore from JSON:
restored = Provenance.from_dict(stored)
# Exact copy of original provenance
```