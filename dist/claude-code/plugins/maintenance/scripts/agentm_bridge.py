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

Both writers file under agentm's own default group, `memory`. agentm files a
note under whatever group it is handed, and the `personal` group they passed
before is the memory space's name from before stage 2, so every entry landed
in a retired home.

save.py bare-imports its siblings inside functions (save_entry() imports
`fingerprint` when the caller passes none), and crickets ships modules under
some of the same names: the diagnostics plugin's fingerprint.py. Every load of
and call into agentm goes through _agentm_names, which keeps such a module from
reaching agentm in a shared process such as the unittest run.
"""
from __future__ import annotations

import contextlib
import importlib.util
import os
import sys
from pathlib import Path

_MEMORY_SCRIPTS_REL = Path("harness") / "skills" / "memory" / "scripts"

_save_module = None
_save_loaded = False

# agentm's own sibling modules by bare name, per scripts dir, kept from one
# _agentm_names block to the next.
_agentm_siblings: dict = {}


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


def _origin_dir(module) -> "Path | None":
    f = getattr(module, "__file__", None)
    return Path(f).resolve().parent if f else None


@contextlib.contextmanager
def _agentm_names(scripts_dir: Path):
    # Same mechanism as src/research/scripts/agentm_bridge.py's: for the length
    # of the block agentm's scripts dir goes first on sys.path, a module held
    # under one of its script names but loaded from another file is set aside,
    # and agentm's own copy from an earlier block takes the name. Afterwards the
    # set-aside modules go back, and agentm's copies are kept, so a call gets
    # the same module its load bound rather than a second copy. A dir that was
    # not on sys.path stays there, where agentm's scripts put it themselves.
    scripts_dir = scripts_dir.resolve()
    names = {p.stem for p in scripts_dir.glob("*.py")}
    set_aside = {
        name: sys.modules.pop(name)
        for name in names & sys.modules.keys()
        if _origin_dir(sys.modules[name]) not in (None, scripts_dir)
    }
    kept = _agentm_siblings.setdefault(scripts_dir, {})
    for name, module in kept.items():
        sys.modules.setdefault(name, module)
    entry = str(scripts_dir)
    was_on_path = entry in sys.path
    sys.path.insert(0, entry)
    try:
        yield
    finally:
        kept.update({
            name: sys.modules[name]
            for name in names & sys.modules.keys()
            if _origin_dir(sys.modules[name]) == scripts_dir
        })
        sys.modules.update(set_aside)
        if was_on_path:
            sys.path.remove(entry)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    with _agentm_names(path.parent):
        spec.loader.exec_module(module)
    return module


def _call(module, function: str, *args, **kwargs):
    # A module with no file behind it (a test's stand-in) is called as it is.
    origin = _origin_dir(module)
    with _agentm_names(origin) if origin else contextlib.nullcontext():
        return getattr(module, function)(*args, **kwargs)


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


def write_debt_entry(vault: Path, *, slug: str, body: str, group: str = "memory", tags: "list | None" = None) -> "Path | None":
    """Write a kind="debt" entry via agentm's save_entry(). Returns the
    written path, or None if an entry with this slug already exists --
    idempotent, not an error (the standing-backlog re-run guarantee)."""
    module = load_save_module()
    if module is None:
        raise RuntimeError("agentm is unresolvable -- cannot write a debt entry")
    try:
        return _call(module, "save_entry", vault, "debt", slug, body, group=group, tags=tags or [])
    except FileExistsError:
        return None


def write_content_refresh_watchlist_entry(vault: Path, *, slug: str, body: str, group: str = "memory", tags: "list | None" = None) -> "Path | None":
    """Write a kind="content-refresh-watchlist" entry via agentm's
    save_entry(). Judgment-bound drift surfaces here instead of being
    auto-edited (Locked design call). Returns the written path, or None if
    an entry with this slug already exists."""
    module = load_save_module()
    if module is None:
        raise RuntimeError("agentm is unresolvable -- cannot write a content-refresh watchlist entry")
    try:
        return _call(module, "save_entry", vault, "content-refresh-watchlist", slug, body, group=group, tags=tags or [])
    except FileExistsError:
        return None


def _reset_cache_for_tests() -> None:
    """Test-only: clear the module-level cache between isolated test cases."""
    global _save_module, _save_loaded
    _save_module = None
    _save_loaded = False
    _agentm_siblings.clear()
