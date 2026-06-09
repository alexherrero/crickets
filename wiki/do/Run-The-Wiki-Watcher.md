# How to run the wiki-watcher

> [!NOTE]
> **Goal:** Run the `wiki-watch` engine over a watched repo and drive it on a loop, so the `documenter` keeps a wiki in sync — PR by default, direct-commit opt-in per trusted repo.
> **Prereqs:** the `wiki-maintenance` plugin installed ([Install crickets plugins](Install-Into-Project)); the watched repo registered in `repo_registry` (`<vault>/_meta/repos.json`) with a `wiki_path`; `git` and — for PR dispatch — an authenticated `gh`. Optional: a durable-memory vault for cross-device cursors + audit log; without one, state falls back to `<repo>/.harness/wiki-watch/`.

The wiki-watcher is an **idempotent single-cycle engine you run on a loop**, not a daemon: one invocation runs one `poll → detect → judge → dispatch` cycle and exits. It's cooldown-gated and cursor-backed, so re-running it (`/loop` or cron) never drops a change or double-dispatches. The full config contract is in [Wiki-watch config](Wiki-Watch-Config).

## Steps

1. **Enable it for this host** (opt-in). In `<install-prefix>/.agentm-config.json` (default `~/.claude`) set `{"wiki_watch": {"enabled": true}}`. Absent or falsey leaves the watcher off.

2. **Opt the repo in.** Create `<repo>/.harness/wiki-watch.json` — its *presence* is the per-repo opt-in. Set `watch_sources` (paths to watch) and `dispatch_mode` (`"pr"` or `"direct"`). Field shapes + defaults: [Wiki-watch config](Wiki-Watch-Config).

3. **Register the repo** in `repo_registry` (`<vault>/_meta/repos.json`) with a `wiki_path` so the engine knows which wiki to write, then confirm it resolves:

   ```bash
   python3 scripts/wiki_watch_config.py wiki-target <repo-root> [--slug X]
   ```

   It prints the resolved target (exit `0`) or a `{"skipped": …}` reason (exit `1`).

4. **Run one cycle.** On Claude Code, `/wiki-watch` (or `/wiki-watch --repo <name>`):

   ```bash
   python3 scripts/wiki_watch_cycle.py run --repo <repo-root> [--slug X] [--no-cooldown]
   ```

   One cycle detects changes since the cursor, judges which are doc-worthy (docs always, code maybe, tests/CI never), dispatches the `documenter`, advances the cursor, and prints a JSON report. A cooldown (default 15 min) skips within-window re-runs; `--no-cooldown` forces one.

5. **Review the output** by `dispatch_mode`. The flow is always branch → documenter authors → commit → PII guard → push:
   - **`pr` (default):** opens a pull request via `gh` — open it and merge (the PR is the human-review boundary).
   - **`direct` (opt-in):** commits straight to the wiki's default branch — inspect the commit.

   The full behavior table (branch naming, the `gh`-unavailable skip) is in [Wiki-watch config](Wiki-Watch-Config).

6. **Drive it on a loop.** Re-invoke under the host's loop — `/loop /wiki-watch`, or a cron line:

   ```bash
   */30 * * * * cd <repo> && claude -p "/wiki-watch"
   ```

   The cooldown + cursors make repeated runs safe. Antigravity has no installable scheduling path for a shipped plugin yet, so the loop is Claude-first — run the skill manually there ([Antigravity limitations](Antigravity-Limitations)).

## Related

- [Wiki-watch config](Wiki-Watch-Config) — the three config sources, state/audit, and what's watched vs. filtered.
- [Antigravity limitations](Antigravity-Limitations) — the scheduling gap that makes the loop Claude-first.
- [Run the style-learning loop](Run-The-Style-Learning-Loop) — the sibling wiki-maintenance how-to.
- [Install crickets plugins](Install-Into-Project) — get `wiki-maintenance` onto your host.
- [Wiki-watcher design](wiki-watcher) — why the watch loop, PR-default, and idempotency exist.
