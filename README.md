# Loom v0.8-dev

**A symbolic knowledge system that learns through natural language dialogue.**

> **What's new since v0.6:** Response composer with varied natural-language generation,
> recursive descent grammar parser for complex sentences, pandas batch loading (2,281 facts/sec),
> pydantic schemas, style learner with feedback loop, Svelte 5 frontend with visualizer,
> file management, per-user settings. See [WHERE_WE_LEFT_OFF.md](./WHERE_WE_LEFT_OFF.md) for
> full status and roadmap.

Loom is a transparent, explainable cognition engine. It stores knowledge as a directed graph of *neurons* (concepts) and *synapses* (connections), reasons over that graph with explicit symbolic primitives, and explains every conclusion it draws back to the facts that produced it.

It learns by being talked to. You teach it sentences, ask it questions, correct its mistakes, and over time it weaves together a coherent picture of whatever domain you bring to it.

---

## Table of Contents

1. [Vision and Goals](#vision-and-goals)
2. [What "No ML" Means in Loom](#what-no-ml-means-in-loom)
3. [Quick Start](#quick-start)
4. [The Core Data Model](#the-core-data-model)
5. [How Loom Works — The Full Pipeline](#how-loom-works--the-full-pipeline)
6. [Subsystems in Depth](#subsystems-in-depth)
7. [CLI Commands](#cli-commands)
8. [Web Interface and HTTP API](#web-interface-and-http-api)
9. [Training Packs and Custom Data](#training-packs-and-custom-data)
10. [Storage Backends](#storage-backends)
11. [Project Layout](#project-layout)
12. [Roadmap](#roadmap)
13. [Engineering Rules](#engineering-rules)
14. [What Loom is NOT](#what-loom-is-not)
15. [Documentation](#documentation)

---

## Vision and Goals

Most modern AI systems are statistical: they compress patterns into vectors, learn distributions, and produce outputs whose justifications cannot be inspected. They are opaque by construction.

Loom takes the opposite stance. It is built on the bet that **a small number of explicit symbolic primitives, applied carefully and consistently, can produce a system that reasons in ways a human can fully follow** — and that this is more valuable for many tasks than a black box that is occasionally brilliant and occasionally wrong for reasons no one can name.

Loom's goals:

- **Total transparency.** Every fact in the graph carries provenance: who said it, when, with what confidence, and which other facts it depends on. Every inference can be traced backwards to the user statements that justified it.
- **Conversational learning.** Teaching Loom is supposed to feel like talking to a curious, honest student. You tell it things, it asks when it's confused, and you correct it when it's wrong.
- **Biologically inspired primitives.** Hebbian connection strengthening, Collins & Loftus spreading activation, and RST-style discourse analysis are first-class — but every one of them is hand-implemented in plain Python. No frameworks, no embeddings.
- **Correctability.** When you say "no, that's wrong," Loom must be able to retract the offending fact *and* every inference that depended on it, then leave the rest of the graph intact.
- **Explainability over coverage.** Loom would rather refuse to answer than fabricate. If it doesn't know, it asks. If it's guessing, it labels the guess.

The end state Loom is aiming for is summarized in `roadmap.md`:

> **The most precise, explainable symbolic reasoning engine you can build.**

Not the most general. Not the most powerful. The most *honest*.

---

## What "No ML" Means in Loom

This is the part that confuses people most, so it gets its own section.

**"No ML" in Loom means: no machine-learning *libraries*.** The codebase has zero dependencies on torch, tensorflow, scikit-learn, transformers, sentence-transformers, spaCy, NLTK's statistical models, gensim, or any other ML tooling. There are no embedding lookups, no model files to download, no GPUs required, no training loops in the gradient-descent sense.

What Loom *does* have, and what it considers entirely fair game:

- **Hebbian learning** as a hand-coded weight update rule (`processing.py`). When a connection is used, its weight goes up; when it sits idle, it decays. The math is six lines of arithmetic.
- **Spreading activation** as a hand-coded breadth-first decay (`activation.py`). Concepts get activation levels that propagate to neighbors with a decay factor. Collins & Loftus, 1975, implemented as a dictionary and a loop.
- **Similarity metrics** computed by counting shared attributes (`frames.py`). Tier-weighted set overlap. Pure Python.
- **Discourse analysis** (`chunker.py`, `discourse.py`) using a hand-curated table of connective words and RST relation types.

The line is between *hand-implementing the math* (welcome) and *importing a library to do it for you* (not welcome). Loom is trying to prove a point about how far you can get with explicit, inspectable rules — and that point only stands if every rule is visible in the source.

**Required dependency:** Python 3.7+ standard library.

**Optional dependencies:**
- `pymongo` — MongoDB storage backend (auto-falls back to a JSON file if missing)
- `flask` — needed only for `web_app.py`
- ASR backends for the optional speech subsystem (`whisper`, `google-cloud-speech`, `azure-cognitiveservices-speech`, `vosk`) — none required for normal use

That's the entire dependency surface.

---

## Quick Start

**CLI:**
```bash
python main.py
```

**Web interface:**
```bash
pip install flask
python web_app.py
# open http://localhost:5000
```

**Windows Unicode fix** (if box-drawing characters break your terminal):
```bash
set PYTHONIOENCODING=utf-8 && python main.py
```

**A first conversation:**
```
> dogs are mammals
Got it, dogs are mammals.

> mammals have fur
Got it, mammals have fur.

> do dogs have fur?
Yes, dogs have fur. (inherited from mammals)

> birds can fly
Got it, birds can fly.

> penguins are birds
Got it, penguins are birds.

> can penguins fly?
Yes, penguins can fly. (inherited from birds)

> no, penguins cannot fly
Corrected. Penguins cannot fly.

> can penguins fly?
No, penguins cannot fly.
```

That last exchange is the whole project in miniature: you taught it a default, the default propagated by inheritance, you flagged the exception, and the system retracted the bad inference and rebuilt the answer.

---

## The Core Data Model

Every fact in Loom is a **quad with properties**:

```
(subject, relation, object, context)  +  properties{...}
```

**Components:**

| Field | Type | Example |
|---|---|---|
| `subject` | string (normalized) | `"penguin"` |
| `relation` | string (lowercase verb or relation type) | `"can"`, `"is"`, `"eats"`, `"causes"` |
| `object` | string (normalized) | `"swim"` |
| `context` | string | `"general"`, `"scientific"`, `"hypothetical"` |

**Properties dict** (carried alongside every fact):

| Property | Values | Purpose |
|---|---|---|
| `confidence` | `"high"` / `"medium"` / `"low"` | Strength of belief |
| `temporal` | `"always"`, `"sometimes"`, `"past"`, `"future"`, `"currently"` | When the fact applies |
| `scope` | `"universal"`, `"typical"`, `"specific"` | Generality |
| `conditions` | list | Constraints under which the fact holds |
| `source_type` | `"user"`, `"inference"`, `"clarification"`, `"inheritance"`, `"system"`, `"speech"` | Where the fact came from |
| `speaker_id` | string | Which user added it (for multi-user web sessions) |
| `premises` | list of triples | The facts this one was derived from |
| `rule_id` | string | The rule that fired, if any |
| `derivation_id` | string | Unique ID for this derivation chain |
| `created_at` | ISO timestamp | When the fact was added |

**Confidence levels:**

- **`high`** — directly stated by the user, or confirmed multiple times
- **`medium`** — inferred from a clear chain (transitive closure, inheritance, rule firing)
- **`low`** — weak inference, hedged input ("maybe", "probably"), or aged

Repeated mention promotes confidence (`low → medium → high`) — this is *memory consolidation*, not learning rate. See `consolidate_confidence()` in `loom/brain.py`.

**Inheritable relations** (the ones that propagate properties down a category chain): `is`, `is_a`, `type_of`, `kind_of`.

**Transitive relations** (the ones that support chained reasoning, A→B→C): `is`, `looks_like`, `causes`, `leads_to`, `part_of`.

---

## How Loom Works — The Full Pipeline

Here is what happens when you type a sentence into Loom:

```
            ┌─────────────────────────────────────┐
            │            Input text               │
            └────────────────┬────────────────────┘
                             │
                             ▼
            ┌─────────────────────────────────────┐
            │   Structural Extractor              │  loom/structural.py
            │   Strips & captures:                │
            │     • hedges    (maybe, probably)   │
            │     • temporal  (yesterday, always) │
            │     • frequency (sometimes, never)  │
            │     • degree    (very, extremely)   │
            │     • comparisons (bigger than X)   │
            │     • quantities (4 legs)           │
            │     • purpose   (used for X)        │
            └────────────────┬────────────────────┘
                             │ clean_text + metadata
                             ▼
            ┌─────────────────────────────────────┐
            │   Context Detection                 │  loom/context_detection.py
            │   • context  (general/scientific…)  │
            │   • temporal scope                  │
            │   • universality scope              │
            └────────────────┬────────────────────┘
                             │
                             ▼
            ┌─────────────────────────────────────┐
            │   Pronoun Resolution                │  loom/context.py
            │   Resolves it/they/he/she using     │
            │   salience-weighted recent entities │
            └────────────────┬────────────────────┘
                             │
                             ▼
            ┌─────────────────────────────────────┐
            │   Sentence Simplification           │  loom/simplifier.py
            │   Splits "X need A, B, C" into      │  loom/advanced_simplifier.py
            │   atomic facts. Handles lists,      │
            │   appositives, relative clauses.    │
            └────────────────┬────────────────────┘
                             │
                             ▼
            ┌─────────────────────────────────────┐
            │   Parser (40+ checks in priority)   │  loom/parser/
            │   Each clause runs through pattern  │
            │   handlers in strict order until    │
            │   one matches.                      │
            └────────────────┬────────────────────┘
                             │ (subject, relation, object)
                             ▼
            ┌─────────────────────────────────────┐
            │   Frame Manager                     │  loom/frames.py
            │   Routes attribute facts into the   │
            │   confirmed or potential tier of    │
            │   the appropriate slot.             │
            └────────────────┬────────────────────┘
                             │
                             ▼
            ┌─────────────────────────────────────┐
            │   Brain.add_fact()                  │  loom/brain.py
            │   • validate entity names           │
            │   • detect contradictions           │
            │   • resolve to existing neuron      │
            │   • write to storage                │
            │   • emit to inference engine        │
            └────────────────┬────────────────────┘
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
   ┌───────────────────────┐   ┌─────────────────────────┐
   │  Storage              │   │  Inference Engine       │
   │  loom/storage/        │   │  loom/inference.py      │
   │  Mongo or JSON        │   │  • activation spread    │
   └───────────────────────┘   │  • Hebbian strengthen   │
                               │  • property inheritance │
                               │  • transitive closure   │
                               │  • rule firing          │
                               └────────────┬────────────┘
                                            │
                                            ▼
                            ┌──────────────────────────────┐
                            │  Background daemon (3s loop) │
                            │  • activation decay          │
                            │  • Hebbian connection decay  │
                            │  • discovery cycle           │
                            │  • frame manager cycle       │
                            │  • rule re-firing            │
                            └──────────────────────────────┘
```

Every step in this pipeline is a discrete file you can read and reason about. Nothing is hidden behind a model.

---

## Subsystems in Depth

### 1. The Structural Extractor (`loom/structural.py`)

Before the parser gets to interpret a sentence, the structural extractor runs over it and pulls out the **modifiers** that don't change *what* is being said, only *how strongly* and *under what conditions*.

This is implemented as **word categories plus position rules**, not regex patterns:

- `HEDGE_WORDS` — `{maybe, perhaps, probably, seemingly, possibly, …}`
- `DEGREE_WORDS` — `{very, extremely, quite, absolutely, …}`
- `FREQUENCY_WORDS` — `{always, never, sometimes, rarely, often, …}`
- `TEMPORAL_WORDS` and `TEMPORAL_PHRASES` — `{yesterday, today, "last week", "in the morning", …}`
- `COMPARATIVE_WORDS` — `{more, less, bigger, faster, …}`
- `SUPERLATIVE_WORDS` — `{most, least, best, largest, …}`
- `PURPOSE_STARTERS` — `{"in order to", "so that", "designed for", …}`
- `NUMBER_WORDS` — word-to-int map (`one → 1`, `dozen → 12`, …)

The extractor returns an `ExtractionResult` containing the **clean text** (with modifiers stripped) plus metadata: `confidence`, `temporal`, `frequency`, `degree`, `comparison`, `quantities`, `purpose`, and an `extra_facts` list.

For example, *"yesterday I saw a really big dog that was bigger than my cat"* becomes:

```
clean_text:  "I saw a dog"
temporal:    "yesterday"
degree:      "really"
extra_facts: [("dog", "bigger_than", "cat")]
```

The parser then works on the clean text, and the metadata is attached to whatever facts get added. Hedged statements ("maybe cats are orange") are routed to the **potential tier** of the frame system rather than asserted.

This layer exists so that the parser doesn't need 40 different regex patterns for hedging — the pattern is captured once, declaratively, in word lists.

### 2. The Parser (`loom/parser/`)

The parser is the largest single subsystem in Loom. It is organized as a **strictly ordered cascade of pattern checks**: each clause is run through every check in sequence until one of them matches and produces a fact (or a query response).

Order matters. Earlier checks have higher precedence and silently consume input.

**Priority order in `parser/base.py`:**

1. `_check_clarification_response` — answer a pending clarification question
2. `_check_correction` — *"no, that's wrong"*, *"actually"*
3. `_check_refinement` — *"only when…"*, *"except…"*
4. `_check_procedural` — *"first…, then…, finally…"*
5. `_check_however_pattern` — *"However, X"*
6. `_check_because_pattern` — *"Because X, Y"* (causal link)
7. `_check_if_then_rule` — explicit rule learning
8. `_check_informational_pattern` — encyclopedic sentences with relative clauses, appositives, pronouns (`parser/informational.py`)
9. `_check_contrast_pattern` — *"X are A, while Y are B"*
10. `_check_name_query` — *"what is the name of X?"*
11. `_check_self_identity_query` — *"what are you?"*
12. **`_check_generic_query`** — the generic SVO query engine (see below)
13. `_check_negation` — *"X is not Y"*, *"X cannot Y"*
14. ...60+ more specific patterns and queries
15. `_check_is_statement` — fallback *"X is Y"*
16. `_check_discourse_patterns` — natural-speech patterns
17. `_learn_from_conversation` — final fallback extraction

**The parser is split across these modules:**

| Module | Purpose |
|---|---|
| `base.py` | The `Parser` class and the cascade orchestration |
| `constants.py` | Shared word lists (CORRECTION_WORDS, REFINEMENT_WORDS, COLORS, …) |
| `relations.py` | `get_relation_for_verb()` — verb conjugation and relation mapping |
| `queries_basic.py` | Simple queries: name, color, where, who, what-has, what-verb, how-many |
| `queries_complex.py` | Complex queries: can, why, what-causes, effects, how, are/is |
| `queries_knowledge.py` | Domain queries: classification, breathing, reproduction |
| `patterns_basic.py` | Negation, looks_like, analogy, same_as |
| `patterns_relations.py` | is_statement, conditional, becomes, list learning |
| `patterns_discourse.py` | Conversational patterns, implicit continuation, chit-chat, first-person |
| `informational.py` | Encyclopedic sentences with relative clauses and appositions |
| `handlers.py` | Corrections, clarifications, procedural, however/because |

### 3. The Generic Query Engine (`loom/query_engine.py`)

A recent refactor (commit `2e2be24`) replaced the bulk of Loom's hardcoded query handlers with a single **generic SVO question parser**.

It works in three steps:

1. `parse_question(text)` — extract `{q_word, subject, verb, relation, object?, direction}` from the question
2. Map the verb to a relation via `get_relation_for_verb()` (which uses morphology and the `RELATION_BY_ANY_VERB` table from `parser/relations.py`)
3. Do a forward or reverse graph lookup and format the result

This handles: *what does X verb?*, *what is X made of?*, *who verb's X?*, *where does X verb?*, *when does X verb?*, *how does X verb Y?*, *can X verb Y?*, *does X verb Y?* — all from the same code path.

When you add a new question type, prefer extending `query_engine.py` to adding another `_check_*` to `parser/base.py`.

### 4. SVO Verb Detection (`loom/svo.py`)

Loom does not maintain a global verb list. Instead, `svo.py` decides whether a word is a verb using **morphology and position**:

- Suffix indicators: `-s` (third person), `-ed` (past), `-ing` (progressive), `-ate`/`-ize`/`-ify` (productive verb suffixes)
- A small `IRREGULAR_PAST` table for common irregular past tenses
- A `NON_VERBS` set covering function words (determiners, prepositions, conjunctions, common adverbs)
- A position rule: a verb follows a subject and precedes an object
- Falls back to checking `RELATION_BY_ANY_VERB` for known mappings
- Supports verb-plus-preposition phrases like *"live in"*, *"feed on"*

This is what lets the parser handle verbs it has never seen before without anyone needing to register them.

### 5. The Frame System (`loom/frames.py`) — *headline of v0.6*

The frame system is Loom's structured-attribute layer. It exists to solve a specific problem: *the difference between what something IS and what something CAN BE*.

The classic example: a user says *"cats are orange"* (a definitional claim) versus *"cats can be orange"* (a possibility). Flat triples can't tell these apart cleanly. The frame system can.

**Core structures:**

- **`AttributeSlot`** — `{confirmed: Set[str], potential: Set[str]}`. Two tiers per slot.
- **`ConceptFrame`** — A concept with typed slots: `color`, `size`, `habitat`, `diet`, `abilities`, `body_parts`, `traits`, plus a `categories` set.
- **`AttributeBridge`** — Links two concepts via shared attribute values; bridge strength is computed with tier weighting (confirmed=1.0, potential=0.5, cross-tier=0.3).
- **`ConceptCluster`** — An emergent category, built from frame membership, with a *prototype* (the attributes commonly shared by its members).

**Behaviors:**

- *"cats are orange"* → `cats.color.confirmed += {orange}`
- *"cats can be orange"* → intercepted by `_handle_can_relation`, parsed as `be orange`, stored as `cats.color.potential += {orange}`
- A potential value gets **promoted** to confirmed if it's later asserted as a definite fact
- `propagate_category(subject, category)` — when *"X is Y"* is learned, similar concepts (frame similarity > 0.4) get queued for category propagation
- `update_clusters()` — runs in the background, builds emergent categories from frame membership (minimum 2 members)
- `hydrate_from_knowledge()` — on startup, rebuilds frames from existing triples

**Why this matters:** This is the prerequisite for the v0.8 *"Exceptions"* roadmap milestone. Defaults, exception precedence, and blocked-inference tracking all rely on being able to distinguish *typically true* from *necessarily true*.

### 6. Spreading Activation (`loom/activation.py`)

A faithful implementation of the Collins & Loftus (1975) spreading activation model.

When a concept is mentioned, it gets an **activation level**. Activation **spreads** to connected concepts, scaled by the connection's Hebbian weight and a `spread_factor`. Activation **decays** over time. When two source concepts both activate the same target, that target is **co-activated** — a signal that the two sources may share a hidden connection.

**Parameters** (in `activation.py`):
- `decay_rate = 0.12` — how fast activation fades
- `spread_factor = 0.5` — how much activation transfers to neighbors
- `priming_window = 30s` — how long a concept stays "primed" (recently mentioned)
- `topic_priming_window = 120s` — primed window for topic-relevant concepts

**Use cases:**
- Faster connection discovery (the `process_with_activation` path in `loom/processing.py`)
- Coreference: recently primed concepts are more likely candidates for *"it"* and *"they"*
- Suggesting bridges: co-activated concepts are flagged as potentially related

You can inspect the current state with the `activation` command.

### 7. Hebbian Learning (`loom/processing.py`)

*"Cells that fire together, wire together."*

Every connection in the graph has a **weight**. Weights start at `1.0` and:

- **Strengthen** when used: `strengthen_connection()` adds `0.2` (capped at `5.0`)
- **Decay** when idle: `decay_all_connections()` weakens unused connections after a configurable threshold
- **Get pruned** when their weight drops below `0.1`

Strong connections (weight > `2.0`) are visible via the `weights` command. They represent the parts of the graph the user has been most engaged with — Loom's working memory of *what's currently important*.

This is the entire learning mechanism for connection importance. Six lines of arithmetic, no gradients.

### 8. The Inference Engine (`loom/inference.py`)

The inference engine runs in two modes: **immediate** (when a fact is added) and **background** (every 3 seconds via a daemon thread).

**Immediate inference** (`process_immediate()`):
1. Track co-occurrence (for the discovery engine)
2. Activate both subject and object in the activation network
3. Spread activation to find related concepts
4. Detect co-activated nodes (potential new connections)
5. Strengthen the Hebbian weight of the connection
6. Copy properties for analogy when `looks_like` is involved
7. Inherit properties through category chains when an `is` relation is added
8. Run a quick syllogism check on transitive relations

**Background loop** (`_background_loop()`):
1. Process recent facts via `process_immediate()`
2. Decay the activation network
3. Run discovery patterns (`loom/discovery.py`)
4. Apply frame manager background cycles (recompute bridges, similarity, clusters, propagations)
5. Decay weak Hebbian connections
6. Re-fire active rules

**Inference types:**

- **Property inheritance** — *"dogs are mammals"* + *"mammals have fur"* → `(dogs, has, fur)` with `source_type=inheritance`, premises pointing to both parents
- **Transitive closure** — A→B and B→C, with both relations in the transitive set, yields A→C (lower confidence)
- **Analogy** — Concepts that share many attributes get linked via `looks_like`
- **Rule firing** — See the rule engine below

Every inferred fact carries its `premises` and a `derivation_id` so the inference can be traced backwards. This is what makes the `chain X R` command possible.

### 9. The Rule Engine (`loom/rules.py`, `loom/rule_engine.py`)

Loom supports **explicit forward-chaining rules**:

```
> if X is mammal and X has fur then X is warm_blooded
Got it, learned rule.
```

Rules are first-class objects with their own lifecycle:

- **CANDIDATE** — newly created (either user-stated or detected from a repeated pattern); needs more support before it fires
- **ACTIVE** — promoted; will fire on every matching pattern
- **SUSPENDED** — temporarily disabled (e.g., the user disagreed with one of its conclusions)
- **REJECTED** — permanently disabled

The engine matches rule premises against the knowledge base, binds variables, and fires the conclusion with `source_type=inference` and `premises` populated. Rules also track `support_count`, `confidence`, and `fire_count` for diagnostics.

### 10. The Curiosity Engine (`loom/curiosity.py`)

Loom doesn't just answer questions — it generates them. The curiosity engine maintains a **prioritized queue** of questions Loom would benefit from having answered, ranked by what would most improve the graph:

| Priority | Question type | Why |
|---|---|---|
| **10.0** | Contradictions | Two facts disagree; resolve them |
| **6.0** | Rule confirmation | A candidate rule wants more evidence to promote to ACTIVE |
| **5.0** | Chain gaps | A transitive closure is missing a link |
| **4.0** | Low-confidence facts | A weakly-held belief that could be confirmed or denied |
| **3.0** | Unknown properties | *"What does X have/eat/need?"* for under-explored concepts |
| **2.0** | Inverse relations | The inverse of an existing relation hasn't been explored |
| **1.0** | Comparison | *"How does X compare to Y?"* for similar-looking concepts |

`CuriosityNodeManager` also tracks **curiosity nodes** — placeholder concepts the user mentioned that Loom doesn't know enough about — and generates hypotheses by analogy with similar known concepts.

The web API exposes this via `GET /api/questions`, which calls `loom.run_curiosity_cycle()` and returns the top 5.

### 11. Provenance Tracking (`loom/provenance.py`)

Every fact carries a **provenance dict** with these fields:

```python
{
    "source_type": "inference",          # USER, INFERENCE, CLARIFICATION, INHERITANCE, SYSTEM, SPEECH
    "premises": [                         # The facts this one was derived from
        {"subject": "dogs", "relation": "is", "object": "mammals"},
        {"subject": "mammals", "relation": "has", "object": "fur"}
    ],
    "rule_id": "rule_123",                # If a rule fired
    "derivation_id": "abc1def2",          # Unique ID for this derivation chain
    "speaker_id": "alice",                # Who introduced the fact
    "created_at": "2026-04-08T..."
}
```

This is what enables **safe retraction**. When a user retracts a fact, Loom walks the dependency tree forward, finds every fact whose premises included the retracted one, and removes them too. Facts that were independently confirmed survive; facts that depended only on the retracted premise are cleaned up.

### 12. Conversation Context (`loom/context.py`)

Loom tracks conversation state with a **salience-weighted entity model**:

| Role | Salience contribution |
|---|---|
| Subject of a sentence | +3.0 |
| Object of a sentence | +2.0 |
| Mentioned anywhere | +1.0 |
| Per-turn decay | −0.3 |

The context tracks the topic stack, last subject and relation, recent statements, conversation mode (normal/teaching/questioning/correcting), and any pending clarification question.

**Coreference resolution** uses this salience score plus semantic fit (animacy, number) to decide what *"it"*, *"they"*, *"he"*, *"she"* refer to.

### 13. Entity Resolution (`loom/resolver.py`)

Before creating a new neuron for a phrase, the resolver tries to match it against existing concepts in this priority order:

1. **Exact match** — normalized phrase already exists
2. **Possessive** — *"dog's tail"* → look up `dog`, find its `has` relations
3. **Compound** — *"dog tail"* → same idea, with a different surface form
4. **Alias** — check `same_as` and `also_known_as` relations
5. **Contextual** — recent topic has a related property
6. **Partial match** — phrase is part of an existing neuron name
7. **New** — create a new neuron

This is what prevents Loom from accumulating duplicate concepts like *"dog"*, *"the dog"*, *"a dog"*, *"dogs"*, *"dog's"*.

### 14. Text Chunking and Discourse (`loom/chunker.py`, `loom/discourse.py`)

Multi-sentence input goes through the chunker, which:

1. Splits on sentence boundaries
2. Splits clauses on discourse connectors
3. Tags each chunk with a **relation type** based on its connector:
   - **Causal** — because, since, so, therefore, thus, consequently
   - **Contrast** — but, however, although, though, whereas, yet
   - **Elaboration** — also, furthermore, moreover, additionally
   - **Temporal** — then, after, before, when, while, first, finally
   - **Example** — for example, for instance, such as
   - **Condition** — if, unless, when, provided that
   - **Similarity** — similarly, likewise
   - **Conclusion** — in conclusion, in summary
4. Identifies **nucleus vs satellite** for each chunk (Rhetorical Structure Theory)

This lets Loom understand paragraphs as structured arguments rather than disconnected sentence soup.

### 15. Sentence Simplification (`loom/simplifier.py`, `loom/advanced_simplifier.py`)

Complex sentences get broken into atomic facts before parsing.

- **`SentenceSimplifier`** handles list constructions and parallel structures: *"dogs need food, water, and shelter"* → `["dogs need food", "dogs need water", "dogs need shelter"]`
- **`AdvancedSimplifier`** handles *"including"* patterns, parallel clauses joined by *"and"*, appositives (*"penguins, flightless birds, …"*), and relative clauses with *"which/who/that"*

### 16. Discovery Engine (`loom/discovery.py`)

A background pattern-mining system that looks for:

- **Co-occurrences** — entities that appear together repeatedly
- **Property groupings** — clusters of entities sharing the same property
- **Bridges** — categories that share instances (e.g., `pets` and `mammals` both contain `dogs`)
- **Facets** — automatic groupings by location (`ocean → aquatic_creatures`, `forest → terrestrial_creatures`, `sky → aerial_creatures`)
- **Suggested connections** — new edges Loom thinks should exist
- **Lonely neurons** — concepts with very few connections (candidates for curiosity questions)
- **Transitive gaps** — chains that are missing a link

The web API exposes all of this via `GET /api/graph` for visualization.

### 17. Speech Processing (`loom/speech.py`)

An optional subsystem with pluggable ASR backends: `whisper_local`, `whisper_api`, `google`, `azure`, `vosk`, `mock`.

The web app exposes two endpoints:

- `POST /api/speech` — receive already-transcribed text plus speech metadata (speaker, ASR confidence)
- `POST /api/speech/audio` — receive an audio file, transcribe it via the chosen backend, then process

ASR confidence influences fact confidence: high → `HIGH`, medium → `MEDIUM`, low → `LOW`. Spoken facts are tagged with `source_type=speech` and the speaker ID.

---

## CLI Commands

Run with `python main.py`. Commands work with or without a leading `/`.

**Knowledge input** (just type naturally, no command needed):
```
dogs are animals               # category
birds can fly                  # ability
rain causes floods             # causation
the sky is blue                # property
no, that's wrong               # correction
only when warm                 # constraint
first X, then Y, finally Z     # procedure
```

**Querying** (also just natural language):
```
what are dogs?                 # categories
can birds fly?                 # abilities
what causes floods?            # causes
where do fish live?            # locations
what does X cause?             # effects
```

**Inspection commands:**

| Command | What it does |
|---|---|
| `show` | Print the full knowledge graph |
| `compact` | Compact list view |
| `neuron X` | Detail view of one concept |
| `frame X` | Show concept's frame (typed attribute slots) |
| `bridges [X]` | Show attribute bridges (all, or only ones touching X) |
| `clusters` | Show emergent category clusters |
| `analogies X` | Find concepts similar to X |
| `inferences` | Show inferred facts |
| `conflicts` | Show detected contradictions |
| `procedures` | Show stored procedural sequences |
| `weights` | Show strong Hebbian connections |
| `activation` | Show current activation state |
| `context` | Show conversation state and salient entities |
| `entities` | Show salient entities only |
| `chain X R` | Trace the reasoning chain for relation R from X |
| `stats` | Storage statistics |

**Management commands:**

| Command | What it does |
|---|---|
| `train` | List available knowledge packs |
| `train [pack]` | Load a built-in pack (`animals`, `nature`, `science`, `geography`, etc.) |
| `load [file]` | Load a custom `.json` or `.txt` training file |
| `verbose` | Toggle debug output |
| `forget` | Erase all memory |
| `clear` | Clear the screen |
| `about` | Print Loom description |
| `help` | Print help |
| `quit` (or `exit`, `bye`, `q`) | Exit |

---

## Web Interface and HTTP API

```bash
pip install flask
python web_app.py
# open http://localhost:5000
```

The web app serves `web_chat.html`, which gives you the chat interface plus a live, animated knowledge graph visualization rendered on a HiDPI canvas.

**Features:**

- **Per-user tagging.** Set a username and every fact you add is tagged with `speaker_id=you`.
- **Per-user forget.** `/forget` removes only your facts when you have a username set; without a username, it wipes the whole graph.
- **Drag-drop training.** Drop one or more `.json` or `.txt` files onto the page; they're validated and loaded with full error reporting.
- **Pasted-JSON shortcut.** Pasting a JSON array directly into the chat box loads it as training data.
- **Auto-refreshing graph.** The visualization re-renders as new facts arrive.

**HTTP endpoints:**

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Serve the web chat page |
| `POST` | `/api/chat` | Process a message (natural language or `/command`) |
| `POST` | `/api/upload-training` | Upload one or more JSON/TXT training files |
| `POST` | `/api/speech` | Process pre-transcribed speech with metadata |
| `POST` | `/api/speech/audio` | Process an uploaded audio file |
| `GET` | `/api/questions` | Get top curiosity questions |
| `GET` | `/api/graph` | Get knowledge graph + discovery data for visualization |

**`POST /api/chat` example:**

```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "dogs are mammals", "user": "alice"}'
```

```json
{
  "response": "Got it, dogs are mammals.",
  "type": "response"
}
```

**`GET /api/graph`** returns nodes, edges, co-occurrences, suggested connections, clusters, transitive gaps, missing properties, lonely neurons, and overall graph statistics — everything the visualization needs in one payload.

---

## Training Packs and Custom Data

Loom ships with built-in knowledge packs. Load one with `train [pack]`:

| Pack | Topic |
|---|---|
| `animals` | Basic animal facts |
| `nature` | Weather, plants, water cycle |
| `science` | Physics, biology, space |
| `geography` | Continents, countries |
| `birds` (`training/birds.json`) | 100+ birds |
| `music_extended` (`training/music_extended.json`) | Music theory and instruments |
| `singing` (`training/singing.json`) | Vocal technique |
| `world_knowledge` (`training/world_knowledge.json`) | General world knowledge |

**Custom training files:**

**JSON format:**
```json
[
  {"subject": "dogs", "relation": "is",   "object": "mammals"},
  {"subject": "dogs", "relation": "has",  "object": "fur"},
  {"subject": "dogs", "relation": "can",  "object": "bark"},
  {"subject": "cats", "relation": "eats", "object": "fish"}
]
```

**Text format** (one fact per line, pipe or comma separated):
```
dogs | is   | mammals
dogs | has  | fur
cats | eats | fish
# lines starting with # are comments
```

Load with `load path/to/file.json`.

---

## Storage Backends

Loom has a **dual-backend persistence layer** that picks the best available option at startup.

### MongoDB (preferred if `pymongo` is installed)

`loom/storage/mongo.py` implements a quad+properties schema with these indexes:

- `(instance, subject, relation)` — fast forward lookup
- `(instance, relation, object)` — fast reverse lookup
- `(instance, subject, relation, object)` — unique index, prevents duplicates
- `(instance, object)` — for arbitrary reverse queries

**Document shape:**

```json
{
  "instance": "default",
  "subject": "dog",
  "relation": "has",
  "object": "fur",
  "context": "general",
  "properties": {
    "confidence": "high",
    "temporal": "always",
    "scope": "universal",
    "conditions": [],
    "source_type": "user",
    "speaker_id": "alice",
    "created_at": "2026-04-08T...",
    "premises": [],
    "rule_id": null,
    "derivation_id": "abc1def2"
  }
}
```

### JSON file (automatic fallback)

`loom/storage/json_fallback.py` writes to `loom_memory/loom_memory.json`. Same quad+properties schema, but loaded entirely into memory and persisted on every change. Ships with backward compatibility for the pre-v0.6 flat format.

**Storage selection** is automatic via `loom/storage/__init__.py`:`get_storage()`.

---

## Project Layout

```
loom/
├── main.py                          # CLI entry point (3-line shim)
├── web_app.py                       # Flask web server
├── web_chat.html                    # Web UI (canvas-rendered animated graph)
├── README.md                        # This file
├── CLAUDE.md                        # Architecture guidance
├── roadmap.md                       # v0.7 → v1.0 release plan
├── ideas.md, notes.txt              # Scratch
├── loom/                            # Main package
│   ├── __init__.py                  # Exports Loom, run_cli, ActivationNetwork, TextChunker
│   ├── brain.py                     # Loom class — knowledge graph + add_fact + storage interface
│   ├── frames.py                    # Two-tier confirmed/potential frame system (v0.6)
│   ├── structural.py                # Modifier extraction layer (v0.6)
│   ├── inference.py                 # Spreading activation, Hebbian, transitive, inheritance
│   ├── activation.py                # Collins & Loftus spreading activation network
│   ├── chunker.py                   # Sentence/clause splitting + RST discourse
│   ├── context.py                   # Conversation state, salience-based coreference
│   ├── context_detection.py         # Detect context/temporal/scope from text
│   ├── discovery.py                 # Background pattern learning, co-occurrence, facets
│   ├── discourse.py                 # Discourse relation analysis
│   ├── resolver.py                  # Entity resolution priority chain
│   ├── normalizer.py                # Text normalization, irregular plural protection
│   ├── grammar.py                   # Pluralization, conjugation, articles
│   ├── simplifier.py                # Basic sentence simplification
│   ├── advanced_simplifier.py       # Complex sentence decomposition
│   ├── svo.py                       # Morphology-based SVO extraction
│   ├── query_engine.py              # Generic SVO query engine
│   ├── curiosity.py                 # Prioritized question generation
│   ├── rules.py                     # Rule, RuleStatus, RuleMemory
│   ├── rule_engine.py               # Forward-chaining engine
│   ├── provenance.py                # Fact origin tracking with dependencies
│   ├── speech.py                    # Pluggable ASR backends
│   ├── processing.py                # HebbianMixin, ProcessingMixin
│   ├── training.py                  # TrainingMixin
│   ├── trainer.py                   # Training pack loader
│   ├── visualizer.py                # ASCII graph visualization
│   ├── cli.py                       # Interactive CLI loop
│   ├── parser/                      # Parser package
│   │   ├── base.py                  # Main Parser class, 40+ check cascade
│   │   ├── constants.py             # Shared word lists
│   │   ├── relations.py             # Verb → relation mapping
│   │   ├── queries_basic.py         # Simple queries
│   │   ├── queries_complex.py       # Complex queries
│   │   ├── queries_knowledge.py     # Domain queries
│   │   ├── patterns_basic.py        # Negation, looks_like, analogy
│   │   ├── patterns_relations.py    # is_statement, conditional, becomes
│   │   ├── patterns_discourse.py    # Discourse, chit-chat, first-person
│   │   ├── informational.py         # Encyclopedic sentences
│   │   └── handlers.py              # Correction, clarification, procedural
│   └── storage/                     # Persistence layer
│       ├── mongo.py                 # MongoDB backend
│       ├── json_fallback.py         # JSON file fallback
│       └── __init__.py              # get_storage() factory
├── training/                        # Built-in knowledge packs
│   ├── birds.json
│   ├── music_extended.json
│   ├── singing.json
│   └── world_knowledge.json
├── loom_memory/                     # Persistent storage (gitignored)
│   ├── loom_memory.json             # The knowledge graph
│   └── loom_rules.json              # Learned rules
├── docs/                            # Documentation
│   ├── COMPLEX_SENTENCE_PARSING.md
│   ├── RESEARCH_PLAN.md
│   ├── demo_animals_graph.py
│   └── demo_smart_loom.py
└── research/                        # Research notes
    └── conversational_learning_research.txt
```

---

## Roadmap

The full release plan is in `roadmap.md`. The short version:

| Version | Theme | Focus |
|---|---|---|
| **v0.7** | **Discipline** | Canonicalization, parser contract, inference guardrails, provenance hardening, safe retraction |
| **v0.8** | **Exceptions** | Default reasoning, exception precedence, contradiction classification, blocked-inference tracking |
| **v0.9** | **Context** | Temporal reasoning, context scoping, conditional knowledge |
| **v1.0** | **Coherence** | Unified fact model, multi-strategy inference, full explanation engine, knowledge maintenance |

**v0.7 — Discipline.** Make Loom *predictable, consistent, and debuggable*. Normalize all inputs, define a strict parser contract with ambiguity detection, add inference guardrails (max depth, cycle detection, duplicate prevention), harden provenance into a full dependency graph, and finalize the safe retraction engine.

**v0.8 — Exceptions.** Real-world reasoning needs *defaults* (birds usually fly) and *overrides* (penguins don't). Add a default-fact type, an exception precedence engine (specific > general; user > inferred), contradiction classification (true conflict vs valid exception vs temporal vs context mismatch), and blocked-inference tracking with explanations.

**v0.9 — Context.** Make truth situated. Add temporal reasoning (past/present/future facts, time-scoped truth), context scoping (location, scenario, conversation, hypothetical), and conditional knowledge (*if X then Y*, *only when X, Y*). Distinguish real conflicts from contextual differences.

**v1.0 — Coherence.** Unify everything. A single fact schema that supports direct/inferred/default/exception/temporal/conditional/scoped facts. A multi-strategy inference engine with clearly separated reasoning types. A full explanation engine that can answer *why true*, *why false*, *why blocked*, *why uncertain*. Symbolic debugging tools: `why X`, `why not X`, `depends X`, `conflicts X`, `blocked X`.

---

## Engineering Rules

These are the design rules Loom commits to. They are non-negotiable; they are what Loom *is*.

1. **No feature without explanation support.** Every new capability must extend the *why* story, not just produce more facts.
2. **No inference without traceability.** Every derived fact must carry its premises and a derivation_id.
3. **No correction without safe retraction.** Fixes must cascade through dependent inferences cleanly.
4. **No ambiguity without clarification.** When the parser can't decide, it asks. It does not guess.
5. **No graph mutation without validation.** Entity validation in `brain.py` (`_is_valid_entity`) is intentional, not paranoid.
6. **No ML libraries.** No torch, sklearn, transformers, spaCy, gensim. Hand-implement the math.

---

## What Loom is NOT

Loom is not, and is not trying to be:

- **Not a chatbot.** It will not generate fluent prose to sound clever. It will tell you what it knows, what it inferred, where it's unsure, and what it cannot answer.
- **Not an LLM replacement.** It cannot summarize a novel, write code, or hold an open-ended conversation about anything in the world. It learns from what you teach it.
- **Not a general-purpose AI.** It is a focused tool for building inspectable, correctable, conversational knowledge bases.
- **Not statistical.** There are no probabilities derived from data. The only "uncertainty" is the explicit `confidence` level on each fact, and the rules for combining them are hand-written.
- **Not a vector database.** No embeddings. No similarity search by cosine distance. Similarity is computed by counting shared symbolic attributes.
- **Not a black box.** Every line of reasoning, every weight, every inferred fact, every contradiction — all of it is inspectable through the CLI or the web API.

What Loom *is* trying to be: **the most precise, explainable symbolic reasoning engine you can build.**

---

## Documentation

Detailed module documentation lives in `docs/`. Each file covers one subsystem:

<!-- docs-index-start -->
| Document | Covers |
|---|---|
| **Core Engine** | |
| [Brain](docs/brain.md) | Knowledge graph, Loom class, add/get/remove facts, storage interface |
| [Activation](docs/activation.md) | Collins & Loftus spreading activation, priming, co-activation |
| [Inference](docs/inference.md) | Immediate & background inference, transitive closure, inheritance, analogy |
| **Knowledge Subsystems** | |
| [Frames](docs/frames.md) | Two-tier confirmed/potential frame system, structural extraction |
| [Rules](docs/rules.md) | Forward-chaining rule engine, rule lifecycle, variable binding |
| [Provenance](docs/provenance.md) | Fact origin tracking, premise dependencies, safe retraction |
| **Parser & NLP** | |
| [Parser](docs/parser.md) | Parser package — cascade of 40+ pattern checks, priority order |
| [SVO & Queries](docs/svo_and_queries.md) | Morphology-based verb detection, generic SVO query engine |
| [Simplifier](docs/simplifier.md) | Sentence decomposition — lists, appositives, relative clauses |
| **Text Processing** | |
| [Chunker](docs/chunker.md) | Sentence/clause splitting, RST discourse relations |
| [Resolver](docs/resolver.md) | Entity resolution, text normalization, grammar utilities |
| [Context](docs/context.md) | Conversation state, salience model, coreference resolution |
| **Subsystems** | |
| [Curiosity](docs/curiosity.md) | Prioritized question generation, knowledge gap detection |
| [Discovery](docs/discovery.md) | Background pattern mining, co-occurrence, facets, bridges |
| [Speech](docs/speech.md) | Pluggable ASR backends, audio-to-text, speaker tagging |
| [Processing](docs/processing.md) | Hebbian weight updates, processing & training mixins |
| **Interfaces** | |
| [CLI](docs/cli.md) | Interactive CLI loop, commands, ASCII graph visualization |
| [Storage](docs/storage.md) | Dual-backend persistence — MongoDB and JSON fallback |
| [Web](docs/web.md) | Flask API, web chat UI, canvas graph visualization |
<!-- docs-index-end -->

*Use `@loom document [module]` to generate docs for any module.*

---

## License

MIT

---

*"Weaving knowledge, one thread at a time."*
