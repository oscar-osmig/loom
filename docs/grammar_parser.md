# Grammar Parser (`loom/grammar_parser.py`)

Recursive descent parser for English sentences. Builds a simple AST and
extracts facts from the tree. Works like a programming-language grammar
checker — deterministic, symbolic, no ML.

## Grammar (simplified BNF)

```
sentence    := clause (conj clause)*
clause      := subject verb_phrase
verb_phrase := [aux] [neg] verb [object] [pp]*
subject     := noun_phrase
object      := noun_phrase
noun_phrase := [det] [adj]* noun [rel_clause]
rel_clause  := ("that" | "which" | "who") verb_phrase
pp          := prep noun_phrase
conj        := "and" | "or" | "but" | ","
```

## What it handles

| Structure | Example | Extraction |
|-----------|---------|------------|
| Simple facts | `"cats are mammals"` | `cats is mammals` |
| Relative clauses | `"cats that have claws can climb trees"` | `cats has claws` + `cats can climb trees` |
| Conjoined subjects | `"cats and dogs are mammals"` | `cats is mammals` + `dogs is mammals` |
| Prepositional phrases | `"whales live in oceans"` | `whales lives_in oceans` |
| Negation | `"birds cannot fly"` | `birds cannot fly` |

## AST Node types

```python
@dataclass
class NounPhrase:
    head: str                                    # main noun
    modifiers: List[str]                         # adjectives
    rel_clause: Optional[Clause]                 # "that/which" clause

@dataclass
class VerbPhrase:
    verb: str
    negated: bool
    obj: Optional[NounPhrase]
    prep_phrases: List[PrepPhrase]

@dataclass
class Clause:
    subject: NounPhrase
    vp: VerbPhrase
    conjoined_subjects: List[NounPhrase]
    conjoined_vps: List[VerbPhrase]

@dataclass
class Sentence:
    clauses: List[Clause]
```

## Public API

### `parse_sentence(text) -> Optional[Sentence]`

Parses into an AST. Returns `None` if parsing fails.

### `parse_and_extract(text) -> List[ExtractedFact]`

Parses and returns extracted facts. Returns empty list on failure.

```python
@dataclass
class ExtractedFact:
    subject: str
    relation: str
    obj: str
    negated: bool
```

## Integration with main parser

Wired into `parser/base.py` as `_check_grammar_parser()`, placed between
`_check_list_learning` and `_check_relation_patterns` in the priority list.

Only attempts parsing if the sentence has:
- A relative clause marker (`that`, `which`, `who` followed by a verb)
- Multiple clauses (commas or `" and "`)

Falls back to the regex handlers if parsing produces fewer than 2 facts.

## Preposition → relation mapping

```python
prep_map = {
    "in": "lives_in" (if verb is live/found) | "located_in",
    "on": "located_on",
    "at": "located_at",
    "with": "has",
    "from": "originates_from",
    "by": "by_agent",
    "for": "used_for",
    "of": "part_of",
}
```

## Known limitations

- **Verb-detection heuristic is fragile** — `_looks_like_verb()` flags any
  word ending in `-s`/`-ed`/`-ing` as a verb, which can miss participial
  nouns ("the tools")
- **Conjoined verb phrases fail** — "birds fly and lay eggs" doesn't extract both
- **Modal + bare verb** — "cannot breathe" currently extracts weakly
- **Stacked prepositions** — "cats in forests at night" attaches everything to
  the first verb
- **Quantifier scope** — "all X that Y are Z" doesn't express universal logic
- **Passive chains** — "the law passed by legislators elected by citizens"
  only extracts one layer

These are areas to improve in Phase B of the roadmap (see `WHERE_WE_LEFT_OFF.md`).

## Why this approach?

Building a full English parser (like Stanford CoreNLP) is a massive undertaking.
This simplified recursive descent parser handles the most common structural
patterns Loom needs, while staying:

- **Pure Python** — no external NLP dependencies
- **Deterministic** — same input → same output, always
- **Fast** — O(n) on sentence length
- **Explainable** — every extracted fact can be traced back to a grammar rule

When it fails, it returns empty and the regex handlers take over — graceful degradation.
