#!/usr/bin/env python3
"""The plan parsers read a `## Steps` plan exactly as they read a `## Tasks`
one (PLAN-tracker-commands task 5).

/plan's template now writes `## Steps` where it wrote `## Tasks`. No production
parser keys on that heading: they read `### N.` headings and the
`- **Status:** [ ]` checkboxes. This test keeps it that way for the four that
read plan steps — task_isolation.parse_task_flags, orient_render's checklist,
session_start_nudge's next-step tier hint, and the evidence tracker's
parse_plan. Each gets the same plan under both headings and must give the same,
non-empty answer.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS = _ROOT / "src" / "development-lifecycle" / "scripts"
_EVIDENCE_TRACKER = (_ROOT / "src" / "code-review" / "hooks" / "evidence-tracker"
                     / "evidence_tracker.py")


def _load(name: str, path: Path):
    if path.parent == _SCRIPTS and str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))  # orient_render imports its siblings by name
    spec = importlib.util.spec_from_file_location(f"heading_parity_{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


task_isolation = _load("task_isolation", _SCRIPTS / "task_isolation.py")
orient_render = _load("orient_render", _SCRIPTS / "orient_render.py")
session_start_nudge = _load("session_start_nudge", _SCRIPTS / "session_start_nudge.py")
evidence_tracker = _load("evidence_tracker", _EVIDENCE_TRACKER)

_PLAN = """---
parent_design_doc: wiki/designs/crickets-development-lifecycle.md
touches_architecture: true
---

# Plan: Parity probe

**Status:** in-progress

## Goal

The parsers read steps the way they read tasks.

{heading}

### 1. The bridge
- **What:** the verbs.
- **Isolated:** true
- **Verification:** `python3 -m unittest scripts/test_bridge.py`
- **Status:** [x]

### 2. The resolver
- **What:** the third field.
- **Work-type (optional):** mechanical-log-scraping
- **Tier hint (auto, only present when Work-type is set):** T0-Mechanical · claude-haiku-4-5 · low
- **Verification:** `python3 -m unittest scripts/test_resolver.py`
- **Status:** [ ]

### 3. The helper
- **Verification:** `python3 -m unittest scripts/test_helper.py`
- **Status:** [ ]

## Risks / open questions

- None identified.
"""


class TestStepsHeadingParity(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="heading-parity-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.texts, self.paths = {}, {}
        for heading in ("## Tasks", "## Steps"):
            text = _PLAN.format(heading=heading)
            path = self.tmp / heading.strip("# ").lower() / "PLAN.md"
            path.parent.mkdir()
            path.write_text(text, encoding="utf-8")
            self.texts[heading], self.paths[heading] = text, path

    def same_under_both(self, read):
        under_tasks = read("## Tasks")
        self.assertTrue(under_tasks, "the parser found nothing, so parity would prove nothing")
        self.assertEqual(read("## Steps"), under_tasks)
        return under_tasks

    def test_task_isolation_flags(self):
        flags = self.same_under_both(lambda h: task_isolation.parse_task_flags(self.paths[h]))
        self.assertEqual([f["isolated"] for f in flags], [True, False, False])

    def test_orient_render_checklist(self):
        checklist = self.same_under_both(lambda h: orient_render._task_checklist(self.texts[h]))
        self.assertEqual(checklist, ["✅ The bridge", "⬜ The resolver", "⬜ The helper"])

    def test_session_start_nudge_tier_hint(self):
        model = self.same_under_both(
            lambda h: session_start_nudge.next_unchecked_task_tier_hint_model(self.texts[h]))
        self.assertEqual(model, "claude-haiku-4-5")

    def test_evidence_tracker_parse_plan(self):
        def read(heading):
            return [(t.id, t.title, t.body, t.checkbox, t.verification_text,
                     t.evidence_annotation)
                    for t in evidence_tracker.parse_plan(self.paths[heading])]
        tasks = self.same_under_both(read)
        self.assertEqual([(t[0], t[3]) for t in tasks], [(1, "[x]"), (2, "[ ]"), (3, "[ ]")])


if __name__ == "__main__":
    unittest.main()
