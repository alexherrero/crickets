#!/usr/bin/env python3
"""Crickets plan 105 (clear out the dead weight): what retired stays gone.

Each entry is a (group, kind, name) primitive or a script the plan deleted. The
test asserts it is absent from `src/` and from both hosts' `dist/` trees, so a
stale copy or a reintroduction fails the build. `generate.py check` separately
proves `dist/` mirrors `src/`; this test pins the retirement itself.
"""
from __future__ import annotations

import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
_CC = _ROOT / "dist" / "claude-code" / "plugins"
_AG = _ROOT / "dist" / "antigravity" / "plugins"

# Step 2: development-lifecycle's unused commands and agents.
RETIRED = [
    ("development-lifecycle", "command", "ci-cd"),
    ("development-lifecycle", "command", "launch"),
    ("development-lifecycle", "command", "deprecate"),
    ("development-lifecycle", "command", "observe"),
    ("development-lifecycle", "command", "orient"),
    ("development-lifecycle", "command", "queue-status-lite"),
    ("development-lifecycle", "agent", "project-manager"),
    ("development-lifecycle", "agent", "tech-lead"),
    ("development-lifecycle", "agent", "researcher"),
    # Step 3: design's and conventions' unused primitives.
    ("design", "command", "document-decision"),
    ("design", "skill", "adr"),
    ("conventions", "skill", "agentic-engineering"),
    ("conventions", "skill", "testing-conventions"),
]

RETIRED_SCRIPTS = [
    ("development-lifecycle", "queue_status.py"),
    ("conventions", "conventions_domain.py"),
]


def _paths(group: str, kind: str, name: str) -> list[Path]:
    """Every place the primitive could live: its source and each host's emit."""
    if kind == "command":
        return [_SRC / group / "commands" / f"{name}.md",
                _CC / group / "commands" / f"{name}.md",
                _AG / group / "skills" / name / "SKILL.md"]
    if kind == "agent":
        return [_SRC / group / "agents" / f"{name}.md",
                _CC / group / "agents" / f"{name}.md",
                _AG / group / "agents" / f"{name}.md"]
    if kind == "skill":
        return [_SRC / group / "skills" / name / "SKILL.md",
                _CC / group / "skills" / name / "SKILL.md",
                _AG / group / "skills" / name / "SKILL.md"]
    raise ValueError(kind)


class TestRetiredPrimitivesAreGone(unittest.TestCase):
    def test_retired_primitives_absent_from_src_and_both_hosts(self):
        for group, kind, name in RETIRED:
            for path in _paths(group, kind, name):
                with self.subTest(primitive=f"{group}:{kind}:{name}", path=str(path.relative_to(_ROOT))):
                    self.assertFalse(path.exists(), f"retired {kind} {name!r} is back at {path}")

    def test_retired_scripts_absent_from_src_and_both_hosts(self):
        for group, script in RETIRED_SCRIPTS:
            for base in (_SRC, _CC, _AG):
                path = base / group / "scripts" / script
                with self.subTest(path=str(path.relative_to(_ROOT))):
                    self.assertFalse(path.exists(), f"retired script {script!r} is back at {path}")

    def test_open_is_the_one_project_entry_point(self):
        text = (_SRC / "development-lifecycle" / "commands" / "open.md").read_text(encoding="utf-8")
        # The command, not the orient_render.py script /open still calls.
        self.assertNotRegex(text, r"/orient(?![_\w])")
        self.assertNotIn("queue-status-lite", text)

    def test_worker_is_the_one_coordinator_role_left(self):
        agents = {p.stem for p in (_SRC / "development-lifecycle" / "agents").glob("*.md")}
        self.assertIn("worker", agents)
        self.assertFalse(agents & {"project-manager", "tech-lead", "researcher"})


if __name__ == "__main__":
    unittest.main()
