#!/usr/bin/env python3
"""Mandatory fan-out announcement + silent-inheritance guard + fleet cost
gate (PLAN-efficiency-dispatch task 4; cost-gate wiring added by the
fanout-cost-gate-wiring plan, Consolidation arc Wave 4 proving window).

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

A **fleet-sized** dispatch (`agent_count >= COST_GATE_MIN_AGENT_COUNT`) also
runs token-audit's `fanout_cost_gate.py` pre-flight — estimated agent-count x
per-agent cost against a budget share, before the fan-out proceeds. A
blocked gate result pauses the same way the inheritance guard does:
`pause_required` is the one flag a dispatch site checks; `cost_gate_warning`
carries the gate's own message. The two mechanisms are independent — either,
both, or neither can fire on a given dispatch, and neither masks the other.
Additive only: when the `token-audit` capability is unresolvable
(graceful-skip, mirroring `escalation_tripwire.py`'s own discovery
convention), the cost gate is simply not consulted and `announce_dispatch()`
behaves exactly as it did before this wiring.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path

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


# ── fleet cost gate (token-audit capability, graceful-skip if absent) ──────
#
# Mirrors escalation_tripwire.py's sibling-capability discovery cascade (same
# directory, same "efficient" opinion -> tokens/scripts target): try
# agentm's opinion_resolve('efficient')['implements'] first, fall back to
# this repo's own src/tokens/scripts when agentm itself isn't reachable
# (CI, or any machine without a sibling agentm checkout). Kept as its own
# self-contained copy rather than importing escalation_tripwire.py's private
# helpers — each cross-plugin consumer in this codebase keeps its own small
# discovery cascade (see also the independently-duplicated `agentm_bridge.py`
# copies under diagnostics/maintenance/research, registered in
# wiki/explanation/Repo-Layout.md's dark registry) rather than coupling
# sibling scripts to one another's internals.

COST_GATE_MIN_AGENT_COUNT = 4

_HERE = Path(__file__).resolve().parent


def _find_opinion_resolver() -> "Path | None":
    candidates: list[Path] = []
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    if env_dir:
        candidates.append(Path(os.path.expanduser(env_dir)))
    candidates.append(_HERE / "scripts")  # co-located install (cascade parity with escalation_tripwire.py)
    candidates.append(Path.home() / "Antigravity" / "agentm" / "scripts")  # conventional clone
    for candidate in candidates:
        p = candidate / "opinion_resolver.py"
        if p.is_file():
            return p
    return None


def _load_module_from_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


_FALLBACK_TOKENS_SCRIPTS = _HERE.parent.parent / "tokens" / "scripts"


def _resolve_tokens_scripts_dir() -> "Path | None":
    """`opinion_resolve('efficient')['implements']` ("crickets/tokens") -> this
    repo's `src/tokens/scripts` dir. Falls back to the same-repo conventional
    path when agentm's opinion resolver is unresolvable — both resolve to the
    same directory whenever agentm IS present."""
    resolver_path = _find_opinion_resolver()
    if resolver_path is not None:
        resolver = _load_module_from_path("_fanout_announcement_opinion_resolver", resolver_path)
        result = resolver.opinion_resolve("efficient")
        implements = result.get("implements")
        if implements and "/" in implements:
            _, capability = implements.split("/", 1)
            candidate = _HERE.parent.parent / capability / "scripts"
            if candidate.is_dir():
                return candidate
    return _FALLBACK_TOKENS_SCRIPTS if _FALLBACK_TOKENS_SCRIPTS.is_dir() else None


_TOKENS_SCRIPTS = _resolve_tokens_scripts_dir()

_HAS_COST_GATE = False
_fanout_cost_gate_fn = None

if _TOKENS_SCRIPTS is not None:
    sys.path.insert(0, str(_TOKENS_SCRIPTS))
    try:
        from fanout_cost_gate import fanout_cost_gate as _fanout_cost_gate_fn  # type: ignore
        _HAS_COST_GATE = True
    except ImportError:
        pass


def run_fanout_cost_gate(agent_count: int, model_id: str):
    """Best-effort call into token-audit's `fanout_cost_gate()`. Returns None
    when the `token-audit` capability is unresolvable — the cost gate is
    additive, never a hard dependency of `announce_dispatch()`."""
    if not _HAS_COST_GATE:
        return None
    return _fanout_cost_gate_fn(agent_count, model_id)


def needs_cost_gate_pause(agent_count: int, model_id: str) -> "tuple[bool, str | None]":
    """(True, block-message) iff a fleet-sized dispatch's pre-flight cost
    estimate exceeds budget. (False, None) below the fleet-size floor, when
    the gate is unresolvable, or when it proceeds silently (under budget)."""
    if agent_count < COST_GATE_MIN_AGENT_COUNT:
        return False, None
    result = run_fanout_cost_gate(agent_count, model_id)
    if result is None or result.proceed:
        return False, None
    return True, result.message


@dataclass(frozen=True)
class AnnouncementResult:
    announcement_line: str
    pause_required: bool
    warning: str | None = None
    cost_gate_warning: str | None = None


def announce_dispatch(a: DispatchAnnouncement, *, session_tier: str | None = None) -> AnnouncementResult:
    """The one call a dispatch site makes: render the announcement, and decide
    whether a frontier-tier silent-inheritance pause and/or a fleet cost-gate
    pause is required. The two mechanisms are independent — either or both
    may fire on the same dispatch, and neither masks the other.
    `pause_required` is the single flag a dispatch site checks; `warning` and
    `cost_gate_warning` carry whichever message(s) actually apply."""
    line = render_announcement(a)

    inheritance_pause = needs_inheritance_pause(a.tier_source, session_tier)
    warning = inheritance_warning(a, session_tier) if inheritance_pause else None

    cost_gate_pause, cost_gate_message = needs_cost_gate_pause(a.agent_count, a.model)

    return AnnouncementResult(
        announcement_line=line,
        pause_required=inheritance_pause or cost_gate_pause,
        warning=warning,
        cost_gate_warning=cost_gate_message,
    )
