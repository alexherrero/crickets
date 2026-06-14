#!/usr/bin/env python3
"""The two cross-repo edges of the re-homed vault backend (V5-2 task 3).

Two things this proves, from the crickets (plugin) side:

  1. **No vendored lock.** There is no second `vault_lock.py` anywhere in the
     `obsidian-vault` plugin tree (LC-3): the backend imports the *single* kernel
     copy, never a vendored one. This check is a pure filesystem scan — it needs
     no agentm clone and always runs.

  2. **Discovery + the lock round-trip.** Driving the agentm engine's own
     discovery resolver (`backend_selection._load_vault_plugin_backend`) against
     the real plugin `scripts/` resolves the *plugin* backend (a class distinct
     from the kernel built-in), leaves the global registry exactly as it found it
     (the built-in stays registered for the parallel-run), composes the same
     `vault_mutex` object the kernel `vault_lock` exports (the single canonical
     write protocol), and round-trips a write LF-exact through it. The backend
     imports `storage_seam` + `vault_lock` from the kernel (LC-3), so this half
     locates the sibling agentm clone and **graceful-skips** when none is reachable
     (keeping crickets CI deterministic).
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_GROUP = REPO_ROOT / "src" / "obsidian-vault"
PLUGIN_SCRIPTS = PLUGIN_GROUP / "scripts"
PLUGIN_BACKEND = PLUGIN_SCRIPTS / "storage_vault.py"

PROTOCOL_NAME = "vault"


def _locate_agentm_scripts() -> Path | None:
    """Find the agentm kernel `scripts/` dir, or None when no clone is reachable.

    Order: an explicit `AGENTM_SCRIPTS` override, then the conventional sibling
    checkout (`../agentm/scripts` next to the crickets repo root) — the same
    strategy the task-1 structural smoke test uses.
    """
    override = os.environ.get("AGENTM_SCRIPTS")
    if override:
        p = Path(override).expanduser()
        return p if (p / "storage_seam.py").is_file() else None
    sibling = REPO_ROOT.parent / "agentm" / "scripts"
    return sibling if (sibling / "storage_seam.py").is_file() else None


class NoVendoredVaultLock(unittest.TestCase):
    """LC-3: the plugin imports the kernel `vault_lock.py`; it never vendors a copy."""

    def test_no_second_vault_lock_in_plugin_tree(self) -> None:
        hits = sorted(str(p.relative_to(REPO_ROOT)) for p in PLUGIN_GROUP.rglob("vault_lock.py"))
        self.assertEqual(
            hits,
            [],
            "the obsidian-vault plugin vendored a vault_lock.py copy "
            f"({hits}) — LC-3 says import the single kernel copy, never vendor it",
        )


@unittest.skipUnless(PLUGIN_BACKEND.is_file(), f"{PLUGIN_BACKEND} not present")
class VaultPluginDiscoveryEdge(unittest.TestCase):
    """The engine resolver discovers + loads the real plugin backend, lock intact."""

    @classmethod
    def setUpClass(cls) -> None:
        agentm_scripts = _locate_agentm_scripts()
        if agentm_scripts is None:
            raise unittest.SkipTest(
                "agentm kernel clone not found (set AGENTM_SCRIPTS or check out "
                "../agentm) — discovery edge skipped to keep CI deterministic"
            )
        if str(agentm_scripts) not in sys.path:
            sys.path.insert(0, str(agentm_scripts))
        # A sibling plugin-test loader (task-1 structural smoke) may have left a
        # plugin class in the shared `vault` slot WITHOUT the kernel built-in ever
        # being imported — the kernel module's import-time self-register
        # (`backend_selection` → `storage_vault`) would then hit the registry's
        # duplicate guard. Free the slot first so the kernel built-in registers
        # clean. (In production the built-in always imports before any plugin
        # loads, so this collision is a single-process test artifact only.)
        import storage_seam  # noqa: E402  (only importable once path is set)

        storage_seam.registry._backends.pop(PROTOCOL_NAME, None)
        import backend_selection  # noqa: E402
        import storage_vault as kernel_vault  # noqa: E402  (the kernel built-in)
        import vault_lock  # noqa: E402

        cls.bs = backend_selection
        cls.seam = storage_seam
        cls.kernel_backend = kernel_vault.VaultBackend
        cls.vault_lock = vault_lock

    def setUp(self) -> None:
        # The registry singleton is shared across every test module in the run, and
        # a sibling loader (task-1 structural smoke) may leave a plugin class in the
        # `vault` slot. Normalize to the kernel built-in so the restore assertion
        # below is deterministic regardless of test ordering.
        self.seam.registry.register(PROTOCOL_NAME, self.kernel_backend, clobber=True)

    def test_resolver_loads_plugin_backend_distinct_from_builtin(self) -> None:
        backend_cls = self.bs._load_vault_plugin_backend(plugin_scripts=PLUGIN_SCRIPTS)
        self.assertIsNotNone(
            backend_cls, "the engine resolver did not discover the plugin backend"
        )
        self.assertTrue(issubclass(backend_cls, self.seam.StorageBackend))
        # The plugin class is the one selection hands back — NOT the kernel built-in.
        self.assertIsNot(backend_cls, self.kernel_backend)

    def test_resolver_restores_registry_to_builtin(self) -> None:
        before = self.seam.registry.get(PROTOCOL_NAME)
        self.bs._load_vault_plugin_backend(plugin_scripts=PLUGIN_SCRIPTS)
        after = self.seam.registry.get(PROTOCOL_NAME)
        # Loading frees the slot so the plugin can self-register, then restores the
        # built-in — discovery must not permanently mutate the shared registry.
        self.assertIs(after, before)
        self.assertIs(after, self.kernel_backend)

    def test_write_composes_the_single_kernel_vault_lock(self) -> None:
        # The lock edge: the plugin backend's `write` is bound to the very same
        # `vault_mutex` / `atomic_write` objects the kernel `vault_lock` exports —
        # proof it imported the single canonical copy rather than a vendored one.
        backend_cls = self.bs._load_vault_plugin_backend(plugin_scripts=PLUGIN_SCRIPTS)
        write_globals = backend_cls.write.__globals__
        self.assertIs(write_globals["vault_mutex"], self.vault_lock.vault_mutex)
        self.assertIs(write_globals["atomic_write"], self.vault_lock.atomic_write)

    def test_write_round_trips_lf_exact_through_the_lock(self) -> None:
        # A live CAS round-trip: write-then-read returns the same bytes (LF-exact),
        # flowing through the imported `vault_mutex` + content-hash CAS.
        backend_cls = self.bs._load_vault_plugin_backend(plugin_scripts=PLUGIN_SCRIPTS)
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as lock:
            backend = backend_cls(root, lock_root=lock)
            loc = backend.resolve("projects", "demo", "note.md")
            content = "alpha\nbeta\ngamma\n"
            backend.write(loc, content)
            self.assertEqual(backend.read(loc), content)


if __name__ == "__main__":
    unittest.main()
