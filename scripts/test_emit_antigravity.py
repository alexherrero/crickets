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
        for slug in ("development-lifecycle", "privacy", "maintenance", "wiki"):
            d = self._plugin_json(slug)
            self.assertEqual(d["name"], slug)
            self.assertNotIn("dependencies", d)
            self.assertIn("author", d)

    def test_components_copied_for_ag_supporting_only(self):
        d = self.agdist / "plugins"
        self.assertTrue((d / "privacy" / "skills" / "pii-scrubber" / "SKILL.md").exists())
        self.assertTrue((d / "maintenance" / "skills" / "dependabot-fixer" / "SKILL.md").exists())
        self.assertTrue((d / "development-lifecycle" / "agents" / "evaluator.md").exists())
        self.assertTrue((d / "wiki" / "agents" / "diataxis-evaluator.md").exists())
        # part 2 fold-in: documenter + diataxis-author support AG → present;
        # wiki-author + recent-wiki-changes are claude-only → absent from AG.
        # part 3 task 2: style-scope-evaluator supports AG (clones the evaluator mold) → present.
        self.assertTrue((d / "wiki" / "agents" / "style-scope-evaluator.md").exists())
        self.assertTrue((d / "wiki" / "agents" / "documenter.md").exists())
        self.assertTrue((d / "wiki" / "skills" / "diataxis-author" / "SKILL.md").exists())
        self.assertFalse((d / "wiki" / "skills" / "wiki-author").exists())
        self.assertFalse((d / "wiki" / "commands" / "recent-wiki-changes.md").exists())
        # part 4 task 4 (DC-W4: Claude-first scheduling): the wiki-watch SKILL is
        # cross-host → present on AG; the wiki-watch COMMAND is claude-only → absent.
        # The engine group scripts are bundled host-agnostically → present.
        self.assertTrue((d / "wiki" / "skills" / "wiki-watch" / "SKILL.md").exists())
        self.assertFalse((d / "wiki" / "commands" / "wiki-watch.md").exists())
        self.assertTrue((d / "wiki" / "scripts" / "wiki_watch_cycle.py").exists())

    def test_thin_composition_no_inlined_base(self):
        # maintenance (ex-github-ci) requires development-lifecycle but carries
        # ONLY its own primitive — no required-plugin components inlined.
        gci = self.agdist / "plugins" / "maintenance"
        self.assertFalse((gci / "agents" / "evaluator.md").exists())
        self.assertEqual([p.name for p in (gci / "skills").iterdir()], ["dependabot-fixer"])

    def test_marketplace_ag_shape(self):
        mk = json.loads((self.agdist / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(mk["interface"]["displayName"], "Crickets")
        by = {p["name"]: p for p in mk["plugins"]}
        self.assertEqual(set(by),
                         {"code-review", "conventions", "design", "developer-safety",
                          "development-lifecycle", "diagnostics", "github-projects",
                          "maintenance", "obsidian-vault", "privacy", "research",
                          "tokens", "wiki"})
        # wiki re-categorized Coding → documentation in part 1; rest stay Coding
        expected_category = {"wiki": "documentation"}
        for p in mk["plugins"]:
            self.assertEqual(p["source"], {"source": "local", "path": f"./plugins/{p['name']}"})
            self.assertEqual(p["policy"]["installation"], "AVAILABLE")
            self.assertEqual(p["category"], expected_category.get(p["name"], "Coding"))
        # requires documented (thin) on dependents, absent on standalone
        self.assertEqual(by["maintenance"]["requires"], ["development-lifecycle"])
        self.assertNotIn("requires", by["wiki"])
        self.assertNotIn("requires", by["privacy"])
        self.assertNotIn("requires", by["development-lifecycle"])

    def test_no_renames_key_named_skip(self):
        # Loose Ends arc, "Release and generator polish" task 2 — Antigravity's
        # marketplace.json carries no `renames` key even though src/wiki/
        # group.yaml declares renamed_from: [wiki-maintenance] (proven present
        # on the Claude side by test_emit_claude.py's
        # test_renames_map_includes_real_wiki_rename against the same real
        # src/ build). A named skip, not a silent one: no Antigravity
        # marketplace-schema field exists to hang this off (checked live
        # against antigravity.google/docs/cli/plugins).
        mk = json.loads((self.agdist / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertNotIn("renames", mk)

    def test_ag_hooks_named_with_relative_paths(self):
        # The control hooks live in developer-safety. agy 1.4.x has every event
        # they use, so all four are registered: steer's UserPromptSubmit rides
        # agy's PreInvocation, coauthor-guard's SessionStart is SessionStart.
        pd = self.agdist / "plugins" / "developer-safety"
        hj = json.loads((pd / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(set(hj), {"coauthor-guard", "commit-on-stop", "kill-switch", "steer"})
        self.assertTrue(hj["commit-on-stop"]["enabled"])
        # agy's Stop / SessionStart / PreInvocation are FLAT handler lists...
        for hook, event in (("commit-on-stop", "Stop"), ("coauthor-guard", "SessionStart"),
                            ("steer", "PreInvocation")):
            self.assertEqual([h["type"] for h in hj[hook][event]], ["command"], (hook, event))
        # ...and PreToolUse is a list of {matcher, hooks} groups.
        group = hj["kill-switch"]["PreToolUse"][0]
        self.assertEqual(group["matcher"], "*")
        self.assertEqual(group["hooks"][0]["type"], "command")
        cmds = []
        for h in hj.values():
            for ev, entries in h.items():
                if ev == "enabled":
                    continue
                for e in entries:
                    cmds += [x["command"] for x in e.get("hooks", [e])]
        # every command runs the original script through the adapter, by relative path
        self.assertTrue(all(c.startswith("python3 ./hooks/_agy_hook_adapter.py ") and " bash ./hooks/" in c
                            for c in cmds), cmds)
        self.assertFalse(any("CLAUDE_PLUGIN_ROOT" in c or ".claude/hooks" in c for c in cmds))
        self.assertTrue((pd / "hooks" / "_agy_hook_adapter.py").exists())
        self.assertTrue((pd / "hooks" / "kill-switch" / "kill-switch.sh").exists())
        self.assertTrue((pd / "hooks" / "steer" / "steer.sh").exists())

    def test_adapter_is_bundled_only_where_there_are_hooks(self):
        plugins = self.agdist / "plugins"
        self.assertTrue((plugins / "tokens" / "hooks" / "_agy_hook_adapter.py").exists())
        self.assertFalse((plugins / "privacy" / "hooks").exists())

    def test_synthetic_event_gap_snippet_mcp(self):
        Primitive = emit_antigravity.Primitive
        Group = emit_antigravity.Group
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            hook_dir = base / "boot"
            hook_dir.mkdir()
            (hook_dir / "boot.sh").write_text("#!/bin/bash\n", encoding="utf-8")
            (hook_dir / "settings-fragment-bash.json").write_text(json.dumps({
                "hooks": {
                    "PreCompact": [{"matcher": ".*", "hooks": [{"type": "command", "command": "bash .claude/hooks/boot.sh"}]}],
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
            # PreCompact has no AG equivalent → skipped; PreToolUse kept
            self.assertIn("PreToolUse", hj["boot"])
            self.assertNotIn("PreCompact", hj["boot"])
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
                "capabilities: [x]\nenhances: [wf]\nversion: 1.2.0\n", encoding="utf-8")
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
            # capabilities.json sidecar IS emitted alongside plugin.json
            sidecar = json.loads(
                (dist / "plugins" / "cr" / "capabilities.json").read_text(encoding="utf-8"))
            self.assertEqual(sidecar["capabilities"], ["x"])
            self.assertEqual(sidecar["enhances"], [{"group": "wf"}])
            self.assertEqual(sidecar["version"], "1.2.0")

    def test_no_capabilities_sidecar_when_neither_declared(self):
        src_model = sys.modules["src_model"]
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "bare").mkdir(parents=True)
            (src / "bare" / "group.yaml").write_text(
                "name: Bare\ndescription: d\nstandalone: true\nrequires: []\n",
                encoding="utf-8")
            group = src_model.load_groups(src)[0]
            dist = Path(t) / "dist"
            emit_antigravity.AntigravityEmitter().emit_group(group, dist)
            # no capabilities/enhances → no sidecar emitted
            self.assertFalse((dist / "plugins" / "bare" / "capabilities.json").exists())

    def test_command_emitted_as_a_skill(self):
        # agy plugins load no commands/ folder, so a command ships as
        # skills/<name>/SKILL.md; claude-only commands are still skipped.
        src_model = sys.modules["src_model"]
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "wf" / "commands").mkdir(parents=True)
            (src / "wf" / "group.yaml").write_text(
                "name: WF\ndescription: d\nstandalone: true\nrequires: []\n", encoding="utf-8")
            (src / "wf" / "commands" / "plan.md").write_text(
                "---\nname: plan\nkind: command\nsupported_hosts: [antigravity]\n"
                "description: Turn a brief into a plan\nargument-hint: <brief>\n---\n"
                "# plan\nBrief: $ARGUMENTS\n", encoding="utf-8")
            (src / "wf" / "commands" / "ccionly.md").write_text(
                "---\nname: ccionly\nkind: command\nsupported_hosts: [claude-code]\n"
                "description: d\n---\n# ccionly\n", encoding="utf-8")
            group = src_model.load_groups(src)[0]
            dist = Path(t) / "dist"
            emit_antigravity.AntigravityEmitter().emit_group(group, dist)
            pd = dist / "plugins" / "wf"
            self.assertFalse((pd / "commands").exists())
            self.assertFalse((pd / "skills" / "ccionly").exists())
            text = (pd / "skills" / "plan" / "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith('---\nname: plan\ndescription: "Turn a brief into a plan"\n---'))
            self.assertIn("**Usage:** `/plan <brief>`", text)
            self.assertNotIn("$ARGUMENTS", text)
            self.assertIn("Brief: <what the user typed after /plan>", text)

    def test_long_command_keeps_its_whole_body_in_a_reference_file(self):
        src_model = sys.modules["src_model"]
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "wf" / "commands").mkdir(parents=True)
            (src / "wf" / "group.yaml").write_text(
                "name: WF\ndescription: d\nstandalone: true\nrequires: []\n", encoding="utf-8")
            body = "step\n" * 6000  # 30 KB, over agy's 24 KB skill limit
            (src / "wf" / "commands" / "big.md").write_text(
                "---\nname: big\nkind: command\nsupported_hosts: [antigravity]\n"
                f"description: d\n---\n{body}", encoding="utf-8")
            group = src_model.load_groups(src)[0]
            dist = Path(t) / "dist"
            emit_antigravity.AntigravityEmitter().emit_group(group, dist)
            sk = dist / "plugins" / "wf" / "skills" / "big"
            self.assertLess(len((sk / "SKILL.md").read_bytes()), 1000)
            self.assertIn("references/big.md", (sk / "SKILL.md").read_text(encoding="utf-8"))
            self.assertEqual((sk / "references" / "big.md").read_text(encoding="utf-8"), body)

    def test_command_never_overwrites_a_skill_of_the_same_name(self):
        src_model = sys.modules["src_model"]
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "wf" / "commands").mkdir(parents=True)
            (src / "wf" / "skills" / "go").mkdir(parents=True)
            (src / "wf" / "group.yaml").write_text(
                "name: WF\ndescription: d\nstandalone: true\nrequires: []\n", encoding="utf-8")
            (src / "wf" / "skills" / "go" / "SKILL.md").write_text(
                "---\nname: go\nkind: skill\nsupported_hosts: [antigravity]\n"
                "description: the real skill\n---\nreal\n", encoding="utf-8")
            (src / "wf" / "commands" / "go.md").write_text(
                "---\nname: go\nkind: command\nsupported_hosts: [antigravity]\n"
                "description: thin entry\n---\nthin\n", encoding="utf-8")
            group = src_model.load_groups(src)[0]
            dist = Path(t) / "dist"
            emit_antigravity.AntigravityEmitter().emit_group(group, dist)
            self.assertIn("real", (dist / "plugins" / "wf" / "skills" / "go" / "SKILL.md").read_text(encoding="utf-8"))

    def test_opinions_good_interpolated_into_design_command(self):
        # PLAN-opinion-consumer-grammar task 2: the same committed snapshot the
        # Claude emitter bakes in must land identically on Antigravity (real
        # src/ tree, via setUp's real build).
        # design is over agy's 24 KB skill limit, so its full text is the reference file.
        design_md = (self.agdist / "plugins" / "design" / "skills" / "design" / "references"
                     / "design.md").read_text(encoding="utf-8")
        snapshot_body = (_ROOT / "scripts" / "opinion-snapshots" / "good.md").read_text(encoding="utf-8")
        snapshot_body = snapshot_body.split("---", 2)[2].strip()
        self.assertIn(snapshot_body, design_md)
        self.assertIn("<!-- opinion:good -->", design_md)
        self.assertIn("<!-- /opinion:good -->", design_md)

    def test_opinions_interpolated_into_skill_manifest(self):
        # PLAN-wave-d-tokens-and-privacy task 4 retrofit: a directory-rooted
        # primitive (skill) declaring opinions: must have its manifest
        # re-rendered too, not just plain-copytree'd -- the directory branch
        # of _copy_component never called render_primitive_text before this
        # fix, so a skill's opinion markers were never actually baked.
        manifest = (self.agdist / "plugins" / "privacy" / "skills" / "privacy-review" / "SKILL.md")
        text = manifest.read_text(encoding="utf-8")
        good_body = (_ROOT / "scripts" / "opinion-snapshots" / "good.md").read_text(encoding="utf-8")
        good_body = good_body.split("---", 2)[2].strip()
        self.assertIn(good_body, text)
        self.assertIn("<!-- opinion:good -->", text)
        self.assertIn("<!-- opinion:how-we-engineer -->", text)

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

    def test_rules_get_the_trigger_agy_requires(self):
        src_model = sys.modules["src_model"]
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "rf" / "snippets").mkdir(parents=True)
            (src / "rf" / "rules").mkdir(parents=True)
            (src / "rf" / "group.yaml").write_text(
                "name: RF\ndescription: d\nstandalone: true\nrequires: []\n", encoding="utf-8")
            (src / "rf" / "snippets" / "always.md").write_text(
                "---\nname: always\nkind: snippet\nsupported_hosts: [antigravity]\n"
                "description: d\n---\nbody\n", encoding="utf-8")
            (src / "rf" / "rules" / "situational.md").write_text(
                "---\nname: situational\nkind: rule\nsupported_hosts: [antigravity]\n"
                "description: when to apply\n---\nbody\n", encoding="utf-8")
            (src / "rf" / "rules" / "chosen.md").write_text(
                "---\nname: chosen\nkind: rule\nsupported_hosts: [antigravity]\n"
                "description: d\ntrigger: manual\n---\nbody\n", encoding="utf-8")
            group = src_model.load_groups(src)[0]
            dist = Path(t) / "dist"
            emit_antigravity.AntigravityEmitter().emit_group(group, dist)
            rules = dist / "plugins" / "rf" / "rules"
            self.assertIn("\ntrigger: always_on\n", (rules / "always.md").read_text(encoding="utf-8"))
            self.assertIn("\ntrigger: model_decision\n", (rules / "situational.md").read_text(encoding="utf-8"))
            # a trigger the source already names is kept, not doubled
            chosen = (rules / "chosen.md").read_text(encoding="utf-8")
            self.assertEqual(chosen.count("trigger:"), 1)
            self.assertIn("trigger: manual", chosen)

    def test_agents_lose_the_lines_agy_cannot_read(self):
        src_model = sys.modules["src_model"]
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "af" / "agents").mkdir(parents=True)
            (src / "af" / "group.yaml").write_text(
                "name: AF\ndescription: d\nstandalone: true\nrequires: []\n", encoding="utf-8")
            (src / "af" / "agents" / "scout.md").write_text(
                "---\nname: scout\ndescription: finds things\nkind: agent\n"
                "supported_hosts: [antigravity]\ntools: Read, Glob, Grep\nmodel: claude-sonnet-5\n"
                "version: 0.1.0\n---\nYou find things.\n", encoding="utf-8")
            group = src_model.load_groups(src)[0]
            dist = Path(t) / "dist"
            emit_antigravity.AntigravityEmitter().emit_group(group, dist)
            text = (dist / "plugins" / "af" / "agents" / "scout.md").read_text(encoding="utf-8")
            self.assertNotIn("tools:", text)
            self.assertNotIn("model:", text)
            self.assertIn("name: scout", text)
            self.assertIn("version: 0.1.0", text)
            self.assertIn("You find things.", text)

    def test_a_folder_the_emitter_no_longer_writes_does_not_linger(self):
        src_model = sys.modules["src_model"]
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "cf").mkdir(parents=True)
            (src / "cf" / "group.yaml").write_text(
                "name: CF\ndescription: d\nstandalone: true\nrequires: []\n", encoding="utf-8")
            group = src_model.load_groups(src)[0]
            dist = Path(t) / "dist"
            stale = dist / "plugins" / "cf" / "commands"
            stale.mkdir(parents=True)
            (stale / "old.md").write_text("old", encoding="utf-8")
            emit_antigravity.AntigravityEmitter().emit_group(group, dist)
            self.assertFalse(stale.exists())

    def test_long_skill_keeps_its_whole_body_reachable(self):
        # wiki's diataxis-author is ~50 KB; agy would load only the first 24 KB.
        sk = self.agdist / "plugins" / "wiki" / "skills" / "diataxis-author"
        self.assertLess(len((sk / "SKILL.md").read_bytes()), 2000)
        full = (sk / "references" / "SKILL.full.md").read_text(encoding="utf-8")
        source = (_ROOT / "src" / "wiki" / "skills" / "diataxis-author" / "SKILL.md").read_text(encoding="utf-8")
        # the body is unchanged except that its relative links go one folder deeper
        body = source.split("\n---\n", 1)[1]
        self.assertEqual(full.strip(), emit_antigravity._deepen_links(body, 1).strip())

    def test_real_dist_has_the_shape_agy_loads(self):
        # The same structural gate CI runs, over this test's own real build.
        spec = importlib.util.spec_from_file_location("check_agy_plugin_shape", _HERE / "check-agy-plugin-shape.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        self.assertEqual(m.check_dist(self.agdist / "plugins"), [])

    def test_relative_links_follow_a_body_that_moves_deeper(self):
        deepen = emit_antigravity._deepen_links
        body = ("[a](../skills/x/SKILL.md) [b](templates/t.md#top) [c](https://e.com/x) "
                "[d](#here) [e](other.md) [f](other.md#part) [g](${CLAUDE_PLUGIN_ROOT}/x)")
        out = deepen(body, 1, frozenset({"other"}))
        self.assertIn("[a](../../skills/x/SKILL.md)", out)
        self.assertIn("[b](../templates/t.md#top)", out)           # anchor kept
        self.assertIn("[c](https://e.com/x)", out)                  # URLs untouched
        self.assertIn("[d](#here)", out)                            # in-page anchors untouched
        self.assertIn("[e](../other/SKILL.md)", out)                # sibling command -> its skill
        self.assertIn("[f](../other/SKILL.md#part)", out)
        self.assertIn("[g](${CLAUDE_PLUGIN_ROOT}/x)", out)          # plugin-root paths untouched
        # a long body goes one level deeper again (references/<name>.md)
        self.assertIn("[a](../../skills/x/SKILL.md)", deepen("[a](../skills/x/SKILL.md)", 1))
        self.assertIn("[a](../../../skills/x/SKILL.md)", deepen("[a](../skills/x/SKILL.md)", 2))

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
