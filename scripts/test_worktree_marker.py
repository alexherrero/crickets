#!/usr/bin/env python3
"""Tests for src/development-lifecycle/scripts/worktree_marker.py.

Binds an already-created worktree (this test builds a plain directory — no
`git worktree add`, since that's now the host primitive's job, not this
script's) to a named plan: the LC-6 pre-flight-reconcile guard, the bare-slug
marker write, and the LC-2 `vault_project` divergent-override copy. Ported
from test_spawn_worker.py's TestVaultProjectFallback / TestOriginBasename /
TestSpawnPreflightReconcile — same assertions, adapted to the new
create-then-bind split (spawn_worker.py bound to a worktree it had just
created via `git worktree add`; this binds to one the caller already has).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
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


wm = _load("worktree_marker")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo),
                          capture_output=True, text=True, check=True)


def _init_repo(repo: Path, *, origin: str | None = None) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "seed")
    if origin is not None:
        _git(repo, "remote", "add", "origin", origin)


class WorktreeMarkerTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wm-"))
        self.repo = self.tmp / "repo"
        self.worktree = self.tmp / "worktree"
        self.worktree.mkdir(parents=True, exist_ok=True)
        self.plan = self.tmp / "PLAN-foo.md"
        self.plan.write_text("# Plan: foo\n", encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _declare(self, *arts: str):
        inline = ", ".join(arts)
        self.plan.write_text(
            f"---\nexpected_artifacts: [{inline}]\n---\n# Plan: foo\n", encoding="utf-8")


class TestHappyPath(WorktreeMarkerTestCase):
    def test_writes_bare_slug_marker(self):
        _init_repo(self.repo)
        rc, out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        self.assertEqual((self.worktree / ".harness" / "active-plan").read_text(), "foo\n")

    def test_marker_round_trips_through_normalize(self):
        _init_repo(self.repo)
        rc, _out, err = wm.write_marker(self.worktree, "PLAN-foo.md", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        self.assertEqual((self.worktree / ".harness" / "active-plan").read_text(), "foo\n")

    def test_empty_slug_refused(self):
        _init_repo(self.repo)
        rc, _out, err = wm.write_marker(self.worktree, "", self.plan, self.repo)
        self.assertEqual(rc, 2)
        self.assertFalse((self.worktree / ".harness").exists())

    def test_missing_worktree_path_refused(self):
        _init_repo(self.repo)
        rc, _out, err = wm.write_marker(self.tmp / "nope", "foo", self.plan, self.repo)
        self.assertEqual(rc, 2)
        self.assertIn("does not exist", err)


class TestVaultProjectFallback(WorktreeMarkerTestCase):
    """LC-2: the `vault_project` copy fires only on a divergent override."""

    def _write_project_json(self, vault_project: str) -> None:
        h = self.repo / ".harness"
        h.mkdir(parents=True, exist_ok=True)
        (h / "project.json").write_text(
            json.dumps({"vault_project": vault_project}), encoding="utf-8")

    def test_copies_when_override_diverges_from_origin(self):
        _init_repo(self.repo, origin="https://github.com/org/myrepo.git")
        self._write_project_json("different")
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        copied = self.worktree / ".harness" / "project.json"
        self.assertTrue(copied.is_file())
        self.assertEqual(json.loads(copied.read_text())["vault_project"], "different")

    def test_copies_full_original_even_when_override_matches_origin(self):
        # The original document is always carried over verbatim once it
        # exists — the divergence check only decides whether vault_project
        # gets refreshed on top, not whether the file is written at all.
        _init_repo(self.repo, origin="example.com:org/myrepo.git")
        self._write_project_json("myrepo")
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        copied = self.worktree / ".harness" / "project.json"
        self.assertTrue(copied.is_file())
        self.assertEqual(json.loads(copied.read_text())["vault_project"], "myrepo")

    def test_no_copy_when_project_json_absent(self):
        _init_repo(self.repo, origin="https://github.com/org/myrepo.git")
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        self.assertFalse((self.worktree / ".harness" / "project.json").exists())
        self.assertEqual((self.worktree / ".harness" / "active-plan").read_text(), "foo\n")

    def test_origin_lookup_timeout_does_not_crash(self):
        _init_repo(self.repo, origin="https://github.com/org/myrepo.git")
        self._write_project_json("different")
        orig_git = wm._git

        def hang_on_remote_geturl(args, root):
            if args[:2] == ["remote", "get-url"]:
                raise subprocess.TimeoutExpired(cmd="git remote get-url origin", timeout=30)
            return orig_git(args, root)

        with mock.patch.object(wm, "_git", hang_on_remote_geturl):
            rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        self.assertEqual((self.worktree / ".harness" / "active-plan").read_text(), "foo\n")
        self.assertTrue((self.worktree / ".harness" / "project.json").is_file())

    def test_copies_when_override_present_but_no_origin(self):
        _init_repo(self.repo, origin=None)
        self._write_project_json("solo")
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        copied = self.worktree / ".harness" / "project.json"
        self.assertTrue(copied.is_file())
        self.assertEqual(json.loads(copied.read_text())["vault_project"], "solo")

    def test_read_vault_project_returns_none_for_non_object_json(self):
        self.repo.mkdir(parents=True, exist_ok=True)
        h = self.repo / ".harness"
        h.mkdir()
        for doc in ("[1, 2, 3]", '"a string"', "42", "true", "null"):
            (h / "project.json").write_text(doc, encoding="utf-8")
            self.assertIsNone(wm._read_vault_project(self.repo),
                              f"non-object project.json {doc!r} must collapse to None")

    def test_non_object_project_json_skips_copy_no_crash(self):
        _init_repo(self.repo, origin="https://github.com/org/myrepo.git")
        h = self.repo / ".harness"
        h.mkdir(parents=True, exist_ok=True)
        (h / "project.json").write_text("[1, 2, 3]", encoding="utf-8")
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        self.assertEqual((self.worktree / ".harness" / "active-plan").read_text(), "foo\n")
        self.assertFalse((self.worktree / ".harness" / "project.json").exists())


class TestIsolationBlockCarryover(WorktreeMarkerTestCase):
    """`.harness/` is gitignored, so a freshly host-created worktree has no
    project.json at all — `isolation_config.read_isolation()` run from inside
    it would otherwise always see the code-default, never the original repo's
    real isolation.mode/integration. Regression: found live running
    PLAN-worktree-native-flow's own task-9 acceptance demo — finalize_unit.py
    resolved mode=direct inside the worktree even though the original repo
    declared worktree-per-plan, and pushed without -u as a result."""

    def _write_isolation_cfg(self, mode: str, integration: str) -> None:
        h = self.repo / ".harness"
        h.mkdir(parents=True, exist_ok=True)
        (h / "project.json").write_text(
            json.dumps({"isolation": {"mode": mode, "integration": integration}}),
            encoding="utf-8")

    def test_isolation_block_carried_over_verbatim(self):
        _init_repo(self.repo)
        self._write_isolation_cfg("worktree-per-plan", "pull-request")
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        copied = json.loads((self.worktree / ".harness" / "project.json").read_text())
        self.assertEqual(copied["isolation"],
                         {"mode": "worktree-per-plan", "integration": "pull-request"})

    def test_isolation_carried_even_when_vault_project_does_not_diverge(self):
        # The old LC-2-only logic wrote NOTHING here (vault_project absent
        # entirely) — the isolation block must still land regardless.
        _init_repo(self.repo, origin="https://github.com/org/myrepo.git")
        self._write_isolation_cfg("worktree-per-plan", "pull-request")
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        copied = json.loads((self.worktree / ".harness" / "project.json").read_text())
        self.assertIn("isolation", copied)
        self.assertNotIn("vault_project", copied)

    def test_both_isolation_and_divergent_vault_project_carried_together(self):
        _init_repo(self.repo, origin="https://github.com/org/myrepo.git")
        h = self.repo / ".harness"
        h.mkdir(parents=True, exist_ok=True)
        (h / "project.json").write_text(json.dumps({
            "isolation": {"mode": "worktree-per-plan", "integration": "pull-request"},
            "vault_project": "different",
        }), encoding="utf-8")
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        copied = json.loads((self.worktree / ".harness" / "project.json").read_text())
        self.assertEqual(copied["isolation"]["mode"], "worktree-per-plan")
        self.assertEqual(copied["vault_project"], "different")

    def test_no_project_json_written_when_original_has_neither(self):
        _init_repo(self.repo)
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        self.assertFalse((self.worktree / ".harness" / "project.json").exists())

    def test_no_project_json_at_all_leaves_worktree_without_one(self):
        self.repo.mkdir(parents=True, exist_ok=True)
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        self.assertFalse((self.worktree / ".harness" / "project.json").exists())

    def test_non_isolation_keys_survive_the_copy(self):
        # Regression: check_project_sync.py / project_sync.py (github-projects
        # plugin) require `vault_project` and `github` in every .harness/
        # project.json they read, including inside a spawned worktree — a
        # rebuild from an isolation/vault_project-only allowlist silently
        # dropped `github` / `fields` / `items_source` and broke board-sync
        # for every plan worked under the worktree-per-plan flow.
        _init_repo(self.repo)
        h = self.repo / ".harness"
        h.mkdir(parents=True, exist_ok=True)
        (h / "project.json").write_text(json.dumps({
            "isolation": {"mode": "worktree-per-plan", "integration": "pull-request"},
            "vault_project": "crickets",
            "github": {"owner": "org", "number": 5, "url": "https://github.com/org/x", "repo": "x"},
            "fields": {"Status": "status-field-id"},
            "items_source": "gh-cli",
        }), encoding="utf-8")
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        copied = json.loads((self.worktree / ".harness" / "project.json").read_text())
        self.assertEqual(copied["github"]["owner"], "org")
        self.assertEqual(copied["fields"], {"Status": "status-field-id"})
        self.assertEqual(copied["items_source"], "gh-cli")


class TestOriginBasename(WorktreeMarkerTestCase):
    def test_https_url(self):
        _init_repo(self.repo, origin="https://github.com/org/myrepo.git")
        self.assertEqual(wm._origin_basename(self.repo), "myrepo")

    def test_scp_style_url(self):
        _init_repo(self.repo, origin="example.com:org/myrepo.git")
        self.assertEqual(wm._origin_basename(self.repo), "myrepo")

    def test_url_without_dot_git_suffix(self):
        _init_repo(self.repo, origin="https://github.com/org/plainname")
        self.assertEqual(wm._origin_basename(self.repo), "plainname")

    def test_no_origin_returns_none(self):
        _init_repo(self.repo, origin=None)
        self.assertIsNone(wm._origin_basename(self.repo))

    def test_git_timeout_collapses_to_none(self):
        _init_repo(self.repo, origin="https://github.com/org/myrepo.git")
        orig_git = wm._git

        def hang(args, root):
            if args[:2] == ["remote", "get-url"]:
                raise subprocess.TimeoutExpired(cmd="git remote get-url", timeout=30)
            return orig_git(args, root)

        with mock.patch.object(wm, "_git", hang):
            self.assertIsNone(wm._origin_basename(self.repo))


class TestPreflightReconcile(WorktreeMarkerTestCase):
    """LC-6 defense-in-depth: refuse (exit 3) before any write when already shipped."""

    def test_already_shipped_plan_refused_before_any_write(self):
        _init_repo(self.repo)
        self._declare("shipped.txt")
        (self.repo / "shipped.txt").write_text("done\n", encoding="utf-8")
        rc, out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 3)
        self.assertEqual(out, "")
        self.assertIn("already shipped — nothing to do", err)
        self.assertFalse((self.worktree / ".harness").exists())

    def test_pending_plan_with_missing_artifact_writes_normally(self):
        _init_repo(self.repo)
        self._declare("not-yet.txt")
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        self.assertEqual((self.worktree / ".harness" / "active-plan").read_text(), "foo\n")

    def test_plan_without_expected_artifacts_writes_normally(self):
        _init_repo(self.repo)
        self.plan.write_text("# Plan: foo\n", encoding="utf-8")
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        self.assertEqual((self.worktree / ".harness" / "active-plan").read_text(), "foo\n")


class TestMainCLI(WorktreeMarkerTestCase):
    def test_write_subcommand(self):
        _init_repo(self.repo)
        rc = wm.main(["worktree_marker.py", "write", str(self.worktree), "foo",
                      str(self.plan), "--project-root", str(self.repo)])
        self.assertEqual(rc, 0)
        self.assertEqual((self.worktree / ".harness" / "active-plan").read_text(), "foo\n")


if __name__ == "__main__":
    unittest.main()
