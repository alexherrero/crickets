#!/usr/bin/env python3
"""Tests for src/development-lifecycle/scripts/resolve_workflow_persona.py
(PLAN-wave-d-personas task 3).

Discovery (find_resolver): $AGENTM_SCRIPTS_DIR, co-located sibling,
conventional ~/Antigravity/ clone, and graceful-skip (None) when absent.

Delegation (run_resolve): propagates resolver stdout + exit code (resolved /
no-persona-for-step / usage); forwards --explicit; exits 1 cleanly when the
resolver is absent (no hang).

One test per wired phase command (plan/work/review/bugfix) asserting the
correct persona resolves when no explicit invocation is given, and that an
explicit invocation still overrides it when both are present.

Every test is hermetic — injectable resolver paths + env overrides ensure no
dependency on a real agentm install (CI runs with none). Mirrors
test_find_governing_design.py.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "development-lifecycle" / "scripts" / "resolve_workflow_persona.py"


def _load():
    spec = importlib.util.spec_from_file_location("resolve_workflow_persona", _SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["resolve_workflow_persona"] = m
    spec.loader.exec_module(m)
    return m


rwp = _load()

# A fake resolver mirroring agentm's workflow_persona_resolver.py contract —
# real enough to exercise --explicit forwarding + the step->persona mapping
# for the four wired phase commands, without depending on a real agentm clone.
_FAKE_RESOLVER_BODY = """
import argparse, sys
MAP = {"plan-phase": "tech-lead", "work-phase": "engineer",
       "review-phase": "reviewer", "bugfix-phase": "troubleshooter"}
ap = argparse.ArgumentParser()
ap.add_argument("step", nargs="?")
ap.add_argument("--explicit", default=None)
args = ap.parse_args(sys.argv[1:])
persona = args.explicit or MAP.get(args.step or "")
if persona:
    sys.stdout.write(persona + "\\n")
    sys.exit(0)
sys.exit(1)
"""


def _make_fake_resolver(path: Path, body: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body or "# stub resolver\n", encoding="utf-8")
    return path


class TestFindResolverDiscovery(unittest.TestCase):
    """find_resolver() locates workflow_persona_resolver.py via fallback order; None when absent."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rwp-discovery-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_found_via_env_agentm_scripts_dir(self):
        r = _make_fake_resolver(self.tmp / "env_scripts" / "workflow_persona_resolver.py")
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(r.parent)}):
            result = rwp.find_resolver()
        self.assertEqual(result, r.resolve())

    def test_env_takes_priority_over_colocated(self):
        env_r = _make_fake_resolver(self.tmp / "env_dir" / "workflow_persona_resolver.py")
        colocated = _make_fake_resolver(_SRC.parent / "workflow_persona_resolver.py")
        try:
            with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(env_r.parent)}):
                result = rwp.find_resolver()
            self.assertEqual(result, env_r.resolve())
        finally:
            colocated.unlink(missing_ok=True)

    def test_found_via_colocated_sibling(self):
        colocated = _make_fake_resolver(_SRC.parent / "workflow_persona_resolver.py")
        try:
            env_without = {k: v for k, v in os.environ.items()
                           if k != "AGENTM_SCRIPTS_DIR"}
            with mock.patch.dict(os.environ, env_without, clear=True):
                result = rwp.find_resolver()
            self.assertIsNotNone(result)
            self.assertTrue(result.is_file())
        finally:
            colocated.unlink(missing_ok=True)

    def test_found_via_conventional_antigravity_clone(self):
        home = self.tmp / "fake_home"
        r = _make_fake_resolver(
            home / "Antigravity" / "agentm" / "scripts" / "workflow_persona_resolver.py")
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}, clear=False):
            with mock.patch.object(Path, "home", return_value=home):
                result = rwp.find_resolver()
        self.assertEqual(result, r.resolve())

    def test_returns_none_when_all_absent(self):
        home = self.tmp / "empty_home"
        home.mkdir()
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}, clear=False):
            with mock.patch.object(Path, "home", return_value=home):
                result = rwp.find_resolver()
        self.assertIsNone(result)


class TestRunResolve(unittest.TestCase):
    """run_resolve() propagates resolver stdout + exit code; exits 1 when absent."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rwp-run-"))
        self.resolver = self.tmp / "fake_resolver.py"
        self.resolver.write_text(_FAKE_RESOLVER_BODY, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- one test per wired phase command: no explicit invocation ---

    def test_plan_phase_resolves_tech_lead(self):
        out, rc = rwp.run_resolve("plan-phase", resolver=self.resolver)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "tech-lead")

    def test_work_phase_resolves_engineer(self):
        out, rc = rwp.run_resolve("work-phase", resolver=self.resolver)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "engineer")

    def test_review_phase_resolves_reviewer(self):
        out, rc = rwp.run_resolve("review-phase", resolver=self.resolver)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "reviewer")

    def test_bugfix_phase_resolves_troubleshooter(self):
        out, rc = rwp.run_resolve("bugfix-phase", resolver=self.resolver)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "troubleshooter")

    # --- explicit invocation overrides the workflow-step default ---

    def test_explicit_invocation_overrides_each_wired_step(self):
        for step in ("plan-phase", "work-phase", "review-phase", "bugfix-phase"):
            with self.subTest(step=step):
                out, rc = rwp.run_resolve(step, explicit="architect", resolver=self.resolver)
                self.assertEqual(rc, 0)
                self.assertEqual(out, "architect")

    def test_unknown_step_no_explicit_exits_one_empty_stdout(self):
        out, rc = rwp.run_resolve("no-such-phase", resolver=self.resolver)
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")

    def test_resolver_absent_exits_one_no_hang(self):
        with mock.patch.object(rwp, "find_resolver", return_value=None):
            out, rc = rwp.run_resolve("plan-phase")
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")

    def test_resolver_error_graceful_skip(self):
        out, rc = rwp.run_resolve(
            "plan-phase", resolver=self.tmp / "does-not-exist.py")
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")


class TestMainCLI(unittest.TestCase):
    """main() exits 2 on bad usage; proxies the resolver; forwards --explicit."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rwp-main-"))
        self.resolver = self.tmp / "fake_resolver.py"
        self.resolver.write_text(_FAKE_RESOLVER_BODY, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_step_exits_two(self):
        rc = rwp.main(["resolve_workflow_persona.py"])
        self.assertEqual(rc, 2)

    def test_wired_step_proxied(self):
        with mock.patch.object(rwp, "find_resolver", return_value=self.resolver):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = rwp.main(["resolve_workflow_persona.py", "review-phase"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue().strip(), "reviewer")

    def test_explicit_flag_forwarded_and_wins(self):
        with mock.patch.object(rwp, "find_resolver", return_value=self.resolver):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = rwp.main(["resolve_workflow_persona.py", "work-phase",
                                "--explicit", "designer"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue().strip(), "designer")

    def test_resolver_absent_exits_one_no_output(self):
        with mock.patch.object(rwp, "find_resolver", return_value=None):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = rwp.main(["resolve_workflow_persona.py", "plan-phase"])
        self.assertEqual(rc, 1)
        self.assertEqual(out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
