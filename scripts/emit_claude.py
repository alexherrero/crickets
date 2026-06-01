#!/usr/bin/env python3
"""Claude Code host emitter (crickets v3.0 #40, part 2).

Emits, per group, a `dist/plugins/<slug>/` Claude plugin:
  - `.claude-plugin/plugin.json` (name/displayName/version/description +
    native `dependencies` derived from the group's `requires:`).
  - components copied under native subdirs (skills/, agents/, commands/).
    Hooks + MCP land in part 2 task 3.
And one top-level `.claude-plugin/marketplace.json` listing every claude-code
group with a relative `source`.

Self-registers with the generator on import.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate import HostEmitter, dump_json  # noqa: E402  (registered by generate._load_emitters)
from src_model import Group  # noqa: E402

HOST = "claude-code"
PLUGIN_VERSION = "0.1.0"

# native component subdir per kind (the kinds T2 copies; hooks/mcp → T3).
_COMPONENT_SUBDIR = {"skill": "skills", "agent": "agents", "command": "commands"}


class ClaudeEmitter(HostEmitter):
    host = HOST

    def emit_group(self, group: Group, dist_root: Path) -> dict | None:
        plugin_dir = dist_root / "plugins" / group.slug

        manifest = {
            "name": group.slug,
            "displayName": group.name,
            "version": PLUGIN_VERSION,
            "description": group.description,
        }
        if group.requires:
            manifest["dependencies"] = sorted(group.requires)
        cp = plugin_dir / ".claude-plugin"
        cp.mkdir(parents=True, exist_ok=True)
        (cp / "plugin.json").write_text(dump_json(manifest), encoding="utf-8")

        # Components (skills / agents / commands). Hooks + MCP handled in T3.
        for prim in group.primitives:
            if not prim.supports(HOST):
                continue
            sub = _COMPONENT_SUBDIR.get(prim.kind)
            if sub is None:
                continue
            dest_dir = plugin_dir / sub
            dest_dir.mkdir(parents=True, exist_ok=True)
            if prim.root.is_dir():
                shutil.copytree(prim.root, dest_dir / prim.root.name, dirs_exist_ok=True)
            else:
                shutil.copy2(prim.root, dest_dir / prim.root.name)

        entry = {
            "name": group.slug,
            "description": group.description,
            "version": PLUGIN_VERSION,
            "source": f"./plugins/{group.slug}",
        }
        if group.requires:
            entry["dependencies"] = sorted(group.requires)
        return entry

    def write_marketplace(self, entries: list[dict], dist_root: Path) -> None:
        marketplace = {
            "name": "crickets",
            "owner": {"name": "alexherrero"},
            "plugins": sorted(entries, key=lambda e: e["name"]),
        }
        cp = dist_root / ".claude-plugin"
        cp.mkdir(parents=True, exist_ok=True)
        (cp / "marketplace.json").write_text(dump_json(marketplace), encoding="utf-8")
