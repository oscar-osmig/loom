# Loom v0.6

**A symbolic knowledge system that learns through natural language dialogue.**

Loom is a symbolic, knowledge-graph-based AI system designed to store, reason about, and expand knowledge in a human-like way. Unlike statistical or vector-based AI, Loom relies on explicit symbolic representations (neurons and synapses) and logical reasoning mechanisms to understand and interact with the world.

**Core Components:**
- **Neurons** — Concepts or entities represented as simple strings (e.g., "dogs", "mammals")
- **Synapses** — Connections between neurons stored as quads: `(subject, relation, object, context)`
- **Knowledge Graph** — Maps neurons to outgoing synapses with confidence, temporal info, and provenance

Loom features fully explainable chains of inference, curiosity-driven discovery, and context-aware dialogue — inspired by Hebbian learning and biological neural plasticity. No ML frameworks, embeddings, or mathematical optimization — pure symbolic reasoning.

## Features

- **Conversational Learning** — Teach facts naturally: "dogs are mammals", "birds can fly"
- **Paragraph Processing** — Understands multi-sentence text with RST discourse relations
- **Spreading Activation** — Related concepts activate each other (Collins & Loftus model)
- **Hebbian Learning** — "Cells that fire together wire together" — connections strengthen with use
- **Category Bridging** — Automatically connects related categories sharing instances
- **Transitive Inference** — If A→B and B→C, then A→C with confidence tracking
- **Property Inheritance** — Instances inherit properties from categories
- **Curiosity Engine** — Actively generates prioritized questions to fill knowledge gaps
- **Rule Learning** — Learns and applies "if X then Y" rules with forward chaining
- **Provenance Tracking** — Every fact has traceable origins and dependencies
- **Conflict Detection** — Identifies contradictions in the knowledge base
- **Speech Support** — Optional audio input via Whisper, Google, Azure, or Vosk

## Quick Start

### CLI Interface
```bash
python main.py
```

### Web Interface
```bash
pip install flask
python web_app.py
# Open http://localhost:5000
```

### Windows Unicode Fix
```bash
set PYTHONIOENCODING=utf-8 && python main.py
```

## How It Works

```
Input Text → Chunker → Parser → Activation Network → Brain → Inference Engine
     ↓           ↓         ↓              ↓              ↓           ↓
  "dogs      Splits    Extracts     Spreads        Stores      Infers new
   are       into      relations    activation     facts       connections
   mammals"  chunks    (subject,    to related     as          transitively
                       relation,    concepts       triples
                       object)
                                        ↓              ↓
                                   Discovery      Curiosity
                                   Engine         Engine
                                        ↓              ↓
                                   Finds         Generates
                                   patterns,     questions
                                   bridges       to fill gaps
```

### Teaching Facts
```
> dogs are mammals
Got it, dogs are mammals.

> mammals have fur
Got it, mammals have fur.

> birds can fly
Got it, birds can fly.
```

### Asking Questions
```
> what are dogs?
Dogs are mammals.

> do dogs have fur?
Yes, dogs have fur.  (inherited from mammals)

> can birds fly?
Yes, birds can fly.
```

### Processing Paragraphs
```
> The ocean contains saltwater. Fish live in the ocean. Sharks eat fish.

Processed 3 chunks, added 3 facts.
Theme: ocean

> what do sharks eat?
Sharks eat fish.

> what lives in the ocean?
Fish live in the ocean.
```

## CLI Commands

### Knowledge Input
| Command | Description |
|---------|-------------|
| `dogs are animals` | Define category membership |
| `birds can fly` | Define abilities |
| `rain causes floods` | Define causation |
| `the sky is blue` | Define properties |
| `no, that's wrong` | Correct previous statement |
| `only when warm` | Add constraints |

### Querying
| Command | Description |
|---------|-------------|
| `what are dogs?` | Query categories |
| `can birds fly?` | Query abilities |
| `what causes floods?` | Query causes |
| `where do fish live?` | Query locations |

### Viewing Knowledge
| Command | Description |
|---------|-------------|
| `show` | View knowledge graph |
| `compact` | Compact knowledge display |
| `neuron X` | Inspect specific concept |
| `stats` | Storage statistics |
| `weights` | Show strong connections |
| `activation` | Show activation state |
| `analogies X` | Find similar concepts |
| `inferences` | View inferred facts |
| `conflicts` | Show contradictions |
| `chain X R` | Trace reasoning chain |

### Management
| Command | Description |
|---------|-------------|
| `train animals` | Load training pack |
| `load file.txt` | Load custom file |
| `verbose` | Toggle debug output |
| `forget` | Clear all memory |
| `about` | What is Loom? |
| `help` | Show help |
| `quit` | Exit |

## Training Packs

Built-in knowledge packs:
- `animals` — 50 facts about animals
- `nature` — Weather, plants, colors
- `science` — Physics, biology, space
- `geography` — Continents, countries

```bash
> train animals
Loaded 50 facts about animals.
```

### Custom Training Files

**Text format (.txt):**
```
dogs | is | mammals
cats | eats | fish
birds | can | fly
```

**JSON format (.json):**
```json
[
  {"subject": "dogs", "relation": "is", "object": "mammals"},
  {"subject": "cats", "relation": "eats", "object": "fish"}
]
```

## Architecture

```
neuro/
├── main.py               # CLI entry point
├── web_app.py            # Flask web server
├── web_chat.html         # Web interface
├── img/                  # Screenshots and diagrams (gitignored)
├── tests/                # Test suite (gitignored)
│   ├── test_comprehensive.py
│   ├── test_paragraphs.py
│   ├── test_bridges.py
│   ├── test_dialogue.py
│   ├── test_curiosity_nodes.py
│   ├── test_smart_loom_features.py
│   └── ...
├── loom_memory/          # Persistent storage (gitignored)
│   ├── loom_memory.json  # Knowledge graph storage
│   └── loom_rules.json   # Learned rules storage
├── docs/                 # Documentation
│   └── COMPLEX_SENTENCE_PARSING.md
├── research/             # Research notes
│   └── conversational_learning_research.txt
└── loom/                 # Main package (~17k LOC)
    ├── brain.py          # Core knowledge graph with Hebbian weights
    ├── activation.py     # Spreading activation network (Collins & Loftus)
    ├── inference.py      # Transitive chaining, property inheritance, analogies
    ├── chunker.py        # Multi-sentence text processing, RST discourse
    ├── context.py        # Conversation state, coreference resolution
    ├── context_detection.py  # Temporal/scope context detection
    ├── discovery.py      # Connection discovery, category bridging, pattern mining
    ├── training.py       # Knowledge pack loading
    ├── processing.py     # HebbianMixin, text processing
    ├── rules.py          # Rule neurons, forward chaining
    ├── rule_engine.py    # Rule execution engine
    ├── curiosity.py      # Prioritized question generation
    ├── provenance.py     # Fact origin tracking with dependencies
    ├── resolver.py       # Entity/pronoun resolution
    ├── simplifier.py     # Basic sentence simplification
    ├── advanced_simplifier.py  # Complex sentence decomposition
    ├── normalizer.py     # Text normalization utilities
    ├── grammar.py        # Pluralization, conjugation, formatting
    ├── visualizer.py     # ASCII knowledge graph visualization
    ├── discourse.py      # Discourse analysis utilities
    ├── cli.py            # Command-line interface
    ├── trainer.py        # Training pack definitions
    ├── speech.py         # Audio-to-text (Whisper/Google/Azure/Vosk)
    ├── parser/           # 40+ pattern recognition handlers
    │   ├── base.py           # Main parser orchestrator
    │   ├── queries_basic.py      # What/who/where questions
    │   ├── queries_complex.py    # Why/can/causes questions
    │   ├── queries_knowledge.py  # Domain-specific queries
    │   ├── patterns_basic.py     # Negation, analogy, properties
    │   ├── patterns_relations.py # Is statements, conditionals
    │   ├── patterns_discourse.py # Conversational learning
    │   ├── handlers.py       # Corrections, clarifications, procedures
    │   ├── informational.py  # Encyclopedic text processing
    │   ├── relations.py      # Relation type definitions
    │   └── constants.py      # Shared word lists
    └── storage/          # Dual-backend persistence
        ├── mongo.py          # MongoDB with indexes, provenance
        └── json_fallback.py  # JSON file fallback
```

## Knowledge Representation

All facts stored as triples: `(subject, relation, object)` with metadata.

**Fact Structure:**
```python
(subject, relation, object)
├── confidence: "high" | "medium" | "low"
├── source_type: "user" | "inference" | "clarification" | "inheritance"
├── context: optional contextual info
└── properties: temporal, scope, conditions
```

**Common Relations:**
- Categories: `is`, `is_a`, `type_of`, `kind_of`
- Properties: `has`, `color`, `size`, `shape`
- Abilities: `can`, `cannot`
- Actions: `eats`, `lives_in`, `causes`, `needs`, `uses`
- Comparisons: `bigger_than`, `faster_than`
- Location: `located_in`, `found_in`, `part_of`

**Transitive Relations** (support chaining):
- `is`, `looks_like`, `causes`, `leads_to`, `part_of`

**Confidence Levels:**
- `high` — Directly stated by user
- `medium` — Inferred or confirmed
- `low` — Weak inference

**Source Types:**
- `user` — Directly taught
- `inference` — Derived via reasoning
- `clarification` — From corrections
- `inheritance` — From category properties

## Advanced Features

### Category Bridging
Automatically detects when categories share instances:
```
> dogs are pets
> cats are pets
> dogs are mammals
> whales are mammals

# System detects: pets overlaps_with mammals (both have dogs)
# Queries now understand the relationship
```

### Hebbian Learning
Connections strengthen with repeated use:
```
> weights
dogs → is → mammals (weight: 2.4)
cats → eats → fish (weight: 1.8)
```

### Spreading Activation
When concepts are mentioned, related concepts activate:
```
> activation
dogs: 1.0 (active)
mammals: 0.6 (spread from dogs)
animals: 0.3 (spread from mammals)
```

### Curiosity Engine
Generates questions to fill knowledge gaps, ranked by priority:
```
> questions
1. What color are dogs? (priority: 4.0)
2. Do cats have fur? (priority: 3.5)
```

Priority rankings:
- Contradictions: 10.0
- Rule confirmation: 6.0
- Chain gaps: 5.0
- Low-confidence facts: 4.0

### Provenance Tracking
Every fact tracks its origin and dependencies:
```
> neuron dogs
dogs is mammals
  └── Source: user
  └── Confidence: high

dogs has fur (inherited)
  └── Source: inheritance
  └── Premise: mammals has fur
```

### Rule Learning
Learns conditional rules from patterns:
```
> if animals eat plants then animals are herbivores
Got it, learned rule: animals eat plants → animals are herbivores

> cows eat plants
Got it, cows eat plants.
Inferred: cows are herbivores (via rule)
```

## Web API

**Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web chat interface |
| `/api/chat` | POST | Process message (supports all CLI commands) |
| `/api/graph` | GET | Get knowledge graph visualization data |
| `/api/questions` | GET | Get curiosity engine questions |
| `/api/speech` | POST | Process transcribed text with metadata |
| `/api/speech/audio` | POST | Process audio file directly |

**Example:**
```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "dogs are mammals"}'
```

**Response:**
```json
{
  "response": "Got it, dogs are mammals.",
  "facts_added": 1,
  "inferences": []
}
```

## Dependencies

**Required:**
- Python 3.7+ (uses standard library only)

**Optional:**
- `pymongo` — MongoDB storage (auto-falls back to JSON)
- `flask` — Web interface
- `openai` — Whisper API for speech
- `google-cloud-speech` — Google Speech-to-Text
- `azure-cognitiveservices-speech` — Azure Speech Services
- `vosk` — Offline speech recognition

```bash
# Install all optional dependencies
pip install pymongo flask openai vosk
```

## Documentation

Additional documentation is available in the `docs/` folder:

- **COMPLEX_SENTENCE_PARSING.md** — Advanced parsing patterns and handling
- **CLAUDE.md** — Project guidance and architecture overview

## Storage

**MongoDB** (if available):
- Indexed queries
- Provenance tracking
- Cascade retraction

**JSON File** (automatic fallback):
- Knowledge: `loom_memory/loom_memory.json`
- Rules: `loom_memory/loom_rules.json`
- Portable, no dependencies

## Testing

Tests are located in the `tests/` folder:

```bash
# Run comprehensive integration tests
python tests/test_comprehensive.py

# Run paragraph processing tests
python tests/test_paragraphs.py

# Run category bridging tests
python tests/test_bridges.py

# Run conversational learning tests
python tests/test_conversational_learning.py

# Run dialogue feature tests
python tests/test_dialogue.py

# Run curiosity node system tests
python tests/test_curiosity_nodes.py

# Run Smart Loom features tests (all 7 features)
python tests/test_smart_loom_features.py

# Run all tests
for f in tests/test_*.py; do python "$f"; done
```

## Philosophy

Loom is built on principles of **transparent, interpretable AI**:

1. **No Black Boxes** — Every inference has traceable provenance
2. **Biological Inspiration** — Hebbian learning, spreading activation
3. **Conversation-Driven** — Learn through natural dialogue
4. **Confidence-Based** — Uncertainty is explicit, not hidden
5. **Correctable** — "No, that's wrong" retracts and corrects

## Version History

**v0.6** (Current)
- Spreading activation network
- Hebbian connection strengthening
- Paragraph processing with discourse relations
- Category bridging
- Improved coreference resolution
- Rule learning engine
- Curiosity-driven question generation
- Speech processing support

## License

MIT License

## Contributing

Contributions welcome! See the codebase structure above for where to add features.

---

*"Weaving knowledge, one thread at a time."*
