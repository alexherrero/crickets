#!/usr/bin/env python3
"""Claude Code host emitter (crickets v3.0 #40, part 2).

Emits, per group, a `dist/plugins/<slug>/` Claude plugin:
  - `.claude-plugin/plugin.json` (name/displayName/version/description +
    native `dependencies` from the group's `requires:`).
  - components copied under native subdirs (skills/, agents/, commands/).
  - `hooks/hooks.json` — each hook primitive translated onto its Claude event
    (read from its settings-fragment-bash.json) with the script path rewritten
    to `${CLAUDE_PLUGIN_ROOT}/...`, and the hook dir bundled under hooks/<name>/.
  - `.mcp.json` merged from mcp-server primitives.
  - output-styles/ copied from output-style primitives.
  - snippets are DROPPED (Claude can't ship instruction files) — recorded on
    stderr per the coverage-gap design call.
And one top-level `.claude-plugin/marketplace.json`.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate import HostEmitter, dump_json  # noqa: E402  (registered by generate._load_emitters)
from src_model import Group, Primitive, bundle_ignore, copy_group_scripts, enhances_to_json  # noqa: E402

HOST = "claude-code"
PLUGIN_VERSION = "0.1.0"

# kinds copied verbatim into a native component subdir.
_COMPONENT_SUBDIR = {"skill": "skills", "agent": "agents", "command": "commands"}

_SCRIPT_RE = re.compile(r"(?:\S*/)?([\w.-]+\.(?:sh|ps1|py))")


def _rewrite_hook_command(command: str, name: str) -> str:
    """Rewrite a settings-fragment hook command's script path to the bundled
    `${CLAUDE_PLUGIN_ROOT}/hooks/<name>/<script>` location."""
    return _SCRIPT_RE.sub(
        lambda m: f"${{CLAUDE_PLUGIN_ROOT}}/hooks/{name}/{m.group(1)}", command, count=1)


class ClaudeEmitter(HostEmitter):
    host = HOST
    root_marketplace_rel = ".claude-plugin/marketplace.json"

    def emit_group(self, group: Group, dist_root: Path) -> dict | None:
        plugin_dir = dist_root / "plugins" / group.slug

        manifest = {
            "name": group.slug,
            "version": PLUGIN_VERSION,
            "description": group.description,
            "author": {"name": "alexherrero", "url": "https://github.com/alexherrero/crickets"},
        }
        if group.requires:
            manifest["dependencies"] = sorted(group.requires)
        # NOTE: `capabilities`/`enhances` are NOT written to plugin.json — Claude's
        # plugin.json schema rejects unrecognized keys (`claude plugin validate`:
        # `root: Unrecognized key: "capabilities"`). Only `dependencies` (from
        # `requires`) is a recognized key. The soft-composition metadata lives in
        # the marketplace entry only (below), mirroring the Antigravity emitter.
        cp = plugin_dir / ".claude-plugin"
        cp.mkdir(parents=True, exist_ok=True)
        (cp / "plugin.json").write_text(dump_json(manifest), encoding="utf-8")

        hooks: dict[str, list] = {}
        mcp_servers: dict[str, dict] = {}

        for prim in group.primitives:
            if not prim.supports(HOST):
                continue
            kind = prim.kind
            if kind in _COMPONENT_SUBDIR:
                self._copy_component(prim, plugin_dir / _COMPONENT_SUBDIR[kind])
            elif kind == "hook":
                self._emit_hook(prim, plugin_dir, hooks)
            elif kind == "output-style":
                self._copy_component(prim, plugin_dir / "output-styles")
            elif kind == "mcp-server":
                self._merge_mcp(prim, mcp_servers)
            elif kind == "snippet":
                # Claude can't ship instruction files — drop (coverage-gap call).
                print(f"emit_claude: dropping snippet '{prim.name}' in group "
                      f"'{group.slug}' (Claude has no instruction-file primitive)",
                      file=sys.stderr)
            else:
                print(f"emit_claude: skipping unsupported kind '{kind}' "
                      f"('{prim.name}' in '{group.slug}')", file=sys.stderr)

        if hooks:
            hd = plugin_dir / "hooks"
            hd.mkdir(parents=True, exist_ok=True)
            # Claude expects hooks.json wrapped in a top-level "hooks" record
            # (confirmed via `claude plugin validate`, v2.1.112).
            (hd / "hooks.json").write_text(dump_json({"hooks": hooks}), encoding="utf-8")
        if mcp_servers:
            (plugin_dir / ".mcp.json").write_text(
                dump_json({"mcpServers": mcp_servers}), encoding="utf-8")
        copy_group_scripts(group, plugin_dir)

        entry = {
            "name": group.slug,
            "description": group.description,
            "version": PLUGIN_VERSION,
            "source": f"./plugins/{group.slug}",
        }
        if group.requires:
            entry["dependencies"] = sorted(group.requires)
        if group.capabilities:
            entry["capabilities"] = list(group.capabilities)
        if group.enhances:
            entry["enhances"] = enhances_to_json(group.enhances)
        return entry

    # ── component kinds ────────────────────────────────────────────────────
    def _copy_component(self, prim: Primitive, dest_dir: Path) -> None:
        dest_dir.mkdir(parents=True, exist_ok=True)
        if prim.root.is_dir():
            shutil.copytree(prim.root, dest_dir / prim.root.name, dirs_exist_ok=True,
                            ignore=bundle_ignore())
        else:
            shutil.copy2(prim.root, dest_dir / prim.root.name)

    # ── hooks ──────────────────────────────────────────────────────────────
    def _emit_hook(self, prim: Primitive, plugin_dir: Path, hooks: dict) -> None:
        # bundle the hook dir (scripts) under hooks/<name>/
        bundled = plugin_dir / "hooks" / prim.name
        bundled.mkdir(parents=True, exist_ok=True)
        if prim.root.is_dir():
            shutil.copytree(prim.root, bundled, dirs_exist_ok=True,
                            ignore=bundle_ignore())
        # translate its settings-fragment into Claude hook entries
        frag_path = (prim.root if prim.root.is_dir() else prim.root.parent) / "settings-fragment-bash.json"
        if not frag_path.exists():
            print(f"emit_claude: hook '{prim.name}' has no settings-fragment-bash.json "
                  f"— bundled scripts only, no event registration", file=sys.stderr)
            return
        frag = json.loads(frag_path.read_text(encoding="utf-8"))
        for event, entries in (frag.get("hooks") or {}).items():
            for entry in entries:
                for h in entry.get("hooks", []):
                    if "command" in h:
                        h["command"] = _rewrite_hook_command(h["command"], prim.name)
                hooks.setdefault(event, []).append(entry)

    # ── mcp ────────────────────────────────────────────────────────────────
    def _merge_mcp(self, prim: Primitive, mcp_servers: dict) -> None:
        root = prim.root if prim.root.is_dir() else prim.root.parent
        cfg_path = next((root / n for n in ("mcp.json", ".mcp.json") if (root / n).exists()), None)
        if cfg_path is None:
            print(f"emit_claude: mcp-server '{prim.name}' has no mcp.json — skipped",
                  file=sys.stderr)
            return
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        mcp_servers.update(cfg.get("mcpServers", cfg))

    def _marketplace(self, entries: list[dict]) -> dict:
        return {
            "name": "crickets",
            "owner": {"name": "alexherrero"},
            "metadata": {
                "description": "Opinionated developer-workflow plugins for Claude Code "
                               "and Antigravity, generated from a single source of truth.",
            },
            "plugins": sorted(entries, key=lambda e: e["name"]),
        }

    def write_marketplace(self, entries: list[dict], dist_root: Path) -> None:
        cp = dist_root / ".claude-plugin"
        cp.mkdir(parents=True, exist_ok=True)
        (cp / "marketplace.json").write_text(dump_json(self._marketplace(entries)), encoding="utf-8")

    def write_root_marketplace(self, entries: list[dict], repo_root: Path) -> None:
        # Same manifest, but each plugin source points at its committed dist/
        # location relative to the repo root (Claude source is a path string).
        rooted = [{**e, "source": f"./dist/{self.host}/plugins/{e['name']}"} for e in entries]
        dest = repo_root / self.root_marketplace_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(dump_json(self._marketplace(rooted)), encoding="utf-8")
