# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Loom (v0.8-dev) is a community-built symbolic knowledge system that learns from what people teach it through natural conversation. Every fact is transparent, attributed, and open to revision — closer to a conversational Wikipedia than a black-box model.

No ML frameworks (PyTorch, scikit-learn, TensorFlow). spaCy is used as a linguistic parsing tool only. No vector embeddings. Pure symbolic reasoning.

**Key systems:** spaCy dependency parser, response composer with varied templates, style learner with feedback loop, pandas batch loading, correction attribution, collaborator leaderboard, per-conversation context, Svelte 5 frontend with neural visualizer.

See `WHERE_WE_LEFT_OFF.md` for full development status and roadmap.

## Running the Project

```bash
python main.py
```

`main.py` launches the Flask web server (it imports `web_app.app` and calls
`app.run`). Open `http://localhost:5000` and interact through the Svelte web
UI. For a production deployment use the WSGI entry point instead:

```bash
gunicorn main:app --workers 1 --threads 8 --timeout 120 --bind 0.0.0.0:5000
```

(A single worker is intentional — the knowledge graph and the background
inference daemon are per-process state; threads provide request concurrency.)

An interactive text CLI also exists in `loom/cli.py` (teach facts like
`dogs are animals`, ask `what are dogs?`, run commands like `help`, `show`,
`train animals`, `neuron dogs`). It is not currently wired to an entry point.

**Dependencies:** see `requirements.txt` (runtime) and `requirements-dev.txt`
(tests). MongoDB is required (`MONGO_URI`); `openai-whisper` is optional for
speech input.

## Web Interface

The Flask REST API (`web_app.py`) serves the built Svelte SPA from `static/`
at `http://localhost:5000`. Key endpoints:
- `POST /api/chat` — process messages (supports all commands)
- `GET  /api/graph` — knowledge graph for the visualizer
- Admin/ownership endpoints require a verified Google ID token sent as
  `Authorization: Bearer <id_token>` (never a client-supplied email).

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
    │  - Dormant neuron management    │
    │  - Access tracking & staleness  │
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
    │  - Confidence-weighted chaining │
    └─────────────────────────────────┘
```

**Key modules:**
- `brain.py` - Core knowledge graph with Hebbian connection weights, dormant neuron management, access tracking, and staleness decay
- `processing.py` - Fact processing pipeline with dormant neuron reactivation on re-mention
- `activation.py` - Spreading activation network for fast connection discovery
- `chunker.py` - Text chunking and RST discourse relation detection
- `parser/` - Modular pattern recognition (see Parser Architecture below)
- `inference.py` - Transitive chaining, property inheritance, analogy detection, confidence-weighted chain scoring
- `context.py` - Conversation state with salience-based coreference resolution, entity disambiguation, and hypothetical mode
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
loom/  (repo root)
├── main.py, web_app.py   # Web server entry points
├── loom/                 # Main Python package (brain, parser, storage, ...)
├── frontend/             # Svelte 5 source (built by Vite)
├── static/               # Built SPA served by Flask (Vite output)
├── tests/                # Pytest suite (run: pytest tests/)
├── docs/                 # Documentation
├── requirements.txt      # Runtime dependencies
├── requirements-dev.txt  # Test dependencies
├── img/                  # Screenshots/diagrams (gitignored)
└── loom_memory/          # Local storage / JSON fallback (gitignored)
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

**Dormant Neuron System (`brain.py`, `processing.py`):** Neurons and connections are never deleted, only marked dormant with auto-reactivation on re-mention. Core concepts (20+ accesses) are protected from dormancy.

**Access Tracking (`brain.py`):** Tracks usage frequency and recency per entity. Concepts with 20+ accesses become core concepts, protected from dormancy and staleness. Every 5 accesses boosts connection weights.

**Confidence-Weighted Inference (`inference.py`):** Product-based chain confidence replaces min-based. Co-activation blocked between low-confidence-only nodes. Configurable via `CONFIDENCE_WEIGHTS` and `MIN_CHAIN_CONFIDENCE`.

**Entity Disambiguation (`context.py`):** Detects entity types (ENTITY_SELF, ENTITY_SYSTEM, ENTITY_THIRD_PARTY). Filters self/system references from coreference candidates.

**Hypothetical Mode (`context.py`, `parser/base.py`):** Triggered by "what if"/"imagine"/"suppose". Facts tracked but not persisted. Auto-exits after definitive statements.

**Staleness Decay (`brain.py`):** Concepts unused 24h+ lose one confidence level (never deleted). Skips core concepts. Runs via the inference background loop.


## Superskills Integration

This project uses **superskills** — a portable skill and agent system.

- **Skills folder:** `superskills/`
- **Project type:** fullstack-web (Python symbolic AI + Svelte 5 frontend)
- **Languages:** Python, JavaScript
- **Frameworks:** Flask, Svelte 5, Vite

### Agent Team

The lead agent (loom-lead) orchestrates work by dispatching to specialist teammates.
Agents are defined in `.claude/agents/`: loom-dev, loom-qa, loom-researcher, loom-frontend, loom-docs, loom-tester.
The lead agent reads each task, decomposes it, and delegates to the right specialist(s) in parallel when possible.

### Skill Selection Rules

1. **Before any task**, check if a relevant skill exists in `superskills/`
2. **Recommended skills for this project:** api-design-principles, modern-python, modern-javascript-patterns, python-testing-patterns
3. **If no appropriate skill exists**, use the `find-skills` skill (`superskills/find-skills/SKILL.md`) to search for and install one:
   - Run `npx skills find [query]` to search
   - Run `npx skills add <package> -g -y` to install
   - Save new skills into the `superskills/` folder
4. **Always read the SKILL.md** before applying — skills evolve and have specific instructions

### Skill Priority by Task Type

| Task Type | Check These Skills First |
|-----------|------------------------|
| New feature / UI | brainstorming -> frontend-design, responsive-design |
| API endpoint | api-design-principles, api-and-interface-design |
| Bug fix | systematic-debugging, debug-buttercup |
| Performance | cost-optimization, python-performance-optimization |
| Testing | e2e-testing-patterns, python-testing-patterns, property-based-testing |
| Security | semgrep, agentic-actions-auditor, supply-chain-risk-auditor |
| Design | high-end-visual-design, visual-design-foundations, ui-ux-pro-max |
| Documentation | doc-coauthoring, internal-comms |
| Code review | differential-review, code-maturity-assessor |
| Refactoring | clarify, modern-python or modern-javascript-patterns |

### Usage Dashboard

Track token consumption with the built-in dashboard:

```bash
python superskills/claude-usage/cli.py scan        # Scan usage data
python superskills/claude-usage/cli.py today       # Today's stats
python superskills/claude-usage/cli.py stats       # All-time stats
python superskills/claude-usage/cli.py dashboard   # Web dashboard on localhost:8080
```

### Available Integrations

When MCP integrations are connected, the lead agent can use them:

- **Google Calendar** — Check schedule, create events, find availability
- **Google Drive** — Search docs, read files, organize documents
- **Gmail** — Read emails, draft responses, search inbox
- **Figma** — Extract designs, implement components from Figma files
- **Vercel** — Deploy, manage env vars, check deployment status
- **Context7** — Fetch latest library/framework documentation

To enable an integration, authenticate it via the Claude Code MCP settings.
The lead agent will auto-detect which integrations are available and use them when relevant.

### Project Conventions

- Follow existing code patterns before introducing new ones
- The lead agent auto-detects stack from package.json, requirements.txt, directory structure
- All agents have access to skills in `superskills/`
- New agents can be created on-the-fly by the lead agent and saved to `.claude/agents/`
