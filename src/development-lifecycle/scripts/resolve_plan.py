#!/usr/bin/env python3
"""Resolve the active plan's (PLAN, progress, tracker) paths for the phase loop.

The development-lifecycle phase specs (`/work`, `/plan`, `/review`, `/release`,
`/bugfix`) call this to learn *which* plan a session owns:

    resolve_plan.py [<name>] [--project-root <path>]
    # stdout: "<plan_path>\t<progress_path>\t<tracker_path>"  (one tab-separated line)

**A thin bridge to agentm, and nothing else.** It makes three calls to agentm's
process seam (`process_seam.py state-path plan|progress|tracker`), reassembles
the tab-separated line, and **propagates** exit codes; it never derives a path
of its own. Where the plan lives is agentm's answer: a task's `tasks/<name>/
plan.md` and the files beside it for a project that keeps tasks, or, in a repo
with no vault, the repo-local `.harness/` singleton or flat pair agentm keeps
there (agentm-vault part 15, ruling 8 of crickets task 101). With no seam there
is no plan: development-lifecycle keeps plans through agentm, and composes no
`.harness/` pair of its own.

**Only agentm names a tracker.** The third field is empty when a seam from
before the tracker (agentm-vault plan 09) refuses `state-path tracker`; the pair
still resolves, the exit stays 0, and stderr says why.

**Risk #7 — no silent fallback.** A located seam is authoritative: if it exits
non-zero (a dangling marker or an unsafe slug), the bridge surfaces that exit
and emits **no** pair.

Exit codes:
    0 — resolved; the line is on stdout.
    1 — no plan: no agentm process seam was found, or the seam found no plan
        home for this project. Nothing on stdout; stderr says which.
    2 — loud: dangling marker or unsafe plan slug.
    4 — name the task: a bare call on a project that keeps its plans in tasks
        has no singleton (agentm-vault plan 10). Nothing on stdout; the
        commands ask which task, or propose a name.

Stdlib-only.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

# Load the seam bridge from the same scripts/ directory (crickets-internal; not
# a cross-repo import — DC-2 prohibits importing agentm's process_seam.py
# directly, not agentm_bridge.py which lives here in crickets).
def _load_bridge():
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "agentm_bridge", here / "agentm_bridge.py"
    )
    if not spec or not spec.loader:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return None
    return mod


_bridge = _load_bridge()

# Sentinel: `resolve(seam=_AUTO)` (the default, and what main() uses) locates
# the seam; tests pass `seam=<stub path>` to force a seam, or `seam=None` to
# stand in for an install with no agentm.
_AUTO = object()

# agentm-vault plan 10: a bare call on a project that keeps its plans in
# numbered task directories has no singleton to fall back on, so the seam
# answers this code instead of a path, and this bridge passes it on. Plan 10
# names the code; if it ever names another, this is the one line to change.
NAME_THE_TASK = 4


# ── filename mapping (the naming contract, not resolution logic) ───────────────

def _normalize_plan_name(name: str) -> str:
    """A plan name in any accepted form → the bare slug, or "" for the singleton.

    "" / "PLAN" / "PLAN.md" → ""  (singleton);  "foo" / "PLAN-foo" / "PLAN-foo.md"
    → "foo". This is the same surface the seam accepts; `stage_plan.py` and
    `worktree_marker.py` use it to check a name before asking the seam.

    Step order mirrors agentm's `_normalize_plan_name` exactly — strip `.md`, strip
    the `PLAN-` prefix, *then* test for the singleton — so an edge form like
    "PLAN-PLAN.md" reduces to the singleton on both sides rather than to a named
    "PLAN" plan here and the singleton there. (Parity fix — 2026-06-13 adversarial
    audit finding ML2; golden vectors in test_resolve_plan.py guard the agreement.)
    """
    slug = (name or "").strip()
    if slug.endswith(".md"):
        slug = slug[:-3]
    if slug.startswith("PLAN-"):
        slug = slug[len("PLAN-"):]
    if not slug or slug == "PLAN":
        return ""
    return slug


def _is_safe_plan_slug(slug: str) -> bool:
    """True iff `slug` is a single path component (no traversal, no separators).

    A pre-check for `stage_plan.py` and `worktree_marker.py`; agentm owns the
    richer guard. Rejects "", ".", "..", a NUL byte, and anything containing a path
    separator. (The NUL-byte rejection matches agentm's guard — 2026-06-13
    adversarial audit finding ML2; without it a "foo\x00" slug slipped through
    here but not there.)
    """
    if not slug or slug in (".", ".."):
        return False
    if "/" in slug or "\\" in slug or "\x00" in slug:
        return False
    if os.sep in slug or (os.altsep and os.altsep in slug):
        return False
    return os.path.basename(slug) == slug


# ── the bridge ─────────────────────────────────────────────────────────────────

def _delegate(seam: Path, name: str, root: str) -> tuple[int, str, str]:
    """Delegate to the V5-4 process seam and reassemble (rc, stdout, stderr).

    Three seam calls: `state-path plan`, `state-path progress`, then
    `state-path tracker`. The seam handles named-plan and task resolution when
    agentm is present. A refused plan or progress call passes its exit code on
    with nothing on stdout. A refused tracker call leaves the third field empty
    and keeps exit 0, because only the tracker is missing.
    """
    if _bridge is None:
        return (2, "", "[resolve_plan] internal error: bridge not loaded\n")

    slug = _normalize_plan_name(name)
    extra: list[str] = []
    if slug:
        extra += ["--plan", slug]
    extra += ["--cwd", str(root)]

    plan_out, plan_rc = _bridge.run_state_path("plan", extra, seam=seam)
    if plan_rc != 0:
        if plan_rc == NAME_THE_TASK and not slug:
            return (plan_rc, "", (
                "[resolve_plan] this project keeps its plans in tasks, so a bare "
                "call names no plan: name the task (resolve_plan.py <task-name>)\n"
            ))
        return (plan_rc, "", f"[resolve_plan] seam state-path plan failed (exit {plan_rc})\n")

    prog_out, prog_rc = _bridge.run_state_path("progress", extra, seam=seam)
    if prog_rc != 0:
        return (prog_rc, "", f"[resolve_plan] seam state-path progress failed (exit {prog_rc})\n")

    tracker_out, tracker_rc = _bridge.run_state_path("tracker", extra, seam=seam)
    err = ""
    if tracker_rc != 0:
        tracker_out = ""
        err = (f"[resolve_plan] seam state-path tracker refused (exit {tracker_rc}), "
               "as an agentm from before the tracker does; the tracker field is empty\n")

    return (0, f"{plan_out}\t{prog_out}\t{tracker_out}\n", err)


NO_SEAM = 1


def resolve(name: str, root: str, *, seam=_AUTO, resolver=_AUTO) -> tuple[int, str, str]:
    """Core: ask agentm's process seam for the plan's three paths.

    `seam` defaults to `_AUTO` (locate it through `agentm_bridge.find_seam`). A
    located seam is authoritative — its result, including a non-zero exit, is
    returned as-is. With no seam there is no plan: exit 1, nothing on stdout,
    and stderr says development-lifecycle keeps plans through agentm.

    `resolver` is a backward-compat alias for `seam`.
    """
    if seam is _AUTO and resolver is not _AUTO:
        seam = resolver  # backward-compat alias: resolver= → seam=
    if seam is _AUTO:
        seam = _bridge.find_seam() if _bridge is not None else None
    if seam is None:
        return (NO_SEAM, "", (
            "[resolve_plan] no plan: development-lifecycle keeps its plans through "
            "agentm, and no agentm process seam was found (checked $AGENTM_SCRIPTS_DIR, "
            "this script's own directory, and ~/Antigravity/agentm/scripts). Install "
            "agentm, or set $AGENTM_SCRIPTS_DIR to its scripts/ directory.\n"
        ))
    return _delegate(seam, name, root)


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="resolve_plan.py",
        description="Emit the active plan's (PLAN, progress, tracker) paths for the phase loop.",
    )
    p.add_argument("name", nargs="?", default="",
                   help="plan name ('foo', 'PLAN-foo', 'PLAN-foo.md'); omit for the singleton")
    p.add_argument("--project-root", default=None,
                   help="project root (default: cwd)")
    return p


def main(argv: list[str]) -> int:
    ns = _build_parser().parse_args(argv[1:])
    root = ns.project_root if ns.project_root is not None else os.getcwd()
    rc, out, err = resolve(ns.name, root)
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
