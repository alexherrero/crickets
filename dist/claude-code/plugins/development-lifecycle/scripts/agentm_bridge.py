#!/usr/bin/env python3
"""Merged thin bridge: agentm capability / governing-design / process-seam /
workflow-persona / repo-registry lookups for the development-lifecycle plugin,
in one file (Consolidation arc, CONS-2 task 2; repo-registry added by
PLAN-open-a-project-by-name task 1).

Previously four separate scripts — find_capability.py, find_governing_design.py,
find_process_seam.py, resolve_workflow_persona.py — each independently
re-implemented the same env-var / co-located / conventional-clone path-fallback
cascade (three of the four identically; find_capability's had a fourth tier,
preserved below) and the same subprocess-proxy-with-timeout contract. This file
keeps every one of those four behaviors verbatim, under one dispatcher:

    agentm_bridge.py capability <capability-name> [<version-range>]
    agentm_bridge.py governing-design <file-or-area> [--root DIR] [--include-proposed] [--json]
    agentm_bridge.py process-seam state-path {plan|progress} [--plan SLUG] [--cwd ROOT]
    agentm_bridge.py workflow-persona <step> [--explicit NAME]
    agentm_bridge.py repo-registry list

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

Call-sites: src/development-lifecycle/commands/*.md invoke the capability,
governing-design, and workflow-persona verbs via `python3 .../agentm_bridge.py
<verb> ...`. resolve_plan.py loads this file's process-seam functions
in-process (a crickets-internal load, not a cross-repo import — DC-2 prohibits
importing agentm's process_seam.py directly, not this bridge, which lives here
in crickets). resolve_project.py (open-a-project-by-name) shells to the
repo-registry verb the same way.

Re-audit trigger honored here (development-lifecycle design, 2026-07-10
amendment): a fifth agentm-facing lookup extends this dispatcher rather than
starting a new standalone bridge file — repo-registry is that fifth verb.
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
# process-seam interface instead.

_SEAM_NAME = "process_seam.py"


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
    """process-seam state-path {plan|progress} [--plan SLUG] [--cwd ROOT]"""
    if len(rest) < 2 or rest[0] != "state-path":
        print(
            "usage: agentm_bridge.py process-seam state-path {plan|progress}"
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


# ── dispatcher ───────────────────────────────────────────────────────────────────

_VERBS = {
    "capability": _main_capability,
    "governing-design": _main_governing_design,
    "process-seam": _main_process_seam,
    "workflow-persona": _main_workflow_persona,
    "repo-registry": _main_repo_registry,
}

_USAGE = (
    "usage: agentm_bridge.py {capability|governing-design|process-seam|"
    "workflow-persona|repo-registry} ...\n"
    "  capability <capability-name> [<version-range>]\n"
    "  governing-design <file-or-area> [--root DIR] [--include-proposed] [--json]\n"
    "  process-seam state-path {plan|progress} [--plan SLUG] [--cwd ROOT]\n"
    "  workflow-persona <step> [--explicit NAME]\n"
    "  repo-registry list\n"
)


def main(argv: "list[str]") -> int:
    if len(argv) < 2 or argv[1] not in _VERBS:
        print(_USAGE, file=sys.stderr)
        return 2
    return _VERBS[argv[1]](argv[2:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
