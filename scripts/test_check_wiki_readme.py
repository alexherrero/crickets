#!/usr/bin/env python3
"""Tests for check-wiki.py rule (l) — repo-root README governance (Option B).

The repo-root README lives outside the walked wiki tree, so it used to be
wholly ungoverned. Rule (l) brings it under the checker: every relative-path
markdown link must resolve to an existing file under the repo root. Governance
defaults on; --no-readme or {"include_readme": false} in <repo>/.diataxis.json
opts out.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so the module's dataclasses resolve their string
    # annotations (from __future__ import annotations) via sys.modules.
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


cw = _load("check_wiki_under_test", "../src/wiki/scripts/check-wiki.py")


class RootDocGovernanceTest(unittest.TestCase):
    def _repo(self) -> Path:
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        return d

    # ── rule l: link resolution ──────────────────────────────────────────

    def test_dead_relative_link_fires_rule_l(self):
        repo = self._repo()
        (repo / "README.md").write_text(
            "# Title\n\nSee [the thing](src/nope/missing.md).\n", encoding="utf-8")
        issues = cw.collect_root_doc_issues(repo)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "l")
        self.assertEqual(issues[0].severity, "hard")
        self.assertIn("src/nope/missing.md", issues[0].message)

    def test_resolving_links_pass(self):
        repo = self._repo()
        (repo / "CONTRIBUTING.md").write_text("x", encoding="utf-8")
        (repo / "docs").mkdir()
        (repo / "docs" / "guide.md").write_text("y", encoding="utf-8")
        (repo / "README.md").write_text(
            "# T\n\n[contrib](CONTRIBUTING.md), [guide](docs/guide.md), "
            "[ext](https://example.com/x.md), [mail](mailto:a@b.c), "
            "[anchor](#sec).\n", encoding="utf-8")
        self.assertEqual(cw.collect_root_doc_issues(repo), [])

    def test_anchor_stripped_then_resolved(self):
        repo = self._repo()
        (repo / "docs").mkdir()
        (repo / "docs" / "guide.md").write_text("y", encoding="utf-8")
        (repo / "README.md").write_text(
            "# T\n\n[g](docs/guide.md#a-section)\n", encoding="utf-8")
        self.assertEqual(cw.collect_root_doc_issues(repo), [])

    def test_directory_link_resolves(self):
        repo = self._repo()
        (repo / "src").mkdir()
        (repo / "README.md").write_text("# T\n\n[tree](src/)\n", encoding="utf-8")
        self.assertEqual(cw.collect_root_doc_issues(repo), [])

    def test_markdown_image_link_checked(self):
        # ![alt](path) — the [alt](path) span is matched; a missing asset fires.
        repo = self._repo()
        (repo / "README.md").write_text(
            "# T\n\n![banner](assets/missing.png)\n", encoding="utf-8")
        issues = cw.collect_root_doc_issues(repo)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "l")

    def test_multiple_dead_links_each_reported(self):
        repo = self._repo()
        (repo / "README.md").write_text(
            "# T\n\n[a](x/one.md) and [b](y/two.md)\n", encoding="utf-8")
        issues = cw.collect_root_doc_issues(repo)
        self.assertEqual(len(issues), 2)
        self.assertEqual({i.rule for i in issues}, {"l"})

    def test_missing_readme_silent(self):
        repo = self._repo()
        self.assertEqual(cw.collect_root_doc_issues(repo), [])

    # ── opt-out resolution ───────────────────────────────────────────────

    def test_include_default_true(self):
        self.assertTrue(cw.resolve_include_readme(self._repo(), True))

    def test_cli_no_readme_opts_out(self):
        self.assertFalse(cw.resolve_include_readme(self._repo(), False))

    def test_config_opts_out(self):
        repo = self._repo()
        (repo / ".diataxis.json").write_text(
            '{"include_readme": false}', encoding="utf-8")
        self.assertFalse(cw.resolve_include_readme(repo, True))

    def test_config_true_keeps_default(self):
        repo = self._repo()
        (repo / ".diataxis.json").write_text(
            '{"include_readme": true}', encoding="utf-8")
        self.assertTrue(cw.resolve_include_readme(repo, True))

    def test_malformed_config_ignored(self):
        repo = self._repo()
        (repo / ".diataxis.json").write_text("{not json", encoding="utf-8")
        self.assertTrue(cw.resolve_include_readme(repo, True))

    def test_cli_overrides_config_include(self):
        # CLI --no-readme wins even if config requests include.
        repo = self._repo()
        (repo / ".diataxis.json").write_text(
            '{"include_readme": true}', encoding="utf-8")
        self.assertFalse(cw.resolve_include_readme(repo, False))

    # ── regression guard: the live repo README must stay clean ───────────

    def test_live_repo_readme_is_clean(self):
        repo_root = SCRIPTS.parent
        if not (repo_root / "README.md").is_file():
            self.skipTest("no repo README at the expected root")
        issues = cw.collect_root_doc_issues(repo_root)
        self.assertEqual(
            issues, [],
            f"live README has unresolved relative links: {[i.message for i in issues]}")


if __name__ == "__main__":
    unittest.main()
