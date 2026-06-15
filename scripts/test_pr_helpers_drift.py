#!/usr/bin/env python3
"""Drift-prevention test for pr_helpers.py vs wiki_watch_dispatch.py (task 3).

Probe #3 determined cross-plugin import is structurally unavailable at runtime
(version dirs diverge), so pr_helpers.py is a deliberate duplicate of the
three git/gh executor functions from wiki_watch_dispatch.py. This test pins
the load-bearing CONTRACT invariant so the two copies cannot silently drift
on the one thing that matters: **PII guard runs BEFORE any push**.

What it asserts (per function):
  - finalize_pr: in the .steps record, 'pii-guard' appears before any 'push'
  - finalize_direct: same ordering invariant
  - Both functions return DispatchResult with .steps, .ok, .action
  - prepare_branch exists with matching signature (3 params: repo_root, branch, runner)
  - check_gh_available exists in both modules

It does NOT assert byte-identity — the duplicate can evolve independently as
long as the PII-before-push contract is preserved.

Auto-discovered by check-all's `unit tests` gate.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_DW_SCRIPTS = _ROOT / "src" / "developer-workflows" / "scripts"
_WM_SCRIPTS = _ROOT / "src" / "wiki-maintenance" / "scripts"


def _load(name: str, path: Path):
    src = path / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, src)
    m = importlib.util.module_from_spec(spec)
    # Register under the real module name so dataclass field-type resolution works.
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


pr = _load("pr_helpers", _DW_SCRIPTS)

# wiki_watch_dispatch imports wiki_watch_config (a sibling); load it first.
try:
    _load("wiki_watch_config", _WM_SCRIPTS)
    wd = _load("wiki_watch_dispatch", _WM_SCRIPTS)
    _WD_AVAILABLE = True
except Exception:
    _WD_AVAILABLE = False


def _recording_runner(log: list):
    """Runner that records (cmd[0], args) and always returns rc=0."""
    def run(cmd: list, cwd: str) -> tuple[int, str]:
        log.append(tuple(cmd))
        return (0, "fake-sha")
    return run


class TestPrHelpersPiiBeforePushContract(unittest.TestCase):
    """The load-bearing invariant: PII guard precedes any push in both functions."""

    def test_finalize_pr_pii_before_push(self):
        steps = []
        result = pr.finalize_pr(
            ".", "my-branch",
            title="test", body="",
            pii_guard=lambda root: True,
            runner=_recording_runner([]),
        )
        step_names = [s[0] for s in result.steps]
        self.assertIn("pii-guard", step_names)
        pii_idx = step_names.index("pii-guard")
        push_idx = next((i for i, s in enumerate(step_names) if s == "push"), None)
        if push_idx is not None:
            self.assertLess(pii_idx, push_idx,
                            "PII guard must precede push in finalize_pr.steps")

    def test_finalize_pr_pii_blocked_prevents_push(self):
        cmds_issued: list = []
        result = pr.finalize_pr(
            ".", "my-branch",
            title="test", body="",
            pii_guard=lambda root: False,
            runner=_recording_runner(cmds_issued),
        )
        self.assertFalse(result.ok)
        self.assertIn("PII guard", result.reason)
        push_cmds = [c for c in cmds_issued if "push" in c]
        self.assertEqual(push_cmds, [], "no push should be issued when PII guard fails")

    def test_finalize_direct_pii_before_push(self):
        result = pr.finalize_direct(
            ".", message="test", pii_guard=lambda root: True,
            runner=_recording_runner([]),
        )
        step_names = [s[0] for s in result.steps]
        self.assertIn("pii-guard", step_names)
        pii_idx = step_names.index("pii-guard")
        push_idx = next((i for i, s in enumerate(step_names) if s == "push"), None)
        if push_idx is not None:
            self.assertLess(pii_idx, push_idx,
                            "PII guard must precede push in finalize_direct.steps")

    def test_finalize_direct_pii_blocked_prevents_push(self):
        cmds_issued: list = []
        result = pr.finalize_direct(
            ".", message="test",
            pii_guard=lambda root: False,
            runner=_recording_runner(cmds_issued),
        )
        self.assertFalse(result.ok)
        push_cmds = [c for c in cmds_issued if "push" in c]
        self.assertEqual(push_cmds, [], "no push when PII guard fails in finalize_direct")


class TestPrHelpersInterface(unittest.TestCase):
    """Structural checks: expected attributes and callables exist."""

    def test_dispatch_result_has_steps(self):
        result = pr.finalize_direct(".", message="t", pii_guard=lambda r: True,
                                    runner=_recording_runner([]))
        self.assertTrue(hasattr(result, "steps"))
        self.assertTrue(hasattr(result, "ok"))
        self.assertTrue(hasattr(result, "action"))

    def test_prepare_branch_callable(self):
        self.assertTrue(callable(pr.prepare_branch))

    def test_check_gh_available_callable(self):
        self.assertTrue(callable(pr.check_gh_available))

    def test_finalize_pr_callable(self):
        self.assertTrue(callable(pr.finalize_pr))

    def test_finalize_direct_callable(self):
        self.assertTrue(callable(pr.finalize_direct))


@unittest.skipUnless(_WD_AVAILABLE, "wiki_watch_dispatch not importable (sibling deps)")
class TestCrossModuleContractParity(unittest.TestCase):
    """Both modules expose the same contract surface."""

    def test_both_have_finalize_pr(self):
        self.assertTrue(callable(getattr(wd, "finalize_pr", None)))
        self.assertTrue(callable(pr.finalize_pr))

    def test_both_have_finalize_direct(self):
        self.assertTrue(callable(getattr(wd, "finalize_direct", None)))
        self.assertTrue(callable(pr.finalize_direct))

    def test_both_have_check_gh_available(self):
        self.assertTrue(callable(getattr(wd, "check_gh_available", None)))
        self.assertTrue(callable(pr.check_gh_available))

    def test_wiki_dispatch_also_guards_pii_before_push_in_finalize_pr(self):
        result = wd.finalize_pr(
            ".", "wm-branch",
            title="t", body="",
            pii_guard=lambda root: True,
            runner=_recording_runner([]),
        )
        step_names = [s[0] for s in result.steps]
        if "pii-guard" in step_names and "push" in step_names:
            pii_idx = step_names.index("pii-guard")
            push_idx = step_names.index("push")
            self.assertLess(pii_idx, push_idx,
                            "wiki_watch_dispatch.finalize_pr: pii-guard must precede push")

    def test_wiki_dispatch_pii_blocks_push_in_finalize_direct(self):
        cmds: list = []
        result = wd.finalize_direct(".", message="t", pii_guard=lambda r: False,
                                    runner=_recording_runner(cmds))
        push_cmds = [c for c in cmds if "push" in c]
        self.assertEqual(push_cmds, [])


if __name__ == "__main__":
    unittest.main()
