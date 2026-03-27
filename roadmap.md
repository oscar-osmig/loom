Here’s a **structured release-plan document** for Loom — written like something you could drop into your repo as `ROADMAP.md`.

---

# Loom Roadmap & Release Plan

**Project:** Loom
**Vision:** A transparent, symbolic cognition system that learns through dialogue, reasons through explicit structure, and explains every conclusion.

---

# 🧭 Development Philosophy

Loom evolves by strengthening:

1. **Representation** — how knowledge is stored
2. **Inference** — how knowledge is derived
3. **Control** — when reasoning should or should not happen
4. **Explainability** — why conclusions are made
5. **Correction** — how mistakes are fixed
6. **Consistency** — how the graph stays valid over time

---

# 🧱 Version Strategy

| Version | Theme      | Focus                                       |
| ------- | ---------- | ------------------------------------------- |
| v0.7    | Discipline | Stability, normalization, inference control |
| v0.8    | Exceptions | Default reasoning + overrides               |
| v0.9    | Context    | Time, scope, conditional truth              |
| v1.0    | Coherence  | Unified symbolic intelligence engine        |

---

# 🚀 v0.7 — Discipline

## Goal

Make Loom **predictable, consistent, and debuggable**.

## Core Upgrades

### 1. Canonicalization System

Normalize all knowledge inputs.

**Features**

* singular/plural normalization
* concept deduplication
* relation normalization (`is`, `is_a`, `type_of` → canonical)
* synonym policy (strict or mapped)

**Deliverables**

* `normalizer.py` upgrade
* canonical concept registry
* duplicate resolution logic

---

### 2. Parser Contract

Define strict boundaries for supported language.

**Features**

* supported pattern registry
* ambiguity detection
* rejection + clarification prompts
* deterministic parsing

**Deliverables**

* parser spec doc
* pattern classification system
* error/clarification responses

---

### 3. Inference Guardrails

Control how reasoning expands.

**Features**

* max inference depth
* cycle detection
* duplicate inference prevention
* confidence propagation rules
* inference reason codes

**Deliverables**

* inference limiter module
* reasoning trace logs
* inference audit tool

---

### 4. Provenance Hardening

Make every fact fully traceable.

**Features**

* parent dependencies
* inference type tagging
* chain-of-reason tracking

**Deliverables**

* provenance graph structure
* dependency tree viewer
* trace API

---

### 5. Safe Retraction Engine

Ensure clean correction behavior.

**Features**

* dependency-based retraction
* cascading inference removal
* selective rebuild of valid facts

**Deliverables**

* retraction engine
* dependency cleanup system
* graph rebuild logic

---

## v0.7 Checklist

* [ ] Canonicalization layer implemented
* [ ] Parser support matrix defined
* [ ] Inference guardrails active
* [ ] Provenance chain complete
* [ ] Retraction system stable
* [ ] No duplicate facts in graph
* [ ] All inference paths traceable

---

# 🧠 v0.8 — Exceptions

## Goal

Enable **real-world reasoning with defaults and exceptions**.

---

### 1. Default Knowledge Model

**Examples**

* birds usually fly
* mammals usually have fur

**Features**

* non-absolute truth representation
* default confidence model

---

### 2. Exception Precedence Engine

**Rules**

* specific > general
* user fact > inferred fact
* exception blocks inheritance

---

### 3. Contradiction Classification

Distinguish:

* true contradiction
* valid exception
* temporal conflict
* context mismatch

---

### 4. Blocked Inference Tracking

Track when inference is prevented.

**Example**

* birds → can fly
* penguins → cannot fly
  → inheritance blocked

---

### 5. Exception-Aware Explanations

System must explain:

* general rule
* exception
* final conclusion

---

## v0.8 Checklist

* [ ] Default fact type implemented
* [ ] Exception precedence rules working
* [ ] Blocked inference recorded
* [ ] Contradictions classified correctly
* [ ] Explanations reflect exceptions
* [ ] Inheritance respects overrides

---

# 🌍 v0.9 — Context

## Goal

Introduce **situated knowledge (time, scope, conditions)**.

---

### 1. Temporal Reasoning

**Support**

* past / present / future facts
* time-scoped truth

---

### 2. Context Scoping

**Scopes**

* location
* scenario
* conversation
* hypothetical

---

### 3. Conditional Knowledge

**Examples**

* if X then Y
* only when X, Y

---

### 4. Context-Aware Contradictions

Distinguish:

* real conflict vs contextual difference

---

### 5. Temporal Provenance

Track:

* when fact applies
* when learned
* if outdated

---

## v0.9 Checklist

* [ ] Temporal fact model implemented
* [ ] Context scopes functional
* [ ] Conditional reasoning active
* [ ] Context-aware queries working
* [ ] Temporal conflicts resolved correctly

---

# 🧠 v1.0 — Coherence

## Goal

Unify Loom into a **complete symbolic cognition engine**.

---

### 1. Unified Fact Model

Single model supports:

* direct facts
* inferred facts
* defaults
* exceptions
* temporal facts
* conditional facts
* scoped facts

---

### 2. Multi-Strategy Inference Engine

Clearly separated reasoning types:

* transitive
* inheritance
* default reasoning
* exception override
* conditional rules

---

### 3. Full Explanation Engine

Answer:

* why true
* why false
* why blocked
* why uncertain

---

### 4. Knowledge Maintenance System

**Features**

* duplicate resolution
* orphan cleanup
* concept merging
* graph validation

---

### 5. Curiosity Engine v2

Driven by:

* contradictions
* missing properties
* weak facts
* incomplete chains

---

### 6. Symbolic Debugging Tools

Commands:

* `why X`
* `why not X`
* `depends X`
* `conflicts X`
* `blocked X`

---

## v1.0 Checklist

* [ ] Unified fact schema complete
* [ ] All inference types integrated
* [ ] Explanation engine stable
* [ ] Graph maintenance system active
* [ ] Curiosity engine v2 working
* [ ] Debugging tools implemented
* [ ] System passes full reasoning test suite

---

# 🧪 Testing Strategy (All Versions)

## Required Test Types

* Parser correctness
* Inference correctness
* Exception handling
* Retraction behavior
* Contradiction classification
* Temporal reasoning
* Provenance accuracy

---

# 🧩 Engineering Rules

* No feature without explanation support
* No inference without traceability
* No correction without safe retraction
* No ambiguity without clarification
* No graph mutation without validation

---

# ⚡ Milestone Summary

### Milestone A — Core Integrity (v0.7)

* normalization
* inference control
* retraction

### Milestone B — Exception Intelligence (v0.8)

* defaults
* overrides
* contradiction classification

### Milestone C — Situated Knowledge (v0.9)

* time
* context
* conditions

### Milestone D — Symbolic Maturity (v1.0)

* unified model
* explanation engine
* full reasoning system

---

# 🧠 Final Direction

Loom should not try to:

* mimic chatbots
* replace LLMs
* be “general AI”

Instead, Loom should become:

👉 **The most precise, explainable symbolic reasoning engine you can build**

---
