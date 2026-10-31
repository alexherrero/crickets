#!/usr/bin/env python3
"""Gate: the plugins emitted for Antigravity have the shape `agy` loads.

`agy plugin validate` is the real check, but it cannot run in CI (agy is not
npm-distributed). Between agy 1.0.2 and 1.4.x the host changed what it loads,
and the emitter kept writing the old shape: agy skipped the commands, the
rules, seven agents and the whole hooks.json of two plugins, and nothing in
CI noticed. This gate encodes the rules `agy plugin validate --strict` was
seen enforcing on 2026-10-30 (agy 1.4.11) and runs them over
dist/antigravity/plugins, so the same drift fails here instead.

What it checks, per plugin:
  - there is no commands/ folder (agy loads none; a command is a skill);
  - every rules/*.md has frontmatter with a `trigger` of always_on,
    model_decision, glob or manual; a model_decision rule has a description,
    a glob rule has globs;
  - every agents/*.md has YAML frontmatter with `name` and `description`, a
    `tools` that (if present) is a list, and no `model` (agy rejects Claude
    model tiers);
  - every skills/*/SKILL.md has `name` equal to its folder and a
    `description`, and a body no longer than agy loads (24,000 bytes);
  - hooks.json is an object; each hook uses only agy's events, with matcher
    groups for PreToolUse / PostToolUse and flat handler lists for
    SessionStart / PreInvocation / PostInvocation / Stop; every handler has a
    `command`; a command that names the hook adapter finds it in the plugin.

Exit 0 when clean, 1 with one line per problem.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIST = ROOT / "dist" / "antigravity" / "plugins"

TRIGGERS = {"always_on", "model_decision", "glob", "manual"}
GROUPED_EVENTS = {"PreToolUse", "PostToolUse"}
FLAT_EVENTS = {"SessionStart", "PreInvocation", "PostInvocation", "Stop"}
SKILL_BODY_LIMIT = 24_000


def split_frontmatter(text: str):
    """(parsed frontmatter dict | None, body). None when absent or not valid YAML."""
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    if end == -1:
        return None, text
    try:
        fm = yaml.safe_load(text[4:end])
    except yaml.YAMLError:
        return None, text[end + 4:]
    return (fm if isinstance(fm, dict) else None), text[end + 4:]


def check_rules(plugin: Path, problems: list[str]) -> None:
    for f in sorted((plugin / "rules").glob("*.md")):
        fm, _ = split_frontmatter(f.read_text(encoding="utf-8"))
        where = f"{plugin.name}/rules/{f.name}"
        if fm is None:
            problems.append(f"{where}: no readable frontmatter")
            continue
        trigger = fm.get("trigger")
        if trigger not in TRIGGERS:
            problems.append(f"{where}: trigger {trigger!r} is not one of {sorted(TRIGGERS)} — the rule never applies")
        elif trigger == "model_decision" and not fm.get("description"):
            problems.append(f"{where}: a model_decision rule needs a description")
        elif trigger == "glob" and not fm.get("globs"):
            problems.append(f"{where}: a glob rule needs globs")


def check_agents(plugin: Path, problems: list[str]) -> None:
    for f in sorted((plugin / "agents").glob("*.md")):
        fm, _ = split_frontmatter(f.read_text(encoding="utf-8"))
        where = f"{plugin.name}/agents/{f.name}"
        if fm is None:
            problems.append(f"{where}: no readable frontmatter — agy skips the agent")
            continue
        for key in ("name", "description"):
            if not fm.get(key):
                problems.append(f"{where}: missing {key}")
        if "tools" in fm and not isinstance(fm["tools"], list):
            problems.append(f"{where}: tools must be a YAML list for agy — agy skips the agent")
        if "model" in fm:
            problems.append(f"{where}: model {fm['model']!r} — agy rejects Claude model tiers; drop the line")


def check_skills(plugin: Path, problems: list[str]) -> None:
    for f in sorted((plugin / "skills").glob("*/SKILL.md")):
        fm, body = split_frontmatter(f.read_text(encoding="utf-8"))
        where = f"{plugin.name}/skills/{f.parent.name}/SKILL.md"
        if fm is None:
            problems.append(f"{where}: no readable frontmatter")
            continue
        if fm.get("name") != f.parent.name:
            problems.append(f"{where}: name {fm.get('name')!r} does not match the folder")
        if not fm.get("description"):
            problems.append(f"{where}: missing description")
        size = len(body.encode("utf-8"))
        if size > SKILL_BODY_LIMIT:
            problems.append(f"{where}: body is {size} bytes; agy loads only the first {SKILL_BODY_LIMIT}")


def check_handler(h, where: str, plugin: Path, problems: list[str]) -> None:
    if not isinstance(h, dict) or not h.get("command"):
        problems.append(f"{where}: a command hook must specify 'command' — agy skips the whole hooks.json")
        return
    m = re.search(r"\./(hooks/_agy_hook_adapter\.py)", h["command"])
    if m and not (plugin / m.group(1)).is_file():
        problems.append(f"{where}: runs {m.group(1)}, which is not in the plugin")


def check_hooks(plugin: Path, problems: list[str]) -> None:
    f = plugin / "hooks.json"
    if not f.is_file():
        return
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as e:
        problems.append(f"{plugin.name}/hooks.json: not valid JSON ({e})")
        return
    if not isinstance(data, dict):
        problems.append(f"{plugin.name}/hooks.json: must be an object keyed by hook name")
        return
    for hook, spec in data.items():
        for event, entries in (spec or {}).items():
            if event == "enabled":
                continue
            where = f"{plugin.name}/hooks.json {hook}.{event}"
            if event not in GROUPED_EVENTS | FLAT_EVENTS:
                problems.append(f"{where}: agy has no {event} event")
            elif not isinstance(entries, list):
                problems.append(f"{where}: must be a list")
            elif event in GROUPED_EVENTS:
                for g in entries:
                    if not isinstance(g, dict) or "matcher" not in g or not isinstance(g.get("hooks"), list):
                        problems.append(f"{where}: needs {{matcher, hooks: [...]}} groups")
                        continue
                    for h in g["hooks"]:
                        check_handler(h, where, plugin, problems)
            else:
                for h in entries:
                    if isinstance(h, dict) and "hooks" in h:
                        problems.append(f"{where}: {event} takes a flat list of handlers, not matcher groups")
                    else:
                        check_handler(h, where, plugin, problems)


def check_dist(dist: Path) -> list[str]:
    problems: list[str] = []
    for plugin in sorted(p for p in dist.iterdir() if p.is_dir()):
        if (plugin / "commands").exists():
            problems.append(f"{plugin.name}/commands: agy loads no commands — emit each as skills/<name>/SKILL.md")
        check_rules(plugin, problems)
        check_agents(plugin, problems)
        check_skills(plugin, problems)
        check_hooks(plugin, problems)
    return problems


def main(argv: list[str]) -> int:
    dist = Path(argv[1]) if len(argv) > 1 else DEFAULT_DIST
    if not dist.is_dir():
        print(f"check-agy-plugin-shape: {dist} not found", file=sys.stderr)
        return 1
    problems = check_dist(dist)
    for p in problems:
        print(f"FAIL {p}")
    if problems:
        print(f"check-agy-plugin-shape: {len(problems)} problem(s) in {dist}", file=sys.stderr)
        return 1
    print(f"check-agy-plugin-shape: clean ({sum(1 for p in dist.iterdir() if p.is_dir())} plugins)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
