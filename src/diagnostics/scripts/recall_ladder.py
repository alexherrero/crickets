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


def _layer2_filter_expr(project: str) -> str:
    return f"kind=failure-incident AND project={project} AND status=active"


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
    """
    hit = fingerprint_index.lookup(vault, fingerprint, project)
    if hit is not None:
        return {"layer": 1, "path": hit}

    candidates = agentm_bridge.query_semantic(
        vault, query_text, filter_expr=_layer2_filter_expr(project), k=k
    )
    return {"layer": 2, "candidates": candidates}
