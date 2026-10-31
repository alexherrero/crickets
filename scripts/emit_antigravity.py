#!/usr/bin/env python3
"""Antigravity host emitter (crickets v3.0 #40, part 3; reshaped for agy 1.4.x).

Emits, per group, an Antigravity plugin under `dist/antigravity/plugins/<slug>/`:
  - `plugin.json` at the plugin ROOT (AG convention; NO `dependencies` — AG
    composition is THIN, the requires is documented in the marketplace entry).
  - skills/ and agents/ copied from the source primitives. An agent loses its
    `tools:` and `model:` lines: agy wants `tools:` as a YAML list of ITS tool
    names and rejects Claude model tiers, so the agent inherits both from the
    session instead (see wiki/reference/Antigravity-Limitations.md, row 5).
  - skills/<command>/SKILL.md for every command. agy plugins have no commands/
    folder (`agy plugin validate`: "commands never loaded"); a skill is how a
    plugin gets a `/name` entry. A body over agy's 24 KB skill limit is
    emitted as a short SKILL.md that points at references/<command>.md.
  - rules/ from snippet / rule / output-style primitives, each given the
    `trigger:` agy requires (a rule without one never applies): always_on for
    snippets and output styles, model_decision for rules.
  - `hooks.json` — each hook keyed by name with `enabled` and its agy events.
    agy's SessionStart / Stop / PreInvocation are flat handler lists and its
    PreToolUse / PostToolUse are matcher groups. Every command runs through
    hooks/_agy_hook_adapter.py, which translates between Claude's hook
    contract (exit codes, plain stdout) and agy's (JSON on stdout).
  - `mcp_config.json` merged from mcp-server primitives.
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

_COMPONENT_SUBDIR = {"skill": "skills"}

# Claude hook event -> (agy event, True when agy wants matcher groups).
# agy has no UserPromptSubmit; PreInvocation (before each model call) is the
# nearest event, and the adapter lets the hook through once per user message.
_EVENT_MAP = {
    "PreToolUse": ("PreToolUse", True),
    "PostToolUse": ("PostToolUse", True),
    "SessionStart": ("SessionStart", False),
    "UserPromptSubmit": ("PreInvocation", False),
    "Stop": ("Stop", False),
}
_ADAPTER_SRC = Path(__file__).resolve().parent / "agy_hook_adapter.py"
_ADAPTER_REL = "hooks/_agy_hook_adapter.py"

# agy caps a skill body at 24 KB; stay under it with headroom.
_SKILL_BODY_LIMIT_BYTES = 23_000
# Rule trigger by source kind (agy: always_on | model_decision | glob | manual).
_RULE_TRIGGER = {"snippet": "always_on", "output-style": "always_on", "rule": "model_decision"}
# Claude tool names agy knows under another name, for hook matchers.
_AG_TOOL = {"Bash": "run_command", "Read": "view_file"}
_SCRIPT_RE = re.compile(r"(?:\S*/)?([\w.-]+\.(?:sh|ps1|py))")


def _split_frontmatter(text: str) -> tuple[str | None, str]:
    """(frontmatter text without fences, everything after the closing fence)."""
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    if end == -1:
        return None, text
    return text[4:end], text[end + 4:]


def _join_frontmatter(fm: str, rest: str) -> str:
    return "---\n" + fm + "\n---" + rest


def _drop_keys(fm: str, keys: set[str]) -> str:
    """Remove top-level `key:` lines, and any indented / list lines under them."""
    out: list[str] = []
    skipping = False
    for line in fm.split("\n"):
        m = re.match(r"([A-Za-z_][\w-]*):", line)
        if m:
            skipping = m.group(1) in keys
        elif skipping and (not line.strip() or line[0] in " \t-"):
            continue
        else:
            skipping = False
        if not skipping:
            out.append(line)
    return "\n".join(out)


def _has_key(fm: str, key: str) -> bool:
    return re.search(rf"^{re.escape(key)}:", fm, re.M) is not None


_REL_LINK_RE = re.compile(r"\]\((?!https?:|mailto:|#|/|\$\{)([^)\s#]+)((?:#[^)\s]*)?)")


def _deepen_links(body: str, levels: int, commands: frozenset[str] = frozenset()) -> str:
    """Keep a body's relative markdown links pointing at the same files.

    A command moves from commands/<name>.md to skills/<name>/SKILL.md, and a
    long body moves down again into references/; each move puts it `levels`
    folders deeper, so every relative link needs that many extra `../`. A link
    to a sibling command (`other.md`) now points at that command's skill.
    """
    def fix(m: re.Match) -> str:
        target, anchor = m.group(1), m.group(2)
        if target.endswith(".md") and "/" not in target and target[:-3] in commands:
            target = f"{target[:-3]}/SKILL.md"
            return "](" + "../" * levels + target + anchor
        return "](" + "../" * levels + target + anchor
    return _REL_LINK_RE.sub(fix, body)


def _ag_matcher(matcher: str | None) -> str:
    if matcher in (None, "", ".*", "*"):
        return "*"
    return "|".join(_AG_TOOL.get(t, t) for t in matcher.split("|"))


def _rewrite_relative(command: str, name: str) -> str:
    """AG hook commands use a RELATIVE script path (no ${CLAUDE_PLUGIN_ROOT})."""
    return _SCRIPT_RE.sub(lambda m: f"./hooks/{name}/{m.group(1)}", command, count=1)


def _long_body_stub(what: str, ref_rel: str, arguments: str = "") -> str:
    """SKILL.md body for instructions too long for agy to load whole."""
    return (f"The full instructions for {what} are too long to load here, so they sit in "
            f"`{ref_rel}` next to this file.\n\n"
            f"Before doing anything else, read that whole file with `view_file` and follow it "
            f"exactly.{arguments}\n")


class AntigravityEmitter(HostEmitter):
    host = HOST
    root_marketplace_rel = ".agents/plugins/marketplace.json"

    def emit_group(self, group: Group, dist_root: Path) -> dict | None:
        plugin_dir = dist_root / "plugins" / group.slug
        # Rebuild from nothing: a folder the emitter no longer writes (the old
        # commands/ dirs) must not linger in the committed dist.
        shutil.rmtree(plugin_dir, ignore_errors=True)

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
        skill_names = {p.name for p in group.primitives
                       if p.kind == "skill" and p.supports(HOST)}
        command_names = frozenset(p.name for p in group.primitives
                                  if p.kind == "command" and p.supports(HOST))

        for prim in group.primitives:
            if not prim.supports(HOST):
                continue
            kind = prim.kind
            if kind in _COMPONENT_SUBDIR:
                self._copy_component(prim, plugin_dir / _COMPONENT_SUBDIR[kind])
            elif kind == "agent":
                self._emit_agent(prim, plugin_dir / "agents")
            elif kind == "command":
                self._emit_command_as_skill(prim, plugin_dir / "skills", skill_names, command_names)
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
                self._emit_rule(prim, plugin_dir / "rules")
            elif kind == "mcp-server":
                self._merge_mcp(prim, mcp_servers)
            else:
                print(f"emit_antigravity: skipping unsupported kind '{kind}' "
                      f"('{prim.name}' in '{group.slug}')", file=sys.stderr)

        if ag_hooks:
            write_utf8(plugin_dir / "hooks.json", dump_json(ag_hooks))
            write_utf8(plugin_dir / _ADAPTER_REL, _ADAPTER_SRC.read_text(encoding="utf-8"))
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
            copied_root = dest_dir / prim.root.name
            shutil.copytree(prim.root, copied_root, dirs_exist_ok=True,
                            ignore=bundle_ignore())
            # A directory-rooted primitive (skill) still needs its manifest
            # re-rendered when it declares `opinions:` -- see emit_claude.py's
            # own comment on this same fix (PLAN-wave-d-tokens-and-privacy
            # task 4's privacy-review retrofit found this gap in both emitters).
            if prim.frontmatter.get("opinions"):
                manifest_rel = prim.manifest.relative_to(prim.root)
                write_utf8(copied_root / manifest_rel, render_primitive_text(prim))
            if prim.kind == "skill":
                self._split_long_skill(copied_root)
        else:
            # render_primitive_text is a no-op (raw text) for a primitive with
            # no `opinions:` frontmatter key — every other single-file primitive
            # emits byte-identical to the plain copy2 this replaces.
            write_utf8(dest_dir / prim.root.name, render_primitive_text(prim))

    @staticmethod
    def _split_long_skill(skill_dir: Path) -> None:
        """agy loads only the first 24 KB of a SKILL.md; keep the rest reachable.

        An over-long skill keeps its frontmatter, moves its whole body to
        references/SKILL.full.md, and gets a short body telling the agent to
        read that file first.
        """
        manifest = skill_dir / "SKILL.md"
        if not manifest.is_file():
            return
        fm, rest = _split_frontmatter(manifest.read_text(encoding="utf-8"))
        if fm is None or len(rest.encode("utf-8")) <= _SKILL_BODY_LIMIT_BYTES:
            return
        ref = skill_dir / "references"
        ref.mkdir(exist_ok=True)
        write_utf8(ref / "SKILL.full.md", _deepen_links(rest.lstrip("\n"), 1))
        write_utf8(manifest, _join_frontmatter(
            fm, "\n\n" + _long_body_stub(f"the `{skill_dir.name}` skill", "references/SKILL.full.md")))

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
            if event not in _EVENT_MAP:
                print(f"emit_antigravity: hook '{prim.name}' event '{event}' has no "
                      f"Antigravity equivalent — skipped", file=sys.stderr)
                continue
            ag_event, grouped = _EVENT_MAP[event]
            handlers_by_matcher: list[tuple[str | None, list[dict]]] = []
            for entry in entries:
                handlers = []
                for h in entry.get("hooks", []):
                    if "command" not in h:
                        continue
                    command = _rewrite_relative(h["command"], prim.name)
                    handler = {"type": "command",
                               "command": f"python3 ./{_ADAPTER_REL} {event} {command}"}
                    if "timeout" in h:
                        handler["timeout"] = h["timeout"]
                    handlers.append(handler)
                if handlers:
                    handlers_by_matcher.append((entry.get("matcher"), handlers))
            if not handlers_by_matcher:
                continue
            if grouped:
                events[ag_event] = [{"matcher": _ag_matcher(m), "hooks": hs}
                                    for m, hs in handlers_by_matcher]
            else:
                events[ag_event] = [h for _, hs in handlers_by_matcher for h in hs]
        if events:
            ag_hooks[prim.name] = {"enabled": True, **events}

    def _emit_agent(self, prim: Primitive, agents_dir: Path) -> None:
        """Copy an agent, minus the `tools:` / `model:` lines agy cannot read.

        agy wants `tools:` as a YAML list of its own tool names and rejects a
        Claude model tier, and either error makes it skip the whole agent. The
        agent inherits the session's tools and model instead.
        """
        if prim.root.is_dir():
            self._copy_component(prim, agents_dir)
            return
        agents_dir.mkdir(parents=True, exist_ok=True)
        text = render_primitive_text(prim)
        fm, rest = _split_frontmatter(text)
        if fm is not None:
            text = _join_frontmatter(_drop_keys(fm, {"tools", "model"}), rest)
        write_utf8(agents_dir / prim.root.name, text)

    def _emit_rule(self, prim: Primitive, rules_dir: Path) -> None:
        """Copy a rule / snippet / output-style, adding the `trigger:` agy needs."""
        if prim.root.is_dir():
            self._copy_component(prim, rules_dir)
            return
        rules_dir.mkdir(parents=True, exist_ok=True)
        text = render_primitive_text(prim)
        fm, rest = _split_frontmatter(text)
        if fm is not None and not _has_key(fm, "trigger"):
            trigger = _RULE_TRIGGER.get(prim.kind, "always_on")
            if trigger == "model_decision" and not prim.frontmatter.get("description"):
                trigger = "always_on"  # a model_decision rule must carry a description
            text = _join_frontmatter(fm + f"\ntrigger: {trigger}", rest)
        write_utf8(rules_dir / prim.root.name, text)

    def _emit_command_as_skill(self, prim: Primitive, skills_dir: Path,
                               taken: set[str], commands: frozenset[str]) -> None:
        """A command becomes skills/<name>/SKILL.md — agy plugins load no commands/.

        `$ARGUMENTS` is a Claude substitution agy does not do, so it is replaced
        by words saying where the arguments are (the text after the command
        name). A body over agy's 24 KB skill limit stays whole in
        references/<name>.md, behind a short SKILL.md that says to read it.
        """
        name = prim.name
        if name in taken:
            print(f"emit_antigravity: command '{name}' skipped — a skill of the same "
                  f"name already ships in this plugin", file=sys.stderr)
            return
        taken.add(name)
        fm, rest = _split_frontmatter(render_primitive_text(prim))
        body = _deepen_links(rest.lstrip("\n"), 1, commands)
        body = body.replace("$ARGUMENTS", f"<what the user typed after /{name}>")
        hint = prim.frontmatter.get("argument-hint")
        if hint:
            body = f"**Usage:** `/{name} {hint}`\n\n{body}"
        description = str(prim.frontmatter.get("description", "")).strip() or name
        sk = skills_dir / name
        sk.mkdir(parents=True, exist_ok=True)
        if len(body.encode("utf-8")) > _SKILL_BODY_LIMIT_BYTES:
            ref = sk / "references"
            ref.mkdir(exist_ok=True)
            write_utf8(ref / f"{name}.md", _deepen_links(body, 1))
            body = _long_body_stub(
                f"`/{name}`", f"references/{name}.md",
                f" Wherever it mentions the arguments, they are the text the user typed "
                f"after `/{name}`.")
        write_utf8(sk / "SKILL.md",
                   f"---\nname: {name}\ndescription: {json.dumps(description, ensure_ascii=False)}\n---\n\n{body}")

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

    def write_marketplace(self, entries: list[dict], dist_root: Path,
                           renames: dict[str, str] | None = None) -> None:
        # `renames` accepted (interface parity with the base HostEmitter) but
        # deliberately NOT emitted — Antigravity's marketplace.json has no
        # documented rename/deprecation field (checked live against
        # antigravity.google/docs/cli/plugins, which covers only plugin.json's
        # shape, nothing marketplace-level). A named skip, not a silent one:
        # an install that predates a group rename still shows a bare
        # not-found here, mitigated by the existing host-agnostic fallback
        # (scripts/reconcile_plugins.py). Re-audit when Antigravity documents
        # an equivalent field.
        mp = dist_root / ".agents" / "plugins"
        mp.mkdir(parents=True, exist_ok=True)
        write_utf8(mp / "marketplace.json", dump_json(self._marketplace(entries)))

    def write_root_marketplace(self, entries: list[dict], repo_root: Path,
                                renames: dict[str, str] | None = None) -> None:
        # `renames` unused — see write_marketplace's comment above.
        # Same manifest, but each plugin source points at its committed dist/
        # location relative to the repo root (AG source is a {source,path} object).
        rooted = [
            {**e, "source": {"source": "local", "path": f"./dist/{self.host}/plugins/{e['name']}"}}
            for e in entries
        ]
        dest = repo_root / self.root_marketplace_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        write_utf8(dest, dump_json(self._marketplace(rooted)))
