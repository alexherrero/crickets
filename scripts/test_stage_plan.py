#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/stage_plan.py (V5-10 sibling #1).

Two-tier named-plan staging composed onto `resolve_plan`. Every test is hermetic:
the staging path is derived from the resolver's output, so we exercise *both*
backends — the standalone `.harness/` fallback (`resolver=None`) and a planted
stub that stands in for agentm's verb (`resolver=<stub path>`) — without a real
agentm clone. The activate guards and the "staged = inactive" invariant (against
the real `queue_status._list_plan_files`) run over throwaway tmp dirs.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS = _ROOT / "src" / "developer-workflows" / "scripts"


def _load(name: str):
    src = _SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, src)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


sp = _load("stage_plan")
qs = _load("queue_status")


def _write_stub(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


class TestStagingPath(unittest.TestCase):
    """`path` resolves `<_harness>/queued-plans/PLAN-<name>.md`, both backends."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sp-path-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_standalone_derives_under_dot_harness(self):
        # Fallback: active is <root>/.harness/PLAN-foo.md → staged sits in
        # the queued-plans/ subdir beside it.
        rc, out, err = sp.staging_path("foo", str(self.tmp), resolver=None)
        self.assertEqual(rc, 0)
        self.assertEqual(err, "")
        expected = self.tmp / ".harness" / "queued-plans" / "PLAN-foo.md"
        self.assertEqual(out.strip(), str(expected))

    def test_standalone_accepts_filename_form(self):
        rc, out, _ = sp.staging_path("PLAN-foo.md", str(self.tmp), resolver=None)
        self.assertEqual(rc, 0)
        expected = self.tmp / ".harness" / "queued-plans" / "PLAN-foo.md"
        self.assertEqual(out.strip(), str(expected))

    def test_delegate_derives_from_resolver_output_not_dot_harness(self):
        # Agentm present: the active path is whatever the resolver says (here a
        # vault-style path with no `.harness`). Staging must compose onto THAT —
        # proving we never re-derive `<root>/.harness`.
        stub = _write_stub(
            self.tmp / "stub_ok.py",
            "import sys\n"
            "sys.stdout.write('/v/_harness/PLAN-foo.md\\t/v/_harness/progress-foo.md\\n')\n"
            "sys.exit(0)\n",
        )
        rc, out, err = sp.staging_path("foo", str(self.tmp), resolver=stub)
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "/v/_harness/queued-plans/PLAN-foo.md")
        self.assertNotIn(".harness", out)  # honored the vault redirect, not <root>/.harness

    def test_empty_or_singleton_name_refused(self):
        for form in ("", "   ", "PLAN", "PLAN.md"):
            rc, out, err = sp.staging_path(form, str(self.tmp), resolver=None)
            self.assertEqual(rc, 2, form)
            self.assertEqual(out, "", form)
            self.assertIn("named plan", err)

    def test_unsafe_slug_propagates_resolver_refusal(self):
        # The named-only guard passes (`../etc` is non-empty), but the resolver's
        # safety guard rejects it — that exit 2 + stderr propagate verbatim.
        rc, out, err = sp.staging_path("../etc", str(self.tmp), resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("unsafe plan name", err)


class TestActivate(unittest.TestCase):
    """`activate` is a guarded copy: staged → active, no clobber, no silent miss."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sp-activate-"))
        self.harness = self.tmp / ".harness"
        self.queued = self.harness / "queued-plans"
        self.queued.mkdir(parents=True, exist_ok=True)
        self.staged = self.queued / "PLAN-foo.md"
        self.active = self.harness / "PLAN-foo.md"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_happy_path_copies_bytes_verbatim(self):
        body = "# Plan: foo\n\n**Status:** planning\nbody bytes ✓\n"
        self.staged.write_text(body, encoding="utf-8")
        self.assertFalse(self.active.exists())
        rc, out, err = sp.activate("foo", str(self.tmp), resolver=None)
        self.assertEqual(rc, 0, err)
        self.assertEqual(err, "")
        self.assertTrue(self.active.is_file())
        self.assertEqual(self.active.read_text(encoding="utf-8"), body)
        self.assertEqual(out.strip(), str(self.active))

    def test_collision_refuses_and_leaves_active_untouched(self):
        self.staged.write_text("STAGED\n", encoding="utf-8")
        self.active.write_text("ACTIVE-IN-FLIGHT\n", encoding="utf-8")
        rc, out, err = sp.activate("foo", str(self.tmp), resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("already exists", err)
        # The in-flight active plan is NOT clobbered by the staged bytes.
        self.assertEqual(self.active.read_text(encoding="utf-8"), "ACTIVE-IN-FLIGHT\n")

    def test_missing_staged_refuses(self):
        self.assertFalse(self.staged.exists())
        rc, out, err = sp.activate("foo", str(self.tmp), resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("no staged plan", err)
        self.assertFalse(self.active.exists())

    def test_activate_leaves_staged_copy_in_place(self):
        # Activation is a copy, not a move — the staged original remains.
        self.staged.write_text("STAGED\n", encoding="utf-8")
        rc, _, err = sp.activate("foo", str(self.tmp), resolver=None)
        self.assertEqual(rc, 0, err)
        self.assertTrue(self.staged.is_file())

    def test_empty_name_refused_before_resolver(self):
        rc, out, err = sp.activate("", str(self.tmp), resolver=None)
        self.assertEqual(rc, 2)
        self.assertIn("named plan", err)


class TestStagedIsInactive(unittest.TestCase):
    """The load-bearing invariant: a staged plan is invisible to the queue reader."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sp-inactive-"))
        self.harness = self.tmp / ".harness"
        (self.harness / "queued-plans").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_queue_status_does_not_list_staged_plans(self):
        # An active singleton + an active named plan ARE listed; a staged plan in
        # the queued-plans/ subdir is NOT (the reader's PLAN-*.md glob is
        # non-recursive, so the subdir is skipped — staged == inactive).
        (self.harness / "PLAN.md").write_text("**Status:** in-progress\n", encoding="utf-8")
        (self.harness / "PLAN-active.md").write_text("**Status:** planning\n", encoding="utf-8")
        staged = self.harness / "queued-plans" / "PLAN-staged.md"
        staged.write_text("**Status:** planning\n", encoding="utf-8")

        listed = qs._list_plan_files(self.harness)
        names = {p.name for p in listed}
        self.assertIn("PLAN.md", names)
        self.assertIn("PLAN-active.md", names)
        self.assertNotIn("PLAN-staged.md", names)
        self.assertNotIn(staged, listed)


class TestMainCLI(unittest.TestCase):
    """End-to-end main() over the fallback backend (forced via the auto-locator)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sp-main-"))
        # Force the standalone fallback regardless of the real machine's agentm
        # install: point resolve_plan's auto-locator at nothing.
        self._saved = sp.resolve_plan.locate_resolver
        sp.resolve_plan.locate_resolver = lambda **_k: None

    def tearDown(self):
        sp.resolve_plan.locate_resolver = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = sp.main(["stage_plan.py", *argv])
        return rc, out.getvalue(), err.getvalue()

    def test_main_path(self):
        rc, out, _ = self._run("path", "foo", "--project-root", str(self.tmp))
        self.assertEqual(rc, 0)
        expected = self.tmp / ".harness" / "queued-plans" / "PLAN-foo.md"
        self.assertEqual(out.strip(), str(expected))

    def test_main_path_singleton_nonzero(self):
        rc, out, err = self._run("path", "PLAN", "--project-root", str(self.tmp))
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("named plan", err)

    def test_main_activate(self):
        queued = self.tmp / ".harness" / "queued-plans"
        queued.mkdir(parents=True, exist_ok=True)
        (queued / "PLAN-foo.md").write_text("# Plan: foo\n", encoding="utf-8")
        rc, out, err = self._run("activate", "foo", "--project-root", str(self.tmp))
        self.assertEqual(rc, 0, err)
        active = self.tmp / ".harness" / "PLAN-foo.md"
        self.assertTrue(active.is_file())
        self.assertEqual(out.strip(), str(active))


if __name__ == "__main__":
    unittest.main()
