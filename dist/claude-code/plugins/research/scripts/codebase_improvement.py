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
(`<watchlist>/<source-slug>/<item-slug>.md`, the watchlist that
`watchlist_dir()` below resolves; `status: pending-review` +
`evaluator_classification` frontmatter) so agentm's
`watchlist_review.py` picks it up as one merged review surface -- no
private agentm function is called to do this; the shape is small enough to
duplicate honestly rather than reach into agentm's internals.

Strictly discovery-surfacing: the matched files are named in the finding's
body, never modified. No auto-fix, ever.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

WATCHLIST_LEAF = "_watchlist"
SOURCE_SLUG = "codebase-improvement"


# agentm-vault plan 05 (2026-09-11): the watchlist is agentm's feature state
# and lives in the vault's project space, `Projects/agentm/_watchlist`. The
# project space sits at the VAULT root beside a nested memory root, or inside a
# flat one; the parent counts as the vault root on the witness agentm's
# vault_layout uses (`.obsidian/` or `standards/` there, no `.obsidian/` in the
# root). The watchlist's memory-space homes before that (`memory/`,
# `personal/`, `personal-private/`) are retired: nothing writes there any more,
# even on a vault that still has one.
FEATURE_PROJECT = "agentm"


# The root space's spellings, newest first: `projects/` since the root casing
# (agentm-vault plan 08, 2026-09-14), `Projects/` on a vault the rename has
# not reached. On a case-insensitive disk the two name one directory, and the
# first that exists wins.
_PROJECTS_SPELLINGS = ("projects", "Projects")


# The AgentKV layout (agentm task 176, the operator's ruling of 2026-09-24):
# the watchlist moved again, to the vault's shared reference library,
# `resources/watchlist/`, a vault-root space beside `projects/`. It is read
# and written there first; the project-space home is the fallback while a
# vault has not had the move.
RESOURCES_WATCHLIST = ("resources", "watchlist")


def _nested(vault: Path) -> bool:
    parent = vault.parent
    return not (vault / ".obsidian").is_dir() and (
        (parent / ".obsidian").is_dir() or (parent / "standards").is_dir())


def _resources_watchlist_candidates(vault: Path) -> list:
    roots = [vault.parent, vault] if _nested(vault) else [vault]
    return [r.joinpath(*RESOURCES_WATCHLIST) for r in roots]


def _project_watchlist_candidates(vault: Path) -> list:
    out = []
    parent = vault.parent
    if not (vault / ".obsidian").is_dir() and ((parent / ".obsidian").is_dir() or (parent / "standards").is_dir()):
        out.extend(parent / name / FEATURE_PROJECT / WATCHLIST_LEAF for name in _PROJECTS_SPELLINGS)
    out.extend(vault / name / FEATURE_PROJECT / WATCHLIST_LEAF for name in _PROJECTS_SPELLINGS)
    return out


def watchlist_dir(vault: Path) -> Path:
    """`resources/watchlist` at the vault root when it exists, else
    `projects/agentm/_watchlist` spelled as the disk lists it when that
    exists, else the new home. Never a retired memory-space home."""
    resources = _resources_watchlist_candidates(vault)
    for c in resources:
        if c.is_dir():
            return c
    for c in _project_watchlist_candidates(vault):
        if c.is_dir():
            return _as_listed(c, vault.parent if c.parent.parent.parent == vault.parent else vault)
    return resources[0]


def _as_listed(path: Path, base: Path) -> Path:
    """`path` with each segment below `base` spelled as its directory lists
    it. A case-insensitive disk opens `projects` on a vault still spelled
    `Projects`; the path handed back names what is there, on any disk."""
    try:
        rel = path.relative_to(base)
    except ValueError:
        return path
    out = base
    for part in rel.parts:
        try:
            names = {n.lower(): n for n in os.listdir(out)}
        except OSError:
            return path
        out = out / names.get(part.lower(), part)
    return out

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


def _entry_path(vault: Path, insight: ResearchInsight) -> Path:
    return watchlist_dir(vault) / SOURCE_SLUG / f"{_slugify(insight.slug)}.md"


def _read_frontmatter_field(entry_path: Path, field: str) -> "Optional[str]":
    if not entry_path.exists():
        return None
    prefix = f"{field}:"
    for line in entry_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def _write_finding(
    vault: Path, insight: ResearchInsight, matches: list, *, created_iso: str, updated_iso: str
) -> Path:
    entry_path = _entry_path(vault, insight)
    matched_list = "\n".join(f"- `{m}`" for m in matches)
    content = (
        "---\n"
        "kind: pattern\n"
        "status: pending-review\n"
        f"created: {created_iso}\n"
        f"updated: {updated_iso}\n"
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
    entry_path.parent.mkdir(parents=True, exist_ok=True)
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
    per-match fan-out). `repo_path` is never written to.

    Idempotent-safe on rescan: if a finding for this insight already exists
    AND an operator has already reviewed it (`status` is anything other
    than `pending-review`), this is a no-op -- a rescan (a scheduled job
    re-running over the same insight, or simply a new file joining an
    already-surfaced pattern) NEVER silently resets an operator's review
    decision back to `pending-review`. Only a still-`pending-review` entry
    (or no entry yet) gets (re)written, and `created` is preserved across
    those still-pending rewrites -- only `updated` and the matched-file
    list change."""
    matches = detect(repo_path, insight)
    if not matches:
        return []

    entry_path = _entry_path(vault, insight)
    existing_status = _read_frontmatter_field(entry_path, "status")
    if existing_status is not None and existing_status != "pending-review":
        return []

    now = now if now is not None else datetime.now(timezone.utc).timestamp()
    now_iso = datetime.fromtimestamp(now, tz=timezone.utc).replace(microsecond=0).isoformat()
    created_iso = _read_frontmatter_field(entry_path, "created") or now_iso
    rel_matches = [str(m.relative_to(repo_path)) for m in matches]
    return [_write_finding(vault, insight, rel_matches, created_iso=created_iso, updated_iso=now_iso)]


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
