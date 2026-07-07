#!/usr/bin/env python3
"""Shared model + parsing for the crickets `src/` source-of-truth tree.

Used by `scripts/lint_src.py` (validation) and `scripts/generate.py` (emission)
so the two share one parser. Requires PyYAML (CI installs it).
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover — callers guard before parsing
    yaml = None  # type: ignore

KIND_ENUM = {
    "skill", "agent", "hook", "command", "mcp-server", "status-line",
    "output-style", "workflow", "rule", "snippet", "settings-fragment",
}
HOST_ENUM = {"claude-code", "antigravity"}

# kind -> (glob relative to a group dir, fn(manifest_path) -> primitive name)
PRIMITIVE_KINDS = {
    "skill": ("skills/*/SKILL.md", lambda p: p.parent.name),
    "hook": ("hooks/*/hook.md", lambda p: p.parent.name),
    "agent": ("agents/*.md", lambda p: p.stem),
    "command": ("commands/*.md", lambda p: p.stem),
    "output-style": ("output-styles/*.md", lambda p: p.stem),
    "rule": ("rules/*.md", lambda p: p.stem),
    "snippet": ("snippets/*.md", lambda p: p.stem),
}
# kind -> the hosts whose emitter actually turns that kind into real output
# (R2.1 / cricketsBuild#1). A primitive's `supported_hosts:` frontmatter is a
# CLAIM; this table is the corresponding fact, read from each emitter's own
# dispatch (scripts/emit_claude.py, scripts/emit_antigravity.py). Kept in
# sync manually — when an emitter's dispatch gains or drops a kind for a
# host, update this table in the same change; `lint_src.py` fails a primitive
# whose `supported_hosts` names a host not listed here for its kind.
KIND_HOST_EXPRESSIBLE: dict[str, frozenset[str]] = {
    "skill": frozenset({"claude-code", "antigravity"}),
    "agent": frozenset({"claude-code", "antigravity"}),
    "command": frozenset({"claude-code", "antigravity"}),
    "hook": frozenset({"claude-code", "antigravity"}),
    "mcp-server": frozenset({"claude-code", "antigravity"}),
    "output-style": frozenset({"claude-code", "antigravity"}),
    "rule": frozenset({"claude-code", "antigravity"}),
    # emit_claude.py explicitly drops snippet ("Claude has no instruction-file
    # primitive") — a deliberate, logged coverage gap, not a bug.
    "snippet": frozenset({"antigravity"}),
}

KNOWN_KIND_DIRS = {"skills", "hooks", "agents", "commands", "snippets", "mcp", "output-styles", "rules", "scripts", "templates", "reference"}
# `scripts/`, `templates/`, and `reference/` are NOT primitive kinds — they're
# group-level asset dirs copied verbatim into the emitted plugin (e.g. code-review's
# cross-review.sh; wiki-maintenance's wiki-sync.yml + section-template library;
# conventions' reference/gate-inventory.md). Listed here so lint doesn't flag it as
# an unexpected kind folder. `reference/` docs are deliberately NOT primitives (no
# name/description/kind/supported_hosts/version frontmatter required) — they are
# objective house facts a rule cites, not a lifecycle-bearing thing to install/
# enable/update on its own (crickets-conventions.md's "cited, not gated").


def read_frontmatter(path: Path):
    """Return the parsed YAML frontmatter dict, or None if the file has none."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return None
    return yaml.safe_load(m.group(1)) or {}


def _strip_frontmatter(text: str) -> str:
    """Return `text` with a leading YAML frontmatter block removed, or `text`
    unchanged if it has none. Mirrors `read_frontmatter`'s own delimiter match."""
    m = re.match(r"^---\n.*?\n---\n?", text, re.S)
    return text[m.end():] if m else text


# opinion-consumer markdown-prose grammar (PLAN-opinion-consumer-grammar task 2).
# A primitive that is genuine cross-plugin reuse of an opinion (its `opinions:`
# name does NOT `implements:` the primitive's own capability) declares the name
# in `opinions:` and marks the splice point in its own body with an HTML-comment
# pair, `<!-- opinion:<name> --> ... <!-- /opinion:<name> -->`. At emit time the
# marked block's contents are replaced with the committed snapshot's body (never
# a live agentm read — see scripts/check-opinion-snapshot-parity.py). A
# self-provider primitive (its opinion `implements:` itself) declares `opinions:`
# too, but has no marker in its body — it stays hardwired prose, honesty-checked
# separately, and this function is a no-op for it (no marker to replace).
_OPINION_SNAPSHOTS_DIR = Path(__file__).resolve().parent / "opinion-snapshots"


def _opinion_marker_re(name: str) -> re.Pattern:
    open_tag = re.escape(f"<!-- opinion:{name} -->")
    close_tag = re.escape(f"<!-- /opinion:{name} -->")
    return re.compile(f"{open_tag}.*?{close_tag}", re.S)


def interpolate_opinions(text: str, opinions: list, snapshots_dir: Path | None = None) -> str:
    """Splice each declared opinion's committed-snapshot body into its marker
    pair inside `text`. A name with no marker present, or no matching snapshot
    file, is left untouched (covers the self-provider case, and a not-yet-baked
    cross-plugin opinion) -- so this is always safe to call unconditionally."""
    snapshots_dir = snapshots_dir or _OPINION_SNAPSHOTS_DIR
    for name in opinions:
        pattern = _opinion_marker_re(str(name))
        if not pattern.search(text):
            continue
        snapshot_path = snapshots_dir / f"{name}.md"
        if not snapshot_path.is_file():
            continue
        body = _strip_frontmatter(snapshot_path.read_text(encoding="utf-8")).strip()
        replacement = f"<!-- opinion:{name} -->\n{body}\n<!-- /opinion:{name} -->"
        text = pattern.sub(lambda _m, r=replacement: r, text, count=1)
    return text


def render_primitive_text(prim: "Primitive", snapshots_dir: Path | None = None) -> str:
    """Return a single-file primitive's emitted text, with any declared
    `opinions:` markers interpolated from the committed snapshot store — ready
    for `write_utf8`. A primitive with no `opinions:` frontmatter key returns
    its source text unchanged -- byte-identical (once `write_utf8`-encoded) to
    the plain `copy2` this replaces, for every primitive that doesn't opt in."""
    text = prim.root.read_text(encoding="utf-8")
    opinions = prim.frontmatter.get("opinions") or []
    if not opinions:
        return text
    return interpolate_opinions(text, opinions, snapshots_dir)


@dataclass
class Primitive:
    name: str
    kind: str
    supported_hosts: list[str]
    manifest: Path          # the frontmatter file (SKILL.md / hook.md / <agent>.md)
    root: Path              # primitive root: the dir (skill/hook) or the .md file (agent)
    frontmatter: dict

    def supports(self, host: str) -> bool:
        return host in self.supported_hosts


@dataclass
class Enhance:
    """A soft-composition edge: this plugin augments `group` (optionally its
    `capability`) when both are installed. Declarative metadata — the runtime
    engages via a capability probe, not a host primitive. Does NOT imply a hard
    dependency (that is `requires`)."""
    group: str
    capability: str | None
    effect: str


def parse_enhance(entry) -> "Enhance":
    """Normalize one `group.yaml` `enhances:` entry. Accepts the string shorthand
    (`enhances: [other-group]`) or the dict form (`{group, capability?, effect}`).
    Lenient — `lint_src.py` validates the result."""
    if isinstance(entry, str):
        return Enhance(group=entry, capability=None, effect="")
    if isinstance(entry, dict):
        cap = entry.get("capability")
        return Enhance(
            group=str(entry.get("group", "")),
            capability=str(cap) if cap is not None else None,
            effect=str(entry.get("effect", "")),
        )
    return Enhance(group="", capability=None, effect="")  # malformed → lint flags


def enhances_to_json(enhances: "list[Enhance]") -> list[dict]:
    """Serialize `enhances` to JSON-friendly dicts for emitted metadata
    (`capability`/`effect` omitted when empty)."""
    out = []
    for e in enhances:
        d: dict = {"group": e.group}
        if e.capability is not None:
            d["capability"] = e.capability
        if e.effect:
            d["effect"] = e.effect
        out.append(d)
    return out


@dataclass
class Group:
    slug: str
    name: str
    description: str
    category: str
    requires: list[str]
    standalone: bool
    primitives: list[Primitive] = field(default_factory=list)
    manifest: Path | None = None
    # soft-composition fields appended (keep positional order stable for callers
    # that build Group(..., primitives) positionally — e.g. the emit tests)
    enhances: list[Enhance] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    # per-plugin marketplace version (the `version:` in group.yaml). Independent
    # of the per-primitive frontmatter versions. Bumping it is what lets
    # `claude plugin update <slug>@crickets` pull new primitives — the marketplace
    # entry compares this value. Defaults to "0.1.0" for groups built positionally
    # (the emit tests) or whose group.yaml omits the key. Appended LAST so the
    # positional ctor `Group(..., primitives)` stays valid.
    version: str = "0.1.0"

    def has_group_assets(self) -> bool:
        """True when the group carries a host-agnostic group-level asset payload —
        a `scripts/`, `templates/`, or `reference/` dir. Such a payload is emittable
        (and must emit, so the dist plugin actually carries it) even when the group
        has zero host primitives: e.g. `obsidian-vault`, whose only payload is the
        agentm-discovered storage backend under `scripts/` (LC-2 — a backend is
        engine-consumed, not a host primitive)."""
        if self.manifest is None:
            return False
        gd = self.manifest.parent
        return (gd / "scripts").is_dir() or (gd / "templates").is_dir() or (gd / "reference").is_dir()

    def supports(self, host: str) -> bool:
        """A group targets a host if any of its primitives do, or it carries a
        host-agnostic group-level asset payload (`scripts/`/`templates/`) — those
        are copied wholesale to every host, so an asset-only group emits on all."""
        return any(p.supports(host) for p in self.primitives) or self.has_group_assets()


# Transient/gitignored cruft excluded from EVERY bundled-asset copytree (group
# scripts/ AND primitive roots — skills, hooks) so the emitted dist/ stays
# deterministic + drift-free regardless of whether tests (or anything else)
# compiled a bundled .py into __pycache__ before the build runs. The factory
# returns a fresh ignore callable per call (shutil's is stateless, but keeping
# it a factory avoids any shared-state surprise).
def bundle_ignore():
    """The `ignore=` filter shared by all bundled-asset copytrees."""
    # `.harness` (R2.1 / cricketsBuild#3): a plan-in-progress can leave a
    # `.harness/` under a group's `scripts/`/`templates/` asset root — it's
    # in .gitignore, but a bare copytree doesn't consult .gitignore, so
    # without this it would leak into the emitted dist/ payload.
    return shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", ".harness")


def copy_group_scripts(group: "Group", plugin_dir: Path) -> None:
    """Copy a group's verbatim `scripts/` asset dir (e.g. code-review's
    `cross-review.sh`) into the emitted plugin at `<plugin_dir>/scripts/`.

    NOT a discovered primitive — a wholesale, host-agnostic asset bundle. No-op
    when the group has no manifest (synthetic groups built positionally) or no
    `scripts/` dir. Shared by both host emitters."""
    if group.manifest is None:
        return
    src_scripts = group.manifest.parent / "scripts"
    if src_scripts.is_dir():
        shutil.copytree(
            src_scripts, plugin_dir / "scripts", dirs_exist_ok=True,
            ignore=bundle_ignore())


def copy_group_templates(group: "Group", plugin_dir: Path) -> None:
    """Copy a group's verbatim `templates/` asset dir into the emitted plugin at
    `<plugin_dir>/templates/`. Like `copy_group_scripts` — a wholesale,
    host-agnostic asset bundle (e.g. wiki-maintenance's `workflows/wiki-sync.yml`
    + the section-template library `wiki-init` scaffolds from). No-op when the
    group has no manifest or no `templates/` dir. Shared by both host emitters."""
    if group.manifest is None:
        return
    src_templates = group.manifest.parent / "templates"
    if src_templates.is_dir():
        shutil.copytree(
            src_templates, plugin_dir / "templates", dirs_exist_ok=True,
            ignore=bundle_ignore())


def copy_group_reference(group: "Group", plugin_dir: Path) -> None:
    """Copy a group's verbatim `reference/` asset dir into the emitted plugin at
    `<plugin_dir>/reference/`. Like `copy_group_scripts`/`copy_group_templates` —
    a wholesale, host-agnostic asset bundle (e.g. conventions' `gate-inventory.md`).
    No-op when the group has no manifest or no `reference/` dir. Shared by both
    host emitters."""
    if group.manifest is None:
        return
    src_reference = group.manifest.parent / "reference"
    if src_reference.is_dir():
        shutil.copytree(
            src_reference, plugin_dir / "reference", dirs_exist_ok=True,
            ignore=bundle_ignore())


def load_groups(src: Path) -> list[Group]:
    """Parse the `src/` tree into Group/Primitive model objects (no validation).

    Deterministic: groups + primitives are returned in sorted path order.
    """
    groups: list[Group] = []
    if not src.is_dir():
        return groups
    for gd in sorted(p for p in src.iterdir() if p.is_dir()):
        gy = gd / "group.yaml"
        meta = yaml.safe_load(gy.read_text(encoding="utf-8")) or {} if gy.exists() else {}
        requires = list(meta.get("requires") or [])
        enhances = [parse_enhance(e) for e in (meta.get("enhances") or [])]
        capabilities = [str(c) for c in (meta.get("capabilities") or [])]
        group = Group(
            slug=gd.name,
            name=meta.get("name", gd.name),
            description=meta.get("description", ""),
            category=meta.get("category", "Coding"),
            requires=requires,
            standalone=bool(meta.get("standalone", not requires)),
            enhances=enhances,
            capabilities=capabilities,
            version=str(meta.get("version", "0.1.0")),
            manifest=gy if gy.exists() else None,
        )
        for kind, (glb, name_of) in PRIMITIVE_KINDS.items():
            for mp in sorted(gd.glob(glb)):
                fm = read_frontmatter(mp) or {}
                root = mp.parent if kind in ("skill", "hook") else mp
                group.primitives.append(Primitive(
                    name=fm.get("name", name_of(mp)),
                    kind=fm.get("kind", kind),
                    supported_hosts=list(fm.get("supported_hosts") or []),
                    manifest=mp,
                    root=root,
                    frontmatter=fm,
                ))
        groups.append(group)
    return groups
