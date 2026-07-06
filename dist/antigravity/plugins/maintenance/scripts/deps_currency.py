#!/usr/bin/env python3
"""deps-currency -- surface drifted-but-not-yet-CI-failing dependencies
before they go red (crickets wave-c-maintenance, task 1).

Read-only: a passive report, never a PR (crickets-maintenance.md's own
distinction from dependabot-fixer, which repairs an already-red PR).
`latest_versions` is handed in (a registry-query result, in real use) rather
than fetched here -- this primitive's own entry point is a version map, the
same advisory-as-input shape cve-security-patch's CVE advisory follows.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_VERSION_PREFIX = "^~=<>"


def _bare(version: str) -> str:
    return version.lstrip(_VERSION_PREFIX).strip()


def scan(manifest_path: Path, latest_versions: dict) -> list:
    """Compare a package.json-shaped manifest's pinned deps against
    `latest_versions`. Returns a finding per drifted (pinned != latest)
    package that `latest_versions` knows about. Never writes to
    `manifest_path`."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    findings = []
    for name, pinned in (manifest.get("dependencies") or {}).items():
        latest = latest_versions.get(name)
        if latest is None:
            continue
        if _bare(pinned) != _bare(latest):
            findings.append({"package": name, "pinned": pinned, "latest": latest})
    return findings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="deps-currency -- surface drifted dependencies")
    parser.add_argument("manifest_path")
    parser.add_argument("--latest-versions", required=True, help="path to a JSON {package: version} map")
    args = parser.parse_args(argv)
    latest_versions = json.loads(Path(args.latest_versions).read_text(encoding="utf-8"))
    findings = scan(Path(args.manifest_path), latest_versions)
    print(json.dumps(findings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
