---
name: wiki-watch
description: "Run the wiki-watcher (W1) — one idempotent cycle that detects doc-worthy changes in a watched repo (+ its active PLAN.md/design/ROADMAP.md), judges significance, and dispatches the documenter to author the update PR-default. Triggers when the operator says 'run the wiki watcher', 'watch the wiki', 'check for doc-worthy changes', or drives /wiki-watch on a loop (/loop or cron). One invocation = ONE cycle (NOT a daemon — DC-W3): cooldown-gated + cursor-backed so repeated runs never drop or double-dispatch. Opt-in: device toggle in .agentm-config.json + a per-repo .harness/wiki-watch.json marker. PR-default (a human merges); direct-commit opt-in per trusted repo. Graceful-skip when disabled / unconfigured / unregistered / gh unavailable. The engine is cross-host; the scheduling wiring is Claude-first (see Antigravity-Limitations)."
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

# wiki-watch — run the wiki-watcher (W1)

The continuous-mode surface of `wiki-maintenance`: instead of running the `documenter` one-shot at a phase boundary, run it on a **watch loop** so a wiki stays in sync with a repo's doc-worthy changes. Ships as **W1** — an **idempotent single-cycle engine the operator drives** (DC-W3), *not* a daemon: one invocation runs one `poll → detect → significance → dispatch → audit` cycle and exits. Cooldown-gated + cursor-backed, so re-running it on the host's loop (`/loop` or cron) never drops a change or double-dispatches.

**Position vs. the phase-boundary documenter.** `developer-workflows`' phase commands dispatch the `documenter` once, at `/work`/`/release` boundaries. `wiki-watch` dispatches the *same* `documenter` (reused as-is — never a second writer) repeatedly, off a change feed, between boundaries. Same write-executor; different trigger.

## Opt-in (two gates) + safety

The watcher dispatches autonomously, so it stays **off** until two opt-ins line up (see [Wiki-Watch-Config](../../../wiki/reference/Wiki-Watch-Config.md)):

1. **Device** — `wiki_watch.enabled: true` (or `wiki_watch_enabled: true`) in `<install-prefix>/.agentm-config.json`.
2. **Per-repo** — a `<repo>/.harness/wiki-watch.json` marker (its presence is the opt-in) carrying `watch_sources` + `dispatch_mode` (`pr` default | `direct`).

**PR is the default autonomous boundary (DC-W1):** the PR *is* the async preview that reconciles the documenter's own preview-before-write gate with autonomous mode — a human merges. `direct` commits straight to the default branch and is an explicit per-repo opt-in for a trusted repo only. The significance gate, the audit log, and PR-as-preview bound the blast radius. **Public-repo PII guardrails gate every push** (the pre-push hook is the hard enforcer; the engine also runs a PII pre-check before any push). The audit log is **local, never committed**.

## Running one cycle

The deterministic engine is `scripts/wiki_watch_cycle.py`. Run it, then act on its report:

```bash
python3 scripts/wiki_watch_cycle.py run --repo <repo-root> [--slug <slug>] [--no-cooldown]
```

It prints a JSON `CycleReport`. The skill then:

1. **Read the report.** If `skipped: true` (disabled / unconfigured / cooldown / unregistered / no commits), stop — clean no-op. Otherwise it carries `token`, `wiki_target`, `dispatch_mode`, the `plan` (`pr`/`direct`/`skip` + `branch`), and `candidates` — each with a deterministic `classification` (`doc-source`/`code`/`minor`) and `recommendation`.
2. **Judge significance (the agent step).** The recommendation is the deterministic floor — **start conservative**:
   - `dispatch` (doc-source): doc-worthy by default — include it.
   - `skip` (minor — tests/CI/config): drop it.
   - `judge` (code): **you decide** — read the changed file's diff and ask "does this change what a *reader of the wiki* needs to know?" (new/changed public API, behavior, architecture → yes; refactor/rename/internal → no). Promote to dispatch only when genuinely doc-worthy. Bias toward fewer, higher-quality updates.
   If nothing survives the judgment, advance the cursor (`finalize_cycle`) and stop — the changes were seen, just not doc-worthy.
3. **Plan the landing.** If `plan.action == "skip"` (PR-default but `gh` unavailable), report it and stop — do **not** fall back to direct-commit. For `pr`: `prepare_branch` (creates `plan.branch`). For `direct`: stay on the current branch.
4. **Dispatch the documenter (reuse).** Spawn the `documenter` sub-agent with the context from `build_documenter_context(...)` (its familiar `/work`-style task+diff contract): the changed sources + the wiki target. It authors/updates only the affected pages, in the operator's voice, Diátaxis single-mode, keeping `check-wiki.py --strict` green. **Never** author wiki content yourself — the documenter is the write-executor.
5. **Land + audit.** Run `finalize_pr` (commit → **PII guard → push → `gh pr create`**) or `finalize_direct` (commit → **PII guard → push**). On success, call `mark_and_audit_dispatch(...)` per candidate (records the dispatch + PR/commit link, prevents re-dispatch on the next cycle); on failure, `record_dispatch_failure(...)` (retry/backoff). When every candidate for this `token` is handled, `finalize_cycle(...)` advances the cursor.

Re-invoking is always safe: the cursor + dispatched-set make a re-run a no-op for already-handled changes (idempotent), and the cooldown gate no-ops a too-soon re-run.

## Scheduling (honest: Claude-first — DC-W4)

`wiki-watch` is a **single-cycle engine**; *you* drive the loop. There is no cross-host plugin scheduler — so the engine ships cross-host but the **scheduling wiring is Claude-first**:

- **Claude Code** — drive it with `/loop` (interactive) or a cron line invoking the `/wiki-watch` command headless (e.g. `claude -p "/wiki-watch"`). The cooldown gate (`--cooldown`, default 15 min) keeps a tight loop from over-firing.
- **Antigravity** — there is **no installable trigger path** for a shipped plugin (native `every()`/`on_file_change()` only; no SessionStart hook). Run `/wiki-watch` manually; true scheduling is deferred to the agentm **V7 scheduled-sidecar**. This gap is tracked in the growing [Antigravity-Limitations](../../../wiki/reference/Antigravity-Limitations.md) register — revisit when the host ships a trigger surface.

The hands-off idle-chain hook (auto-fire on SessionStart) and always-on (W3) are deferred follow-ons; both would just call this same single-cycle engine.

## Graceful-skip (clean no-ops, never hard-fail)

- Device toggle off / no per-repo marker → skip with a reason.
- Repo unregistered in `repo_registry` or no `wiki_path` (and no `<root>/wiki`) → skip.
- Within the cooldown window → skip.
- Not a git repo / no commits → skip.
- `gh` unavailable in PR-default mode → skip (never silently direct-commits).
- agentm kernel unreachable (no `repo_registry.py` / `harness_memory.py`) → state falls back to repo-local `<repo>/.harness/wiki-watch/`; an unresolved wiki target skips the repo.

## Companion surfaces

- `documenter` sub-agent — the write-executor `wiki-watch` dispatches (reused as-is; `wiki/**`-scoped).
- `/wiki-watch` command — the thin slash entry for `/loop`/cron (Claude Code).
- [Run the wiki-watcher](../../../wiki/how-to/Run-The-Wiki-Watcher.md) — the operator how-to.
- `recent-wiki-changes` — the read-only "what changed in my wikis" view (this skill is the write loop).
