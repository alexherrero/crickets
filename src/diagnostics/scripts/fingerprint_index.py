#!/usr/bin/env python3
"""Diagnostics-owned fingerprint sidecar index -- the Layer-1 exact-match
substrate for /diagnose (crickets wave-c-diagnostics).

Locked design call (2026-07-06, PLAN-wave-c-diagnostics.md): agentm's
entry_meta.fingerprint (V6-11) has no durable write path today --
save.py::_build_frontmatter's field order is locked (no fingerprint/project
key), and even a direct SQL write would be reset on the next drain/full-sync
(_extract_meta_from_file re-derives every entry_meta column from frontmatter
on each upsert). This index is diagnostics' own durable substitute: a flat
JSON file, keyed by "<project>::<fingerprint>", mapping to the entry's vault
path. Untouched by any agentm reindex cycle. Swappable for the real SQL
column later with no change to lookup()'s signature, if agentm ever adds
frontmatter support for it.
"""
from __future__ import annotations

import json
from pathlib import Path

_INDEX_RELATIVE = Path("_meta") / "diagnostics-fingerprints.json"


def index_path(vault: Path) -> Path:
    return vault / _INDEX_RELATIVE


def _key(project: str, fingerprint: str) -> str:
    return f"{project}::{fingerprint}"


def load_index(vault: Path) -> dict:
    path = index_path(vault)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_index(vault: Path, index: dict) -> None:
    path = index_path(vault)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def lookup(vault: Path, fingerprint: str, project: str) -> str | None:
    """Exact fingerprint+project lookup. Returns the entry's vault path, or None."""
    entry = load_index(vault).get(_key(project, fingerprint))
    return entry["path"] if entry else None


def record(vault: Path, fingerprint: str, project: str, path: str) -> None:
    """Record a new fingerprint -> entry path mapping (the task 4 writer)."""
    index = load_index(vault)
    index[_key(project, fingerprint)] = {"path": path, "aliases": []}
    _save_index(vault, index)


def add_alias(vault: Path, canonical_fingerprint: str, alias_fingerprint: str, project: str) -> None:
    """Attach a Layer-2-drifted fingerprint as an alias of an existing incident
    (task 3's self-reinforcing convergence). A subsequent lookup() on the alias
    fingerprint resolves via this same flat map -- i.e. as a Layer-1 hit."""
    index = load_index(vault)
    canonical_key = _key(project, canonical_fingerprint)
    canonical_entry = index.get(canonical_key)
    if canonical_entry is None:
        raise KeyError(
            f"no existing entry for fingerprint {canonical_fingerprint!r} in project {project!r}"
        )
    canonical_entry.setdefault("aliases", []).append(alias_fingerprint)
    index[_key(project, alias_fingerprint)] = {
        "path": canonical_entry["path"],
        "aliases": [],
        "alias_of": canonical_fingerprint,
    }
    _save_index(vault, index)
