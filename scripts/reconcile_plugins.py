#!/usr/bin/env python3
"""reconcile_plugins.py — reconcile crickets plugins, and retire shadowing standalones.

Two modes:

  python3 scripts/reconcile_plugins.py                        # plugins vs marketplace
  python3 scripts/reconcile_plugins.py --standalones          # ~/.claude standalones (preview)
  python3 scripts/reconcile_plugins.py --standalones --apply  # remove superseded (confirms first)

Plugin mode (default): after an upgrade that renames or drops a plugin group, the
old install lingers as a silent `✘ failed to load` and nothing says what to do —
this prints what's out of sync + the exact `claude plugin {install,uninstall}`
commands to fix it.

Standalone mode (--standalones): the pre-v3 install left ~/.claude/{skills,agents,
commands}/<name> standalones that *shadow* the installed plugins. This retires
only the ones an INSTALLED crickets plugin provably supersedes — matched by
(kind, name) AND plugin provenance — never a standalone no plugin provides
(design / memory / doctor / …), and never a KNOWN_DIVERGENT one. Preview-first;
--apply confirms before removing; every removal is reversible (reinstall).

Operator-run — NOT a CI gate (it needs the `claude` CLI for the installed side).
The pure diffs (`compute_actions`, `compute_primitive_actions`), the primitive
enumeration, and the ~/.claude scan/classify are unit-tested; the host shell-out
graceful-skips when `claude` is absent (then nothing is eligible for removal).
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


def installed_standalones(claude_home: Path = CLAUDE_HOME) -> set:
    """The (kind, name) standalones under ~/.claude/{skills,agents,commands}/.
    Skills are subdirectories; agents/commands are *.md files."""
    found = set()
    skills = claude_home / "skills"
    if skills.is_dir():
        found |= {("skill", d.name) for d in skills.iterdir() if d.is_dir()}
    for kind in ("agent", "command"):
        sub = claude_home / KINDS[kind]
        if sub.is_dir():
            found |= {(kind, f.stem) for f in sub.glob("*.md")}
    return found


def classify_standalones(claude_home: Path = CLAUDE_HOME,
                         plugins_root: Path = PLUGINS_ROOT, installed=None) -> dict:
    """Read-only: scan the ~/.claude standalones, read the installed plugins'
    offered primitives, and return {superseded, kept, provenance}. `provenance`
    maps each superseded primitive to the plugin group that supersedes it (for
    the preview). No writes — this is the report half; removal lives in main()."""
    offered = offered_primitive_map(plugins_root, installed)
    actions = compute_primitive_actions(set(offered), installed_standalones(claude_home))
    actions["provenance"] = {prim: offered[prim] for prim in actions["superseded"]}
    return actions


def remove_standalone(claude_home: Path, prim) -> Path:
    """Remove one ~/.claude standalone — a skill directory or an agent/command
    .md file — and return the path removed. Reversible: reinstall the plugin (or
    the standalone) to restore it."""
    kind, name = prim
    target = claude_home / KINDS[kind] / (name if kind == "skill" else f"{name}.md")
    if kind == "skill":
        shutil.rmtree(target)
    else:
        target.unlink()
    return target


def apply_retirement(claude_home: Path, superseded) -> list:
    """Remove every superseded standalone; return the removed paths (sorted by the
    primitive). Pure mechanics — confirmation + printing live in the CLI."""
    return [remove_standalone(claude_home, prim) for prim in sorted(superseded)]


def _reconcile_plugins() -> int:
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


def _reconcile_standalones(apply: bool = False, assume_yes: bool = False,
                           claude_home: Path = CLAUDE_HOME,
                           plugins_root: Path = PLUGINS_ROOT, installed=None) -> int:
    if installed is None:
        installed = installed_plugins()
    if installed is None:
        print("reconcile: `claude` CLI unavailable — can't confirm installed plugins,")
        print(f"  so no standalone under {claude_home} is eligible for retirement "
              f"(safe default).")
        return 0
    rep = classify_standalones(claude_home, plugins_root, installed)
    sup, kept, prov = rep["superseded"], rep["kept"], rep["provenance"]
    divergent = sorted(KNOWN_DIVERGENT & installed_standalones(claude_home))
    if not sup:
        print(f"reconcile: ✓ no superseded standalones under {claude_home} "
              f"({len(kept)} kept).")
        return 0
    print(f"reconcile: {len(sup)} superseded standalone(s) under {claude_home}:")
    for kind, name in sup:
        print(f"  ✘ {KINDS[kind]}/{name}  — superseded by {prov[(kind, name)]}@{MARKET}")
    for kind, name in divergent:
        print(f"  ◆ {KINDS[kind]}/{name}  — kept (known-divergent, not auto-removed)")
    if not apply:
        print(f"\n  preview only — re-run with --standalones --apply to remove the "
              f"{len(sup)} superseded standalone(s). Reversible (reinstall to restore).")
        return 0
    if not assume_yes:
        resp = input(f"\nRemove {len(sup)} superseded standalone(s)? [y/N] ").strip().lower()
        if resp not in ("y", "yes"):
            print("  aborted — nothing removed.")
            return 0
    for path in apply_retirement(claude_home, sup):
        print(f"  removed {path}")
    print(f"reconcile: removed {len(sup)} standalone(s).")
    return 0


def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(
        description="Reconcile installed crickets plugins (default), or retire "
                    "shadowing ~/.claude primitive standalones (--standalones).")
    p.add_argument("--standalones", action="store_true",
                   help="reconcile ~/.claude primitive standalones instead of plugins")
    p.add_argument("--apply", action="store_true",
                   help="(with --standalones) remove superseded standalones after confirmation")
    p.add_argument("--yes", action="store_true",
                   help="(with --apply) skip the interactive confirmation")
    args = p.parse_args(argv)
    if args.standalones:
        return _reconcile_standalones(apply=args.apply, assume_yes=args.yes)
    if args.apply or args.yes:
        p.error("--apply / --yes require --standalones")
    return _reconcile_plugins()


if __name__ == "__main__":
    sys.exit(main())
