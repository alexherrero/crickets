#!/usr/bin/env python3
"""Tests for src/development-lifecycle/scripts/vault_designs.py.

A project's living designs sit in its vault, beside (not inside) the repo's own
wiki/designs/. /plan and the session-start hook must find them with no agentm
resolver and no repo page. These tests build the notes in a scratch folder, so what
is pinned is the scoring and the ordering, not the operator's real vault.

stdlib only.
"""
from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPT = _ROOT / "src" / "development-lifecycle" / "scripts" / "vault_designs.py"


def _load():
    spec = importlib.util.spec_from_file_location("vault_designs", _SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules["vault_designs"] = m
    spec.loader.exec_module(m)
    return m


vd = _load()


def note(directory: Path, name: str, **fm) -> Path:
    lines = ["---"]
    for k, v in fm.items():
        lines.append("%s: %s" % (k, v))
    lines += ["---", "", "# %s" % name, ""]
    p = directory / ("%s.md" % name)
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


class TmpCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)


class FrontmatterTests(unittest.TestCase):
    def test_flow_lists_block_lists_and_scalars(self):
        fm = vd.parse_frontmatter("---\nslug: a\naliases: [a, 'b c', \"d\"]\nrelated: [\"[[x]]\", \"[[y]]\"]\n"
                                  "governs:\n  - src/a\n  - src/b/\nstatus: active\n---\nbody\n")
        self.assertEqual(fm["slug"], "a")
        self.assertEqual(fm["aliases"], ["a", "b c", "d"])
        self.assertEqual(fm["related"], ["x", "y"])
        self.assertEqual(fm["governs"], ["src/a", "src/b/"])

    def test_no_frontmatter_or_a_broken_one_gives_nothing_and_never_raises(self):
        for text in ("", "# just a heading\n", "---\nunterminated: yes\n", "---\n: : :\n---\n"):
            self.assertIsInstance(vd.parse_frontmatter(text), dict)


class ScoreTests(unittest.TestCase):
    def d(self, **kw):
        base = dict(path=Path("x.md"), slug="s", status="active", updated="", aliases=[], tags=[], governs=[])
        base.update(kw)
        return vd.Design(**base)

    def test_a_governs_entry_matches_the_path_and_anything_under_it(self):
        d = self.d(governs=["src/design"])
        self.assertEqual(vd.score(d, "src/design"), 10)
        self.assertEqual(vd.score(d, "src/design/commands/design.md"), 10)
        self.assertEqual(vd.score(d, "src/designer/x.py"), 0)

    def test_an_area_name_matches_the_slug_or_an_alias(self):
        d = self.d(slug="build-it-create-it", aliases=["build-it", "create-it"])
        self.assertEqual(vd.score(d, "build-it"), 5)
        self.assertEqual(vd.score(d, "build-it-create-it"), 5)
        self.assertEqual(vd.score(d, "src/build-it"), 0)  # a path is not an area name

    def test_tags_score_one_each_and_the_generic_design_tag_never_counts(self):
        d = self.d(tags=["crickets", "development-lifecycle", "design"])
        self.assertEqual(vd.score(d, "src/development-lifecycle/commands/work.md"), 1)
        self.assertEqual(vd.score(d, "src/design/x.py"), 0)

    def test_an_empty_target_scores_nothing(self):
        self.assertEqual(vd.score(self.d(governs=["a"], slug="a"), ""), 0)


class FindTests(TmpCase):
    def test_a_governs_match_wins_over_tags(self):
        note(self.dir, "a", slug="a", status="active", updated="2026-01-01", governs="[src/x]", tags="[x]")
        note(self.dir, "b", slug="b", status="active", updated="2026-02-01", tags="[x, src, y]")
        got = vd.find(vd.scan(self.dir), "src/x/y.py")
        self.assertEqual(got.slug, "a")

    def test_one_shared_tag_is_not_a_match(self):
        note(self.dir, "a", slug="a", status="active", tags="[crickets]")
        self.assertIsNone(vd.find(vd.scan(self.dir), "crickets/foo.py"))

    def test_two_shared_tags_are_a_match(self):
        note(self.dir, "a", slug="a", status="active", tags="[crickets, development-lifecycle]")
        got = vd.find(vd.scan(self.dir), "crickets/development-lifecycle/x.py")
        self.assertEqual(got.slug, "a")

    def test_a_note_that_is_not_live_is_never_found(self):
        for status in ("draft", "superseded", "proposed", "", "retired"):
            note(self.dir, "n-%s" % (status or "none"), slug="n", status=status, aliases="[build-it]")
        self.assertIsNone(vd.find(vd.scan(self.dir), "build-it"))

    def test_both_live_statuses_are_found(self):
        note(self.dir, "a", slug="a", status="launched", aliases="[topic]")
        self.assertEqual(vd.find(vd.scan(self.dir), "topic").slug, "a")
        note(self.dir, "b", slug="b", status="active", aliases="[topic]", updated="2099-01-01")
        self.assertEqual(vd.find(vd.scan(self.dir), "topic").slug, "b")

    def test_a_tie_goes_to_the_newer_note_then_the_slug_and_is_repeatable(self):
        note(self.dir, "old", slug="old", status="active", updated="2026-01-01", aliases="[t]")
        note(self.dir, "new", slug="new", status="active", updated="2026-06-01", aliases="[t]")
        note(self.dir, "also-new", slug="also-new", status="active", updated="2026-06-01", aliases="[t]")
        for _ in range(3):
            self.assertEqual(vd.find(vd.scan(self.dir), "t").slug, "also-new")

    def test_a_timestamp_ranks_above_the_same_day_date(self):
        # #287: the old key negated each character, which reverses order only for strings
        # of one length; "2026-04-10" is a prefix of "2026-04-10T15:30:00Z".
        note(self.dir, "z-older", slug="z-older", status="active", updated="2026-04-10", aliases="[topic]")
        note(self.dir, "a-newer", slug="a-newer", status="active", updated="2026-04-10T15:30:00Z", aliases="[topic]")
        self.assertEqual(vd.find(vd.scan(self.dir), "topic").slug, "a-newer")
        self.assertEqual([d.slug for d in vd._newest_first(vd.live(vd.scan(self.dir)))], ["a-newer", "z-older"])

    def test_a_note_without_a_date_ranks_last(self):
        note(self.dir, "nodate", slug="nodate", status="active", aliases="[t]")
        note(self.dir, "dated", slug="dated", status="active", updated="2020-01-01", aliases="[t]")
        self.assertEqual(vd.find(vd.scan(self.dir), "t").slug, "dated")

    def test_the_slug_defaults_to_the_file_name(self):
        note(self.dir, "from-the-file", status="active")
        self.assertEqual(vd.scan(self.dir)[0].slug, "from-the-file")

    def test_an_empty_folder_matches_nothing(self):
        self.assertIsNone(vd.find(vd.scan(self.dir), "anything"))

    def test_a_note_shaped_like_a_real_vault_design_is_found_by_its_alias(self):
        note(self.dir, "build-it-create-it", type="design", status="active", created="2026-11-21",
             updated="2026-11-21", slug="build-it-create-it", aliases="[build-it-create-it, build-it, create-it]",
             tags="[crickets, development-lifecycle, build-it, create-it, review-loop, design]",
             related='["[[build-it-create-it-brief]]"]')
        for target in ("build-it", "create-it"):
            self.assertEqual(vd.find(vd.scan(self.dir), target).slug, "build-it-create-it", target)
        # a path under the area the tags name: two tags (crickets path part absent, development-lifecycle present)
        self.assertEqual(vd.find(vd.scan(self.dir), "src/development-lifecycle/create-it/x.md").slug,
                         "build-it-create-it")


class ListTests(TmpCase):
    def test_only_live_notes_newest_first_and_capped(self):
        note(self.dir, "a", slug="a", status="active", updated="2026-01-01")
        note(self.dir, "b", slug="b", status="launched", updated="2026-03-01")
        note(self.dir, "c", slug="c", status="draft", updated="2026-09-01")
        note(self.dir, "d", slug="d", status="active", updated="2026-02-01")
        names = [d.slug for d in vd._newest_first(vd.live(vd.scan(self.dir)))]
        self.assertEqual(names, ["b", "d", "a"])

    def test_non_markdown_and_unreadable_files_are_skipped(self):
        (self.dir / "x.txt").write_text("---\nstatus: active\n---\n", encoding="utf-8")
        (self.dir / "bad.md").write_bytes(b"\xff\xfe\x00bad")
        note(self.dir, "ok", slug="ok", status="active")
        self.assertEqual([d.slug for d in vd.scan(self.dir)], ["ok"])


class CliTests(TmpCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = vd.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def test_list_prints_paths_and_exits_zero_even_with_none(self):
        p = note(self.dir, "a", slug="a", status="active", updated="2026-01-01")
        rc, out, _ = self.run_cli("list", "--dir", str(self.dir))
        self.assertEqual((rc, out.strip()), (0, str(p)))
        empty = self.dir / "empty"
        empty.mkdir()
        self.assertEqual(self.run_cli("list", "--dir", str(empty)), (0, "", ""))

    def test_list_limit(self):
        for i in range(6):
            note(self.dir, "n%d" % i, slug="n%d" % i, status="active", updated="2026-01-0%d" % (i + 1))
        self.assertEqual(len(self.run_cli("list", "--dir", str(self.dir))[1].splitlines()), 4)
        self.assertEqual(len(self.run_cli("list", "--dir", str(self.dir), "--limit", "2")[1].splitlines()), 2)

    def test_find_exit_codes(self):
        p = note(self.dir, "a", slug="a", status="active", aliases="[topic]")
        self.assertEqual(self.run_cli("find", "topic", "--dir", str(self.dir))[:2], (0, str(p) + "\n"))
        self.assertEqual(self.run_cli("find", "nothing-like-it", "--dir", str(self.dir))[0], 1)

    def test_a_missing_folder_exits_three_and_creates_nothing(self):
        gone = self.dir / "nope"
        rc, _, err = self.run_cli("list", "--dir", str(gone))
        self.assertEqual(rc, 3)
        self.assertIn("no designs folder", err)
        self.assertFalse(gone.exists())

    def test_without_agentm_it_exits_three(self):
        with mock.patch.object(vd, "_project_homes", return_value=None):
            self.assertEqual(self.run_cli("find", "x")[0], 3)

    def test_it_asks_project_homes_when_no_dir_is_given(self):
        p = note(self.dir, "a", slug="a", status="active", aliases="[topic]")
        fake = mock.Mock()
        fake.home.return_value = self.dir
        with mock.patch.object(vd, "_project_homes", return_value=fake):
            rc, out, _ = self.run_cli("find", "topic", "--cwd", "/some/repo")
        self.assertEqual((rc, out.strip()), (0, str(p)))
        fake.home.assert_called_once_with("designs", cwd="/some/repo")

    def test_a_timeout_is_passed_through_to_the_ask(self):
        fake = mock.Mock()
        fake.home.return_value = self.dir
        with mock.patch.object(vd, "_project_homes", return_value=fake):
            self.run_cli("list", "--cwd", "/r", "--timeout", "3")
        fake.home.assert_called_once_with("designs", cwd="/r", timeout=3.0)

    def test_home_that_names_no_folder_is_exit_three(self):
        fake = mock.Mock()
        fake.home.return_value = None
        with mock.patch.object(vd, "_project_homes", return_value=fake):
            self.assertEqual(self.run_cli("list")[0], 3)

    def test_usage_errors_exit_two(self):
        self.assertEqual(self.run_cli("find")[0], 2)
        self.assertEqual(self.run_cli("list", "--dir", "a", "--cwd", "b")[0], 2)

    def test_runs_as_a_script(self):
        note(self.dir, "a", slug="a", status="active", aliases="[topic]")
        p = subprocess.run([sys.executable, str(_SCRIPT), "find", "topic", "--dir", str(self.dir)],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)


class SourceTests(unittest.TestCase):
    def test_it_does_not_import_agentm_or_write(self):
        text = _SCRIPT.read_text(encoding="utf-8")
        for bad in ("import harness_memory", "import process_seam", "write_text(", "mkdir(", ".open(\"w", "open(path, \"w"):
            self.assertNotIn(bad, text, bad)


if __name__ == "__main__":
    unittest.main()
