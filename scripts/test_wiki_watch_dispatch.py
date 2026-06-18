#!/usr/bin/env python3
"""Tests for wiki_watch_dispatch.py — dispatch plumbing
(src/wiki-maintenance/scripts/wiki_watch_dispatch.py) — crickets ④ wiki-maintenance
part 4/5 (the wiki-watcher, W1), task 3.

Deterministic-only (DC-W8): the PR-vs-direct planner, branch derivation, the
documenter-context prose builder, the audit-log format, and — via an injected fake
runner — the git/gh executor COMMAND SEQUENCE, the PII-guard-before-push ordering,
and graceful-skip on failure. No real gh / remote is touched.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_WW_SCRIPTS = _ROOT / "src" / "wiki-maintenance" / "scripts"


def _load(name: str):
    if str(_WW_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_WW_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, _WW_SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


dsp = _load("wiki_watch_dispatch")
cfg = _load("wiki_watch_config")


def _run_config(mode):
    return cfg.RunConfig(watch_sources=["."], dispatch_mode=mode)


class FakeRunner:
    """Records argv + appends a token to a shared `order` list; returns scripted
    (rc, stdout) keyed by 'git:<sub>' / 'gh'. Defaults to success."""
    def __init__(self, order, responses=None):
        self.calls: list = []
        self.order = order
        self.responses = responses or {}

    def __call__(self, argv, cwd):
        self.calls.append(argv)
        token = argv[1] if argv and argv[0] == "git" and len(argv) > 1 else argv[0]
        self.order.append(token)
        if argv[:2] == ["git", "rev-parse"]:
            return 0, "deadbeefcafe"
        key = f"{argv[0]}:{argv[1]}" if len(argv) > 1 else argv[0]
        return self.responses.get(key, self.responses.get(argv[0], (0, "")))


# ----------------------------------------------------------------------------
# Branch derivation
# ----------------------------------------------------------------------------

class TestBranch(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(dsp.slugify("Hello, World!"), "hello-world")
        self.assertEqual(dsp.slugify("a__b--c"), "a-b-c")

    def test_branch_name_deterministic(self):
        b = dsp.branch_name("agentm", "deadbeefcafe1234")
        self.assertEqual(b, "wiki-watch/agentm-deadbeefcafe")
        self.assertEqual(b, dsp.branch_name("agentm", "deadbeefcafe1234"))  # stable

    def test_branch_name_fallbacks(self):
        self.assertEqual(dsp.branch_name("", ""), "wiki-watch/repo-head")


# ----------------------------------------------------------------------------
# Planner
# ----------------------------------------------------------------------------

class TestPlanDispatch(unittest.TestCase):
    def test_direct_mode(self):
        p = dsp.plan_dispatch(_run_config("direct"), gh_available=False, slug="x", token="t")
        self.assertEqual(p.action, "direct")

    def test_pr_mode_with_gh(self):
        p = dsp.plan_dispatch(_run_config("pr"), gh_available=True, slug="agentm", token="abc123")
        self.assertEqual(p.action, "pr")
        self.assertEqual(p.branch, "wiki-watch/agentm-abc123")

    def test_pr_mode_without_gh_skips_not_direct(self):
        # The load-bearing guard: PR-default + no gh must SKIP, never silently
        # downgrade to direct-commit (that would bypass the human-merge boundary).
        p = dsp.plan_dispatch(_run_config("pr"), gh_available=False, slug="x", token="t")
        self.assertEqual(p.action, "skip")
        self.assertIn("bypass", p.reason)


# ----------------------------------------------------------------------------
# Documenter context (prose builder)
# ----------------------------------------------------------------------------

class TestDocumenterContext(unittest.TestCase):
    def test_contains_candidates_and_boundary(self):
        ctx = dsp.build_documenter_context(
            repo_root="/r", wiki_target="/r/wiki", candidates=["PLAN.md", "src/a.py"],
            dispatch_mode="pr", head_token="sha9")
        self.assertIn("PLAN.md", ctx)
        self.assertIn("src/a.py", ctx)
        self.assertIn("PR is the human-review boundary", ctx)
        self.assertIn("/r/wiki", ctx)

    def test_direct_boundary_text(self):
        ctx = dsp.build_documenter_context(
            repo_root="/r", wiki_target="/r/wiki", candidates=[], dispatch_mode="direct",
            head_token="sha9")
        self.assertIn("Direct-commit opt-in", ctx)
        self.assertIn("(none)", ctx)


# ----------------------------------------------------------------------------
# gh availability
# ----------------------------------------------------------------------------

class TestGhAvailable(unittest.TestCase):
    def setUp(self):
        self._which = dsp.shutil.which

    def tearDown(self):
        dsp.shutil.which = self._which

    def test_false_when_gh_missing(self):
        dsp.shutil.which = lambda name: None
        self.assertFalse(dsp.check_gh_available(runner=lambda a, c: (0, "")))

    def test_true_when_present_and_authed(self):
        dsp.shutil.which = lambda name: "/usr/bin/gh"
        self.assertTrue(dsp.check_gh_available(runner=lambda a, c: (0, "Logged in")))

    def test_false_when_not_authed(self):
        dsp.shutil.which = lambda name: "/usr/bin/gh"
        self.assertFalse(dsp.check_gh_available(runner=lambda a, c: (1, "not logged in")))


# ----------------------------------------------------------------------------
# Executors — command sequence, PII-before-push ordering, graceful-skip
# ----------------------------------------------------------------------------

class TestFinalizePR(unittest.TestCase):
    def test_happy_path_sequence_and_pii_before_push(self):
        order: list = []
        runner = FakeRunner(order, responses={"gh:pr": (0, "https://github.com/x/y/pull/7")})

        def pii_guard(repo):
            order.append("pii")
            return True

        res = dsp.finalize_pr("/r", "wiki-watch/x-abc", title="t", body="b",
                              pii_guard=pii_guard, runner=runner)
        self.assertTrue(res.ok)
        self.assertEqual(res.pr_url, "https://github.com/x/y/pull/7")
        self.assertEqual(res.commit, "deadbeefcafe")
        # PII guard ran BEFORE the push (the contract).
        self.assertLess(order.index("pii"), order.index("push"))
        # And before the PR was opened.
        self.assertLess(order.index("pii"), order.index("gh"))

    def test_pii_block_aborts_before_push(self):
        order: list = []
        runner = FakeRunner(order)
        res = dsp.finalize_pr("/r", "br", title="t", body="b",
                              pii_guard=lambda repo: False, runner=runner)
        self.assertFalse(res.ok)
        self.assertIn("PII guard", res.reason)
        self.assertNotIn("push", order)   # never pushed
        self.assertNotIn("gh", order)     # never opened a PR

    def test_commit_failure_aborts(self):
        order: list = []
        runner = FakeRunner(order, responses={"git:commit": (1, "nothing to commit")})
        res = dsp.finalize_pr("/r", "br", title="t", body="b",
                              pii_guard=lambda repo: True, runner=runner)
        self.assertFalse(res.ok)
        self.assertNotIn("push", order)

    def test_push_failure_is_graceful(self):
        order: list = []
        runner = FakeRunner(order, responses={"git:push": (1, "remote rejected")})
        res = dsp.finalize_pr("/r", "br", title="t", body="b",
                              pii_guard=lambda repo: True, runner=runner)
        self.assertFalse(res.ok)
        self.assertIn("push failed", res.reason)
        self.assertNotIn("gh", order)  # no PR after a failed push


class TestFinalizeDirect(unittest.TestCase):
    def test_sequence_and_pii_before_push(self):
        order: list = []
        runner = FakeRunner(order)
        res = dsp.finalize_direct("/r", message="m", pii_guard=lambda r: order.append("pii") or True,
                                  runner=runner)
        self.assertTrue(res.ok)
        self.assertEqual(res.action, "direct")
        self.assertLess(order.index("pii"), order.index("push"))

    def test_pii_block_aborts(self):
        order: list = []
        runner = FakeRunner(order)
        res = dsp.finalize_direct("/r", message="m", pii_guard=lambda r: False, runner=runner)
        self.assertFalse(res.ok)
        self.assertNotIn("push", order)


class TestPrepareBranch(unittest.TestCase):
    def test_checkout(self):
        order: list = []
        runner = FakeRunner(order)
        res = dsp.prepare_branch("/r", "wiki-watch/x-abc", runner=runner)
        self.assertTrue(res.ok)
        self.assertEqual(runner.calls[0], ["git", "checkout", "-B", "wiki-watch/x-abc"])

    def test_checkout_failure_graceful(self):
        order: list = []
        runner = FakeRunner(order, responses={"git:checkout": (1, "bad ref")})
        res = dsp.prepare_branch("/r", "br", runner=runner)
        self.assertFalse(res.ok)


# ----------------------------------------------------------------------------
# Audit log
# ----------------------------------------------------------------------------

class TestAudit(unittest.TestCase):
    def test_record_shape(self):
        rec = dsp.audit_record(phase="decided", source="repo", ts="2026-06-06T00:00:00Z",
                               decision="significant", candidates=["PLAN.md"])
        self.assertEqual(rec["phase"], "decided")
        self.assertEqual(rec["source"], "repo")
        self.assertEqual(rec["candidates"], ["PLAN.md"])

    def test_append_and_read_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            sdir = Path(td) / "wiki-watch"
            dsp.append_audit(sdir, dsp.audit_record(phase="saw", candidates=["a"]))
            dsp.append_audit(sdir, dsp.audit_record(phase="dispatched", action="pr",
                                                    pr_url="http://x/pull/1", ok=True))
            recs = dsp.read_audit(sdir)
            self.assertEqual(len(recs), 2)
            self.assertEqual(recs[0]["phase"], "saw")
            self.assertEqual(recs[1]["pr_url"], "http://x/pull/1")
            # one JSON object per line
            lines = (sdir / "audit.log").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)

    def test_read_missing_is_empty(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(dsp.read_audit(Path(td) / "wiki-watch"), [])


if __name__ == "__main__":
    unittest.main()
