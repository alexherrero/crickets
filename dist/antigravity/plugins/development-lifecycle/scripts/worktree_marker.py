#!/usr/bin/env python3
"""Bind an already-created host worktree to a named plan (host-native worktree flow).

`EnterWorktree` (Claude Code) / New-Worktree-Mode (Antigravity) own worktree
*creation* now — this script only does what's left once the worktree already
exists: the LC-6 pre-flight-reconcile defense-in-depth guard, the worktree-local
`.harness/active-plan` marker write, and the LC-2 `vault_project` divergent-override
copy. It replaces `spawn_worker.py`'s post-creation responsibilities; the git
`worktree add` / rollback / locking / concurrency-cap machinery that script also
carried is gone — the host primitive owns that now (host-native primitives only,
per this plan's own constraint).

    worktree_marker.py write <worktree-path> <slug> <plan-path> [--project-root <root>]
                            [--no-root-pointer]
    worktree_marker.py read <slug> [--project-root <root>]
    worktree_marker.py clear <slug> [--project-root <root>]

`write` exit codes:
    0 — marker written. `.harness/project.json` is also written into the
        worktree whenever the original repo has one, as a copy of the
        original's full project.json (so `isolation_config.read_isolation()`
        and every other plugin that reads this file — e.g. github-projects'
        board-sync, which needs `vault_project` / `github` / `fields` /
        `items_source` — resolve the same way inside the worktree as outside
        it; `.harness/` is gitignored, so a freshly host-created worktree
        otherwise has no project.json at all), with `vault_project` refreshed
        on top iff that override diverges from the origin basename (LC-2,
        unchanged). A **root-side pointer** is written too — see below.
    2 — loud: empty slug, a slug that isn't a single path component, worktree
        path does not exist / is not a directory, the path exists but is NOT a
        registered git worktree of `root` (the fake-slot guard — see
        `_is_registered_worktree` below), or the marker write itself failed.
        Never a partial write: the pre-flight check runs before any write.
    3 — pre-flight reconcile no-op (LC-6): the resolved plan's declared
        `expected_artifacts` already exist under `--project-root` — the lane is
        already shipped. Nothing written. The caller holds a worktree bound to
        nothing; it must exit/remove it, not proceed.

**The root-side pointer (the resume half of the bind).** The two writes above
are both *worktree-local*, so they leave nothing on the main-clone side: a later
session that opens at the repo root has no way to learn which worktree a plan is
bound to, and `/work`'s resume path silently runs in the main clone instead. So
`write` also records `<main-root>/.harness/worktree-for-<slug>` — one line, the
resolved worktree path — which `read` resolves back for `/work` step 1.5's
re-entry branch. Per-slug by name, never a singleton file: more than one plan is
routinely in flight, and a shared pointer would have them overwrite each other.
`.harness/` is gitignored, so this stays local state and never becomes a
committed artifact. `--no-root-pointer` suppresses the write for a *transient*
bind (the per-task worktrees `/work` step 2.5 spawns and prunes within one
session, which no later session should ever be sent back into). A pointer write
that fails is a **warning on stderr, still exit 0** — the worktree is bound and
fully usable; only the resume convenience is lost.

`read` exit codes — re-entry is best-effort and **never blocks a plan**:
    0 — the pointer resolves to a live, registered worktree; its path is on
        stdout. The caller re-enters it via the host's own worktree primitive.
    1 — nothing to re-enter; carry on in the current directory. stderr says
        which of the four reasons applies: the plan is the singleton (no
        per-slug pointer exists by construction), no pointer was recorded,
        the pointer is **stale** (the path is gone, is no longer a registered
        worktree of `root`, can't be verified, or now carries a *different*
        plan's `active-plan` marker), or the session is **already inside** that
        worktree (the no-op case — re-entering would be redundant).
    2 — usage: a slug that isn't a single path component.

`clear` drops the pointer (idempotent — already-absent is exit 0). `/work` runs
it at close-out so a finished plan doesn't leave a pointer into a worktree its
PR is about to retire.

Stdlib-only; mirrors `spawn_worker.py`'s LC-2/LC-6 helpers verbatim (relocated,
not rewritten) so their own test coverage carries over unchanged in intent.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import isolation_config  # noqa: E402
import preflight_reconcile  # noqa: E402
import resolve_plan  # noqa: E402

# `<main-root>/.harness/worktree-for-<slug>` — the root-side half of the bind.
_POINTER_PREFIX = "worktree-for-"


# ── LC-2: vault_project divergent-override copy (relocated from spawn_worker.py) ──

def _git(args: list[str], root: str | os.PathLike) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(root), capture_output=True, text=True, timeout=30,
    )


def _origin_basename(root: str | os.PathLike) -> str | None:
    """The `origin` remote URL's repo basename, or None if unset / no remote.

    Best-effort: any failure (no remote, missing git, a >30s hang) collapses to
    None — never raises.
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


def _registered_worktree_paths(root: str | os.PathLike) -> set[str] | None:
    """Every path `git worktree list --porcelain` reports for `root`'s repo,
    resolved so a symlinked/relative path still matches. None iff the registry
    itself couldn't be read (git missing, a >30s hang, or a non-zero exit) —
    callers must treat that as "can't verify", never as "not registered".
    """
    try:
        r = _git(["worktree", "list", "--porcelain"], root)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    paths: set[str] = set()
    for line in r.stdout.splitlines():
        if line.startswith("worktree "):
            p = line[len("worktree "):].strip()
            try:
                paths.add(str(Path(p).resolve()))
            except OSError:
                paths.add(p)
    return paths


def _is_registered_worktree(worktree_path: str | os.PathLike,
                            root: str | os.PathLike) -> bool | None:
    """True iff `worktree_path` is a real, git-registered worktree of `root`.

    The fake-slot guard: a host worktree primitive can leave a plain directory
    behind a slot path instead of an actual `git worktree add`-created checkout
    (observed live — a directory that never appears in `git worktree list`, so
    every git command run inside it silently walks up to `root`'s own `.git`
    and operates on the SHARED checkout). Binding a plan marker into a fake
    slot would make `/work` believe it has isolation it doesn't have. Returns
    None (not False) when the registry itself is unreadable — an unverifiable
    slot is refused by the caller exactly like a confirmed-fake one, never
    silently trusted (mirrors `worktree_shepherd.is_safe_to_reclaim`'s "never
    guess safe on an unreadable repo").
    """
    registered = _registered_worktree_paths(root)
    if registered is None:
        return None
    try:
        resolved = str(Path(worktree_path).resolve())
    except OSError:
        resolved = str(worktree_path)
    return resolved in registered


def _read_vault_project(root: str | os.PathLike) -> str | None:
    """`vault_project` from `<root>/.harness/project.json`, or None if absent/malformed.

    Any read/parse error (missing file, bad JSON, non-object document, non-string
    value) collapses to None — the fallback is optional, never fatal.
    """
    pj = Path(root) / ".harness" / "project.json"
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
        val = data.get("vault_project") if isinstance(data, dict) else None
    except Exception:
        return None
    return val if isinstance(val, str) and val.strip() else None


def _needs_vault_project_copy(root: str | os.PathLike) -> bool:
    """True iff a `vault_project` override would diverge from the origin basename."""
    vp = _read_vault_project(root)
    if not vp:
        return False
    origin = _origin_basename(root)
    return origin is None or vp != origin


def _worktree_project_json(root: str | os.PathLike) -> dict | None:
    """The `.harness/project.json` content to write into the new worktree, or
    None if there's nothing worth carrying over.

    `.harness/` is gitignored, so a freshly host-created worktree has NO
    project.json at all — any code that later runs `isolation_config.
    read_isolation()` from inside it (finalize_unit.py at close-out, for
    instance) would see the code-default (`direct`) instead of the ORIGINAL
    repo's real `isolation.mode` / `isolation.integration`, silently
    mis-resolving the very setting that got the worktree spawned in the first
    place. Other plugins read the same file too (github-projects' board-sync
    needs `vault_project` / `github` / `fields` / `items_source`), so the fix
    is to carry over a COPY of the original's full project.json rather than
    a fresh dict built from an allowlist of keys — a minimal rebuild silently
    drops whatever the allowlist forgot. `vault_project` is refreshed on top
    of the copy only when it diverges from the origin basename (LC-2,
    unchanged from before); the rest of the original document rides along
    verbatim.
    """
    pj = Path(root) / ".harness" / "project.json"
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
    except Exception:
        data = None

    if not isinstance(data, dict):
        return None

    out = dict(data)
    if _needs_vault_project_copy(root):
        out["vault_project"] = _read_vault_project(root)
    return out or None


# ── root-side pointer (the resume half of the bind) ──────────────────────────

def _resolved(p: str | os.PathLike) -> Path:
    """`p` resolved, falling back to the literal path when resolution fails."""
    try:
        return Path(p).resolve()
    except OSError:
        return Path(p)


def _main_root(root: str | os.PathLike) -> Path:
    """The MAIN checkout of `root`'s repo — where the pointer lives.

    Normalizing through `isolation_config.resolve_main_worktree` is what makes
    `write` and `read` symmetric: a caller that hands either side a worktree
    path instead of the main clone still lands on the same pointer file, rather
    than stranding the write inside a worktree nobody will look in. Graceful by
    contract (that helper collapses every git failure to the resolved input).
    """
    return _resolved(isolation_config.resolve_main_worktree(root))


def _pointer_path(root: str | os.PathLike, slug: str) -> Path:
    """`<main-root>/.harness/worktree-for-<slug>`. Per-slug, never a singleton."""
    return _main_root(root) / ".harness" / f"{_POINTER_PREFIX}{slug}"


def _normalize_and_check(slug: str) -> tuple[str, str]:
    """(bare slug, error) — error is "" when the slug is usable as a filename.

    The slug becomes part of the pointer's *filename*, so single-path-component
    safety is now load-bearing rather than cosmetic; `resolve_plan`'s own guard
    is reused so the two agree on what a usable name is.
    """
    norm = resolve_plan._normalize_plan_name(slug)
    if not norm:
        return ("", f"[worktree_marker] a named plan slug is required (got {slug!r}).\n")
    if not resolve_plan._is_safe_plan_slug(norm):
        return ("", f"[worktree_marker] unsafe plan slug {slug!r}: a slug becomes part of "
                    f"the root-side pointer's filename, so it must be a single path "
                    f"component (no separators, no traversal).\n")
    return (norm, "")


def _write_pointer(root: str | os.PathLike, slug: str,
                   worktree_path: str | os.PathLike) -> str:
    """Record slug → worktree. Returns "" on success, or a non-fatal warning.

    Idempotent: re-binding the same slug to the same worktree rewrites the same
    single line. Never raises and never fails the bind — a worktree whose
    pointer didn't land is still a correctly bound, fully usable worktree; the
    only thing lost is a later session's ability to find it without being told.
    """
    try:
        target = _pointer_path(root, slug)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"{_resolved(worktree_path)}\n", encoding="utf-8")
        return ""
    except Exception as exc:
        return (f"[worktree_marker] WARNING: bound the worktree, but could not write the "
                f"root-side pointer ({exc}). This worktree is fully usable; a later "
                f"`/work --name {slug}` just won't find it on its own — re-enter it by "
                f"path, or re-run this bind once the root is writable.\n")


def _pointer_worktree_plan(worktree: Path) -> str | None:
    """The `active-plan` slug the recorded worktree currently carries, or None
    when it has no readable marker. Used only to catch a *repurposed* worktree
    (bound to some other plan since the pointer was written)."""
    try:
        text = (worktree / ".harness" / "active-plan").read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    return text or None


def read_pointer(slug: str, root: str | os.PathLike, *,
                 cwd: str | os.PathLike | None = None) -> tuple[int, str, str]:
    """Resolve slug → the worktree to re-enter. Pure core; mutates nothing.

    Exit 0 hands back a path to re-enter; **exit 1 always means "carry on where
    you are"** — absent, stale, unverifiable, repurposed, and already-inside all
    collapse to that one non-blocking code deliberately, so no caller can turn a
    stale pointer into something that stops a plan. Only a malformed slug (a
    programming error, not a state-of-the-world one) is exit 2.
    """
    norm, err = _normalize_and_check(slug)
    if not norm:
        if "unsafe plan slug" in err:
            return (2, "", err)
        return (1, "", "[worktree_marker] singleton plan — no per-slug worktree pointer "
                       "exists; proceeding in the current directory.\n")

    main_root = _main_root(root)
    pointer = _pointer_path(root, norm)
    try:
        recorded_text = pointer.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        recorded_text = ""
    if not recorded_text:
        return (1, "", f"[worktree_marker] no worktree pointer recorded for plan {norm!r} "
                       f"(looked in {pointer}); proceeding in the current directory.\n")

    recorded = _resolved(recorded_text)

    def stale(reason: str) -> tuple[int, str, str]:
        # Built by concatenation, not %-formatting: a path is free to contain a
        # literal `%`, and a message that raises on the way to reporting a stale
        # pointer would turn the one case this must degrade through into a crash.
        return (1, "", f"[worktree_marker] STALE POINTER for plan {norm!r}: {pointer} "
                       f"records {recorded}, but {reason}. Proceeding in the current "
                       f"directory — remove the pointer with `worktree_marker.py clear "
                       f"{norm}` once you've confirmed that worktree is really gone.\n")

    if not recorded.is_dir():
        return stale("that path no longer exists")

    registered = _is_registered_worktree(recorded, main_root)
    if registered is False:
        return stale(f"`git -C {main_root} worktree list --porcelain` no longer lists it "
                     f"as a worktree of this repo")
    if registered is None:
        return stale("its worktree registry could not be read, so re-entry cannot be "
                     "confirmed safe")

    bound = _pointer_worktree_plan(recorded)
    if bound is not None and bound != norm:
        return stale(f"that worktree is now bound to plan {bound!r} instead")

    here = _current_worktree_root(cwd if cwd is not None else root)
    if here is not None and here == recorded:
        return (1, "", f"[worktree_marker] already inside the worktree bound to plan "
                       f"{norm!r} ({recorded}) — nothing to re-enter.\n")

    return (0, f"{recorded}\n", "")


def _current_worktree_root(where: str | os.PathLike) -> Path | None:
    """The working-tree root containing `where`, or None when git can't say."""
    try:
        r = _git(["rev-parse", "--show-toplevel"], where)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return _resolved(r.stdout.strip())


def clear_pointer(slug: str, root: str | os.PathLike) -> tuple[int, str, str]:
    """Drop the pointer for `slug`. Idempotent — already-absent is exit 0."""
    norm, err = _normalize_and_check(slug)
    if not norm:
        if "unsafe plan slug" in err:
            return (2, "", err)
        return (0, "", "[worktree_marker] singleton plan — no per-slug pointer to clear.\n")
    pointer = _pointer_path(root, norm)
    try:
        pointer.unlink()
    except FileNotFoundError:
        return (0, "", "")
    except OSError as exc:
        return (1, "", f"[worktree_marker] could not remove {pointer} ({exc}).\n")
    return (0, f"{pointer}\n", "")


# ── core ────────────────────────────────────────────────────────────────────

def write_marker(worktree_path: str | os.PathLike, slug: str,
                 plan_path: str | os.PathLike, root: str | os.PathLike,
                 *, root_pointer: bool = True) -> tuple[int, str, str]:
    """Bind `worktree_path` to `slug`. Pure core, no git-worktree mutation.

    `plan_path` is the already-resolved `PLAN-<slug>.md` (the caller — `/work`
    step 1 — already ran `resolve_plan.py` to get here; this never re-resolves).
    `root` is the ORIGINAL repo root (not the worktree) — LC-2's vault_project /
    origin lookups and LC-6's artifact-existence check both read against it, and
    the root-side pointer lands in its `.harness/`.

    `root_pointer=False` binds without recording the root-side pointer — for a
    transient bind (a per-task worktree, spawned and pruned inside one session)
    that no later session should be re-entered into.
    """
    norm, err = _normalize_and_check(slug)
    if not norm:
        return (2, "", err)

    wt = Path(worktree_path)
    if not wt.is_dir():
        return (2, "", f"[worktree_marker] worktree path does not exist: {wt}\n")

    # Fake-slot guard: refuse to bind a plan into a directory that isn't
    # actually a git-registered worktree of `root`. Trusting the host
    # primitive's return value without checking it back against `git worktree
    # list` is exactly how a session ends up silently sharing the parent
    # checkout instead of an isolated one (see _is_registered_worktree).
    registered = _is_registered_worktree(wt, root)
    if registered is not True:
        reason = ("git worktree list --porcelain does not list it" if registered is False
                  else "its worktree registry could not be read")
        return (2, "",
                f"[worktree_marker] refusing to bind: {wt} exists on disk but {reason} — "
                f"it is not confirmed to be a real, isolated git worktree of {root}. Binding "
                f"a plan here would silently operate on the parent checkout instead. Verify "
                f"with `git -C {root} worktree list --porcelain` and re-create the slot via "
                f"the host's worktree primitive before retrying.\n")

    # LC-6 defense-in-depth: refuse before any write if the plan already shipped.
    shipped, present = preflight_reconcile.already_shipped(plan_path, root)
    if shipped:
        return (preflight_reconcile.SHIPPED_NOOP, "",
                preflight_reconcile.shipped_message(slug, present))

    try:
        marker_dir = wt / ".harness"
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / "active-plan").write_text(f"{norm}\n", encoding="utf-8")

        project_json = _worktree_project_json(root)
        if project_json is not None:
            (marker_dir / "project.json").write_text(
                json.dumps(project_json, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:
        return (2, "", f"[worktree_marker] marker write failed ({exc}).\n")

    warning = _write_pointer(root, norm, wt) if root_pointer else ""
    return (0, f"{wt}\n", warning)


# ── CLI ────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="worktree_marker.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write", help="bind an already-created worktree to a named plan")
    w.add_argument("worktree_path")
    w.add_argument("slug")
    w.add_argument("plan_path")
    w.add_argument("--project-root", default=None)
    w.add_argument("--no-root-pointer", action="store_true",
                   help="skip the root-side pointer (transient bind — a per-task "
                        "worktree no later session should be sent back into)")
    r = sub.add_parser("read", help="print the worktree a named plan is bound to")
    r.add_argument("slug")
    r.add_argument("--project-root", default=None)
    c = sub.add_parser("clear", help="drop a named plan's root-side pointer")
    c.add_argument("slug")
    c.add_argument("--project-root", default=None)
    return p


def main(argv: list[str]) -> int:
    ns = _build_parser().parse_args(argv[1:])
    root = ns.project_root if ns.project_root is not None else os.getcwd()
    if ns.cmd == "read":
        rc, out, err = read_pointer(ns.slug, root)
    elif ns.cmd == "clear":
        rc, out, err = clear_pointer(ns.slug, root)
    else:
        rc, out, err = write_marker(ns.worktree_path, ns.slug, ns.plan_path, root,
                                    root_pointer=not ns.no_root_pointer)
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
