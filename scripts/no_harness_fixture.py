"""no_harness_fixture — a scratch project in the task layout, and a stub agentm.

Test helper, not shipped. Tests that exercise a plugin's writer build a
`ScratchProject`, point the plugin at its stub agentm through
`AGENTM_SCRIPTS_DIR`, run the writer, then call `harness_dirs(root)` — which
must come back empty. That is how a test proves a writer cannot recreate the
retired harness directory (agentm-vault part 15).

The layout is the project skeleton since the projects migration:

    <root>/vault/projects/demo/
        charter.md
        tasks/042-build-the-brief/{plan.md, progress.md, tracker.md}
        designs/
        desk/
    <root>/repo/.harness/project.json      {"vault_project": "demo"}
    <root>/agentm/process_seam.py           project-path {tasks|designs|desk}
    <root>/agentm/harness_memory.py         list-plans, resolve-active-plan
    <root>/agentm/tracker.py                show

The stubs answer the way agentm's verbs do (`process_seam.py project-path`,
`harness_memory.py list-plans` and `resolve-active-plan --with-tracker`,
`tracker.py show`), from this scratch vault. `no_home=True` makes
`project-path` exit 1, the answer for a project with no vault home.
`resolve_by_slug=False` makes `resolve-active-plan` refuse `--project`, as an
agentm from before crickets task 101's ruling 9 does.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

# The directory name no writer may create.
HARNESS_DIRNAME = "_harness"  # harness-deprecation: the name the no-harness check refuses

TASK = "042-build-the-brief"

_PLAN = """---
parent_design_doc: wiki/designs/demo.md
touches_architecture: false
---

# Plan: Build the brief

## Goal

A brief exists.

## Steps

### 1. Write it
- **What:** write the brief.
- **Verification:** it exists.
- **Status:** [ ]
"""

_TRACKER = """---
kind: tracker
title: Build the brief
project: demo
task: 042-build-the-brief
status: active
opened: 2026-09-22
updated: 2026-09-22
closed:
design: wiki/designs/demo.md
---

## Objective

A brief exists.

## State

## Next

Step 1: Write it

## Outcome
"""

_PROCESS_SEAM = '''#!/usr/bin/env python3
import sys
VAULT_PROJECTS = {vault_projects!r}
NO_HOME = {no_home!r}
args = sys.argv[1:]
if not args or args[0] != "project-path" or len(args) < 2:
    sys.stderr.write("usage: process_seam project-path {{tasks,designs,desk}}\\n")
    sys.exit(2)
kind = args[1]
if kind not in ("tasks", "designs", "desk"):
    sys.stderr.write("process_seam: invalid choice: %r\\n" % kind)
    sys.exit(2)
project = "demo"
if "--project" in args:
    project = args[args.index("--project") + 1]
if NO_HOME:
    sys.stderr.write("process_seam: no vault home for this project\\n")
    sys.exit(1)
print(VAULT_PROJECTS + "/" + project + "/" + kind)
'''

_HARNESS_MEMORY = '''#!/usr/bin/env python3
import sys
from pathlib import Path
VAULT_PROJECTS = {vault_projects!r}
RESOLVE_BY_SLUG = {resolve_by_slug!r}
args = sys.argv[1:]
if not args or args[0] not in ("list-plans", "resolve-active-plan"):
    sys.stderr.write("usage: harness_memory {{list-plans,resolve-active-plan}}\\n")
    sys.exit(2)
if "--project" in args and args[0] == "resolve-active-plan" and not RESOLVE_BY_SLUG:
    sys.stderr.write("harness_memory: error: unrecognized arguments: --project\\n")
    sys.exit(2)
project = "demo"
if "--project" in args:
    project = args[args.index("--project") + 1]
tasks = Path(VAULT_PROJECTS) / project / "tasks"
if args[0] == "list-plans":
    for plan in sorted(tasks.glob("*/plan.md")):
        print(plan)
    sys.exit(0)
task = tasks / args[args.index("--plan") + 1]
if not (task / "plan.md").is_file():
    sys.stderr.write("harness_memory: no such plan\\n")
    sys.exit(2)
fields = [task / "plan.md", task / "progress.md"]
if "--with-tracker" in args:
    fields.append(task / "tracker.md")
print("\\t".join(str(f) for f in fields))
'''

_TRACKER_PY = '''#!/usr/bin/env python3
import json, sys
from pathlib import Path
args = sys.argv[1:]
if len(args) != 2 or args[0] != "show" or not Path(args[1]).is_file():
    sys.stderr.write("tracker: usage: show PATH\\n")
    sys.exit(2)
fields = {}
lines = Path(args[1]).read_text(encoding="utf-8").splitlines()
for line in lines[1:lines.index("---", 1)]:
    key, _, value = line.partition(":")
    fields[key.strip()] = value.strip() or None
print(json.dumps(fields))
'''


class ScratchProject:
    """A scratch vault project in the task layout, a repo bound to it, and a stub agentm."""

    def __init__(self, *, no_home: bool = False, resolve_by_slug: bool = True):
        self.root = Path(tempfile.mkdtemp(prefix="no-harness-")).resolve()
        self.vault = self.root / "vault"
        self.projects = self.vault / "projects"
        self.project = self.projects / "demo"
        self.task = self.project / "tasks" / TASK
        self.designs = self.project / "designs"
        self.desk = self.project / "desk"
        self.repo = self.root / "repo"
        self.agentm = self.root / "agentm"

        self.task.mkdir(parents=True)
        self.designs.mkdir()
        self.desk.mkdir()
        (self.project / "charter.md").write_text("# demo\n\n**What:** a demo project.\n", encoding="utf-8")
        (self.task / "plan.md").write_text(_PLAN, encoding="utf-8")
        (self.task / "progress.md").write_text("# Progress\n", encoding="utf-8")
        (self.task / "tracker.md").write_text(_TRACKER, encoding="utf-8")

        (self.repo / ".harness").mkdir(parents=True)
        (self.repo / ".harness" / "project.json").write_text(
            json.dumps({"vault_project": "demo"}) + "\n", encoding="utf-8")

        self.agentm.mkdir()
        fill = {"vault_projects": str(self.projects), "no_home": no_home}
        (self.agentm / "process_seam.py").write_text(_PROCESS_SEAM.format(**fill), encoding="utf-8")
        (self.agentm / "harness_memory.py").write_text(
            _HARNESS_MEMORY.format(vault_projects=str(self.projects), resolve_by_slug=resolve_by_slug),
            encoding="utf-8")
        (self.agentm / "tracker.py").write_text(_TRACKER_PY, encoding="utf-8")

    @property
    def plan(self) -> Path:
        return self.task / "plan.md"

    def env(self, base: "dict | None" = None) -> dict:
        """An environment whose agentm is this project's stub."""
        env = dict(os.environ if base is None else base)
        env["AGENTM_SCRIPTS_DIR"] = str(self.agentm)
        return env

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> "ScratchProject":
        return self

    def __exit__(self, *exc) -> None:
        self.cleanup()


def harness_dirs(root: "str | os.PathLike") -> list[Path]:
    """Every directory under `root` named like the retired harness directory."""
    return sorted(p for p in Path(root).rglob(HARNESS_DIRNAME) if p.is_dir())
