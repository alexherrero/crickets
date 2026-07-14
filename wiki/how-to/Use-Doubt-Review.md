# How to run an in-flight decision review with /doubt

> [!NOTE]
> **Goal:** Catch a wrong decision before it stands — before you write the code, commit the architecture, or invoke an irreversible action.
> **Prereqs:** the `code-review` plugin installed ([Install crickets plugins](Install-Into-Project)). Optional: `agy` CLI authed (for cross-model escalation).

`/doubt` is distinct from `/code-review`. `/code-review` reviews a diff **after** code is written. `/doubt` fires **in flight**, while course-correction is still cheap.

## When to reach for it

Use `/doubt` when one or more of the following apply:

- Correctness matters more than speed — a wrong call is expensive to undo
- You're working in unfamiliar code and your confidence is borrowed
- The path is production-critical, security-sensitive, or irreversible
- You can clearly name the decision you're about to make (if you can't, clarify first)

**Do not use `/doubt` for** mechanical operations (copy, reformat, scaffold), one-line renames with obvious scope, or instructions with exactly one correct interpretation.

## Steps

1. **Invoke the command** at the moment you're about to commit to a decision:

   ```text
   /doubt
   ```

   No arguments. `/doubt` is a structured loop, not a diff target.

2. **CLAIM (private).** The command prompts you to name the decision and why it matters — two to three lines. This stays local; it is never sent to any reviewer.

   > Example: "Using `os.open` with `O_BINARY` on Windows so the staged→active copy is byte-verbatim. Matters because byte divergence would cause integrity failures on Windows CI."

3. **EXTRACT.** Isolate two things, stripping your reasoning from both:

   - **ARTIFACT** — the exact code, config block, schema, or action you're about to take.
   - **CONTRACT** — what it must do: the spec, invariant, or verification clause.

   The loop writes these to `/tmp/doubt-material.txt`. Your CLAIM never reaches that file.

4. **DOUBT (reviewer dispatch).** The command invokes the cross-model reviewer:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/cross-review.sh" < /tmp/doubt-material.txt
   ```

   The adversarial prompt is locked: *"find issues, assume overconfidence, do NOT validate."*

   - **Exit 0** — cross-model reviewer returned findings.
   - **Exit 1/2** — agy unavailable; falls back to the in-process `adversarial-reviewer` agent with the same material and the same prompt.

   In an **interactive session**, after the single-model pass completes, the command always offers: *"Single-model review complete — want a cross-model second opinion?"* The user decides.

   In a **non-interactive context** (CI, `/loop`, autonomous-loop), the command announces: *"Non-interactive session: skipping cross-model escalation offer."* It does not invoke any external CLI without explicit per-invocation authorization.

5. **RECONCILE.** For every finding, classify it against the artifact text (not your reasoning):

   | Class | Meaning |
   |---|---|
   | `contract-misread` | Reviewer misread the contract — artifact satisfies it when read correctly |
   | `valid+actionable` | Finding is correct, artifact must change |
   | `valid-tradeoff` | Finding is correct, tradeoff accepted — log the acceptance explicitly |
   | `noise` | Finding is not grounded in the artifact or contract text |

   Every classification must cite the artifact line or contract clause it's based on.

6. **STOP.** The loop ends when:

   - All findings in the current cycle are `contract-misread`, `valid-tradeoff`, or `noise`
   - 3 cycles are complete (hard cap — the command escalates rather than looping again)
   - You say "ship it"

   If the 3-cycle cap is hit with unresolved `valid+actionable` findings, the command escalates: *"3-cycle cap reached with unresolved findings — operator decision needed."*

## Verify

After each cycle confirm:

```
[ ] CLAIM was not passed to the reviewer
[ ] /tmp/doubt-material.txt contains only ARTIFACT + CONTRACT (no CLAIM, no reasoning)
[ ] Every finding is classified with an artifact/contract citation
[ ] Stop condition was evaluated after RECONCILE
[ ] Cross-model offer was made (interactive) or skip was announced (non-interactive)
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Command exits immediately | Can't name the decision (CLAIM fails) | Finish clarifying the decision first, then re-invoke |
| "Doubt theater detected" escalation | 2+ cycles, findings returned, zero classified `valid+actionable` | You're validating, not doubting. Stop and make an operator call |
| Cross-model pass silently skipped | `agy` absent or unauthed | Expected — falls back to in-process reviewer. Auth `agy` to enable cross-model pass |
| Reviewer disagrees but you think you're right | Disagreement is information, not verdict | Classify the finding with a citation; if `contract-misread`, proceed |

## See also

- [Review a change after it's written](Use-Code-Review) — `/code-review` for post-hoc diff review
- [Install crickets plugins](Install-Into-Project) — get the `code-review` plugin installed
- [Why adversarial review](Why-Adversarial-Review) — the reasoning behind the adversarial stance
- [Manifest schema](Manifest-Schema) — command primitive frontmatter reference
