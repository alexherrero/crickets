#!/usr/bin/env python3
"""Tests for src/conventions/scripts/coalescence_checks.py — the deterministic
close-out assertions ship-release now runs before tagging (coalescence-gate
items 1, 3, 5). Each of the three checks gets a passing fixture, a failing
fixture, and (where the convention can legitimately be absent) a graceful-skip
fixture, plus an end-to-end `main()` pass over all three at once.

stdlib only -- no pytest, no network, no `gh` binary required (the live issue
lookup is injected).
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "conventions" / "scripts"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


cc = _load("coalescence_checks_module", _SRC / "coalescence_checks.py")


class NarrativeRowTests(unittest.TestCase):
    def test_missing_row_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "Completed-Features.md"
            page.write_text(
                "| Date | Feature | Release | Roadmap id |\n"
                "|---|---|---|---|\n"
                "| 2026-07-01 | Something else shipped | crickets v3.20.0 | #1 |\n",
                encoding="utf-8",
            )
            result = cc.check_narrative_row(
                "v3.28.0", "crickets", Path(tmp), narrative_page=page,
            )
            self.assertEqual(result.status, "fail")
            self.assertIn("v3.28.0", result.message)

    def test_present_row_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "Completed-Features.md"
            page.write_text(
                "| Date | Feature | Release | Roadmap id |\n"
                "|---|---|---|---|\n"
                "| 2026-07-11 | Coalescence checks land | crickets v3.28.0 | #187 |\n",
                encoding="utf-8",
            )
            result = cc.check_narrative_row(
                "v3.28.0", "crickets", Path(tmp), narrative_page=page,
            )
            self.assertEqual(result.status, "pass")

    def test_combined_row_matches_either_repo(self):
        # agentm's page carries combined rows like "agentm v7.0.0 + crickets v3.27.0".
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "Completed-Features.md"
            page.write_text(
                "| 2026-07-10 | Paired release | agentm v7.0.0 + crickets v3.27.0 | ruling 4 |\n",
                encoding="utf-8",
            )
            result = cc.check_narrative_row(
                "v3.27.0", "crickets", Path(tmp), narrative_page=page,
            )
            self.assertEqual(result.status, "pass")

    def test_no_page_anywhere_skips_gracefully(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = cc.check_narrative_row(
                "v9.9.9", "some-third-party-project", Path(tmp),
                narrative_page=Path(tmp) / "no-such-file.md",
                fallback_page=Path(tmp) / "also-missing.md",
            )
            self.assertEqual(result.status, "skip")


class ArchiveHygieneTests(unittest.TestCase):
    def test_flat_plan_archive_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            harness = Path(tmp) / ".harness"
            harness.mkdir()
            (harness / "PLAN.archive.20260101-oops.md").write_text("stale", encoding="utf-8")
            result = cc.check_archive_hygiene(harness)
            self.assertEqual(result.status, "fail")
            self.assertIn("PLAN.archive.20260101-oops.md", result.message)

    def test_archived_under_archive_subdir_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            harness = Path(tmp) / ".harness"
            (harness / "archive").mkdir(parents=True)
            (harness / "archive" / "PLAN.archive.20260101-fine.md").write_text("ok", encoding="utf-8")
            (harness / "progress.md").write_text("log", encoding="utf-8")
            result = cc.check_archive_hygiene(harness)
            self.assertEqual(result.status, "pass")

    def test_no_harness_dir_skips_gracefully(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = cc.check_archive_hygiene(Path(tmp) / "no-such-harness")
            self.assertEqual(result.status, "skip")


class BoardItemClosedTests(unittest.TestCase):
    def _write_board_items(self, tmp, items):
        path = Path(tmp) / "board-items.json"
        path.write_text(json.dumps({"items": items}), encoding="utf-8")
        return path

    def test_no_item_id_skips_gracefully(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_board_items(tmp, [])
            result = cc.check_board_item_closed(None, path)
            self.assertEqual(result.status, "skip")

    def test_missing_board_items_file_skips_gracefully(self):
        result = cc.check_board_item_closed("plan-1", Path("/no/such/board-items.json"))
        self.assertEqual(result.status, "skip")

    def test_unknown_item_id_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_board_items(tmp, [{"id": "plan-1", "type": "plan", "title": "x"}])
            result = cc.check_board_item_closed("plan-does-not-exist", path)
            self.assertEqual(result.status, "fail")

    def test_still_open_issue_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_board_items(
                tmp, [{"id": "plan-1", "type": "plan", "title": "x", "issue": 42}],
            )
            result = cc.check_board_item_closed(
                "plan-1", path, gh_repo="alexherrero/crickets",
                gh_issue_state_fn=lambda repo, n: "OPEN",
            )
            self.assertEqual(result.status, "fail")
            self.assertIn("42", result.message)

    def test_closed_issue_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_board_items(
                tmp, [{"id": "plan-1", "type": "plan", "title": "x", "issue": 42}],
            )
            result = cc.check_board_item_closed(
                "plan-1", path, gh_repo="alexherrero/crickets",
                gh_issue_state_fn=lambda repo, n: "CLOSED",
            )
            self.assertEqual(result.status, "pass")

    def test_no_issue_falls_back_to_status_field_done_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_board_items(
                tmp, [{"id": "plan-1", "type": "plan", "title": "x", "status": "Done"}],
            )
            result = cc.check_board_item_closed("plan-1", path)
            self.assertEqual(result.status, "pass")

    def test_no_issue_falls_back_to_status_field_not_done_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_board_items(
                tmp, [{"id": "plan-1", "type": "plan", "title": "x", "status": "In Progress"}],
            )
            result = cc.check_board_item_closed("plan-1", path)
            self.assertEqual(result.status, "fail")

    def test_issue_present_but_no_gh_repo_skips_gracefully(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_board_items(
                tmp, [{"id": "plan-1", "type": "plan", "title": "x", "issue": 42}],
            )
            result = cc.check_board_item_closed("plan-1", path)
            self.assertEqual(result.status, "skip")


class MainEndToEndTests(unittest.TestCase):
    """All three checks wired together through main(), the way ship-release
    actually invokes this script."""

    def _setup_project(self, tmp, *, narrative_ok, archive_ok, board_status):
        repo_root = Path(tmp)
        wiki_dir = repo_root / "wiki" / "reference"
        wiki_dir.mkdir(parents=True)
        row = "| 2026-07-11 | Ships it | crickets v3.28.0 | #187 |\n" if narrative_ok else \
              "| 2026-07-01 | Unrelated | crickets v3.20.0 | #1 |\n"
        (wiki_dir / "Completed-Features.md").write_text(row, encoding="utf-8")

        harness = repo_root / ".harness"
        if archive_ok:
            (harness / "archive").mkdir(parents=True)
        else:
            harness.mkdir()
            (harness / "PLAN.archive.20260101-stale.md").write_text("x", encoding="utf-8")

        board_items = repo_root / "board-items.json"
        board_items.write_text(json.dumps({"items": [
            {"id": "plan-1", "type": "plan", "title": "x", "status": board_status},
        ]}), encoding="utf-8")
        return repo_root, board_items

    def test_all_three_satisfied_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root, board_items = self._setup_project(
                tmp, narrative_ok=True, archive_ok=True, board_status="Done",
            )
            rc = cc.main([
                "--tag", "v3.28.0", "--repo-root", str(repo_root),
                "--repo-name", "crickets", "--item-id", "plan-1",
                "--board-items-path", str(board_items),
            ])
            self.assertEqual(rc, 0)

    def test_still_open_board_row_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root, board_items = self._setup_project(
                tmp, narrative_ok=True, archive_ok=True, board_status="In Progress",
            )
            rc = cc.main([
                "--tag", "v3.28.0", "--repo-root", str(repo_root),
                "--repo-name", "crickets", "--item-id", "plan-1",
                "--board-items-path", str(board_items),
            ])
            self.assertEqual(rc, 1)

    def test_flat_archive_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root, board_items = self._setup_project(
                tmp, narrative_ok=True, archive_ok=False, board_status="Done",
            )
            rc = cc.main([
                "--tag", "v3.28.0", "--repo-root", str(repo_root),
                "--repo-name", "crickets", "--item-id", "plan-1",
                "--board-items-path", str(board_items),
            ])
            self.assertEqual(rc, 1)

    def test_missing_narrative_row_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root, board_items = self._setup_project(
                tmp, narrative_ok=False, archive_ok=True, board_status="Done",
            )
            rc = cc.main([
                "--tag", "v3.28.0", "--repo-root", str(repo_root),
                "--repo-name", "crickets", "--item-id", "plan-1",
                "--board-items-path", str(board_items),
                "--fallback-narrative-page", str(repo_root / "no-fallback.md"),
            ])
            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()


class ExtractGhRefsTests(unittest.TestCase):
    def test_finds_the_real_v9_0_2_form(self):
        # The literal shape that shipped: "Plan A of 2 (GH #70)".
        body = ("**PATCH.** Loose Ends Release 3, Plan A of 2 (GH #70). Builds "
                "out the install-mode x OS test matrix.")
        self.assertEqual(cc.extract_gh_refs(body), [70])

    def test_finds_several_and_dedupes_preserving_order(self):
        body = "ships GH #72 and GH #45, and again GH #72"
        self.assertEqual(cc.extract_gh_refs(body), [72, 45])

    def test_is_case_insensitive(self):
        self.assertEqual(cc.extract_gh_refs("closes gh #9"), [9])

    def test_ignores_a_bare_pr_reference(self):
        # A bare #359 is a PR link; a merged PR closes by a different mechanism
        # than the issue it ships, so matching it would fail every release.
        self.assertEqual(cc.extract_gh_refs("merged in #359, see also #12"), [])

    def test_empty_or_none_body_yields_nothing(self):
        self.assertEqual(cc.extract_gh_refs(""), [])
        self.assertEqual(cc.extract_gh_refs(None), [])


class ReleaseBodyRefsClosedTests(unittest.TestCase):
    def _check(self, body, states, **kw):
        return cc.check_release_body_refs_closed(
            body, gh_repo="o/r",
            gh_issue_state_fn=lambda repo, n: states.get(n), **kw)

    def test_fails_when_a_named_id_is_still_open(self):
        # THE regression. v9.0.2's body named GH #70 while #70 stayed open for
        # weeks. This check would have stopped that release.
        r = self._check("Plan A of 2 (GH #70).", {70: "OPEN"})
        self.assertEqual(r.status, "fail")
        self.assertIn("#70", r.message)

    def test_passes_when_every_named_id_is_closed(self):
        r = self._check("ships GH #70 and GH #72", {70: "CLOSED", 72: "CLOSED"})
        self.assertEqual(r.status, "pass")

    def test_fails_naming_only_the_open_ones(self):
        r = self._check("ships GH #70 and GH #72", {70: "CLOSED", 72: "OPEN"})
        self.assertEqual(r.status, "fail")
        self.assertIn("#72", r.message)
        self.assertNotIn("#70", r.message)

    def test_passes_when_the_body_names_no_ids(self):
        r = self._check("a routine patch release", {})
        self.assertEqual(r.status, "pass")

    def test_an_unreadable_id_is_skipped_not_failed(self):
        # gh unavailable, or the ref resolves to a PR — must not block a release.
        r = self._check("ships GH #70", {70: None})
        self.assertEqual(r.status, "pass")
        self.assertIn("unreadable", r.message)

    def test_skips_without_a_body(self):
        self.assertEqual(cc.check_release_body_refs_closed(None).status, "skip")

    def test_skips_when_ids_are_named_but_no_repo_is_given(self):
        r = cc.check_release_body_refs_closed("ships GH #70")
        self.assertEqual(r.status, "skip")
