#!/usr/bin/env python3
"""Thin bridge: discovers agentm's capability_resolver and proxies exit codes.

Usage: find_capability.py <capability-name> [<version-range>]
  Exit 0: capability available
  Exit 1: capability unavailable (or agentm resolver not discoverable)
  Exit 2: usage error

Call-site in review.md:
    python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_capability.py" adversarial-review

Post-probe replacement for capability_probe.py (retired with agentm V5-8).
The probe queried plugin slugs (e.g. "code-review installed?"); this script
queries capabilities (e.g. "adversarial-review available?") via agentm's
capability_resolver (the V5-8 capability-keyed resolver, LC-5 cutover).

DC-2: siblings not layers. Discovery is best-effort via path-fallback; when
agentm is absent (resolver undiscoverable), exit 1 (unavailable) — gates-only
degradation, no error or hang.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _find_capability_resolver() -> Path | None:
    """Locate agentm's capability_resolver.py via path-fallback, or None.

    Mirrors the find_agentm_script pattern in wiki-maintenance's
    wiki_watch_config.py — the portable cross-repo seam. Candidates,
    first hit wins:
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


def main(argv: list[str]) -> int:
    if len(argv) < 2 or len(argv) > 3:
        print("usage: find_capability.py <capability-name> [<version-range>]",
              file=sys.stderr)
        return 2

    capability = argv[1]
    version_range = argv[2] if len(argv) == 3 else None

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


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
