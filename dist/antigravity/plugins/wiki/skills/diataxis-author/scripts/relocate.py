#!/usr/bin/env python3
# relocate.py — _always-load -> on-demand _global relocation for diataxis-author
# (wiki-maintenance part 3/5, style-learning-loop, task 4).
#
# Moves the operator's GLOBAL wiki/Diataxis conventions out of the always-load
# tier (`<vault>/personal/_always-load/diataxis-*.md`, injected into
# EVERY session's context) into the on-demand global store the resolver reads
# (`<vault>/projects/_global/wiki-style/*.md`) — so they load only when authoring.
#
# Touches the operator's LIVE VAULT, so it mirrors agentm's migrate-harness-to-vault
# discipline: PREVIEW-FIRST (--preview prints WOULD: lines, mutates nothing),
# REVERSIBLE (--rollback reverses a prior relocation via a manifest), conflict-safe
# (byte-compare; never clobber a differing dest), and CLEANUP only after a
# byte-identical verify (--cleanup, gated by --yes / TTY confirm). Idempotent.
#
# `_global` is a reserved cross-project pseudo-project under the top-level
# `projects/` root (NOT under personal/ — that root is personal,
# non-project-keyed data; its `_always-load/` subset is the always-injected
# globals). See agentm ADR 0010 (vault internal taxonomy). Stdlib-only.

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# Default source set: the global wiki/Diataxis conventions in always-load.
_DEFAULT_SOURCE_GLOB = "diataxis-*.md"
# Manifest (a dotfile, NOT *.md → invisible to the resolver's glob) recording
# which filenames were relocated, so --rollback reverses precisely (and never
# touches lessons captured directly into _global by the capture loop).
_MANIFEST_NAME = ".relocated-from-always-load"


@dataclass
class Action:
    """One planned/performed step. `verb` is the disposition; tests assert on it."""

    verb: str   # WOULD-RELOCATE | RELOCATED | SKIP-IDENTICAL | CONFLICT
                # | WOULD-CLEANUP | CLEANED | SKIP-CLEANUP
                # | WOULD-ROLLBACK | ROLLED-BACK
    name: str
    note: str = ""


def _resolve_vault(arg_path: str | None) -> Path | None:
    if arg_path:
        return Path(arg_path).expanduser()
    env = os.environ.get("MEMORY_VAULT_PATH", "").strip()
    return Path(env).expanduser() if env else None


def _always_load_dir(vault: Path) -> Path:
    return vault / "personal" / "_always-load"


def _global_wiki_style_dir(vault: Path) -> Path:
    return vault / "projects" / "_global" / "wiki-style"


def _manifest_path(vault: Path) -> Path:
    return _global_wiki_style_dir(vault) / _MANIFEST_NAME


def _identical(a: Path, b: Path) -> bool:
    """Byte-compare two files (the `cmp -s` of the mirror). Missing -> not identical."""
    try:
        return a.is_file() and b.is_file() and a.read_bytes() == b.read_bytes()
    except OSError:
        return False


def _read_manifest(vault: Path) -> list:
    p = _manifest_path(vault)
    if not p.is_file():
        return []
    try:
        return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError:
        return []


def _write_manifest(vault: Path, names: list) -> None:
    p = _manifest_path(vault)
    if not names:
        # Clear the manifest entirely when nothing remains relocated.
        if p.exists():
            p.unlink()
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    # Stable order so re-runs are deterministic.
    p.write_text("\n".join(sorted(set(names))) + "\n", encoding="utf-8")


def relocate(
    vault: Path,
    *,
    source_glob: str = _DEFAULT_SOURCE_GLOB,
    preview: bool = False,
    cleanup: bool = False,
    assume_yes: bool = False,
) -> list:
    """Copy `_always-load/<source_glob>` -> `projects/_global/wiki-style/`.

    Conflict-safe (never overwrites a differing dest), idempotent (byte-identical
    dest -> skip), records relocated filenames in the manifest. `--cleanup` then
    deletes each successfully-relocated source AFTER a byte-identical verify, but
    only when `assume_yes` (or it's a no-op) — never silently destroys the source.
    """
    src_dir = _always_load_dir(vault)
    dest_dir = _global_wiki_style_dir(vault)
    actions: list = []
    relocated_now: list = []
    for src in sorted(src_dir.glob(source_glob)) if src_dir.is_dir() else []:
        dest = dest_dir / src.name
        if dest.exists():
            if _identical(src, dest):
                actions.append(Action("SKIP-IDENTICAL", src.name, "dest already up to date"))
                relocated_now.append(src.name)  # idempotent: keep it manifested
            else:
                actions.append(Action("CONFLICT", src.name,
                                       "dest exists and differs; not overwriting"))
            continue
        if preview:
            actions.append(Action("WOULD-RELOCATE", src.name, f"-> {dest}"))
            continue
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        actions.append(Action("RELOCATED", src.name, f"-> {dest}"))
        relocated_now.append(src.name)

    # Cleanup: delete sources whose dest is byte-identical (verified), gated.
    if cleanup:
        for name in list(relocated_now):
            src = src_dir / name
            dest = dest_dir / name
            if not src.exists():
                continue
            if not _identical(src, dest):
                actions.append(Action("SKIP-CLEANUP", name, "dest not byte-identical; keeping source"))
                continue
            if preview:
                actions.append(Action("WOULD-CLEANUP", name, f"delete {src}"))
                continue
            if not assume_yes:
                actions.append(Action("SKIP-CLEANUP", name, "needs --yes to delete source"))
                continue
            src.unlink()
            actions.append(Action("CLEANED", name, f"deleted {src}"))

    if not preview and relocated_now:
        _write_manifest(vault, _read_manifest(vault) + relocated_now)
    return actions


def rollback(vault: Path, *, preview: bool = False) -> list:
    """Reverse a prior relocation, precisely, using the manifest.

    For each recorded filename: restore the source from the relocated copy (if the
    source was cleaned up), remove the relocated copy, drop it from the manifest.
    Lessons captured directly into `_global` (never manifested) are untouched."""
    src_dir = _always_load_dir(vault)
    dest_dir = _global_wiki_style_dir(vault)
    actions: list = []
    manifest = _read_manifest(vault)
    remaining: list = list(manifest)
    for name in manifest:
        src = src_dir / name
        dest = dest_dir / name
        if not dest.exists():
            # Nothing to reverse for this entry; just drop it from the manifest.
            if not preview:
                remaining.remove(name)
            actions.append(Action("ROLLED-BACK", name, "relocated copy already gone"))
            continue
        if preview:
            restore = "" if src.exists() else f"restore {src}; "
            actions.append(Action("WOULD-ROLLBACK", name, f"{restore}remove {dest}"))
            continue
        if not src.exists():
            src_dir.mkdir(parents=True, exist_ok=True)
            src.write_bytes(dest.read_bytes())
        dest.unlink()
        remaining.remove(name)
        actions.append(Action("ROLLED-BACK", name, f"restored -> {src}"))
    if not preview:
        _write_manifest(vault, remaining)
    return actions


# ── CLI ──────────────────────────────────────────────────────────────────────

def _print_actions(actions: list) -> None:
    if not actions:
        print("relocate: nothing to do (no matching _always-load/ conventions).")
        return
    for a in actions:
        note = f"  ({a.note})" if a.note else ""
        print(f"{a.verb}: {a.name}{note}")


def main(argv: list | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="diataxis-relocate",
        description="Relocate global wiki conventions from _always-load to the on-demand _global store.")
    p.add_argument("--vault-path", default=None, help="vault root (default: $MEMORY_VAULT_PATH)")
    p.add_argument("--source-glob", default=_DEFAULT_SOURCE_GLOB,
                   help=f"which _always-load files to relocate (default: {_DEFAULT_SOURCE_GLOB})")
    p.add_argument("--preview", action="store_true", help="dry-run: print WOULD: lines, mutate nothing")
    p.add_argument("--cleanup", action="store_true",
                   help="delete each source after a byte-identical verify (needs --yes)")
    p.add_argument("--rollback", action="store_true", help="reverse a prior relocation (via the manifest)")
    p.add_argument("--yes", action="store_true", help="confirm destructive --cleanup deletes")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    vault = _resolve_vault(args.vault_path)
    if vault is None:
        print("relocate: no vault (pass --vault-path or set MEMORY_VAULT_PATH)", file=sys.stderr)
        return 1
    if not vault.is_dir():
        print(f"relocate: vault path is not a directory: {vault}", file=sys.stderr)
        return 1

    if args.rollback:
        actions = rollback(vault, preview=args.preview)
    else:
        actions = relocate(vault, source_glob=args.source_glob, preview=args.preview,
                            cleanup=args.cleanup, assume_yes=args.yes)
    _print_actions(actions)
    if any(a.verb == "CONFLICT" for a in actions):
        print("relocate: conflicts found — resolve manually; nothing overwritten.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
