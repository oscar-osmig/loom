# Style Learner (`loom/style_learner.py`)

Extracts writing patterns from user input and tracks feedback on Loom's
responses. Enables Loom to develop its own writing style over time.

## What it learns

1. **Openers** — how sentences start (`"unlike X"`, `"most X"`, `"all X"`)
2. **Connectives** — how clauses join (`", but"`, `", which"`, `"; "`)
3. **Sentence templates** — abstracted structure with placeholders
   - "Unlike birds, mammals nurse their young" → `"unlike [1], [2] [3] [4] [5]"`
4. **Composer template effectiveness** — like/dislike counters per template label

## Public API

### `StyleLearner(loom)`

Attached to Loom instance as `loom.style_learner`.

### `observe(text)`

Called on every user statement (not questions) via the parser's entry point.
Extracts patterns and increments their counts in MongoDB.

### `record(input_text, response_text, rating)`

Called when user clicks 👍 or 👎 on a response. Updates like/dislike counters
for patterns and composer templates detected in the response.

### `get_template_score(label)`

Returns a score in `[-1, +1]` for a composer template label. Used by
`composer._pick_template()` to boost/demote templates based on feedback.

### `get_top_patterns(kind, limit=5)`

Returns top patterns of a kind (opener, connective, template, composer_template)
ordered by `count + (likes * 2) - dislikes`.

### `get_stats()`

Summary:
```python
{
    "total_patterns": 42,
    "templates_learned": 15,
    "openers_learned": 8,
    "feedback_received": 23,
}
```

## MongoDB schema

Collection: `style_patterns`

```
{
    instance: "loom",
    kind: "opener" | "connective" | "template" | "composer_template",
    value: <pattern or label>,
    count: <times seen>,
    likes: <thumbs up count>,
    dislikes: <thumbs down count>,
    first_seen: ISO datetime,
    last_seen: ISO datetime,
}
```

Collection: `feedback`

```
{
    instance: "loom",
    message_id: <int>,
    rating: "like" | "dislike",
    user: <nickname>,
    input_text: <first 500 chars>,
    response_text: <first 1000 chars>,
    created_at: ISO datetime,
}
```

## How feedback influences composition

1. User sees: "Elephant is classified as mammal."
2. User clicks 👍
3. `/api/feedback` stores the feedback
4. `StyleLearner.record()` detects `"is classified as"` in response
5. Increments `composer_template.is_classified_as.likes`
6. Next time composer runs for a similar concept, `_pick_template()` sees
   the positive score and prefers "is classified as" over "is a kind of"

## Limitations

- Template extraction is regex-based; it doesn't understand deep structure
- Feedback doesn't yet influence template selection for short-form
  acknowledgments — only long descriptive responses
- No context-aware style (e.g., "use formal style for admins")
