#!/usr/bin/env python3
"""Tests for scripts/check-dist-references.py (R2.1 / cricketsPluginsB#3).

A synthetic fixture dist/ tree proves the classifier: a dangling relative
markdown link is caught, a sibling-plugin ${CLAUDE_PLUGIN_ROOT}/../other
reference resolves cleanly, and a template placeholder (<link>, bare wiki
page slug) is never mistaken for a real path.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_SPEC = importlib.util.spec_from_file_location("check_dist_references", _HERE / "check-dist-references.py")
assert _SPEC and _SPEC.loader
cdr = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cdr)  # type: ignore[union-attr]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestFindDanglingReferences(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dist = Path(self._tmp.name) / "dist"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_clean_tree_finds_nothing(self) -> None:
        _write(self.dist / "claude-code" / "plugins" / "demo" / "skills" / "x" / "SKILL.md",
               "See [the guide](../y.md).\n")
        _write(self.dist / "claude-code" / "plugins" / "demo" / "skills" / "y.md", "# y\n")
        findings = cdr.find_dangling_references(self.dist)
        self.assertEqual(findings, [])

    def test_dangling_relative_link_is_caught(self) -> None:
        _write(self.dist / "claude-code" / "plugins" / "demo" / "agents" / "a.md",
               "Templates in [here](../does-not-exist.md).\n")
        findings = cdr.find_dangling_references(self.dist)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["plugin"], "demo")
        self.assertEqual(findings[0]["target"], "../does-not-exist.md")
        self.assertFalse(findings[0]["grandfathered"])

    def test_link_escaping_the_plugin_tree_is_dangling_even_if_file_exists_elsewhere(self) -> None:
        # A markdown link (not ${CLAUDE_PLUGIN_ROOT}) escaping to a sibling
        # plugin is still dangling — plain relative links are NOT the
        # documented cross-plugin escape hatch; only ${CLAUDE_PLUGIN_ROOT}/..
        # is (see the sibling-plugin test below).
        _write(self.dist / "claude-code" / "plugins" / "demo" / "hooks" / "h.md",
               "See [sibling](../../other/README.md).\n")
        _write(self.dist / "claude-code" / "plugins" / "other" / "README.md", "# other\n")
        findings = cdr.find_dangling_references(self.dist)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["target"], "../../other/README.md")

    def test_plugin_root_var_reaching_a_sibling_plugin_resolves_cleanly(self) -> None:
        _write(self.dist / "claude-code" / "plugins" / "demo" / "commands" / "c.md",
               "Run `python3 ${CLAUDE_PLUGIN_ROOT}/../other/scripts/tool.py`.\n")
        _write(self.dist / "claude-code" / "plugins" / "other" / "scripts" / "tool.py", "# tool\n")
        findings = cdr.find_dangling_references(self.dist)
        self.assertEqual(findings, [])

    def test_plugin_root_var_reaching_outside_the_host_plugins_tree_is_dangling(self) -> None:
        _write(self.dist / "claude-code" / "plugins" / "demo" / "commands" / "c.md",
               "Run `python3 ${CLAUDE_PLUGIN_ROOT}/../../not-a-plugin.py`.\n")
        findings = cdr.find_dangling_references(self.dist)
        self.assertEqual(len(findings), 1)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/", findings[0]["target"])

    def test_placeholders_are_never_flagged(self) -> None:
        _write(self.dist / "claude-code" / "plugins" / "demo" / "templates" / "t.md",
               "See [Overview](Overview) and [x](<link>) and {{commit_url}} "
               "and `${CLAUDE_PLUGIN_ROOT}/…` and a real [broken](../broken.md).\n")
        findings = cdr.find_dangling_references(self.dist)
        # only the one real relative-path reference should surface
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["target"], "../broken.md")

    def test_external_and_anchor_only_links_are_never_flagged(self) -> None:
        _write(self.dist / "claude-code" / "plugins" / "demo" / "a.md",
               "[web](https://example.com/x) [mail](mailto:a@example.com) [anchor](#section)\n")
        findings = cdr.find_dangling_references(self.dist)
        self.assertEqual(findings, [])

    def test_known_violation_is_marked_grandfathered(self) -> None:
        # Mirror a real remaining grandfathered pair exactly (cricketsPluginsB#3's
        # documenter.md -> ../documentation.md pair was fixed + removed 2026-07-05).
        _write(self.dist / "claude-code" / "plugins" / "code-review" / "hooks" / "evidence-tracker" / "hook.md",
               "See [here](../kill-switch/hook.md).\n")
        findings = cdr.find_dangling_references(self.dist)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0]["grandfathered"])


class TestMainExitCodes(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dist = Path(self._tmp.name) / "dist"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_missing_dist_exits_2(self) -> None:
        self.assertEqual(cdr.main(["--dist-root", str(self.dist)]), 2)

    def test_clean_tree_exits_0(self) -> None:
        _write(self.dist / "claude-code" / "plugins" / "demo" / "a.md", "clean\n")
        self.assertEqual(cdr.main(["--dist-root", str(self.dist)]), 0)

    def test_dangling_reference_exits_1_default_mode(self) -> None:
        _write(self.dist / "claude-code" / "plugins" / "demo" / "a.md", "[x](../gone.md)\n")
        self.assertEqual(cdr.main(["--dist-root", str(self.dist)]), 1)

    def test_grandfathered_only_exits_0_in_default_mode_but_1_in_strict(self) -> None:
        _write(self.dist / "claude-code" / "plugins" / "code-review" / "hooks" / "evidence-tracker" / "hook.md",
               "[x](../kill-switch/hook.md)\n")
        self.assertEqual(cdr.main(["--dist-root", str(self.dist)]), 0)
        self.assertEqual(cdr.main(["--dist-root", str(self.dist), "--strict"]), 1)

    def test_real_repo_dist_is_clean_after_grandfathering(self) -> None:
        """The actual gate wired into check-all.sh: run against this repo's
        own dist/ (skips gracefully if not built) and expect a clean pass —
        the real reproduction of the plan's Task 3 Verification bullet."""
        if not cdr.DIST.is_dir():
            self.skipTest("dist/ not built — run scripts/generate.py build first")
        self.assertEqual(cdr.main([]), 0)


if __name__ == "__main__":
    unittest.main()
