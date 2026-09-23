#!/usr/bin/env python3
"""Tests for src/development-lifecycle/scripts/stage_plan.py (V5-10 sibling #1;
both plan layouts since PLAN-tracker-commands task 4).

Two-tier named-plan staging composed onto `resolve_plan`. The staging path is
derived from the resolver's output, so we exercise *both* backends — the
standalone `.harness/` fallback (`resolver=None`) and a planted stub that stands
in for agentm's process seam (`resolver=<stub path>`), answering `state-path
plan`, `progress` and `tracker` one path per call — and three layouts: the
singleton (refused), a flat named plan, and a numbered task
(`tasks/042-build-the-brief/`). Tracker reads and moves go through a stub
tracker.py under $AGENTM_SCRIPTS_DIR. The activate guards run over
throwaway tmp dirs. No test reaches a real seam except the real-bridge class,
which runs against a scratch vault and skips when no agentm checkout is found.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS = _ROOT / "src" / "development-lifecycle" / "scripts"


def _load(name: str):
    src = _SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, src)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


sp = _load("stage_plan")


def _write_stub(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def _seam_stub(path: Path, plan, progress, tracker, *, exit_code: int = 0) -> Path:
    """A stub process_seam.py that answers `state-path {plan|progress|tracker}`
    one path per call, the way agentm's seam does. `tracker=None` makes the
    tracker call an invalid choice, as it is for a seam from before the tracker;
    a non-zero `exit_code` makes every call exit with it."""
    answers = {"plan": str(plan), "progress": str(progress)}
    if tracker is not None:
        answers["tracker"] = str(tracker)
    return _write_stub(path, (
        "import sys\n"
        f"answers = {answers!r}\n"
        f"if {exit_code}:\n"
        "    sys.stderr.write('[process_seam] refused\\n')\n"
        f"    sys.exit({exit_code})\n"
        "which = sys.argv[2]\n"
        "if which not in answers:\n"
        "    sys.stderr.write('invalid choice: ' + which + '\\n')\n"
        "    sys.exit(2)\n"
        "print(answers[which])\n"
        "sys.exit(0)\n"
    ))


# A stand-in for agentm's tracker.py: `show` prints a tracker's status from
# $STUB_TRACKER_STATE (a JSON map of path to status), and `transition` follows
# the real table, or refuses when $STUB_TRACKER_REFUSE is set.
_STUB_TRACKER = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
argv = sys.argv[1:]
state_file = Path(os.environ["STUB_TRACKER_STATE"])
state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
if argv[0] == "show":
    if argv[1] not in state:
        sys.stderr.write("tracker: no such tracker\n")
        sys.exit(2)
    print(json.dumps({"status": state[argv[1]]}))
    sys.exit(0)
if argv[0] == "transition":
    current, to = state[argv[1]], argv[argv.index("--to") + 1]
    moves = {"queued": ("active", "dropped"), "active": ("parked", "done", "dropped"),
             "parked": ("active", "dropped")}
    if os.environ.get("STUB_TRACKER_REFUSE") or to not in moves.get(current, ()):
        sys.stderr.write(f"tracker: a `{current}` tracker cannot become `{to}`\n")
        sys.exit(1)
    state[argv[1]] = to
    state_file.write_text(json.dumps(state), encoding="utf-8")
    print(f"{argv[1]}: {current} -> {to}")
    sys.exit(0)
sys.exit(2)
'''


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
        stub = _seam_stub(self.tmp / "stub_ok.py", "/v/_harness/PLAN-foo.md",
                          "/v/_harness/progress-foo.md", "/v/_harness/tracker-foo.md")
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
        stub = _seam_stub(self.tmp / "stub_active.py", plan_p, prog_p, vault / "tracker-foo.md")
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


# TestStagedIsInactive retired with task 101 step 1: it proved a flat plan staged
# in queued-plans/ was invisible to queue_status.py's own lister. That lister is
# gone (agentm's reader lists plans, and a staged task is inert by its queued
# tracker), and step 2 retires flat staging itself.


class TestMainCLI(unittest.TestCase):
    """End-to-end main() over the fallback backend (forced via the auto-locator)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sp-main-"))
        # Force the standalone fallback regardless of the real machine's agentm
        # install: point the bridge's seam discovery at nothing, so no test here
        # reaches a real seam. (locate_resolver, which this patched before, is
        # not on resolve()'s path.)
        self._saved = sp.resolve_plan._bridge.find_seam
        sp.resolve_plan._bridge.find_seam = lambda: None
        # Also isolate the R2.5 task 12 vault-mismatch guard — main() has no CLI
        # flag to inject vault_check, so patch the module default directly.
        self._saved_vault_check = sp.resolve_plan._vault_configured_and_reachable
        sp.resolve_plan._vault_configured_and_reachable = lambda **_k: False

    def tearDown(self):
        sp.resolve_plan._bridge.find_seam = self._saved
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


class _Layouts:
    """A scratch vault project holding a flat plan's `_harness/` and the numbered
    task `042-build-the-brief`, a stub tracker.py under $AGENTM_SCRIPTS_DIR, and
    a Path.home() with no agentm clone under it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sp-layouts-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        scripts = self.tmp / "agentm" / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "tracker.py").write_text(_STUB_TRACKER, encoding="utf-8")
        home = self.tmp / "home"
        home.mkdir()
        self.state = self.tmp / "tracker-state.json"
        for patcher in (
            mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(scripts),
                                         "STUB_TRACKER_STATE": str(self.state),
                                         "STUB_TRACKER_REFUSE": ""}),
            mock.patch.object(Path, "home", return_value=home),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        project = self.tmp / "vault" / "projects" / "probe"
        self.harness = project / "_harness"
        (self.harness / "queued-plans").mkdir(parents=True)
        self.task = project / "tasks" / "042-build-the-brief"
        self.task.mkdir(parents=True)
        (self.task / "plan.md").write_text("# Plan: Build the brief\n\n**Status:** planning\n",
                                           encoding="utf-8")
        self.root = self.tmp / "repo"
        self.root.mkdir()

    def flat_seam(self, *, tracker: bool = True) -> Path:
        return _seam_stub(self.tmp / "seam-flat.py", self.harness / "PLAN-foo.md",
                          self.harness / "progress-foo.md",
                          self.harness / "tracker-foo.md" if tracker else None)

    def task_seam(self, *, exit_code: int = 0) -> Path:
        return _seam_stub(self.tmp / "seam-task.py", self.task / "plan.md",
                          self.task / "progress.md", self.task / "tracker.md",
                          exit_code=exit_code)

    def stage_flat(self, body: str = "# Plan: foo\n\n**Status:** planning\n") -> None:
        (self.harness / "queued-plans" / "PLAN-foo.md").write_text(body, encoding="utf-8")

    def set_tracker(self, path: Path, status: str) -> None:
        state = json.loads(self.state.read_text(encoding="utf-8")) if self.state.exists() else {}
        state[str(path)] = status
        self.state.write_text(json.dumps(state), encoding="utf-8")
        path.write_text("tracker\n", encoding="utf-8")

    def status_of(self, path: Path) -> str:
        return json.loads(self.state.read_text(encoding="utf-8"))[str(path)]

    def ship(self, rel: str) -> None:
        shipped = self.root / rel
        shipped.parent.mkdir(parents=True, exist_ok=True)
        shipped.write_text("shipped\n", encoding="utf-8")


class TestPathInBothLayouts(_Layouts, unittest.TestCase):

    def test_the_singleton_is_refused_by_both_verbs(self):
        for verb in (sp.staging_path, sp.activate):
            with self.subTest(verb=verb.__name__):
                rc, out, err = verb("PLAN.md", str(self.root), resolver=self.flat_seam())
                self.assertEqual((rc, out), (2, ""))
                self.assertIn("named plan", err)

    def test_a_flat_plan_stages_in_queued_plans_beside_it(self):
        rc, out, err = sp.staging_path("foo", str(self.root), resolver=self.flat_seam())
        self.assertEqual((rc, err), (0, ""))
        self.assertEqual(Path(out.strip()), self.harness / "queued-plans" / "PLAN-foo.md")

    def test_a_task_stages_as_its_own_plan_never_in_queued_plans(self):
        rc, out, err = sp.staging_path("042-build-the-brief", str(self.root),
                                       resolver=self.task_seam())
        self.assertEqual((rc, err), (0, ""))
        self.assertEqual(Path(out.strip()), self.task / "plan.md")
        self.assertNotIn("queued-plans", out)

    def test_exit_4_passes_through_both_verbs(self):
        seam = self.task_seam(exit_code=4)
        for verb in (sp.staging_path, sp.activate):
            with self.subTest(verb=verb.__name__):
                rc, out, _err = verb("build-the-brief", str(self.root), resolver=seam)
                self.assertEqual((rc, out), (4, ""))


class TestActivateFlatTracker(_Layouts, unittest.TestCase):

    def activate(self, **seam):
        return sp.activate("foo", str(self.root), resolver=self.flat_seam(**seam))

    def test_with_no_tracker_it_copies_only(self):
        self.stage_flat()
        rc, out, err = self.activate()
        self.assertEqual(rc, 0, err)
        self.assertEqual(Path(out.strip()), self.harness / "PLAN-foo.md")
        self.assertTrue((self.harness / "PLAN-foo.md").is_file())
        self.assertFalse(self.state.exists())

    def test_a_seam_from_before_the_tracker_copies_only(self):
        self.stage_flat()
        rc, _out, err = self.activate(tracker=False)
        self.assertEqual(rc, 0, err)
        self.assertTrue((self.harness / "PLAN-foo.md").is_file())

    def test_a_queued_tracker_moves_to_active_after_the_copy(self):
        self.stage_flat()
        tracker = self.harness / "tracker-foo.md"
        self.set_tracker(tracker, "queued")
        rc, _out, err = self.activate()
        self.assertEqual(rc, 0, err)
        self.assertTrue((self.harness / "PLAN-foo.md").is_file())
        self.assertEqual(self.status_of(tracker), "active")

    def test_a_tracker_that_is_not_queued_is_refused_before_anything_is_written(self):
        self.stage_flat()
        tracker = self.harness / "tracker-foo.md"
        for status in ("active", "parked", "done"):
            with self.subTest(status=status):
                self.set_tracker(tracker, status)
                rc, out, err = self.activate()
                self.assertEqual((rc, out), (2, ""))
                self.assertIn(f"is {status}", err)
                self.assertFalse((self.harness / "PLAN-foo.md").exists())
                self.assertEqual(self.status_of(tracker), status)

    def test_a_failed_move_after_the_copy_says_the_plan_was_activated(self):
        self.stage_flat()
        tracker = self.harness / "tracker-foo.md"
        self.set_tracker(tracker, "queued")
        with mock.patch.dict(os.environ, {"STUB_TRACKER_REFUSE": "1"}):
            rc, out, err = self.activate()
        self.assertEqual((rc, out), (2, ""))
        self.assertTrue((self.harness / "PLAN-foo.md").is_file())
        self.assertIn("activated", err)
        self.assertIn("not moved", err)
        self.assertEqual(self.status_of(tracker), "queued")

    def test_lc6_is_exit_3_and_moves_nothing(self):
        self.stage_flat("---\nexpected_artifacts: [src/done.py]\n---\n# Plan: foo\n")
        self.ship("src/done.py")
        tracker = self.harness / "tracker-foo.md"
        self.set_tracker(tracker, "queued")
        rc, out, _err = self.activate()
        self.assertEqual((rc, out), (3, ""))
        self.assertFalse((self.harness / "PLAN-foo.md").exists())
        self.assertEqual(self.status_of(tracker), "queued")


class TestActivateTask(_Layouts, unittest.TestCase):

    def activate(self):
        return sp.activate("042-build-the-brief", str(self.root), resolver=self.task_seam())

    def test_a_queued_task_activates_by_its_transition(self):
        tracker = self.task / "tracker.md"
        self.set_tracker(tracker, "queued")
        before = (self.task / "plan.md").read_bytes()
        rc, out, err = self.activate()
        self.assertEqual(rc, 0, err)
        self.assertEqual(Path(out.strip()), self.task / "plan.md")
        self.assertEqual(self.status_of(tracker), "active")
        self.assertEqual((self.task / "plan.md").read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.task.iterdir()), ["plan.md", "tracker.md"])
        self.assertEqual([p.name for p in self.harness.iterdir()], ["queued-plans"])

    def test_a_task_with_no_tracker_is_refused(self):
        rc, out, err = self.activate()
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("no tracker", err)

    def test_a_task_already_active_is_refused(self):
        tracker = self.task / "tracker.md"
        self.set_tracker(tracker, "active")
        rc, out, err = self.activate()
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("is active", err)
        self.assertEqual(self.status_of(tracker), "active")

    def test_lc6_is_exit_3_and_leaves_the_tracker_queued(self):
        (self.task / "plan.md").write_text(
            "---\nexpected_artifacts: [src/done.py]\n---\n# Plan: Build the brief\n",
            encoding="utf-8")
        self.ship("src/done.py")
        tracker = self.task / "tracker.md"
        self.set_tracker(tracker, "queued")
        rc, out, _err = self.activate()
        self.assertEqual((rc, out), (3, ""))
        self.assertEqual(self.status_of(tracker), "queued")


def _real_agentm_scripts() -> "Path | None":
    """An agentm checkout's scripts dir holding both process_seam.py and
    tracker.py: $AGENTM_SCRIPTS_DIR, else the conventional clone; else None."""
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    dirs = [Path(env_dir)] if env_dir else []
    dirs.append(Path.home() / "Antigravity" / "agentm" / "scripts")
    for d in dirs:
        if (d / "process_seam.py").is_file() and (d / "tracker.py").is_file():
            return d.resolve()
    return None


REAL_AGENTM = _real_agentm_scripts()


@unittest.skipIf(REAL_AGENTM is None, "no agentm checkout with process_seam.py and tracker.py")
class TestRealBridge(unittest.TestCase):
    """Both activations through agentm's real seam and tracker.py, in a scratch
    vault: a flat staged plan with a queued tracker, and a queued
    `tasks/042-build-the-brief/`. Nothing points at the live vault or the
    operator's home."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sp-real-bridge-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        vault = self.tmp / "vault"
        self.harness = vault / "projects" / "probe" / "_harness"
        (self.harness / "queued-plans").mkdir(parents=True)
        self.task = vault / "projects" / "probe" / "tasks" / "042-build-the-brief"
        self.task.mkdir(parents=True)
        self.repo = self.tmp / "repo"
        (self.repo / ".harness").mkdir(parents=True)
        (self.repo / ".harness" / "project.json").write_text(
            json.dumps({"vault_project": "probe"}), encoding="utf-8")
        home = self.tmp / "home"
        (home / ".claude").mkdir(parents=True)
        patcher = mock.patch.dict(os.environ, {
            "HOME": str(home),
            "AGENTM_INSTALL_PREFIX": str(home / ".claude"),
            "MEMORY_ROOT": str(vault),
            "AGENTM_SCRIPTS_DIR": str(REAL_AGENTM),
            "OBSIDIAN_VAULT_SCRIPTS": str(_ROOT / "src" / "obsidian-vault" / "scripts"),
            "XDG_CACHE_HOME": str(self.tmp / "cache"),
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("MEMORY_VAULT_PATH", None)
        self.seam = REAL_AGENTM / "process_seam.py"

    def run_tracker(self, *args: str) -> str:
        code, out, err = sp.resolve_plan._bridge.run_tracker(list(args))
        self.assertEqual(code, 0, err)
        return out

    def open_queued(self, path: Path, task: str) -> None:
        self.run_tracker("new", "--title", "Probe", "--project", "probe", "--task", task,
                         "--objective", "It activates.", "--next", "Step 1: activate",
                         "--out", str(path))

    def status_of(self, path: Path) -> str:
        return json.loads(self.run_tracker("show", str(path)))["status"]

    # The flat staged plan's real-bridge case retired with agentm #680
    # (agentm-vault part 15): agentm no longer answers a flat pair, so a staged
    # `queued-plans/` copy has no active path to land on. Task 101 retires the
    # flat branch stage_plan.py still carries.

    def test_a_queued_numbered_task(self):
        (self.task / "plan.md").write_text("# Plan: Build the brief\n\n**Status:** planning\n",
                                           encoding="utf-8")
        tracker = self.task / "tracker.md"
        self.open_queued(tracker, "042-build-the-brief")
        rc, out, err = sp.activate("042-build-the-brief", str(self.repo), resolver=self.seam)
        self.assertEqual(rc, 0, err)
        self.assertEqual(Path(out.strip()), self.task / "plan.md")
        self.assertEqual(self.status_of(tracker), "active")


if __name__ == "__main__":
    unittest.main()
