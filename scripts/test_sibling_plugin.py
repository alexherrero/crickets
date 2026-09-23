#!/usr/bin/env python3
"""Tests for sibling_plugin.py, the cross-plugin path resolver.

Claude Code installs each plugin at
`<plugins>/cache/<marketplace>/<plugin>/<version>/`, so a caller that reaches a
sibling as `${CLAUDE_PLUGIN_ROOT}/../<plugin>/...` names nothing once installed.
The flat `dist/` tree hides that: the same path resolves there. The documenter's
prose pass degraded on every dispatch through such a path (2026-09-10), and
design_doc.py could not import its plan resolver.

Three layers:
  - the resolver's rungs, against hand-built layouts
  - the copies every calling plugin ships are byte-identical
  - the gate: the emitted Claude Code payload is copied into a simulated
    versioned cache, and every sibling_plugin.py call site in it has to
    resolve there. A call site that does not resolve fails the build instead
    of degrading at runtime behind a marker nobody reads.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_DIST_CC = _ROOT / "dist" / "claude-code"
_CALLERS = ("design", "development-lifecycle", "maintenance", "wiki")

_SPEC = importlib.util.spec_from_file_location(
    "sibling_plugin", _ROOT / "src" / "wiki" / "scripts" / "sibling_plugin.py")
sp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sp)

# `sibling_plugin.py" <plugin> <rel>` in markdown; `resolve_sibling("<plugin>", "<rel>")` in Python.
_MD_CALL = re.compile(r"sibling_plugin\.py\"?\s+([a-z0-9][a-z0-9-]*)\s+([^\s\"'`)]+)")
_PY_CALL = re.compile(r"resolve_sibling\(\s*\"([a-z0-9][a-z0-9-]*)\"\s*,\s*\"([^\"]+)\"")


def _touch(path: Path, text: str = "# stub\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _installed(plugins_dir: Path, entries: dict) -> None:
    body = {"version": 2, "plugins": {
        key: [{"scope": "user", "installPath": str(p), "version": p.name}]
        for key, p in entries.items()}}
    _touch(plugins_dir / "installed_plugins.json", json.dumps(body))


def _call_sites(plugin_dir: Path) -> "set[tuple[str, str]]":
    sites: set[tuple[str, str]] = set()
    for f in plugin_dir.rglob("*.md"):
        sites.update(_MD_CALL.findall(f.read_text(encoding="utf-8")))
    for f in plugin_dir.rglob("*.py"):
        sites.update(_PY_CALL.findall(f.read_text(encoding="utf-8")))
    return sites


class ResolverRungs(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.cache = self.tmp / "plugins" / "cache" / "crickets"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_flat_layout_resolves_the_sibling(self) -> None:
        plugins = self.tmp / "plugins"
        want = _touch(plugins / "design" / "scripts" / "prose_pass.py")
        got = sp.resolve_sibling("design", "scripts/prose_pass.py", plugins / "wiki")
        self.assertEqual(got, want.resolve())

    def test_cache_takes_the_installed_version_over_the_newest(self) -> None:
        old = _touch(self.cache / "design" / "0.9.2" / "scripts" / "prose_pass.py")
        _touch(self.cache / "design" / "0.10.1" / "scripts" / "prose_pass.py")
        _installed(self.tmp / "plugins", {"design@crickets": old.parents[1]})
        got = sp.resolve_sibling("design", "scripts/prose_pass.py", self.cache / "wiki" / "0.11.2")
        self.assertEqual(got, old.resolve())

    def test_cache_without_a_record_takes_the_highest_version_not_the_last_by_name(self) -> None:
        _touch(self.cache / "design" / "0.9.2" / "scripts" / "prose_pass.py")
        new = _touch(self.cache / "design" / "0.10.1" / "scripts" / "prose_pass.py")
        got = sp.resolve_sibling("design", "scripts/prose_pass.py", self.cache / "wiki" / "0.11.2")
        self.assertEqual(got, new.resolve())

    def test_a_record_pointing_at_a_missing_file_falls_through_to_the_versions(self) -> None:
        new = _touch(self.cache / "design" / "0.10.1" / "scripts" / "prose_pass.py")
        _installed(self.tmp / "plugins", {"design@crickets": self.cache / "design" / "0.8.0"})
        got = sp.resolve_sibling("design", "scripts/prose_pass.py", self.cache / "wiki" / "0.11.2")
        self.assertEqual(got, new.resolve())

    def test_a_root_outside_a_cache_never_scans_version_directories(self) -> None:
        _touch(self.tmp / "design" / "1.0.0" / "scripts" / "prose_pass.py")
        got = sp.resolve_sibling("design", "scripts/prose_pass.py", self.tmp / "plugins" / "wiki")
        self.assertIsNone(got)

    def test_a_missing_plugin_resolves_to_none(self) -> None:
        _touch(self.cache / "design" / "0.10.1" / "scripts" / "prose_pass.py")
        self.assertIsNone(sp.resolve_sibling("design", "scripts/nope.py", self.cache / "wiki" / "0.11.2"))
        self.assertIsNone(sp.resolve_sibling("absent", "scripts/prose_pass.py", self.cache / "wiki" / "0.11.2"))


class ResolverCli(unittest.TestCase):
    """The CLI resolves from its own location, the way callers run it."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        cache = Path(self._tmp.name) / "plugins" / "cache" / "crickets"
        self.script = cache / "wiki" / "0.11.2" / "scripts" / "sibling_plugin.py"
        self.script.parent.mkdir(parents=True)
        shutil.copy(sp.__file__, self.script)
        self.target = _touch(cache / "design" / "0.10.1" / "scripts" / "prose_pass.py")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(self.script), *args],
                              capture_output=True, text=True, timeout=30)

    def test_found_prints_the_path_and_exits_0(self) -> None:
        res = self._run("design", "scripts/prose_pass.py")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(Path(res.stdout.strip()), self.target.resolve())

    def test_missing_exits_1_and_names_what_it_tried(self) -> None:
        res = self._run("design", "scripts/absent.py")
        self.assertEqual(res.returncode, 1)
        self.assertEqual(res.stdout, "")
        self.assertIn("design/scripts/absent.py is not installed; tried", res.stderr)

    def test_usage_errors_exit_2(self) -> None:
        for args in ((), ("design",), ("design", "../escape.py"), ("design", "/etc/hosts"),
                     ("design", "C:\\x.py"), ("design", "scripts\\..\\..\\x.py"), ("design", ""),
                     ("Design!", "scripts/prose_pass.py")):
            with self.subTest(args=args):
                self.assertEqual(self._run(*args).returncode, 2)


class CopiesStayIdentical(unittest.TestCase):
    def test_every_calling_plugin_ships_the_same_resolver(self) -> None:
        copies = {p.parent.parent.name: p.read_bytes()
                  for p in (_ROOT / "src").glob("*/scripts/sibling_plugin.py")}
        self.assertEqual(sorted(copies), sorted(_CALLERS))
        self.assertEqual(len(set(copies.values())), 1, "sibling_plugin.py copies have drifted")


class EmittedCallSitesResolveInTheVersionedCache(unittest.TestCase):
    """Rebuild Claude Code's cache from dist/ and resolve every call site in it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        marketplace = json.loads((_DIST_CC / ".claude-plugin" / "marketplace.json").read_text())["name"]
        plugins_dir = Path(cls._tmp.name) / "plugins"
        cls.roots: dict[str, Path] = {}
        for src in sorted((_DIST_CC / "plugins").iterdir()):
            manifest = json.loads((src / ".claude-plugin" / "plugin.json").read_text())
            root = plugins_dir / "cache" / marketplace / src.name / manifest["version"]
            shutil.copytree(src, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            cls.roots[src.name] = root
        _installed(plugins_dir, {f"{n}@{marketplace}": r for n, r in cls.roots.items()})

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_the_simulated_cache_reproduces_the_broken_sibling_path(self) -> None:
        # The layout this gate runs against has to be one where the old path fails.
        old = "../design/scripts/prose_pass.py"
        self.assertTrue((_DIST_CC / "plugins" / "wiki" / old).exists())
        self.assertFalse((self.roots["wiki"] / old).exists())

    def test_every_call_site_resolves_inside_its_target_plugin(self) -> None:
        checked = set()
        for caller, root in self.roots.items():
            for target, rel in sorted(_call_sites(root)):
                checked.add((caller, target, rel))
                with self.subTest(caller=caller, target=target, rel=rel):
                    res = subprocess.run(
                        [sys.executable, str(root / "scripts" / "sibling_plugin.py"), target, rel],
                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(res.returncode, 0, res.stderr)
                    got = Path(res.stdout.strip())
                    self.assertTrue(got.is_relative_to(self.roots[target].resolve()), got)
        # The call sites this fix exists for, so an extraction that matches
        # nothing cannot pass by checking nothing.
        for site in (("wiki", "design", "scripts/prose_pass.py"),
                     ("wiki", "design", "skills/prose-pass/SKILL.md"),
                     ("design", "development-lifecycle", "scripts/stage_plan.py"),
                     # design_doc.py's load of resolve_plan.py retired with
                     # agentm-vault part 15 (task 100): it asks agentm for the
                     # designs home through its own project_homes.py.
                     ("development-lifecycle", "github-projects", "scripts/project_sync.py"),
                     ("development-lifecycle", "diagnostics", "scripts/diagnose.py"),
                     ("maintenance", "development-lifecycle", "scripts/agentm_bridge.py")):
            self.assertIn(site, checked)

    def test_design_helpers_import_their_plan_resolver_from_the_cache(self) -> None:
        # design_doc.py loaded development-lifecycle's resolve_plan.py at import
        # time, and design_sequence.py imports design_doc; through the old
        # sibling path, /design translate and sequence both halted here. Since
        # task 100 it loads its own project_homes.py instead; both must still
        # import cleanly from the versioned cache.
        for script in ("design_doc.py", "design_sequence.py"):
            with self.subTest(script=script):
                res = subprocess.run(
                    [sys.executable, str(self.roots["design"] / "scripts" / script), "--help"],
                    capture_output=True, text=True, timeout=60)
                self.assertEqual(res.returncode, 0, res.stderr)


if __name__ == "__main__":
    unittest.main()
