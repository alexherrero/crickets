#!/usr/bin/env python3
"""check-voice-floor-parity.py — the overlay->floor promotion parity gate
(PLAN-r3-voice-mechanism task 4).

base-style-guide.md's `banned:` line (src/wiki-maintenance/skills/diataxis-author/
style/base-style-guide.md) is the crickets-committed floor every fresh wiki
draft inherits without an overlay. Task 1's rule pack is the union of every
vault-global banned-list; if the floor ever falls behind that union again
(a repeat of the load-bearing/powerful/cutting-edge lag Task 4 fixed), this
catches it deterministically instead of waiting for the next audit.

Report-only (matches Task 2's check-slop.py posture) — `--report` forces
exit 0; the default and `--strict` exit codes exist for the parity check's
own test suite to exercise the real signal.

Stdlib-only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_DIATAXIS_SCRIPTS = (
    _HERE.parent / "src" / "wiki-maintenance" / "skills" / "diataxis-author" / "scripts"
)
if str(_DIATAXIS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIATAXIS_SCRIPTS))

import rule_pack  # noqa: E402
import check as diataxis_check  # noqa: E402

_BASE_STYLE_GUIDE = _DIATAXIS_SCRIPTS.parent / "style" / "base-style-guide.md"


def floor_banned_terms(base_style_guide_path: Path | None = None) -> set[str]:
    """The floor's actual banned set, parsed the same quote-aware way
    check.py's own convention-drift scanner reads it (never a second parser)."""
    path = base_style_guide_path or _BASE_STYLE_GUIDE
    text = path.read_text(encoding="utf-8")
    return set(diataxis_check._extract_banned_terms(text))


def rule_pack_word_phrase_terms(pack: dict | None = None) -> set[str]:
    """The rule pack's floor-eligible word/phrase-kind patterns.

    `floor_eligible: true` marks the subset meant as a blanket, cross-context
    ban appropriate for the committed floor every draft inherits — NOT every
    rule-pack entry. Excluded: genre-scoped marketing/architecture-metaphor
    phrases (user-facing-prose.md's scope is landing pages, not general
    design prose) and the research doc's broader A1-A4 catalog additions
    (chat artifacts, extra single words) that were never in any vault
    banned-list to begin with — promoting those would make check.py's
    untiered drift scanner trip on ordinary English ("vibrant", "intricate").
    """
    pack = pack if pack is not None else rule_pack.load_shipped_pack()
    return {
        r["pattern"].lower() for r in pack["rules"]
        if r["kind"] in ("word", "phrase") and r.get("floor_eligible")
    }


def missing_terms(base_style_guide_path: Path | None = None, pack: dict | None = None) -> set[str]:
    """Rule-pack terms absent from the floor — the lag this gate exists to catch."""
    return rule_pack_word_phrase_terms(pack) - floor_banned_terms(base_style_guide_path)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="check-voice-floor-parity", description=__doc__)
    p.add_argument("--base-style-guide", default=None, type=Path)
    p.add_argument("--report", action="store_true", help="always exit 0 — non-blocking wiring")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    missing = missing_terms(args.base_style_guide)
    if missing:
        print(f"check-voice-floor-parity: floor lags the rule pack by {len(missing)} "
              f"term(s): {sorted(missing)}")
    else:
        print("check-voice-floor-parity: floor is a superset of the rule pack — in sync")
    if args.report:
        return 0
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
