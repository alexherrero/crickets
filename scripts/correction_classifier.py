#!/usr/bin/env python3
"""Disposition classifier for operator corrections.

Rule corrections flow through this classifier at close-out.  Two paths:
  kernel-defect    — shipped artifact contradicts a universal contract
                     → patch src/ + developer-workflows plugin release
  operator-tuning  — personal preference, not universal
                     → write vault overlay only, never mutates src/

Hybrid-by-leverage governs kernel-defect amendments:
  low       — prompt-wording fix, default flip, doc clause → auto-apply
  contract  — alters external behavior contract or a gate → one-tap ratify before landing

Usage (library):
    from correction_classifier import classify, Disposition, Leverage
    result = classify(universality=True, is_contract_change=True)
    # DispositionResult(disposition=Disposition.KERNEL_DEFECT, leverage=Leverage.CONTRACT, ...)

See also: corrections.md schema (vault _harness/), correction_quality_gate.py (evaluator seam).
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class CorrectionClass(str, Enum):
    RULE = "rule"
    ONE_OFF = "one-off"


class Disposition(str, Enum):
    KERNEL_DEFECT = "kernel-defect"
    OPERATOR_TUNING = "operator-tuning"
    PENDING = "pending"


class Leverage(str, Enum):
    LOW = "low"          # auto-apply at close-out
    CONTRACT = "contract"  # one-tap ratify before landing


@dataclass
class CorrectionEntry:
    """Structured representation of one corrections.md entry."""

    timestamp: str
    summary: str
    did: str
    should: str
    artifact: str
    correction_class: CorrectionClass
    disposition: Disposition = field(default=Disposition.PENDING)
    leverage: Optional[Leverage] = field(default=None)


@dataclass
class DispositionResult:
    disposition: Disposition
    leverage: Optional[Leverage]
    rationale: str


def classify(universality: bool, is_contract_change: bool = False) -> DispositionResult:
    """Classify a rule correction by universality + leverage.

    Args:
        universality: True if every operator shares this contract (kernel defect);
                      False if this is a personal preference (operator tuning).
        is_contract_change: True if the amendment alters a command's external
                            behavior contract or a gate — forces one-tap ratify.

    Returns:
        DispositionResult with disposition, leverage (kernel-defect only), and rationale.

    One-off corrections are handled at capture time and never reach this function.
    """
    if not universality:
        return DispositionResult(
            disposition=Disposition.OPERATOR_TUNING,
            leverage=None,
            rationale=(
                "Personal preference — not universal across operators. "
                "Routes to vault overlay; no src/ mutation, no release."
            ),
        )
    leverage = Leverage.CONTRACT if is_contract_change else Leverage.LOW
    auto_note = "Contract change → one-tap ratify." if is_contract_change else "Low-leverage → auto-apply."
    return DispositionResult(
        disposition=Disposition.KERNEL_DEFECT,
        leverage=leverage,
        rationale=(
            "Universal contract conflict — patch shipped source + release. " + auto_note
        ),
    )


def apply_operator_tuning(overlay_path: Path, entry: CorrectionEntry) -> None:
    """Write an operator-tuning correction to the vault overlay.

    This function writes ONLY to overlay_path — it never reads or mutates
    the repo's src/ tree.  overlay_path must live in the operator-private vault
    (_harness/ subtree); never pass a path inside the committed repo.
    """
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    with overlay_path.open("a", encoding="utf-8") as fh:
        fh.write(f"\n## {entry.timestamp} — {entry.summary}\n")
        fh.write(f"- artifact: {entry.artifact}\n")
        fh.write(f"- should:   {entry.should}\n")
