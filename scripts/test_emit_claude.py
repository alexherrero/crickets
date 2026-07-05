#!/usr/bin/env python3
"""Tests for scripts/emit_claude.py (crickets v3.0 #40, part 2)."""
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
    emit_claude = _load("emit_claude")


@unittest.skipUnless(HAVE_YAML, "PyYAML required")
class TestClaudeEmitter(unittest.TestCase):
    def setUp(self):
        self._saved = dict(generate.EMITTERS)
        generate.EMITTERS.clear()
        generate.register(emit_claude.ClaudeEmitter())
        self.tmp = tempfile.TemporaryDirectory()
        self.dist = Path(self.tmp.name) / "dist"
        generate.build(src=_ROOT / "src", dist=self.dist)
        self.cdist = self.dist / "claude-code"  # per-host namespace

    def tearDown(self):
        generate.EMITTERS.clear()
        generate.EMITTERS.update(self._saved)
        self.tmp.cleanup()

    def _plugin_json(self, slug):
        p = self.cdist / "plugins" / slug / ".claude-plugin" / "plugin.json"
        return json.loads(p.read_text(encoding="utf-8"))

    def test_plugin_json_per_group(self):
        # Per-plugin semver: each plugin.json version is sourced from that
        # group's `group.yaml` `version:` (default "0.1.0"), NOT a single global
        # constant — bumping one group's version is what lets `claude plugin
        # update <slug>@crickets` pull its new primitives. Assert the wiring
        # (plugin.json == declared group version) so this stays true across
        # future bumps without re-hardcoding numbers here.
        src_model = sys.modules["src_model"]
        declared = {g.slug: g.version for g in src_model.load_groups(_ROOT / "src")}
        for slug in ("developer-workflows", "pii", "github-ci", "wiki-maintenance"):
            d = self._plugin_json(slug)
            self.assertEqual(d["name"], slug)
            self.assertTrue(d.get("description"))
            self.assertEqual(d["version"], declared[slug])
        # Concrete anchor for the per-plugin-semver fix: wiki-maintenance was
        # bumped past the original 0.1.0 (0.3.0 = six-section taxonomy — the
        # Decisions section retired from the scaffolder, gate, and ADR routing;
        # 0.3.1 = repoint retired-ADR src/ references to the living designs;
        # 0.3.2 = diataxis-author/documenter/diataxis-evaluator/migrate.py four-mode
        # → six-section taxonomy modernization; 0.3.3 = check-wiki rule (e) accepts
        # the combined plugin-page shape (## Architecture + ## Reference two-parent);
        # 0.3.4 = codify the combined plugin-reference page standard (template + section
        # library + diagram-style.md house SVG spec + plain-spoken voice lessons);
        # 0.3.5 = explanation-page four-beat skeleton (why-leads) in templates/explanation.md;
        # 0.3.6 = check-wiki rule (p) shape axis (explanation-as-lookup / reference-as-narrative);
        # 0.3.7 = diataxis-author tutorial->dir map corrected to how-to (retired tutorials/
        # folder), SKILL.md Status rewritten to as-built, duplicate stub repair section dropped;
        # 0.3.8 = SKILL.md's absolute example paths -> repo-relative; SKILL.md's + diataxis-
        # evaluator.md's "ADR 0004" citations repointed to the crickets-conventions design;
        # 0.3.9 = recent-wiki-changes.sh/.ps1 $AGENTM_SCRIPTS_DIR env-override resolver.
        self.assertEqual(self._plugin_json("wiki-maintenance")["version"], "0.3.9")
        self.assertEqual(self._plugin_json("pii")["version"], "0.2.1")  # 0.2.1 = capabilities: [privacy]

    def test_dependencies_from_requires(self):
        # post-seed-retirement: github-ci depends on developer-workflows; wiki-maintenance
        # flipped to standalone (no requires) in the wiki-maintenance scaffold (part 1).
        self.assertEqual(self._plugin_json("github-ci").get("dependencies"), ["developer-workflows"])
        self.assertNotIn("dependencies", self._plugin_json("wiki-maintenance"))
        self.assertNotIn("dependencies", self._plugin_json("pii"))
        self.assertNotIn("dependencies", self._plugin_json("developer-workflows"))

    def test_components_copied(self):
        d = self.cdist / "plugins"
        self.assertTrue((d / "pii" / "skills" / "pii-scrubber" / "SKILL.md").exists())
        self.assertTrue((d / "github-ci" / "skills" / "dependabot-fixer" / "SKILL.md").exists())
        self.assertTrue((d / "developer-workflows" / "agents" / "evaluator.md").exists())
        self.assertTrue((d / "wiki-maintenance" / "agents" / "diataxis-evaluator.md").exists())
        # part 2 fold-in (copy-not-move from agentm): all five primitives + skill
        # subdirs (generator copytree's the whole skill root) + group scripts.
        # part 3 task 2 added the read-only style-scope-evaluator agent (both hosts).
        self.assertTrue((d / "wiki-maintenance" / "agents" / "style-scope-evaluator.md").exists())
        self.assertTrue((d / "wiki-maintenance" / "agents" / "documenter.md").exists())
        self.assertTrue((d / "wiki-maintenance" / "skills" / "wiki-author" / "SKILL.md").exists())
        self.assertTrue((d / "wiki-maintenance" / "skills" / "diataxis-author" / "SKILL.md").exists())
        self.assertTrue((d / "wiki-maintenance" / "skills" / "diataxis-author" / "scripts" / "classify.py").exists())
        self.assertTrue((d / "wiki-maintenance" / "skills" / "diataxis-author" / "templates" / "how-to.md").exists())
        self.assertTrue((d / "wiki-maintenance" / "commands" / "recent-wiki-changes.md").exists())
        self.assertTrue((d / "wiki-maintenance" / "scripts" / "check-wiki.py").exists())
        self.assertTrue((d / "wiki-maintenance" / "scripts" / "recent-wiki-changes.sh").exists())
        # part 4 task 4: the wiki-watch skill (cross-host) + command (claude-only
        # scheduling entry) + the engine group scripts (bundled both hosts).
        self.assertTrue((d / "wiki-maintenance" / "skills" / "wiki-watch" / "SKILL.md").exists())
        self.assertTrue((d / "wiki-maintenance" / "commands" / "wiki-watch.md").exists())
        self.assertTrue((d / "wiki-maintenance" / "scripts" / "wiki_watch_cycle.py").exists())

    def test_marketplace_lists_all_with_resolving_sources(self):
        mk = json.loads((self.cdist / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual({p["name"] for p in mk["plugins"]},
                         {"code-review", "design-docs", "developer-safety",
                          "developer-workflows", "pii", "github-ci",
                          "github-projects", "obsidian-vault",
                          "releasing-conventions", "status-line-meter",
                          "testing-conventions",
                          "token-audit", "wiki-maintenance"})
        for p in mk["plugins"]:
            self.assertEqual(p["source"], f"./plugins/{p['name']}")
            self.assertTrue((self.cdist / "plugins" / p["name"]).is_dir())

    def test_hooks_emitted_on_correct_events(self):
        # the control hooks live in developer-safety post-seed-retirement
        raw = json.loads((self.cdist / "plugins" / "developer-safety" / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        # Claude plugin hooks.json is wrapped in a top-level "hooks" record.
        self.assertIn("hooks", raw)
        hj = raw["hooks"]
        self.assertIn("Stop", hj)
        self.assertIn("PreToolUse", hj)
        # steer moved PreToolUse -> UserPromptSubmit in R2.2 task 5 (the
        # documented PreToolUse-stdout-injection mechanism was live-verified
        # false); it no longer shares kill-switch's event.
        self.assertIn("UserPromptSubmit", hj)
        stop_cmds = [h["command"] for e in hj["Stop"] for h in e.get("hooks", [])]
        self.assertTrue(any("${CLAUDE_PLUGIN_ROOT}/hooks/commit-on-stop/commit-on-stop.sh" in c
                            for c in stop_cmds), stop_cmds)
        pre_cmds = [h["command"] for e in hj["PreToolUse"] for h in e.get("hooks", [])]
        self.assertTrue(any("kill-switch/kill-switch.sh" in c for c in pre_cmds), pre_cmds)
        self.assertFalse(any("steer/steer.sh" in c for c in pre_cmds), pre_cmds)
        prompt_cmds = [h["command"] for e in hj["UserPromptSubmit"] for h in e.get("hooks", [])]
        self.assertTrue(any("steer/steer.sh" in c for c in prompt_cmds), prompt_cmds)
        # no raw .claude/hooks path leaks through
        self.assertFalse(any(".claude/hooks" in c for c in stop_cmds + pre_cmds + prompt_cmds))
        # scripts bundled under the plugin
        self.assertTrue((self.cdist / "plugins" / "developer-safety" / "hooks" / "commit-on-stop" / "commit-on-stop.sh").exists())

    def test_synthetic_mcp_output_style_snippet(self):
        Primitive = emit_claude.Primitive
        Group = emit_claude.Group
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            os_md = base / "terse.md"
            os_md.write_text("---\nname: terse\nkind: output-style\nsupported_hosts: [claude-code]\n---\n# terse\n", encoding="utf-8")
            sn_md = base / "note.md"
            sn_md.write_text("---\nname: note\nkind: snippet\nsupported_hosts: [claude-code]\n---\nbe terse\n", encoding="utf-8")
            mcp_dir = base / "srv"
            mcp_dir.mkdir()
            (mcp_dir / "mcp.json").write_text('{"mcpServers": {"srv": {"command": "x"}}}', encoding="utf-8")
            prims = [
                Primitive("terse", "output-style", ["claude-code"], os_md, os_md, {}),
                Primitive("note", "snippet", ["claude-code"], sn_md, sn_md, {}),
                Primitive("srv", "mcp-server", ["claude-code"], mcp_dir / "mcp.json", mcp_dir, {}),
            ]
            group = Group("extras", "Extras", "d", "Coding", [], True, prims)
            dist = base / "dist"
            emit_claude.ClaudeEmitter().emit_group(group, dist)
            pd = dist / "plugins" / "extras"
            # output-style copied
            self.assertTrue((pd / "output-styles" / "terse.md").exists())
            # mcp merged into .mcp.json
            mcp = json.loads((pd / ".mcp.json").read_text(encoding="utf-8"))
            self.assertIn("srv", mcp["mcpServers"])
            # snippet dropped (no native Claude home)
            self.assertFalse((pd / "snippets").exists())
            self.assertFalse((pd / "note.md").exists())

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

    def test_enhances_capabilities_emitted(self):
        src_model = sys.modules["src_model"]
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "cr").mkdir(parents=True)
            (src / "cr" / "group.yaml").write_text(
                "name: CR\ndescription: d\nstandalone: true\nrequires: []\n"
                "capabilities: [x]\n"
                "enhances:\n  - group: wf\n    capability: review\n    effect: dispatches\n",
                encoding="utf-8")
            group = src_model.load_groups(src)[0]
            dist = Path(t) / "dist"
            entry = emit_claude.ClaudeEmitter().emit_group(group, dist)
            # marketplace entry carries both (the discovery surface)
            self.assertEqual(entry["capabilities"], ["x"])
            self.assertEqual(entry["enhances"],
                             [{"group": "wf", "capability": "review", "effect": "dispatches"}])
            # plugin.json stays THIN — Claude's plugin.json schema rejects
            # unrecognized keys (`claude plugin validate`: 'Unrecognized key:
            # "capabilities"'), so capabilities/enhances live in the marketplace
            # entry ONLY, like Antigravity. Only `dependencies` is recognized.
            pj = json.loads((dist / "plugins" / "cr" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
            self.assertNotIn("capabilities", pj)
            self.assertNotIn("enhances", pj)

    def test_command_emitted(self):
        # a discovered `command` primitive is copied into the native commands/
        # subdir (the developer-workflows phase commands); host-filtered.
        src_model = sys.modules["src_model"]
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "wf" / "commands").mkdir(parents=True)
            (src / "wf" / "group.yaml").write_text(
                "name: WF\ndescription: d\nstandalone: true\nrequires: []\n", encoding="utf-8")
            (src / "wf" / "commands" / "plan.md").write_text(
                "---\nname: plan\nkind: command\nsupported_hosts: [claude-code]\n"
                "description: d\n---\n# plan\n", encoding="utf-8")
            # an antigravity-only command must NOT reach the Claude plugin
            (src / "wf" / "commands" / "agonly.md").write_text(
                "---\nname: agonly\nkind: command\nsupported_hosts: [antigravity]\n"
                "description: d\n---\n# agonly\n", encoding="utf-8")
            group = src_model.load_groups(src)[0]
            dist = Path(t) / "dist"
            emit_claude.ClaudeEmitter().emit_group(group, dist)
            cmds = dist / "plugins" / "wf" / "commands"
            self.assertTrue((cmds / "plan.md").exists())
            self.assertFalse((cmds / "agonly.md").exists())

    def test_snippet_discovered_dropped(self):
        # a discovered `snippet` primitive is DROPPED on Claude (no instruction-file
        # primitive) — emit_claude notes it on stderr; nothing lands in dist/.
        src_model = sys.modules["src_model"]
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "sf" / "snippets").mkdir(parents=True)
            (src / "sf" / "group.yaml").write_text(
                "name: SF\ndescription: d\nstandalone: true\nrequires: []\n", encoding="utf-8")
            (src / "sf" / "snippets" / "no-coauthor.md").write_text(
                "---\nname: no-coauthor\nkind: snippet\nsupported_hosts: [claude-code]\n"
                "description: d\n---\nbody\n", encoding="utf-8")
            group = src_model.load_groups(src)[0]
            dist = Path(t) / "dist"
            emit_claude.ClaudeEmitter().emit_group(group, dist)
            pd = dist / "plugins" / "sf"
            # dropped — no snippets/ or rules/ dir, no stray file landed
            self.assertFalse((pd / "snippets").exists())
            self.assertFalse((pd / "rules").exists())
            self.assertFalse((pd / "no-coauthor.md").exists())

    def test_group_scripts_bundled(self):
        # a group-level scripts/ asset dir is copied verbatim into the plugin
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
            emit_claude.ClaudeEmitter().emit_group(group, dist)
            f = dist / "plugins" / "cr" / "scripts" / "cross-review.sh"
            self.assertTrue(f.exists())
            self.assertIn("echo hi", f.read_text(encoding="utf-8"))

    def test_group_scripts_excludes_pycache(self):
        # the asset copy must NOT pull __pycache__/*.pyc (transient, gitignored)
        # into dist/ — else a fresh build after tests compiled a bundled .py
        # drifts vs. the committed (clean) dist/. Regression for the CI failure
        # the developer-workflows capability_probe.py surfaced.
        src_model = sys.modules["src_model"]
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "cr" / "scripts" / "__pycache__").mkdir(parents=True)
            (src / "cr" / "group.yaml").write_text(
                "name: CR\ndescription: d\nstandalone: true\nrequires: []\n", encoding="utf-8")
            (src / "cr" / "scripts" / "probe.py").write_text("x = 1\n", encoding="utf-8")
            (src / "cr" / "scripts" / "__pycache__" / "probe.cpython-311.pyc").write_text(
                "bytecode", encoding="utf-8")
            group = src_model.load_groups(src)[0]
            dist = Path(t) / "dist"
            emit_claude.ClaudeEmitter().emit_group(group, dist)
            sd = dist / "plugins" / "cr" / "scripts"
            self.assertTrue((sd / "probe.py").exists())
            self.assertFalse((sd / "__pycache__").exists())

    def test_skill_root_copytree_excludes_pycache(self):
        # the COMPONENT (skill / agent) root copytree must ALSO exclude
        # __pycache__/*.pyc — not just the group scripts/ asset path. The
        # diataxis-author style_resolver/author tests are the first to import a
        # bundled skill's .py as modules, so CI compiled
        # src/.../skills/diataxis-author/scripts/__pycache__/*.pyc before
        # generate.py check, and the unfiltered _copy_component copytree dragged
        # them into a fresh dist/ → drift vs. the committed (clean) dist/.
        # Regression for that CI failure (wiki-maintenance part 3 task 1).
        src_model = sys.modules["src_model"]
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            sk = src / "sk" / "skills" / "foo" / "scripts"
            (sk / "__pycache__").mkdir(parents=True)
            (src / "sk" / "group.yaml").write_text(
                "name: SK\ndescription: d\nstandalone: true\nrequires: []\n", encoding="utf-8")
            (src / "sk" / "skills" / "foo" / "SKILL.md").write_text(
                "---\nname: foo\nkind: skill\nsupported_hosts: [claude-code]\n"
                "description: d\n---\n# foo\n", encoding="utf-8")
            (sk / "helper.py").write_text("x = 1\n", encoding="utf-8")
            (sk / "__pycache__" / "helper.cpython-311.pyc").write_text(
                "bytecode", encoding="utf-8")
            group = src_model.load_groups(src)[0]
            dist = Path(t) / "dist"
            emit_claude.ClaudeEmitter().emit_group(group, dist)
            sd = dist / "plugins" / "sk" / "skills" / "foo" / "scripts"
            self.assertTrue((sd / "helper.py").exists())
            self.assertFalse((sd / "__pycache__").exists())


if __name__ == "__main__":
    unittest.main()
