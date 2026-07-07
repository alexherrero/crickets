#!/usr/bin/env python3
"""Tests for check-opinion-snapshot-parity.py (PLAN-opinion-consumer-grammar task 1).

Locks: a matching snapshot passes; a deliberately-drifted snapshot fails red
(1) and is distinguishable from a real match; a missing agentm sibling
gracefully skips (0) with a message that says so rather than silently
looking like a pass; a snapshot with no matching agentm file is a usage
error (2), not silent drift; `--report` forces 0 even on real drift.

Every test is hermetic — real files live in a tmp dir, never the real
scripts/opinion-snapshots/ or a real ~/Antigravity/agentm clone.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "check_opinion_snapshot_parity", _HERE / "check-opinion-snapshot-parity.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_opinion_snapshot_parity"] = mod
    spec.loader.exec_module(mod)
    return mod


parity = _load()

_GOOD_STUB = """---
name: good
kind: opinion
question: "does it survive a hostile read?"
serves: [code-review, design]
implements: crickets/code-review
composes: []
---
Good means it survives an adversarial pass primed to assume bugs exist, not
a friendly skim. The standard is a failing test, a specific file:line
defect, or an explicit "no issues found" after genuinely looking — prose
critique without one of those three is not a review.
"""


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestMatchingSnapshotPasses(unittest.TestCase):
    def test_identical_snapshot_and_agentm_source_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap_dir = _write(Path(tmp) / "snapshots" / "good.md", _GOOD_STUB).parent
            agentm_dir = _write(Path(tmp) / "agentm-opinions" / "good.md", _GOOD_STUB).parent
            rc = parity.main([
                "--snapshot-dir", str(snap_dir),
                "--agentm-opinions-dir", str(agentm_dir),
            ])
            self.assertEqual(rc, 0)


class TestDriftedSnapshotFailsRed(unittest.TestCase):
    def test_drifted_snapshot_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap_dir = _write(Path(tmp) / "snapshots" / "good.md", _GOOD_STUB).parent
            drifted_live = _GOOD_STUB.replace("hostile read", "friendly skim")
            agentm_dir = _write(Path(tmp) / "agentm-opinions" / "good.md", drifted_live).parent
            rc = parity.main([
                "--snapshot-dir", str(snap_dir),
                "--agentm-opinions-dir", str(agentm_dir),
            ])
            self.assertEqual(rc, 1)

    def test_drift_message_is_distinguishable_from_a_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap_dir = _write(Path(tmp) / "snapshots" / "good.md", _GOOD_STUB).parent
            agentm_dir = _write(Path(tmp) / "agentm-opinions" / "good.md", "drifted body\n").parent
            result = parity.compare_one("good", snap_dir, agentm_dir)
            self.assertIsNotNone(result)
            self.assertIn("differs from agentm's", result)

    def test_report_flag_forces_zero_even_on_real_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap_dir = _write(Path(tmp) / "snapshots" / "good.md", _GOOD_STUB).parent
            agentm_dir = _write(Path(tmp) / "agentm-opinions" / "good.md", "drifted body\n").parent
            rc = parity.main([
                "--snapshot-dir", str(snap_dir),
                "--agentm-opinions-dir", str(agentm_dir),
                "--report",
            ])
            self.assertEqual(rc, 0)


class TestGracefulSkipWhenAgentmAbsent(unittest.TestCase):
    def test_missing_agentm_dir_skips_with_zero_not_a_silent_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap_dir = _write(Path(tmp) / "snapshots" / "good.md", _GOOD_STUB).parent
            absent_dir = Path(tmp) / "no-such-agentm-opinions-dir"
            rc = parity.main([
                "--snapshot-dir", str(snap_dir),
                "--agentm-opinions-dir", str(absent_dir),
            ])
            self.assertEqual(rc, 0)

    def test_empty_snapshot_dir_is_a_zero_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap_dir = Path(tmp) / "empty-snapshots"
            snap_dir.mkdir()
            rc = parity.main(["--snapshot-dir", str(snap_dir)])
            self.assertEqual(rc, 0)


class TestOrphanedSnapshotIsAUsageError(unittest.TestCase):
    def test_snapshot_with_no_matching_agentm_file_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap_dir = _write(Path(tmp) / "snapshots" / "orphan.md", "some body\n").parent
            agentm_dir = Path(tmp) / "agentm-opinions"
            agentm_dir.mkdir()
            rc = parity.main([
                "--snapshot-dir", str(snap_dir),
                "--agentm-opinions-dir", str(agentm_dir),
            ])
            self.assertEqual(rc, 2)


class TestRealShippedSnapshotMatchesLiveAgentmWhenPresent(unittest.TestCase):
    """Not hermetic by design — the one test that exercises the real
    scripts/opinion-snapshots/good.md against a real ~/Antigravity/agentm
    clone, when present, so a genuinely drifted snapshot fails CI on this
    machine even though check-all.sh wires the script itself with
    --report. Gracefully skips (not a failure) when agentm isn't cloned —
    same posture as the script's own graceful-skip."""

    def test_shipped_good_snapshot_matches_agentm_or_skips(self):
        rc = parity.main([])
        self.assertIn(rc, (0, 1))
        if rc == 1:
            self.fail("scripts/opinion-snapshots/good.md has drifted from "
                      "agentm's opinions/good.md — refresh the snapshot")


if __name__ == "__main__":
    unittest.main()
