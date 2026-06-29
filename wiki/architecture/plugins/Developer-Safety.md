<!-- mode: index -->
# Developer Safety

_Operator control + safety: hooks that let you halt, redirect, and recover an agent session, plus two standing commit conventions._

Full primitive detail: [developer-safety design](crickets-developer-safety).

## Driving the control trio

The three hooks are driven by **trigger files** under `.harness/` (all per-repo):

| File | Who writes it | Lifecycle |
|---|---|---|
| `.harness/STOP` | you | `touch` to halt; `rm` to resume |
| `.harness/STEER.md` | you | the hook renames it to `STEER.consumed-<ts>.md` after reading |
| `auto-save/<ts>` (branch) | `commit-on-stop` | recover with cherry-pick, then `git branch -D auto-save/<ts>` |

To **halt *and* redirect**, write `STEER.md` first, then `touch .harness/STOP`. `kill-switch` is declared before `steer`, so the halt always wins; remove STOP, and `steer` injects the redirect on the next call.

**On Antigravity** the hooks run observe-only (no veto/inject). Approximate with an always-on rule that checks `.harness/STOP` and `.harness/STEER.md` before each step.

See [Hooks](Hooks) for the full hook catalog and per-host effectiveness.

## How it composes

- **Standalone** — depends on nothing.
- **Enhances `developer-workflows`** — hooks engage across the phase loop when both are installed.
- **Hosts** — both; Claude-effective, observe-only on Antigravity ([Compatibility](Compatibility)).

## Related

- [Hooks](Hooks) — the hook catalog + per-host effectiveness.
- [Developer safety design](crickets-developer-safety) — the design rationale + re-audit triggers.
- [Plugin anatomy](Plugin-Anatomy) — what a crickets plugin is + its structure.
- [Composition design](crickets-composition) — the developer-workflows / safety / code-review split.

[Architecture](Architecture) · [Plugins](Plugins) · [Home](Home)
