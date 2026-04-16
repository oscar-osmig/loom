# Processing & Training

## Overview

Three modules work together to enable Hebbian learning, sentence simplification, and knowledge pack training:

1. **HebbianMixin** (`processing.py`) — Connection weight management (strengthen, weaken, decay)
2. **ProcessingMixin** (`processing.py`) — Text processing with spreading activation and paragraph handling
3. **TrainingMixin** + **Trainer** (`training.py`, `trainer.py`) — Knowledge pack loading and batch training

Hebbian learning follows the principle "cells that fire together wire together": connections strengthen with co-activation and weaken from disuse.

## Key Concepts

### Hebbian Connection Weights
- **Initial weight**: 1.0 for new connections
- **Strengthening**: +0.2 per co-activation (max 5.0)
- **Decay**: -0.05 per unused cycle (pruned at < 0.1)
- **Tracking**: `connection_weights[(subject, relation, object)] = weight`
- **Timestamps**: `connection_times[(subject, relation, object)] = time.time()` for decay calculation

Weights > 1.5 indicate strong, reliable facts. Use `show_weights` command to view.

### Activation-Enhanced Processing
When input is processed, the activation network spreads from mentioned entities to find related knowledge, then strengthens connections between co-activated concepts:

1. Extract entities from input
2. Activate them in the network
3. Find co-activated nodes (multiple sources activating same node)
4. Strengthen connections between co-activated pairs

### Advanced Simplification
Complex sentences are broken into atomic facts before parsing:

**Input:**
```
Native to Africa and known for long necks, giraffes have spotted fur and eat leaves high in trees.
```

**Simplified output:**
```
- giraffes is native to Africa
- giraffes have long necks
- giraffes have spotted fur
- giraffes eat leaves
- giraffes live in trees
```

Then each statement is parsed independently, maintaining coherence through activation.

### Paragraph Processing
Multi-sentence text is processed chunk-by-chunk with:
- Theme extraction (main topic from first sentence)
- Sentence-level splitting
- Complex sentence simplification
- Pronoun resolution (last_subject = theme)
- Cross-chunk entity linking (strengthen connections between consecutive chunks)
- Activation decay between chunks

### Knowledge Packs
Pre-built fact collections for quick bootstrapping:
- **animals** — 40+ facts about dogs, cats, birds, fish
- **nature** — Weather cycles, plant properties, water
- **science** — Physics, planets, elements, biology
- **geography** — Continents, countries, landmarks

Each pack is a dict of (subject, relation, object) tuples. Load via `train("animals")` or `loom.train("pack_name")`.

## API / Public Interface

### HebbianMixin

```python
# Connection strength query
get_connection_weight(subject: str, relation: str, obj: str) -> float

# Strength modification
strengthen_connection(subject: str, relation: str, obj: str, amount: float = STRENGTHENING_FACTOR)
weaken_connection(subject: str, relation: str, obj: str, amount: float = DECAY_FACTOR)

# Bulk decay (synaptic pruning)
decay_all_connections(elapsed_threshold: float = 60.0)
# Weakens connections not activated in last N seconds

# Queries
get_strong_connections(threshold: float = 2.0) -> List[Tuple[str, str, str, float]]
show_weights(min_weight: float = 1.5)  # Display to user
```

### ProcessingMixin

```python
# Single-statement processing with activation
process_with_activation(text: str, already_simplified: bool = False) -> str
# Returns response; also activates entities and strengthens connections

# Paragraph/multi-sentence processing
process_paragraph(text: str) -> Dict
# Returns: {
#     chunks_processed: int,
#     facts_added: int,
#     connections_made: int,
#     theme: str,
#     responses: List[str]
# }

# Auto-detection: single vs paragraph
process_text(text: str) -> str
# Detects sentence count, calls process_paragraph or process_with_activation

# Display activation state
show_activation()  # Print primed nodes and top activated concepts

# Helper
_extract_entities(text: str) -> List[str]  # Extract & normalize entity names
_map_discourse_to_relation(discourse_type: str) -> str  # Map RST to relations
```

### TrainingMixin

```python
# Main entry point (polymorphic)
train(source) -> int
# source can be:
#   str: pack name ("animals") or file path ("data.json")
#   list of tuples: [("dogs", "is", "animals"), ...]
#   list of dicts: [{"subject": "dogs", "relation": "is", "object": "animals"}, ...]
#   list of strings: ["dogs are animals", ...]

# Format-specific training
train_facts(facts: list) -> int  # [(subj, rel, obj), ...]
train_dicts(facts: list) -> int  # [{"subject": "...", "relation": "...", "object": "..."}, ...]
train_statements(statements: list, silent: bool = True) -> int  # ["dogs are animals", ...]
train_batch(facts: list, batch_size: int = 100) -> int  # Efficient bulk loading

# Query available packs
available_packs() -> list  # ["animals", "nature", "science", "geography"]
```

### Trainer Module

```python
# Pack-based training
train(loom, pack_name: str) -> tuple[int, str]
# Returns (count_added, message)

# File loading
train_from_file(loom, filepath: str) -> tuple[int, str]
# Supports .json and .txt formats

# Pack queries
list_packs() -> list[str]  # Available pack names
get_pack_info(pack_name: str) -> str  # Display pack contents
```

## How It Works

### Hebbian Strengthening Flow

```
Input: "Dogs are animals. Cats are animals."

Parse first statement:
├─ add_fact("dogs", "is", "animals")
├─ Extract entities: ["dogs", "animals"]
├─ Activate: dogs (1.0), animals (0.8)
└─ Co-activated: strengthen_connection("dogs", "related_to", "animals")
    └─ connection_weights[(dogs, related_to, animals)] = 1.0 + 0.2 = 1.2
    └─ connection_times[(dogs, related_to, animals)] = now

Parse second statement:
├─ add_fact("cats", "is", "animals")
├─ Extract entities: ["cats", "animals"]
├─ Activate: cats (1.0), animals (0.8)
└─ Co-activated: strengthen_connection("cats", "related_to", "animals")
    └─ connection_weights[(cats, related_to, animals)] = 1.2

Background decay (every 60s):
├─ For connections not activated for > 60s
├─ weaken_connection(...)
│   └─ weight = max(weight - 0.05, 0.1)
└─ Prune if weight ≤ 0.1
```

### Advanced Simplification Example

```python
text = "Native to Africa and known for long necks, giraffes have spotted fur."

# ProcessingMixin.process_paragraph() calls AdvancedSimplifier.simplify()
simplified = advanced_simplifier.simplify(text)
# Returns:
# [
#   "giraffes is native to Africa",
#   "giraffes have long necks",
#   "giraffes have spotted fur"
# ]

# Each simplified statement is parsed independently
for stmt in simplified:
    parser.parse(stmt)  # "giraffes is native to Africa" → add_fact(...)
```

The simplifier detects:
- Appositives: "giraffes, which live in Africa" → separate facts
- Parallel structures: "have X, Y, and Z" → three separate "have" facts
- Conjunctions: "are A and B" → two separate "is" facts

### Paragraph Processing with Pronoun Resolution

```python
text = """
Giraffes are tall animals. They have long necks.
They live in Africa. They eat leaves.
"""

# process_paragraph detects theme: "giraffes"
# For each sentence:
# - Set last_subject = "giraffes" for pronoun resolution
# - "They" resolves to "giraffes"
# - Simplify complex sentences
# - Parse: "giraffes have long necks", "giraffes live in Africa", etc.
```

Parser resolves pronouns using `last_subject` (set by ProcessingMixin).

### Knowledge Pack Training

```python
# Built-in pack loading
loom.train("animals")
# Calls trainer.train(loom, "animals")
# Retrieves KNOWLEDGE_PACKS["animals"]
# For each (subject, relation, object) in pack:
#   - Check if fact already exists (case-insensitive)
#   - Call loom.add_fact(subject, relation, object)
#   - Count += 1
# Returns count_added

# Custom file
loom.train("custom_facts.json")
# Detects .json extension
# Calls trainer.train_from_file(loom, path)
# Loads JSON array: [{"subject": "X", "relation": "is", "object": "Y"}, ...]
# Or text file: subject|relation|object (one per line)
```

### Batch Training (MongoDB optimization)

```python
loom.train_batch(large_fact_list, batch_size=100)
# Splits into batches of 100
# Processes each batch via train_facts()
# Reduces MongoDB round-trips
```

### Activation-Enhanced Connection Discovery

```python
# Input: "Dogs and cats both like food and toys."
input_text = "dogs and cats like food toys"

process_with_activation(input_text):
├─ Extract entities: ["dogs", "cats", "food", "toys"]
├─ Activation.process_input(entities, knowledge, weights)
│   ├─ Activate "dogs" (1.0)
│   ├─ Activate "cats" (1.0)
│   ├─ Spread to related: "animals", "pets", "mammals"
│   └─ Detect co-activation:
│       ├─ "animals" activated from dogs (0.5) and cats (0.5)
│       └─ Co-activation detected: strengthen_connection("dogs", "related_to", "cats")
├─ Parse parsed statements with these strengths boosted
└─ Return response
```

## Dependencies

**Imports from:**
- `normalizer.normalize` — entity name normalization
- `simplifier.SentenceSimplifier` — basic sentence simplification
- `advanced_simplifier.AdvancedSimplifier` — complex sentence decomposition
- `brain.Loom` — parent knowledge system
- Standard lib: `time`, `re`, `typing`

**Used by:**
- CLI: `train`, `train <pack>`, `train <file>`, `weights`, `verbose`
- Web API: `POST /api/upload-training`
- Inference loop: periodic `decay_all_connections()`
- Parser: calls strengthen_connection after adding facts

**Data sources:**
- `trainer.KNOWLEDGE_PACKS` — pre-built training data
- `self.knowledge` — current knowledge graph for entity extraction
- `self.connection_weights` — Hebbian weights
- `self.connection_times` — last activation time per connection
- `self.activation` — spreading activation network

## Examples

### Training from a Pack

```python
from loom import Loom

loom = Loom("learning_example")

# Load the animals pack (40 facts)
count = loom.train("animals")
print(f"Loaded {count} facts")

# Query what was learned
print(loom.get("dogs", "is"))      # ["mammals"]
print(loom.get("dogs", "has"))     # ["four legs", "fur", "a tail"]
print(loom.get("dogs", "can"))     # ["bark", "run", "swim"]
```

### Training from Custom File

```python
# JSON file: custom_facts.json
# [
#   {"subject": "kiwi", "relation": "is", "object": "bird"},
#   {"subject": "kiwi", "relation": "lives_in", "object": "new zealand"},
#   {"subject": "kiwi", "relation": "cannot", "object": "fly"}
# ]

loom.train("custom_facts.json")

# Or text format: custom_facts.txt
# kiwi | is | bird
# kiwi | lives_in | new zealand
# kiwi | cannot | fly

loom.train("custom_facts.txt")
```

### Monitoring Connection Weights

```python
loom.add_fact("dogs", "is", "animals")
loom.add_fact("cats", "is", "animals")
loom.add_fact("dogs", "can", "bark")

# Show strong connections (weight > 1.5)
loom.show_weights(min_weight=1.5)
# +-- Connection Weights -------------------------+
# |  dogs ~is~> animals: 1.20
# |  cats ~is~> animals: 1.20
# +-----------------------------------------------+

# Query a specific connection
weight = loom.get_connection_weight("dogs", "is", "animals")
# Returns: 1.2
```

### Processing Paragraph with Theme Extraction

```python
text = """
Dolphins are marine mammals. They live in oceans and seas.
They communicate using clicks and whistles. They eat fish and squid.
They are highly intelligent and social.
"""

result = loom.process_paragraph(text)
print(f"Theme: {result['theme']}")  # "dolphins"
print(f"Chunks processed: {result['chunks_processed']}")  # 5
print(f"Facts added: {result['facts_added']}")  # ~6
print(f"Connections made: {result['connections_made']}")  # Cross-chunk links
```

### Activation-Enhanced Learning

```python
# Tell Loom about dolphins and whales
text = "Dolphins are mammals. Whales are mammals. Both are intelligent."

loom.process_with_activation(text)
# Activation flow:
# 1. Extract: [dolphins, whales, mammals, intelligent]
# 2. Activate dolphins, whales → spread to mammals
# 3. Find mammals co-activated from dolphins + whales
# 4. Strengthen: dolphins ~related_to~> whales
# 5. Query weights: connection_weights[(dolphins, related_to, whales)] > 1.0
```

### Batch Training (Large Dataset)

```python
large_facts = [
    ("entity_1", "relation", "entity_2"),
    ("entity_3", "relation", "entity_4"),
    # ... 10,000 facts
]

# Efficient bulk load (reduced MongoDB round-trips)
count = loom.train_batch(large_facts, batch_size=500)
print(f"Loaded {count} facts in batches of 500")
```

### Training from Natural Language

```python
statements = [
    "dogs are animals",
    "cats can meow",
    "birds have feathers",
    "fish live in water"
]

count = loom.train(statements)  # Auto-detects list of strings
print(f"Processed {count} statements")

# Each statement goes through parser:
# "dogs are animals" → add_fact("dogs", "is", "animals")
```

## CLI Integration

```bash
# Load a pack
> train animals
Loaded 40 facts from 'animals' pack.

# Load from file
> train custom_facts.json
Loaded 15 facts from 'custom_facts.json'.

# View strong connections
> weights
  +-- Connection Weights -------------------------+
  |  dogs ~is~> animals: 1.20
  |  ...
  +-----------------------------------------------+

# View activation state
> show activation
  +-- Activation State ---------------------------+
  |  Primed nodes: 3
  |    - dogs: 0.85
  |    - animals: 0.72
  |  Top activated:
  |    - mammals: 0.45
  |    - pets: 0.38
  +-----------------------------------------------+
```
