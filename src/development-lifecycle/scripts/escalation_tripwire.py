#!/usr/bin/env python3
"""`/work` escalation tripwire (PLAN-efficiency-dispatch task 5).

A counter on the existing per-task verification-gate loop: `FIRE_THRESHOLD`
(3) consecutive failures on the SAME gate for the SAME task fires the
tripwire — writes a handoff-pack escalation entry (token-audit's
`handoff_pack.py`, capability-gated) and returns a loud stop signal. The
tripwire NEVER attempts to change the session's own model; it hands off to
a human or a fresh session instead — `FIRE_THRESHOLD` is a prior, not a
measurement (P14 routing-autonomy verdict §5), tuned later from real firing
data via token-audit's routing-conformance report, not mid-plan.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path

FIRE_THRESHOLD = 3

_HERE = Path(__file__).resolve().parent
_TA_SCRIPTS = _HERE.parent.parent / "tokens" / "scripts"

_HAS_HANDOFF_PACK = False
HandoffEntry = None
build_handoff_pack = None
_classify_work_type = None

if _TA_SCRIPTS.is_dir():
    sys.path.insert(0, str(_TA_SCRIPTS))
    try:
        from handoff_pack import HandoffEntry as _HandoffEntry, build_handoff_pack as _build_handoff_pack  # type: ignore
        from classify_work_type import classify_work_type as _cwt  # type: ignore
        HandoffEntry = _HandoffEntry
        build_handoff_pack = _build_handoff_pack
        _classify_work_type = _cwt
        _HAS_HANDOFF_PACK = True
    except ImportError:
        pass


@dataclass
class FailureCounter:
    """Per-task, per-gate consecutive-failure counter. Resets on success."""
    consecutive_failures: int = 0

    def record_failure(self) -> None:
        self.consecutive_failures += 1

    def record_success(self) -> None:
        self.consecutive_failures = 0

    def should_fire(self) -> bool:
        return self.consecutive_failures >= FIRE_THRESHOLD


@dataclass(frozen=True)
class TripwireResult:
    fired: bool
    announcement: str
    handoff_pack_dir: str | None = None


def fire_tripwire(
    task_id: str,
    task_title: str,
    gate_name: str,
    error_output: str,
    dest_dir: Path,
    *,
    work_type: str = "worker-build",
) -> TripwireResult:
    """Write the escalation handoff pack (capability-gated) + return the loud
    stop announcement. Takes no model-mutating parameter and calls nothing
    that could switch the session's own model — hand-off only, never a
    self-escalation."""
    if not _HAS_HANDOFF_PACK:
        return TripwireResult(
            fired=True,
            announcement=(
                f"ESCALATION: task {task_id!r} failed gate {gate_name!r} "
                f"{FIRE_THRESHOLD} consecutive times — token-audit unavailable, "
                f"no handoff pack written. Stopping; hand off manually. This "
                f"session never changes its own model to try to push through."
            ),
        )

    classification = _classify_work_type(role_name=work_type)
    entry = HandoffEntry(
        title=f"Escalation: task {task_id} failed {gate_name!r} {FIRE_THRESHOLD}x",
        prompt_text=(
            f"A prior session's task {task_id!r} ({task_title!r}) failed its "
            f"{gate_name!r} verification gate {FIRE_THRESHOLD} consecutive "
            f"times. Full error output:\n\n{error_output}\n\nDiagnose the root "
            f"cause and fix it — do not just retry."
        ),
        tier=classification.tier,
        model_id=classification.model_id,
        effort=classification.effort,
    )
    build_handoff_pack([entry], {"error-output.txt": error_output}, dest_dir)

    announcement = (
        f"ESCALATION: task {task_id!r} failed gate {gate_name!r} "
        f"{FIRE_THRESHOLD} consecutive times. Handoff pack written to "
        f"{dest_dir}. Stopping — this session does not retry a 4th time and "
        f"never changes its own model to try to push through."
    )
    return TripwireResult(fired=True, announcement=announcement, handoff_pack_dir=str(dest_dir))


def check_and_maybe_fire(
    counter: FailureCounter,
    task_id: str,
    task_title: str,
    gate_name: str,
    error_output: str,
    dest_dir: Path,
    *,
    work_type: str = "worker-build",
) -> TripwireResult | None:
    """Record a failure against `counter`; fire iff it now meets the threshold."""
    counter.record_failure()
    if not counter.should_fire():
        return None
    return fire_tripwire(task_id, task_title, gate_name, error_output, dest_dir, work_type=work_type)
