---
name: commit-msg-gate
description: Deterministic commit-msg git hook that rejects a commit subject containing an internal codename pattern or this repo's own slop-pack vocabulary (warning-tier or above). Mechanical enforcement of Consolidation ruling 4's "Commit messages, go-forward" standard — conventional-commit prefixes and a parenthesized roadmap id are unaffected.
kind: hook
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

# commit-msg-gate — plain-English-at-the-door

A native git `commit-msg` hook, not a Claude Code lifecycle hook — it fires
on every `git commit` regardless of which host or agent produced it, exactly
like its sibling [`coauthor-guard`](../coauthor-guard/hook.md). Where
`coauthor-guard` strips a trailer, this hook can **reject the commit
outright**: `commit-msg` (unlike `prepare-commit-msg`) is git's validation
stage, so a non-zero exit aborts the commit before it's created.

## What it enforces

Consolidation ruling 4's "Commit messages, go-forward" standard
(`CONSOLIDATION-VERDICT.md`): *"a subject a stranger can read; the
conventional prefix (`feat:`/`fix:`) stays because release tooling sizes
versions from it; the roadmap id in parentheses where one applies; internal
codenames (AA/C/FIN/R/G, wave letters) banned from subjects — they live in
pack files and progress.md only."*

Two independent checks, **subject line only** (the first line of the commit
message — never the body, where a fuller narrative including a codename is
fine for traceability):

1. **Codename patterns** — the named families, matched by regex:
   `AA5`, `C7`, `FIN-2a`, `R0`/`R2.1`, `G12`, `Wave A`…`Wave E` (with or
   without a following noun), `PLAN-<slug>` references. A roadmap id in
   parentheses (e.g. `(V6-15)`) is explicitly allowed — parenthesized spans
   are blanked out before this check runs, per CONS-4's own PR-title
   precedent that a parenthesized roadmap id is a real cross-reference, not
   a codename.
2. **Slop-pack vocabulary** — reuses this repo's own canonical rule pack
   (`src/wiki/skills/diataxis-author/style/voice-rules.json`, read through
   its existing loader `rule_pack.py`) rather than a second word list, so
   this gate and the wiki gate (`scripts/check-slop.py`) can never drift
   apart. Only **error/warning**-tier rules block — suggestion-tier terms
   (the single-word AI-tell adjectives, highest false-positive risk) stay
   allowed in a commit subject, the same tiering `check-slop.py` already
   applies. `metric`-kind rules (em-dash rate, paragraph variance, ...) are
   skipped: they're a per-1000-word document signal with no meaningful
   denominator on one subject line.

## What it explicitly allows

- Conventional-commit prefixes (`feat:`, `fix:`, `docs:`, `chore:`,
  `refactor:`, `perf:`, ...) — untouched; release tooling
  (`check-version-bump.py` / `ship-release`) sizes semver from these.
- A roadmap id in parentheses, e.g. `(V6-15)`.
- Suggestion-tier vocabulary terms (see above).
- Anything at all in the commit **body** — this gate only ever reads the
  first line of the message file.

## How it works

- **Trigger:** git's native `commit-msg` hook, called as `commit-msg
  <msg-file>`.
- **Logic:** all matching lives in the co-located `commit_msg_gate.py` (a
  thin `.sh`/`.ps1` dispatch shim on each host calls it) — Python is the
  natural fit here because the vocabulary check needs to read
  `rule_pack.py`'s JSON pack, not re-parse it a second time in bash/pwsh
  (mirrors `evidence-tracker`'s own `.sh`/`.ps1` → `.py` split in
  `src/code-review/hooks/evidence-tracker/`). The `.sh`/`.ps1` shim looks for
  `commit_msg_gate.py` next to itself, so the two must be installed together
  (see "Installing" below) — a live end-to-end install test during CONS-8
  caught a first-draft version of this hook that shipped install
  instructions copying only the `.sh` shim, which then failed outright with
  a "no such file" error the moment it ran without its sibling `.py`.
- **Repo-root resolution for the shared rule pack:** rather than a fixed
  `__file__.parent` count (which breaks the moment this file sits at a
  different depth after being copied to `.git/hooks/`), `commit_msg_gate.py`
  asks `git rev-parse --show-toplevel` for the repo root and looks for
  `src/wiki/skills/diataxis-author/scripts/rule_pack.py` under it. A git hook
  always runs inside a git repository, so this holds regardless of install
  layout; when the resolved root has no `src/wiki/...` tree (a standalone
  install outside a full crickets/agentm checkout), the vocabulary check
  simply graceful-skips, same as any other missing-dependency case below.
- **If either check finds something:** the hook prints the offending
  pattern(s)/word(s) plus a suggested fix to stderr and exits 1, aborting
  the commit.
- **If neither finds anything:** exit 0, byte-identical pass-through.

## Failure modes (graceful-skip, never a hard block on infra)

- **Hook not installed:** no effect — see "Installing" below.
- **`<msg-file>` missing/unreadable, or an empty subject:** exit 0 (no-op).
- **No `python3`/`python` resolvable:** the `.sh`/`.ps1` shim prints a
  warning and exits 0 — a commit is never blocked because the host lacks
  Python.
- **The shared rule pack (`rule_pack.py` / `voice-rules.json`) isn't
  importable** (e.g. this hook was copied out standalone, without its
  `src/wiki/...` sibling tree): the codename check still runs; the
  vocabulary check is skipped with a one-line stderr notice rather than
  crashing.

## Installing

No automated installer copies this in yet (mirrors `coauthor-guard`'s own
convention, which mirrors `privacy`'s `pre-push` hook). Unlike
`coauthor-guard` (a single self-contained file), this hook's `.sh`/`.ps1`
shim dispatches to a co-located `commit_msg_gate.py` — **both files must be
installed together**. An operator installs it once per repo:

**Unix / macOS:**

```bash
cp src/developer-safety/hooks/commit-msg-gate/commit-msg-gate.sh .git/hooks/commit-msg
cp src/developer-safety/hooks/commit-msg-gate/commit_msg_gate.py .git/hooks/commit_msg_gate.py
chmod +x .git/hooks/commit-msg
```

**Windows / pwsh** (via a `core.hooksPath` directory whose `commit-msg` shim
invokes the script):

```powershell
git config core.hooksPath .githooks
# copy BOTH commit-msg-gate.ps1 and commit_msg_gate.py into .githooks/, then
# .githooks/commit-msg (no extension) invokes:
#   pwsh -NoProfile -File .githooks/commit-msg-gate.ps1 $args
```

This installs alongside `coauthor-guard` without conflict — `commit-msg` and
`prepare-commit-msg` are separate git hook slots that fire at different
stages of the same commit.

## See also

- [`coauthor-guard`](../coauthor-guard/hook.md) — the sibling native-git-hook
  this one is modeled on (same install convention, same determinism
  discipline).
- `scripts/check-slop.py` + `src/wiki/skills/diataxis-author/style/voice-rules.json`
  — the canonical slop-pack rule source this hook reads, never forks.
- Consolidation `CONSOLIDATION-VERDICT.md`, ruling 4 — the standard this hook
  mechanically enforces.
