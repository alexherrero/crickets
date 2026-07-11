#!/usr/bin/env python3
"""check-cross-repo-script-parity.py — keeps crickets' canonical check-no-pii.sh
and check-wiki.py honest against agentm's independently-maintained copies
(CONS-2 task 4, the Consolidation arc's crickets-slim lane).

crickets ships its OWN canonical copy of each of these two scripts inside a
plugin's src/ tree (src/privacy/scripts/check-no-pii.sh,
src/wiki/scripts/check-wiki.py) -- agentm carries its own top-level
scripts/check-no-pii.sh / scripts/check-wiki.py, evolved independently as the
kernel repo's own gate battery. The two pairs are NOT meant to be
byte-identical: each repo's copy carries repo-specific plumbing (self-skip
paths, allowlists) that has no business existing in the other repo, and each
side has grown its own not-yet-ported feature (see below). What SHOULD stay
in sync is the actual detection/rule CONTRACT -- the set of PII "kinds"
check-no-pii.sh scans for, and the set of lettered content rules
check-wiki.py enforces -- because a kind or rule silently added to one copy
and never ported to the other is real, un-intentional drift worth a human's
attention.

This gate is deliberately NOT a byte-diff (an exact-match assertion would
permanently red this check on the two known, understood, intentional
divergences below) -- it compares just the kind-name / rule-letter sets,
mirroring check-opinion-self-provider-drift.py's own "not a byte-diff by
design" posture and check-dist-references.py's grandfather-list idiom for
naming a known exception explicitly rather than silently swallowing it.

Known, intentional one-sided divergence (as of CONS-2 task 4, 2026-07-10):

  - check-wiki.py: crickets' copy carries 3 extra rules (m, n, o) that
    enforce a component-overview section model (architecture/<slug>/<Base>.md
    landing pages, the section library shipped with crickets' wiki-maintenance
    diataxis-author skill, DC-5). agentm's wiki has no such page-type in its
    taxonomy, so these 3 rules have never been ported there -- porting them
    would no-op (zero matching pages), never add real coverage. Listed in
    ALLOWED_CRICKETS_ONLY_RULES below so this check doesn't cry wolf on a
    known asymmetry.
  - check-wiki.py: agentm's copy carries a --jsonl-out flag (a
    {suite,axis,check,pass,weight} health-axis record for agentm's own AA5 C7
    tracking) that crickets has no use for. This isn't a lettered rule (it's
    a CLI/output feature), so it never enters the rule-letter comparison
    below and needs no explicit exemption.
  - check-no-pii.sh: SELF_SKIP_PATHS and ALLOWLIST_PATTERNS legitimately
    differ between the two copies (each repo skips its own files and
    allowlists its own known-safe strings, e.g. crickets' `@crickets.local`
    synthetic hook identity). This check only compares PATTERNS kind names --
    the actual detection contract -- never these repo-specific lists.

Exit 0: every kind/rule matches (modulo the documented exemption above), or
        agentm is absent (graceful skip -- printed distinctly from a match)
Exit 1: an undocumented kind/rule divergence was found
Exit 2: usage/read error (a named crickets-side canonical file is missing --
        that's a real config problem, not agentm-sibling absence)

--report forces exit 0 (non-blocking wiring), matching every other
agentm-sibling-dependent gate's posture (check-opinion-snapshot-parity.py,
check-opinion-self-provider-drift.py).

Stdlib-only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src_model import find_agentm_scripts_dir  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CRICKETS_NO_PII = _REPO_ROOT / "src" / "privacy" / "scripts" / "check-no-pii.sh"
_DEFAULT_CRICKETS_WIKI = _REPO_ROOT / "src" / "wiki" / "scripts" / "check-wiki.py"

# See the module docstring's "Known, intentional one-sided divergence" note.
ALLOWED_CRICKETS_ONLY_RULES = {"m", "n", "o"}

_RULE_DEF_RE = re.compile(r"^\s*def rule_([a-z])_", re.MULTILINE)
_PATTERN_KIND_RE = re.compile(r"^\s*'([a-zA-Z][a-zA-Z0-9-]*)\|", re.MULTILINE)


def rule_letters(text: str) -> set[str]:
    """The set of lettered check-wiki.py rule identifiers (`rule_a_...` ->
    "a") a file's `def rule_X_...` function names declare."""
    return set(_RULE_DEF_RE.findall(text))


def pattern_kinds(text: str) -> set[str]:
    """The set of PII "kind" names a check-no-pii.sh PATTERNS array declares
    (the `KIND` half of each `'KIND|REGEX'` entry). Matches only the
    PATTERNS array's own `kind|regex` shape -- SELF_SKIP_PATHS and
    ALLOWLIST_PATTERNS entries have no adjacent `|` and never match."""
    return set(_PATTERN_KIND_RE.findall(text))


def compare_wiki_rules(crickets_text: str, agentm_text: str) -> list[str]:
    crickets_rules = rule_letters(crickets_text)
    agentm_rules = rule_letters(agentm_text)
    crickets_only = crickets_rules - agentm_rules - ALLOWED_CRICKETS_ONLY_RULES
    agentm_only = agentm_rules - crickets_rules
    findings = []
    if crickets_only:
        findings.append(
            f"check-wiki.py: crickets has rule(s) {sorted(crickets_only)} that "
            f"agentm doesn't, and they're not in the documented "
            f"ALLOWED_CRICKETS_ONLY_RULES exemption {sorted(ALLOWED_CRICKETS_ONLY_RULES)} "
            f"-- port the rule to agentm, or add it to the exemption if it's "
            f"intentionally crickets-only")
    if agentm_only:
        findings.append(
            f"check-wiki.py: agentm has rule(s) {sorted(agentm_only)} that "
            f"crickets doesn't -- crickets is the canonical copy, port it back")
    return findings


def compare_no_pii_kinds(crickets_text: str, agentm_text: str) -> list[str]:
    crickets_kinds = pattern_kinds(crickets_text)
    agentm_kinds = pattern_kinds(agentm_text)
    crickets_only = crickets_kinds - agentm_kinds
    agentm_only = agentm_kinds - crickets_kinds
    findings = []
    if crickets_only:
        findings.append(
            f"check-no-pii.sh: crickets detects kind(s) {sorted(crickets_only)} "
            f"that agentm doesn't -- port it")
    if agentm_only:
        findings.append(
            f"check-no-pii.sh: agentm detects kind(s) {sorted(agentm_only)} "
            f"that crickets doesn't -- crickets is the canonical copy, port it back")
    return findings


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="check-cross-repo-script-parity", description=__doc__)
    p.add_argument("--crickets-no-pii-script", default=None, type=Path)
    p.add_argument("--crickets-wiki-script", default=None, type=Path)
    p.add_argument("--agentm-scripts-dir", default=None, type=Path,
                    help="override agentm scripts/ dir discovery (tests)")
    p.add_argument("--report", action="store_true", help="always exit 0 — non-blocking wiring")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    crickets_no_pii = args.crickets_no_pii_script or _DEFAULT_CRICKETS_NO_PII
    crickets_wiki = args.crickets_wiki_script or _DEFAULT_CRICKETS_WIKI

    if not crickets_no_pii.is_file():
        print(f"check-cross-repo-script-parity: error: crickets canonical "
              f"file missing: {crickets_no_pii}")
        return 2
    if not crickets_wiki.is_file():
        print(f"check-cross-repo-script-parity: error: crickets canonical "
              f"file missing: {crickets_wiki}")
        return 2

    agentm_dir = args.agentm_scripts_dir or find_agentm_scripts_dir()
    if agentm_dir is None or not agentm_dir.is_dir():
        print("check-cross-repo-script-parity: agentm sibling not found — "
              "SKIPPING (nothing was compared, this is not a pass)")
        return 0

    agentm_no_pii = agentm_dir / "check-no-pii.sh"
    agentm_wiki = agentm_dir / "check-wiki.py"
    if not agentm_no_pii.is_file() or not agentm_wiki.is_file():
        print(f"check-cross-repo-script-parity: agentm sibling at {agentm_dir} "
              f"is missing check-no-pii.sh and/or check-wiki.py — SKIPPING "
              f"(nothing was compared, this is not a pass)")
        return 0

    findings: list[str] = []
    findings += compare_no_pii_kinds(
        crickets_no_pii.read_text(encoding="utf-8"),
        agentm_no_pii.read_text(encoding="utf-8"),
    )
    findings += compare_wiki_rules(
        crickets_wiki.read_text(encoding="utf-8"),
        agentm_wiki.read_text(encoding="utf-8"),
    )

    if findings:
        print(f"check-cross-repo-script-parity: {len(findings)} undocumented "
              f"divergence(s):")
        for line in findings:
            print(f"  {line}")
    else:
        print("check-cross-repo-script-parity: check-no-pii.sh + check-wiki.py "
              "detection contracts match agentm (modulo the documented "
              "component-overview rule exemption) — in sync")

    if args.report:
        return 0
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
