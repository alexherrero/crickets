#!/usr/bin/env python3
"""Merged thin bridge: agentm capability / governing-design / process-seam /
workflow-persona / repo-registry / phase-dispatch / tracker / project-brief /
plans lookups for the development-lifecycle plugin, in one file (Consolidation
arc, CONS-2 task 2; repo-registry added by PLAN-open-a-project-by-name task 1;
phase-dispatch added by the Loose Ends follow-on's orphaned-bridge-caller plan;
tracker, project-brief and plans added by PLAN-tracker-commands task 1).

Previously four separate scripts — find_capability.py, find_governing_design.py,
find_process_seam.py, resolve_workflow_persona.py — each independently
re-implemented the same env-var / co-located / conventional-clone path-fallback
cascade (three of the four identically; find_capability's had a fourth tier,
preserved below) and the same subprocess-proxy-with-timeout contract. This file
keeps every one of those four behaviors verbatim, under one dispatcher:

    agentm_bridge.py capability <capability-name> [<version-range>]
    agentm_bridge.py governing-design <file-or-area> [--root DIR] [--include-proposed] [--json]
    agentm_bridge.py process-seam state-path {plan|progress|tracker} [--plan SLUG] [--cwd ROOT]
    agentm_bridge.py workflow-persona <step> [--explicit NAME]
    agentm_bridge.py repo-registry list
    agentm_bridge.py phase-dispatch {post-work|post-release} [--project-root DIR]
    agentm_bridge.py tracker {new|show|transition|check} ...
    agentm_bridge.py project-brief [--cwd DIR]
    agentm_bridge.py plans [--project-root DIR | --project SLUG]

DC-2: siblings not layers. Every verb's discovery is best-effort via
path-fallback; when agentm is absent (the target script undiscoverable) each
verb degrades to its own documented graceful-skip exit code — never an error,
never a hang. Exit 2 is reserved for a usage error, either on the dispatcher
itself (no/unknown verb) or within a verb's own argument parsing:

    capability:        exit 0 available       / 1 unavailable or agentm absent / 2 usage
    governing-design:  exit 0 governed        / 1 greenfield or agentm absent  / 2 usage
    process-seam:      exit 0 resolved        / 1 absent or unresolvable       / 2 usage
    workflow-persona:  exit 0 persona resolved / 1 no persona or agentm absent / 2 usage
    repo-registry:      exit 0 repos listed    / 1 unresolvable or backend absent / 2 usage
    phase-dispatch:     exit 0 always (fired, skipped, or agentm absent — the
                         underlying phase_dispatch() is itself non-blocking
                         by contract) / 2 usage
    tracker:            exit 0 ok / 1 a finding or a refused transition / 2 a
                         usage or I/O error — tracker.py's own codes, passed
                         through with its stdout and stderr / 3 tracker.py
                         not found
    project-brief:      exit 0 a brief printed / 3 no brief, or agentm absent / 2 usage
    plans:              exit 0 listed, possibly nothing / 3 agentm absent or no
                         listing / 2 usage

The tracker, project-brief and plans verbs answer "agentm absent" with exit 3,
not 1, because tracker.py already gives 1 and 2 meanings of its own.

Call-sites: src/development-lifecycle/commands/*.md invoke the capability,
governing-design, and workflow-persona verbs via `python3 .../agentm_bridge.py
<verb> ...`. resolve_plan.py loads this file's process-seam functions
in-process (a crickets-internal load, not a cross-repo import — DC-2 prohibits
importing agentm's process_seam.py directly, not this bridge, which lives here
in crickets). resolve_project.py (open-a-project-by-name) shells to the
repo-registry verb the same way. work.md fires `phase-dispatch post-work`
after each task's commit; release.md fires `phase-dispatch post-release`
after the release lands. The tracker, project-brief and plans verbs serve the
commands' tracker bookkeeping and /orient; scripts load run_tracker,
run_project_brief and run_list_plans in-process, the way resolve_plan.py loads
run_state_path.

Re-audit trigger honored here (development-lifecycle design, 2026-07-10
amendment): a fifth agentm-facing lookup extends this dispatcher rather than
starting a new standalone bridge file — repo-registry was that fifth verb,
phase-dispatch is the sixth, and tracker, project-brief and plans are the
seventh, eighth and ninth.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


# ── shared 3-tier cascade (governing-design / process-seam / workflow-persona) ─
# find_capability's own cascade has a 4th tier and keeps its own function, below.

def _default_candidate_dirs() -> "list[Path]":
    """$AGENTM_SCRIPTS_DIR (explicit override), this script's own directory
    (co-located install), then the conventional ~/Antigravity/agentm/scripts
    clone — first hit (per target filename) wins."""
    here = Path(__file__).resolve().parent
    candidates: list[Path] = []
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    if env_dir:
        candidates.append(Path(os.path.expanduser(env_dir)))
    candidates.append(here)
    candidates.append(Path.home() / "Antigravity" / "agentm" / "scripts")
    return candidates


def _first_candidate(name: str) -> "Path | None":
    for d in _default_candidate_dirs():
        c = d / name
        if c.is_file():
            return c.resolve()
    return None


# ── capability (formerly find_capability.py) ────────────────────────────────────
# Thin bridge: discovers agentm's capability_resolver and proxies exit codes.
#
# Post-probe replacement for capability_probe.py (retired with agentm V5-8).
# The probe queried plugin slugs (e.g. "code-review installed?"); this verb
# queries capabilities (e.g. "adversarial-review available?") via agentm's
# capability_resolver (the V5-8 capability-keyed resolver, LC-5 cutover).

def _find_capability_resolver() -> "Path | None":
    """Locate agentm's capability_resolver.py via path-fallback, or None.

    Candidates, first hit wins:
      1. $AGENTM_SCRIPTS_DIR/capability_resolver.py  (explicit override)
      2. <this-script-dir>/capability_resolver.py    (co-located install)
      3. <this-script-dir>/../lib/install/python/capability_resolver.py
      4. ~/Antigravity/agentm/scripts/capability_resolver.py  (conventional clone)
    """
    here = Path(__file__).resolve().parent
    name = "capability_resolver.py"
    candidates: list[Path] = []
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    if env_dir:
        candidates.append(Path(os.path.expanduser(env_dir)) / name)
    candidates.append(here / name)
    candidates.append(here / ".." / "lib" / "install" / "python" / name)
    candidates.append(Path.home() / "Antigravity" / "agentm" / "scripts" / name)
    for c in candidates:
        if c.is_file():
            return c.resolve()
    return None


def _main_capability(rest: "list[str]") -> int:
    """capability <capability-name> [<version-range>]
    Exit 0: capability available. Exit 1: unavailable, or agentm's resolver is
    undiscoverable (gates-only degradation). Exit 2: usage error."""
    if len(rest) < 1 or len(rest) > 2:
        print("usage: agentm_bridge.py capability <capability-name> [<version-range>]",
              file=sys.stderr)
        return 2

    capability = rest[0]
    version_range = rest[1] if len(rest) == 2 else None

    resolver = _find_capability_resolver()
    if resolver is None:
        return 1  # agentm absent → unavailable → gates-only

    cmd = [sys.executable, str(resolver), capability]
    if version_range:
        cmd.append(version_range)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return 1  # graceful-skip on resolver error
    return res.returncode  # pass through: 0=available, 1=unavailable, 2=usage


# ── governing-design (formerly find_governing_design.py) ───────────────────────
# Thin bridge: discovers agentm's governs_resolver and proxies design-governance
# queries. Targets agentm's governs_resolver.py contract (see
# wiki/reference/Design-Governance.md in agentm). The resolver scans
# `<root>/wiki/designs/` and **defaults root to agentm's own repo**, so this
# verb passes `--root` = the repo being worked in (default: cwd) — that is how
# /plan and /review resolve THIS repo's governing designs rather than agentm's.

_GOVERNS_RESOLVER_NAME = "governs_resolver.py"


def find_governing_design_resolver() -> "Path | None":
    """Locate agentm's governs_resolver.py via path-fallback, or None.

    Candidates, first hit wins:
      1. $AGENTM_SCRIPTS_DIR/governs_resolver.py         (explicit override)
      2. <this-script-dir>/governs_resolver.py           (co-located install)
      3. ~/Antigravity/agentm/scripts/governs_resolver.py (conventional clone)
    """
    return _first_candidate(_GOVERNS_RESOLVER_NAME)


def run_governing_design_resolve(
    target: str,
    *,
    root: "str | None" = None,
    include_proposed: bool = False,
    as_json: bool = False,
    resolver: "Path | None" = None,
) -> "tuple[str, int]":
    """Call governs_resolver on `target`; return (stdout_stripped, exit_code).

    Returns ("", 1) when the resolver is absent — graceful-skip, never hangs.
    `root` is forwarded as `--root` so the resolver scans THIS repo's
    wiki/designs/ (the CLI layer defaults it to cwd). Injectable resolver path
    for tests.
    """
    if resolver is None:
        resolver = find_governing_design_resolver()
    if resolver is None or not Path(resolver).is_file():
        return ("", 1)  # absent / stale path → graceful-skip (greenfield)
    cmd = [sys.executable, str(resolver)]
    if as_json:
        cmd.append("--json")
    if root:
        cmd += ["--root", str(root)]
    if include_proposed:
        cmd.append("--include-proposed")
    cmd.append(target)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (res.stdout.strip(), res.returncode)
    except (OSError, subprocess.SubprocessError):
        return ("", 1)  # graceful-skip on resolver error


def _build_governing_design_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="agentm_bridge.py governing-design",
        description="Resolve the living design that governs a file or area "
                    "(bridge to agentm's governs_resolver).",
        add_help=True,
    )
    ap.add_argument("target", nargs="?", help="repo-relative file path or area name")
    ap.add_argument("--root", default=None,
                    help="repo root to resolve against (default: cwd)")
    ap.add_argument("--include-proposed", action="store_true",
                    help="also index status: proposed designs (default: launched only)")
    ap.add_argument("--json", action="store_true",
                    help="print the full result dict instead of the bare path")
    return ap


def _main_governing_design(rest: "list[str]") -> int:
    ap = _build_governing_design_parser()
    try:
        args = ap.parse_args(rest)
    except SystemExit:
        return 2
    if not args.target:
        print("usage: agentm_bridge.py governing-design <file-or-area> [--root DIR] "
              "[--include-proposed] [--json]", file=sys.stderr)
        return 2

    root = args.root or os.getcwd()
    out, code = run_governing_design_resolve(
        args.target, root=root,
        include_proposed=args.include_proposed, as_json=args.json,
    )
    if out:
        print(out)
    return code


# ── process-seam (formerly find_process_seam.py) ───────────────────────────────
# Thin bridge: discovers agentm's process_seam and proxies state-path calls.
#
# V5-4 downstream adoption (LC-5): resolve_plan.py previously bridged to
# harness_memory.py directly; it now routes through this designed V5-4
# process-seam interface instead. `state-path tracker` (agentm-vault plan 09)
# names a plan's tracker beside its plan and progress log; a seam from before
# the tracker refuses it with its own usage error, exit 2, which passes through.

_SEAM_NAME = "process_seam.py"
_STATE_PATH_KINDS = ("plan", "progress", "tracker")


def find_seam() -> "Path | None":
    """Locate agentm's process_seam.py via path-fallback, or None.

    Candidates, first hit wins:
      1. $AGENTM_SCRIPTS_DIR/process_seam.py    (explicit override)
      2. <this-script-dir>/process_seam.py      (co-located install)
      3. ~/Antigravity/agentm/scripts/process_seam.py  (conventional clone)
    """
    return _first_candidate(_SEAM_NAME)


def run_state_path(
    which: str,
    extra_args: "list[str]",
    seam: "Path | None" = None,
) -> "tuple[str, int]":
    """Call the seam's state-path verb; return (stdout_stripped, exit_code).

    Returns ("", 1) when the seam is absent — graceful-skip, never hangs.
    Injectable seam path for tests (and for resolve_plan.py's own delegation).
    """
    if seam is None:
        seam = find_seam()
    if seam is None:
        return ("", 1)
    cmd = [sys.executable, str(seam), "state-path", which] + list(extra_args)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (res.stdout.strip(), res.returncode)
    except (OSError, subprocess.SubprocessError):
        return ("", 1)  # graceful-skip on seam error


def _main_process_seam(rest: "list[str]") -> int:
    """process-seam state-path {plan|progress|tracker} [--plan SLUG] [--cwd ROOT]"""
    if len(rest) < 2 or rest[0] != "state-path" or rest[1] not in _STATE_PATH_KINDS:
        print(
            "usage: agentm_bridge.py process-seam state-path {plan|progress|tracker}"
            " [--plan SLUG] [--cwd ROOT]",
            file=sys.stderr,
        )
        return 2

    which = rest[1]
    extra_args = rest[2:]  # forward --plan / --cwd verbatim to the seam

    out, code = run_state_path(which, extra_args)
    if out:
        print(out)
    return code


# ── workflow-persona (formerly resolve_workflow_persona.py) ────────────────────
# Thin bridge: discovers agentm's workflow_persona_resolver and proxies
# workflow-step persona resolution. Targets agentm's workflow_persona_resolver.py
# contract (see wiki/designs/agentm-persona-activation.md in agentm). The phase
# spec is the source of truth for a workflow-step adoption — this verb only
# proxies the lookup, it never re-derives the step->persona mapping itself.

_WORKFLOW_PERSONA_RESOLVER_NAME = "workflow_persona_resolver.py"


def find_workflow_persona_resolver() -> "Path | None":
    """Locate agentm's workflow_persona_resolver.py via path-fallback, or None.

    Candidates, first hit wins:
      1. $AGENTM_SCRIPTS_DIR/workflow_persona_resolver.py         (explicit override)
      2. <this-script-dir>/workflow_persona_resolver.py           (co-located install)
      3. ~/Antigravity/agentm/scripts/workflow_persona_resolver.py (conventional clone)
    """
    return _first_candidate(_WORKFLOW_PERSONA_RESOLVER_NAME)


def run_workflow_persona_resolve(
    step: str,
    *,
    explicit: "str | None" = None,
    resolver: "Path | None" = None,
) -> "tuple[str, int]":
    """Call workflow_persona_resolver on `step`; return (stdout_stripped, exit_code).

    Returns ("", 1) when the resolver is absent — graceful-skip, never hangs.
    Injectable resolver path for tests.
    """
    if resolver is None:
        resolver = find_workflow_persona_resolver()
    if resolver is None or not Path(resolver).is_file():
        return ("", 1)  # absent / stale path → graceful-skip (no persona adopted)
    cmd = [sys.executable, str(resolver)]
    if explicit:
        cmd += ["--explicit", explicit]
    cmd.append(step)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (res.stdout.strip(), res.returncode)
    except (OSError, subprocess.SubprocessError):
        return ("", 1)  # graceful-skip on resolver error


def _build_workflow_persona_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="agentm_bridge.py workflow-persona",
        description="Resolve the persona a workflow step wears "
                    "(bridge to agentm's workflow_persona_resolver).",
        add_help=True,
    )
    ap.add_argument("step", nargs="?", help="workflow-step name, e.g. plan-phase")
    ap.add_argument("--explicit", default=None,
                    help="an already-adopted persona name this session wears; "
                         "wins over the step's default when present")
    return ap


def _main_workflow_persona(rest: "list[str]") -> int:
    ap = _build_workflow_persona_parser()
    try:
        args = ap.parse_args(rest)
    except SystemExit:
        return 2
    if not args.step:
        print("usage: agentm_bridge.py workflow-persona <step> [--explicit NAME]",
              file=sys.stderr)
        return 2

    out, code = run_workflow_persona_resolve(args.step, explicit=args.explicit)
    if out:
        print(out)
    return code


# ── repo-registry (new, PLAN-open-a-project-by-name task 1) ────────────────────
# Thin bridge: discovers agentm's repo_registry.py and proxies its `list`
# subcommand. Targets agentm's scripts/repo_registry.py contract (vault-backed
# `_meta/repos.json`, registered agent-aware repos: slug/root_path/wiki_path).
# repo_registry.py's own `list` verb already emits its documented graceful-skip
# envelope (`{"skipped": true, "reason": ...}`, exit 1) when its storage backend
# is unavailable, so this verb proxies stdout + exit code verbatim rather than
# re-wrapping that contract — the same shape as governing-design/process-seam.

_REPO_REGISTRY_NAME = "repo_registry.py"


def find_repo_registry() -> "Path | None":
    """Locate agentm's repo_registry.py via path-fallback, or None.

    Candidates, first hit wins:
      1. $AGENTM_SCRIPTS_DIR/repo_registry.py         (explicit override)
      2. <this-script-dir>/repo_registry.py           (co-located install)
      3. ~/Antigravity/agentm/scripts/repo_registry.py (conventional clone)
    """
    return _first_candidate(_REPO_REGISTRY_NAME)


def run_repo_registry_list(*, registry: "Path | None" = None) -> "tuple[str, int]":
    """Call repo_registry.py's `list` subcommand; return (stdout_stripped, exit_code).

    Returns ("", 1) when repo_registry.py is undiscoverable — graceful-skip,
    never hangs. When found, repo_registry.py's own exit code/stdout (0 +
    `{"repos": [...]}`, or 1 + a skip envelope on an unavailable backend) pass
    through verbatim. Injectable registry path for tests.
    """
    if registry is None:
        registry = find_repo_registry()
    if registry is None or not Path(registry).is_file():
        return ("", 1)  # absent → graceful-skip (no repos known)
    cmd = [sys.executable, str(registry), "list"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (res.stdout.strip(), res.returncode)
    except (OSError, subprocess.SubprocessError):
        return ("", 1)  # graceful-skip on registry error


def _build_repo_registry_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="agentm_bridge.py repo-registry",
        description="List agent-aware registered repos (bridge to agentm's repo_registry.py).",
        add_help=True,
    )
    ap.add_argument("subcommand", nargs="?", choices=["list"], help="only 'list' is supported")
    return ap


def _main_repo_registry(rest: "list[str]") -> int:
    ap = _build_repo_registry_parser()
    try:
        args = ap.parse_args(rest)
    except SystemExit:
        return 2
    if not args.subcommand:
        print("usage: agentm_bridge.py repo-registry list", file=sys.stderr)
        return 2

    out, code = run_repo_registry_list()
    if out:
        print(out)
    return code


# ── phase-dispatch (new, Loose Ends follow-on — the orphaned bridge caller) ────
# Thin bridge: discovers agentm's harness_memory.py and proxies its
# `phase-dispatch` CLI verb (the V5-5 orchestration bridge, `[LC-3]`). This is
# the caller wiki/explanation/Auto-Orchestration.md said didn't exist: /work
# fires `post-work` after each task's commit, /release fires `post-release`
# once the release lands — both dedup-guarded and cooldown-gated entirely on
# agentm's own side (`orchestration_phase.py`), so this bridge verb has
# nothing to gate beyond discovery. `phase_dispatch()` itself is documented as
# "always returns 0 — a phase is never wedged by orchestration errors", so
# this verb mirrors that non-blocking contract rather than inventing a
# 0/1-available/unavailable distinction the underlying function doesn't have.

_HARNESS_MEMORY_NAME = "harness_memory.py"


def find_harness_memory() -> "Path | None":
    """Locate agentm's harness_memory.py via path-fallback, or None.

    Candidates, first hit wins:
      1. $AGENTM_SCRIPTS_DIR/harness_memory.py         (explicit override)
      2. <this-script-dir>/harness_memory.py           (co-located install)
      3. ~/Antigravity/agentm/scripts/harness_memory.py (conventional clone)
    """
    return _first_candidate(_HARNESS_MEMORY_NAME)


def run_phase_dispatch(
    phase: str, *, project_root: "str | None" = None,
    harness_memory: "Path | None" = None,
) -> "tuple[str, int]":
    """Call harness_memory.py's `phase-dispatch` verb; return (stdout_stripped, exit_code).

    Returns ("", 0) when harness_memory.py is undiscoverable, or on any
    subprocess error — graceful-skip, matching `phase_dispatch()`'s own
    non-blocking contract (always 0) rather than the 1-unavailable shape the
    other verbs use, since the underlying function already folds "agentm
    absent" into a clean no-op. Injectable harness_memory path for tests.
    """
    if harness_memory is None:
        harness_memory = find_harness_memory()
    if harness_memory is None or not Path(harness_memory).is_file():
        return ("", 0)
    cmd = [sys.executable, str(harness_memory), "phase-dispatch", phase]
    if project_root:
        cmd += ["--project-root", project_root]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=200)
        return (res.stdout.strip(), res.returncode)
    except (OSError, subprocess.SubprocessError):
        return ("", 0)  # graceful-skip on dispatch error — never blocks the phase


def _build_phase_dispatch_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="agentm_bridge.py phase-dispatch",
        description="Fire a named phase-boundary chain through agentm's kernel "
                    "(bridge to harness_memory.py's phase_dispatch).",
        add_help=True,
    )
    ap.add_argument("phase", nargs="?", choices=["post-work", "post-release"],
                    help="which phase boundary just fired")
    ap.add_argument("--project-root", default=None,
                    help="repo root to dispatch against (default: cwd)")
    return ap


def _main_phase_dispatch(rest: "list[str]") -> int:
    ap = _build_phase_dispatch_parser()
    try:
        args = ap.parse_args(rest)
    except SystemExit:
        return 2
    if not args.phase:
        print("usage: agentm_bridge.py phase-dispatch {post-work|post-release} "
              "[--project-root DIR]", file=sys.stderr)
        return 2

    out, code = run_phase_dispatch(args.phase, project_root=args.project_root)
    if out:
        print(out)
    return code


# ── text-carrying runs (tracker / project-brief / plans) ────────────────────────
# These three verbs carry free text (a plan's title, a tracker's State, a brief)
# and paths that can hold any character, so their runs are UTF-8 both ways on
# every OS instead of the platform's locale encoding, and a byte that won't
# decode is replaced rather than raised.

def _run_utf8(cmd: "list[str]", *, timeout: int = 30) -> "subprocess.CompletedProcess":
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        cmd, capture_output=True, encoding="utf-8", errors="replace",
        env=env, timeout=timeout,
    )


# ── tracker (new, PLAN-tracker-commands task 1) ─────────────────────────────────
# Thin bridge: discovers agentm's scripts/tracker.py and proxies its four
# subcommands. tracker.py owns the tracker's one schema (agentm-vault § Projects
# and tasks) and is the only writer of a tracker: crickets composes the
# arguments and reads `show`'s JSON, and never renders, parses or edits tracker
# text. So this verb hands argv over untouched and gives back tracker.py's exit
# code, stdout and stderr as they came: 0 ok, 1 a finding or a refused
# transition, 2 a usage or I/O error. It adds one code of its own, 3, for
# "there is no tracker.py to run", which a caller reads as "carry on without a
# tracker".

_TRACKER_NAME = "tracker.py"
_TRACKER_SUBCOMMANDS = ("new", "show", "transition", "check")
TRACKER_UNAVAILABLE = 3


def find_tracker() -> "Path | None":
    """Locate agentm's tracker.py via path-fallback, or None.

    Candidates, first hit wins:
      1. $AGENTM_SCRIPTS_DIR/tracker.py         (explicit override)
      2. <this-script-dir>/tracker.py           (co-located install)
      3. ~/Antigravity/agentm/scripts/tracker.py (conventional clone)
    """
    return _first_candidate(_TRACKER_NAME)


def run_tracker(
    args: "list[str]", *, tracker: "Path | None" = None,
) -> "tuple[int, str, str]":
    """Run `tracker.py <args>`; return (exit_code, stdout, stderr) as they came.

    Exit 3, with a note on stderr, when tracker.py can't be found or can't be
    started at all. Injectable tracker path for tests.
    """
    if tracker is None:
        tracker = find_tracker()
    if tracker is None or not Path(tracker).is_file():
        return (TRACKER_UNAVAILABLE, "",
                "[agentm_bridge] tracker: agentm's scripts/tracker.py was not found\n")
    try:
        res = _run_utf8([sys.executable, str(tracker)] + [str(a) for a in args])
    except (OSError, subprocess.SubprocessError) as exc:
        return (TRACKER_UNAVAILABLE, "",
                f"[agentm_bridge] tracker: {tracker} could not be run ({exc})\n")
    return (res.returncode, res.stdout, res.stderr)


def _main_tracker(rest: "list[str]") -> int:
    """tracker {new|show|transition|check} ..."""
    if not rest or rest[0] not in _TRACKER_SUBCOMMANDS:
        print("usage: agentm_bridge.py tracker {new|show|transition|check} ...",
              file=sys.stderr)
        return 2
    code, out, err = run_tracker(rest)
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    return code


# ── project-brief (new, PLAN-tracker-commands task 1) ───────────────────────────
# Thin bridge: discovers agentm's scripts/project_brief.py (the opening brief:
# where the bound project and task stand, in under twenty lines) and proxies it.
# project_brief.py exits 0 with a brief and 3 with none. This verb keeps both
# answers and folds every other outcome into 3 as well (agentm absent, a run
# that can't start, any other exit, a 0 that printed nothing), because a
# missing brief is never a reason to stop.

_PROJECT_BRIEF_NAME = "project_brief.py"
NO_BRIEF = 3


def find_project_brief() -> "Path | None":
    """Locate agentm's project_brief.py via path-fallback, or None.

    Candidates, first hit wins:
      1. $AGENTM_SCRIPTS_DIR/project_brief.py         (explicit override)
      2. <this-script-dir>/project_brief.py           (co-located install)
      3. ~/Antigravity/agentm/scripts/project_brief.py (conventional clone)
    """
    return _first_candidate(_PROJECT_BRIEF_NAME)


def run_project_brief(
    cwd: "str | os.PathLike | None", *, brief: "Path | None" = None,
) -> "tuple[int, str]":
    """Run project_brief.py for the session directory `cwd`; return (0, brief)
    or (3, ""). With `cwd` None the brief uses this process's directory.
    Injectable brief path for tests.
    """
    if brief is None:
        brief = find_project_brief()
    if brief is None or not Path(brief).is_file():
        return (NO_BRIEF, "")
    cmd = [sys.executable, str(brief)]
    if cwd:
        cmd += ["--cwd", str(cwd)]
    try:
        res = _run_utf8(cmd)
    except (OSError, subprocess.SubprocessError):
        return (NO_BRIEF, "")
    text = res.stdout.rstrip()
    if res.returncode != 0 or not text:
        return (NO_BRIEF, "")
    return (0, text)


def _build_project_brief_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="agentm_bridge.py project-brief",
        description="Print the opening brief for the bound project and task "
                    "(bridge to agentm's project_brief.py).",
        add_help=True,
    )
    ap.add_argument("--cwd", default=None,
                    help="the session's directory (default: cwd)")
    return ap


def _main_project_brief(rest: "list[str]") -> int:
    ap = _build_project_brief_parser()
    try:
        args = ap.parse_args(rest)
    except SystemExit:
        return 2
    code, out = run_project_brief(args.cwd or os.getcwd())
    if out:
        print(out)
    return code


# ── plans (new, PLAN-tracker-commands task 1) ───────────────────────────────────
# Lists every active plan agentm knows for a project root, each with its
# progress log and its tracker: one `harness_memory.py list-plans`, then one
# `resolve-active-plan --with-tracker --plan <name>` per plan. The name is how
# agentm's resolver finds that plan again: the file name in the flat layout
# (`PLAN.md`, `PLAN-foo.md`), the directory's name in the task layout
# (`tasks/042-build-the-brief/plan.md` is `042-build-the-brief`). Every path
# comes from agentm; crickets composes none of them.
#
# Two answers stay partial rather than wrong. An agentm from before the tracker
# (plan 09) refuses `--with-tracker`, so its rows carry the pair and an empty
# tracker field. And a plan the resolver refuses, or resolves to a different
# plan (a slug with both a task and a flat pair, where the task wins), keeps its
# own path with empty progress and tracker fields: still listed, and never
# paired with another plan's files.
#
# `--project SLUG` asks the same two verbs about a project with no repo
# checkout (crickets task 101, ruling 9): `list-plans --project`, then
# `resolve-active-plan --project`. An agentm without the second refuses the
# flag, and its rows stay partial the same way.

PLANS_UNAVAILABLE = 3


def _resolver_name(plan: str) -> str:
    """The name agentm's resolver takes for a plan path list-plans printed."""
    p = Path(plan)
    return p.parent.name if p.name == "plan.md" else p.name


def _resolve_listed_plan(
    harness_memory: Path, where: "list[str]", plan: str,
) -> "tuple[str, str, str]":
    cmd = [sys.executable, str(harness_memory), "resolve-active-plan",
           "--plan", _resolver_name(plan), *where]
    try:
        res = _run_utf8(cmd + ["--with-tracker"])
        if res.returncode == 2 and "--with-tracker" in res.stderr:
            res = _run_utf8(cmd)  # an agentm from before the tracker
    except (OSError, subprocess.SubprocessError):
        return (plan, "", "")
    fields = res.stdout.strip().split("\t")
    if res.returncode != 0 or len(fields) < 2 or Path(fields[0]) != Path(plan):
        return (plan, "", "")
    return (plan, fields[1], fields[2] if len(fields) > 2 else "")


def run_list_plans(
    root: "str | os.PathLike | None" = None, *, project: "str | None" = None,
    harness_memory: "Path | None" = None,
) -> "tuple[int, list[tuple[str, str, str]]]":
    """Every active plan of a project, as (plan, progress, tracker) rows in
    agentm's listing order: the project bound to checkout `root` (default: the
    cwd), or, with `project`, the one named by that slug. Returns (0, rows), or
    (3, []) when agentm is absent or gives no listing. Injectable harness_memory
    path for tests.
    """
    if harness_memory is None:
        harness_memory = find_harness_memory()
    if harness_memory is None or not Path(harness_memory).is_file():
        return (PLANS_UNAVAILABLE, [])
    if project is not None:
        where = ["--project", str(project)]
    else:
        where = ["--project-root", str(root if root is not None else os.getcwd())]
    try:
        listed = _run_utf8([sys.executable, str(harness_memory), "list-plans", *where])
    except (OSError, subprocess.SubprocessError):
        return (PLANS_UNAVAILABLE, [])
    if listed.returncode != 0:
        return (PLANS_UNAVAILABLE, [])
    rows = []
    for line in listed.stdout.splitlines():
        plan = line.strip()
        if plan and not plan.startswith("active-binding="):
            rows.append(_resolve_listed_plan(Path(harness_memory), where, plan))
    return (0, rows)


def _build_plans_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="agentm_bridge.py plans",
        description="List every active plan with its progress log and tracker "
                    "(bridge to agentm's list-plans and resolve-active-plan).",
        add_help=True,
    )
    where = ap.add_mutually_exclusive_group()
    where.add_argument("--project-root", default=None,
                       help="project root to list plans for (default: cwd)")
    where.add_argument("--project", default=None, metavar="SLUG",
                       help="a project named by slug, for one with no repo checkout")
    return ap


def _main_plans(rest: "list[str]") -> int:
    ap = _build_plans_parser()
    try:
        args = ap.parse_args(rest)
    except SystemExit:
        return 2
    code, rows = run_list_plans(args.project_root, project=args.project)
    for plan, progress, tracker in rows:
        print(f"{plan}\t{progress}\t{tracker}")
        if not progress:
            print(f"[agentm_bridge] plans: agentm did not resolve {plan}; its "
                  "progress and tracker fields are empty", file=sys.stderr)
    return code


# ── dispatcher ───────────────────────────────────────────────────────────────────

_VERBS = {
    "capability": _main_capability,
    "governing-design": _main_governing_design,
    "process-seam": _main_process_seam,
    "workflow-persona": _main_workflow_persona,
    "repo-registry": _main_repo_registry,
    "phase-dispatch": _main_phase_dispatch,
    "tracker": _main_tracker,
    "project-brief": _main_project_brief,
    "plans": _main_plans,
}

_USAGE = (
    "usage: agentm_bridge.py {capability|governing-design|process-seam|"
    "workflow-persona|repo-registry|phase-dispatch|tracker|project-brief|plans} ...\n"
    "  capability <capability-name> [<version-range>]\n"
    "  governing-design <file-or-area> [--root DIR] [--include-proposed] [--json]\n"
    "  process-seam state-path {plan|progress|tracker} [--plan SLUG] [--cwd ROOT]\n"
    "  workflow-persona <step> [--explicit NAME]\n"
    "  repo-registry list\n"
    "  phase-dispatch {post-work|post-release} [--project-root DIR]\n"
    "  tracker {new|show|transition|check} ...\n"
    "  project-brief [--cwd DIR]\n"
    "  plans [--project-root DIR | --project SLUG]\n"
)


def main(argv: "list[str]") -> int:
    if len(argv) < 2 or argv[1] not in _VERBS:
        print(_USAGE, file=sys.stderr)
        return 2
    return _VERBS[argv[1]](argv[2:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
