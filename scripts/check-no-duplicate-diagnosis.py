#!/usr/bin/env python3
"""check-no-duplicate-diagnosis.py — portfolio-consistency gate: no bespoke
diagnosis logic remains outside diagnose.py (PLAN-wave-d-cross-wiring task 3).

Wave C shipped one shared failure-diagnosis engine (`src/diagnostics/scripts/
diagnose.py`): classify -> recall (fingerprint-first) -> rank hypotheses ->
write. Tasks 1-2 of PLAN-wave-d-cross-wiring recast dependabot-fixer's
Diagnose step and /bugfix's Analyze phase onto that engine instead of each
reasoning inline. This gate is the "no two diagnosis engines" regression
net: it fails if either consumer's markdown re-grows its own bespoke
category/confidence-scoring or ad hoc traceback-classification logic instead
of delegating to `diagnose()`.

Mirrors check-no-dangling-name.py's fixture-and-test style (Wave A) --
grep-based, stdlib only, no host CLI needed.

Run: `python3 scripts/check-no-duplicate-diagnosis.py`
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

# The two recast consumers. Each must call the shared engine (diagnose.py /
# diagnose()) and must NOT contain the old bespoke inline-reasoning shape --
# a from-scratch category + high/medium/low confidence judgment, or an ad hoc
# traceback-classification pass that isn't just consuming diagnose()'s output.
_CONSUMERS = {
    "dependabot-fixer": "maintenance/skills/dependabot-fixer/SKILL.md",
    "bugfix.md": "development-lifecycle/commands/bugfix.md",
}

_ENGINE_CALL_RE = re.compile(r"diagnose\.py|diagnose\(")

# The old inline-reasoning shape this gate rejects: a fresh category +
# confidence judgment produced from scratch, not sourced from diagnose()'s
# own outcome/hypotheses fields. Matched loosely (order-independent phrases)
# so a paraphrase doesn't slip past a literal-string check.
_INLINE_CATEGORY_RE = re.compile(r"failure category", re.IGNORECASE)
_INLINE_CONFIDENCE_RE = re.compile(
    r"confidence\s*\(?\s*high\s*/\s*medium\s*/\s*low\s*\)?", re.IGNORECASE
)

# A documented graceful-skip fallback (diagnostics not installed -> degrade to
# the old inline behavior) is NOT the regression this gate hunts for -- every
# other find_capability.py consumer in this codebase degrades the same way on
# exit 1, and forbidding it here would be inconsistent with that convention.
# Only flag the inline shape when it appears with no such fallback framing
# nearby, i.e. it's the file's *only* path, not an opt-in degrade branch.
_FALLBACK_CONTEXT_RE = re.compile(
    r"fall\s*back|not\s+install(?:ed)?|graceful[- ]?skip|pre-recast", re.IGNORECASE
)
_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")


def _inline_reasoning_outside_fallback(text: str) -> bool:
    """True if the old category+confidence shape appears in a paragraph that
    is NOT itself framed as a graceful-skip fallback branch."""
    for para in _PARAGRAPH_SPLIT_RE.split(text):
        if _INLINE_CATEGORY_RE.search(para) and _INLINE_CONFIDENCE_RE.search(para):
            if not _FALLBACK_CONTEXT_RE.search(para):
                return True
    return False


def check(src: Path = SRC) -> list[str]:
    """Return a list of `file: <finding>` strings. Empty means clean.

    Graceful no-op if a consumer file doesn't exist in this tree (fixture
    trees in tests need not carry every file; a real repo checkout always
    has both).
    """
    findings: list[str] = []
    for label, rel in _CONSUMERS.items():
        path = src / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")

        calls_engine = bool(_ENGINE_CALL_RE.search(text))

        if not calls_engine:
            findings.append(
                f"{rel}: {label} no longer calls diagnose.py / diagnose() — "
                "wiring appears to have regressed"
            )
        if _inline_reasoning_outside_fallback(text):
            findings.append(
                f"{rel}: {label} still contains the old bespoke inline "
                "category+confidence diagnosis logic outside a documented "
                "graceful-skip fallback — delegate to diagnose() instead"
            )
    return findings


def main() -> int:
    findings = check()
    if findings:
        for f in findings:
            print(f, file=sys.stderr)
        print(
            f"\ncheck-no-duplicate-diagnosis: {len(findings)} finding(s)",
            file=sys.stderr,
        )
        return 1
    print("check-no-duplicate-diagnosis: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
