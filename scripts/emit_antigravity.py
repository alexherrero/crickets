#!/usr/bin/env python3
"""Antigravity host emitter (crickets v3.0 #40, part 3).

Emits, per group, an Antigravity plugin under `dist/antigravity/plugins/<slug>/`:
  - `plugin.json` at the plugin ROOT (AG convention — confirmed via
    `agy plugin validate` v1.0.2; NO `dependencies` — AG composition is THIN,
    the requires is documented in the marketplace entry).
  - components copied under native subdirs (skills/, agents/, commands/).
  - `hooks.json` — each hook keyed by name with `enabled` + its AG event(s);
    script paths are RELATIVE (no `${CLAUDE_PLUGIN_ROOT}`); hook dir bundled
    under hooks/<name>/. Events with no AG equivalent (SessionStart /
    UserPromptSubmit) are skipped (the gap).
  - `mcp_config.json` merged from mcp-server primitives.
  - `rules/` — snippet/rule/output-style primitives all emit here (AG *can*
    ship instruction files, unlike Claude; output-style prose has no distinct
    AG mechanism so it folds into the same standing-instruction surface).
And one `.agents/plugins/marketplace.json` (AG marketplace shape) per host root.

Only `antigravity`-supporting primitives are emitted. Registered via
`generate._EMITTER_MODULES` (no self-register).
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate import HostEmitter, dump_json, write_utf8  # noqa: E402
from src_model import Group, Primitive, bundle_ignore, copy_group_scripts, copy_group_templates, copy_group_reference, enhances_to_json, render_primitive_text  # noqa: E402

HOST = "antigravity"

_COMPONENT_SUBDIR = {"skill": "skills", "agent": "agents", "command": "commands"}
# Antigravity's hook event set (no SessionStart / UserPromptSubmit).
AG_EVENTS = {"PreToolUse", "PostToolUse", "PreInvocation", "PostInvocation", "Stop"}
_SCRIPT_RE = re.compile(r"(?:\S*/)?([\w.-]+\.(?:sh|ps1|py))")


def _rewrite_relative(command: str, name: str) -> str:
    """AG hook commands use a RELATIVE script path (no ${CLAUDE_PLUGIN_ROOT})."""
    return _SCRIPT_RE.sub(lambda m: f"./hooks/{name}/{m.group(1)}", command, count=1)


class AntigravityEmitter(HostEmitter):
    host = HOST
    root_marketplace_rel = ".agents/plugins/marketplace.json"

    def emit_group(self, group: Group, dist_root: Path) -> dict | None:
        plugin_dir = dist_root / "plugins" / group.slug

        manifest = {
            "name": group.slug,
            "version": group.version,
            "description": group.description,
            "author": {"name": "alexherrero", "url": "https://github.com/alexherrero/crickets"},
        }
        # AG plugin.json lives at the plugin ROOT (not under .claude-plugin/) and
        # carries NO dependencies (thin composition; requires documented in the
        # marketplace entry).
        plugin_dir.mkdir(parents=True, exist_ok=True)
        write_utf8(plugin_dir / "plugin.json", dump_json(manifest))

        ag_hooks: dict[str, dict] = {}
        mcp_servers: dict[str, dict] = {}

        for prim in group.primitives:
            if not prim.supports(HOST):
                continue
            kind = prim.kind
            if kind in _COMPONENT_SUBDIR:
                self._copy_component(prim, plugin_dir / _COMPONENT_SUBDIR[kind])
            elif kind == "hook":
                self._emit_hook(prim, plugin_dir, ag_hooks)
            elif kind in ("snippet", "rule", "output-style"):
                # AG ships rules/ (unlike Claude) — snippet/rule are already
                # instruction-file content, and output-style prose ("silence
                # inter-tool chatter…") is functionally the same kind of
                # standing instruction; AG has no distinct output-style
                # mechanism, so it folds in here rather than getting dropped
                # (cricketsBuild#1 — supported_hosts claimed antigravity for
                # these kinds but the emitter dropped them on the floor).
                self._copy_component(prim, plugin_dir / "rules")
            elif kind == "mcp-server":
                self._merge_mcp(prim, mcp_servers)
            else:
                print(f"emit_antigravity: skipping unsupported kind '{kind}' "
                      f"('{prim.name}' in '{group.slug}')", file=sys.stderr)

        if ag_hooks:
            write_utf8(plugin_dir / "hooks.json", dump_json(ag_hooks))
        if mcp_servers:
            write_utf8(plugin_dir / "mcp_config.json",
                       dump_json({"mcpServers": mcp_servers}))
        copy_group_scripts(group, plugin_dir)
        copy_group_templates(group, plugin_dir)
        copy_group_reference(group, plugin_dir)

        # capabilities.json sidecar — persists capabilities:/enhances: alongside
        # the plugin.json so the agentm resolver can read them after `agy plugin
        # install <path>` (agy has no marketplace registry; plugin.json stays thin).
        # Only emitted when the group declares at least one capability or enhance.
        if group.capabilities or group.enhances:
            sidecar: dict = {"version": group.version}
            if group.capabilities:
                sidecar["capabilities"] = list(group.capabilities)
            if group.enhances:
                sidecar["enhances"] = enhances_to_json(group.enhances)
            write_utf8(plugin_dir / "capabilities.json", dump_json(sidecar))

        entry = {
            "name": group.slug,
            "source": {"source": "local", "path": f"./plugins/{group.slug}"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": group.category,
        }
        if group.requires:
            entry["requires"] = sorted(group.requires)
        if group.capabilities:
            entry["capabilities"] = list(group.capabilities)
        if group.enhances:
            entry["enhances"] = enhances_to_json(group.enhances)
        return entry

    def _copy_component(self, prim: Primitive, dest_dir: Path) -> None:
        dest_dir.mkdir(parents=True, exist_ok=True)
        if prim.root.is_dir():
            shutil.copytree(prim.root, dest_dir / prim.root.name, dirs_exist_ok=True,
                            ignore=bundle_ignore())
        else:
            # render_primitive_text is a no-op (raw text) for a primitive with
            # no `opinions:` frontmatter key — every other single-file primitive
            # emits byte-identical to the plain copy2 this replaces.
            write_utf8(dest_dir / prim.root.name, render_primitive_text(prim))

    def _emit_hook(self, prim: Primitive, plugin_dir: Path, ag_hooks: dict) -> None:
        bundled = plugin_dir / "hooks" / prim.name
        bundled.mkdir(parents=True, exist_ok=True)
        if prim.root.is_dir():
            shutil.copytree(prim.root, bundled, dirs_exist_ok=True,
                            ignore=bundle_ignore())
        frag_path = (prim.root if prim.root.is_dir() else prim.root.parent) / "settings-fragment-bash.json"
        if not frag_path.exists():
            print(f"emit_antigravity: hook '{prim.name}' has no settings-fragment-bash.json "
                  f"— bundled scripts only, no event registration", file=sys.stderr)
            return
        frag = json.loads(frag_path.read_text(encoding="utf-8"))
        events: dict[str, list] = {}
        for event, entries in (frag.get("hooks") or {}).items():
            if event not in AG_EVENTS:
                print(f"emit_antigravity: hook '{prim.name}' event '{event}' has no "
                      f"Antigravity equivalent — skipped", file=sys.stderr)
                continue
            for entry in entries:
                for h in entry.get("hooks", []):
                    if "command" in h:
                        h["command"] = _rewrite_relative(h["command"], prim.name)
            events[event] = entries
        if events:
            ag_hooks[prim.name] = {"enabled": True, **events}

    def _merge_mcp(self, prim: Primitive, mcp_servers: dict) -> None:
        root = prim.root if prim.root.is_dir() else prim.root.parent
        cfg_path = next((root / n for n in ("mcp.json", "mcp_config.json") if (root / n).exists()), None)
        if cfg_path is None:
            print(f"emit_antigravity: mcp-server '{prim.name}' has no mcp.json — skipped",
                  file=sys.stderr)
            return
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        mcp_servers.update(cfg.get("mcpServers", cfg))

    def _marketplace(self, entries: list[dict]) -> dict:
        return {
            "name": "crickets",
            "interface": {"displayName": "Crickets"},
            "plugins": sorted(entries, key=lambda e: e["name"]),
        }

    def write_marketplace(self, entries: list[dict], dist_root: Path) -> None:
        mp = dist_root / ".agents" / "plugins"
        mp.mkdir(parents=True, exist_ok=True)
        write_utf8(mp / "marketplace.json", dump_json(self._marketplace(entries)))

    def write_root_marketplace(self, entries: list[dict], repo_root: Path) -> None:
        # Same manifest, but each plugin source points at its committed dist/
        # location relative to the repo root (AG source is a {source,path} object).
        rooted = [
            {**e, "source": {"source": "local", "path": f"./dist/{self.host}/plugins/{e['name']}"}}
            for e in entries
        ]
        dest = repo_root / self.root_marketplace_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        write_utf8(dest, dump_json(self._marketplace(rooted)))
