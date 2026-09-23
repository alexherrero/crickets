#!/usr/bin/env python3
"""Tests for the `plans` verb of
src/development-lifecycle/scripts/agentm_bridge.py (PLAN-tracker-commands
task 1).

`plans` asks agentm for a project's active plans with one `harness_memory.py
list-plans`, then resolves each with `resolve-active-plan --with-tracker --plan
<name>`, and pairs every plan with the progress log and tracker agentm names
for it. The name is the file name for a flat plan and the directory's name for
a task, so these tests cover a repo-local singleton and flat named pair (what
agentm keeps for a repo with no vault) and a numbered task
(`tasks/042-build-the-brief/`). `--project SLUG` asks the same verbs about a
project with no checkout (crickets task 101, ruling 9).

A stub harness_memory.py plays agentm. It reads the listing and the resolver's
answers from a fixture.json in the project root it is handed ($STUB_FIXTURE_DIR
for a slug), and logs every argv to calls.jsonl beside it. $AGENTM_SCRIPTS_DIR points at the stub and
Path.home() at an empty directory, so no real agentm is reached.
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
_SRC = _ROOT / "src" / "development-lifecycle" / "scripts" / "agentm_bridge.py"


def _load():
    spec = importlib.util.spec_from_file_location("agentm_bridge_plans", _SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["agentm_bridge_plans"] = m
    spec.loader.exec_module(m)
    return m


ab = _load()

_STUB_HARNESS_MEMORY = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
argv = sys.argv[1:]
if "--project-root" in argv:
    root = Path(argv[argv.index("--project-root") + 1])
else:
    root = Path(os.environ["STUB_FIXTURE_DIR"])
fixture = json.loads((root / "fixture.json").read_text(encoding="utf-8"))
with (root / "calls.jsonl").open("a", encoding="utf-8") as log:
    log.write(json.dumps(argv) + "\n")
if argv[0] == "list-plans":
    for line in fixture["listed"]:
        print(line)
    sys.exit(fixture.get("list_exit", 0))
if argv[0] == "resolve-active-plan":
    if "--project" in argv and not fixture.get("resolve_by_slug", True):
        sys.stderr.write("harness_memory: error: unrecognized arguments: --project probe\n")
        sys.exit(2)
    if "--with-tracker" in argv and not fixture.get("with_tracker", True):
        sys.stderr.write("harness_memory: error: unrecognized arguments: --with-tracker\n")
        sys.exit(2)
    fields = fixture["resolve"].get(argv[argv.index("--plan") + 1])
    if fields is None:
        sys.stderr.write("[harness_memory] unsafe plan name\n")
        sys.exit(2)
    print("\t".join(fields if "--with-tracker" in argv else fields[:2]))
    sys.exit(0)
sys.exit(2)
'''


class _Project:
    """A repo-local singleton and `PLAN-foo.md`, the numbered task
    `042-build-the-brief` in a vault project, a repo root for agentm to be asked
    about, and a stub harness_memory.py answering for them."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bridge-plans-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        scripts = self.tmp / "agentm" / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "harness_memory.py").write_text(_STUB_HARNESS_MEMORY, encoding="utf-8")
        home = self.tmp / "home"
        home.mkdir()
        for patcher in (
            mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(scripts),
                                         "STUB_FIXTURE_DIR": str(self.tmp / "repo")}),
            mock.patch.object(ab.Path, "home", return_value=home),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

        self.root = self.tmp / "repo"
        self.root.mkdir()
        project = self.tmp / "vault" / "projects" / "probe"
        harness = self.root / ".harness"
        task = project / "tasks" / "042-build-the-brief"
        self.singleton = (str(harness / "PLAN.md"), str(harness / "progress.md"),
                          str(harness / "tracker.md"))
        self.flat = (str(harness / "PLAN-foo.md"), str(harness / "progress-foo.md"),
                     str(harness / "tracker-foo.md"))
        self.task = (str(task / "plan.md"), str(task / "progress.md"),
                     str(task / "tracker.md"))
        self.fixture = {
            "listed": [self.singleton[0], self.flat[0], self.task[0], "active-binding=foo"],
            "resolve": {
                "PLAN.md": list(self.singleton),
                "PLAN-foo.md": list(self.flat),
                "042-build-the-brief": list(self.task),
            },
        }

    def write_fixture(self, **changes):
        fixture = {**self.fixture, **changes}
        (self.root / "fixture.json").write_text(json.dumps(fixture), encoding="utf-8")

    def calls(self) -> "list[list[str]]":
        log = self.root / "calls.jsonl"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

    def main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ab.main(["agentm_bridge.py", *argv])
        return code, out.getvalue(), err.getvalue()


class TestRunListPlans(_Project, unittest.TestCase):

    def test_pairs_every_listed_plan_with_its_progress_and_tracker(self):
        self.write_fixture()
        self.assertEqual(ab.run_list_plans(self.root),
                         (0, [self.singleton, self.flat, self.task]))

    def test_the_resolver_gets_the_file_name_or_the_task_directory_name(self):
        self.write_fixture()
        ab.run_list_plans(self.root)
        calls = self.calls()
        self.assertEqual(calls[0], ["list-plans", "--project-root", str(self.root)])
        resolves = calls[1:]
        self.assertEqual([c[c.index("--plan") + 1] for c in resolves],
                         ["PLAN.md", "PLAN-foo.md", "042-build-the-brief"])
        for call in resolves:
            self.assertEqual(call[0], "resolve-active-plan")
            self.assertIn("--with-tracker", call)
            self.assertEqual(call[call.index("--project-root") + 1], str(self.root))

    def test_a_project_with_no_plans_lists_nothing(self):
        self.write_fixture(listed=[])
        self.assertEqual(ab.run_list_plans(self.root), (0, []))

    def test_an_agentm_from_before_the_tracker_leaves_the_tracker_field_empty(self):
        self.write_fixture(with_tracker=False)
        self.assertEqual(
            ab.run_list_plans(self.root),
            (0, [(plan, progress, "") for plan, progress, _tracker
                 in (self.singleton, self.flat, self.task)]))

    def test_a_plan_the_resolver_refuses_keeps_its_path_and_nothing_else(self):
        self.write_fixture(resolve={"PLAN.md": list(self.singleton),
                                    "042-build-the-brief": list(self.task)})
        self.assertEqual(ab.run_list_plans(self.root),
                         (0, [self.singleton, (self.flat[0], "", ""), self.task]))

    def test_a_plan_resolved_to_another_plan_is_not_paired_with_its_files(self):
        # A slug with both a task and a flat pair: the resolver answers the task.
        self.write_fixture(resolve={**self.fixture["resolve"], "PLAN-foo.md": list(self.task)})
        code, rows = ab.run_list_plans(self.root)
        self.assertEqual(code, 0)
        self.assertEqual(rows[1], (self.flat[0], "", ""))

    def test_exit_3_when_list_plans_fails(self):
        self.write_fixture(list_exit=1)
        self.assertEqual(ab.run_list_plans(self.root), (3, []))

    def test_exit_3_when_agentm_is_absent(self):
        self.write_fixture()
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}):
            self.assertEqual(ab.run_list_plans(self.root), (3, []))
        self.assertEqual(self.calls(), [])

    def test_exit_3_for_an_injected_path_that_is_gone(self):
        self.write_fixture()
        self.assertEqual(ab.run_list_plans(self.root, harness_memory=self.tmp / "gone.py"),
                         (3, []))


class TestRunListPlansBySlug(_Project, unittest.TestCase):
    """A project with no checkout, named by slug (ruling 9)."""

    def test_lists_and_resolves_by_slug(self):
        self.write_fixture(listed=[self.task[0]])
        self.assertEqual(ab.run_list_plans(project="probe"), (0, [self.task]))
        calls = self.calls()
        self.assertEqual(calls[0], ["list-plans", "--project", "probe"])
        self.assertEqual(calls[1][calls[1].index("--project") + 1], "probe")
        self.assertNotIn("--project-root", calls[1])
        self.assertIn("--with-tracker", calls[1])

    def test_an_agentm_without_resolve_by_slug_gives_partial_rows(self):
        self.write_fixture(listed=[self.task[0]], resolve_by_slug=False)
        self.assertEqual(ab.run_list_plans(project="probe"), (0, [(self.task[0], "", "")]))


class TestPlansVerb(_Project, unittest.TestCase):

    def test_registered_in_the_dispatcher(self):
        self.assertIn("plans", ab._VERBS)

    def test_prints_one_tab_separated_row_per_plan(self):
        self.write_fixture()
        code, out, err = self.main("plans", "--project-root", str(self.root))
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(),
                         ["\t".join(row) for row in (self.singleton, self.flat, self.task)])
        self.assertEqual(err, "")

    def test_notes_a_plan_it_could_not_pair(self):
        self.write_fixture(resolve={"PLAN.md": list(self.singleton),
                                    "042-build-the-brief": list(self.task)})
        code, out, err = self.main("plans", "--project-root", str(self.root))
        self.assertEqual(code, 0)
        self.assertIn(f"{self.flat[0]}\t\t", out.splitlines())
        self.assertIn(self.flat[0], err)

    def test_absent_agentm_exits_3_and_prints_nothing(self):
        self.write_fixture()
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}):
            code, out, _err = self.main("plans", "--project-root", str(self.root))
        self.assertEqual((code, out), (3, ""))

    def test_prints_the_rows_of_a_project_named_by_slug(self):
        self.write_fixture(listed=[self.task[0]])
        code, out, _err = self.main("plans", "--project", "probe")
        self.assertEqual((code, out.splitlines()), (0, ["\t".join(self.task)]))

    def test_project_and_project_root_together_are_a_usage_error(self):
        code, out, _err = self.main("plans", "--project", "probe", "--project-root", str(self.root))
        self.assertEqual((code, out), (2, ""))

    def test_an_unknown_flag_is_a_usage_error(self):
        code, out, _err = self.main("plans", "--root", str(self.root))
        self.assertEqual((code, out), (2, ""))


if __name__ == "__main__":
    unittest.main()
