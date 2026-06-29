<!-- mode: index -->
# Code Review

_Standalone adversarial code review of any diff or PR — and it sharpens `developer-workflows`' `/review` when both are installed. The framing is **"assume the code has bugs"**: a reviewer returns a failing test, a `DEFECT: file:line`, or `NO ISSUES FOUND` — never prose._

Full primitive detail: [code-review design](crickets-code-review).

## How it composes

- **Standalone** — review any diff or PR directly; `requires: []`.
- **Enhances `developer-workflows`** — at `/review` the phase dispatches the adversarial reviewers; `evidence-tracker` guards `/work`'s checkbox-flips. Both engage only when `developer-workflows` is also installed.
- **Hosts** — command + both reviewer agents are host-symmetric; the cross-model reviewer degrades gracefully without `gemini`; the `evidence-tracker` `PreToolUse` hook is Claude-only ([Antigravity limitations](Antigravity-Limitations)).

## Why it works

A reviewer primed to assume bugs finds real ones; demanding a failing test or a `file:line` defect keeps the output actionable. The cross-model pass escapes the same-model echo chamber. See [Why adversarial review](Why-Adversarial-Review).

## Related

- [First code review](01-First-Code-Review) — the tutorial.
- [Review a change](Use-Code-Review) · [Simplify a diff](Simplify-A-Diff) · [In-flight decision review](Use-Doubt-Review) — the how-tos.
- [Why adversarial review](Why-Adversarial-Review) — why the assume-bugs framing works.
- [Composition design](crickets-composition) — the developer-workflows / safety / code-review split.

[Architecture](Architecture) · [Plugins](Plugins) · [Home](Home)
