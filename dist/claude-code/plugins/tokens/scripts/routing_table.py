#!/usr/bin/env python3
"""Versioned routing table — the single home of current model ids (crickets-token-audit design, 2026-07-04 amendment).

ONE source of truth for "what model id does this work-type currently route to."
`model-effort-routing` keeps the abstract tier scale + effort ladder; this file
keeps the concrete model-id strings, colocated with `pricing.py` so a routing
decision and its price are read off the same transcript in the same breath —
they can never disagree about how a model's name is spelled.

Every `model_id` here must be a key in `pricing.py`'s `PRICING` dict (a parity
test enforces this, not eyeballing). `claude-fable-5` is deliberately present
as a *recognized* id — resolving from zero work-type rows — so an `INHERITED`
announcement naming it is instantly recognizable as the Mythos failure shape
(silent inheritance of the most expensive model at fan-out scale), not a name
the operator has to look up mid-incident.

To update: bump `VERSION` and edit `TABLE` here only.
"""
from __future__ import annotations

from dataclasses import dataclass

VERSION = "2026-07-04"


@dataclass(frozen=True)
class RoutingRow:
    tier: str
    model_id: str
    effort: str


# `opusplan` is a routing alias, not a billable model id — Opus plans, Sonnet
# executes. It resolves to two concrete `pricing.py` rows, never one; the
# parity guard below checks the *resolved* ids, never the alias string itself.
ALIASES: dict[str, tuple[str, ...]] = {
    "opusplan": ("claude-opus-4-8", "claude-sonnet-5"),
}


def concrete_model_ids(model_id: str) -> tuple[str, ...]:
    """Resolve a table `model_id` (possibly an alias) to its concrete id(s)."""
    return ALIASES.get(model_id, (model_id,))


TABLE: dict[str, RoutingRow] = {
    "research-adversarial-audit": RoutingRow(
        tier="T4-Deep", model_id="claude-opus-4-8", effort="max",
    ),
    "roadmap-architecture-priority": RoutingRow(
        tier="T3-Architect", model_id="claude-opus-4-8", effort="max",
    ),
    "author-roadmap-shaped": RoutingRow(
        tier="T2-Author", model_id="claude-opus-4-8", effort="high",
    ),
    "author-transcription-shaped": RoutingRow(
        tier="T2-Author", model_id="claude-sonnet-5", effort="high",
    ),
    "worker-build": RoutingRow(
        tier="T1-Execute", model_id="opusplan", effort="medium",
    ),
    "wiki-mechanical-plus": RoutingRow(
        tier="T1-Execute", model_id="claude-sonnet-5", effort="medium",
    ),
    "mechanical-log-scraping": RoutingRow(
        tier="T0-Mechanical", model_id="claude-sonnet-5", effort="low",
    ),
}

# Recognized-but-unrouted ids: valid model ids that no work-type resolves to.
# `claude-fable-5` lives here, not in TABLE, so it stays a name the classifier
# can recognize (never invent) without ever being a routing target.
RECOGNIZED_UNROUTED: frozenset[str] = frozenset({"claude-fable-5"})


def routed_model_ids() -> frozenset[str]:
    """Every concrete (alias-resolved) model id at least one work-type routes to."""
    ids: set[str] = set()
    for row in TABLE.values():
        ids.update(concrete_model_ids(row.model_id))
    return frozenset(ids)


def all_recognized_model_ids() -> frozenset[str]:
    """Routed ids plus recognized-but-unrouted ids (e.g. `claude-fable-5`)."""
    return routed_model_ids() | RECOGNIZED_UNROUTED
