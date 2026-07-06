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
import os
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

    def test_dangling_symlink_at_path_refused_no_write_through(self):
        # A dangling symlink at the worktree path must count as "already exists"
        # (os.path.lexists, not exists) so the spawn refuses and writes nothing
        # *through* the link — the DEFECT-1 lesson from sibling #1 (stage_plan).
        target = self.tmp / "nonexistent-target"
        link = self.tmp / "dangling-wt"
        link.symlink_to(target)  # dangling: target does not exist
        rc, out, err = sw.spawn("foo", str(self.repo), worktree=link, resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("already exists", err)
        self.assertFalse(target.exists(), "nothing written through the dangling link")
        self.assertFalse(sw._branch_exists(self.repo, "worker/foo"))

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
        self.assertNotEqual(err, "")  # error surfaced (seam stderr captured by bridge)
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

    def test_origin_lookup_timeout_does_not_crash_post_add(self):
        # Re-review defect: `_origin_basename`'s `git remote get-url` runs INSIDE the
        # post-`worktree add` block (via `_needs_vault_project_copy`). A
        # subprocess.TimeoutExpired there (a SubprocessError, NOT an OSError) escaped
        # the post-create `except OSError` and crashed spawn() *after* the worktree +
        # branch were created — a partial spawn via uncaught exception. The
        # best-effort `_origin_basename` must swallow it to None and degrade to a
        # conservative copy, never crash. (Pre-fix: this ERRORs.)
        _init_repo(self.repo, origin="https://github.com/org/myrepo.git")
        self._write_project_json("different")  # diverges → the copy branch is entered

        orig_git = sw._git

        def hang_on_remote_geturl(args, root):
            if args[:2] == ["remote", "get-url"]:
                raise subprocess.TimeoutExpired(cmd="git remote get-url origin", timeout=30)
            return orig_git(args, root)

        with mock.patch.object(sw, "_git", hang_on_remote_geturl):
            rc, out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 0, err)  # no crash; origin unknown → conservative copy
        wt = sw.worktree_path(self.repo, "foo")
        self.assertEqual((wt / ".harness" / "active-plan").read_text(), "foo\n")
        self.assertTrue((wt / ".harness" / "project.json").is_file())

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

    def test_read_vault_project_returns_none_for_non_object_json(self):
        # A valid-JSON-but-not-an-object document parses fine, but `data.get(...)`
        # would raise AttributeError (not OSError/SubprocessError). The helper's
        # documented contract is "any error → None"; its guard must cover the .get().
        # (Pre-fix: each of these raises AttributeError.)
        self.repo.mkdir(parents=True, exist_ok=True)
        h = self.repo / ".harness"
        h.mkdir()
        for doc in ("[1, 2, 3]", '"a string"', "42", "true", "null"):
            (h / "project.json").write_text(doc, encoding="utf-8")
            self.assertIsNone(sw._read_vault_project(self.repo),
                              f"non-object project.json {doc!r} must collapse to None")

    def test_non_object_project_json_skips_copy_no_crash(self):
        # End-to-end: a non-object project.json is reached on the POST-create path
        # (via `_needs_vault_project_copy`). Pre-fix the AttributeError escaped the
        # post-create `except OSError` and crashed spawn() with the worktree + branch
        # + marker already created — a partial spawn. It must instead skip the copy
        # and succeed. (Pre-fix: this ERRORs.)
        _init_repo(self.repo, origin="https://github.com/org/myrepo.git")
        h = self.repo / ".harness"
        h.mkdir(parents=True, exist_ok=True)
        (h / "project.json").write_text("[1, 2, 3]", encoding="utf-8")
        rc, _out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 0, err)
        wt = sw.worktree_path(self.repo, "foo")
        self.assertEqual((wt / ".harness" / "active-plan").read_text(), "foo\n")
        self.assertFalse((wt / ".harness" / "project.json").exists(),
                         "a malformed project.json must skip the copy, not crash")


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

    def test_git_timeout_collapses_to_none(self):
        # Best-effort contract: a raising `_git` (a >30s hang → TimeoutExpired, a
        # SubprocessError not an OSError) must collapse to None, never propagate.
        _init_repo(self.repo, origin="https://github.com/org/myrepo.git")
        orig_git = sw._git

        def hang(args, root):
            if args[:2] == ["remote", "get-url"]:
                raise subprocess.TimeoutExpired(cmd="git remote get-url", timeout=30)
            return orig_git(args, root)

        with mock.patch.object(sw, "_git", hang):
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


class TestRelativeWorktreePath(unittest.TestCase):
    """DEFECT-1 regression: a relative --worktree-path is anchored to `root`, not cwd.

    `git worktree add` runs with cwd=root, so it resolves a relative path against
    root; before the fix the Python-side guard + marker write resolved it against
    the process cwd, splitting the worktree from its marker when root != cwd.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-relpath-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)
        self.cwd_elsewhere = self.tmp / "elsewhere"
        self.cwd_elsewhere.mkdir()
        self._orig_cwd = os.getcwd()
        os.chdir(self.cwd_elsewhere)

    def tearDown(self):
        os.chdir(self._orig_cwd)
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_relative_worktree_path_marker_lands_inside_real_worktree(self):
        rc, out, err = sw.spawn("foo", str(self.repo), worktree="rel-wt", resolver=None)
        self.assertEqual(rc, 0, err)
        # git (cwd=root) creates the worktree at <root>/rel-wt; the fix anchors the
        # Python-side path there too. Resolve to dodge macOS /private symlinks.
        real_wt = Path(self.repo).resolve() / "rel-wt"
        phantom = self.cwd_elsewhere / "rel-wt"  # where the pre-fix bug dropped the marker
        # stdout reports the real (absolute) worktree, not the relative input.
        self.assertEqual(out.strip(), str(real_wt))
        marker = real_wt / ".harness" / "active-plan"
        self.assertTrue(marker.is_file(), "marker must live inside git's real worktree")
        self.assertEqual(marker.read_text(encoding="utf-8"), "foo\n")
        # No phantom .harness littered into the process cwd.
        self.assertFalse((phantom / ".harness").exists(),
                         "no phantom marker dir in the process cwd")


class TestPartialSpawnRollback(unittest.TestCase):
    """DEFECT-2 regression: a post-`git worktree add` write failure rolls back.

    The marker write + project.json copy run after the worktree + branch exist; if
    one fails, spawn must remove the worktree, delete the branch, and return rc 2 —
    never leave a registered worktree with no marker.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-partial-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_marker_write_failure_rolls_back_worktree_and_branch(self):
        # Inject a filesystem failure at the marker write — the one mutation that
        # happens after `git worktree add`. Path.write_text is called nowhere else
        # in spawn(), so scoping the fault to the "active-plan" leaf targets exactly
        # the post-add step (real rollback runs; only the I/O failure is simulated).
        orig_write_text = Path.write_text

        def boom(self, *a, **k):
            if self.name == "active-plan":
                raise OSError("simulated ENOSPC")
            return orig_write_text(self, *a, **k)

        with mock.patch.object(Path, "write_text", boom):
            rc, out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("rolled back", err)
        # The worktree dir and the branch are both gone — no partial spawn.
        self.assertFalse(sw.worktree_path(self.repo, "foo").exists())
        self.assertFalse(sw._branch_exists(self.repo, "worker/foo"))
        # And re-spawn succeeds cleanly — the no-clobber guards don't block it.
        rc2, _out2, err2 = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc2, 0, err2)
        self.assertEqual(
            (sw.worktree_path(self.repo, "foo") / ".harness" / "active-plan").read_text(),
            "foo\n")

    def test_rollback_failure_reported_not_mislabeled(self):
        # Finding 1 regression: if the rollback git calls themselves fail, spawn must
        # NOT claim "no partial spawn" — it must report ROLLBACK INCOMPLETE and name
        # the worktree + branch that survived for manual cleanup. Simulate: the marker
        # write fails (triggers the rollback), and the rollback git calls return rc!=0.
        orig_write_text = Path.write_text

        def boom(self, *a, **k):
            if self.name == "active-plan":
                raise OSError("simulated ENOSPC")
            return orig_write_text(self, *a, **k)

        orig_git = sw._git

        def failing_rollback_git(args, root):
            if args[:2] == ["worktree", "remove"] or args[:2] == ["branch", "-D"]:
                return subprocess.CompletedProcess(args, 1, "", "simulated rollback failure")
            return orig_git(args, root)

        with mock.patch.object(Path, "write_text", boom), \
                mock.patch.object(sw, "_git", failing_rollback_git):
            rc, out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("ROLLBACK INCOMPLETE", err)
        self.assertNotIn("no partial spawn", err)
        # The honest message names what the operator must remove by hand.
        self.assertIn("worker/foo", err)
        self.assertIn(str(sw.worktree_path(self.repo, "foo")), err)

    def test_rollback_tolerates_git_timeout_no_crash(self):
        # Finding 2 regression: a rollback git call that hangs >30s surfaces as
        # subprocess.TimeoutExpired, which is NOT an OSError. The rollback must absorb
        # it (returning ROLLBACK INCOMPLETE) rather than let it escape and crash spawn
        # with a traceback. On the pre-fix code (bare `except OSError`, un-wrapped
        # rollback `_git`) this raises out of spawn and the test ERRORs.
        orig_write_text = Path.write_text

        def boom(self, *a, **k):
            if self.name == "active-plan":
                raise OSError("simulated ENOSPC")
            return orig_write_text(self, *a, **k)

        orig_git = sw._git

        def hanging_rollback_git(args, root):
            if args[:2] == ["worktree", "remove"]:
                raise subprocess.TimeoutExpired(cmd="git worktree remove", timeout=30)
            return orig_git(args, root)

        with mock.patch.object(Path, "write_text", boom), \
                mock.patch.object(sw, "_git", hanging_rollback_git):
            rc, out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("ROLLBACK INCOMPLETE", err)

    def test_rollback_incomplete_names_only_the_survivor(self):
        # Re-review observation: when the worktree removal succeeds but the branch
        # delete fails, the ROLLBACK INCOMPLETE message must name ONLY the surviving
        # branch — not the already-removed worktree. (Pre-fix the message named both
        # unconditionally.)
        orig_write_text = Path.write_text

        def boom(self, *a, **k):
            if self.name == "active-plan":
                raise OSError("simulated ENOSPC")
            return orig_write_text(self, *a, **k)

        orig_git = sw._git

        def branch_delete_fails(args, root):
            # Let the real worktree removal happen; only the branch delete "fails".
            if args[:2] == ["branch", "-D"]:
                return subprocess.CompletedProcess(args, 1, "", "simulated branch -D failure")
            return orig_git(args, root)

        with mock.patch.object(Path, "write_text", boom), \
                mock.patch.object(sw, "_git", branch_delete_fails):
            rc, out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("ROLLBACK INCOMPLETE", err)
        # The branch survived → named; the worktree was really removed → NOT named.
        self.assertIn("worker/foo", err)
        self.assertNotIn(str(sw.worktree_path(self.repo, "foo")), err)

    def test_post_create_non_oserror_failure_rolls_back(self):
        # ARCHITECTURAL safety net: the post-create block calls helpers that can raise
        # beyond OSError (subprocess.TimeoutExpired, AttributeError, ValueError, ...).
        # A narrow `except OSError` let those escape and crash spawn() after the
        # worktree + branch + marker were created — a partial spawn. The block must
        # catch *any* Exception and roll back. Inject a non-OSError from the copy
        # decision to prove the net fires regardless of exception type. (Pre-fix the
        # `except OSError` lets the ValueError escape → this ERRORs.)
        def boom(_root):
            raise ValueError("simulated unanticipated helper failure")

        with mock.patch.object(sw, "_needs_vault_project_copy", boom):
            rc, out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("no partial spawn", err)
        # The worktree + branch (and the marker inside the worktree) are all gone.
        self.assertFalse(sw.worktree_path(self.repo, "foo").exists())
        self.assertFalse(sw._branch_exists(self.repo, "worker/foo"))
        # And re-spawn succeeds — the no-clobber guards don't block it.
        rc2, _out2, err2 = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc2, 0, err2)


class TestFailedAddRollback(unittest.TestCase):
    """Finding 3 regression: a failed `git worktree add` deletes its orphan branch.

    `git worktree add -b worker/<slug>` registers the branch ref before it builds
    the worktree dir, so a failed add strands an orphan branch (verified against
    real git) that would trip the no-clobber branch guard on re-spawn. The
    add-failure path must delete it — never a partial spawn.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-addfail-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_failed_worktree_add_deletes_orphan_branch(self):
        orig_git = sw._git

        def failing_add(args, root):
            if args[:2] == ["worktree", "add"]:
                # Simulate git's real partial behavior: the branch ref is created,
                # then the add reports failure.
                orig_git(["branch", "worker/foo"], root)
                return subprocess.CompletedProcess(args, 1, "", "simulated add failure")
            return orig_git(args, root)

        with mock.patch.object(sw, "_git", failing_add):
            rc, out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("git worktree add", err)
        # The orphan branch the failed add left behind was deleted — re-spawn isn't
        # blocked by the no-clobber branch guard. (Pre-fix: the branch survives.)
        self.assertFalse(sw._branch_exists(self.repo, "worker/foo"),
                         "a failed add must delete its orphan worker/foo branch")
        # And a clean re-spawn succeeds.
        rc2, _out2, err2 = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc2, 0, err2)

    def test_failed_add_cleanup_that_raises_reports_no_crash(self):
        # Primary re-review defect: the orphan-branch cleanup on the add-failure path
        # must be guarded like the post-create rollback. A raising `_git` (git hangs
        # → subprocess.TimeoutExpired, NOT an OSError) must be absorbed and reported,
        # not escape and crash spawn() with a traceback. On the pre-fix code the
        # cleanup `_git` was unguarded, so this ERRORs.
        orig_git = sw._git

        def failing_add_then_hang(args, root):
            if args[:2] == ["worktree", "add"]:
                orig_git(["branch", "worker/foo"], root)  # git creates the ref, add fails
                return subprocess.CompletedProcess(args, 1, "", "simulated add failure")
            if args[:2] == ["branch", "-D"]:
                raise subprocess.TimeoutExpired(cmd="git branch -D", timeout=30)
            return orig_git(args, root)

        with mock.patch.object(sw, "_git", failing_add_then_hang):
            rc, out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("git worktree add", err)
        # The cleanup couldn't finish → honest report naming the surviving orphan.
        self.assertIn("ROLLBACK INCOMPLETE", err)
        self.assertIn("worker/foo", err)

    def test_failed_add_with_registered_worktree_rolls_back_both(self):
        # The realistic add failure: a checkout-PHASE failure (failing post-checkout
        # hook — verified against real git) returns rc!=0 with the worktree dir AND
        # branch fully built and registered, NOT just an orphan branch. The non-zero-rc
        # path must roll the worktree back too (worktree-first, or `branch -D` can't
        # delete a branch still checked out there) — else the worktree survives and the
        # no-clobber guard permanently blocks re-spawn. No mocks: real git end to end.
        # Pre-fix (rc-path cleaned only the branch) the worktree dir survives → FAIL.
        hooks = self.tmp / "hooks"
        hooks.mkdir()
        (hooks / "post-checkout").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        (hooks / "post-checkout").chmod(0o755)
        subprocess.run(["git", "-C", str(self.repo), "config",
                        "core.hooksPath", str(hooks)], check=True)

        wt = sw.worktree_path(self.repo, "foo")
        rc, out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("git worktree add", err)
        # The defect: the registered worktree dir must be gone, not stranded.
        self.assertFalse(os.path.lexists(wt),
                         "a checkout-phase add failure must roll back the worktree dir")
        self.assertFalse(sw._branch_exists(self.repo, "worker/foo"),
                         "...and the branch it left checked out there")
        # Clean rollback names no survivor.
        self.assertNotIn("ROLLBACK INCOMPLETE", err)
        # With the partial state gone, a re-spawn (hook removed) succeeds.
        subprocess.run(["git", "-C", str(self.repo), "config", "--unset",
                        "core.hooksPath"], check=True)
        rc2, _out2, err2 = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc2, 0, err2)

    def test_worktree_add_that_raises_rolls_back_no_crash(self):
        # The `git worktree add` call is itself non-atomic: git registers the branch
        # ref, then builds the worktree dir. A >30s hang raises subprocess.TimeoutExpired
        # (a SubprocessError, NOT an OSError) and SIGKILLs git mid-op, stranding the
        # orphan branch — a partial spawn via uncaught exception. The add call must be
        # guarded and rolled back. On the pre-fix code the raise escapes spawn() → ERROR.
        orig_git = sw._git

        def add_hangs(args, root):
            if args[:2] == ["worktree", "add"]:
                orig_git(["branch", "worker/foo"], root)  # git registers the ref first
                raise subprocess.TimeoutExpired(cmd="git worktree add", timeout=30)
            return orig_git(args, root)

        with mock.patch.object(sw, "_git", add_hangs):
            rc, out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("git worktree add", err)
        self.assertIn("no partial spawn", err)
        # The orphan branch the timed-out add stranded was rolled back.
        self.assertFalse(sw._branch_exists(self.repo, "worker/foo"),
                         "a raising add must roll back its orphan worker/foo branch")
        # And a clean re-spawn succeeds.
        rc2, _out2, err2 = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc2, 0, err2)

    def test_worktree_add_raise_rollback_incomplete_names_survivor(self):
        # Same raising-add path, but the rollback `branch -D` also hangs: the report
        # must name only the surviving orphan branch (not the worktree, which never
        # materialized) and still must not crash. Pre-fix: the add raise escapes → ERROR.
        orig_git = sw._git

        def add_hangs_then_branch_hangs(args, root):
            if args[:2] == ["worktree", "add"]:
                orig_git(["branch", "worker/foo"], root)
                raise subprocess.TimeoutExpired(cmd="git worktree add", timeout=30)
            if args[:2] == ["branch", "-D"]:
                raise subprocess.TimeoutExpired(cmd="git branch -D", timeout=30)
            return orig_git(args, root)

        with mock.patch.object(sw, "_git", add_hangs_then_branch_hangs):
            rc, out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("ROLLBACK INCOMPLETE", err)
        self.assertIn("worker/foo", err)
        self.assertNotIn("no partial spawn", err)
        # The worktree never materialized, so it must NOT be named as a survivor.
        self.assertNotIn("the worktree", err)


class TestSpawnPreflightReconcile(unittest.TestCase):
    """LC-6 defense-in-depth: a direct `/spawn-worker` onto an already-shipped plan
    no-ops (exit 3) before any worktree is created — `/plan --activate` is the
    primary chokepoint, this is the backstop. The resolved active plan's
    `expected_artifacts` are checked against the repo root."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-reconcile-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)
        self.harness = self.repo / ".harness"
        self.harness.mkdir(parents=True, exist_ok=True)
        # Standalone resolve returns <root>/.harness/PLAN-foo.md (existence not
        # required by the resolver) — plant a plan there for the reconcile to read.
        self.plan = self.harness / "PLAN-foo.md"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _declare(self, *arts: str):
        inline = ", ".join(arts)
        self.plan.write_text(
            f"---\nexpected_artifacts: [{inline}]\n---\n# Plan: foo\n", encoding="utf-8")

    def test_already_shipped_plan_refused_before_any_worktree(self):
        self._declare("shipped.txt")
        (self.repo / "shipped.txt").write_text("done\n", encoding="utf-8")
        rc, out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 3)
        self.assertEqual(out, "")
        self.assertIn("already shipped — nothing to do", err)
        # Nothing created: no worktree, no branch.
        self.assertFalse(sw.worktree_path(self.repo, "foo").exists())
        self.assertFalse(sw._branch_exists(self.repo, "worker/foo"))

    def test_pending_plan_with_missing_artifact_spawns_normally(self):
        self._declare("not-yet.txt")  # artifact absent → lane has work → proceed
        rc, out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 0, err)
        self.assertTrue(sw.worktree_path(self.repo, "foo").is_dir())
        self.assertTrue(sw._branch_exists(self.repo, "worker/foo"))

    def test_plan_without_expected_artifacts_spawns_normally(self):
        # Back-compat: no opt-in → the guard is dormant, spawn behaves as before.
        self.plan.write_text("# Plan: foo\n", encoding="utf-8")
        rc, out, err = sw.spawn("foo", str(self.repo), resolver=None)
        self.assertEqual(rc, 0, err)
        self.assertTrue(sw.worktree_path(self.repo, "foo").is_dir())


if __name__ == "__main__":
    unittest.main()
