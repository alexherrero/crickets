#!/usr/bin/env python3
"""Crickets artifact-prepare step for the single-writer integrator (ADR 0030).

Invoked by `integrate_worker.py` after it merges a `worker/<slug>` branch, BEFORE
the gate, via the thin `scripts/integrate-prepare.sh` wrapper the generic plugin
looks for. The worker committed `src/` + `dist/` regenerated at the *current*
(unbumped) version and deferred the version bump (the `worker/` branch makes
`check-version-bump.py` advisory). This step — the single serialized writer of
the shared version registry — does what the worker deferred:

    1. diff the merge's contribution (`<pre-merge-sha>`..HEAD under `src/`) to find
       every plugin whose source changed;
    2. bump each one's `group.yaml` `version:` (patch by default);
    3. regenerate `dist/` + the `marketplace.json` registries from current `main`;
    4. stage the bumped `group.yaml`(s) + the regenerated outputs by explicit path
       (never `git add -A` — the shared-tree collision rule) and commit.

Because no worker branch ever writes a version line, the cross-plugin
`marketplace.json` collision is structurally gone; the registry moves only here,
on the integration branch, one landing at a time. The version-bump gate (run next
by the integrator) then passes on the integrated tree.

    integrate_prepare.py <pre-merge-sha> [--level patch|minor|major] [--project-root .]

Bump level: patch by default; `$INTEGRATE_BUMP_LEVEL` or `--level` overrides (a
feature landing passes `--level minor`). Exit 0 on a clean prepare (or nothing to
bump); non-zero on any failure, which makes `integrate_worker.py` roll the merge
back — a half-applied bump must never land.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

SRC_DIRNAME = "src"
_LEVELS = ("patch", "minor", "major")
# Generated outputs staged by explicit path after a regenerate (no `git add -A`).
_GENERATED_PATHS = ("dist", ".claude-plugin", ".agents")
_VERSION_RE = re.compile(r"^(version:\s*)(.+?)(\s*)$", re.MULTILINE)


# ── pure logic (unit-tested without git) ─────────────────────────────────────

def bump_version(version: str, level: str) -> str:
    """Return `version` incremented by `level` (patch | minor | major).

    Accepts the only shape crickets uses — three dotted non-negative integers,
    tolerating a leading `v` and dropping any `-pre`/`+build` suffix (the bumped
    result is always a clean `x.y.z`). Raises ValueError on anything else, so a
    garbage version surfaces loudly here rather than silently shipping.
    """
    if level not in _LEVELS:
        raise ValueError(f"unknown bump level {level!r} (expected one of {_LEVELS})")
    core = version.strip()
    if core[:1] == "v":
        core = core[1:]
    core = re.split(r"[-+]", core, maxsplit=1)[0]
    parts = core.split(".")
    if len(parts) != 3:
        raise ValueError(f"not a 3-part semver: {version!r}")
    try:
        major, minor, patch = (int(p) for p in parts)
    except ValueError:
        raise ValueError(f"non-integer version component in {version!r}")
    if any(n < 0 for n in (major, minor, patch)):
        raise ValueError(f"negative version component in {version!r}")
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def changed_plugin_slugs(changed_paths) -> set[str]:
    """Map changed repo-relative paths to the plugin slugs they touch.

    A path counts only under `src/<slug>/...`; identical to the gate's mapping so
    the bumped set matches what `check-version-bump.py` would have demanded.
    """
    slugs: set[str] = set()
    for raw in changed_paths:
        parts = Path(raw.strip()).parts
        if len(parts) >= 3 and parts[0] == SRC_DIRNAME:
            slugs.add(parts[1])
    return slugs


def rewrite_version(group_yaml_text: str, new_version: str) -> str:
    """Return `group_yaml_text` with its top-level `version:` set to `new_version`.

    Substitutes the existing `version:` line in place (preserving leading key text
    and trailing whitespace), so surrounding formatting is untouched. Raises
    ValueError when there is no `version:` line to rewrite.
    """
    new_text, n = _VERSION_RE.subn(
        lambda m: f"{m.group(1)}{new_version}{m.group(3)}", group_yaml_text, count=1)
    if n == 0:
        raise ValueError("group.yaml has no top-level `version:` line to bump")
    return new_text


def read_version(group_yaml_text: str) -> str | None:
    m = _VERSION_RE.search(group_yaml_text)
    return m.group(2).strip().strip("'\"") if m else None


# ── git + regenerate plumbing ────────────────────────────────────────────────

def _git(args, root) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(root),
                          capture_output=True, text=True, timeout=60)


def _diff_slugs(root, pre_sha: str) -> set[str]:
    """Plugins whose `src/` the merge changed (pre-merge SHA .. HEAD)."""
    out = _git(["diff", "--name-only", pre_sha, "HEAD", "--", SRC_DIRNAME], root)
    if out.returncode != 0:
        raise RuntimeError(f"git diff failed: {out.stderr.strip()}")
    return changed_plugin_slugs(
        ln for ln in out.stdout.splitlines() if ln.strip())


def _default_regenerate(root) -> tuple[int, str]:
    """Production regenerate: `python3 scripts/generate.py build`."""
    r = subprocess.run([sys.executable, "scripts/generate.py", "build"],
                       cwd=str(root), capture_output=True, text=True, timeout=600)
    return (r.returncode, r.stdout + r.stderr)


# ── core ─────────────────────────────────────────────────────────────────────

def run_prepare(root, pre_sha: str, *, level: str = "patch",
                regenerate=_default_regenerate) -> tuple[int, str]:
    """Bump the merge's changed plugins, regenerate, stage + commit. (rc, output).

    Pure-ish core with an injectable `regenerate` (tests pass a stub that mimics
    `generate.py` without the full src tree). rc 0 on success or when the merge
    changed no plugin source (nothing to bump — a docs/scripts-only worker);
    non-zero (with the reason) on any failure, so `integrate_worker` rolls back.
    """
    root = Path(root)
    try:
        slugs = sorted(_diff_slugs(root, pre_sha))
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        return (1, f"[integrate-prepare] could not diff the merge: {exc}\n")
    if not slugs:
        return (0, "[integrate-prepare] the merge changed no plugin src/ — "
                   "nothing to bump.\n")

    # 1+2. Bump each changed plugin's group.yaml version.
    bumped = []
    for slug in slugs:
        gy = root / SRC_DIRNAME / slug / "group.yaml"
        if not gy.is_file():
            return (1, f"[integrate-prepare] {slug} changed but has no group.yaml "
                       f"({gy}) — cannot bump.\n")
        text = gy.read_text(encoding="utf-8")
        old = read_version(text)
        try:
            new = bump_version(old, level) if old is not None else None
            if new is None:
                raise ValueError("no version: line")
            gy.write_text(rewrite_version(text, new), encoding="utf-8")
        except ValueError as exc:
            return (1, f"[integrate-prepare] cannot bump {slug}: {exc}\n")
        bumped.append(f"{slug} {old}→{new}")

    # 3. Regenerate dist/ + the marketplace registries from the bumped src.
    rrc, rout = regenerate(root)
    if rrc != 0:
        return (1, f"[integrate-prepare] regenerate failed (rc={rrc}):\n{rout}\n")

    # 4. Stage by explicit path (never `git add -A`) + commit. Generated paths are
    # filtered to those that exist (a repo may emit only a subset; `git add` errors
    # on a pathspec that matches nothing) — the bumped group.yaml(s) always exist.
    paths = [f"{SRC_DIRNAME}/{s}/group.yaml" for s in slugs]
    paths += [p for p in _GENERATED_PATHS if (root / p).exists()]
    add = _git(["add", "--", *paths], root)
    if add.returncode != 0:
        return (1, f"[integrate-prepare] git add failed: {add.stderr.strip()}\n")
    msg = (f"chore(release): bump {', '.join(slugs)} via integrate-worker "
           f"(single-writer, ADR 0030)")
    commit = _git(["commit", "-m", msg], root)
    if commit.returncode != 0:
        # An empty commit (nothing staged changed) is not an error: the worker may
        # have already produced byte-identical dist at the current version and the
        # bump is the only delta — but if even that is a no-op, surface it.
        if "nothing to commit" in (commit.stdout + commit.stderr).lower():
            return (0, "[integrate-prepare] nothing to commit after bump+regen "
                       "(already in sync).\n")
        return (1, f"[integrate-prepare] git commit failed: "
                   f"{(commit.stdout + commit.stderr).strip()}\n")
    return (0, f"[integrate-prepare] bumped {', '.join(bumped)}; regenerated + "
               f"committed.\n")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="integrate_prepare.py",
        description="Single-writer artifact-prepare for the integrator (ADR 0030).",
    )
    p.add_argument("pre_sha", help="the pre-merge SHA (HEAD before the integrator merged)")
    p.add_argument("--level", choices=_LEVELS,
                   default=os.environ.get("INTEGRATE_BUMP_LEVEL", "patch"),
                   help="bump level (default: patch, or $INTEGRATE_BUMP_LEVEL)")
    p.add_argument("--project-root", default=None)
    ns = p.parse_args(argv[1:])
    root = ns.project_root if ns.project_root is not None else os.getcwd()
    rc, out = run_prepare(root, ns.pre_sha, level=ns.level)
    sys.stdout.write(out)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
