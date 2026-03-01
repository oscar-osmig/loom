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

**Optional:** Install `pymongo` for MongoDB storage (falls back to JSON file if unavailable).

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
    │  (parser.py)    │
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
    │  Brain (brain.py)               │ ◄──► Storage (storage.py)
    │  - Knowledge graph              │      (MongoDB or JSON)
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
- `parser.py` - Pattern recognition for relations, corrections, questions
- `inference.py` - Transitive chaining, property inheritance, analogy detection
- `context.py` - Conversation state with salience-based coreference resolution
- `storage.py` - MongoDB primary, JSON fallback

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
