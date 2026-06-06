<!-- Status: pending — wiki-watcher (W1). Plan: .harness/PLAN.md (The wiki-watcher (W1) — wiki-maintenance part 4/5), tasks 1–4. Skeleton authored at /plan; `## Steps` to be filled from the implementation diff at /work once tasks 1–4 land and gates are green. Do not flip to implemented until the diff proves each step. -->

# How to run the wiki-watcher (W1)

> [!NOTE]
> **Status:** pending — the engine is being built across `wiki-maintenance` part 4 (tasks 1–4). The steps below are a skeleton; each is filled from the implementation diff once the matching task lands and the gate battery is green. Treat anything not yet implemented as forward-looking.
> **Goal:** Run the `wiki-watch` single-cycle engine over a watched repo, and drive it on a loop so the `documenter` keeps a wiki in sync — PR-default, with direct-commit opt-in per trusted repo.
> **Prereqs:** the `wiki-maintenance` plugin installed ([Install crickets plugins](Install-Into-Project)); the watched repo registered in `repo_registry` (`<vault>/_meta/repos.json`) with a `wiki_path`; `git` and (for PR-default dispatch) the `gh` CLI authenticated. Optional: a configured durable-memory vault for cross-device cursors and audit log — without one, state falls back to the per-repo `.harness/wiki-watch/`.

The wiki-watcher is an **idempotent single-cycle engine the operator drives**, not a daemon: one invocation runs one `poll → detect → significance → dispatch → audit` cycle and exits. It is cooldown-gated and cursor-backed, so re-running it on the host's loop (`/loop` or cron) never drops a change or double-dispatches. Dispatch is **PR-default** (a human merges); direct-commit is opt-in per trusted repo — see step 4.

## Steps

1. **Enable the watcher for this host** (opt-in). In `<install-prefix>/.agentm-config.json` (install-prefix = `$AGENTM_INSTALL_PREFIX`, default `~/.claude`) set either `{"wiki_watch": {"enabled": true}}` (canonical) or `{"wiki_watch_enabled": true}` (alias). Absent / malformed / falsey leaves the watcher off. Then confirm the watched repo resolves to a wiki target: it must be registered in `repo_registry` with a `wiki_path` (absent `wiki_path` falls back to `<root>/wiki` only if that dir exists; an unregistered repo is skipped). See [Wiki-watch config](Wiki-Watch-Config) for the exact shapes and resolver subcommands.

2. **Write the per-repo run-config marker** at `<repo>/.harness/wiki-watch.json` — its *presence* is the per-repo opt-in. Shape: `{"watch_sources": ["PLAN.md", "designs/", ...], "dispatch_mode": "pr" | "direct"}`. `watch_sources` defaults to `["."]` (whole repo); `dispatch_mode` defaults to `"pr"` and any unrecognized value falls back to `"pr"` (direct-commit is opt-in only). This marker is the on-host run config; nothing is written to the vault (honors DC-8).

3. _(Filled from task 4's diff at `/work`.)_ Run one cycle with the `wiki-watch` invocation. It polls the watched sources since the last cursor, drops noise via the deterministic pre-filter, judges doc-worthiness, dispatches the `documenter` on a candidate, and writes the audit log. The cooldown gate makes a within-window re-run a no-op. _Filled by human._

4. **Review the dispatch output.** What the cycle does with the documenter's authored changes is set by `dispatch_mode` (from the per-repo marker). The flow is always: branch → documenter authors → commit → **PII guard → push → open PR / land commit**.
   - **`pr` (default).** Pushes to a deterministic branch `wiki-watch/<repo-slug>-<short-token>` (stable, so a re-run reuses the branch — no duplicate PRs) and opens a pull request via `gh`. **Open that PR and merge it** — the PR *is* the async preview that reconciles the documenter's interactive preview-before-write gate with autonomous mode; a human merges. **`gh` is required for PR mode**: if `gh` is unavailable or unauthenticated the cycle **skips** dispatch — it does **not** downgrade to direct-commit, which would bypass the human-merge boundary.
   - **`direct` (per-repo opt-in, trusted repos only).** Commits straight to the wiki's default branch; inspect the commit. Used only for a repo explicitly marked `"dispatch_mode": "direct"`.
   - In both modes the **PII guard runs before any push** (the in-engine pre-check; the repo's pre-push hook is the hard enforcer). Every git/`gh` step graceful-skips on failure — a failed push or PR-create no-ops rather than hard-failing the cycle.

5. _(Filled from task 4's diff at `/work`.)_ Drive it on a loop. On Claude Code, run the cycle under the host's loop (`/loop`) or a cron entry that re-invokes the single-cycle engine — the cooldown and cursors make repeated invocation safe. Antigravity has no installable scheduling path today, so the loop is Claude-first; see [Antigravity limitations](Antigravity-Limitations) for the gap and its re-address trigger. _Filled by human._

## What gets watched vs. filtered as noise

Before any candidate reaches the doc-worthiness judge, a deterministic, coarse **significance pre-filter** drops obvious noise: generated/vendored/transient trees (`.git`, `__pycache__`, `node_modules`, `dist`, `build`, `target`, `.venv`, lockfiles, `*.pyc`, `*.min.js`, `.DS_Store`, …) — **and the output `wiki/` tree**, since watching the documenter's own writes would loop the watcher back onto itself. Everything else is kept (the filter is permissive by design): code, `PLAN.md`/`ROADMAP.md`, and design docs all pass through. This is only the coarse gate — the fine, doc-worthiness judgment runs later in the cycle.

## Where state and audit live

State lives under a `wiki-watch/` leaf — in the vault at `<vault>/projects/<slug>/_harness/wiki-watch/` when a vault is configured, or repo-local at `<repo>/.harness/wiki-watch/` when agentm is unreachable or no vault is available (DC-W6). Two JSON files back the idempotency guarantee:

- **`cursors.json`** — the per-source high-water mark (a git SHA for git sources, a content hash for non-git ones like a vault `PLAN.md`). A cursor only advances once its token is *fully* processed, so a change is never dropped.
- **`pending.json`** — the token currently mid-processing, the `dispatched` paths under it (so a re-run or restart never double-dispatches), and a `failures` map driving exponential retry/backoff (60s · 120s · 240s …, capped at 3600s).

The audit log is a JSONL file, `audit.log`, alongside these under `_harness/wiki-watch/`. It records each cycle's `saw → decided → dispatched` trail with PR links. It is **local and never committed** — git never touches it.

## Related

- [Wiki-watch config](Wiki-Watch-Config) — the three config sources the engine reads (enablement, run config, wiki target).
- [Antigravity limitations](Antigravity-Limitations) — the host scheduling/trigger gap that makes W1 scheduling Claude-first.
- [Run the style-learning loop](Run-The-Style-Learning-Loop) — the sibling `wiki-maintenance` how-to (teach `wiki-author` your house voice).
- [Install crickets plugins](Install-Into-Project) — get `wiki-maintenance` onto your host.
- [Wiki-watcher (W1) design](../explanation/designs/wiki-maintenance/parts/wiki-watcher.md) — why the watch loop, PR-default dispatch, and idempotency model exist.
