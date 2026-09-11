#!/usr/bin/env python3
"""sibling_plugin.py — find a file inside a sibling crickets plugin.

    sibling_plugin.py <plugin> <relative-path>

Prints the absolute path of <relative-path> inside the installed <plugin> and
exits 0. Exits 1 when that plugin or file is not installed, with the paths it
tried on stderr. Exits 2 on a usage error. Callers reach it through their own
plugin root: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sibling_plugin.py" ...`.

Why a resolver instead of `${CLAUDE_PLUGIN_ROOT}/../<plugin>/...`: that literal
assumes every plugin sits flat under one `plugins/` directory. The generated
`dist/<host>/plugins/` tree does, and so does Antigravity's install. Claude
Code's plugin cache does not. It installs each plugin at
`<plugins>/cache/<marketplace>/<plugin>/<version>/`, so `../<plugin>` from one
version directory names nothing. The documenter's prose pass degraded on every
dispatch that way, and `/design translate` could not load its plan resolver.

Candidates, first hit wins:
  1. flat       <this-plugin-root>/../<plugin>/<rel>, taken lexically and then
                through any symlink on the plugin root
  2. installed  the installPath Claude Code records for <plugin>@<marketplace>
                in <plugins>/installed_plugins.json, which is the live version
  3. newest     the highest <cache>/<marketplace>/<plugin>/<version>/ that
                holds <rel>, for when installed_plugins.json is unreadable

Rungs 2 and 3 run only when the plugin root has the cache's shape. Every plugin
that calls this ships a byte-identical copy, because plugin version directories
diverge and a cross-plugin import cannot work at runtime.
scripts/test_sibling_plugin.py pins the copies identical.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).absolute().parent.parent

_PLUGIN_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _version_key(name: str) -> "tuple[int, ...]":
    return tuple(int(part) for part in re.findall(r"\d+", name))


def _installed_roots(plugin: str, marketplace: str, plugins_dir: Path) -> "list[Path]":
    try:
        data = json.loads((plugins_dir / "installed_plugins.json").read_text(encoding="utf-8"))
        entries = data["plugins"][f"{plugin}@{marketplace}"]
        return [Path(e["installPath"]) for e in entries if e.get("installPath")]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return []


def candidates(plugin: str, rel: str, plugin_root: "Path | None" = None) -> "list[Path]":
    """Every path the resolver tries for <plugin>/<rel>, in order."""
    root = Path(plugin_root) if plugin_root is not None else PLUGIN_ROOT
    found: list[Path] = [root.parent / plugin / rel]
    physical = root.resolve()
    if physical != root:
        found.append(physical.parent / plugin / rel)

    # Claude Code's cache: <plugins>/cache/<marketplace>/<this-plugin>/<version>
    marketplace_dir = root.parent.parent
    if marketplace_dir.parent.name == "cache":
        plugins_dir = marketplace_dir.parent.parent
        found += [r / rel for r in _installed_roots(plugin, marketplace_dir.name, plugins_dir)]
        sibling = marketplace_dir / plugin
        if sibling.is_dir():
            versions = sorted((d for d in sibling.iterdir() if d.is_dir()),
                              key=lambda d: _version_key(d.name), reverse=True)
            found += [d / rel for d in versions]
    return list(dict.fromkeys(found))


def resolve_sibling(plugin: str, rel: str, plugin_root: "Path | None" = None) -> "Path | None":
    """The installed path of <rel> inside the sibling <plugin>, or None."""
    for path in candidates(plugin, rel, plugin_root):
        if path.is_file():
            return path.resolve()
    return None


def _usage_error(plugin: str, rel: str) -> "str | None":
    if not _PLUGIN_NAME.match(plugin):
        return f"not a plugin name: {plugin!r}"
    parts = Path(rel).parts
    if not parts or Path(rel).is_absolute() or ".." in parts:
        return f"relative path must stay inside the plugin: {rel!r}"
    return None


def main(argv: "list[str]") -> int:
    if len(argv) != 2:
        print("usage: sibling_plugin.py <plugin> <relative-path>", file=sys.stderr)
        return 2
    plugin, rel = argv
    problem = _usage_error(plugin, rel)
    if problem:
        print(f"sibling_plugin: {problem}", file=sys.stderr)
        return 2
    path = resolve_sibling(plugin, rel)
    if path is None:
        tried = ", ".join(str(c) for c in candidates(plugin, rel))
        print(f"sibling_plugin: {plugin}/{rel} is not installed; tried {tried}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
