#!/usr/bin/env python3
"""Spawn an operator-initiated worker worktree bound to a named plan.

The coordinator runs this to hand one named plan to an isolated worker: it
creates a git worktree on a `worker/<slug>` branch and drops the worktree-local
`.harness/active-plan` marker so that, *inside the worktree*, agentm's
`resolve_active_plan` binds to `PLAN-<slug>.md` with **no `--name` argument and
no singleton ambiguity** — the marker is the per-worktree precedence tier
between an explicit name and the singleton.

    spawn_worker.py <name> [--project-root <path>] [--worktree-path <path>]
    # stdout (rc 0): "<worktree_path>\n"

**Operator-initiated, never autonomous.** This is the deliberate counterpart to
the `worktrees-operator-initiated` norm (ADR 0022): an agent never spawns a
worktree on its own, but when the *operator* invokes this helper, creating the
worktree IS the initiation. Nothing here runs unprompted.

**The marker contract (owned by agentm's `harness_memory.py`).** The marker is
the **bare slug** + trailing newline (`"foo\\n"`). agentm reads it
case-preserving with `.strip()`, then through `_normalize_plan_name`
("foo" / "PLAN-foo" / "PLAN-foo.md" all → "foo"), so the bare slug round-trips
exactly. A present-but-blank or dangling marker is a *loud* error there (never a
silent singleton fallback) — which is why we write a correct, non-empty marker
or none at all.

**Plan resolution is delegated, not re-derived.** Before touching git, we ask
`resolve_plan.resolve` whether the named plan resolves. With an agentm clone that
proves `PLAN-<slug>.md` exists and is non-empty; standalone it validates slug
safety. A non-zero resolve is propagated verbatim and **nothing is created** —
we never spawn a worktree for a plan that doesn't resolve.

**LC-2 worktree slug resolution (the `vault_project` fallback).** Inside a
worktree, agentm resolves the vault project via the Tier-3 `git remote get-url
origin` basename (it survives because a worktree shares the parent repo's
`.git/config`). The `.harness/project.json` `vault_project` copy is a **fallback
only** — reproduced into the worktree *iff* it would diverge from the origin
basename (a divergent override), so a worker can't silently bind to the wrong
vault. When the origin basename already equals `vault_project` (the common case)
the copy is dormant and skipped.

Exit codes (aligned with `resolve_plan.py`, so the backends stay transparent):
    0 — worktree created; its path is on stdout.
    1 — graceful-skip: propagated from a located resolver (agentm present, no
        resolvable `_harness/`).
    2 — loud: empty/singleton/unsafe name, a pre-existing worktree path or
        branch (no-clobber), a resolver refusal (dangling marker / unsafe slug),
        or a failed `git worktree add`. Never a partial spawn.

Stdlib-only; mirrors `resolve_plan.py`'s shape (pure core + injectable backend).
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# `resolve_plan` is a sibling module; ensure this dir is importable whether the
# script is run directly, imported by path (tests), or invoked from a worktree.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# Sibling bridge — the single owner of plan resolution + the naming contract.
import resolve_plan  # noqa: E402

_AUTO = resolve_plan._AUTO

_WORKTREES_SUFFIX = ".worktrees"
_BRANCH_PREFIX = "worker/"


# ── git helpers ─────────────────────────────────────────────────────────────

def _git(args: list[str], root: str | os.PathLike) -> subprocess.CompletedProcess:
    """Run a git command in `root`, capturing output. Never raises on non-zero."""
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=30,
    )


def _origin_basename(root: str | os.PathLike) -> str | None:
    """The `origin` remote URL's repo basename, or None if unset / no remote.

    Handles both URL flavors: "https://host/org/repo.git" and the scp-style
    "git@host:org/repo.git". Splits on both `/` and `:` so the scp colon counts
    as a separator, takes the last component, strips a trailing ".git".
    """
    r = _git(["remote", "get-url", "origin"], root)
    if r.returncode != 0:
        return None
    url = r.stdout.strip().rstrip("/")
    if not url:
        return None
    last = re.split(r"[/:]", url)[-1]
    if last.endswith(".git"):
        last = last[: -len(".git")]
    return last or None


def _read_vault_project(root: str | os.PathLike) -> str | None:
    """`vault_project` from `<root>/.harness/project.json`, or None if absent.

    Read with the stdlib json parser; any read/parse error (missing file, bad
    JSON, non-string value) collapses to None — the fallback is *optional*, so a
    malformed project.json must never crash the spawn, only skip the copy.
    """
    pj = Path(root) / ".harness" / "project.json"
    try:
        import json

        data = json.loads(pj.read_text(encoding="utf-8"))
    except Exception:
        return None
    val = data.get("vault_project")
    return val if isinstance(val, str) and val.strip() else None


def _needs_vault_project_copy(root: str | os.PathLike) -> bool:
    """True iff the `vault_project` override would diverge from the origin basename.

    The copy is a fallback for a *divergent* override only. If there is no
    `vault_project` there is nothing to preserve (False). If it equals the origin
    basename the worktree's Tier-3 resolution already lands the same vault, so the
    copy is dormant (False). It fires only when they differ — or when there is no
    origin at all to fall back on (then the override is the *only* signal).
    """
    vp = _read_vault_project(root)
    if not vp:
        return False
    origin = _origin_basename(root)
    return origin is None or vp != origin


def _branch_exists(root: str | os.PathLike, branch: str) -> bool:
    return _git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], root).returncode == 0


# ── path derivations (pure) ───────────────────────────────────────────────────

def worktree_path(root: str | os.PathLike, slug: str) -> Path:
    """Default worktree location: `<repo>.worktrees/<slug>` beside the repo.

    A sibling `*.worktrees/` dir keeps every worker out of the repo's own working
    tree (so they never appear in its `git status`) while staying adjacent for
    discovery. Resolved so the parent is the repo's real parent, not a symlink.
    """
    base = Path(root).resolve()
    return base.parent / f"{base.name}{_WORKTREES_SUFFIX}" / slug


def branch_name(slug: str) -> str:
    return f"{_BRANCH_PREFIX}{slug}"


# ── core ────────────────────────────────────────────────────────────────────

def spawn(name: str, root: str, *, worktree: str | os.PathLike | None = None,
          resolver=_AUTO) -> tuple[int, str, str]:
    """Create a worker worktree bound to the named plan. Pure core, injectable backend.

    All guards run *before* any mutation, so a refusal leaves the repo untouched
    (no-clobber). `resolver` is forwarded to `resolve_plan.resolve` — `_AUTO`
    locates an agentm clone (production); tests pass `None` (force the `.harness/`
    fallback) or a stub Path (force the delegate branch).
    """
    slug = resolve_plan._normalize_plan_name(name)
    if not slug:
        return (2, "", f"[spawn_worker] a named plan is required (got {name!r}); "
                       "the singleton plan cannot be spawned into a worker.\n")

    # Delegate plan resolution — a non-zero exit (unsafe slug, dangling marker,
    # missing plan) is authoritative and propagated; nothing is created.
    rc, _out, err = resolve_plan.resolve(name, root, resolver=resolver)
    if rc != 0:
        return (rc, "", err)

    branch = branch_name(slug)
    wt = Path(worktree) if worktree is not None else worktree_path(root, slug)

    # No-clobber guards (lexists, so a dangling symlink at the path still counts).
    if os.path.lexists(wt):
        return (2, "", f"[spawn_worker] worktree path already exists: {wt} — refusing "
                       "to clobber. Remove it or pass a different --worktree-path.\n")
    if _branch_exists(root, branch):
        return (2, "", f"[spawn_worker] branch already exists: {branch} — refusing to "
                       "reuse it. Delete it or spawn under a different plan name.\n")

    wt.parent.mkdir(parents=True, exist_ok=True)
    add = _git(["worktree", "add", "-b", branch, str(wt)], root)
    if add.returncode != 0:
        return (2, "", f"[spawn_worker] `git worktree add` failed (rc={add.returncode}): "
                       f"{add.stderr.strip()}\n")

    # The worktree-local marker: the BARE SLUG + newline, the form agentm's
    # resolve_active_plan reads back through _normalize_plan_name unchanged.
    marker_dir = wt / ".harness"
    marker_dir.mkdir(parents=True, exist_ok=True)
    (marker_dir / "active-plan").write_text(f"{slug}\n", encoding="utf-8")

    # LC-2: reproduce a *divergent* vault_project override (fallback only).
    if _needs_vault_project_copy(root):
        shutil.copyfile(
            str(Path(root) / ".harness" / "project.json"),
            str(marker_dir / "project.json"),
        )

    return (0, f"{wt}\n", "")


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="spawn_worker.py",
        description="Spawn an operator-initiated worker worktree bound to a named plan.",
    )
    p.add_argument("name",
                   help="named plan ('foo', 'PLAN-foo', 'PLAN-foo.md'); the singleton is refused")
    p.add_argument("--project-root", default=None,
                   help="project root (default: cwd)")
    p.add_argument("--worktree-path", default=None,
                   help="override the worktree location (default: <repo>.worktrees/<slug>)")
    return p


def main(argv: list[str]) -> int:
    ns = _build_parser().parse_args(argv[1:])
    root = ns.project_root if ns.project_root is not None else os.getcwd()
    rc, out, err = spawn(ns.name, root, worktree=ns.worktree_path)
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
