#!/usr/bin/env python3
"""Tests for scripts/check-version-bump.py — the per-plugin-version anti-recurrence guard.

Most coverage exercises the pure logic (path→slug mapping, version parsing,
SemVer comparison, offender detection) directly, no git needed. One class
(`TestDiffPathsMergeBase`) spins up a throwaway git repo to lock in the
merge-base diff behavior — the regression that keeps a concurrent advance on
`main` from being mis-attributed to a feature branch.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, _HERE / filename)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


cvb = _load("check_version_bump", "check-version-bump.py")


class TestChangedPluginSlugs(unittest.TestCase):
    def test_maps_src_paths_to_slugs(self):
        paths = [
            "src/wiki-maintenance/skills/wiki-author/SKILL.md",
            "src/wiki-maintenance/group.yaml",
            "src/pii/skills/pii-scrubber/SKILL.md",
        ]
        self.assertEqual(cvb.changed_plugin_slugs(paths),
                         {"wiki-maintenance", "pii"})

    def test_ignores_non_src_and_top_level(self):
        paths = [
            "dist/claude-code/plugins/wiki-maintenance/.claude-plugin/plugin.json",
            "scripts/emit_claude.py",
            "wiki/Home.md",
            "CHANGELOG.md",
            "src",            # bare top-level, no plugin component
            "src/lonefile",   # only 2 parts — not under a plugin dir
        ]
        self.assertEqual(cvb.changed_plugin_slugs(paths), set())


class TestParseVersion(unittest.TestCase):
    def test_extracts_plain_value(self):
        self.assertEqual(cvb.parse_version("name: X\nversion: 0.2.0\n"), "0.2.0")

    def test_strips_quotes(self):
        self.assertEqual(cvb.parse_version('version: "1.4.2"\n'), "1.4.2")
        self.assertEqual(cvb.parse_version("version: '0.1.0'\n"), "0.1.0")

    def test_none_text_and_missing_key(self):
        self.assertIsNone(cvb.parse_version(None))
        self.assertIsNone(cvb.parse_version("name: X\nstandalone: true\n"))


class TestFindUnbumped(unittest.TestCase):
    def _versions(self, mapping):
        """Build a slug -> group.yaml-text lookup from a slug -> version map.
        A None value means 'group.yaml absent at that ref'."""
        def lookup(slug):
            v = mapping.get(slug)
            return None if v is None else f"name: {slug}\nversion: {v}\n"
        return lookup

    def test_unbumped_is_flagged(self):
        base = self._versions({"wiki-maintenance": "0.1.0"})
        cur = self._versions({"wiki-maintenance": "0.1.0"})
        self.assertEqual(
            cvb.find_unbumped({"wiki-maintenance"}, base, cur),
            ["wiki-maintenance"],
        )

    def test_bumped_passes(self):
        base = self._versions({"wiki-maintenance": "0.1.0"})
        cur = self._versions({"wiki-maintenance": "0.2.0"})
        self.assertEqual(cvb.find_unbumped({"wiki-maintenance"}, base, cur), [])

    def test_new_plugin_skipped(self):
        # No group.yaml at base → brand-new plugin, first publish, no bump req.
        base = self._versions({"newplug": None})
        cur = self._versions({"newplug": "0.1.0"})
        self.assertEqual(cvb.find_unbumped({"newplug"}, base, cur), [])

    def test_deleted_plugin_skipped(self):
        # No group.yaml in working tree → plugin removed, nothing to bump.
        base = self._versions({"gone": "0.1.0"})
        cur = self._versions({"gone": None})
        self.assertEqual(cvb.find_unbumped({"gone"}, base, cur), [])

    def test_missing_version_key_both_sides_is_unbumped(self):
        # A group.yaml with no version: key parses to None on both sides;
        # changed content + no bump → flagged (must add + set version:).
        base = lambda s: "name: x\nstandalone: true\n"
        cur = lambda s: "name: x\nstandalone: true\ncategory: documentation\n"
        self.assertEqual(cvb.find_unbumped({"x"}, base, cur), ["x"])

    def test_multiple_mixed(self):
        base = self._versions({"a": "0.1.0", "b": "0.3.0", "c": "1.0.0"})
        cur = self._versions({"a": "0.1.0", "b": "0.4.0", "c": "1.0.0"})
        self.assertEqual(
            cvb.find_unbumped({"a", "b", "c"}, base, cur),
            ["a", "c"],  # sorted; b bumped
        )

    def test_downgrade_is_flagged(self):
        # A downgrade differs from the base yet still defeats the guard's
        # purpose: consumers on the published higher version never pull "down".
        base = self._versions({"wiki-maintenance": "0.2.0"})
        cur = self._versions({"wiki-maintenance": "0.1.0"})
        self.assertEqual(
            cvb.find_unbumped({"wiki-maintenance"}, base, cur),
            ["wiki-maintenance"],
        )

    def test_garbage_current_version_is_flagged(self):
        # An unparseable current version can't be proven a real increase.
        base = self._versions({"x": "0.1.0"})
        cur = self._versions({"x": "banana"})
        self.assertEqual(cvb.find_unbumped({"x"}, base, cur), ["x"])

    def test_partial_current_version_is_flagged(self):
        # `0.2` is not the three-part SemVer core the guard requires.
        base = self._versions({"x": "0.1.0"})
        cur = self._versions({"x": "0.2"})
        self.assertEqual(cvb.find_unbumped({"x"}, base, cur), ["x"])

    def test_garbage_base_with_valid_current_is_forward_correction(self):
        # Replacing a historical garbage version with a real one is progress,
        # not a regression — not an offender.
        base = self._versions({"x": "banana"})
        cur = self._versions({"x": "0.2.0"})
        self.assertEqual(cvb.find_unbumped({"x"}, base, cur), [])

    def test_major_and_patch_increases_pass(self):
        base = self._versions({"maj": "1.4.2", "pat": "0.1.0"})
        cur = self._versions({"maj": "2.0.0", "pat": "0.1.1"})
        self.assertEqual(cvb.find_unbumped({"maj", "pat"}, base, cur), [])


class TestSemverKey(unittest.TestCase):
    def test_parses_three_part_core(self):
        self.assertEqual(cvb.semver_key("0.2.0"), (0, 2, 0))
        self.assertEqual(cvb.semver_key("1.4.2"), (1, 4, 2))

    def test_ordering_is_numeric_not_lexical(self):
        # 0.10.0 > 0.9.0 numerically (a string compare would get this wrong).
        self.assertGreater(cvb.semver_key("0.10.0"), cvb.semver_key("0.9.0"))

    def test_tolerates_v_prefix_and_metadata(self):
        self.assertEqual(cvb.semver_key("v1.2.3"), (1, 2, 3))
        self.assertEqual(cvb.semver_key("1.2.3-rc1"), (1, 2, 3))
        self.assertEqual(cvb.semver_key("1.2.3+build7"), (1, 2, 3))

    def test_rejects_non_semver(self):
        for bad in (None, "banana", "0.2", "1.2.3.4", "", "a.b.c", "-1.0.0"):
            self.assertIsNone(cvb.semver_key(bad), bad)


class TestDiffPathsMergeBase(unittest.TestCase):
    """Integration test for the merge-base diff (DEFECT 1 regression).

    Builds a throwaway git repo where `main` advances *after* a feature branch
    forks, touching a plugin the feature branch never touches. The guard must
    measure the diff from the fork point, so main's advance is NOT attributed to
    the feature branch — while the branch's own (uncommitted) change still shows.
    """

    def _git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args],
                       check=True, capture_output=True, text=True)

    def _write(self, relpath, text):
        p = self.repo / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self._git("init", "-q")
        self._git("config", "user.email", "t@example.com")
        self._git("config", "user.name", "Test")
        # fork point M: foo and bar both present (both with a tracked SKILL so
        # the branch can *modify* one — `git diff <commit>` only surfaces
        # tracked-file changes from the worktree, not brand-new untracked files)
        self._write("src/foo/group.yaml", "name: foo\nversion: 0.1.0\n")
        self._write("src/foo/skills/foo/SKILL.md", "v1\n")
        self._write("src/bar/group.yaml", "name: bar\nversion: 0.1.0\n")
        self._write("src/bar/skills/bar/SKILL.md", "v1\n")
        self._git("add", "-A")
        self._git("commit", "-qm", "M")
        # the default branch name varies by git config — capture it
        self.base_branch = subprocess.run(
            ["git", "-C", str(self.repo), "rev-parse", "--abbrev-ref", "HEAD"],
            check=True, capture_output=True, text=True).stdout.strip()
        self._orig_root = cvb.ROOT
        cvb.ROOT = self.repo  # _git()/_diff_paths() run cwd=ROOT

    def tearDown(self):
        cvb.ROOT = self._orig_root
        self._tmp.cleanup()

    def test_main_advance_not_attributed_to_branch(self):
        self._git("checkout", "-q", "-b", "feature")          # fork at M
        self._git("checkout", "-q", self.base_branch)
        self._write("src/foo/skills/foo/SKILL.md", "v2-on-main\n")  # concurrent
        self._git("add", "-A")
        self._git("commit", "-qm", "advance foo on main")
        self._git("checkout", "-q", "feature")
        self._write("src/bar/skills/bar/SKILL.md", "bar-change\n")  # uncommitted edit

        changed = cvb.changed_plugin_slugs(cvb._diff_paths(self.base_branch))
        self.assertIn("bar", changed)      # branch's own (uncommitted) change seen
        self.assertNotIn("foo", changed)   # main's post-fork advance NOT blamed here


class TestIsDeferredBumpContext(unittest.TestCase):
    """Pure logic for the deferred-bump (worker) context detection (ADR 0030).

    Under Model A, a `worker/<slug>` branch defers its version bump to the
    serialized integrator, so an absent bump there is advisory, not a failure.
    The explicit `$VERSION_BUMP_DEFER` env wins over the branch heuristic (the
    CI-topology re-audit hook the ADR names).
    """

    def test_worker_branch_is_deferred(self):
        self.assertTrue(cvb.is_deferred_bump_context("worker/foo", {}))
        self.assertTrue(cvb.is_deferred_bump_context("worker/some-long-slug", {}))

    def test_main_and_other_branches_are_not(self):
        for branch in ("main", "feature/x", "release/1.0", "worker", "myworker/x"):
            with self.subTest(branch=branch):
                self.assertFalse(cvb.is_deferred_bump_context(branch, {}), branch)

    def test_none_branch_is_not_deferred(self):
        self.assertFalse(cvb.is_deferred_bump_context(None, {}))

    def test_env_forces_on_even_off_worker(self):
        for val in ("1", "true", "TRUE", "Yes", "on", "  on  "):
            with self.subTest(val=val):
                self.assertTrue(
                    cvb.is_deferred_bump_context("main", {"VERSION_BUMP_DEFER": val}), val)

    def test_env_forces_off_even_on_worker(self):
        # An explicit env value wins over the branch heuristic — off / empty /
        # garbage all resolve to "not deferred", overriding a `worker/` branch.
        for val in ("0", "false", "no", "off", "", "banana"):
            with self.subTest(val=val):
                self.assertFalse(
                    cvb.is_deferred_bump_context("worker/foo", {"VERSION_BUMP_DEFER": val}), val)


class TestDeferralEndToEnd(unittest.TestCase):
    """The version-bump gate is advisory in a worker context, FAIL otherwise (ADR 0030).

    A real git repo where a plugin's src/ changed but its `version:` did NOT move:
    on a `worker/<slug>` branch (or with `$VERSION_BUMP_DEFER` set) `main()` treats
    the absent bump as advisory (rc 0); on a `feature/<x>` branch the same state
    fails (rc 1). Drives the full `main()` path, including the CI-PR-safe branch
    resolution — so the env signals are isolated per case (`$GITHUB_HEAD_REF` /
    `$VERSION_BUMP_DEFER` popped so the local checked-out branch is what's read).
    """

    def _git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args],
                       check=True, capture_output=True, text=True)

    def _write(self, relpath, text):
        p = self.repo / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self._git("init", "-q")
        self._git("config", "user.email", "t@example.com")
        self._git("config", "user.name", "Test")
        self._write("src/foo/group.yaml", "name: foo\nversion: 0.1.0\n")
        self._write("src/foo/skills/foo/SKILL.md", "v1\n")
        self._git("add", "-A")
        self._git("commit", "-qm", "M")
        self.base_branch = subprocess.run(
            ["git", "-C", str(self.repo), "rev-parse", "--abbrev-ref", "HEAD"],
            check=True, capture_output=True, text=True).stdout.strip()
        self._orig_root = cvb.ROOT
        cvb.ROOT = self.repo  # _git()/_diff_paths()/_resolve_branch_name() run cwd=ROOT

    def tearDown(self):
        cvb.ROOT = self._orig_root
        self._tmp.cleanup()

    def _change_foo_without_bump(self, branch):
        """On a fresh `branch` off base, change foo's src but leave its version."""
        self._git("checkout", "-q", "-b", branch)
        self._write("src/foo/skills/foo/SKILL.md", "v2-no-bump\n")
        self._git("commit", "-qam", "edit foo, no version bump")

    def _run_main(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cvb.main(["--base", self.base_branch])
        return rc, out.getvalue()

    def test_worker_branch_makes_absent_bump_advisory(self):
        self._change_foo_without_bump("worker/foo")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GITHUB_HEAD_REF", None)
            os.environ.pop("VERSION_BUMP_DEFER", None)
            rc, out = self._run_main()
        self.assertEqual(rc, 0, out)
        self.assertIn("deferred-bump worker context", out)
        self.assertIn("foo", out)

    def test_feature_branch_still_fails(self):
        self._change_foo_without_bump("feature/x")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GITHUB_HEAD_REF", None)
            os.environ.pop("VERSION_BUMP_DEFER", None)
            rc, out = self._run_main()
        self.assertEqual(rc, 1, out)
        self.assertIn("FAIL", out)
        self.assertIn("foo", out)

    def test_env_defer_makes_absent_bump_advisory_off_worker(self):
        # Even on a non-worker branch, $VERSION_BUMP_DEFER=1 asserts the context
        # (the CI-topology re-audit hook), so the absent bump is advisory.
        self._change_foo_without_bump("feature/x")
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GITHUB_HEAD_REF", None)
            os.environ["VERSION_BUMP_DEFER"] = "1"
            rc, out = self._run_main()
        self.assertEqual(rc, 0, out)
        self.assertIn("deferred-bump worker context", out)


if __name__ == "__main__":
    unittest.main()
