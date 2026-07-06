#!/usr/bin/env python3
"""check-no-dangling-name.py — repo-wide dangling-plugin/capability-name gate
(PLAN-wave-a-repoints task 1, AG Wave A's closing pass).

Two checks:

  1. Every `src/*/group.yaml`'s `requires:` / `enhances:` (bare-list and
     `{group: ...}` mapping forms) names a group slug that resolves to an
     existing `src/<slug>/` directory. (`lint_src.py` already enforces this
     per-plugin as part of its schema validation; this gate re-asserts it as
     part of the permanent repo-wide regression net the wave's rename
     mechanism needs — a name that resolves to nothing is exactly the
     failure mode a botched rename produces.)
  2. Every `find_capability.py <name>`-style capability-name invocation in
     `src/**/commands/*.md` / `src/**/skills/**/*.md` / `wiki/**/*.md`
     (excluding designs' own Amendment-log sections) names a capability
     declared by at least one group's `capabilities:` list.

**Permissive of dual-names by design.** An OLD name is not a violation as
long as it still resolves to something (a directory, or a declared
capability) — that is the whole point of Wave A's declare-both-names
mechanism. This gate only catches a reference that resolves to **nothing**.
It is not an old-name-usage linter; that is a different, later gate (the one
that runs when a name is actually dropped).

Run: `python3 scripts/check-no-dangling-name.py`
Requires PyYAML (CI installs it).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("check-no-dangling-name: PyYAML not installed — skipping (pip install pyyaml)", file=sys.stderr)
    sys.exit(0)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
WIKI = ROOT / "wiki"

_FIND_CAPABILITY_RE = re.compile(r"find_capability\.py[\"']\s+([a-zA-Z][a-zA-Z0-9-]*)")


def _load_groups(src: Path) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    if not src.is_dir():
        return groups
    for gd in sorted(p for p in src.iterdir() if p.is_dir()):
        gy = gd / "group.yaml"
        if not gy.is_file():
            continue
        try:
            data = yaml.safe_load(gy.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            data = {}
        if isinstance(data, dict):
            groups[gd.name] = data
    return groups


def _all_capabilities(groups: dict[str, dict]) -> set[str]:
    caps: set[str] = set()
    for data in groups.values():
        declared = data.get("capabilities")
        if isinstance(declared, list):
            caps.update(c for c in declared if isinstance(c, str))
    return caps


def _group_slug_edges(gy: Path, data: dict) -> list[tuple[str, str, int]]:
    """[(field, target_slug, line_no)] for this group.yaml's requires:/enhances:."""
    edges: list[tuple[str, str, int]] = []
    lines = gy.read_text(encoding="utf-8").splitlines()

    def line_of(key: str) -> int:
        for i, ln in enumerate(lines, 1):
            if re.match(rf"^\s*{re.escape(key)}\s*:", ln):
                return i
        return 1

    requires = data.get("requires") or []
    if isinstance(requires, list):
        for r in requires:
            if isinstance(r, str):
                edges.append(("requires", r, line_of("requires")))

    enhances = data.get("enhances") or []
    if isinstance(enhances, list):
        for entry in enhances:
            if isinstance(entry, str):
                edges.append(("enhances", entry, line_of("enhances")))
            elif isinstance(entry, dict) and isinstance(entry.get("group"), str):
                edges.append(("enhances", entry["group"], line_of("enhances")))
    return edges


def _find_capability_invocations(src: Path, wiki: Path) -> list[tuple[Path, int, str]]:
    """[(file, line_no, name)] for every find_capability.py <name> invocation."""
    hits: list[tuple[Path, int, str]] = []
    patterns = list(src.glob("*/commands/*.md")) + list(src.glob("*/skills/**/*.md"))
    if wiki.is_dir():
        patterns += list(wiki.rglob("*.md"))
    for path in sorted(set(patterns)):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        is_design_doc = "designs" in path.parts
        in_amendment_log = False
        for i, line in enumerate(text.splitlines(), 1):
            if is_design_doc and line.strip().startswith("## Amendment log"):
                in_amendment_log = True
            if in_amendment_log:
                continue
            for m in _FIND_CAPABILITY_RE.finditer(line):
                hits.append((path, i, m.group(1)))
    return hits


def check(src: Path = SRC, root: Path = ROOT) -> list[str]:
    """Return a list of `file:line: dangling reference to '<name>'` strings."""
    findings: list[str] = []
    groups = _load_groups(src)
    group_slugs = set(groups.keys())
    all_caps = _all_capabilities(groups)

    for slug, data in groups.items():
        gy = src / slug / "group.yaml"
        for field, target, line_no in _group_slug_edges(gy, data):
            if target not in group_slugs:
                rel = gy.relative_to(root)
                findings.append(f"{rel}:{line_no}: dangling reference to '{target}' ({field})")

    wiki = root / "wiki"
    for path, line_no, name in _find_capability_invocations(src, wiki):
        if name not in all_caps and name not in group_slugs:
            rel = path.relative_to(root)
            findings.append(f"{rel}:{line_no}: dangling reference to '{name}'")

    return findings


def main() -> int:
    findings = check()
    if findings:
        for f in findings:
            print(f, file=sys.stderr)
        print(f"\ncheck-no-dangling-name: {len(findings)} dangling reference(s)", file=sys.stderr)
        return 1
    print("check-no-dangling-name: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
