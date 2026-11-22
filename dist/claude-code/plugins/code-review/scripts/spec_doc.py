#!/usr/bin/env python3
"""spec_doc.py — render, parse, place and check a spec, the anchor every task is graded against.

    spec_doc.py place --slug SLUG [--plan PLAN.md [--multi]] [--project-root DIR]
    spec_doc.py check FILE.md
    spec_doc.py render [FILE.json]            (JSON on stdin when no file is given)

A spec is one markdown file with these sections, in this order:

    # Spec: <title>
    **Profile:** build | create | both
    ## Goal
    ## Done when            checkable lines, one per bullet
    ## Rules               "- <rule> — source: <where it comes from>"
    ## Not doing
    ## Open questions      "none", or blocking questions only
    ## Reference           create / both only: the reference folder
    ## Likeness list       create / both only: 5 to 10 lines

`/spec` writes it; `/plan`, `/build-it` and `/create-it` read it. The judgment
(what the goal is, which rules apply, what to ask the operator) is the command's.
Everything a script can settle lives here: where the file goes, whether the
shape is complete, and the round trip between text and fields.

Where a spec goes (`place`):
    --plan PLAN.md            beside that plan, as `spec.md`
    --plan PLAN.md --multi    the spec covers several tasks: one level up, in the
                              project, as `spec-<slug>.md`; each plan links it
    neither                   no vault: `<project-root>/.harness/spec-<slug>.md`
`place` only computes the path. It creates nothing and asks agentm nothing.

What `check` enforces:
    - every section is present, in the profile it belongs to
    - Goal is not empty; Done when has at least one line
    - every Done-when line can be checked: it names something observable (a code
      span, a number, a path, or a check verb such as "returns" or "exits") and
      is not only a vague word ("works well", "clean", "robust")
    - every rule names its source
    - Not doing and Open questions each say "none" or list items; Open questions
      lists blocking questions only, and each ends in "?"
    - create / both: a reference folder and 5 to 10 likeness lines

Exit codes: 0 fine; 1 `check` found problems (printed one per line, `section: message`);
2 usage error or unreadable input.

No agentm, no vault, no network. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

PROFILES = ("build", "create", "both")
LIKENESS_MIN, LIKENESS_MAX = 5, 10

_NONE_RE = re.compile(r"^\s*none\.?\s*$", re.IGNORECASE)
_SOURCE_RE = re.compile(r"\s+(?:—|--|-)\s*source:\s*(?P<src>.*)$", re.IGNORECASE)
_PAREN_SOURCE_RE = re.compile(r"\s*\(source:\s*(?P<src>[^)]*)\)\s*$", re.IGNORECASE)
_BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(?:\[[ xX]\]\s+)?(?P<text>.*\S)\s*$")
_HEADING_RE = re.compile(r"^##\s+(?P<name>.+?)\s*$")
_TITLE_RE = re.compile(r"^#\s+Spec:\s*(?P<title>.+?)\s*$")
_PROFILE_RE = re.compile(r"^\*\*Profile:\*\*\s*(?P<p>\S+)\s*$")

# Section names as written, keyed by the field they fill.
SECTIONS = {
    "goal": "Goal",
    "done_when": "Done when",
    "rules": "Rules",
    "not_doing": "Not doing",
    "open_questions": "Open questions",
    "reference": "Reference",
    "likeness": "Likeness list",
}
_BY_HEADING = {v.lower(): k for k, v in SECTIONS.items()}

# A Done-when line is checkable when it names something a person or a script can
# look at. These are the signs of that; a vague word with none of them is flagged.
_CHECK_VERBS = (
    "returns", "return", "exits", "exit", "prints", "print", "contains", "contain",
    "fails", "fail", "passes", "pass", "shows", "show", "emits", "emit", "renders",
    "render", "matches", "match", "equals", "equal", "exists", "exist", "is present",
    "are present", "is absent", "are absent", "appears", "appear", "lists", "list",
    "writes", "write", "creates", "create", "rejects", "reject", "refuses", "refuse",
    "opens", "open", "names", "name", "reports", "report", "runs", "run", "builds",
    "build", "reads", "read", "asks", "ask", "stops", "stop", "skips", "skip",
    "at least", "at most", "no more than", "fewer than", "more than", "under",
    "over", "every", "none of", "never",
)
_VAGUE_WORDS = (
    "works well", "work well", "good", "nice", "clean", "robust", "properly",
    "correctly", "better", "intuitive", "easy", "easily", "fast", "quick",
    "user-friendly", "as expected", "appropriate", "appropriately", "elegant",
    "polished", "seamless", "reasonable", "sensible", "etc",
)


@dataclass
class Rule:
    text: str
    source: str = ""


@dataclass
class Spec:
    """One spec. A list that is `None` means the section was missing; an empty
    list means the section said "none"."""

    title: str = ""
    profile: str = "build"
    goal: str = ""
    done_when: Optional[List[str]] = None
    rules: Optional[List[Rule]] = None
    not_doing: Optional[List[str]] = None
    open_questions: Optional[List[str]] = None
    reference: Optional[str] = None
    likeness: Optional[List[str]] = None
    extra: List[Tuple[str, str]] = field(default_factory=list)

    @property
    def wants_reference(self) -> bool:
        return self.profile in ("create", "both")


# --------------------------------------------------------------------- render

def _bullets(items: List[str]) -> str:
    return "\n".join(f"- {i}" for i in items)


def _render_list(items: Optional[List[str]]) -> str:
    if items is None:
        return ""
    return "none" if not items else _bullets(items)


def render(spec: Spec) -> str:
    """The spec as markdown. A section left `None` is omitted, so `check`
    reports it; the round trip `parse(render(s))` gives back an equal spec."""
    out: List[str] = [f"# Spec: {spec.title}", "", f"**Profile:** {spec.profile}", ""]

    def section(key: str, body: str) -> None:
        out.extend([f"## {SECTIONS[key]}", "", body.rstrip(), ""])

    section("goal", spec.goal)
    if spec.done_when is not None:
        section("done_when", _bullets(spec.done_when))
    if spec.rules is not None:
        if spec.rules:
            section("rules", "\n".join(
                f"- {r.text} — source: {r.source}".rstrip() if r.source else f"- {r.text}"
                for r in spec.rules))
        else:
            section("rules", "none")
    if spec.not_doing is not None:
        section("not_doing", _render_list(spec.not_doing))
    if spec.open_questions is not None:
        section("open_questions", _render_list(spec.open_questions))
    if spec.reference is not None:
        section("reference", spec.reference)
    if spec.likeness is not None:
        section("likeness", _render_list(spec.likeness))
    for heading, body in spec.extra:
        out.extend([f"## {heading}", "", body.rstrip(), ""])
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------------- parse

def _parse_list(body: str) -> List[str]:
    """Bullets in a section body; `none` (alone) is an empty list."""
    if _NONE_RE.match(body.strip()):
        return []
    items: List[str] = []
    for line in body.splitlines():
        m = _BULLET_RE.match(line)
        if m:
            items.append(m.group("text").strip())
        elif line.strip() and items and line.startswith((" ", "\t")):
            items[-1] += " " + line.strip()  # a wrapped bullet
    return items


def _parse_rule(text: str) -> Rule:
    m = _PAREN_SOURCE_RE.search(text) or _SOURCE_RE.search(text)
    if not m:
        return Rule(text.strip())
    return Rule(text[: m.start()].strip(), m.group("src").strip())


def parse(text: str) -> Spec:
    """Read a spec. Tolerant: a missing section is `None`, never an error, so
    `check` can say what is missing. Unknown sections are kept in `extra`."""
    spec = Spec()
    sections: List[Tuple[str, List[str]]] = []
    current: Optional[Tuple[str, List[str]]] = None
    for line in text.splitlines():
        m = _TITLE_RE.match(line)
        if m and current is None and not spec.title:
            spec.title = m.group("title")
            continue
        m = _PROFILE_RE.match(line)
        if m and current is None:
            spec.profile = m.group("p").lower()
            continue
        m = _HEADING_RE.match(line)
        if m:
            current = (m.group("name"), [])
            sections.append(current)
            continue
        if current is not None:
            current[1].append(line)

    for heading, lines in sections:
        body = "\n".join(lines).strip("\n")
        key = _BY_HEADING.get(heading.strip().lower())
        if key is None:
            spec.extra.append((heading, body.strip()))
        elif key == "goal":
            spec.goal = body.strip()
        elif key == "done_when":
            spec.done_when = _parse_list(body)
        elif key == "rules":
            spec.rules = [] if _NONE_RE.match(body.strip()) else [
                _parse_rule(i) for i in _parse_list(body)]
        elif key == "not_doing":
            spec.not_doing = _parse_list(body)
        elif key == "open_questions":
            spec.open_questions = _parse_list(body)
        elif key == "reference":
            spec.reference = body.strip()
        elif key == "likeness":
            spec.likeness = _parse_list(body)
    return spec


# ---------------------------------------------------------------------- check

def done_line_problem(line: str) -> Optional[str]:
    """Why a Done-when line cannot be checked, or None when it can."""
    low = line.lower()
    concrete = bool(re.search(r"`[^`]+`|\d|[\w.-]+/[\w./-]+|\w+\.\w{1,5}\b", line))
    verb = any(re.search(rf"\b{re.escape(v)}\b", low) for v in _CHECK_VERBS)
    vague = [w for w in _VAGUE_WORDS if re.search(rf"\b{re.escape(w)}\b", low)]
    if vague and not concrete:
        return (f"cannot be checked: \"{vague[0]}\" is a judgment, not an observation "
                "(name the output, file, number or command that shows it)")
    if not concrete and not verb:
        return ("cannot be checked: it names nothing to look at "
                "(a command, a file, a number, or what the output says)")
    return None


def check(spec: Spec) -> List[str]:
    """Every shape problem, as `section: message`. Empty when the spec is sound."""
    problems: List[str] = []

    def add(section: str, msg: str) -> None:
        problems.append(f"{section}: {msg}")

    if not spec.title:
        add("Title", "missing `# Spec: <title>` heading")
    if spec.profile not in PROFILES:
        add("Profile", f"'{spec.profile}' is not one of {', '.join(PROFILES)}")

    if not spec.goal.strip():
        add("Goal", "missing or empty")

    if spec.done_when is None:
        add("Done when", "section missing")
    elif not spec.done_when:
        add("Done when", "has no lines (a spec with nothing to check is not an anchor)")
    else:
        for line in spec.done_when:
            why = done_line_problem(line)
            if why:
                add("Done when", f"\"{line}\" {why}")

    if spec.rules is None:
        add("Rules", "section missing (write `none` if no rule applies)")
    else:
        for r in spec.rules:
            if not r.text:
                add("Rules", "an empty rule")
            elif not r.source:
                add("Rules", f"\"{r.text}\" names no source (add `— source: <file or section>`)")

    if spec.not_doing is None:
        add("Not doing", "section missing (write `none` if there is nothing to rule out)")

    if spec.open_questions is None:
        add("Open questions", "section missing (write `none` if nothing blocks)")
    else:
        for q in spec.open_questions:
            if not q.rstrip().endswith("?"):
                add("Open questions", f"\"{q}\" is not a question; this section lists blocking questions only")

    if spec.wants_reference:
        if not (spec.reference or "").strip():
            add("Reference", "missing: a create spec names its reference folder")
        n = None if spec.likeness is None else len(spec.likeness)
        if n is None:
            add("Likeness list", "section missing: a create spec carries a likeness list")
        elif not LIKENESS_MIN <= n <= LIKENESS_MAX:
            add("Likeness list", f"has {n} lines; keep it to {LIKENESS_MIN}-{LIKENESS_MAX}")
    return problems


# ---------------------------------------------------------------------- place

def place(slug: str, *, plan: Optional[Path] = None, multi: bool = False,
          project_root: Optional[Path] = None) -> Path:
    """Where this spec goes. Computes a path; creates nothing.

    `plan` is the task's plan.md (the file need not exist yet). With `multi`
    the spec sits one level up, in the project, because several tasks share it.
    """
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", slug):
        raise ValueError(f"slug '{slug}' must be lowercase letters, digits, dots, dashes or underscores")
    if plan is not None:
        task_dir = Path(plan).parent
        if not multi:
            return task_dir / "spec.md"
        # <project>/tasks/<NNN-name>/plan.md -> <project>; with no `tasks` level,
        # one directory up from the plan's own.
        project = task_dir.parent.parent if task_dir.parent.name == "tasks" else task_dir.parent
        return project / f"spec-{slug}.md"
    if multi:
        raise ValueError("--multi needs --plan: a spec shared by tasks sits above their plans")
    if project_root is None:
        raise ValueError("no vault: pass --project-root so the spec can go in <project-root>/.harness/")
    return Path(project_root) / ".harness" / f"spec-{slug}.md"


# ------------------------------------------------------------------------ CLI

def _spec_from_json(data: dict) -> Spec:
    rules = data.get("rules")
    return Spec(
        title=data.get("title", ""),
        profile=data.get("profile", "build"),
        goal=data.get("goal", ""),
        done_when=data.get("done_when"),
        rules=None if rules is None else [
            Rule(r, "") if isinstance(r, str) else Rule(r.get("text", ""), r.get("source", ""))
            for r in rules],
        not_doing=data.get("not_doing"),
        open_questions=data.get("open_questions"),
        reference=data.get("reference"),
        likeness=data.get("likeness"),
        extra=[tuple(e) for e in data.get("extra", [])],
    )


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="spec_doc.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("place", help="print where a spec goes")
    pl.add_argument("--slug", required=True)
    pl.add_argument("--plan", help="the task's plan.md")
    pl.add_argument("--multi", action="store_true", help="the spec covers several tasks")
    pl.add_argument("--project-root", help="the repo root, for the no-vault path")
    ck = sub.add_parser("check", help="check a spec's shape; exit 1 on problems")
    ck.add_argument("file")
    rd = sub.add_parser("render", help="render a spec from JSON")
    rd.add_argument("file", nargs="?", help="JSON file (stdin when omitted)")
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
    args = _build_parser().parse_args(argv)
    try:
        if args.cmd == "place":
            path = place(args.slug, plan=Path(args.plan) if args.plan else None,
                         multi=args.multi,
                         project_root=Path(args.project_root) if args.project_root else None)
            print(path)
            return 0
        if args.cmd == "check":
            text = Path(args.file).read_text(encoding="utf-8")
            problems = check(parse(text))
            for line in problems:
                print(line)
            return 1 if problems else 0
        if args.cmd == "render":
            raw = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
            sys.stdout.write(render(_spec_from_json(json.loads(raw))))
            return 0
    except (OSError, ValueError) as exc:
        print(f"spec_doc: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
