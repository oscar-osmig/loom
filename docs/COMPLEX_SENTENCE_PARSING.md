# Complex Sentence Parsing for Knowledge Extraction

## Overview

Encyclopedia-style text uses complex sentence structures that pack multiple facts into single sentences. This document analyzes these structures and defines rules for extracting atomic facts.

## Common Complex Sentence Patterns

### 1. Participial Phrases

**Pattern:** `Subject VERB Object, PARTICIPLE additional_info`

**Examples:**
- "Giraffes have strong hearts, **necessary to pump blood** to their brains"
- "The giraffe is recognizable, **known for** its long neck"
- "They browse on trees, **giving them** access to food"

**Extraction Rules:**
```
Input:  "X is Y, known for Z"
Output: ["X is Y", "X is known for Z", "X has Z"]

Input:  "X has Y, necessary to Z"
Output: ["X has Y", "Y is necessary to Z", "Y helps X Z"]

Input:  "X does Y, giving them Z"
Output: ["X does Y", "X has Z", "Y gives Z"]
```

### 2. Fronted Modifiers

**Pattern:** `MODIFIER, Subject VERB Object`

**Examples:**
- "**Native to Africa**, giraffes use their necks to reach leaves"
- "**Despite their height**, they are graceful animals"
- "**As herbivores**, giraffes eat only plants"

**Extraction Rules:**
```
Input:  "Native to X, Y VERB Z"
Output: ["Y is native to X", "Y VERB Z"]

Input:  "Despite X, Y is Z"
Output: ["Y has X", "Y is Z"]

Input:  "As X, Y VERB Z"
Output: ["Y is X", "Y VERB Z"]
```

### 3. Appositive Clauses

**Pattern:** `Subject (—which/who VERB—) VERB Object`

**Examples:**
- "Their height**—which can exceed 18 feet—**makes them tall"
- "The heart**—which pumps blood—**is strong"
- "Giraffes**, which are herbivores,** eat leaves"

**Extraction Rules:**
```
Input:  "X—which VERB Y—VERB2 Z"
Output: ["X VERB Y", "X VERB2 Z"]

Input:  "X, which is Y, VERB Z"
Output: ["X is Y", "X VERB Z"]
```

### 4. List Structures

**Pattern:** `Subject VERB A, B, and C`

**Examples:**
- "Giraffes have **long necks, strong hearts, and spotted coats**"
- "They are **tall, graceful, and gentle**"
- "Giraffes eat **leaves, twigs, and bark**"

**Extraction Rules:**
```
Input:  "X has A, B, and C"
Output: ["X has A", "X has B", "X has C"]

Input:  "X is A, B, and C"
Output: ["X is A", "X is B", "X is C"]

Input:  "X VERB A, B, and C"
Output: ["X VERB A", "X VERB B", "X VERB C"]
```

### 5. Comparison Structures

**Pattern:** `X VERB Y, (much) like Z`

**Examples:**
- "Their patterns are unique, **much like human fingerprints**"
- "They move slowly, **like elephants**"
- "Giraffes sleep standing, **similar to horses**"

**Extraction Rules:**
```
Input:  "X is Y, like Z"
Output: ["X is Y", "X is like Z", "X looks like Z"]

Input:  "X VERB, similar to Y"
Output: ["X VERB", "X is similar to Y"]
```

### 6. Relative Clauses

**Pattern:** `Subject VERB Object that/which/who VERB2`

**Examples:**
- "Giraffes reach leaves **that other animals cannot reach**"
- "They have hearts **that pump blood efficiently**"
- "Scientists **who study giraffes** found patterns"

**Extraction Rules:**
```
Input:  "X VERB Y that VERB2 Z"
Output: ["X VERB Y", "Y VERB2 Z"]

Input:  "X that VERB Y is Z"
Output: ["X VERB Y", "X is Z"]
```

### 7. Compound Predicates

**Pattern:** `Subject VERB1 Object1 and VERB2 Object2`

**Examples:**
- "Giraffes **eat leaves** and **drink water**"
- "They **have long necks** and **use them** to reach food"
- "The heart **pumps blood** and **regulates pressure**"

**Extraction Rules:**
```
Input:  "X VERB1 Y and VERB2 Z"
Output: ["X VERB1 Y", "X VERB2 Z"]
```

### 8. Purpose Clauses

**Pattern:** `Subject VERB Object to/for PURPOSE`

**Examples:**
- "Giraffes have strong hearts **to pump blood to their brains**"
- "They use their necks **for reaching high leaves**"
- "Valves regulate flow **to prevent fainting**"

**Extraction Rules:**
```
Input:  "X has Y to VERB Z"
Output: ["X has Y", "Y helps VERB Z", "Y is for VERBing Z"]

Input:  "X VERB Y for Z"
Output: ["X VERB Y", "Y is for Z"]
```

### 9. Causative Structures

**Pattern:** `X VERB, which/causing/making Y`

**Examples:**
- "Iron oxide covers Mars, **which gives it** a red color"
- "They eat plants, **making them** herbivores"
- "The heart pumps hard, **causing** strong blood flow"

**Extraction Rules:**
```
Input:  "X VERB Y, which gives Z"
Output: ["X VERB Y", "Y gives Z", "X has Z"]

Input:  "X VERB, making X Z"
Output: ["X VERB", "X is Z"]
```

### 10. Existential Descriptions

**Pattern:** `X is [description with multiple properties]`

**Examples:**
- "The giraffe is **one of the most recognizable animals on Earth**"
- "Mars is **the fourth planet from the Sun**"
- "The Sun is **a massive star at the center of our solar system**"

**Extraction Rules:**
```
Input:  "X is one of the most Y Z"
Output: ["X is Z", "X is Y"]

Input:  "X is the Nth Y from Z"
Output: ["X is Y", "X is near Z", "X is Nth from Z"]

Input:  "X is a Y at/in/of Z"
Output: ["X is Y", "X is at/in/of Z"]
```

## Sentence Decomposition Algorithm

### Step 1: Sentence Segmentation
Split on sentence boundaries (., !, ?) while preserving abbreviations.

### Step 2: Clause Identification
1. Identify main clause (subject + main verb)
2. Identify subordinate clauses (that, which, who, where, when)
3. Identify participial phrases (VERBing, VERBed, known for, etc.)
4. Identify prepositional phrases (in, on, at, to, for, with)

### Step 3: Extract Core Facts
For each clause:
1. Identify subject (noun phrase before verb)
2. Identify verb (main action)
3. Identify object (noun phrase after verb)
4. Extract as triple: (subject, relation, object)

### Step 4: Resolve References
1. Replace pronouns (they, it, their) with antecedent
2. Resolve possessives (their necks → giraffes' necks → necks belong to giraffes)
3. Link related facts through shared entities

### Step 5: Normalize Relations
Map verbose phrases to standard relations:
- "is known for" → "has"
- "is native to" → "lives_in" or "native_to"
- "is necessary to" → "helps"
- "is used for" → "used_for"

## Implementation Priority

1. **High Priority** (most common in encyclopedias):
   - List structures
   - Compound predicates
   - Participial phrases
   - Relative clauses

2. **Medium Priority**:
   - Fronted modifiers
   - Purpose clauses
   - Appositive clauses

3. **Lower Priority**:
   - Comparison structures
   - Causative structures
   - Complex existential descriptions

## Example Full Decomposition

**Input:**
"Native to the savannas of Africa, giraffes use their long necks to reach leaves high up in acacia trees, giving them access to food sources that most other herbivores cannot reach."

**Step 1 - Identify Structures:**
- Fronted modifier: "Native to the savannas of Africa"
- Main clause: "giraffes use their long necks to reach leaves"
- Purpose: "to reach leaves high up in acacia trees"
- Participial: "giving them access to food sources"
- Relative: "that most other herbivores cannot reach"

**Step 2 - Extract Facts:**
1. "giraffes native_to savannas"
2. "giraffes native_to Africa"
3. "giraffes has long_necks"
4. "giraffes use long_necks"
5. "long_necks help reach_leaves"
6. "leaves located_in acacia_trees"
7. "acacia_trees has leaves"
8. "giraffes eats leaves"
9. "giraffes has access_to_food"
10. "other_herbivores cannot reach_leaves"

**Output:** 10 atomic facts from 1 complex sentence.
