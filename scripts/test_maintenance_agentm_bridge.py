#!/usr/bin/env python3
"""Tests for src/maintenance/scripts/agentm_bridge.py: which group its entries
file under, and how it calls agentm's save.py in a process that already holds
a same-named module of its own.

- Both writers file under agentm's default group, `memory`, never under
  `personal`, the memory space's name before stage 2.
- agentm's save_entry() imports `fingerprint` inside the call when the caller
  passes none, and the diagnostics plugin ships its own fingerprint.py. Each
  write must hand agentm agentm's module, then give the process back the one
  it already held.

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
_SRC = _HERE.parent / "src" / "maintenance" / "scripts"

# The sys.modules names a load or call can leave behind; each test puts back
# whatever the suite held under them.
_TOUCHED_MODULES = ("fingerprint", "maintenance_save_bridge")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


# Under a name of its own, so the bridge the other maintenance tests load keeps
# its sys.modules entry and its load cache.
agentm_bridge = _load("maintenance_agentm_bridge_under_test", _SRC / "agentm_bridge.py")

# agentm's save_entry() computes a fingerprint inside the call when the caller
# passes none; the stand-in hands back what it filed, and with which fingerprint.
_SAVE = textwrap.dedent(
    """\
    def save_entry(vault, kind, slug, body, *, group="memory", tags=(), fingerprint=None):
        if fingerprint is None:
            from fingerprint import compute_fingerprint
            fingerprint = compute_fingerprint(body)
        return {"kind": kind, "group": group, "fingerprint": fingerprint}
    """
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class SaveEntryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        agentm_dir = root / "agentm" / "harness" / "skills" / "memory" / "scripts"
        _write(agentm_dir / "save.py", _SAVE)
        _write(agentm_dir / "fingerprint.py", 'def compute_fingerprint(body):\n    return "agentm"\n')
        diagnostics_dir = root / "diagnostics" / "scripts"
        _write(diagnostics_dir / "fingerprint.py",
               'def compute_fingerprint(traceback_text):\n    return ("diagnostics", "v1")\n')

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
        self.diagnostics_module = _load("fingerprint", diagnostics_dir / "fingerprint.py")

    def test_a_debt_entry_files_under_memory_with_agentm_s_fingerprint(self):
        filed = agentm_bridge.write_debt_entry(Path("vault"), slug="s", body="b")

        self.assertEqual(filed, {"kind": "debt", "group": "memory", "fingerprint": "agentm"})
        self.assertIs(sys.modules["fingerprint"], self.diagnostics_module,
                      "the module cached before the call was not put back")

    def test_a_content_refresh_entry_files_under_memory_with_agentm_s_fingerprint(self):
        filed = agentm_bridge.write_content_refresh_watchlist_entry(Path("vault"), slug="s", body="b")

        self.assertEqual(filed, {"kind": "content-refresh-watchlist", "group": "memory", "fingerprint": "agentm"})
        self.assertIs(sys.modules["fingerprint"], self.diagnostics_module,
                      "the module cached before the call was not put back")


if __name__ == "__main__":
    unittest.main()
