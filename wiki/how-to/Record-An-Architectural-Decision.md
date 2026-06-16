# How to record an architectural decision with /document-decision

> [!IMPORTANT]
> **Status: pending** (developer-workflows Ship phase). This is a forward-declared skeleton — `/document-decision` does not yet exist. Step bodies are reserved, not written; a later `/work` task fills them from the shipped diff. Do not follow these steps yet.

> [!NOTE]
> **Goal:** Decide when an architectural decision warrants an ADR, draft it before implementing (so the rationale is honest, not retrofitted), answer "why not the alternative" for each call, and link the ADR from the CHANGELOG.
> **Prereqs:** the `developer-workflows` plugin installed at a version that ships `/document-decision` ([Install crickets plugins](Install-Into-Project)); a decision worth recording — see "When to use this" below. _Exact prereqs filled by `/work` once the task ships._

`/document-decision` is an ADR trigger workflow: it enforces **when** to write (before implementing) and **how** to execute (mandatory "why not the alternative" per call; link from CHANGELOG). It references the ADR shape convention in the project's `CLAUDE.md` and does not redefine the format — the format is fixed.

## When to use this

Reach for `/document-decision` when any of the following are true:

- **Architectural decision** — the choice affects the structure, boundaries, or load-bearing assumptions of the codebase.
- **Public API change** — an interface external callers depend on is being added, changed, or removed.
- **Non-obvious behavior change** — the code does something that would surprise a future reader or a code-reviewer; the decision log is the explanation.

**Do not use** `/document-decision` for mechanical changes (renaming, formatting, routine dependency bumps), bug fixes with a single correct solution, or decisions that are self-evident from the diff.

## Steps

1. Invoke the command **before implementing** the decision:

   ```text
   /document-decision
   ```

   _Filled by `/work` once the task ships._

2. Name the decision and the context that makes it non-obvious.

   _Filled by `/work` once the task ships._

3. Write the Decision section: what was decided and, for each considered alternative, why it was rejected ("why not the alternative").

   _Filled by `/work` once the task ships._

4. Write the Consequences section: positive bullets, negative bullets, and load-bearing assumptions with re-audit triggers.

   _Filled by `/work` once the task ships._

5. Link the new ADR from the CHANGELOG entry for the release that ships the decision.

   _Filled by `/work` once the task ships._

## Verify

_Filled by `/work` once the task ships._

## Troubleshooting

_Filled by `/work` once the task ships._

## See also

- [Developer Workflows plugin](Developer-Workflows) — the plugin that ships `/document-decision`.
- [Decisions](../../decisions/Decisions) — the ADR index for this project.
- [How to author a design with /design](Author-A-Design) — if the decision is part of a larger design, author the design first; ADRs record the non-obvious calls within it.
