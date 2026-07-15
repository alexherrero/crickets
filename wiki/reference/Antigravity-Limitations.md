<!-- Status: implemented. A growing register of Antigravity (agy) host gaps that constrain crickets primitives — four rows today (scheduling · hooks · multi-agent orchestration · scheduled-task durability). Append a row when a new agy gap blocks/degrades a crickets customization; strike + "resolved YYYY-MM-DD" when the host ships the missing surface. Compatibility summarizes these gaps and links here for the detail. -->

# Antigravity Limitations

Antigravity (`agy`) is missing a few host surfaces that crickets primitives depend on, and this register tracks each one. Every entry names the gap as it hits our primitives, the workaround we ship in the meantime, and the condition that would let us close it for good. When Antigravity ships a missing surface, the entry is struck through and kept as history. The [agy CLI plugin docs](https://antigravity.google/docs/cli-plugins) describe what the host does expose today.

## ⚡ Quick Reference

| # | Gap | Affected surface | Mitigation | Re-assess when | Status |
|---|---|---|---|---|---|
| 1 | **Scheduling / triggers** — no installable trigger path for a shipped plugin | wiki-watcher scheduling | Claude-first scheduling (`/loop` / cron); the watcher *engine* is cross-host | `agy` ships a file-based or plugin-installable scheduled-task surface | 🟡 mitigated |
| 2 | **Hooks** — no file-based hook surface (Python decorators only) | the six crickets hooks | run Claude-effective; observe-only on Antigravity ([Hooks](Hooks)) | `agy` ships a file-based / plugin-installable hook surface | 🟡 mitigated |
| 3 | **Multi-agent orchestration** — no plugin-author spawn-policy surface | orchestration policy | the sub-agent-as-skill pattern (ship agents the parent can spawn) | `agy` exposes a plugin-author orchestration surface | 🟡 mitigated |
| 4 | **Scheduled-task durability** — an in-flight scheduled task does not survive an app restart/sleep; it silently transitions to `CANCELED` instead of firing late or catching up | wiki-watcher scheduling · the agentm runner | rely on OS cron/launchd, not Antigravity's native Scheduled Tasks, for anything that must survive the app being closed | `agy` ships a persistence/catch-up guarantee for its scheduled-task primitive | 🟡 mitigated |

## 1 — Scheduling / triggers

**The gap.** Antigravity's scheduled-task primitive (triggers) is registered as Python code at agent-creation time — `every(seconds, callback)`, `on_file_change(path, callback)`, custom async functions via `LocalAgentConfig(triggers=[...])`. There's no file-based config and no plugin-installable trigger path, and no SessionStart-equivalent hook a plugin can register. A shipped plugin can't register a trigger.

**Why it matters.** The wiki-watcher is an idempotent single-cycle engine that something must re-invoke on a loop. On Claude Code the operator drives the loop with `/loop` or cron; on Antigravity there's no installable path to schedule it, so wiki-watcher **scheduling is Claude-first**. The watcher engine (config, cursors, significance, dispatch — all stdlib) is cross-host and tested on both; only the scheduling wiring is Claude-first.

**Mitigation.** Ship the engine cross-host; ship the scheduling wiring for Claude Code; document Antigravity scheduling as manual. The cross-host answer is the agentm **V7 scheduled-sidecar** — a future cross-host scheduling primitive that, if it lands, also provides an Antigravity-trigger path.

**Re-assess when** `agy` ships a file-based or plugin-installable scheduled-task surface (or a SessionStart-equivalent hook). Close once the watcher can self-schedule on Antigravity without a Python SDK environment.

## 2 — Hooks

**The gap.** Antigravity hooks are **Python decorators** registered at agent creation via `LocalAgentConfig(hooks=[...])`. The host's nine hook events (`on_session_start`, `on_session_end`, `pre_turn`, `post_turn`, `pre_tool_call_decide`, `post_tool_call`, `on_tool_error`, `on_compaction`, `on_interaction`) cover most of what Claude Code's file-based hooks do — but they require Python SDK integration to register. There's no `.agents/hooks/` directory or `hooks.json` a plugin can ship.

**Why it matters.** crickets ships six file-based hooks ([Hooks](Hooks)). Antigravity runs plugin hooks **observe / side-effect-only**, so a veto (exit code) or inject (stdout) hook is inert there, and `evidence-tracker` + `harness-context` — which need the Claude-only contract — are Claude-only.

**Mitigation.** Ship the hooks Claude-effective; on Antigravity they run observe-only. A future Python sidecar (`crickets-hooks-py`?) could translate the file-based hook scripts to SDK decorator registration at agent-author boot.

The `obsidian-vault` plugin's `conflict-merger-session-start` hook is a concrete instance: it fires its GDrive/DriveFS conflict-file nudge at session boot on Claude Code only — Antigravity has no `SessionStart` event, so the automatic nudge never fires. Detection is **not lost** there, only the automatic nudge: the plugin's `vault-doctor` skill (`supported_hosts: [claude-code, antigravity]`) and the read-only `doctor_vault.py` `conflicts` check are the Antigravity-reachable substitute — same detector, run on demand. See [Obsidian vault backend → Host coverage](Obsidian-Vault-Backend#host-coverage).

**Re-assess when** `agy` ships a file-based or plugin-installable hook surface.

## 3 — Multi-agent orchestration

**The gap.** Antigravity's multi-agent orchestration is **operator-facing**: the parent agent decides when to spawn subagents via the built-in `start_subagent` tool (`CapabilitiesConfig(enable_subagents=True)`). There's no plugin-author surface for orchestration *policy* — which subagents to spawn, when, with what context.

**Why it matters.** crickets can supply the *agents available* to spawn (the sub-agent-as-skill pattern — ship `SKILL.md` agents the parent treats as callable subagents), but not the spawn decisions.

**Mitigation.** The sub-agent-as-skill pattern is what crickets controls; the spawning is the parent agent's call. Deeper policy (specifying spawn rules via a manifest) would need a customization kind we don't have — and its value over letting the agent reason dynamically is unclear.

**Re-assess when** `agy` exposes a plugin-author orchestration-policy surface.

## 4 — Scheduled-task durability

**The gap.** Antigravity's scheduled-task primitive does not persist an in-flight task across an app restart or the machine sleeping. Hands-on verified 2026-07-06 (agentm-runner.md's Wave-B close-out): a task scheduled to fire in 180 seconds, with the app terminated before the fire time and reopened well after it, did not fire on reopen — `manage_task` reported its status as `CANCELED`, and the agent environment logged `[Notice] All your subagents and background tasks have been stopped due to server restart.` The task is dropped, not deferred or re-queued.

**Why it matters.** This is distinct from gap #1 (no plugin-installable trigger path): even a task an operator or agent schedules directly through the native surface doesn't survive the app being closed at the wrong moment. Anything that depends on "missed while off, catches up on wake" — the agentm runner's `lookback` window, or a future wiki-watcher schedule — cannot rely on Antigravity's own Scheduled Tasks to deliver that guarantee, regardless of whether a plugin could install the trigger.

**Mitigation.** Use OS cron/launchd for anything that must survive the device sleeping or the app closing — it runs independent of Antigravity's app lifecycle entirely. Antigravity Scheduled Tasks remains fine for same-session, app-stays-open use, just not as a durable heartbeat.

**Re-assess when** `agy` ships a persistence or catch-up guarantee for its scheduled-task primitive (e.g., a due-but-missed task fires on next app open instead of canceling).

## Resolving a gap

When Antigravity ships the surface a gap's re-assess trigger names:

1. Confirm crickets can use it without a Python SDK environment.
2. Update the affected crickets primitive to use the new surface (and note it in the CHANGELOG).
3. Record it **here**: strike the Quick Reference row (`~~ … ~~`), set its Status to **✅ resolved YYYY-MM-DD**, and leave the `## N — <gap>` section in place as history — the record of what the gap was and how we worked around it.

(A new gap follows the same row + section shape, opening at Status `🟡 mitigated`.)

## Related

- [Compatibility](Compatibility) — the supported-hosts contract; summarizes these gaps and links here.
- [Hooks](Hooks) — the hook catalog + per-host effectiveness.
- [Run the wiki-watcher](Run-The-Wiki-Watcher) — the watcher whose scheduling gap #1 constrains.
- [Wiki-watch config](Wiki-Watch-Config) — the config the watcher reads.
