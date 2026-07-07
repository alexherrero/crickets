#!/usr/bin/env python3
"""`/design finalize` tooling (crickets wave-c-design-and-conventions, task
3): auto-collapse the amendment log + flag a stale `[PENDING-IMPL]`
placeholder, replacing today's by-hand process.

Design call (documented, not silently decided): staleness is doc-level, not
per-marker -- a doc's `[PENDING-IMPL]` marker(s) are stale iff the doc's own
`governs:` frontmatter target already exists on disk, mirroring the real,
already-established signal agentm's `scripts/health/designed_vs_built.py`
uses (governs target exists + no PENDING-IMPL == built) and the real
"flip [PENDING-IMPL] markers now the engine shipped" commits this repo's
own history already does by hand -- those flip every marker in a doc once
its whole governed target ships, not one marker in isolation. A precise
per-marker staleness check would need to associate each individual marker
with its own narrower target, which no existing convention supports
today; PLAN-wave-c-design-and-conventions's own Out of scope excludes a
wiki-wide sweep, so this doc-level signal is exercised by fixtures only,
never against the real corpus in this plan.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import architecture_rung  # noqa: E402

_PENDING_IMPL_RE = re.compile(r"\[PENDING-IMPL\]")
_AMENDMENT_LOG_HEADING_RE = re.compile(r"^##[ \t]+Amendment log[ \t]*$", re.MULTILINE)
_AMENDMENT_BULLET_RE = re.compile(r"^\*\*(\d{4}-\d{2}-\d{2})\*\*\s*(?:—|--)\s*(.*)$")


def check_stale_placeholders(doc_path: "str | Path", repo_root: "str | Path") -> dict:
    """A doc's `[PENDING-IMPL]` marker(s) are stale iff its own `governs:`
    target already exists on disk (a `governs:` glob matches at least one
    real file under `repo_root`) while the doc still claims the target is
    unbuilt. Returns {"has_pending_impl", "governs", "governed_target_exists",
    "stale"}."""
    doc_path = Path(doc_path)
    repo_root = Path(repo_root)
    text = doc_path.read_text(encoding="utf-8")
    lists = architecture_rung.parse_frontmatter_lists(text)
    governs = lists.get("governs", [])
    has_pending = bool(_PENDING_IMPL_RE.search(text))
    governed_exists = any(any(repo_root.glob(pattern)) for pattern in governs)
    return {
        "has_pending_impl": has_pending,
        "governs": governs,
        "governed_target_exists": governed_exists,
        "stale": has_pending and bool(governs) and governed_exists,
    }


def collapse_amendment_log(text: str) -> str:
    """Collapse consecutive same-day `## Amendment log` bullets
    (`**YYYY-MM-DD** — ...`) into one bullet per day, joining descriptions
    with a space -- mirrors the full design-doc template's own Document
    History same-day consolidation convention. Content outside the
    Amendment log section (including the heading itself) is untouched."""
    m = _AMENDMENT_LOG_HEADING_RE.search(text)
    if not m:
        return text
    head, body = text[: m.end()], text[m.end():]

    collapsed: list = []  # list of [date, [descriptions]]
    for line in body.splitlines():
        bullet = _AMENDMENT_BULLET_RE.match(line.strip())
        if bullet is None:
            if line.strip():
                # Non-bullet content (a blank line, or prose) -- preserve
                # verbatim by flushing it as its own passthrough entry.
                collapsed.append([None, [line]])
            continue
        date, desc = bullet.group(1), bullet.group(2)
        if collapsed and collapsed[-1][0] == date:
            collapsed[-1][1].append(desc)
        else:
            collapsed.append([date, [desc]])

    lines = []
    for date, descs in collapsed:
        if date is None:
            lines.append(descs[0])
        else:
            lines.append(f"**{date}** — {' '.join(d for d in descs if d)}")
    return head + "\n" + "\n".join(lines) + "\n"


def finalize(doc_path: "str | Path", repo_root: "str | Path") -> dict:
    """Runs the finalize pass: check staleness first (never silently
    collapse over a stale placeholder), then collapse the amendment log if
    clean. Returns {"stale": {...}, "collapsed_text": str | None} --
    `collapsed_text` is None when `stale["stale"]` is True (the caller
    should surface the finding and NOT write anything)."""
    stale = check_stale_placeholders(doc_path, repo_root)
    if stale["stale"]:
        return {"stale": stale, "collapsed_text": None}
    text = Path(doc_path).read_text(encoding="utf-8")
    return {"stale": stale, "collapsed_text": collapse_amendment_log(text)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="/design finalize -- amendment-log collapse + stale-placeholder check")
    parser.add_argument("doc_path")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--write", action="store_true", help="write the collapsed text back to doc_path")
    args = parser.parse_args(argv)

    result = finalize(args.doc_path, args.repo_root)
    if result["collapsed_text"] is None:
        sys.stderr.write(
            f"[design_finalize] stale [PENDING-IMPL] placeholder(s) in {args.doc_path}: "
            f"governs {result['stale']['governs']!r} already exists on disk but the doc "
            f"still claims it's unbuilt. Not auto-collapsing -- resolve the marker(s) first.\n"
        )
        return 2
    if args.write:
        Path(args.doc_path).write_text(result["collapsed_text"], encoding="utf-8")
        print(f"[design_finalize] amendment log collapsed and written to {args.doc_path}")
    else:
        print(result["collapsed_text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
