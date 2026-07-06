#!/usr/bin/env python3
"""Task-level isolation flags for the worktree-per-task mode.

Reads PLAN.md task entries and determines which tasks are operator-declared
as isolated (eligible for per-task worktree spawning). A task is isolated
when its body contains the marker line:

    - **Isolated:** true

Independence is operator-declared, not inferred from prose — the operator
asserts isolation at plan time; the worker trusts the declaration and spawns
a per-task worktree only when the flag is explicit. Conservative default:
a task without the marker is never isolated. A wrong call that runs a
dependent task in a separate worktree would corrupt the build, so the gate
must never guess.

CLI: task_isolation.py check <plan_path> <task_num>
  Exit 0: task is isolated — spawn a per-task worktree.
  Exit 1: task is not isolated — run directly in current context.
  Exit 2: usage error or plan file not found.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_TASK_HEADER = re.compile(r'^### (\d+)\.')
_ISOLATED_MARKER = re.compile(r'^\s*-\s+\*\*Isolated:\*\*\s+true\s*$', re.IGNORECASE)


def parse_task_flags(plan_path: str | Path) -> list[dict]:
    """Parse task entries from a PLAN.md and return their isolation flags.

    Returns a list of dicts: [{"index": 1, "title": "...", "isolated": bool}, ...]
    Tasks are 1-indexed, matching the `### N.` header numbering in PLAN.md.
    Returns [] if the plan file is missing or unreadable.
    """
    try:
        text = Path(plan_path).read_text(encoding="utf-8")
    except Exception:
        return []

    tasks: list[dict] = []
    current: dict | None = None

    for line in text.splitlines():
        m = _TASK_HEADER.match(line)
        if m:
            if current is not None:
                tasks.append(current)
            idx = int(m.group(1))
            title = line[m.end():].strip().lstrip(". ").strip()
            current = {"index": idx, "title": title, "isolated": False}
        elif current is not None and _ISOLATED_MARKER.match(line):
            current["isolated"] = True

    if current is not None:
        tasks.append(current)

    return tasks


def should_isolate_task(plan_path: str | Path, task_num: int) -> bool:
    """Return True iff task_num in plan_path is marked **Isolated:** true.

    Conservative: returns False on any error (missing file, task not found).
    A dependent or ambiguous task must never be isolated by default.
    """
    for task in parse_task_flags(plan_path):
        if task["index"] == task_num:
            return task["isolated"]
    return False


def main(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="task_isolation.py")
    sub = p.add_subparsers(dest="cmd")

    chk = sub.add_parser("check", help="exit 0 if task is isolated, 1 if not")
    chk.add_argument("plan_path", help="path to PLAN.md")
    chk.add_argument("task_num", type=int, help="1-indexed task number")

    ns = p.parse_args(argv[1:])
    if ns.cmd == "check":
        if not Path(ns.plan_path).exists():
            print(f"task_isolation.py: plan not found: {ns.plan_path}", file=sys.stderr)
            return 2
        return 0 if should_isolate_task(ns.plan_path, ns.task_num) else 1

    p.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
