#!/usr/bin/env python3
"""Dangling-reference gate over emitted plugin payloads (R2.1 / cricketsPluginsB#3).

Walks every emitted `dist/*/plugins/*/**/*.md` across all host dist trees
(claude-code, antigravity, ...), extracting:

  - relative markdown links `[text](path)` (http(s)/mailto/anchor-only skipped)
  - `${CLAUDE_PLUGIN_ROOT}`-relative paths referenced in prose or code spans

and asserts each resolves to a real file *inside that same emitted plugin's
own tree* — never elsewhere in dist, never the `src/` a reader might fall
back to by hand. Extends the existing spec-grep pattern
(`scripts/test_developer_workflows_specs.py`, which greps one command's
`${CLAUDE_PLUGIN_ROOT}` script references) from a single command's prose to
every emitted markdown file in every plugin.

Multiple dangling references ship today, undetected until this gate:
`cricketsPluginsB#3` — `wiki-maintenance/agents/documenter.md` links
`../documentation.md`, which has never existed in this repo. The *content*
fix lands in `PLAN-r2-docs-and-phase-loop` R2.4 Task 6 — this gate's job is
catching it, not fixing it. It is grandfathered in `_KNOWN_VIOLATIONS` below
so this gate can land (and stay wired into `check-all.sh`) without
retroactively failing the battery on a pre-existing defect a sibling plan
owns; the grandfather list must only shrink, never grow — `--strict` ignores
it entirely (used by the regression fixture + to reproduce the raw failure).

Exit 0 clean (including grandfathered violations under default mode), 1 on
any non-grandfathered dangling reference (or `--strict` finds any at all),
2 on usage error.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_PLUGIN_ROOT_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s\"'`)]+)")

# (plugin-relative markdown file, dangling target — anchor stripped) pairs
# found predating this gate (2026-07-04 first run). Two classes:
#   (a) cricketsPluginsB#3 — documenter.md's normative-source link; the
#       content fix is PLAN-r2-docs-and-phase-loop R2.4 Task 6's job.
#   (b) cricketsPluginsA#10 — hook/skill docs linking back to this repo's
#       wiki/ (or a cross-plugin doc) with a relative path that can never
#       resolve once emitted — wiki/ ships in no plugin payload at all, and
#       the hook cross-references assume a directory layout the plugins
#       don't share. Real content debt this gate now makes visible; not
#       this task's job to fix (Task 3 is "the gate that would have caught
#       it, not the content fix").
# This list must only shrink as each entry's owning plan lands its fix —
# never grow; `--strict` ignores it entirely to reproduce the raw failure.
_KNOWN_VIOLATIONS: frozenset[tuple[str, str]] = frozenset({
    ("wiki-maintenance/agents/documenter.md", "../documentation.md"),
    ("wiki-maintenance/commands/wiki-watch.md", "../../../wiki/reference/Antigravity-Limitations.md"),
    ("wiki-maintenance/commands/wiki-watch.md", "../../../wiki/reference/Wiki-Watch-Config.md"),
    ("wiki-maintenance/skills/diataxis-author/SKILL.md", "../memory/SKILL.md"),
    ("wiki-maintenance/skills/wiki-watch/SKILL.md", "../../../wiki/how-to/Run-The-Wiki-Watcher.md"),
    ("wiki-maintenance/skills/wiki-watch/SKILL.md", "../../../wiki/reference/Antigravity-Limitations.md"),
    ("wiki-maintenance/skills/wiki-watch/SKILL.md", "../../../wiki/reference/Wiki-Watch-Config.md"),
    ("code-review/hooks/evidence-tracker/hook.md", "../../wiki/how-to/Use-The-Evidence-Tracker-Hook.md"),
    ("code-review/hooks/evidence-tracker/hook.md", "../commit-on-stop/hook.md"),
    ("code-review/hooks/evidence-tracker/hook.md", "../kill-switch/hook.md"),
    ("code-review/hooks/evidence-tracker/hook.md", "../steer/hook.md"),
    ("developer-safety/hooks/commit-on-stop/hook.md", "../../wiki/how-to/Use-The-Base-Hooks.md"),
    ("developer-safety/hooks/kill-switch/hook.md", "../../wiki/how-to/Use-The-Base-Hooks.md"),
    ("developer-safety/hooks/steer/hook.md", "../../wiki/how-to/Use-The-Base-Hooks.md"),
    ("developer-workflows/commands/plan.md", "${CLAUDE_PLUGIN_ROOT}/scripts/check-plan-grounding.py"),
})


_PLACEHOLDER_MARKERS = ("<", ">", "{{", "}}", "…")  # angle-bracket / template-var / ellipsis prose examples


def _is_external_or_anchor(target: str) -> bool:
    target = target.strip()
    if not target or target.startswith("#"):
        return True
    return target.startswith(("http://", "https://", "mailto:"))


def _is_placeholder(target: str) -> bool:
    """Template scaffolding uses non-path prose in link position: `<link>`,
    `{{commit_url}}`, `…/releases/tag/vX.Y.Z`, or a bare wiki-style page slug
    with no `/` and no leading `.` (e.g. `Overview`, `Plugin-Anatomy`) — none
    of these are real same-tree filesystem references this gate should judge.
    """
    if any(marker in target for marker in _PLACEHOLDER_MARKERS):
        return True
    return "/" not in target and not target.startswith(".")


def _strip_anchor(target: str) -> str:
    return target.split("#", 1)[0]


def _iter_dist_markdown() -> list[tuple[Path, str, Path]]:
    """Yield (plugin_root, plugin_rel_name, md_file) for every emitted plugin markdown file.

    `plugin_rel_name` is e.g. `wiki-maintenance` — the plugin's own dir name,
    used as the grandfather-list key (host-independent: claude-code and
    antigravity emit byte-identical content for a shared source doc).
    """
    if not DIST.is_dir():
        return []
    out = []
    for host_dir in sorted(DIST.iterdir()):
        plugins_dir = host_dir / "plugins"
        if not plugins_dir.is_dir():
            continue
        for plugin_root in sorted(plugins_dir.iterdir()):
            if not plugin_root.is_dir():
                continue
            for md_file in sorted(plugin_root.rglob("*.md")):
                out.append((plugin_root, plugin_root.name, md_file))
    return out


def find_dangling_references(dist_root: Path | None = None) -> list[dict]:
    """Return every dangling reference found under `dist_root` (default: repo dist/).

    Each result: {"plugin": str, "file": str (plugin-relative), "target": str,
    "grandfathered": bool}.
    """
    global DIST
    scan_root = dist_root if dist_root is not None else DIST
    results = []
    if not scan_root.is_dir():
        return results
    for host_dir in sorted(scan_root.iterdir()):
        plugins_dir = host_dir / "plugins"
        if not plugins_dir.is_dir():
            continue
        for plugin_root in sorted(plugins_dir.iterdir()):
            if not plugin_root.is_dir():
                continue
            for md_file in sorted(plugin_root.rglob("*.md")):
                text = md_file.read_text(encoding="utf-8", errors="replace")
                file_rel = md_file.relative_to(plugin_root).as_posix()
                grandfather_key_file = f"{plugin_root.name}/{file_rel}"

                for m in _MD_LINK_RE.finditer(text):
                    raw_target = m.group(1).strip()
                    if _is_external_or_anchor(raw_target) or _is_placeholder(raw_target):
                        continue
                    target = _strip_anchor(raw_target)
                    if not target:
                        continue
                    resolved = (md_file.parent / target).resolve()
                    inside_plugin = resolved.is_relative_to(plugin_root.resolve())
                    if resolved.exists() and inside_plugin:
                        continue
                    results.append({
                        "plugin": plugin_root.name,
                        "file": file_rel,
                        "target": raw_target,
                        "grandfathered": (grandfather_key_file, target) in _KNOWN_VIOLATIONS,
                    })

                for m in _PLUGIN_ROOT_RE.finditer(text):
                    rel = m.group(1)
                    if _is_placeholder(rel):
                        continue
                    resolved = (plugin_root / rel).resolve()
                    # `${CLAUDE_PLUGIN_ROOT}/../other-plugin/...` is a documented,
                    # working cross-plugin pattern (e.g. developer-workflows'
                    # commands reach github-projects' project_sync.py this way) —
                    # a real install co-locates every one of a host's plugins
                    # under one `plugins/` dir, so the right scope for THIS
                    # extraction is "somewhere under this host's plugins/", not
                    # strictly this one plugin's own subtree.
                    host_plugins_root = plugin_root.parent.resolve()
                    inside_host_plugins = resolved.is_relative_to(host_plugins_root)
                    if resolved.exists() and inside_host_plugins:
                        continue
                    results.append({
                        "plugin": plugin_root.name,
                        "file": file_rel,
                        "target": "${CLAUDE_PLUGIN_ROOT}/" + rel,
                        "grandfathered": (grandfather_key_file, "${CLAUDE_PLUGIN_ROOT}/" + rel) in _KNOWN_VIOLATIONS,
                    })
    return results


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dist-root", default=None, help="scan this dist/ tree instead of the repo's own")
    p.add_argument("--strict", action="store_true", help="ignore the grandfather list — report every dangling reference")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    dist_root = Path(args.dist_root).resolve() if args.dist_root else DIST
    if not dist_root.is_dir():
        print(f"check-dist-references: no dist/ tree at {dist_root} — build first (scripts/generate.py build)",
              file=sys.stderr)
        return 2

    findings = find_dangling_references(dist_root)
    blocking = [f for f in findings if args.strict or not f["grandfathered"]]

    if not findings:
        print("check-dist-references: clean — every emitted reference resolves inside its own plugin tree")
        return 0

    for f in findings:
        tag = "GRANDFATHERED" if f["grandfathered"] and not args.strict else "DANGLING"
        print(f"check-dist-references: [{tag}] {f['plugin']}/{f['file']} -> {f['target']}", file=sys.stderr)

    if blocking:
        print(f"check-dist-references: {len(blocking)} dangling reference(s) (excluding grandfathered)", file=sys.stderr)
        return 1

    print(f"check-dist-references: {len(findings)} grandfathered violation(s), 0 new — pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
