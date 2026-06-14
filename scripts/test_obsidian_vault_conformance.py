#!/usr/bin/env python3
"""V5-2 task 5 — the load-bearing conformance + byte-identical parallel-run proof (LC-5).

This is the **entire acceptance bar** for the storage re-home: green here is
exactly what unlocks V5-3 to delete the built-in ``vault`` backend on *evidence*,
never on assertion. Three proofs, all from the crickets (plugin) side, driving the
real agentm machinery imported from the located sibling clone:

  1. **Conformance — the plugin is a valid backend** (``PluginVaultConformance``).
     The V5-1-authored kernel suite (``storage_conformance``) run *unchanged*
     against the obsidian-vault *plugin* backend (loaded through the engine's own
     discovery resolver), as an auto-discovered ``unittest`` mixin so the LF-exact
     round-trip is proven on the **Windows** CI runner too. The ``reindex``
     derived-layer clause is present-but-**vacuous** (M4 — the vault keeps no
     derived index): ``run_conformance`` reports ``derived: "skipped"`` and
     ``PluginVaultRunConformanceReport`` asserts that explicitly, so a green run is
     never misread as index-rebuild proof.

  2. **Parallel-run — plugin ≡ built-in, byte-for-byte** (``PluginVsBuiltinParallelRun``).
     On a *shared* scratch vault root the plugin reads exactly what the built-in
     wrote (and vice-versa), byte-identical including CRLF + non-ASCII; two
     *independent* vaults given identical writes produce byte-identical files on
     disk; locator resolution and ``list``/``exists``/``info`` agree. The empty
     diff *is* LC-5.

All of it locates the sibling agentm clone and **graceful-skips** when none is
reachable, so crickets CI stays deterministic (the kernel suite is agentm-homed;
it runs live wherever ``../agentm`` is checked out — e.g. the operator's machine).
This is the "how does crickets CI reach an agentm-homed suite?" edge the plan
flags: the suite must be importable at *class-definition* time, so the clone is
located at **module load** and the whole battery is skipped when it is absent —
never an import error that reds the run.

The operator's *real* vault is never touched here: every case uses a fresh
``tempfile`` scratch tree (the factory contract — a clean root per check), and the
``vault_mutex`` lock base is redirected into that tree so the real ``~/.cache``
lock base is never written. A read-only resolution spot-check against the live
vault is a *manual* verification scenario, not an automated (non-hermetic) case.
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
    """Find the agentm kernel ``scripts/`` dir, or None when no clone is reachable.

    Order: an explicit ``AGENTM_SCRIPTS`` override, then the conventional sibling
    checkout (``../agentm/scripts`` next to the crickets repo root) — the same
    strategy the task-1 structural smoke and the task-3/4 discovery edges use.
    """
    override = os.environ.get("AGENTM_SCRIPTS")
    if override:
        p = Path(override).expanduser()
        return p if (p / "storage_seam.py").is_file() else None
    sibling = REPO_ROOT.parent / "agentm" / "scripts"
    return sibling if (sibling / "storage_seam.py").is_file() else None


# --- module-load resolution: import the agentm-homed suite, or arm the skip -----
# The kernel `ConformanceSuite` mixin must exist when the class statements below
# execute, but it lives in the agentm clone — so the path is set up HERE, at
# import time, not in setUpClass. When the clone is absent we leave a placeholder
# base and a False flag so every class is cleanly `skipUnless`-skipped rather than
# crashing discovery with an ImportError (CI determinism — the plan's Risks edge).
_AGENTM_SCRIPTS = _locate_agentm_scripts()
_AGENTM_AVAILABLE = _AGENTM_SCRIPTS is not None and PLUGIN_BACKEND.is_file()
_SKIP_REASON = (
    "agentm kernel clone not found (set AGENTM_SCRIPTS or check out ../agentm) — "
    "the imported conformance + parallel-run battery is skipped to keep CI deterministic"
)

if _AGENTM_AVAILABLE:
    if str(_AGENTM_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_AGENTM_SCRIPTS))
    # Free the shared `vault` slot before the kernel's import-time self-register
    # (`backend_selection` → `storage_vault`) so it registers clean past the
    # duplicate guard — a sibling loader (the task-1 smoke / discovery edge) may
    # have left a plugin class in the slot without the built-in ever importing.
    # This is a single-process test artifact only; production imports the built-in
    # before any plugin loads.
    import storage_seam as _ss  # noqa: E402

    _ss.registry._backends.pop(PROTOCOL_NAME, None)
    import backend_selection as _bs  # noqa: E402
    import storage_conformance as _sc  # noqa: E402
    import storage_vault as _kernel_vault  # noqa: E402  (the kernel built-in)
    from storage_conformance import ConformanceSuite, run_conformance  # noqa: E402

    # Whatever the prior import ordering across the discover run, leave the shared
    # `vault` slot holding the built-in so sibling modules that call
    # `registry.get('vault')` see the canonical backend (the parallel-run reaches
    # the built-in by direct import, but a good citizen restores the registry).
    _ss.registry.register(PROTOCOL_NAME, _kernel_vault.VaultBackend, clobber=True)
else:  # pragma: no cover - exercised only on a clone-less host (e.g. crickets CI)
    # A distinct empty placeholder (NOT `object`) so the `(…, ConformanceSuite,
    # unittest.TestCase)` bases keep a consistent MRO — `object` would illegally
    # precede its own `TestCase` subclass. The classes are `skipUnless`-skipped, so
    # the placeholder contributes no test methods and is never instantiated.
    class ConformanceSuite:  # noqa: D401 - placeholder for the clone-absent path
        pass

    run_conformance = None


# Markdown samples pinning byte-identical fidelity across the two implementations:
# LF-only, CRLF, mixed, no-trailing-newline, and non-ASCII (accented Latin + Greek
# + a cricket 🦗) crossed with CRLF. A backend that translated newlines would
# diverge from its twin on at least the CRLF samples.
_PARALLEL_SAMPLES = (
    "unix line one\nunix line two\n",
    "windows line one\r\nwindows line two\r\n",
    "mixed\r\nlf\nbare-cr\rtail",
    "no trailing newline",
    "non-ascii café ναί \U0001f997\r\nsecond\r\n",
)

# Logical paths whose resolution must be identical between plugin and built-in.
_RESOLVE_BATTERY = (
    (),
    ("a",),
    ("a", "b", "c"),
    ("projects", "demo", "note.md"),
    ("projects", "crickets", "_index.md"),
)


class _PluginBackendCase:
    """Shared scaffolding — loads the plugin backend class through the real resolver.

    NOT a ``TestCase`` (so ``unittest`` discovery does not collect the abstract
    base): only the concrete ``(_PluginBackendCase, …, unittest.TestCase)``
    subclasses are run, and each is ``skipUnless``-guarded on a reachable clone.
    """

    _plugin_cls = None
    _builtin_cls = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # The engine's own discovery resolver loads the plugin backend (pops the
        # `vault` slot, execs the plugin, restores the built-in) and hands back the
        # class — the same path `select_backend` uses on a `storage.backend=vault`.
        cls._plugin_cls = _bs._load_vault_plugin_backend(plugin_scripts=PLUGIN_SCRIPTS)
        if cls._plugin_cls is None:
            raise RuntimeError(
                f"the obsidian-vault plugin backend at {PLUGIN_SCRIPTS} failed to load "
                "via the engine resolver — task-3 discovery is broken (this is a loud "
                "error, not a skip: the plugin file is present)"
            )
        cls._builtin_cls = _kernel_vault.VaultBackend

    def _scratch_vault(self) -> Path:
        """A fresh throwaway vault tree, auto-removed when the test finishes."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def _make_plugin_backend(self):
        """A fresh plugin ``VaultBackend`` over a clean scratch root (the factory).

        Shaped like the real per-project vault path (``<vault>/projects/<slug>``)
        so the suite exercises the layout the operator's vault actually uses; the
        ``vault_mutex`` lock base is redirected into the same scratch tree.
        """
        base = self._scratch_vault()
        return self._plugin_cls(
            root=base / "vault" / "projects" / "crickets",
            lock_root=base / "locks",
        )

    def _make_builtin_backend(self):
        """A fresh kernel built-in ``VaultBackend`` over its own clean scratch root."""
        base = self._scratch_vault()
        return self._builtin_cls(
            root=base / "vault" / "projects" / "crickets",
            lock_root=base / "locks",
        )

    def _shared_vault_pair(self):
        """A (plugin, built-in, root) trio over **one** shared scratch vault root.

        Both backends address the *same* vault tree (each idempotently mkdir's it),
        with separate lock bases so the shared tree holds only data files — the
        setup for "the plugin reads exactly what the built-in wrote" on one vault.
        """
        base = self._scratch_vault()
        root = base / "vault" / "projects" / "crickets"
        plugin = self._plugin_cls(root=root, lock_root=base / "locks-plugin")
        builtin = self._builtin_cls(root=root, lock_root=base / "locks-builtin")
        return plugin, builtin, root


@unittest.skipUnless(_AGENTM_AVAILABLE, _SKIP_REASON)
class PluginVaultConformance(_PluginBackendCase, ConformanceSuite, unittest.TestCase):
    """The V5-1 universal battery over the **plugin** backend — runs on every CI OS.

    The load-bearing GREEN-on-conformance proof: the plugin is held to the *same*
    objective contract every backend passes (resolve/read/write/list/exists/info/
    mkdir, the byte-identical LF-exact round-trip, list-on-absent, root-confinement)
    over a fresh scratch vault per check. Auto-discovered ``test_*`` methods come
    from ``ConformanceSuite``, so the LF-exact case executes on the **Windows**
    runner — the only place ``\\r\\n`` translation would surface. ``derived_layout``
    defaults to ``None``, so ``test_derived_rebuildable`` skips: the vault exposes
    no derived layer (M4 — the ``reindex`` clause is vacuous here, **not** counted
    as index-rebuild proof).
    """

    def make_backend(self):
        return self._make_plugin_backend()


@unittest.skipUnless(_AGENTM_AVAILABLE, _SKIP_REASON)
class PluginVaultRunConformanceReport(_PluginBackendCase, unittest.TestCase):
    """``run_conformance`` over the plugin — the importable one-call self-test surface.

    The mixin above rides the auto-discovered ``test_*`` path; this proves the
    *other* driver — the one-call :func:`run_conformance` the plugin self-tests
    through (importing the kernel module, mirroring LC-3 import-don't-vendor) — also
    passes, and asserts the derived/reindex clause is reported **vacuous**.
    """

    def test_run_conformance_green_and_derived_vacuous(self) -> None:
        report = run_conformance(self._make_plugin_backend)
        # Every universal contract ran, in the declared order — the plugin is green.
        self.assertEqual(report["universal"], [name for name, _ in _sc.UNIVERSAL_CHECKS])
        self.assertIn("lf_exact_round_trip", report["universal"])
        # The reindex/derived-layer clause is VACUOUS (M4): the vault keeps no
        # derived index, so it is reported skipped — a green run is NOT index-rebuild
        # proof (that first lands with the V6 temporal-graph backend).
        self.assertEqual(report["derived"], "skipped")


@unittest.skipUnless(_AGENTM_AVAILABLE, _SKIP_REASON)
class PluginVsBuiltinParallelRun(_PluginBackendCase, unittest.TestCase):
    """Byte-identical parallel-run: the plugin and the built-in are one backend.

    The belt-and-suspenders half of LC-5 (the conformance suite is the contract;
    this is the on-the-real-code-path equivalence). Two implementations of one
    backend must resolve, serve, and persist identically — the parallel-run *diff
    is empty*. That empty diff is what lets V5-3 delete the built-in.
    """

    def test_plugin_reads_what_builtin_wrote_byte_identical(self) -> None:
        # One vault, written by the built-in, read by the plugin — byte-for-byte.
        plugin, builtin, _ = self._shared_vault_pair()
        for i, content in enumerate(_PARALLEL_SAMPLES):
            builtin.write(builtin.resolve("notes", f"s{i}.md"), content)
            got = plugin.read(plugin.resolve("notes", f"s{i}.md"))
            self.assertEqual(
                got, content, f"plugin did not read the built-in's write verbatim (sample {i})"
            )
            self.assertEqual(
                got.encode("utf-8"),
                content.encode("utf-8"),
                f"plugin/built-in diverged at the byte level (sample {i})",
            )

    def test_builtin_reads_what_plugin_wrote_byte_identical(self) -> None:
        # The mirror direction: written by the plugin, read by the built-in.
        plugin, builtin, _ = self._shared_vault_pair()
        for i, content in enumerate(_PARALLEL_SAMPLES):
            plugin.write(plugin.resolve("notes", f"s{i}.md"), content)
            got = builtin.read(builtin.resolve("notes", f"s{i}.md"))
            self.assertEqual(
                got, content, f"built-in did not read the plugin's write verbatim (sample {i})"
            )
            self.assertEqual(
                got.encode("utf-8"),
                content.encode("utf-8"),
                f"built-in/plugin diverged at the byte level (sample {i})",
            )

    def test_independent_writes_produce_byte_identical_files(self) -> None:
        # Two *independent* vaults, identical input → byte-identical output files.
        # This is the parallel-run in its purest form: same writes, same bytes on
        # disk, regardless of which implementation produced them.
        p_base = self._scratch_vault()
        b_base = self._scratch_vault()
        p_root = p_base / "vault" / "projects" / "crickets"
        b_root = b_base / "vault" / "projects" / "crickets"
        plugin = self._plugin_cls(root=p_root, lock_root=p_base / "locks")
        builtin = self._builtin_cls(root=b_root, lock_root=b_base / "locks")
        for i, content in enumerate(_PARALLEL_SAMPLES):
            rel = ("notes", f"s{i}.md")
            plugin.write(plugin.resolve(*rel), content)
            builtin.write(builtin.resolve(*rel), content)
            p_bytes = p_root.joinpath(*rel).read_bytes()
            b_bytes = b_root.joinpath(*rel).read_bytes()
            self.assertEqual(
                p_bytes,
                b_bytes,
                f"plugin and built-in wrote different bytes for identical input (sample {i}) — "
                "the parallel-run diff is NOT empty",
            )

    def test_locator_resolution_is_identical(self) -> None:
        plugin, builtin, _ = self._shared_vault_pair()
        for parts in _RESOLVE_BATTERY:
            self.assertEqual(
                plugin.resolve(*parts).key,
                builtin.resolve(*parts).key,
                f"locator resolution diverged for {parts!r}",
            )

    def test_list_exists_info_agree_after_identical_writes(self) -> None:
        # A small tree written through the built-in; the plugin (same vault) must
        # agree on the directory listing, existence, and byte sizes.
        plugin, builtin, _ = self._shared_vault_pair()
        builtin.write(builtin.resolve("box", "a.md"), "a\n")
        builtin.write(builtin.resolve("box", "b.md"), "café\r\n")  # non-ASCII + CRLF
        builtin.mkdir(builtin.resolve("box", "sub"))
        builtin.write(builtin.resolve("box", "sub", "deep.md"), "deep\n")

        p_children = sorted(loc.key for loc in plugin.list(plugin.resolve("box")))
        b_children = sorted(loc.key for loc in builtin.list(builtin.resolve("box")))
        self.assertEqual(p_children, b_children, "list disagreed on immediate children")
        self.assertEqual(
            set(b_children),
            {"box/a.md", "box/b.md", "box/sub"},
            "the built-in's own list is not the expected immediate-children set",
        )

        for parts in (("box", "a.md"), ("box", "b.md"), ("box", "sub"), ("box", "absent.md")):
            self.assertEqual(
                plugin.exists(plugin.resolve(*parts)),
                builtin.exists(builtin.resolve(*parts)),
                f"exists disagreed for {parts!r}",
            )

        for parts in (("box", "a.md"), ("box", "b.md")):
            self.assertEqual(
                plugin.info(plugin.resolve(*parts)).size,
                builtin.info(builtin.resolve(*parts)).size,
                f"info.size disagreed for {parts!r}",
            )


if __name__ == "__main__":
    unittest.main()
