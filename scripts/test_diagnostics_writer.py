#!/usr/bin/env python3
"""Tests for src/diagnostics/scripts/writer.py -- the scrubbed failure-incident
writer (crickets wave-c-diagnostics, task 4).

Integration-style (not mocked): exercises the real bridge to agentm's
save_entry(), so the mandatory privacy scrub is proven end-to-end rather than
merely assumed. A third test proves the written entry round-trips through
task 2's Layer-1 recall path via its own fingerprint.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "diagnostics" / "scripts"

# agentm's save.py/recall.py insert their own scripts dir onto sys.path (and
# bare-import siblings like permeable_boundary/vault_lock into sys.modules) as
# a side effect of being loaded -- a real, process-global mutation that
# otherwise leaks into whatever test file runs next alphabetically (observed:
# test_diataxis_capture.py's own permeable_boundary-unavailable expectation
# broke once this file's real bridge calls had run first in the same
# process). Cleaned up in tearDownClass.
#
# Both the sys.modules purge AND the sys.path cleanup are filtered by path,
# not a blanket snapshot-restore -- a blanket restore also reverts sys.path
# entries some OTHER test module inserted at ITS OWN import time (module
# imports all happen during `discover`, before any test method runs), which
# that module then relies on later in a test method (observed:
# test_obsidian_vault_conformance.py inserts agentm's top-level scripts/ dir
# at module load so its setUpClass can `import storage_seam` -- a blanket
# `sys.path[:] = snapshot` here silently stripped that entry back out before
# that setUpClass ran, breaking it with ModuleNotFoundError). Same reasoning
# already applies to the sys.modules purge below (a blanket new-keys diff
# also deletes unrelated modules some OTHER test file happens to bare-import
# for the first time during this window -- observed: test_finalize_unit.py's
# own `import finalize_unit`, which broke a same-object monkeypatch once
# purged and re-imported fresh).
#
# The path-marker filter alone still isn't enough for `storage_seam` /
# `backend_selection`: test_obsidian_vault_conformance.py's own module-load
# code bare-imports those from agentm's top-level scripts/ dir (caching
# module objects `backend_selection` binds `registry`/`StorageBackend` to at
# ITS import time). If this file's purge deletes those sys.modules entries
# anyway, a later bare `import storage_seam` in that other file's setUpClass
# re-executes the module from disk into a SECOND, distinct module object --
# same file, different identity, so `issubclass(plugin_cls, StorageBackend)`
# there silently fails against the wrong `StorageBackend` class and
# `_load_vault_plugin_backend` returns None. So the purge additionally
# excludes any name already cached before this class's own real-bridge
# activity started (`cls._pre_existing_modules`, snapshotted in setUpClass)
# -- only names genuinely new since then are agentm-path-purged.
_AGENTM_PATH_MARKERS = ("/agentm/harness/", "/agentm/scripts/")
# Narrower than _AGENTM_PATH_MARKERS on purpose: this is the exact dir
# save.py/recall.py insert onto sys.path -- NOT agentm's top-level scripts/,
# which other test modules (e.g. test_obsidian_vault_conformance.py) insert
# themselves and still need.
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


writer = _load("diagnostics_writer", _SRC / "writer.py")
ladder = _load("diagnostics_recall_ladder_for_writer_test", _SRC / "recall_ladder.py")


class FailureIncidentWriterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Snapshot right before the first real-bridge call -- not at this
        # file's own import time -- since discovery has already imported
        # every test module by now, including ones that cached their own
        # agentm modules earlier and still need them (see the module-level
        # comment above).
        cls._pre_existing_modules = set(sys.modules)
        # Integration-style: needs the real agentm sibling checkout (a local
        # dev-machine convention, not present in CI, which has no sibling
        # repo). Skip gracefully rather than error -- matches the codebase's
        # own convention for an absent optional dependency (e.g. agentm's own
        # tests skip when sqlite-vec is unavailable).
        if writer.agentm_bridge.load_save_module() is None:
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

    def test_injected_secret_is_scrubbed_from_written_entry(self):
        target = writer.write_failure_incident(
            self.vault,
            project="crickets",
            fingerprint="fp-secret-test",
            namespace="runtime",
            symptom="ValueError raised; log line: key=sk-" + "a" * 40,
            hypotheses=["a config key leaked into the log line"],
        )
        content = target.read_text(encoding="utf-8")
        self.assertNotIn("sk-" + "a" * 40, content)
        self.assertIn("[REDACTED-API-KEY]", content)

    def test_written_entry_has_failure_incident_frontmatter_and_body(self):
        target = writer.write_failure_incident(
            self.vault,
            project="crickets",
            fingerprint="fp-frontmatter-test",
            namespace="test",
            symptom="assertion failed in test_foo",
            root_cause="off-by-one in the loop bound",
            fix_or_workaround="use range(n) not range(n+1)",
            hypotheses=["off-by-one", "stale fixture data"],
        )
        content = target.read_text(encoding="utf-8")
        self.assertIn("kind: failure-incident", content)
        self.assertIn("fingerprint: fp-frontmatter-test", content)
        self.assertIn("## Symptom", content)
        self.assertIn("assertion failed in test_foo", content)
        self.assertIn("## Root cause", content)
        self.assertIn("off-by-one in the loop bound", content)
        self.assertIn("## Fix / workaround", content)
        self.assertIn("## Hypotheses", content)
        self.assertIn("stale fixture data", content)

    def test_written_entry_round_trips_through_layer1_recall(self):
        writer.write_failure_incident(
            self.vault,
            project="crickets",
            fingerprint="fp-round-trip",
            namespace="build",
            symptom="build failed: missing dependency",
            hypotheses=["lockfile drift"],
        )
        result = ladder.recall(
            vault=self.vault,
            fingerprint="fp-round-trip",
            project="crickets",
            query_text="build failed: missing dependency",
            namespace="build",
        )
        self.assertEqual(result["layer"], 1)
        self.assertTrue(result["path"].endswith(".md"))

    def test_written_entry_includes_resolved_how_we_engineer_opinion(self):
        # Real-bridge: proves the incident body carries agentm's actual
        # opinions/how-we-engineer.md base text, resolved via
        # opinion_resolve() -- not a duplicated/inline copy (PLAN-wave-d-
        # opinion-wiring task 1).
        target = writer.write_failure_incident(
            self.vault,
            project="crickets",
            fingerprint="fp-opinion-test",
            namespace="test",
            symptom="assertion failed in test_bar",
            hypotheses=["stale fixture"],
        )
        content = target.read_text(encoding="utf-8")
        self.assertIn("## Opinion: how-we-engineer", content)
        self.assertIn("phase discipline", content)  # opinions/how-we-engineer.md's base body


class FailureIncidentOpinionWiringUnitTests(unittest.TestCase):
    """Hermetic: writer._build_body() calls opinion_resolve("how-we-engineer")
    via a planted fake opinion_resolver.py -- no real agentm sibling needed.
    Mirrors test_find_capability.py's fake-module-on-disk injection idiom."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _plant_fake_opinion_resolver(self, body: str) -> Path:
        scripts_dir = self.tmp / "fake_agentm_scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "opinion_resolver.py").write_text(
            "def opinion_resolve(name, *, root=None, supplement_dir=None):\n"
            "    return {\n"
            f"        'name': name, 'reason': 'base-only', 'base': {body!r},\n"
            "        'supplement': None, 'question': None, 'implements': None,\n"
            "        'composes': [],\n"
            "    }\n",
            encoding="utf-8",
        )
        return scripts_dir

    def test_build_body_folds_in_resolved_opinion_text(self):
        scripts_dir = self._plant_fake_opinion_resolver("Fake how-we-engineer body.")
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(scripts_dir)}):
            writer.agentm_bridge._reset_cache_for_tests()
            body = writer._build_body(
                symptom="s", root_cause=None, fix_or_workaround=None,
                outcome=None, hypotheses=None,
            )
        self.assertIn("Fake how-we-engineer body.", body)
        self.assertIn("## Opinion: how-we-engineer", body)
        writer.agentm_bridge._reset_cache_for_tests()

    def test_write_failure_incident_calls_privacy_scrub_text_explicitly(self):
        # PLAN-wave-d-tokens-and-privacy task 6: writer.py must call privacy's
        # scrub_text() explicitly at the crickets call site -- not rely
        # solely on save_entry()'s own implicit kind-gated scrub one layer
        # down. Spy on the loaded bridge module to prove THIS call fires,
        # independent of whether agentm's own internal gate also fires.
        calls = []

        class _FakeScrubTextModule:
            @staticmethod
            def scrub_text(text):
                calls.append(text)
                return text.replace("SENTINEL-SECRET", "[REDACTED-SENTINEL]")

        tmp = tempfile.TemporaryDirectory()
        try:
            vault = Path(tmp.name) / "vault"
            vault.mkdir()
            if writer.agentm_bridge.load_save_module() is None:
                self.skipTest("agentm sibling checkout unavailable")
            with mock.patch.object(writer, "_privacy_scrub_text", _FakeScrubTextModule):
                target = writer.write_failure_incident(
                    vault, project="crickets", fingerprint="fp-explicit-scrub-test",
                    namespace="test", symptom="leaked SENTINEL-SECRET in log",
                    hypotheses=["test"],
                )
            self.assertTrue(calls, "scrub_text() was never called explicitly by writer.py")
            content = target.read_text(encoding="utf-8")
            self.assertIn("[REDACTED-SENTINEL]", content)
            self.assertNotIn("SENTINEL-SECRET", content)
        finally:
            tmp.cleanup()

    def test_build_body_degrades_gracefully_when_resolver_absent(self):
        empty_home = self.tmp / "empty_home"
        empty_home.mkdir()
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}, clear=False):
            with mock.patch.object(Path, "home", return_value=empty_home):
                writer.agentm_bridge._reset_cache_for_tests()
                body = writer._build_body(
                    symptom="s", root_cause=None, fix_or_workaround=None,
                    outcome=None, hypotheses=None,
                )
                writer.agentm_bridge._reset_cache_for_tests()
        # No opinion section when agentm is unresolvable -- graceful-skip,
        # never raises, never blocks the incident write.
        self.assertNotIn("## Opinion: how-we-engineer", body)
        self.assertIn("## Symptom", body)


if __name__ == "__main__":
    unittest.main()
