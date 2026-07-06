#!/usr/bin/env python3
"""Tests for src/research/scripts/idea_search.py (crickets wave-c-research,
task 1).

Integration-style (not mocked): exercises the real bridge to agentm's
recall.py, so the ranking is proven end-to-end rather than merely assumed.
A second test proves idea-search is provably side-effect-free by snapshotting
the vault directory tree before/after the scan.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "research" / "scripts"

# See test_diagnostics_writer.py for the full rationale (this is the same
# idiom, narrowed to the recall-only bridge this plugin loads): agentm's
# recall.py inserts its own scripts dir onto sys.path (and bare-imports
# siblings into sys.modules) as a side effect of being loaded -- a real,
# process-global mutation that would otherwise leak into whatever test file
# runs next alphabetically. Purged in tearDownClass, filtered by path/name so
# an OTHER test file's own pre-existing agentm imports are left alone.
_AGENTM_PATH_MARKERS = ("/agentm/harness/", "/agentm/scripts/")
_REAL_BRIDGE_SYS_PATH_MARKER = "/agentm/harness/skills/memory/scripts"


def _purge_real_bridge_sys_path():
    sys.path[:] = [p for p in sys.path if _REAL_BRIDGE_SYS_PATH_MARKER not in p]


def _purge_agentm_modules(pre_existing_names):
    for name, mod in list(sys.modules.items()):
        if name in pre_existing_names:
            continue
        f = getattr(mod, "__file__", None)
        if f and any(marker in f for marker in _AGENTM_PATH_MARKERS):
            del sys.modules[name]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


idea_search = _load("research_idea_search", _SRC / "idea_search.py")


def _snapshot(vault: Path) -> set:
    return {p.relative_to(vault).as_posix() for p in vault.rglob("*")}


class IdeaSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Snapshot right before the first real-bridge call -- discovery has
        # already imported every test module by now, including ones that
        # cached their own agentm modules earlier and still need them.
        cls._pre_existing_modules = set(sys.modules)
        idea_search.agentm_bridge._reset_cache_for_tests()
        if idea_search.agentm_bridge.load_recall_module() is None:
            raise unittest.SkipTest("agentm sibling checkout unavailable -- real-bridge test skipped")

    @classmethod
    def tearDownClass(cls):
        _purge_real_bridge_sys_path()
        _purge_agentm_modules(cls._pre_existing_modules)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name) / "vault"
        (self.vault / "personal" / "reference").mkdir(parents=True)
        (self.vault / "personal" / "reference" / "relevant.md").write_text(
            "database migration rollback plan: snapshot before, verify after, "
            "rollback the migration if verification fails",
            encoding="utf-8",
        )
        # Shares exactly one query token ("plan") with the fixed test
        # question below, so it still surfaces in the ranked results
        # (recall.py drops zero-overlap entries entirely) but scores far
        # below relevant.md, which shares all four query tokens.
        (self.vault / "personal" / "reference" / "irrelevant.md").write_text(
            "sourdough bread recipe plan: feed the starter, fold the dough, "
            "proof overnight, bake at 450F",
            encoding="utf-8",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_relevant_entry_ranks_above_irrelevant_entry(self):
        results = idea_search.search(
            "database migration rollback plan", self.vault, k=10,
        )
        paths = [r["path"] for r in results]
        self.assertIn("personal/reference/relevant.md", paths)
        self.assertIn("personal/reference/irrelevant.md", paths)
        self.assertLess(
            paths.index("personal/reference/relevant.md"),
            paths.index("personal/reference/irrelevant.md"),
        )

    def test_search_makes_zero_writes_to_the_vault(self):
        before = _snapshot(self.vault)
        idea_search.search("database migration rollback plan", self.vault, k=10)
        after = _snapshot(self.vault)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
