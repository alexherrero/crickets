#!/usr/bin/env python3
"""Tests for check-opinion-self-provider-drift.py (PLAN-opinion-consumer-grammar task 3).

Locks: `missing_anchors` (the pure presence check); a caller that drops an
anchor trips the check red (1); reverting clears it; a missing caller/stub
file is a usage error (2), not silent drift; a stale anchor against the
live stub prints a warning without changing the exit code (the check's own
upkeep, not the caller's drift); graceful-skip (0) when agentm is absent;
`--report` forces 0; the shipped real binding (adversarial-reviewer.md vs.
agentm's opinions/good.md) is clean today.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "check_opinion_self_provider_drift", _HERE / "check-opinion-self-provider-drift.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_opinion_self_provider_drift"] = mod
    spec.loader.exec_module(mod)
    return mod


drift = _load()


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestMissingAnchorsPure(unittest.TestCase):
    def test_all_anchors_present_returns_empty(self):
        text = "a failing test proves it, or an explicit NO ISSUES FOUND sign-off."
        self.assertEqual(drift.missing_anchors(text, ["failing test", "no issues found"]), [])

    def test_case_insensitive_match(self):
        self.assertEqual(drift.missing_anchors("FAILING TEST", ["failing test"]), [])

    def test_missing_anchor_is_reported(self):
        self.assertEqual(drift.missing_anchors("only a failing test here", ["failing test", "no issues found"]),
                          ["no issues found"])


class TestMainRedThenGreenViaMonkeypatchedBinding(unittest.TestCase):
    """Full main() red-then-green, isolated from the real shipped binding via
    a monkeypatched SELF_PROVIDER_BINDINGS dict."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="opinion-drift-"))
        self.agentm_dir = _write(self.tmp / "agentm-opinions" / "good.md",
                                  "---\nname: good\n---\nfailing test, or no issues found.\n").parent
        self.caller = _write(self.tmp / "caller.md", "a failing test, or no issues found.\n")
        self._patched = mock.patch.dict(
            drift.SELF_PROVIDER_BINDINGS,
            {"good": {"caller": self.caller, "anchors": ["failing test", "no issues found"]}},
            clear=True,
        )
        self._patched.start()

    def tearDown(self):
        self._patched.stop()

    def test_clean_binding_exits_zero(self):
        rc = drift.main(["--agentm-opinions-dir", str(self.agentm_dir)])
        self.assertEqual(rc, 0)

    def test_caller_dropping_an_anchor_exits_nonzero(self):
        self.caller.write_text("only a failing test remains here.\n", encoding="utf-8")
        rc = drift.main(["--agentm-opinions-dir", str(self.agentm_dir)])
        self.assertEqual(rc, 1)

    def test_reverting_the_drop_clears_it(self):
        self.caller.write_text("only a failing test remains here.\n", encoding="utf-8")
        self.assertEqual(drift.main(["--agentm-opinions-dir", str(self.agentm_dir)]), 1)
        self.caller.write_text("a failing test, or no issues found.\n", encoding="utf-8")
        self.assertEqual(drift.main(["--agentm-opinions-dir", str(self.agentm_dir)]), 0)

    def test_report_flag_forces_zero_even_on_real_drift(self):
        self.caller.write_text("only a failing test remains here.\n", encoding="utf-8")
        rc = drift.main(["--agentm-opinions-dir", str(self.agentm_dir), "--report"])
        self.assertEqual(rc, 0)

    def test_missing_caller_file_is_a_usage_error(self):
        self.caller.unlink()
        rc = drift.main(["--agentm-opinions-dir", str(self.agentm_dir)])
        self.assertEqual(rc, 2)

    def test_missing_stub_file_is_a_usage_error(self):
        (self.agentm_dir / "good.md").unlink()
        rc = drift.main(["--agentm-opinions-dir", str(self.agentm_dir)])
        self.assertEqual(rc, 2)

    def test_stale_anchor_against_live_stub_warns_but_stays_green(self):
        # the stub itself no longer mentions "no issues found" -- this check's
        # own anchor list needs review, but that's not the caller's fault, and
        # the caller still satisfies both anchors, so the exit stays 0.
        (self.agentm_dir / "good.md").write_text(
            "---\nname: good\n---\nonly a failing test matters.\n", encoding="utf-8")
        rc = drift.main(["--agentm-opinions-dir", str(self.agentm_dir)])
        self.assertEqual(rc, 0)


class TestGracefulSkipWhenAgentmAbsent(unittest.TestCase):
    def test_missing_agentm_dir_skips_with_zero(self):
        with tempfile.TemporaryDirectory() as t:
            absent = Path(t) / "no-such-agentm-opinions-dir"
            rc = drift.main(["--agentm-opinions-dir", str(absent)])
            self.assertEqual(rc, 0)


class TestRealShippedBindingIsCleanOrSkips(unittest.TestCase):
    """Not hermetic by design -- exercises the real adversarial-reviewer.md
    against a real ~/Antigravity/agentm clone, when present, mirroring
    check-opinion-snapshot-parity.py's equivalent real-tree test."""

    def test_shipped_good_binding_is_clean_or_skips(self):
        rc = drift.main([])
        self.assertIn(rc, (0, 1))
        if rc == 1:
            self.fail("src/code-review/agents/adversarial-reviewer.md no longer "
                      "mirrors agentm's opinions/good.md anchors — review both")


if __name__ == "__main__":
    unittest.main()
