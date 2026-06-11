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
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

# The plugin root bundling our sibling scripts (vendor_gate, check-wiki) + the
# templates/ library — this file's dir's parent. Resolves correctly as the dist
# copy under ${CLAUDE_PLUGIN_ROOT}/scripts/.
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vendor_gate as _vendor  # noqa: E402  (sibling in the plugin's scripts/)

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


# --- template library (in-code) -----------------------------------------------
# Produces a wiki/ that passes the bundled check-wiki gate: landings are
# `<!-- mode: index -->` (exempt from the per-mode shape rules); per-folder +
# root _Sidebar.md together reference every content page (rule j); Home is
# curated. File-based / i18n templates are a future enhancement.

_LANDING = """<!-- mode: index -->
# {title}

_{purpose}_

Add pages under `{section}/` and list them in this folder's `_Sidebar.md`.
"""

_FOLDER_SIDEBAR = """### {title}

- [{title}]({landing_base})
"""


def render_landing(section: str) -> str:
    base, title, purpose = section_meta(section)
    return _LANDING.format(title=title, purpose=purpose or title, section=section)


def render_folder_sidebar(section: str) -> str:
    base, title, _ = section_meta(section)
    return _FOLDER_SIDEBAR.format(title=title, landing_base=base)


def render_root_sidebar(sections: list[str], project: str) -> str:
    lines = [f"### {project} Wiki", "", "- [Home](Home)"]
    for s in sections:
        base, title, _ = section_meta(s)
        lines.append(f"- [{title}]({base})")
    return "\n".join(lines) + "\n"


def render_home(sections: list[str], project: str) -> str:
    links = "  ".join(f"**[{section_meta(s)[1]}]({section_meta(s)[0]})**" for s in sections)
    return (
        f"# {project} Wiki\n\n"
        f"Welcome. Jump in: {links}.\n\n"
        f"_This wiki uses the intent-group structure "
        f"({' · '.join(sections)}); each folder has its own `_Sidebar.md`._\n"
    )


def render_item(item: ScaffoldItem, sections: list[str], project: str) -> str:
    """The file content for one scaffold item."""
    if item.kind == "home":
        return render_home(sections, project)
    if item.kind == "root_sidebar":
        return render_root_sidebar(sections, project)
    if item.kind == "landing":
        return render_landing(item.section)
    if item.kind == "folder_sidebar":
        return render_folder_sidebar(item.section)
    raise ValueError(f"unknown scaffold item kind: {item.kind}")


def apply_scaffold(root: Path, plan: list[ScaffoldItem], sections: list[str],
                   project: str) -> list[Path]:
    """Write every planned (gap-fill) item; return the paths written. Only plan
    items are written, and the plan excludes existing paths, so this never
    clobbers operator content."""
    written = []
    for it in plan:
        dest = root / it.relpath
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render_item(it, sections, project), encoding="utf-8")
        written.append(dest)
    return written


# --- CI provisioning: drop the workflows + vendor the gate ---------------------
# The publish (wiki-sync) + lint (wiki-lint) workflow templates, plus the vendored
# check-wiki gate (GH Actions has no ${CLAUDE_PLUGIN_ROOT}). Workflows are gap-fill
# (the user owns them after install — never overwrite); the gate is (re)vendored
# when missing or on --resync-gate.

TEMPLATE_WORKFLOWS = ["wiki-sync.yml", "wiki-lint.yml"]


def plan_ci(target_root: Path, plugin_root: Path = PLUGIN_ROOT,
            resync_gate: bool = False) -> dict:
    """What CI provisioning WOULD do (no writes): which workflows are missing
    (would be dropped) vs present (skipped), and whether the gate would be
    vendored. For --preview."""
    wf_dir = target_root / ".github" / "workflows"
    missing = [name for name in TEMPLATE_WORKFLOWS if not (wf_dir / name).exists()]
    skipped = [name for name in TEMPLATE_WORKFLOWS if (wf_dir / name).exists()]
    gate_dest = target_root / _vendor.VENDOR_REL
    gate = resync_gate or not gate_dest.exists()
    return {"workflows": missing, "skipped": skipped, "gate": gate}


def provision_ci(target_root: Path, plugin_root: Path = PLUGIN_ROOT,
                 resync_gate: bool = False) -> dict:
    """Drop the publish + lint workflow templates into <target>/.github/workflows/
    (gap-fill — never overwrites a user-owned workflow) and vendor the check-wiki
    gate into <target>/.github/scripts/. Returns {workflows, skipped, gate}."""
    workflows_src = plugin_root / "templates" / "workflows"
    wf_dir = target_root / ".github" / "workflows"
    written, skipped = [], []
    for name in TEMPLATE_WORKFLOWS:
        dest = wf_dir / name
        if dest.exists():
            skipped.append(dest)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(workflows_src / name, dest)
        written.append(dest)
    gate_dest = target_root / _vendor.VENDOR_REL
    gate = _vendor.vendor_gate(target_root, plugin_root) \
        if (resync_gate or not gate_dest.exists()) else None
    return {"workflows": written, "skipped": skipped, "gate": gate}


def default_project_name(root: Path) -> str:
    """A reasonable project name for Home/_Sidebar titles: the wiki's repo dir."""
    return root.resolve().parent.name or "Project"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Scaffold a repo's wiki to the intent-group IA + provision CI.")
    ap.add_argument("--root", type=Path, default=Path("wiki"),
                    help="wiki root to scaffold (default: ./wiki)")
    ap.add_argument("--sections", default=None,
                    help=f"comma/space-separated section folders (default: {','.join(DEFAULT_SECTIONS)})")
    ap.add_argument("--name", default=None,
                    help="project name for Home/_Sidebar titles (default: the repo dir name)")
    ap.add_argument("--preview", action="store_true",
                    help="print the gap-fill plan and write nothing")
    ap.add_argument("--yes", action="store_true",
                    help="skip the confirmation prompt before writing")
    ap.add_argument("--no-ci", action="store_true",
                    help="scaffold the wiki only; skip CI provisioning (workflows + gate)")
    ap.add_argument("--resync-gate", action="store_true",
                    help="re-vendor the check-wiki gate into .github/scripts/ and exit (post-upgrade)")
    args = ap.parse_args(argv)

    target_root = args.root.resolve().parent  # the repo root (wiki's parent)

    if args.resync_gate:
        dest = _vendor.vendor_gate(target_root, PLUGIN_ROOT)
        print(f"wiki-init: re-vendored gate -> {dest}")
        return 0

    sections = parse_sections(args.sections)
    project = args.name or default_project_name(args.root)
    existing = {str(p.relative_to(args.root)) for p in args.root.rglob("*") if p.is_file()} \
        if args.root.is_dir() else set()
    plan = compute_scaffold_plan(existing, sections)
    ci = plan_ci(target_root) if not args.no_ci else {"workflows": [], "skipped": [], "gate": False}

    if not plan and not ci["workflows"] and not ci["gate"]:
        print(f"wiki-init: ✓ {args.root} already scaffolded + CI provisioned — nothing to do.")
        return 0

    if plan:
        print(f"wiki-init: {len(plan)} wiki file(s) to create under {args.root} "
              f"(sections: {', '.join(sections)}):")
        for it in plan:
            print(f"  + {args.root}/{it.relpath}  ({it.kind})")
    if not args.no_ci and (ci["workflows"] or ci["gate"]):
        print(f"wiki-init: CI provisioning under {target_root}/.github/:")
        for name in ci["workflows"]:
            print(f"  + .github/workflows/{name}")
        if ci["gate"]:
            print("  + .github/scripts/check-wiki.py  (vendored gate)")
        for name in ci["skipped"]:
            print(f"  = .github/workflows/{name}  (exists — kept)")

    if args.preview:
        print("\n  preview only — re-run without --preview to write.")
        return 0
    if not args.yes:
        if input("\nProceed with the writes above? [y/N] ").strip().lower() not in ("y", "yes"):
            print("  aborted — nothing written.")
            return 0

    if plan:
        for p in apply_scaffold(args.root, plan, sections, project):
            print(f"  wrote {p}")
    if not args.no_ci:
        result = provision_ci(target_root)
        for p in result["workflows"]:
            print(f"  wrote {p}")
        if result["gate"]:
            print(f"  vendored {result['gate']}")
    print("wiki-init: done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
