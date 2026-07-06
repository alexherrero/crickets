#!/usr/bin/env python3
"""Bridge to agentm's memory-save engine, for maintenance's new memory
kinds -- `debt` (task 3) and `content-refresh-watchlist` (task 4) (crickets
wave-c-maintenance).

Locates agentm's harness/skills/memory/scripts/ dir via the same
path-fallback convention as src/diagnostics/scripts/agentm_bridge.py, then
file-path-loads save.py so maintenance's primitives can call save_entry()
in-process. Each kind is a convention over the existing engine -- no schema
change (crickets-maintenance.md) -- so this bridge only adds thin wrappers,
not a new write path.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

_MEMORY_SCRIPTS_REL = Path("harness") / "skills" / "memory" / "scripts"

_save_module = None
_save_loaded = False


def _candidate_dirs() -> list[Path]:
    here = Path(__file__).resolve().parent
    candidates = []
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    if env_dir:
        candidates.append(Path(os.path.expanduser(env_dir)))
    candidates.append(here / _MEMORY_SCRIPTS_REL)  # co-located install
    candidates.append(Path.home() / "Antigravity" / "agentm" / _MEMORY_SCRIPTS_REL)  # conventional clone
    return candidates


def _find_save_scripts_dir() -> "Path | None":
    for candidate in _candidate_dirs():
        if (candidate / "save.py").is_file():
            return candidate
    return None


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_save_module():
    """Return agentm's save module, loaded once and cached. None if agentm
    is unresolvable (graceful-skip, not an error)."""
    global _save_module, _save_loaded
    if _save_loaded:
        return _save_module
    _save_loaded = True
    scripts_dir = _find_save_scripts_dir()
    if scripts_dir is None:
        _save_module = None
        return None
    _save_module = _load_module("maintenance_save_bridge", scripts_dir / "save.py")
    return _save_module


def write_debt_entry(vault: Path, *, slug: str, body: str, group: str = "personal", tags: "list | None" = None) -> "Path | None":
    """Write a kind="debt" entry via agentm's save_entry(). Returns the
    written path, or None if an entry with this slug already exists --
    idempotent, not an error (the standing-backlog re-run guarantee)."""
    module = load_save_module()
    if module is None:
        raise RuntimeError("agentm is unresolvable -- cannot write a debt entry")
    try:
        return module.save_entry(vault, "debt", slug, body, group=group, tags=tags or [])
    except FileExistsError:
        return None


def write_content_refresh_watchlist_entry(vault: Path, *, slug: str, body: str, group: str = "personal", tags: "list | None" = None) -> "Path | None":
    """Write a kind="content-refresh-watchlist" entry via agentm's
    save_entry(). Judgment-bound drift surfaces here instead of being
    auto-edited (Locked design call). Returns the written path, or None if
    an entry with this slug already exists."""
    module = load_save_module()
    if module is None:
        raise RuntimeError("agentm is unresolvable -- cannot write a content-refresh watchlist entry")
    try:
        return module.save_entry(vault, "content-refresh-watchlist", slug, body, group=group, tags=tags or [])
    except FileExistsError:
        return None


def _reset_cache_for_tests() -> None:
    """Test-only: clear the module-level cache between isolated test cases."""
    global _save_module, _save_loaded
    _save_module = None
    _save_loaded = False
