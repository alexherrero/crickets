# `features.json` schema

Objective house facts, cited by `conventions` rules and by `/plan` when it decides whether a task warrants a feature entry — not gated itself.

## Shape

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "features": [
    {
      "description": "<one-sentence user-visible capability>",
      "steps": ["<how to exercise it manually>"],
      "passes": false
    }
  ]
}
```

Top-level: `{"features": [...]}`, an array of feature entries. JSON, not Markdown — a model is less likely to inappropriately edit JSON than Markdown.

## Per-feature fields

| Field | Type | Meaning |
|---|---|---|
| `description` | string | one-sentence, user-visible capability — not a task or an implementation detail |
| `steps` | array of strings | how to exercise the feature manually (a real user flow) |
| `passes` | bool | whether the feature is verified working; see the pass criteria below |

## Feature pass criteria

A feature may only be marked `passes: true` after:

1. All deterministic gates pass with the feature exercised.
2. Where relevant, an end-to-end test (a real user flow, not code inspection) confirms the feature works.
3. The adversarial reviewer either cleared it or its findings were addressed in a follow-up commit.

`passes: true` is set by `/review`, never by `/plan` — a feature is a changelog-worthy, user-visible capability (not 1:1 with a task); scaffolding and refactors don't produce a feature entry at all.
