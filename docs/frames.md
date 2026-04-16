# Frames System

## Overview

The frame system provides structured attribute storage for concepts using a two-tier certainty model. Every concept can hold confirmed (definite) and potential (possible) values for typed attributes like color, size, habitat, diet, etc. Bridges between concepts reveal shared attribute values, and category propagation creates emergent concept clusters.

## Key Concepts

**AttributeSlot:** Two-tier value container holding confirmed (definite facts) and potential (possible facts) values. Example: cats.color = {confirmed: {orange}, potential: {white}}.

**Confidence Tiers:**
- **Confirmed:** Facts stated directly ("cats are orange")
- **Potential:** Facts with modal hedging ("cats can be white", "cats might be black")

**Promotion:** When a potential value is later confirmed, it's promoted to the confirmed tier and removed from potential.

**Similarity:** Weighted comparison of concept frames using tier-aware scoring (confirmed weight=1.0, potential=0.5, cross-tier=0.3).

**AttributeBridge:** A connection between two concepts sharing attribute values. Bridges track shared confirmed/potential/cross-tier values and a strength score.

**Category Propagation:** When "subject is category" is learned, similar concepts are queued for category inheritance based on attribute similarity.

**ConceptCluster:** An emergent category grouping similar concepts with shared prototype attributes (values appearing in >50% of members).

## API / Public Interface

### FrameManager

**Initialization:**
- `FrameManager(loom)` - Initialize with a Loom instance

**Frame Lifecycle:**
- `get_or_create_frame(concept)` → ConceptFrame - Get or create a concept's frame
- `on_fact_added(subject, relation, obj, confidence)` - Called by brain.add_fact() to route facts to slots
- `hydrate_from_knowledge()` - Rebuild frames from existing knowledge on startup

**Similarity & Bridges:**
- `compute_similarity(concept_a, concept_b)` → float [0.0-1.0] - Weighted similarity score
- `get_similar_concepts(concept, threshold=0.3)` → List[(concept, similarity)] - Find similar concepts
- `get_bridges_for(concept)` → List[AttributeBridge] - Get all bridges involving a concept

**Category Propagation:**
- `propagate_category(subject, category)` - Queue category propagation for similar concepts
- `apply_pending_propagations()` → List[(subject, relation, obj)] - Apply queued propagations via add_fact()

**Clustering:**
- `update_clusters()` - Recompute clusters from category memberships
- `get_cluster(category)` → ConceptCluster | None - Get cluster for a category
- `get_prototype(category)` → Dict[str, Set[str]] - Get prototype attributes for a category

**Background Cycle:**
- `run_background_cycle()` → List[(subject, relation, obj)] - Called by inference engine; recomputes bridges, updates clusters, applies propagations

**Persistence:**
- `to_dict()` → dict - Serialize frame data to JSON
- `from_dict(data)` - Load frame data from JSON
- `reset()` - Clear all frame data

**Display:**
- `format_frame(concept)` → str - Format frame for display
- `format_bridges(concept=None)` → str - Format bridges for display
- `format_clusters()` → str - Format all clusters for display

## How It Works

**Fact Routing:**
1. Parser extracts (subject, relation, object, confidence)
2. brain.add_fact() calls frame_manager.on_fact_added()
3. FrameManager classifies the relation (e.g., "color", "size", "habitat")
4. For hedged facts (confidence="low"), value goes to potential tier; otherwise confirmed
5. Special handling for "is" (category vs trait), "can be" (modal possibility), comparatives

**Similarity Computation:**
1. For each shared attribute between two frames, compare their slots
2. Score each shared value based on tier overlap (confirmed=1.0, potential=0.5, cross=0.3)
3. Normalize by total possible values
4. Factor in shared categories as bonus (70% attribute, 30% category)
5. Cache similarity unless dirty concepts force recomputation

**Category Propagation:**
1. When new "X is category" fact added, compute similar concepts
2. Queue propagation for similar concepts lacking that category
3. Background cycle applies queued propagations via add_fact() with provenance
4. Provenance marks source as "frame_inference" with similarity score

**Cluster Formation:**
1. Scan all frames for category memberships
2. Group concepts by shared categories (min 2 members)
3. Compute prototype: confirmed values appearing in >50% of members
4. Assign confidence based on member count

## Dependencies

**Imports:**
- dataclasses, typing, time
- brain.Loom (type-checked)
- normalizer.normalize
- grammar.is_adjective
- parser.constants.COLORS

**Imported By:**
- brain.py - Creates FrameManager, calls on_fact_added()
- inference.py - Calls run_background_cycle()

**Relations with Other Systems:**
- **Parser:** Extracts relations; FrameManager routes them to slots
- **Brain:** add_fact() triggers on_fact_added(); FrameManager calls add_fact() for propagations
- **Inference:** Calls background cycle periodically
- **Storage:** Frames serialized/deserialized via to_dict()/from_dict()

## Examples

**Creating and Populating Frames:**
```python
# User says "cats are orange"
parser.parse("cats are orange")
# → (cats, is, orange, high)
brain.add_fact("cats", "is", "orange", confidence="high")
# → FrameManager.on_fact_added("cats", "is", "orange", "high")
# → Classifies as color trait → frame.slots["color"].confirmed.add("orange")

# User says "cats can be white"
parser.parse("cats can be white")
# → (cats, can, be white, high)
brain.add_fact("cats", "can", "be white", confidence="high")
# → FrameManager._handle_can_relation("cats", "be white")
# → Classifies "white" as color → frame.slots["color"].potential.add("white")

# Later: "cats are white" promotes it
brain.add_fact("cats", "is", "white", confidence="high")
# → _fill_slot(..., potential=False)
# → "white" moved from potential to confirmed
```

**Similarity and Bridges:**
```python
# After learning: dogs are orange, dogs can run
#                 tigers are orange, tigers can run
sim = frame_manager.compute_similarity("dogs", "tigers")
# → 0.85 (shared confirmed "orange", shared potential "run", category overlap)

bridges = frame_manager.get_bridges_for("dogs")
# → [AttributeBridge(dogs, tigers, color, confirmed={orange}, strength=1.0)]
```

**Category Propagation:**
```python
# User says "dogs are mammals"
brain.add_fact("dogs", "is", "mammals", confidence="high")
# → FrameManager.propagate_category("dogs", "mammals")
# → Finds similar concepts (e.g., wolves, cats with sim > 0.4)
# → Queues: ("wolves", "is", "mammals", sim=0.7)

# Background cycle applies:
# → brain.add_fact("wolves", "is", "mammals", confidence="medium",
#      provenance={source_type: frame_inference, ...})
```

---

# Structural Extraction Layer

## Overview

The structural extraction layer is a pre-processor that extracts metadata from sentences by recognizing word categories (hedging, temporal, comparative, numbers, purpose, frequency, degree) based on their position in the sentence. Instead of hardcoding 40+ regex patterns, it defines word categories and position rules, then strips modifiers to return clean text + metadata enrichment.

## Key Concepts

**Word Categories:** Vocabularies of modifier words grouped by semantic type (hedging words, temporal phrases, degree words, etc.).

**Position Rules:** Rules that find categories at specific sentence positions (sentence-initial, pre-adjective, post-verb, etc.).

**Extraction Result:** The output structure containing cleaned text and extracted metadata fields (confidence, temporal, frequency, degree, comparison, quantities, purpose, extra_facts).

**Confidence Tiers from Hedging:**
- Low confidence: hedging words/phrases ("maybe", "i think", "it seems")
- High confidence: no hedging modifiers

**Comparison Extraction:** Detects comparative ("bigger than") and superlative ("tallest among") patterns, derives base adjectives, extracts comparison metadata and extra facts.

**Quantity Extraction:** Extracts number+unit pairs ("4 legs", "two eyes") with support for digit and word numbers.

**Extra Facts:** Secondary facts derived from metadata (e.g., comparative "bigger than cats" → extra fact ("dogs", "bigger_than", "cats")).

## API / Public Interface

### StructuralExtractor

**Initialization:**
- `StructuralExtractor()` - Initialize extractor

**Main Interface:**
- `extract(text)` → ExtractionResult - Extract metadata from text and return clean sentence + metadata

**Extraction Methods (called by extract() in sequence):**
- `_strip_fillers(result)` - Remove conversational filler from sentence start
- `_extract_hedging(result)` - Detect hedging markers, set confidence to "low"
- `_extract_temporal(result)` - Extract temporal context (e.g., "yesterday", "in the morning")
- `_extract_frequency(result)` - Extract frequency adverbs (e.g., "always", "sometimes")
- `_extract_degree(result)` - Extract intensity modifiers (e.g., "very", "extremely")
- `_extract_comparison(result)` - Extract comparative/superlative structures
- `_extract_quantities(result)` - Extract number+unit pairs
- `_extract_purpose(result)` - Extract purpose/function phrases (e.g., "used for", "in order to")

**Helpers:**
- `_base_adjective(comparative_or_superlative)` → str - Derive base adjective from -er/-est/-ier/-iest forms

### ExtractionResult

**Fields:**
- `clean_text: str` - Sentence with modifiers stripped
- `original_text: str` - Original input
- `confidence: Optional[str]` - "high", "medium", "low" from hedging
- `temporal: Optional[str]` - Temporal context (e.g., "yesterday")
- `frequency: Optional[str]` - Frequency adverb (e.g., "always")
- `degree: Optional[str]` - Intensity modifier (e.g., "very")
- `comparison: Optional[Dict]` - Comparison metadata with type, adjective, target
- `quantities: List[Dict]` - List of {number, unit} dictionaries
- `purpose: Optional[str]` - Purpose/function
- `extra_facts: List[(subject, relation, object)]` - Additional facts to store

**Properties:**
- `has_metadata` → bool - True if any metadata was extracted

## How It Works

**Pipeline (called in sequence by extract()):**
1. Strip fillers → clean conversational cruft from sentence start
2. Extract hedging → detect uncertainty markers, set confidence="low"
3. Extract temporal → find temporal context and remove from text
4. Extract frequency → find frequency adverbs and remove
5. Extract degree → find intensity modifiers and remove
6. Extract comparison → detect comparative/superlative patterns, derive base adjectives
7. Extract quantities → find number+unit pairs
8. Extract purpose → detect "used for"/"in order to" patterns
9. Final cleanup → normalize whitespace

**Confidence Mapping:**
- Hedging detected → confidence="low"
- No hedging → confidence="high" (implied)

**Comparison Patterns:**
- Comparative: "X is bigger than Y" → base="big", comparative="bigger", type="comparative"
- Superlative: "X is the fastest animal" → base="fast", superlative="fastest", category="animal"
- More/Less: "X is more intelligent than Y" → modifier="more", adjective="intelligent"

**Quantity Extraction:**
- Digit pattern: "have 4 legs" → {number: 4, unit: "legs"}
- Word pattern: "four legs" → {number: 4, unit: "legs"}
- Skips 4-digit numbers (years)

**Extra Facts Generation:**
- Comparative: ("X", "bigger_than", "Y")
- Superlative: ("X", "is", "category") + ("X", "superlative_among", "category")
- Purpose: ("X", "used_for", "purpose")

**Safety Net:**
- If stripping modifiers reduces sentence to <3 words while original had >=3, restore original
- Ensures downstream parser has enough tokens to find subject+verb+object

## Dependencies

**Imports:**
- dataclasses, typing, re

**Imported By:**
- Parser pipeline (before pattern matching)
- brain.py (optional pre-processor step)

**Relations with Other Systems:**
- **Parser:** Takes ExtractionResult.clean_text, routes metadata separately
- **FrameManager:** Extra facts from comparison/purpose extraction may populate slots
- **Brain:** confidence and extra_facts feed into add_fact() provenance

## Examples

**Basic hedging detection:**
```python
extractor = StructuralExtractor()
result = extractor.extract("maybe dogs are bigger than cats")
# result.clean_text = "dogs are big"
# result.confidence = "low"
# result.comparison = {type: "comparative", adjective: "big", target: "cats"}
# result.extra_facts = [("dogs", "bigger_than", "cats")]
```

**Temporal + degree extraction:**
```python
result = extractor.extract("Yesterday, dogs were very fast")
# result.clean_text = "dogs were fast"
# result.temporal = "yesterday"
# result.degree = "very"
```

**Quantity extraction:**
```python
result = extractor.extract("Dogs have four legs")
# result.clean_text = "Dogs have legs"
# result.quantities = [{number: 4, unit: "legs"}]
```

**Purpose extraction:**
```python
result = extractor.extract("Forks are used for eating")
# result.clean_text = "Forks are for eating"
# result.purpose = "eating"
# result.extra_facts = [("Forks", "used_for", "eating")]
```
