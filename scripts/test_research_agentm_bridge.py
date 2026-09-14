#!/usr/bin/env python3
"""Tests for how src/research/scripts/agentm_bridge.py loads an agentm module
into a process that already holds a same-named module of its own.

agentm's memory scripts bare-import their siblings (`import vault_layout`),
and crickets ships modules under some of the same names: the wiki plugin's
vault_layout.py has a different API. In one process -- the unit suite is one --
the bridge must hand the agentm module agentm's sibling, then give the process
back the module it already held.

Hermetic: a stand-in agentm scripts dir in a temp directory, reached through
AGENTM_SCRIPTS_DIR, so these run without an agentm checkout, CI included. The
real-bridge tests in test_research_learn_forward.py skip there.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parent / "src" / "research" / "scripts"

# The sys.modules names a load can leave behind; each test puts back whatever
# the suite held under them.
_TOUCHED_MODULES = ("vault_layout", "research_forward_learning_bridge")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


# Under a name of its own: loading it as `research_agentm_bridge` would replace
# the entry learn_forward.py and idea_search.py registered.
agentm_bridge = _load("research_agentm_bridge_under_test", _SRC / "agentm_bridge.py")

# The shape of agentm's forward_learning.py header: put its own dir on
# sys.path, bare-import a sibling at module level, use it later.
_FORWARD_LEARNING = textwrap.dedent(
    """\
    import sys
    from pathlib import Path

    _HERE = Path(__file__).resolve().parent
    if str(_HERE) not in sys.path:
        sys.path.insert(0, str(_HERE))
    import vault_layout  # noqa: E402


    def layout_owner():
        return vault_layout.OWNER
    """
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class LoadModuleSiblingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        self.agentm_dir = root / "agentm" / "harness" / "skills" / "memory" / "scripts"
        _write(self.agentm_dir / "recall.py", "")  # the file the resolver looks for
        _write(self.agentm_dir / "forward_learning.py", _FORWARD_LEARNING)
        _write(self.agentm_dir / "vault_layout.py", 'OWNER = "agentm"\n')
        self.wiki_dir = root / "wiki" / "scripts"
        _write(self.wiki_dir / "vault_layout.py", 'OWNER = "wiki"\n')

        saved_path = list(sys.path)
        saved_modules = {n: sys.modules[n] for n in _TOUCHED_MODULES if n in sys.modules}

        def restore():
            sys.path[:] = saved_path
            for n in _TOUCHED_MODULES:
                sys.modules.pop(n, None)
            sys.modules.update(saved_modules)

        self.addCleanup(restore)
        env = mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(self.agentm_dir)})
        env.start()
        self.addCleanup(env.stop)
        agentm_bridge._reset_cache_for_tests()
        self.addCleanup(agentm_bridge._reset_cache_for_tests)

    def test_a_module_already_cached_under_the_name_does_not_reach_agentm(self):
        cached = _load("vault_layout", self.wiki_dir / "vault_layout.py")

        fl = agentm_bridge.load_forward_learning_module()

        self.assertEqual(fl.layout_owner(), "agentm")
        self.assertIs(sys.modules["vault_layout"], cached,
                      "the module cached before the load was not put back")

    def test_a_file_earlier_on_sys_path_under_the_name_does_not_reach_agentm(self):
        sys.modules.pop("vault_layout", None)
        sys.path[:0] = [str(self.wiki_dir), str(self.agentm_dir)]
        path_before = list(sys.path)

        fl = agentm_bridge.load_forward_learning_module()

        self.assertEqual(fl.layout_owner(), "agentm")
        self.assertEqual(sys.path, path_before, "the load left sys.path changed")

    def test_agentm_s_dir_stays_on_sys_path_for_the_imports_it_makes_later(self):
        agentm_bridge.load_forward_learning_module()

        self.assertIn(str(self.agentm_dir), sys.path)


if __name__ == "__main__":
    unittest.main()
