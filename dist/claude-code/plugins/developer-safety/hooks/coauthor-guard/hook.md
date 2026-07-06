---
name: coauthor-guard
description: Deterministic prepare-commit-msg git hook that strips any Co-Authored-By trailer from a commit message before it reaches the human. Additive enforcement on top of the existing commit-no-coauthor snippet + host includeCoAuthoredBy setting — not a replacement for that floor.
kind: hook
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

# coauthor-guard — deterministic Co-Authored-By strip

A native git `prepare-commit-msg` hook, not a Claude Code lifecycle hook — it fires on every `git commit` regardless of which host or agent produced it, closing the gap the prose-only floor (the `commit-no-coauthor` snippet + a host's `includeCoAuthoredBy` setting) leaves when either is forgotten or the host ignores the setting.

## How it works

- **Trigger:** git's native `prepare-commit-msg` hook, called as `prepare-commit-msg <msg-file> <source> [<sha1>]`.
- **Check:** does the message at `<msg-file>` contain a line matching `Co-Authored-By:` (case-insensitive)?
- **If yes:** the matching line(s) are removed; every other line is left byte-identical.
- **If no:** the file is left byte-identical — no false-positive edits.

Deterministic regex/string-match only, never LLM-judged — mirrors `content-refresh`'s mechanical-vs-judgment-bound split and the diagnostics privacy scrub's determinism discipline. Not hardcoded to any one agent's name (`Claude`, `Gemini`, or anyone else's trailer strips the same way).

## Installing

No automated installer copies this in yet (mirrors `privacy`'s `pre-push` hook — see its own `hook.md`/template for the same convention). An operator installs it once per repo:

**Unix / macOS:**

```bash
cp src/developer-safety/hooks/coauthor-guard/coauthor-guard.sh .git/hooks/prepare-commit-msg
chmod +x .git/hooks/prepare-commit-msg
```

**Windows / pwsh** (via a `core.hooksPath` directory whose `prepare-commit-msg` shim invokes the script):

```powershell
git config core.hooksPath .githooks
# .githooks/prepare-commit-msg (no extension) then invokes:
#   pwsh -NoProfile -File src/developer-safety/hooks/coauthor-guard/coauthor-guard.ps1 $args
```

Or point `core.hooksPath` at a directory containing either twin directly, per your git-for-Windows setup.

## Relationship to the existing floor

The `commit-no-coauthor` snippet (prose instructing an agent never to add the trailer) plus the host's `includeCoAuthoredBy` setting are the **floor** this hook sits on top of, not replaces:

- The snippet + setting are the first line of defense — most commits never carry the trailer in the first place.
- `coauthor-guard` is the deterministic backstop for when either is forgotten, misconfigured, or the host's setting is silently ignored — it catches the trailer at commit time, unconditionally.

Removing the snippet or the host setting because this hook exists would be a regression — see `AGENTS.md` and this repo's `CLAUDE.md` for the floor's own rules, unchanged by this hook.

## Failure modes

- **Hook not installed:** no effect — the floor above is all that's protecting the commit. `check-all.sh` does not verify installation (it's a per-operator manual step, like `pre-push`).
- **`<msg-file>` missing or unreadable:** the hook exits 0 (no-op) rather than blocking the commit — a guard that can fail a commit outright would be worse than one that occasionally misses a strip.
- **A message with no trailer:** left byte-identical — never a spurious edit.

## Host support — effective on both

Unlike `kill-switch`/`steer` (Claude-Code-only-effective PreToolUse hooks), `coauthor-guard` is a **native git hook** — git invokes it identically regardless of which host or agent is driving the commit, so it is fully effective on both Claude Code and Antigravity (and even a human committing by hand).

## See also

- [`kill-switch`](../kill-switch/hook.md) / [`steer`](../steer/hook.md) / [`commit-on-stop`](../commit-on-stop/hook.md) — the Claude-Code-lifecycle hook trio this hook sits alongside.
- `snippets/commit-no-coauthor.md` — the prose floor this hook backs up.
- [developer-safety design](https://github.com/alexherrero/crickets/wiki/crickets-developer-safety) — design rationale.
