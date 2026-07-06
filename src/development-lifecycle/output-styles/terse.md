---
name: terse
description: Silence inter-tool chatter; preserve the full end-of-task status report.
kind: output-style
supported_hosts: [claude-code, antigravity]
version: 0.1.0
---

## Inter-tool silence

Stay silent between tool calls. Do not narrate each step — surface a line only when you find something load-bearing, change direction, or hit a blocker. One sentence per update is almost always enough.

## Carve-out: keep-coding-instructions

`keep-coding-instructions: true` — This style trims inter-tool chatter only. Short updates that signal direction or a blocker are still expected. Do not suppress implementation-level context that helps the operator understand what is happening.

## Carve-out: end-of-task status report

The full end-of-task status report is always emitted — this carve-out is load-bearing. Terse applies to narration between tool calls, not to the summary that closes a task. A detailed per-task status report (tasks completed, files changed, commit SHA, gate results, handoff phrase) is never trimmed by this style.
