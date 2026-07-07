#!/usr/bin/env python3
"""Thin bridge: discovers agentm's workflow_persona_resolver and proxies
workflow-step persona resolution.

Usage: resolve_workflow_persona.py <step> [--explicit NAME]
  stdout: the persona name to wear for this phase
  Exit 0: a persona resolved (explicit override or the step's own default)
  Exit 1: no persona for this step / resolver absent (graceful-skip — the
          phase proceeds with no persona adopted, its own prose unchanged)
  Exit 2: usage error

Call-sites (workflow-step adoption, agentm-persona-activation.md §Selection):
    python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_workflow_persona.py" plan-phase
    python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_workflow_persona.py" work-phase --explicit architect

DC-2: siblings not layers. Discovery is best-effort via path-fallback; when
agentm is absent (resolver undiscoverable) the bridge exits 1 — the phase
proceeds with no persona adopted, never an error or hang. Mirrors
find_governing_design.py / find_capability.py exactly.

This bridge targets agentm's workflow_persona_resolver.py contract (see
wiki/designs/agentm-persona-activation.md in agentm). The phase spec is the
source of truth for a workflow-step adoption — this bridge only proxies the
lookup, it never re-derives the step->persona mapping itself.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_RESOLVER_NAME = "workflow_persona_resolver.py"


def find_resolver() -> "Path | None":
    """Locate agentm's workflow_persona_resolver.py via path-fallback, or None.

    Mirrors find_governing_design.find_resolver — the portable cross-repo seam.
    Candidates, first hit wins:
      1. $AGENTM_SCRIPTS_DIR/workflow_persona_resolver.py         (explicit override)
      2. <this-script-dir>/workflow_persona_resolver.py           (co-located install)
      3. ~/Antigravity/agentm/scripts/workflow_persona_resolver.py (conventional clone)
    """
    here = Path(__file__).resolve().parent
    candidates: list[Path] = []
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    if env_dir:
        candidates.append(Path(os.path.expanduser(env_dir)) / _RESOLVER_NAME)
    candidates.append(here / _RESOLVER_NAME)
    candidates.append(Path.home() / "Antigravity" / "agentm" / "scripts" / _RESOLVER_NAME)
    for c in candidates:
        if c.is_file():
            return c.resolve()
    return None


def run_resolve(
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
        resolver = find_resolver()
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


def main(argv: "list[str]") -> int:
    ap = argparse.ArgumentParser(
        prog="resolve_workflow_persona.py",
        description="Resolve the persona a workflow step wears "
                    "(bridge to agentm's workflow_persona_resolver).",
        add_help=True,
    )
    ap.add_argument("step", nargs="?", help="workflow-step name, e.g. plan-phase")
    ap.add_argument("--explicit", default=None,
                    help="an already-adopted persona name this session wears; "
                         "wins over the step's default when present")
    try:
        args = ap.parse_args(argv[1:])
    except SystemExit:
        return 2
    if not args.step:
        print("usage: resolve_workflow_persona.py <step> [--explicit NAME]",
              file=sys.stderr)
        return 2

    out, code = run_resolve(args.step, explicit=args.explicit)
    if out:
        print(out)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
