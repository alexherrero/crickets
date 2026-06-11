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
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# The plugin root bundling our sibling scripts (vendor_gate, check-wiki) + the
# templates/ library — this file's dir's parent. Resolves correctly as the dist
# copy under ${CLAUDE_PLUGIN_ROOT}/scripts/.
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vendor_gate as _vendor  # noqa: E402  (sibling in the plugin's scripts/)

# Default section set — the ordered seven-section taxonomy (wiki-section-taxonomy
# design). Five always-present (how-to · reference · designs · explanation ·
# decisions) plus two CONDITIONAL slots: architecture (gated on a declared
# wiki/architecture.yml manifest — part 2) and operational (gated on non-public
# visibility — part 3). Architecture sits BEFORE designs (understanding-oriented
# component map first; per-feature designs follow).
DEFAULT_SECTIONS = ["how-to", "reference", "architecture", "designs",
                    "explanation", "decisions", "operational"]

# section slug -> (landing basename, H1 title, one-line purpose). Drives both the
# plan (basename) and the render (title + purpose). Unknown sections fall back to
# a title-cased basename + the slug as title. Basenames + titles mirror crickets'
# OWN (post-restructure) wiki so a wiki-init run on crickets stays a near-no-op —
# notably do -> how-to/How-To and why -> explanation/Explanation (reversing the
# earlier do->Do / why->Why-It-Works experiment; the crickets dogfood, part 4,
# moves the folders to match).
SECTION_META: dict[str, tuple[str, str, str]] = {
    "how-to": ("How-To", "How-to", "Task-focused recipes for getting things done."),
    "reference": ("Reference", "Reference", "Lookup-oriented technical detail."),
    "architecture": ("Architecture", "Architecture", "The structural component map — how the project is built."),
    "designs": ("Designs", "Designs", "Design docs for in-flight and shipped work."),
    "explanation": ("Explanation", "Explanation", "Background, rationale, and decisions."),
    "decisions": ("Decisions", "Decisions", "Architecture Decision Records."),
    "operational": ("Operational", "Operational", "Runbooks, SLAs, monitoring, and rollback (non-public wikis)."),
}


def section_meta(section: str) -> tuple[str, str, str]:
    """(landing basename, H1 title, purpose) for a section — with a sane fallback
    for a section not in SECTION_META."""
    if section in SECTION_META:
        return SECTION_META[section]
    base = "-".join(w.capitalize() for w in section.split("-"))
    return (base, section, "")


# The two conditional sections (wiki-section-taxonomy design): architecture is
# suppressed unless the project declares a wiki/architecture.yml manifest (gate
# wired in part 2); operational is suppressed on public/unknown wikis (visibility
# gate wired in part 3). The other five always render. This part owns only the
# mechanism — "given which conditionals are active, emit only the active sections."
CONDITIONAL_SECTIONS = frozenset({"architecture", "operational"})


def active_sections(sections: list[str], *, has_architecture: bool = False,
                    non_public: bool = False) -> list[str]:
    """Filter `sections` to those that should actually render: every always-present
    section, plus each conditional section only when its gate is on. Defaults
    suppress both conditionals — the gating inputs (manifest presence, visibility)
    are wired in parts 2-3, so a part-1 render emits the five always-present
    sections."""
    gated = {"architecture": has_architecture, "operational": non_public}
    return [s for s in sections
            if s not in CONDITIONAL_SECTIONS or gated.get(s, False)]


# --- the per-project Architecture manifest (wiki-section-taxonomy 2/6) ----------
# Architecture is the one section whose CONTENTS are per-project. Rather than
# hard-code sub-sections, the generator reads a small per-repo manifest —
# wiki/architecture.yml — listing each large component as {slug, title, summary,
# overview} plus an optional `pillars:` list of recurring toggles. The reader
# expands each pillar to its known template, validates, and fails CLOSED (scaffolds
# nothing on any violation). An absent/empty manifest suppresses Architecture
# entirely (conditional gate #1 — wired into main() via has_architecture). The
# nested sidebar render that consumes the ordered list is part 3 (render-and-gate).

@dataclass(frozen=True)
class Component:
    """One Architecture component: a folder `architecture/<slug>/` whose landing
    page is `<overview>.md`. `summary` is the landing's one-liner."""
    slug: str
    title: str
    summary: str
    overview: str              # landing basename within architecture/<slug>/


# Recurring components that ship as one-keyword `pillars:` toggles — they recur
# across the operator's sibling repos. Templates are deliberately repo-agnostic so
# they fit either side of a pair; a project that wants repo-specific wording adds a
# `components:` entry with the SAME slug to override the template's fields in place.
PILLAR_TEMPLATES: dict[str, Component] = {
    "host-adapters": Component(
        "host-adapters", "Host adapters",
        "How the toolkit adapts to each supported host.", "Host-Adapters"),
    "sibling-interface": Component(
        "sibling-interface", "Sibling interface",
        "The contract with the paired sibling repo.", "Sibling-Interface"),
    "distribution": Component(
        "distribution", "Build & distribution",
        "How the project is built and distributed to consumers.", "Build-And-Distribution"),
}

_REQUIRED_COMPONENT_KEYS = ("slug", "title", "summary", "overview")


class ManifestError(ValueError):
    """A malformed architecture.yml. Raising this is the fail-closed contract —
    main() turns it into a clear error and writes NOTHING (never a partial scaffold)."""


def parse_architecture_manifest(text: str) -> list[Component]:
    """Parse architecture.yml text into the ORDERED component list. Pillars expand
    first (in declared order) to their known templates; free-form `components:`
    follow (in declared order); a `components:` entry whose slug matches a pillar
    OVERRIDES that pillar's fields in place (the pillar's position is kept, the
    operator's wording wins). Raises ManifestError on any violation — an empty
    document (or empty `architecture:` block) yields [] (no Architecture)."""
    try:
        import yaml  # guarded — only imported when a manifest actually exists
    except ImportError as e:  # pragma: no cover - environment-dependent
        raise ManifestError(
            "architecture.yml is present but PyYAML is not installed "
            "(pip install pyyaml) — Architecture scaffolding needs it.") from e
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ManifestError(f"architecture.yml is not valid YAML: {e}") from e
    if data is None:
        return []                                  # empty file → no Architecture
    if not isinstance(data, dict) or "architecture" not in data:
        raise ManifestError("architecture.yml must have a top-level 'architecture:' mapping.")
    block = data["architecture"] or {}
    if not isinstance(block, dict):
        raise ManifestError("'architecture:' must be a mapping of pillars/components.")
    pillars = block.get("pillars") or []
    components_raw = block.get("components") or []
    if not isinstance(pillars, list):
        raise ManifestError("'pillars:' must be a list of toggle names.")
    if not isinstance(components_raw, list):
        raise ManifestError("'components:' must be a list of component mappings.")

    ordered: dict[str, Component] = {}
    for name in pillars:
        if name not in PILLAR_TEMPLATES:
            raise ManifestError(
                f"unknown pillar {name!r}. Known pillars: "
                f"{', '.join(sorted(PILLAR_TEMPLATES))}.")
        c = PILLAR_TEMPLATES[name]
        ordered[c.slug] = c
    for raw in components_raw:
        if not isinstance(raw, dict):
            raise ManifestError("each 'components:' entry must be a mapping.")
        missing = [k for k in _REQUIRED_COMPONENT_KEYS if not str(raw.get(k, "")).strip()]
        if missing:
            raise ManifestError(
                f"'components:' entry {raw.get('slug', '?')!r} is missing required "
                f"key(s): {', '.join(missing)}.")
        c = Component(str(raw["slug"]).strip(), str(raw["title"]).strip(),
                      str(raw["summary"]).strip(), str(raw["overview"]).strip())
        ordered[c.slug] = c                        # override-in-place on slug collision
    return list(ordered.values())


def read_architecture_manifest(wiki_root: Path) -> list[Component]:
    """Read `<wiki_root>/architecture.yml` into the ordered component list. An
    absent file yields [] (Architecture cleanly suppressed — NOT an error); a
    present-but-malformed file raises ManifestError (fail closed)."""
    manifest = wiki_root / "architecture.yml"
    if not manifest.is_file():
        return []
    return parse_architecture_manifest(manifest.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class ScaffoldItem:
    """One file the scaffold may create, relative to wiki/."""
    relpath: str               # e.g. "how-to/_Sidebar.md"
    kind: str                  # home | root_sidebar | landing | folder_sidebar
                               #   | arch_landing | arch_folder_sidebar
    section: str | None        # the section folder, or None for root-level items
    component: str | None = None  # the Architecture component slug, for arch_* kinds


def architecture_items(components: list[Component]) -> list[ScaffoldItem]:
    """The scaffold items for the Architecture components, in manifest order: a
    section landing (`architecture/<slug>/<overview>.md`) + a per-component
    `_Sidebar.md` per entry. The third-level nested render that lists these in the
    Architecture section's sidebar is part 3 (render-and-gate)."""
    items: list[ScaffoldItem] = []
    for c in components:
        items.append(ScaffoldItem(
            f"architecture/{c.slug}/{c.overview}.md", "arch_landing", "architecture", c.slug))
        items.append(ScaffoldItem(
            f"architecture/{c.slug}/_Sidebar.md", "arch_folder_sidebar", "architecture", c.slug))
    return items


def planned_items(sections: list[str],
                  components: list[Component] | None = None) -> list[ScaffoldItem]:
    """The full set of files a scaffold of `sections` would own (before gap-fill):
    the curated Home + root sidebar, then a landing + per-folder sidebar per section.
    When `architecture` is among the sections AND `components` is non-empty, each
    component's folder (landing + `_Sidebar.md`) is scaffolded right after the
    Architecture section's own landing."""
    components = components or []
    items = [
        ScaffoldItem("Home.md", "home", None),
        ScaffoldItem("_Sidebar.md", "root_sidebar", None),
    ]
    for s in sections:
        base = section_meta(s)[0]
        items.append(ScaffoldItem(f"{s}/{base}.md", "landing", s))
        items.append(ScaffoldItem(f"{s}/_Sidebar.md", "folder_sidebar", s))
        if s == "architecture" and components:
            items.extend(architecture_items(components))
    return items


def compute_scaffold_plan(existing: set[str], sections: list[str] | None = None,
                          components: list[Component] | None = None) -> list[ScaffoldItem]:
    """Pure gap-fill plan: the wiki-relative files to CREATE given what already
    exists. Only missing paths are returned — an existing page is never in the
    plan, so apply can never clobber operator content. `existing` is the set of
    wiki-relative paths (e.g. {"Home.md", "reference/Reference.md"}). `components`
    (from the Architecture manifest) adds the per-component folders when present."""
    sections = sections or DEFAULT_SECTIONS
    return [it for it in planned_items(sections, components) if it.relpath not in existing]


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

# An Architecture component landing — index-mode (architecture/ folders are
# index-mode in check-wiki), keyed on the component's summary.
_ARCH_LANDING = """<!-- mode: index -->
# {title}

_{summary}_

Pages for the {title} component go under `architecture/{slug}/`; list them in this folder's `_Sidebar.md`.
"""


def render_landing(section: str) -> str:
    base, title, purpose = section_meta(section)
    return _LANDING.format(title=title, purpose=purpose or title, section=section)


def render_folder_sidebar(section: str) -> str:
    base, title, _ = section_meta(section)
    return _FOLDER_SIDEBAR.format(title=title, landing_base=base)


def render_arch_landing(component: Component) -> str:
    return _ARCH_LANDING.format(
        title=component.title, summary=component.summary, slug=component.slug)


def render_arch_folder_sidebar(component: Component) -> str:
    return _FOLDER_SIDEBAR.format(title=component.title, landing_base=component.overview)


def render_root_sidebar(sections: list[str], project: str,
                        components: list[Component] | None = None) -> str:
    """The root _Sidebar.md: Home + one bullet per active section. When
    `architecture` is among the sections AND components are declared, the
    Architecture bullet expands into an indented sub-block — one sub-bullet per
    component, in manifest order, each linking to its overview page. This third
    nesting level (ADR 0018's root→folder model is two levels; this is the one new
    render mechanic, wiki-section-taxonomy 3/6) is the ONLY nested render: every
    other section stays a flat top-level bullet. Two-space indent is the
    GitHub-flavored-Markdown nested-list convention."""
    components = components or []
    lines = [f"### {project} Wiki", "", "- [Home](Home)"]
    for s in sections:
        base, title, _ = section_meta(s)
        lines.append(f"- [{title}]({base})")
        if s == "architecture" and components:
            for c in components:
                lines.append(f"  - [{c.title}]({c.overview})")
    return "\n".join(lines) + "\n"


def render_home(sections: list[str], project: str) -> str:
    links = "  ".join(f"**[{section_meta(s)[1]}]({section_meta(s)[0]})**" for s in sections)
    return (
        f"# {project} Wiki\n\n"
        f"Welcome. Jump in: {links}.\n\n"
        f"_This wiki uses the intent-group structure "
        f"({' · '.join(sections)}); each folder has its own `_Sidebar.md`._\n"
    )


def render_item(item: ScaffoldItem, sections: list[str], project: str,
                components: list[Component] | None = None) -> str:
    """The file content for one scaffold item. `components` (manifest order) is
    needed only for the arch_* kinds — looked up by the item's component slug."""
    if item.kind == "home":
        return render_home(sections, project)
    if item.kind == "root_sidebar":
        return render_root_sidebar(sections, project, components)
    if item.kind == "landing":
        return render_landing(item.section)
    if item.kind == "folder_sidebar":
        return render_folder_sidebar(item.section)
    if item.kind in ("arch_landing", "arch_folder_sidebar"):
        by_slug = {c.slug: c for c in (components or [])}
        component = by_slug[item.component]
        return (render_arch_landing(component) if item.kind == "arch_landing"
                else render_arch_folder_sidebar(component))
    raise ValueError(f"unknown scaffold item kind: {item.kind}")


def apply_scaffold(root: Path, plan: list[ScaffoldItem], sections: list[str],
                   project: str, components: list[Component] | None = None) -> list[Path]:
    """Write every planned (gap-fill) item; return the paths written. Only plan
    items are written, and the plan excludes existing paths, so this never
    clobbers operator content. `components` carries the Architecture manifest for
    the arch_* items."""
    written = []
    for it in plan:
        dest = root / it.relpath
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render_item(it, sections, project, components), encoding="utf-8")
        written.append(dest)
    return written


# --- CI provisioning: drop the workflow + vendor the gate ----------------------
# The single lint-then-publish wiki workflow template (wiki-sync.yml: a lint-wiki
# job runs the gate, an update-wiki job publishes only `needs: lint-wiki`), plus
# the vendored check-wiki gate the lint job invokes (GH Actions has no
# ${CLAUDE_PLUGIN_ROOT}). The workflow is gap-fill (the user owns it after install
# — never overwrite); the gate is (re)vendored when missing or on --resync-gate.

TEMPLATE_WORKFLOWS = ["wiki-sync.yml"]


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
    """Drop the lint-then-publish wiki workflow template into
    <target>/.github/workflows/ (gap-fill — never overwrites a user-owned workflow)
    and vendor the check-wiki gate into <target>/.github/scripts/. Returns
    {workflows, skipped, gate}."""
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


# --- non-public cost warning ---------------------------------------------------
# GitHub Actions minutes are free only on PUBLIC repos. Dropping the wiki workflow
# onto a private/internal target adds a billed-minutes surface (it runs the gate on
# every push/PR and publishes on the default branch), so we warn (and the
# confirmation gate stops) before the workflow lands. The requirement is
# operator-locked: "the non-public-only cost warning." An undeterminable
# visibility (gh missing / not a GitHub repo / network error) is treated
# conservatively — warn, but say we couldn't confirm.

def _gh_visibility(target_root: Path) -> str:
    """Shell out to `gh` for the target repo's visibility (the runtime detector)."""
    out = subprocess.run(
        ["gh", "repo", "view", "--json", "visibility", "-q", ".visibility"],
        cwd=target_root, capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def detect_visibility(target_root: Path, fetch=_gh_visibility) -> str:
    """The target repo's GitHub visibility, lowercased ('public' | 'private' |
    'internal'), or 'unknown' if it can't be determined. `fetch` is injectable
    for testing; any failure (gh absent, not a GitHub repo, network) → 'unknown'."""
    try:
        v = fetch(target_root).strip().lower()
    except Exception:
        return "unknown"
    return v or "unknown"


def cost_warning(visibility: str) -> str | None:
    """The billed-Actions warning for a non-public target, or None for a public
    one. Public repos run Actions free; private/internal (or undeterminable)
    targets bill the wiki workflow against the account's quota."""
    if visibility == "public":
        return None
    if visibility == "unknown":
        return ("⚠ Could not determine this repo's visibility. If it is NOT public, "
                "the wiki workflow will consume billed GitHub Actions minutes. "
                "Public repos run free.")
    return (f"⚠ This repo is {visibility}. The wiki workflow will consume billed "
            "GitHub Actions minutes — Actions is free only on public repos. "
            "Proceed only if that billing is acceptable.")


def renders_operational(visibility: str) -> bool:
    """Whether the Operational conditional section renders, given the repo's
    visibility (wiki-section-taxonomy 3/6 — the visibility gate). `private` and
    `internal` are both non-public and render it (the axis is AUDIENCE, not
    content-sensitivity — both get Operational); `public` and `unknown` suppress
    it (conservative on an undeterminable visibility). Feeds `active_sections`'
    `non_public` gate in main()."""
    return visibility in ("private", "internal")


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
    ap.add_argument("--visibility", default=None,
                    choices=["public", "private", "internal", "unknown"],
                    help="override repo-visibility detection (default: auto-detect via gh)")
    args = ap.parse_args(argv)

    target_root = args.root.resolve().parent  # the repo root (wiki's parent)

    if args.resync_gate:
        dest = _vendor.vendor_gate(target_root, PLUGIN_ROOT)
        print(f"wiki-init: re-vendored gate -> {dest}")
        return 0

    sections = parse_sections(args.sections)
    # Read the per-project Architecture manifest (wiki/architecture.yml). Absent /
    # empty → [] (Architecture suppressed); malformed → fail closed, write nothing.
    try:
        components = read_architecture_manifest(args.root)
    except ManifestError as e:
        print(f"wiki-init: ✗ {e}", file=sys.stderr)
        return 1
    # Repo visibility drives two gates — detect once (gh shell-out; → 'unknown' on
    # any failure), reuse for both: (1) Operational renders only on non-public
    # wikis (the conditional-section gate, below); (2) the billed-Actions cost
    # warning fires on non-public CI provisioning (further down).
    visibility = args.visibility or detect_visibility(target_root)
    # Suppress undeclared conditional sections: architecture gates on a declared
    # manifest (conditional gate #1); operational gates on non-public visibility
    # (conditional gate #2 — public/unknown suppress, private/internal render).
    sections = active_sections(sections, has_architecture=bool(components),
                               non_public=renders_operational(visibility))
    project = args.name or default_project_name(args.root)
    existing = {str(p.relative_to(args.root)) for p in args.root.rglob("*") if p.is_file()} \
        if args.root.is_dir() else set()
    plan = compute_scaffold_plan(existing, sections, components)
    ci = plan_ci(target_root) if not args.no_ci else {"workflows": [], "skipped": [], "gate": False}

    # Cost warning fires only when this run would ADD a billing surface — i.e.
    # at least one workflow would be dropped — on a non-public target.
    warn = cost_warning(visibility) if (not args.no_ci and ci["workflows"]) else None

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

    if warn:
        print(f"\n{warn}")

    if args.preview:
        print("\n  preview only — re-run without --preview to write.")
        return 0
    if not args.yes:
        prompt = ("\nNon-public target — proceed and bill Actions minutes? [y/N] "
                  if warn else "\nProceed with the writes above? [y/N] ")
        if input(prompt).strip().lower() not in ("y", "yes"):
            print("  aborted — nothing written.")
            return 0

    if plan:
        for p in apply_scaffold(args.root, plan, sections, project, components):
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
