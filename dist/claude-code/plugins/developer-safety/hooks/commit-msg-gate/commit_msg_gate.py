#!/usr/bin/env python3
"""commit_msg_gate.py — deterministic commit-msg git hook: plain-English-at-
the-door (Consolidation ruling 4, shipped CONS-8).

Ruling 4's "Commit messages, go-forward" standard: a subject a stranger can
read; the conventional prefix (`feat:`/`fix:`/...) stays (release tooling
sizes versions from it); a roadmap id is fine in parentheses (e.g.
`(V6-15)`); internal codenames (the `AA`/`C`/`FIN`/`R`/`G` families, "Wave
A"..."Wave E", `PLAN-<slug>` references) are banned from the subject line —
they belong in pack files and progress.md only. This module is the
mechanical enforcement ruling 4 calls for: "a commit-message git hook in the
existing developer-safety hook family ... rejects codename patterns and
slop-pack vocabulary in the subject line."

Two independent checks, both scoped to the SUBJECT LINE ONLY (first line of
the commit message file) — never the body, where a fuller narrative
(including a codename, for traceability) is fine:

  1. Codename patterns — the six shapes named in the ruling, matched by
     regex. A roadmap id in parentheses is explicitly allowed (CONS-4's own
     PR-title treatment): parenthesized spans are stripped before this check
     runs, so `(V6-15)` never trips anything, codename-shaped or not.

  2. Slop-pack vocabulary — reuses this repo's OWN canonical rule pack
     (`src/wiki/skills/diataxis-author/style/voice-rules.json`, read via its
     existing loader `rule_pack.py`) rather than inventing a second word
     list, so the wiki gate and this gate can never drift apart. Only
     error/warning severity rules apply (suggestion-tier terms — the highest
     false-positive-risk single words — stay allowed in a commit subject,
     same tiering logic check-slop.py already uses for the wiki gate). Only
     word/phrase/template rule kinds apply; `metric` rules are a per-1000-
     word document-level signal (em-dash rate, paragraph variance, ...) that
     doesn't have a meaningful denominator on a ~10-word subject line, so
     they're skipped here by design, not by oversight.

Graceful-skip, mirroring coauthor-guard's determinism discipline: a missing/
unreadable message file is a no-op (exit 0); if the shared rule pack can't be
found (e.g. this file was copied out standalone into `.git/hooks/`, without
its `src/wiki/...` sibling tree), the codename check still runs and the
vocabulary check is skipped with a one-line stderr notice — this gate never
hard-fails a commit over its own missing dependency.

Stdlib-only.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# ── locate + import the shared voice rule-pack loader ───────────────────────
# Resolved via `git rev-parse --show-toplevel` rather than a fixed number of
# `__file__.parent`s: a live end-to-end install test (CONS-8) found that a
# static parents[N] walk breaks the moment this file is copied to a different
# depth (e.g. installed standalone alongside its .sh/.ps1 twin directly under
# `.git/hooks/`, only one level below the repo root instead of four). A git
# hook always runs inside a git repository, so "ask git for the repo root" is
# the one location fact that holds across every install layout — in-place
# inside src/developer-safety/hooks/commit-msg-gate/, copied alongside its
# twins into .git/hooks/, or anywhere else. When the resolved root has no
# src/wiki/... tree at all (a standalone install outside a full crickets/
# agentm checkout), the import is skipped -- same graceful-skip outcome the
# static-path version had for that case, now reached without a wrong-path
# crash for the *other* install layouts.
def _find_repo_root() -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    top = result.stdout.strip()
    return Path(top) if top else None


_rule_pack = None
_repo_root = _find_repo_root()
if _repo_root is not None:
    _RULE_PACK_SCRIPTS = (
        _repo_root / "src" / "wiki" / "skills" / "diataxis-author" / "scripts"
    )
    if (_RULE_PACK_SCRIPTS / "rule_pack.py").is_file():
        if str(_RULE_PACK_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(_RULE_PACK_SCRIPTS))
        try:
            import rule_pack as _rule_pack  # noqa: E402
        except ImportError:
            _rule_pack = None


# ── codename patterns (ruling 4's named families) ───────────────────────────
# Parenthesized spans are stripped before this list runs — the roadmap-id-in-
# parens exemption (CONS-4's PR-title precedent) applies to ALL of these, not
# just the V-prefixed roadmap shape (which doesn't collide with this family
# anyway: none of AA/C/FIN/R/G start with "V").
_PAREN_RE = re.compile(r"\([^)]*\)")

_CODENAME_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("codename-aa", re.compile(r"\bAA-?\d+[a-z]?\b")),
    ("codename-fin", re.compile(r"\bFIN-?\d+[a-z]?\b")),
    ("codename-c", re.compile(r"\bC-?\d+[a-z]?\b")),
    ("codename-r", re.compile(r"\bR-?\d+(?:\.\d+)?[a-z]?\b")),
    ("codename-g", re.compile(r"\bG-?\d+[a-z]?\b")),
    ("codename-wave", re.compile(r"\bWave [A-E]\b")),
    ("codename-plan-slug", re.compile(r"\bPLAN-[A-Za-z0-9][\w-]*\b")),
]
# Ordered longest-prefix-first (FIN before C, AA before... nothing shorter
# collides) purely for readable output when a subject trips more than one —
# match correctness doesn't depend on the order since each pattern is
# independently `\b`-anchored.


def find_codenames(subject: str) -> list[tuple[str, str]]:
    """Return [(rule_id, matched_text), ...] for every codename family found.

    Operates on `subject` with parenthesized spans blanked out first (a
    roadmap id in parentheses, e.g. "(V6-15)", is a real cross-reference —
    CONS-4's own PR-title precedent — never a codename).
    """
    stripped = _PAREN_RE.sub(" ", subject)
    hits: list[tuple[str, str]] = []
    for rule_id, pattern in _CODENAME_PATTERNS:
        m = pattern.search(stripped)
        if m:
            hits.append((rule_id, m.group(0)))
    return hits


# ── slop-pack vocabulary (reuses rule_pack.py — never a second word list) ───
def _word_boundary_pattern(literal: str) -> re.Pattern:
    """Mirrors check-slop.py's own word/phrase matcher exactly (non-\\w-bounded,
    case-insensitive) so the two gates never silently diverge in what counts
    as a match."""
    return re.compile(r"(?<!\w)" + re.escape(literal) + r"(?!\w)", re.IGNORECASE)


def _load_rules() -> list[dict]:
    """Load the shipped voice rule pack. Returns [] (graceful-skip) if the
    rule_pack module or the pack file itself is unavailable — this hook must
    never hard-fail a commit over its own missing dependency."""
    if _rule_pack is None:
        print(
            "commit-msg-gate: rule_pack.py not importable (no src/wiki/ sibling "
            "tree found) — skipping the slop-vocabulary check; codename check "
            "still applies.",
            file=sys.stderr,
        )
        return []
    try:
        pack = _rule_pack.load_shipped_pack()
    except Exception as exc:  # noqa: BLE001 — any load failure is graceful-skip
        print(
            f"commit-msg-gate: voice rule pack failed to load ({exc}) — "
            f"skipping the slop-vocabulary check; codename check still applies.",
            file=sys.stderr,
        )
        return []
    return pack.get("rules", [])


_BLOCKING_SEVERITIES = ("error", "warning")
_LINE_LEVEL_KINDS = ("word", "phrase", "template")


def find_slop(subject: str, rules: list[dict]) -> list[dict]:
    """Return matching error/warning-tier word/phrase/template findings.

    Suggestion-tier (the single-word AI-tell adjectives — highest false-
    positive risk) is deliberately excluded: ruling 2's "warning-tier and
    above blocks" convention, same tiering the wiki gate already uses.
    `metric`-kind rules are skipped too — they're a per-1000-word document
    signal with no meaningful denominator on one subject line.
    """
    findings: list[dict] = []
    for rule in rules:
        if rule.get("severity") not in _BLOCKING_SEVERITIES:
            continue
        kind = rule.get("kind")
        if kind in ("word", "phrase"):
            m = _word_boundary_pattern(rule["pattern"]).search(subject)
        elif kind == "template":
            m = re.search(rule["pattern"], subject, re.IGNORECASE)
        else:
            continue
        if m:
            findings.append({
                "id": rule["id"], "severity": rule["severity"],
                "snippet": m.group(0), "hint": rule["hint"],
            })
    return findings


# ── reporting ────────────────────────────────────────────────────────────────
def render_rejection(subject: str, codename_hits: list[tuple[str, str]],
                      slop_hits: list[dict]) -> str:
    lines = [
        "commit-msg-gate: REJECTED — commit subject fails the plain-English-at-"
        "the-door standard (Consolidation ruling 4).",
        f'  subject: "{subject}"',
        "",
    ]
    if codename_hits:
        lines.append("  codename pattern(s) found:")
        for rule_id, text in codename_hits:
            lines.append(f"    [{rule_id}] {text!r}")
    if slop_hits:
        lines.append("  slop-pack vocabulary (warning-tier or above):")
        for f in slop_hits:
            lines.append(f"    [{f['id']}] {f['snippet']!r} — {f['hint']}")
    lines += [
        "",
        "Fix: rewrite the subject so a stranger could read it. Keep the",
        "conventional-commit prefix (feat:/fix:/docs:/chore:/refactor:/perf:/...)",
        "— release tooling sizes versions from it. A roadmap id is fine in",
        "parentheses, e.g. \"(V6-15)\". Internal codenames (AA/C/FIN/R/G, wave",
        "letters) and PLAN-<slug> references belong in pack files and",
        "progress.md only, never the commit subject. Suggestion-tier vocabulary",
        "terms are still allowed here — only warning-tier and above block.",
    ]
    return "\n".join(lines)


# ── main ─────────────────────────────────────────────────────────────────────
def read_subject(msg_file: Path) -> str:
    text = msg_file.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    return lines[0] if lines else ""


def main(argv: list[str]) -> int:
    if len(argv) < 2 or not argv[1]:
        return 0
    msg_file = Path(argv[1])
    if not msg_file.is_file():
        return 0

    try:
        subject = read_subject(msg_file)
    except OSError:
        return 0
    if not subject.strip():
        return 0

    codename_hits = find_codenames(subject)
    slop_hits = find_slop(subject, _load_rules())

    if not codename_hits and not slop_hits:
        return 0

    print(render_rejection(subject, codename_hits, slop_hits), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
