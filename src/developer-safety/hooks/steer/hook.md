---
name: steer
description: Mid-run redirect — write `.harness/STEER.md` with a "do it this way instead" instruction and it surfaces on your next prompt. The hook reads STEER.md's contents and emits them as additionalContext (Claude Code's UserPromptSubmit injection mechanism) then renames the file to STEER.consumed-<iso-ts>.md for audit trail.
kind: hook
supported_hosts: [claude-code, antigravity]
version: 0.2.0
install_scope: project
---

# steer — inject mid-run guidance without restart

A UserPromptSubmit hook that lets you redirect a running agent session without closing it. Write a brief instruction to `.harness/STEER.md`; it surfaces on your next prompt and the file is renamed for an audit trail.

## Mechanism history (why this isn't the original PreToolUse version)

Through v0.1.0, this hook fired on `PreToolUse` and printed `STEER.md`'s contents to plain stdout, on the documented assumption that Claude Code injects a PreToolUse hook's stdout into the agent's context. That assumption was never actually true. PLAN-r2-enforcement-and-sync task 5 live-verified it with a real headless Claude Code session: a PreToolUse hook was proven to fire (an independent audit-log side effect recorded the invocation, and `STEER.md` was genuinely consumed/renamed), and the model — explicitly asked in the same turn to report ANY extra context or instructions it had received, from any source — never mentioned the injected content. The mechanism claim was false, silently, since the hook's original release.

`UserPromptSubmit` + `additionalContext` is Claude Code's real injection surface (independently corroborated by this repo's own `memory-recall-prompt-submit`-style hooks, which use the identical mechanism and are observably effective in live interactive sessions). v0.2.0 migrates to it.

**The real behavior change this brings:** guidance now surfaces on the **next user-submitted prompt**, not the next tool call within the current turn. If you write `STEER.md` mid-turn (while the agent is still working through a multi-tool-call task), it will NOT reach the agent until you send your next message — there is no longer a way to redirect the agent's very next tool call without operator input arriving first. This is a real capability narrowing relative to what was originally advertised (and never actually true) for PreToolUse, not merely a mechanism swap. For an in-flight halt, use `kill-switch` instead — it genuinely does block the next tool call.

## How it works

- **Trigger:** Claude Code's `UserPromptSubmit` event with matcher `.*` (every submitted prompt).
- **Check:** does `<project-root>/.harness/STEER.md` exist?
- **If yes:** emit `{"additionalContext": "<contents>"}` as JSON on stdout (Claude Code's UserPromptSubmit injection contract), then rename the file to `.harness/STEER.consumed-<iso-timestamp>.md`. Exit 0.
- **If no:** exit 0 (no-op).

The audit-trail rename preserves a record of every steer that was injected, with timestamps. The `consumed-*.md` files accumulate in `.harness/`; periodically delete or `git mv` them as you'd prefer.

## Operator usage

**To inject guidance before your next message:**

```bash
echo "Actually, please use the existing helper in src/utils.py instead of writing a new one." > .harness/STEER.md
```

When you next submit a prompt, the agent sees the instruction as additional context. The file gets renamed to `STEER.consumed-20260513T230400Z.md` (UTC timestamp) for the audit trail.

**Multi-line guidance:**

```bash
cat > .harness/STEER.md <<'EOF'
Three corrections:
1. The test file should live at tests/test_parser.py, not src/test_parser.py.
2. Don't add new imports of `os.system` — use `subprocess.run` instead.
3. The acceptance criterion at line 47 of the spec needs an explicit test.
EOF
```

**When to reach for it:**

- You spot a mistake the agent should fix and you're about to send another message anyway.
- You want to add context the agent didn't have at the start of the session, ahead of your next turn.
- You realize the agent is heading the wrong direction and are willing to wait for your next prompt to redirect it (for an immediate, in-flight halt use `kill-switch` instead — see below).

## Interaction with `kill-switch`

`kill-switch` fires on `PreToolUse`; `steer` fires on `UserPromptSubmit` — different events, so there is no install-order dependency between them anymore (through v0.1.0 they shared `PreToolUse` and ran in alphabetical order; that coupling no longer applies).

- `kill-switch` halts the **very next tool call**, immediately, regardless of what you've typed.
- `steer` surfaces guidance on your **next submitted prompt** — it never blocks anything.
- To halt AND redirect: touch `.harness/STOP` (halts immediately), write `STEER.md`, send your next message (steer surfaces the guidance), then remove `STOP` when ready to resume.

## Audit trail

After a steer fires, `.harness/STEER.consumed-<ts>.md` files accumulate. Use them for:

- **Forensics:** what redirects did I give the agent, and when?
- **Pattern detection:** if you steer the same way three sessions in a row, that's a signal to update `AGENTS.md` / `CLAUDE.md` with the pattern.
- **Cleanup:** `rm .harness/STEER.consumed-*.md` when you don't need the history.

## File location (v0.7.0)

Per-repo only: `<project-root>/.harness/STEER.md`. Device-scope is deferred.

## Failure modes

- **STEER.md unwritable / unreadable:** the hook can't read it; falls through to no-op. Check file permissions.
- **STEER.md is a directory:** `[[ -f ... ]]` only matches regular files. The hook treats it as absent and doesn't try to read.
- **No `python3` on PATH:** the JSON-encoding step can't run; the hook no-ops rather than emit malformed JSON. `STEER.md` is left in place (not consumed) so nothing is silently lost.
- **Filesystem race:** if you write STEER.md while a prompt is mid-flight, the hook may or may not pick it up on this submission — but it WILL pick it up on the next. Single-session, single-operator assumption.
- **`.claude/settings.json` malformed:** hooks won't load. Validate JSON.

## Host support — Claude-effective, Antigravity unregistered

`steer` is **fully effective on Claude Code**: the hook emits `additionalContext` JSON, which Claude Code injects into the agent's context on the next prompt.

On **Antigravity**, `UserPromptSubmit` has no equivalent event in Antigravity's own hook surface — the generator skips this event's registration entirely for the Antigravity emission (logged at build time: "no Antigravity equivalent — skipped"), so `steer` **does not fire at all** there (a change from the PreToolUse version, which fired but couldn't inject — the net effect for an Antigravity operator is unchanged, since the PreToolUse version was already non-functional in practice on that host). For an effective redirect on Antigravity, use the manual-rule equivalent: add an always-on rule — *"before each step, check `.harness/STEER.md`; if it exists, treat its contents as a redirect and rename the file with a timestamp"* — best-effort.

## See also

- [`kill-switch`](../kill-switch/hook.md) — companion emergency-halt hook; the immediate, in-flight equivalent this hook no longer is.
- [`commit-on-stop`](../commit-on-stop/hook.md) — companion safety-branch hook.
- [How to use the base hooks](../../wiki/how-to/Use-The-Base-Hooks.md) — practical scenarios for all three.
- [developer-safety design — base operator hooks rationale](https://github.com/alexherrero/crickets/wiki/crickets-developer-safety) — design rationale.
