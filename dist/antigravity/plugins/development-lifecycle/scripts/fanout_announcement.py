#!/usr/bin/env python3
"""Mandatory fan-out announcement + silent-inheritance guard (PLAN-efficiency-dispatch task 4).

Before any sub-agent launch — capability present or absent — the
dispatching agent prints one line per dispatch group: role · agent count ·
model (+ effort where bound) · **tier source**. This is unconditional: it
degrades to `agent frontmatter` / `INHERITED` sources when token-audit isn't
installed, so visibility never depends on the efficiency capability being
present.

An **inheriting** dispatch (no model resolved at all — the Agent tool falls
through to the parent session's model) at a **frontier-tier** (T3/T4)
session triggers a loud warning + a confirmation pause instead of proceeding
silently — the direct fix for the Mythos incident (112 sub-agents silently
inheriting `claude-fable-5`).
"""
from __future__ import annotations

from dataclasses import dataclass

TIER_SOURCE_TABLE_ROW = "table row"
TIER_SOURCE_AGENT_FRONTMATTER = "agent frontmatter"
TIER_SOURCE_UNCLASSIFIED_DEFAULT = "UNCLASSIFIED-DEFAULT"
TIER_SOURCE_INHERITED = "INHERITED"

FRONTIER_TIERS: frozenset[str] = frozenset({"T3-Architect", "T4-Deep"})

# classify_work_type.Classification.tier_source -> this module's announcement
# vocabulary. A classifier tier_source of None means classify_work_type was
# never consulted at all (no capability, or no model/frontmatter resolved) —
# that collapses to INHERITED, the same value a dispatch site reports when
# neither the model param nor the agent-def's own frontmatter supplied one.
_CLASSIFIER_TO_ANNOUNCEMENT_SOURCE: dict[str, str] = {
    "ROLE-MATCH": TIER_SOURCE_TABLE_ROW,
    "FRONTMATTER": TIER_SOURCE_AGENT_FRONTMATTER,
    "UNCLASSIFIED-DEFAULT": TIER_SOURCE_UNCLASSIFIED_DEFAULT,
}


def announcement_tier_source(classifier_tier_source: str | None) -> str:
    """A classify_work_type tier_source (or None) -> the announcement vocabulary."""
    if classifier_tier_source is None:
        return TIER_SOURCE_INHERITED
    return _CLASSIFIER_TO_ANNOUNCEMENT_SOURCE.get(classifier_tier_source, TIER_SOURCE_INHERITED)


@dataclass(frozen=True)
class DispatchAnnouncement:
    role: str
    agent_count: int
    model: str
    tier_source: str


def render_announcement(a: DispatchAnnouncement) -> str:
    """The one-line-per-dispatch-group announcement. Always renders — never
    conditional on any capability being present."""
    return f"DISPATCH: {a.role} · {a.agent_count} agent(s) · {a.model} · tier-source: {a.tier_source}"


def needs_inheritance_pause(tier_source: str, session_tier: str | None) -> bool:
    """True iff a dispatch is INHERITED and the session's own tier is frontier (T3/T4)."""
    if tier_source != TIER_SOURCE_INHERITED:
        return False
    return session_tier in FRONTIER_TIERS


def inheritance_warning(a: DispatchAnnouncement, session_tier: str) -> str:
    return (
        f"WARNING: {a.role} dispatch ({a.agent_count} agent(s)) is INHERITING the "
        f"session model {a.model!r} at frontier tier {session_tier!r} — confirm "
        f"before proceeding. This is the Mythos failure shape: silent inheritance "
        f"of an expensive model at fan-out scale."
    )


@dataclass(frozen=True)
class AnnouncementResult:
    announcement_line: str
    pause_required: bool
    warning: str | None = None


def announce_dispatch(a: DispatchAnnouncement, *, session_tier: str | None = None) -> AnnouncementResult:
    """The one call a dispatch site makes: render the announcement, and decide
    whether a frontier-tier silent-inheritance pause is required."""
    line = render_announcement(a)
    if needs_inheritance_pause(a.tier_source, session_tier):
        return AnnouncementResult(
            announcement_line=line, pause_required=True,
            warning=inheritance_warning(a, session_tier),
        )
    return AnnouncementResult(announcement_line=line, pause_required=False)
