<!-- mode: how-to -->
# How to record a design decision

> [!NOTE]
> **Goal:** Record a load-bearing design call in the amendment log of the relevant living design so the "why X, not Y" rationale is discoverable in one place.
> **Prereqs:** A living design already exists under [`wiki/designs/`](Designs) that governs the area you're changing. If the area has no design yet, [author one first](Author-A-Design).

> [!IMPORTANT]
> **The ADR model is retired in crickets** (AG Phase 4, 2026-06-24). Load-bearing calls go into the **amendment log** of the relevant living design under [`wiki/designs/`](Designs), not standalone ADR files. See [Design Docs](Design-Docs) for the `design-docs` plugin that ships the format tooling.

## When to record a decision

Record a decision whenever any of these are true:

- **Structural choice** — the call affects boundaries, load-bearing assumptions, or the composition model.
- **Non-obvious behavior** — the code does something that would surprise a future reader; the decision log is the explanation.
- **Why-not-the-alternative** — the obvious alternative will be suggested in review; write the rationale now so the discussion doesn't recur.

Do NOT record mechanical changes (renaming, formatting, dependency bumps) or decisions self-evident from the diff.

## Steps

1. **Locate the governing design** under `wiki/designs/` (e.g. `crickets-development-lifecycle.md`, `crickets-developer-safety.md`).
2. **Amend the body** if the decision changes the design's stated behavior — reconcile the body text to current truth.
3. **Add an amendment-log entry** at the bottom of the design under `## Amendment log`:

   ```markdown
   **YYYY-MM-DD — [summary of the change].**
   <decision prose>. Why not the alternative: <why-not>. *Re-audit triggers:* <triggers>.
   ```

4. **Land body + amendment-log entry as one atomic commit.**
5. **Link from the CHANGELOG** entry for the release that ships this decision.

## Verify

- [ ] Governing design identified and body reconciled to current truth.
- [ ] Amendment-log entry states the decision, "why not the alternative", and at least one re-audit trigger.
- [ ] Body + amendment-log entry in one atomic commit.
- [ ] CHANGELOG entry links to the relevant design.

## See also

- [Author a design](Author-A-Design) — use this when the decision is part of a larger design that doesn't exist yet.
- [Designs](Designs) — the living design index.
- [Design Docs](Design-Docs) — the `design-docs` plugin and its decision-format tooling.

[How-To](How-To) · [Home](Home)
