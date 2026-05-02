# Conversation Context

## Overview

The context module maintains conversational state and enables coreference resolution (pronoun → referent). It tracks topics, recent entities with salience scores, conversation modes, and dialogue types. The context detection module detects qualifiers from natural language (scientific context, temporal modifiers, scope).

## Key Concepts

**Entity Salience**: A weighted score indicating how "active" an entity is in the conversation. Subjects (role=subject) start at 3.0, objects at 2.0, others at 1.0. Salience decays 0.3 per turn, favoring recent mentions.

**Salience-Based Coreference**: To resolve "it" or "they", the context returns candidates sorted by salience (most salient first), optionally filtered by animacy constraints (he/she → animate; it → inanimate).

**Entity Mention**: Wraps text, role (subject/object/other), turn number, animacy, plurality. Used internally for coreference resolution.

**Entity Type Detection**: Classifies entities as `self`, `system`, or `third_party`. Self-references ("I", "me", "my") and system-references ("you", "loom", "system") are filtered out of coreference candidates so pronouns only resolve to third-party entities.

**Hypothetical Mode**: Triggered by phrases like "what if", "imagine", "suppose". Facts stated during hypothetical mode are tracked in a separate `hypothetical_facts` list and are **not** persisted to the knowledge graph. The mode auto-exits after 2+ definitive (non-hypothetical) statements, and responses are prefixed with `[Hypothetical]`.

**Topic Relevance Scoring**: Scores how related a new topic is to the current topic using knowledge graph connections (direct links, shared parents, shared relations, co-mentions).

**Previous Topics**: A bounded history of the last 5 topics, enabling return to a prior topic when the conversation circles back.

**Conversation Modes**: "normal", "teaching", "questioning", "correcting", "clarifying" — track dialogue state.

**Dialogue Types**: "factual", "personal", "question", "opinion", "chit_chat" — categorize user intent.

**Topic Stack**: Recent topics (max 5) for nested discussions. When a new main subject appears, the old topic is pushed.

## API / Public Interface

### context.py

**Constants**:
- `ENTITY_SELF = 'self'` — Entity type for first-person references
- `ENTITY_SYSTEM = 'system'` — Entity type for system/assistant references
- `ENTITY_THIRD_PARTY = 'third_party'` — Entity type for all other entities
- `_SELF_WORDS` — Set of first-person words (`"i"`, `"me"`, `"my"`, `"myself"`, etc.)
- `_SYSTEM_WORDS` — Set of system-referencing words (`"you"`, `"loom"`, `"system"`, etc.)

**`detect_entity_type(word: str) -> str`**: Module-level function. Returns `ENTITY_SELF`, `ENTITY_SYSTEM`, or `ENTITY_THIRD_PARTY` based on whether `word` matches `_SELF_WORDS` or `_SYSTEM_WORDS`.

**`ConversationContext(history_size: int = 10)`**: Main class. Initialize once per conversation.

**Public methods**:

**`update(subject: str = None, relation: str = None, obj: str = None, statement_type: str = "statement")`**: Update context after processing a statement.
- Records subject/object as entities (adds to entity_mentions with salience)
- Updates topic if subject differs from current
- Stores statement in recent_statements deque
- Advances turn (increments current_turn)

**`add_entity(text: str, role: str = 'other')`**: Track a mentioned entity with salience scoring.
- Calls `detect_entity_type()` first; skips self/system references so they never become coreference candidates
- Decays existing entities based on current_turn
- Detects animacy (regex pattern) and plurality
- Keeps top 15 entities by salience (to avoid memory bloat)

**`resolve_pronoun(text: str) -> str`**: Replace pronouns with referents using enhanced resolution.
- Uses salience scoring + recency + animacy constraints
- Fallback to simple resolution (last_subject, last_object)
- Returns text with pronouns replaced
- Example: "The dog saw the cat. It ran away." → "The dog saw the cat. cat ran away."

**`resolve_with_semantics(pronoun: str, verb: str = None) -> Optional[str]`**: Resolve pronoun using semantic fit.
- Gets candidates from get_candidates()
- If verb provided, checks knowledge graph for abilities
- Returns first candidate whose abilities match verb
- Fallback to highest salience

**`get_candidates(pronoun: str) -> List[EntityMention]`**: Get candidate antecedents for a pronoun.
- Filters by animacy constraints:
  - "he/she" → animate entities
  - "it" → inanimate or unknown
  - "they/them" → plural preferred
  - "this/these" → recent preferred
- Returns sorted by salience (highest first)

**`detect_mode(text: str) -> str`**: Detect conversation mode from text.
- "correcting" if contains "no,", "wrong", "incorrect", "actually"
- "questioning" if ends with "?" or starts with question words
- "teaching" (default)

**`detect_dialogue_type(text: str) -> str`**: Detect dialogue type.
- "question" if ends with "?"
- "personal" if contains "I am", "I like", "my ", etc.
- "opinion" if contains "I think", "seems like", "favorite", etc.
- "chit_chat" if contains greetings, pleasantries
- "factual" (default)

**`resolve_dialogue_roles(text: str) -> str`**: Replace first/second person pronouns.
- "I am" → "user is"
- "my " → "user's "
- "you" → preserved (for self-identity queries like "what are you?")

**`set_knowledge_ref(knowledge_graph)`**: Link to knowledge graph for semantic checking in resolve_with_semantics().

**`set_clarification(question: str, about: str)`**: Set a pending clarification request; mode becomes "clarifying".

**`clear_clarification()`**: Clear pending clarification; mode reverts to "normal".

**`add_correction(original: str, corrected: str, relation: str = None)`**: Track user correction for learning.

**`get_recent_about(subject: str, limit: int = 3) -> list`**: Get recent statements about a subject.

**`is_follow_up(text: str) -> bool`**: Check if text is a follow-up to previous statement (contains "also", "but", "because", etc.).

**`check_hypothetical_trigger(text: str) -> bool`**: Check if text starts a hypothetical scenario.
- Matches against `HYPOTHETICAL_TRIGGERS` (`"what if"`, `"imagine"`, `"suppose"`)
- Returns `True` if a trigger phrase is found

**`enter_hypothetical(trigger: str = None)`**: Enter hypothetical mode.
- Sets `hypothetical_mode = True`
- Records the trigger phrase in `_hypothetical_trigger`
- Initializes empty `hypothetical_facts` list

**`exit_hypothetical()`**: Exit hypothetical mode.
- Sets `hypothetical_mode = False`
- Clears `hypothetical_facts` and `_hypothetical_trigger`

**`is_hypothetical`** *(property)*: Returns `True` if currently in hypothetical mode.

**`topic_relevance_score(new_topic: str, current_topic: str) -> float`**: Score how related two topics are using the knowledge graph.
- Direct connection between topics: +0.5
- Shared parent concepts: +0.3
- Each shared relation: +0.05
- Co-mention in recent statements: +0.3
- Requires knowledge graph reference (via `set_knowledge_ref`)

**`get_previous_topic() -> Optional[str]`**: Return the most recent previous topic without removing it.

**`return_to_previous_topic() -> Optional[str]`**: Pop and return the most recent previous topic, restoring it as the current topic.

**`get_salient_entities(limit: int = 5) -> List[Tuple[str, float]]`**: Get most salient entities in context (decayed).

**`get_context_summary() -> dict`**: Snapshot of context state.

**`next_turn()`**: Advance to next conversation turn.

### context_detection.py

**`detect_context(text: str) -> str`**: Detect context qualifier.
- Checks patterns for: "scientific", "domestic", "cultural", "temporal", "geographic"
- Returns matched context or "general"
- Example: "Scientifically, dolphins are mammals" → "scientific"

**`detect_temporal(text: str) -> str`**: Detect temporal modifier.
- Returns: "always", "sometimes", "past", "future", "currently"
- Example: "Dogs used to be wild" → "past"
- Default: "always"

**`detect_scope(text: str) -> str`**: Detect scope qualifier.
- Returns: "universal", "typical", "specific"
- "all" → "universal"; "most" → "typical"; "some" → "specific"
- Default: "universal"

## How It Works

### Salience Decay

Each entity has a salience score computed at mention time:
- **Subject role**: 3.0 initial
- **Object role**: 2.0 initial
- **Other role**: 1.0 initial

Each turn, salience decays: `salience = max(0.1, salience - (turns_passed * 0.3))`

Coreference resolution sorts candidates by salience; highest wins.

### Pronoun Resolution Steps

1. **Gather candidates**: Call `get_candidates(pronoun)` to filter by animacy/plurality constraints
2. **Rank by salience**: EntityMention with highest salience is first candidate
3. **Apply semantic fit** (optional): If verb provided and knowledge graph available, check if candidate's abilities match the verb
4. **Fallback**: If no entity mentions yet, use last_subject / last_object
5. **Return**: Best candidate's text; preserve case

### Dialogue Type Detection

Text is categorized into one of 5 types:
1. **Question**: Ends with "?" or starts with "what", "how", "can", etc.
2. **Personal**: Contains "I like", "my ", "I am", "I've"
3. **Opinion**: Contains "I think", "seems", "probably", "favorite"
4. **Chit-chat**: Greetings, pleasantries ("hello", "thanks", "bye")
5. **Factual**: Default; neutral statement

Used to set conversation mode and adjust parsing strategy.

### Entity Type Filtering

When `add_entity()` is called, the text is first passed through `detect_entity_type()`:
1. If the word is in `_SELF_WORDS` (e.g., "I", "me", "my"), it is classified as `ENTITY_SELF` and **skipped**
2. If the word is in `_SYSTEM_WORDS` (e.g., "you", "loom", "system"), it is classified as `ENTITY_SYSTEM` and **skipped**
3. Otherwise it is `ENTITY_THIRD_PARTY` and added normally with salience scoring

This prevents "I" or "you" from appearing as coreference candidates when resolving pronouns like "it" or "they".

### Hypothetical Mode

1. `check_hypothetical_trigger(text)` scans input against `HYPOTHETICAL_TRIGGERS` (`"what if"`, `"imagine"`, `"suppose"`)
2. If triggered, `enter_hypothetical()` activates the mode and records the trigger phrase
3. While `hypothetical_mode` is `True`, facts are appended to `hypothetical_facts` instead of being persisted to the knowledge graph
4. Responses generated during hypothetical mode are prefixed with `[Hypothetical]`
5. The mode **auto-exits** after 2 or more consecutive definitive (non-hypothetical) statements
6. Can also be exited explicitly via `exit_hypothetical()`

### Topic Relevance Scoring

`topic_relevance_score(new_topic, current_topic)` computes a float score using the knowledge graph:

| Signal | Score |
|--------|-------|
| Direct connection between topics | +0.5 |
| Shared parent concepts | +0.3 |
| Each shared relation | +0.05 |
| Co-mentioned in recent statements | +0.3 |

Higher scores indicate the new topic is closely related to the current one, which can inform whether to push the current topic or treat the shift as a natural continuation.

### Previous Topics

`previous_topics` is a `deque(maxlen=5)` that stores displaced topics when the conversation shifts:
- When `update()` detects a new main subject, the old topic is pushed onto `previous_topics`
- `get_previous_topic()` peeks at the most recent entry without removing it
- `return_to_previous_topic()` pops the most recent entry and restores it as the current topic

### Context Detection Patterns

**Scientific**: Detects "biologically", "species", "taxonomy", "molecule", "organism", etc.

**Domestic**: Detects "pet", "house cat", "indoor", "at home", etc.

**Cultural**: Detects "culture", "traditionally", "mythology", "folklore"

**Temporal**: Detects "past", "historically", "currently", "1950s", "century"

**Geographic**: Detects "Africa", "tropical", "desert", "marine", "ocean"

Returns the first matching context; default is "general".

## Dependencies

- **context.py imports**: `time`, `collections.deque`, `typing`, `re`
- **context.py constants**: `ENTITY_SELF`, `ENTITY_SYSTEM`, `ENTITY_THIRD_PARTY`, `_SELF_WORDS`, `_SYSTEM_WORDS`, `HYPOTHETICAL_TRIGGERS`
- **context_detection.py imports**: `re`
- **Used by**: `parser/base.py`, `main.py`, `brain.py` (all reference ConversationContext)
- **Used by**: `parser/` modules use context detection to tag facts with qualifiers

## Examples

### Basic Coreference Resolution
```python
from loom.context import ConversationContext

ctx = ConversationContext()
ctx.update("dog", "sees", "cat")
ctx.update("it", "runs")  # 'it' should resolve

text = "The cat ran away and then it jumped"
resolved = ctx.resolve_pronoun(text)
# "it" resolves to "cat" (last mentioned, object role = salience 2.0)
```

### Animacy-Constrained Resolution
```python
ctx = ConversationContext()
ctx.add_entity("dog", role="subject")        # animate
ctx.add_entity("rock", role="other")         # inanimate

# 'he' prefers animate entities
candidates = ctx.get_candidates("he")
# Returns dog first (animate bonus), not rock
```

### Dialogue Type Detection
```python
ctx = ConversationContext()
ctx.detect_dialogue_type("what are dogs?")     # → "question"
ctx.detect_dialogue_type("I like dogs")        # → "personal"
ctx.detect_dialogue_type("hello, how are you?") # → "chit_chat"
```

### Context Detection
```python
from loom.context_detection import detect_context, detect_temporal

detect_context("Biologically, birds have feathers")     # → "scientific"
detect_temporal("Dogs used to live in the wild")        # → "past"
detect_temporal("Most cats are independent")            # Returns "always" (default)
```

### Entity Type Detection
```python
from loom.context import detect_entity_type, ENTITY_SELF, ENTITY_SYSTEM, ENTITY_THIRD_PARTY

detect_entity_type("I")      # → 'self'
detect_entity_type("you")    # → 'system'
detect_entity_type("dog")    # → 'third_party'

ctx = ConversationContext()
ctx.add_entity("I", role="subject")      # Skipped (self-reference)
ctx.add_entity("dog", role="subject")    # Added normally
ctx.get_salient_entities()               # Only contains "dog"
```

### Hypothetical Mode
```python
ctx = ConversationContext()

ctx.check_hypothetical_trigger("what if dogs could fly?")  # → True
ctx.enter_hypothetical("what if")
ctx.is_hypothetical                                         # → True

# Facts during this mode go to hypothetical_facts, not the knowledge graph
# Responses are prefixed with [Hypothetical]

# After 2+ definitive statements, mode auto-exits
ctx.exit_hypothetical()
ctx.is_hypothetical                                         # → False
```

### Topic Relevance Scoring
```python
ctx = ConversationContext()
ctx.set_knowledge_ref(brain.knowledge)

# If "dog" and "cat" are both connected to "animal" in the graph:
score = ctx.topic_relevance_score("cat", "dog")
# score includes +0.3 for shared parent "animal"
```

### Previous Topics
```python
ctx = ConversationContext()
ctx.update("dog", "is", "animal")       # topic = "dog"
ctx.update("cat", "is", "animal")       # topic = "cat", "dog" pushed to previous_topics

ctx.get_previous_topic()                # → "dog"
ctx.return_to_previous_topic()          # → "dog", topic restored to "dog"
```

### Clarification Workflow
```python
ctx = ConversationContext()
ctx.set_clarification("Do you mean the blue one?", "about_color")
# mode = "clarifying", pending_clarification is set

# ... get user response ...

ctx.clear_clarification()
# mode = "normal", pending_clarification = None
```
