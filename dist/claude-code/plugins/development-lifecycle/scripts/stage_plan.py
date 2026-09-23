#!/usr/bin/env python3
"""Two-tier staging for the phase loop (V5-10 sibling #1): a queued task.

The `/plan` command calls this to **stage** a task — write it but leave it inert
— and later **activate** it:

    stage_plan.py path     <name> [--project-root <path>]   # where to write a staged task
    stage_plan.py activate <name> [--project-root <path>]   # queued → active

**Composed onto the resolver — never re-derived.** Where a task lives is agentm's
answer, through `resolve_plan.resolve` → agentm's process seam (`process_seam.py
state-path`), which returns the plan, its progress log and its tracker. A task's
plan is `plan.md` inside its own directory (`tasks/042-build-the-brief/plan.md`),
and a queued task is its own staging tier, kept inert by its `queued` tracker:
`path` prints the task's own `plan.md`, and `activate` moves the tracker to
`active` — nothing is copied. Nothing here composes a layout or creates a
directory.

**Only a task stages** (agentm-vault part 15, crickets task 101). When agentm
answers a flat plan — a repo with no vault keeps its plans in its repo-local
`.harness/` — both verbs refuse (exit 2) before writing anything; write that
plan with `/plan --name` instead. The retired `queued-plans/` tier was a layout
crickets composed. The singleton has no staged form either: an empty name is a
loud refusal (exit 2), before the resolver is consulted.

**`activate` is guarded — no silent fallback (Risk #7).** It refuses (exit 2,
stderr, no write) when the task's plan is missing, it has no tracker, or its
tracker isn't `queued`. A resolver that ran and refused (unsafe slug, dangling
marker, exit 4) or found no agentm (exit 1) propagates its own exit verbatim.

Exit codes (aligned with `resolve_plan.py` so the surface is transparent):
    0 — ok; the task's plan path is on stdout.
    1 — no plan, passed on from the resolver (no agentm process seam).
    2 — loud: empty/unsafe name, a flat answer (staging needs the task layout),
        a missing task plan, a task with no tracker, or a tracker that isn't
        `queued` (the message says which).
    3 — `activate` only: pre-flight reconcile no-op (LC-6) — the plan's declared
        `expected_artifacts` already exist on `main`, so the lane is already
        shipped. Benign (nothing written), not an error. Absent the key, never
        fires.
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


def _not_a_task(plan: Path) -> tuple[int, str, str]:
    return (2, "", f"[stage_plan] staging needs the task layout, and agentm placed this "
                   f"plan at {plan}, not in a task (a repo with no vault keeps its plans "
                   f"in its repo-local .harness/); write it with /plan --name instead\n")


def staging_path(name: str, root: str, *, resolver=_AUTO) -> tuple[int, str, str]:
    """Where a staged task is written: the task's own `plan.md`. Read-only —
    emits the path. A flat answer from agentm is refused (exit 2)."""
    rc, active, _tracker, err = _resolved(name, root, resolver=resolver)
    if rc != 0:
        return (rc, "", err)
    p = Path(active)
    if not _is_task(p):
        return _not_a_task(p)
    return (0, f"{p}\n", "")


def activate(name: str, root: str, *, resolver=_AUTO) -> tuple[int, str, str]:
    """Activate a queued task in place: its tracker must exist and say `queued`,
    and its transition to `active` is the activation. The task's plan path is
    emitted. A flat answer from agentm is refused (exit 2).

    Pre-flight reconcile (LC-6): if the plan declares `expected_artifacts` and
    every one already exists on `main` (under `root`), the lane is already
    shipped — return exit 3 (`SHIPPED_NOOP`) with a benign "already shipped —
    nothing to do" message and change nothing. Dormant unless the plan opts in.
    """
    rc, active_str, tracker, err = _resolved(name, root, resolver=resolver)
    if rc != 0:
        return (rc, "", err)
    plan = Path(active_str)
    if not _is_task(plan):
        return _not_a_task(plan)
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


# ── CLI ──────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stage_plan.py",
        description="Stage a queued task, or activate one.",
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
