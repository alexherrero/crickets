#!/usr/bin/env python3
"""doctor_vault — read-only health check for the obsidian-vault backing plugin (V5-2 task 6).

The operator-facing diagnostic the `vault-doctor` skill drives. It answers, in one
read-only pass, the three questions that tell an operator the re-homed vault
backend is wired up and healthy (the design's plugin `doctor` surface, §6):

  1. **vault-path** — the configured ``vault_path`` resolves to a *real*
     MemoryVault (the ``vault_probe`` shape: ``_meta/repos.json`` or a
     ``personal-private/`` dir), recovering a nested ``Obsidian/AgentMemory`` via
     its parent the same way the installer does.
  2. **backend** — selection resolves the ``vault`` protocol to *this* plugin
     (not the kernel built-in, not a silent demotion to device-local), routed
     through the engine's own read-only ``storage_preview`` so this row can never
     drift from what the engine would actually do at runtime.
  3. **conflicts** — the conflict-merger detector finds no unresolved GDrive/
     DriveFS sync-conflict files in the vault (or the ``lost_and_found/`` dump).

**Read-only by contract.** It never constructs a backend (construction mkdirs the
vault root), never writes the vault or the engine config (LC-4 — ``vault_path`` is
read in place), and mutates nothing. ``main`` exits 1 only on a ``FAIL`` row
(mirroring the kernel ``backend_selection --doctor``); ``WARN`` and ``OK`` exit 0 —
a conflict file or an unreachable engine is not an install failure.

**Present-engine pattern (LC-3).** The vault backend only ever runs under a
present agentm engine, so the checks that need the kernel (the ``vault_probe``
shape test, ``storage_preview``, the ``_conflict_family`` classifier
``vault_conflicts`` imports) **locate** the engine ``scripts/`` dir and import from
it — never a vendored copy. When no engine is reachable (a crickets-only checkout,
CI), those rows degrade to a ``WARN`` "engine not reachable — cannot verify" rather
than crashing: the diagnostic must never blow up.

**Antigravity coverage.** On Claude Code the ``conflict-merger-session-start`` hook
surfaces conflict files automatically at session boot; Antigravity has no
``SessionStart`` event, so the nudge does not fire there. This doctor (check 3) is
the reachable substitute — running it (via the ``vault-doctor`` skill) gives the
Antigravity operator the same detection on demand. Detection is not lost on AG;
only the automatic nudge is.

    doctor_vault.py [--vault-path <dir>] [--no-lost-and-found]
    # stdout: one [OK]/[WARN]/[FAIL] line per check; exit 1 iff any FAIL

Stdlib-only; mirrors the pure-core shape of its sibling diagnostics
(``diagnose()`` returns data; ``main()`` resolves inputs, formats, prints).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import NamedTuple, Optional

# Status tokens — the bracketed form (`[OK]` / `[WARN]` / `[FAIL]`) is what the
# skill / a doctor aggregator greps per row, matching the kernel storage doctor.
OK = "OK"
WARN = "WARN"
FAIL = "FAIL"

# This module ships in the plugin's scripts/ dir, beside vault_conflicts.py — so
# its own parent IS the plugin scripts root when running as an installed plugin.
_HERE = Path(__file__).resolve().parent

_PROTOCOL = "vault"


class Check(NamedTuple):
    """One classified doctor row (mutually exclusive status; printed verbatim)."""

    name: str       # short check id: "vault-path" | "backend" | "conflicts"
    status: str     # OK | WARN | FAIL
    detail: str     # one-line operator-facing summary


# ── locating the present engine + this plugin ────────────────────────────────

def locate_kernel_scripts() -> Optional[Path]:
    """The present agentm engine's ``scripts/`` dir, or None when none is reachable.

    Order (first hit wins): ``$AGENTM_SCRIPTS`` override → ``~/Antigravity/agentm/
    scripts`` → the cwd-relative sibling ``../agentm/scripts`` / ``../../agentm/
    scripts``. Mirrors the conflict-merger hook's search so the two share one
    present-engine contract. A dir only counts if it carries ``harness_memory.py``
    (the engine module ``vault_conflicts`` / ``backend_selection`` import from).
    """
    candidates: list[Path] = []
    override = os.environ.get("AGENTM_SCRIPTS")
    if override:
        candidates.append(Path(override).expanduser())
    candidates += [
        Path.home() / "Antigravity" / "agentm" / "scripts",
        Path("../agentm/scripts"),
        Path("../../agentm/scripts"),
    ]
    for cand in candidates:
        try:
            if (cand / "harness_memory.py").is_file():
                return cand.resolve()
        except OSError:
            continue
    return None


def _kernel_on_path(kernel_scripts: Optional[Path]) -> bool:
    """Put the engine ``scripts/`` dir on ``sys.path`` (idempotent). False if absent."""
    if kernel_scripts is None:
        return False
    p = str(kernel_scripts)
    if p not in sys.path:
        sys.path.insert(0, p)
    return True


def _load_vault_conflicts(plugin_scripts: Path):
    """Import the plugin's ``vault_conflicts`` module by file location.

    It does ``from harness_memory import _conflict_family`` at load (LC-3 present-
    engine import), so the caller must have put the engine ``scripts/`` dir on
    ``sys.path`` first. Returns the module, or None if it cannot load.
    """
    src = plugin_scripts / "vault_conflicts.py"
    if not src.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location("vault_conflicts", src)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    except Exception:  # noqa: BLE001 — a doctor never crashes on an import failure
        return None


# ── the three checks (pure: return data, print/mutate nothing) ───────────────

def _check_vault_path(
    vault_path: Optional[str], kernel_scripts: Optional[Path]
) -> tuple[Check, Optional[Path]]:
    """Resolve + classify the configured vault path. Returns the row + the refined
    vault root (None when there is no usable directory to scan downstream)."""
    if not vault_path:
        return (
            Check(
                "vault-path",
                FAIL,
                "no vault_path configured — set it (agentm_config --vault-path "
                "<dir>) or export MEMORY_VAULT_PATH",
            ),
            None,
        )
    root = Path(vault_path)
    if not root.is_dir():
        return (
            Check("vault-path", FAIL, f"vault_path {root} does not exist on disk"),
            None,
        )
    if not _kernel_on_path(kernel_scripts):
        # No engine to import vault_probe from — the dir exists, but we cannot
        # certify it has MemoryVault shape. Hand the existing dir downstream.
        return (
            Check(
                "vault-path",
                WARN,
                f"vault_path {root} exists, but no agentm engine is reachable to "
                "confirm MemoryVault shape (vault_probe) — install/locate agentm",
            ),
            root,
        )
    try:
        import vault_probe  # noqa: E402 — only importable once kernel is on path

        refined = Path(vault_probe.find_nested_vault(str(root)))
        if vault_probe._has_vault_shape(refined):
            extra = f" → {refined}" if refined != root else ""
            return (
                Check(
                    "vault-path",
                    OK,
                    f"vault_path resolves to a real MemoryVault: {root}{extra}",
                ),
                refined,
            )
        return (
            Check(
                "vault-path",
                WARN,
                f"vault_path {root} exists but lacks MemoryVault shape "
                "(no _meta/repos.json or personal-private/) — is it the right dir?",
            ),
            refined,
        )
    except Exception as exc:  # noqa: BLE001 — degrade, never crash the diagnostic
        return (
            Check("vault-path", WARN, f"could not run vault_probe on {root}: {exc}"),
            root,
        )


def _check_backend(
    kernel_scripts: Optional[Path],
    plugin_scripts: Path,
    install_prefix: Optional[Path],
) -> Check:
    """Classify whether selection resolves ``vault`` to *this* plugin (read-only)."""
    if not _kernel_on_path(kernel_scripts):
        return Check(
            "backend",
            WARN,
            "no agentm engine reachable — cannot confirm the vault backend "
            "selection (the backend runs only under a present engine)",
        )
    try:
        import backend_selection  # noqa: E402 — importable once kernel is on path

        preview = backend_selection.storage_preview(
            install_prefix=install_prefix,
            vault_plugin_scripts=plugin_scripts,
        )
    except Exception as exc:  # noqa: BLE001 — degrade, never crash
        return Check("backend", WARN, f"storage preview unavailable: {exc}")

    if preview.status == "fail":
        # The engine would refuse at runtime — surface its exact message.
        return Check("backend", FAIL, preview.line)
    if preview.protocol != _PROTOCOL:
        return Check(
            "backend",
            WARN,
            f"selected storage backend is {preview.protocol!r}, not 'vault' — "
            "the obsidian-vault plugin is installed but not the active backend "
            "(set storage.backend=vault to route through it)",
        )
    if preview.status == "warn":
        return Check("backend", WARN, preview.line)
    return Check(
        "backend",
        OK,
        "selection resolves 'vault' to the obsidian-vault plugin "
        "(not the built-in, not device-local)",
    )


def _check_conflicts(
    vault_root: Optional[Path],
    kernel_scripts: Optional[Path],
    plugin_scripts: Path,
    *,
    include_lost_and_found: bool,
) -> Check:
    """Run the conflict-merger detector over the vault; classify the result."""
    if vault_root is None:
        return Check(
            "conflicts",
            WARN,
            "skipped — no usable vault directory to scan (see the vault-path row)",
        )
    if not _kernel_on_path(kernel_scripts):
        return Check(
            "conflicts",
            WARN,
            "no agentm engine reachable — cannot import the _conflict_family "
            "classifier the detector composes (LC-3 present-engine import)",
        )
    vc = _load_vault_conflicts(plugin_scripts)
    if vc is None:
        return Check(
            "conflicts",
            WARN,
            f"could not load vault_conflicts.py from {plugin_scripts} — "
            "is the plugin payload intact?",
        )
    try:
        laf = vc.default_lost_and_found_root() if include_lost_and_found else None
        conflicts = vc.detect_conflict_files(vault_root, lost_and_found_root=laf)
    except Exception as exc:  # noqa: BLE001 — degrade, never crash
        return Check("conflicts", WARN, f"conflict sweep failed: {exc}")

    if not conflicts:
        return Check(
            "conflicts", OK, "no GDrive/DriveFS sync-conflict files detected"
        )
    n_laf = sum(1 for e in conflicts if e.get("source") == "lost_and_found")
    n_vault = len(conflicts) - n_laf
    where = f"{n_vault} in vault" + (f", {n_laf} in DriveFS lost_and_found" if n_laf else "")
    return Check(
        "conflicts",
        WARN,
        f"{len(conflicts)} conflict/duplicate file(s) detected ({where}) — "
        "triage by hand in Obsidian (the merger surfaces them; it does not auto-merge)",
    )


def diagnose(
    *,
    vault_path: Optional[str],
    kernel_scripts: Optional[Path],
    plugin_scripts: Optional[Path] = None,
    install_prefix: Optional[Path] = None,
    include_lost_and_found: bool = True,
) -> list[Check]:
    """Run all three read-only checks and return their rows, in display order.

    Every argument is injectable so the suite can drive the checks hermetically
    against a synthetic vault + a located kernel, never the operator's real store.
    ``plugin_scripts`` defaults to this module's own dir (the installed-plugin
    layout: ``doctor_vault.py`` beside ``vault_conflicts.py``).
    """
    plugin_scripts = plugin_scripts or _HERE
    vp_row, vault_root = _check_vault_path(vault_path, kernel_scripts)
    backend_row = _check_backend(kernel_scripts, plugin_scripts, install_prefix)
    conflict_row = _check_conflicts(
        vault_root,
        kernel_scripts,
        plugin_scripts,
        include_lost_and_found=include_lost_and_found,
    )
    return [vp_row, backend_row, conflict_row]


# ── CLI (resolves inputs, formats, prints; exit 1 iff any FAIL) ──────────────

def _resolve_vault_path(install_prefix: Optional[Path]) -> Optional[str]:
    """Resolve the vault path the way the engine does: ``$MEMORY_VAULT_PATH`` →
    the on-device config's ``vault_path`` → None. Read-only (LC-4): never writes.

    Reads the config directly (a tiny JSON load) rather than importing the engine,
    so the path resolves even when no engine is reachable — the hook uses the same
    inline read for the same reason (Claude Code does not inject MEMORY_VAULT_PATH
    into a user-scope hook/skill env).
    """
    env = os.environ.get("MEMORY_VAULT_PATH")
    if env:
        return env
    prefix = install_prefix or Path(
        os.environ.get("AGENTM_INSTALL_PREFIX", "").strip() or (Path.home() / ".claude")
    )
    cfg = Path(prefix) / ".agentm-config.json"
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get("vault_path")
    return value or None


def _format(checks: list[Check]) -> str:
    lines = ["[doctor_vault] obsidian-vault backing-plugin health:"]
    width = max(len(c.name) for c in checks)
    for c in checks:
        lines.append(f"  [{c.status}] {c.name:<{width}}  {c.detail}")
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="doctor_vault.py",
        description="Read-only health check for the obsidian-vault backing plugin: "
        "vault-path shape, backend selection, and GDrive conflict files.",
    )
    p.add_argument(
        "--vault-path",
        default=None,
        help="vault root to check (default: $MEMORY_VAULT_PATH or the configured "
        "vault_path)",
    )
    p.add_argument(
        "--no-lost-and-found",
        action="store_true",
        help="skip the DriveFS lost_and_found/ sweep (scan only the vault tree)",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    ns = _build_parser().parse_args(argv)
    vault_path = ns.vault_path or _resolve_vault_path(None)
    checks = diagnose(
        vault_path=vault_path,
        kernel_scripts=locate_kernel_scripts(),
        include_lost_and_found=not ns.no_lost_and_found,
    )
    sys.stdout.write(_format(checks))
    return 1 if any(c.status == FAIL for c in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
