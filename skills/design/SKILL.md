---
name: design
description: Human-facing design pipeline that walks the user through a locked 10-section design-doc template, gates on human approval (Status draft → review → final), then translates the approved design into structural parts and generates a PLAN.md per part for the harness's `/work` + `/review` flow to execute. Published designs surface in `wiki/Home.md` as the canonical "Why we built X" entry point.
kind: skill
supported_hosts: [claude-code, antigravity, gemini-cli]
version: 0.1.0
install_scope: project
---

# design — human-facing design pipeline → agent execution handoff

A skill that runs the **front** of a project: the design phase a human cares about. Walks the user through a precise 10-section design-doc template, gates on human approval, then hands the approved design off to the harness's `/work` + `/review` flow as one or more `PLAN.md` files (one per structural part).

**Position vs. the harness's `/plan`:** `/plan` expects a brief and emits tasks — good for "I know what I want, give me a task breakdown." This skill starts *earlier*: it walks you through assembling a real design doc in a specific structured shape, then uses that same shape to drive the breakdown. Reach for `/design` when the problem is ambiguous, has multiple stakeholders, or needs Quality Attributes / Operations thinking before code starts. Reach for `/plan` when the design is already settled.

## Sub-commands

The skill exposes three sub-commands, dispatched by the host's slash-command surface:

| Sub-command | Inputs | Outputs | Status gate |
|---|---|---|---|
| `/design author` | Slug + Visibility | Design doc at `wiki/explanation/designs/<slug>.md` (published) or `.harness/designs/<slug>.md` (confidential) | Drives `draft → review → final` |
| `/design translate` | A `Status: final` design doc | Structural-part files at `<doc-dir>/parts/<part-slug>.md` | Requires `Status: final` (hard gate) |
| `/design sequence` | A populated `<doc-dir>/parts/` directory | One `PLAN.md` per part (first activated; rest queued) | Requires `Status: final` |

**Status `launched`** is set by the harness `/release` flow when the last part's PLAN.md completes — the design skill does not transition to `launched` directly.

### `/design author`

Walks a human through assembling a design doc in the 10-section template. Two modes:

- **Authoring** (new doc or `Status: draft`): bootstrap a new file or resume an in-progress draft. Section-by-section interactive flow. Saves after each section so partial drafts survive session interruption.
- **Review pass** (`Status: review`): walk an author-marked-ready doc and approve / revise / skip per section. Drives `review → final`.

`/design author` is the **only** sub-command that transitions Status (`draft → review → final`). It never advances past `final` — `Status: launched` is set by the harness `/release` flow when the last queued part's `PLAN.md` completes.

#### Inputs

The skill accepts (in any order):

- **`<slug>`** — short identifier used in the filename (e.g. `context-vault`, `learn-skill`, `kill-switch-v2`). Required for new docs; inferred from the path for resume.
- **`--visibility {confidential|published}`** *(optional, defaults to `confidential` on new docs)* — controls the output path:
  - `confidential` → `.harness/designs/<slug>.md` (gitignored, machine-local)
  - `published` → `wiki/explanation/designs/<slug>.md` (committed; surfaces in `wiki/Home.md` + `_Sidebar.md` as the canonical "Why we built X" entry point per the locked design call)
- **`--resume <path>`** *(optional)* — explicitly resume an existing doc at the given path. Without this flag, the skill checks both `.harness/designs/<slug>.md` and `wiki/explanation/designs/<slug>.md`; if exactly one exists, resumes that; if both exist, asks the human which.

#### Step-by-step flow

**Step 1 — Bootstrap (new doc only).** If the target path doesn't exist:

1. Confirm the title with the human (default: derive from slug → title case).
2. Copy the template at `agent-toolkit/skills/design/templates/design-doc.md` (or the equivalent project-local path if the skill is installed) to the target path.
3. Prefill frontmatter:
   - `title` ← confirmed title
   - `status: draft`
   - `visibility` ← caller's choice
   - `author` ← read from `.git/config` via `Read` tool, parsing the `[user]` block's `name = ...` line. If `.git/config` unreadable or `name` absent, prompt the human for their name.
   - `contributors: []`
   - `created` ← today's UTC date in `YYYY-MM-DD`
   - `updated` ← same as `created` initially
   - `last_major_revision` ← same as `created` initially
   - `prd` / `project` left empty unless the human provides on bootstrap
4. Seed the Document History table with the initial-draft row: `| <today> | Initial draft created via /design author. | draft |`
5. Confirm bootstrap to the human with the path + ready-to-walk message.

If the target path already exists, skip step 1 and proceed to walk-sections; the doc's existing Status determines the mode (Authoring vs. Review pass).

**Step 2 — Walk sections.** For each top-level section in template order (Context → Design → Alternatives Considered → Dependencies → Migrations → Technical Debt & Risks → Quality Attributes → Project management → Operations):

1. Read the current state of the section from the file via `Read`.
2. If the section is empty (only contains the italic prompt + HTML comments): present the prompt to the human, ask `"What goes in this section?"`, and accept multi-line response (paste or typed).
3. If the section already has content (resume case): present the existing content, ask `"Keep / Edit / Replace?"`.
4. Write the human's response into the section via `Edit`, replacing the italic prompt + HTML comments with the actual content. The italic prompt + comments are author-facing scaffolding; once filled, they don't render in the final doc.
5. Optionally read the section back via `Read` and confirm to the human.
6. Update the `updated` frontmatter field after each section save.

Sub-sections inside Design (Overview / Infrastructure / Detailed Design) and Project management (Work estimates / Documentation Plan / Launch Plans) and Operations (SLAs / Monitoring and Alerting / Logging Plan / Rollback Strategy) get prompted as individual children of their parent section, in template order.

**Step 3 — Quality Attributes drill-down.** Quality Attributes is the section with the strictest discipline. Walk each of the 11 sub-attrs in template order: Security → Reliability → Data Integrity → Privacy → Scalability → Latency → Abuse → Accessibility → Testability → Internationalization & Localization → Compliance.

For each sub-attr, prompt:

> `"<attr>: Does this design have <attr> concerns? Describe them, or 'N/A' with one sentence on why."`

Accept responses in two shapes:
- **Substantive content**: write into the sub-section as-is.
- **N/A response**: must take the form `"N/A: <one-sentence rationale>"`. If the human just says `"N/A"` without rationale, push back: `"N/A needs a one-sentence reason. Why doesn't this design have <attr> concerns?"`

The discipline is non-negotiable per the locked design call — forcing conscious N/A catches ops blind spots early. If the human resists giving an N/A rationale across multiple attrs, the skill flags it: `"Most designs have at least one concern in <Reliability | Security | Testability>; want to revisit?"`

**Step 4 — Alternatives Considered.** Single-section prompt:

> `"What other approaches did you consider? Why did you reject each?"`

Default behavior pushes for at least one alternative. Only accept `"N/A: only one viable approach (<one-sentence justify>)"` if the human explicitly confirms after one push-back. Most designs have an alternative worth recording.

**Step 5 — Save + Status lifecycle.** After all sections are filled:

1. Present a summary of the doc to the human (sections filled, sub-attrs marked N/A vs. described, total length).
2. Ask: `"Ready for review? (Status → review)"` / `"Keep drafting?"` / `"Stop and resume later?"`.
3. On `Ready for review`: transition `status: draft → review`. Append to Document History: `| <date> | Author signaled ready for review. | review |`. Tell the human the doc is now in review and the next `/design author <slug>` invocation will run the review-pass flow.
4. On `Keep drafting`: stay in draft; return to walk-sections for any section the human wants to revisit.
5. On `Stop and resume later`: save current state; remind the human that `/design author --resume <path>` (or just `/design author <slug>`) will pick up where they left off.

**Step 6 — Review pass support.** If `/design author` is invoked on a `Status: review` doc:

1. Announce the review-pass mode: `"This doc is Status: review. Walking sections for approve / revise / skip."`.
2. For each section (Context → Design → ... → Operations) and each sub-attr inside Quality Attributes: present the current content and prompt `"Approve / Revise / Skip?"`.
   - `Approve`: section passes review unchanged. Track the approval count.
   - `Revise`: open the section for edits via the same walk-sections flow as Step 2 (accept new content, replace).
   - `Skip`: move to next section without judgment. Track skip count.
3. After all sections reviewed: present a summary. If any section was Skipped or Revised, ask: `"Some sections still need attention. Continue review pass? Or transition to final anyway?"`.
4. On approval to finalize: ask explicit `"Approve as final? This locks the doc and unblocks /design translate."`. On `yes`: transition `status: review → final`. Append to Document History: `| <date> | Approved as final via /design author review pass. | final |`. Update `last_major_revision` to today.

After `Status: final` is set, `/design author` refuses further invocations on the same doc — finalized docs are immutable until a `/design translate` run promotes them into structural parts (or a human manually edits the file + reverts Status to `review`, which is an escape hatch documented in the troubleshooting section of the how-to).

#### Status transition summary

| Transition | Trigger | Set by |
|---|---|---|
| (none) → `draft` | Bootstrap on new doc | `/design author` (Step 1) |
| `draft → review` | Human signals "ready for review" | `/design author` (Step 5) |
| `review → final` | Human explicitly approves the reviewed doc | `/design author` (Step 6) |
| `final → launched` | Last queued part's PLAN.md completes | Harness `/release` (task 5 of plan #6) |
| `review → draft` (rare) | Human manually edits Status field after a stalled review | Manual — escape hatch |

The skill never transitions backwards. Going `review → draft` is operator-driven.

#### Tool allowlist

**`Read, Write, Edit, Glob, Grep` only.** No `Bash`. The `git config user.name` read in Step 1 is via `Read` on `.git/config` + string parsing — not via `git config` shell invocation.

If `Read` on `.git/config` fails (file unreadable, no `[user]` block, missing `name` key), the skill prompts the human for their name as a fallback. Never silently leaves the `author:` field blank.

#### Hard gates

`/design author` is the **only** sub-command that transitions `Status`. `/design translate` and `/design sequence` will refuse to run on non-`final` docs with a clear error message pointing the user back to `/design author` to complete the review pass.

#### Worked example

Walking a 3-section synthetic design end-to-end ("add a `/foo` command").

**Invocation:** `/design author foo-command --visibility published`

**Step 1 (bootstrap):**

> Agent: "Confirming title — default is 'Foo Command' from the slug. Use that, or different?"
> Human: "Use that."
> Agent: *(copies template, prefills frontmatter, writes file at `wiki/explanation/designs/foo-command.md` with Status: draft + Document History initial row)*
> Agent: "Bootstrap done. Doc at `wiki/explanation/designs/foo-command.md`, Status: draft. Ready to walk sections — starting with Context/Objective."

**Step 2 (walk: Context/Objective):**

> Agent: "Context/Objective. *What problem does this solve, and why now?*"
> Human: "Users want a quick way to invoke the `foo` action without going through the menu. Now because the feature shipped underspecified and people are confused."
> Agent: *(Edits the file; replaces italic prompt + HTML comments in the Objective sub-section with the human's response)*
> Agent: "Got it. Next: Context/Background."

**Step 2 (walk: Context/Background):**

> Agent: "Context/Background. *History, related work, current state.*"
> Human: "We shipped `foo` in v2.1.0 via the menu only. ADR 0023 chose menu-first as a UX call; this design revisits that for keyboard-driven users."
> Agent: *(writes; presents next prompt)*

**Step 2 (walk: Design/Overview):**

> Agent: "Design/Overview. *The shape of the design in 1-3 paragraphs.*"
> Human: "A new slash command `/foo` that triggers the same action as the menu item. Lives in commands/. Reuses the existing foo-handler with no logic changes — pure plumbing."
> Agent: *(writes; continues to Infrastructure → Detailed Design → Alternatives → Dependencies → ... walking each in order)*

**Step 3 (Quality Attributes drill-down — example for Security):**

> Agent: "Security: *Does this design have Security concerns? Describe them, or 'N/A' with one sentence on why.*"
> Human: "N/A"
> Agent: "N/A needs a one-sentence reason. Why doesn't this design have Security concerns?"
> Human: "N/A: pure UI plumbing; reuses existing handler with no new permissions, no new data paths, no new attack surface."
> Agent: *(writes "N/A: pure UI plumbing; ..." into the Security sub-section)*
> Agent: "Reliability: *Does this design have Reliability concerns? ...*"

*(continues through all 11 sub-attrs)*

**Step 5 (save + lifecycle):**

> Agent: "All sections filled. Summary: 10 sections / 7 sub-attrs described + 4 marked N/A with rationale / 1 alternative captured. Ready for review? (Status → review) Or keep drafting?"
> Human: "Ready for review."
> Agent: *(transitions Status: draft → review, appends to Document History, updates `updated` field)*
> Agent: "Doc transitioned to Status: review. Next invocation of `/design author foo-command` runs the review pass. When you're ready to approve, the pass concludes with `/design translate` becoming available."

**Later — review pass (Step 6):**

> *(human invokes `/design author foo-command` later)*
> Agent: "This doc is Status: review. Walking sections for approve / revise / skip. — Context/Objective: <content>. Approve / Revise / Skip?"
> Human: "Approve."
> Agent: "Context/Background: <content>. Approve / Revise / Skip?"
> *(continues through all sections)*
> Agent: "Review pass complete: 10 sections approved, 1 revised, 0 skipped. Approve as final? This locks the doc and unblocks `/design translate`."
> Human: "Approve as final."
> Agent: *(transitions Status: review → final, appends Document History, updates last_major_revision)*
> Agent: "Doc is Status: final. Run `/design translate foo-command` next to split into structural parts."

#### Failure modes

- **Template not found** — if `agent-toolkit/skills/design/templates/design-doc.md` is unreadable, the skill halts with a clear error and a hint to verify the toolkit install. Never falls back to a degraded inline template.
- **Existing doc with malformed frontmatter** — if resume hits a doc whose frontmatter doesn't parse as YAML, the skill halts with `"<path>: frontmatter invalid; manual fix needed before resume"`. Doesn't try to auto-repair.
- **Existing doc with unknown Status value** — Status must be one of `draft|review|final|launched`. Anything else halts with an error.
- **Session interrupted mid-section** — the doc is saved after each section, so partial state survives. Resume picks up at the first incomplete section. If the user wrote half a section and the session died mid-Edit, the half-written state may be present — the resume prompt presents what's there and asks `"Keep / Edit / Replace?"`.
- **Quality Attributes N/A loop** — if the human N/A's all 11 sub-attrs without rationale across multiple prompts, the skill surfaces: `"All 11 Quality Attributes marked N/A; this is unusual. Want to revisit, or confirm the design genuinely has no quality-attribute concerns?"`. Doesn't block, but documents the unusual choice in the Document History.

#### Anti-patterns

`/design author` must not:

- **Silently transition Status.** Every transition is announced and confirmed.
- **Skip Quality Attributes prompts.** Even on resume, any sub-attr without content is prompted.
- **Auto-publish a confidential doc.** Visibility transitions (`confidential → published`) require explicit human change of the frontmatter field + a fresh `/design author` invocation.
- **Edit Status backwards.** The skill never moves `final → review` or `review → draft`. The escape hatch is manual: human edits the Status field directly.
- **Lose work on session crash.** Saves are per-section, not batched. `commit-on-stop` (from agent-toolkit's base hooks, plan #4) provides additional safety net if the session crashes mid-Edit.

### `/design translate` *(stub — full body lands in task 3 of plan #6)*

Reads a `Status: final` design doc and proposes a split of the Detailed Design into N structural parts (one per top-level subsection by default; human can merge / split / reshape). Writes `<doc-dir>/parts/<part-slug>.md` files with: inherited frontmatter, part-specific Title / Scope / Dependencies on other parts / Verification criteria. Appends to Document History.

### `/design sequence` *(stub — full body lands in task 4 of plan #6)*

Topologically sorts the parts by their declared dependencies and generates one `PLAN.md` per part using the harness's existing `templates/PLAN.md` shape. First part's plan activates at `.harness/PLAN.md`; subsequent parts queue in `.harness/designs/<doc-slug>/queued-plans/`. Harness `/release` auto-promotes the next queued plan when the active plan completes.

## Tool allowlist

**`Read, Write, Edit, Glob, Grep` only.** No `Bash`, no `NotebookEdit`. The skill's job is file authorship + structured edits — not shell invocation. Bash invocation, if needed downstream, comes from the harness `/work` phase during stage 5 (per-part execution).

## File conventions

- **Template:** `agent-toolkit/skills/design/templates/design-doc.md` (ships with the skill). The `/design author` flow copies this template into the target project as the starting point for a new design.
- **Confidential designs:** `.harness/designs/<slug>.md` — gitignored, machine-local; not committed to a public repo. Use for early exploration, internal-only designs.
- **Published designs:** `wiki/explanation/designs/<slug>.md` — committed; surfaces in `wiki/Home.md` + `wiki/_Sidebar.md` as the canonical "Why we built X" entry point per ADR 0004 (lands in task 6 of plan #6).
- **Parts:** `<doc-dir>/parts/<part-slug>.md` — same dir as the parent design doc, in a `parts/` subdir.
- **Queued plans:** `.harness/designs/<doc-slug>/queued-plans/<part-slug>.PLAN.md` — waiting in the wings until harness `/release` promotes the next one.

## Status lifecycle

| State | Set by | Meaning |
|---|---|---|
| `draft` | `/design author` (initial creation) | Authoring in progress; not ready for review. |
| `review` | `/design author` (human signals readiness) | Author thinks it's done; awaiting human approval. |
| `final` | `/design author` (explicit human approval) | Approved. **Hard gate:** `/design translate` and `/design sequence` only run on `Status: final`. |
| `launched` | Harness `/release` (last queued part's PLAN.md hits `Status: done`) | All structural parts shipped. The design's full execution arc is complete. |

`Status` is set by the skill; users don't edit it by hand.

## When to reach for it

- **Use `/design`** when: the problem is ambiguous, multiple stakeholders need to align, the change has cross-cutting Quality Attributes (security/reliability/scalability/etc.) or Operations (SLAs/monitoring/rollback) concerns that need explicit thinking before code starts, or you want a canonical "Why we built X" wiki entry point.
- **Use `/plan` instead** when: the problem is already well-scoped, you can name the verification criteria in one sentence per task, and the change is fully contained to code (no ops / no rollout complexity).
- **Use both** when: you're standing up something substantial that will ship in multiple parts. Run `/design author` → `/design translate` → `/design sequence` once; then `/work` cycles through each part's PLAN.md tasks.

## Cross-references

- [Use-The-Design-Skill](../../wiki/how-to/Use-The-Design-Skill.md) — practical recipe with three worked scenarios *(lands in task 6 of plan #6)*
- [ADR 0004 — Design skill design](../../wiki/explanation/decisions/0004-design-skill.md) — locked design calls + rationale + consequences *(lands in task 6 of plan #6)*
- Template: [`templates/design-doc.md`](templates/design-doc.md) — the 10-section structure all `/design author` flows write against
- agentic-harness phases: [`/work`](https://github.com/alexherrero/agentic-harness/blob/main/harness/phases/03-work.md), [`/release`](https://github.com/alexherrero/agentic-harness/blob/main/harness/phases/05-release.md) — execute the per-part PLAN.md files generated by `/design sequence`
