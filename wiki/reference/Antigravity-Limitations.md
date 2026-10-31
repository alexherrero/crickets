<!-- Status: implemented. You use this register to track Antigravity (agy) host gaps. These gaps constrain crickets primitives. You will see seven rows today (scheduling · hooks, resolved · multi-agent orchestration · scheduled-task durability · agent tool allowlists · built-in name clashes · the 24 KB skill limit). You must append a row when a new agy gap blocks or degrades a crickets customization. You must strike the row and append "resolved YYYY-MM-DD" when the host ships the missing surface. Compatibility summarizes these gaps. It links here for the detail. -->

# Antigravity Limitations

Antigravity (`agy`) lacks a few host surfaces. Your crickets primitives depend on these surfaces. You use this register to track each gap. Each entry names the gap. It describes how the gap hits your primitives. It details the workaround you ship in the meantime. It states the condition that lets you close the gap. You strike through the entry when Antigravity ships a missing surface. You keep the struck entry as history. The [agy CLI plugin docs](https://antigravity.google/docs/cli-plugins) describe what the host exposes today.

## ⚡ Quick Reference

| # | Gap | Affected surface | Mitigation | Re-assess when | Status |
|---|---|---|---|---|---|
| 1 | **Scheduling / triggers** — no installable trigger path for a shipped plugin | wiki-watcher scheduling | Claude-first scheduling (`/loop` / cron); the watcher *engine* is cross-host | `agy` ships a file-based or plugin-installable scheduled-task surface | 🟡 mitigated |
| ~~2~~ | ~~**Hooks** — no file-based hook surface (Python decorators only)~~ | ~~the crickets hooks~~ | `agy` 1.4 reads `hooks.json`; crickets ships its hooks through an adapter ([Hooks](Hooks)) | ~~`agy` ships a file-based / plugin-installable hook surface~~ | ✅ resolved 2026-10-30 |
| 3 | **Multi-agent orchestration** — no plugin-author spawn-policy surface | orchestration policy | the sub-agent-as-skill pattern (ship agents the parent can spawn) | `agy` exposes a plugin-author orchestration surface | 🟡 mitigated |
| 4 | **Scheduled-task durability** — an in-flight scheduled task does not survive an app restart/sleep; it silently transitions to `CANCELED` instead of firing late or catching up | wiki-watcher scheduling · the agentm runner | rely on OS cron/launchd, not Antigravity's native Scheduled Tasks, for anything that must survive the app being closed | `agy` ships a persistence/catch-up guarantee for its scheduled-task primitive | 🟡 mitigated |
| 5 | **Agent tool allowlists** — `agy` wants `tools:` as a list of its own tool names, and rejects a Claude model tier | every crickets agent | the emitter drops `tools:` and `model:`; the agent uses the session's tools and model | `agy` documents its agent tool names, or a Claude name maps to one | 🟡 mitigated |
| 6 | **Built-in name clashes** — `agy`'s own `/plan` wins over a skill called `plan` | `/plan` from `development-lifecycle` | type `/development-lifecycle:plan` | `agy` namespaces plugin skills by default, or stops reserving the name | 🟡 mitigated |
| 7 | **24 KB skill limit** — `agy` loads only the first 24 KB of a `SKILL.md` | `/work`, `/design`, `diataxis-author` | a long body moves to `references/`, behind a short `SKILL.md` that says to read it first | `agy` lifts the limit | 🟡 mitigated |

## 1 — Scheduling / triggers

**The gap.** Antigravity registers its scheduled-task primitive (triggers) as Python code at agent-creation time. You use `every(seconds, callback)`. You use `on_file_change(path, callback)`. You use custom async functions via `LocalAgentConfig(triggers=[...])`. You lack file-based config. You lack a plugin-installable trigger path. You lack a SessionStart-equivalent hook. A shipped plugin cannot register a trigger.

**Why it matters.** The wiki-watcher is an idempotent single-cycle engine. Something must re-invoke it on a loop. You drive the loop with `/loop` or cron on Claude Code. You lack an installable path to schedule it on Antigravity. Therefore, wiki-watcher **scheduling is Claude-first**. The watcher engine (config, cursors, significance, dispatch — all stdlib) runs cross-host. You test it on both. Only the scheduling wiring remains Claude-first.

**Mitigation.** You ship the engine cross-host. You ship the scheduling wiring for Claude Code. You document Antigravity scheduling as manual. The agentm **V7 scheduled-sidecar** provides the cross-host answer. This future cross-host scheduling primitive provides an Antigravity-trigger path if it lands.

**Re-assess when** `agy` ships a file-based or plugin-installable scheduled-task surface. You can also accept a SessionStart-equivalent hook. You close this gap once the watcher can self-schedule on Antigravity without a Python SDK environment.

## ~~2 — Hooks~~ — resolved 2026-10-30

**The gap (history).** Under `agy` 1.0.2, hooks were Python decorators registered at agent creation, with no `hooks.json` and no `SessionStart` or pre-prompt event. crickets shipped its hooks anyway, and `agy` ran them observe-only: it ignored exit codes and never read stdout. That left `kill-switch` advisory, `steer` unregistered, and the `SessionStart` hooks Claude-only.

**What changed.** `agy` 1.4 loads a `hooks.json` from the plugin root, with six events (`SessionStart`, `PreToolUse`, `PostToolUse`, `PreInvocation`, `PostInvocation`, `Stop`) and a JSON answer contract. `PreInvocation` receives the user's last message, which is the pre-prompt event the old gap waited for.

**What crickets does.** Every hook runs through `hooks/_agy_hook_adapter.py`, which runs the Claude-style script unchanged and translates its answer ([Hooks](Hooks) has the table). The old emitter wrote the 1.0.2-era shape, so `agy` 1.4 skipped the whole `hooks.json` of two plugins for want of a `command` on a mis-shaped `Stop` entry; the plugin shape gate (`check-agy-plugin-shape`) now fails CI on that.

**What is still Claude-only.** `evidence-tracker` and `compact-nudge-resume`, for reasons that are about Claude's payloads and session file, not about `agy`'s events. The PowerShell twins are not wired for `agy`.

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

## 5 — Agent tool allowlists

**The gap.** A crickets agent lists `tools: Read, Glob, Grep, Bash` (Claude's names) and some name a Claude `model:`. `agy` wants `tools:` as a YAML list of its own tool names (`view_file`, `run_command`, ...) and rejects a Claude model tier. Either mismatch makes `agy` skip the whole agent; `agy plugin validate` reported nine agents skipped this way on 2026-10-30.

**Why it matters.** A read-only agent such as `adversarial-reviewer` lost its tool restriction on the way to `agy`, so on `agy` it is read-only by its instructions alone.

**Mitigation.** The emitter drops `tools:` and `model:` for Antigravity. The agent inherits the session's tools and model.

**Re-assess when** `agy` documents its agent tool names, so a Claude name can be mapped to one.

## 6 — Built-in name clashes

**The gap.** `agy` has built-in slash commands, and a built-in wins a name clash with a plugin skill. `/plan` is one: it starts `agy`'s planning mode, not the crickets plan phase. Watched on 2026-10-30, and the same run showed the crickets skill was still listed.

**Mitigation.** Type `/development-lifecycle:plan`. The prefixed form ran the crickets skill. Other names may clash too; `/help` in an interactive session lists the built-ins.

**Re-assess when** `agy` namespaces plugin skills by default or stops reserving the name.

## 7 — 24 KB skill limit

**The gap.** `agy` loads only the first 24 KB of a `SKILL.md` body and warns on the rest. `/work` (38 KB), `/design` (35 KB) and the wiki plugin's `diataxis-author` (50 KB) are over it; `/plan` (21 KB) and `/release` (19 KB) fit.

**Mitigation.** The emitter keeps the whole body in `references/` and writes a short `SKILL.md` that tells the agent to read it first. Relative links in the moved body get the extra `../` they need.

**Re-assess when** `agy` lifts the limit.

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
