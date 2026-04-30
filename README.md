# Loom

**A community-built symbolic knowledge system that learns from what people teach it through natural conversation.**

---

### What makes it different

- **Built from contributions** — Loom starts with minimal built-in knowledge and grows as people add and refine facts
- **Explicit relationships** — No opaque embeddings. Every idea is stored as a named connection (e.g., `dog → is → mammal`)
- **Attribution built-in** — Facts, edits, and corrections are tied to the people who contributed them
- **Consensus over time** — As more people confirm or challenge a fact, its reliability becomes clearer

### The idea

A knowledge system you can talk to, where every fact is transparent, attributed, and open to revision — closer to a conversational Wikipedia than a black-box model.

---

## Quick Start

```bash
pip install flask pymongo pandas pydantic python-dotenv
pip install spacy
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

python web_app.py
# open http://localhost:5000
```

Create a `.env` file:
```
MONGO_URI=mongodb://...
ADMIN_EMAIL=your@email.com
google_client_id=...  (optional, for Google sign-in)
```

---

## How It Works

```
User input → Structural extractor → Pronoun resolution → Sentence simplification
           → spaCy dependency parser (complex sentences)
           → Manual grammar parser (fallback)
           → 40+ regex pattern handlers (fallback)
           → Fact extraction → MongoDB storage
           → Background inference (every 3s): activation, Hebbian, rules, discovery
```

### Parsing pipeline

| Layer | File | Handles |
|-------|------|---------|
| **spaCy parser** | `loom/spacy_parser.py` | Conjoined subjects/objects, relative clauses, prep phrases |
| **Grammar parser** | `loom/grammar_parser.py` | Recursive descent with clause decomposition |
| **Composer query** | `loom/parser/base.py` | Unified handler for what/where/can/why questions |
| **Pattern handlers** | `loom/parser/*.py` | 40+ regex patterns for statements and corrections |

### Response generation

| Component | File | Purpose |
|-----------|------|---------|
| **Composer** | `loom/composer.py` | Multi-fact paragraphs, varied templates, reasoning chains |
| **Style learner** | `loom/style_learner.py` | Learns writing patterns from user input + feedback |
| **Grammar** | `loom/grammar.py` | Conjugation, pluralization, plural-aware responses |

### Knowledge representation

All facts stored as quads in MongoDB:
```
(subject, relation, object, context) + properties {
    confidence, temporal, scope, source_type,
    speaker_id, corrected_by, agreement_count, agreed_by,
    premises, rule_id, derivation_id, created_at
}
```

### Reasoning

| System | File | What it does |
|--------|------|-------------|
| **Spreading activation** | `loom/activation.py` | Collins & Loftus model, surfaces related concepts |
| **Hebbian learning** | `loom/processing.py` | Connections strengthen with use, decay when idle |
| **Inference engine** | `loom/inference.py` | Transitive chains, property inheritance, background daemon |
| **Rule engine** | `loom/rule_engine.py` | Forward-chaining if/then rules |
| **Discovery** | `loom/discovery.py` | Pattern mining, co-occurrence, auto-neuron creation |
| **Frame system** | `loom/frames.py` | Confirmed/potential attribute tiers, emergent clusters |
| **Curiosity** | `loom/curiosity.py` | Prioritized question generation for knowledge gaps |

---

## Web Interface

### Frontend (Svelte 5 + Vite)

Built frontend is pre-compiled in `static/`. No npm needed to run.

- **Chat** with persistence (survives refresh), right-click to copy
- **Neural visualizer** — dendrites, signal flow, pulse waves, sparks, zoom indicator
- **File management** — drag/drop upload, browser storage, inline edit with auto-retrain
- **Leaderboard** — people icon shows contributors ranked by facts/corrections/messages
- **About page** — community-focused description
- **Style page** (admin) — writing style analytics with feedback bars
- **Load results page** — per-file training breakdown chart
- **Like/dislike feedback** on responses
- **Guest vs Google auth** with admin gating

To rebuild frontend after changes:
```bash
cd frontend && npm install && npm run build
```

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/chat` | Process message (includes `conversation_id` for context isolation) |
| `GET` | `/api/graph` | Knowledge graph data with creator/corrector attribution |
| `GET` | `/api/collaborators` | Leaderboard data (neurons, corrections, messages per user) |
| `GET` | `/api/style` | Style analytics (admin only) |
| `POST` | `/api/feedback` | Record like/dislike on a response |
| `GET` | `/api/check-nickname` | Validate nickname uniqueness |
| `POST` | `/api/upload-training-batch` | Upload training files |
| `GET` | `/api/questions` | Curiosity engine questions |
| `GET` | `/api/config` | Public config (Google client ID) |

### Chat Commands

| Command | Access | Action |
|---------|--------|--------|
| `/help` | everyone | Show help (filtered by role) |
| `/about` | everyone | Open About page |
| `/visualize` | everyone | Open neural graph |
| `/clear` | everyone | Clear chat |
| `/forget` | everyone | Erase own facts |
| `/show` | admin | Knowledge summary |
| `/stats` | admin | Storage statistics |
| `/style` | admin | Style analytics |
| `/load-all` | admin | Load all training files |
| `/procedures` | admin | Show stored procedures |
| `/neuron X` | admin | Inspect concept |
| `/forget-all` | admin | Erase all memory |

---

## Community Features

### Correction attribution
When a user corrects Loom ("no, actually X is Y"), the correction is stored
with `corrected_by` and recorded in a `corrections` MongoDB collection. The
visualizer shows "Corrected by" tags on affected neurons.

### Consensus
When multiple users teach the same fact, `agreement_count` increments and
`agreed_by` tracks the list of agreeing users. Future: higher-agreement facts
will be prioritized in responses.

### Leaderboard
`/api/collaborators` aggregates three metrics per user:
- **Neurons** — facts created (from `facts.properties.speaker_id`)
- **Corrections** — facts fixed (from `corrections.corrected_by`)
- **Messages** — total chat messages (from `user_stats.message_count`)

Admin users are badged in the UI.

### Feedback loop
Like/dislike buttons on responses feed into the style learner. Templates with
positive feedback are boosted; negative feedback demotes them. Over time, Loom
learns which explanation styles work best.

---

## Dependencies

**Required:**
- Python 3.10+
- `flask` — web server
- `pymongo` — MongoDB storage
- `pandas` — batch fact loading
- `pydantic` — data validation
- `python-dotenv` — environment variable loading

**Optional but recommended:**
- `spacy` + `en_core_web_sm` — dependency parsing for complex sentences
  (graceful fallback to manual parser if unavailable)

**Not used (by design):**
- No PyTorch, TensorFlow, scikit-learn
- No Word2Vec, BERT, or any vector embeddings
- No neural networks for reasoning

spaCy is used strictly as a linguistic parsing tool, not for learning or training.

---

## Project Layout

```
├── web_app.py                  # Flask backend (loads .env, all API endpoints)
├── main.py                     # CLI entry point
├── .env                        # Environment variables (MONGO_URI, ADMIN_EMAIL, etc.)
├── WHERE_WE_LEFT_OFF.md        # Development status and roadmap
├── CLAUDE.md                   # Architecture guidance for Claude Code
├── frontend/                   # Svelte 5 source (npm run build → static/)
├── static/                     # Pre-built frontend assets
├── training/                   # 27 training files (.json)
├── loom/                       # Main Python package
│   ├── brain.py                # Loom class, context pool, add_fact, add_facts_batch
│   ├── models.py               # Pydantic schemas, enums
│   ├── composer.py             # Response generation, varied templates
│   ├── style_learner.py        # Writing pattern extraction + feedback
│   ├── spacy_parser.py         # spaCy dependency parser
│   ├── grammar_parser.py       # Manual recursive descent parser
│   ├── inference.py            # Background inference daemon
│   ├── activation.py           # Spreading activation network
│   ├── discovery.py            # Pattern mining (AUTO_CREATE_NEURONS enabled)
│   ├── context.py              # Conversation state with persistence snapshots
│   ├── frames.py               # Two-tier attribute system
│   ├── rules.py / rule_engine.py  # Forward-chaining rules
│   ├── curiosity.py            # Question generation
│   ├── normalizer.py           # Text normalization
│   ├── grammar.py              # Conjugation, pluralization
│   ├── parser/                 # 40+ pattern handlers
│   │   ├── base.py             # Parser class, _check_composer_query
│   │   ├── handlers.py         # Corrections with attribution
│   │   └── ...                 # queries, patterns, relations, discourse
│   └── storage/
│       ├── mongo.py            # MongoDB with consensus tracking
│       └── json_fallback.py    # Automatic fallback
└── docs/                       # Module documentation
```

---

## Documentation

| Document | Covers |
|----------|--------|
| [WHERE_WE_LEFT_OFF.md](./WHERE_WE_LEFT_OFF.md) | Full dev status, roadmap, known bugs |
| [docs/composer.md](./docs/composer.md) | Response composer, unified query handler |
| [docs/spacy_parser.md](./docs/spacy_parser.md) | spaCy integration, installation, capabilities |
| [docs/style_learner.md](./docs/style_learner.md) | Style extraction, feedback tracking |
| [docs/grammar_parser.md](./docs/grammar_parser.md) | Manual recursive descent parser |
| [docs/brain.md](./docs/brain.md) | Core knowledge graph |
| [docs/activation.md](./docs/activation.md) | Spreading activation |
| [docs/inference.md](./docs/inference.md) | Inference engine |
| [docs/frames.md](./docs/frames.md) | Frame system |
| [docs/rules.md](./docs/rules.md) | Rule engine |
| [docs/storage.md](./docs/storage.md) | Persistence layer |

---

## Architectural Principles

1. **No ML frameworks** — PyTorch, TensorFlow, scikit-learn are off-limits
2. **spaCy is OK** — linguistic parsing tool, not for learning/training
3. **Every inference must be traceable** — show the reasoning chain
4. **Attribution on everything** — who taught it, who corrected it
5. **Community consensus** — reliability emerges from multiple contributors
6. **No feature without explanation support** — if the user can't ask "why?", don't build it

---

*"A knowledge system built from what people teach it. Every fact is transparent, attributed, and open to revision."*
