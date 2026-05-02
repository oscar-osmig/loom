# Response Composer (`loom/composer.py`)

Generates fluid natural language responses from Loom's knowledge graph.
Pure symbolic — no ML, no embeddings.

## Architecture

The composer is the primary response path for all questions. The unified
query handler (`_check_composer_query` in `parser/base.py`) routes questions
through the composer BEFORE any legacy regex handlers:

```
User question → _check_composer_query → compose_response() → natural paragraph
                     ↓ (if None)
              legacy regex handlers (fallback)
```

## Public API

### `gather_facts(loom, concept, depth=2)`

Collects everything Loom knows about a concept:

- **direct**: facts where concept is subject (`{relation: [objects]}`)
- **inherited**: facts from parent categories (walks up `is` chain)
- **reverse**: facts where concept is object
- **parents**: parent categories
- **children**: instances of this concept
- **confidence**: per-fact confidence level
- **agreement**: per-fact consensus count (how many users agree)

Resolves singular/plural via `_resolve_concept()` (tries "dog"→"dogs"→"dog").

### `compose_response(loom, question_type, concept, ...)`

Routes to specific composers by question type:

| Type | Handles | Example output |
|------|---------|---------------|
| `what_is` | "what is X?" | "Elephant is largest animal and mammal. It has trunk and tusks." |
| `can` | "can X do Y?" | "Yes, brain can process information — and also control the body." |
| `why` | "why does X Y?" | "Because dogs is mammal; mammal has fur; therefore dogs has fur." |
| `where` | "where is X?" | "Whale is found in aquatic and ocean." |
| `has` | "what does X have?" | "Elephant has trunk and tusks." |
| `describe` | "tell me about X" | Full multi-sentence description with varied templates |
| `general` | any relation | "Rain causes wet ground." |

### `acknowledge_fact(subject, relation, obj, original_text)`

Varied acknowledgments: "Noted —", "I see,", "Understood.", "I'll remember that:",
"Good to know.", "Interesting —". Template picked by deterministic hash.

### `trace_reasoning(loom, subject, relation, obj)`

Follows multi-hop inheritance chains and returns the reasoning steps.

## Template Variation

Composers use `_pick_template(loom, seed, templates, labels)` which factors
in feedback scores from `StyleLearner`. Templates with positive feedback
are boosted; negative feedback demotes them.

## Plural-Aware Grammar

`_compose_describe` detects plural subjects and uses "have"/"are" instead
of "has"/"is". `_is_plural()` checks word endings and common irregular plurals.

## Deduplication

`_collect_from_rels()` deduplicates by substring matching — if "fish" and
"fresh fish" both appear, only the more specific one is kept.

## Consensus Data

`gather_facts()` pulls `agreement_count` and `agreed_by` from MongoDB.
Future: facts with higher agreement could be prioritized in responses.

## "I Don't Know" Responses

When all available facts for a concept are low-confidence, the composer returns an honest "I don't know" response instead of presenting unreliable information as truth.

**`_check_knowledge_sufficiency()`** evaluates whether the gathered facts are reliable enough to compose a response. It returns an IDK response only when ALL facts for the concept have low confidence — if any fact is medium or high confidence, the composer proceeds normally.

**`_IDK_TEMPLATES`** provides 4 varied templates for IDK responses:
1. "I don't have confident information about {concept} yet."
2. "I'm not sure enough about {concept} to give a reliable answer."
3. "My knowledge of {concept} is still too uncertain — teach me more?"
4. "I don't know enough about {concept} to say with confidence."

Template selection is **deterministic via MD5 hash** of the concept name. This means the same concept always produces the same IDK phrasing, avoiding inconsistency across repeated queries while still varying across different concepts.

## Unified Query Handler

`_check_composer_query` in `parser/base.py` handles:
- Strips articles ("the", "a", "an") from subjects before lookup
- Resolves "what is X", "where do X live", "can X do Y", "what can X do",
  "what does X eat/have/cause", "does X have Y"
- Falls through to legacy handlers only when composer returns None
