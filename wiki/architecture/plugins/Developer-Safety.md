<!-- mode: index -->
# Developer Safety

The **operator-control + safety** plugin: hooks that let you halt, redirect, and recover an agent session, plus two standing commit conventions. It's the safety half of the developer plugin suite — installable on its own, and it engages with `developer-workflows`' phase loop when both are present.

## Install

```bash
claude plugin install developer-safety@crickets
```

On Antigravity, install by path (see [Install crickets plugins](Install-Into-Project)). The hooks run **observe / side-effect-only on Antigravity** — the veto/inject behaviour is Claude-effective ([Compatibility](Compatibility)).

## What it ships

| Primitive | Kind | What it does |
|---|---|---|
| **`kill-switch`** | hook · `PreToolUse` | halt the next tool call when `.harness/STOP` exists — emergency operator stop |
| **`steer`** | hook · `PreToolUse` | inject `.harness/STEER.md` into context, then archive it — mid-run redirect |
| **`commit-on-stop`** | hook · `Stop` | save a dirty tree to an `auto-save/<ts>` branch at session end — crash recovery (never touches your branch, never pushes) |
| **`commit-no-coauthor`** | snippet | never append a `Co-Authored-By` trailer — the user is the sole author |
| **`worktrees-operator-initiated`** | snippet | worktrees are operator-initiated — first-class but never autonomous |
| **`recoverability`** | skill | autonomy doctrine — classify every action as recoverable or unrecoverable; proceed on the former, stop on the latter |

Drive the control trio with the trigger files under `.harness/` — see **[Driving the control trio](#driving-the-control-trio)** below; the full hook catalog is in [Hooks](Hooks). The snippets emit as Antigravity `rules/` and drop on Claude (where the conventions live in `CLAUDE.md`/`AGENTS.md` instead — see [Customization types](Customization-Types)).

## Driving the control trio

The three hooks are driven by **trigger files** under `.harness/` (all per-repo):

| File | Who writes it | Lifecycle |
|---|---|---|
| `.harness/STOP` | you | `touch` to halt; `rm` to resume |
| `.harness/STEER.md` | you | the hook renames it to `STEER.consumed-<ts>.md` after reading |
| `auto-save/<ts>` (branch) | `commit-on-stop` | recover (below), then `git branch -D auto-save/<ts>` |

**Halt a runaway session** — in another terminal at the repo root:

```bash
touch .harness/STOP     # next tool call is blocked; rm .harness/STOP to resume
```

**Redirect mid-run** — write the correction; the next tool call injects it into context:

```bash
cat > .harness/STEER.md <<'EOF'
Use the existing helper at src/utils.py:format_record() instead of writing a new one.
EOF
```

To **halt *and* redirect**, write `STEER.md` first, then `touch .harness/STOP`. `kill-switch` is declared before `steer` in the plugin's `hooks.json`, so the halt always wins; when you `rm` STOP, the next call passes kill-switch and then `steer` injects the redirect. (Re-audit on every Claude Code release — this relies on declaration-ordered firing; rationale in [ADR 0003](crickets-developer-safety).)

**Recover crashed work** — `commit-on-stop` saved each dirty turn to a branch:

```bash
git branch -a | grep auto-save                        # find the safety branches
git checkout main && git cherry-pick auto-save/<ts>    # bring the commit onto main
```

The hook never modifies your current branch or pushes — recovery is always your call.

**On Antigravity** the hooks run observe-only (no veto/inject). Approximate them with an always-on rule (`.agents/rules/operator-control.md`) that, before each step, checks `.harness/STOP` (halt) and `.harness/STEER.md` (apply + rename), and saves a dirty tree to an `auto-save/<ts>` branch at the end — best-effort, since the agent has to remember to check.

**Troubleshooting.** A hook didn't fire → confirm `claude plugin list` shows `developer-safety` (re-sync with `claude plugin install developer-safety@crickets`; the hooks run from the plugin, not `.claude/hooks/`). `.harness/STOP` ignored → it must be a regular file (`touch`, not `mkdir`), resolved against the repo root. No `auto-save` branch → a silent no-op when git is absent, you're not in a work tree, or the tree is already clean.

## Recoverability skill

The `recoverability` skill is the **pre-action discipline** that complements the hooks' in-flight controls. It encodes the autonomy doctrine: the stop-gate is **reversibility, not destructiveness or blast-radius**.

| Class | Behavior |
|---|---|
| **Recoverable** — `git push`, `gh pr create`, `gh release create`, force-push to your own un-shared branch | **Announce + proceed** — no confirmation wait |
| **Unrecoverable** — force-push rewriting published shared history, sole-ref branch delete, published-tag overwrite, immutable deploy | **Stop + confirm** — pre-announce, then wait |
| **Unresolved decision** — a question the plan never settled | **Stop + ask** — and log it as a design/plan gap |

When uncertain, treat as unrecoverable (conservative default). Close-out bookkeeping (archiving a completed plan, updating progress files, moving ROADMAP items) is always recoverable → autonomous.

The skill ships the same classification table as the recoverability gate in `developer-workflows` `/work` · `/bugfix` · `/release`, but as a **standing instruction active in every session** — not just during a named phase. The hooks are the runtime enforcement; this skill is the pre-action judgment layer.

## How it composes

- **Standalone** — installs and works on its own; depends on nothing.
- **Enhances `developer-workflows`** — soft: its hooks engage across the phase loop (`/plan` · `/work` · `/review` · `/release`) when both are installed.
- **Hosts** — both; Claude-effective, **observe-only on Antigravity** ([Compatibility](Compatibility)).

## Why it works

The primitives compose into a safety net: **operator-controllable** (kill-switch + steer), **recoverable** (commit-on-stop saves to a side branch, never your own), and **convention-enforcing** (the commit guards). The agent stays steerable and its mistakes stay recoverable.

## Related

- [Hooks](Hooks) — the hook catalog + per-host effectiveness.
- [ADR 0003 — base operator hooks](crickets-developer-safety) — the design rationale + re-audit triggers.
- [Plugin anatomy](Plugin-Anatomy) — what a crickets plugin is + its structure.
- [Install crickets plugins](Install-Into-Project) — all three install modes.
- [Developer Plugin Suite design](developer-plugin-suite) — the developer-workflows / safety / code-review split.
