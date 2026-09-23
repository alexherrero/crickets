#!/usr/bin/env python3
"""check-no-harness-paths — no crickets code composes, probes or names `_harness/`.

Since the projects migration (agentm-vault plan 10, 2026-09-16) a project keeps
its state in its own skeleton: tasks under `tasks/NNN-<slug>/`, machine files
under `desk/`, designs under `designs/`. `_harness/` is gone, and agentm-vault
part 15 retires everything that still reached for it. A plugin asks agentm where
a project's homes are (`project_homes.py`) and composes none of its own.

This gate keeps the word out of the plugins, because the behaviour cannot be
caught any other way: a reader that composes `_harness/` and tests `is_dir()`
fails soft on a vault where the directory is gone, and a writer that composes
it recreates the directory. agentm carries the same gate under the same name,
with the same pattern and marker.

What counts as a hit: the literal `_harness` not glued to a longer identifier
(`resolve_harness_root`, `find_harness_memory` and `.harness/` are not hits), on
any line, comments included.

Scanned: tracked files under `src/`, `scripts/`, `templates/`, `.github/` and
`bootstrap.sh`, tests included — a fixture that builds a `_harness/` directory is
exactly what this gate exists to stop. `wiki/`, `CHANGELOG.md` and `dist/` (which
`generate.py` builds from `src/`) are not scanned.

What is allowed:

  - a line carrying the marker `harness-deprecation:` with the reason where the
    literal sits: history that must keep the word, a test's negative assertion;
  - a whole file whose opening lines carry `harness-deprecation: file`.

There is no exemption list: tasks 100 and 101 cleared every plugin, and the
gate enforces everywhere it scans.

  --inventory   print every hit, allowed ones marked, with counts by plugin. Exit 0.
  (default)     print the unallowed hits and exit 1 on any; 0 when clean.

Exit: 0 clean · 1 violations · 2 setup error.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

MARKER = "harness-deprecation:"
FILE_MARKER = "harness-deprecation: file"
_FILE_MARKER_LINES = 40

# `_harness` as a name of its own — agentm's gate uses the same pattern.
_LITERAL = re.compile(r"(?<![A-Za-z0-9])_harness(?![A-Za-z0-9_])")
_SCOPE = ("src/", "scripts/", "templates/", ".github/")
_SCOPE_FILES = frozenset({"bootstrap.sh"})
_EXTENSIONS = frozenset({".py", ".sh", ".ps1", ".md", ".txt", ".yml", ".yaml", ".json", ".toml"})
# The gate names the pattern it looks for, and so does its test.
_SKIP_NAMES = frozenset({Path(__file__).name, "test_check_no_harness_paths.py"})

def _in_scope(rel: str) -> bool:
    return rel in _SCOPE_FILES or rel.startswith(_SCOPE)


def _tracked(root: Path) -> list[str] | None:
    """Repo-relative paths git tracks under `root`, or None off a work tree."""
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                           capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return sorted(p for p in r.stdout.decode("utf-8", "replace").split("\0") if p)


def _walked(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*")
                  if p.is_file() and ".git" not in p.relative_to(root).parts)


def _candidates(root: Path) -> list[str]:
    rels = _tracked(root)
    if rels is None:
        rels = _walked(root)
    return [rel for rel in rels
            if _in_scope(rel)
            and (Path(rel).suffix in _EXTENSIONS or rel in _SCOPE_FILES)
            and rel.rsplit("/", 1)[-1] not in _SKIP_NAMES]


def plugin_of(rel: str) -> str:
    """The plugin a path belongs to, for the inventory's grouping."""
    parts = rel.split("/")
    if parts[0] == "src" and len(parts) > 1:
        return parts[1]
    return "(repo)"


def scan_file(path: Path, rel: str) -> list[dict]:
    """Every hit in one file: `{rel, line, text, allowed}`."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = text.splitlines()
    place = None
    if any(FILE_MARKER in line for line in lines[:_FILE_MARKER_LINES]):
        place = "marker (file)"
    out = []
    for lineno, line in enumerate(lines, 1):
        if not _LITERAL.search(line):
            continue
        allowed = place if place else ("marker" if MARKER in line else None)
        out.append({"rel": rel, "line": lineno, "text": line.strip()[:120], "allowed": allowed})
    return out


def scan(root: Path) -> list[dict]:
    hits: list[dict] = []
    for rel in _candidates(root):
        p = root / rel
        if p.is_file():
            hits.extend(scan_file(p, rel))
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=None, help="repo root to scan (default: the script's own repo)")
    ap.add_argument("--inventory", action="store_true",
                    help="print every hit, allowed ones marked, with counts by plugin; exit 0")
    args = ap.parse_args(argv)
    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent
    if not root.is_dir():
        print(f"check-no-harness-paths: not a directory: {root}", file=sys.stderr)
        return 2

    hits = scan(root)
    open_hits = [h for h in hits if not h["allowed"]]

    if args.inventory:
        by_plugin: dict[str, list[dict]] = {}
        for h in hits:
            by_plugin.setdefault(plugin_of(h["rel"]), []).append(h)
        for plugin in sorted(by_plugin):
            group = by_plugin[plugin]
            print(f"{plugin}: {len(group)} hit(s) in {len({h['rel'] for h in group})} file(s)")
            for h in group:
                tag = f"  ({h['allowed']})" if h["allowed"] else ""
                print(f"  {h['rel']}:{h['line']}  {h['text']}{tag}")
        tests = [h for h in hits if h["rel"].rsplit("/", 1)[-1].startswith("test_")]
        code = [h for h in hits if h not in tests]
        print(f"check-no-harness-paths: inventory — {len(code)} hit(s) in "
              f"{len({h['rel'] for h in code})} non-test file(s), {len(tests)} in "
              f"{len({h['rel'] for h in tests})} test file(s); {len(open_hits)} unallowed")
        return 0

    rc = 0
    if open_hits:
        files = len({h["rel"] for h in open_hits})
        print(f"check-no-harness-paths: {len(open_hits)} literal(s) in {files} file(s) name "
              "`_harness` — a project's homes are its own `tasks/`, `designs/` and `desk/`, "
              "and a plugin asks agentm for them (project_homes.py).", file=sys.stderr)
        print(f"  Ask agentm for the path, or explain the literal where it sits with "
              f"`{MARKER} <why>`.", file=sys.stderr)
        for h in open_hits:
            print(f"  {h['rel']}:{h['line']}  {h['text']}", file=sys.stderr)
        rc = 1
    if rc == 0:
        allowed = len(hits)
        print(f"check-no-harness-paths: clean ({allowed} marked literal(s))")
    return rc


if __name__ == "__main__":
    sys.exit(main())
