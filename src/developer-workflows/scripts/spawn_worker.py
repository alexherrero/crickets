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
        a failed `git worktree add`, or a post-create setup failure. Never a
        partial spawn: guards run before any mutation; a failed add removes the
        orphan branch git left behind; a post-create failure rolls the worktree +
        branch back. Cleanup is itself guarded — in the rare case it can't finish
        (a hang, a non-zero git), the exit-2 message names exactly what survived
        for the operator to remove by hand, rather than crash or claim a clean
        rollback.

Stdlib-only; mirrors `resolve_plan.py`'s shape (pure core + injectable backend).
"""
from __future__ import annotations

import argparse
import contextlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# `resolve_plan` and `isolation_config` are sibling modules; ensure this dir is
# importable whether the script is run directly, imported by path (tests), or
# invoked from a worktree.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# Sibling bridge — the single owner of plan resolution + the naming contract.
import resolve_plan  # noqa: E402
import isolation_config  # noqa: E402

_AUTO = resolve_plan._AUTO

_WORKTREES_SUFFIX = ".worktrees"
_BRANCH_PREFIX = "worker/"
_MAX_WORKTREES = 10  # cap: refuse to spawn if this many worker/ worktrees exist


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

    Best-effort: any failure — no remote (non-zero rc), a missing git
    (FileNotFoundError) or a >30s hang (subprocess.TimeoutExpired, a
    SubprocessError NOT caught by OSError) — collapses to None, mirroring
    `_read_vault_project`. This runs inside the post-`worktree add` block (via
    `_needs_vault_project_copy`), so a raise here would crash spawn() *after* the
    mutation; swallowing keeps that path crash-free, degrading to the
    conservative "origin unknown" fallback.
    """
    try:
        r = _git(["remote", "get-url", "origin"], root)
    except (OSError, subprocess.SubprocessError):
        return None
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
        # A *valid-JSON-but-not-an-object* document (`[1,2,3]`, `"x"`, `42`, `null`)
        # parses fine, then `data.get(...)` would raise AttributeError — neither an
        # OSError nor a SubprocessError, so on the post-create path it would escape
        # the rollback and crash the spawn. Honor the docstring's "any error → None":
        # the `isinstance` check (and keeping the `.get()` inside the try) collapses
        # every malformed shape to None, so a bad project.json only *skips* the copy.
        val = data.get("vault_project") if isinstance(data, dict) else None
    except Exception:
        return None
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


# ── concurrency-safety helpers (task 7 mitigations) ─────────────────────────

@contextlib.contextmanager
def _gc_disabled(root: str | os.PathLike):
    """Mitigation 2: set gc.auto=0 for the duration of a worktree add.

    Disabling gc prevents a concurrent `git gc --auto` from racing with
    `git worktree add` and corrupting the object store. Restores the prior
    value (or unsets if it was unset) on exit. Graceful-skip: any git config
    error is swallowed (never raises), since gc.auto is a best-effort guard.
    """
    get = _git(["config", "--local", "gc.auto"], root)
    prior = get.stdout.strip() if get.returncode == 0 else None
    _git(["config", "--local", "gc.auto", "0"], root)
    try:
        yield
    finally:
        if prior is None:
            _git(["config", "--local", "--unset", "gc.auto"], root)
        else:
            _git(["config", "--local", "gc.auto", prior], root)


def _worktree_lock_path(root: str | os.PathLike) -> Path:
    """Mitigation 1: a per-repo lockfile that serializes concurrent worktree adds."""
    git_dir = _git(["rev-parse", "--git-dir"], root)
    if git_dir.returncode == 0 and git_dir.stdout.strip():
        candidate = Path(root) / git_dir.stdout.strip()
        if candidate.is_dir():
            return candidate / "worktree-spawn.lock"
    return Path(root) / ".git" / "worktree-spawn.lock"


@contextlib.contextmanager
def _worktree_lock(root: str | os.PathLike):
    """Mitigation 1+4: acquire an exclusive advisory lock for worktree+config writes.

    Uses a plain lockfile (fnctl.flock on POSIX, cooperative on Windows).
    Graceful-skip: if the lock cannot be acquired/released, continue anyway —
    a best-effort advisory lock is better than blocking spawn indefinitely.
    """
    lock_path = _worktree_lock_path(root)
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lf = open(str(lock_path), "a")
        try:
            import fcntl
            fcntl.flock(lf, fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        try:
            yield
        finally:
            try:
                import fcntl
                fcntl.flock(lf, fcntl.LOCK_UN)
            except (ImportError, OSError):
                pass
            lf.close()
    except OSError:
        yield


def _count_worker_worktrees(root: str | os.PathLike) -> int:
    """Mitigation 8: count active `worker/` worktrees to enforce the cap."""
    r = _git(["worktree", "list", "--porcelain"], root)
    if r.returncode != 0:
        return 0
    count = 0
    for line in r.stdout.splitlines():
        if line.startswith("branch refs/heads/worker/"):
            count += 1
    return count


def _has_submodules(root: str | os.PathLike) -> bool:
    """Mitigation 6: True if the repo has any registered submodules."""
    return (Path(root) / ".gitmodules").exists()


def _worktree_is_clean(wt: Path) -> bool:
    """Mitigation 3: check if a worktree is clean before removal.

    Returns True when clean (safe to remove) or when the check fails
    (graceful-skip: an unresponsive worktree shouldn't block cleanup).
    Never uses --prune=now.
    """
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(wt),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            return True
        return r.stdout.strip() == ""
    except (OSError, subprocess.SubprocessError):
        return True


def _worktree_gone(root: str | os.PathLike, wt: Path) -> bool:
    """Best-effort `git worktree remove --force`; True iff `wt` is gone afterward.

    Fully guarded: a non-zero rc leaves the path in place (→ False), and a
    *raising* `_git` resolves to False too — the bare `_git` is NOT
    exception-free on an error path (a >30s hang surfaces as
    `subprocess.TimeoutExpired`, a `SubprocessError` not an `OSError`; a missing
    git as `FileNotFoundError`). Truth is the path itself (`os.path.lexists`),
    not the rc, so the caller reports exactly what actually survived.
    """
    try:
        _git(["worktree", "remove", "--force", str(wt)], root)
    except (OSError, subprocess.SubprocessError):
        return False
    return not os.path.lexists(wt)


def _branch_gone(root: str | os.PathLike, branch: str) -> bool:
    """Best-effort: ensure `branch` does not exist; True iff it's gone afterward.

    Returns True if the branch is already absent (e.g. a `git worktree add` that
    failed *before* creating the ref — so no false "cleanup failed" alarm) or is
    deleted now; False only if it still exists after a delete attempt or a git
    call raised. Fully guarded for the same reason as `_worktree_gone`. Remove a
    worktree holding the branch *before* calling this — a checked-out branch
    can't be deleted.
    """
    try:
        if not _branch_exists(root, branch):
            return True
        _git(["branch", "-D", branch], root)
        return not _branch_exists(root, branch)
    except (OSError, subprocess.SubprocessError):
        return False


def _rollback_worktree_and_branch(root: str | os.PathLike, wt: Path, branch: str) -> str:
    """Roll back a (possibly partial) worktree + branch; return the survivor clause.

    Removes the worktree FIRST (a branch checked out in it can't be deleted), then
    the branch, and returns a human clause naming only what *actually* survived —
    `""` when both are gone (a clean rollback). Both helpers swallow a raising /
    hanging `_git`, so the rollback itself never crashes and truth is the artifact's
    real presence, never an rc. Shared by the post-create rollback and the
    `git worktree add` raise path so the two can't drift.
    """
    wt_gone = _worktree_gone(root, wt)
    branch_gone = _branch_gone(root, branch)
    survivors = []
    if not wt_gone:
        survivors.append(f"the worktree ({wt})")
    if not branch_gone:
        survivors.append(f"the branch ({branch})")
    return " and ".join(survivors)


# ── path derivations (pure) ───────────────────────────────────────────────────

def worktree_path(root: str | os.PathLike, slug: str) -> Path:
    """Default worktree location: `<repo>.worktrees/<slug>` beside the repo.

    Mitigation 9 (root-anchor): anchors to the MAIN working tree via
    isolation_config.resolve_main_worktree so a spawn launched from inside an
    existing worktree never creates a nested sub-worktree. A sibling
    `*.worktrees/` dir keeps every worker out of the repo's own working tree (so
    they never appear in its `git status`) while staying adjacent for discovery.
    """
    base = isolation_config.resolve_main_worktree(root)
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

    Concurrency-safety mitigations (task 7): serialized worktree add (lock),
    gc.auto=0 for the duration, dirty-check before removal, cap on concurrent
    worker worktrees, submodule warning, root-anchored worktree path.
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

    # Mitigation 8: cap concurrent worker worktrees before touching git.
    active = _count_worker_worktrees(root)
    if active >= _MAX_WORKTREES:
        return (2, "", f"[spawn_worker] cap reached: {active} worker/ worktrees already "
                       f"exist (limit {_MAX_WORKTREES}). Integrate or clean up an existing "
                       f"worker before spawning a new one.\n")

    # Mitigation 6: warn about submodules (don't block, but surface the risk).
    if _has_submodules(root):
        import sys as _sys
        print("[spawn_worker] WARNING: repo has submodules — worktrees share "
              "the submodule checkout; a `git submodule update` in the worktree "
              "may conflict with other workers.", file=_sys.stderr)

    branch = branch_name(slug)
    if worktree is not None:
        wt = Path(worktree)
        # `git worktree add` runs with cwd=root, so it resolves a *relative*
        # override against root. Anchor the Python-side path the same way, or the
        # no-clobber guard / marker write / stdout below resolve it against the
        # process cwd instead — splitting the marker from git's real worktree when
        # root != cwd. Anchor only; don't `.resolve()` the leaf, so the guard can
        # still see a symlink sitting *at* wt.
        if not wt.is_absolute():
            wt = Path(root).resolve() / wt
    else:
        wt = worktree_path(root, slug)

    # No-clobber guards (lexists, so a dangling symlink at the path still counts).
    if os.path.lexists(wt):
        return (2, "", f"[spawn_worker] worktree path already exists: {wt} — refusing "
                       "to clobber. Remove it or pass a different --worktree-path.\n")
    if _branch_exists(root, branch):
        return (2, "", f"[spawn_worker] branch already exists: {branch} — refusing to "
                       "reuse it. Delete it or spawn under a different plan name.\n")

    wt.parent.mkdir(parents=True, exist_ok=True)
    # Mitigations 1+2+4: serialize worktree add + config writes with a per-repo
    # lockfile; disable gc.auto for the duration to prevent a racing `git gc --auto`
    # from corrupting the object store mid-worktree-add.
    with _worktree_lock(root), _gc_disabled(root):
        # `git worktree add -b` is NOT atomic: it registers the branch ref *before*
        # it builds the worktree dir (verified against real git). A >30s hang surfaces
        # as `subprocess.TimeoutExpired` — a `SubprocessError`, NOT an `OSError`, so
        # it would escape the post-create `except OSError` below — and SIGKILLs git
        # mid-operation, leaving an orphan branch and/or a partial worktree dir.
        # Catch it and roll both back, exactly like the post-create block.
        try:
            add = _git(["worktree", "add", "-b", branch, str(wt)], root)
        except (OSError, subprocess.SubprocessError) as exc:
            survivors = _rollback_worktree_and_branch(root, wt, branch)
            if not survivors:
                return (2, "", f"[spawn_worker] `git worktree add` raised ({exc}); rolled "
                               f"back — no partial spawn.\n")
            return (2, "", f"[spawn_worker] `git worktree add` raised ({exc}); ROLLBACK "
                           f"INCOMPLETE — manually remove {survivors} before re-spawning.\n")
        if add.returncode != 0:
            # `git worktree add -b` fails at one of two stages, BOTH verified against
            # real git: *before* the checkout (bad ref/args) it strands only the orphan
            # `worker/<slug>` branch it already registered; *during* the checkout (a
            # failing post-checkout hook, ENOSPC, a smudge/filter error) it returns
            # non-zero with the worktree dir AND branch fully built and registered — not
            # just a branch. Either way, roll back through the SAME shared reporter.
            msg = (f"[spawn_worker] `git worktree add` failed (rc={add.returncode}): "
                   f"{add.stderr.strip()}")
            survivors = _rollback_worktree_and_branch(root, wt, branch)
            if survivors:
                return (2, "", f"{msg}; ROLLBACK INCOMPLETE — manually remove {survivors} "
                               f"before re-spawning.\n")
            return (2, "", f"{msg}\n")

        # These writes run AFTER `git worktree add` has created the worktree + branch,
        # so a failure here would otherwise leave a partial spawn (worktree + branch
        # but no marker — which the no-clobber guards then block from re-spawning).
        # Roll back to honor the "never a partial spawn" contract.
        try:
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
        except Exception as exc:
            # ARCHITECTURAL SAFETY NET — catch *every* exception type, not just
            # OSError. This block calls helpers and stdlib ops that can raise beyond
            # OSError — a git hang surfaces as subprocess.TimeoutExpired (a
            # SubprocessError), a malformed config as AttributeError/ValueError. The
            # block's real contract is "if ANYTHING goes wrong after the worktree
            # exists, undo it", so it catches Exception (BaseException —
            # KeyboardInterrupt/SystemExit — still propagates) and rolls back.
            survivors = _rollback_worktree_and_branch(root, wt, branch)
            if not survivors:
                return (2, "", f"[spawn_worker] worktree created but post-create setup failed "
                               f"({exc}); rolled back the worktree and branch — no partial spawn.\n")
            return (2, "", f"[spawn_worker] worktree created but post-create setup failed "
                           f"({exc}); ROLLBACK INCOMPLETE — manually remove "
                           f"{survivors} before re-spawning.\n")

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
    # Mitigation 9: anchor to the MAIN working tree, not the cwd, so a spawn
    # launched from inside a worktree does not nest a second one.
    cwd = ns.project_root if ns.project_root is not None else os.getcwd()
    root = str(isolation_config.resolve_main_worktree(cwd))
    rc, out, err = spawn(ns.name, root, worktree=ns.worktree_path)
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
