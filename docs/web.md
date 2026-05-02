# Web Interface

## Overview

The web interface (`web_app.py` + `web_chat.html`) provides a modern chat-based UI for Loom. It runs a Flask server exposing REST endpoints for chat, file upload, graph visualization, and discovery. The frontend is a single-page app with dark theme, real-time messaging, drag-drop training, per-user fact tracking, and an interactive graph canvas.

## Key Concepts

- **REST API**: Flask endpoints handle all interactions (chat, file upload, graph data, questions, speech)
- **Single-Page App**: HTML5 + vanilla JavaScript, no framework dependencies
- **Per-User Tracking**: Facts tagged with `speaker_id` for user isolation
- **Training Methods**: Natural language chat, JSON/TXT file drag-drop, pasted JSON arrays
- **Graph Visualization**: Canvas-based node-link diagram with force-directed layout
- **Dark Theme**: Modern UI with accent color, responsive design, invisible scrollbars
- **Real-Time Feedback**: Toast notifications, typing indicator, loading spinners

## API / Public Interface

### Flask Endpoints

#### `GET /`
Serves `web_chat.html` (main chat interface).

#### `GET /loom.png`
Serves Loom icon image.

#### `POST /api/chat`
**Request Body:**
```json
{
  "message": "string (natural language or /command)",
  "user": "string (optional username for fact tagging)"
}
```

**Response (JSON):**
- `response`: String output (HTML-formatted for display)
- `type`: "response" | "error" | "info" | "help" | "questions" | "speech_response" | "audio_response"
- `meta`: Optional metadata (chunks_processed, facts_added, theme for paragraphs)

**Command Processing:**
- `/help` — Show command list
- `/show` — Knowledge summary
- `/activation` — Primed nodes and activation levels
- `/weights` — Strong connections (Hebbian weight > 1.2)
- `/stats` — Storage statistics
- `/forget` — Erase user facts (if username provided) or all facts
- `/about` — System information
- `/analogies <concept>` — Find similar concepts
- `/neuron <name>` — Inspect neuron
- `/frame <concept>` — Show frame (attributes)
- `/bridges [<concept>]` — Attribute bridges
- `/clusters` — Emergent clusters
- `/train [<pack>]` — List packs or load one
- `/load <filepath>` — Load custom file

**Natural Language Processing:**
- Detects pasted JSON arrays `[{subject, relation, object}, ...]` and loads as training data
- Single statements: processed with activation network
- Paragraphs (`. ` or len > 100): chunked and processed for cross-sentence connections

#### `POST /api/upload-training`
**Request (multipart/form-data):**
- `file`: JSON or TXT file
- `user`: Optional username

**JSON Format:**
```json
[
  {"subject": "cat", "relation": "is", "object": "animal"},
  {"s": "dog", "r": "can", "o": "bark"}
]
```

**TXT Format:**
```
cat | is | animal
dog , can , bark
(pipe or comma separated, comments with #)
```

**Response:**
```json
{
  "loaded": 42,
  "filename": "animals.json",
  "warnings": ["Item 5 missing relation"],
  "warning_count": 1
}
```

#### `POST /api/speech`
**Request Body:**
```json
{
  "text": "string (transcribed text)",
  "speaker_id": "string (optional)",
  "confidence": 0.95
}
```

**Response:**
```json
{
  "response": "string",
  "type": "speech_response",
  "source": {
    "type": "speech",
    "speaker_id": "alice",
    "confidence": 0.95
  }
}
```

#### `POST /api/speech/audio`
**Request (multipart/form-data):**
- `audio`: WAV/MP3 file
- `backend`: "whisper_local" | "whisper_api" | "vosk" | "mock" (optional)

**Response:**
```json
{
  "type": "audio_response",
  "transcript": {},
  "segments_processed": 3,
  "responses": ["Processed segment 1", ...]
}
```

#### `GET /api/corrections/<concept>`
Returns the correction history for a given concept.

**Response (JSON):**
```json
{
  "concept": "dog",
  "corrections": [
    {
      "subject": "dog",
      "relation": "is",
      "old_value": "reptile",
      "new_value": "mammal",
      "corrected_by": "alice",
      "original_speaker": "bob",
      "timestamp": "2026-04-15T..."
    }
  ],
  "properties": {
    "taught_by": "alice",
    "source_type": "clarification",
    "correction_count": 1
  }
}
```

Sources correction records from MongoDB and includes inline properties from the fact metadata. Returns an empty corrections list if no corrections exist for the concept.

#### `GET /api/questions`
Returns curiosity engine questions.

**Response:**
```json
{
  "questions": ["What does dog eat?", "Can cats fly?", ...],
  "count": 5,
  "type": "questions"
}
```

#### `GET /api/graph`
Returns knowledge graph data for visualization.

**Response (JSON):**
```json
{
  "nodes": [
    {
      "id": "dog",
      "label": "Dog",
      "connections": 5,
      "outgoing": 3,
      "incoming": 2,
      "is_lonely": false,
      "relations": {"is": ["animal"], "can": ["bark"]},
      "creators": ["alice"]
    }
  ],
  "edges": [
    {
      "source": "dog",
      "target": "animal",
      "relation": "is",
      "weight": 1.5,
      "taught_by": "alice",
      "source_type": "user",
      "corrected_by": null,
      "original_value": null,
      "correction_count": 0
    }
  ],
  "co_occurrences": [
    {"entity1": "dog", "entity2": "cat", "count": 3}
  ],
  "patterns": [
    {"name": "X is Y", "type": "category", "confidence": 0.85, "entities": [...]}
  ],
  "potential_edges": [...],
  "clusters": [...],
  "transitive_gaps": [...],
  "missing_properties": [...],
  "lonely_neurons": [...],
  "statistics": {}
}
```

## How It Works

### Backend (web_app.py)

**Initialization:**
- Creates Loom instance with optional MongoDB connection
- Links context to knowledge graph for semantic resolution
- Sets Flask routes

**Chat Handler (`/api/chat`):**
1. Extract message and user from request
2. Tag facts with user's speaker_id (for later forgetting)
3. If starts with `/`:
   - Parse as command (lowercase, strip leading `/`)
   - Match against known commands
   - Call corresponding handler (returns JSON response)
4. Else if looks like JSON array:
   - Parse and load as training facts
   - Return count loaded
5. Else:
   - Detect paragraph vs. single statement
   - Use `process_paragraph()` or `process_with_activation()`
   - Return response

**Neuron Info (`get_neuron_info()`):**
- Per-fact detail now includes `taught_by` (speaker_id), `source_type`, and `corrected_by` fields
- Enables the frontend to display who taught each fact and whether it has been corrected

**User-Scoped Forgetting:**
- `forget_user_facts()` removes facts where `speaker_id` matches username
- Works with both JSON and MongoDB storage
- Rebuilds frame manager after removal

**File Upload Handler (`/api/upload-training`):**
1. Validate file type (.json or .txt)
2. Decode UTF-8 content
3. For JSON:
   - Parse as array of objects
   - Validate each item (subject, relation, object required)
   - Accept `s/r/o` aliases
4. For TXT:
   - Split by newlines
   - Skip empty lines and comments (#)
   - Split by pipe (|) or comma (,)
   - Validate 3 parts per line
5. Return count loaded + any errors

**Graph API (`/api/graph`):**
1. Collect all nodes (subjects + objects from all facts)
2. Build incoming/outgoing connection counts
3. Get fact creator (speaker_id) per node
4. Create nodes with metadata (label, connections, relations, creators)
5. Create edges with Hebbian weights and provenance metadata (`taught_by`, `source_type`, `corrected_by`, `original_value`, `correction_count`)
6. Query discovery engine for:
   - Co-occurrence patterns
   - Discovered relation patterns
   - Suggested new connections
   - Emergent clusters
   - Transitive gaps
   - Missing properties
   - Lonely neurons
7. Return comprehensive graph data for frontend visualization

### Frontend (web_chat.html)

**Architecture:**
- Single HTML file with embedded CSS and JavaScript
- Dark theme with accent colors (indigo)
- Responsive layout (chat container, input area, optional info panel)

**Components:**

**Header:**
- Logo and title ("Loom")
- Action buttons: Train, Stats, Questions, Clear, Forget, Account
- Account icon shows username initials
- Training info modal with format examples

**Chat Area:**
- Message list (scrollable, auto-scroll to bottom)
- User messages (right-aligned, accent color)
- Assistant messages (left-aligned, bordered)
- Info messages (left border, monospace font)
- Error messages (red border)
- Typing indicator (3 animated dots)

**Input Area:**
- Auto-expanding textarea
- Placeholder: "Teach, ask, or use /commands"
- Send button (keyboard: Ctrl+Enter or Cmd+Enter)
- Clear chat button

**Info Panel (Side or Bottom on Mobile):**
- Toggles from commands like `/show`, `/activation`
- Displays formatted output (pre-wrapped, monospace)
- Close button to dismiss

**Drag-Drop Zone:**
- Overlay appears when file dragged over window
- Accepts .json, .txt files
- Shows visual feedback (pulsing border, glow)

**Key Interactions:**

```javascript
// Send message (auto-submit on Ctrl+Enter)
input.addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.key === 'Enter') sendMessage();
});

// Auto-expand textarea
textarea.addEventListener('input', () => {
  textarea.style.height = 'auto';
  textarea.style.height = textarea.scrollHeight + 'px';
});

// Drag-drop file upload
document.addEventListener('dragover', () => dropOverlay.classList.add('active'));
document.addEventListener('drop', (e) => {
  const file = e.dataTransfer.files[0];
  if (file.type.endsWith('json') || file.name.endsWith('.txt')) {
    uploadTraining(file);
  }
});

// Graph visualization (canvas-based)
function renderGraph(data) {
  // D3-like force layout or custom physics engine
  // Render nodes, edges, co-occurrences, potential edges
  // Handle node click → show details
}

// Per-user state
function setUsername(name) {
  localStorage.setItem('loomUser', name);
  sendAllMessages({ user: name }); // Re-tag facts
}
```

**Dark Theme Colors:**
- Primary bg: `#0f0f0f` (black)
- Secondary bg: `#1a1a1a` (dark gray)
- Tertiary bg: `#252525` (medium gray)
- Accent: `#6366f1` (indigo)
- Text: `#ffffff` (white)
- Border: `#2e2e2e` (dark)

**Responsive Design:**
- Desktop: Info panel on left (300px)
- Mobile (max-width 768px): Info panel at bottom (50vh max)

**Toast Notifications:**
- Auto-appear top-right
- Types: success (green), error (red), info
- Auto-dismiss after 5 seconds or manual close

**Training Modal:**
- Shows JSON/TXT format examples
- Drag-drop zone, file input
- Progress spinner during upload
- Success/error toast feedback

**Account Menu:**
- Username input with validation
- Forget facts for this user
- Account icon shows initials (uppercase first char)

## Dependencies

**Backend:**
- `flask` — Web server and routing
- `loom.brain.Loom` — Core system
- `loom.normalizer` — Concept normalization
- `json` — Data parsing
- `os` — File operations

**Frontend:**
- Vanilla JavaScript (ES6+)
- No external dependencies (no jQuery, React, D3, etc.)
- Canvas API (if graph visualization uses canvas)
- HTML5 Drag-Drop API
- Local Storage API (user preferences)

**Imported by:**
- Entry point: `python web_app.py` starts Flask server
- Browser: Navigate to `http://localhost:5000`

## Examples

### Chat Examples

**Natural Language:**
```
you > dogs are animals
loom > Noted: dogs is animals.

you > what can birds do?
loom > Birds can: fly (confidence: high), sing, nest-build
```

**Commands:**
```
you > /stats
Storage Statistics

Storage: MongoDB
Neurons: 156
Synapses: 423
Procedures: 5
Inferences: 12
Conflicts: 2

you > /frame animal
Frame: animal
- Confirmed attributes:
  - can: move, eat, breathe
  - is: organism
  - has: DNA
- Potential attributes:
  - might: feel emotions
  - typically: has legs
```

**Training Upload:**
```
[Drag animals.json onto window]
Training Info Modal shows:
- Format: JSON array of {subject, relation, object}
- Click upload or drag file
→ Toast: "Loaded 47 facts!"
```

**Graph Interaction:**
```
Canvas shows:
- Nodes (circles) labeled with concept names
- Edges (lines) labeled with relation type
- Node size = connection count
- Color = concept type
- Click node → highlight neighbors, show details panel
- Hover edge → show relation type
```

### Training File Formats

**JSON (`animals.json`):**
```json
[
  {"subject": "dog", "relation": "is", "object": "animal"},
  {"subject": "dog", "relation": "can", "object": "bark"},
  {"subject": "cat", "relation": "is", "object": "animal"},
  {"s": "bird", "r": "can", "o": "fly"}
]
```

**TXT (`animals.txt`):**
```
dog | is | animal
dog | can | bark
cat | is | animal
bird , can , fly

# Comment lines ignored
elephant | is | mammal
```

**Pasted JSON Array:**
```
you > [{"subject": "whale", "relation": "is", "object": "mammal"}]
loom > Loaded 1 facts from pasted JSON.
```

### Server Initialization

```python
# web_app.py
from loom import Loom
from flask import Flask

app = Flask(__name__)
loom = Loom(
    verbose=False,
    use_mongo=True,
    mongo_uri="mongodb://loom:password@localhost:27017/loom_memory",
    database_name="loom_memory"
)
loom.context.set_knowledge_ref(loom.knowledge)

if __name__ == '__main__':
    print("Loom Web Interface")
    print("Storage: MongoDB")
    print("Database: loom_memory")
    stats = loom.get_stats()
    print(f"Loaded: {stats['nodes']} neurons, {stats['facts']} synapses")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, port=5000)
```

**Run:**
```bash
pip install flask
python web_app.py
# Open http://localhost:5000
```
