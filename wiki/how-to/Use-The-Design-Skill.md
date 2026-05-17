# How to use the design skill

> [!NOTE]
> **Goal:** Walk a human through a 10-section design doc, split the approved design into structural parts, generate one PLAN.md per part for the harness `/work` + `/release` flow to execute, and surface published designs as the canonical "Why we built X" entry point in `wiki/`.
> **Prereqs:** `agent-toolkit` installed into the target project (the `/design` skill ships there); `agentic-harness` v2.3.0+ installed alongside (the `/release` flow's §1b hook handles plan promotion + the `final → launched` Status transition); a git repo (per-part PLAN.md files live in `.harness/`, which is gitignored).

The `/design` skill runs the **front** of a project: the human-facing design phase that produces a structured doc, splits it into structural parts, and hands off to the harness's existing `/work` + `/review` flow as one `PLAN.md` per part. The original human-authored design doc is positioned as the canonical "Why we built X" entry point in `wiki/`.

This how-to walks through when to reach for `/design`, the three sub-commands at-a-glance, three worked scenarios, troubleshooting, and the manual equivalents for non-Claude-Code hosts.

## ⚡ At-a-glance

| Sub-command | Input | Output | Status gate |
|---|---|---|---|
| `/design author <slug> [--visibility]` | `<slug>` + Visibility (default `confidential`) | Design doc at `wiki/explanation/designs/<slug>.md` (published) or `.harness/designs/<slug>.md` (confidential); transitions `draft → review → final` | Only sub-command that transitions Status |
| `/design translate <slug>` | A `Status: final` design doc | N structural-part files at `<doc-dir>/parts/<part-slug>.md` | Requires `Status: final` (hard gate) |
| `/design sequence <slug>` | A populated `<doc-dir>/parts/` directory | One `PLAN.md` per part: first activated at `<project>/.harness/PLAN.md`; rest queued at `<project>/.harness/designs/<doc-slug>/queued-plans/<part-slug>.PLAN.md` | Requires `Status: final` |

`Status: launched` is set by the harness `/release` flow (not the skill) when the design's last queued part's `PLAN.md` completes. See [§1b of `/release`](https://github.com/alexherrero/agentic-harness/blob/main/harness/phases/05-release.md) for the lifecycle hook.

## When to reach for `/design` vs. `/plan`

| You have… | Reach for |
|---|---|
| A precise problem statement; can name verification criteria per task in one sentence each; no cross-cutting Quality Attributes / Operations thinking needed | `/plan` directly |
| Ambiguous scope; multiple stakeholders; the change has cross-cutting Quality Attributes (security/reliability/scalability/etc.) or Operations (SLAs/monitoring/rollback) concerns that need explicit thinking before code starts | `/design author` |
| You want a canonical "Why we built X" wiki entry point that survives the implementation phase | `/design author --visibility published` |
| The design is settled but you want to ship it in independent slices | `/design translate` + `/design sequence` after `/design author` finalizes |

Use both when standing up something substantial that ships in multiple parts: `/design author` → `/design translate` → `/design sequence` once; then `/work` cycles through each part's PLAN.md tasks. The harness `/release` flow handles per-part plan promotion + the launched-Status transition.

## Scenario 1 — Feature design from a blank slate (the typical case)

**Goal:** stand up a new `/foo` system across data layer + UI + rollout. Three structural parts; want it discoverable in the wiki as a canonical design doc.

**Step 1 — Author the design.**

```
/design author foo-system --visibility published
```

Skill bootstraps the doc at `wiki/explanation/designs/foo-system.md` with `Status: draft` + prefilled frontmatter. Then walks each of the 10 template sections:

- Context → Objective + Background
- Design → Overview + Infrastructure + Detailed Design
- Alternatives Considered
- Dependencies / Migrations / Technical Debt & Risks
- Quality Attributes (all 11 sub-attrs prompted — N/A allowed only with one-sentence rationale)
- Project management → Work estimates + Documentation Plan + Launch Plans
- Operations → SLAs + Monitoring + Logging + Rollback
- Document History (seeded by skill)

At the end: `Ready for review?` → `Yes` → `Status: draft → review`. Skill announces the doc is awaiting review.

**Step 2 — Review pass.**

```
/design author foo-system
```

Skill detects `Status: review`; walks each section asking `Approve / Revise / Skip?`. After all sections reviewed: `Approve as final?` → `Yes` → `Status: review → final`. The doc is now locked; `/design translate` becomes available.

**Step 3 — Translate to structural parts.**

```
/design translate foo-system
```

Skill proposes a 3-part split (one per Detailed Design subsection):

```
| # | Slug | Title | Dependencies | Est. | Source sections |
|---|------|-------|--------------|------|-----------------|
| 1 | foundations | Foundations: data model + access layer | (none) | M | Detailed Design §1 |
| 2 | ui | UI: command + status display | depends on #1 | S | Detailed Design §2 |
| 3 | rollout | Rollout: feature flag + telemetry | depends on #1, #2 | S | Detailed Design §3 + Operations §Monitoring |

Approve / Reshape / Cancel?
```

Operator reshapes to rename `ui → command-surface`, then `Approve`. Skill writes three part files at `wiki/explanation/designs/foo-system/parts/{foundations,command-surface,rollout}.md` and appends to parent's Document History.

**Step 4 — Sequence into PLAN.md per part.**

```
/design sequence foo-system
```

Skill topologically sorts (foundations → command-surface → rollout); generates a `PLAN.md` per part using the harness PLAN.md template shape. Result:

```
<project>/.harness/PLAN.md                                          (foundations — active, Status: draft)
<project>/.harness/designs/foo-system/queued-plans/command-surface.PLAN.md  (queued)
<project>/.harness/designs/foo-system/queued-plans/rollout.PLAN.md           (queued)
```

Parent's Document History updated; `Status` stays `final`.

**Step 5 — Execute via existing harness flow.**

```
/plan         # refine the active foundations.PLAN.md task decomposition
/work         # task 1
/work         # task 2 ... etc.
/release      # when all foundations tasks [x] → triggers §1b plan promotion:
              #   command-surface.PLAN.md auto-promoted to .harness/PLAN.md
              #   foundations.PLAN.md archived
              # /release halts with "Plan foundations complete (1 of 3). Plan
              # command-surface now active. Run /work to start the next part."
```

When the **last part** (`rollout`) completes, `/release` Case C transitions the parent design `Status: final → launched`, updates `wiki/Home.md` + `_Sidebar.md` to surface the design, and continues with the rest of the release flow (CHANGELOG, tag, etc.).

## Scenario 2 — Revising mid-execution

**Setup:** halfway through `command-surface.PLAN.md` (the second part of the `foo-system` design), the operator spots a flaw in the parent design's Infrastructure section that affects both `command-surface` and the still-queued `rollout` part.

**Step 1 — Edit the parent design.**

Operator manually edits `wiki/explanation/designs/foo-system.md`:
- Updates `## Design / ### Infrastructure` to reflect the new approach
- Manually appends a row to `## Document History`:
  ```
  | 2026-05-20 | Revised Infrastructure approach: <one-line summary of change>. Re-translate affects command-surface + rollout. | final |
  ```
- Status stays `final` (revisions to a finalized design append history but don't transition Status).

**Step 2 — Re-translate.**

```
/design translate foo-system
```

Skill detects existing `parts/` and re-proposes the split. It diffs the new proposal against the existing part files and presents the delta:

```
Re-translate detected. Diff vs existing parts/:

| Part | Status | Change |
|------|--------|--------|
| foundations | unchanged | (already shipped via PLAN.md → done; no regeneration needed) |
| command-surface | proposed-revise | Scope updated per new Infrastructure |
| rollout | proposed-revise | Verification criteria updated per new Infrastructure |

Per-file: Overwrite / Keep existing / Cancel?
```

Operator approves overwrite for `command-surface` + `rollout`. Skill updates those two part files; foundations untouched (it already shipped — that part is `Status: done` in its own PLAN.md).

**Step 3 — Re-sequence.**

```
/design sequence foo-system --force-replace
```

The `--force-replace` flag is needed because there's an in-progress active PLAN.md (the partially-completed `command-surface.PLAN.md`). Skill:
- Archives the in-progress PLAN.md to `.harness/PLAN.archive.<date>-command-surface-pre-revision.md`
- Generates a new `command-surface.PLAN.md` from the revised part + activates it at `.harness/PLAN.md`
- Re-generates `rollout.PLAN.md` in queued-plans/
- Appends Document History on parent

**Step 4 — Continue execution.**

Operator runs `/plan` to merge in any unfinished tasks from the archived in-progress plan (or starts fresh if the revision is significant enough). Then `/work` continues.

The Document History on the parent design is the **audit trail** — every translate / sequence / launched transition writes a row. Mid-execution revisions are normal; the workflow accommodates them.

## Scenario 3 — Confidential design (machine-local only)

**Goal:** design an internal-only tool that shouldn't appear in the public wiki. The structural-parts + PLAN.md generation works identically; only the doc location differs.

**Invocation:**

```
/design author internal-ops-tool --visibility confidential
```

Skill routes the doc to `.harness/designs/internal-ops-tool.md` instead of `wiki/explanation/designs/`. Since `.harness/` is gitignored, the doc never enters the public repo.

**The rest of the workflow is identical:**

- `/design translate internal-ops-tool` writes parts to `.harness/designs/internal-ops-tool/parts/<part-slug>.md` (still gitignored).
- `/design sequence internal-ops-tool` writes `PLAN.md` + queued plans to `.harness/` as usual (those are gitignored too).
- `/work` + `/release` run normally.
- When the last part launches, `/release` transitions the design `Status: final → launched` — but **does NOT** update `wiki/Home.md` + `_Sidebar.md` (the visibility check filters confidential designs out of the wiki surface).

The design lives entirely on the operator's machine; the audit trail (Document History) accumulates in the gitignored file. To "promote" a confidential design to published later: edit the frontmatter `visibility:` to `published`, move the file from `.harness/designs/` to `wiki/explanation/designs/`, append Document History noting the promotion, and re-run `/release` if the design is already `launched` to trigger the wiki surfacing.

## Scenario 4 — External-review handoff (long-doc Antigravity-Gemini workflow, v0.8.1+)

**Goal:** review a long design doc (or PLAN.md, or proposed translate split) using Antigravity's native inline-comment UI + Gemini-applies-comments pattern, instead of Claude Code's block-by-block walk. Useful when the doc is too long for inline review to feel ergonomic (~2000+ words; the 30-min walk threshold).

**When to pick external over inline**:

| You're reviewing… | Reach for |
|---|---|
| A short design doc (<1500 words) or focused PLAN.md (<8 tasks) | Inline (current default) — context-switch overhead isn't worth it |
| A long design doc with many sections needing attention | External — Antigravity-Gemini handles the apply pass in one shot |
| A proposed `/design translate` split with several reshape ops you want to think through | External — comment all reshape requests at once, Gemini applies in one pass |
| Anything you'd want to read carefully in your editor of choice before commenting | External — leverage editor scrollback + search |
| Anything you want Claude to walk you through one section at a time | Inline — the per-section pacing helps you think |

**Step 1 — Pick external review at one of three offer points.**

Three skill points offer the option:

- `/design author` Step 5 (after walk-sections, alternative to "Ready for review" transition)
- `/design author` Step 6 (review-pass on `Status: review` docs, alternative to per-section Approve/Revise/Skip)
- `/design translate` Step 4 (alternative to inline Reshape commands on proposed part split)

Pick `"Hand off for external review"` when prompted.

**Step 2 — Skill generates handoff artifacts.**

The skill writes:

- **Pre-handoff snapshot**: `<target-doc>.pre-handoff-<YYYYMMDDhhmmss>.md` — used by Claude on resume to diff against the revised version.
- **Transfer-context file**: `.harness/transfer/<doc-slug>-<YYYYMMDDhhmmss>.md` — inlines operator intent + recent decisions to honor + dev-flow conventions + doc-type guardrails + explicit MUST-NOT rules. Gives Antigravity-Gemini everything it needs without requiring access to the Claude Code conversation. Template at `agent-toolkit/skills/design/templates/transfer-context.md`.

The skill outputs a **handoff prompt** for you to take to Antigravity:

```
External-review handoff ready. Take to Antigravity:

  1. Open the target doc: <absolute path>
  2. Open the transfer context: <.harness/transfer/<slug>-<ts>.md>
  3. Add inline comments using Antigravity's native comment UI wherever
     you want changes. The transfer context tells Gemini what conventions
     to honor + what's locked.
  4. When done commenting, ask Gemini: "apply my comments per the
     transfer context". Gemini revises the doc + writes a change-summary
     log at <target-doc>.diff.md.
  5. Return to Claude Code and say "review complete on <slug>" (or run
     `/design author <slug> --resume-external-review`). Claude will diff
     against the pre-handoff snapshot and surface findings.

Pre-handoff snapshot saved at <snapshot path>.
```

The Claude Code session pauses (return control to you) until resume.

**Step 3 — Review in Antigravity.**

Open the target doc + the transfer-context file side-by-side. Walk the doc; add inline comments using Antigravity's native UI wherever you want changes. The transfer context tells Gemini the conventions to follow + what's locked (frontmatter, Document History pre-handoff rows, Status fields, the 11 Quality Attribute sub-attrs discipline, etc.).

When done commenting, ask Gemini: *"apply my comments per the transfer context"*. Gemini:

1. Reads the transfer context.
2. Applies each inline comment in document order, honoring the dev-flow conventions + MUST-NOT rules.
3. Saves the revised doc to the same path.
4. Writes a **change-summary log** at `<target-doc>.diff.md` listing per-comment narrative + any "Comments not applied" with rationale + a "Suggestions" section for adjacent issues you may want to address in a future pass.

**Step 4 — Return to Claude Code with the resume prompt.**

```
/design author memoryvault --resume-external-review
```

(or natural language `"review complete on memoryvault"`).

Claude reads the revised doc + the change-summary log, diffs against the pre-handoff snapshot, and surfaces:

- **Applied changes**: per-comment, what changed and why.
- **Frontmatter modifications**: any change to `status` / `visibility` / `last_major_revision` etc. (which should be flagged in the change-summary log if expected).
- **"Recent decisions to honor" modifications**: any apparent override (should be flagged in the change-summary log if intentional).
- **Suggestions**: Gemini's adjacent issues you may want to address in another pass.

Claude asks: `"Accept all changes / iterate further (another external pass) / discard the handoff entirely?"`.

- **Accept** → cleanup snapshot + transfer-context (moved to `.harness/transfer/_archive/`); continue original flow (transition to `review` if invoked at Step 5; final-approval prompt if invoked at Step 6).
- **Iterate** → regenerate transfer-context with updated "Recent decisions to honor" (including what was applied in the previous round); re-run handoff.
- **Discard** → restore from pre-handoff snapshot; doc returns to its pre-handoff state; archive the failed handoff for audit; continue with inline flow.

**Step 5 — Multi-round iteration if needed.**

The cycle can repeat. Each subsequent handoff regenerates a fresh transfer-context file with updated context. The pre-handoff snapshot is regenerated per round so diffs always compare against the immediate-prior state.

**Trade-offs to know about**:

- **Context-switch overhead** — you're moving between Claude Code + Antigravity per round. For short docs this overhead isn't worth it; for long docs the inline-comment UX win dominates.
- **Silent-drift risk** — Antigravity-Gemini may revise things you didn't comment on. The transfer-context MUST-NOT list + Claude's diff-on-resume catch this; surfaces appear in the diff review.
- **Artifacts to manage** — `.harness/transfer/`, `<path>.pre-handoff-<ts>.md`, `<path>.diff.md`. Cleanup happens on Accept (auto-archive) or Discard (auto-restore). 30-day GC on archived handoffs comes post-MemoryVault.

## Status lifecycle

| State | Set by | Meaning | What's unlocked |
|---|---|---|---|
| `draft` | `/design author` (initial bootstrap) | Authoring in progress; not yet submitted for review | Continue `/design author` |
| `review` | `/design author` (human signals readiness) | Author thinks it's done; awaiting review pass | `/design author` runs the review pass with Approve/Revise/Skip per section |
| `final` | `/design author` (explicit human approval in review pass) | Approved. Hard gate cleared | `/design translate` + `/design sequence` |
| `launched` | Harness `/release` (last queued part's PLAN.md hits Status: done) | All structural parts shipped. Full execution arc complete | Published designs surface in `wiki/Home.md` + `_Sidebar.md` |

The skill never transitions Status backwards. `review → draft` is an escape-hatch manual edit if a review pass stalls; document the reason in Document History.

## Wiki integration

`visibility: published` designs are the canonical "Why we built X" entry points. When the harness `/release` Case C fires (last queued part's PLAN.md complete):

1. Parent design Status: `final → launched`
2. Document History row appended
3. **If** `visibility: published`:
   - `wiki/Home.md` gains a "Designs" section row (idempotent — re-runs are no-op)
   - `wiki/_Sidebar.md` mirrors the addition

Confidential designs **never** appear in `wiki/Home.md` / `_Sidebar.md` — `.harness/designs/` is gitignored and the visibility check in `/release` §1b filters them out.

## Manual equivalents for other hosts

The `/design` skill ships for all three hosts (`claude-code`, `antigravity`, `gemini-cli`) but the **interactive flow** depends on the host's slash-command + file-editing surface:

- **Claude Code**: native — slash commands trigger the skill body; `Read` / `Write` / `Edit` tools handle file ops. The flow described above is the canonical user experience.
- **Antigravity**: install an always-on rule that says *"between steps, check `wiki/explanation/designs/` and `.harness/designs/` for any Status: review or Status: final docs awaiting next-stage skill invocation. Surface them to the operator as next-action candidates."* The skill body is still readable but invocation is operator-driven not slash-command-triggered.
- **Gemini CLI**: similar — operator prompt convention citing `wiki/explanation/designs/` + `.harness/designs/` as canonical context dirs. Read the skill's SKILL.md as a workflow reference.

Manual-equivalent flows are best-effort (operator drives invocation) and don't have the precision of Claude Code's native slash commands. Use Claude Code for the strongest end-to-end experience.

## Troubleshooting

**`/design translate` refuses to run with "Status is 'draft' / 'review' / 'launched'":**

The skill is enforcing the Status gate. Run `/design author <slug>` to complete authoring (`draft → review`) or the review pass (`review → final`) first. If Status is `launched` and you're trying to revise, edit the design doc manually + append a Document History entry + run translate; the skill will detect the launched state and refuse, prompting you to either (a) revert Status to `final` manually if revising substantively, or (b) author a new design doc if the change is large enough.

**`/design sequence` says "<doc-dir>/parts/ does not exist":**

You haven't run `/design translate` yet. Translate produces the `parts/` directory; sequence consumes it. Run `/design translate <slug>` first.

**Queued plans not promoting at `/release`:**

Check that the active plan has `parent_design_doc:` in its frontmatter. The harness `/release` §1b detects design-sourced plans via that field. If the field is missing (e.g. you hand-edited PLAN.md), §1b silent-skips and falls through to the standard release flow. Either restore the `parent_design_doc:` frontmatter or manually promote the next queued plan with `mv .harness/designs/<doc-slug>/queued-plans/<next-part-slug>.PLAN.md .harness/PLAN.md`.

**Wiki entry not surfacing after launched transition:**

Check the parent design's `visibility:` frontmatter. Only `published` designs surface in `wiki/Home.md` + `_Sidebar.md`. Confidential designs deliberately stay machine-local. If you intend to publish a previously-confidential design, edit `visibility: confidential → published`, move the file from `.harness/designs/` to `wiki/explanation/designs/`, append Document History, and re-run `/release` to trigger the wiki update.

**Mid-execution revision didn't re-translate affected parts:**

Re-running `/design translate` after manually editing the parent design diffs the proposed split against the existing parts/ files. If you see "no proposed changes" but the parent design was edited, the change probably didn't affect the Detailed Design subsections (translate only re-proposes when the source-of-truth content changes). For substantive revisions, edit the affected Detailed Design subsection content + re-run translate.

## See also

- [Customization Types](Customization-Types) — what `kind: skill` means and where `/design` lands per host.
- [Manifest Schema](Manifest-Schema) — the YAML frontmatter contract for skills.
- [Per-Host Paths](Per-Host-Paths) — destination paths for skills + agents + hooks across the three hosts.
- [Installer CLI](Installer-CLI) — flag reference + exit codes; how `/design` ships into target projects.
- [`/design` skill spec](../../skills/design/SKILL.md) — full body documentation for all three sub-commands.
- [`templates/design-doc.md`](../../skills/design/templates/design-doc.md) — the locked 10-section template.
- [ADR 0004 — Design skill design](../explanation/decisions/0004-design-skill.md) — design rationale + locked design calls + consequences.
- [agentic-harness `/release` §1b](https://github.com/alexherrero/agentic-harness/blob/main/harness/phases/05-release.md) — the harness-side plan-promotion + Status transition hook.
