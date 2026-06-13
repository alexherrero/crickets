#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/spawn_worker.py (V5-10 sibling #2).

Operator-initiated worker-worktree spawning composed onto `resolve_plan`. Every
test builds a throwaway temp git repo and drives a real `git worktree add` — no
mocked git, no real agentm clone, never the vault. Both resolution backends are
exercised: the standalone `.harness/` fallback (`resolver=None`) and a planted
stub standing in for agentm's verb (`resolver=<stub path>`), exactly as
test_stage_plan.py does.

The load-bearing assertions: (a) the worktree-local marker is the BARE SLUG that
round-trips through agentm's `_normalize_plan_name`; (b) no-clobber — a
pre-existing worktree path or branch refuses with exit 2 and creates nothing;
(c) the named-only guard; (d) the `vault_project` fallback fires only on a
divergent override.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
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


sw = _load("spawn_worker")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo),
                          capture_output=True, text=True, check=True)


def _init_repo(repo: Path, *, origin: str | None = None) -> None:
    """A throwaway git repo with one commit and (optionally) an origin remote."""
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


def _write_stub(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


_STUB_OK = (
    "import sys\n"
    "sys.stdout.write('/v/_harness/PLAN-foo.md\\t/v/_harness/progress-foo.md\\n')\n"
    "sys.exit(0)\n"
)
_STUB_REFUSE = (
    "import sys\n"
    "sys.stderr.write('[resolver] dangling active-plan marker\\n')\n"
    "sys.exit(2)\n"
)


class TestSpawnHappyPath(unittest.TestCase):
    """A spawn creates the worktree + branch and writes a round-tripping marker."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-happy-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_creates_worktree_branch_and_bare_slug_marker(self):
        rc, out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 0, err)
        self.assertEqual(err, "")
        wt = sw.worktree_path(self.repo, "foo")
        self.assertEqual(out.strip(), str(wt))
        self.assertTrue(wt.is_dir())
        # branch worker/foo exists and the worktree is checked out on it.
        self.assertTrue(sw._branch_exists(self.repo, "worker/foo"))
        head = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"],
                              cwd=str(wt), capture_output=True, text=True)
        self.assertEqual(head.stdout.strip(), "worker/foo")
        # The marker is the BARE SLUG + newline.
        marker = (wt / ".harness" / "active-plan").read_text(encoding="utf-8")
        self.assertEqual(marker, "foo\n")

    def test_marker_round_trips_through_normalize(self):
        # The contract: what we write is exactly what agentm reads back —
        # case-preserving .strip() then _normalize_plan_name → the same slug.
        sw.spawn("foo", str(self.repo), resolver=None)
        marker = (sw.worktree_path(self.repo, "foo") / ".harness" / "active-plan").read_text()
        self.assertEqual(sw.resolve_plan._normalize_plan_name(marker.strip()), "foo")

    def test_filename_form_name_writes_bare_slug_marker(self):
        # A "PLAN-bar.md"-form name normalizes to "bar" for both the branch and
        # the marker — never the decorated form.
        rc, out, err = sw.spawn("PLAN-bar.md", str(self.repo), resolver=None)
        self.assertEqual(rc, 0, err)
        wt = sw.worktree_path(self.repo, "bar")
        self.assertEqual(out.strip(), str(wt))
        self.assertTrue(sw._branch_exists(self.repo, "worker/bar"))
        self.assertEqual((wt / ".harness" / "active-plan").read_text(), "bar\n")

    def test_worktree_path_override_is_honored(self):
        custom = self.tmp / "elsewhere" / "wt-foo"
        rc, out, err = sw.spawn("foo", str(self.repo), worktree=custom, resolver=None)
        self.assertEqual(rc, 0, err)
        self.assertEqual(out.strip(), str(custom))
        self.assertTrue(custom.is_dir())
        self.assertEqual((custom / ".harness" / "active-plan").read_text(), "foo\n")


class TestSpawnRefusals(unittest.TestCase):
    """Named-only + no-clobber guards run before any mutation."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-refuse-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_singleton_and_empty_names_refused_no_mutation(self):
        for form in ("", "   ", "PLAN", "PLAN.md"):
            with self.subTest(form=form):
                rc, out, err = sw.spawn(form, str(self.repo), resolver=None)
                self.assertEqual(rc, 2, form)
                self.assertEqual(out, "", form)
                self.assertIn("named plan", err)
        # No stray branch and no sibling worktrees dir was created.
        branches = subprocess.run(["git", "branch", "--list"], cwd=str(self.repo),
                                  capture_output=True, text=True).stdout
        self.assertNotIn("worker/", branches)
        self.assertFalse((self.tmp / "repo.worktrees").exists())

    def test_existing_worktree_path_refused(self):
        wt = sw.worktree_path(self.repo, "foo")
        wt.mkdir(parents=True)  # pre-occupy the path
        rc, out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("already exists", err)
        # The no-clobber guard fired before `git worktree add` / branch creation.
        self.assertFalse(sw._branch_exists(self.repo, "worker/foo"))

    def test_existing_branch_refused(self):
        _git(self.repo, "branch", "worker/foo")
        rc, out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("already exists", err)
        # No worktree was created at the default path.
        self.assertFalse(sw.worktree_path(self.repo, "foo").exists())

    def test_unsafe_slug_propagates_resolver_refusal(self):
        # The named-only guard passes ("../etc" is non-empty), but resolve_plan's
        # safety guard rejects it — that exit 2 + stderr propagate, nothing created.
        rc, out, err = sw.spawn("../etc", str(self.repo), resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("unsafe plan name", err)
        self.assertFalse((self.tmp / "repo.worktrees").exists())


class TestDelegateBackend(unittest.TestCase):
    """A located resolver (agentm stub) is authoritative — gates the spawn."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-delegate-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_resolver_ok_allows_spawn(self):
        stub = _write_stub(self.tmp / "stub_ok.py", _STUB_OK)
        rc, out, err = sw.spawn("foo", str(self.repo), resolver=stub)
        self.assertEqual(rc, 0, err)
        wt = sw.worktree_path(self.repo, "foo")
        self.assertTrue(wt.is_dir())
        self.assertEqual((wt / ".harness" / "active-plan").read_text(), "foo\n")
        self.assertTrue(sw._branch_exists(self.repo, "worker/foo"))

    def test_resolver_refusal_propagates_no_mutation(self):
        stub = _write_stub(self.tmp / "stub_refuse.py", _STUB_REFUSE)
        rc, out, err = sw.spawn("foo", str(self.repo), resolver=stub)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("dangling", err)
        # The authoritative refusal stopped the spawn before git was touched.
        self.assertFalse(sw._branch_exists(self.repo, "worker/foo"))
        self.assertFalse((self.tmp / "repo.worktrees").exists())


class TestVaultProjectFallback(unittest.TestCase):
    """LC-2: the `vault_project` copy fires only on a divergent override."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-vault-"))
        self.repo = self.tmp / "repo"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_project_json(self, vault_project: str) -> None:
        h = self.repo / ".harness"
        h.mkdir(parents=True, exist_ok=True)
        (h / "project.json").write_text(
            json.dumps({"vault_project": vault_project}), encoding="utf-8")

    def test_copies_when_override_diverges_from_origin(self):
        _init_repo(self.repo, origin="https://github.com/org/myrepo.git")
        self._write_project_json("different")  # diverges from origin basename "myrepo"
        rc, out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 0, err)
        copied = sw.worktree_path(self.repo, "foo") / ".harness" / "project.json"
        self.assertTrue(copied.is_file())
        self.assertEqual(json.loads(copied.read_text())["vault_project"], "different")

    def test_no_copy_when_override_matches_origin(self):
        # scp-style host:path form (the canonical "git@" user is omitted only to
        # dodge the PII detector's email-shape match — the parser discards
        # everything before the last "/" or ":" anyway).
        _init_repo(self.repo, origin="example.com:org/myrepo.git")
        self._write_project_json("myrepo")  # equals the origin basename → dormant
        rc, _out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 0, err)
        copied = sw.worktree_path(self.repo, "foo") / ".harness" / "project.json"
        self.assertFalse(copied.exists())

    def test_no_copy_when_project_json_absent(self):
        _init_repo(self.repo, origin="https://github.com/org/myrepo.git")
        rc, _out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 0, err)
        copied = sw.worktree_path(self.repo, "foo") / ".harness" / "project.json"
        self.assertFalse(copied.exists())
        # ...but the marker is always written.
        self.assertEqual(
            (sw.worktree_path(self.repo, "foo") / ".harness" / "active-plan").read_text(),
            "foo\n")

    def test_copies_when_override_present_but_no_origin(self):
        # No origin remote to fall back on → the override is the only signal, so
        # it must be carried into the worktree.
        _init_repo(self.repo, origin=None)
        self._write_project_json("solo")
        rc, _out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 0, err)
        copied = sw.worktree_path(self.repo, "foo") / ".harness" / "project.json"
        self.assertTrue(copied.is_file())
        self.assertEqual(json.loads(copied.read_text())["vault_project"], "solo")


class TestOriginBasename(unittest.TestCase):
    """`_origin_basename` parses both URL flavors and tolerates a missing remote."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-origin-"))
        self.repo = self.tmp / "repo"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_https_url(self):
        _init_repo(self.repo, origin="https://github.com/org/myrepo.git")
        self.assertEqual(sw._origin_basename(self.repo), "myrepo")

    def test_scp_style_url(self):
        # scp-style host:path (colon separator). The "git@" user is omitted to
        # avoid the PII detector's email-shape false positive; it's discarded by
        # the parser regardless, so the colon-split path is what's under test.
        _init_repo(self.repo, origin="example.com:org/myrepo.git")
        self.assertEqual(sw._origin_basename(self.repo), "myrepo")

    def test_url_without_dot_git_suffix(self):
        _init_repo(self.repo, origin="https://github.com/org/plainname")
        self.assertEqual(sw._origin_basename(self.repo), "plainname")

    def test_no_origin_returns_none(self):
        _init_repo(self.repo, origin=None)
        self.assertIsNone(sw._origin_basename(self.repo))


class TestMainCLI(unittest.TestCase):
    """End-to-end main() over the fallback backend (auto-locator forced to None)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-main-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)
        self._saved = sw.resolve_plan.locate_resolver
        sw.resolve_plan.locate_resolver = lambda **_k: None

    def tearDown(self):
        sw.resolve_plan.locate_resolver = self._saved
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = sw.main(["spawn_worker.py", *argv])
        return rc, out.getvalue(), err.getvalue()

    def test_main_spawns_and_prints_worktree_path(self):
        rc, out, err = self._run("foo", "--project-root", str(self.repo))
        self.assertEqual(rc, 0, err)
        wt = sw.worktree_path(self.repo, "foo")
        self.assertEqual(out.strip(), str(wt))
        self.assertTrue(wt.is_dir())

    def test_main_singleton_nonzero(self):
        rc, out, err = self._run("PLAN", "--project-root", str(self.repo))
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("named plan", err)


if __name__ == "__main__":
    unittest.main()
