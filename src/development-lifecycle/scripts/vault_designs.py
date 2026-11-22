#!/usr/bin/env python3
"""vault_designs.py — find the living design notes a project keeps in its vault.

    vault_designs.py list [--dir DIR | --cwd DIR] [--limit N] [--timeout SECS]
    vault_designs.py find TARGET [--dir DIR | --cwd DIR] [--timeout SECS]

A living design is one note in the project's `designs/` folder (agentm names where):
objective, current design, open questions, amendment log, with no status gate. The
repo's own `wiki/designs/` pages are read by agentm's governs resolver and keep
working as they did; this finds the vault notes beside them, so `/plan` and the
session-start hook see both.

`list` prints the path of each note that is live (frontmatter `status:` of `active` or
`launched`), newest `updated:` first, at most `--limit` (default 4).

`find` prints the one note that governs TARGET, a repo-relative path or an area name.
A note scores:
    10  a `governs:` entry equal to the target, or a folder the target sits under
     5  the area name (the target when it has no `/`) equals the note's `slug:` or one
        of its `aliases:`
     1  each `tags:` entry equal to the area name or to a folder in the target path
        (the generic tag `design` never counts)
A note needs 2 or more to count, so one shared tag is not a match. Highest score wins;
a tie goes to the newer `updated:`, then the slug, so the same notes always give the
same answer. Reads only frontmatter. Never writes.

Where the notes are: `--dir DIR` names the folder; otherwise this asks agentm through
this plugin's `project_homes.py` (`--cwd` is the repo, default the current directory).

Exit codes: 0 answered; 1 `find` matched nothing (greenfield, or no live note governs
it); 2 usage error; 3 no designs folder: agentm is absent, there is no vault, or the
folder does not exist. Nothing is created either way.

No agentm import, no network. Standard library only.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

LIVE_STATUSES = ("active", "launched")
MIN_SCORE = 2
DEFAULT_LIMIT = 4
_GENERIC_TAGS = {"design"}
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)


class Design(NamedTuple):
    path: Path
    slug: str
    status: str
    updated: str
    aliases: List[str]
    tags: List[str]
    governs: List[str]


def _items(value: str) -> List[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    out = []
    for part in value.split(","):
        part = part.strip().strip("\"'").strip()
        if part.startswith("[[") and part.endswith("]]"):
            part = part[2:-2]
        if part:
            out.append(part)
    return out


def parse_frontmatter(text: str) -> Dict[str, object]:
    """Scalars as strings; `[a, b]` flow lists and `- item` block lists as lists. Never raises."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm = {}  # type: Dict[str, object]
    key = None  # type: Optional[str]
    for raw in m.group(1).splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith((" ", "\t", "-")) and key is not None and raw.lstrip().startswith("- "):
            current = fm.get(key)
            if not isinstance(current, list):
                current = []
            current.append(raw.lstrip()[2:].strip().strip("\"'"))
            fm[key] = current
            continue
        k, sep, v = raw.partition(":")
        if not sep or raw.startswith((" ", "\t")):
            continue
        key = k.strip()
        v = v.strip()
        fm[key] = _items(v) if v.startswith("[") else v.strip("\"'")
    return fm


def _as_list(value: object) -> List[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [value.strip()] if isinstance(value, str) and value.strip() else []


def read_design(path: Path) -> Optional[Design]:
    try:
        fm = parse_frontmatter(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None
    return Design(path=path, slug=str(fm.get("slug") or path.stem), status=str(fm.get("status") or "").lower(),
                  updated=str(fm.get("updated") or ""), aliases=_as_list(fm.get("aliases")),
                  tags=_as_list(fm.get("tags")), governs=_as_list(fm.get("governs")))


def scan(directory: Path) -> List[Design]:
    """Every readable note under `directory` (one level), live or not, in path order."""
    notes = []
    for p in sorted(directory.glob("*.md")):
        d = read_design(p)
        if d is not None:
            notes.append(d)
    return notes


def live(designs: List[Design]) -> List[Design]:
    return [d for d in designs if d.status in LIVE_STATUSES]


def _newest_first(designs: List[Design]) -> List[Design]:
    return sorted(designs, key=lambda d: (0 if d.updated else 1, _neg(d.updated), d.slug))


def _neg(s: str) -> tuple:
    # sort descending on a string without reversing the whole key
    return tuple(-ord(c) for c in s)


def score(design: Design, target: str) -> int:
    target = target.strip().strip("/")
    if not target:
        return 0
    parts = [p.lower() for p in target.split("/") if p]
    area = target.lower() if "/" not in target else ""
    total = 0
    for g in design.governs:
        g = g.strip().strip("/")
        if g and (target == g or target.startswith(g + "/")):
            total += 10
            break
    names = {design.slug.lower()} | {a.lower() for a in design.aliases}
    if area and area in names:
        total += 5
    for tag in {t.lower() for t in design.tags} - _GENERIC_TAGS:
        if tag == area or tag in parts:
            total += 1
    return total


def find(designs: List[Design], target: str) -> Optional[Design]:
    scored = [(score(d, target), d) for d in live(designs)]
    scored = [(s, d) for s, d in scored if s >= MIN_SCORE]
    if not scored:
        return None
    best = max(s for s, _ in scored)
    return _newest_first([d for s, d in scored if s == best])[0]


def _project_homes():
    path = Path(__file__).resolve().parent / "project_homes.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("vault_designs_project_homes", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def designs_dir(directory: Optional[str], cwd: Optional[str], timeout: Optional[float] = None) -> Optional[Path]:
    """The folder to read, or None when there is none to read. `timeout` bounds the ask."""
    if directory:
        p = Path(directory)
        return p if p.is_dir() else None
    homes = _project_homes()
    if homes is None:
        return None
    extra = {} if timeout is None else {"timeout": timeout}
    home = homes.home("designs", cwd=cwd or ".", **extra)
    return Path(home) if home is not None and Path(home).is_dir() else None


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vault_designs.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("list", "find"):
        sp = sub.add_parser(name)
        where = sp.add_mutually_exclusive_group()
        where.add_argument("--dir", help="the designs folder to read")
        where.add_argument("--cwd", help="the repo to ask agentm about (default: the current directory)")
        sp.add_argument("--timeout", type=float, help="seconds to wait for agentm's answer (a session-start "
                                                     "hook passes a short one so it can never stall boot)")
        if name == "list":
            sp.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
        else:
            sp.add_argument("target", help="a repo-relative path or an area name")
    return p


def _utf8_stdio() -> None:
    """Write UTF-8 whatever the console's code page is: a Windows console's cp1252 cannot encode
    the arrows and dots this prints. A stream that cannot be reconfigured is left alone."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv: Optional[List[str]] = None) -> int:
    _utf8_stdio()
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    directory = designs_dir(args.dir, args.cwd, args.timeout)
    if directory is None:
        print("vault_designs: no designs folder to read (agentm absent, no vault, or the folder is missing)",
              file=sys.stderr)
        return 3
    designs = scan(directory)
    if args.cmd == "list":
        for d in _newest_first(live(designs))[:max(0, args.limit)]:
            print(d.path)
        return 0
    best = find(designs, args.target)
    if best is None:
        return 1
    print(best.path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
