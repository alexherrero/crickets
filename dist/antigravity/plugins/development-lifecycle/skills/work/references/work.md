**Usage:** `/work ['optional — "--name <plan-name>" to target a named plan or task', 'and/or "step N" (or "task N") to pick a specific step']`

You are running the **work** phase of the developer-workflows loop. Work through `.harness/PLAN.md`'s steps **autonomously** — one step at a time, in sequence, assuming the full list — and keep the plan's tracker current as you go. Before each step, run a safety pre-check; **stop and ask the operator only when a step fails it or an important clarification is needed.** Otherwise run to the end of the plan, gates green before each `[x]`.

**Argument (if any):** <what the user typed after /work>

> **Recommended model for this phase:** `opusplan` — Opus 5.5 plans, Sonnet 5.5 executes the long autonomous stretch. Override with `/model` if needed.

> The session works the **whole step list autonomously** — the unit is the plan, not a single step. What keeps that safe is the **per-step safety pre-check**: before each step, decide whether it can be done safely and autonomously, and stop to ask if it can't (or if a clarification is needed). Single-threaded execution is the load-bearing constraint — never fan out parallel implementers; the autonomy boundary is the safety check, not the step count.

## Recoverability gate

Invoking this phase **authorizes** finishing it. The stop-gate is **recoverability, not destructiveness or blast-radius**: recoverable actions (push, tag, release, PR merge, close-out) are **announced and proceed**; unrecoverable ones (force-push over published shared history, sole-ref delete of unmerged work, published-tag overwrite, immutable deploy or migration) **stop and confirm**; an unresolved decision stops and asks. When uncertain, treat as unrecoverable. Unchanged: worktree spawns need operator authority, the PII hook and `pii-scrubber` stay mandatory, the no-`Co-Authored-By` rule holds. Full doctrine: the `recoverability` skill.

## Non-negotiable constraints

1. **Assume the full step list; safety-gate each step.** Work the plan's steps autonomously, in sequence — no per-step approval. Before each step, run a safety pre-check; **stop and ask only when a step fails it (genuinely-unrecoverable / ambiguous / scope-drifting / unverifiable — per the recoverability gate above) or needs a clarification** — otherwise continue to the end of the plan. Single-threaded always; never fan out parallel implementers.
2. **Gates must be green before the step is marked `[x]`.** No "I'll fix this next session" on failed gates.
3. **Never edit or delete a failing test to make it pass.** If a test is wrong, surface it and stop.
4. **Feed full error output back** on gate failures — do not summarize. The exact error is the signal.
5. **The escalation tripwire fires at 3 consecutive failures on the same gate for the same step** (`escalation_tripwire.py`, step 6): no session reaches a 4th attempt on an unresolved gate. Only the handoff pack needs the `tokens` plugin; the stop does not.
6. **Do not silently expand step scope.** If it turns out bigger than planned, stop and ask.
7. **Docs are not part of the loop.** Edit `wiki/` only when the step's **What** names the page.
8. **Docs are an opt-in pass, later:** run `wiki-author` when a page should change; a repo that keeps a wiki can let `wiki-watch` catch up on a schedule.
9. **End by updating the resolved `PLAN.md` (mark `[x]`), the plan's tracker (`plan_tracker.py step`, or `close` after the last step), the resolved `progress.md` (append line), and committing.**
10. **The board is not part of the loop.** `/work` posts nothing to a project board: a project that keeps one runs the `report-board-drift` cycle (on a loop or cron) to see what the board is missing, and `planner-maintain` to fix it. An out-of-scope finding (an adjacent bug, a refactor, a stale doc elsewhere) goes into `progress.md` as a `FOLLOW-UP:` line.
11. **Do not create tags.** Tag creation is reserved for `/release` — the sole tag writer that tags `main` HEAD after CI-green. Creating a tag during `/work` would point to a branch tip, not a main commit, violating the tag-reachability guarantee and the concurrent-release serialization model.
12. **Fire agentm's post-work reflection after each commit** (step 9.6, graceful-skip). Always exit 0 by contract — nothing to react to, but the call itself must not be skipped; it's the only session-completion reflect on a host with no Stop hook.

## Process

### 1. Read state

**Resolve the active plan first.** A `/work` invocation may target a named plan or task with **`--name <slug>`** anywhere in `<what the user typed after /work>`; the `task N` selector keeps its meaning, and `step N` is the same selector, so `/work --name <slug> step N` carries both. Absent `--name`, the worktree's `.harness/active-plan` marker binds the plan, else agentm answers a bare call. Resolve the on-disk paths by **consuming** the agentm reader — never re-deriving the paths here (pass the `--name` value as `<slug>`; omit it for a bare call):

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" [<slug>]
```

It emits one tab-separated line of three fields, `<plan_path>\t<progress_path>\t<tracker_path>` — the **resolved paths** every later step reads and writes. The tracker field is empty when agentm names no tracker; the tracker calls below then answer exit 3, and the plan carries on without one, its progress log the record. A bare call exits **0** only in a repo with no vault, where agentm answers its repo-local singleton (`.harness/PLAN.md`, `progress.md`, `tracker.md`). **Exit 1** means no agentm: stop and say so — development-lifecycle keeps its plans through agentm. **Exit 4** means the project keeps its plans in numbered tasks and has no singleton: stop and ask which task, listing the project's queued and active tasks from `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agentm_bridge.py" plans --project-root <root>` (one `<plan>\t<progress>\t<tracker>` row per plan; `plan_tracker.py status` gives each row's status), then continue as `--name <that task>`. Any other **non-zero exit is a hard stop** — surface its stderr and stop; never fall back to the singleton on a dangling binding (that would silently bind the worker to the wrong plan). If `CLAUDE_PLUGIN_ROOT` is unset the resolver can't be found: stop and say so.

Then read the **resolved `PLAN.md`** (find the first unchecked `[ ]` step, or honor the `step N` / `task N` selector); the **resolved `progress.md`** (was a prior session interrupted — resume or restart?); `AGENTS.md` / `CLAUDE.md` (commit style, test runner, conventions).

**Duplicate guard (run before anything else).** After reading PLAN.md, check two conditions and stop on either:

1. **Status** — run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/plan_tracker.py" status --plan <plan> --tracker <tracker>`. It prints `<status>\t<source>`: the tracker's status, else `none` — a plan carries no Status line, and none is read.
   - **`done`** — check `progress.md` for a final completion line, in either spelling: `completed step N`, or the older `completed task N`. If found, stop immediately: *"DUPLICATE GUARD: the plan is done and close-out is complete — it was completed by another session. If the previous output is wrong, reset its tracker and re-invoke."* If no completion line exists in `progress.md`, treat it as an interrupted close-out: proceed with a warning *"The plan is done but close-out appears incomplete — resuming close-out steps only (no re-implementation)."* and jump directly to step 7 (the plan, its tracker and `progress.md`) then steps 9–12.
   - **`dropped`** — stop: *"DUPLICATE GUARD: the plan was dropped; its Outcome says why."*
   - Anything else passes.
2. **Live-worker branch (named plans only)** — if a plan slug is available (from `--name` or the worktree-local `.harness/active-plan` marker), run `git ls-remote --heads origin "worker/<slug>"`. If it returns a non-empty line, stop: *"DUPLICATE GUARD: branch `worker/<slug>` already exists on origin — another worker session is likely active on this plan. If that session was interrupted, run `git push origin --delete worker/<slug>` then re-invoke."*

Both checks are read-only. A clean plan (not done, no live branch) passes both silently.

### 1.5. Bind this session to the plan's worktree (spawn on the first run, re-enter on resume)

**Pick the branch first.** If no step in the resolved `PLAN.md` is `[x]` yet, this is the plan's **first run** — take *Auto-spawn* below. If any step is already `[x]`, the plan is **resuming** — skip the spawn entirely and take *Re-enter* instead. Either way, the plan pair resolved in step 1 stays authoritative: those are absolute paths, and entering a worktree neither re-resolves them nor moves them.

#### Auto-spawn (first run)

Run the isolation check — **operator authority required**: this step fires only when the operator enabled `isolation.mode: worktree-per-plan` in `.harness/project.json` (a durable config opt-in), or passed `--isolate` explicitly. It never runs silently without that authority.

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/isolation_config.py" check [--no-isolate if <what the user typed after /work> contains --no-isolate] [--project-root <root>]
```

- **Exit 0** (should auto-spawn): call the **host's own worktree primitive** — Claude Code: `EnterWorktree` with `name` set to the plan's slug; Antigravity: New-Worktree-Mode / `invoke_subagent` (best-effort, per Antigravity-Limitations). Do not invent a worktree path or branch name — read back whatever the primitive actually returns (Claude Code: `.claude/worktrees/<name>` on branch `worktree-<name>`, not the retired `<repo>.worktrees/<slug>` / `worker/<slug>` convention). Then bind it: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/worktree_marker.py" write <worktree-path> <slug> <plan-path> --project-root <original-root>` (the `<plan-path>` is the resolved path from step 1 — never re-resolved here). Here, and wherever this step and step 12 say `<slug>`, pass the plan's name as agentm placed it: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/plan_tracker.py" name --plan <plan-path>` prints a task's directory name (`042-build-the-brief`) or a flat plan's slug, and that is what the marker carries, not the `--name` text the operator typed.
  - **Exit 0**: **announce the spawn** ("Auto-spawning worktree at `<path>` — operator config-gated"), then proceed from inside the new worktree for all subsequent steps. The bind writes three things: the worktree-local `.harness/active-plan` marker, the worktree-local `.harness/project.json` copy, and — in the **original root**, not the worktree — `.harness/worktree-for-<slug>`, the pointer the *Re-enter* branch below reads on every later session. A `WARNING:` line on stderr about that pointer is not a failure: the worktree is bound and usable, and only the resume convenience is lost.
  - **Exit 3** (LC-6 already-shipped no-op): the plan shipped before this session got here — exit the worktree (`ExitWorktree` `remove`, or the Antigravity equivalent; nothing was written to it) and report the `already shipped` message. Stop; do not proceed to step 2.
  - **Exit 2**: surface stderr, exit/remove the now-orphaned worktree, and stop. Do not retry.
- **Exit 1** (no auto-spawn): proceed directly — no worktree needed (mode is `direct`, no config, or single-owner guard fired because we're already inside a worktree).

**Note:** `--no-isolate` in `<what the user typed after /work>` is the command-arg override that wins over any config setting.

**`worktree-per-task` mode does NOT trigger a per-plan auto-spawn here.** When `isolation.mode` is `worktree-per-task`, this check returns exit 1 (no plan-level worktree). Per-task worktrees are spawned mid-loop in step 2.5, one per operator-declared-isolated step.

#### Re-enter (resume)

A plan that spawned a worktree on its first run recorded it in the **original root** at `.harness/worktree-for-<slug>`. Without reading that back, a session opened at the repo root just runs in the main clone — the plan's own worktree sits there untouched, and every resumed multi-session plan needs a hand-written "enter the worktree at `<path>` first" sentence in its opening prompt. Read the pointer instead:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/worktree_marker.py" read <slug> --project-root <root>
```

- **Exit 0**: stdout is the worktree's path. Announce (*"Re-entering this plan's worktree at `<path>`"*), then call the host's own primitive against that **existing** path — Claude Code: `EnterWorktree` with `path` set to it (it accepts an already-existing worktree; do **not** pass `name`, which would ask for a new one); Antigravity: New-Worktree-Mode / `invoke_subagent`, best-effort per Antigravity-Limitations. Proceed from inside for every subsequent step.
- **Exit 1**: nothing to re-enter — print the note and **proceed in the current directory**. One code covers all five non-blocking cases, and stderr says which: singleton plan, no pointer recorded, a **stale** pointer (the worktree was removed by hand, is no longer registered, can't be verified, or now carries a different plan's marker), or this session is already inside the right worktree. A stale pointer degrades with a visible note; it never blocks the plan.
- **Exit 2**: a malformed slug. Surface stderr and still proceed in the current directory — re-entry is best-effort and is never a reason to stop a plan.

**This is a re-entry, not a spawn.** Nothing here creates a worktree: the pointer is only ever followed to a directory `git worktree list` already claims, and the authority that permitted the original spawn (durable `isolation.mode: worktree-per-plan`, or an explicit operator instruction) is what put the pointer there. Skip the read for a bare (singleton) `/work` — the pointer is per-slug, and a singleton plan never has one.

### 1.6. Mark the start in the tracker

Once step 1.5 has bound the session, on a first run or a resume, name the step about to run:

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/plan_tracker.py" step --plan <plan> --tracker <tracker> --state "<what is true now, and which step starts>" --next "Step N: <title>"`

It opens a tracker the plan doesn't have yet (a plan written before trackers, or a plan staged by `stage_plan.py`), moves a `queued` or `parked` one to `active`, and rewrites an `active` one in place. It never writes the plan file. **Exit 3** — announce the reason and carry on without a tracker, logging the step to progress. **Exit 1** — a hard stop: surface stderr.

### 2. Safety pre-check (before each step)

The session assumes the **full step list** — it does not ask permission per step. Before starting each step, run a go/no-go safety pre-check: **proceed autonomously if the step is safe; stop and ask only when it isn't, or when an important clarification is needed.** Triggers to stop — the step performs a genuinely **unrecoverable** action (per the recoverability gate above: recoverable actions proceed announced; only force-push rewriting published shared history, sole-ref delete of unmerged work, published-tag overwrite, or an immutable deploy/migration stops); needs a decision that isn't locked (an **unresolved decision** — stop, ask, and log it as a design/plan gap); turns out bigger or different than the plan said (scope drift); has a verification that can't be made executable or an unmet prerequisite; or surfaces a failing test that invalidates its premise. Before you stop, record it: `plan_tracker.py step` with `--state` naming the trigger and `--next` naming what the run is waiting on (exit 3 is announced and ignored). Then state the trigger plainly and wait — even mid-plan. For a `medium` or `large` step the pre-check includes the **direction check** (step 4's loop, below): a real finding there that says the approach is wrong is a stop trigger like the rest; a real finding that is only a detail inside an approach that stands is corrected and rechecked without a stop (`/build-it` step 3 tells the two apart). Otherwise proceed to step 3.

### Common Rationalizations

| Excuse | Why it's wrong |
|---|---|
| "This step is small enough to skip the pre-check" | The pre-check exists precisely for steps you're confident about — confidence is when blind spots hide. |
| "I'll run verification after the whole plan is done" | Verification gates are per-step; batch verification misses regressions introduced mid-plan. |
| "The test is wrong, not the code" | First reproduce the test's intent independently; delete only if the intent is wrong, never because it makes the code fail. |

### 2.5. Per-task isolation check (worktree-per-task mode only)

**Only when** `isolation.mode` is `worktree-per-task` AND the safety pre-check passed. Skip for all other modes.

Read the isolation mode:
```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/isolation_config.py" read [--project-root <root>]
```

If `mode` is `worktree-per-task`, run the isolation check before starting this step:
```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/task_isolation.py" check <plan_path> <task_num>
```

- **Exit 0** (the step is isolated): spawn a per-task worktree for this step via the host's own primitive — `EnterWorktree` with `name` set to `<plan-slug>-task-<N>` (Antigravity: New-Worktree-Mode / `invoke_subagent`, best-effort) — then bind it with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/worktree_marker.py" write <worktree-path> <plan-slug> <plan-path> --project-root <original-root> --no-root-pointer` (the marker binds to the *plan* slug, not the task-scoped worktree name — a per-task worktree still resolves the same plan). `--no-root-pointer` is required here: this worktree is merged back and pruned before the task ends, so recording it as the plan's worktree would point step 1.5's resume branch at something that no longer exists. Announce: *"Spawning per-task worktree for step N — operator-declared isolated (N× CI cost)."* Proceed with steps 3–9 from inside that worktree. After step 9 (commit): merge the task branch back with `git merge --no-ff <task-branch>` (the branch name the primitive returned) from the plan's main context, then prune with `ExitWorktree` `remove` (or the Antigravity equivalent). Resume the step loop in the plan's main context.
- **Exit 1** (the step is not isolated): proceed directly in the current context — no worktree spawned.
- **Exit 2** or any error from `task_isolation.py`: surface stderr and stop.

**Cost note:** per-task worktrees multiply CI minutes by the number of isolated steps (N× CI). This is the documented tradeoff — execution isolation + rollback granularity vs. pipeline minutes. The per-task override rate is the re-audit trigger: if it stays near zero, the feature isn't earning its cost.

**Knob separation:** per-task execution isolation is independent of merge granularity. Per-task worktrees merge back into the plan's main branch; the plan-level `integration` setting (step 12) still controls whether the finished plan lands as one PR or a direct push. Running steps in separate worktrees does not force per-step PRs.

### 3. Gather context (optional)

If the step touches unfamiliar code, dispatch the `explorer` sub-agent on model `sonnet` for read-only fan-out ("Where is X handled? What tests exist for Y? Return file:line references."). Fan out only for multiple independent questions — for one question, just read.

### 4. Implement

- **Run the step's loop.** Read the step's `**Anchor:**`, `**Profile:**` and `**Size:**`. `build` follows `/build-it --spec <Anchor> --size <Size>`; `create` follows `/create-it` the same way; `both` runs each for its own files. Do not copy them here: their steps are the loop. The direction check comes first, before any code (a `small` step has none). Making is this step's work, the loop's free checks are step 5's gates (run them once), and its review passes run once those are green. A step with none of the three tags is a legacy step: `build`, `medium`, anchored to the plan.
- Write code that satisfies the step's **What**. Write the tests that satisfy its **Verification** in the **same session** — tests-after is an anti-pattern; verification lands with the implementation.
- Follow project conventions (formatters, naming, layout). If the step implies a deviation, flag it and ask.
- **Leave `wiki/` alone** unless the step's **What** names the page (constraint 7).
- If mid-implementation the step turns out bigger than planned, **stop**: *"Step N is bigger than planned because [reason]. Options: (a) finish narrow, (b) expand + re-plan, (c) split. Your call."* Then wait.

### 5. Run deterministic gates

Run in order, short-circuit on failure: **typecheck → lint → tests → build** (build only if the step affects build output). Commands come from `.harness/init.sh` / package scripts / Makefile. If a gate isn't configured, note it and skip — don't invent one.

**Evidence-tracking + operator-control hooks (graceful-skip).** If a safety/review plugin (e.g. crickets `developer-safety` / `code-review`) is installed, its hooks engage automatically — a default-FAIL evidence contract before a `[ ]`→`[x]` flip, plus `kill-switch` / `steer` / `commit-on-stop`. Absent those plugins, `/work` runs exactly as written here with no behavior change.

### 6. Iterate on failures

Feed the **full error output** into the next pass (don't summarize). If a test is itself wrong, **stop** — do not edit or delete it to go green; surface the defect and ask.

**Escalation tripwire.** Track consecutive failures on this step's current gate with `escalation_tripwire.py`'s `FailureCounter` (reset on a green pass, `record_failure()` on each red one). After each failure, call `check_and_maybe_fire()` — on the 3rd consecutive failure it writes a `/handoff`-shaped escalation entry (packed context + a tier-labeled prompt, same machine-readable label format that command emits) to a vault escalation directory and returns a loud `ESCALATION:` announcement. Print it and **stop the session** — never attempt a 4th pass, and never change the session's own model to try to push through (the tripwire hands off; it does not self-escalate).

### 7. Update state

Once all gates are green: edit the **resolved `PLAN.md`** to mark the step `[x]`. Then bring the tracker up to date — the tracker is the plan's only status, and the plan carries no Status line to edit:

- **After any step but the last:** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/plan_tracker.py" step --plan <plan> --tracker <tracker> --state "<what is now true, in three to eight lines>" --next "Step N+1: <title>"`.
- **After the last step:** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/plan_tracker.py" close --plan <plan> --tracker <tracker> --outcome "<the close-out recap>"`.

**Exit 3** — announce the reason and carry on with no tracker and no Status line: the progress append below is the record, and the next `/work` opens a tracker at its first step. **Exit 1** — a hard stop: surface stderr and stop.

Append to the **resolved `progress.md`** (the resolver's second field — the task's own `progress.md`, or the repo-local log in a repo with no vault):

```
<YYYY-MM-DD HH:MM> /work — completed step N: "<title>" (<filesChanged> files, <testsAdded> tests)
```

When the step ran a loop at `medium` or `large`, paste its done-report (`loop_record.py report`) under that line, so the next session sees what was checked and what was not.

### 8. Docs

Nothing happens here (constraint 8).

### 9. Commit

One step, one commit, referencing the step. Follow project trailer conventions (check recent `git log`). **Do not add a `Co-Authored-By:` trailer** — the user is the sole author of intent, the agent is the tool. Don't use `--no-verify`; let pre-commit hooks run.

### 9.5. Reset evidence-tracker state (graceful-skip)

If `code-review`'s evidence-tracker is installed (`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sibling_plugin.py" code-review hooks/evidence-tracker/evidence_tracker.py` exits 0 and prints its path — check by path, no dedicated capability is declared for this), reset its per-session read state now that this task boundary is closed: `python3 "$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sibling_plugin.py" code-review hooks/evidence-tracker/evidence_tracker.py)" --mode reset`. This clears the read-before-flip state so the **next** step's evidence requirement is never silently satisfied by reads recorded for the step that just finished (cricketsPluginsA#3's reset gap). Silent no-op if the resolver exits 1 (code-review not installed) or `CLAUDE_PLUGIN_ROOT` is unset.

### 9.6. Fire post-work reflection (graceful-skip)

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agentm_bridge.py" phase-dispatch post-work --project-root <root>`. Fires agentm's V5-5 orchestration bridge to reflect the just-finished session — dedup-guarded and cooldown-gated entirely on agentm's own side (a `.harness/session-id-*.start`/`.reflected` marker keeps this from double-reflecting against the Stop hook), so it's safe to call after every step's commit, not just once at plan-end. Always exit 0 (agentm's `phase_dispatch()` is non-blocking by contract) — nothing to branch on. On a host with no Stop hook (Antigravity), this is the only session-completion reflect; on Claude Code it's a safety-net that no-ops once the Stop hook has already reflected.

### 10. Board

Nothing happens here (constraint 10).

### 11. Loop or stop

After the commit, **loop back to step 2** for the next unchecked step — same session, same context — running the plan autonomously. Stop only when the plan is done (no `[ ]` left) or a safety pre-check fires / a clarification is needed (stop mid-plan and ask). Return a ≤5-bullet summary: steps completed this session; why it stopped (plan done / safety stop); files changed; gates (green per task, or N iterations + why); next.

### 12. Finalize the unit (when plan is done, isolation mode only)

**Only when:** the last step is now `[x]` AND step 1.5 auto-spawned a worktree (i.e. isolation mode is active). Skip entirely for direct mode (the tasks already committed on main).

Run the finalization helper — **recoverable, announce + proceed**:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/finalize_unit.py" <slug> --branch <worktree-branch> [--project-root <root>] [--title "<plan title>: plan complete — <close-out summary first line>"] [--body "<full close-out summary, the same content progress.md's close-out entry gets>"] [--no-pr if <what the user typed after /work> contains --no-pr]
```

`<worktree-branch>` is the branch step 1.5's `EnterWorktree` call actually returned — never assume `worker/<slug>` (that convention retired with `spawn_worker.py`). The helper reads `isolation.integration` from `.harness/project.json` and acts accordingly:
- **Refreshing a stale branch: rebase, never merge.** When GitHub reports a PR `BEHIND` its base (branch
  protection here requires branches be up to date before merging, so this happens routinely), refresh it
  with `gh pr update-branch --rebase` or a local `git rebase origin/main`. **Never merge `main` backwards
  into the branch.** `gh pr update-branch` defaults to that merge, and these repos squash-merge: the commit
  on `main` shares no ancestry with the branch commits it came from, so git cannot see that it already
  contains work the branch has since reverted — the back-merge re-adds it with no conflict and no signal.
  Force-pushing your own rebased branch is recoverable → announce + proceed.
- **`pull-request` (default):** PII guard → push `<worktree-branch>` → `gh pr create` with the close-out summary as its body → **arm auto-merge** (`gh pr merge --auto --squash`, immediately after PR creation). **`gh pr create` and `gh pr merge --auto` are both recoverable** (closeable / revertable) → announce + proceed. A PR that opens but fails to arm (e.g. "Allow auto-merge" isn't enabled on the repo yet — task 4's one-time setting) still counts as success; the helper surfaces the arm failure in its reason, not as a hard stop — merge it by hand and go fix the repo setting.
- **`direct-push`:** PII guard → push on current branch (no PR).
- **`gh` unavailable / unauthenticated / no remote:** fall back to direct push + announce the downgrade. A completed unit of work is **never hard-stopped** by a missing `gh` — the push always goes through.

After the helper returns, drop the plan's root-side worktree pointer — the plan is finished, so no later session should be re-entered into a worktree whose PR is about to retire it:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/worktree_marker.py" clear <slug> --project-root <root>
```

Idempotent and local (`.harness/` is gitignored) → recoverable, announce + proceed; a non-zero exit here is informational, never a hard stop. Then `ExitWorktree` `keep` (never `remove` — the branch has an open PR against it; the shepherd in task 5 or the PR's own merge is what eventually cleans it up).

Announce what's about to happen before running. A non-zero exit from the helper is a hard stop — surface the full error output.

## Failure modes to avoid

- **Pushing past a failed safety pre-check.** Being in an approved run isn't a license — if a step performs a genuinely *unrecoverable* action, is ambiguous, is scope-drifting, or needs a clarification, stop and ask, even mid-plan. (A recoverable-but-destructive action is not a stop trigger — announce it and proceed.)
- **Editing tests to make them pass.** Banned — if a test is wrong, say so and stop.
- **Skipping failed gates** ("I'll fix it next session"). Green before `[x]`.
- **Silently expanding scope.** Surface it; don't quietly do more than the plan says.
- **Summarizing errors** instead of passing them through on failure.
- **Committing without running gates.** Gates first, commit second.
- **Forgetting `PLAN.md` + `progress.md`.** The next session is blind without them.
