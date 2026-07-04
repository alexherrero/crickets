#!/usr/bin/env python3
"""Resolve a dispatch to a routing_table.py row (crickets-token-audit design, 2026-07-04 amendment).

Three-step resolution, in order — never a model-making-a-judgment-call:

1. **Persona-declared.** The sub-agent's agent-def already declares a tier via
   its `model:`/`effort:` (and optionally `tier:`) frontmatter. The
   declaration *is* the answer; the role-name table (step 2) is never
   consulted when a declaration is present.
2. **Ad-hoc role-name match.** An exact-match lookup of the dispatch's role
   name against `ROLE_TO_WORK_TYPE`, which resolves into Task 1's
   `routing_table.TABLE` by work-type key.
3. **No match.** Resolve to the fixed, hardcoded `UNCLASSIFIED_DEFAULT` —
   never `claude-fable-5`, never a session-inherited value. This is the
   direct Mythos-incident guard: a classification gap stays visible as
   `UNCLASSIFIED-DEFAULT` in the fan-out announcement rather than being
   quietly absorbed into "it just worked."

One classifier, three call sites (sub-agent dispatch, plan staging,
session-start nudge) — never three copies of the same judgment.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load_routing_table():
    spec = importlib.util.spec_from_file_location("routing_table", _HERE / "routing_table.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("routing_table", m)
    spec.loader.exec_module(m)
    return m


routing_table = _load_routing_table()

# Tier-source values — distinct from each other and from the fan-out
# announcement's `INHERITED`, so a reader can tell at a glance *how* a
# dispatch's model was decided.
TIER_SOURCE_FRONTMATTER = "FRONTMATTER"
TIER_SOURCE_ROLE_MATCH = "ROLE-MATCH"
TIER_SOURCE_UNCLASSIFIED_DEFAULT = "UNCLASSIFIED-DEFAULT"

# Ad-hoc dispatch roles that carry no persona manifest, matched against
# Task 1's seeded work-types. Session-shaped keys (worker-build, etc.) are
# matched directly against role_name too, so a caller can pass either an
# ad-hoc role or a work-type key interchangeably.
ROLE_TO_WORK_TYPE: dict[str, str] = {
    "explorer": "mechanical-log-scraping",
    "adversarial-reviewer": "research-adversarial-audit",
    "cross-model-reviewer": "research-adversarial-audit",
    "documenter": "wiki-mechanical-plus",
    "verification-clerk": "mechanical-log-scraping",
    # Phase-command names (PLAN-efficiency-dispatch task 1) — the same
    # classifier that resolves an ad-hoc dispatch role also resolves a
    # phase command's routing nudge, one function, not a parallel table.
    "plan": "author-transcription-shaped",
    "review": "author-transcription-shaped",
    "design": "author-transcription-shaped",
    "spec": "author-transcription-shaped",
    "interview-me": "author-transcription-shaped",
    "work": "worker-build",
    "bugfix": "worker-build",
}

# The fixed, hardcoded safe default — never derived from the table, so a
# future table edit can never accidentally change what "unclassified" means.
UNCLASSIFIED_DEFAULT_TIER = "T1-Execute"
UNCLASSIFIED_DEFAULT_MODEL_ID = "claude-sonnet-5"
UNCLASSIFIED_DEFAULT_EFFORT = "medium"


@dataclass(frozen=True)
class Classification:
    tier: str
    model_id: str
    effort: str
    tier_source: str
    work_type: str | None = None


def classify_work_type(role_name: str | None = None, declared: dict | None = None) -> Classification:
    """Resolve a dispatch to a `Classification`.

    `declared` — a persona's already-declared frontmatter, e.g.
    `{"model": "...", "effort": "...", "tier": "..."}`. When present, this
    wins outright; `role_name` (even if it would otherwise match) is not
    consulted.

    `role_name` — an ad-hoc dispatch role name (or a work-type key), matched
    against `ROLE_TO_WORK_TYPE` then `routing_table.TABLE` directly.

    No match on either → `UNCLASSIFIED_DEFAULT`, tier source
    `UNCLASSIFIED-DEFAULT`.
    """
    if declared:
        return Classification(
            tier=declared.get("tier") or "",
            model_id=declared.get("model") or "",
            effort=declared.get("effort") or "",
            tier_source=TIER_SOURCE_FRONTMATTER,
            work_type=None,
        )

    if role_name:
        work_type = ROLE_TO_WORK_TYPE.get(role_name, role_name)
        row = routing_table.TABLE.get(work_type)
        if row is not None:
            return Classification(
                tier=row.tier,
                model_id=row.model_id,
                effort=row.effort,
                tier_source=TIER_SOURCE_ROLE_MATCH,
                work_type=work_type,
            )

    return Classification(
        tier=UNCLASSIFIED_DEFAULT_TIER,
        model_id=UNCLASSIFIED_DEFAULT_MODEL_ID,
        effort=UNCLASSIFIED_DEFAULT_EFFORT,
        tier_source=TIER_SOURCE_UNCLASSIFIED_DEFAULT,
        work_type=None,
    )
