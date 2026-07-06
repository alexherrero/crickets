#!/usr/bin/env python3
"""Advisor rider config validation (PLAN-efficiency-dispatch task 3).

A T0/T1 session can carry an `advisorModel` config value — a stronger model
paired alongside the cheap main session, escalated to ad hoc for a hard call
without switching the whole session. This module validates that pairing
(the advisor must not be weaker than the main session — a weaker "advisor"
defeats the point) and renders the session-start availability line. Anthropic
API only; wiring the config value into an actual session-start read is
Task 7's job — this module owns the validation + rendering logic itself.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Relative strength for the pairing constraint ONLY — not a general model
# quality ranking. Equal rank means comparable generation (sonnet-4-6 and
# sonnet-5 are both rank 1), not identical.
MODEL_STRENGTH_RANK: dict[str, int] = {
    "claude-haiku-4-5": 0,
    "claude-sonnet-4-6": 1,
    "claude-sonnet-5": 1,
    "claude-opus-4-8": 2,
    "claude-fable-5": 3,
}

# claude-fable-5's availability as an advisor pairing wasn't confirmed below
# this host version — flagged, not silently allowed.
FABLE_MIN_CLI_VERSION: tuple[int, int, int] = (2, 1, 170)


def _parse_version(v: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(p) for p in v.split("."))
    except (ValueError, AttributeError, TypeError):
        return None


@dataclass(frozen=True)
class AdvisorValidation:
    valid: bool
    error: str | None = None
    warning: str | None = None


def validate_advisor_rider(
    main_session_model: str,
    advisor_model: str,
    *,
    cli_version: str | None = None,
) -> AdvisorValidation:
    """Validate an `advisorModel` pairing against the main session's model.

    Rejects (valid=False) an advisor ranked weaker than the main session, or
    an unrecognized model on either side. `claude-fable-5` as advisor is
    accepted with a warning when `cli_version` is unknown, rejected outright
    when known and below `FABLE_MIN_CLI_VERSION`.
    """
    main_rank = MODEL_STRENGTH_RANK.get(main_session_model)
    advisor_rank = MODEL_STRENGTH_RANK.get(advisor_model)

    if main_rank is None or advisor_rank is None:
        return AdvisorValidation(
            valid=False,
            error=f"unrecognized model in advisor pairing: main={main_session_model!r} advisor={advisor_model!r}",
        )

    if advisor_rank < main_rank:
        return AdvisorValidation(
            valid=False,
            error=(
                f"advisorModel {advisor_model!r} is weaker than the main session "
                f"model {main_session_model!r} — the pairing constraint requires "
                f"the advisor to be at least as strong"
            ),
        )

    if advisor_model == "claude-fable-5":
        parsed = _parse_version(cli_version) if cli_version else None
        min_str = ".".join(str(p) for p in FABLE_MIN_CLI_VERSION)
        if parsed is None:
            return AdvisorValidation(
                valid=True,
                warning=(
                    f"claude-fable-5 as advisor requires CLI >= {min_str}; the "
                    f"installed version could not be determined — proceeding, "
                    f"confirm manually"
                ),
            )
        if parsed < FABLE_MIN_CLI_VERSION:
            return AdvisorValidation(
                valid=False,
                error=f"claude-fable-5 as advisor requires CLI >= {min_str}; installed is {cli_version}",
            )

    return AdvisorValidation(valid=True)


def read_advisor_model(root: str | Path) -> str | None:
    """Read `advisorModel` from `<root>/.harness/project.json`.

    Missing file, malformed JSON, wrong type, or absent/empty key all
    collapse to None (task 7 consumes this at session-start; a config read
    failure must never block session boot) — never raises.
    """
    pj = Path(root) / ".harness" / "project.json"
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    value = data.get("advisorModel")
    return value if isinstance(value, str) and value else None


def advisor_availability_line(advisor_model: str | None) -> str:
    """The session-start advisor-availability line, or "" when unconfigured."""
    if not advisor_model:
        return ""
    return f"Advisor available: {advisor_model} (escalate ad hoc — advisory only, never auto-switches)"
