#!/usr/bin/env python3
"""Recall ladder for /diagnose: Layer-1 exact fingerprint match, Layer-2
semantic fallback (crickets wave-c-diagnostics).

Zero-inference guarantee (locked in PLAN-wave-c-diagnostics.md): a Layer-1 hit
must short-circuit before Layer-2's semantic engine ever runs. `recall()` below
checks fingerprint_index.lookup() first and only calls agentm_bridge on a miss.

Sibling modules (fingerprint_index, agentm_bridge) are loaded by file path
under private sys.modules keys, then exposed as attributes on this module --
this lets tests patch `recall_ladder.agentm_bridge.query_semantic` directly,
independent of however else those siblings might be loaded elsewhere in the
same process (avoids bare-name sys.modules collisions across plugins).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load_sibling(label: str, filename: str):
    spec = importlib.util.spec_from_file_location(
        f"_diagnostics_internal_{label}", _HERE / filename
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fingerprint_index = _load_sibling("fingerprint_index", "fingerprint_index.py")
agentm_bridge = _load_sibling("agentm_bridge", "agentm_bridge.py")

_DEFAULT_K = 5

# Self-reinforcing alias mechanism (task 3): a Layer-2 top candidate at or
# above this score auto-attaches the queried fingerprint as an alias of the
# candidate's existing incident, so a repeat of this same drifted fingerprint
# converges to a Layer-1 hit next time. Below threshold: no side effect --
# a merely-related candidate is not the same incident.
_ALIAS_CONFIDENCE_THRESHOLD = 0.75


def _layer2_filter_expr(project: str) -> str:
    return f"kind=failure-incident AND project={project} AND status=active"


def _maybe_attach_alias(vault: Path, fingerprint: str, project: str, candidates: list) -> None:
    if not candidates:
        return
    top = candidates[0]
    if top.get("score", 0) < _ALIAS_CONFIDENCE_THRESHOLD:
        return
    canonical = fingerprint_index.find_canonical_fingerprint(vault, project, top["path"])
    if canonical is None:
        return  # the matched entry predates the sidecar index -- no-op, not an error
    fingerprint_index.add_alias(vault, canonical, fingerprint, project)


def recall(
    *,
    vault: Path,
    fingerprint: str,
    project: str,
    query_text: str,
    namespace: str,
    k: int = _DEFAULT_K,
) -> dict:
    """Classify->recall entry point. Returns either:
      {"layer": 1, "path": <entry path>}
      {"layer": 2, "candidates": [<ranked candidate dict>, ...]}
    A confident Layer-2 top candidate self-reinforces (see _maybe_attach_alias).
    """
    hit = fingerprint_index.lookup(vault, fingerprint, project)
    if hit is not None:
        return {"layer": 1, "path": hit}

    candidates = agentm_bridge.query_semantic(
        vault, query_text, filter_expr=_layer2_filter_expr(project), k=k
    )
    _maybe_attach_alias(vault, fingerprint, project, candidates)
    return {"layer": 2, "candidates": candidates}
