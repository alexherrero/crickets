#!/usr/bin/env python3
"""Bridge to agentm's memory-recall engine (siblings-not-layers, DC-2).

Locates agentm's harness/skills/memory/scripts/ dir via the same path-fallback
convention as find_agentm_script / find_process_seam.py elsewhere in this repo,
then file-path-loads recall.py so diagnostics can call its hybrid query engine
in-process. Absent agentm -> graceful-skip (query_semantic returns []), never
raises and never hangs -- Layer-2 is a fallback, not a hard dependency.

Also bridges agentm's top-level opinion_resolver.py (a sibling dir to the
memory scripts, not the same one) so diagnostics can request the
`how-we-engineer` opinion by name (PLAN-wave-d-opinion-wiring task 1) --
same path-fallback shape, same graceful-skip-on-absence contract.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

_MEMORY_SCRIPTS_REL = Path("harness") / "skills" / "memory" / "scripts"
# agentm's top-level scripts/ dir -- where opinion_resolver.py ships, distinct
# from the memory-engine's own scripts/ dir above. Mirrors find_capability.py /
# find_governing_design.py's own AGENTM_SCRIPTS_DIR + co-located + conventional-
# clone fallback order.
_OPINION_SCRIPTS_REL = Path("scripts")

_recall_module = None
_loaded = False
_save_module = None
_save_loaded = False
_opinion_module = None
_opinion_loaded = False


def _candidate_dirs() -> list[Path]:
    here = Path(__file__).resolve().parent
    candidates = []
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    if env_dir:
        candidates.append(Path(os.path.expanduser(env_dir)))
    candidates.append(here / _MEMORY_SCRIPTS_REL)  # co-located install
    candidates.append(Path.home() / "Antigravity" / "agentm" / _MEMORY_SCRIPTS_REL)  # conventional clone
    return candidates


def _opinion_candidate_dirs() -> list[Path]:
    here = Path(__file__).resolve().parent
    candidates = []
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    if env_dir:
        candidates.append(Path(os.path.expanduser(env_dir)))
    candidates.append(here / _OPINION_SCRIPTS_REL)  # co-located install
    candidates.append(Path.home() / "Antigravity" / "agentm" / _OPINION_SCRIPTS_REL)  # conventional clone
    return candidates


def _find_memory_scripts_dir() -> "Path | None":
    for candidate in _candidate_dirs():
        if (candidate / "recall.py").is_file():
            return candidate
    return None


def _find_save_scripts_dir() -> "Path | None":
    for candidate in _candidate_dirs():
        if (candidate / "save.py").is_file():
            return candidate
    return None


def _find_opinion_scripts_dir() -> "Path | None":
    for candidate in _opinion_candidate_dirs():
        if (candidate / "opinion_resolver.py").is_file():
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
    _recall_module = _load_module("agentm_recall_bridge", scripts_dir / "recall.py")
    return _recall_module


def query_semantic(vault: Path, query_text: str, *, filter_expr: str, k: int = 5) -> list:
    """Run agentm's hybrid recall query. [] if agentm is unresolvable."""
    module = load_recall_module()
    if module is None:
        return []
    return module.query(vault=vault, query_text=query_text, filter_expr=filter_expr, k=k)


def load_save_module():
    """Return agentm's save module, loaded once and cached. None if agentm
    is unresolvable."""
    global _save_module, _save_loaded
    if _save_loaded:
        return _save_module
    _save_loaded = True
    scripts_dir = _find_save_scripts_dir()
    if scripts_dir is None:
        _save_module = None
        return None
    _save_module = _load_module("agentm_save_bridge", scripts_dir / "save.py")
    return _save_module


def write_failure_incident(
    vault: Path, *, slug: str, body: str, project: str, fingerprint: str, tags: list
) -> Path:
    """Write a kind="failure-incident" entry via agentm's save_entry(). Unlike
    query_semantic's graceful empty-list fallback, there is no fallback for a
    write -- raises RuntimeError if agentm is unresolvable (the mandatory
    privacy scrub agentm's save_entry runs for this kind cannot be skipped by
    routing around agentm)."""
    module = load_save_module()
    if module is None:
        raise RuntimeError("agentm is unresolvable -- cannot write a failure-incident entry")
    group = f"projects/{project}/failure-incident"
    return module.save_entry(
        vault, "failure-incident", slug, body,
        group=group, tags=tags, fingerprint=fingerprint,
    )


def load_opinion_module():
    """Return agentm's opinion_resolver module, loaded once and cached. None
    if agentm is unresolvable (graceful-skip, not an error)."""
    global _opinion_module, _opinion_loaded
    if _opinion_loaded:
        return _opinion_module
    _opinion_loaded = True
    scripts_dir = _find_opinion_scripts_dir()
    if scripts_dir is None:
        _opinion_module = None
        return None
    _opinion_module = _load_module("agentm_opinion_bridge", scripts_dir / "opinion_resolver.py")
    return _opinion_module


def opinion_resolve(name: str) -> dict:
    """Resolve an Opinion by name via agentm's opinion_resolve(). Never
    raises -- degrades to a `no-opinion`-shaped dict when agentm is
    unresolvable, matching opinion_resolver.py's own never-raise contract."""
    module = load_opinion_module()
    if module is None:
        return {"name": name, "reason": "no-opinion", "base": None, "supplement": None,
                "question": None, "implements": None, "composes": []}
    return module.opinion_resolve(name)


def _reset_cache_for_tests() -> None:
    """Test-only: clear the module-level cache between isolated test cases."""
    global _recall_module, _loaded, _save_module, _save_loaded
    global _opinion_module, _opinion_loaded
    _recall_module = None
    _loaded = False
    _save_module = None
    _save_loaded = False
    _opinion_module = None
    _opinion_loaded = False
