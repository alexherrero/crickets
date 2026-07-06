#!/usr/bin/env python3
"""cve-security-patch -- patch a vulnerable dependency against a security
advisory before it fails CI (crickets wave-c-maintenance, task 2).

Advisory-as-input only (crickets-maintenance.md): the advisory is handed to
this primitive as a parameter, never polled from a live GHSA/NVD feed -- a
live polling integration is a later, separate, service-shaped build.

Reuses dependabot-fixer's repair guarantees (its SKILL.md is a prompt, not
importable code, so the discipline is re-implemented here rather than
shared): never merge, never touch the default branch directly, never pin
older, never claim success unless verification passed. Unlike
dependabot-fixer's unknown-CI-failure case, the advisory already names the
exact fixed version -- no diagnosis loop is needed, one deterministic patch
attempt either succeeds or is rolled back.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_VERSION_PREFIX = "^~=<>"


def _bare(version: str) -> str:
    return version.lstrip(_VERSION_PREFIX).strip()


def _git(args: list, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True,
    )


class AdvisoryNotApplicable(Exception):
    """The manifest's pinned version isn't in the advisory's vulnerable range."""


def patch(
    repo_root: Path,
    manifest_relpath: str,
    advisory: dict,
    *,
    branch_prefix: str = "cve-patch",
    verify_cmd: "list | None" = None,
) -> dict:
    """Patch `advisory["package"]`'s pinned version in
    `<repo_root>/<manifest_relpath>` to `advisory["fixed_version"]`, on a NEW
    branch off the current HEAD -- never writing to the branch that was
    checked out when this was called. Raises `AdvisoryNotApplicable` if the
    pinned version doesn't match `advisory["vulnerable_version"]` (nothing to
    patch). If `verify_cmd` is given and it fails, the patch branch is
    discarded and the original branch restored -- never a half-verified
    "success".

    Returns {"branch", "package", "old_version", "new_version"}.
    """
    package = advisory["package"]
    vulnerable = advisory["vulnerable_version"]
    fixed = advisory["fixed_version"]

    manifest_path = repo_root / manifest_relpath
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    deps = manifest.get("dependencies") or {}
    pinned = deps.get(package)
    if pinned is None or _bare(pinned) != _bare(vulnerable):
        raise AdvisoryNotApplicable(
            f"{package} is not pinned at the advisory's vulnerable version "
            f"({vulnerable!r}); nothing to patch"
        )

    original_branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root).stdout.strip()
    branch = f"{branch_prefix}/{package}-{fixed}"
    _git(["checkout", "-b", branch], repo_root)

    deps[package] = fixed
    manifest["dependencies"] = deps
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _git(["add", manifest_relpath], repo_root)
    _git(["commit", "-m", f"fix: patch {package} {pinned} -> {fixed} (CVE advisory)"], repo_root)

    if verify_cmd is not None:
        result = subprocess.run(verify_cmd, cwd=str(repo_root), capture_output=True, text=True)
        if result.returncode != 0:
            _git(["checkout", original_branch], repo_root)
            _git(["branch", "-D", branch], repo_root)
            raise RuntimeError(
                f"verify_cmd failed after patching {package} -> {fixed}; "
                f"rolled back, never claiming success on a failed verification:\n{result.stdout}\n{result.stderr}"
            )

    _git(["checkout", original_branch], repo_root)
    return {"branch": branch, "package": package, "old_version": pinned, "new_version": fixed}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="cve-security-patch -- advisory-driven pre-CI patch")
    parser.add_argument("repo_root")
    parser.add_argument("manifest_relpath")
    parser.add_argument("--advisory", required=True, help="path to a JSON advisory {package, vulnerable_version, fixed_version}")
    args = parser.parse_args(argv)
    advisory = json.loads(Path(args.advisory).read_text(encoding="utf-8"))
    result = patch(Path(args.repo_root), args.manifest_relpath, advisory)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
