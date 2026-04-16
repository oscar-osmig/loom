# Inference Engine

## Overview

The InferenceEngine class (`loom/inference.py`) weaves new threads through reasoning. It performs two types of inference: **immediate** (triggered when facts are added) and **background** (continuous 3-second-interval processing). It handles transitive chaining (hypothetical syllogism), property inheritance through categories, analogy detection, and category bridging.

## Key Concepts

- **Immediate Inference**: Runs synchronously when a fact is added—fast property copying, quick syllogisms, co-activation detection
- **Background Inference**: Runs asynchronously every 3 seconds—deeper transitive chains, connection decay, curiosity generation, rule engine, frame propagation
- **Transitive Relations**: Relations that support chaining—looks_like, is, causes, leads_to, part_of
- **Category Relations**: Mark membership—is, is_a, type_of, kind_of (trigger inheritance)
- **Property Relations**: Properties that propagate—has, can, color, size, shape, eats, lives_in, needs
- **Property Inheritance**: Categories propagate properties to instances (category has property → instance inherits property)
- **Syllogism**: If A→B and B→C (via transitive relation), infer A→C
- **Category Bridges**: Auto-detect category relationships (equivalent_to, subset_of, overlaps_with, similar_to)
- **Analogy Detection**: Find similar concepts based on shared properties; infer missing properties via analogy

## API / Public Interface

### Lifecycle

- `start()` → `None`
  - Start the background inference daemon thread (runs until `stop()` called)

- `stop()` → `None`
  - Signal the background thread to exit on next iteration

### Immediate Inference

- `process_immediate(subject: str, relation: str, obj: str)` → `None`
  - Main entry point called when a fact is added to knowledge graph
  - Activates subject and object, spreads activation, detects co-activation
  - Strengthens direct connection, copies properties for "looks_like"
  - Runs property inheritance for categories, checks transitive chains

### Transitive Chains & Syllogism

- `transitive_chain(start: str, relation: str, visited: set = None, depth: int = 0, max_depth: int = 5)` → `list`
  - Find all reachable nodes via transitive relation (with cycle detection)
  - Returns list of `(target, depth)` tuples where depth is hop distance

- `_apply_syllogism(subject: str, relation: str)` → `None`
  - Apply hypothetical syllogism: if A→B→C, create A→C (with provenance)
  - Checks both forward chains (from subject) and backward chains (to subject)

- `_check_chain_from(subject: str, relation: str)` → `None`
  - Internal helper: find and infer all transitive targets from a subject
  - Creates inferred facts with provenance tracking chain premises

- `_build_chain_premises(start: str, relation: str, end: str)` → `List[dict]`
  - Reconstruct the path from start to end node
  - Returns list of premise dicts: `[{subject, relation, object}, ...]`

### Property Propagation

- `_inherit_properties(instance: str, category: str)` → `None`
  - Immediate: inherit category's properties to instance
  - Example: dogs is mammals, mammals has fur → dogs inherits has fur

- `_deep_inherit(instance: str, relation: str, depth: int = 0, max_depth: int = 3)` → `None`
  - Background: recursively inherit through category chains
  - Example: poodle is dog, dog is mammal, mammal has fur → poodle eventually inherits fur

- `_propagate_properties(subject: str)` → `None`
  - Copy properties across "looks_like" relationships (bidirectional)

### Analogy Detection

- `find_analogies(concept: str)` → `List[Tuple[str, float]]`
  - Find conceptually similar concepts based on property overlap (Jaccard similarity)
  - Returns up to 5 analogies sorted by similarity (threshold ≥ 0.3)

- `infer_from_analogy(concept: str)` → `List[Tuple[str, str, str]]`
  - Infer missing properties from analogous concepts
  - If A similar to B (similarity ≥ 0.5) and B has property P, maybe A has P

### Category Bridging

- `detect_category_bridges()` → `List[Tuple[str, str, str]]`
  - Find implicit relationships between categories based on shared instances
  - Logic: entity_to_categories → category_to_instances → compare categories pairwise
  - Returns list of `(cat1, relation, cat2)` bridges created

- `_get_all_categories(entity: str, visited: Set[str] = None)` → `Set[str]`
  - Get transitive closure of all categories an entity belongs to
  - Example: poodle is dog, dog is mammal, mammal is animal → {dog, mammal, animal}

- `_determine_bridge_relation(cat1: str, instances1: Set[str], cat2: str, instances2: Set[str], shared: Set[str])` → `Tuple[Optional[str], str]`
  - Determine logical relationship between two categories:
    - **equivalent_to**: Same instances (synonyms)
    - **subset_of**: All instances of one are in the other
    - **overlaps_with**: Significant overlap (≥ 50%)
    - **similar_to**: Weak overlap (≥ 25% or ≥ 2 shared instances)
  - Returns `(relation_name, direction)` tuple

- `_already_bridged(cat1: str, cat2: str)` → `bool`
  - Check if two categories already connected via bridge relation

- `_add_bridge(cat1: str, relation: str, cat2: str)` → `None`
  - Add bridging fact and auto-reverse if symmetric (equivalent_to, overlaps_with, similar_to)

### State & Debugging

- `get_inferences()` → `list`
  - Return all inferred facts accumulated: `[(subject, relation, object, depth), ...]`

- `consolidate_knowledge()` → `None`
  - Find co-occurring concept pairs, strengthen frequently-co-occurring connections (≥ 3 times)

## How It Works

### Immediate Inference (Synchronous)

Called when `add_fact(subject, relation, obj)` completes:

1. **Activation**: Activate subject and object in the network
2. **Spreading**: Propagate activation to find co-activated nodes
3. **Co-Activation Processing**: Strengthen connections through shared concepts
4. **Hebbian Strengthening**: Increase weight on the direct connection
5. **Analogy Properties**: For "looks_like", copy properties bidirectionally
6. **Category Inheritance**: For "is" relations, inherit parent's properties immediately
7. **Transitive Check**: For transitive relations, check and infer chains

### Background Inference (Asynchronous)

Runs every 3 seconds in daemon thread (`_background_loop`):

1. **Decay Activations** (every cycle)
2. **Decay Connection Weights** (every 10 cycles = 30s) — synaptic pruning
3. **Curiosity Cycle** (every 5 cycles = 15s) — generate questions
4. **Curiosity Cleanup** (every 20 cycles = 60s) — expire old nodes
5. **Forward Chaining** (every 3 cycles = 9s) — rule engine inference
6. **Connection Discovery** (every 10 cycles = 30s) — find implicit connections
7. **Category Bridges** (every 4 cycles = 12s) — detect category relationships
8. **Frame Propagation** (every 5 cycles = 15s) — attribute slot inheritance

For each fact in `loom.recent` (batch added last cycle):
1. **Apply Syllogism** (for transitive relations)
2. **Propagate Properties** (for looks_like, color, is)
3. **Deep Inherit** (for category relations)

### Transitive Chaining Example

```
facts: dog → is → animal
       animal → needs → food

add_fact("dog", "needs", "food") via syllogism?

_apply_syllogism("dog", "needs"):
  transitive_chain("dog", "needs"):
    - direct: [] (dog has no "needs")
    - return []
  _apply_syllogism("animal", "needs"):
    transitive_chain("animal", "needs"):
      - direct: [food]
      - return [(food, 1)]
    _check_chain_from("animal", "needs"):
      chain = [(food, 1), ...]
      since depth=1 but target in existing, don't infer
      
# Inferred when fact is first added (immediate), not retroactively
```

### Category Bridge Detection

```
Facts:
  poodle is dog
  puppy is dog
  poodle is mammal
  puppy is mammal

detect_category_bridges():
  entity_to_categories = {
    poodle: {dog, mammal},
    puppy: {dog, mammal}
  }
  category_to_instances = {
    dog: {poodle, puppy},
    mammal: {poodle, puppy}
  }
  Compare dog vs mammal:
    instances1 = {poodle, puppy}
    instances2 = {poodle, puppy}
    Equal → equivalent_to
  Creates: dog equivalent_to mammal
```

### Analogy Inference

```
Concepts: robin, sparrow, penguin (all birds)
  robin: {has → [wings, feathers], can → [fly]}
  sparrow: {has → [wings, feathers], can → [fly]}
  penguin: {has → [wings, feathers], can → [NOT fly]}

find_analogies("penguin"):
  Jaccard(penguin, robin): 2/(2+1) = 0.67
  Jaccard(penguin, sparrow): 2/(2+1) = 0.67
  Return: [(robin, 0.67), (sparrow, 0.67)]

infer_from_analogy("penguin"):
  For robin (sim=0.67 ≥ 0.5):
    robin has "fly" but penguin doesn't
    → tentatively infer: penguin can fly (via analogy)
```

## Dependencies

### Imports
- `threading` — Daemon thread for background loop
- `time` — Sleep interval control
- `uuid`, `datetime` — Provenance tracking
- `normalizer.py` — Text normalization functions

### What Imports InferenceEngine
- `brain.py` — Loom creates an engine instance and starts it on init
- `main.py`, `web_app.py` — Indirect via Loom

## Examples

### Transitive Chaining

```python
loom = Loom()
loom.add_fact("dog", "is", "animal")
loom.add_fact("animal", "needs", "food")

# Transitive chain via hypothetical syllogism
chain = loom.inference.transitive_chain("dog", "needs")
print(chain)  # → [("food", 2)] — dog eventually needs food (2 hops)

# Check if inferred fact exists
print(loom.get("dog", "needs"))
# → ["food"] if immediate inference ran, or queued for next background cycle
```

### Property Inheritance

```python
loom.add_fact("mammal", "has", "fur")
loom.add_fact("dog", "is", "mammal")

# Immediate: dog inherits mammal's properties
print(loom.get("dog", "has"))  # → ["fur"] (inherited)
```

### Analogy Inference

```python
loom.add_fact("robin", "has", "wings")
loom.add_fact("robin", "can", "fly")
loom.add_fact("penguin", "has", "wings")

# Find analogies
analogies = loom.inference.find_analogies("penguin")
print(analogies)  # → [("robin", 0.5)]

# Infer missing property from analogy
new_facts = loom.inference.infer_from_analogy("penguin")
print(new_facts)  # → [("penguin", "can", "fly")] (via robin analogy)
```

### Category Bridge Detection

```python
loom.add_fact("poodle", "is", "dog")
loom.add_fact("poodle", "is", "pet")
loom.add_fact("cat", "is", "pet")

# Background cycle detects bridge
bridges = loom.inference.detect_category_bridges()
print(bridges)  # → [("dog", "similar_to", "pet")] or [("pet", "overlaps_with", "dog")]
```

### Background Processing

```python
loom = Loom(verbose=True)

# Inference thread already running in background
loom.add_fact("A", "causes", "B")
loom.add_fact("B", "causes", "C")

# Wait ~3-9 seconds for background inference
time.sleep(10)

# Check inferred transitive fact
print(loom.get("A", "causes"))  # → ["B", "C"] (C inferred in background)
print(loom.inference.get_inferences())
# → [("A", "causes", "C", 2)] (with chain depth)
```
