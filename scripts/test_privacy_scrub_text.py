#!/usr/bin/env python3
"""Tests for src/privacy/scripts/scrub_text.py -- the arbitrary-text scrub
surface (PLAN-wave-d-tokens-and-privacy task 6).

Real-bridge tests (skipped without an agentm sibling checkout) prove
scrub_text() redacts the same PII categories the git-range scrubber
(check-no-pii.sh) catches -- email, personal path, API-key shape, US phone
number -- because both ultimately reuse agentm's privacy_scrub.scrub_pii
rules; scrub_text() never forks its own detection patterns. A hermetic unit
test covers the graceful-skip-when-unresolvable contract without needing a
real agentm checkout.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "privacy" / "scripts"

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


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


scrub_text_mod = _load("scrub_text_under_test", _SRC / "scrub_text.py")


class ScrubTextGracefulSkipTests(unittest.TestCase):
    """Hermetic: no real agentm checkout needed."""

    def test_returns_text_unchanged_when_agentm_unresolvable(self):
        empty_home = Path(__import__("tempfile").mkdtemp())
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}, clear=False):
            with mock.patch.object(Path, "home", return_value=empty_home):
                scrub_text_mod._reset_cache_for_tests()
                result = scrub_text_mod.scrub_text("contact alice@example.com")
                available = scrub_text_mod.scrub_text_available()
                scrub_text_mod._reset_cache_for_tests()
        self.assertEqual(result, "contact alice@example.com")
        self.assertFalse(available)

    def test_never_raises_on_empty_string(self):
        empty_home = Path(__import__("tempfile").mkdtemp())
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}, clear=False):
            with mock.patch.object(Path, "home", return_value=empty_home):
                scrub_text_mod._reset_cache_for_tests()
                result = scrub_text_mod.scrub_text("")
                scrub_text_mod._reset_cache_for_tests()
        self.assertEqual(result, "")


class ScrubTextRealBridgeTests(unittest.TestCase):
    """Real-bridge: proves the same detection categories check-no-pii.sh
    catches in git ranges are redacted identically via scrub_text()."""

    @classmethod
    def setUpClass(cls):
        cls._pre_existing_modules = set(sys.modules)
        scrub_text_mod._reset_cache_for_tests()
        if not scrub_text_mod.scrub_text_available():
            raise unittest.SkipTest("agentm sibling checkout unavailable -- real-bridge test skipped")

    @classmethod
    def tearDownClass(cls):
        scrub_text_mod._reset_cache_for_tests()
        _purge_real_bridge_sys_path()
        _purge_agentm_modules(cls._pre_existing_modules)

    def test_redacts_email(self):
        result = scrub_text_mod.scrub_text("contact alice@example.com for details")
        self.assertNotIn("alice@example.com", result)
        self.assertIn("[REDACTED-EMAIL]", result)

    def test_redacts_personal_path(self):
        # /Users/alexherrero/ -- allowlisted handle, not a real personal path.
        result = scrub_text_mod.scrub_text("log at /Users/alexherrero/secret/file.log")
        self.assertNotIn("/Users/alexherrero/", result)
        self.assertIn("[REDACTED-PATH]", result)

    def test_redacts_api_key_shape(self):
        key = "sk-" + "a" * 40
        result = scrub_text_mod.scrub_text(f"leaked key: {key}")
        self.assertNotIn(key, result)
        self.assertIn("[REDACTED-API-KEY]", result)

    def test_redacts_phone_number(self):
        # 555-0123 -- NANP reserved fictional prefix (RFC-analog convention
        # this codebase's own check-no-pii.sh allowlists), not a real number.
        result = scrub_text_mod.scrub_text("call me at 212-555-0123")
        self.assertNotIn("212-555-0123", result)
        self.assertIn("[REDACTED-PHONE]", result)

    def test_clean_text_passes_through_unchanged(self):
        clean = "the build failed with exit code 1"
        self.assertEqual(scrub_text_mod.scrub_text(clean), clean)

    def test_idempotent_on_already_scrubbed_text(self):
        once = scrub_text_mod.scrub_text("contact alice@example.com")
        twice = scrub_text_mod.scrub_text(once)
        self.assertEqual(once, twice)


if __name__ == "__main__":
    unittest.main()
