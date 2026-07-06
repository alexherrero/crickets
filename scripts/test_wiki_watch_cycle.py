#!/usr/bin/env python3
"""Tests for wiki_watch_cycle.py — the single-cycle driver
(src/wiki-maintenance/scripts/wiki_watch_cycle.py) — crickets ④ wiki-maintenance
part 4/5 (the wiki-watcher, W1), task 4.

Deterministic-only (DC-W8): the cooldown ledger, the significance-judgment
deterministic FLOOR (fixture-validated: doc-worthy -> dispatch, noise -> skip), and
the whole cycle END-TO-END with tasks 1-3 stubbed via run_cycle's injectable probes
(enablement / run_config / wiki_target / token / changed_paths / state_dir) — incl.
the graceful-skip branches, the cooldown no-op, and the idempotent re-run.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_WW_SCRIPTS = _ROOT / "src" / "wiki" / "scripts"


def _load(name: str):
    if str(_WW_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_WW_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, _WW_SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


cyc = _load("wiki_watch_cycle")
cfg = _load("wiki_watch_config")
dsp = _load("wiki_watch_dispatch")


def _rc(mode="pr", sources=None):
    return cfg.RunConfig(watch_sources=sources or ["."], dispatch_mode=mode)


# ----------------------------------------------------------------------------
# Cooldown ledger
# ----------------------------------------------------------------------------

class TestCooldown(unittest.TestCase):
    def test_should_fire_no_history(self):
        self.assertTrue(cyc.should_fire({}, "repo", now=1000.0, cooldown_s=900))

    def test_within_window_blocks(self):
        led = cyc.record_fire({}, "repo", now=1000.0)
        self.assertFalse(cyc.should_fire(led, "repo", now=1500.0, cooldown_s=900))

    def test_outside_window_fires(self):
        led = cyc.record_fire({}, "repo", now=1000.0)
        self.assertTrue(cyc.should_fire(led, "repo", now=2000.0, cooldown_s=900))

    def test_nonpositive_cooldown_always_fires(self):
        led = cyc.record_fire({}, "repo", now=1000.0)
        self.assertTrue(cyc.should_fire(led, "repo", now=1000.0, cooldown_s=0))

    def test_ledger_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            sd = Path(td) / "wiki-watch"
            led = cyc.load_fire_ledger(sd)
            cyc.record_fire(led, "repo", now=1234.0)
            cyc.save_fire_ledger(sd, led)
            self.assertEqual(cyc.load_fire_ledger(sd)["last_fire"]["repo"], 1234.0)


# ----------------------------------------------------------------------------
# Significance floor (fixture-validated)
# ----------------------------------------------------------------------------

class TestSignificanceFloor(unittest.TestCase):
    def test_doc_sources_dispatch(self):
        for p in ["PLAN.md", "ROADMAP.md", "README.md", "designs/wiki.md",
                  "wiki-stuff/decisions/0007-foo.md", "docs/guide.md", "CHANGELOG.md"]:
            self.assertEqual(cyc.classify_significance(p), "doc-source", p)
            self.assertEqual(cyc.recommend(p), "dispatch", p)

    def test_code_defers_to_judge(self):
        for p in ["src/app.py", "lib/core.ts", "main.go", "pkg/x.rs"]:
            self.assertEqual(cyc.classify_significance(p), "code", p)
            self.assertEqual(cyc.recommend(p), "judge", p)

    def test_minor_skips(self):
        for p in ["tests/test_app.py", "src/foo_test.go", "spec/x.spec.js",
                  ".github/workflows/ci.yml", "config.json", "settings.yaml", "data.csv"]:
            self.assertEqual(cyc.classify_significance(p), "minor", p)
            self.assertEqual(cyc.recommend(p), "skip", p)

    def test_test_markdown_under_tests_is_minor(self):
        # a .md inside a tests/ tree is test scaffolding, not a doc source.
        self.assertEqual(cyc.classify_significance("tests/fixtures/sample.md"), "minor")


# ----------------------------------------------------------------------------
# run_cycle — graceful-skip branches
# ----------------------------------------------------------------------------

class TestRunCycleSkips(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.sd = Path(self._td.name) / "wiki-watch"

    def tearDown(self):
        self._td.cleanup()

    def test_disabled(self):
        r = cyc.run_cycle("/r", enabled=False, state_dir=self.sd)
        self.assertTrue(r.skipped)
        self.assertIn("disabled", r.reason)

    def test_unconfigured(self):
        r = cyc.run_cycle("/r", enabled=True, run_config=None, state_dir=self.sd)
        self.assertTrue(r.skipped)
        self.assertIn("not configured", r.reason)

    def test_no_wiki_target(self):
        r = cyc.run_cycle("/r", enabled=True, run_config=_rc(), wiki_target=None,
                          state_dir=self.sd, respect_cooldown=False, token="T",
                          changed_paths=["PLAN.md"])
        self.assertTrue(r.skipped)
        self.assertIn("wiki target", r.reason)

    def test_no_token(self):
        r = cyc.run_cycle("/r", enabled=True, run_config=_rc(), wiki_target="/w",
                          state_dir=self.sd, respect_cooldown=False, token="",
                          changed_paths=["PLAN.md"])
        self.assertTrue(r.skipped)
        self.assertIn("git", r.reason)

    def test_cooldown_blocks_second_run(self):
        a = cyc.run_cycle("/r", enabled=True, run_config=_rc(), wiki_target="/w",
                          state_dir=self.sd, token="T", changed_paths=["PLAN.md"],
                          gh_available=True, now=1000.0, cooldown_s=900)
        self.assertFalse(a.skipped)
        b = cyc.run_cycle("/r", enabled=True, run_config=_rc(), wiki_target="/w",
                          state_dir=self.sd, token="T2", changed_paths=["PLAN.md"],
                          gh_available=True, now=1300.0, cooldown_s=900)
        self.assertTrue(b.skipped)
        self.assertIn("cooldown", b.reason)
        # …and fires again once the window passes.
        c = cyc.run_cycle("/r", enabled=True, run_config=_rc(), wiki_target="/w",
                          state_dir=self.sd, token="T2", changed_paths=["PLAN.md"],
                          gh_available=True, now=2500.0, cooldown_s=900)
        self.assertFalse(c.skipped)


# ----------------------------------------------------------------------------
# run_cycle — happy path + audit + idempotency
# ----------------------------------------------------------------------------

class TestRunCycleHappy(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.sd = Path(self._td.name) / "wiki-watch"

    def tearDown(self):
        self._td.cleanup()

    def _run(self, *, token="T1", changed=None, mode="pr", gh=True):
        return cyc.run_cycle(
            "/r", slug="demo", enabled=True, run_config=_rc(mode), wiki_target="/r/wiki",
            state_dir=self.sd, token=token, changed_paths=changed or ["PLAN.md", "src/app.py", "dist/x.js"],
            gh_available=gh, respect_cooldown=False, now=1000.0)

    def test_candidates_classified_and_planned(self):
        r = self._run()
        self.assertFalse(r.skipped)
        paths = {c["path"]: c["recommendation"] for c in r.candidates}
        self.assertEqual(paths.get("PLAN.md"), "dispatch")
        self.assertEqual(paths.get("src/app.py"), "judge")
        self.assertNotIn("dist/x.js", paths)  # noise pre-filtered (task 2)
        self.assertEqual(r.plan["action"], "pr")
        self.assertEqual(r.plan["branch"], dsp.branch_name("demo", "T1"))
        self.assertEqual(r.wiki_target, "/r/wiki")

    def test_pr_without_gh_plans_skip(self):
        r = self._run(gh=False)
        self.assertEqual(r.plan["action"], "skip")

    def test_direct_mode(self):
        r = self._run(mode="direct", gh=False)
        self.assertEqual(r.plan["action"], "direct")

    def test_audit_saw_and_decided_written(self):
        self._run()
        recs = dsp.read_audit(self.sd)
        phases = [r["phase"] for r in recs]
        self.assertIn("saw", phases)
        self.assertIn("decided", phases)

    def test_idempotent_after_finalize(self):
        # First cycle surfaces candidates; after finalize_cycle advances the cursor,
        # the same token yields nothing (idempotent).
        r1 = self._run(token="T1")
        self.assertTrue(r1.candidates)
        cyc.finalize_cycle(self.sd, "T1")
        r2 = self._run(token="T1")
        self.assertEqual(r2.candidates, [])

    def test_mark_dispatched_suppresses_recandidate(self):
        # Mark PLAN.md dispatched under T1 (no cursor advance) -> next same-token
        # cycle drops PLAN.md but keeps the still-pending src/app.py.
        self._run(token="T1")
        cyc.mark_and_audit_dispatch(self.sd, "T1", "PLAN.md",
                                    result={"ok": True, "pr_url": "http://x/pull/1"})
        r2 = self._run(token="T1")
        paths = {c["path"] for c in r2.candidates}
        self.assertNotIn("PLAN.md", paths)
        self.assertIn("src/app.py", paths)
        # the dispatched audit record landed
        self.assertTrue(any(r["phase"] == "dispatched" for r in dsp.read_audit(self.sd)))

    def test_mark_dispatch_tolerates_colliding_result_key(self):
        # A stray result key colliding with audit_record's named params must not
        # raise out of this "never-fails" completion helper (graceful-skip #6).
        self._run(token="T1")
        cyc.mark_and_audit_dispatch(self.sd, "T1", "PLAN.md",
                                    result={"ok": True, "phase": "X", "source": "Y"})
        recs = dsp.read_audit(self.sd)
        disp = [r for r in recs if r["phase"] == "dispatched"]
        self.assertTrue(disp)               # it wrote, didn't raise
        self.assertEqual(disp[0]["phase"], "dispatched")  # reserved key not overridden

    def test_iso_pathological_now_does_not_raise(self):
        # inf / NaN must degrade to "" rather than raising out of run_cycle.
        self.assertEqual(cyc._iso(float("inf")), "")
        self.assertEqual(cyc._iso(float("nan")), "")

    def test_record_failure_then_backoff(self):
        self._run(token="T1")
        cyc.record_dispatch_failure(self.sd, "T1", "src/app.py", now=1000.0)
        # within backoff (60s for 1 failure) the candidate is suppressed
        r2 = cyc.run_cycle("/r", slug="demo", enabled=True, run_config=_rc(),
                           wiki_target="/r/wiki", state_dir=self.sd, token="T1",
                           changed_paths=["src/app.py"], gh_available=True,
                           respect_cooldown=False, now=1030.0)
        self.assertEqual(r2.candidates, [])


if __name__ == "__main__":
    unittest.main()
