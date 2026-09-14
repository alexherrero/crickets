#!/usr/bin/env python3
"""Bridge to agentm's memory-recall + forward-learning engines, read/discovery-
only (crickets wave-c-research).

Locates agentm's harness/skills/memory/scripts/ dir via the same path-fallback
convention as src/diagnostics/scripts/agentm_bridge.py, then file-path-loads
recall.py (idea-search) and forward_learning.py (learn-forward,
PLAN-wave-c-research-forward-learning task 1) so each primitive can call
agentm's real engines in-process. Absent agentm -> graceful-skip
(query_semantic returns []; load_forward_learning_module returns None),
never raises.

Deliberately narrower than diagnostics' bridge: this module never resolves or
loads agentm's save.py directly -- forward_learning.py's own writes (the
watchlist its watchlist_root() resolves, and the watermark cache in agentm's
engine state dir) already route through agentm's save/write primitives
internally; this bridge adds no new write path of its own.

The loaded modules bare-import their siblings, and crickets ships modules under
some of the same names (the wiki plugin's `vault_layout`). The research CLIs
each run in a process of their own, but a shared process such as the unittest
run can already hold one; _load_module keeps it from reaching agentm.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

_MEMORY_SCRIPTS_REL = Path("harness") / "skills" / "memory" / "scripts"

_recall_module = None
_loaded = False

_forward_learning_module = None
_fl_loaded = False


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


def _set_aside_shadowing_modules(scripts_dir: Path) -> dict:
    """Take out of sys.modules, and return, every module held under the name
    of a script in `scripts_dir` that was loaded from some other file."""
    set_aside = {}
    for name in sys.modules.keys() & {p.stem for p in scripts_dir.glob("*.py")}:
        f = getattr(sys.modules[name], "__file__", None)
        if f and Path(f).resolve().parent != scripts_dir:
            set_aside[name] = sys.modules.pop(name)
    return set_aside


def _load_module(name: str, path: Path):
    # agentm's scripts bare-import their siblings (`import vault_layout`). A
    # bare import returns whatever sys.modules already holds under that name,
    # else the first match on sys.path, and crickets ships modules under some
    # of the same names: the wiki plugin's vault_layout.py has a different
    # API. A process that loaded one of those first would hand it to agentm.
    # idea_search.py's _load_sibling sidesteps this kind of collision with a
    # private name, but agentm's imports are not ours to rename. So for the
    # length of the load, agentm's scripts dir goes first on sys.path and any
    # same-named module from elsewhere is set aside; afterwards those modules
    # go back, so the code that loaded them keeps them. This covers module
    # execution only: a bare import agentm makes inside a function runs later,
    # against the restored modules.
    scripts_dir = path.resolve().parent
    entry = str(scripts_dir)
    was_on_path = entry in sys.path
    set_aside = _set_aside_shadowing_modules(scripts_dir)
    sys.path.insert(0, entry)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        # agentm's scripts put their dir on sys.path themselves and import from
        # it later, so the entry stays -- unless it was already there, in which
        # case only the copy inserted above comes out.
        if was_on_path:
            sys.path.remove(entry)
        sys.modules.update(set_aside)
    return module


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
    return module.query(vault=vault, query_text=query_text, filter_expr=filter_expr, k=k)


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


def _reset_cache_for_tests() -> None:
    """Test-only: clear the module-level cache between isolated test cases."""
    global _recall_module, _loaded, _forward_learning_module, _fl_loaded
    _recall_module = None
    _loaded = False
    _forward_learning_module = None
    _fl_loaded = False
