#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/resolve_plan.py (multi-plan writers T2).

The bridge has two backends with one contract: **delegate** to agentm's
process seam (`state-path plan`, `progress` and `tracker`) when discoverable,
else a standalone `.harness/` **fallback**. Every test is hermetic — the
delegate branch is exercised with a planted *stub* seam and the fallback via
`seam=None`, so nothing here depends on a real agentm clone (CI runs with none).
"""
from __future__ import annotations

import importlib.util
import io
import contextlib
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
_SRC = _ROOT / "src" / "development-lifecycle" / "scripts" / "resolve_plan.py"


def _load():
    spec = importlib.util.spec_from_file_location("resolve_plan", _SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["resolve_plan"] = m
    spec.loader.exec_module(m)
    return m


rp = _load()


def _write_stub(path: Path, body: str) -> Path:
    """A throwaway seam stub that stands in for agentm's process_seam.py."""
    path.write_text(body, encoding="utf-8")
    return path


# A seam stub for one vault project in both layouts. It answers
# `state-path {plan|progress|tracker} [--plan NAME] --cwd ROOT` the way agentm's
# seam does: no --plan is the singleton, `042-build-the-brief` is a numbered
# task, and any other name is a flat pair. $STUB_SEAM_BARE_EXIT makes a bare
# call exit with that code instead (agentm-vault plan 10's answer on a project
# that keeps tasks), and $STUB_SEAM_NO_TRACKER makes `tracker` an invalid
# choice, as it is for a seam from before the tracker.
_LAYOUT_SEAM = r'''
import os, sys
argv = sys.argv[1:]
which = argv[1]
name = argv[argv.index("--plan") + 1] if "--plan" in argv else None
project = "/v/projects/probe"
if which == "tracker" and os.environ.get("STUB_SEAM_NO_TRACKER"):
    sys.stderr.write("process_seam state-path: error: invalid choice: 'tracker'\n")
    sys.exit(2)
if name is None and os.environ.get("STUB_SEAM_BARE_EXIT"):
    sys.stderr.write("[process_seam] this project keeps tasks\n")
    sys.exit(int(os.environ["STUB_SEAM_BARE_EXIT"]))
if name is None:
    files = {"plan": "PLAN.md", "progress": "progress.md", "tracker": "tracker.md"}
    print(f"{project}/_harness/{files[which]}")
elif name == "042-build-the-brief":
    files = {"plan": "plan.md", "progress": "progress.md", "tracker": "tracker.md"}
    print(f"{project}/tasks/{name}/{files[which]}")
else:
    files = {"plan": f"PLAN-{name}.md", "progress": f"progress-{name}.md",
             "tracker": f"tracker-{name}.md"}
    print(f"{project}/_harness/{files[which]}")
sys.exit(0)
'''


class TestNameMapping(unittest.TestCase):
    """The filename contract the fallback shares with the agentm verb."""

    def test_normalize_singleton_forms(self):
        for form in ("", "   ", "PLAN", "PLAN.md"):
            self.assertEqual(rp._normalize_plan_name(form), "")

    def test_normalize_named_forms(self):
        for form in ("foo", "PLAN-foo", "PLAN-foo.md"):
            self.assertEqual(rp._normalize_plan_name(form), "foo")

    def test_plan_pair(self):
        self.assertEqual(rp._plan_pair(""), ("PLAN.md", "progress.md"))
        self.assertEqual(rp._plan_pair("foo"), ("PLAN-foo.md", "progress-foo.md"))

    def test_safe_slug(self):
        for ok in ("foo", "foo-bar", "foo.bar", "v2"):
            self.assertTrue(rp._is_safe_plan_slug(ok), ok)
        for bad in ("", ".", "..", "../etc", "a/b", "a\\b"):
            self.assertFalse(rp._is_safe_plan_slug(bad), bad)


class TestFallback(unittest.TestCase):
    """No seam (`seam=None`) → plain `.harness/` resolution."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-fallback-"))
        # Isolate from the real machine's own agentm config (R2.5 task 12's new
        # guard): these tests exercise the bare fallback, not the vault-mismatch
        # guard, so force vault_check() False regardless of what this machine's
        # ~/.claude/.agentm-config.json actually says.
        self._saved_vault_check = rp._vault_configured_and_reachable
        rp._vault_configured_and_reachable = lambda **_k: False

    def tearDown(self):
        rp._vault_configured_and_reachable = self._saved_vault_check
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _pair(self, *names: str) -> str:
        base = self.tmp / ".harness"
        return "\t".join(str(base / n) for n in names)

    def test_a_bare_is_byte_identical_singleton(self):
        # The load-bearing invariant: bare resolves to the unchanged singleton pair.
        rc, out, err = rp.resolve("", str(self.tmp), seam=None)
        self.assertEqual(rc, 0)
        self.assertEqual(err, "")
        self.assertEqual(out.strip(), self._pair("PLAN.md", "progress.md"))

    def test_b_named_pair(self):
        rc, out, _ = rp.resolve("foo", str(self.tmp), seam=None)
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), self._pair("PLAN-foo.md", "progress-foo.md"))

    def test_b_named_accepts_filename_form(self):
        rc, out, _ = rp.resolve("PLAN-foo.md", str(self.tmp), seam=None)
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), self._pair("PLAN-foo.md", "progress-foo.md"))

    def test_c_unsafe_slug_rejected_no_path(self):
        rc, out, err = rp.resolve("../etc", str(self.tmp), seam=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertNotIn(".harness", out)
        self.assertIn("unsafe plan name", err)

    def test_d_the_fallback_names_no_tracker(self):
        # Only agentm names a tracker, so the standalone line's third field is empty.
        rc, out, err = rp.resolve("foo", str(self.tmp), seam=None)
        self.assertEqual((rc, err), (0, ""))
        base = self.tmp / ".harness"
        self.assertEqual(out, f"{base / 'PLAN-foo.md'}\t{base / 'progress-foo.md'}\t\n")


class TestDelegation(unittest.TestCase):
    """A located seam is authoritative — its paths and exit code pass through.

    Stubs stand in for process_seam.py: they receive
    `state-path {plan|progress|tracker} [--plan SLUG] [--cwd ROOT]` and return
    one absolute path per call (or an error exit code). resolve_plan.py makes
    three calls and assembles the tab-separated line.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-delegate-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_d_returns_stub_pair_unchanged(self):
        # Stub returns one path per kind; resolve_plan reassembles the line.
        stub = _write_stub(
            self.tmp / "stub_ok.py",
            "import sys\n"
            "which = sys.argv[2]\n"
            "paths = {'plan': '/v/PLAN-foo.md', 'progress': '/v/progress-foo.md',"
            " 'tracker': '/v/tracker-foo.md'}\n"
            "sys.stdout.write(paths[which] + '\\n')\n"
            "sys.exit(0)\n",
        )
        rc, out, err = rp.resolve("foo", str(self.tmp), seam=stub)
        self.assertEqual(rc, 0)
        self.assertEqual(err, "")
        self.assertEqual(out, "/v/PLAN-foo.md\t/v/progress-foo.md\t/v/tracker-foo.md\n")

    def test_d_passes_plan_and_cwd_through(self):
        # Bridge forwards --plan and --cwd to each seam call.
        stub = _write_stub(
            self.tmp / "stub_echo.py",
            "import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\nsys.exit(0)\n",
        )
        rc, out, _ = rp.resolve("bar", "/proj/root", seam=stub)
        self.assertEqual(rc, 0)
        self.assertIn("state-path", out)
        self.assertIn("--plan", out)
        self.assertIn("bar", out)
        self.assertIn("--cwd", out)
        self.assertIn("/proj/root", out)

    def test_d_bare_omits_plan_flag(self):
        stub = _write_stub(
            self.tmp / "stub_echo2.py",
            "import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\nsys.exit(0)\n",
        )
        rc, out, _ = rp.resolve("", str(self.tmp), seam=stub)
        self.assertEqual(rc, 0)
        self.assertNotIn("--plan", out)

    def test_e_dangling_exit_propagates_no_singleton_fallback(self):
        # Risk #7 across the second hop: a seam that ran and refused must NOT
        # degrade to the singleton — its non-zero exit surfaces and no pair emitted.
        stub = _write_stub(
            self.tmp / "stub_dangling.py",
            "import sys\n"
            "sys.stderr.write('[process_seam] dangling .harness/active-plan marker\\n')\n"
            "sys.exit(2)\n",
        )
        rc, out, err = rp.resolve("", str(self.tmp), seam=stub)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertNotIn("PLAN.md", out)   # never the singleton
        self.assertNotEqual(err, "")       # error is surfaced

    def test_e_graceful_skip_exit_one_propagates(self):
        # rc 1 (seam present, no resolvable _harness/) also passes through — the
        # fallback is for *absent seam*, never for a seam that returned a signal.
        stub = _write_stub(
            self.tmp / "stub_skip.py",
            "import sys\nsys.exit(1)\n",
        )
        rc, out, _ = rp.resolve("", str(self.tmp), seam=stub)
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")


class TestVaultReachabilityGuard(unittest.TestCase):
    """R2.5 task 12: refuse the repo-side `.harness/` fallback when agentm's own
    config independently confirms a vault-backed memory layer is configured and
    reachable — the guard against the four-repeat "plan state landed on the
    wrong .harness/ tier" bug. Locked design call: default to refuse, not
    warn-and-proceed.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-vaultguard-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mismatch_refuses_no_path_emitted(self):
        # Seam absent (would fall back) + vault_check() True (a vault-backed
        # layer really is configured and reachable) → refuse, exit 2, no path.
        rc, out, err = rp.resolve("", str(self.tmp), seam=None, vault_check=lambda: True)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("refusing repo-side .harness/ fallback", err)
        self.assertNotIn(str(self.tmp), out)

    def test_no_mismatch_proceeds_exactly_as_before(self):
        # Seam absent + vault_check() False (genuinely no vault configured, or
        # configured-but-unreachable) → the ordinary fallback, unchanged.
        rc, out, err = rp.resolve("", str(self.tmp), seam=None, vault_check=lambda: False)
        self.assertEqual(rc, 0)
        self.assertEqual(err, "")
        base = self.tmp / ".harness"
        self.assertEqual(out.strip(), f"{base / 'PLAN.md'}\t{base / 'progress.md'}")

    def test_seam_present_never_consults_vault_check(self):
        # A located seam is authoritative and delegates outright — the guard
        # only fires on the fallback path. A vault_check that would refuse must
        # never even be consulted when a seam is present.
        stub = _write_stub(
            self.tmp / "stub_ok.py",
            "import sys\n"
            "which = sys.argv[2]\n"
            "paths = {'plan': '/v/PLAN.md', 'progress': '/v/progress.md', 'tracker': '/v/tracker.md'}\n"
            "sys.stdout.write(paths[which] + '\\n')\n"
            "sys.exit(0)\n",
        )
        called = []
        rc, out, err = rp.resolve(
            "", str(self.tmp), seam=stub,
            vault_check=lambda: called.append(1) or True,
        )
        self.assertEqual(rc, 0)
        self.assertEqual(out, "/v/PLAN.md\t/v/progress.md\t/v/tracker.md\n")
        self.assertEqual(called, [])


class TestVaultConfiguredAndReachableProbe(unittest.TestCase):
    """Direct coverage of `_vault_configured_and_reachable`'s own resolution —
    the evidence source the guard above consults."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-vaultprobe-"))
        self._saved_env = {
            k: os.environ.get(k)
            for k in ("MEMORY_ROOT", "MEMORY_VAULT_PATH", "AGENTM_INSTALL_PREFIX")
        }
        os.environ.pop("MEMORY_ROOT", None)
        os.environ.pop("MEMORY_VAULT_PATH", None)
        os.environ.pop("AGENTM_INSTALL_PREFIX", None)

    def tearDown(self):
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_config(self, prefix: Path, data: dict) -> None:
        prefix.mkdir(parents=True, exist_ok=True)
        (prefix / ".agentm-config.json").write_text(json.dumps(data), encoding="utf-8")

    def test_env_override_existing_dir_true(self):
        vault_dir = self.tmp / "envvault"
        vault_dir.mkdir()
        os.environ["MEMORY_ROOT"] = str(vault_dir)
        self.assertTrue(rp._vault_configured_and_reachable())

    def test_env_override_nonexistent_dir_false(self):
        os.environ["MEMORY_ROOT"] = str(self.tmp / "does-not-exist")
        self.assertFalse(rp._vault_configured_and_reachable())

    def test_deprecated_alias_still_read_when_memory_root_unset(self):
        # MEMORY_VAULT_PATH is the name agentm exported before 2026-09-11 and
        # keeps as an alias for one release; alone, it still counts as reachable.
        vault_dir = self.tmp / "aliasvault"
        vault_dir.mkdir()
        os.environ["MEMORY_VAULT_PATH"] = str(vault_dir)
        self.assertTrue(rp._vault_configured_and_reachable())

    def test_memory_root_wins_over_the_alias(self):
        # MEMORY_ROOT names a missing dir while the alias names a real one:
        # the probe answers for MEMORY_ROOT, so it is False.
        vault_dir = self.tmp / "aliasvault"
        vault_dir.mkdir()
        os.environ["MEMORY_ROOT"] = str(self.tmp / "does-not-exist")
        os.environ["MEMORY_VAULT_PATH"] = str(vault_dir)
        self.assertFalse(rp._vault_configured_and_reachable())
        # Empty MEMORY_ROOT (CI's isolation value) falls through to the alias.
        os.environ["MEMORY_ROOT"] = ""
        self.assertTrue(rp._vault_configured_and_reachable())

    def test_no_config_file_false(self):
        empty_prefix = self.tmp / "no-config-here"
        empty_prefix.mkdir()
        self.assertFalse(rp._vault_configured_and_reachable(install_prefix=empty_prefix))

    def test_config_vault_backend_reachable_true(self):
        prefix = self.tmp / "prefix-ok"
        vault_dir = self.tmp / "realvault"
        vault_dir.mkdir()
        self._write_config(prefix, {
            "storage.backend": "vault",
            "plugins.obsidian-vault.vault_path": str(vault_dir),
        })
        self.assertTrue(rp._vault_configured_and_reachable(install_prefix=prefix))

    def test_config_vault_backend_but_path_missing_false(self):
        # Configured but NOT reachable — both facts are required, not just one.
        prefix = self.tmp / "prefix-unreachable"
        self._write_config(prefix, {
            "storage.backend": "vault",
            "plugins.obsidian-vault.vault_path": str(self.tmp / "gone"),
        })
        self.assertFalse(rp._vault_configured_and_reachable(install_prefix=prefix))

    def test_config_legacy_vault_path_key_fallback(self):
        # Mirrors harness_memory.vault_path()'s own legacy flat-key fallback.
        prefix = self.tmp / "prefix-legacy"
        vault_dir = self.tmp / "legacyvault"
        vault_dir.mkdir()
        self._write_config(prefix, {
            "storage.backend": "vault",
            "vault_path": str(vault_dir),
        })
        self.assertTrue(rp._vault_configured_and_reachable(install_prefix=prefix))

    def test_config_non_vault_backend_false(self):
        prefix = self.tmp / "prefix-devicelocal"
        vault_dir = self.tmp / "irrelevant"
        vault_dir.mkdir()
        self._write_config(prefix, {
            "storage.backend": "device-local",
            "plugins.obsidian-vault.vault_path": str(vault_dir),
        })
        self.assertFalse(rp._vault_configured_and_reachable(install_prefix=prefix))

    def test_corrupt_config_false(self):
        prefix = self.tmp / "prefix-corrupt"
        prefix.mkdir()
        (prefix / ".agentm-config.json").write_text("not json {{{", encoding="utf-8")
        self.assertFalse(rp._vault_configured_and_reachable(install_prefix=prefix))


class TestMainCLI(unittest.TestCase):
    """End-to-end main() over the fallback backend (delegate is unit-tested above)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-main-"))
        # Force the fallback deterministically regardless of the real machine's
        # agentm install by stubbing out find_seam on the loaded bridge.
        self._saved = rp._bridge.find_seam
        rp._bridge.find_seam = lambda: None
        # Also isolate the R2.5 task 12 vault-mismatch guard — main() has no CLI
        # flag to inject vault_check, so patch the module default the same way.
        self._saved_vault_check = rp._vault_configured_and_reachable
        rp._vault_configured_and_reachable = lambda **_k: False

    def tearDown(self):
        rp._bridge.find_seam = self._saved
        rp._vault_configured_and_reachable = self._saved_vault_check
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = rp.main(["resolve_plan.py", *argv])
        return rc, out.getvalue(), err.getvalue()

    def test_main_bare_singleton(self):
        rc, out, _ = self._run("--project-root", str(self.tmp))
        self.assertEqual(rc, 0)
        base = self.tmp / ".harness"
        self.assertEqual(out.strip(), f"{base / 'PLAN.md'}\t{base / 'progress.md'}")

    def test_main_named(self):
        rc, out, _ = self._run("foo", "--project-root", str(self.tmp))
        self.assertEqual(rc, 0)
        base = self.tmp / ".harness"
        self.assertEqual(out.strip(), f"{base / 'PLAN-foo.md'}\t{base / 'progress-foo.md'}")

    def test_main_unsafe_nonzero(self):
        rc, out, err = self._run("../etc", "--project-root", str(self.tmp))
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("unsafe plan name", err)

    def test_main_prints_three_fields_the_last_empty_without_agentm(self):
        rc, out, _ = self._run("foo", "--project-root", str(self.tmp))
        self.assertEqual(rc, 0)
        base = self.tmp / ".harness"
        self.assertEqual(out.rstrip("\n").split("\t"),
                         [str(base / "PLAN-foo.md"), str(base / "progress-foo.md"), ""])

    def test_main_passes_exit_4_on_with_nothing_on_stdout(self):
        seam = _write_stub(self.tmp / "seam.py", _LAYOUT_SEAM)
        rp._bridge.find_seam = lambda: seam
        with mock.patch.dict(os.environ, {"STUB_SEAM_BARE_EXIT": "4"}):
            rc, out, err = self._run("--project-root", str(self.tmp))
        self.assertEqual((rc, out), (4, ""))
        self.assertIn("name the task", err)


class TestLayouts(unittest.TestCase):
    """The line in each layout agentm resolves (the singleton, a flat named
    pair, a numbered task), and the two answers that aren't a whole line."""

    _PROJECT = "/v/projects/probe"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-layouts-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.seam = _write_stub(self.tmp / "seam.py", _LAYOUT_SEAM)
        patcher = mock.patch.dict(os.environ, {"STUB_SEAM_BARE_EXIT": "",
                                               "STUB_SEAM_NO_TRACKER": ""})
        patcher.start()
        self.addCleanup(patcher.stop)

    def resolve(self, name: str) -> tuple[int, str, str]:
        return rp.resolve(name, str(self.tmp), seam=self.seam)

    def test_the_singleton(self):
        h = f"{self._PROJECT}/_harness"
        self.assertEqual(self.resolve(""),
                         (0, f"{h}/PLAN.md\t{h}/progress.md\t{h}/tracker.md\n", ""))

    def test_a_flat_named_pair(self):
        h = f"{self._PROJECT}/_harness"
        self.assertEqual(self.resolve("foo"),
                         (0, f"{h}/PLAN-foo.md\t{h}/progress-foo.md\t{h}/tracker-foo.md\n", ""))

    def test_a_numbered_task(self):
        t = f"{self._PROJECT}/tasks/042-build-the-brief"
        self.assertEqual(self.resolve("042-build-the-brief"),
                         (0, f"{t}/plan.md\t{t}/progress.md\t{t}/tracker.md\n", ""))

    def test_a_seam_from_before_the_tracker_leaves_the_field_empty(self):
        h = f"{self._PROJECT}/_harness"
        with mock.patch.dict(os.environ, {"STUB_SEAM_NO_TRACKER": "1"}):
            rc, out, err = self.resolve("foo")
        self.assertEqual(rc, 0)
        self.assertEqual(out, f"{h}/PLAN-foo.md\t{h}/progress-foo.md\t\n")
        self.assertIn("tracker field is empty", err)

    def test_a_bare_call_on_a_project_that_keeps_tasks_is_exit_4(self):
        with mock.patch.dict(os.environ, {"STUB_SEAM_BARE_EXIT": "4"}):
            rc, out, err = self.resolve("")
        self.assertEqual((rc, out), (4, ""))
        self.assertIn("name the task", err)
        self.assertEqual(rp.NAME_THE_TASK, 4)

    def test_a_named_call_on_that_project_still_resolves(self):
        t = f"{self._PROJECT}/tasks/042-build-the-brief"
        with mock.patch.dict(os.environ, {"STUB_SEAM_BARE_EXIT": "4"}):
            rc, out, _err = self.resolve("042-build-the-brief")
        self.assertEqual((rc, out), (0, f"{t}/plan.md\t{t}/progress.md\t{t}/tracker.md\n"))

    def test_field_one_is_still_the_plan_for_python_callers(self):
        # stage_plan.py and design_doc.py keep only split("\t", 1)[0].
        _rc, out, _err = self.resolve("042-build-the-brief")
        self.assertEqual(out.split("\t", 1)[0],
                         f"{self._PROJECT}/tasks/042-build-the-brief/plan.md")


def _real_seam() -> "Path | None":
    """agentm's own process_seam.py in a checkout, or None: $AGENTM_SCRIPTS_DIR,
    else the conventional ~/Antigravity/agentm clone."""
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    dirs = [Path(env_dir)] if env_dir else []
    dirs.append(Path.home() / "Antigravity" / "agentm" / "scripts")
    for d in dirs:
        if (d / "process_seam.py").is_file():
            return (d / "process_seam.py").resolve()
    return None


REAL_SEAM = _real_seam()


@unittest.skipIf(REAL_SEAM is None, "no agentm checkout with scripts/process_seam.py")
class TestRealSeam(unittest.TestCase):
    """The resolver through agentm's real seam, against a scratch vault: a flat
    pair, and a numbered task by its full name, trackers included. Nothing
    points at the live vault or the operator's home: MEMORY_ROOT names the
    scratch vault, AGENTM_INSTALL_PREFIX a blank scratch prefix, HOME and
    XDG_CACHE_HOME scratch directories, and OBSIDIAN_VAULT_SCRIPTS this repo's
    own vault plugin."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-real-seam-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        vault = self.tmp / "vault"
        self.harness = vault / "projects" / "probe" / "_harness"
        self.harness.mkdir(parents=True)
        (self.harness / "PLAN-foo.md").write_text("# Plan: foo\n\n**Status:** planning\n",
                                                  encoding="utf-8")
        self.task = vault / "projects" / "probe" / "tasks" / "042-build-the-brief"
        self.task.mkdir(parents=True)
        (self.task / "plan.md").write_text("# Plan: Build the brief\n\n**Status:** planning\n",
                                           encoding="utf-8")
        self.repo = self.tmp / "repo"
        (self.repo / ".harness").mkdir(parents=True)
        (self.repo / ".harness" / "project.json").write_text(
            json.dumps({"vault_project": "probe"}), encoding="utf-8")
        home = self.tmp / "home"
        (home / ".claude").mkdir(parents=True)
        patcher = mock.patch.dict(os.environ, {
            "HOME": str(home),
            "AGENTM_INSTALL_PREFIX": str(home / ".claude"),
            "MEMORY_ROOT": str(vault),
            "OBSIDIAN_VAULT_SCRIPTS": str(_ROOT / "src" / "obsidian-vault" / "scripts"),
            "XDG_CACHE_HOME": str(self.tmp / "cache"),
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("MEMORY_VAULT_PATH", None)

    # The flat pair's real-seam case retired with agentm #680 (agentm-vault part
    # 15): agentm places a named plan in a numbered task and no longer answers a
    # flat pair. Task 101 retires the flat branch this bridge still carries.

    def test_a_numbered_task_by_its_full_name(self):
        rc, out, err = rp.resolve("042-build-the-brief", str(self.repo), seam=REAL_SEAM)
        self.assertEqual(rc, 0, err)
        t = self.task
        self.assertEqual(out, f"{t / 'plan.md'}\t{t / 'progress.md'}\t{t / 'tracker.md'}\n")


# ── Plan-name contract — golden vectors shared with the agentm twin ─────────────
# These two tables are duplicated VERBATIM in the agentm authority's test suite
# (agentm/scripts/test_resolve_active_plan.py, class PlanNameContractParity) so
# this standalone fallback normalizer can't drift from what agentm means. That's
# the disposition of the 2026-06-13 adversarial audit (finding ML2): no cross-repo
# import edge (DC-2), just one table asserted on both sides. Change a row here →
# change it there. `PLAN-PLAN.md` (singleton on both) and `foo\x00` (unsafe on
# both) are the two rows that encode the drifts the audit caught and this fix
# closed.
_PLAN_NAME_VECTORS = [
    ("", ("PLAN.md", "progress.md")),
    ("   ", ("PLAN.md", "progress.md")),
    ("PLAN", ("PLAN.md", "progress.md")),
    ("PLAN.md", ("PLAN.md", "progress.md")),
    ("PLAN-PLAN", ("PLAN.md", "progress.md")),
    ("PLAN-PLAN.md", ("PLAN.md", "progress.md")),
    ("foo", ("PLAN-foo.md", "progress-foo.md")),
    ("PLAN-foo", ("PLAN-foo.md", "progress-foo.md")),
    ("PLAN-foo.md", ("PLAN-foo.md", "progress-foo.md")),
    ("  PLAN-foo.md  ", ("PLAN-foo.md", "progress-foo.md")),
    ("my-plan", ("PLAN-my-plan.md", "progress-my-plan.md")),
]

_PLAN_SLUG_SAFETY = [
    ("foo", True), ("foo-bar", True), ("foo.bar", True), ("v2", True),
    (".", False), ("..", False), ("a/b", False), ("a\\b", False), ("foo\x00", False),
]


class PlanNameContractParity(unittest.TestCase):
    """The (name → pair) + slug-safety contract this fallback must match in agentm.

    agentm is the authority (this bridge delegates to it when a clone is present);
    these vectors pin the meaning so the standalone fallback can't drift from it.
    """

    def test_name_to_pair_golden_vectors(self):
        for name, expected in _PLAN_NAME_VECTORS:
            slug = rp._normalize_plan_name(name)
            self.assertEqual(rp._plan_pair(slug), expected, f"name={name!r}")

    def test_slug_safety_golden_vectors(self):
        for slug, expected in _PLAN_SLUG_SAFETY:
            self.assertEqual(rp._is_safe_plan_slug(slug), expected, f"slug={slug!r}")


if __name__ == "__main__":
    unittest.main()
