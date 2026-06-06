<!-- Status: pending — wiki-watcher (W1). Plan: .harness/PLAN.md (The wiki-watcher (W1) — wiki-maintenance part 4/5), task 5 (DC-W5). The scheduling/trigger gap row is seeded here; the documenter authors the final copy at the phase boundary. This is a growing register — append future agy limitations as rows; close a row (strike + "resolved YYYY-MM-DD") when the host ships the missing surface. Cross-link from Compatibility.md is an OPEN QUESTION pending caller confirmation (Compatibility.md is published, not pending). -->

# Antigravity limitations register

A durable, **growing** list of Antigravity (`agy`) host limitations that constrain crickets customizations. Each row records the gap as it affects **our** primitives, the crickets-side mitigation, and a **re-address trigger** — the condition under which the row should be re-opened and closed once the host ships the missing surface.

This page documents only the seam where an `agy` gap touches a crickets customization. For the host's own primitive surface, link out to the [agy CLI plugin docs](https://antigravity.google/docs/cli-plugins) — we don't re-document Antigravity's API here.

> [!NOTE]
> **Status:** pending — seeded by `wiki-maintenance` part 4 (task 5, DC-W5) with the wiki-watcher scheduling gap. The `documenter` authors the published copy at the phase boundary. **This register grows:** append a new row whenever an `agy` gap blocks or degrades a crickets customization, and close a row when the host resolves it.

## ⚡ Quick Reference

| # | Limitation | Affected crickets surface | Crickets mitigation | Re-address when resolved | Status |
|---|---|---|---|---|---|
| 1 | **Scheduling / trigger gap** — no installable trigger path for a shipped plugin. | wiki-watcher (W1) scheduling | Claude-first scheduling (`/loop`/cron); cross-host engine; Antigravity scheduling documented-manual + deferred to agentm V7 scheduled-sidecar. | `agy` ships a file-based or plugin-installable scheduled-task surface — re-audit on each `agy` release. | open |

## 1 — Scheduling / trigger gap

**The gap.** Antigravity's scheduled-task primitive (triggers) is registered as Python code at agent-creation time — `every(seconds, callback)`, `on_file_change(path, callback)`, and custom async functions via `LocalAgentConfig(triggers=[...])`. There is **no file-based config and no plugin-installable trigger path**, and there is **no SessionStart hook surface**. A shipped crickets plugin cannot register a trigger.

**Why it matters for crickets.** The wiki-watcher (W1) is an idempotent single-cycle engine that something must re-invoke on a loop. On Claude Code the operator drives that loop with `/loop` or cron. On Antigravity there is no installable path to schedule the re-invocation, so **wiki-watcher scheduling is Claude-first**. The watcher *engine* (config, cursors, significance, dispatch — all stdlib) is cross-host and unit-tested for both hosts; only the **scheduling** wiring is Claude-first (DC-W4).

**Crickets mitigation.** Ship the engine cross-host; ship the scheduling wiring for Claude Code; document Antigravity scheduling as manual + deferred. The cross-host answer is the agentm **V7 scheduled-sidecar** — a future cross-host scheduling primitive that, if it lands, also provides an Antigravity-trigger integration path.

**Re-address trigger.** Re-open this row when `agy` ships a file-based or plugin-installable scheduled-task surface (or a SessionStart-equivalent hook a plugin can register). Re-audit on each `agy` release; close the row (strike the entry + note `resolved YYYY-MM-DD`) once the watcher can self-schedule on Antigravity without a Python SDK environment.

**See also.** [Compatibility § Scheduled tasks (triggers) gap](Compatibility#scheduled-tasks-triggers-gap) for the broader host-surface framing; [How to run the wiki-watcher (W1)](Run-The-Wiki-Watcher) for the Claude-first loop; agentm V7 roadmap for the scheduled-sidecar.

## How to add a row

When an `agy` gap blocks or degrades a crickets customization:

1. Add a row to the Quick Reference table (next `#`, `Status: open`).
2. Add a matching `## N — <limitation>` section: the gap, why it matters for crickets, the mitigation, and the **re-address trigger**.
3. When the host resolves it, strike the table row and append `resolved YYYY-MM-DD` to its Status; leave the section in place as history.

## Related

- [Compatibility](Compatibility) — the supported-hosts contract and the broader "Known gaps — Antigravity 2.0 surface" framing this register draws its seed entry from.
- [How to run the wiki-watcher (W1)](Run-The-Wiki-Watcher) — the watcher whose scheduling the gap constrains.
- [Wiki-watch config](Wiki-Watch-Config) — the config the watcher reads.
