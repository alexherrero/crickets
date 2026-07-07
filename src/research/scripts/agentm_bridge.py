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
loads agentm's save.py directly -- forward_learning.py's own writes (to
personal/_watchlist/ + _meta/forward-learning-cache/) already route through
agentm's save/write primitives internally; this bridge adds no new write path
of its own.
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


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
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
