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
