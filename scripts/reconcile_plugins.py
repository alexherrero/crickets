#!/usr/bin/env python3
"""reconcile_plugins.py — diff installed crickets plugins against the marketplace.

After an upgrade that renames or drops a plugin group, the old install lingers
as a silent `✘ failed to load` and nothing says what to do. This prints what's
out of sync + the exact `claude plugin {install,uninstall}` commands to fix it.

  python3 scripts/reconcile_plugins.py

Operator-run — NOT a CI gate (it needs the `claude` CLI for the installed
side). The pure diff (`compute_actions`) + the marketplace read are unit-tested;
the host shell-out graceful-skips when `claude` is absent.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MARKETPLACE = REPO / ".claude-plugin" / "marketplace.json"
PLUGINS_ROOT = REPO / "dist" / "claude-code" / "plugins"
MARKET = "crickets"
CLAUDE_HOME = Path.home() / ".claude"


def offered_plugins(marketplace_path: Path = MARKETPLACE) -> set:
    """The plugin names the marketplace currently offers."""
    data = json.loads(marketplace_path.read_text(encoding="utf-8"))
    return {p["name"] for p in data.get("plugins", [])}


def installed_plugins():
    """The crickets plugins `claude` reports installed — or None if the CLI is
    absent / unreadable (graceful-skip on every non-Claude host or in CI)."""
    if shutil.which("claude") is None:
        return None
    try:
        out = subprocess.run(
            ["claude", "plugin", "list", "--json"],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if out.returncode != 0:
        return None
    try:
        entries = json.loads(out.stdout)
    except json.JSONDecodeError:
        return None
    suffix = f"@{MARKET}"
    return {e["id"][: -len(suffix)] for e in entries
            if isinstance(e, dict) and e.get("id", "").endswith(suffix)}


def compute_actions(offered: set, installed: set) -> dict:
    """Pure diff: what to uninstall (installed but no longer offered — a rename
    or removal) and what to install (offered but not present)."""
    return {
        "stale": sorted(installed - offered),
        "missing": sorted(offered - installed),
        "ok": sorted(offered & installed),
    }


# --- primitive-level reconcile: retire shadowing ~/.claude standalones ---------
#
# The pre-v3 install symlinked agentm's source into ~/.claude/{skills,agents,
# commands}/<name>. After the v3 plugin migration those standalones *shadow* the
# installed plugins. This retires them — but only the ones an installed crickets
# plugin provably supersedes, matched by (kind, name) AND plugin provenance.
# A standalone no installed plugin provides (design, memory, doctor, …) is never
# touched.

# Primitive kind -> the ~/.claude (and dist plugin) subdirectory that holds it.
KINDS = {"skill": "skills", "agent": "agents", "command": "commands"}

# Standalones a plugin nominally provides but which are known to DIVERGE from the
# plugin's copy — always kept + reported, never auto-removed. (Operator flag,
# 2026-06-10: ~/.claude/agents/documenter.md differs from wiki-maintenance's.)
KNOWN_DIVERGENT = {("agent", "documenter")}


def compute_primitive_actions(offered_primitives: set, installed_standalones: set,
                              protected: set = KNOWN_DIVERGENT) -> dict:
    """Pure diff over (kind, name) primitives. A standalone is `superseded` iff an
    installed crickets plugin provides the same (kind, name) AND it is not
    `protected` (known-divergent); everything else is `kept`. A standalone no
    plugin provides is always kept — the false-remove guard is structural: only
    members of `offered_primitives` can ever be superseded."""
    superseded, kept = [], []
    for prim in installed_standalones:
        if prim in offered_primitives and prim not in protected:
            superseded.append(prim)
        else:
            kept.append(prim)
    return {"superseded": sorted(superseded), "kept": sorted(kept)}


def plugin_primitives(plugin_dir: Path) -> set:
    """The (kind, name) primitives a single plugin directory provides: skills
    (subdirs of skills/), agents (agents/*.md), commands (commands/*.md). Hooks
    and bundled scripts are not ~/.claude standalones, so they're not included."""
    found = set()
    skills = plugin_dir / "skills"
    if skills.is_dir():
        found |= {("skill", d.name) for d in skills.iterdir() if d.is_dir()}
    for kind in ("agent", "command"):
        sub = plugin_dir / KINDS[kind]
        if sub.is_dir():
            found |= {(kind, f.stem) for f in sub.glob("*.md")}
    return found


def offered_primitive_map(plugins_root: Path = PLUGINS_ROOT, installed=None) -> dict:
    """Map (kind, name) -> the installed crickets plugin group that provides it.

    Only an INSTALLED plugin's primitives can supersede a standalone, so if
    `installed` is None (host CLI unavailable — can't confirm what's installed)
    this returns {}: nothing is eligible for removal, the safe default. Pass the
    set of installed group names to enumerate their primitives."""
    if installed is None or not plugins_root.is_dir():
        return {}
    out = {}
    for group_dir in sorted(plugins_root.iterdir()):
        if not group_dir.is_dir() or group_dir.name not in installed:
            continue
        for prim in plugin_primitives(group_dir):
            out.setdefault(prim, group_dir.name)
    return out


def main() -> int:
    offered = offered_plugins()
    installed = installed_plugins()
    if installed is None:
        print("reconcile: `claude` CLI unavailable — can't read installed plugins.")
        print(f"  the {MARKET} marketplace offers: {', '.join(sorted(offered))}")
        return 0
    a = compute_actions(offered, installed)
    if not a["stale"] and not a["missing"]:
        print(f"reconcile: ✓ all {len(a['ok'])} {MARKET} plugins in sync.")
        return 0
    for name in a["stale"]:
        print(f"  ✘ {name}@{MARKET} is installed but no longer in the marketplace "
              f"(renamed or removed) → claude plugin uninstall {name}@{MARKET}")
    for name in a["missing"]:
        print(f"  ○ {name}@{MARKET} is available but not installed "
              f"→ claude plugin install {name}@{MARKET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
