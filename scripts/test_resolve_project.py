#!/usr/bin/env python3
"""Tests for src/development-lifecycle/scripts/resolve_project.py — the LOCATE
+ CONFIRM engine for `/open` / `/orient` (PLAN-open-a-project-by-name task 2).

Three sources, each independently graceful-skip: repo-registry (via
agentm_bridge.py's `repo-registry` verb), the vault `projects/` tree (via a
file-path-loaded `harness_memory.py`), and agentm recall (via a file-path-loaded
`recall.py`, mirroring src/research/scripts/agentm_bridge.py's pattern). Every
test is hermetic — stub scripts/modules, tempdirs, and injected env overrides —
no dependency on a real agentm install (CI runs with none).
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "development-lifecycle" / "scripts" / "resolve_project.py"


def _load():
    spec = importlib.util.spec_from_file_location("resolve_project", _SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["resolve_project"] = m
    spec.loader.exec_module(m)
    return m


rp = _load()


class TestListRegisteredRepos(unittest.TestCase):
    """Source (a): repo-registry, via agentm_bridge.py."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-repo-registry-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _stub_bridge(self, body: str) -> Path:
        p = self.tmp / "agentm_bridge.py"
        p.write_text(body, encoding="utf-8")
        return p

    def test_absent_bridge_returns_empty(self):
        self.assertEqual(rp.list_registered_repos(bridge=self.tmp / "nope.py"), [])

    def test_success_returns_repos(self):
        bridge = self._stub_bridge(
            "import sys, json\n"
            "print(json.dumps({'repos': [{'slug': 'widgets', 'root_path': '/tmp/w'}]}))\n"
            "sys.exit(0)\n"
        )
        repos = rp.list_registered_repos(bridge=bridge)
        self.assertEqual(repos, [{"slug": "widgets", "root_path": "/tmp/w"}])

    def test_nonzero_exit_returns_empty(self):
        bridge = self._stub_bridge("import sys\nsys.exit(1)\n")
        self.assertEqual(rp.list_registered_repos(bridge=bridge), [])

    def test_unparsable_json_returns_empty(self):
        bridge = self._stub_bridge("print('not json')\n")
        self.assertEqual(rp.list_registered_repos(bridge=bridge), [])


class TestScanVaultProjects(unittest.TestCase):
    """Source (b): the vault projects/ tree."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-vault-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_vault_returns_empty(self):
        with mock.patch.object(rp, "resolve_vault_path", return_value=None):
            self.assertEqual(rp.scan_vault_projects(vault=None), [])

    def test_no_projects_dir_returns_empty(self):
        vault = self.tmp / "vault"
        vault.mkdir()
        self.assertEqual(rp.scan_vault_projects(vault=vault), [])

    def test_lists_project_dirs_with_gloss(self):
        vault = self.tmp / "vault"
        proj = vault / "projects" / "widgets" / "_harness"
        proj.mkdir(parents=True)
        (proj / "PLAN.md").write_text("**Brief:** The widgets project.\n", encoding="utf-8")
        (vault / "projects" / ".hidden").mkdir(parents=True)
        result = rp.scan_vault_projects(vault=vault)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["slug"], "widgets")
        self.assertEqual(result[0]["gloss"], "The widgets project.")

    def test_project_with_no_gloss_source_omits_gloss(self):
        vault = self.tmp / "vault"
        (vault / "projects" / "bare").mkdir(parents=True)
        result = rp.scan_vault_projects(vault=vault)
        self.assertEqual(result, [{"slug": "bare", "vault_project_path": str(vault / "projects" / "bare"), "gloss": None}])

    # ── filing-v2 2b: the vault-root Projects/ generation ────────────────────
    # The memory root is `<vault>/Agent`; the newest project space is its
    # SIBLING `<vault>/Projects/`. During the merge window both exist.

    def test_window_unions_root_shell_with_desk_projects(self):
        """Root Projects/ exists but near-empty (index.md only) while every
        project still sits under desk/projects: first-space-only would return
        nothing. The union lists them all."""
        vault = self.tmp / "Vault" / "Agent"
        (self.tmp / "Vault" / ".obsidian").mkdir(parents=True, exist_ok=True)
        (self.tmp / "Vault" / "Projects").mkdir(parents=True)
        (self.tmp / "Vault" / "Projects" / "index.md").write_text("# Projects\n", encoding="utf-8")
        (vault / "desk" / "projects" / "agentm" / "_harness").mkdir(parents=True)
        (vault / "desk" / "projects" / "crickets").mkdir(parents=True)
        slugs = [r["slug"] for r in rp.scan_vault_projects(vault=vault)]
        self.assertEqual(slugs, ["agentm", "crickets"])

    def test_moved_project_resolves_from_root_and_wins_the_slug(self):
        """After the move a slug lives at root Projects/; a stale copy left
        under desk/projects must not shadow it — newest layout wins."""
        vault = self.tmp / "Vault" / "Agent"
        (self.tmp / "Vault" / ".obsidian").mkdir(parents=True, exist_ok=True)
        root = self.tmp / "Vault" / "Projects" / "agentm" / "_harness"
        root.mkdir(parents=True)
        (root / "PLAN.md").write_text("**Brief:** moved.\n", encoding="utf-8")
        stale = vault / "desk" / "projects" / "agentm" / "_harness"
        stale.mkdir(parents=True)
        (stale / "PLAN.md").write_text("**Brief:** stale.\n", encoding="utf-8")
        (vault / "desk" / "projects" / "other").mkdir(parents=True)
        result = {r["slug"]: r for r in rp.scan_vault_projects(vault=vault)}
        self.assertEqual(sorted(result), ["agentm", "other"])
        self.assertEqual(result["agentm"]["gloss"], "moved.")
        self.assertEqual(Path(result["agentm"]["vault_project_path"]).resolve(),
                         (self.tmp / "Vault" / "Projects" / "agentm").resolve())

    def test_relpath_parse_accepts_root_relative_projects_paths(self):
        """Daemon hits arrive vault-root-relative: `Projects/<slug>/...`."""
        self.assertEqual(rp._project_slug_from_vault_relpath("Projects/agentm/_harness/PLAN.md"), "agentm")
        self.assertEqual(rp._project_slug_from_vault_relpath("desk/projects/agentm/x.md"), "agentm")
        self.assertIsNone(rp._project_slug_from_vault_relpath("memory/semantic/note.md"))

    def test_extract_gloss_from_objective_heading(self):
        text = "# Design\n\n## Objective\n\nDoes the widget thing.\n"
        self.assertEqual(rp._extract_gloss(text), "Does the widget thing.")

    def test_extract_gloss_none_when_absent(self):
        self.assertIsNone(rp._extract_gloss("# Design\n\nJust prose, no markers.\n"))


class TestRecallCandidates(unittest.TestCase):
    """Source (c): agentm recall, mirrors research's agentm_bridge.py pattern."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-recall-"))
        rp._reset_cache_for_tests()

    def tearDown(self):
        rp._reset_cache_for_tests()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_empty_query_returns_empty_without_touching_recall(self):
        with mock.patch.object(rp, "resolve_vault_path", side_effect=AssertionError("should not be called")):
            self.assertEqual(rp._recall_project_candidates(""), [])

    def test_no_vault_returns_empty(self):
        with mock.patch.object(rp, "resolve_vault_path", return_value=None):
            self.assertEqual(rp._recall_project_candidates("widgets"), [])

    def test_recall_module_absent_returns_empty(self):
        vault = self.tmp / "vault"
        vault.mkdir()
        with mock.patch.object(rp, "resolve_vault_path", return_value=vault):
            with mock.patch.object(rp, "load_recall_module", return_value=None):
                self.assertEqual(rp._recall_project_candidates("widgets"), [])

    def test_hits_under_projects_slug_surface_as_candidates(self):
        vault = self.tmp / "vault"
        vault.mkdir()

        class _FakeRecall:
            @staticmethod
            def query(*, vault, query_text, k=5):
                return [
                    {"path": "projects/widgets/notes.md", "combined": 0.9},
                    {"path": "personal/unrelated.md", "combined": 0.5},
                ]

        with mock.patch.object(rp, "resolve_vault_path", return_value=vault):
            with mock.patch.object(rp, "load_recall_module", return_value=_FakeRecall):
                result = rp._recall_project_candidates("widgets")
        self.assertEqual(result, [{"slug": "widgets", "recall_score": 0.9}])

    def test_query_recall_swallows_exceptions(self):
        class _RaisingRecall:
            @staticmethod
            def query(**kwargs):
                raise RuntimeError("boom")

        with mock.patch.object(rp, "load_recall_module", return_value=_RaisingRecall):
            self.assertEqual(rp.query_recall(self.tmp, "x"), [])


class TestMergeAndClassify(unittest.TestCase):
    """resolve() merges the three sources, dedupes by slug, classifies 0/1/many."""

    def setUp(self):
        rp._reset_cache_for_tests()

    def tearDown(self):
        rp._reset_cache_for_tests()

    def _stub_all_sources(self, *, repos=(), vault_projects=(), recall=()):
        return (
            mock.patch.object(rp, "list_registered_repos", return_value=list(repos)),
            mock.patch.object(rp, "scan_vault_projects", return_value=list(vault_projects)),
            mock.patch.object(rp, "_recall_project_candidates", return_value=list(recall)),
        )

    def test_no_agentm_at_all_returns_none_classification(self):
        with mock.patch.object(rp, "list_registered_repos", return_value=[]), \
             mock.patch.object(rp, "scan_vault_projects", return_value=[]), \
             mock.patch.object(rp, "_recall_project_candidates", return_value=[]):
            result = rp.resolve("anything")
        self.assertEqual(result, {"matches": [], "classification": "none"})

    def test_single_source_single_match_classifies_one(self):
        with mock.patch.object(rp, "list_registered_repos", return_value=[{"slug": "widgets", "root_path": "/tmp/w"}]), \
             mock.patch.object(rp, "scan_vault_projects", return_value=[]), \
             mock.patch.object(rp, "_recall_project_candidates", return_value=[]):
            result = rp.resolve("widgets")
        self.assertEqual(result["classification"], "one")
        self.assertEqual(result["matches"][0]["slug"], "widgets")

    def test_dedup_across_sources_by_normalized_slug(self):
        with mock.patch.object(rp, "list_registered_repos", return_value=[{"slug": "Widgets", "root_path": "/tmp/w"}]), \
             mock.patch.object(rp, "scan_vault_projects", return_value=[{"slug": "widgets", "vault_project_path": "/vault/projects/widgets", "gloss": "The widgets thing."}]), \
             mock.patch.object(rp, "_recall_project_candidates", return_value=[{"slug": "WIDGETS", "recall_score": 0.7}]):
            result = rp.resolve("widgets")
        self.assertEqual(result["classification"], "one")
        m = result["matches"][0]
        self.assertEqual(m["root_path"], "/tmp/w")
        self.assertEqual(m["gloss"], "The widgets thing.")
        self.assertEqual(m["recall_score"], 0.7)

    def test_many_matches_for_a_broad_query(self):
        with mock.patch.object(rp, "list_registered_repos", return_value=[{"slug": "widgets"}, {"slug": "widget-tools"}]), \
             mock.patch.object(rp, "scan_vault_projects", return_value=[]), \
             mock.patch.object(rp, "_recall_project_candidates", return_value=[]):
            result = rp.resolve("widget")
        self.assertEqual(result["classification"], "many")
        self.assertEqual({m["slug"] for m in result["matches"]}, {"widgets", "widget-tools"})

    def test_query_filters_out_non_matching_candidates(self):
        with mock.patch.object(rp, "list_registered_repos", return_value=[{"slug": "widgets"}, {"slug": "gizmos"}]), \
             mock.patch.object(rp, "scan_vault_projects", return_value=[]), \
             mock.patch.object(rp, "_recall_project_candidates", return_value=[]):
            result = rp.resolve("gizmos")
        self.assertEqual(result["classification"], "one")
        self.assertEqual(result["matches"][0]["slug"], "gizmos")

    def test_empty_query_matches_everything(self):
        with mock.patch.object(rp, "list_registered_repos", return_value=[{"slug": "widgets"}, {"slug": "gizmos"}]), \
             mock.patch.object(rp, "scan_vault_projects", return_value=[]), \
             mock.patch.object(rp, "_recall_project_candidates", return_value=[]):
            result = rp.resolve("")
        self.assertEqual(result["classification"], "many")


class TestCLI(unittest.TestCase):
    def test_main_json_output(self):
        with mock.patch.object(rp, "list_registered_repos", return_value=[{"slug": "widgets"}]), \
             mock.patch.object(rp, "scan_vault_projects", return_value=[]), \
             mock.patch.object(rp, "_recall_project_candidates", return_value=[]):
            code = rp.main(["resolve_project.py", "widgets", "--json"])
        self.assertEqual(code, 0)



class TestRootSpaceWitness(unittest.TestCase):
    """The `..` rung counts only when the memory root is nested inside an
    Obsidian vault (`.obsidian/` at the parent, none at the memory root). A
    flat vault's parent is the operator's home, where `Projects/` is common
    — never probed. The flat generation `<memory-root>/Projects` needs no
    witness (agentm 2b review, defect 1)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-witness-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_flat_vault_never_probes_the_operators_projects_dir(self):
        home = self.tmp / "home"
        vault = home / "Vault"
        (vault / ".obsidian").mkdir(parents=True)
        (vault / "desk" / "projects" / "mine").mkdir(parents=True)
        (home / "Projects" / "agentm" / "_harness").mkdir(parents=True)  # the operator's own repos
        self.assertFalse(rp.root_sibling_witnessed(vault))
        self.assertEqual(rp.vault_projects_dirs(vault), [vault / "desk" / "projects"])
        self.assertEqual([r["slug"] for r in rp.scan_vault_projects(vault=vault)], ["mine"])

    def test_a_flat_vaults_own_projects_dir_is_the_root_space(self):
        vault = self.tmp / "Vault"
        (vault / ".obsidian").mkdir(parents=True)
        (vault / "Projects" / "agentm" / "_harness").mkdir(parents=True)
        self.assertEqual(rp.vault_projects_dirs(vault), [vault / "Projects"])
        result = rp.scan_vault_projects(vault=vault)
        self.assertEqual([r["slug"] for r in result], ["agentm"])
        self.assertEqual(Path(result[0]["vault_project_path"]).resolve(), (vault / "Projects" / "agentm").resolve())

    def test_the_flat_rung_matches_the_directorys_exact_case(self):
        """A V4-era `projects/` rung is not the flat root space, whatever the
        filesystem's case rules say."""
        vault = self.tmp / "Vault"
        (vault / ".obsidian").mkdir(parents=True)
        (vault / "projects" / "legacy").mkdir(parents=True)
        self.assertFalse(rp.flat_root_space_present(vault))
        self.assertEqual(rp.vault_projects_dirs(vault), [vault / "projects"])

    def test_a_nested_root_without_the_witness_is_not_a_sibling(self):
        vault = self.tmp / "Vault" / "Agent"
        (vault / "desk" / "projects" / "p").mkdir(parents=True)
        (self.tmp / "Vault" / "Projects" / "q").mkdir(parents=True)  # no .obsidian anywhere
        self.assertEqual(rp.vault_projects_dirs(vault), [vault / "desk" / "projects"])
        self.assertEqual([r["slug"] for r in rp.scan_vault_projects(vault=vault)], ["p"])

if __name__ == "__main__":
    unittest.main()
