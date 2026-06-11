#!/usr/bin/env python3
"""wiki_init.py — scaffold a repo's wiki to the intent-group IA (ADR 0018).

The logic behind the `wiki-init` plugin command (an agent action — plugins have
no target-repo install hook). Idempotent + preview-first: it computes the set of
files MISSING from the target's wiki/ and fills only those, never clobbering an
operator-authored page. It scaffolds the section folders, each with a section-index
landing (`<!-- mode: index -->`, exempt from the per-mode shape rules) and a
per-folder `_Sidebar.md`, plus the curated `Home.md` + root `_Sidebar.md`.

  python3 wiki_init.py --preview            # print the gap-fill plan, write nothing
  python3 wiki_init.py --sections a,b,c     # choose the folder set
  python3 wiki_init.py                       # apply the gap-fill (confirms first)

The scaffold is built so a freshly-provisioned wiki/ passes the bundled
check-wiki.py gate (a near-no-op run on an already-built wiki is the smoke test).
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

# Default section set — the four core doc folders the gate's _FOLDER_MODE maps
# (tutorial / how-to / reference / explanation in intent-group naming).
# Operator-confirmed 2026-06-10. designs/decisions/plugins are toolkit-specific,
# opt-in via --sections.
DEFAULT_SECTIONS = ["get-started", "do", "reference", "why"]

# section slug -> (landing basename, H1 title, one-line purpose). Drives both the
# plan (basename) and the render (title + purpose). Unknown sections fall back to
# a title-cased basename + the slug as title.
SECTION_META: dict[str, tuple[str, str, str]] = {
    "get-started": ("Get-Started", "Get started", "Tutorials and first steps."),
    "do": ("How-To", "How-to guides", "Task-focused recipes for getting things done."),
    "reference": ("Reference", "Reference", "Lookup-oriented technical detail."),
    "why": ("Why", "Why it works this way", "Background, rationale, and decisions."),
    "designs": ("Designs", "Designs", "Design docs for in-flight and shipped work."),
    "decisions": ("Decisions", "Decisions", "Architecture Decision Records."),
    "plugins": ("Plugins", "Plugins", "One page per plugin."),
}


def section_meta(section: str) -> tuple[str, str, str]:
    """(landing basename, H1 title, purpose) for a section — with a sane fallback
    for a section not in SECTION_META."""
    if section in SECTION_META:
        return SECTION_META[section]
    base = "-".join(w.capitalize() for w in section.split("-"))
    return (base, section, "")


@dataclass(frozen=True)
class ScaffoldItem:
    """One file the scaffold may create, relative to wiki/."""
    relpath: str               # e.g. "get-started/_Sidebar.md"
    kind: str                  # home | root_sidebar | landing | folder_sidebar
    section: str | None        # the section folder, or None for root-level items


def planned_items(sections: list[str]) -> list[ScaffoldItem]:
    """The full set of files a scaffold of `sections` would own (before gap-fill):
    the curated Home + root sidebar, then a landing + per-folder sidebar per section."""
    items = [
        ScaffoldItem("Home.md", "home", None),
        ScaffoldItem("_Sidebar.md", "root_sidebar", None),
    ]
    for s in sections:
        base = section_meta(s)[0]
        items.append(ScaffoldItem(f"{s}/{base}.md", "landing", s))
        items.append(ScaffoldItem(f"{s}/_Sidebar.md", "folder_sidebar", s))
    return items


def compute_scaffold_plan(existing: set[str], sections: list[str] | None = None) -> list[ScaffoldItem]:
    """Pure gap-fill plan: the wiki-relative files to CREATE given what already
    exists. Only missing paths are returned — an existing page is never in the
    plan, so apply can never clobber operator content. `existing` is the set of
    wiki-relative paths (e.g. {"Home.md", "reference/Reference.md"})."""
    sections = sections or DEFAULT_SECTIONS
    return [it for it in planned_items(sections) if it.relpath not in existing]


def parse_sections(raw: str | None) -> list[str]:
    """Parse a --sections value (comma/space separated) into a section list;
    None/empty -> the default set."""
    if not raw:
        return list(DEFAULT_SECTIONS)
    parts = [s.strip() for s in raw.replace(",", " ").split()]
    return [s for s in parts if s] or list(DEFAULT_SECTIONS)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Scaffold a repo's wiki to the intent-group IA.")
    ap.add_argument("--root", type=Path, default=Path("wiki"),
                    help="wiki root to scaffold (default: ./wiki)")
    ap.add_argument("--sections", default=None,
                    help=f"comma/space-separated section folders (default: {','.join(DEFAULT_SECTIONS)})")
    ap.add_argument("--preview", action="store_true",
                    help="print the gap-fill plan and write nothing")
    args = ap.parse_args(argv)

    sections = parse_sections(args.sections)
    existing = {str(p.relative_to(args.root)) for p in args.root.rglob("*") if p.is_file()} \
        if args.root.is_dir() else set()
    plan = compute_scaffold_plan(existing, sections)

    if not plan:
        print(f"wiki-init: ✓ {args.root} already scaffolded ({len(sections)} sections) — nothing to do.")
        return 0
    print(f"wiki-init: {len(plan)} file(s) to create under {args.root} "
          f"(sections: {', '.join(sections)}):")
    for it in plan:
        print(f"  + {args.root}/{it.relpath}  ({it.kind})")
    if args.preview:
        print("\n  preview only — re-run without --preview to write the gap-fill.")
        return 0
    # apply lands in the command surface (task 2); the pure plan is task 1.
    print("\n  (apply not wired in this entrypoint yet — see the wiki-init command)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
