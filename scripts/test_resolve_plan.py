#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/resolve_plan.py (multi-plan writers T2).

The bridge has two backends with one contract: **delegate** to agentm's
process seam (`state-path plan`, `progress` and `tracker`) when discoverable,
else a standalone `.harness/` **fallback**. Every test is hermetic — the
delegate branch is exercised with a planted *stub* seam and the fallback via
`seam=None`, so nothing here depends on a real agentm clone (CI runs with none).
"""
from __future__ import annotations

import importlib.util
import io
import contextlib
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
_SRC = _ROOT / "src" / "development-lifecycle" / "scripts" / "resolve_plan.py"


def _load():
    spec = importlib.util.spec_from_file_location("resolve_plan", _SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["resolve_plan"] = m
    spec.loader.exec_module(m)
    return m


rp = _load()


def _write_stub(path: Path, body: str) -> Path:
    """A throwaway seam stub that stands in for agentm's process_seam.py."""
    path.write_text(body, encoding="utf-8")
    return path


# A seam stub for the layouts agentm answers. It answers
# `state-path {plan|progress|tracker} [--plan NAME] --cwd ROOT` the way agentm's
# seam does: `042-build-the-brief` is a numbered task in a vault project; no
# --plan is the singleton and any other name a flat pair, both in the repo-local
# `.harness/` agentm keeps for a repo with no vault (task 101, ruling 8). $STUB_SEAM_BARE_EXIT makes a bare
# call exit with that code instead (agentm-vault plan 10's answer on a project
# that keeps tasks), and $STUB_SEAM_NO_TRACKER makes `tracker` an invalid
# choice, as it is for a seam from before the tracker.
_LAYOUT_SEAM = r'''
import os, sys
argv = sys.argv[1:]
which = argv[1]
name = argv[argv.index("--plan") + 1] if "--plan" in argv else None
project = "/v/projects/probe"
repo = "/r/repo"
if which == "tracker" and os.environ.get("STUB_SEAM_NO_TRACKER"):
    sys.stderr.write("process_seam state-path: error: invalid choice: 'tracker'\n")
    sys.exit(2)
if name is None and os.environ.get("STUB_SEAM_BARE_EXIT"):
    sys.stderr.write("[process_seam] this project keeps tasks\n")
    sys.exit(int(os.environ["STUB_SEAM_BARE_EXIT"]))
if name is None:
    files = {"plan": "PLAN.md", "progress": "progress.md", "tracker": "tracker.md"}
    print(f"{repo}/.harness/{files[which]}")
elif name == "042-build-the-brief":
    files = {"plan": "plan.md", "progress": "progress.md", "tracker": "tracker.md"}
    print(f"{project}/tasks/{name}/{files[which]}")
else:
    files = {"plan": f"PLAN-{name}.md", "progress": f"progress-{name}.md",
             "tracker": f"tracker-{name}.md"}
    print(f"{repo}/.harness/{files[which]}")
sys.exit(0)
'''


class TestNameMapping(unittest.TestCase):
    """What a plan name means — the surface agentm's seam accepts."""

    def test_normalize_singleton_forms(self):
        for form in ("", "   ", "PLAN", "PLAN.md"):
            self.assertEqual(rp._normalize_plan_name(form), "")

    def test_normalize_named_forms(self):
        for form in ("foo", "PLAN-foo", "PLAN-foo.md"):
            self.assertEqual(rp._normalize_plan_name(form), "foo")

    def test_safe_slug(self):
        for ok in ("foo", "foo-bar", "foo.bar", "v2"):
            self.assertTrue(rp._is_safe_plan_slug(ok), ok)
        for bad in ("", ".", "..", "../etc", "a/b", "a\\b"):
            self.assertFalse(rp._is_safe_plan_slug(bad), bad)


class TestNoSeam(unittest.TestCase):
    """No seam (`seam=None`) → no plan: development-lifecycle keeps its plans
    through agentm and composes no `.harness/` pair of its own (task 101)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-no-seam-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_bare_named_and_unsafe_calls_all_find_no_plan(self):
        for name in ("", "foo", "PLAN-foo.md", "../etc"):
            with self.subTest(name=name):
                rc, out, err = rp.resolve(name, str(self.tmp), seam=None)
                self.assertEqual((rc, out), (rp.NO_SEAM, ""))
                self.assertIn("keeps its plans through agentm", err)

    def test_nothing_is_written(self):
        rp.resolve("foo", str(self.tmp), seam=None)
        self.assertEqual(list(self.tmp.iterdir()), [])


class TestDelegation(unittest.TestCase):
    """A located seam is authoritative — its paths and exit code pass through.

    Stubs stand in for process_seam.py: they receive
    `state-path {plan|progress|tracker} [--plan SLUG] [--cwd ROOT]` and return
    one absolute path per call (or an error exit code). resolve_plan.py makes
    three calls and assembles the tab-separated line.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-delegate-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_d_returns_stub_pair_unchanged(self):
        # Stub returns one path per kind; resolve_plan reassembles the line.
        stub = _write_stub(
            self.tmp / "stub_ok.py",
            "import sys\n"
            "which = sys.argv[2]\n"
            "paths = {'plan': '/v/PLAN-foo.md', 'progress': '/v/progress-foo.md',"
            " 'tracker': '/v/tracker-foo.md'}\n"
            "sys.stdout.write(paths[which] + '\\n')\n"
            "sys.exit(0)\n",
        )
        rc, out, err = rp.resolve("foo", str(self.tmp), seam=stub)
        self.assertEqual(rc, 0)
        self.assertEqual(err, "")
        self.assertEqual(out, "/v/PLAN-foo.md\t/v/progress-foo.md\t/v/tracker-foo.md\n")

    def test_d_passes_plan_and_cwd_through(self):
        # Bridge forwards --plan and --cwd to each seam call.
        stub = _write_stub(
            self.tmp / "stub_echo.py",
            "import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\nsys.exit(0)\n",
        )
        rc, out, _ = rp.resolve("bar", "/proj/root", seam=stub)
        self.assertEqual(rc, 0)
        self.assertIn("state-path", out)
        self.assertIn("--plan", out)
        self.assertIn("bar", out)
        self.assertIn("--cwd", out)
        self.assertIn("/proj/root", out)

    def test_d_bare_omits_plan_flag(self):
        stub = _write_stub(
            self.tmp / "stub_echo2.py",
            "import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\nsys.exit(0)\n",
        )
        rc, out, _ = rp.resolve("", str(self.tmp), seam=stub)
        self.assertEqual(rc, 0)
        self.assertNotIn("--plan", out)

    def test_e_dangling_exit_propagates_no_singleton_fallback(self):
        # Risk #7 across the second hop: a seam that ran and refused must NOT
        # degrade to the singleton — its non-zero exit surfaces and no pair emitted.
        stub = _write_stub(
            self.tmp / "stub_dangling.py",
            "import sys\n"
            "sys.stderr.write('[process_seam] dangling .harness/active-plan marker\\n')\n"
            "sys.exit(2)\n",
        )
        rc, out, err = rp.resolve("", str(self.tmp), seam=stub)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertNotIn("PLAN.md", out)   # never the singleton
        self.assertNotEqual(err, "")       # error is surfaced

    def test_e_graceful_skip_exit_one_propagates(self):
        # rc 1 (seam present, no plan home for this project) also passes
        # through: a seam that answered is authoritative.
        stub = _write_stub(
            self.tmp / "stub_skip.py",
            "import sys\nsys.exit(1)\n",
        )
        rc, out, _ = rp.resolve("", str(self.tmp), seam=stub)
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")


class TestMainCLI(unittest.TestCase):
    """End-to-end main(): no seam is no plan; a seam's answers pass through."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-main-"))
        self._saved = rp._bridge.find_seam
        rp._bridge.find_seam = lambda: None

    def tearDown(self):
        rp._bridge.find_seam = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = rp.main(["resolve_plan.py", *argv])
        return rc, out.getvalue(), err.getvalue()

    def test_main_without_agentm_is_exit_1(self):
        for argv in ((), ("foo",)):
            with self.subTest(argv=argv):
                rc, out, err = self._run(*argv, "--project-root", str(self.tmp))
                self.assertEqual((rc, out), (1, ""))
                self.assertIn("no agentm process seam was found", err)

    def test_main_prints_three_fields_from_the_seam(self):
        seam = _write_stub(self.tmp / "seam.py", _LAYOUT_SEAM)
        rp._bridge.find_seam = lambda: seam
        with mock.patch.dict(os.environ, {"STUB_SEAM_BARE_EXIT": "", "STUB_SEAM_NO_TRACKER": ""}):
            rc, out, _ = self._run("042-build-the-brief", "--project-root", str(self.tmp))
        t = "/v/projects/probe/tasks/042-build-the-brief"
        self.assertEqual((rc, out.rstrip("\n").split("\t")),
                         (0, [f"{t}/plan.md", f"{t}/progress.md", f"{t}/tracker.md"]))

    def test_main_passes_exit_4_on_with_nothing_on_stdout(self):
        seam = _write_stub(self.tmp / "seam.py", _LAYOUT_SEAM)
        rp._bridge.find_seam = lambda: seam
        with mock.patch.dict(os.environ, {"STUB_SEAM_BARE_EXIT": "4"}):
            rc, out, err = self._run("--project-root", str(self.tmp))
        self.assertEqual((rc, out), (4, ""))
        self.assertIn("name the task", err)


class TestLayouts(unittest.TestCase):
    """The line in each layout agentm resolves (a numbered task in a vault
    project; the repo-local singleton and flat pair of a repo with no vault),
    and the two answers that aren't a whole line. The bridge passes each on."""

    _PROJECT = "/v/projects/probe"
    _REPO = "/r/repo"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-layouts-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.seam = _write_stub(self.tmp / "seam.py", _LAYOUT_SEAM)
        patcher = mock.patch.dict(os.environ, {"STUB_SEAM_BARE_EXIT": "",
                                               "STUB_SEAM_NO_TRACKER": ""})
        patcher.start()
        self.addCleanup(patcher.stop)

    def resolve(self, name: str) -> tuple[int, str, str]:
        return rp.resolve(name, str(self.tmp), seam=self.seam)

    def test_the_repo_local_singleton(self):
        h = f"{self._REPO}/.harness"
        self.assertEqual(self.resolve(""),
                         (0, f"{h}/PLAN.md\t{h}/progress.md\t{h}/tracker.md\n", ""))

    def test_a_repo_local_flat_pair(self):
        h = f"{self._REPO}/.harness"
        self.assertEqual(self.resolve("foo"),
                         (0, f"{h}/PLAN-foo.md\t{h}/progress-foo.md\t{h}/tracker-foo.md\n", ""))

    def test_a_numbered_task(self):
        t = f"{self._PROJECT}/tasks/042-build-the-brief"
        self.assertEqual(self.resolve("042-build-the-brief"),
                         (0, f"{t}/plan.md\t{t}/progress.md\t{t}/tracker.md\n", ""))

    def test_a_seam_from_before_the_tracker_leaves_the_field_empty(self):
        h = f"{self._REPO}/.harness"
        with mock.patch.dict(os.environ, {"STUB_SEAM_NO_TRACKER": "1"}):
            rc, out, err = self.resolve("foo")
        self.assertEqual(rc, 0)
        self.assertEqual(out, f"{h}/PLAN-foo.md\t{h}/progress-foo.md\t\n")
        self.assertIn("tracker field is empty", err)

    def test_a_bare_call_on_a_project_that_keeps_tasks_is_exit_4(self):
        with mock.patch.dict(os.environ, {"STUB_SEAM_BARE_EXIT": "4"}):
            rc, out, err = self.resolve("")
        self.assertEqual((rc, out), (4, ""))
        self.assertIn("name the task", err)
        self.assertEqual(rp.NAME_THE_TASK, 4)

    def test_a_named_call_on_that_project_still_resolves(self):
        t = f"{self._PROJECT}/tasks/042-build-the-brief"
        with mock.patch.dict(os.environ, {"STUB_SEAM_BARE_EXIT": "4"}):
            rc, out, _err = self.resolve("042-build-the-brief")
        self.assertEqual((rc, out), (0, f"{t}/plan.md\t{t}/progress.md\t{t}/tracker.md\n"))

    def test_field_one_is_still_the_plan_for_python_callers(self):
        # stage_plan.py and design_doc.py keep only split("\t", 1)[0].
        _rc, out, _err = self.resolve("042-build-the-brief")
        self.assertEqual(out.split("\t", 1)[0],
                         f"{self._PROJECT}/tasks/042-build-the-brief/plan.md")


def _real_seam() -> "Path | None":
    """agentm's own process_seam.py in a checkout, or None: $AGENTM_SCRIPTS_DIR,
    else the conventional ~/Antigravity/agentm clone."""
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    dirs = [Path(env_dir)] if env_dir else []
    dirs.append(Path.home() / "Antigravity" / "agentm" / "scripts")
    for d in dirs:
        if (d / "process_seam.py").is_file():
            return (d / "process_seam.py").resolve()
    return None


REAL_SEAM = _real_seam()


@unittest.skipIf(REAL_SEAM is None, "no agentm checkout with scripts/process_seam.py")
class TestRealSeam(unittest.TestCase):
    """The resolver through agentm's real seam, against a scratch vault: a
    numbered task by its full name, and a repo with no vault, whose repo-local
    pair agentm still serves (ruling 8), trackers included. Nothing
    points at the live vault or the operator's home: MEMORY_ROOT names the
    scratch vault, AGENTM_INSTALL_PREFIX a blank scratch prefix, HOME and
    XDG_CACHE_HOME scratch directories, and OBSIDIAN_VAULT_SCRIPTS this repo's
    own vault plugin."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-real-seam-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        vault = self.tmp / "vault"
        self.task = vault / "projects" / "probe" / "tasks" / "042-build-the-brief"
        self.task.mkdir(parents=True)
        (self.task / "plan.md").write_text("# Plan: Build the brief\n\n**Status:** planning\n",
                                           encoding="utf-8")
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
            "OBSIDIAN_VAULT_SCRIPTS": str(_ROOT / "src" / "obsidian-vault" / "scripts"),
            "XDG_CACHE_HOME": str(self.tmp / "cache"),
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("MEMORY_VAULT_PATH", None)

    def test_a_repo_with_no_vault_gets_its_repo_local_pair(self):
        bare = self.tmp / "bare"
        bare.mkdir()
        with mock.patch.dict(os.environ, {"MEMORY_ROOT": ""}):
            rc, out, err = rp.resolve("foo", str(bare), seam=REAL_SEAM)
        self.assertEqual(rc, 0, err)
        h = bare / ".harness"
        self.assertEqual(out, f"{h / 'PLAN-foo.md'}\t{h / 'progress-foo.md'}\t{h / 'tracker-foo.md'}\n")

    def test_a_numbered_task_by_its_full_name(self):
        rc, out, err = rp.resolve("042-build-the-brief", str(self.repo), seam=REAL_SEAM)
        self.assertEqual(rc, 0, err)
        t = self.task
        self.assertEqual(out, f"{t / 'plan.md'}\t{t / 'progress.md'}\t{t / 'tracker.md'}\n")


# ── Plan-name contract — golden vectors shared with the agentm twin ─────────────
# These two tables are duplicated VERBATIM in the agentm authority's test suite
# (agentm/scripts/test_resolve_active_plan.py, class PlanNameContractParity) so
# this standalone fallback normalizer can't drift from what agentm means. That's
# the disposition of the 2026-06-13 adversarial audit (finding ML2): no cross-repo
# import edge (DC-2), just one table asserted on both sides. Change a row here →
# change it there. `PLAN-PLAN.md` (singleton on both) and `foo\x00` (unsafe on
# both) are the two rows that encode the drifts the audit caught and this fix
# closed.
_PLAN_NAME_VECTORS = [
    ("", ("PLAN.md", "progress.md")),
    ("   ", ("PLAN.md", "progress.md")),
    ("PLAN", ("PLAN.md", "progress.md")),
    ("PLAN.md", ("PLAN.md", "progress.md")),
    ("PLAN-PLAN", ("PLAN.md", "progress.md")),
    ("PLAN-PLAN.md", ("PLAN.md", "progress.md")),
    ("foo", ("PLAN-foo.md", "progress-foo.md")),
    ("PLAN-foo", ("PLAN-foo.md", "progress-foo.md")),
    ("PLAN-foo.md", ("PLAN-foo.md", "progress-foo.md")),
    ("  PLAN-foo.md  ", ("PLAN-foo.md", "progress-foo.md")),
    ("my-plan", ("PLAN-my-plan.md", "progress-my-plan.md")),
]

_PLAN_SLUG_SAFETY = [
    ("foo", True), ("foo-bar", True), ("foo.bar", True), ("v2", True),
    (".", False), ("..", False), ("a/b", False), ("a\\b", False), ("foo\x00", False),
]


class PlanNameContractParity(unittest.TestCase):
    """The name + slug-safety contract `stage_plan.py` and `worktree_marker.py`
    check before asking agentm, which is the authority; these vectors pin the
    meaning so the pre-check can't drift from it. Each vector's pair is the
    flat file a name used to mean; the slug is what it names now."""

    def test_name_to_pair_golden_vectors(self):
        for name, (plan_file, _progress) in _PLAN_NAME_VECTORS:
            want = "" if plan_file == "PLAN.md" else plan_file[len("PLAN-"):-len(".md")]
            self.assertEqual(rp._normalize_plan_name(name), want, f"name={name!r}")

    def test_slug_safety_golden_vectors(self):
        for slug, expected in _PLAN_SLUG_SAFETY:
            self.assertEqual(rp._is_safe_plan_slug(slug), expected, f"slug={slug!r}")


if __name__ == "__main__":
    unittest.main()
