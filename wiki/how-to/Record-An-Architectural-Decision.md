# How to record an architectural decision with /document-decision

> [!IMPORTANT]
> **Status: implemented** — `/document-decision` shipped in `src/developer-workflows/commands/document-decision.md`.

> [!NOTE]
> **Goal:** Decide when an architectural decision warrants an ADR, draft it before implementing (so the rationale is honest, not retrofitted), answer "why not the alternative" for each call, and link the ADR from the CHANGELOG.
> **Prereqs:** the `developer-workflows` plugin installed at a version that ships `/document-decision` ([Install crickets plugins](Install-Into-Project)).

`/document-decision` is an ADR trigger workflow: it enforces **when** to write (before implementing) and **how** to execute (mandatory "why not the alternative" per call; link from CHANGELOG). It references the ADR shape convention in your `CLAUDE.md` and does not redefine the format — the format is owned by the `adr-shape` convention.

## When to use this

Reach for `/document-decision` when any of the following are true:

- **Architectural decision** — the choice affects the structure, boundaries, or load-bearing assumptions of the codebase.
- **Public API change** — an interface external callers depend on is being added, changed, or removed.
- **Non-obvious behavior change** — the code does something that would surprise a future reader; the decision log is the explanation.
- **Proactive "why not"** — the obvious alternative will be suggested in review; write the ADR now so the discussion doesn't recur.

**Do not use** `/document-decision` for mechanical changes (renaming, formatting, routine dependency bumps), bug fixes with a single correct solution, or decisions that are self-evident from the diff.

## Steps

1. **State the decision in one sentence** before opening the ADR file:

   > "We are choosing X to accomplish Y."

   If you cannot state it in one sentence, the decision is not yet clear enough to implement or document.

2. **Invoke before writing any code:**

   ```text
   /document-decision <one-sentence description of the decision>
   ```

   The command walks you through drafting the ADR before any implementation starts ([`src/developer-workflows/commands/document-decision.md`](../src/developer-workflows/commands/document-decision.md)).

3. **Open the ADR file and fill Context.** Write what question this decision resolves and what was true that made it necessary. Include the open questions the decision closes.

4. **Fill Decision — with explicit "why not the alternative" per call.** For every load-bearing choice:
   - State what was decided and why.
   - Name the strongest alternative you considered and why you rejected it. *"We chose X over Y because Z; we did not choose Y because Q."*
   - If an alternative was not considered, note that too.

5. **Fill Consequences.** Three parts:
   - Positive bullets — what this enables.
   - Negative bullets — what this costs or forecloses.
   - Load-bearing assumptions with **re-audit triggers** — e.g. "re-audit if [assumption] changes." At least one trigger is required.

6. **Link the ADR from the CHANGELOG.** In the CHANGELOG entry for the release that ships this decision, add a link to the ADR. Without the link, the ADR will not be found by someone reading the changelog months later.

7. **Verify** all sections are complete before merging (see Verify below).

## Verify

- [ ] Decision stated in one sentence before starting.
- [ ] ADR drafted **before** any implementation code committed.
- [ ] All four sections complete: Context, Decision, Consequences, Related.
- [ ] "Why not the alternative" present for every load-bearing call in Decision.
- [ ] At least one re-audit trigger named in Consequences.
- [ ] CHANGELOG entry for this release links to the ADR.
- [ ] ADR `Status` field set: `accepted`, `superseded`, or `rejected`.
- [ ] No placeholder text remaining in any section.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "I can't state the decision in one sentence" | The decision is not yet settled | Stop; clarify the tradeoff before writing the ADR or any code |
| "I wrote the ADR after implementing — the 'why not' section feels forced" | Decision was made before the ADR was opened | Note the commit where the decision actually happened; for future decisions, draft the ADR first |
| CHANGELOG was written but doesn't link the ADR | Skipped step 6 | Add the ADR link to the CHANGELOG entry before the release ships |
| ADR Consequences has no re-audit triggers | Decision treated as permanent | Add at least one concrete condition that would make the decision wrong |

## See also

- [Developer Workflows plugin](Developer-Workflows) — the plugin that ships `/document-decision`.
- [Manifest schema](Manifest-Schema) — command primitive frontmatter reference.
- [Decisions](decisions/Decisions) — the ADR index for this project.
- [How to author a design with /design](Author-A-Design) — if the decision is part of a larger design, author the design first; ADRs record the non-obvious calls within it.
