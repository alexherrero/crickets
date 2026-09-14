#!/usr/bin/env python3
"""Tests for scripts/agentm_isolation.py: a real-bridge test class keeps the
suite's same-named modules away from agentm's imports for its whole life,
including the imports agentm makes inside functions after the load.

Hermetic: a stand-in agentm scripts dir and a stand-in wiki dir in a temp
directory, so these run without an agentm checkout, CI included.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import agentm_isolation

# The stand-in agentm has the shape of the real failure: recall imports
# lifecycle inside a function, and lifecycle imports vault_layout at module
# level. Only vault_layout shares its name with a crickets module.
_RECALL = textwrap.dedent(
    """\
    def lifecycle_layout_owner():
        import isolation_standin_lifecycle
        return isolation_standin_lifecycle.layout_owner()
    """
)
_LIFECYCLE = textwrap.dedent(
    """\
    import vault_layout


    def layout_owner():
        return vault_layout.OWNER
    """
)
_TOUCHED_MODULES = ("vault_layout", "isolation_standin_lifecycle", "isolation_standin_recall")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


class IsolateAgentmImportsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        self.agentm_dir = root / "agentm" / "scripts"
        _write(self.agentm_dir / "isolation_standin_recall.py", _RECALL)
        _write(self.agentm_dir / "isolation_standin_lifecycle.py", _LIFECYCLE)
        _write(self.agentm_dir / "vault_layout.py", 'OWNER = "agentm"\n')
        wiki_dir = root / "wiki" / "scripts"
        _write(wiki_dir / "vault_layout.py", 'OWNER = "wiki"\n')

        saved_path = list(sys.path)
        saved_modules = {n: sys.modules[n] for n in _TOUCHED_MODULES if n in sys.modules}

        def restore():
            sys.path[:] = saved_path
            for n in _TOUCHED_MODULES:
                sys.modules.pop(n, None)
            sys.modules.update(saved_modules)

        self.addCleanup(restore)

        # The state discovery leaves the suite in: the wiki's module cached
        # under the shared name, and the wiki's dir ahead of agentm's.
        sys.path[:0] = [str(wiki_dir), str(self.agentm_dir)]
        self.wiki_layout = _load("vault_layout", wiki_dir / "vault_layout.py")

        class RealBridgeTests(unittest.TestCase):
            pass

        self.test_class = RealBridgeTests
        self.addCleanup(RealBridgeTests.doClassCleanups)

    def _load_recall(self):
        return _load("isolation_standin_recall", self.agentm_dir / "isolation_standin_recall.py")

    def test_without_it_a_lazy_import_gets_the_suite_s_module(self):
        # The failure the helper exists for: agentm's module loads fine, and a
        # function it calls later is handed the wiki's module.
        self.assertEqual(self._load_recall().lifecycle_layout_owner(), "wiki")

    def test_a_lazy_import_inside_the_class_gets_agentm_s_sibling(self):
        agentm_isolation.isolate_agentm_imports(self.test_class, self.agentm_dir)

        self.assertEqual(self._load_recall().lifecycle_layout_owner(), "agentm")

    def test_the_class_cleanup_gives_back_the_suite_s_module_and_sys_path(self):
        path_before = list(sys.path)
        agentm_isolation.isolate_agentm_imports(self.test_class, self.agentm_dir)
        self.assertNotIn("vault_layout", sys.modules)
        self.assertEqual(sys.path[0], str(self.agentm_dir))
        self._load_recall().lifecycle_layout_owner()

        self.test_class.doClassCleanups()

        self.assertIs(sys.modules["vault_layout"], self.wiki_layout)
        self.assertEqual(sys.path, path_before)

    def test_a_module_loaded_from_agentm_s_own_dir_stays(self):
        own = _load("vault_layout", self.agentm_dir / "vault_layout.py")

        agentm_isolation.isolate_agentm_imports(self.test_class, self.agentm_dir)

        self.assertIs(sys.modules["vault_layout"], own)

    def test_without_an_agentm_checkout_it_changes_nothing(self):
        path_before = list(sys.path)

        agentm_isolation.isolate_agentm_imports(self.test_class, None)
        self.test_class.doClassCleanups()

        self.assertIs(sys.modules["vault_layout"], self.wiki_layout)
        self.assertEqual(sys.path, path_before)


if __name__ == "__main__":
    unittest.main()
