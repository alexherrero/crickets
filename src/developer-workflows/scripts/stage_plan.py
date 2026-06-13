#!/usr/bin/env python3
"""Two-tier named-plan staging for the phase loop (V5-10 sibling #1).

The `/plan` command calls this to **stage** a named plan into an inactive tier
and later **activate** it. Two verbs, one staging dir (`<_harness>/queued-plans/`):

    stage_plan.py path     <name> [--project-root <path>]   # where to write a staged plan
    stage_plan.py activate <name> [--project-root <path>]   # promote staged → active

**Why a second tier.** The shipped `--name` writer (`resolve_plan.py`) targets the
*active* pair `<_harness>/PLAN-<name>.md` / `progress-<name>.md` directly — the
path `/work --name` and agentm's `resolve_active_plan` read. Staging adds an
**inactive** tier: a coordinator pre-authors a batch of worker plans into
`queued-plans/` (inert — invisible to `/work` and `/queue-status-lite`), then
activates them one at a time as workers pick them up. The active tier and the
one-tier `--name` write are unchanged; this is purely additive.

**Composed onto the resolver — never re-derived.** The active-pair resolution
(precedence, slug-safety, vault redirection, the dangling-marker loud-error) is
owned by `resolve_plan.resolve` → agentm's `resolve-active-plan` verb. We call it,
take the resolved *active* `PLAN-<name>.md`, and compose `queued-plans/` onto its
parent. We never re-derive the `_harness/` location or the vault redirect: if a
future resolver moves the active plan, the staging path tracks it automatically.
`resolve_plan` stays a pure resolver — the side-effecting copy lives only here.

**Staging is named-only.** The singleton `PLAN.md` *is* the active default; there
is nothing to stage for it. An empty/singleton name is a loud refusal (exit 2),
before the resolver is even consulted.

**`activate` is guarded — no clobber, no silent fallback (Risk #7).** It refuses
(exit 2, stderr, no write) when the staged file is missing *or* an active
`PLAN-<name>.md` already exists. A resolver that ran and refused (unsafe slug,
dangling marker) propagates its own non-zero exit verbatim — never a singleton
fallback.

Exit codes (aligned with `resolve_plan.py` so the surface is transparent):
    0 — ok; the resolved path (or the activated path) is on stdout.
    1 — graceful-skip propagated from the resolver (agentm present, no `_harness/`).
    2 — loud: empty/unsafe name, missing staged plan, or active-plan collision.

Stdlib-only; mirrors `resolve_plan.py`'s shape (pure core + injectable resolver).
"""
from __future__ import annotations

import argparse
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

_AUTO = resolve_plan._AUTO

# The inactive staging tier, flat under the resolved `_harness/` (crickets
# convention — no per-design subdir). Stage as `<_harness>/queued-plans/PLAN-<n>.md`.
_QUEUED_DIR = "queued-plans"


# ── core (pure but for the injected resolver / a single guarded copy) ────────────

def _active_plan_path(name: str, root: str, *, resolver) -> tuple[int, str, str]:
    """Resolve the *active* `PLAN-<name>.md` via the bridge, named-only.

    Returns (0, plan_path, "") on success, else the resolver's non-zero exit and
    stderr verbatim — or a loud (2, "", msg) when `name` is empty/singleton (there
    is no staged form of the singleton). The progress half of the pair is dropped:
    only `PLAN-<name>.md` is staged.
    """
    if not resolve_plan._normalize_plan_name(name):
        return (2, "", f"[stage_plan] staging requires a named plan (got {name!r})\n")
    rc, out, err = resolve_plan.resolve(name, root, resolver=resolver)
    if rc != 0:
        return (rc, "", err)
    plan_path = out.split("\t", 1)[0].strip()
    return (0, plan_path, "")


def staging_path(name: str, root: str, *, resolver=_AUTO) -> tuple[int, str, str]:
    """Resolve the inactive staging path `<_harness>/queued-plans/PLAN-<name>.md`.

    Composed onto the resolver's active `PLAN-<name>.md`: same `_harness/` parent,
    same filename, under the `queued-plans/` subdir. Read-only — emits the path.
    """
    rc, active, err = _active_plan_path(name, root, resolver=resolver)
    if rc != 0:
        return (rc, "", err)
    p = Path(active)
    staged = p.parent / _QUEUED_DIR / p.name
    return (0, f"{staged}\n", "")


def activate(name: str, root: str, *, resolver=_AUTO) -> tuple[int, str, str]:
    """Promote `queued-plans/PLAN-<name>.md` → the active `PLAN-<name>.md`.

    Guarded copy (Risk #7): refuses with exit 2 + stderr and writes nothing when
    the staged file is absent or an active `PLAN-<name>.md` already exists. On
    success the bytes are copied verbatim (fresh mtime) and the active path is
    emitted; the staged copy is left in place (activation is a copy, not a move).
    """
    rc, active_str, err = _active_plan_path(name, root, resolver=resolver)
    if rc != 0:
        return (rc, "", err)
    active = Path(active_str)
    staged = active.parent / _QUEUED_DIR / active.name
    if not staged.is_file():
        return (2, "", f"[stage_plan] no staged plan to activate at {staged}\n")
    collision = (2, "",
                 f"[stage_plan] active plan already exists at {active}; "
                 f"refusing to clobber\n")
    # Path-occupancy guard, not target-existence: `os.path.lexists` reports on
    # the link itself, so a *dangling* symlink (which `Path.exists()` misses)
    # counts as a collision and is refused — never followed and written through
    # to a path outside the harness.
    if os.path.lexists(str(active)):
        return collision
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
                   help="plan name ('foo', 'PLAN-foo', 'PLAN-foo.md'); the singleton cannot be staged")
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
