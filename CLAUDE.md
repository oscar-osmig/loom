# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Loom (v0.6) is a symbolic knowledge system that learns through natural language dialogue. It creates neurons (concepts) and synapses (connections) from conversation, inspired by Hebbian learning and biological neural plasticity. No ML frameworks, embeddings, or mathematical optimization - pure symbolic reasoning.

**New in v0.6:** Spreading activation, Hebbian connection strengthening, paragraph processing, improved coreference resolution.

## Running the Project

```bash
python main.py
```

This starts an interactive CLI. Within the CLI:
- Type natural language statements to teach facts: `dogs are animals`
- Ask questions: `what are dogs?`
- Use commands: `help`, `show`, `train animals`, `neuron dogs`, `verbose`, `quit`

**Windows:** If Unicode box-drawing characters fail, run with:
```bash
set PYTHONIOENCODING=utf-8 && python main.py
```

**Optional dependencies:**
- `pymongo` - MongoDB storage (falls back to JSON file if unavailable)
- `flask` - Web interface (`python web_app.py`)

## Web Interface

```bash
pip install flask
python web_app.py
```

Flask REST API serving `web_chat.html` at `http://localhost:5000`. Endpoint:
- `POST /api/chat` - Process messages (supports all CLI commands)

## Architecture

```
Input Text (single or paragraph)
         │
         ▼
    ┌─────────────────┐
    │  Text Chunker   │ ◄── Splits paragraphs into semantic chunks
    │  (chunker.py)   │     Detects discourse relations (RST)
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │  Parser         │     Extracts relations per clause
    │  (parser/)      │     40+ pattern checks in priority order
    └────────┬────────┘
             │
             ▼
    ┌─────────────────────────────────┐
    │  Activation Network             │ ◄── Spreading activation (Collins & Loftus)
    │  (activation.py)                │     Co-activation detection
    └────────────────┬────────────────┘     Priming window
                     │
                     ▼
    ┌─────────────────────────────────┐
    │  Brain (brain.py)               │ ◄──► Storage (storage/)
    │  - Knowledge graph              │      MongoDB or JSON fallback
    │  - Connection weights           │
    │  - Hebbian strengthening        │
    └────────────────┬────────────────┘
                     │
                     ▼
    ┌─────────────────────────────────┐
    │  Inference Engine               │
    │  (inference.py)                 │
    │  - Immediate activation-based   │
    │  - Background transitive chains │
    │  - Property inheritance         │
    │  - Analogy detection            │
    └─────────────────────────────────┘
```

**Key modules:**
- `brain.py` - Core knowledge graph with Hebbian connection weights
- `activation.py` - Spreading activation network for fast connection discovery
- `chunker.py` - Text chunking and RST discourse relation detection
- `parser/` - Modular pattern recognition (see Parser Architecture below)
- `inference.py` - Transitive chaining, property inheritance, analogy detection
- `context.py` - Conversation state with salience-based coreference resolution
- `storage/` - Dual-backend persistence layer

## Parser Architecture

The `loom/parser/` package splits parsing into specialized modules:
- `base.py` - Main Parser class orchestrating 40+ pattern checks in strict priority order
- `queries_basic.py` - Simple queries (what, who, where, name, color)
- `queries_complex.py` - Complex queries (can, why, causes, effects)
- `queries_knowledge.py` - Domain queries (classification, breathing, reproduction)
- `patterns_basic.py` - Basic patterns (negation, looks_like, analogy)
- `patterns_relations.py` - Relation patterns (is_statement, conditional, becomes)
- `patterns_discourse.py` - Natural conversation learning
- `handlers.py` - Correction, clarification, procedural, causal handlers
- `constants.py` - Shared word lists (CORRECTION_WORDS, REFINEMENT_WORDS)

## Storage Layer

The `loom/storage/` package provides dual-backend persistence:
- `mongo.py` - MongoDB with indexes, provenance tracking, cascade retraction
- `json_fallback.py` - Automatic fallback to `loom_memory/loom_memory.json`

Storage backend is selected automatically via `get_storage()`.

## Project Structure

```
neuro/
├── main.py, web_app.py   # Entry points
├── img/                  # Screenshots/diagrams (gitignored)
├── tests/                # Test suite (gitignored)
├── loom_memory/          # Persistent storage (gitignored)
│   ├── loom_memory.json
│   └── loom_rules.json
├── docs/                 # Documentation
└── loom/                 # Main package
```

## Knowledge Representation

All facts stored as triples: `(subject, relation, object)` with confidence levels (high/medium/low).

Transitive relations that support chaining: `looks_like`, `is`, `causes`, `leads_to`, `part_of`

Relations are lowercase, subjects/objects are normalized (stripped articles, underscores for spaces).

## Training Packs

Pre-built knowledge packs loaded via `train [pack]` command: `animals`, `nature`, `science`, `geography`

Custom training from `.txt` or `.json` files via `load [file]` command.

## Spreading Activation

The activation network (`activation.py`) implements Collins & Loftus spreading activation:
- When concepts are mentioned, they get activated
- Activation spreads to connected nodes with decay
- Co-activation (multiple sources activating same node) signals potential new connections
- Priming window keeps recently activated concepts ready for faster connections

## Hebbian Learning

Connection weights strengthen with use ("cells that fire together wire together"):
- `strengthen_connection()` increases weight when facts are used
- `decay_all_connections()` weakens unused connections (synaptic pruning)
- Strong connections (weight > 2.0) can be viewed with `weights` command

## Paragraph Processing

The chunker (`chunker.py`) handles multi-sentence text:
- Splits into sentences and clauses
- Detects discourse connectors (because, but, therefore, etc.)
- Identifies nucleus/satellite relationships (RST)
- Processes chunks in order, building cross-sentence connections

## Threading Model

Inference engine runs as a daemon thread, processing facts asynchronously every 3 seconds without blocking CLI interaction. Also handles periodic connection decay.

## Advanced Subsystems (New)

**Rule Learning (`rules.py`):** Forward-chaining rule engine. Learns rules from "if X then Y" statements and repeated patterns. Rules have status lifecycle: CANDIDATE → ACTIVE → SUSPENDED/REJECTED.

**Curiosity Engine (`curiosity.py`):** Generates prioritized questions to fill knowledge gaps. Question types ranked by priority: contradictions (10.0), rule confirmation (6.0), chain gaps (5.0), low-confidence facts (4.0).

**Provenance Tracking (`provenance.py`):** Tracks fact origins with SourceType (USER, INFERENCE, CLARIFICATION, INHERITANCE, SYSTEM) and premise dependencies for truth maintenance.

**Sentence Simplifier (`simplifier.py`):** Breaks complex sentences (lists like "X need A, B, C", parallel structures, contrast patterns) into simple statements for parsing.

**Speech Processing (`speech.py`):** Audio-to-text with pluggable ASR backends (Whisper local/API, Google, Azure, Vosk). Links spoken facts to audio metadata.
