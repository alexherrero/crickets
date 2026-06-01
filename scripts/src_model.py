#!/usr/bin/env python3
"""Shared model + parsing for the crickets `src/` source-of-truth tree.

Used by `scripts/lint_src.py` (validation) and `scripts/generate.py` (emission)
so the two share one parser. Requires PyYAML (CI installs it; mirrors
validate-manifests.py / lint_src.py).
"""
from __future__ import annotations

import re
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
}
KNOWN_KIND_DIRS = {"skills", "hooks", "agents", "commands", "mcp", "rules"}


def read_frontmatter(path: Path):
    """Return the parsed YAML frontmatter dict, or None if the file has none."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return None
    return yaml.safe_load(m.group(1)) or {}


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
class Group:
    slug: str
    name: str
    description: str
    category: str
    requires: list[str]
    standalone: bool
    primitives: list[Primitive] = field(default_factory=list)
    manifest: Path | None = None

    def supports(self, host: str) -> bool:
        """A group targets a host if any of its primitives do."""
        return any(p.supports(host) for p in self.primitives)


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
        group = Group(
            slug=gd.name,
            name=meta.get("name", gd.name),
            description=meta.get("description", ""),
            category=meta.get("category", "Coding"),
            requires=requires,
            standalone=bool(meta.get("standalone", not requires)),
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
