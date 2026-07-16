<!-- Status: implemented. You use this register to track Antigravity (agy) host gaps. These gaps constrain crickets primitives. You will see four rows today (scheduling · hooks · multi-agent orchestration · scheduled-task durability). You must append a row when a new agy gap blocks or degrades a crickets customization. You must strike the row and append "resolved YYYY-MM-DD" when the host ships the missing surface. Compatibility summarizes these gaps. It links here for the detail. -->

# Antigravity Limitations

Antigravity (`agy`) lacks a few host surfaces. Your crickets primitives depend on these surfaces. You use this register to track each gap. Each entry names the gap. It describes how the gap hits your primitives. It details the workaround you ship in the meantime. It states the condition that lets you close the gap. You strike through the entry when Antigravity ships a missing surface. You keep the struck entry as history. The [agy CLI plugin docs](https://antigravity.google/docs/cli-plugins) describe what the host exposes today.

## ⚡ Quick Reference

| # | Gap | Affected surface | Mitigation | Re-assess when | Status |
|---|---|---|---|---|---|
| 1 | **Scheduling / triggers** — no installable trigger path for a shipped plugin | wiki-watcher scheduling | Claude-first scheduling (`/loop` / cron); the watcher *engine* is cross-host | `agy` ships a file-based or plugin-installable scheduled-task surface | 🟡 mitigated |
| 2 | **Hooks** — no file-based hook surface (Python decorators only) | the six crickets hooks | run Claude-effective; observe-only on Antigravity ([Hooks](Hooks)) | `agy` ships a file-based / plugin-installable hook surface | 🟡 mitigated |
| 3 | **Multi-agent orchestration** — no plugin-author spawn-policy surface | orchestration policy | the sub-agent-as-skill pattern (ship agents the parent can spawn) | `agy` exposes a plugin-author orchestration surface | 🟡 mitigated |
| 4 | **Scheduled-task durability** — an in-flight scheduled task does not survive an app restart/sleep; it silently transitions to `CANCELED` instead of firing late or catching up | wiki-watcher scheduling · the agentm runner | rely on OS cron/launchd, not Antigravity's native Scheduled Tasks, for anything that must survive the app being closed | `agy` ships a persistence/catch-up guarantee for its scheduled-task primitive | 🟡 mitigated |

## 1 — Scheduling / triggers

**The gap.** Antigravity registers its scheduled-task primitive (triggers) as Python code at agent-creation time. You use `every(seconds, callback)`. You use `on_file_change(path, callback)`. You use custom async functions via `LocalAgentConfig(triggers=[...])`. You lack file-based config. You lack a plugin-installable trigger path. You lack a SessionStart-equivalent hook. A shipped plugin cannot register a trigger.

**Why it matters.** The wiki-watcher is an idempotent single-cycle engine. Something must re-invoke it on a loop. You drive the loop with `/loop` or cron on Claude Code. You lack an installable path to schedule it on Antigravity. Therefore, wiki-watcher **scheduling is Claude-first**. The watcher engine (config, cursors, significance, dispatch — all stdlib) runs cross-host. You test it on both. Only the scheduling wiring remains Claude-first.

**Mitigation.** You ship the engine cross-host. You ship the scheduling wiring for Claude Code. You document Antigravity scheduling as manual. The agentm **V7 scheduled-sidecar** provides the cross-host answer. This future cross-host scheduling primitive provides an Antigravity-trigger path if it lands.

**Re-assess when** `agy` ships a file-based or plugin-installable scheduled-task surface. You can also accept a SessionStart-equivalent hook. You close this gap once the watcher can self-schedule on Antigravity without a Python SDK environment.

## 2 — Hooks

**The gap.** Antigravity hooks are **Python decorators**. You register them at agent creation via `LocalAgentConfig(hooks=[...])`. The host provides nine hook events. These are `on_session_start`, `on_session_end`, `pre_turn`, `post_turn`, `pre_tool_call_decide`, `post_tool_call`, `on_tool_error`, `on_compaction`, and `on_interaction`. They cover most of what Claude Code's file-based hooks do. However, you need Python SDK integration to register them. You cannot ship an `.agents/hooks/` directory. You cannot ship a `hooks.json`.

**Why it matters.** You ship six file-based hooks in crickets. See [Hooks](Hooks). Antigravity runs plugin hooks **observe / side-effect-only**. A veto (exit code) hook is inert there. An inject (stdout) hook is inert there. The `evidence-tracker` and `harness-context` hooks require the Claude-only contract. Therefore, they are Claude-only.

**Mitigation.** You ship the hooks Claude-effective. You run them observe-only on Antigravity. A future Python sidecar (`crickets-hooks-py`?) can translate the file-based hook scripts. It handles SDK decorator registration at agent-author boot.

The `obsidian-vault` plugin's `conflict-merger-session-start` hook provides a concrete instance. It fires its GDrive/DriveFS conflict-file nudge at session boot on Claude Code only. Antigravity lacks a `SessionStart` event. The automatic nudge never fires there. You do **not lose** detection. You only lose the automatic nudge. You provide the plugin's `vault-doctor` skill (`supported_hosts: [claude-code, antigravity]`) as a substitute. You also provide the read-only `doctor_vault.py` `conflicts` check. You run this substitute on demand. See [Obsidian vault backend → Host coverage](Obsidian-Vault-Backend#host-coverage).

**Re-assess when** `agy` ships a file-based or plugin-installable hook surface.

## 3 — Multi-agent orchestration

**The gap.** Antigravity's multi-agent orchestration is **operator-facing**. The parent agent decides when to spawn subagents. It uses the built-in `start_subagent` tool (`CapabilitiesConfig(enable_subagents=True)`). You lack a plugin-author surface for orchestration *policy*. You cannot specify which subagents to spawn. You cannot specify when to spawn them. You cannot specify their context.

**Why it matters.** You use crickets to supply the *agents available* to spawn. This is the sub-agent-as-skill pattern. You ship `SKILL.md` agents. The parent treats them as callable subagents. You cannot supply the spawn decisions.

**Mitigation.** You control the sub-agent-as-skill pattern with crickets. The parent agent handles the spawning. You need a new customization kind for deeper policy. This lets you specify spawn rules via a manifest. The value of this over dynamic agent reasoning is unclear.

**Re-assess when** `agy` exposes a plugin-author orchestration-policy surface.

## 4 — Scheduled-task durability

**The gap.** Antigravity's scheduled-task primitive drops an in-flight task across an app restart or a machine sleep. You verified this hands-on on 2026-07-06 (agentm-runner.md's Wave-B close-out). You scheduled a task to fire in 180 seconds. You terminated the app before the fire time. You reopened the app well after the fire time. The task did not fire on reopen. The tool `manage_task` reported its status as `CANCELED`. The agent environment logged `[Notice] All your subagents and background tasks have been stopped due to server restart.` The host drops the task. It does not defer it. It does not re-queue it.

**Why it matters.** This is distinct from gap #1 (no plugin-installable trigger path). The native surface drops a task when the app closes. This affects tasks scheduled directly by an operator or an agent. Some features depend on "missed while off, catches up on wake". The agentm runner's `lookback` window is one example. A future wiki-watcher schedule is another. You cannot rely on Antigravity's native Scheduled Tasks for this guarantee. A plugin-installable trigger cannot fix this.

**Mitigation.** You use OS cron/launchd for anything that must survive the device sleeping or the app closing. It runs independent of Antigravity's app lifecycle. You use Antigravity Scheduled Tasks for same-session, app-stays-open workloads. You cannot use it as a durable heartbeat.

**Re-assess when** `agy` ships a persistence or catch-up guarantee for its scheduled-task primitive. For example, a due-but-missed task fires on next app open instead of canceling.

## Resolving a gap

When Antigravity ships the surface a gap's re-assess trigger names:

1. You confirm crickets can use it without a Python SDK environment.
2. You update the affected crickets primitive to use the new surface. You note it in the CHANGELOG.
3. You record it **here**. You strike the Quick Reference row (`~~ … ~~`). You set its Status to **✅ resolved YYYY-MM-DD**. You leave the `## N — <gap>` section in place as history. It records the gap and your workaround.

(A new gap follows the same row and section shape. It opens at Status `🟡 mitigated`.)

## Related

- [Compatibility](Compatibility) — the supported-hosts contract. It summarizes these gaps and links here.
- [Hooks](Hooks) — the hook catalog and per-host effectiveness.
- [Run the wiki-watcher](Run-The-Wiki-Watcher) — the watcher. Scheduling gap #1 constrains it.
- [Wiki-watch config](Wiki-Watch-Config) — the config the watcher reads.
