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
        for slug in ("development-lifecycle", "privacy", "maintenance", "wiki"):
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
        # 0.3.9 = recent-wiki-changes.sh/.ps1 $AGENTM_SCRIPTS_DIR env-override resolver;
        # 0.4.0 = restored documenter.md's normative template source (templates/README.md).
        # 0.5.0 = PLAN-r3-voice-mechanism task 1 — voice-rules.json + rule_pack.py.
        # 0.5.1 = task 2 calibration — Tier-B thresholds + 2 severity downgrades.
        # 0.5.2 = task 4 — floor promotion + floor_eligible field.
        # 0.5.3 = task 5 — role-noun carve-out codified in base-style-guide.md.
        # 0.6.1 = Consolidation arc CONS-2 task 7 — diataxis-author check.py
        # stale-xref /bugfix (SVG/asset targets + structural Home/_Sidebar/README
        # links no longer false-positive as stale).
        # 0.6.2 = Consolidation arc CONS-3 task 3 — voice-a4-load-bearing hint
        # extended with an explicit term-of-art carve-out, locked by a new
        # check-slop test.
        # 0.7.0 = L6 wiki-publish-render fix (F10/F11) — new
        # scripts/wiki_publish_transform.py strips YAML frontmatter and
        # rewrites relative asset links to raw-asset URLs at publish time;
        # wired into wiki-sync.yml between rsync and commit, plus a post-push
        # render smoke check; vendor_gate.py vendors it alongside check-wiki.py.
        # 0.7.1 = check-wiki gains rule (q) — top-note length, ported from
        # agentm's rule q (PR #305) to close a cross-repo-script-parity gap.
        # 0.7.2 = wiki_publish_transform.py stops rewriting bare extension-less
        # page links as broken asset URLs; new test_wiki_publish_transform.py.
        # 0.8.0 = the design plugin's prose-pass skill wired into authoring —
        # documenter.md runs it (via scripts/prose_pass.py) on every drafted
        # page before preview (announced Claude-only fallback); diataxis-author
        # + wiki-author document the step by cross-reference.
        # 0.9.0 = Loose Ends arc, "Release and generator polish" task 2 —
        # declares renamed_from: [wiki-maintenance], the single-hop proof of
        # the generator's new Claude Code marketplace renames map.
        self.assertEqual(self._plugin_json("wiki")["version"], "0.9.0")
        # 0.3.0 = check-no-pii.sh + templates/hooks/pre-push moved into src/pii/
        # so they actually ship inside the plugin payload (R2.4 task 7).
        # 0.3.1 = check-no-pii.sh scan collapsed to one grep per file (fixes a
        # 9.4x Windows-vs-Mac subprocess-spawn slowdown; PLAN-ci-walltime-diet
        # task 1). Detection behavior unchanged.
        # 0.4.0 = AG Wave A rename 2: directory pii -> privacy.
        # 0.5.0 = PLAN-wave-d-tokens-and-privacy tasks 4-6: privacy-review
        # skill + Semgrep taint pack + scrub_text() surface.
        # 0.6.0 = task 4 retrofit: real opinions: [good, how-we-engineer]
        # wiring once PLAN-opinion-consumer-grammar (#167) landed.
        # 0.6.1 = Consolidation CONS-2 task 6 — stale src/pii/ header-comment
        # path in templates/hooks/pre-push fixed to src/privacy/. Doc-only.
        self.assertEqual(self._plugin_json("privacy")["version"], "0.6.1")

    def test_dependencies_from_requires(self):
        # post-seed-retirement: maintenance (ex-github-ci) depends on
        # development-lifecycle; wiki (ex-wiki-maintenance) flipped to
        # standalone (no requires) in the wiki-maintenance scaffold (part 1).
        self.assertEqual(self._plugin_json("maintenance").get("dependencies"), ["development-lifecycle"])
        self.assertNotIn("dependencies", self._plugin_json("wiki"))
        self.assertNotIn("dependencies", self._plugin_json("privacy"))
        self.assertNotIn("dependencies", self._plugin_json("development-lifecycle"))

    def test_skill_with_opinions_frontmatter_gets_markers_interpolated(self):
        # PLAN-wave-d-tokens-and-privacy task 4 retrofit: a directory-rooted
        # primitive (skill) that declares `opinions:` must have its manifest
        # re-rendered from the committed snapshot store, not just plain-
        # copytree'd -- _copy_component's directory branch never called
        # render_primitive_text at all before this fix, so no skill's
        # opinions: markers were ever actually baked from the snapshot.
        manifest = self.cdist / "plugins" / "privacy" / "skills" / "privacy-review" / "SKILL.md"
        self.assertTrue(manifest.is_file())
        text = manifest.read_text(encoding="utf-8")
        self.assertIn("Good means it survives an adversarial pass", text)
        self.assertIn("How we engineer means the phase discipline", text)

    def test_components_copied(self):
        d = self.cdist / "plugins"
        self.assertTrue((d / "privacy" / "skills" / "pii-scrubber" / "SKILL.md").exists())
        self.assertTrue((d / "maintenance" / "skills" / "dependabot-fixer" / "SKILL.md").exists())
        self.assertTrue((d / "development-lifecycle" / "agents" / "evaluator.md").exists())
        self.assertTrue((d / "wiki" / "agents" / "diataxis-evaluator.md").exists())
        # part 2 fold-in (copy-not-move from agentm): all five primitives + skill
        # subdirs (generator copytree's the whole skill root) + group scripts.
        # part 3 task 2 added the read-only style-scope-evaluator agent (both hosts).
        self.assertTrue((d / "wiki" / "agents" / "style-scope-evaluator.md").exists())
        self.assertTrue((d / "wiki" / "agents" / "documenter.md").exists())
        self.assertTrue((d / "wiki" / "skills" / "wiki-author" / "SKILL.md").exists())
        self.assertTrue((d / "wiki" / "skills" / "diataxis-author" / "SKILL.md").exists())
        self.assertTrue((d / "wiki" / "skills" / "diataxis-author" / "scripts" / "classify.py").exists())
        self.assertTrue((d / "wiki" / "skills" / "diataxis-author" / "templates" / "how-to.md").exists())
        self.assertTrue((d / "wiki" / "commands" / "recent-wiki-changes.md").exists())
        self.assertTrue((d / "wiki" / "scripts" / "check-wiki.py").exists())
        self.assertTrue((d / "wiki" / "scripts" / "recent-wiki-changes.sh").exists())
        # part 4 task 4: the wiki-watch skill (cross-host) + command (claude-only
        # scheduling entry) + the engine group scripts (bundled both hosts).
        self.assertTrue((d / "wiki" / "skills" / "wiki-watch" / "SKILL.md").exists())
        self.assertTrue((d / "wiki" / "commands" / "wiki-watch.md").exists())
        self.assertTrue((d / "wiki" / "scripts" / "wiki_watch_cycle.py").exists())

    def test_marketplace_lists_all_with_resolving_sources(self):
        mk = json.loads((self.cdist / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual({p["name"] for p in mk["plugins"]},
                         {"code-review", "conventions", "design", "developer-safety",
                          "development-lifecycle", "diagnostics", "github-projects",
                          "maintenance", "obsidian-vault", "privacy", "research",
                          "tokens", "wiki"})
        for p in mk["plugins"]:
            self.assertEqual(p["source"], f"./plugins/{p['name']}")
            self.assertTrue((self.cdist / "plugins" / p["name"]).is_dir())

    def test_renames_map_includes_real_wiki_rename(self):
        # Loose Ends arc, "Release and generator polish" task 2 — the single-hop
        # proof against real src/ data: src/wiki/group.yaml declares
        # renamed_from: [wiki-maintenance], the actual FOLLOWUPS-motivating
        # incident (an install on the pre-rename name hit plugin-not-found,
        # 2026-06-10). Built through the real setUp() build, not a synthetic
        # fixture.
        mk = json.loads((self.cdist / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(mk["renames"].get("wiki-maintenance"), "wiki")

    def test_renames_map_absent_key_when_no_group_declares_it(self):
        # A catalog with zero renamed_from declarations must not carry an
        # empty "renames": {} key at all — omitted entirely, matching how
        # pre-v2.1.193 Claude Code hosts (which ignore the field) and every
        # other conditional marketplace-entry field (dependencies/capabilities/
        # enhances) already behave.
        src_model = sys.modules["src_model"]
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "plain").mkdir(parents=True)
            (src / "plain" / "group.yaml").write_text(
                "name: Plain\ndescription: d\nstandalone: true\nrequires: []\n",
                encoding="utf-8")
            groups = src_model.load_groups(src)
            dist = Path(t) / "dist"
            emitter = emit_claude.ClaudeEmitter()
            entries = [emitter.emit_group(g, dist) for g in groups]
            renames = src_model.build_renames_map(groups)
            emitter.write_marketplace(entries, dist, renames)
            mk = json.loads((dist / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
            self.assertNotIn("renames", mk)

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

    def test_opinions_good_interpolated_into_design_command(self):
        # PLAN-opinion-consumer-grammar task 2: design/commands/design.md
        # declares opinions: [good] with a marker in its Step-6 review-pass
        # prose -- generate.py must have baked the committed snapshot's body
        # in at build time (real src/ tree, via setUp's real build).
        design_md = (self.cdist / "plugins" / "design" / "commands" / "design.md").read_text(encoding="utf-8")
        snapshot_body = (_ROOT / "scripts" / "opinion-snapshots" / "good.md").read_text(encoding="utf-8")
        snapshot_body = snapshot_body.split("---", 2)[2].strip()
        self.assertIn(snapshot_body, design_md)
        self.assertIn("<!-- opinion:good -->", design_md)
        self.assertIn("<!-- /opinion:good -->", design_md)
        self.assertIn("good", design_md.split("opinions: [", 1)[1].split("]", 1)[0])

    def test_opinions_how_we_engineer_interpolated_into_design_command(self):
        # PLAN-wave-d-personas task 2: design/commands/design.md additionally
        # declares how-we-engineer (alongside good) with a marker at the
        # rung-picking (sizing-ladder) prose -- the second binding fanned out
        # through the same cross-plugin grammar proven above.
        design_md = (self.cdist / "plugins" / "design" / "commands" / "design.md").read_text(encoding="utf-8")
        snapshot_body = (_ROOT / "scripts" / "opinion-snapshots" / "how-we-engineer.md").read_text(encoding="utf-8")
        snapshot_body = snapshot_body.split("---", 2)[2].strip()
        self.assertIn(snapshot_body, design_md)
        self.assertIn("<!-- opinion:how-we-engineer -->", design_md)
        self.assertIn("<!-- /opinion:how-we-engineer -->", design_md)
        self.assertIn("how-we-engineer", design_md.split("opinions: [", 1)[1].split("]", 1)[0])

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
