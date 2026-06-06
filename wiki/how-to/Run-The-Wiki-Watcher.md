<!-- Status: pending — wiki-watcher (W1). Plan: .harness/PLAN.md (The wiki-watcher (W1) — wiki-maintenance part 4/5), tasks 1–4. Skeleton authored at /plan; `## Steps` to be filled from the implementation diff at /work once tasks 1–4 land and gates are green. Do not flip to implemented until the diff proves each step. -->

# How to run the wiki-watcher (W1)

> [!NOTE]
> **Status:** pending — the engine is being built across `wiki-maintenance` part 4 (tasks 1–4). The steps below are a skeleton; each is filled from the implementation diff once the matching task lands and the gate battery is green. Treat anything not yet implemented as forward-looking.
> **Goal:** Run the `wiki-watch` single-cycle engine over a watched repo, and drive it on a loop so the `documenter` keeps a wiki in sync — PR-default, with direct-commit opt-in per trusted repo.
> **Prereqs:** the `wiki-maintenance` plugin installed ([Install crickets plugins](Install-Into-Project)); the watched repo registered in `repo_registry` (`<vault>/_meta/repos.json`) with a `wiki_path`; `git` and (for PR-default dispatch) the `gh` CLI authenticated. Optional: a configured durable-memory vault for cross-device cursors and audit log — without one, state falls back to the per-repo `.harness/wiki-watch/`.

The wiki-watcher is an **idempotent single-cycle engine the operator drives**, not a daemon: one invocation runs one `poll → detect → significance → dispatch → audit` cycle and exits. It is cooldown-gated and cursor-backed, so re-running it on the host's loop (`/loop` or cron) never drops a change or double-dispatches. Dispatch is **PR-default** (a human merges); direct-commit is opt-in per trusted repo.

## Steps

1. _(Filled from task 1's diff at `/work`.)_ Enable the watcher for this host by setting the `wiki_watch_enabled` toggle in `.agentm-config.json`. Confirm the watched repo resolves to a wiki target: it must be registered in `repo_registry` with a `wiki_path` (absent `wiki_path` falls back to `<root>/wiki`; an unregistered repo is skipped). _Filled by human._

2. _(Filled from task 1's diff at `/work`.)_ Write the per-repo run-config marker under `<repo>/.harness/` — the watch sources (the repo plus the active `PLAN.md` / design / `ROADMAP.md`) and the dispatch mode (`pr` or `direct`). This marker is the on-host run config; nothing is written to the vault (honors DC-8). _Filled by human._

3. _(Filled from task 4's diff at `/work`.)_ Run one cycle with the `wiki-watch` invocation. It polls the watched sources since the last cursor, drops noise via the deterministic pre-filter, judges doc-worthiness, dispatches the `documenter` on a candidate, and writes the audit log. The cooldown gate makes a within-window re-run a no-op. _Filled by human._

4. _(Filled from task 3's diff at `/work`.)_ Review the output. In PR mode, open the pull request the engine created and merge it — the PR is the async preview that reconciles the documenter's interactive preview-before-write gate with autonomous mode. In direct mode (opt-in trusted repos only), inspect the commit. The PII guardrails (pre-push hook + `pii-scrubber`) gate anything pushed. _Filled by human._

5. _(Filled from task 4's diff at `/work`.)_ Drive it on a loop. On Claude Code, run the cycle under the host's loop (`/loop`) or a cron entry that re-invokes the single-cycle engine — the cooldown and cursors make repeated invocation safe. Antigravity has no installable scheduling path today, so the loop is Claude-first; see [Antigravity limitations](Antigravity-Limitations) for the gap and its re-address trigger. _Filled by human._

## Where state and audit live

Cursors, the processed-set, and the audit log (`saw → decided → dispatched`, with PR links) live under `_harness/wiki-watch/` — in the vault under `<vault>/projects/<slug>/_harness/wiki-watch/` when a vault is configured, or `<repo>/.harness/wiki-watch/` in local mode. The audit log is **local and never committed**.

## Related

- [Wiki-watch config](Wiki-Watch-Config) — the three config sources the engine reads (enablement, run config, wiki target).
- [Antigravity limitations](Antigravity-Limitations) — the host scheduling/trigger gap that makes W1 scheduling Claude-first.
- [Run the style-learning loop](Run-The-Style-Learning-Loop) — the sibling `wiki-maintenance` how-to (teach `wiki-author` your house voice).
- [Install crickets plugins](Install-Into-Project) — get `wiki-maintenance` onto your host.
- [Wiki-watcher (W1) design](../explanation/designs/wiki-maintenance/parts/wiki-watcher.md) — why the watch loop, PR-default dispatch, and idempotency model exist.
