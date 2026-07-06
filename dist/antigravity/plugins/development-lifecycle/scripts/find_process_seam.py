#!/usr/bin/env python3
"""Thin bridge: discovers agentm's process_seam and proxies state-path calls.

Usage: find_process_seam.py state-path {plan|progress} [--plan SLUG] [--cwd ROOT]
  stdout: the resolved absolute path (one line)
  Exit 0: path resolved
  Exit 1: seam absent / graceful-skip / path unresolvable
  Exit 2: usage error

Call-sites:
    python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_process_seam.py" state-path plan
    python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_process_seam.py" state-path progress --plan foo

DC-2: siblings not layers. Discovery is best-effort via path-fallback; when
agentm is absent (seam undiscoverable), exit 1 — the standalone .harness/
fallback is the caller's responsibility (resolve_plan.py handles it). No error
or hang on absent agentm.

V5-4 downstream adoption (LC-5): resolve_plan.py previously bridged to
harness_memory.py directly; this bridge routes through the designed V5-4
process-seam interface instead.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_SEAM_NAME = "process_seam.py"


def find_seam() -> "Path | None":
    """Locate agentm's process_seam.py via path-fallback, or None.

    Mirrors the find_agentm_script pattern in wiki-maintenance's
    wiki_watch_config.py — the portable cross-repo seam. Candidates,
    first hit wins:
      1. $AGENTM_SCRIPTS_DIR/process_seam.py    (explicit override)
      2. <this-script-dir>/process_seam.py      (co-located install)
      3. ~/Antigravity/agentm/scripts/process_seam.py  (conventional clone)
    """
    here = Path(__file__).resolve().parent
    candidates: list[Path] = []
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    if env_dir:
        candidates.append(Path(os.path.expanduser(env_dir)) / _SEAM_NAME)
    candidates.append(here / _SEAM_NAME)
    candidates.append(Path.home() / "Antigravity" / "agentm" / "scripts" / _SEAM_NAME)
    for c in candidates:
        if c.is_file():
            return c.resolve()
    return None


def run_state_path(
    which: str,
    extra_args: "list[str]",
    seam: "Path | None" = None,
) -> "tuple[str, int]":
    """Call the seam's state-path verb; return (stdout_stripped, exit_code).

    Returns ("", 1) when the seam is absent — graceful-skip, never hangs.
    Injectable seam path for tests.
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


def main(argv: "list[str]") -> int:
    if len(argv) < 3 or argv[1] != "state-path":
        print(
            "usage: find_process_seam.py state-path {plan|progress}"
            " [--plan SLUG] [--cwd ROOT]",
            file=sys.stderr,
        )
        return 2

    which = argv[2]
    extra_args = argv[3:]  # forward --plan / --cwd verbatim to the seam

    out, code = run_state_path(which, extra_args)
    if out:
        print(out)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
