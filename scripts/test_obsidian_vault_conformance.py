#!/usr/bin/env python3
"""The load-bearing conformance proof for the obsidian-vault plugin backend (LC-5).

Originally the V5-2 acceptance bar for the storage re-home — green here is what
unlocked V5-3 to delete the kernel built-in ``vault`` backend on *evidence*. **That
deletion has since happened**, so this suite reconciled (AG Wave 2, 2026-06-24) from
"prove the plugin ≡ the built-in" to "hold the sole (plugin) backend to the kernel
contract." Two proofs remain, both from the crickets (plugin) side, driving the real
agentm machinery imported from the located sibling clone:

  1. **Conformance — the plugin is a valid backend** (``PluginVaultConformance``).
     The V5-1-authored kernel suite (``storage_conformance``) run *unchanged*
     against the obsidian-vault *plugin* backend (loaded through the engine's own
     discovery resolver), as an auto-discovered ``unittest`` mixin so the LF-exact
     round-trip is proven on the **Windows** CI runner too. The ``reindex``
     derived-layer clause is present-but-**vacuous** (M4 — the vault keeps no
     derived index): ``run_conformance`` reports ``derived: "skipped"`` and
     ``PluginVaultRunConformanceReport`` asserts that explicitly, so a green run is
     never misread as index-rebuild proof.

  2. **Behavioral contract — the CAS the byte suite can't see** (``PluginVaultBehavioralContract``).
     Proof 1 establishes byte-faithfulness under quiescent single-writer access — a
     strictly weaker claim than the byte-*and-behavior* faithfulness the vault needs.
     A plugin whose ``write`` was degraded to ``atomic_write`` *only*
     (device-local-equivalent) passes every conformance case green. This proof
     closes that gap: the plugin's public ``write`` must **bite** on a concurrent
     modification (raise :class:`ConcurrentModificationError`, driven
     deterministically by interposing a foreign write into the CAS window); and the
     plugin must advertise the vault's real profile (``concurrent_writers=True`` /
     ``"whole-file"``), pinned to literals. Homed here, not in the universal kernel
     suite, because the seam's ``write`` exposes no CAS precondition — a universal
     check would need a frozen-seam-API extension (DC-7); see the class docstring.

  (The former proof 2 — ``PluginVsBuiltinParallelRun``, the byte-identical
  plugin↔built-in parallel-run — was the migration gate that authorized deleting the
  built-in. V5-3 has deleted it, so the twin no longer exists; that class was removed
  in AG Wave 2. Git history retains the parallel-run proof.)

All of it locates the sibling agentm clone and **graceful-skips** when none is
reachable, so the suite stays importable at *class-definition* time — the clone is
located at **module load** and the whole battery is skipped when absent, never an
import error that reds the run. crickets CI reaches the kernel by checking out the
sibling agentm repo in a dedicated ``obsidian-vault-conformance`` job (Linux +
Windows; see ``.github/workflows/tests-{linux,windows}.yml``); on the operator's
machine the suite runs live against ``../agentm``.

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
from unittest import mock

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
    # The kernel ships the contract + harness (`backend_selection`,
    # `storage_conformance`) from _AGENTM_SCRIPTS. The vault backend itself is no
    # longer a kernel built-in — V5-3 deleted it and re-homed it in THIS plugin
    # (PLUGIN_SCRIPTS) — so it is loaded only through the engine resolver
    # `backend_selection._load_vault_plugin_backend` (which execs the plugin in
    # isolation and pops its self-registration), never by a global `import
    # storage_vault`. No registry mutation happens at module load.
    import backend_selection as _bs  # noqa: E402
    import storage_conformance as _sc  # noqa: E402
    from storage_conformance import ConformanceSuite, run_conformance  # noqa: E402

    # The vault's distinguishing safety vocabulary — the CAS raise the byte-only
    # universal suite never exercises. Single-sourced from its canonical home
    # (vault_lock, an agentm kernel module the plugin also imports).
    from vault_lock import ConcurrentModificationError  # noqa: E402
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
# (The `_PARALLEL_SAMPLES` / `_RESOLVE_BATTERY` fixtures fed the removed
# plugin↔built-in parallel-run class — dropped in AG Wave 2 with that class, since
# V5-3 deleted the built-in. The LF-exact / CRLF byte fidelity they pinned is still
# covered by `ConformanceSuite`'s `test_lf_exact_round_trip` over the plugin.)


class _PluginBackendCase:
    """Shared scaffolding — loads the plugin backend class through the real resolver.

    NOT a ``TestCase`` (so ``unittest`` discovery does not collect the abstract
    base): only the concrete ``(_PluginBackendCase, …, unittest.TestCase)``
    subclasses are run, and each is ``skipUnless``-guarded on a reachable clone.
    """

    _plugin_cls = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # The registry singleton is shared across the whole `discover` run; a sibling
        # module (the structural smoke) may leave a plugin class in the `vault` slot.
        # `_load_vault_plugin_backend` assumes the slot is empty at entry (post-V5-3
        # there is no kernel built-in), so clear it first — else the plugin's
        # import-time self-register would hit the duplicate guard.
        import storage_seam  # noqa: E402  (path set at module load)

        storage_seam.registry._backends.pop(PROTOCOL_NAME, None)
        # The engine's own discovery resolver loads the plugin backend (execs the
        # plugin, then pops its self-registration in `finally`) and hands back the
        # class — the same path `select_backend` uses on a `storage.backend=vault`.
        cls._plugin_cls = _bs._load_vault_plugin_backend(plugin_scripts=PLUGIN_SCRIPTS)
        if cls._plugin_cls is None:
            raise RuntimeError(
                f"the obsidian-vault plugin backend at {PLUGIN_SCRIPTS} failed to load "
                "via the engine resolver — task-3 discovery is broken (this is a loud "
                "error, not a skip: the plugin file is present)"
            )

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


# NOTE: the `PluginVsBuiltinParallelRun` class (byte-identical plugin↔kernel-built-in
# twin comparison) was removed in AG Wave 2 (2026-06-24). It was a migration-gate
# test — its docstring noted "that empty diff is what lets V5-3 delete the built-in."
# V5-3 has since deleted the kernel built-in, so the twin no longer exists; comparing
# the sole (plugin) backend against itself is vacuous. The plugin's ongoing contract
# is covered by `PluginVaultConformance` (the universal battery) above. Git history
# retains the parallel-run proof.


@unittest.skipUnless(_AGENTM_AVAILABLE, _SKIP_REASON)
class PluginVaultBehavioralContract(_PluginBackendCase, unittest.TestCase):
    """The behavior the byte-only conformance suite structurally cannot assert.

    LC-5's green authorizes V5-3 to **delete** the built-in, on the premise that
    the plugin is byte-*and-behavior* faithful. The V5-1 ``UNIVERSAL_CHECKS`` are
    single-writer / byte-round-trip only — they never touch ``vault_mutex``, the
    content-hash CAS, or :class:`ConcurrentModificationError`. So a plugin whose
    ``write`` was degraded to ``atomic_write`` *only* (device-local-equivalent —
    dropping the whole load-bearing difference) passes every conformance + parallel
    -run case **green**. This class closes that gap with the two checks the suite
    can't express, both deterministic and public-API-driven:

      1. **The CAS bites end-to-end** (``test_*_write_bites_on_concurrent_modification``).
         The vault's CAS only fires when the on-disk bytes change *between* the two
         reads ``write`` makes under the mutex (the pre-write hash capture and the
         re-check in ``_cas_atomic_write``) — a concurrency window the public verbs
         cannot reach single-threaded. We force a non-mutex writer (Drive sync /
         another device) into exactly that window by interposing on
         ``Path.read_bytes`` — the same deterministic technique agentm's own
         ``test_storage_vault`` uses end-to-end — and require the public ``write``
         to **raise** and leave the foreign bytes intact. (Pre-V5-3 this also ran
         against the kernel built-in as a parity anchor; the built-in is gone, so it
         now runs against the plugin and is pinned by the literal advertisement (2).)

      2. **Advertised contract pinned to literals** (``test_plugin_advertises_the_vault_contract``).
         ``capabilities`` + ``conflict_strategy`` must match the vault's real profile
         (``concurrent_writers=True``, ``conflict_strategy="whole-file"``) **pinned to
         literals** — so a backend degraded its way to device-local's all-False floor
         cannot pass. Together with (1) the mutant is boxed in: degrade the ``write``
         and (1) reds; downgrade the advertisement to dodge (1) and (2) reds.

    Why crickets-side and not the agentm kernel suite: the seam's
    ``write(locator, content)`` has no ``expected_hash`` parameter, so there is no
    public, implementation-agnostic way to drive a CAS from the *universal* suite —
    the working trigger is the ``Path.read_bytes`` interposition, which is specific
    to this backend's read pattern (a future etag/fcntl backend would differ). A
    universal kernel check would require extending the frozen seam API (DC-7); that
    is out of scope for closing this gap. So the behavioral proof lives where the
    implementation is known — mirroring where agentm homes its own CAS test.
    """

    def _assert_write_cas_bites(self, backend) -> None:
        """Force a foreign write into ``backend.write``'s CAS window; require the raise.

        ``write`` reads the target twice under the mutex: once to capture the
        ``expected`` hash, once to re-check in the CAS just before the atomic land.
        Interpose on ``Path.read_bytes`` to land ``b"v2-foreign"`` *between* those
        two reads (after the first, before the second): the re-read then sees
        ``v2-foreign`` ≠ ``expected=hash(v1)`` → :class:`ConcurrentModificationError`,
        so the blind ``v3-mine`` overwrite is refused and the foreign write survives.
        A degrade to ``atomic_write``-only has no second read / no CAS, so it would
        clobber silently and this assertion would red — the regression bite.
        """
        loc = backend.resolve("a.md")
        backend.write(loc, "v1")
        target = backend._path(loc)
        real_read_bytes = Path.read_bytes
        reads = {"n": 0}

        def _foreign_write_between_reads(self_path: Path):
            data = real_read_bytes(self_path)
            if self_path == target:
                reads["n"] += 1
                if reads["n"] == 1:  # after the pre-write read, before the CAS re-read
                    target.write_bytes(b"v2-foreign")
            return data

        with mock.patch.object(Path, "read_bytes", _foreign_write_between_reads):
            with self.assertRaises(ConcurrentModificationError):
                backend.write(loc, "v3-mine")
        # The interposition must actually have opened the window (not a vacuous pass):
        # both reads happened, and the foreign write — not our refused v3 — survives.
        self.assertGreaterEqual(reads["n"], 2, "the CAS window never opened — the harness is miswired")
        self.assertEqual(
            backend.read(loc),
            "v2-foreign",
            "the refused write must not clobber the foreign write the CAS protected",
        )

    def test_plugin_write_bites_on_concurrent_modification(self) -> None:
        # The regression bite: a degraded (atomic_write-only) plugin would NOT raise.
        # (The V5-2 built-in parity anchor was removed in AG Wave 2 — V5-3 deleted the
        # built-in; the CAS bite is now pinned against the literal expectation below.)
        self._assert_write_cas_bites(self._make_plugin_backend())

    def test_plugin_advertises_the_vault_contract(self) -> None:
        plugin = self._make_plugin_backend()
        # Absolute pin: the vault's real synced/multi-writer profile, not the
        # device-local all-False floor. A `write` degraded to `atomic_write`-only
        # (dropping the CAS) reds the bite above; downgrading the advertisement to
        # dodge it reds these literals. (Pre-V5-3 this was a plugin↔built-in parity
        # check; the built-in is gone, so it pins literals directly.)
        self.assertTrue(
            plugin.capabilities.concurrent_writers,
            "the vault plugin must declare concurrent_writers (the mutex makes N writers safe)",
        )
        self.assertEqual(
            plugin.conflict_strategy,
            "whole-file",
            "the vault plugin must name the GDrive whole-file conflict strategy, not the 'none' floor",
        )


if __name__ == "__main__":
    unittest.main()
