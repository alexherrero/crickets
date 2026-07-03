#!/usr/bin/env python3
"""project_model.py — vault project state -> stable-id'd board item graph.

crickets github-projects (#41), task 3.

Reads a project's structured board-items source into an item graph following the
flat locked taxonomy (Version - Feature - Sub-feature - Plan - Task, plus
Backlog-item - Idea - Bug), resolves the parent-chain, validates the hierarchy,
and applies the **DC-1 materialization rule**:

  - every item *feature-level-and-up* (Version - Feature - Sub-feature, plus the
    top-level Backlog-item / Idea / Bug) is **always materialized** the moment it
    exists -- it is the human-facing roadmap and must always be visible;
  - **Plan + Task** items materialize **only for an active plan**, to bound
    repo-issue volume. Future plans/tasks live implicitly under their already-
    materialized feature until work picks them up.

Rule of thumb (DC-1): never pre-persist task breakdowns; always persist features
and up.

stdlib only. The board-items source is **JSON** (matching the vault's
``features.json``), not YAML, so the shipped helper need not assume PyYAML --
honoring the locked stdlib-helper constraint. The structured source is the
machine projection the agent maintains alongside the prose roadmap (seeded once
by the operator-gated inaugural backfill, then kept in sync by the phase hooks);
silent-source attribution is carried here as a flagged field and stripped at
public render time (task 4), never in the model.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# ── Flat Type taxonomy — locked 2026-06-06 ───────────────────────────────────
TYPES = frozenset({
    "version", "feature", "sub-feature", "plan", "task",
    "backlog-item", "idea", "bug",
})

# Parent-chain rules. A type listed here must have a parent of one of the given
# types; every other type is top-level (parent must be None).
PARENT_TYPES: dict[str, frozenset] = {
    "feature": frozenset({"version"}),
    "sub-feature": frozenset({"feature"}),
    "plan": frozenset({"feature", "sub-feature"}),
    "task": frozenset({"plan"}),
}
TOP_LEVEL = frozenset({"version", "backlog-item", "idea", "bug"})

# DC-1 materialization partition.
ALWAYS_MATERIALIZE = frozenset({
    "version", "feature", "sub-feature", "backlog-item", "idea", "bug",
})
DEFERRED_MATERIALIZE = frozenset({"plan", "task"})

# Structural keys read off each item; everything else is a model-supplied human
# sentence and lands in `fields` (the template `{{placeholders}}`).
_STRUCTURAL = frozenset({
    "id", "type", "title", "parent", "track", "priority",
    "start", "target", "status", "issue", "silent_source", "fields",
})


class ModelError(ValueError):
    """Raised on a malformed item graph (unknown type, bad/missing parent,
    duplicate id, cycle, or a top-level type carrying a parent)."""


@dataclass
class Item:
    id: str
    type: str
    title: str
    parent: str | None = None
    track: str | None = None
    priority: str | None = None
    start: str | None = None
    target: str | None = None
    status: str | None = None
    issue: int | None = None            # materialized GitHub issue number (idempotent resolve)
    silent_source: str | None = None    # named in the vault, stripped from the public mirror
    fields: dict = field(default_factory=dict)   # model-supplied human sentences
    children: list = field(default_factory=list)  # resolved by build_graph (ordered)

    @property
    def is_top_level(self) -> bool:
        return self.type in TOP_LEVEL


# ── parsing ──────────────────────────────────────────────────────────────────
def parse_items(data: dict) -> list:
    """Turn a parsed board-items mapping into a flat list of Item (unresolved).

    Validates shape per item (id/type/title present, type known) and that ids are
    unique. Does NOT resolve the parent-chain — that is build_graph's job.
    """
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ModelError("board-items source must be a mapping with an 'items' list")

    items: list = []
    seen: set = set()
    for raw in data["items"]:
        if not isinstance(raw, dict):
            raise ModelError(f"each item must be a mapping, got {type(raw).__name__}")
        for req in ("id", "type", "title"):
            if not raw.get(req):
                raise ModelError(f"item missing required '{req}': {raw!r}")
        iid = raw["id"]
        if iid in seen:
            raise ModelError(f"duplicate item id: {iid!r}")
        seen.add(iid)
        itype = raw["type"]
        if itype not in TYPES:
            raise ModelError(f"unknown type {itype!r} for item {iid!r} (allowed: {sorted(TYPES)})")
        # Any non-structural key is a human-sentence placeholder; merge with an
        # explicit `fields` block if present.
        extra = {k: v for k, v in raw.items() if k not in _STRUCTURAL}
        fields = dict(raw.get("fields") or {})
        fields.update(extra)
        items.append(Item(
            id=iid,
            type=itype,
            title=raw["title"],
            parent=raw.get("parent"),
            track=raw.get("track"),
            priority=raw.get("priority"),
            start=raw.get("start"),
            target=raw.get("target"),
            status=raw.get("status"),
            issue=raw.get("issue"),
            silent_source=raw.get("silent_source"),
            fields=fields,
        ))
    return items


def load_items(path) -> list:
    """Read board-items.json at `path` and parse into a flat Item list."""
    text = Path(path).read_text(encoding="utf-8")
    return parse_items(json.loads(text))


# ── graph build + validation ─────────────────────────────────────────────────
def build_graph(items: list) -> dict:
    """Index items by id, validate the parent-chain, link children, detect cycles.

    Returns an ordered dict id -> Item with `children` populated (in input order).
    Raises ModelError on a missing/typed-wrong parent, a top-level type carrying a
    parent, or a cycle.
    """
    by_id: dict = {}
    for it in items:
        by_id[it.id] = it  # parse_items already guaranteed unique ids

    for it in items:
        if it.type in TOP_LEVEL:
            if it.parent is not None:
                raise ModelError(
                    f"{it.type} {it.id!r} is top-level but declares parent {it.parent!r}")
            continue
        # Non-top-level types require a parent of an allowed type.
        allowed = PARENT_TYPES[it.type]
        if it.parent is None:
            raise ModelError(f"{it.type} {it.id!r} requires a parent ({sorted(allowed)})")
        if it.parent not in by_id:
            raise ModelError(f"{it.id!r} parent {it.parent!r} does not exist")
        parent = by_id[it.parent]
        if parent.type not in allowed:
            raise ModelError(
                f"{it.type} {it.id!r} parent {it.parent!r} is {parent.type!r}; "
                f"must be one of {sorted(allowed)}")

    # Link children in input order (deterministic render order downstream).
    for it in items:
        it.children = []
    for it in items:
        if it.parent is not None:
            by_id[it.parent].children.append(it)

    _assert_acyclic(by_id)
    return by_id


def _assert_acyclic(by_id: dict) -> None:
    """Walk each item's parent links to the root; a repeat means a cycle."""
    for start in by_id:
        seen: set = set()
        cur = start
        while cur is not None:
            if cur in seen:
                raise ModelError(f"cycle in parent-chain at {cur!r}")
            seen.add(cur)
            cur = by_id[cur].parent


def load(path) -> dict:
    """Convenience: load_items + build_graph from a board-items.json path."""
    return build_graph(load_items(path))


# ── DC-1 materialization ─────────────────────────────────────────────────────
def materialize(graph: dict, active_plans=()) -> list:
    """Apply DC-1: return the items that should be persisted on the board.

    Every ALWAYS_MATERIALIZE item is included. A `plan` is included iff its id is
    in `active_plans`; a `task` is included iff its parent plan is in
    `active_plans`. Output preserves input (graph insertion) order for a
    deterministic downstream render.

    `active_plans`: iterable of plan ids whose task breakdown is materialized
    (the caller derives this — e.g. plans with status in-progress, or an explicit
    config list). Unknown ids are ignored (a not-yet-authored plan simply
    materializes nothing).
    """
    active = set(active_plans)
    out: list = []
    for it in graph.values():
        if it.type in ALWAYS_MATERIALIZE:
            out.append(it)
        elif it.type == "plan" and it.id in active:
            out.append(it)
        elif it.type == "task" and it.parent in active:
            out.append(it)
    return out


def parent_chain(graph: dict, item_id: str) -> list:
    """Return [parent, grandparent, ... root] for `item_id` (empty for top-level).

    Raises ModelError if `item_id` is unknown.
    """
    if item_id not in graph:
        raise ModelError(f"unknown item id: {item_id!r}")
    chain: list = []
    cur = graph[item_id].parent
    while cur is not None:
        chain.append(graph[cur])
        cur = graph[cur].parent
    return chain


# ── persistence (the write-back half of load()) ──────────────────────────────
def item_to_dict(item: Item) -> dict:
    """Serialize one Item back to board-items.json shape (the load_items()
    inverse). Structural keys are omitted when None; non-structural values stay
    nested under 'fields' (load_items()'s merge of an explicit 'fields' block
    with top-level extras is a superset read, so writing everything back under
    'fields' round-trips cleanly)."""
    d: dict = {"id": item.id, "type": item.type, "title": item.title}
    for key in ("parent", "track", "priority", "start", "target", "status",
                "issue", "silent_source"):
        value = getattr(item, key)
        if value is not None:
            d[key] = value
    if item.fields:
        d["fields"] = item.fields
    return d


def dump(graph: dict, path) -> None:
    """Write `graph` back to the board-items.json at `path` (load()'s inverse).

    Only the 'items' array is replaced; any other top-level keys already in the
    file (e.g. a human-authored '_comment' or '_reconciled_at') are preserved
    verbatim. A missing or unparsable file at `path` just means there is no
    prior top-level metadata to preserve.
    """
    p = Path(path)
    top: dict = {}
    if p.exists():
        try:
            existing = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                top = {k: v for k, v in existing.items() if k != "items"}
        except (json.JSONDecodeError, OSError):
            top = {}
    top["items"] = [item_to_dict(it) for it in graph.values()]
    p.write_text(json.dumps(top, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
