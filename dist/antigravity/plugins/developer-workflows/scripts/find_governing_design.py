#!/usr/bin/env python3
"""Thin bridge: discovers agentm's governs_resolver and proxies design-governance queries.

Usage: find_governing_design.py <file-or-area> [--root DIR] [--include-proposed] [--json]
  stdout: the governing design's repo-relative path (or the full dict with --json)
  Exit 0: a living design governs the target
  Exit 1: greenfield / resolver absent / error (graceful-skip)
  Exit 2: usage error

Call-sites (the grounding hooks, design-doc §6):
    python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_governing_design.py" src/foo/bar.py
    python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_governing_design.py" --json memory

DC-2: siblings not layers. Discovery is best-effort via path-fallback; when agentm
is absent (resolver undiscoverable) the bridge exits 1 (greenfield) — the
no-design / gates-only degradation, never an error or hang. Mirrors
find_capability.py / find_process_seam.py exactly.

This bridge targets agentm's governs_resolver.py contract (see
wiki/reference/Design-Governance.md in agentm). The resolver scans
`<root>/wiki/designs/` and **defaults root to agentm's own repo**, so this bridge
passes `--root` = the repo being worked in (default: cwd) — that is how /plan and
/review resolve THIS repo's governing designs rather than agentm's.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_RESOLVER_NAME = "governs_resolver.py"


def find_resolver() -> "Path | None":
    """Locate agentm's governs_resolver.py via path-fallback, or None.

    Mirrors find_process_seam.find_seam — the portable cross-repo seam.
    Candidates, first hit wins:
      1. $AGENTM_SCRIPTS_DIR/governs_resolver.py         (explicit override)
      2. <this-script-dir>/governs_resolver.py           (co-located install)
      3. ~/Antigravity/agentm/scripts/governs_resolver.py (conventional clone)
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
        resolver = find_resolver()
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


def main(argv: "list[str]") -> int:
    ap = argparse.ArgumentParser(
        prog="find_governing_design.py",
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
    try:
        args = ap.parse_args(argv[1:])
    except SystemExit:
        return 2
    if not args.target:
        print("usage: find_governing_design.py <file-or-area> [--root DIR] "
              "[--include-proposed] [--json]", file=sys.stderr)
        return 2

    root = args.root or os.getcwd()
    out, code = run_resolve(
        args.target, root=root,
        include_proposed=args.include_proposed, as_json=args.json,
    )
    if out:
        print(out)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
