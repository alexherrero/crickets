#!/usr/bin/env python3
"""The phase commands' one helper for a plan's tracker (PLAN-tracker-commands).

agentm's `scripts/tracker.py` owns the tracker's one schema and is the only
writer of a tracker (agentm-vault § Projects and tasks). The development-lifecycle
commands call this script instead of composing tracker calls in the prompt. It
reads what it needs from the plan agentm resolved, composes the arguments, and
sends every tracker call through `agentm_bridge.run_tracker`. It never renders,
parses or edits tracker text; what it knows of a tracker comes from
`tracker.py show`'s JSON.

    plan_tracker.py name   --plan PATH
    plan_tracker.py status --plan PATH --tracker PATH
    plan_tracker.py open   --plan PATH --tracker PATH [--issue N] [--root DIR]
    plan_tracker.py step   --plan PATH --tracker PATH --state TEXT --next TEXT [--root DIR]
    plan_tracker.py close  --plan PATH --tracker PATH --outcome TEXT
                           [--state TEXT] [--next TEXT] [--root DIR]

`--plan` and `--tracker` are the first and third fields `resolve_plan.py`
prints. An empty `--tracker` means agentm named no tracker (an agentm from
before the tracker): the verbs that write say so and exit 3, and the plan
carries on without one, its progress log the record.

**Layout comes from the path agentm returned.** A task's plan is `plan.md` in
its own directory (`tasks/042-build-the-brief/plan.md`); in a repo with no
vault, agentm answers a repo-local `PLAN-<name>.md` or `PLAN.md`. Nothing here
composes a path.

**The tracker is a plan's only status.** A plan carries no `**Status:**` line
(crickets task 101): `status` reads the tracker, else prints `none`, and `step`
and `close` never touch the plan file. agentm's own readers take the tracker
first since agentm task 172.

Exit codes:
    0 — done, or nothing to do
    1 — refused: a final tracker, or a transition tracker.py refused
    2 — a usage or I/O error
    3 — carry on without a tracker; the reason is on stderr

Standard library only.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

REFUSED = 1
USAGE = 2
NO_TRACKER = 3

_HERE = Path(__file__).resolve().parent
_FINAL = ("done", "dropped")

_PLAN_TITLE = re.compile(r"^#[ \t]+Plan:[ \t]*([^\r\n]+?)[ \t]*\r?$", re.MULTILINE)
_ANY_TITLE = re.compile(r"^#[ \t]+([^\r\n]+?)[ \t]*\r?$", re.MULTILINE)
_BRIEF = re.compile(r"^\*\*Brief:\*\*[ \t]*([^\r\n]+?)[ \t]*\r?$", re.MULTILINE)
_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_STEP_HEADING = re.compile(r"^###[ \t]+(\d+)\.[ \t]*(.*?)[ \t]*$")
_HEADING_STATUS = re.compile(r"^(.*?)[ \t]*[—–-]+[ \t]*Status:[ \t]*\[([ xX])\][ \t]*$")
_BULLET_STATUS = re.compile(r"^[ \t]*-[ \t]+\*\*Status:\*\*[ \t]*\[([ xX])\]")


def _load_sibling(name: str):
    """A script from this directory, loaded by path (crickets-internal, never
    agentm's own modules), or None when it can't be loaded."""
    spec = importlib.util.spec_from_file_location(f"plan_tracker_{name}", _HERE / f"{name}.py")
    if not spec or not spec.loader:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return None
    return mod


_bridge = _load_sibling("agentm_bridge")


# ── reading the plan ────────────────────────────────────────────────────────────

def _read_plan(plan: Path) -> str:
    with open(plan, encoding="utf-8", newline="") as f:
        return f.read()


def plan_name(plan: "str | os.PathLike") -> str:
    """The plan's name as agentm placed it: a task's directory name, a flat
    named plan's slug, or "" for the singleton."""
    p = Path(plan)
    if p.name == "plan.md":
        return p.parent.name
    if p.name.startswith("PLAN-") and p.name.endswith(".md") and len(p.name) > len("PLAN-.md"):
        return p.name[len("PLAN-"):-len(".md")]
    return ""


def _title(text: str, plan: Path) -> str:
    m = _PLAN_TITLE.search(text) or _ANY_TITLE.search(text)
    if m:
        return m.group(1).strip()
    return plan_name(plan) or plan.stem


def _section(text: str, heading: str) -> str:
    """The body of `## <heading>`, up to the next `## ` heading, stripped."""
    body, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].strip().lower() == heading.lower()
            continue
        if inside:
            body.append(line)
    return "\n".join(body).strip()


def _objective(text: str, title: str) -> str:
    goal = _section(text, "Goal")
    if goal:
        return goal
    brief = _BRIEF.search(text)
    if brief:
        return brief.group(1).strip()
    return title


def first_open_step(text: str) -> "tuple[str, str] | None":
    """(number, title) of the first unchecked step, in either shape: a
    `### N. Title` heading with a `- **Status:** [ ]` bullet under it, or a
    `### N. Title — Status: [ ]` heading."""
    current = None
    for line in text.splitlines():
        heading = _STEP_HEADING.match(line)
        if heading:
            number, title = heading.group(1), heading.group(2)
            suffix = _HEADING_STATUS.match(title)
            if suffix:
                if suffix.group(2) == " ":
                    return (number, suffix.group(1).strip())
                current = None
            else:
                current = (number, title)
            continue
        if line.startswith("## "):
            current = None
            continue
        bullet = _BULLET_STATUS.match(line)
        if bullet and current is not None:
            if bullet.group(1) == " ":
                return current
            current = None
    return None


def _next_step(text: str) -> str:
    step = first_open_step(text)
    if step is None:
        return "Every step is checked: close the plan."
    return f"Step {step[0]}: {step[1]}"


def _frontmatter_value(text: str, key: str) -> "str | None":
    m = _FRONTMATTER.match(text)
    if not m:
        return None
    for line in m.group(1).splitlines():
        k, sep, v = line.partition(":")
        if sep and k.strip() == key:
            return v.strip().strip("'\"") or None
    return None


def _vault_project(root: "str | os.PathLike | None") -> "str | None":
    """`vault_project` from `<root>/.harness/project.json`, through the reader
    worktree_marker.py already has."""
    marker = _load_sibling("worktree_marker")
    reader = getattr(marker, "_read_vault_project", None)
    if reader is None:
        return None
    try:
        return reader(root if root is not None else os.getcwd())
    except Exception:
        return None


def _project(plan: Path, tracker: Path, root) -> str:
    """The tracker's `project`: `vault_project`, else the project directory the
    tracker sits in, which is the name agentm's tracker gate checks."""
    configured = _vault_project(root)
    if configured:
        return configured
    for place in (tracker, plan):
        if place.parent.parent.name == "tasks":
            return place.parent.parent.parent.name
    return plan.parent.parent.name


# ── the tracker, through the bridge ─────────────────────────────────────────────

def _run(args: "list[str]") -> "tuple[int, str, str]":
    if _bridge is None:
        return (NO_TRACKER, "", "agentm_bridge.py could not be loaded\n")
    return _bridge.run_tracker(args)


def _show(tracker: Path) -> "tuple[int, dict | None, str]":
    code, out, err = _run(["show", str(tracker)])
    if code != 0:
        return (code, None, err.strip() or f"tracker.py show exited {code}")
    try:
        shown = json.loads(out)
    except ValueError:
        return (REFUSED, None, f"tracker.py show printed no JSON for {tracker}")
    return (0, shown if isinstance(shown, dict) else None, "")


def _failed(code: int, err: str, what: str) -> "tuple[int, str]":
    if code == NO_TRACKER:
        return (NO_TRACKER, err.strip() or "tracker.py is not available")
    return (code if code in (REFUSED, USAGE) else REFUSED,
            err.strip() or f"tracker.py {what} exited {code}")


def plan_status(plan: Path, tracker: str) -> "tuple[str, str]":
    """(status, source): the tracker's status, else ("none", "none"). A plan's
    own text is never read for a status."""
    if tracker and Path(tracker).is_file():
        code, shown, err = _show(Path(tracker))
        if shown is not None and shown.get("status"):
            return (str(shown["status"]), "tracker")
        print(f"[plan_tracker] could not read the tracker at {tracker} ({err})",
              file=sys.stderr)
    return ("none", "none")


def open_tracker(plan: Path, tracker: str, *, issue: "int | None" = None,
                 root=None) -> "tuple[int, str]":
    """Open the plan's tracker at `queued`, unless one is already open."""
    if not tracker:
        return (NO_TRACKER, "agentm named no tracker for this plan; it runs without one")
    path = Path(tracker)
    if path.exists():
        code, shown, err = _show(path)
        if shown is None:
            return _failed(code, err, "show")
        if shown.get("status") in _FINAL:
            return (NO_TRACKER, f"the tracker at {path} is already {shown['status']}; "
                                "the plan runs without one")
        return (0, f"already open ({shown.get('status')}): {path}")
    text = _read_plan(plan)
    title = _title(text, plan)
    args = ["new", "--title", title, "--project", _project(plan, path, root),
            "--objective", _objective(text, title), "--next", _next_step(text)]
    name = plan_name(plan)
    if name:
        args += ["--task", name]
    design = _frontmatter_value(text, "parent_design_doc")
    if design:
        args += ["--design", design]
    if issue is not None:
        args += ["--issue", str(issue)]
    args += ["--out", str(path)]
    code, _out, err = _run(args)
    if code != 0:
        return _failed(code, err, "new")
    return (0, f"opened {path} at queued")


def step(plan: Path, tracker: str, *, state: str, next_steps: str,
         root=None) -> "tuple[int, str]":
    """Record a step: open a missing tracker, move `queued` or `parked` to
    `active`, rewrite an `active` one in place. A final tracker is refused."""
    if not tracker:
        return (NO_TRACKER, "agentm named no tracker for this plan; progress records the step")
    path = Path(tracker)
    if not path.exists():
        code, message = open_tracker(plan, tracker, root=root)
        if code != 0:
            return (code, message)
    code, shown, err = _show(path)
    if shown is None:
        return _failed(code, err, "show")
    current = shown.get("status")
    if current in _FINAL:
        return (REFUSED, f"the tracker at {path} is {current}, and a final tracker takes no more steps")
    code, out, err = _run(["transition", str(path), "--to", "active",
                           "--state", state, "--next", next_steps])
    if code == REFUSED and current == "active" and "cannot become `active`" in err:
        return (NO_TRACKER, "this agentm's tracker.py predates the same-status rewrite, so "
                            "State and Next were not rewritten; update agentm")
    if code != 0:
        return _failed(code, err, "transition")
    return (0, out.strip())


def close(plan: Path, tracker: str, *, outcome: str, state: "str | None" = None,
          next_steps: "str | None" = None, root=None) -> "tuple[int, str]":
    """Close the tracker at `done` with its Outcome. `queued` and `parked` pass
    through `active` first; a tracker already `done` is left as it is."""
    if not tracker:
        return (NO_TRACKER, "agentm named no tracker for this plan; progress records the close")
    path = Path(tracker)
    if not path.exists():
        code, message = open_tracker(plan, tracker, root=root)
        if code != 0:
            return (code, message)
    code, shown, err = _show(path)
    if shown is None:
        return _failed(code, err, "show")
    current = shown.get("status")
    if current == "done":
        return (0, f"already done: {path}")
    if current == "dropped":
        return (REFUSED, f"the tracker at {path} was dropped; it is not closed as done")
    if current in ("queued", "parked"):
        code, _out, err = _run(["transition", str(path), "--to", "active"])
        if code != 0:
            return _failed(code, err, "transition")
    args = ["transition", str(path), "--to", "done", "--outcome", outcome]
    if state is not None:
        args += ["--state", state]
    if next_steps is not None:
        args += ["--next", next_steps]
    code, out, err = _run(args)
    if code != 0:
        return _failed(code, err, "transition")
    return (0, out.strip())


# ── CLI ─────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="plan_tracker.py",
                                description="Open, step and close a plan's tracker.")
    sub = p.add_subparsers(dest="verb")

    def verb(name: str, help_text: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("--plan", required=True, help="the plan path resolve_plan.py printed")
        sp.add_argument("--tracker", default="",
                        help="the tracker path resolve_plan.py printed; empty means none")
        return sp

    verb("name", "print the plan's name as agentm placed it")
    verb("status", "print <status>\\t<source>")
    sp = verb("open", "open the tracker at queued")
    sp.add_argument("--issue", type=int, default=None)
    sp.add_argument("--root", default=None, help="project root holding .harness/project.json")
    sp = verb("step", "record a step: State, Next, and the move to active")
    sp.add_argument("--state", required=True)
    sp.add_argument("--next", dest="next_steps", required=True)
    sp.add_argument("--root", default=None)
    sp = verb("close", "close the tracker at done with its Outcome")
    sp.add_argument("--outcome", required=True)
    sp.add_argument("--state", default=None)
    sp.add_argument("--next", dest="next_steps", default=None)
    sp.add_argument("--root", default=None)
    return p


def main(argv: "list[str] | None" = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return USAGE if exc.code else 0
    if not args.verb:
        parser.print_usage(sys.stderr)
        return USAGE
    plan = Path(args.plan)
    try:
        if args.verb == "name":
            name = plan_name(plan)
            if name:
                print(name)
            return 0
        if args.verb == "status":
            status, source = plan_status(plan, args.tracker)
            print(f"{status}\t{source}")
            return 0
        if args.verb == "open":
            code, message = open_tracker(plan, args.tracker, issue=args.issue, root=args.root)
        elif args.verb == "step":
            code, message = step(plan, args.tracker, state=args.state,
                                 next_steps=args.next_steps, root=args.root)
        else:
            code, message = close(plan, args.tracker, outcome=args.outcome, state=args.state,
                                  next_steps=args.next_steps, root=args.root)
    except OSError as exc:
        print(f"[plan_tracker] {exc}", file=sys.stderr)
        return USAGE
    if code == 0:
        print(message)
    else:
        print(f"[plan_tracker] {message}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
