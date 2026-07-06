#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/find_capability.py.

`_find_capability_resolver` discovery: $AGENTM_SCRIPTS_DIR override, co-located
sibling, conventional ~/Antigravity/agentm clone (the R0.5 fix — mirrors
find_process_seam.py's third tier), and None when all tiers are absent.

Every test is hermetic — injectable env var overrides and a mocked Path.home()
ensure no dependency on a real agentm install (CI runs with none).
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "development-lifecycle" / "scripts" / "find_capability.py"


def _load():
    spec = importlib.util.spec_from_file_location("find_capability", _SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["find_capability"] = m
    spec.loader.exec_module(m)
    return m


fc = _load()


def _make_fake_resolver(path: Path, body: str = "") -> Path:
    """Plant a fake capability_resolver.py at path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body or "# stub resolver\n", encoding="utf-8")
    return path


class TestFindCapabilityResolverDiscovery(unittest.TestCase):
    """_find_capability_resolver() locates capability_resolver.py via fallback order."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fc-discovery-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_found_via_env_agentm_scripts_dir(self):
        resolver = _make_fake_resolver(self.tmp / "env_scripts" / "capability_resolver.py")
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(resolver.parent)}):
            result = fc._find_capability_resolver()
        self.assertEqual(result, resolver.resolve())

    def test_found_via_colocated_sibling(self):
        colocated = _make_fake_resolver(_SRC.parent / "capability_resolver.py")
        try:
            env_without = {k: v for k, v in os.environ.items()
                           if k != "AGENTM_SCRIPTS_DIR"}
            with mock.patch.dict(os.environ, env_without, clear=True):
                result = fc._find_capability_resolver()
            self.assertIsNotNone(result)
            self.assertTrue(result.is_file())
        finally:
            colocated.unlink(missing_ok=True)

    def test_found_via_conventional_antigravity_clone(self):
        home = self.tmp / "fake_home"
        resolver = _make_fake_resolver(
            home / "Antigravity" / "agentm" / "scripts" / "capability_resolver.py"
        )
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}, clear=False):
            with mock.patch.object(Path, "home", return_value=home):
                result = fc._find_capability_resolver()
        self.assertEqual(result, resolver.resolve())

    def test_returns_none_when_all_absent(self):
        home = self.tmp / "empty_home"
        home.mkdir()
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}, clear=False):
            with mock.patch.object(Path, "home", return_value=home):
                result = fc._find_capability_resolver()
        self.assertIsNone(result)


if __name__ == "__main__":
    # R2.1 — dashboard visibility for cricketsPluginsA#0 (the already-fixed
    # find_capability fallback-chain gap). Plain `python3 -m unittest
    # discover` (check-all.sh's own invocation) never reaches this block;
    # `--jsonl-out <path>` only matters when this file is run directly, e.g.
    # from scripts/health/run-crickets-fast-tier.sh.
    sys.path.insert(0, str(_HERE / "health"))
    import jsonl_emit as _je  # noqa: E402
    sys.exit(_je.run_module_as_health_check(
        sys.modules[__name__], sys.argv,
        suite="test_find_capability", check="cricketsPluginsA#0: find_capability fallback chain",
    ))
