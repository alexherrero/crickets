#!/usr/bin/env python3
"""Tests for wiki_watch_detect.py — change-detection + durable idempotency
(src/wiki-maintenance/scripts/wiki_watch_detect.py) — crickets ④ wiki-maintenance
part 4/5 (the wiki-watcher, W1), task 2.

Deterministic-only (DC-W8): the significance pre-filter, the per-source cursor +
pending/dispatched state, candidate computation, the never-drop / never-double-
dispatch restart proof, and retry/backoff bookkeeping — all PURE over injected
deltas + an explicit `now`. The git/content probes are exercised against a
throwaway temp git repo (deterministic; git is on PATH in CI).
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_WW_SCRIPTS = _ROOT / "src" / "wiki-maintenance" / "scripts"


def _load(name: str):
    if str(_WW_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_WW_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, _WW_SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


det = _load("wiki_watch_detect")


# ----------------------------------------------------------------------------
# Significance pre-filter
# ----------------------------------------------------------------------------

class TestSignificance(unittest.TestCase):
    def test_keeps_code_and_doc_sources(self):
        for p in ["src/app.py", "PLAN.md", "ROADMAP.md", "designs/wiki.md",
                  "lib/foo.ts", "scripts/run.sh", "README.md", ".harness/PLAN.md"]:
            self.assertTrue(det.is_significant(p), p)

    def test_drops_noise_dirs(self):
        for p in ["dist/app.js", "node_modules/x/index.js", "__pycache__/m.pyc",
                  ".git/config", "build/out.o", "target/debug/bin",
                  "wiki/how-to/Page.md"]:  # wiki/ = documenter output -> no loop
            self.assertFalse(det.is_significant(p), p)

    def test_drops_noise_suffixes_and_basenames(self):
        for p in ["m.pyc", "a.min.js", "x.lock", "package-lock.json",
                  "poetry.lock", ".DS_Store", "build.log", "a/b/Cargo.lock"]:
            self.assertFalse(det.is_significant(p), p)

    def test_blank_path_insignificant(self):
        self.assertFalse(det.is_significant(""))
        self.assertFalse(det.is_significant("   "))

    def test_windows_separators_normalized(self):
        self.assertFalse(det.is_significant("dist\\app.js"))
        self.assertTrue(det.is_significant("src\\app.py"))

    def test_filter_is_order_preserving_and_deduped(self):
        got = det.filter_significant(["b.py", "a.py", "b.py", "dist/x.js", "a.py"])
        self.assertEqual(got, ["b.py", "a.py"])


class TestWatchSourceMatching(unittest.TestCase):
    def test_dot_matches_everything(self):
        self.assertTrue(det._matches_watch_sources("any/where.py", ["."]))

    def test_prefix_and_exact(self):
        self.assertTrue(det._matches_watch_sources("designs/wiki.md", ["designs/"]))
        self.assertTrue(det._matches_watch_sources("PLAN.md", ["PLAN.md"]))
        self.assertFalse(det._matches_watch_sources("src/app.py", ["designs/", "PLAN.md"]))

    def test_dir_without_trailing_slash(self):
        self.assertTrue(det._matches_watch_sources("designs/a/b.md", ["designs"]))
        self.assertFalse(det._matches_watch_sources("designsX/a.md", ["designs"]))


# ----------------------------------------------------------------------------
# Backoff
# ----------------------------------------------------------------------------

class TestBackoff(unittest.TestCase):
    def test_schedule(self):
        self.assertEqual(det.backoff_seconds(0), 0)
        self.assertEqual(det.backoff_seconds(1), 60)
        self.assertEqual(det.backoff_seconds(2), 120)
        self.assertEqual(det.backoff_seconds(3), 240)

    def test_capped(self):
        self.assertEqual(det.backoff_seconds(100), 3600)


# ----------------------------------------------------------------------------
# Durable state: cursors + pending/dispatched + save/load
# ----------------------------------------------------------------------------

class TestWikiWatchState(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.dir = Path(self._td.name) / "wiki-watch"

    def tearDown(self):
        self._td.cleanup()

    def test_fresh_source_is_empty(self):
        s = det.WikiWatchState(self.dir).source("repo")
        self.assertEqual(s.cursor, "")
        self.assertEqual(s.token, "")
        self.assertEqual(s.dispatched, [])

    def test_mark_dispatched_and_reload(self):
        st = det.WikiWatchState(self.dir)
        st.mark_dispatched("repo", "sha1", "a.py")
        st.mark_dispatched("repo", "sha1", "b.py")
        st.save()
        s = det.WikiWatchState(self.dir).source("repo")
        self.assertEqual(s.token, "sha1")
        self.assertEqual(s.dispatched, ["a.py", "b.py"])
        self.assertEqual(s.cursor, "")  # not advanced yet

    def test_new_token_resets_dispatched(self):
        st = det.WikiWatchState(self.dir)
        st.mark_dispatched("repo", "sha1", "a.py")
        st.mark_dispatched("repo", "sha2", "c.py")  # token rolled over
        self.assertEqual(st.source("repo").dispatched, ["c.py"])

    def test_advance_cursor_clears_pending(self):
        st = det.WikiWatchState(self.dir)
        st.mark_dispatched("repo", "sha1", "a.py")
        st.advance_cursor("repo", "sha1")
        st.save()
        s = det.WikiWatchState(self.dir).source("repo")
        self.assertEqual(s.cursor, "sha1")
        self.assertEqual(s.dispatched, [])
        self.assertEqual(s.token, "")

    def test_record_failure_increments(self):
        st = det.WikiWatchState(self.dir)
        st.record_failure("repo", "sha1", "a.py", now=1000.0)
        st.record_failure("repo", "sha1", "a.py", now=1100.0)
        rec = st.source("repo").failures["a.py"]
        self.assertEqual(rec["count"], 2)
        self.assertEqual(rec["last"], 1100.0)

    def test_dispatch_clears_failure(self):
        st = det.WikiWatchState(self.dir)
        st.record_failure("repo", "sha1", "a.py", now=1000.0)
        st.mark_dispatched("repo", "sha1", "a.py")
        self.assertNotIn("a.py", st.source("repo").failures)

    def test_corrupt_state_files_treated_as_empty(self):
        self.dir.mkdir(parents=True)
        (self.dir / "cursors.json").write_text("{ broken", encoding="utf-8")
        (self.dir / "pending.json").write_text("also broken", encoding="utf-8")
        s = det.WikiWatchState(self.dir).source("repo")
        self.assertEqual(s.cursor, "")


# ----------------------------------------------------------------------------
# Candidate computation + the idempotency proof
# ----------------------------------------------------------------------------

class TestComputeCandidates(unittest.TestCase):
    def _paths(self, cands):
        return [c.path for c in cands]

    def test_unchanged_token_yields_nothing(self):
        s = det.SourceState(cursor="sha1")
        self.assertEqual(det.compute_candidates(s, token="sha1", changed_paths=["a.py"]), [])

    def test_filters_noise_and_watch_sources(self):
        s = det.SourceState(cursor="sha0")
        cands = det.compute_candidates(
            s, token="sha1",
            changed_paths=["designs/x.md", "src/app.py", "dist/y.js", "node_modules/z.js"],
            watch_sources=["designs/"])
        self.assertEqual(self._paths(cands), ["designs/x.md"])

    def test_drops_already_dispatched_under_token(self):
        s = det.SourceState(cursor="sha0", token="sha1", dispatched=["a.py"])
        cands = det.compute_candidates(
            s, token="sha1", changed_paths=["a.py", "b.py"])
        self.assertEqual(self._paths(cands), ["b.py"])

    def test_dispatched_under_different_token_not_excluded(self):
        # dispatched set is scoped to its token; a new token re-surfaces everything.
        s = det.SourceState(cursor="sha0", token="OLD", dispatched=["a.py"])
        cands = det.compute_candidates(s, token="sha2", changed_paths=["a.py", "b.py"])
        self.assertEqual(self._paths(cands), ["a.py", "b.py"])

    def test_backoff_suppresses_then_releases(self):
        s = det.SourceState(cursor="sha0", token="sha1",
                            failures={"a.py": {"count": 1, "last": 1000.0}})
        # within backoff (60s) -> suppressed
        self.assertEqual(
            self._paths(det.compute_candidates(
                s, token="sha1", changed_paths=["a.py"], now=1030.0)), [])
        # after backoff -> eligible again
        self.assertEqual(
            self._paths(det.compute_candidates(
                s, token="sha1", changed_paths=["a.py"], now=1061.0)), ["a.py"])

    def test_restart_idempotency_no_drop_no_double_dispatch(self):
        """The load-bearing proof: dispatch some candidates, DON'T advance the
        cursor (simulating a crash mid-cycle), reload state, recompute -> only the
        undispatched change resurfaces; the dispatched one does NOT (no double-
        dispatch), and nothing is lost (no drop). Then advance the cursor and the
        same token yields nothing."""
        with tempfile.TemporaryDirectory() as td:
            sdir = Path(td) / "wiki-watch"
            token = "shaHEAD"
            changed = ["a.py", "b.py", "c.py"]

            # Cycle 1: compute 3 candidates, dispatch a.py + b.py, then "crash"
            # (cursor NOT advanced).
            st = det.WikiWatchState(sdir)
            c1 = det.compute_candidates(st.source("repo"), token=token, changed_paths=changed)
            self.assertEqual(sorted(self._paths(c1)), ["a.py", "b.py", "c.py"])
            st.mark_dispatched("repo", token, "a.py")
            st.mark_dispatched("repo", token, "b.py")
            st.save()

            # Cycle 2 (post-restart): reload, recompute against the SAME token.
            st2 = det.WikiWatchState(sdir)
            c2 = det.compute_candidates(st2.source("repo"), token=token, changed_paths=changed)
            self.assertEqual(self._paths(c2), ["c.py"])  # no drop (c.py), no re-dispatch (a/b)

            # Finish c.py, advance the cursor.
            st2.mark_dispatched("repo", token, "c.py")
            st2.advance_cursor("repo", token)
            st2.save()

            # Cycle 3: same token now == cursor -> nothing.
            st3 = det.WikiWatchState(sdir)
            self.assertEqual(
                det.compute_candidates(st3.source("repo"), token=token, changed_paths=changed), [])


# ----------------------------------------------------------------------------
# Git + content probes (impure) — against a throwaway repo
# ----------------------------------------------------------------------------

def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True)


class TestGitProbes(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.repo = Path(self._td.name)
        _git(self.repo, "init", "-q")
        _git(self.repo, "config", "user.email", "t@example.com")
        _git(self.repo, "config", "user.name", "Test")

    def tearDown(self):
        self._td.cleanup()

    def _commit(self, msg):
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", msg)
        return det.git_current_head(self.repo)

    def test_head_none_for_non_git(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(det.git_current_head(td))

    def test_changed_between_commits(self):
        (self.repo / "a.py").write_text("1\n", encoding="utf-8")
        first = self._commit("a")
        (self.repo / "b.py").write_text("2\n", encoding="utf-8")
        (self.repo / "a.py").write_text("1\n2\n", encoding="utf-8")
        self._commit("b+edit")
        changed = det.git_changed_files(self.repo, first, include_uncommitted=False)
        self.assertEqual(changed, ["a.py", "b.py"])

    def test_changed_empty_when_at_head(self):
        (self.repo / "a.py").write_text("1\n", encoding="utf-8")
        head = self._commit("a")
        self.assertEqual(det.git_changed_files(self.repo, head, include_uncommitted=False), [])

    def test_uncommitted_changes_seen(self):
        (self.repo / "a.py").write_text("1\n", encoding="utf-8")
        head = self._commit("a")
        (self.repo / "c.py").write_text("new\n", encoding="utf-8")  # untracked, uncommitted
        changed = det.git_changed_files(self.repo, head, include_uncommitted=True)
        self.assertIn("c.py", changed)

    def test_no_cursor_lists_all_tracked(self):
        (self.repo / "a.py").write_text("1\n", encoding="utf-8")
        (self.repo / "dir").mkdir()
        (self.repo / "dir" / "b.py").write_text("2\n", encoding="utf-8")
        self._commit("init")
        changed = det.git_changed_files(self.repo, "", include_uncommitted=False)
        self.assertEqual(sorted(changed), ["a.py", "dir/b.py"])


class TestContentToken(unittest.TestCase):
    def test_absent_is_empty(self):
        self.assertEqual(det.content_token("/no/such/file/here.md"), "")

    def test_changes_with_content(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "PLAN.md"
            p.write_text("v1", encoding="utf-8")
            t1 = det.content_token(p)
            p.write_text("v2", encoding="utf-8")
            t2 = det.content_token(p)
            self.assertTrue(t1 and t2 and t1 != t2)


class TestStateDirResolution(unittest.TestCase):
    def test_local_mode_is_repo_harness(self):
        with tempfile.TemporaryDirectory() as td:
            sd = det.resolve_state_dir(td, prefer_vault=False)
            self.assertEqual(sd, Path(td) / ".harness" / "wiki-watch")


if __name__ == "__main__":
    unittest.main()
