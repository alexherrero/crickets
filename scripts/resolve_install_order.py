#!/usr/bin/env python3
"""Order a set of crickets plugins so every plugin's `requires:` installs first.

Antigravity's `agy` (1.0.2) has no cross-plugin dependency resolution — it
installs exactly what you point it at, in the order you point at it. Until it
grows native deps, the installer has to do the ordering. `bootstrap.sh` used to
lean on `dist/default-set.json` being alphabetical, which happened to put
`development-lifecycle` ahead of the five plugins that require it. That was
luck, not a guarantee: a rename, or a new plugin sorting ahead of its own
dependency, would silently break the order with no error anywhere.

So: read the declared edges and topologically sort them. Edges come from each
plugin's `group.yaml` `requires:`, transported through the generated
marketplace as `dependencies` (`emit_claude.py` writes it straight from
`group.requires`, and the generate-drift gate proves dist matches src). Reading
the generated render rather than `src/*/group.yaml` keeps this stdlib-only —
`bootstrap.sh` runs on a fresh clone that may not have PyYAML — and matches how
`suggest_enhancers.py` already sources host-agnostic composition metadata.

A `requires:` entry names a **capability**, not a directory. Those are not the
same string: `code-review` declares only `adversarial-review`, and a renamed or
merged plugin declares BOTH its old and its new capability name so existing
`requires:` keep resolving (wiki/designs/crickets-composition.md § "Renames
keep both old and new names resolving" — `maintenance` still answers to
`github-ci`). So resolution goes through a provider index, never a name match
against the plugin list.

Ties break alphabetically, so the output is deterministic. A cycle is fatal —
falling back to alphabetical would reintroduce exactly the silent mis-ordering
this script exists to remove.

    usage: resolve_install_order.py <marketplace.json> <plugin-slug>...
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


class CycleError(RuntimeError):
    """A `requires:` cycle — unorderable, and never safe to guess at."""


def _warn(msg: str) -> None:
    print(f"    WARN: resolve_install_order: {msg}", file=sys.stderr)


def build_index(marketplace: dict) -> tuple[dict[str, str], dict[str, list[str]], dict[str, str]]:
    """Three lookups over a generated marketplace: plugin-slug -> itself,
    capability -> the plugins declaring it (sorted), and the old-name -> new-name
    rename chain."""
    plugins: dict[str, str] = {}
    caps: dict[str, list[str]] = {}
    for entry in marketplace.get("plugins") or []:
        name = entry.get("name")
        if not name:
            continue
        plugins[name] = name
        for cap in entry.get("capabilities") or []:
            caps.setdefault(str(cap), []).append(name)
    return plugins, {c: sorted(p) for c, p in caps.items()}, dict(marketplace.get("renames") or {})


def resolve_target(target: str, index, wanted: set[str]) -> str | None:
    """The plugin that satisfies `target`, or None if nothing in this
    marketplace does.

    A plugin slug wins over a capability of the same name — a slug is
    unambiguous. Failing that, the capability's providers; when a capability has
    more than one, prefer a provider that is actually being installed, then the
    alphabetically first, and say so. Last, walk the marketplace rename chain
    (`status-line-meter` -> `token-audit` -> `tokens`) and retry.
    """
    plugins, caps, renames = index
    if target in plugins:
        return plugins[target]
    providers = caps.get(target)
    if providers:
        pool = [p for p in providers if p in wanted] or providers
        if len(pool) > 1:
            _warn(f"capability '{target}' has {len(pool)} providers {pool} — ordering against '{pool[0]}'")
        return pool[0]
    seen = {target}
    cur = target
    while cur in renames and renames[cur] not in seen:
        cur = renames[cur]
        seen.add(cur)
        if cur in plugins:
            return plugins[cur]
        if caps.get(cur):
            return caps[cur][0]
    return None


def install_order(marketplace: dict, wanted) -> list[str]:
    """`wanted` ordered so each plugin follows everything it requires.

    Kahn's algorithm with an alphabetically sorted ready-queue: dependency order
    where it is declared, alphabetical where it is not. Edges pointing outside
    `wanted` are dropped (a curated install set is allowed to omit an optional
    dependency's provider); edges naming nothing at all are reported and
    dropped. Raises CycleError if the declared edges cannot be linearized.
    """
    wanted_set = set(wanted)
    index = build_index(marketplace)
    entries = {e["name"]: e for e in (marketplace.get("plugins") or []) if e.get("name")}

    deps: dict[str, set[str]] = {}
    for plugin in sorted(wanted_set):
        entry = entries.get(plugin)
        if entry is None:
            _warn(f"'{plugin}' is not in the marketplace — installing it with no declared dependencies")
            deps[plugin] = set()
            continue
        edges = set()
        for target in entry.get("dependencies") or []:
            provider = resolve_target(str(target), index, wanted_set)
            if provider is None:
                _warn(f"'{plugin}' requires '{target}', which no plugin provides — ignoring that edge")
            elif provider in wanted_set:
                edges.add(provider)
        deps[plugin] = edges

    ordered: list[str] = []
    placed: set[str] = set()
    while len(ordered) < len(deps):
        ready = sorted(p for p in deps if p not in placed and deps[p] <= placed)
        if not ready:
            stuck = sorted(p for p in deps if p not in placed)
            raise CycleError(
                "requires: cycle (or unsatisfiable edge) among " + ", ".join(stuck)
            )
        ordered.extend(ready)
        placed.update(ready)
    return ordered


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: resolve_install_order.py <marketplace.json> <plugin-slug>...",
              file=sys.stderr)
        return 2
    mk_path = Path(argv[1])
    try:
        marketplace = json.loads(mk_path.read_text(encoding="utf-8"))
    except Exception as exc:  # missing or unparseable — the caller decides what to do
        print(f"resolve_install_order: cannot read {mk_path}: {exc}", file=sys.stderr)
        return 2
    try:
        for plugin in install_order(marketplace, argv[2:]):
            print(plugin)
    except CycleError as exc:
        print(f"resolve_install_order: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
