#!/usr/bin/env python3
"""Bridge to agentm's memory-recall + forward-learning engines, read/discovery-
only (crickets wave-c-research).

Locates agentm's harness/skills/memory/scripts/ dir via the same path-fallback
convention as src/diagnostics/scripts/agentm_bridge.py, then file-path-loads
recall.py (idea-search) and forward_learning.py (learn-forward,
PLAN-wave-c-research-forward-learning task 1) so each primitive can call
agentm's real engines in-process. Absent agentm -> graceful-skip
(query_semantic returns []; load_forward_learning_module and
run_forward_learning return None), never raises.

Deliberately narrower than diagnostics' bridge: this module never resolves or
loads agentm's save.py directly -- forward_learning.py's own writes (the
watchlist its watchlist_root() resolves, and the watermark cache in agentm's
engine state dir) already route through agentm's save/write primitives
internally; this bridge adds no new write path of its own.

The loaded modules bare-import their siblings, and crickets ships modules under
some of the same names (the wiki plugin's `vault_layout`). The research CLIs
each run in a process of their own, but a shared process such as the unittest
run can already hold one. Every load of and call into agentm goes through
_agentm_names, which keeps such a module from reaching agentm.
"""
from __future__ import annotations

import contextlib
import importlib.util
import os
import sys
from pathlib import Path

_MEMORY_SCRIPTS_REL = Path("harness") / "skills" / "memory" / "scripts"

_recall_module = None
_loaded = False

_forward_learning_module = None
_fl_loaded = False

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


def _find_memory_scripts_dir() -> "Path | None":
    for candidate in _candidate_dirs():
        if (candidate / "recall.py").is_file():
            return candidate
    return None


def _origin_dir(module) -> "Path | None":
    f = getattr(module, "__file__", None)
    return Path(f).resolve().parent if f else None


@contextlib.contextmanager
def _agentm_names(scripts_dir: Path):
    # agentm's scripts bare-import their siblings, at module level and inside
    # functions alike, and a bare import returns whatever sys.modules holds
    # under that name, else the first match on sys.path. agentm's imports are
    # not ours to rename (idea_search.py's _load_sibling dodges the same
    # collision with a private name), so for the length of the block agentm's
    # scripts dir goes first on sys.path, a module held under one of its script
    # names but loaded from another file is set aside, and agentm's own copy
    # from an earlier block takes the name. Afterwards the set-aside modules go
    # back, and agentm's copies are kept, so a call gets the same module its
    # load bound rather than a second copy. A dir that was not on sys.path
    # stays there, where agentm's scripts put it themselves.
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


def load_recall_module():
    """Return agentm's recall module, loaded once and cached. None if agentm
    is unresolvable (graceful-skip, not an error)."""
    global _recall_module, _loaded
    if _loaded:
        return _recall_module
    _loaded = True
    scripts_dir = _find_memory_scripts_dir()
    if scripts_dir is None:
        _recall_module = None
        return None
    _recall_module = _load_module("research_recall_bridge", scripts_dir / "recall.py")
    return _recall_module


def query_semantic(vault: Path, query_text: str, *, filter_expr: "str | None" = None, k: int = 5) -> list:
    """Run agentm's hybrid recall query. [] if agentm is unresolvable."""
    module = load_recall_module()
    if module is None:
        return []
    return _call(module, "query", vault=vault, query_text=query_text, filter_expr=filter_expr, k=k)


def load_forward_learning_module():
    """Return agentm's forward_learning module (PLAN-wave-e-experience task
    1's approved-source pipeline), loaded once and cached. None if agentm is
    unresolvable (graceful-skip, not an error) -- same posture as
    load_recall_module. Lives in the same scripts dir as recall.py, so the
    same resolver applies unchanged."""
    global _forward_learning_module, _fl_loaded
    if _fl_loaded:
        return _forward_learning_module
    _fl_loaded = True
    scripts_dir = _find_memory_scripts_dir()
    if scripts_dir is None:
        _forward_learning_module = None
        return None
    _forward_learning_module = _load_module("research_forward_learning_bridge", scripts_dir / "forward_learning.py")
    return _forward_learning_module


def run_forward_learning(vault: Path, **kwargs):
    """Run one scan through agentm's run_forward_learning(), `kwargs` passed
    straight through. None if agentm is unresolvable."""
    module = load_forward_learning_module()
    if module is None:
        return None
    return _call(module, "run_forward_learning", vault, **kwargs)


def _reset_cache_for_tests() -> None:
    """Test-only: clear the module-level cache between isolated test cases."""
    global _recall_module, _loaded, _forward_learning_module, _fl_loaded
    _recall_module = None
    _loaded = False
    _forward_learning_module = None
    _fl_loaded = False
    _agentm_siblings.clear()
