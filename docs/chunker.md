# Chunker

## Overview

The chunker breaks input text into semantic units (chunks) and identifies discourse relations between them using Rhetorical Structure Theory (RST) principles. It processes both single sentences and multi-sentence paragraphs, detecting how clauses relate to each other (causal, contrast, temporal, etc.) and classifying chunks as nucleus (main point) or satellite (supporting).

## Key Concepts

**Chunk**: A semantic unit of text with an associated type (statement, question, command), discourse relation, and RST role.

**Discourse Connectors**: Words and phrases that signal relationships between clauses ("because", "however", "therefore", etc.). The chunker maps these to 8 relation types: causal, contrast, elaboration, temporal, example, condition, similarity, conclusion.

**Nucleus vs. Satellite (RST)**: The nucleus is the core/main clause; satellites provide supporting information. Processing nuclei first often captures the primary knowledge before elaborations.

**Discourse Structure**: A directed graph of relations linking chunks. Example: Chunk 0 (nucleus) --[causal]--> Chunk 1 (satellite).

## API / Public Interface

**`TextChunker()`**: Main class. Stateless; instantiate once per session.

**`chunk_text(text: str) -> ChunkedText`**: Entry point. Returns `ChunkedText` dataclass with:
- `original`: The input text (normalized)
- `sentences`: List of split sentences
- `chunks`: List of `Chunk` objects
- `paragraph_theme`: Most frequent non-stopword (optional)
- `discourse_structure`: List of relation dicts linking chunk indices

**`Chunk` dataclass**:
- `text`: Clause text
- `chunk_type`: "statement", "question", or "command"
- `connector`: Detected discourse connector (e.g., "because")
- `relation_type`: Mapped relation ("causal", "contrast", etc.)
- `entities`: Extracted entities (currently unused)
- `is_nucleus`: Boolean; True if main clause

**`get_discourse_relations(chunked: ChunkedText) -> List[Dict]`**: Extract relations for knowledge graph insertion. Returns list with keys: `from_text`, `to_text`, `relation`, `connector`, `from_is_nucleus`, `to_is_nucleus`.

**`process_for_knowledge(text: str) -> Dict`**: High-level API returning:
- `chunks`: List of clause texts
- `chunk_types`: List of types
- `relations`: Discourse relations
- `theme`: Paragraph theme
- `processing_order`: Suggested order (nuclei indices first, then satellites)
- `sentence_count`, `chunk_count`

**`iter_chunks(text: str)`**: Generator yielding chunks one at a time, nuclei first, then satellites.

## How It Works

1. **Normalize whitespace**: Collapse multiple spaces.
2. **Split sentences**: Use regex `(?<=[.!?])\s+(?=[A-Z])` with abbreviation protection (Mr., Dr., etc.).
3. **Split clauses per sentence**: Check for list patterns (e.g., "X, Y, and Z are W"), then split on clause separators (`, and `, ` but `, ` because `, etc.). Connectors are preserved as prefix of following clause.
4. **Detect connector & relation**: Scan clause start for discourse markers, longest match first. Map to relation type.
5. **Detect chunk type**: "?" → question; command starters ("do", "make", "let") → command; else statement.
6. **Determine nucleus/satellite**: First clause (no connector) is nucleus. Clauses with elaboration/example/condition connectors are satellites. "because" introduces a satellite.
7. **Build discourse structure**: Link adjacent chunks if a relation exists.
8. **Detect theme**: Count word frequencies (excluding stopwords, len > 2); return most frequent.

**Processing order** (for knowledge extraction): Nuclei first (capture primary knowledge), then satellites (add details).

## Dependencies

- **Imports**: `re`, `typing`, `dataclasses`
- **Imported by**: `parser/base.py` (processes input text before parsing), `main.py` (CLI entry)
- **Discourse markers** are separate in `discourse.py` but chunker uses its own hardcoded `DISCOURSE_CONNECTORS` dict

## Examples

### CLI Usage
```python
from loom.chunker import TextChunker

chunker = TextChunker()
result = chunker.chunk_text("Dogs are animals. They bark because they are alert.")
# result.chunks has 2 chunks:
#   1. "Dogs are animals" (statement, nucleus)
#   2. "because they are alert" (statement, satellite, relation=causal)
# result.discourse_structure links them: 0 --[causal]--> 1
```

### Knowledge Extraction
```python
knowledge_data = chunker.process_for_knowledge("Penguins are birds. They live in Antarctica and swim well.")
# Returns processing order: [0, 1] (nuclei) then [2] (satellite)
# Suggests processing nuclei first, then adding satellite properties
```

### Paragraph with Lists
```python
result = chunker.chunk_text("Dogs, cats, and birds are animals. However, fish are different.")
# Correctly avoids splitting "Dogs, cats, and birds are animals" into separate clauses
# Identifies "However" as contrast relation
```
