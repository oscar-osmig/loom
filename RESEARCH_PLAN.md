# Loom Research + Accuracy Improvement Plan

## Goal
Improve Loom so it learns from conversation in a mouth-to-mouth style (speech/text input), strengthens symbolic logic over time, and actively asks high-value follow-up questions. The target behavior is logic-first reasoning like:

- If `A -> B` and `B -> C`, infer `A -> C`
- Use that inference process to strengthen concept connections
- Continuously generate clarifying and exploratory questions in the background

---

## Research Summary (current codebase)

### 1) Symbolic logic foundation already exists
- Loom already performs symbolic transitive chaining in the inference engine.
- `transitive_chain()` and `_apply_syllogism()` encode the exact `A->B, B->C => A->C` pattern.
- Inferred facts are materialized back into knowledge via `add_fact`, making them reusable.

### 2) There is already a background reasoning thread
- `_background_loop()` runs periodically and processes recent facts.
- It already handles transitive inference and propagation behavior.
- This is the natural insertion point for a “question generation / curiosity” loop.

### 3) Conversation parsing is broad but mostly pattern-based
- Parser runs a large ordered set of handlers for corrections, queries, patterns, and discourse fallback.
- Clarification scaffolding is already present (`pending_clarification`).
- This is good for breadth, but accuracy can improve with stronger confidence/provenance and rule dependencies.

### 4) “Unknowns” are already represented
- The parser emits `has_open_question` facts in multiple places.
- This is ideal seed data for an active question queue.

### 5) No real speech ingestion pipeline yet
- Runtime interfaces currently ingest text (CLI/web chat).
- There is discourse text analysis called `analyze_speech`, but not raw audio-to-text ingestion.

### 6) Storage lacks inference dependency tracking
- Facts include confidence and constraints.
- But there is no robust dependency graph tying inferred facts to source premises/rules.
- Without this, correction/retraction cannot reliably retract downstream inferences.

---

## Plan

## Phase 1 — Increase logical reliability first (before speech)
1. **Inference provenance**
   - Add metadata to inferred facts:
     - `source_type` (`user`, `inference`, `clarification`)
     - `premises` (supporting facts)
     - `rule_id` / derivation token
     - `created_at` and optional `speaker_id`
2. **Truth maintenance**
   - On correction/retraction, invalidate or downgrade dependent inferred facts.
   - Prevent stale inferences from surviving premise changes.
3. **Confidence policy**
   - Direct user facts: high by default.
   - New inferred facts: medium/low until reinforced.
   - Repeatedly observed facts increase confidence.

### Deliverable
A dependency-aware symbolic memory where logic remains self-consistent after corrections.

---

## Phase 2 — Add Curiosity Engine (active questioning)
1. Build `QuestionGenerator` module.
2. On each background cycle:
   - collect unresolved `has_open_question`
   - scan contradictions
   - detect high-value chain gaps
3. Rank candidate questions by expected utility:
   - contradiction resolution
   - missing causal/relational bridges
   - low-confidence high-centrality entities
4. Surface one (or top-k) next questions to user in CLI/web responses.

### Example prompts to generate
- “You said A causes B and B causes C. Should we store that A causes C?”
- “What causes X?”
- “Can you clarify whether Y is Z or not Z?”

### Deliverable
A background process that proactively strengthens the graph through targeted dialogue.

---

## Phase 3 — Add speech ingestion (mouth-to-mouth)
1. Add speech endpoint (e.g., `/api/speech`) or streaming channel.
2. Pipeline:
   - audio input -> ASR transcript
   - transcript chunking -> parser
   - inference + question generator
3. Persist speech provenance:
   - transcript snippet, timestamp, confidence, speaker

### Deliverable
Audio conversation can teach Loom while preserving symbolic logic and traceability.

---

## Phase 4 — Introduce explicit rule neurons
1. Add rule memory objects:
   - `premises[]`, `conclusion`, `support_count`, `confidence`, `provenance[]`
2. Generate rules from repeated conversational patterns.
3. Fire rules in background for forward chaining.
4. Ask confirmation questions for low-confidence candidate rules.

### Deliverable
Reusable, explicit logic structures that make reasoning deeper and more stable.

---

## Phase 5 — Measure and improve learning accuracy
Track metrics such as:
- inference precision (validated vs corrected)
- contradiction rate over time
- question usefulness (answer rate + confidence gain)
- time to resolve open questions
- graph consistency after retractions

### Deliverable
Objective signal that the system is becoming more accurate and smarter through dialogue.

---

## Recommended First Sprint (high ROI)
1. Add inference provenance fields and storage support.
2. Add dependency-aware rollback for corrected facts.
3. Implement a basic question queue using `has_open_question` + contradictions.
4. Expose one best-next question in CLI/web responses.

This delivers immediate gains in reliability and active learning, without changing Loom’s symbolic philosophy.

---

## Notes
- Keep architecture logic-first and interpretable.
- Avoid black-box prediction dependencies for core reasoning.
- Speech can be modular; symbolic parser/inference remain source-agnostic.
