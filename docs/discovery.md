# Discovery Engine

## Overview

The discovery engine runs background pattern scanning to find implicit connections, fill gaps, and identify emerging structure in the knowledge graph. It operates via two complementary systems:

1. **DiscoveryMixin** — Core methods for inheritance propagation, facet grouping, and contextual queries
2. **ConnectionDiscoveryEngine** — Enhanced pattern discovery (property clusters, co-occurrence, structural similarity, transitive gaps, lonely neurons, analogies, path-based similarities)

Both use spreading activation to find related concepts and weak inference patterns that warrant strengthening.

## Key Concepts

### Thresholds & Constants

Discovery uses tuned thresholds to balance sensitivity and noise:

- **`MIN_PATTERN_SUPPORT = 3`** (lowered from 5) — minimum entity count to recognize a property cluster
- **`MIN_DISCOVERY_CONFIDENCE = 0.6`** (lowered from 0.7) — minimum confidence to act on a discovered pattern
- **`WEAK_NEURON_MAX_CONNECTIONS = 3`** — neurons with this many or fewer connections are considered weak
- **`WEAK_NEURON_MAX_AVG_WEIGHT = 1.5`** — neurons whose average connection weight is at or below this are considered weak

The lowered thresholds allow discovery to find patterns in smaller knowledge graphs where strict thresholds would miss valid connections.

### Property Clusters
Groups of entities sharing 2+ properties. Example:
- `cat`, `dog`, `lion` all have `fur` and `can_hunt`
- Discovery creates `similar_to` links with confidence based on overlap count

### Inheritance Propagation
- **Up**: If `dolphin is mammal` and `mammal is animal`, then `dolphin is animal` (transitively)
- **Down**: If `mammal can breathe_air` and `dolphin is mammal`, then `dolphin can breathe_air` (with conflict checking)
- Respects conflicts: won't propagate `can_X` if entity has `cannot_X`

### Facets & Location Grouping
Automatic categorization by habitat/property:
- `ocean`, `sea`, `water`, `river`, `lake` → `aquatic`
- `land`, `forest`, `jungle`, `desert`, `savanna` → `terrestrial`
- `sky`, `air` → `aerial`

When `dolphin lives_in ocean`, automatically adds `dolphin habitat_type aquatic` and `aquatic_creatures includes dolphin`.

### Co-occurrence Mining
Tracks entities mentioned together; if they co-occur 2+ times, suggests connection.
- Used in `ConnectionDiscoveryEngine.track_co_occurrence(entities)`
- Helps discover implicit associations

### Transitive Gaps
Finds missing transitive edges (A→B→C but no A→C).
- Typical gaps: `causes`, `leads_to`, `part_of`
- Suggests new inferences or suggests questions to the curiosity engine

### Structural Similarity
Entities with similar relation patterns:
- Both have same subject relations with same objects
- Suggests they're similar in role or function
- Lower confidence than property clustering

### Lonely Neurons
Entities with few connections in knowledge graph.
- May indicate incomplete learning or emergent specialization
- Prioritized for curiosity exploration

### Weak Neuron Strengthening

`strengthen_weak_neurons(brain)` identifies neurons that are technically connected but underserved (at most `WEAK_NEURON_MAX_CONNECTIONS` connections with average weight at most `WEAK_NEURON_MAX_AVG_WEIGHT`) and attempts to strengthen them using three strategies:

1. **Shared categories** — If weak neuron X and strong neuron Y share a parent category (`X is A`, `Y is A`), suggest a `similar_to` link between them
2. **Properties** — If weak neuron X shares properties with other neurons (e.g., both `has fur`), suggest `similar_to` links based on property overlap
3. **Activation** — Use spreading activation from the weak neuron to find related concepts that could form new connections

Each suggestion goes through `_suggest_connection()`, a helper that performs quality checks before proposing a connection:
- Verifies the connection does not already exist
- Ensures it would not create a self-loop
- Checks that the target entity actually exists in the knowledge graph
- Validates that the proposed relation type is appropriate for the entities involved

### Bridges & Analogies
- **Bridge neurons**: Intermediate concepts connecting disparate clusters
- **Analogies**: A:B :: C:? pattern detection
- Help surface unexpected connections for learning

## API / Public Interface

### DiscoveryMixin

```python
# Inheritance chains
_propagate_inheritance(subject: str, parent: str, confidence: str)
get_category_chain(entity: str) -> List[str]

# Instance tracking
_add_instance(category: str, instance: str)
get_instances(category: str) -> List[str]  # All instances of a category

# Facet grouping
_update_location_facet(subject: str, location: str)
get_by_facet(facet: str) -> List[str]  # Get entities in facet (e.g., "aquatic")

# Connection discovery
discover_connections() -> List[Tuple[str, str, str]]  # Returns new (subject, relation, object)
_propagate_properties_down() -> List[Tuple[str, str, str]]
find_related_by_context(entity: str, context: str) -> List[str]
run_discovery_cycle() -> Dict  # Returns {connections_discovered, properties_propagated, categories_linked}
```

### ConnectionDiscoveryEngine

```python
__init__(loom: "Loom")

# Co-occurrence tracking
track_co_occurrence(entities: List[str])  # Called when processing input

# Background discovery
run_background_discovery()  # Full scan for patterns

# Pattern finding (internal)
_find_property_clusters() -> List[DiscoveredPattern]
_find_structural_similarities() -> List[DiscoveredPattern]
_analyze_co_occurrence() -> List[DiscoveredPattern]
_find_transitive_gaps() -> List[DiscoveredPattern]
_find_missing_properties() -> List[DiscoveredPattern]
_find_lonely_neurons() -> List[DiscoveredPattern]
_find_analogies() -> List[DiscoveredPattern]
_find_path_similarities() -> List[DiscoveredPattern]
_create_inverse_relations() -> List[Tuple[str, str, str]]

# Neuron proposal (if enabled)
_propose_neurons_from_patterns()  # Create emergent categories

# Statistics
get_stats() -> Dict
```

### DiscoveredPattern (dataclass)

```python
pattern_type: str                  # cluster, co_occurrence, bridge, similar, gap, analogy
entities: List[str]                # Entities involved in pattern
shared_properties: Dict[str, List[str]]  # relation -> values
support_count: int = 1             # How many instances support pattern
confidence: float = 0.5            # Confidence score
created_at: float                  # Timestamp
```

### DiscoveredNeuron (dataclass)

```python
name: str                          # Proposed category/bridge name
neuron_type: str                   # category, bridge, process
members: List[str]                 # Entities in this group
properties: Dict[str, List[str]]   # Relation → values
provenance: dict                   # Why this neuron was proposed
confidence: float = 0.5            # Confidence score
```

## How It Works

### DiscoveryMixin Flow

1. **Adding a fact**: `add_fact("dolphin", "lives_in", "ocean", confidence)`
2. **Propagation up**: `_propagate_inheritance("dolphin", "mammal")` finds that mammal is animal, adds dolphin is animal transitively
3. **Propagation down**: For each dolphin category (mammal), look for mammal's inheritable relations (can, has, needs) and propagate if no conflict
4. **Facet grouping**: Check if location matches facet; add to aquatic_creatures, set habitat_type
5. **Periodic discovery**: `run_discovery_cycle()` calls `discover_connections()` to find similar entities

### ConnectionDiscoveryEngine Flow

Called from background inference loop (every 30 seconds):

1. **Track co-occurrence**: While parsing input, call `track_co_occurrence(extracted_entities)`
2. **Run background discovery**:
   - Find property clusters (2+ shared properties → similar_to)
   - Analyze co-occurrence patterns (entities mentioned together)
   - Find structural similarities (same relation signatures)
   - Find transitive gaps (A→B→C, suggest A→C)
   - Find missing properties (80%+ of category has it)
   - Find lonely neurons (< 3 connections)
   - Find analogies (A:B :: C:?)
   - Find path similarities (indirect connections)
   - Create inverse relations (if A→B, add B←A)
3. **Process patterns**: For each strong pattern, decide whether to add relation or suggest to curiosity engine
4. **Propose neurons**: If AUTO_CREATE_NEURONS enabled, create new categories from patterns

### Transitive Gap Example

```
Knowledge graph:
- rain causes flooding
- flooding causes evacuation
- (gap: no rain → evacuation link)

Discovery finds:
- Entities in causal chain: rain, flooding, evacuation
- Creates DiscoveredPattern(pattern_type="gap", entities=[rain, flooding, evacuation])
- Suggests: "Does rain cause evacuation?" to curiosity engine
```

### Property Cluster Example

```
Input: "dolphins have fur, dolphins can swim, dolphins are intelligent"
Input: "whales have fur, whales can swim"
Input: "lions have fur, lions can hunt"

Discovery scan finds:
- Property index: (has, fur) → {dolphin, whale, lion}
- Property index: (can, swim) → {dolphin, whale, fish}
- Overlap: dolphin, whale share 2 properties
- Creates: similar_to link (dolphin, whale) with confidence 0.4
```

### Facet Grouping Flow

```python
add_fact("penguin", "lives_in", "antarctica")
├─ Detect location="antarctica" not in facet map
└─ Skip facet creation

add_fact("dolphin", "lives_in", "ocean")
├─ Detect location="ocean" in LOCATION_FACETS
├─ Map to facet="aquatic"
├─ Add: aquatic_creatures includes dolphin
└─ Add: dolphin habitat_type aquatic
```

### Conflict Checking in Propagation

```python
# Category has property
add_fact("birds", "can", "fly")
# But specific instance contradicts
add_fact("penguin", "is", "bird")
add_fact("penguin", "cannot", "fly")

# During propagation:
Propagate birds.can→penguin?
├─ Check penguin has conflicting cannot_fly
├─ Skip propagation (conflict detected)
└─ Don't add penguin can fly
```

## Dependencies

**Imports from:**
- `brain.Loom` — parent knowledge system
- `normalizer.normalize` — entity normalization
- `time`, `collections.defaultdict` — pattern tracking
- `dataclasses`, `enum` — pattern dataclasses

**Used by:**
- Inference engine (calls `run_discovery_cycle()` in background loop)
- CLI commands: `show frames`, `show bridges`, `show clusters`
- Potential future: Explain engine (for "why is X similar to Y?")

**Data sources:**
- `self.knowledge` — the full knowledge graph
- `self.storage` — persistent fact storage
- `self.connection_weights` — Hebbian weights from co-activation
- `self.activation` — spreading activation network

## Examples

### Discovering Connections Between Animals

```python
loom = Loom("animals")
loom.train("animals")  # Adds dogs, cats, birds, fish

# After training, call discovery
result = loom.run_discovery_cycle()
# Result: {
#   "connections_discovered": 3,  # Similar_to links
#   "properties_propagated": 12,  # Inherited properties
#   "categories_linked": 1        # New category chains
# }

# Check discovered similarity
similar = loom.get("dogs", "similar_to")
# Returns: ["cats", "wolves", ...]  # All mammals with fur/legs/domestication
```

### Using Facets to Query by Habitat

```python
# After adding facts about aquatic animals:
loom.add_fact("shark", "lives_in", "ocean")
loom.add_fact("dolphin", "lives_in", "sea")

# Discovery automatically groups them
aquatic = loom.get_by_facet("aquatic")
# Returns: ["shark", "dolphin", "fish", ...]

# Find only aquatic mammals
aquatic_mammals = loom.find_related_by_context("mammals", "aquatic")
# Returns: ["dolphin", "whale", "seal", ...]
```

### Handling Inheritance Chains

```python
loom.add_fact("poodle", "is", "dog")
loom.add_fact("dog", "is", "mammal")
loom.add_fact("mammal", "is", "animal")

# Check inherited categories
chain = loom.get_category_chain("poodle")
# Returns: ["dog", "mammal", "animal"]

# Propagation adds inherited facts:
# poodle is mammal (inferred)
# poodle is animal (inferred)
```

### Co-occurrence Tracking

```python
# During parsing of: "Dogs bark and cats meow"
engine.track_co_occurrence(["dog", "cat"])
# Increments: co_occurrence[(cat, dog)] += 1

# After multiple statements mention dogs and wolves together:
co_occurrence[(dog, wolf)] = 5

# During next background_discovery:
# Finds high co-occurrence → suggests link or creates similar_to
```

### Detecting Lonely Neurons

```python
# Entities in knowledge graph with few connections
loom.add_fact("xylophone", "is", "instrument")
# But no other facts about xylophone

# run_background_discovery finds:
# xylophone has only 1 connection
# Returns DiscoveredPattern with pattern_type="lonely"
# Suggests to curiosity: "What properties does xylophone have?"
```

### Analogy Discovery

```python
# If knowledge has:
# A: dog is_to mammal :: bird is_to ?
# (bird is to what as dog is to mammal?)

# Discovery scans for analogous structures:
# dog → mammal (is relation)
# bird → animal (is relation)
# Suggests: bird is_to animal (analogy confidence 0.6)
```
