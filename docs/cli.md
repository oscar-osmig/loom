# CLI Interface

## Overview

The CLI provides an interactive command-line interface for Loom. Users interact with Loom through natural language statements (to teach facts), questions (to query knowledge), and commands (prefixed with `/` or standalone keywords). The visualizer renders the knowledge graph as ASCII neurons with synapses.

## Key Concepts

- **Interactive Loop**: Runs in `run_cli()`, continuously prompts user input, parses commands, and processes natural language.
- **Command Parsing**: Commands are case-insensitive and optionally prefixed with `/`. Both `show` and `/show` work.
- **Knowledge Graph Display**: The visualizer (`visualizer.py`) renders neurons as ASCII boxes with relation symbols connecting to targets.
- **Neuron Styles**: Different bracket styles indicate neuron type (concept, action, property, default).
- **Relation Symbols**: Each relation type has a unique ASCII symbol (e.g., `═══` for "is", `~~~` for "can").

## API / Public Interface

### `run_cli()`
Main entry point. Initializes Loom instance and runs the interactive loop.

### User Input Processing

**Natural Language:**
- Single statements: `"dogs are animals"` → processed with activation network
- Paragraphs (`.` or len > 100 chars): processed chunk-by-chunk

**Commands** (all optional `/` prefix):
- `quit`, `exit`, `bye`, `q` — Exit CLI
- `show` — Display full knowledge graph (20 most connected nodes)
- `compact` — Compact node list with connection counts
- `neuron <name>` — Inspect single node and all connections
- `inferences` — Show inferred facts
- `conflicts` — Show contradictions
- `procedures` — Show stored procedural sequences
- `context` — Display conversation context (topic, salience, pending clarifications)
- `activation` — Show primed nodes and activation levels
- `weights` — Show strengthened connections (Hebbian weight > 1.2)
- `frame <concept>` — Show concept frame (confirmed/potential attributes)
- `bridges [<concept>]` — Show attribute bridges between concepts
- `clusters` — Show emergent category clusters
- `analogies <concept>` — Find similar concepts
- `chain <subject> <relation>` — Trace reasoning chain
- `train [<pack>]` — List packs or load a pack (`animals`, `nature`, `science`, `geography`)
- `load <file>` — Load custom training from `.txt` or `.json`
- `stats` — Storage statistics (nodes, synapses, procedures, inferences, conflicts)
- `forget` — Erase all memory
- `verbose` — Toggle debug output
- `clear` — Clear screen
- `about` — Show system information
- `help` — Display command reference
- `entities` — Show salient entities in current context

## How It Works

### Interactive Loop Flow

1. Print welcome header
2. Initialize Loom instance with context reference
3. Loop:
   - Read user input (EOFError/KeyboardInterrupt exit gracefully)
   - Skip empty input
   - Normalize to lowercase
   - Strip leading `/` if present
   - Match against known commands
   - If no match, treat as natural language:
     - Detect paragraphs (`. ` or len > 100)
     - Use `loom.process_text()` for paragraphs
     - Use `loom.process_with_activation()` for single statements
   - Print response

### Visualization (visualizer.py)

**Neuron Rendering:**
- `draw_neuron()` creates 3-line ASCII box with brackets based on style (concept, action, property, default)
- Truncates text to fit (max 12 chars default)
- Center-pads content

**Relation Symbols:**
- Defined in `RELATION_SYMBOLS` dict
- `draw_connection()` renders single arrow with symbol
- Connections limited to 5 per neuron; excess shown as "+X more"

**Full Graph Display (`visualize_graph()`):**
- Sorts nodes by outgoing connection count (most connected first)
- Limits display to top 20 nodes
- Shows stats footer (neuron count, synapse count)
- Includes legend with symbol meanings

**Node Detail Display (`visualize_node()`):**
- Central neuron shown in expanded style
- All outgoing connections listed with targets
- Reverse lookup shows incoming connections
- Uses `get_neuron_type()` to infer style from relations

**Compact Display (`visualize_compact()`):**
- One line per node: name, visual bar, connection count
- Bar is min(10, connection_count) filled blocks

## Dependencies

**Imports:**
- `loom.brain.Loom` — Core knowledge graph
- `loom.trainer` — Pre-built training packs and file loading
- `loom.visualizer` — ASCII graph rendering
- `loom.context` — Conversation state and salience tracking
- `loom.inference` — Reasoning engine

**Imported by:**
- `main.py` — Entry point calls `run_cli()`

## Examples

### Teaching
```
you > dogs are animals
loom > Noted: dogs is animals.

you > birds can fly
loom > Learned: birds can fly.
```

### Querying
```
you > what are dogs?
loom > Dogs are: animals. (inferred: mammals)

you > can birds fly?
loom > Yes, birds can fly.
```

### Commands
```
you > /show
[Displays full knowledge graph as ASCII neurons]

you > /neuron dog
[Shows all connections for "dog" neuron]

you > /stats
+-- Storage Statistics -------+
|  Storage: JSON File
|  Neurons: 42
|  Synapses: 156
|  Procedures: 3
|  Inferences: 8
|  Conflicts: 0
+-------------------------------+

you > /train animals
[Loads pre-built animals pack: "Loaded 47 facts about animals."]

you > /analogies dog
[Shows similar concepts with similarity scores]

you > /help
[Displays command reference]
```

### Visualization Example
```
╔══════════════════════════════════════════════════════════╗
║              🧠  NEURAL KNOWLEDGE MAP  🧠                ║
╚══════════════════════════════════════════════════════════╝

    ╭──────────────╮
   ⟨ animal       ⟩  (concept neuron)
    ╰──────────────╯
        ├═══─► (dog)
        ├═══─► (cat)
        └~~~─► (can_move)

LEGEND:
═══  is/category    ───  has/property
~~~  can/ability    >>>  causes/leads to
```
