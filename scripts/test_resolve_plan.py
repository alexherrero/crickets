#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/resolve_plan.py (multi-plan writers T2).

The bridge has two backends with one contract: **delegate** to agentm's
process seam (`state-path plan` + `state-path progress`) when discoverable,
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


class TestDelegation(unittest.TestCase):
    """A located seam is authoritative — its paths and exit code pass through.

    Stubs stand in for process_seam.py: they receive
    `state-path {plan|progress} [--plan SLUG] [--cwd ROOT]` and return one
    absolute path per call (or an error exit code). resolve_plan.py makes two
    calls and assembles the tab-separated pair.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-delegate-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_d_returns_stub_pair_unchanged(self):
        # Stub returns one path per verb; resolve_plan reassembles the pair.
        stub = _write_stub(
            self.tmp / "stub_ok.py",
            "import sys\n"
            "which = sys.argv[2]\n"
            "sys.stdout.write('/v/PLAN-foo.md\\n' if which == 'plan' else '/v/progress-foo.md\\n')\n"
            "sys.exit(0)\n",
        )
        rc, out, err = rp.resolve("foo", str(self.tmp), seam=stub)
        self.assertEqual(rc, 0)
        self.assertEqual(err, "")
        self.assertEqual(out, "/v/PLAN-foo.md\t/v/progress-foo.md\n")

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
            "sys.stdout.write('/v/PLAN.md\\n' if which == 'plan' else '/v/progress.md\\n')\n"
            "sys.exit(0)\n",
        )
        called = []
        rc, out, err = rp.resolve(
            "", str(self.tmp), seam=stub,
            vault_check=lambda: called.append(1) or True,
        )
        self.assertEqual(rc, 0)
        self.assertEqual(out, "/v/PLAN.md\t/v/progress.md\n")
        self.assertEqual(called, [])


class TestVaultConfiguredAndReachableProbe(unittest.TestCase):
    """Direct coverage of `_vault_configured_and_reachable`'s own resolution —
    the evidence source the guard above consults."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-vaultprobe-"))
        self._saved_env = {
            k: os.environ.get(k) for k in ("MEMORY_VAULT_PATH", "AGENTM_INSTALL_PREFIX")
        }
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
        os.environ["MEMORY_VAULT_PATH"] = str(vault_dir)
        self.assertTrue(rp._vault_configured_and_reachable())

    def test_env_override_nonexistent_dir_false(self):
        os.environ["MEMORY_VAULT_PATH"] = str(self.tmp / "does-not-exist")
        self.assertFalse(rp._vault_configured_and_reachable())

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
