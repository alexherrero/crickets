<!-- mode: index -->
# Code Review

Standalone adversarial code review of any diff or PR — and it sharpens `developer-workflows`' `/review` when both are installed. The framing is **"assume the code has bugs"**: a reviewer returns a failing test, a `DEFECT: file:line`, or `NO ISSUES FOUND` — never prose.

## Install

```bash
claude plugin install code-review@crickets
```

On Antigravity, install by path (see [Install crickets plugins](Install-Into-Project)). The command + both reviewer agents work on both hosts; the cross-model reviewer needs the Gemini CLI, and the evidence-tracker hook is Claude-only ([Compatibility](Compatibility)).

## What it ships

| Primitive | Kind | What it does |
|---|---|---|
| **`/code-review`** | command | adversarially review the current diff or PR — dispatches the reviewer agent(s) |
| **`adversarial-reviewer`** | agent | in-process critic — output is a failing test, a `DEFECT: file:line`, or `NO ISSUES FOUND`; prose-only critiques are rejected |
| **`adversarial-reviewer-cross`** | agent | cross-model critic — shells out to the Gemini CLI for a second opinion, and **falls back** to the in-process reviewer when `gemini` is absent |
| **`evidence-tracker`** | hook · `PreToolUse` | default-FAIL evidence gate for `/work` — blocks flipping a `PLAN.md` task to `[x]` until a read matching that task is recorded (Claude-only) |
| **`/simplify`** | command | cleanup pass over a diff — Chesterton's Fence + Rule of 500 guard + rationalization table; reports, then optionally applies |
| **`/doubt`** | command | in-flight adversarial review before a decision stands — CLAIM→EXTRACT→DOUBT→RECONCILE→STOP loop, hard 3-cycle cap |
| **`security-review`** | skill | three-tier boundary model for security analysis: LLM API boundary, persistence boundary, system execution boundary |
| **`testing-strategy`** | skill | DAMP + Beyonce Rule test-design heuristics: deterministic, anti-fragile, meaningful, proportionate |
| **`security-auditor`** | agent | sub-agent dispatched by `security-review`; scans a diff or file set for security boundary violations |
| **`test-engineer`** | agent | sub-agent dispatched by `testing-strategy`; generates DAMP-conformant test scaffolding |

`cross-review.sh` is the Gemini shell-out behind the cross-model reviewer.

## How it composes

- **Standalone** — review any diff or PR directly with `/code-review`; `requires: []`.
- **Enhances `developer-workflows`** — soft, two ways: at `/review` the phase dispatches the adversarial reviewers (the `enhances: review` declaration); `evidence-tracker` guards `/work`'s checkbox-flips. Both engage only when `developer-workflows` is also installed.
- **Hosts** — the command + both reviewer agents are host-symmetric; the cross-model reviewer degrades gracefully without `gemini`; the `evidence-tracker` `PreToolUse` hook is Claude-only ([Antigravity limitations](Antigravity-Limitations)).

## Why it works

A reviewer primed to **assume bugs exist** finds real ones; demanding a failing test or a `file:line` defect keeps the output actionable instead of a sycophantic "looks good." The cross-model pass escapes the same-model echo chamber — a model reviewing its own code tends to rubber-stamp; a different model has different blind spots. And `evidence-tracker` stops a task being marked done before the work was actually read. See [Why adversarial review](Why-Adversarial-Review).

## Related

- [First code review](01-First-Code-Review) — the tutorial.
- [Review a change](Use-Code-Review) — the how-to for `/code-review`.
- [Simplify a diff](Simplify-A-Diff) — the how-to for `/simplify`.
- [In-flight decision review](Use-Doubt-Review) — the how-to for `/doubt`.
- [Why adversarial review](Why-Adversarial-Review) — why the assume-bugs framing works.
- [Developer Workflows](Developer-Workflows) — the base plugin this enhances at `/review`.
- [Hooks](Hooks) · [Plugin anatomy](Plugin-Anatomy) — the evidence-tracker catalog entry + the shared plugin structure.
- [Developer Plugin Suite design](developer-plugin-suite) — the developer-workflows / safety / code-review split.
