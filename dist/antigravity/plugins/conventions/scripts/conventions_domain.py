#!/usr/bin/env python3
"""Domain lookup for src/conventions/ (crickets wave-c-design-and-conventions,
task 4).

A domain (e.g. "agentic-engineering", "ci-battery") resolves to whichever of
its three shapes exist on disk -- rules/<domain>.md, skills/<domain>/SKILL.md,
reference/<domain>.md (crickets-conventions.md's "extensible shell": adding a
domain is dropping a file under one of these, no new plugin, no new wiring).
An unknown domain resolves to all-empty lists -- graceful, matching the
by-name resolver convention this plugin's consumers already use elsewhere
(find_capability / capability_resolver), never an error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def resolve(domain: str, conventions_root: Path) -> dict:
    """{"rules": [...], "skills": [...], "reference": [...]} of the paths
    that exist for `domain` under `conventions_root`. Each list holds at
    most one path today (one file per shape per domain); never raises."""
    result = {"rules": [], "skills": [], "reference": []}
    rule_path = conventions_root / "rules" / f"{domain}.md"
    if rule_path.is_file():
        result["rules"].append(rule_path)
    skill_path = conventions_root / "skills" / domain / "SKILL.md"
    if skill_path.is_file():
        result["skills"].append(skill_path)
    reference_path = conventions_root / "reference" / f"{domain}.md"
    if reference_path.is_file():
        result["reference"].append(reference_path)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Resolve a conventions domain to its on-disk shapes")
    parser.add_argument("domain")
    parser.add_argument("--conventions-root", default=str(Path(__file__).resolve().parent.parent))
    args = parser.parse_args(argv)
    found = resolve(args.domain, Path(args.conventions_root))
    print(json.dumps({k: [str(p) for p in v] for k, v in found.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
