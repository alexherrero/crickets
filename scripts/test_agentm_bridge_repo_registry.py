#!/usr/bin/env python3
"""Tests for the `repo-registry` verb of
src/development-lifecycle/scripts/agentm_bridge.py (PLAN-open-a-project-by-name
task 1 — the fifth verb added to the merged CONS-2 dispatcher, per that design's
own 2026-07-10 amendment-log re-audit trigger: a fifth agentm-facing lookup
extends this dispatcher rather than starting a new bridge file).

`find_repo_registry` discovery mirrors the other four verbs' 3-tier cascade
($AGENTM_SCRIPTS_DIR override / co-located sibling / conventional
~/Antigravity/agentm clone). `run_repo_registry_list` proxies repo_registry.py's
own `list` subcommand stdout + exit code verbatim (0 + `{"repos": [...]}`, or 1
+ repo_registry.py's own skip envelope on an unavailable backend) rather than
re-wrapping that contract.

Every test is hermetic — a planted stub `repo_registry.py`, injectable env var
overrides, and a mocked Path.home() ensure no dependency on a real agentm
install (CI runs with none).
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
_SRC = _ROOT / "src" / "development-lifecycle" / "scripts" / "agentm_bridge.py"


def _load():
    spec = importlib.util.spec_from_file_location("agentm_bridge_repo_registry", _SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["agentm_bridge_repo_registry"] = m
    spec.loader.exec_module(m)
    return m


ab = _load()


def _make_stub_registry(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


_STUB_LIST_OK = """#!/usr/bin/env python3
import sys, json
if sys.argv[1:] == ["list"]:
    print(json.dumps({"repos": [{"slug": "widgets", "root_path": "/tmp/widgets"}]}))
    sys.exit(0)
sys.exit(2)
"""

_STUB_SKIPPED = """#!/usr/bin/env python3
import sys, json
if sys.argv[1:] == ["list"]:
    print(json.dumps({"skipped": True, "reason": "no backend"}))
    sys.exit(1)
sys.exit(2)
"""


class TestFindRepoRegistryDiscovery(unittest.TestCase):
    """find_repo_registry() locates repo_registry.py via the 3-tier fallback."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="repo-registry-discovery-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_found_via_env_agentm_scripts_dir(self):
        registry = _make_stub_registry(self.tmp / "env_scripts" / "repo_registry.py", _STUB_LIST_OK)
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(registry.parent)}):
            result = ab.find_repo_registry()
        self.assertEqual(result, registry.resolve())

    def test_found_via_conventional_clone(self):
        clone_scripts = self.tmp / "Antigravity" / "agentm" / "scripts"
        registry = _make_stub_registry(clone_scripts / "repo_registry.py", _STUB_LIST_OK)
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}, clear=False):
            os.environ.pop("AGENTM_SCRIPTS_DIR", None)
            with mock.patch.object(ab.Path, "home", return_value=self.tmp):
                result = ab.find_repo_registry()
        self.assertEqual(result, registry.resolve())

    def test_absent_returns_none(self):
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}, clear=False):
            os.environ.pop("AGENTM_SCRIPTS_DIR", None)
            with mock.patch.object(ab.Path, "home", return_value=self.tmp):
                result = ab.find_repo_registry()
        self.assertIsNone(result)


class TestRunRepoRegistryList(unittest.TestCase):
    """run_repo_registry_list() proxies repo_registry.py's `list` verbatim."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="repo-registry-run-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_success_passes_through_stdout_and_exit_0(self):
        registry = _make_stub_registry(self.tmp / "repo_registry.py", _STUB_LIST_OK)
        out, code = ab.run_repo_registry_list(registry=registry)
        self.assertEqual(code, 0)
        self.assertIn('"widgets"', out)

    def test_backend_skip_passes_through_exit_1_and_envelope(self):
        registry = _make_stub_registry(self.tmp / "repo_registry.py", _STUB_SKIPPED)
        out, code = ab.run_repo_registry_list(registry=registry)
        self.assertEqual(code, 1)
        self.assertIn('"skipped": true', out.lower())

    def test_registry_none_graceful_skips(self):
        # registry=None triggers a real find_repo_registry() lookup; force absence.
        with mock.patch.object(ab, "find_repo_registry", return_value=None):
            out, code = ab.run_repo_registry_list(registry=None)
        self.assertEqual((out, code), ("", 1))

    def test_missing_file_graceful_skips(self):
        out, code = ab.run_repo_registry_list(registry=self.tmp / "nope.py")
        self.assertEqual((out, code), ("", 1))


class TestMainRepoRegistryDispatch(unittest.TestCase):
    """The `repo-registry` verb is wired into the top-level dispatcher."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="repo-registry-dispatch-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_verb_registered_in_dispatcher(self):
        self.assertIn("repo-registry", ab._VERBS)

    def test_no_subcommand_is_usage_error(self):
        self.assertEqual(ab._main_repo_registry([]), 2)

    def test_unknown_subcommand_is_usage_error(self):
        self.assertEqual(ab._main_repo_registry(["delete"]), 2)

    def test_list_dispatches_through_main(self):
        registry = _make_stub_registry(self.tmp / "repo_registry.py", _STUB_LIST_OK)
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(registry.parent)}):
            code = ab.main(["agentm_bridge.py", "repo-registry", "list"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
