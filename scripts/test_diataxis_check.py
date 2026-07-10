#!/usr/bin/env python3
"""Tests for the diataxis-author convention-drift (voice-drift) check
(src/wiki-maintenance/skills/diataxis-author/scripts/check.py) — crickets ④
wiki-maintenance part 3/5, task 5.

Deterministic-only (DC-7): the `banned:` directive parse, the term-scan finding
emission (drifting page surfaces a finding; clean page none), the strict-vs-info
severity, and the non-breaking exit-code rule (info findings don't fail; --strict
escalates to error). The check runs against a FIXTURE overlay (a per-repo
`.diataxis-conventions.md` with a `banned:` line).
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SKILL_SCRIPTS = _ROOT / "src" / "wiki" / "skills" / "diataxis-author" / "scripts"


def _load(name: str):
    if str(_SKILL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SKILL_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, _SKILL_SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


chk = _load("check")


class TestExtractBannedTerms(unittest.TestCase):
    def test_parses_comma_list(self):
        self.assertEqual(chk._extract_banned_terms("banned: alpha, beta, gamma"),
                         ["alpha", "beta", "gamma"])

    def test_strips_quotes_and_keeps_phrases(self):
        self.assertEqual(
            chk._extract_banned_terms('banned: "this journey", essentially'),
            ["this journey", "essentially"])

    def test_dedupes_case_insensitively_order_preserving(self):
        self.assertEqual(chk._extract_banned_terms("banned: Foo, foo, BAR, foo"),
                         ["foo", "bar"])

    def test_accumulates_multiple_directives(self):
        text = "intro\nbanned: a, b\nmore text\n  banned: c\n"
        self.assertEqual(chk._extract_banned_terms(text), ["a", "b", "c"])

    def test_no_directive_yields_empty(self):
        self.assertEqual(chk._extract_banned_terms("# A page\nno banned line here.\n"), [])

    def test_quoted_phrase_with_internal_commas_is_one_term(self):
        # Quoting is the grouping delimiter, not the comma (regression) — and it
        # must hold in ANY list position, not just the first segment.
        self.assertEqual(
            chk._extract_banned_terms('banned: "ready, set, go", essentially'),
            ["ready, set, go", "essentially"])
        self.assertEqual(
            chk._extract_banned_terms('banned: essentially, "ready, set, go"'),
            ["essentially", "ready, set, go"])

    def test_single_quoted_non_leading_term_strips_its_quotes(self):
        self.assertEqual(chk._extract_banned_terms("banned: a, 'b c', d"),
                         ["a", "b c", "d"])

    def test_empty_quotes_dropped(self):
        self.assertEqual(chk._extract_banned_terms('banned: "", foo'), ["foo"])

    def test_banned_line_inside_a_code_fence_is_ignored(self):
        overlay = "Example:\n```\nbanned: notreal\n```\nbanned: actual\n"
        self.assertEqual(chk._extract_banned_terms(overlay), ["actual"])


class TestConventionDriftHeuristic(unittest.TestCase):
    def _page(self, body: str) -> Path:
        d = Path(self._td.name)
        p = d / "page.md"
        p.write_text(body, encoding="utf-8")
        return p

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._td.cleanup()

    def test_drifting_page_surfaces_info_finding(self):
        p = self._page("# Doc\nWe synergize the teams to ship.\n")
        findings = chk._heuristic_convention_drift(p, ["synergize"], strict=False)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "diataxis/convention-drift")
        self.assertEqual(findings[0].severity, "info")
        self.assertIn("synergize", findings[0].msg)

    def test_strict_escalates_to_error(self):
        p = self._page("# Doc\nWe synergize the teams.\n")
        findings = chk._heuristic_convention_drift(p, ["synergize"], strict=True)
        self.assertEqual(findings[0].severity, "error")

    def test_clean_page_no_finding(self):
        p = self._page("# Doc\nRun the command to start the widget.\n")
        self.assertEqual(chk._heuristic_convention_drift(p, ["synergize"], strict=False), [])

    def test_no_banned_terms_no_finding(self):
        p = self._page("# Doc\nWe synergize everything.\n")
        self.assertEqual(chk._heuristic_convention_drift(p, [], strict=False), [])

    def test_term_match_is_word_bounded(self):
        # "synergize" must not match inside "synergized" (word boundary).
        p = self._page("# Doc\nThe synergized output is fine.\n")
        self.assertEqual(chk._heuristic_convention_drift(p, ["synergize"], strict=False), [])

    def test_banned_word_only_in_house_style_block_is_not_flagged(self):
        # The author-facing house-style scaffolding block embeds banned words;
        # it's deleted before publish, so it must not count as drift.
        block = ("<!-- ─── house style (base) — author-facing; delete before publishing\n"
                 "LEARNED LESSONS: avoid synergize and delve\n"
                 "─── end house style ─── -->")
        p = self._page(f"# Doc\n{block}\nRun the command to start the widget.\n")
        self.assertEqual(chk._heuristic_convention_drift(p, ["synergize", "delve"], strict=False), [])

    def test_banned_word_in_body_still_flagged_even_with_a_house_style_block(self):
        # Only the scaffolding block is stripped — real body drift still fires.
        block = ("<!-- ─── house style — author-facing\n"
                 "─── end house style ─── -->")
        p = self._page(f"# Doc\n{block}\nWe synergize the teams here.\n")
        findings = chk._heuristic_convention_drift(p, ["synergize"], strict=False)
        self.assertEqual(len(findings), 1)

    def test_arbitrary_comment_does_not_swallow_real_body_text(self):
        # A stray `<!--` documenting comment syntax must NOT cause real body drift
        # to be skipped (we strip only the house-style block, not all comments).
        p = self._page("# Doc\nWrite `<!--` to open a comment. We synergize here.\n")
        findings = chk._heuristic_convention_drift(p, ["synergize"], strict=False)
        self.assertEqual(len(findings), 1)

    def test_regex_metachar_term_does_not_crash_or_false_match(self):
        p = self._page("# Doc\nUse the c++ compiler here.\n")
        findings = chk._heuristic_convention_drift(p, ["c++"], strict=False)
        self.assertEqual(len(findings), 1)
        # And a metachar term absent from the page yields nothing (no regex blowup).
        self.assertEqual(chk._heuristic_convention_drift(
            self._page("# Doc\nplain text.\n"), ["a.b", "(note)"], strict=False), [])


class TestStaleXrefHeuristic(unittest.TestCase):
    """Consolidation arc CONS-2 task 7 — /bugfix for two stale-xref false
    positives: asset links (SVG et al.) and structural-page links (Home)."""

    def _page(self, body: str) -> Path:
        d = Path(self._td.name)
        p = d / "page.md"
        p.write_text(body, encoding="utf-8")
        return p

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._td.cleanup()

    def test_svg_target_not_flagged_stale(self):
        p = self._page("# Doc\nSee the [architecture diagram](diagram.svg).\n")
        self.assertEqual(chk._heuristic_stale_xref(p, {"Doc"}), [])

    def test_other_non_markdown_asset_targets_not_flagged(self):
        p = self._page(
            "# Doc\n[a png](shot.png) [a pdf](spec.pdf) [a json](data.json)\n")
        self.assertEqual(chk._heuristic_stale_xref(p, {"Doc"}), [])

    def test_genuinely_stale_md_link_still_flagged(self):
        # Regression guard: the SVG/asset fix must not blunt real detection.
        p = self._page("# Doc\nSee [Gone](TotallyMadeUp.md) for details.\n")
        findings = chk._heuristic_stale_xref(p, {"Doc"})
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "diataxis/stale-xref")
        self.assertIn("TotallyMadeUp", findings[0].msg)

    def test_genuinely_stale_extensionless_link_still_flagged(self):
        p = self._page("# Doc\nSee [Gone](TotallyMadeUp) for details.\n")
        findings = chk._heuristic_stale_xref(p, {"Doc"})
        self.assertEqual(len(findings), 1)


class TestStaleXrefHomeLinkEndToEnd(unittest.TestCase):
    """The Home-link case is fixed in run_check (all_stems is built there, not
    inside the heuristic itself), so it needs an end-to-end fixture."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._td.cleanup()

    def _stale_findings(self, report) -> list:
        return [f for f in report.findings if f.rule == "diataxis/stale-xref"]

    def test_home_link_not_flagged_stale(self):
        wiki = Path(self._td.name) / "wiki"
        (wiki / "how-to").mkdir(parents=True)
        (wiki / "Home.md").write_text("# Home\nWelcome.\n", encoding="utf-8")
        (wiki / "how-to" / "Page.md").write_text(
            "# Page\nBack to [Home](Home).\n", encoding="utf-8")
        report = chk.run_check(wiki_root=wiki, strict=False, check_wiki_py=None)
        flagged_targets = {f.msg for f in self._stale_findings(report)}
        self.assertFalse(any("Home" in msg for msg in flagged_targets))

    def test_genuinely_stale_link_still_flagged_end_to_end(self):
        wiki = Path(self._td.name) / "wiki"
        (wiki / "how-to").mkdir(parents=True)
        (wiki / "Home.md").write_text("# Home\nWelcome.\n", encoding="utf-8")
        (wiki / "how-to" / "Page.md").write_text(
            "# Page\nSee [Gone](NoSuchPage) for details.\n", encoding="utf-8")
        report = chk.run_check(wiki_root=wiki, strict=False, check_wiki_py=None)
        self.assertEqual(len(self._stale_findings(report)), 1)


class TestExitCode(unittest.TestCase):
    def _report(self, *severities) -> object:
        r = chk.CheckReport(wiki_root="x", check_wiki_status="ran",
                            check_wiki_findings=0, skill_heuristic_findings=0)
        r.findings = [chk.Finding(file="f", rule="r", severity=s, msg="m") for s in severities]
        return r

    def test_only_info_findings_pass(self):
        # convention-drift in non-strict mode = info → must NOT fail (non-breaking).
        self.assertEqual(chk._exit_code(self._report("info", "info")), 0)

    def test_error_finding_fails(self):
        self.assertEqual(chk._exit_code(self._report("info", "error")), 1)

    def test_warning_finding_fails(self):
        self.assertEqual(chk._exit_code(self._report("warning")), 1)

    def test_no_findings_pass(self):
        self.assertEqual(chk._exit_code(self._report()), 0)


class TestRunCheckEndToEnd(unittest.TestCase):
    def _make_wiki(self, banned: str, pages: dict) -> Path:
        d = Path(self._td.name)
        wiki = d / "wiki"
        (wiki / "how-to").mkdir(parents=True)
        # The fixture overlay: a per-repo .diataxis-conventions.md `banned:` line.
        (wiki / ".diataxis-conventions.md").write_text(
            f"# repo conventions\nbanned: {banned}\n", encoding="utf-8")
        for name, body in pages.items():
            (wiki / "how-to" / name).write_text(body, encoding="utf-8")
        return wiki

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._td.cleanup()

    def _drift_findings(self, report) -> list:
        return [f for f in report.findings if f.rule == "diataxis/convention-drift"]

    def test_fixture_overlay_drives_a_finding_on_the_drifting_page(self):
        wiki = self._make_wiki("synergize", {
            "Drift.md": "# Drift\nWe synergize the teams to ship faster.\n",
            "Clean.md": "# Clean\nRun the command to start the widget.\n",
        })
        report = chk.run_check(wiki_root=wiki, strict=False, check_wiki_py=None)
        drift = self._drift_findings(report)
        # The drifting page is flagged; the clean page is not.
        flagged = {Path(f.file).name for f in drift}
        self.assertIn("Drift.md", flagged)
        self.assertNotIn("Clean.md", flagged)
        # Non-strict → info severity → does not fail the check on its own.
        self.assertTrue(all(f.severity == "info" for f in drift))

    def test_strict_makes_convention_drift_fail(self):
        wiki = self._make_wiki("synergize", {
            "Drift.md": "# Drift\nWe synergize the teams.\n",
        })
        report = chk.run_check(wiki_root=wiki, strict=True, check_wiki_py=None)
        drift = self._drift_findings(report)
        self.assertTrue(drift and all(f.severity == "error" for f in drift))
        self.assertEqual(chk._exit_code(report), 1)

    def test_conventions_file_itself_is_not_scanned(self):
        # The .diataxis-conventions.md overlay source declares the banned term but
        # must not be flagged for it (dotfiles are skipped from the page walk).
        wiki = self._make_wiki("synergize", {
            "Clean.md": "# Clean\nRun the command to start the widget.\n",
        })
        report = chk.run_check(wiki_root=wiki, strict=True, check_wiki_py=None)
        flagged = {Path(f.file).name for f in self._drift_findings(report)}
        self.assertNotIn(".diataxis-conventions.md", flagged)


if __name__ == "__main__":
    unittest.main()
