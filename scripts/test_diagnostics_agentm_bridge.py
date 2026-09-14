#!/usr/bin/env python3
"""Tests for how src/diagnostics/scripts/agentm_bridge.py calls agentm's
modules in a process that already holds a same-named module of its own.

agentm's scripts bare-import their siblings, inside functions as well as at
module level, and crickets ships modules under some of the same names (the
wiki plugin's vault_layout.py). Each of the bridge's calls -- query_semantic,
write_failure_incident, opinion_resolve -- must hand agentm agentm's sibling,
then give the process back the module it already held.

Hermetic: a stand-in agentm scripts dir in a temp directory, reached through
AGENTM_SCRIPTS_DIR, so these run without an agentm checkout, CI included.

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
_SRC = _HERE.parent / "src" / "diagnostics" / "scripts"

# The sys.modules names a load or call can leave behind; each test puts back
# whatever the suite held under them.
_TOUCHED_MODULES = ("vault_layout", "agentm_recall_bridge", "agentm_save_bridge", "agentm_opinion_bridge")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


# Under a name of its own, so the bridge the other diagnostics tests load keeps
# its sys.modules entry and its load cache.
agentm_bridge = _load("diagnostics_agentm_bridge_under_test", _SRC / "agentm_bridge.py")

# Each stand-in imports its sibling inside the function, as agentm's
# recall.query (through lifecycle) and save.save_entry do.
_STAND_INS = {
    "recall.py": """\
        def query(vault, query_text, filter_expr=None, k=5):
            import vault_layout
            return [vault_layout.OWNER]
        """,
    "save.py": """\
        def save_entry(vault, kind, slug, body, *, group="memory", tags=(), fingerprint=None):
            import vault_layout
            return vault_layout.OWNER
        """,
    "opinion_resolver.py": """\
        def opinion_resolve(name):
            import vault_layout
            return {"name": name, "owner": vault_layout.OWNER}
        """,
    "vault_layout.py": 'OWNER = "agentm"\n',
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class AgentmSiblingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        agentm_dir = root / "agentm" / "harness" / "skills" / "memory" / "scripts"
        for filename, text in _STAND_INS.items():
            _write(agentm_dir / filename, textwrap.dedent(text))
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
        env = mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(agentm_dir)})
        env.start()
        self.addCleanup(env.stop)
        agentm_bridge._reset_cache_for_tests()
        self.addCleanup(agentm_bridge._reset_cache_for_tests)
        self.wiki_module = _load("vault_layout", wiki_dir / "vault_layout.py")

    def assert_wiki_module_is_back(self):
        self.assertIs(sys.modules["vault_layout"], self.wiki_module,
                      "the module cached before the call was not put back")

    def test_query_semantic_hands_agentm_its_own_sibling(self):
        owners = agentm_bridge.query_semantic(Path("vault"), "q", filter_expr="kind:failure-incident")

        self.assertEqual(owners, ["agentm"])
        self.assert_wiki_module_is_back()

    def test_write_failure_incident_hands_agentm_its_own_sibling(self):
        owner = agentm_bridge.write_failure_incident(
            Path("vault"), slug="s", body="b", project="p", fingerprint="f", tags=[])

        self.assertEqual(owner, "agentm")
        self.assert_wiki_module_is_back()

    def test_opinion_resolve_hands_agentm_its_own_sibling(self):
        resolved = agentm_bridge.opinion_resolve("how-we-engineer")

        self.assertEqual(resolved["owner"], "agentm")
        self.assert_wiki_module_is_back()


if __name__ == "__main__":
    unittest.main()
