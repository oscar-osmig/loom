# Conversation Context

## Overview

The context module maintains conversational state and enables coreference resolution (pronoun → referent). It tracks topics, recent entities with salience scores, conversation modes, and dialogue types. The context detection module detects qualifiers from natural language (scientific context, temporal modifiers, scope).

## Key Concepts

**Entity Salience**: A weighted score indicating how "active" an entity is in the conversation. Subjects (role=subject) start at 3.0, objects at 2.0, others at 1.0. Salience decays 0.3 per turn, favoring recent mentions.

**Salience-Based Coreference**: To resolve "it" or "they", the context returns candidates sorted by salience (most salient first), optionally filtered by animacy constraints (he/she → animate; it → inanimate).

**Entity Mention**: Wraps text, role (subject/object/other), turn number, animacy, plurality. Used internally for coreference resolution.

**Conversation Modes**: "normal", "teaching", "questioning", "correcting", "clarifying" — track dialogue state.

**Dialogue Types**: "factual", "personal", "question", "opinion", "chit_chat" — categorize user intent.

**Topic Stack**: Recent topics (max 5) for nested discussions. When a new main subject appears, the old topic is pushed.

## API / Public Interface

### context.py

**`ConversationContext(history_size: int = 10)`**: Main class. Initialize once per conversation.

**Public methods**:

**`update(subject: str = None, relation: str = None, obj: str = None, statement_type: str = "statement")`**: Update context after processing a statement.
- Records subject/object as entities (adds to entity_mentions with salience)
- Updates topic if subject differs from current
- Stores statement in recent_statements deque
- Advances turn (increments current_turn)

**`add_entity(text: str, role: str = 'other')`**: Track a mentioned entity with salience scoring.
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

### Context Detection Patterns

**Scientific**: Detects "biologically", "species", "taxonomy", "molecule", "organism", etc.

**Domestic**: Detects "pet", "house cat", "indoor", "at home", etc.

**Cultural**: Detects "culture", "traditionally", "mythology", "folklore"

**Temporal**: Detects "past", "historically", "currently", "1950s", "century"

**Geographic**: Detects "Africa", "tropical", "desert", "marine", "ocean"

Returns the first matching context; default is "general".

## Dependencies

- **context.py imports**: `time`, `collections.deque`, `typing`, `re`
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

### Clarification Workflow
```python
ctx = ConversationContext()
ctx.set_clarification("Do you mean the blue one?", "about_color")
# mode = "clarifying", pending_clarification is set

# ... get user response ...

ctx.clear_clarification()
# mode = "normal", pending_clarification = None
```
