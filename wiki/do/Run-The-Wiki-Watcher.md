<!-- Status: implemented — wiki-watcher (W1). Plan: .harness/PLAN.md (The wiki-watcher (W1) — wiki-maintenance part 4/5), tasks 1–4. Engine ships end-to-end: config resolvers (task 1), significance pre-filter (task 2), dispatch plumbing (task 3), and the single-cycle driver `wiki_watch_cycle.py` (task 4). `## Steps` filled from those diffs. -->

# How to run the wiki-watcher (W1)

> [!NOTE]
> **Status:** implemented — the `wiki-watch` engine runs end-to-end as of `wiki-maintenance` part 4. Scheduling is Claude-first (DC-W4): the engine is cross-host, but the loop wiring ships for Claude Code; on Antigravity run the skill manually (step 6).
> **Goal:** Run the `wiki-watch` single-cycle engine over a watched repo, and drive it on a loop so the `documenter` keeps a wiki in sync — PR-default, with direct-commit opt-in per trusted repo.
> **Prereqs:** the `wiki-maintenance` plugin installed ([Install crickets plugins](Install-Into-Project)); the watched repo registered in `repo_registry` (`<vault>/_meta/repos.json`) with a `wiki_path`; `git` and (for PR-default dispatch) the `gh` CLI authenticated. Optional: a configured durable-memory vault for cross-device cursors and audit log — without one, state falls back to the per-repo `.harness/wiki-watch/`.

The wiki-watcher is an **idempotent single-cycle engine the operator drives**, not a daemon: one invocation runs one `poll → detect → significance → dispatch → audit` cycle and exits. It is cooldown-gated and cursor-backed, so re-running it on the host's loop (`/loop` or cron) never drops a change or double-dispatches. Dispatch is **PR-default** (a human merges); direct-commit is opt-in per trusted repo — see step 5.

## Steps

1. **Enable the watcher for this host** (opt-in). In `<install-prefix>/.agentm-config.json` (default `~/.claude`) set `{"wiki_watch": {"enabled": true}}`. Absent / malformed / falsey leaves the watcher off. See [Wiki-watch config](Wiki-Watch-Config) § Enablement for the alias shape and resolver subcommand.

2. **Write the per-repo run-config marker** at `<repo>/.harness/wiki-watch.json` — its *presence* is the per-repo opt-in. Set `watch_sources` (which paths to watch) and `dispatch_mode` (`"pr"` or `"direct"`). See [Wiki-watch config](Wiki-Watch-Config) § Run config for the field shapes, defaults, and parsing fallbacks.

3. **Register the watched repo in `repo_registry`** (`<vault>/_meta/repos.json`) with a `wiki_path` so the engine can resolve which wiki to write. Confirm resolution: `python3 scripts/wiki_watch_config.py wiki-target <repo-root> [--slug X]` prints the resolved `wiki_target` (exit `0`) or a `{"skipped": ...}` reason (exit `1`). See [Wiki-watch config](Wiki-Watch-Config) § Wiki target for the fallback rules.

4. **Run one cycle.** On Claude Code use the slash entry `/wiki-watch` (or `/wiki-watch --repo <name>`); the underlying engine is `python3 scripts/wiki_watch_cycle.py run --repo <repo-root> [--slug X] [--no-cooldown]`. One invocation runs one `poll → detect → significance → dispatch → audit` cycle and prints a JSON `CycleReport`, then exits. The cycle:
   - resolves the two opt-ins + wiki target, then gates on the cooldown window (default 15 min; `--no-cooldown` forces a manual run) — within-window re-runs return `{"skipped": true, "reason": "within cooldown window"}`;
   - reads the current HEAD token, lists changed paths since the cursor, and applies the deterministic **significance floor**: doc-source (`PLAN.md`, `ROADMAP.md`, ADRs, `designs/`, any tracked `.md`) → `recommendation: dispatch`; code → `judge` (deferred to the agent's doc-worthiness call); tests/CI/config → `skip`;
   - records the fire, writes the `saw` + `decided` audit records, and returns the report's `candidates`, `plan` (`pr`/`direct`/`skip` + `branch`), and `dispatch_mode`. The agent half then refines the `judge` candidates, dispatches the `documenter`, lands the result, and advances the cursor (`finalize_cycle`) — so a re-run never drops or double-dispatches a change.

5. **Review the dispatch output** per `dispatch_mode` (from the per-repo marker). The flow is always: branch → documenter authors → commit → PII guard → push → open PR / land commit.
   - **`pr` (default):** the cycle opens a pull request via `gh` on a deterministic branch — **open that PR and merge it** (a human merges; the PR is the async preview boundary).
   - **`direct` (trusted-repo opt-in):** the cycle commits straight to the wiki's default branch — inspect that commit.
   See [Wiki-watch config](Wiki-Watch-Config) § How `dispatch_mode` is acted on for the full behavior table (branch naming, the `gh`-unavailable skip, PII-guard ordering, graceful-skip).

6. **Drive it on a loop.** On Claude Code, re-invoke the cycle under the host's loop (`/loop /wiki-watch`) or a cron line that runs it headless (`*/30 * * * * cd <repo> && claude -p "/wiki-watch"`) — the cooldown and cursors make repeated invocation safe. Antigravity has no installable scheduling path for a shipped plugin today, so the loop is Claude-first; run the `wiki-watch` skill manually there. See [Antigravity limitations](Antigravity-Limitations) for the gap and its re-address trigger (the agentm V7 scheduled-sidecar).

## Related

- [Wiki-watch config](Wiki-Watch-Config) — the three config sources the engine reads (enablement, run config, wiki target); state, audit, and what's watched vs. filtered live there too.
- [Antigravity limitations](Antigravity-Limitations) — the host scheduling/trigger gap that makes W1 scheduling Claude-first.
- [Run the style-learning loop](Run-The-Style-Learning-Loop) — the sibling `wiki-maintenance` how-to (teach `wiki-author` your house voice).
- [Install crickets plugins](Install-Into-Project) — get `wiki-maintenance` onto your host.
- [Wiki-watcher (W1) design](../explanation/designs/wiki-maintenance/parts/wiki-watcher.md) — why the watch loop, PR-default dispatch, and idempotency model exist.
