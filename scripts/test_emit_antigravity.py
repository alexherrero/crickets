#!/usr/bin/env python3
"""Tests for scripts/emit_antigravity.py (crickets v3.0 #40, part 3)."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _HERE / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


try:
    import yaml  # noqa: F401
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

if HAVE_YAML:
    generate = _load("generate")
    emit_antigravity = _load("emit_antigravity")


@unittest.skipUnless(HAVE_YAML, "PyYAML required")
class TestAntigravityEmitter(unittest.TestCase):
    def setUp(self):
        self._saved = dict(generate.EMITTERS)
        generate.EMITTERS.clear()
        generate.register(emit_antigravity.AntigravityEmitter())
        self.tmp = tempfile.TemporaryDirectory()
        self.dist = Path(self.tmp.name) / "dist"
        generate.build(src=_ROOT / "src", dist=self.dist)
        self.agdist = self.dist / "antigravity"

    def tearDown(self):
        generate.EMITTERS.clear()
        generate.EMITTERS.update(self._saved)
        self.tmp.cleanup()

    def _plugin_json(self, slug):
        # Antigravity expects plugin.json at the plugin root (not .claude-plugin/).
        return json.loads((self.agdist / "plugins" / slug / "plugin.json").read_text(encoding="utf-8"))

    def test_plugin_json_no_native_dependencies(self):
        # AG composition is thin — plugin.json never carries dependencies.
        for slug in ("developer-workflows", "pii", "github-ci", "wiki-maintenance"):
            d = self._plugin_json(slug)
            self.assertEqual(d["name"], slug)
            self.assertNotIn("dependencies", d)
            self.assertIn("author", d)

    def test_components_copied_for_ag_supporting_only(self):
        d = self.agdist / "plugins"
        self.assertTrue((d / "pii" / "skills" / "pii-scrubber" / "SKILL.md").exists())
        self.assertTrue((d / "github-ci" / "skills" / "dependabot-fixer" / "SKILL.md").exists())
        self.assertTrue((d / "developer-workflows" / "agents" / "evaluator.md").exists())
        self.assertTrue((d / "wiki-maintenance" / "agents" / "diataxis-evaluator.md").exists())
        # part 2 fold-in: documenter + diataxis-author support AG → present;
        # wiki-author + recent-wiki-changes are claude-only → absent from AG.
        # part 3 task 2: style-scope-evaluator supports AG (clones the evaluator mold) → present.
        self.assertTrue((d / "wiki-maintenance" / "agents" / "style-scope-evaluator.md").exists())
        self.assertTrue((d / "wiki-maintenance" / "agents" / "documenter.md").exists())
        self.assertTrue((d / "wiki-maintenance" / "skills" / "diataxis-author" / "SKILL.md").exists())
        self.assertFalse((d / "wiki-maintenance" / "skills" / "wiki-author").exists())
        self.assertFalse((d / "wiki-maintenance" / "commands" / "recent-wiki-changes.md").exists())
        # part 4 task 4 (DC-W4: Claude-first scheduling): the wiki-watch SKILL is
        # cross-host → present on AG; the wiki-watch COMMAND is claude-only → absent.
        # The engine group scripts are bundled host-agnostically → present.
        self.assertTrue((d / "wiki-maintenance" / "skills" / "wiki-watch" / "SKILL.md").exists())
        self.assertFalse((d / "wiki-maintenance" / "commands" / "wiki-watch.md").exists())
        self.assertTrue((d / "wiki-maintenance" / "scripts" / "wiki_watch_cycle.py").exists())

    def test_thin_composition_no_inlined_base(self):
        # github-ci requires developer-workflows but carries ONLY its own
        # primitive — no required-plugin components inlined.
        gci = self.agdist / "plugins" / "github-ci"
        self.assertFalse((gci / "agents" / "evaluator.md").exists())
        self.assertEqual([p.name for p in (gci / "skills").iterdir()], ["dependabot-fixer"])

    def test_marketplace_ag_shape(self):
        mk = json.loads((self.agdist / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(mk["interface"]["displayName"], "Crickets")
        by = {p["name"]: p for p in mk["plugins"]}
        self.assertEqual(set(by),
                         {"code-review", "developer-safety",
                          "developer-workflows", "pii", "github-ci",
                          "github-projects", "obsidian-vault", "token-audit", "wiki-maintenance"})
        # wiki-maintenance re-categorized Coding → documentation in part 1; rest stay Coding
        expected_category = {"wiki-maintenance": "documentation"}
        for p in mk["plugins"]:
            self.assertEqual(p["source"], {"source": "local", "path": f"./plugins/{p['name']}"})
            self.assertEqual(p["policy"]["installation"], "AVAILABLE")
            self.assertEqual(p["category"], expected_category.get(p["name"], "Coding"))
        # requires documented (thin) on dependents, absent on standalone
        self.assertEqual(by["github-ci"]["requires"], ["developer-workflows"])
        self.assertNotIn("requires", by["wiki-maintenance"])
        self.assertNotIn("requires", by["pii"])
        self.assertNotIn("requires", by["developer-workflows"])

    def test_ag_hooks_named_with_relative_paths(self):
        # the control hooks live in developer-safety post-seed-retirement
        hj = json.loads((self.agdist / "plugins" / "developer-safety" / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(set(hj), {"commit-on-stop", "kill-switch", "steer"})
        self.assertTrue(hj["commit-on-stop"]["enabled"])
        self.assertIn("Stop", hj["commit-on-stop"])
        self.assertIn("PreToolUse", hj["kill-switch"])
        self.assertIn("PreToolUse", hj["steer"])
        cmds = []
        for h in hj.values():
            for ev, entries in h.items():
                if ev == "enabled":
                    continue
                for e in entries:
                    cmds += [x["command"] for x in e.get("hooks", [])]
        self.assertTrue(all(c.startswith("bash ./hooks/") for c in cmds), cmds)
        self.assertFalse(any("CLAUDE_PLUGIN_ROOT" in c or ".claude/hooks" in c for c in cmds))
        self.assertTrue((self.agdist / "plugins" / "developer-safety" / "hooks" / "kill-switch" / "kill-switch.sh").exists())

    def test_synthetic_sessionstart_gap_snippet_mcp(self):
        Primitive = emit_antigravity.Primitive
        Group = emit_antigravity.Group
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            hook_dir = base / "boot"
            hook_dir.mkdir()
            (hook_dir / "boot.sh").write_text("#!/bin/bash\n", encoding="utf-8")
            (hook_dir / "settings-fragment-bash.json").write_text(json.dumps({
                "hooks": {
                    "SessionStart": [{"matcher": ".*", "hooks": [{"type": "command", "command": "bash .claude/hooks/boot.sh"}]}],
                    "PreToolUse": [{"matcher": ".*", "hooks": [{"type": "command", "command": "bash .claude/hooks/boot.sh"}]}],
                }
            }), encoding="utf-8")
            sn = base / "note.md"
            sn.write_text("---\nname: note\nkind: snippet\nsupported_hosts: [antigravity]\n---\nbe terse\n", encoding="utf-8")
            mcp_dir = base / "srv"
            mcp_dir.mkdir()
            (mcp_dir / "mcp.json").write_text('{"mcpServers": {"srv": {"command": "x"}}}', encoding="utf-8")
            prims = [
                Primitive("boot", "hook", ["antigravity"], hook_dir / "hook.md", hook_dir, {}),
                Primitive("note", "snippet", ["antigravity"], sn, sn, {}),
                Primitive("srv", "mcp-server", ["antigravity"], mcp_dir / "mcp.json", mcp_dir, {}),
            ]
            group = Group("extras", "Extras", "d", "Coding", [], True, prims)
            dist = base / "dist"
            emit_antigravity.AntigravityEmitter().emit_group(group, dist)
            pd = dist / "plugins" / "extras"
            hj = json.loads((pd / "hooks.json").read_text(encoding="utf-8"))
            # SessionStart has no AG equivalent → skipped; PreToolUse kept
            self.assertIn("PreToolUse", hj["boot"])
            self.assertNotIn("SessionStart", hj["boot"])
            # snippet → rules/ (AG ships instruction files)
            self.assertTrue((pd / "rules" / "note.md").exists())
            # mcp → mcp_config.json
            mcp = json.loads((pd / "mcp_config.json").read_text(encoding="utf-8"))
            self.assertIn("srv", mcp["mcpServers"])

    def test_deterministic_rebuild(self):
        tmp2 = tempfile.TemporaryDirectory()
        try:
            dist2 = Path(tmp2.name) / "dist"
            generate.build(src=_ROOT / "src", dist=dist2)
            f1 = sorted(p.relative_to(self.dist) for p in self.dist.rglob("*") if p.is_file())
            f2 = sorted(p.relative_to(dist2) for p in dist2.rglob("*") if p.is_file())
            self.assertEqual(f1, f2)
            for rel in f1:
                self.assertEqual((self.dist / rel).read_bytes(), (dist2 / rel).read_bytes(), rel)
        finally:
            tmp2.cleanup()

    def test_enhances_capabilities_in_entry_not_plugin_json(self):
        src_model = sys.modules["src_model"]
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "cr").mkdir(parents=True)
            (src / "cr" / "group.yaml").write_text(
                "name: CR\ndescription: d\nstandalone: true\nrequires: []\n"
                "capabilities: [x]\nenhances: [wf]\n", encoding="utf-8")
            group = src_model.load_groups(src)[0]
            dist = Path(t) / "dist"
            entry = emit_antigravity.AntigravityEmitter().emit_group(group, dist)
            # the marketplace entry carries both (like `requires` on AG)
            self.assertEqual(entry["capabilities"], ["x"])
            self.assertEqual(entry["enhances"], [{"group": "wf"}])
            # AG plugin.json stays THIN — no enhances/capabilities leak
            pj = json.loads((dist / "plugins" / "cr" / "plugin.json").read_text(encoding="utf-8"))
            self.assertNotIn("enhances", pj)
            self.assertNotIn("capabilities", pj)

    def test_command_emitted(self):
        # a discovered `command` primitive lands in the native commands/ subdir
        # on Antigravity too; host-filtered (claude-only commands are skipped).
        src_model = sys.modules["src_model"]
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "wf" / "commands").mkdir(parents=True)
            (src / "wf" / "group.yaml").write_text(
                "name: WF\ndescription: d\nstandalone: true\nrequires: []\n", encoding="utf-8")
            (src / "wf" / "commands" / "plan.md").write_text(
                "---\nname: plan\nkind: command\nsupported_hosts: [antigravity]\n"
                "description: d\n---\n# plan\n", encoding="utf-8")
            # a claude-only command must NOT reach the Antigravity plugin
            (src / "wf" / "commands" / "ccionly.md").write_text(
                "---\nname: ccionly\nkind: command\nsupported_hosts: [claude-code]\n"
                "description: d\n---\n# ccionly\n", encoding="utf-8")
            group = src_model.load_groups(src)[0]
            dist = Path(t) / "dist"
            emit_antigravity.AntigravityEmitter().emit_group(group, dist)
            cmds = dist / "plugins" / "wf" / "commands"
            self.assertTrue((cmds / "plan.md").exists())
            self.assertFalse((cmds / "ccionly.md").exists())

    def test_snippet_discovered_to_rules(self):
        # a discovered `snippet` primitive lands in rules/ on Antigravity (AG ships
        # instruction files, unlike Claude which drops them).
        src_model = sys.modules["src_model"]
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "sf" / "snippets").mkdir(parents=True)
            (src / "sf" / "group.yaml").write_text(
                "name: SF\ndescription: d\nstandalone: true\nrequires: []\n", encoding="utf-8")
            (src / "sf" / "snippets" / "no-coauthor.md").write_text(
                "---\nname: no-coauthor\nkind: snippet\nsupported_hosts: [antigravity]\n"
                "description: d\n---\nbody\n", encoding="utf-8")
            group = src_model.load_groups(src)[0]
            dist = Path(t) / "dist"
            emit_antigravity.AntigravityEmitter().emit_group(group, dist)
            self.assertTrue((dist / "plugins" / "sf" / "rules" / "no-coauthor.md").exists())

    def test_group_scripts_bundled(self):
        # a group-level scripts/ asset dir is copied verbatim into the AG plugin
        # (e.g. code-review's cross-review.sh) — not a discovered primitive.
        src_model = sys.modules["src_model"]
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "cr" / "scripts").mkdir(parents=True)
            (src / "cr" / "group.yaml").write_text(
                "name: CR\ndescription: d\nstandalone: true\nrequires: []\n", encoding="utf-8")
            (src / "cr" / "scripts" / "cross-review.sh").write_text(
                "#!/usr/bin/env bash\necho hi\n", encoding="utf-8")
            group = src_model.load_groups(src)[0]
            dist = Path(t) / "dist"
            emit_antigravity.AntigravityEmitter().emit_group(group, dist)
            f = dist / "plugins" / "cr" / "scripts" / "cross-review.sh"
            self.assertTrue(f.exists())
            self.assertIn("echo hi", f.read_text(encoding="utf-8"))

    def test_skill_root_copytree_excludes_pycache(self):
        # the COMPONENT (skill / agent) root copytree must ALSO exclude
        # __pycache__/*.pyc on the Antigravity emitter — mirror of the Claude
        # regression. Surfaced by the diataxis-author style_resolver/author
        # tests compiling bundled skill .py into __pycache__ before
        # generate.py check (wiki-maintenance part 3 task 1).
        src_model = sys.modules["src_model"]
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            sk = src / "sk" / "skills" / "foo" / "scripts"
            (sk / "__pycache__").mkdir(parents=True)
            (src / "sk" / "group.yaml").write_text(
                "name: SK\ndescription: d\nstandalone: true\nrequires: []\n", encoding="utf-8")
            (src / "sk" / "skills" / "foo" / "SKILL.md").write_text(
                "---\nname: foo\nkind: skill\nsupported_hosts: [antigravity]\n"
                "description: d\n---\n# foo\n", encoding="utf-8")
            (sk / "helper.py").write_text("x = 1\n", encoding="utf-8")
            (sk / "__pycache__" / "helper.cpython-311.pyc").write_text(
                "bytecode", encoding="utf-8")
            group = src_model.load_groups(src)[0]
            dist = Path(t) / "dist"
            emit_antigravity.AntigravityEmitter().emit_group(group, dist)
            sd = dist / "plugins" / "sk" / "skills" / "foo" / "scripts"
            self.assertTrue((sd / "helper.py").exists())
            self.assertFalse((sd / "__pycache__").exists())


if __name__ == "__main__":
    unittest.main()
