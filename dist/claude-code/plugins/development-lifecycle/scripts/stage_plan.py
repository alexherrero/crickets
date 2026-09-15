#!/usr/bin/env python3
"""Two-tier named-plan staging for the phase loop (V5-10 sibling #1), in both
plan layouts.

The `/plan` command calls this to **stage** a named plan into an inactive tier
and later **activate** it:

    stage_plan.py path     <name> [--project-root <path>]   # where to write a staged plan
    stage_plan.py activate <name> [--project-root <path>]   # promote staged → active

**Composed onto the resolver — never re-derived.** The active plan's resolution
(precedence, slug-safety, vault redirection, the dangling-marker loud-error) is
owned by `resolve_plan.resolve` → agentm's process seam (`process_seam.py
state-path`), which returns the plan, its progress log and its tracker. We take
the plan path it returns and tell the two layouts apart by it: a task's plan is
`plan.md` inside its own directory (`tasks/042-build-the-brief/plan.md`), and a
flat plan is `PLAN-<name>.md`. Nothing here composes a layout. If a future
resolver moves the active plan, staging follows it. `resolve_plan` stays a pure
resolver — the side-effecting copy and the tracker's move live only here.

- **Flat.** A coordinator pre-authors plans into `queued-plans/` beside the
  flat plan (inert: invisible to `/work` and `/queue-status-lite`), then
  activates them one at a time as workers pick them up. `path` prints
  `queued-plans/PLAN-<name>.md`; `activate` is the guarded copy below. A tracker
  already at the resolved tracker path must say `queued`, or the activation is
  refused before a byte is written; a `queued` one moves to `active` after the
  copy. With no tracker, the normal case, the copy is the whole activation, and
  the plan's tracker opens at its first `/work` step.
- **Task.** A queued task is its own staging tier, kept inert by its `queued`
  tracker. `path` prints the task's own `plan.md`, never a `queued-plans/`
  inside a task directory, and nothing here creates `_harness/`. `activate`
  requires the tracker to exist and say `queued`; its transition to `active` is
  the activation, and nothing is copied.

**Staging is named-only.** The singleton `PLAN.md` *is* the active default; there
is nothing to stage for it. An empty/singleton name is a loud refusal (exit 2),
before the resolver is even consulted.

**`activate` is guarded — no clobber, no silent fallback (Risk #7).** It refuses
(exit 2, stderr, no write) when the staged file is missing *or* an active
`PLAN-<name>.md` already exists. A resolver that ran and refused (unsafe slug,
dangling marker, exit 4) propagates its own non-zero exit verbatim — never a
singleton fallback.

Exit codes (aligned with `resolve_plan.py` so the surface is transparent):
    0 — ok; the resolved path (or the activated path) is on stdout.
    1 — graceful-skip propagated from the resolver (agentm present, no `_harness/`).
    2 — loud: empty/unsafe name, missing staged plan, active-plan collision, a
        tracker that isn't `queued`, a task with no tracker, or a flat copy that
        landed while its tracker's move failed (the message says which).
    3 — `activate` only: pre-flight reconcile no-op (LC-6) — the plan's declared
        `expected_artifacts` already exist on `main`, so the lane is already
        shipped. Benign (nothing written), not an error; the operator does not
        proceed to `/work`. Absent the key, never fires. Both layouts.
    4 — name the task, passed on from the resolver.

Stdlib-only; mirrors `resolve_plan.py`'s shape (pure core + injectable resolver).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# One owner of resolution + the PLAN/progress naming contract: the sibling bridge.
# Reuse its `_AUTO` sentinel verbatim so `resolver=` passes through transparently
# (tests inject `resolver=None` to force the `.harness/` fallback, or a stub Path
# to force the delegate branch — exactly as on `resolve_plan`/`queue_status`).
import resolve_plan  # noqa: E402
# The cheap pre-flight reconcile (LC-6): refuse to activate a lane whose declared
# artifacts already exist on `main`. Read-only — it only reads the plan's
# frontmatter and tests path existence; it never mutates.
import preflight_reconcile  # noqa: E402

_AUTO = resolve_plan._AUTO

# The inactive staging tier for a flat plan, flat beside it (crickets convention —
# no per-design subdir). Stage as `queued-plans/PLAN-<n>.md`. A task has none.
_QUEUED_DIR = "queued-plans"


# ── core (pure but for the injected resolver, a single guarded copy, and the
#    tracker's move through agentm's tracker.py) ──────────────────────────────────

def _resolved(name: str, root: str, *, resolver) -> tuple[int, str, str, str]:
    """Resolve the active plan and its tracker via the bridge, named-only.

    Returns (0, plan_path, tracker_path, "") on success — `tracker_path` is ""
    wherever agentm names no tracker — else the resolver's non-zero exit and
    stderr verbatim, or a loud (2, "", "", msg) when `name` is empty/singleton
    (there is no staged form of the singleton). The progress path is dropped.
    """
    if not resolve_plan._normalize_plan_name(name):
        return (2, "", "", f"[stage_plan] staging requires a named plan (got {name!r})\n")
    rc, out, err = resolve_plan.resolve(name, root, resolver=resolver)
    if rc != 0:
        return (rc, "", "", err)
    fields = out.rstrip("\r\n").split("\t")
    tracker = fields[2].strip() if len(fields) > 2 else ""
    return (0, fields[0].strip(), tracker, "")


def _is_task(plan: Path) -> bool:
    """A task's plan is `plan.md` in its own directory; a flat plan is `PLAN-<name>.md`."""
    return plan.name == "plan.md"


def _tracker_status(tracker: str) -> tuple[int, str, str]:
    """(0, status, "") from `tracker.py show`, through the bridge; else a non-zero
    code and the reason."""
    bridge = resolve_plan._bridge
    if bridge is None:
        return (3, "", "agentm_bridge.py could not be loaded")
    code, out, err = bridge.run_tracker(["show", tracker])
    if code != 0:
        return (code, "", err.strip() or f"tracker.py show exited {code}")
    try:
        status = json.loads(out).get("status") or ""
    except (ValueError, AttributeError):
        return (1, "", f"tracker.py show printed no tracker for {tracker}")
    return (0, str(status), "")


def _move_to_active(tracker: str) -> tuple[int, str]:
    code, out, err = resolve_plan._bridge.run_tracker(["transition", tracker, "--to", "active"])
    return (code, err.strip() or out.strip())


def staging_path(name: str, root: str, *, resolver=_AUTO) -> tuple[int, str, str]:
    """Where a staged plan is written. Read-only — emits the path.

    Flat: `queued-plans/PLAN-<name>.md` beside the active plan the resolver
    returned. Task: the task's own `plan.md`, since a queued task is its own
    staging tier.
    """
    rc, active, _tracker, err = _resolved(name, root, resolver=resolver)
    if rc != 0:
        return (rc, "", err)
    p = Path(active)
    if _is_task(p):
        return (0, f"{p}\n", "")
    return (0, f"{p.parent / _QUEUED_DIR / p.name}\n", "")


def activate(name: str, root: str, *, resolver=_AUTO) -> tuple[int, str, str]:
    """Activate a staged plan in whichever layout the resolver returns.

    Flat: the guarded copy `queued-plans/PLAN-<name>.md` → the active
    `PLAN-<name>.md` (Risk #7): refuses with exit 2 + stderr and writes nothing
    when the staged file is absent, an active `PLAN-<name>.md` already exists, or
    a tracker already at the resolved path isn't `queued`. On success the bytes
    are copied verbatim (fresh mtime), a `queued` tracker moves to `active`, and
    the active path is emitted; the staged copy is left in place (activation is a
    copy, not a move).

    Task: the task's tracker must exist and say `queued`; the transition to
    `active` is the activation, and the task's plan path is emitted.

    Pre-flight reconcile (LC-6), both layouts: if the plan declares
    `expected_artifacts` and every one already exists on `main` (under `root`),
    the lane is already shipped — return exit 3 (`SHIPPED_NOOP`) with a benign
    "already shipped — nothing to do" message and change nothing. The guard is
    dormant unless the plan opts in via the frontmatter key, so this is back-compat.
    """
    rc, active_str, tracker, err = _resolved(name, root, resolver=resolver)
    if rc != 0:
        return (rc, "", err)
    active = Path(active_str)
    if _is_task(active):
        return _activate_task(name, root, active, tracker)
    return _activate_flat(name, root, active, tracker)


def _activate_task(name: str, root: str, plan: Path, tracker: str) -> tuple[int, str, str]:
    if not plan.is_file():
        return (2, "", f"[stage_plan] no task plan to activate at {plan}\n")
    shipped, present = preflight_reconcile.already_shipped(plan, root)
    if shipped:
        return (preflight_reconcile.SHIPPED_NOOP, "",
                preflight_reconcile.shipped_message(name, present))
    if not tracker or not Path(tracker).is_file():
        return (2, "", f"[stage_plan] the task at {plan.parent} has no tracker; a staged "
                       f"task is a queued tracker, so there is nothing to activate\n")
    code, status, reason = _tracker_status(tracker)
    if code != 0:
        return (2, "", f"[stage_plan] could not read the task's tracker at {tracker}: {reason}\n")
    if status != "queued":
        return (2, "", f"[stage_plan] the task's tracker at {tracker} is {status}, "
                       f"not queued; refusing to activate\n")
    code, reason = _move_to_active(tracker)
    if code != 0:
        return (2, "", f"[stage_plan] tracker.py did not move {tracker} to active: {reason}\n")
    return (0, f"{plan}\n", "")


def _activate_flat(name: str, root: str, active: Path, tracker: str) -> tuple[int, str, str]:
    staged = active.parent / _QUEUED_DIR / active.name
    if not staged.is_file():
        return (2, "", f"[stage_plan] no staged plan to activate at {staged}\n")
    # Pre-flight reconcile (LC-6): if the staged plan declares the net-new artifacts
    # it ships and every one already exists on `main` (under `root`), the lane is
    # already shipped — refuse the redundant activation with a benign no-op (exit 3,
    # nothing written) rather than spinning up a worker for done work. Read the
    # *staged* frontmatter (the bytes we are about to copy); check existence against
    # the repo `root`, not the harness. Dormant unless the plan opts in.
    shipped, present = preflight_reconcile.already_shipped(staged, root)
    if shipped:
        return (preflight_reconcile.SHIPPED_NOOP, "",
                preflight_reconcile.shipped_message(name, present))
    collision = (2, "",
                 f"[stage_plan] active plan already exists at {active}; "
                 f"refusing to clobber\n")
    # Path-occupancy guard, not target-existence: `os.path.lexists` reports on
    # the link itself, so a *dangling* symlink (which `Path.exists()` misses)
    # counts as a collision and is refused — never followed and written through
    # to a path outside the harness.
    if os.path.lexists(str(active)):
        return collision
    # A tracker already at the resolved path must say `queued` — checked before
    # anything is written. Usually there is none: a staged flat plan gets its
    # tracker at its first /work step, or from the migration that moves it.
    queued_tracker = False
    if tracker and os.path.lexists(tracker):
        code, status, reason = _tracker_status(tracker)
        if code != 0:
            return (2, "", f"[stage_plan] a tracker already sits at {tracker} and could not "
                           f"be read ({reason}); refusing to activate\n")
        if status != "queued":
            return (2, "", f"[stage_plan] a tracker already sits at {tracker} and is {status}, "
                           f"not queued; refusing to activate\n")
        queued_tracker = True
    active.parent.mkdir(parents=True, exist_ok=True)
    data = staged.read_bytes()
    # Atomic, non-following create: O_EXCL fails (EEXIST) if anything — including
    # a symlink — already occupies the path, and never follows a symlink. This is
    # the backstop for the TOCTOU window between the lexists check and the write:
    # a worker that lands the active plan in that window can't be clobbered.
    # `O_BINARY` (Windows-only; `getattr(..., 0)` → no-op on POSIX) keeps the fd
    # in binary mode so `os.write` does NOT translate `\n`→`\r\n` — the copy must
    # be byte-verbatim on every OS, not only the ones whose fd defaults to binary.
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(str(active), flags, 0o644)
    except FileExistsError:
        return collision
    try:
        # Write-all loop: `os.write` may short-write, so drain the buffer fully
        # (the replaced `shutil.copyfile` looped internally) — keeps the copy
        # byte-verbatim even on a short write.
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
    finally:
        os.close(fd)
    if queued_tracker:
        code, reason = _move_to_active(tracker)
        if code != 0:
            return (2, "", f"[stage_plan] activated {active}, but its tracker at {tracker} was "
                           f"not moved to active ({reason}); its first /work step moves it\n")
    return (0, f"{active}\n", "")


# ── CLI ──────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stage_plan.py",
        description="Stage a named plan into the inactive tier, or activate one.",
    )
    p.add_argument("mode", choices=("path", "activate"),
                   help="'path' = print the staging path; 'activate' = promote staged → active")
    p.add_argument("name",
                   help="plan name ('foo', 'PLAN-foo', 'PLAN-foo.md', or a task's "
                        "'042-build-the-brief'); the singleton cannot be staged")
    p.add_argument("--project-root", default=None,
                   help="project root (default: cwd)")
    return p


def main(argv: list[str]) -> int:
    ns = _build_parser().parse_args(argv[1:])
    root = ns.project_root if ns.project_root is not None else os.getcwd()
    fn = staging_path if ns.mode == "path" else activate
    rc, out, err = fn(ns.name, root)
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
