#!/usr/bin/env python3
"""Read-only dashboard of every active plan of a project — the coordinator's glance.

The development-lifecycle `/queue-status-lite` command calls this to list, for
each active plan of the project the cwd is bound to (its tasks, or in a repo with
no vault its repo-local plans), the plan's status and the most-recent entry of
its progress log. **Read-only by contract** (the V5-10 design call): no claim
arbitration, no leases, no writes — the human is the arbiter.

    queue_status.py
    # stdout: a deterministic, human-scannable dashboard block

A thin **bridge** to agentm's `queue_status_lite.py`, the one owner of the
enumeration and the render: which plans a project has, where they live, and
their status from each tracker. The bridge runs it from the cwd and re-emits its
output verbatim. crickets enumerates nothing itself (agentm-vault part 15): with
no agentm there is no plan list, and the bridge says so in one line.

A status read, never a gate: always exits 0 in normal use.
"""
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent

# Same interpreter that runs this bridge runs the agentm reader — avoids a PATH
# `python3` that differs from the one development-lifecycle was launched with.
_PY = sys.executable or "python3"

# Sentinel: `run(reader=_AUTO)` (the default, and what main() uses) locates
# agentm's reader; tests pass `reader=<stub path>` or `reader=None`.
_AUTO = object()

_READER_NAME = "queue_status_lite.py"
NO_AGENTM = ("No plan list: development-lifecycle lists a project's plans through "
             "agentm, and no agentm checkout was found.\n")


def locate_reader() -> "Path | None":
    """agentm's `queue_status_lite.py`, found the way every other agentm script
    is (`agentm_bridge._first_candidate`: `$AGENTM_SCRIPTS_DIR`, co-located, the
    conventional `~/Antigravity/agentm/scripts`), or None."""
    spec = importlib.util.spec_from_file_location("agentm_bridge", _HERE / "agentm_bridge.py")
    if not spec or not spec.loader:
        return None
    bridge = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(bridge)
    except Exception:
        return None
    return bridge._first_candidate(_READER_NAME)


def run(*, reader=_AUTO) -> "tuple[int, str, str]":
    """Run agentm's reader from the cwd and pass (rc, stdout, stderr) through.

    With no reader, one line and exit 0 — a status read never fails the caller.
    A reader that exists but will not start is a soft non-zero.
    """
    if reader is _AUTO:
        reader = locate_reader()
    if reader is None:
        return (0, NO_AGENTM, "")
    try:
        r = subprocess.run([_PY, str(reader)], capture_output=True, text=True, timeout=15)
    except Exception as exc:  # the reader path existed but would not run
        return (1, "", f"[queue_status] could not invoke agentm reader: {exc}\n")
    return (r.returncode, r.stdout, r.stderr)


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="queue_status.py",
        description="Read-only dashboard of every active plan of the project the cwd is bound to.",
    )


def main(argv: "list[str]") -> int:
    _build_parser().parse_args(argv[1:])
    rc, out, err = run()
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
