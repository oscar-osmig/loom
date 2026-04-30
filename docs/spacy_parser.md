# spaCy Parser (`loom/spacy_parser.py`)

Uses spaCy's dependency parse tree to extract facts from complex sentences.
Primary parser for sentences with structural complexity; the manual
`grammar_parser.py` serves as fallback.

## Installation

spaCy is installed as a pip package. The English model is installed from
a direct GitHub URL (bypasses `spacy download` which can fail on Windows):

```bash
pip install spacy
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
```

## What It Handles

| Structure | Example | Extraction |
|-----------|---------|------------|
| Simple facts | "cats are mammals" | `cats [is] mammals` |
| Conjoined subjects | "cats and dogs are mammals" | `cats [is] mammals` + `dogs [is] mammals` |
| Conjoined objects | "cats eat fish, birds, and mice" | 3 separate `[eats]` facts |
| Conjoined properties | "elephants have thick skin and long trunks" | 2 `[has]` facts |
| Relative clauses | "cats that have claws can climb" | `cats [has] claws` + `cats [can] climb` |
| Prepositional phrases | "whales live in oceans" | `whales [lives_in] oceans` |
| Modal abilities | "cats can climb trees" | `cats [can] climb trees` |
| Negation | "dogs cannot fly" | `dogs [cannot] fly` (negated=True) |
| Intransitive verbs | "birds fly" | `birds [can] fly` |
| Conjoined verbs | "birds fly and lay eggs" | `birds [lay] eggs` (root VP partially) |

## How It Works

1. **Tokenize** with spaCy's `en_core_web_sm` model
2. **Find root verb** of each sentence
3. **Extract subjects** — walk `nsubj`/`nsubjpass` deps, expand conjuncts
4. **Extract objects** — walk `dobj`/`attr`/`acomp` deps, expand conjuncts
5. **Extract prepositions** — walk `prep` → `pobj` chains
6. **Handle modals** — detect `aux` with "can"/"could", make verb the object
7. **Handle relative clauses** — find `relcl` deps, extract as separate facts
8. **Handle conjoined verbs** — find `conj` of root verb, extract each VP
9. **Deduplicate** by (subject, relation, object) key

## Integration

Wired into `parser/base.py` via `_check_grammar_parser()`:

```
complex sentence detected? (commas, "and", relative pronouns)
  → try spacy_parser.parse()
  → if < 2 facts, try grammar_parser.parse_and_extract()
  → if < 2 facts, fall through to regex handlers
```

The spaCy parser only activates for sentences with structural complexity
(relative clauses, conjunctions, multiple commas). Simple "X is Y" sentences
go directly to `_check_is_statement`.

## Relation Mapping

Verbs map to Loom relations:
- `be/is/are` → `is` (or `is_not` if negated)
- `have/has` → `has` (or `has_not`)
- `can/could` → `can` (or `cannot`)
- `live/lives` → `lives_in`
- `eat/eats` → `eats`
- etc.

Prepositions map to location/property relations:
- `in` → `lives_in` or `located_in`
- `with` → `has`
- `by` → `by_agent`
- `for` → `used_for`
- `of` → `part_of`

## Graceful Degradation

If spaCy isn't installed or the model fails to load, `SPACY_AVAILABLE`
is `False` and `parse()` returns an empty list. The manual grammar parser
takes over seamlessly.

## Known Limitations

- First parse takes ~2s (model loading)
- Intransitive root verbs ("birds fly") extracted as ability, not direct relation
- Conjoined verb root ("fly" in "birds fly and lay eggs") sometimes missed
- Very long sentences (>500 chars) skipped for performance
- spaCy's small model occasionally misparses complex nested structures
