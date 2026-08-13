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


def _add_worktree(repo: Path, worktree: Path, branch: str = "wt-test") -> None:
    """A REAL `git worktree add` — mirrors what the host primitive is supposed
    to produce, so tests exercise the fake-slot guard's happy path (added by
    the worktree-slot integrity fix) against genuine git state rather than a
    bare `mkdir`."""
    _git(repo, "worktree", "add", "-b", branch, str(worktree))


class WorktreeMarkerTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wm-"))
        self.repo = self.tmp / "repo"
        self.worktree = self.tmp / "worktree"
        self.plan = self.tmp / "PLAN-foo.md"
        self.plan.write_text("# Plan: foo\n", encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_worktree(self) -> Path:
        """Register `self.worktree` as a real git worktree of `self.repo` —
        call after `_init_repo(self.repo, ...)` in any test that binds a
        marker into it, so the fake-slot guard's happy path is satisfied."""
        _add_worktree(self.repo, self.worktree)
        return self.worktree

    def _declare(self, *arts: str):
        inline = ", ".join(arts)
        self.plan.write_text(
            f"---\nexpected_artifacts: [{inline}]\n---\n# Plan: foo\n", encoding="utf-8")


class TestHappyPath(WorktreeMarkerTestCase):
    def test_writes_bare_slug_marker(self):
        _init_repo(self.repo)
        self._make_worktree()
        rc, out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        self.assertEqual((self.worktree / ".harness" / "active-plan").read_text(), "foo\n")

    def test_marker_round_trips_through_normalize(self):
        _init_repo(self.repo)
        self._make_worktree()
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


class TestFakeSlotGuard(WorktreeMarkerTestCase):
    """The fake-slot guard: refuse to bind a plan into a directory that is not
    a real, git-registered worktree of `root` — the defense against a host
    worktree primitive leaving a bare directory behind a slot path instead of
    an actual `git worktree add`-created checkout (the live worktree-slot
    integrity bug: a session assigned such a slot silently shares the parent
    checkout's HEAD/index/working-tree with every other session on it)."""

    def test_plain_directory_refused_even_though_it_is_a_dir(self):
        _init_repo(self.repo)
        self.worktree.mkdir(parents=True, exist_ok=True)  # never `git worktree add`-ed
        rc, out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("not confirmed to be a real, isolated git worktree", err)
        self.assertIn("does not list it", err)
        self.assertFalse((self.worktree / ".harness").exists(), "must refuse before any write")

    def test_real_worktree_is_accepted(self):
        _init_repo(self.repo)
        self._make_worktree()
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)

    def test_unreadable_registry_refused_not_silently_trusted(self):
        # `root` doesn't exist at all — `git worktree list` can't run against
        # it, so the registry is unreadable. Must refuse (None collapses to
        # "not registered"), never fall through and trust the directory.
        self.repo.mkdir(parents=True, exist_ok=True)  # a dir, but never `git init`
        self.worktree.mkdir(parents=True, exist_ok=True)
        rc, out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("could not be read", err)

    def test_a_different_repos_worktree_is_not_accepted(self):
        # A directory that IS a real git worktree — but of a DIFFERENT repo,
        # not `root`. Registered-elsewhere must not satisfy this repo's check.
        _init_repo(self.repo)
        other_repo = self.tmp / "other-repo"
        _init_repo(other_repo)
        _add_worktree(other_repo, self.worktree)
        rc, out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 2)
        self.assertIn("does not list it", err)


class TestRegisteredWorktreeHelpers(WorktreeMarkerTestCase):
    """Direct coverage of `_registered_worktree_paths` / `_is_registered_worktree`."""

    def test_registered_paths_includes_the_main_checkout_and_worktrees(self):
        _init_repo(self.repo)
        self._make_worktree()
        paths = wm._registered_worktree_paths(self.repo)
        self.assertIn(str(self.repo.resolve()), paths)
        self.assertIn(str(self.worktree.resolve()), paths)

    def test_registered_paths_none_on_unreadable_repo(self):
        self.repo.mkdir(parents=True, exist_ok=True)  # never `git init`
        self.assertIsNone(wm._registered_worktree_paths(self.repo))

    def test_is_registered_worktree_true_for_real_worktree(self):
        _init_repo(self.repo)
        self._make_worktree()
        self.assertTrue(wm._is_registered_worktree(self.worktree, self.repo))

    def test_is_registered_worktree_false_for_bare_directory(self):
        _init_repo(self.repo)
        self.worktree.mkdir(parents=True, exist_ok=True)
        self.assertFalse(wm._is_registered_worktree(self.worktree, self.repo))

    def test_is_registered_worktree_none_when_registry_unreadable(self):
        self.repo.mkdir(parents=True, exist_ok=True)
        self.worktree.mkdir(parents=True, exist_ok=True)
        self.assertIsNone(wm._is_registered_worktree(self.worktree, self.repo))


class TestVaultProjectFallback(WorktreeMarkerTestCase):
    """LC-2: the `vault_project` copy fires only on a divergent override."""

    def _write_project_json(self, vault_project: str) -> None:
        h = self.repo / ".harness"
        h.mkdir(parents=True, exist_ok=True)
        (h / "project.json").write_text(
            json.dumps({"vault_project": vault_project}), encoding="utf-8")

    def test_copies_when_override_diverges_from_origin(self):
        _init_repo(self.repo, origin="https://github.com/org/myrepo.git")
        self._make_worktree()
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
        self._make_worktree()
        self._write_project_json("myrepo")
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        copied = self.worktree / ".harness" / "project.json"
        self.assertTrue(copied.is_file())
        self.assertEqual(json.loads(copied.read_text())["vault_project"], "myrepo")

    def test_no_copy_when_project_json_absent(self):
        _init_repo(self.repo, origin="https://github.com/org/myrepo.git")
        self._make_worktree()
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        self.assertFalse((self.worktree / ".harness" / "project.json").exists())
        self.assertEqual((self.worktree / ".harness" / "active-plan").read_text(), "foo\n")

    def test_origin_lookup_timeout_does_not_crash(self):
        _init_repo(self.repo, origin="https://github.com/org/myrepo.git")
        self._make_worktree()
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
        self._make_worktree()
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
        self._make_worktree()
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
        self._make_worktree()
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
        self._make_worktree()
        self._write_isolation_cfg("worktree-per-plan", "pull-request")
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        copied = json.loads((self.worktree / ".harness" / "project.json").read_text())
        self.assertIn("isolation", copied)
        self.assertNotIn("vault_project", copied)

    def test_both_isolation_and_divergent_vault_project_carried_together(self):
        _init_repo(self.repo, origin="https://github.com/org/myrepo.git")
        self._make_worktree()
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
        self._make_worktree()
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        self.assertFalse((self.worktree / ".harness" / "project.json").exists())

    def test_no_project_json_at_all_leaves_worktree_without_one(self):
        # A real (if minimal) repo — the fake-slot guard requires `root` to be
        # a readable git repo before it can verify anything against it.
        _init_repo(self.repo)
        self._make_worktree()
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
        self._make_worktree()
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
        self._make_worktree()
        self._declare("shipped.txt")
        (self.repo / "shipped.txt").write_text("done\n", encoding="utf-8")
        rc, out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 3)
        self.assertEqual(out, "")
        self.assertIn("already shipped — nothing to do", err)
        self.assertFalse((self.worktree / ".harness").exists())

    def test_pending_plan_with_missing_artifact_writes_normally(self):
        _init_repo(self.repo)
        self._make_worktree()
        self._declare("not-yet.txt")
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        self.assertEqual((self.worktree / ".harness" / "active-plan").read_text(), "foo\n")

    def test_plan_without_expected_artifacts_writes_normally(self):
        _init_repo(self.repo)
        self._make_worktree()
        self.plan.write_text("# Plan: foo\n", encoding="utf-8")
        rc, _out, err = wm.write_marker(self.worktree, "foo", self.plan, self.repo)
        self.assertEqual(rc, 0, err)
        self.assertEqual((self.worktree / ".harness" / "active-plan").read_text(), "foo\n")


class PointerTestCase(WorktreeMarkerTestCase):
    """Shared fixture for the root-side pointer — the resume half of the bind."""

    def _pointer(self, slug: str = "foo") -> Path:
        return self.repo / ".harness" / f"worktree-for-{slug}"

    def _bind(self, slug: str = "foo", worktree: Path | None = None, **kw):
        return wm.write_marker(worktree or self.worktree, slug, self.plan, self.repo, **kw)


class TestPointerWrittenOnBind(PointerTestCase):
    """The gap this closes: both of the bind's original writes were worktree-LOCAL,
    so a session that opened at the repo root had no way to learn which worktree a
    plan was bound to. `/work` step 1.5's resume branch reads this pointer."""

    def test_pointer_written_into_the_root_harness(self):
        _init_repo(self.repo)
        self._make_worktree()
        rc, _out, err = self._bind()
        self.assertEqual(rc, 0, err)
        self.assertEqual(err, "", "a successful pointer write emits no warning")
        self.assertEqual(self._pointer().read_text(encoding="utf-8"),
                         f"{self.worktree.resolve()}\n")

    def test_pointer_name_normalizes_like_the_marker(self):
        _init_repo(self.repo)
        self._make_worktree()
        rc, _out, err = self._bind("PLAN-foo.md")
        self.assertEqual(rc, 0, err)
        self.assertTrue(self._pointer("foo").is_file(),
                        "the pointer is named by the bare slug, like the marker's content")

    def test_rebinding_the_same_slug_is_idempotent(self):
        _init_repo(self.repo)
        self._make_worktree()
        self._bind()
        first = self._pointer().read_text(encoding="utf-8")
        rc, _out, err = self._bind()
        self.assertEqual(rc, 0, err)
        self.assertEqual(self._pointer().read_text(encoding="utf-8"), first)

    def test_no_root_pointer_flag_suppresses_the_write(self):
        # A per-task worktree (step 2.5) is spawned and pruned inside one
        # session — no later session should ever be sent back into it.
        _init_repo(self.repo)
        self._make_worktree()
        rc, _out, err = self._bind(root_pointer=False)
        self.assertEqual(rc, 0, err)
        self.assertFalse(self._pointer().exists())
        self.assertEqual((self.worktree / ".harness" / "active-plan").read_text(), "foo\n")

    def test_unwritable_root_warns_but_still_binds(self):
        # The worktree is bound and fully usable; only the resume convenience
        # is lost, so this must never fail the bind.
        _init_repo(self.repo)
        self._make_worktree()
        with mock.patch.object(wm, "_pointer_path",
                               side_effect=OSError("read-only file system")):
            rc, out, err = self._bind()
        self.assertEqual(rc, 0)
        self.assertEqual(out, f"{self.worktree}\n")
        self.assertIn("WARNING", err)
        self.assertIn("root-side pointer", err)
        self.assertEqual((self.worktree / ".harness" / "active-plan").read_text(), "foo\n")

    def test_unsafe_slug_refused_before_any_write(self):
        # The slug is now part of a FILENAME, so path-component safety is
        # load-bearing rather than cosmetic.
        _init_repo(self.repo)
        self._make_worktree()
        rc, out, err = self._bind("../escape")
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("unsafe plan slug", err)
        self.assertFalse((self.worktree / ".harness").exists())

    def test_no_pointer_written_when_the_bind_itself_is_refused(self):
        # LC-6 already-shipped: nothing written anywhere, pointer included.
        _init_repo(self.repo)
        self._make_worktree()
        self._declare("shipped.txt")
        (self.repo / "shipped.txt").write_text("done\n", encoding="utf-8")
        rc, _out, _err = self._bind()
        self.assertEqual(rc, 3)
        self.assertFalse(self._pointer().exists())


class TestConcurrentSlugs(PointerTestCase):
    """agentm routinely carries more than one active plan — the pointer is
    per-slug by name precisely so two in-flight plans can't overwrite each
    other's binding."""

    def test_two_plans_keep_separate_pointers(self):
        _init_repo(self.repo)
        wt_a = self.tmp / "wt-a"
        wt_b = self.tmp / "wt-b"
        _add_worktree(self.repo, wt_a, branch="worktree-alpha")
        _add_worktree(self.repo, wt_b, branch="worktree-beta")

        self.assertEqual(self._bind("alpha", wt_a)[0], 0)
        self.assertEqual(self._bind("beta", wt_b)[0], 0)

        self.assertEqual(self._pointer("alpha").read_text(), f"{wt_a.resolve()}\n")
        self.assertEqual(self._pointer("beta").read_text(), f"{wt_b.resolve()}\n")

        rc_a, out_a, _ = wm.read_pointer("alpha", self.repo)
        rc_b, out_b, _ = wm.read_pointer("beta", self.repo)
        self.assertEqual((rc_a, out_a.strip()), (0, str(wt_a.resolve())))
        self.assertEqual((rc_b, out_b.strip()), (0, str(wt_b.resolve())))

    def test_clearing_one_leaves_the_other(self):
        _init_repo(self.repo)
        wt_a = self.tmp / "wt-a"
        wt_b = self.tmp / "wt-b"
        _add_worktree(self.repo, wt_a, branch="worktree-alpha")
        _add_worktree(self.repo, wt_b, branch="worktree-beta")
        self._bind("alpha", wt_a)
        self._bind("beta", wt_b)

        self.assertEqual(wm.clear_pointer("alpha", self.repo)[0], 0)
        self.assertFalse(self._pointer("alpha").exists())
        self.assertEqual(wm.read_pointer("beta", self.repo)[0], 0)


class TestResumeReEntry(PointerTestCase):
    """`/work` step 1.5's resume branch: exit 0 → re-enter at the printed path."""

    def test_bind_then_read_resolves_the_worktree(self):
        _init_repo(self.repo)
        self._make_worktree()
        self._bind()
        rc, out, err = wm.read_pointer("foo", self.repo)
        self.assertEqual(rc, 0, err)
        self.assertEqual(out.strip(), str(self.worktree.resolve()))
        self.assertEqual(err, "")

    def test_read_accepts_any_accepted_slug_spelling(self):
        _init_repo(self.repo)
        self._make_worktree()
        self._bind()
        for spelling in ("foo", "PLAN-foo", "PLAN-foo.md"):
            rc, out, err = wm.read_pointer(spelling, self.repo)
            self.assertEqual(rc, 0, f"{spelling}: {err}")
            self.assertEqual(out.strip(), str(self.worktree.resolve()))

    def test_already_inside_is_a_no_op_not_a_re_entry(self):
        # Idempotence: a session already in the right worktree must be told to
        # stay put, never handed a path to re-enter.
        _init_repo(self.repo)
        self._make_worktree()
        self._bind()
        rc, out, err = wm.read_pointer("foo", self.worktree)
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")
        self.assertIn("already inside", err)

    def test_pointer_is_found_from_inside_the_worktree_too(self):
        # The pointer lives in the MAIN checkout; resolving through
        # resolve_main_worktree is what makes read symmetric with write.
        _init_repo(self.repo)
        self._make_worktree()
        self._bind()
        self.assertEqual(wm._pointer_path(self.worktree, "foo"),
                         self._pointer().resolve())

    def test_write_from_inside_a_worktree_still_lands_in_the_main_root(self):
        _init_repo(self.repo)
        self._make_worktree()
        self.assertEqual(wm._write_pointer(self.worktree, "foo", self.worktree), "")
        self.assertTrue(self._pointer().is_file())


class TestStalePointerDegrades(PointerTestCase):
    """Every stale/unverifiable case collapses to exit 1 — 'carry on in the
    current directory' with a visible note. Re-entry is a convenience layer;
    it must never be something that can block a plan."""

    def test_absent_pointer_is_not_an_error(self):
        _init_repo(self.repo)
        rc, out, err = wm.read_pointer("foo", self.repo)
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")
        self.assertIn("no worktree pointer recorded", err)

    def test_blank_pointer_is_not_an_error(self):
        _init_repo(self.repo)
        p = self._pointer()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("   \n", encoding="utf-8")
        rc, _out, err = wm.read_pointer("foo", self.repo)
        self.assertEqual(rc, 1)
        self.assertIn("no worktree pointer recorded", err)

    def test_removed_worktree_degrades_with_a_note(self):
        # The operator removed the worktree by hand after the bind.
        import shutil
        _init_repo(self.repo)
        self._make_worktree()
        self._bind()
        shutil.rmtree(self.worktree)
        rc, out, err = wm.read_pointer("foo", self.repo)
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")
        self.assertIn("STALE POINTER", err)
        self.assertIn("no longer exists", err)
        self.assertIn("clear foo", err, "the note names the fix")

    def test_deregistered_worktree_degrades_with_a_note(self):
        # The directory survives but `git worktree list` no longer claims it —
        # the same fake-slot hazard the bind's own guard exists for.
        _init_repo(self.repo)
        self._make_worktree()
        self._bind()
        _git(self.repo, "worktree", "remove", "--force", str(self.worktree))
        self.worktree.mkdir(parents=True, exist_ok=True)
        rc, out, err = wm.read_pointer("foo", self.repo)
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")
        self.assertIn("STALE POINTER", err)
        self.assertIn("no longer lists it", err)

    def test_unreadable_registry_degrades_rather_than_re_entering(self):
        # Never guess safe on an unreadable repo — but never hard-stop either.
        _init_repo(self.repo)
        self._make_worktree()
        self._bind()
        with mock.patch.object(wm, "_is_registered_worktree", return_value=None):
            rc, out, err = wm.read_pointer("foo", self.repo)
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")
        self.assertIn("could not be read", err)

    def test_repurposed_worktree_degrades_with_a_note(self):
        # The worktree still exists and is registered, but has since been bound
        # to a different plan — re-entering would put the session on the wrong one.
        _init_repo(self.repo)
        self._make_worktree()
        self._bind()
        (self.worktree / ".harness" / "active-plan").write_text("other\n", encoding="utf-8")
        rc, out, err = wm.read_pointer("foo", self.repo)
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")
        self.assertIn("bound to plan 'other'", err)

    def test_missing_marker_does_not_block_re_entry(self):
        # A dangling marker is doctor_worktrees' business; the pointer is the
        # binding we were asked to trust here, so re-entry still proceeds.
        _init_repo(self.repo)
        self._make_worktree()
        self._bind()
        (self.worktree / ".harness" / "active-plan").unlink()
        rc, out, err = wm.read_pointer("foo", self.repo)
        self.assertEqual(rc, 0, err)
        self.assertEqual(out.strip(), str(self.worktree.resolve()))

    def test_singleton_slug_reads_as_nothing_to_do(self):
        _init_repo(self.repo)
        rc, out, err = wm.read_pointer("", self.repo)
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")
        self.assertIn("singleton plan", err)

    def test_a_percent_in_the_path_does_not_crash_the_stale_note(self):
        # The one case that MUST degrade cleanly is the one where a
        # %-formatted message would raise on the way to reporting it.
        import shutil
        _init_repo(self.repo)
        odd = self.tmp / "wt-100%-done"
        _add_worktree(self.repo, odd, branch="worktree-odd")
        self._bind("foo", odd)
        shutil.rmtree(odd)
        rc, _out, err = wm.read_pointer("foo", self.repo)
        self.assertEqual(rc, 1)
        self.assertIn("STALE POINTER", err)
        self.assertIn("100%", err)

    def test_unsafe_slug_is_the_only_loud_read(self):
        _init_repo(self.repo)
        rc, out, err = wm.read_pointer("../escape", self.repo)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("unsafe plan slug", err)


class TestClearPointer(PointerTestCase):
    def test_clear_removes_the_pointer(self):
        _init_repo(self.repo)
        self._make_worktree()
        self._bind()
        rc, _out, err = wm.clear_pointer("foo", self.repo)
        self.assertEqual(rc, 0, err)
        self.assertFalse(self._pointer().exists())

    def test_clear_is_idempotent(self):
        _init_repo(self.repo)
        self.assertEqual(wm.clear_pointer("foo", self.repo)[0], 0)
        self.assertEqual(wm.clear_pointer("foo", self.repo)[0], 0)

    def test_clear_singleton_is_a_quiet_no_op(self):
        _init_repo(self.repo)
        rc, _out, err = wm.clear_pointer("", self.repo)
        self.assertEqual(rc, 0)
        self.assertIn("singleton plan", err)

    def test_clear_refuses_an_unsafe_slug(self):
        _init_repo(self.repo)
        self.assertEqual(wm.clear_pointer("../escape", self.repo)[0], 2)


class TestMainCLI(WorktreeMarkerTestCase):
    def test_write_subcommand(self):
        _init_repo(self.repo)
        self._make_worktree()
        rc = wm.main(["worktree_marker.py", "write", str(self.worktree), "foo",
                      str(self.plan), "--project-root", str(self.repo)])
        self.assertEqual(rc, 0)
        self.assertEqual((self.worktree / ".harness" / "active-plan").read_text(), "foo\n")
        self.assertTrue((self.repo / ".harness" / "worktree-for-foo").is_file())

    def test_write_subcommand_honors_no_root_pointer(self):
        _init_repo(self.repo)
        self._make_worktree()
        rc = wm.main(["worktree_marker.py", "write", str(self.worktree), "foo",
                      str(self.plan), "--project-root", str(self.repo),
                      "--no-root-pointer"])
        self.assertEqual(rc, 0)
        self.assertFalse((self.repo / ".harness" / "worktree-for-foo").exists())

    def test_read_subcommand_round_trips(self):
        _init_repo(self.repo)
        self._make_worktree()
        wm.main(["worktree_marker.py", "write", str(self.worktree), "foo",
                 str(self.plan), "--project-root", str(self.repo)])
        rc = wm.main(["worktree_marker.py", "read", "foo",
                      "--project-root", str(self.repo)])
        self.assertEqual(rc, 0)

    def test_read_subcommand_exits_1_when_nothing_is_bound(self):
        _init_repo(self.repo)
        rc = wm.main(["worktree_marker.py", "read", "foo",
                      "--project-root", str(self.repo)])
        self.assertEqual(rc, 1)

    def test_clear_subcommand(self):
        _init_repo(self.repo)
        self._make_worktree()
        wm.main(["worktree_marker.py", "write", str(self.worktree), "foo",
                 str(self.plan), "--project-root", str(self.repo)])
        rc = wm.main(["worktree_marker.py", "clear", "foo",
                      "--project-root", str(self.repo)])
        self.assertEqual(rc, 0)
        self.assertFalse((self.repo / ".harness" / "worktree-for-foo").exists())


if __name__ == "__main__":
    unittest.main()
