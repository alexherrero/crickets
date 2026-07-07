#!/usr/bin/env python3
"""Dreaming-pass efficiency-trend review hook — staged as a dark/stub only
(PLAN-wave-d-tokens-and-privacy task 3).

The real hook (not built here) would review accumulated `kind: session-cost`
records for cost creep over time, feeding the `efficient` opinion a
longitudinal signal. It is explicitly gated on agentm's Wave-E dreaming pass
-- a whole-corpus consolidation sweep that is designed but not built
(agentm-experience-and-dreaming.md: dreaming is `[PENDING-IMPL]`, blocked on
its own revert-log prerequisite, which is itself unbuilt).

Building real trend-analysis logic now would mean writing consumer code
against infrastructure that does not exist -- untestable against anything
real, and liable to silently ossify around a shape the eventual dreaming
pass doesn't actually have. So this module is the acceptance surface named
in the plan: a stub that proves the gate correctly no-ops TODAY (dreaming
pass absent -> clean no-op) rather than attempting the analysis itself. When
Wave-E's dreaming pass ships, this stub is the extension point a real
implementation replaces -- not a placeholder left to rot silently: the
dreaming-pass-absent branch below is the one line that must change.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DreamingTrendResult:
    ran: bool          # True only once a real dreaming pass exists and ran
    reason: str         # "dreaming-pass-unavailable" (today's only value) | "ok"


def dreaming_pass_available() -> bool:
    """Whether agentm's Wave-E dreaming pass exists on this machine.

    Always False today -- dreaming is designed, not built
    (agentm-experience-and-dreaming.md). This is the single check a real
    Wave-E implementation would replace with an actual capability probe
    (e.g. resolving agentm's dreaming module the way session_cost_writer.py
    resolves save.py).
    """
    return False


def review_efficiency_trend(records: "list[dict] | None" = None) -> DreamingTrendResult:
    """The gated entry point the tokens capability's efficiency review would
    call. Correctly-gated-dark: with no dreaming pass available, this always
    returns a clean no-op -- never an error, never a silent partial
    implementation of the trend logic itself.

    `records` (accumulated `session-cost` entries) is accepted but
    deliberately unused today -- real trend analysis is Wave-E scope.
    """
    if not dreaming_pass_available():
        return DreamingTrendResult(ran=False, reason="dreaming-pass-unavailable")
    # Unreachable until Wave-E ships a real dreaming pass; a future
    # implementation replaces this branch with the actual trend-analysis
    # call (e.g. detecting per-model cost creep across `records`).
    return DreamingTrendResult(ran=False, reason="ok")  # pragma: no cover
