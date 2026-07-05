#!/usr/bin/env python3
"""check-slop.py — deterministic anti-slop prose gate (PLAN-r3-voice-mechanism
task 2). Reads the versioned voice rule pack (Task 1's
src/wiki-maintenance/skills/diataxis-author/style/voice-rules.json, via
rule_pack.py) and scans markdown files for banned vocabulary, stock-phrase
templates, and Tier-B countable-metric drift.

Gate contract (per research-slop-detection-voice.md): "this prose contains a
banned pattern" — reproducible, fixable — never "this is AI-written". A regex
match, never a statistical/LLM classifier.

Severity tiers (locked design call — "report-only before strict, everywhere"):
  error      — Tier-A chat artifacts + citation residue only. Fails even
               without --strict (near-zero false-positive rate by design).
  warning    — Tier-A2 stock phrases, Tier-A3 templates, Tier-B metrics.
               Fails only under --strict.
  suggestion — Tier-A4 single banned words. NEVER fails, even under --strict
               (term-of-art carve-out risk is highest here — findings, not
               failures, until Task 5's carve-outs are written and Task 6's
               sweep has run).

FP-risk tiers (documented per-rule in voice-rules.json's own `hint` field, and
enforced by tier above):
  low            — single banned words with the term-of-art carve-out (A4).
  medium         — contrastive ", not Y" / prior-art templates (A3) — must
                   exempt Alternatives-Considered / amendment-log sections;
                   inline-ignore (below) is the escape hatch until a
                   section-aware exemption lands.
  high-until-cal — Tier-B metrics (em-dash / triad / bold / paragraph-variance).
                   Calibrated 2026-07-05 against prose-audit.json's 72 clean
                   pages (see voice-rules.json's per-rule `threshold`); the
                   operator's own approved register must never trip these.

Markdown-aware: fenced code blocks and link URLs are stripped before scanning
(a URL or code sample containing a banned word is not prose drift).

Inline-ignore (Vale-style): a trailing `<!-- slop-ignore: id1,id2 -->` comment
on a line suppresses those rule ids for that line only; `<!-- slop-ignore-start
-->` / `<!-- slop-ignore-end -->` suppress every rule inside the block (the
escape hatch for a real misconception-correction ", not Y" or an
Alternatives-Considered section).

Term-of-art allowlist: reuses rule_pack.py's existing overlay-by-id mechanism
(Task 1) — an overlay rule pack entry re-declaring a shipped id with
severity: "suggestion" downgrades it project-/repo-wide without editing this
script or the shipped pack. Task 5 codifies the two ratified carve-outs this
way (role-noun "the operator", term-of-art findings-not-failures).

--jsonl-out emits one aggregate {suite, axis, check, pass, weight} record
(mirrors scripts/health/jsonl_emit.py's contract) onto the agentm dashboard's
existing "docs+voice health" family (weight 5) — no separate wiring plan.

Exit codes: 0 clean (or --report); 1 any error finding, or any warning finding
under --strict. --report forces 0 always (check-all.sh's non-blocking wiring).

Stdlib-only.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_RULE_PACK_SCRIPTS = (
    _HERE.parent / "src" / "wiki-maintenance" / "skills" / "diataxis-author" / "scripts"
)
if str(_RULE_PACK_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_RULE_PACK_SCRIPTS))
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import rule_pack  # noqa: E402


# ── markdown-aware stripping ──────────────────────────────────────────────
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_LINK_URL_RE = re.compile(r"\]\([^)]*\)")
_INLINE_IGNORE_RE = re.compile(r"<!--\s*slop-ignore:\s*([\w,\-\s]+?)\s*-->")
_IGNORE_BLOCK_RE = re.compile(
    r"<!--\s*slop-ignore-start\s*-->.*?<!--\s*slop-ignore-end\s*-->", re.DOTALL
)


def strip_markdown_noise(text: str) -> str:
    """Strip fenced code blocks + link URLs (keeps link text) before scanning."""
    text = _FENCE_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    text = _LINK_URL_RE.sub("]", text)
    return text


def strip_ignore_blocks(text: str) -> str:
    """Strip slop-ignore-start/end blocks entirely (line-count preserved)."""
    return _IGNORE_BLOCK_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


# Structural nav pages (mirrors check-wiki.py's own exemption list) are bold-
# heavy link indexes, not prose — the Tier-B metrics were calibrated against
# prose-audit.json's explanation/how-to/reference corpus and don't apply here.
_STRUCTURAL_NAV_FILENAMES = {"home.md", "_sidebar.md", "_footer.md", "readme.md"}


def _is_structural_nav_file(path: Path) -> bool:
    return path.name.lower() in _STRUCTURAL_NAV_FILENAMES


def _line_ignored_ids(line: str) -> set[str]:
    m = _INLINE_IGNORE_RE.search(line)
    if not m:
        return set()
    return {t.strip() for t in m.group(1).split(",") if t.strip()}


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


# ── Tier-B metric computation ───────────────────────────────────────────────
_EM_DASH = "—"
_TRIAD_RE = re.compile(r"\b[\w][\w \-']{2,25}?, [\w][\w \-']{2,25}?,? and [\w][\w \-']{2,25}?\b")
_BOLD_RE = re.compile(r"\*\*[^*\n]+\*\*")


def _paragraphs(text: str) -> list[int]:
    paras = []
    for block in re.split(r"\n\s*\n", text):
        lines = [
            ln for ln in block.splitlines()
            if ln.strip() and not ln.strip().startswith(("#", "-", "*", "|", ">", "```"))
        ]
        if not lines:
            continue
        wc = word_count(" ".join(lines))
        if wc >= 10:
            paras.append(wc)
    return paras


def compute_metrics(text: str) -> dict[str, float | None]:
    """Compute the Tier-B countable metrics over one file's stripped text."""
    words = word_count(text)
    metrics: dict[str, float | None] = {
        "em_dash_rate_per_1k": 1000.0 * text.count(_EM_DASH) / words if words else 0.0,
        "triad_density_per_1k": 1000.0 * len(_TRIAD_RE.findall(text)) / words if words else 0.0,
        "bold_span_count_per_1k": 1000.0 * len(_BOLD_RE.findall(text)) / words if words else 0.0,
    }
    paras = _paragraphs(text)
    metrics["paragraph_length_variance_floor"] = (
        statistics.pvariance(paras) if len(paras) >= 2 else None
    )
    return metrics


# ── findings ─────────────────────────────────────────────────────────────────
@dataclass
class Finding:
    file: str
    line: int
    rule_id: str
    severity: str
    kind: str
    snippet: str
    hint: str


def _word_boundary_pattern(literal: str) -> re.Pattern:
    return re.compile(r"(?<!\w)" + re.escape(literal) + r"(?!\w)", re.IGNORECASE)


def scan_file(path: Path, rules: list[dict]) -> list[Finding]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    text = strip_ignore_blocks(strip_markdown_noise(raw))
    lines = text.splitlines()

    word_phrase_rules = [r for r in rules if r["kind"] in ("word", "phrase")]
    template_rules = [r for r in rules if r["kind"] == "template"]
    metric_rules = [r for r in rules if r["kind"] == "metric"]

    findings: list[Finding] = []

    for lineno, line in enumerate(lines, start=1):
        ignored = _line_ignored_ids(line)
        for rule in word_phrase_rules:
            if rule["id"] in ignored:
                continue
            m = _word_boundary_pattern(rule["pattern"]).search(line)
            if m:
                findings.append(Finding(
                    file=str(path), line=lineno, rule_id=rule["id"],
                    severity=rule["severity"], kind=rule["kind"],
                    snippet=m.group(0), hint=rule["hint"],
                ))
        for rule in template_rules:
            if rule["id"] in ignored:
                continue
            m = re.search(rule["pattern"], line, re.IGNORECASE)
            if m:
                findings.append(Finding(
                    file=str(path), line=lineno, rule_id=rule["id"],
                    severity=rule["severity"], kind=rule["kind"],
                    snippet=m.group(0), hint=rule["hint"],
                ))

    if metric_rules and not _is_structural_nav_file(path):
        metrics = compute_metrics(text)
        for rule in metric_rules:
            value = metrics.get(rule["pattern"])
            threshold = rule.get("threshold")
            if value is None or threshold is None:
                continue
            is_floor = rule["pattern"].endswith("_floor")
            tripped = value < threshold if is_floor else value > threshold
            if tripped:
                findings.append(Finding(
                    file=str(path), line=1, rule_id=rule["id"],
                    severity=rule["severity"], kind=rule["kind"],
                    snippet=f"{rule['pattern']}={value:.2f} (threshold {threshold})",
                    hint=rule["hint"],
                ))
    return findings


def scan_paths(paths: list[Path], rules: list[dict]) -> list[Finding]:
    findings: list[Finding] = []
    for p in paths:
        if p.is_dir():
            for md in sorted(p.rglob("*.md")):
                findings.extend(scan_file(md, rules))
        elif p.suffix == ".md":
            findings.extend(scan_file(p, rules))
    return findings


# ── reporting + exit code ───────────────────────────────────────────────────
def print_report(findings: list[Finding]) -> None:
    if not findings:
        print("check-slop: 0 findings")
        return
    by_sev = {"error": 0, "warning": 0, "suggestion": 0}
    for f in findings:
        by_sev[f.severity] += 1
        print(f"{f.severity.upper()}: {f.file}:{f.line}: [{f.rule_id}] "
              f"{f.snippet!r} — {f.hint}")
    print(f"check-slop: {len(findings)} finding(s) "
          f"({by_sev['error']} error, {by_sev['warning']} warning, "
          f"{by_sev['suggestion']} suggestion)")


def compute_exit_code(findings: list[Finding], *, strict: bool, report_only: bool) -> int:
    if report_only:
        return 0
    if any(f.severity == "error" for f in findings):
        return 1
    if strict and any(f.severity == "warning" for f in findings):
        return 1
    return 0


def emit_jsonl(jsonl_out: str | None, *, passed: bool | None) -> None:
    """Append one {suite, axis, check, pass, weight} record — self-contained
    (no health/jsonl_emit.py dependency) so this gate is portable to a repo
    that doesn't ship the crickets health/ package (e.g. agentm's own copy).
    `passed=None` marks a dark/skipped check (agentm's delegator when the
    crickets sibling isn't checked out) — excluded from health_score.py's
    numerator and denominator, same convention as scripts/health/jsonl_emit.py."""
    if not jsonl_out:
        return
    record = {
        "suite": "check-slop", "axis": "docs+voice health",
        "check": "voice-vocabulary-drift", "pass": passed, "weight": 5,
    }
    with open(jsonl_out, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


# ── CLI ──────────────────────────────────────────────────────────────────────
def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="check-slop",
        description="Deterministic anti-slop prose gate — reads the versioned voice rule pack.",
    )
    p.add_argument("paths", nargs="*", default=["wiki"],
                    help="files or directories to scan (default: wiki/)")
    p.add_argument("--strict", action="store_true",
                    help="fail on warning-severity findings too (error always fails)")
    p.add_argument("--report", action="store_true",
                    help="always exit 0 — non-blocking wiring for check-all.sh")
    p.add_argument("--jsonl-out", default=None, help="append a {suite,axis,check,pass,weight} record")
    p.add_argument("--vault-path", default=None, help="vault root for the rule-pack overlay")
    p.add_argument("--project-slug", default=None, help="project slug for the per-project overlay scope")
    p.add_argument("--wiki-root", default=None, help="repo root for the per-repo overlay scope")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    pack = rule_pack.load_rule_pack(
        vault_path=args.vault_path, project_slug=args.project_slug,
        wiki_root=args.wiki_root,
    )
    paths = [Path(p) for p in args.paths]
    findings = scan_paths(paths, pack["rules"])
    print_report(findings)
    exit_code = compute_exit_code(findings, strict=args.strict, report_only=args.report)
    emit_jsonl(args.jsonl_out, passed=(exit_code == 0))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
