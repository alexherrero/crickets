#!/usr/bin/env python3
"""Structural smoke test for the re-homed `obsidian-vault` plugin backend (V5-2 task 1).

Asserts the lifted-into-the-plugin `storage_vault.py` still declares the full
storage-seam contract — all seven verbs, the synced/multi-writer capability
descriptor, the named whole-file conflict strategy — and self-registers under the
`vault` protocol in the seam's default registry when loaded under a present
engine. This is the LC-1 "the move was faithful, structurally" check; the
behavioral proof (the V5-1 conformance suite + byte-identical parallel-run) lands
in task 5.

The backend imports `storage_seam` and `vault_lock` from the agentm kernel — the
plugin only ever runs under a present engine (LC-3). So this test locates the
sibling agentm clone and puts its `scripts/` on `sys.path`; when no clone is
found (e.g. crickets CI in isolation) it **graceful-skips** so the deterministic
gate stays deterministic.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_BACKEND = REPO_ROOT / "src" / "obsidian-vault" / "scripts" / "storage_vault.py"

#: The seven storage-seam verbs the backend must implement.
SEVEN_VERBS = ("resolve", "read", "write", "list", "exists", "info", "mkdir")


def _locate_agentm_scripts() -> Path | None:
    """Find the agentm kernel `scripts/` dir, or None when no clone is reachable.

    Order: an explicit `AGENTM_SCRIPTS` override, then the conventional sibling
    checkout (`../agentm/scripts` next to the crickets repo root). The module
    under test imports `storage_seam` + `vault_lock` from here.
    """
    override = os.environ.get("AGENTM_SCRIPTS")
    if override:
        p = Path(override).expanduser()
        return p if (p / "storage_seam.py").is_file() else None
    sibling = REPO_ROOT.parent / "agentm" / "scripts"
    return sibling if (sibling / "storage_seam.py").is_file() else None


def _load_plugin_backend(agentm_scripts: Path):
    """Import the plugin's storage_vault.py by path, under a present engine.

    Puts the agentm `scripts/` on `sys.path` (so the module's `from storage_seam`
    / `from vault_lock` imports resolve), clears any pre-existing `vault`
    registration so the module's import-time self-register can't collide, then
    loads the file under a unique module name (avoiding the name clash with the
    kernel's own `storage_vault`).
    """
    if str(agentm_scripts) not in sys.path:
        sys.path.insert(0, str(agentm_scripts))
    import storage_seam  # noqa: E402  (only importable once the path is set)

    # A fresh slot for the import-time `registry.register("vault", ...)` — the
    # default registry refuses a silent duplicate (ProtocolError) otherwise.
    storage_seam.registry._backends.pop(PROTOCOL_NAME, None)

    spec = importlib.util.spec_from_file_location(
        "obsidian_vault_storage_vault", PLUGIN_BACKEND
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, storage_seam


PROTOCOL_NAME = "vault"


@unittest.skipUnless(PLUGIN_BACKEND.is_file(), f"{PLUGIN_BACKEND} not present")
class ObsidianVaultBackendStructure(unittest.TestCase):
    """The re-homed backend declares the full seam contract + self-registers."""

    @classmethod
    def setUpClass(cls) -> None:
        agentm_scripts = _locate_agentm_scripts()
        if agentm_scripts is None:
            raise unittest.SkipTest(
                "agentm kernel clone not found (set AGENTM_SCRIPTS or check out "
                "../agentm) — structural import skipped to keep CI deterministic"
            )
        cls.module, cls.seam = _load_plugin_backend(agentm_scripts)
        cls.Backend = cls.module.VaultBackend

    def test_protocol_name_is_vault(self) -> None:
        self.assertEqual(self.module.PROTOCOL, PROTOCOL_NAME)

    def test_declares_all_seven_verbs(self) -> None:
        for verb in SEVEN_VERBS:
            with self.subTest(verb=verb):
                self.assertTrue(
                    callable(getattr(self.Backend, verb, None)),
                    f"backend is missing the seam verb {verb!r}",
                )

    def test_capability_descriptor(self) -> None:
        # The synced, multi-writer profile — the positive contrast to
        # device-local's all-False floor.
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as lock:
            backend = self.Backend(root, lock_root=lock)
            caps = backend.capabilities
            self.assertTrue(caps.concurrent_writers)
            self.assertTrue(caps.conflict_files)
            self.assertFalse(caps.encryption)
            self.assertTrue(caps.sync)

    def test_named_conflict_strategy(self) -> None:
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as lock:
            backend = self.Backend(root, lock_root=lock)
            self.assertEqual(backend.conflict_strategy, "whole-file")

    def test_resolve_returns_seam_locator_not_path(self) -> None:
        # The seam contract: verbs traffic in Locator, never pathlib.Path.
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as lock:
            backend = self.Backend(root, lock_root=lock)
            loc = backend.resolve("_harness", "PLAN.md")
            self.assertIsInstance(loc, self.seam.Locator)
            self.assertNotIsInstance(loc, Path)

    def test_registers_under_vault_protocol(self) -> None:
        # Import-time self-registration into the seam's default registry under
        # the protocol name selection looks up.
        self.assertIn(PROTOCOL_NAME, self.seam.registry)
        self.assertIs(self.seam.registry.get(PROTOCOL_NAME), self.Backend)


if __name__ == "__main__":
    unittest.main()
