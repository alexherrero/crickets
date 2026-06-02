#!/usr/bin/env python3
"""Antigravity host emitter (crickets v3.0 #40, part 3).

Emits, per group, an Antigravity plugin under `dist/antigravity/plugins/<slug>/`:
  - `.claude-plugin/plugin.json` (AG reuses the convention — minimal
    name/version/description/author; NO `dependencies` — AG composition is
    THIN, the requires is documented in the marketplace entry).
  - components copied under native subdirs (skills/, agents/, commands/).
  - hooks (AG event set + relative paths), mcp_config.json, snippets→rules/ land
    in part 3 task 3.
And one `.agents/plugins/marketplace.json` (AG marketplace shape) per host root.

Only `antigravity`-supporting primitives are emitted. Registered via
`generate._EMITTER_MODULES` (no self-register — the part-2 pattern).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate import HostEmitter, dump_json  # noqa: E402
from src_model import Group, Primitive  # noqa: E402

HOST = "antigravity"
PLUGIN_VERSION = "0.1.0"

_COMPONENT_SUBDIR = {"skill": "skills", "agent": "agents", "command": "commands"}


class AntigravityEmitter(HostEmitter):
    host = HOST

    def emit_group(self, group: Group, dist_root: Path) -> dict | None:
        plugin_dir = dist_root / "plugins" / group.slug

        manifest = {
            "name": group.slug,
            "version": PLUGIN_VERSION,
            "description": group.description,
            "author": {"name": "alexherrero", "url": "https://github.com/alexherrero/crickets"},
        }
        # AG composition is THIN: no native dependencies in plugin.json. The
        # `requires` is recorded in the marketplace entry below (documented, not
        # inlined). If AG turns out to support native deps (part 3 task 4
        # verify-on-dogfood), switch this to a real dependencies field.
        cp = plugin_dir / ".claude-plugin"
        cp.mkdir(parents=True, exist_ok=True)
        (cp / "plugin.json").write_text(dump_json(manifest), encoding="utf-8")

        for prim in group.primitives:
            if not prim.supports(HOST):
                continue
            sub = _COMPONENT_SUBDIR.get(prim.kind)
            if sub is None:
                continue  # hooks / mcp / snippets handled in task 3
            self._copy_component(prim, plugin_dir / sub)

        entry = {
            "name": group.slug,
            "source": {"source": "local", "path": f"./plugins/{group.slug}"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": group.category,
        }
        if group.requires:
            entry["requires"] = sorted(group.requires)  # documented (thin composition)
        return entry

    def _copy_component(self, prim: Primitive, dest_dir: Path) -> None:
        dest_dir.mkdir(parents=True, exist_ok=True)
        if prim.root.is_dir():
            shutil.copytree(prim.root, dest_dir / prim.root.name, dirs_exist_ok=True)
        else:
            shutil.copy2(prim.root, dest_dir / prim.root.name)

    def write_marketplace(self, entries: list[dict], dist_root: Path) -> None:
        marketplace = {
            "name": "crickets",
            "interface": {"displayName": "Crickets"},
            "plugins": sorted(entries, key=lambda e: e["name"]),
        }
        mp = dist_root / ".agents" / "plugins"
        mp.mkdir(parents=True, exist_ok=True)
        (mp / "marketplace.json").write_text(dump_json(marketplace), encoding="utf-8")
