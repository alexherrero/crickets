#!/usr/bin/env python3
"""Tests for project_homes.py — the one pinned way a plugin asks agentm for a project's homes.

Four parts:
  - the copies: every plugin that asks ships the same bytes;
  - the verbs against a stub agentm (`no_harness_fixture.ScratchProject`);
  - the ways agentm gives no answer: absent, no home, a refusal, a timeout;
  - the real agentm, against a scratch vault, when a checkout with
    `process_seam.py project-path` is present.
"""
from __future__ import annotations

import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import no_harness_fixture as nhf  # noqa: E402

# Every plugin that ships a copy. development-lifecycle joins in task 101.
COPIES = ("code-review", "design", "github-projects", "wiki", "tokens")
CANONICAL = ROOT / "src" / "code-review" / "scripts" / "project_homes.py"

_spec = importlib.util.spec_from_file_location("project_homes_under_test", CANONICAL)
ph = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ph)


class TheCopies(unittest.TestCase):
    def test_every_copy_is_byte_identical(self):
        want = CANONICAL.read_bytes()
        for plugin in COPIES:
            with self.subTest(plugin=plugin):
                path = ROOT / "src" / plugin / "scripts" / "project_homes.py"
                self.assertTrue(path.is_file(), f"{plugin} ships no project_homes.py")
                self.assertEqual(path.read_bytes(), want,
                                 f"{plugin}'s project_homes.py drifted from code-review's")

    def test_no_other_plugin_ships_one(self):
        found = sorted(p.parent.parent.name for p in (ROOT / "src").glob("*/scripts/project_homes.py"))
        self.assertEqual(found, sorted(COPIES))


class _Env(unittest.TestCase):
    """An isolated HOME, so the conventional ~/Antigravity/agentm clone is not found."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)

    def use(self, scripts_dir: "Path | None"):
        env = {"HOME": str(self.home), "AGENTM_SCRIPTS_DIR": str(scripts_dir or "")}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def stub(self, name: str, body: str) -> Path:
        d = self.home / "agentm-stub"
        d.mkdir(exist_ok=True)
        (d / name).write_text(body, encoding="utf-8")
        return d


class Home(_Env):
    def test_each_home_from_a_bound_repo(self):
        with nhf.ScratchProject() as sp:
            self.use(sp.agentm)
            for kind, want in (("tasks", sp.project / "tasks"), ("designs", sp.designs),
                               ("desk", sp.desk)):
                with self.subTest(kind=kind):
                    self.assertEqual(ph.ask_home(kind, cwd=sp.repo), (0, want, ""))
                    self.assertEqual(ph.home(kind, cwd=sp.repo), want)

    def test_project_passes_through(self):
        with nhf.ScratchProject() as sp:
            self.use(sp.agentm)
            self.assertEqual(ph.home("desk", project="other"), sp.projects / "other" / "desk")

    def test_home_creates_nothing(self):
        with nhf.ScratchProject() as sp:
            shutil.rmtree(sp.desk)
            self.use(sp.agentm)
            self.assertEqual(ph.home("desk", cwd=sp.repo), sp.desk)
            self.assertFalse(sp.desk.exists())
            self.assertEqual(nhf.harness_dirs(sp.root), [])

    def test_an_unknown_kind_is_refused(self):
        rc, path, reason = ph.ask_home("archive", cwd=".")
        self.assertEqual((rc, path), (2, None))
        self.assertIn("unknown home", reason)


class Plans(_Env):
    def test_lists_the_task(self):
        with nhf.ScratchProject() as sp:
            self.use(sp.agentm)
            self.assertEqual(ph.plans(sp.repo), [sp.plan])

    def test_skips_the_active_binding_line(self):
        d = self.stub("harness_memory.py",
                      "print('/v/projects/demo/tasks/042-x/plan.md')\nprint('active-binding=042-x')\n")
        self.use(d)
        self.assertEqual(ph.plans("."), [Path("/v/projects/demo/tasks/042-x/plan.md")])

    def test_absent_agentm_is_none(self):
        self.use(None)
        rc, found, reason = ph.ask_plans(cwd=".")
        self.assertEqual((rc, found), (ph.NO_ANSWER, []))
        self.assertIn("not installed", reason)
        self.assertIsNone(ph.plans("."))


class NoAnswer(_Env):
    def test_agentm_absent(self):
        self.use(None)
        rc, path, reason = ph.ask_home("desk", cwd=".")
        self.assertEqual((rc, path), (ph.NO_ANSWER, None))
        self.assertIn("not installed", reason)

    def test_no_home_for_the_project(self):
        with nhf.ScratchProject(no_home=True) as sp:
            self.use(sp.agentm)
            rc, path, reason = ph.ask_home("desk", cwd=sp.repo)
            self.assertEqual((rc, path), (ph.NO_ANSWER, None))
            self.assertIn("no vault home", reason)

    def test_a_refusal_is_2(self):
        d = self.stub("process_seam.py",
                      "import sys\nsys.stderr.write('unsafe slug')\nsys.exit(2)\n")
        self.use(d)
        self.assertEqual(ph.ask_home("desk", project="../x"), (2, None, "unsafe slug"))

    def test_an_agentm_without_the_verb(self):
        d = self.stub("process_seam.py",
                      "import sys\nsys.stderr.write(\"invalid choice: 'project-path'\")\nsys.exit(2)\n")
        self.use(d)
        rc, _, reason = ph.ask_home("desk", cwd=".")
        self.assertEqual(rc, 2)
        self.assertIn("project-path", reason)

    def test_a_timeout(self):
        d = self.stub("process_seam.py", "import time\ntime.sleep(5)\n")
        self.use(d)
        rc, path, reason = ph.ask_home("desk", cwd=".", timeout=0.5)
        self.assertEqual((rc, path), (ph.NO_ANSWER, None))
        self.assertIn("did not answer", reason)

    def test_a_non_utf8_byte_is_replaced(self):
        d = self.stub("process_seam.py",
                      "import sys\nsys.stdout.buffer.write(b'/v/d\\xffesk\\n')\n")
        self.use(d)
        self.assertEqual(ph.home("desk", cwd="."), Path("/v/d�esk"))


class TheCli(_Env):
    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = ph.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_home_prints_the_path(self):
        with nhf.ScratchProject() as sp:
            self.use(sp.agentm)
            self.assertEqual(self.run_main(["home", "desk", "--cwd", str(sp.repo)]),
                             (0, f"{sp.desk}\n", ""))

    def test_plans_prints_one_per_line(self):
        with nhf.ScratchProject() as sp:
            self.use(sp.agentm)
            self.assertEqual(self.run_main(["plans", "--cwd", str(sp.repo)]),
                             (0, f"{sp.plan}\n", ""))

    def test_no_answer_is_3_with_the_reason(self):
        self.use(None)
        rc, out, err = self.run_main(["home", "desk"])
        self.assertEqual((rc, out), (3, ""))
        self.assertIn("[project_homes]", err)

    def test_cwd_and_project_are_exclusive(self):
        with self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
            ph.main(["home", "desk", "--cwd", ".", "--project", "demo"])
        self.assertEqual(cm.exception.code, 2)


def _real_seam() -> "Path | None":
    seam = Path.home() / "Antigravity" / "agentm" / "scripts" / "process_seam.py"
    if not seam.is_file():
        return None
    r = subprocess.run([sys.executable, str(seam), "project-path", "--help"],
                       capture_output=True, text=True)
    return seam.parent if r.returncode == 0 else None


REAL = _real_seam()


@unittest.skipIf(REAL is None, "no agentm checkout with process_seam.py project-path")
class TheRealAgentm(unittest.TestCase):
    """The deployed agentm answers from a scratch vault, and writes nothing."""

    def setUp(self):
        self.sp = nhf.ScratchProject()
        self.addCleanup(self.sp.cleanup)
        (self.sp.root / "home").mkdir()
        patcher = mock.patch.dict(os.environ, {
            "AGENTM_SCRIPTS_DIR": str(REAL),
            "MEMORY_ROOT": str(self.sp.vault),
            "OBSIDIAN_VAULT_SCRIPTS": str(ROOT / "src" / "obsidian-vault" / "scripts"),
            "AGENTM_INSTALL_PREFIX": "",
            "HOME": str(self.sp.root / "home"),
            "XDG_CACHE_HOME": str(self.sp.root / "cache"),
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("MEMORY_VAULT_PATH", None)

    def test_homes_and_plans(self):
        sp = self.sp
        self.assertEqual(ph.home("desk", cwd=sp.repo), sp.desk)
        self.assertEqual(ph.home("designs", cwd=sp.repo), sp.designs)
        self.assertEqual(ph.home("tasks", project="demo"), sp.project / "tasks")
        self.assertEqual(ph.plans(sp.repo), [sp.plan])
        self.assertEqual(ph.plans(project="demo"), [sp.plan])
        self.assertEqual(nhf.harness_dirs(sp.root), [])


if __name__ == "__main__":
    unittest.main()
