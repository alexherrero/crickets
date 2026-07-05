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
from unittest import mock

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
        # Isolate from the real machine's own agentm config (R2.5 task 12's new
        # resolve_plan guard) — these tests exercise staging composition, not
        # the vault-mismatch guard, so force it off regardless of what this
        # machine's ~/.claude/.agentm-config.json actually says.
        self._saved_vault_check = sp.resolve_plan._vault_configured_and_reachable
        sp.resolve_plan._vault_configured_and_reachable = lambda **_k: False

    def tearDown(self):
        sp.resolve_plan._vault_configured_and_reachable = self._saved_vault_check
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
        # Compare as Path objects, not a forward-slash literal: staging_path emits
        # a native filesystem path (back-slashes on Windows), so the separator is
        # incidental — the assertion is that queued-plans/ is composed onto the
        # resolver's vault path.
        self.assertEqual(Path(out.strip()), Path("/v/_harness/queued-plans/PLAN-foo.md"))
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
        # Same isolation as TestStagingPath — activate() composes onto the same
        # resolve_plan.resolve(), so it inherits the R2.5 task 12 guard too.
        self._saved_vault_check = sp.resolve_plan._vault_configured_and_reachable
        sp.resolve_plan._vault_configured_and_reachable = lambda **_k: False

    def tearDown(self):
        sp.resolve_plan._vault_configured_and_reachable = self._saved_vault_check
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

    def test_symlink_at_active_is_refused_no_write_through(self):
        """Regression (DEFECT 1): a symlink at the active path is a collision —
        refused exit 2, never followed/written-through.

        `Path.exists()` returns False for a *dangling* symlink, so the old
        `active.exists()` guard let `shutil.copyfile` follow the link and write
        the staged bytes to its target — a path OUTSIDE the harness. The
        `os.path.lexists()` guard + the non-following `O_EXCL` create close it.
        Exercised for a dangling link (target absent) and a live link (target
        present), both pointing outside the harness.
        """
        self.staged.write_text("STAGED BYTES\n", encoding="utf-8")
        dangling = self.tmp / "OUTSIDE-dangling.md"          # target absent
        live = _write_stub(self.tmp / "OUTSIDE-live.md", "PRE-EXISTING\n")
        for flavor, target in (("dangling", dangling), ("live", live)):
            with self.subTest(flavor=flavor):
                if self.active.is_symlink() or self.active.exists():
                    self.active.unlink()
                self.active.symlink_to(target)
                rc, out, err = sp.activate("foo", str(self.tmp), resolver=None)
                self.assertEqual(rc, 2)
                self.assertEqual(out, "")
                self.assertIn("already exists", err)
                self.assertTrue(self.active.is_symlink())   # link left untouched, not deleted
        # Neither external target was written through.
        self.assertFalse(dangling.exists())
        self.assertEqual(live.read_text(encoding="utf-8"), "PRE-EXISTING\n")

    def test_toctou_oexcl_backstop_refuses_raced_in_file(self):
        """DEFECT 2: the O_EXCL create is the atomic backstop for the TOCTOU
        window. Defeat the early lexists() guard (simulate a worker landing the
        active plan *after* the check passes) and assert the create still
        refuses rather than clobber the file that raced in.
        """
        self.staged.write_text("STAGED\n", encoding="utf-8")
        real_lexists = sp.os.path.lexists

        def racy_lexists(p):
            if Path(p) == self.active:
                # The race: a concurrent activate/worker lands the active plan
                # in the check→create window — but the check already saw nothing.
                self.active.write_text("RACED-IN\n", encoding="utf-8")
                return False
            return real_lexists(p)

        with mock.patch.object(sp.os.path, "lexists", racy_lexists):
            rc, out, err = sp.activate("foo", str(self.tmp), resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("already exists", err)
        # The raced-in active plan is NOT clobbered by the staged bytes.
        self.assertEqual(self.active.read_text(encoding="utf-8"), "RACED-IN\n")

    def test_activate_uses_delegate_resolver_output_not_dot_harness(self):
        """The "both backends" claim must hold for activate(), not just `path`:
        with agentm present, activate copies into the resolver-derived
        `_harness/` (here a vault-style dir with no `.harness`), never
        <root>/.harness — mirroring the staging_path delegate test.
        """
        vault = self.tmp / "vault" / "_harness"
        (vault / "queued-plans").mkdir(parents=True, exist_ok=True)
        (vault / "queued-plans" / "PLAN-foo.md").write_text(
            "STAGED-DELEGATE\n", encoding="utf-8")
        plan_p, prog_p = vault / "PLAN-foo.md", vault / "progress-foo.md"
        stub = _write_stub(
            self.tmp / "stub_active.py",
            "import sys\n"
            "sys.stdout.write(" + repr(f"{plan_p}\t{prog_p}\n") + ")\n"
            "sys.exit(0)\n",
        )
        rc, out, err = sp.activate("foo", str(self.tmp), resolver=stub)
        self.assertEqual(rc, 0, err)
        self.assertTrue(plan_p.is_file())
        self.assertEqual(plan_p.read_text(encoding="utf-8"), "STAGED-DELEGATE\n")
        self.assertEqual(out.strip(), str(plan_p))
        # Derived from the resolver, NOT <root>/.harness.
        self.assertFalse((self.tmp / ".harness" / "PLAN-foo.md").exists())

    def test_staging_path_and_activate_agree_on_staged_location(self):
        """staging_path() and activate() must derive the SAME staged path for a
        name — guards against future drift between the two derivations.
        """
        rc, staged_str, err = sp.staging_path("foo", str(self.tmp), resolver=None)
        self.assertEqual(rc, 0, err)
        staged = Path(staged_str.strip())
        self.assertEqual(staged, self.queued / "PLAN-foo.md")  # same as setUp's staged
        # Plant the staged plan ONLY at staging_path()'s location, then activate
        # must find it there (proving it reads the same derivation) and copy it.
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_text("AGREED\n", encoding="utf-8")
        rc, out, err = sp.activate("foo", str(self.tmp), resolver=None)
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.active.read_text(encoding="utf-8"), "AGREED\n")


class TestActivatePreflightReconcile(unittest.TestCase):
    """LC-6: `activate` no-ops (exit 3) on an already-shipped slug; proceeds on a
    pending one. The guard reads the STAGED plan's `expected_artifacts` frontmatter
    and checks each against the project ROOT (the repo, not the harness)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sp-reconcile-"))
        self.harness = self.tmp / ".harness"
        self.queued = self.harness / "queued-plans"
        self.queued.mkdir(parents=True, exist_ok=True)
        self.staged = self.queued / "PLAN-foo.md"
        self.active = self.harness / "PLAN-foo.md"
        self._saved_vault_check = sp.resolve_plan._vault_configured_and_reachable
        sp.resolve_plan._vault_configured_and_reachable = lambda **_k: False

    def tearDown(self):
        sp.resolve_plan._vault_configured_and_reachable = self._saved_vault_check
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _stage(self, *arts: str):
        inline = ", ".join(arts)
        self.staged.write_text(
            f"---\nexpected_artifacts: [{inline}]\n---\n# Plan: foo\n", encoding="utf-8")

    def _touch(self, rel: str):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("shipped\n", encoding="utf-8")

    def test_already_shipped_slug_is_a_noop_exit_3_writes_nothing(self):
        # Both declared artifacts already exist under root → already shipped.
        self._stage("src/new_a.py", "wiki/0099-x.md")
        self._touch("src/new_a.py")
        self._touch("wiki/0099-x.md")
        rc, out, err = sp.activate("foo", str(self.tmp), resolver=None)
        self.assertEqual(rc, 3)
        self.assertEqual(out, "")
        self.assertIn("already shipped — nothing to do", err)
        # The benign no-op writes nothing — no active plan is created.
        self.assertFalse(self.active.exists())

    def test_pending_slug_with_missing_artifacts_activates_normally(self):
        # One artifact missing → the lane still has work → activate as usual (rc 0).
        self._stage("src/new_a.py", "src/new_b.py")
        self._touch("src/new_a.py")  # only one of the two exists
        rc, out, err = sp.activate("foo", str(self.tmp), resolver=None)
        self.assertEqual(rc, 0, err)
        self.assertTrue(self.active.is_file())
        self.assertEqual(out.strip(), str(self.active))

    def test_plan_without_expected_artifacts_is_unaffected(self):
        # Back-compat: a staged plan that does not opt in activates byte-for-byte
        # as before, even though unrelated files exist in the repo.
        self.staged.write_text("# Plan: foo\n\n**Status:** planning\n", encoding="utf-8")
        self._touch("src/whatever.py")
        rc, out, err = sp.activate("foo", str(self.tmp), resolver=None)
        self.assertEqual(rc, 0, err)
        self.assertTrue(self.active.is_file())

    def test_reconcile_runs_before_the_collision_guard(self):
        # If the work is already shipped AND an active plan exists, "already
        # shipped" is the reported outcome (exit 3) — the more informative,
        # forward-looking signal — and the in-flight active is left untouched.
        self._stage("src/new_a.py")
        self._touch("src/new_a.py")
        self.active.write_text("ACTIVE-IN-FLIGHT\n", encoding="utf-8")
        rc, out, err = sp.activate("foo", str(self.tmp), resolver=None)
        self.assertEqual(rc, 3)
        self.assertIn("already shipped — nothing to do", err)
        self.assertEqual(self.active.read_text(encoding="utf-8"), "ACTIVE-IN-FLIGHT\n")


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
        # Also isolate the R2.5 task 12 vault-mismatch guard — main() has no CLI
        # flag to inject vault_check, so patch the module default directly.
        self._saved_vault_check = sp.resolve_plan._vault_configured_and_reachable
        sp.resolve_plan._vault_configured_and_reachable = lambda **_k: False

    def tearDown(self):
        sp.resolve_plan.locate_resolver = self._saved
        sp.resolve_plan._vault_configured_and_reachable = self._saved_vault_check
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
