#!/usr/bin/env python3
"""vault_conflicts — GDrive/DriveFS sync-conflict detection for the obsidian-vault
backing plugin.

Re-homed out of the agentm kernel's ``harness_memory.py`` (V5-2 task 2): the
*vault-specific* conflict-merger machinery — the recursive sweep + the DriveFS
``lost_and_found/`` scan + the operator-canonical base-path inference — belongs
beside the backend it serves, not in a storage-agnostic kernel. The carried-out
form is the ``conflict-merger-session-start`` hook in this plugin, which walks
``detect_conflict_files`` at SessionStart.

LC-1 — the function bodies travel **byte-faithful** from the proven kernel code;
this is a move, not a reimplementation.

LC-3 — the pure filename classifier ``_conflict_family`` is **not** moved. It is a
storage-agnostic primitive the kernel's own named-plan dashboard
(``queue_status_lite.py``) still consumes (it must work even when this plugin is
absent), so it stays kernel-side and is **imported** here. The plugin runs only
under a present engine, so the single canonical classifier stays single — no
vendored copy, no parity gate (the same reasoning that imports ``vault_lock``).
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

# LC-3: the conflict-copy filename classifier stays in the kernel (shared with
# queue_status_lite.py); import it rather than vendor it. Resolves via the engine
# scripts dir the hook/loader puts on sys.path — present-engine-only by contract.
from harness_memory import _conflict_family


def _infer_conflict_base_path(conflict: Path) -> Path:
    """Strip whichever conflict/duplicate marker(s) a filename carries to derive
    the operator-canonical base path (same parent, cleaned basename).

    Examples:
        "PLAN (conflicted copy 2026-05-27).md"           → "PLAN.md"
        "PLAN (conflicted copy 2026-05-27) - Mac.md"     → "PLAN.md"
        "PLAN (conflicted copy 2026-05-27 from iPad).md" → "PLAN.md"
        "PLAN [Conflict].md"                             → "PLAN.md"
        "PLAN [Conflict 2].md"                           → "PLAN.md"
        "Copy of PLAN.md"                                → "PLAN.md"
        "PLAN (1).md"                                    → "PLAN.md"

    Each strip is a no-op when its marker is absent, so the rules compose:
    "Copy of PLAN (1).md" reduces to "PLAN.md". Best-effort — a name carrying no
    recognizable marker returns unchanged.
    """
    name = conflict.name
    # 1. GDrive "(conflicted copy …)" + optional "- <device>" tail.
    name = re.sub(
        r"\s*\(conflicted copy[^)]*\)(\s*-\s*[^.]+)?", "", name, flags=re.IGNORECASE,
    )
    # 2. Bracketed "[Conflict]" / "[Conflict N]" marker.
    name = re.sub(r"\s*\[conflict[^\]]*\]", "", name, flags=re.IGNORECASE)
    # 3. Trailing " (N)" numbered-duplicate, immediately before the extension.
    name = re.sub(r"\s+\(\d+\)(?=(\.[^.]+)?$)", "", name)
    # 4. Leading "Copy of ".
    name = re.sub(r"^copy of\s+", "", name, flags=re.IGNORECASE)
    return conflict.parent / name


def default_lost_and_found_root() -> Optional[Path]:
    """The platform DriveFS `lost_and_found/` directory, or None if absent.

    DriveFS dumps files it could not re-home into a `lost_and_found/` folder and
    raises no notification. The folder lives under the platform's app-data root:

        macOS    ~/Library/Application Support/Google/DriveFS/lost_and_found/
        Windows  %LOCALAPPDATA%\\Google\\DriveFS\\lost_and_found\\

    Both candidates are probed (they are mutually exclusive on a real machine)
    and the first that exists is returned, so the operator's dual macOS+Windows
    setup gets the sweep on *either* OS rather than macOS only (audit ML1). A
    machine with no DriveFS folder — Linux, or DriveFS not installed — gets None
    and simply no lost_and_found sweep. macOS resolves via `Path.home()` (honors
    `$HOME`) and Windows via `%LOCALAPPDATA%` (falling back to `~/AppData/Local`),
    so a redirected-env hook test stays hermetic against the real machine.
    """
    home = Path.home()
    candidates = [
        # macOS app-support tree.
        home / "Library" / "Application Support" / "Google" / "DriveFS" / "lost_and_found",
    ]
    # Windows: DriveFS lives under %LOCALAPPDATA% (normally USERPROFILE\AppData\
    # Local). Honor the env var for hermeticity; fall back to the conventional
    # location when it is unset.
    local_appdata = os.environ.get("LOCALAPPDATA")
    win_base = Path(local_appdata) if local_appdata else home / "AppData" / "Local"
    candidates.append(win_base / "Google" / "DriveFS" / "lost_and_found")

    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def detect_conflict_files(
    vault_root: Path, *, lost_and_found_root: Optional[Path] = None,
) -> list[dict]:
    """Walk `vault_root` (and optionally a DriveFS `lost_and_found/` root) for
    conflict/duplicate files across all four marker families.

    Returns a list of dicts:
        [{"conflict": <conflict-file-path>,
          "base":     <inferred-base-file-path>,   # best-effort
          "rel":      <path relative to its own scan root>,
          "source":   "vault" | "lost_and_found"}, ...]

    The `base` field is the operator-canonical filename the conflict pairs with
    (marker stripped). For `lost_and_found` entries base inference is best-effort
    (the file is already orphaned out of its home directory).

    `lost_and_found_root` is opt-in: pass `default_lost_and_found_root()` (the
    hook does) to include the DriveFS dump, or leave it None to sweep only the
    vault. Keeping it opt-in keeps unit tests hermetic — they never touch the
    real `~/Library/.../lost_and_found`.

    The dispatcher hook (conflict-merger-session-start) walks this list at
    SessionStart and surfaces an operator-facing notice per entry.

    Detection is best-effort by design: GDrive may change a format without
    notice, so false-negatives are acceptable (the operator still finds the file
    in Obsidian). The numbered "(N)" family is guarded against year-like false-
    positives by requiring the de-numbered base to co-exist.
    """
    out: list[dict] = []

    vault_root = Path(vault_root)
    if vault_root.is_dir():
        # rglob is recursive, depth-first. Safe for vault sizes <10k files.
        for conflict in vault_root.rglob("*"):
            if not conflict.is_file():
                continue
            family = _conflict_family(conflict.name)
            if family is None:
                continue
            base = _infer_conflict_base_path(conflict)
            # Numbered "(N)" duplicates are real collisions only when the de-
            # numbered base co-exists — otherwise "report (2026).md" would be
            # flagged as a phantom conflict.
            if family == "numbered" and not base.exists():
                continue
            out.append({
                "conflict": conflict,
                "base": base,
                "rel": conflict.relative_to(vault_root),
                "source": "vault",
            })

    if lost_and_found_root is not None:
        laf = Path(lost_and_found_root)
        if laf.is_dir():
            for orphan in laf.rglob("*"):
                if not orphan.is_file():
                    continue
                # Every file DriveFS dumps here is orphaned — surface them all
                # for triage (no marker filter). Base inference is best-effort.
                out.append({
                    "conflict": orphan,
                    "base": _infer_conflict_base_path(orphan),
                    "rel": orphan.relative_to(laf),
                    "source": "lost_and_found",
                })

    return out
