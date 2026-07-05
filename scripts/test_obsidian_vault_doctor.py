#!/usr/bin/env python3
"""The obsidian-vault operator doctor check — `scripts/doctor_vault.py` (V5-2 task 6).

Two layers, mirroring the rest of the obsidian-vault cross-repo suite:

  1. **Pure rows (always run).** The mechanics that need no agentm clone — the
     `vault-path [FAIL]` rows (unconfigured / missing dir), the `vault_path`
     resolution precedence (`$MEMORY_VAULT_PATH` → config → None), the formatter,
     the `locate_kernel_scripts` search, and `main`'s exit-code contract (1 iff a
     FAIL row). These pin the read-only-diagnostic shape regardless of environment.

  2. **With a present engine (graceful-skip).** Drive the three real checks against
     a *synthetic* vault + the *real* kernel (`vault_probe`, `storage_preview`,
     `_conflict_family`) + the *real* plugin `scripts/`, never the operator's live
     vault or `~/.claude/.agentm-config.json`. Proves: a real MemoryVault + the
     installed plugin + a clean tree → three OK rows; a shapeless dir → vault-path
     WARN; the plugin absent → backend FAIL (the check bites); a conflict file →
     conflicts WARN; and the whole pass is read-only (config byte-identical, no
     device-local root, no mkdir in the vault). Graceful-skips when no sibling
     agentm clone is reachable, so crickets CI stays deterministic.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SCRIPTS = REPO_ROOT / "src" / "obsidian-vault" / "scripts"
DOCTOR_SRC = PLUGIN_SCRIPTS / "doctor_vault.py"
PROTOCOL_NAME = "vault"


def _load_doctor():
    """Import doctor_vault.py by file location (it ships in the plugin scripts/)."""
    spec = importlib.util.spec_from_file_location("doctor_vault", DOCTOR_SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _locate_agentm_scripts() -> Path | None:
    """The agentm kernel scripts/ dir, or None when no clone is reachable.

    `$AGENTM_SCRIPTS` override → conventional sibling `../agentm/scripts` — the
    same locate-or-skip strategy as the discovery / conformance edges.
    """
    override = os.environ.get("AGENTM_SCRIPTS")
    if override:
        p = Path(override).expanduser()
        return p if (p / "storage_seam.py").is_file() else None
    sibling = REPO_ROOT.parent / "agentm" / "scripts"
    return sibling if (sibling / "storage_seam.py").is_file() else None


doctor = _load_doctor()


# ── layer 1: pure rows (no agentm clone needed) ──────────────────────────────


class DoctorVaultPureRows(unittest.TestCase):
    """The mechanics that hold regardless of whether an engine is reachable."""

    def test_unconfigured_vault_path_fails(self) -> None:
        row, root = doctor._check_vault_path(None, kernel_scripts=None)
        self.assertEqual((row.name, row.status), ("vault-path", doctor.FAIL))
        self.assertIsNone(root)

    def test_missing_vault_dir_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / "nope")
            row, root = doctor._check_vault_path(missing, kernel_scripts=None)
            self.assertEqual((row.name, row.status), ("vault-path", doctor.FAIL))
            self.assertIsNone(root)

    def test_existing_dir_without_engine_warns_but_keeps_root(self) -> None:
        # The dir exists but no engine is reachable to run vault_probe: WARN, and
        # the existing dir is still handed downstream so the conflict sweep can try.
        with tempfile.TemporaryDirectory() as tmp:
            row, root = doctor._check_vault_path(tmp, kernel_scripts=None)
            self.assertEqual((row.name, row.status), ("vault-path", doctor.WARN))
            self.assertEqual(root, Path(tmp))

    def test_backend_and_conflicts_warn_without_engine(self) -> None:
        # No kernel → both engine-dependent checks degrade to WARN, never crash.
        backend = doctor._check_backend(None, PLUGIN_SCRIPTS, install_prefix=None)
        self.assertEqual((backend.name, backend.status), ("backend", doctor.WARN))
        with tempfile.TemporaryDirectory() as tmp:
            conflicts = doctor._check_conflicts(
                Path(tmp), None, PLUGIN_SCRIPTS, include_lost_and_found=False
            )
        self.assertEqual((conflicts.name, conflicts.status), ("conflicts", doctor.WARN))

    def test_resolve_vault_path_prefers_env(self) -> None:
        with mock.patch.dict(os.environ, {"MEMORY_VAULT_PATH": "/tmp/envwins"}, clear=False):
            self.assertEqual(doctor._resolve_vault_path(None), "/tmp/envwins")

    def test_resolve_vault_path_reads_config_when_env_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp)
            (prefix / ".agentm-config.json").write_text(
                json.dumps({"vault_path": "/tmp/from-config"}), encoding="utf-8"
            )
            env = {k: v for k, v in os.environ.items() if k != "MEMORY_VAULT_PATH"}
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(
                    doctor._resolve_vault_path(prefix), "/tmp/from-config"
                )

    def test_resolve_vault_path_none_when_no_env_no_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = {k: v for k, v in os.environ.items() if k != "MEMORY_VAULT_PATH"}
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertIsNone(doctor._resolve_vault_path(Path(tmp)))

    def test_resolve_vault_path_non_object_config_returns_none(self) -> None:
        # Regression (review finding 1): a config that is valid JSON but NOT an
        # object (`[]`, `42`, `"x"`, `null`) must degrade to None — the way the
        # engine's _read_config_vault_path guards `isinstance(data, dict)` — not
        # crash with AttributeError on `data.get`. A corrupt config is exactly what
        # the doctor should report cleanly (vault-path FAIL), never blow up on.
        for blob in ("[]", "42", '"just-a-string"', "null", "true"):
            with self.subTest(blob=blob), tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / ".agentm-config.json").write_text(blob, encoding="utf-8")
                env = {k: v for k, v in os.environ.items() if k != "MEMORY_VAULT_PATH"}
                with mock.patch.dict(os.environ, env, clear=True):
                    self.assertIsNone(doctor._resolve_vault_path(Path(tmp)))

    def test_resolve_vault_path_non_string_value_returns_none(self) -> None:
        # Regression (review finding 2): a truthy non-string `vault_path` (number,
        # array, object) must collapse to None (mirroring the engine's
        # `isinstance(raw, str)` guard) — the old `value or None` passed it through,
        # and `Path(42)` then raised TypeError downstream in _check_vault_path.
        for bad in (42, ["x"], {"k": "v"}, True):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / ".agentm-config.json").write_text(
                    json.dumps({"vault_path": bad}), encoding="utf-8"
                )
                env = {k: v for k, v in os.environ.items() if k != "MEMORY_VAULT_PATH"}
                with mock.patch.dict(os.environ, env, clear=True):
                    self.assertIsNone(doctor._resolve_vault_path(Path(tmp)))

    def test_resolve_vault_path_expands_tilde(self) -> None:
        # Regression (task-6 /review): a `vault_path` with a leading `~` must be
        # expanded to $HOME — the way the engine's _read_config_vault_path returns
        # `os.path.expanduser(raw.strip())`. The old raw `return value` handed
        # `~/somedir` downstream verbatim, so _check_vault_path's `is_dir()` saw a
        # literal `~` path that never exists → a spurious vault-path FAIL the live
        # engine never produces.
        #
        # The expectation mirrors the production call *exactly* —
        # `os.path.expanduser("~/somedir")`, NOT `os.path.join(expanduser("~"),
        # "somedir")`. On Windows `expanduser` preserves the literal `/` in the
        # suffix (`C:\Users\<name>/somedir`) while `os.path.join` inserts a native `\`,
        # so the join form spuriously fails on Windows though the two coincide on
        # POSIX. Engine parity is the literal `expanduser` result — normalizing the
        # separator in production would reintroduce the very doctor-vs-engine gap
        # this test guards.
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp)
            (prefix / ".agentm-config.json").write_text(
                json.dumps({"vault_path": "~/somedir"}), encoding="utf-8"
            )
            env = {k: v for k, v in os.environ.items() if k != "MEMORY_VAULT_PATH"}
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(
                    doctor._resolve_vault_path(prefix),
                    os.path.expanduser("~/somedir"),
                )

    def test_resolve_vault_path_strips_whitespace(self) -> None:
        # Regression (task-6 /review): surrounding whitespace on `vault_path` must
        # be stripped (engine parity) — `"  /padded  "` resolves to `/padded`, not
        # a padded literal that fails `is_dir()` while the engine resolves it fine.
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp)
            (prefix / ".agentm-config.json").write_text(
                json.dumps({"vault_path": "  /padded  "}), encoding="utf-8"
            )
            env = {k: v for k, v in os.environ.items() if k != "MEMORY_VAULT_PATH"}
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(doctor._resolve_vault_path(prefix), "/padded")

    def test_main_never_crashes_on_malformed_config(self) -> None:
        # Symptom-level regression: the whole CLI path must return an int exit code
        # on a malformed on-device config (LC-3 — the doctor never crashes), not
        # propagate AttributeError/TypeError out of main(). Drives the real
        # resolution (AGENTM_INSTALL_PREFIX → synthetic config), engine absent so
        # the rows degrade to WARN/FAIL deterministically.
        for blob in ("[]", '{"vault_path": 42}'):
            with self.subTest(blob=blob), tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / ".agentm-config.json").write_text(blob, encoding="utf-8")
                env = {k: v for k, v in os.environ.items()
                       if k not in ("MEMORY_VAULT_PATH", "AGENTM_SCRIPTS")}
                env["AGENTM_INSTALL_PREFIX"] = tmp
                with mock.patch.dict(os.environ, env, clear=True):
                    with mock.patch.object(doctor, "locate_kernel_scripts", return_value=None):
                        buf = io.StringIO()
                        with redirect_stdout(buf):
                            rc = doctor.main([])
                self.assertIn(rc, (0, 1))  # an exit code, not an exception
                self.assertIn("vault-path", buf.getvalue())

    def test_format_one_row_per_check(self) -> None:
        rows = [
            doctor.Check("vault-path", doctor.OK, "ok"),
            doctor.Check("backend", doctor.WARN, "warn"),
            doctor.Check("conflicts", doctor.FAIL, "fail"),
        ]
        out = doctor._format(rows)
        self.assertIn("[OK] vault-path", out)
        self.assertIn("[WARN] backend", out)
        self.assertIn("[FAIL] conflicts", out)
        # header + one line per row.
        self.assertEqual(len(out.strip().splitlines()), 1 + len(rows))

    def test_locate_kernel_honors_override_and_absence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # A dir with harness_memory.py is accepted via the override.
            (Path(tmp) / "harness_memory.py").write_text("# stub\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS": tmp}, clear=False):
                self.assertEqual(doctor.locate_kernel_scripts(), Path(tmp).resolve())
            # An override pointing at a dir without the engine module → not accepted
            # (falls through to the conventional locations, which may or may not
            # resolve on the dev box — assert only that the empty override is rejected
            # by checking it is never the returned value).
            empty = Path(tmp) / "empty"
            empty.mkdir()
            with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS": str(empty)}, clear=False):
                self.assertNotEqual(doctor.locate_kernel_scripts(), empty.resolve())

    def test_main_exit_1_on_fail_row(self) -> None:
        # Unconfigured vault_path with no engine → vault-path FAIL → exit 1.
        env = {k: v for k, v in os.environ.items()
               if k not in ("MEMORY_VAULT_PATH", "AGENTM_SCRIPTS", "AGENTM_INSTALL_PREFIX")}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(doctor, "locate_kernel_scripts", return_value=None):
                with mock.patch.object(
                    doctor, "_resolve_vault_path", return_value=None
                ):
                    buf = io.StringIO()
                    with redirect_stdout(buf):
                        rc = doctor.main([])
        self.assertEqual(rc, 1)
        self.assertIn("[FAIL] vault-path", buf.getvalue())


# ── layer 2: the real three checks, against a present engine ─────────────────


@unittest.skipUnless(DOCTOR_SRC.is_file(), f"{DOCTOR_SRC} not present")
class DoctorVaultWithEngine(unittest.TestCase):
    """Drive the three checks against the real kernel + plugin, synthetic vault."""

    @classmethod
    def setUpClass(cls) -> None:
        agentm_scripts = _locate_agentm_scripts()
        if agentm_scripts is None:
            raise unittest.SkipTest(
                "agentm kernel clone not found (set AGENTM_SCRIPTS or check out "
                "../agentm) — doctor engine edge skipped to keep CI deterministic"
            )
        if str(agentm_scripts) not in sys.path:
            sys.path.insert(0, str(agentm_scripts))
        # V5-3 deleted the kernel built-in; the vault backend is plugin-only, and the
        # doctor preview loads it through `_load_vault_plugin_backend(plugin_scripts=…)`
        # (never a pre-registered registry slot). Clear the shared `vault` slot so a
        # sibling loader can't leave a stale class in it.
        import storage_seam  # noqa: E402

        storage_seam.registry._backends.pop(PROTOCOL_NAME, None)
        import backend_selection  # noqa: E402

        cls.kernel_scripts = agentm_scripts
        cls.seam = storage_seam

    def setUp(self) -> None:
        # Clear the shared `vault` slot so the doctor preview discovers the plugin
        # from scratch (post-V5-3 there is no pre-registered built-in), deterministic
        # regardless of test ordering.
        self.seam.registry._backends.pop(PROTOCOL_NAME, None)
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        # A synthetic, real-shaped MemoryVault: `_meta/repos.json` gives it the
        # authoritative vault shape vault_probe keys on; `projects/` keeps the layout.
        self.vault = tmp / "vault"
        (self.vault / "_meta").mkdir(parents=True)
        (self.vault / "_meta" / "repos.json").write_text("{}", encoding="utf-8")
        (self.vault / "projects").mkdir()
        # A synthetic on-device config selecting the vault backend + the in-place path.
        # Uses the post-V5-7 plugin-namespaced key so _read_config_vault_path() does
        # not fire the migration (which would mutate the file and break read-only tests).
        self.prefix = tmp / "prefix"
        self.prefix.mkdir()
        self.config = self.prefix / ".agentm-config.json"
        self.config.write_text(
            json.dumps({
                "storage.backend": "vault",
                "plugins.obsidian-vault.vault_path": str(self.vault),
            }),
            encoding="utf-8",
        )
        # Hermetic env: point the engine's vault_path() read at the synthetic config,
        # clear MEMORY_VAULT_PATH (so the config key is the source, not an override),
        # clear OBSIDIAN_VAULT_SCRIPTS (the plugin is injected explicitly).
        self._env = mock.patch.dict(
            os.environ,
            {"AGENTM_INSTALL_PREFIX": str(self.prefix)},
            clear=False,
        )
        self._env.start()
        for var in ("MEMORY_VAULT_PATH", "OBSIDIAN_VAULT_SCRIPTS"):
            os.environ.pop(var, None)

    def tearDown(self) -> None:
        self._env.stop()
        self._tmp.cleanup()

    def _diagnose(self, *, vault_path=None, plugin_scripts=PLUGIN_SCRIPTS):
        return doctor.diagnose(
            vault_path=str(self.vault) if vault_path is None else vault_path,
            kernel_scripts=self.kernel_scripts,
            plugin_scripts=plugin_scripts,
            install_prefix=self.prefix,
            include_lost_and_found=False,  # never touch the real DriveFS dump
        )

    def test_healthy_install_three_ok_rows(self) -> None:
        rows = {r.name: r for r in self._diagnose()}
        self.assertEqual(rows["vault-path"].status, doctor.OK, rows["vault-path"].detail)
        self.assertEqual(rows["backend"].status, doctor.OK, rows["backend"].detail)
        self.assertEqual(rows["conflicts"].status, doctor.OK, rows["conflicts"].detail)

    def test_vault_path_warns_on_shapeless_dir(self) -> None:
        # A real dir with no _meta/repos.json + no personal/ → not a vault.
        with tempfile.TemporaryDirectory() as plain:
            rows = {r.name: r for r in self._diagnose(vault_path=plain)}
        self.assertEqual(rows["vault-path"].status, doctor.WARN)

    def test_backend_fails_when_plugin_absent(self) -> None:
        # Point the plugin-scripts dir at one with NO storage_vault.py → the engine
        # loader returns None → storage_preview's fail-loud refusal → backend FAIL.
        # Proves the backend row genuinely checks plugin discoverability (it bites).
        with tempfile.TemporaryDirectory() as empty:
            rows = {r.name: r for r in self._diagnose(plugin_scripts=Path(empty))}
        self.assertEqual(rows["backend"].status, doctor.FAIL, rows["backend"].detail)

    def test_conflicts_warn_on_conflict_file(self) -> None:
        # A GDrive "(conflicted copy …)" file in the vault → conflicts WARN.
        (self.vault / "projects" / "PLAN (conflicted copy 2026-05-27).md").write_text(
            "x", encoding="utf-8"
        )
        rows = {r.name: r for r in self._diagnose()}
        self.assertEqual(rows["conflicts"].status, doctor.WARN, rows["conflicts"].detail)
        self.assertIn("conflict", rows["conflicts"].detail.lower())

    def test_diagnose_is_read_only(self) -> None:
        # The whole pass must not write the config, the vault, or a device-local root.
        before = self.config.read_bytes()
        vault_listing_before = sorted(p.name for p in self.vault.rglob("*"))
        rows = self._diagnose()
        self.assertEqual(self.config.read_bytes(), before, "doctor wrote the engine config")
        self.assertEqual(
            sorted(p.name for p in self.vault.rglob("*")),
            vault_listing_before,
            "doctor mutated the vault tree",
        )
        # Sanity: it really did run all three checks (non-vacuous).
        self.assertEqual({r.name for r in rows}, {"vault-path", "backend", "conflicts"})


if __name__ == "__main__":
    unittest.main()
