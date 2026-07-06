#!/usr/bin/env python3
"""Phase-2 conventions-conformance gate (crickets wave-c-design-and-conventions,
task 6).

Checks DECLARATION, not content correctness: a plugin whose command/skill
prose consults a `conventions` domain must declare `conventions` in its own
`group.yaml` `requires:`/`enhances:` -- so "forgot to call conventions"
becomes a gate finding, not a silent gap (crickets-conventions.md). This
gate never grades whether the plugin followed the convention correctly;
that would be a different, unbuilt content linter.

Consultation signal: an HTML comment marker `<!-- consults-conventions-
domain: <domain> -->` in a command/skill file -- the same machine-readable-
but-invisible-when-rendered convention wiki pages already use for
`<!-- mode: X -->`. A plugin author marks a genuine consultation explicitly;
this gate never infers one from free prose (that would be unreliable and
turn a declaration check into a content-guessing one).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

_MARKER_RE = re.compile(r"<!--\s*consults-conventions-domain:\s*([A-Za-z0-9-]+)\s*-->")
_CONSULTABLE_GLOBS = ("commands/*.md", "skills/*/SKILL.md")


def _find_markers(plugin_dir: Path) -> set:
    """Every distinct domain name a plugin's command/skill files mark as
    consulted, via the consults-conventions-domain HTML-comment marker."""
    domains = set()
    for glob in _CONSULTABLE_GLOBS:
        for path in plugin_dir.glob(glob):
            text = path.read_text(encoding="utf-8", errors="replace")
            domains.update(_MARKER_RE.findall(text))
    return domains


def _declares_conventions(group_yaml: Path) -> bool:
    """True iff the plugin's group.yaml requires: or enhances: conventions."""
    if yaml is None or not group_yaml.is_file():
        return False
    try:
        data = yaml.safe_load(group_yaml.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return False
    if not isinstance(data, dict):
        return False
    requires = data.get("requires") or []
    if "conventions" in requires:
        return True
    for entry in data.get("enhances") or []:
        target = entry if isinstance(entry, str) else (entry.get("group") if isinstance(entry, dict) else None)
        if target == "conventions":
            return True
    return False


def scan(src: Path) -> list:
    """Findings: plugin dirs that consult a conventions domain (by marker)
    without declaring conventions as a requires:/enhances: dependency."""
    findings = []
    if not src.is_dir():
        return findings
    for plugin_dir in sorted(p for p in src.iterdir() if p.is_dir()):
        if plugin_dir.name == "conventions":
            continue  # conventions doesn't need to declare a dependency on itself
        domains = _find_markers(plugin_dir)
        if not domains:
            continue
        if not _declares_conventions(plugin_dir / "group.yaml"):
            findings.append(
                f"{plugin_dir.name}: consults conventions domain(s) "
                f"{sorted(domains)} but does not declare conventions in "
                f"requires:/enhances: (group.yaml)"
            )
    return findings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=SRC, help="src/ root to scan (default: this repo's src/)")
    args = parser.parse_args(argv)

    if yaml is None:
        print("check-conventions-conformance: PyYAML unavailable -- skipping (CI installs it)")
        return 0

    findings = scan(args.src)
    if findings:
        print("check-conventions-conformance: FAIL -- a plugin consults a conventions "
              "domain without declaring the dependency:")
        for f in findings:
            print(f"  - {f}")
        return 1
    print("check-conventions-conformance: OK -- every domain-consulting plugin declares conventions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
