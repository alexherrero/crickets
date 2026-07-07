#!/usr/bin/env python3
"""codebase-improvement -- scheduled stale-pattern detection onto the
watchlist (crickets wave-c-research, PLAN-wave-c-research-forward-learning
task 2).

Applies a research insight (a pattern a source says is outdated) to the
operator's own repo: scans for the pattern, and if found, surfaces exactly
ONE watchlist finding describing it -- never edits the repo itself. This is
the "codebase-improvement" half of the design's forward-learning pair
(wiki/designs/crickets-research.md): `learn-forward` mines external
sources, `codebase-improvement` checks whether what it found still applies
to code the operator actually owns.

Deliberately thin, stdlib-only detection (a substring/regex scan, not an
AST pass) -- matches the "small fixture repo containing one deliberately
stale pattern" scope this task's own verification names. Writes directly
in the SAME watchlist entry shape `forward_learning.py` uses
(`personal/_watchlist/<source-slug>/<item-slug>.md`, `status: pending-
review` + `evaluator_classification` frontmatter) so agentm's
`watchlist_review.py` picks it up as one merged review surface -- no
private agentm function is called to do this; the shape is small enough to
duplicate honestly rather than reach into agentm's internals.

Strictly discovery-surfacing: the matched files are named in the finding's
body, never modified. No auto-fix, ever.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

WATCHLIST_REL = Path("personal") / "_watchlist"
SOURCE_SLUG = "codebase-improvement"

# Directories a scan never descends into -- matches the repo hygiene any
# stale-pattern scan should already assume (VCS metadata, dependency trees).
_EXCLUDE_DIR_NAMES = frozenset({".git", "node_modules", "__pycache__", ".venv", "venv"})


@dataclass(frozen=True)
class ResearchInsight:
    slug: str
    title: str
    stale_pattern: str
    recommendation: str


def _iter_repo_files(repo_path: Path):
    for p in sorted(repo_path.rglob("*")):
        if not p.is_file():
            continue
        if any(part in _EXCLUDE_DIR_NAMES for part in p.relative_to(repo_path).parts[:-1]):
            continue
        yield p


def detect(repo_path: Path, insight: ResearchInsight) -> list:
    """Scan `repo_path` for files whose text contains `insight.stale_pattern`
    (a literal substring, not a regex -- keeps a fixture's expectations
    exact and avoids accidental catastrophic-backtracking on arbitrary
    operator input). Read-only; returns matching file paths, sorted."""
    matches = []
    for path in _iter_repo_files(repo_path):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if insight.stale_pattern in text:
            matches.append(path)
    return matches


def _slugify(text: str) -> str:
    out = []
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-") or "finding"


def _write_finding(vault: Path, insight: ResearchInsight, matches: list, *, now_iso: str) -> Path:
    entry_dir = vault / WATCHLIST_REL / SOURCE_SLUG
    entry_path = entry_dir / f"{_slugify(insight.slug)}.md"
    matched_list = "\n".join(f"- `{m}`" for m in matches)
    content = (
        "---\n"
        "kind: pattern\n"
        "status: pending-review\n"
        f"created: {now_iso}\n"
        f"updated: {now_iso}\n"
        f"source_slug: {SOURCE_SLUG}\n"
        f"insight_slug: {insight.slug}\n"
        "evaluator_classification: MEDIUM\n"
        "---\n"
        f"# {insight.title}\n\n"
        f"**Stale pattern:** `{insight.stale_pattern}`\n\n"
        f"**Recommendation:** {insight.recommendation}\n\n"
        "**Matched files (surfaced only -- not edited):**\n\n"
        f"{matched_list}\n"
    )
    entry_dir.mkdir(parents=True, exist_ok=True)
    # Same temp-then-rename convention as agentm's atomic_write -- avoids a
    # torn read if a concurrent watchlist_review scan is mid-walk.
    tmp = entry_path.with_suffix(entry_path.suffix + ".tmp")
    tmp.write_bytes(content.encode("utf-8"))
    tmp.replace(entry_path)
    return entry_path


def improve(
    vault: Path, repo_path: Path, insight: ResearchInsight, *, now: Optional[float] = None
) -> list:
    """Detect `insight.stale_pattern` in `repo_path`; if any file matches,
    write exactly ONE watchlist finding naming them all. Returns the list
    of watchlist entries written (0 or 1 -- never more, never a partial
    per-match fan-out). `repo_path` is never written to."""
    matches = detect(repo_path, insight)
    if not matches:
        return []
    now = now if now is not None else datetime.now(timezone.utc).timestamp()
    now_iso = datetime.fromtimestamp(now, tz=timezone.utc).replace(microsecond=0).isoformat()
    rel_matches = [str(m.relative_to(repo_path)) for m in matches]
    return [_write_finding(vault, insight, rel_matches, now_iso=now_iso)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="codebase-improvement -- scheduled stale-pattern detection onto the watchlist")
    parser.add_argument("--vault-path", required=True)
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--insight-slug", required=True)
    parser.add_argument("--insight-title", required=True)
    parser.add_argument("--stale-pattern", required=True)
    parser.add_argument("--recommendation", required=True)
    args = parser.parse_args(argv)

    insight = ResearchInsight(
        slug=args.insight_slug,
        title=args.insight_title,
        stale_pattern=args.stale_pattern,
        recommendation=args.recommendation,
    )
    written = improve(Path(args.vault_path), Path(args.repo_path), insight)
    print(f"codebase-improvement: {len(written)} finding(s) written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
