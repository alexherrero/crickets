---
name: _fixture-test-hook
description: Temporary fixture for task 1 of plan #4 — exercises the toolkit's kind=hook installer dispatch end-to-end (script copy to .claude/hooks/ + .claude/settings.json deep-merge). Replaced by the three real base hooks (kill-switch + steer + commit-on-stop) in task 2.
kind: hook
supported_hosts: [claude-code]
version: 0.1.0
install_scope: project
deprecated: Temporary fixture for installer-path verification; remove in task 2 of plan #4 when the three real base hooks land.
---

# _fixture-test-hook

Temporary fixture used during task 1 of plan #4 to exercise the toolkit's `kind: hook`
installer end-to-end:

1. **Script dispatch** — installer copies `_fixture-test-hook.sh` (POSIX) or
   `_fixture-test-hook.ps1` (Windows) into the target's `.claude/hooks/`.
2. **Settings merge** — installer deep-merges `settings-fragment-bash.json` (POSIX)
   or `settings-fragment-pwsh.json` (Windows) into the target's
   `.claude/settings.json` via the new `scripts/merge-settings-fragment.py` helper.

Both the script and the fragment are minimal no-op stubs. The fixture registers
itself on the `PreToolUse` event with a `.*` matcher (matches every tool call)
and exits 0 unconditionally.

This file is **replaced** by `hooks/{kill-switch,steer,commit-on-stop}/hook.md` in
task 2 of the same plan. If you see this file in a tagged release, that's a bug —
task 2 should have removed it before v0.7.0 landed.
