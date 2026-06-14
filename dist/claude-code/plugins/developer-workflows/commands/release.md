---
name: release
description: Pre-merge gate — verify plan done, gates green, CI passing, then run to completion under the recoverability gate (recoverable push/tag/release proceed announced; only unrecoverable actions stop).
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

You are running the **release** phase of the developer-workflows loop. This is a **pre-merge gate**: verify the plan is complete and everything is green, then prepare and ship the release. Invoking `/release` **is** the authorization to push / tag / release — those are recoverable, so they run announce-and-proceed under the recoverability gate below; only a genuinely unrecoverable action stops for confirmation.

<!-- BEGIN recoverability-gate · canonical · byte-identical across work.md · bugfix.md · release.md (scripts/ drift test enforces) -->
## Recoverability gate (autonomy doctrine)

Invoking this phase **is** the authorization to run it to completion. The stop-gate is **recoverability, not destructiveness or blast-radius**: a recoverable action proceeds (announced); only a genuinely unrecoverable one stops for confirmation.

| Class | Examples | Behavior |
|---|---|---|
| **Recoverable** | `git push` / `-u` / `HEAD:`; create + push a tag; `gh release create` (deletable); `gh pr merge` (revertable); `gh issue create` / `close`; force-push to your **own un-shared** worker branch; delete a branch whose tip is still reachable | **Announce + proceed** — no confirmation wait. |
| **Unrecoverable** | force-push rewriting **published shared** history; sole-ref delete of unmerged work; **published-tag** overwrite; immutable publish / deploy / migration | **Stop + confirm** — pre-announce (state, don't ask), then wait. |
| **Unresolved decision** | a genuine question the design/plan never settled | **Stop + ask** — and log it as a design/plan gap (an upstream phase missed it). |

**When uncertain, treat as unrecoverable** (conservative default). Pre-announcing a recoverable-but-destructive action — state what is about to happen; do not ask permission — carries over verbatim. Any summary this phase produces is a **record of what the autonomous run did**, not a stop-and-wait barrier.

**Close-out autonomy.** Archiving a completed plan (`PLAN.md` → `PLAN.archive.YYYYMMDD-<slug>.md`) and the rest of close-out bookkeeping (append `progress.md`, move the ROADMAP item to Completed/SHIPPED, update staging notes) is **recoverable → autonomous** — never stop to ask approval to archive or to do close-out bookkeeping.

**Carve-outs — unchanged by this doctrine.** Worker-tree initiation stays operator-initiated (`/spawn-worker` + `/integrate-worker`); the PII pre-push hook + `pii-scrubber` invocation stay mandatory; the no-`Co-Authored-By` commit rule is untouched.
<!-- END recoverability-gate -->

## Non-negotiable constraints

1. **Preconditions** — `PLAN.md` `Status: done`, all tasks `[x]`, `/review` resolved, working tree clean, branch ahead of base. If any fails, **stop and report**.
2. **Re-run the full deterministic gate suite** — the *full* test suite (not a subset), a *production* build (not just dev-server).
3. **Set `features.json` `passes: true` only on verified features** — one feature, one verified test exercise, one clean review, then `true`. Never speculative.
4. **Dispatch the documenter** — probe with `bash "${CLAUDE_PLUGIN_ROOT}/scripts/capability_probe.py" wiki-maintenance`; on **exit 0** dispatch the `documenter` with the full plan-to-HEAD diff for a wiki sweep: flip any missed `pending → implemented`, add ADRs for non-obvious decisions, update `Home.md` / `_Sidebar.md`, append to the completed-features log (**block the release** on unresolved `OPEN QUESTIONS` — shipping stale docs poisons the wiki); on **exit 1** (no `wiki-maintenance`, or no `CLAUDE_PLUGIN_ROOT`) skip the sweep silently.
5. **Push / merge / tag / release run under the recoverability gate.** They are recoverable (a pushed branch resets, a tag/release deletes, a merge reverts) → announce and proceed; do **not** wait for per-action confirmation. Only a genuinely *unrecoverable* action (force-push rewriting published shared history, published-tag overwrite, an immutable deploy/migration) stops and pre-announces. Honor wake-on-CI (constraint 6): push, wait for green, *then* tag — that is a correctness gate, not a confirmation wait.
6. **If CI is red, stop.** Do not release past failing checks.
7. **Sync the release to the GitHub Project board** (optional, graceful-skip) — when `github-projects` is installed (capability probe) + `.harness/project.json` present + `gh` authed, emit the **Plan + Feature closeout** for what shipped: update each completed Plan's and its parent Feature's closeout fields in `board-items.json`, then render+write via the github-projects plugin's `project_sync.py post --config <project.json> --id <id>` (full re-render — closeout is template-driven, not a `--type` flag stage). Optionally capture a *recurring* next-release theme (not a single deferral) as a board-backed `Backlog-item`/`Idea` in `board-items.json` (**never** raw `gh project item-create` — an unbacked board issue is an orphan the `vault==board` gate flags as drift). Deterministic + idempotent → announce + proceed (preview with `--dry-run`). Silent-skip (zero behavior change) if the plugin, `project.json`, or `gh` is absent.

## Process

1. **Check preconditions** (constraint 1). Any miss → stop and report what's outstanding.
2. **Re-run the full gate suite** (constraint 2). Capture results.
3. **Verify CI** if the repo has it — green across the matrix before proceeding (constraint 6). Honor **wake-on-CI**: push the branch, wait for green, *then* tag/release — never tag ahead of a green CI run.
4. **Update `features.json`** — set `passes: true` only on features with a verified test exercise + clean review (constraint 3).
5. **Documenter wiki sweep** (constraint 4 — probe `wiki-maintenance`, dispatch on exit 0).
6. **Prepare release artifacts** — changelog entry + version bump per the project's convention. If a release skill is installed (e.g. crickets `ship-release`), use it; otherwise run the steps manually. Push / tag / release execute under the recoverability gate (announce + proceed; wake-on-CI before the tag).
7. **Execute + record.** Run the release through to completion (push → wake-on-CI green → tag → `gh release` / `gh pr merge`), pre-announcing each recoverable-destructive step. Then produce the summary as a **record** of what the run did — the commands executed and their results — not a stop-and-wait barrier. Stop only for a genuinely unrecoverable action or an unresolved decision (constraint 5 + the recoverability gate).
8. **Sync the board** (constraint 7, graceful-skip). After the release lands, probe `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/capability_probe.py" github-projects`; on **exit 0** with `.harness/project.json` + `gh` present, emit the Plan + Feature closeout via the github-projects plugin's `project_sync.py post` (deterministic + idempotent → announce + proceed). On **exit 1** (plugin absent, or no `CLAUDE_PLUGIN_ROOT`) / no `project.json` / no `gh`, skip silently — zero behavior change.

## Failure modes to avoid

- Releasing with the plan not `done` or `/review` unresolved.
- Running a test subset instead of the full suite.
- Setting `passes: true` speculatively.
- Stopping to ask before a *recoverable* push / tag / merge (the recoverability gate says announce + proceed) — or, conversely, proceeding on a genuinely *unrecoverable* action without pre-announcing and confirming.
- Releasing past a red CI.
