#!/usr/bin/env python3
"""The cross-repo edges of the re-homed vault backend (V5-2 tasks 3–4).

Three things this proves, from the crickets (plugin) side:

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

  3. **First-run adoption is invisible (task 4, LC-4).** Driving the real
     `backend_selection.select_backend` against a *synthetic* on-device config
     (`storage.backend = vault` + an in-place `vault_path`) and the real plugin:
     selection resolves `vault` to the *plugin* seeded from that path (the same
     `projects/<slug>/…` layout the built-in served), the `.agentm-config.json`
     stays **byte-identical** (the plugin reads `vault_path`, never writes the
     kernel's config), and no migration prompt fires / no device-local root is
     created (adopted in place, never demoted). Same locate-or-skip discipline.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

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
        # V5-3 deleted the kernel built-in vault backend — the vault backend now
        # lives only in this plugin, discovered on demand by the engine resolver
        # (`backend_selection._load_vault_plugin_backend`). The shared `vault`
        # registry slot is therefore empty in production; clear it here so a sibling
        # plugin-test loader can't leave a stale class in it and skew the
        # leaves-unmutated assertion below.
        import storage_seam  # noqa: E402  (only importable once path is set)

        storage_seam.registry._backends.pop(PROTOCOL_NAME, None)
        import backend_selection  # noqa: E402
        import vault_lock  # noqa: E402

        cls.bs = backend_selection
        cls.seam = storage_seam
        cls.vault_lock = vault_lock

    def setUp(self) -> None:
        # The registry singleton is shared across every test module in the run, and
        # a sibling loader may leave a plugin class in the `vault` slot. Clear it so
        # the slot starts empty — the V5-3 production state (no kernel built-in) the
        # leaves-unmutated assertion below pins.
        self.seam.registry._backends.pop(PROTOCOL_NAME, None)

    def test_resolver_loads_plugin_backend(self) -> None:
        backend_cls = self.bs._load_vault_plugin_backend(plugin_scripts=PLUGIN_SCRIPTS)
        self.assertIsNotNone(
            backend_cls, "the engine resolver did not discover the plugin backend"
        )
        self.assertTrue(issubclass(backend_cls, self.seam.StorageBackend))
        # Post-V5-3 the plugin is the sole vault backend (no kernel built-in to be
        # distinct from); the resolver hands back its `VaultBackend`.
        self.assertEqual(backend_cls.__name__, "VaultBackend")

    def test_resolver_leaves_registry_unmutated(self) -> None:
        before = self.seam.registry.get(PROTOCOL_NAME)
        self.bs._load_vault_plugin_backend(plugin_scripts=PLUGIN_SCRIPTS)
        after = self.seam.registry.get(PROTOCOL_NAME)
        # Loading frees the slot so the plugin can self-register, then pops it again
        # in `finally` — discovery must not permanently mutate the shared registry.
        # Post-V5-3 there is no built-in to restore, so the slot is empty (None)
        # both before and after.
        self.assertIs(after, before)
        self.assertIsNone(after)

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


@unittest.skipUnless(PLUGIN_BACKEND.is_file(), f"{PLUGIN_BACKEND} not present")
class FirstRunAdoptionEdge(unittest.TestCase):
    """V5-2 task 4 — the invisible handoff: the plugin adopts the in-place `vault_path`.

    The adoption *mechanism* shipped in task 3 (`select_backend` reads
    `harness_memory.vault_path()` and seeds the plugin from it). This proves the
    handoff is **invisible** end-to-end, driving the real agentm `select_backend`
    against the real plugin with a synthetic on-device config — never the
    operator's real `~/.claude/.agentm-config.json` or vault. Graceful-skips when
    no sibling agentm clone is reachable, like the discovery edge above.
    """

    @classmethod
    def setUpClass(cls) -> None:
        agentm_scripts = _locate_agentm_scripts()
        if agentm_scripts is None:
            raise unittest.SkipTest(
                "agentm kernel clone not found (set AGENTM_SCRIPTS or check out "
                "../agentm) — adoption edge skipped to keep CI deterministic"
            )
        if str(agentm_scripts) not in sys.path:
            sys.path.insert(0, str(agentm_scripts))
        # V5-3 deleted the kernel built-in; the vault backend is plugin-only,
        # discovered by `select_backend` via `_load_vault_plugin_backend`. Clear the
        # shared `vault` slot so a sibling loader can't leave a stale class in it.
        import storage_seam  # noqa: E402

        storage_seam.registry._backends.pop(PROTOCOL_NAME, None)
        import backend_selection  # noqa: E402

        cls.bs = backend_selection
        cls.seam = storage_seam

    def setUp(self) -> None:
        # Clear the shared `vault` slot so `select_backend` discovers the plugin
        # from scratch (post-V5-3 there is no pre-registered built-in), deterministic
        # regardless of test ordering.
        self.seam.registry._backends.pop(PROTOCOL_NAME, None)
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        # The on-device install prefix carrying the operator's *existing* state —
        # `storage.backend = vault` + the plugin-namespaced `plugins.obsidian-vault.vault_path`
        # key (post-V5-7 migration format). V5-7 migrates the legacy flat `vault_path` key to
        # this form on first read; using the already-migrated format here keeps the adoption
        # invisible (no migration prompt fires). The `projects/` subdir keeps the resolved
        # layout on the post-V4 name (no legacy-rename warning to confound the output check).
        self.prefix = tmp / "prefix"
        self.prefix.mkdir()
        self.vault = tmp / "vault"
        (self.vault / "projects").mkdir(parents=True)
        self.lock = tmp / "lock"
        self.lock.mkdir()
        # A device-local root that must NEVER be created — adoption is in place,
        # never a demotion (the never-demote invariant, proved on the adoption path).
        self.device_root = tmp / "device-local-root"
        self.config_path = self.prefix / ".agentm-config.json"
        self.config_path.write_text(
            json.dumps({
                "storage.backend": "vault",
                "plugins.obsidian-vault.vault_path": str(self.vault),
            }),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _select_under_config(self):
        """Run the real `select_backend` against the synthetic config + real plugin.

        Hermetic env: `$AGENTM_INSTALL_PREFIX` points *both* config reads (the
        `storage.backend` selection and the `vault_path` seed) at the synthetic
        prefix; `$MEMORY_VAULT_PATH` is cleared so the config's `vault_path` *key*
        is the source — proving in-place adoption, not an env override; and
        `$OBSIDIAN_VAULT_SCRIPTS` is cleared (the plugin is injected explicitly).
        stdout+stderr are captured to assert no migration prompt fires.
        """
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(
            os.environ, {"AGENTM_INSTALL_PREFIX": str(self.prefix)}, clear=False
        ):
            os.environ.pop("MEMORY_VAULT_PATH", None)
            os.environ.pop("OBSIDIAN_VAULT_SCRIPTS", None)
            with redirect_stdout(out), redirect_stderr(err):
                backend = self.bs.select_backend(
                    install_prefix=self.prefix,
                    device_local_root=self.device_root,
                    vault_lock_root=self.lock,
                    vault_plugin_scripts=PLUGIN_SCRIPTS,
                )
        return backend, out.getvalue() + err.getvalue()

    def test_selection_resolves_vault_to_the_plugin_reading_the_configured_path(self) -> None:
        backend, _ = self._select_under_config()
        # The plugin's `VaultBackend` (the sole vault backend post-V5-3), a real
        # StorageBackend.
        self.assertIsInstance(backend, self.seam.StorageBackend)
        self.assertEqual(type(backend).__name__, "VaultBackend")
        # Seeded from the in-place config `vault_path` — the same root the built-in had.
        self.assertEqual(backend.root, self.vault)
        # The same projects/<slug>/… layout: a write lands under <vault>/projects/...
        loc = backend.resolve("projects", "demo", "note.md")
        backend.write(loc, "alpha\nbeta\n")
        on_disk = self.vault / "projects" / "demo" / "note.md"
        self.assertTrue(
            on_disk.is_file(),
            "the plugin did not resolve the built-in's projects/<slug> layout",
        )
        self.assertEqual(on_disk.read_text(encoding="utf-8"), "alpha\nbeta\n")

    def test_config_is_byte_identical_after_selection(self) -> None:
        before = self.config_path.read_bytes()
        self._select_under_config()
        after = self.config_path.read_bytes()
        self.assertEqual(
            before,
            after,
            "selection mutated the kernel's config file — LC-4: the plugin reads "
            "`vault_path`, it never writes the kernel's config",
        )

    def test_adoption_fires_no_migration_prompt_and_never_demotes(self) -> None:
        backend, output = self._select_under_config()
        self.assertIsInstance(backend, self.seam.StorageBackend)
        self.assertNotIn(
            "migrat",
            output.lower(),
            f"a migration prompt fired during the invisible handoff: {output!r}",
        )
        # Adopted in place: no data move, and the device-local root is never created
        # (selection resolved the plugin, it did not demote to device-local).
        self.assertFalse(
            self.device_root.exists(),
            "adoption created a device-local root — it demoted instead of adopting "
            "the vault in place",
        )


if __name__ == "__main__":
    unittest.main()
