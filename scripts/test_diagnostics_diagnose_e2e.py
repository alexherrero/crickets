#!/usr/bin/env python3
"""End-to-end integration test for /diagnose (crickets wave-c-diagnostics, task 5).

Runs the full pipeline (classify -> recall -> rank -> write) against a small
seeded corpus of representative build/test/type/lint failures, not mocked --
the real bridge to agentm's recall/save engines. Asserts: the first run of
each failure writes a failure-incident; an identical repeat resolves via
Layer-1 (no new entry, no semantic search).

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
_SRC = _ROOT / "src" / "diagnostics" / "scripts"

# See test_diagnostics_writer.py's matching comment: agentm's save.py/
# recall.py mutate sys.path/sys.modules as a side effect of being loaded,
# which otherwise leaks into whatever test file runs next alphabetically.
# Cleaned up in tearDownClass -- both the sys.path cleanup and the
# sys.modules purge are filtered by path, not a blanket snapshot-restore
# (see test_diagnostics_writer.py for why a blanket restore/diff is unsafe
# for each). The sys.modules purge additionally excludes names already
# cached before this class's own real-bridge activity started (see
# test_diagnostics_writer.py's `cls._pre_existing_modules` comment for why --
# storage_seam/backend_selection class-identity, not just a stale cache).
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


diagnose_mod = _load("diagnostics_diagnose", _SRC / "diagnose.py")

_CORPUS = [
    {
        "expected_namespace": "build",
        "tool": "make",
        "traceback": (
            'Traceback (most recent call last):\n'
            '  File "/Users/alexherrero/proj/build.py", line 10, in run\n'
            '    raise RuntimeError("missing dependency: libfoo")\n'
            'RuntimeError: missing dependency: libfoo\n'
        ),
    },
    {
        "expected_namespace": "test",
        "tool": "pytest",
        "traceback": (
            'Traceback (most recent call last):\n'
            '  File "/Users/alexherrero/proj/tests/test_foo.py", line 22, in test_bar\n'
            '    assert x == y\n'
            'AssertionError: 1 != 2\n'
        ),
    },
    {
        "expected_namespace": "type",
        "tool": "mypy",
        "traceback": (
            'proj/module.py:15: error: Argument 1 to "foo" has incompatible '
            'type "int"; expected "str"\nFound 1 error in 1 file\n'
        ),
    },
    {
        "expected_namespace": "lint",
        "tool": None,
        "structured_output": {"rule_id": "no-unused-vars"},
        "traceback": (
            'proj/module.py:5:1: no-unused-vars: "x" is assigned a value '
            'but never used.\n'
        ),
    },
]


class DiagnoseEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Snapshot right before the first real-bridge call -- see
        # test_diagnostics_writer.py's matching setUpClass comment.
        cls._pre_existing_modules = set(sys.modules)
        # See test_diagnostics_writer.py: needs the real agentm sibling
        # checkout, absent in CI. Skip gracefully rather than error.
        if diagnose_mod.writer.agentm_bridge.load_save_module() is None:
            raise unittest.SkipTest("agentm sibling checkout unavailable -- real-bridge test skipped")

    @classmethod
    def tearDownClass(cls):
        _purge_real_bridge_sys_path()
        _purge_agentm_modules(cls._pre_existing_modules)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name) / "vault"
        self.vault.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_corpus_first_run_writes_second_run_is_layer1_hit(self):
        for case in _CORPUS:
            with self.subTest(namespace=case["expected_namespace"]):
                first = diagnose_mod.diagnose(
                    vault=self.vault,
                    project="crickets",
                    traceback_text=case["traceback"],
                    tool=case.get("tool"),
                    structured_output=case.get("structured_output"),
                )
                self.assertEqual(first["namespace"], case["expected_namespace"])
                self.assertEqual(first["outcome"], "written")
                self.assertTrue((self.vault / first["path"]).is_file())
                self.assertGreaterEqual(len(first["hypotheses"]), 1)
                self.assertLessEqual(len(first["hypotheses"]), 3)

                second = diagnose_mod.diagnose(
                    vault=self.vault,
                    project="crickets",
                    traceback_text=case["traceback"],
                    tool=case.get("tool"),
                    structured_output=case.get("structured_output"),
                )
                self.assertEqual(second["outcome"], "layer1_hit")
                self.assertEqual(second["path"], first["path"])
                self.assertEqual(second["fingerprint"], first["fingerprint"])


if __name__ == "__main__":
    unittest.main()
