# Activation Network

## Overview

The ActivationNetwork class (`loom/activation.py`) implements Collins & Loftus spreading activation—a model of how concepts activate and spread through knowledge networks. When a concept is mentioned, activation spreads to connected nodes with decay over time. Co-activation (multiple sources activating the same node) signals meaningful implicit connections.

## Key Concepts

- **Activation Level**: Numeric value (0 to max_activation, default 2.0) representing how "hot" a concept is
- **Spreading**: Activation propagates along knowledge graph edges, diminishing with distance and edge weight
- **Decay**: All activations decay over time unless renewed, modeling attention drift
- **Co-activation**: A node receiving activation from multiple sources suggests implicit connection
- **Priming**: Concepts stay in a priming window after activation, making them more accessible
- **Topic Concepts**: Domain-specific concepts get extended priming window (default 120s vs 30s)
- **Concept Assemblies**: Clusters of concepts that frequently co-activate together, like Hebbian cell assemblies

## API / Public Interface

### Core Activation

- `activate(node: str, amount: float = 1.0, source: str = None)` → `None`
  - Activate a single node by a given amount (capped at max_activation)
  - `source` parameter tracks which node caused the activation (for co-activation detection)

- `spread(knowledge_graph: Dict[str, Dict[str, List[str]]], connection_weights: Dict = None)` → `None`
  - Propagate activation from all currently active nodes to their connected neighbors
  - Respects connection weights if provided: spread_amount = level × spread_factor × weight

- `decay()` → `None`
  - Reduce all activations by decay_rate (default 0.12 per cycle)
  - Remove nodes with activation below 0.01 threshold

### Querying Activation State

- `get_activation(node: str)` → `float`
  - Get current activation level of a node

- `get_top_activated(limit: int = 10)` → `List[Tuple[str, float]]`
  - Get the most activated nodes, sorted by activation level

- `get_primed_nodes()` → `List[str]`
  - Get all currently primed nodes (within priming window or topic window)

- `is_primed(node: str)` → `bool`
  - Check if a node is currently primed (within activation time window)
  - Topic concepts use extended priming window; others use standard window

### Co-Activation Detection

- `find_coactivated(min_sources: int = 2, min_activation: float = 0.3)` → `List[Tuple[str, float, Set[str]]]`
  - Find nodes receiving activation from multiple sources
  - Returns list of `(node, activation_level, source_set)` tuples sorted by activation level (highest first)
  - Candidates for new implicit connections

- `suggest_connections(subject: str, obj: str, knowledge_graph: Dict)` → `List[Tuple[str, str]]`
  - Suggest potential new connections based on co-activation patterns
  - Both subject and object activate intermediate node → suggests implicit relationship
  - Returns list of `(intermediate_node, suggested_relation)` tuples

### Concept Assemblies

- `track_coactivation(nodes: List[str])` → `None`
  - Record that these nodes co-activated together
  - Increments co-activation count for each node pair

- `form_assemblies(min_coactivation: int = 3)` → `List[Set[str]]`
  - Identify frequently co-activated concept clusters (min_coactivation count threshold)
  - Returns list of newly formed assemblies (sets of nodes)

- `get_assembly_for(concept: str)` → `Optional[Set[str]]`
  - Get the assembly that contains a concept, if any

- `activate_assembly(concept: str, amount: float = 0.3)` → `None`
  - When a concept activates, also activate its assembly members (chunking effect)

### Topic & Priming Management

- `set_topic(concepts: List[str])` → `None`
  - Mark a set of concepts as topic-related (get extended priming window)
  - Also immediately activates all topic concepts

- `add_topic_concept(concept: str)` → `None`
  - Add a single concept to the topic set

### Main Processing Entrypoint

- `process_input(entities: List[str], knowledge_graph: Dict, connection_weights: Dict = None)` → `List[Tuple[str, float, Set[str]]]`
  - Main entry point for processing new input
  - Decays existing activations → activates input entities → spreads (2 rounds) → finds co-activated nodes
  - Also tracks co-activation for assembly formation
  - Returns co-activated nodes (candidates for new connections)

### State & Debugging

- `get_state()` → `Dict`
  - Return full internal state: activations, sources, primed nodes, top activated, assemblies, topic concepts
  - Useful for debugging and visualization

- `clear()` → `None`
  - Clear all activations and timing data (reset network)

## How It Works

### Spreading Activation Step-by-Step

1. **Activation**: When a concept is mentioned, `activate(node)` sets its level and records current time
2. **Spread Phase**: `spread()` iterates over all active nodes (above threshold)
   - For each outgoing edge: `spread_amount = current_level × spread_factor × edge_weight`
   - Accumulate spread amounts to target nodes
   - Apply new activations and track sources
3. **Decay Phase**: `decay()` multiplies all levels by `(1 - decay_rate)`, removes near-zero
4. **Repeat**: Multiple spread rounds deepen the cascade

Example: If A activates (level 1.0) with 2 neighbors B, C and spread_factor=0.5:
- Spread to B: 1.0 × 0.5 = 0.5
- Spread to C: 1.0 × 0.5 = 0.5
- After decay (rate=0.12): A→0.88, B→0.44, C→0.44

### Co-Activation Detection

When a node receives activation from multiple independent sources, it signals an implicit connection:

```
Subject: dog → activates [animal, mammal, tail]
Object: puppy → activates [animal, young, cute]
Shared: animal

Conclusion: dog and puppy are implicitly related through "animal" category
```

### Concept Assemblies (Hebbian)

Tracks pairwise co-activation counts. When pairs co-activate frequently (≥min_coactivation times), they form assemblies:

1. Identify strong pairs (count ≥ threshold)
2. BFS to find connected components
3. Each component becomes an assembly
4. Activating one member primes others (chunking effect)

### Priming Window

Nodes stay in the activation window for a configurable time (default 30s, or 120s for topic concepts):
- Recently activated concepts are faster to retrieve
- Longer window keeps conversation context active
- Topic concepts (set via `set_topic()`) stay primed longer

## Dependencies

### Imports
- `time` — Track activation timestamps for priming
- `collections.defaultdict` — Efficient multi-value mappings

### What Imports ActivationNetwork
- `brain.py` — Loom creates a network instance and calls process_input during fact processing
- `inference.py` — Inference engine uses spread/find_coactivated during immediate processing

## Examples

### Basic Activation & Spreading

```python
from loom.activation import ActivationNetwork

# Initialize with default parameters
network = ActivationNetwork(decay_rate=0.12, spread_factor=0.5)

# Knowledge graph: dog -> has/[tail, fur], dog -> is/[animal], animal -> needs/[food]
knowledge = {
    "dog": {"has": ["tail", "fur"], "is": ["animal"]},
    "animal": {"needs": ["food"]}
}

# Activate "dog"
network.activate("dog", amount=1.0)

# Spread activation to neighbors
network.spread(knowledge)

# Check what activated
print(network.get_top_activated(3))
# → [("dog", 0.88), ("tail", 0.44), ("fur", 0.44)] (after decay)

# Check what's primed
print(network.get_primed_nodes())
# → ["dog", "tail", "fur"] (within 30s window)
```

### Co-Activation Detection

```python
# Full process_input: decay → activate → spread → find co-activated
entities = ["dog", "puppy"]
coactivated = network.process_input(entities, knowledge)

print(coactivated)
# → [("animal", 1.0, {"dog", "puppy"})]
# Suggests: dog and puppy both activate "animal" → implicit connection
```

### Suggesting New Connections

```python
suggestions = network.suggest_connections("dog", "puppy", knowledge)
print(suggestions)
# → [("animal", "shares_category")]
# Suggests: dog and puppy share a category through "animal"
```

### Topic Priming

```python
# Set conversation topic to "animals"
network.set_topic(["dog", "cat", "bird"])

# These topic concepts now stay primed for 120s instead of 30s
print(network.is_primed("dog"))  # True for 2 minutes
```

### Concept Assemblies

```python
# Simulate repeated co-activation of related concepts
for _ in range(3):
    network.track_coactivation(["dog", "puppy", "bark"])
    network.track_coactivation(["dog", "tail", "wag"])

# Form assemblies from strong pairs
assemblies = network.form_assemblies(min_coactivation=3)
print(assemblies)
# → [{dog, puppy, bark}, {dog, tail, wag}]

# When "dog" activates, its assembly members auto-activate
network.activate_assembly("dog", amount=0.3)
print(network.get_activation("puppy"))  # > 0 (inherited from assembly)
```
