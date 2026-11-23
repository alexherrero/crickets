---
name: wiki-watch
description: Run one wiki-watcher (W1) cycle — detect doc-worthy changes in a watched repo, judge significance, dispatch the documenter PR-default. One invocation = one idempotent cycle (cooldown-gated, cursor-backed), so it is safe on a loop (/loop or cron). Opt-in per device and per repo; graceful-skip when disabled, unconfigured, unregistered or gh is unavailable.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.2.0
---

Run **one** wiki-watcher cycle for the current repo (or a named repo): `poll → detect → significance → dispatch → audit`, then exit. It is not a daemon; you drive the loop, and the cooldown gate and cursors make repeated runs safe. It dispatches the same `documenter` the `wiki-author` skill uses — never a second writer.

## Usage

```bash
/wiki-watch                    # one cycle for the current repo
/wiki-watch --repo crickets    # a named repo (resolved via repo_registry)
/loop /wiki-watch              # Claude Code: drive it on a loop
#   */30 * * * *  cd /path/to/repo && claude -p "/wiki-watch"   # headless cron
```

## Opt-in and safety

Off until both line up (see [Wiki-Watch-Config](../../../wiki/reference/Wiki-Watch-Config.md)):

1. **Device:** `wiki_watch.enabled: true` (or `wiki_watch_enabled: true`) in `<install-prefix>/.agentm-config.json`.
2. **Repo:** a `<repo>/.harness/wiki-watch.json` marker carrying `watch_sources` and `dispatch_mode` (`pr` default, or `direct`).

**PR is the default boundary:** the PR is the preview, and a human merges. `direct` commits to the default branch and is a per-repo opt-in for a trusted repo only. PII guardrails gate every push (the pre-push hook enforces; the engine also pre-checks). The audit log stays local.

## One cycle

```bash
python3 scripts/wiki_watch_cycle.py run --repo <repo-root> [--slug <slug>] [--no-cooldown]
```

It prints a JSON `CycleReport`. Then:

1. **Read the report.** `skipped: true` → stop (clean no-op). Otherwise it carries `token`, `wiki_target`, `dispatch_mode`, the `plan` (`pr` / `direct` / `skip`, with `branch`) and `candidates`, each with a `classification` (`doc-source` / `code` / `minor`) and `recommendation`.
2. **Judge significance.** Start conservative: `dispatch` (doc-source) → include; `skip` (tests, CI, config) → drop; `judge` (code) → read the diff and ask "does this change what a reader of the wiki needs to know?" (new or changed public API, behaviour, architecture → yes; refactor, rename, internal → no). If nothing survives, `finalize_cycle` advances the cursor and you stop.
3. **Plan the landing.** `plan.action == "skip"` (PR-default without `gh`) → report and stop; never fall back to a direct commit. `pr` → `prepare_branch`. `direct` → stay on the branch.
4. **Dispatch the documenter** with `build_documenter_context(...)`: the changed sources and the wiki target. It updates only the affected pages, single-mode, keeping `check-wiki.py --strict` green. Never write wiki content yourself.
5. **Land and audit.** `finalize_pr` (commit → PII guard → push → `gh pr create`) or `finalize_direct` (commit → PII guard → push). On success `mark_and_audit_dispatch(...)` per candidate; on failure `record_dispatch_failure(...)` (retry with backoff). When every candidate for the `token` is handled, `finalize_cycle(...)`.

## Graceful-skip

Prints a `skipped` reason and exits 1 (clean no-op) when: disabled on this device, no repo marker, inside the cooldown window, repo unregistered or no wiki target, not a git repo or no commits, `gh` unavailable in PR mode, or no desk for the project (state lives only in `<desk>/wiki-watch/`). Never hard-fails.

## Scheduling

Claude Code: `/loop` or cron, with the cooldown (`--cooldown`, default 15 min) keeping a tight loop from over-firing. Antigravity has no installable trigger for a shipped plugin, so run it by hand there; see [Antigravity-Limitations](../../../wiki/reference/Antigravity-Limitations.md).
