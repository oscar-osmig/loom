# Curiosity Engine

## Overview

The curiosity engine generates high-value questions to strengthen the knowledge graph by identifying knowledge gaps, contradictions, and opportunities for learning. It works in two complementary parts:

1. **CuriosityNodeManager** — Manages special "?_<topic>" nodes representing unknown concepts, tracking their lifecycle from creation through exploration to resolution
2. **QuestionGenerator** — Generates prioritized questions from 8 types, scored by expected utility

No direct CLI wiring yet, but the infrastructure is ready for integration into the background reasoning loop.

## Key Concepts

### Curiosity Nodes
When Loom encounters an unknown concept, a `CuriosityNode` is created with a normalized topic name (stored as `?_<topic>` in the knowledge graph):
- **Activation level** (0.0–1.0) — how strongly we want to know about this concept
- **Timeout** — 5 minutes by default; node expires if not resolved
- **Linked facts** — hypotheses generated from similar concepts
- **Lifecycle**: ACTIVE → EXPLORING → HYPOTHESIZING → RESOLVED/EXPIRED

### Question Types & Priorities
Questions are weighted by expected utility (higher = ask first):
- **CONTRADICTION** (10.0) — conflicting facts needing resolution
- **CONFIRM_RULE** (6.0) — verify candidate rules  
- **CONFIRM_INFERENCE** (5.0) — verify inferred facts
- **CHAIN_GAP** (4.0) — missing links in causal chains
- **LOW_CONFIDENCE** (3.0) — strengthen weak facts
- **OPEN_QUESTION** (3.0) — user-stated open questions
- **CAUSAL_ORIGIN** (2.0) — explore what causes things
- **CAUSAL_EFFECT** (2.0) — explore what things cause
- **MISSING_PROPERTY** (1.0) — fill expected properties

### Hypothesis Generation
When exploring a curiosity node, the engine looks at similar/related concepts and generates hypotheses:
```python
# Example: ?_platypus is unknown
# Found related: duck, beaver
# Both have "can_lay_eggs" and "has_fur"
# Hypothesis: platypus can lay eggs (confidence 0.4)
# Hypothesis: platypus has fur (confidence 0.4)
```

## API / Public Interface

### CuriosityNodeManager

```python
# Lifecycle management
create_node(topic: str, context: str = "") -> CuriosityNode
explore_node(topic: str) -> List[str]  # Return related concepts via spreading activation
generate_hypotheses(topic: str) -> List[dict]
resolve_node(topic: str, facts: List[dict] = None) -> bool
resolve_from_knowledge(brain) -> int  # Resolve ACTIVE nodes when brain already has answers
cleanup_expired() -> int

# Queries
get_node(topic: str) -> Optional[CuriosityNode]
get_all_nodes() -> List[CuriosityNode]
get_active_topics() -> List[str]
has_curiosity(topic: str) -> bool
format_curiosity_question(topic: str) -> Optional[str]  # Human-readable question
```

### CuriosityNode (dataclass)

```python
topic: str                     # The unknown concept (no ?_ prefix)
activation: float = 1.0        # How strongly we want to know (0–1)
timeout: float = 300.0         # Seconds before expiry
created_at: float              # Creation timestamp
attempts: int = 0              # How many resolution attempts
linked_facts: List[dict]       # Generated hypotheses
status: CuriosityNodeStatus    # ACTIVE, EXPLORING, etc.
related_concepts: Set[str]     # From spreading activation
status_changed_at: float       # Timestamp of last status transition

# Properties
@property node_name -> str     # Returns "?_<topic>"
@property age -> float         # Seconds since creation
@property is_expired -> bool   # Check if expired

# Methods
decay_activation(rate: float = 0.1)
boost_activation(amount: float = 0.2)
add_hypothesis(relation: str, value: str, confidence: float = 0.5)
get_best_hypothesis() -> Optional[dict]
```

### QuestionGenerator

```python
# Cycle management
run_cycle()                          # Run full question generation
get_next_question() -> Optional[Question]
get_top_questions(n: int = 3) -> List[Question]
mark_asked(question: Question)
mark_answered(question: Question)

# Statistics
get_queue_size() -> int
clear_queue()
format_question_prompt(question: Question) -> str

# Internal (called by run_cycle)
_collect_open_questions() -> List[Question]
_collect_contradiction_questions() -> List[Question]
_collect_chain_gap_questions() -> List[Question]
_collect_inference_questions() -> List[Question]
_collect_low_confidence_questions() -> List[Question]
_collect_missing_property_questions() -> List[Question]
_collect_causal_questions() -> List[Question]
_collect_rule_questions() -> List[Question]
```

### Question (dataclass)

```python
text: str                      # The question text
question_type: QuestionType    # CONTRADICTION, CHAIN_GAP, etc.
priority: float = 0.0          # Computed by _calculate_priority
related_facts: List[dict]      # Context for the question
created_at: float              # When generated
```

## How It Works

### CuriosityNodeManager Flow

1. **Node Creation**: Unknown topic detected → normalize name → create `?_<topic>` node in graph
2. **Exploration**: Spreading activation spreads from topic to find related concepts (substring matching + activation network)
3. **Hypothesis Generation**: Analyze related concepts for common patterns; if 2+ related concepts share a property, create hypothesis with confidence = min(0.9, count × 0.2)
4. **Resolution**: User confirms or provides facts → add them with high confidence → retract curiosity node
5. **Resolution from knowledge**: `resolve_from_knowledge(brain)` scans all ACTIVE nodes and checks whether the brain's knowledge graph already contains answers for their topics. If facts exist, the node is automatically resolved without user interaction.
6. **Cleanup**: Check every 60s; enhanced timeout handling:
   - EXPLORING nodes idle for >10 minutes are reset back to ACTIVE (uses `status_changed_at`)
   - HYPOTHESIZING nodes idle for >30 minutes are reset back to ACTIVE (uses `status_changed_at`)
   - Expired nodes (age > 5min OR attempts >= 5) are removed as before

### QuestionGenerator Flow

1. **Collect**: Run 8 specialized collectors (open questions, contradictions, chain gaps, inferences, low confidence, missing properties, causal, rules)
2. **Score**: Each question gets priority = base_weight + recency_boost + centrality_boost
3. **Rank**: Sort by priority descending; keep top 20
4. **Track**: Mark asked questions to avoid repeats
5. **Cycle**: Run periodically (called from background inference loop)

### Spreading Activation in Curiosity

Uses the Loom activation network to find related concepts:
- Activate the unknown topic with amount=1.0
- Collect all entities with activation > 0.3 threshold
- Deduplicate and return

Entities with overlapping activation sources (co-activation) are more relevant.

## Dependencies

**Imports from:**
- `brain.Loom` — the parent knowledge system
- `time` — for timeouts and lifecycle tracking
- `dataclasses` — for CuriosityNode, Question dataclasses
- `enum` — for CuriosityNodeStatus, QuestionType
- `collections.defaultdict` — for pattern tracking

**Used by:**
- Inference engine background loop (calls `QuestionGenerator.run_cycle()` periodically)
- CLI (potential future integration with `curiosity` or `why` commands)
- Frame system (may use curiosity to inform attribute slot values)

**Data sources:**
- `self.loom.knowledge` — existing facts for hypothesis generation
- `self.loom.activation` — spreading activation network
- `self.loom.storage.get_conflicts()` — conflict tracking
- `self.loom.storage.get_inferred_facts()` — inferred knowledge
- `self.loom.rule_memory` — candidate rules for confirmation

## Examples

### Creating and Resolving a Curiosity Node

```python
# User mentions unknown concept
manager = CuriosityNodeManager(loom)
node = manager.create_node("platypus", context="user asked about platypus")

# Explore related concepts
related = manager.explore_node("platypus")
# Returns: ["duck", "beaver", "mammal", "animal"]

# Generate hypotheses
hypotheses = manager.generate_hypotheses("platypus")
# Returns: [
#   {"subject": "?_platypus", "relation": "can", "object": "lay_eggs", "confidence": 0.4},
#   {"subject": "?_platypus", "relation": "has", "object": "fur", "confidence": 0.4}
# ]

# User provides fact
manager.resolve_node("platypus", facts=[
    {"subject": "platypus", "relation": "is", "object": "mammal"}
])
# Node is removed from knowledge graph and manager
```

### Question Generation

```python
gen = QuestionGenerator(loom)

# Load knowledge with contradictions and gaps
loom.add_fact("birds", "can", "fly")
loom.add_fact("penguin", "is", "bird")
loom.add_fact("penguin", "cannot", "fly")

# Generate questions
gen.run_cycle()

# Get high-priority questions
questions = gen.get_top_questions(3)
# Returns questions like:
# 1. (priority 10.0) "There's a conflict: 'bird can fly' vs 'penguin cannot fly'. Which is correct?"
# 2. (priority 4.0) "What does flight enable in birds?"
# 3. (priority 1.0) "Do penguins have feathers? (Like birds)"
```

### Caching Curiosity Nodes in Parser

When the parser encounters an unknown entity during query handling:
```python
# In some parser handler
unknown_entity = "platypus"
if unknown_entity not in loom.knowledge:
    # Don't just skip — create curiosity node for later exploration
    if hasattr(loom, 'curiosity_manager'):
        loom.curiosity_manager.create_node(
            unknown_entity, 
            context=f"encountered in query: {question_text}"
        )
```

### Checking for Lonely Neurons

Inside `QuestionGenerator._collect_causal_questions()`, the engine ranks entities by centrality (number of relations) and asks about entities with no known causes or effects:

```python
# Find central entities
entity_counts = defaultdict(int)  # relation count per entity
for subject, relations in loom.knowledge.items():
    entity_counts[subject] += len(relations)

central = sorted(entity_counts.items(), reverse=True)[:10]
# Ask: "What effects does <central_entity> have?"
```

This helps keep the knowledge graph fully connected.
