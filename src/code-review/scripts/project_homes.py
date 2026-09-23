#!/usr/bin/env python3
"""project_homes.py — ask agentm where a project keeps its tasks, designs and desk.

    project_homes.py home {tasks|designs|desk} [--cwd DIR | --project SLUG]
    project_homes.py plans [--cwd DIR | --project SLUG]

A project keeps its state in its own skeleton: tasks under `tasks/`, designs
under `designs/`, machine files under `desk/` (agentm-vault § Projects and
tasks). Where that skeleton is — which vault, which project — is agentm's answer,
never a plugin's. So no plugin composes a project path: it asks here, and this
module asks agentm, as a subprocess, through two verbs agentm ships:

    process_seam.py project-path {tasks|designs|desk} [--cwd ROOT | --project SLUG]
    harness_memory.py list-plans [--project-root ROOT | --project SLUG]

`home` prints the directory agentm names. It creates nothing: a plugin may make a
file or subdirectory inside a home, never the home itself. `plans` prints one
plan path per line — the project's tasks that are not done or dropped.

`--cwd` is a repo bound to a vault project (its `.harness/project.json`);
`--project` names a project with no repo checkout.

No home, no write: when agentm is absent, or names no home for the project (no
vault, a device-local opt-out), the caller writes nothing and says why. Nothing
here falls back to a directory of its own.

Exit codes:
    0 — answered (`plans` may print nothing)
    2 — a usage error, or agentm refused the request (an unsafe slug)
    3 — no answer: agentm is absent, timed out, or names no home; the reason is on stderr

In-process callers load this file by path from their own plugin root — a
cross-plugin import cannot work at runtime — and call `home()` or `plans()`.

Every plugin that asks ships a byte-identical copy; scripts/test_project_homes.py
pins the copies, and its discovery order is development-lifecycle's
`agentm_bridge._default_candidate_dirs`, pinned by the same test. Standard
library only.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

KINDS = ("tasks", "designs", "desk")
TIMEOUT = 30

NO_ANSWER = 3

_SEAM_NAME = "process_seam.py"
_HARNESS_MEMORY_NAME = "harness_memory.py"


def _default_candidate_dirs() -> "list[Path]":
    """$AGENTM_SCRIPTS_DIR (explicit override), this script's own directory
    (co-located install), then the conventional ~/Antigravity/agentm/scripts
    clone — first hit (per target filename) wins."""
    here = Path(__file__).resolve().parent
    candidates: list[Path] = []
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    if env_dir:
        candidates.append(Path(os.path.expanduser(env_dir)))
    candidates.append(here)
    candidates.append(Path.home() / "Antigravity" / "agentm" / "scripts")
    return candidates


def _find(name: str) -> "Path | None":
    for d in _default_candidate_dirs():
        c = d / name
        if c.is_file():
            return c.resolve()
    return None


def _run(script: Path, args: "list[str]", *, timeout: float) -> "tuple[int, str, str]":
    """Run an agentm script, UTF-8 both ways. (rc, stdout, stderr); a launch
    failure or a timeout is `NO_ANSWER` with the reason in stderr."""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        r = subprocess.run([sys.executable, str(script), *args], capture_output=True,
                           timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return (NO_ANSWER, "", f"agentm's {script.name} did not answer within {timeout:g}s")
    except OSError as exc:
        return (NO_ANSWER, "", f"agentm's {script.name} could not start: {exc}")
    return (r.returncode, r.stdout.decode("utf-8", "replace"),
            r.stderr.decode("utf-8", "replace"))


def _where(cwd: "str | os.PathLike | None", project: "str | None", flag: str) -> "list[str]":
    if project is not None:
        return ["--project", project]
    return [flag, str(cwd if cwd is not None else os.getcwd())]


def ask_home(kind: str, *, cwd=None, project: "str | None" = None,
             timeout: float = TIMEOUT) -> "tuple[int, Path | None, str]":
    """(rc, path, reason) for a project's `kind` home. rc is 0 with a path, 2 on
    a refusal, `NO_ANSWER` otherwise."""
    if kind not in KINDS:
        return (2, None, f"unknown home {kind!r}; one of {', '.join(KINDS)}")
    seam = _find(_SEAM_NAME)
    if seam is None:
        return (NO_ANSWER, None, "agentm is not installed (no process_seam.py found)")
    rc, out, err = _run(seam, ["project-path", kind, *_where(cwd, project, "--cwd")],
                        timeout=timeout)
    line = out.strip()
    if rc == 0 and line:
        return (0, Path(line), "")
    if rc == 2:
        return (2, None, err.strip() or "agentm refused the request")
    if rc == 0 or rc == 1:
        return (NO_ANSWER, None, err.strip() or "agentm names no home for this project")
    return (NO_ANSWER, None,
            err.strip() or f"agentm's process_seam.py exited {rc} (an agentm without project-path?)")


def ask_plans(*, cwd=None, project: "str | None" = None,
              timeout: float = TIMEOUT) -> "tuple[int, list[Path], str]":
    """(rc, plans, reason): the project's plans agentm lists. rc is 0 (the list
    may be empty), 2 on a refusal, `NO_ANSWER` otherwise."""
    hm = _find(_HARNESS_MEMORY_NAME)
    if hm is None:
        return (NO_ANSWER, [], "agentm is not installed (no harness_memory.py found)")
    rc, out, err = _run(hm, ["list-plans", *_where(cwd, project, "--project-root")],
                        timeout=timeout)
    if rc == 2:
        return (2, [], err.strip() or "agentm refused the request")
    if rc != 0:
        return (NO_ANSWER, [], err.strip() or f"agentm's harness_memory.py exited {rc}")
    plans = [Path(line.strip()) for line in out.splitlines()
             if line.strip() and not line.startswith("active-binding=")]
    return (0, plans, "")


def home(kind: str, *, cwd=None, project: "str | None" = None,
         timeout: float = TIMEOUT) -> "Path | None":
    """The project's `kind` home as agentm names it, or None."""
    return ask_home(kind, cwd=cwd, project=project, timeout=timeout)[1]


def plans(cwd=None, *, project: "str | None" = None,
          timeout: float = TIMEOUT) -> "list[Path] | None":
    """The project's plans as agentm lists them, or None when agentm gave no answer."""
    rc, found, _ = ask_plans(cwd=cwd, project=project, timeout=timeout)
    return found if rc == 0 else None


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="project_homes.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="verb", required=True)
    h = sub.add_parser("home", help="print a project's tasks, designs or desk directory")
    h.add_argument("kind", choices=KINDS)
    for sp in (h, sub.add_parser("plans", help="print the project's plans, one per line")):
        where = sp.add_mutually_exclusive_group()
        where.add_argument("--cwd", default=None, help="a repo bound to a vault project (default: cwd)")
        where.add_argument("--project", default=None, help="a project named by slug, for one with no checkout")
    return p


def main(argv: "list[str] | None" = None) -> int:
    ns = _build_parser().parse_args(argv)
    if ns.verb == "home":
        rc, path, reason = ask_home(ns.kind, cwd=ns.cwd, project=ns.project)
        if path is not None:
            print(path)
    else:
        rc, found, reason = ask_plans(cwd=ns.cwd, project=ns.project)
        for p in found:
            print(p)
    if reason:
        print(f"[project_homes] {reason}", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
