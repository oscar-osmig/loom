# Rule Engine

## Overview

The rule engine implements forward-chaining logic for learning and firing explicit rules. Rules are learned from "if X then Y" statements and conversational patterns, stored with a status lifecycle (CANDIDATE → ACTIVE → SUSPENDED/REJECTED), and fired to derive new facts when their premises match the knowledge base.

**Key Principle:** Rules express generalizable knowledge independent of ML/embeddings. Example: "if X is mammal and X has live_birth then X is placental_mammal".

## Key Concepts

**Rule:** A logical statement IF premises THEN conclusion, with support count, confidence, status, and provenance.

**RuleStatus Lifecycle:**
- **CANDIDATE:** Newly learned, awaiting validation
- **ACTIVE:** Confirmed valid, actively fires to derive new facts
- **SUSPENDED:** Disabled due to high false-positive rate
- **REJECTED:** User explicitly rejected; never fires

**RulePremise:** A single condition (subject_var, relation, object_var) where variables start with "?" (e.g., "?X", "?Y") and values are constants (e.g., "mammal").

**RuleConclusion:** The conclusion triple (subject_var, relation, object_var) with same variable/constant syntax.

**Variable Binding:** When a rule's premises match knowledge, variables bind to concrete entities. Example: if "?X is mammal" and "?X has fur" both match for entity "dog", bindings = {"?X": "dog"}.

**Forward Chaining:** Iteratively find all rule premises that match, apply bindings to conclusion, add derived facts, repeat until fixed point (no new facts).

**Quality Gates:** Multi-stage validation preventing low-quality rules:
- Minimum support (3+ examples)
- Minimum confidence (60%)
- Minimum lift (1.2x better than random)
- Maximum false-positive rate (15%)
- Structural validity (bounded premises, no unbound variables)

**Apriori-Style Pattern Mining:** Automatically learn rules from category-property associations in knowledge base.

## API / Public Interface

### Rule

**Initialization:**
- `Rule(rule_id, premises, conclusion, support_count=0, confidence=0.5, status=CANDIDATE, ...)` - Create rule

**Matching & Inference:**
- `matches_premises(knowledge, bindings=None)` → List[dict] - Find all variable bindings satisfying premises
- `apply_conclusion(bindings)` → (subject, relation, object) - Apply bindings to get concrete fact
- `to_dict()` → dict - Serialize for storage
- `from_dict(d)` → Rule - Deserialize from storage

**Properties:**
- `status: RuleStatus` - Current status (CANDIDATE, ACTIVE, SUSPENDED, REJECTED)
- `support_count: int` - How many examples support this rule
- `confidence: float` - Confidence in rule (0.0–1.0)
- `fire_count: int` - How many times rule has fired
- `last_fired: float` - Timestamp of last firing

### RuleMemory

**Initialization:**
- `RuleMemory(loom, use_mongo=False, storage_path=None)` - Initialize with Loom instance

**Rule Storage:**
- `add_rule(rule)` → str - Add rule, return rule_id
- `get_rule(rule_id)` → Rule | None
- `get_all_rules(status=None)` → List[Rule]
- `get_active_rules()` → List[Rule]
- `get_candidate_rules()` → List[Rule]

**Rule Lifecycle:**
- `confirm_rule(rule_id)` - Set status to ACTIVE
- `reject_rule(rule_id)` - Set status to REJECTED
- `update_rule_status(rule_id, status)`
- `increment_support(rule_id)` - Increment support count; auto-promote CANDIDATE with support >= 3

**Rule Learning:**
- `learn_from_if_then(text)` → Rule | None - Parse "if X then Y" statement and create rule
- `create_rule_from_pattern(premises, conclusion, provenance)` → Rule - Create rule from observed pattern
- `learn_rules_from_patterns()` → List[Rule] - Mine rules from category-property associations

**Rule Matching:**
- `find_matching_rules(knowledge)` → List[(rule, bindings_list)] - Find rules whose premises match

**Persistence:**
- `_load_from_json()` - Load rules from JSON file
- `_load_from_mongo()` - Load rules from MongoDB
- `_save_to_json()` - Save rules to JSON file

**Statistics:**
- `get_stats()` → dict - Return counts of rules by status

### RuleEngine

**Initialization:**
- `RuleEngine(loom, rule_memory)` - Initialize with Loom and RuleMemory instances

**Inference:**
- `run_forward_chain(max_iterations=10)` → List[dict] - Run forward chaining to fixed point
- `_forward_chain_step()` → List[dict] - Execute one iteration of forward chaining
- `check_rule_applicability(rule)` → List[dict] - Check where rule could apply without firing

**Forward Chaining Internals:**
- Finds all matching rules (premises satisfied)
- For each rule match and binding, applies bindings to conclusion
- Skips if fact already exists or would create infinite loop
- Adds derived fact with medium confidence and rule provenance

## How It Works

**Rule Learning from If-Then Statements:**
1. Parser recognizes "if ... then ..." pattern
2. RuleMemory._parse_simple_statement() extracts premises and conclusion
3. Single-letter variables (X, Y) converted to "?X", "?Y"
4. Creates Rule with status=CANDIDATE, confidence=0.7
5. Rule added to RuleMemory with provenance tracking

**Pattern-Based Rule Learning (Apriori):**
1. Scan knowledge base for category-property associations
2. For each category with min 3 members, count property occurrences
3. Compute support (count) and confidence (% of members with property)
4. Filter by MIN_CONFIDENCE (60%) and MIN_SUPPORT (3)
5. Create rule: "if ?X is category then ?X has property"
6. Rules marked CANDIDATE; need confirmation to become ACTIVE

**Variable Binding & Premise Matching:**
1. For each premise in rule, find matching (subject, relation, object) in knowledge
2. If subject is variable ("?X"), bind to all matching entities
3. If subject is constant ("mammal"), only match that entity
4. Same for object; handle singular/plural variations
5. Recursively process next premise with accumulated bindings
6. Return all valid binding combinations

**Forward Chaining:**
1. Iterate until max iterations or fixed point:
   a. For each ACTIVE rule, find matching bindings
   b. For each binding, apply to conclusion to get concrete fact
   c. Skip if fact exists or exact derivation already fired this cycle
   d. Add fact via add_fact() with rule provenance
   e. Update rule statistics (fire_count, last_fired)
2. Return all derived facts

**Quality Gates:**
- **Structure:** Rule must have premises, bounded variables, all conclusion vars bound by premises
- **Support:** Positive matches must be >= MIN_SUPPORT (3)
- **Confidence:** (positives / (positives + negatives)) >= MIN_CONFIDENCE (60%)
- **False Positives:** negatives / total <= MAX_FALSE_POSITIVE_RATE (15%)
- **Triviality:** Conclusion base rate must be < 80% (rule must be informative)

**Singular/Plural Matching:**
- "bird" matches "birds", "mammal" matches "mammals"
- "-es" plurals: "fish" / "fishes"
- "-ies" plurals: "fly" / "flies"

## Dependencies

**Imports:**
- dataclasses, typing, time, enum, logging, re, json
- brain.Loom (type-checked)

**Imported By:**
- brain.py - Creates RuleMemory and RuleEngine
- inference.py - May call forward_chain() periodically

**Relations with Other Systems:**
- **Brain:** Rules fire via loom.add_fact() with rule provenance
- **Knowledge:** Rules match against and derive facts in loom.knowledge
- **Storage:** Rules persisted to JSON or MongoDB; loaded on startup
- **Inference:** Background inference may trigger forward chaining

## Examples

**Learning from explicit if-then statement:**
```python
rule_memory = RuleMemory(loom)
rule = rule_memory.learn_from_if_then("if X is mammal then X has fur")
# Creates:
#   premises = [RulePremise("?X", "is", "mammal")]
#   conclusion = RuleConclusion("?X", "has", "fur")
#   status = CANDIDATE
#   confidence = 0.7
```

**Pattern-based rule learning:**
```python
# Assuming knowledge has: dogs is animals, dogs has fur
#                       cats is animals, cats has fur
#                       birds is animals
rule_engine.learn_rules_from_patterns()
# Discovers: 2 animals have fur (confidence=100%)
# Creates rule: "if ?X is animals then ?X has fur"
```

**Forward chaining execution:**
```python
# Knowledge: dog is mammal, cat is mammal, dog has fur, cat has fur
# Rule: if ?X is mammal then ?X has fur (ACTIVE)

bindings = rule.matches_premises(knowledge)
# Returns: [{"?X": "dog"}, {"?X": "cat"}]

# Applied to conclusion:
# ("dog", "has", "fur") - already exists, skip
# ("cat", "has", "fur") - already exists, skip
# No new facts derived
```

**Rule with multiple premises:**
```python
rule = Rule(
    rule_id="rule_1",
    premises=[
        RulePremise("?X", "is", "mammal"),
        RulePremise("?X", "has", "live_birth"),
    ],
    conclusion=RuleConclusion("?X", "is", "placental_mammal"),
    status=RuleStatus.ACTIVE,
)

# Matching:
# Knowledge: dog is mammal, dog has live_birth
#            kangaroo is mammal, kangaroo has pouch
# 
# Bindings: [{"?X": "dog"}]  (only dog matches both premises)
# Derived fact: ("dog", "is", "placental_mammal")
```

**Rule promotion by support:**
```python
rule = Rule(..., status=RuleStatus.CANDIDATE, support_count=0)
rule_memory.add_rule(rule)

# Later, same pattern observed again:
rule_memory.increment_support(rule.rule_id)  # count = 1
rule_memory.increment_support(rule.rule_id)  # count = 2
rule_memory.increment_support(rule.rule_id)  # count = 3
# Auto-promoted to ACTIVE since support >= 3
```