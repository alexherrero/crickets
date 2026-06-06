#!/usr/bin/env python3
"""Tests for wiki_watch_config.py — config + wiki-target resolution
(src/wiki-maintenance/scripts/wiki_watch_config.py) — crickets ④ wiki-maintenance
part 4/5 (the wiki-watcher, W1), task 1.

Deterministic-only (DC-W8): the three PURE resolvers — host enablement reader,
per-repo run-config marker parse, and the repo->wiki-target resolver — plus the
graceful-skip behavior of the cross-repo registry locator. The shell-out to a live
agentm registry is NOT exercised (best-effort seam); we test that an absent locator
yields [] rather than a crash.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_WW_SCRIPTS = _ROOT / "src" / "wiki-maintenance" / "scripts"


def _load(name: str):
    if str(_WW_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_WW_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, _WW_SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


cfg = _load("wiki_watch_config")


# ----------------------------------------------------------------------------
# (a) Host enablement
# ----------------------------------------------------------------------------

class TestEnablement(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.prefix = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def _write_config(self, obj) -> None:
        (self.prefix / ".agentm-config.json").write_text(
            json.dumps(obj) if not isinstance(obj, str) else obj, encoding="utf-8")

    def test_nested_block_enabled(self):
        self._write_config({"wiki_watch": {"enabled": True}})
        self.assertTrue(cfg.read_enablement(self.prefix))

    def test_nested_block_disabled(self):
        self._write_config({"wiki_watch": {"enabled": False}})
        self.assertFalse(cfg.read_enablement(self.prefix))

    def test_top_level_alias_enabled(self):
        self._write_config({"wiki_watch_enabled": True})
        self.assertTrue(cfg.read_enablement(self.prefix))

    def test_nested_block_wins_over_alias(self):
        # nested block present (even if False) takes precedence over the alias.
        self._write_config({"wiki_watch": {"enabled": False}, "wiki_watch_enabled": True})
        self.assertFalse(cfg.read_enablement(self.prefix))

    def test_absent_file_is_disabled(self):
        # opt-in: no config => disabled.
        self.assertFalse(cfg.read_enablement(self.prefix))

    def test_absent_key_is_disabled(self):
        self._write_config({"vault_path": "/somewhere"})
        self.assertFalse(cfg.read_enablement(self.prefix))

    def test_malformed_json_is_disabled(self):
        self._write_config("{ not valid json ")
        self.assertFalse(cfg.read_enablement(self.prefix))

    def test_non_dict_json_is_disabled(self):
        self._write_config([1, 2, 3])
        self.assertFalse(cfg.read_enablement(self.prefix))


class TestVaultPathResolution(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.prefix = Path(self._td.name)
        self._vault = tempfile.TemporaryDirectory()
        self.vault = Path(self._vault.name)

    def tearDown(self):
        self._td.cleanup()
        self._vault.cleanup()

    def test_config_vault_path_resolved_when_dir_exists(self):
        (self.prefix / ".agentm-config.json").write_text(
            json.dumps({"vault_path": str(self.vault)}), encoding="utf-8")
        self.assertEqual(cfg.read_vault_path(self.prefix), str(self.vault))

    def test_config_vault_path_skipped_when_dir_missing(self):
        (self.prefix / ".agentm-config.json").write_text(
            json.dumps({"vault_path": str(self.vault / "nope")}), encoding="utf-8")
        self.assertIsNone(cfg.read_vault_path(self.prefix))

    def test_absent_config_yields_none(self):
        self.assertIsNone(cfg.read_vault_path(self.prefix))


# ----------------------------------------------------------------------------
# (b) Per-repo run config marker
# ----------------------------------------------------------------------------

class TestRunConfigMarker(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.repo = Path(self._td.name)
        (self.repo / ".harness").mkdir()

    def tearDown(self):
        self._td.cleanup()

    def _write_marker(self, obj) -> None:
        (self.repo / ".harness" / "wiki-watch.json").write_text(
            json.dumps(obj) if not isinstance(obj, str) else obj, encoding="utf-8")

    def test_absent_marker_returns_none(self):
        # marker presence is the per-repo opt-in; absent => skip.
        self.assertIsNone(cfg.read_run_config(self.repo))

    def test_empty_marker_returns_none(self):
        self._write_marker("   \n")
        self.assertIsNone(cfg.read_run_config(self.repo))

    def test_malformed_marker_returns_none(self):
        self._write_marker("{ oops ")
        self.assertIsNone(cfg.read_run_config(self.repo))

    def test_non_object_marker_returns_none(self):
        self._write_marker([1, 2])
        self.assertIsNone(cfg.read_run_config(self.repo))

    def test_minimal_marker_defaults(self):
        # present-but-empty object => default sources + pr mode (the safe default).
        self._write_marker({})
        rc = cfg.read_run_config(self.repo)
        self.assertIsNotNone(rc)
        self.assertEqual(rc.watch_sources, cfg.DEFAULT_WATCH_SOURCES)
        self.assertEqual(rc.dispatch_mode, "pr")
        self.assertFalse(rc.is_direct)

    def test_explicit_sources_and_direct_mode(self):
        self._write_marker({"watch_sources": ["PLAN.md", "designs/"], "dispatch_mode": "direct"})
        rc = cfg.read_run_config(self.repo)
        self.assertEqual(rc.watch_sources, ["PLAN.md", "designs/"])
        self.assertEqual(rc.dispatch_mode, "direct")
        self.assertTrue(rc.is_direct)

    def test_unknown_dispatch_mode_falls_back_to_pr(self):
        # DC-W1: direct is an explicit opt-in; anything unrecognized is PR-default.
        self._write_marker({"dispatch_mode": "banana"})
        self.assertEqual(cfg.read_run_config(self.repo).dispatch_mode, "pr")

    def test_dispatch_mode_case_insensitive(self):
        self._write_marker({"dispatch_mode": "DIRECT"})
        self.assertEqual(cfg.read_run_config(self.repo).dispatch_mode, "direct")

    def test_non_list_sources_falls_back_to_default(self):
        self._write_marker({"watch_sources": "PLAN.md"})
        self.assertEqual(cfg.read_run_config(self.repo).watch_sources, cfg.DEFAULT_WATCH_SOURCES)

    def test_empty_list_sources_falls_back_to_default(self):
        self._write_marker({"watch_sources": []})
        self.assertEqual(cfg.read_run_config(self.repo).watch_sources, cfg.DEFAULT_WATCH_SOURCES)

    def test_non_string_source_entries_dropped(self):
        self._write_marker({"watch_sources": ["PLAN.md", 42, "", "ROADMAP.md"]})
        self.assertEqual(cfg.read_run_config(self.repo).watch_sources, ["PLAN.md", "ROADMAP.md"])

    def test_read_is_non_mutating_no_vault_write(self):
        # DC-8: the reader writes no config (vault or otherwise). The marker file is
        # untouched and no sibling files appear.
        self._write_marker({"dispatch_mode": "pr"})
        before = sorted(p.name for p in (self.repo / ".harness").iterdir())
        cfg.read_run_config(self.repo)
        after = sorted(p.name for p in (self.repo / ".harness").iterdir())
        self.assertEqual(before, after)


# ----------------------------------------------------------------------------
# (c) Wiki-target resolver
# ----------------------------------------------------------------------------

class TestWikiTargetResolver(unittest.TestCase):
    def setUp(self):
        self.repos = [
            {"slug": "agentm", "root_path": "/srv/projects/agentm",
             "wiki_path": "/srv/projects/agentm/wiki"},
            {"slug": "nowiki", "root_path": "/srv/projects/nowiki"},
        ]

    def test_explicit_wiki_path(self):
        self.assertEqual(
            cfg.resolve_wiki_target_for_repo(self.repos, slug="agentm"),
            "/srv/projects/agentm/wiki")

    def test_match_by_root_path(self):
        self.assertEqual(
            cfg.resolve_wiki_target_for_repo(self.repos, root_path="/srv/projects/agentm"),
            "/srv/projects/agentm/wiki")

    def test_root_path_is_normalized(self):
        # trailing slash + redundant segments still match.
        self.assertEqual(
            cfg.resolve_wiki_target_for_repo(
                self.repos, root_path="/srv/projects/foo/../agentm/"),
            "/srv/projects/agentm/wiki")

    def test_unregistered_repo_skips(self):
        self.assertIsNone(cfg.resolve_wiki_target_for_repo(self.repos, slug="ghost"))
        self.assertIsNone(cfg.resolve_wiki_target_for_repo(
            self.repos, root_path="/srv/projects/ghost"))

    def test_absent_wiki_path_fallback_when_dir_exists(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "wiki").mkdir()
            repos = [{"slug": "x", "root_path": str(root)}]
            self.assertEqual(
                cfg.resolve_wiki_target_for_repo(repos, slug="x"),
                (root / "wiki").as_posix())

    def test_absent_wiki_path_skips_when_fallback_missing(self):
        with tempfile.TemporaryDirectory() as td:
            repos = [{"slug": "x", "root_path": str(Path(td))}]  # no wiki/ subdir
            self.assertIsNone(cfg.resolve_wiki_target_for_repo(repos, slug="x"))

    def test_absent_wiki_path_fallback_unchecked_is_pure(self):
        # With existence-check off, the fallback path is returned without a stat.
        self.assertEqual(
            cfg.resolve_wiki_target_for_repo(
                self.repos, slug="nowiki", check_fallback_exists=False),
            "/srv/projects/nowiki/wiki")

    def test_blank_wiki_path_treated_as_absent(self):
        repos = [{"slug": "x", "root_path": "/srv/x", "wiki_path": "  "}]
        self.assertEqual(
            cfg.resolve_wiki_target(repos[0], check_fallback_exists=False),
            "/srv/x/wiki")

    def test_root_path_precedence_over_slug(self):
        # When both are given, root_path wins the match.
        target = cfg.resolve_wiki_target_for_repo(
            self.repos, root_path="/srv/projects/agentm", slug="nowiki")
        self.assertEqual(target, "/srv/projects/agentm/wiki")


# ----------------------------------------------------------------------------
# Cross-repo registry locator — graceful-skip
# ----------------------------------------------------------------------------

class TestRegistryLocator(unittest.TestCase):
    def test_find_registry_script_none_without_env_or_colocated(self):
        # In the crickets dev tree nothing is co-located and the env is unset; the
        # locator must return None (=> caller graceful-skips), never raise.
        import os
        saved = os.environ.pop("AGENTM_SCRIPTS_DIR", None)
        try:
            self.assertIsNone(cfg.find_registry_script())
        finally:
            if saved is not None:
                os.environ["AGENTM_SCRIPTS_DIR"] = saved

    def test_find_registry_script_honors_env_override(self):
        import os
        with tempfile.TemporaryDirectory() as td:
            reg = Path(td) / "repo_registry.py"
            reg.write_text("# stub\n", encoding="utf-8")
            saved = os.environ.get("AGENTM_SCRIPTS_DIR")
            os.environ["AGENTM_SCRIPTS_DIR"] = td
            try:
                self.assertEqual(cfg.find_registry_script(), reg)
            finally:
                if saved is None:
                    os.environ.pop("AGENTM_SCRIPTS_DIR", None)
                else:
                    os.environ["AGENTM_SCRIPTS_DIR"] = saved

    def test_list_repos_empty_when_no_script_located(self):
        import os
        # Force the locator to find nothing: clear the env candidate (nothing is
        # co-located in the dev tree) => list returns [] (graceful), never raises.
        saved = os.environ.pop("AGENTM_SCRIPTS_DIR", None)
        try:
            self.assertEqual(cfg.list_repos_via_registry(registry_script=None), [])
        finally:
            if saved is not None:
                os.environ["AGENTM_SCRIPTS_DIR"] = saved

    def test_list_repos_empty_when_vault_unavailable(self):
        # A located script but no resolvable vault => [] before any shell-out.
        with tempfile.TemporaryDirectory() as td:
            reg = Path(td) / "repo_registry.py"
            reg.write_text("import sys; print('{}'); sys.exit(0)\n", encoding="utf-8")
            self.assertEqual(
                cfg.list_repos_via_registry(vault_path="", registry_script=reg), [])

    def test_list_repos_parses_stub_registry_output(self):
        # Happy path of the shell-out: a stub `repo_registry.py list` whose stdout is
        # the registry JSON => list_repos_via_registry returns its `repos`.
        stub = (
            "import sys, json\n"
            "if sys.argv[1:] == ['list']:\n"
            "    print(json.dumps({'repos': [{'slug': 'x', 'root_path': '/x',\n"
            "                                 'wiki_path': '/x/wiki'}]}))\n"
        )
        with tempfile.TemporaryDirectory() as td:
            reg = Path(td) / "repo_registry.py"
            reg.write_text(stub, encoding="utf-8")
            repos = cfg.list_repos_via_registry(vault_path=td, registry_script=reg)
            self.assertEqual(repos, [{"slug": "x", "root_path": "/x", "wiki_path": "/x/wiki"}])
            # …and the pure resolver composes over the shelled-out data end-to-end.
            self.assertEqual(
                cfg.resolve_wiki_target_for_repo(repos, slug="x"), "/x/wiki")

    def test_list_repos_empty_on_non_json_stub(self):
        with tempfile.TemporaryDirectory() as td:
            reg = Path(td) / "repo_registry.py"
            reg.write_text("print('not json at all')\n", encoding="utf-8")
            self.assertEqual(
                cfg.list_repos_via_registry(vault_path=td, registry_script=reg), [])


if __name__ == "__main__":
    unittest.main()
