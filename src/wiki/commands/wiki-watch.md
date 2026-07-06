---
name: wiki-watch
description: Run one wiki-watcher (W1) cycle — detect doc-worthy changes in a watched repo, judge significance, dispatch the documenter PR-default. The thin slash entry for driving the watcher on a loop (/loop or cron). Delegates to the wiki-watch skill; one invocation = one idempotent cycle (cooldown-gated, cursor-backed). Claude-first scheduling per DC-W4.
kind: command
supported_hosts: [claude-code]
version: 0.1.0
install_scope: project
---

Run **one** wiki-watcher cycle for the current repo (or a named repo).

This command is the thin scheduling entrypoint — the thing you put in `/loop` or a cron line. It delegates to the **`wiki-watch` skill**, which runs the single cycle `poll → detect → significance → dispatch → audit` and exits. One invocation = one idempotent cycle; the cooldown gate + cursors make repeated runs safe.

## Usage

```bash
# One cycle for the current repo:
/wiki-watch

# A named repo (resolved via repo_registry):
/wiki-watch --repo crickets

# Drive it on a loop (Claude Code) — cooldown-gated so it won't over-fire:
/loop /wiki-watch

# Headless cron (Claude-first scheduling, DC-W4):
#   */30 * * * *  cd /path/to/repo && claude -p "/wiki-watch"
```

Under the hood this runs `scripts/wiki_watch_cycle.py run --repo <root>` and then performs the agent-facing significance judgment + documenter dispatch + landing per the [`wiki-watch` skill](../skills/wiki-watch/SKILL.md).

## Opt-in + safety (summary)

Off until the device toggle (`.agentm-config.json`) **and** the per-repo `.harness/wiki-watch.json` marker both opt in. **PR-default** (a human merges); `direct` is a per-repo opt-in. PII guardrails gate every push; the audit log stays local. Full detail: [Wiki-Watch-Config](../../../wiki/reference/Wiki-Watch-Config.md).

## Graceful-skip

Prints a `skipped` reason and exits 1 (clean no-op) when: disabled on this device, no per-repo marker, within the cooldown window, repo unregistered / no wiki target, not a git repo, or `gh` unavailable in PR-default mode. Never hard-fails.

## Scheduling note (Claude-first — DC-W4)

The engine is cross-host but the scheduling wiring is Claude-first. On **Antigravity** there is no installable trigger path for a shipped plugin — run the `wiki-watch` skill manually; auto-scheduling is deferred to the agentm V7 scheduled-sidecar. Tracked in [Antigravity-Limitations](../../../wiki/reference/Antigravity-Limitations.md).
