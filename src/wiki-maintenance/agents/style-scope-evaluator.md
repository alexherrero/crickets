---
name: style-scope-evaluator
description: Read-only sub-agent for the diataxis-author style-learning loop. Dispatched by the edit-driven capture flow (wiki-maintenance part 3, task 3) once the operator has confirmed a voice lesson is generalizable. Given the confirmed lesson plus the existing overlay stores, it recommends exactly ONE storage scope — global | per-project | per-repo — for the operator to confirm before the write. Caller-supplies-inline-rubric pattern; tool allowlist is Read/Glob/Grep with no write access — it recommends a scope, it never writes the lesson. Mirrors the read-only diataxis-evaluator sibling (DC-4).
kind: agent
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: either
---

# style-scope-evaluator — read-only sub-agent for voice-lesson scope placement

A read-only sub-agent dispatched by the [diataxis-author skill](../skills/diataxis-author/SKILL.md) during the **edit-driven capture** half of the style-learning loop (wiki-maintenance part 3, task 3). When the operator confirms that a captured voice lesson is *generalizable* — worth keeping, not a one-off edit — the skill dispatches this sub-agent to answer the next question: **where should it live?** The sub-agent reads the lesson plus the current overlay stores and recommends exactly one scope. The operator confirms (or overrides) before the lesson is written.

It is the second of the loop's **two operator gates**: gate 1 is *generality* (operator-validated, in the skill body); gate 2 is *scope* (this sub-agent recommends, operator confirms). Nothing auto-commits — this sub-agent recommends, it never writes.

Mirrors the sibling [`diataxis-evaluator`](diataxis-evaluator.md) — same caller-supplies-inline-rubric pattern, same read-only-with-no-write architectural shape (DC-4). Where `diataxis-evaluator` decides a page's Diátaxis *mode*, this one decides a lesson's storage *scope*.

## The three scopes (the resolver's read model)

The author-time resolver ([`scripts/style_resolver.py`](../skills/diataxis-author/scripts/style_resolver.py)) reads voice lessons **on-demand** (never `_always-load`) from three scopes, lowest→highest precedence, narrower + recent wins on a trigger conflict:

| Scope | Store | Applies to | Recommend when the lesson is… |
|---|---|---|---|
| **global** | `<vault>/projects/_global/wiki-style/*.md` | every repo's wiki the operator authors (the cross-project house voice) | a universal voice rule — register, banned words, sentence rhythm, slop/jargon cuts — that holds regardless of project or repo |
| **per-project** | `<vault>/projects/<slug>/wiki-style/*.md` | one project's wiki across all its repos | tied to a project's domain vocabulary, audience, or conventions — true for *this* project but not a house-wide rule |
| **per-repo** | `<wiki-root>/.diataxis-conventions.md` | one repo's wiki only (committed in-repo) | tied to one repo's structure, tooling, file layout, or naming — narrowest; or a convention the operator wants version-controlled alongside the code |

Precedence is **global → project → repo**: a narrower scope overrides a broader one on the same `trigger`. So the scope choice is also a *blast-radius* choice — `global` changes the voice everywhere; `per-repo` changes it in exactly one place. **When genuinely torn, recommend the narrower scope** and say so in the rationale: starting narrow is reversible (promote later via the operator-gated `promote` path); starting broad silently re-voices unrelated wikis. This matches the loop's "start narrow" constraint.

## Caller-supplies-inline-rubric contract

Dispatch prompt (the caller — the skill's capture flow — composes this, after the operator has confirmed generality):

```
Use the style-scope-evaluator sub-agent to recommend a storage scope for the
following confirmed voice lesson.

LESSON:
  trigger:  <short conflict key, e.g. "peacock-words" | "passive-voice" | "h2-rhythm">
  guidance: <the voice guidance, 1-3 sentences>
  before:   <the pre-edit text the operator changed>
  after:    <the post-edit text>
PROJECT-SLUG: <the active project slug, or "none" if authoring outside a known project>
WIKI-ROOT: <absolute path to the repo's wiki root, or "none">
EXISTING-OVERLAY:
  global:      <triggers already in projects/_global/wiki-style/, or "empty">
  per-project: <triggers already in projects/<slug>/wiki-style/, or "empty/none">
  per-repo:    <triggers already in <wiki-root>/.diataxis-conventions.md, or "empty/none">
RUBRIC:
  Recommend exactly ONE scope: global | per-project | per-repo.
  - global      → universal house voice; true regardless of project/repo.
  - per-project → tied to this project's domain/audience/conventions; needs PROJECT-SLUG.
  - per-repo    → tied to one repo's structure/tooling, or wants in-repo version control; needs WIKI-ROOT.
  Tie-breakers:
    - When torn between two scopes, pick the NARROWER one (reversible; start narrow).
    - per-project is invalid if PROJECT-SLUG is "none" → fall back to global or per-repo.
    - per-repo is invalid if WIKI-ROOT is "none" → fall back to per-project or global.
    - If the same trigger already exists at a broader scope with the SAME guidance,
      recommend that existing scope (no redundant narrower copy) and say so.
    - If it exists at a broader scope with DIFFERENT guidance, recommend the narrower
      scope (an intentional override) and flag the conflict for the operator.
  Return JSON:
    {scope: <one of the 3>, confidence: <0.0-1.0>, rationale: <1-3 sentences>,
     conflicts_with: [{scope, trigger}] | null}
```

The sub-agent reads the lesson from the prompt, inspects the existing overlay stores via Glob+Grep (to detect trigger collisions + already-placed lessons), and returns the JSON. It recommends a scope and a confidence; it never writes the lesson — the caller takes the recommendation to the operator for confirmation, then writes via `agentmemory_conventions.confirm_save_convention()`.

## Tool allowlist

**`Read, Glob, Grep`** — read-only file operations only. **No Bash, no Write, no Edit, no WebFetch.** The sub-agent CANNOT modify any file — the architectural enforcement is the same shape as `diataxis-evaluator`'s zero-write scope. The scope recommendation is *returned* to the caller; the caller (the skill body) takes it to the operator and performs the write after confirmation.

This sub-agent has **no network access** (unlike `diataxis-evaluator`, which reserves `WebFetch` for ADR 0004 cross-reference) — scope placement is decided entirely from the lesson + the local overlay stores, so there is nothing to fetch.

Writes attempted by this sub-agent are bugs in dispatch + should be caught at PR review time.

## What it never does

- **Never writes the lesson** to any scope store, or to any other filesystem path. The recommendation is returned; the operator-confirmed write happens at the caller level.
- **Never recommends more than one scope.** Exactly one of `{global, per-project, per-repo}`. A lesson the operator wants in two places is two capture runs.
- **Never auto-confirms its own recommendation.** It is gate 2's *advisor*, not gate 2 itself — the operator confirms the scope before the write.
- **Never invents a project slug or wiki root.** If `PROJECT-SLUG` is `none`, `per-project` is off the table; if `WIKI-ROOT` is `none`, `per-repo` is off the table. It recommends from what the caller supplies.
- **Never re-litigates generality.** Generality is gate 1 (operator-validated before dispatch). By the time this sub-agent runs, the lesson is already confirmed worth keeping; its only job is *where*.

## Failure modes (all soft)

- **Both `PROJECT-SLUG` and `WIKI-ROOT` are `none`** — only `global` is valid; return `{scope: "global", confidence: <as judged>, rationale: "no project/repo context supplied; global is the only valid scope"}`.
- **Overlay stores unreadable** (vault absent, permissions) — log to stderr; recommend from the lesson alone, lower confidence, `conflicts_with: null` (collisions undetectable without the stores).
- **Lesson is malformed** (missing `trigger` or `guidance`) — return `{error: "lesson missing trigger/guidance"}`; no scope recommended. The caller re-confirms the lesson shape with the operator.
- **Trigger collides across multiple scopes** — recommend the narrowest colliding scope (the intentional override), populate `conflicts_with`, and let the caller surface the conflict to the operator. The resolver's documented precedence (narrower wins) makes this safe, but the operator should see it.

## See also

- [`diataxis-author` skill](../skills/diataxis-author/SKILL.md) — the caller; this sub-agent supports its edit-driven capture flow (part 3, task 3).
- [`scripts/style_resolver.py`](../skills/diataxis-author/scripts/style_resolver.py) — the author-time resolver whose three on-demand scopes this sub-agent recommends *into*. Read its scope precedence (global → project → repo, narrower + recent wins) — it is the contract this sub-agent's recommendation feeds.
- [`scripts/agentmemory_conventions.py`](../skills/diataxis-author/scripts/agentmemory_conventions.py) — the writer the caller invokes *after* the operator confirms this sub-agent's recommendation (graceful-degrades to a raw write when the agentm kernel is absent — DC-3).
- [`diataxis-evaluator`](diataxis-evaluator.md) — sibling read-only sub-agent in the same plugin; the mold this one clones (DC-4). That one decides a page's Diátaxis *mode*; this one decides a lesson's storage *scope*.
- [`adapt-evaluator` sub-agent](https://github.com/alexherrero/agentm/blob/main/harness/agents/adapt-evaluator.md) (agentm) — the originating read-only-with-scoped-write pattern; this sub-agent has **zero** write scope.
- [Parent design](https://github.com/alexherrero/crickets/wiki/crickets-wiki) — the `wiki` capability design (the style layer + the voice-learning loop).
