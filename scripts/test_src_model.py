#!/usr/bin/env python3
"""Tests for scripts/src_model.py (crickets v3.0 #40, part 2)."""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _HERE / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m  # dataclasses resolve field types via sys.modules[__module__]
    spec.loader.exec_module(m)
    return m


try:
    import yaml  # noqa: F401
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

src_model = _load("src_model") if HAVE_YAML else None


@unittest.skipUnless(HAVE_YAML, "PyYAML required")
class TestSrcModel(unittest.TestCase):
    def test_real_tree_shape(self):
        groups = src_model.load_groups(_ROOT / "src")
        by = {g.slug: g for g in groups}
        # "research" (wave-c-research task 1): a scripts-only dir with no
        # group.yaml yet -- load_groups discovers it by directory presence
        # alone, ahead of task 4's group.yaml + primitives.
        self.assertEqual(set(by),
                         {"code-review", "conventions", "design", "developer-safety",
                          "development-lifecycle", "diagnostics", "github-projects",
                          "maintenance", "obsidian-vault", "privacy", "research",
                          "tokens", "wiki"})
        # obsidian-vault (V5-2): the re-homed `vault` storage backend lands as a
        # group asset under scripts/ (LC-2 — engine-consumed, not a host primitive).
        # Task 2 additionally re-homed the vault-specific conflict-merger out of the
        # kernel: scripts/vault_conflicts.py (another group asset) + the
        # conflict-merger-session-start hook. Task 6 adds the operator-facing
        # `vault-doctor` skill (the thin packaging surface over the read-only
        # scripts/doctor_vault.py). So two *discovered* primitives now: the
        # claude-only hook (SessionStart has no Antigravity equivalent) + the skill
        # (both hosts). The backend scripts emit on every host, so the group still
        # supports both.
        ov = by["obsidian-vault"]
        self.assertTrue(ov.standalone)
        self.assertEqual(ov.requires, [])
        self.assertEqual(ov.enhances, [])
        self.assertEqual(ov.capabilities, ["storage-backend"])
        self.assertEqual({(p.name, p.kind) for p in ov.primitives},
                         {("conflict-merger-session-start", "hook"),
                          ("vault-doctor", "skill")})
        cm = {p.name: p for p in ov.primitives}["conflict-merger-session-start"]
        self.assertEqual(cm.supported_hosts, ["claude-code"])
        doctor = {p.name: p for p in ov.primitives}["vault-doctor"]
        self.assertEqual(sorted(doctor.supported_hosts), ["antigravity", "claude-code"])
        self.assertTrue(ov.has_group_assets())
        self.assertTrue(ov.supports("claude-code"))
        self.assertTrue(ov.supports("antigravity"))
        # composition: the developer seed is retired (part 6); maintenance still requires
        # development-lifecycle (AG Wave A rename 2: github-ci -> maintenance,
        # requires: re-pointed developer-workflows -> development-lifecycle at
        # renames-1). wiki flipped to standalone + an enhance during the
        # scaffold (part 1, capability-less); the documenter-wiring part tightened the enhance
        # to target the 'documentation' capability, now declared on development-lifecycle
        # (AG Wave A rename 1: developer-workflows -> development-lifecycle).
        self.assertEqual(by["maintenance"].requires, ["development-lifecycle"])
        wm = by["wiki"]
        self.assertEqual(wm.requires, [])
        self.assertTrue(wm.standalone)
        self.assertEqual([e.group for e in wm.enhances], ["development-lifecycle"])
        self.assertEqual(wm.enhances[0].capability, "documentation")
        # part 2 folded in the bucket-A primitives (copy-not-move from agentm);
        # part 3 task 2 added the read-only style-scope-evaluator agent (DC-4);
        # part 4 task 4 added the wiki-watch skill (cross-host) + the wiki-watch
        # command (claude-only scheduling entry, DC-W4). The provisioning part
        # (wiki-maintenance-provisioning 3/4) added the wiki-init command → 9
        # primitives. Keyed by (name, kind) since wiki-watch is BOTH a skill and a
        # command (same name, distinct kinds + emit subdirs — no collision).
        self.assertEqual({(p.name, p.kind) for p in wm.primitives}, {
            ("diataxis-evaluator", "agent"), ("documenter", "agent"),
            ("style-scope-evaluator", "agent"),
            ("wiki-author", "skill"), ("diataxis-author", "skill"),
            ("wiki-watch", "skill"),
            ("recent-wiki-changes", "command"), ("wiki-watch", "command"),
            ("wiki-init", "command")})
        self.assertEqual(by["privacy"].requires, [])
        self.assertTrue(by["privacy"].standalone)
        self.assertFalse(by["maintenance"].standalone)
        self.assertEqual(len(by["privacy"].primitives), 2)  # 0.2.0: skill + pii-patterns rule
        # development-lifecycle (AG Wave A rename 1, ex-developer-workflows):
        # standalone base; the six phase capabilities (setup..bugfix) plus
        # 'documentation' — added by wiki-maintenance's documenter-wiring part
        # so that plugin's enhance can target capability: documentation (the
        # deferred half of part-1 DC-1).
        dw = by["development-lifecycle"]
        self.assertTrue(dw.standalone)
        self.assertEqual(dw.requires, [])
        self.assertEqual(dw.capabilities,
                         ["developer-workflows", "development-lifecycle",
                          "setup", "plan", "work", "review", "release", "bugfix", "documentation"])
        dw_cmds = {p.name for p in dw.primitives if p.kind == "command"}
        self.assertLessEqual({"setup", "plan", "work"}, dw_cmds)
        # developer-safety (part 3/6): standalone, enhances development-lifecycle
        # (the first real enhances edge), carries the 3 control hooks.
        ds = by["developer-safety"]
        self.assertTrue(ds.standalone)
        self.assertEqual(ds.requires, [])
        self.assertEqual([e.group for e in ds.enhances], ["development-lifecycle"])
        ds_hooks = {p.name for p in ds.primitives if p.kind == "hook"}
        self.assertLessEqual({"kill-switch", "steer", "commit-on-stop"}, ds_hooks)
        # code-review (part 4/6): standalone, capability-targeted enhances edge,
        # carries the adversarial-reviewer agents.
        cr = by["code-review"]
        self.assertTrue(cr.standalone)
        self.assertEqual(cr.requires, [])
        self.assertEqual(len(cr.enhances), 1)
        self.assertEqual((cr.enhances[0].group, cr.enhances[0].capability),
                         ("development-lifecycle", "review"))
        cr_agents = {p.name for p in cr.primitives if p.kind == "agent"}
        self.assertLessEqual({"adversarial-reviewer", "adversarial-reviewer-cross"}, cr_agents)
        # a primitive's shape (commit-on-stop now lives in developer-safety)
        prims = {p.name: p for p in by["developer-safety"].primitives}
        self.assertEqual(prims["commit-on-stop"].kind, "hook")
        self.assertIn("claude-code", prims["commit-on-stop"].supported_hosts)

    def test_supports_host(self):
        by = {g.slug: g for g in src_model.load_groups(_ROOT / "src")}
        self.assertTrue(by["development-lifecycle"].supports("claude-code"))

    def test_deterministic_order(self):
        a = [g.slug for g in src_model.load_groups(_ROOT / "src")]
        b = [g.slug for g in src_model.load_groups(_ROOT / "src")]
        self.assertEqual(a, b)
        self.assertEqual(a, sorted(a))

    def test_missing_src_returns_empty(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(src_model.load_groups(Path(t) / "nope"), [])

    def test_backcompat_no_enhances_capabilities(self):
        # a group that declares neither field → both default to empty lists.
        # (Real src plugins all declare capabilities since AG Phase-2 hygiene, so
        # src_model's backcompat default is exercised with a synthetic fixture; the
        # non-empty requirement is enforced by lint_src, not the model.)
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "bare").mkdir(parents=True)
            (src / "bare" / "group.yaml").write_text(
                "name: Bare\ndescription: d\nrequires: []\nstandalone: true\n",
                encoding="utf-8")
            by = {g.slug: g for g in src_model.load_groups(src)}
            self.assertEqual(by["bare"].enhances, [])
            self.assertEqual(by["bare"].capabilities, [])

    def test_enhances_and_capabilities_roundtrip(self):
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "wf").mkdir(parents=True)
            (src / "wf" / "group.yaml").write_text(
                "name: WF\nrequires: []\nstandalone: true\n"
                "capabilities: [review, work]\n", encoding="utf-8")
            # enhancer A — dict form, capability-targeted
            (src / "cr").mkdir(parents=True)
            (src / "cr" / "group.yaml").write_text(
                "name: CR\nrequires: []\nstandalone: true\n"
                "enhances:\n  - group: wf\n    capability: review\n"
                "    effect: dispatches reviewers\n", encoding="utf-8")
            # enhancer B — string shorthand
            (src / "sf").mkdir(parents=True)
            (src / "sf" / "group.yaml").write_text(
                "name: SF\nrequires: []\nstandalone: true\n"
                "enhances: [wf]\n", encoding="utf-8")
            by = {g.slug: g for g in src_model.load_groups(src)}
            # the enhancee's declared capabilities
            self.assertEqual(by["wf"].capabilities, ["review", "work"])
            self.assertEqual(by["wf"].enhances, [])
            # dict-form enhance round-trips group + capability + effect
            self.assertEqual(len(by["cr"].enhances), 1)
            e = by["cr"].enhances[0]
            self.assertEqual((e.group, e.capability, e.effect),
                             ("wf", "review", "dispatches reviewers"))
            # string-shorthand enhance: group only, capability None
            self.assertEqual(len(by["sf"].enhances), 1)
            self.assertEqual(by["sf"].enhances[0].group, "wf")
            self.assertIsNone(by["sf"].enhances[0].capability)
            # standalone + enhances coexist (invariant untouched)
            self.assertTrue(by["cr"].standalone)
            self.assertEqual(by["cr"].requires, [])

    def test_command_discovery(self):
        # `commands/*.md` are discovered as `command` primitives (the surface
        # the developer-workflows phase commands ride on). Root is the .md file
        # itself (like an agent), so the emitter copies the single file.
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "wf" / "commands").mkdir(parents=True)
            (src / "wf" / "group.yaml").write_text(
                "name: WF\nrequires: []\nstandalone: true\n", encoding="utf-8")
            (src / "wf" / "commands" / "plan.md").write_text(
                "---\nname: plan\nkind: command\n"
                "supported_hosts: [claude-code, antigravity]\ndescription: d\n---\n"
                "# plan\n", encoding="utf-8")
            by = {g.slug: g for g in src_model.load_groups(src)}
            prims = {p.name: p for p in by["wf"].primitives}
            self.assertIn("plan", prims)
            cmd = prims["plan"]
            self.assertEqual(cmd.kind, "command")
            self.assertEqual(cmd.root, src / "wf" / "commands" / "plan.md")
            self.assertEqual(cmd.supported_hosts, ["claude-code", "antigravity"])

    def test_snippet_discovery(self):
        # `snippets/*.md` are discovered as `snippet` primitives (the AGENTS.md /
        # CLAUDE.md-fragment kind). Root is the .md file itself (like an agent),
        # so the emitter copies the single file.
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "sf" / "snippets").mkdir(parents=True)
            (src / "sf" / "group.yaml").write_text(
                "name: SF\nrequires: []\nstandalone: true\n", encoding="utf-8")
            (src / "sf" / "snippets" / "no-coauthor.md").write_text(
                "---\nname: no-coauthor\nkind: snippet\n"
                "supported_hosts: [claude-code, antigravity]\ndescription: d\n---\n"
                "Do not add a Co-Authored-By trailer.\n", encoding="utf-8")
            by = {g.slug: g for g in src_model.load_groups(src)}
            prims = {p.name: p for p in by["sf"].primitives}
            self.assertIn("no-coauthor", prims)
            sn = prims["no-coauthor"]
            self.assertEqual(sn.kind, "snippet")
            self.assertEqual(sn.root, src / "sf" / "snippets" / "no-coauthor.md")

    def test_real_tree_commands_in_expected_groups(self):
        # command primitives live in development-lifecycle (the phase commands),
        # code-review (the standalone /code-review), wiki
        # (recent-wiki-changes, folded in part 2; + wiki-watch, the part-4
        # claude-only scheduling entry), design (spec/interview-me/document-decision/
        # design — re-homed from development-lifecycle at AG Wave A rename 2
        # task 4), tokens (handoff-pack/token-audit), github-projects
        # (report-board-drift, the board-write-path task 6 scheduling entry —
        # mirrors wiki-watch's pattern), and diagnostics (/diagnose, wave-c-diagnostics).
        # No other group ships commands.
        groups = src_model.load_groups(_ROOT / "src")
        by = {g.slug: g for g in groups}
        cmd_groups = {g.slug for g in groups for p in g.primitives if p.kind == "command"}
        self.assertEqual(cmd_groups, {"development-lifecycle", "code-review", "design",
                                      "wiki", "tokens", "github-projects", "diagnostics"})
        dw_cmds = {p.name for p in by["development-lifecycle"].primitives if p.kind == "command"}
        self.assertIn("plan", dw_cmds)
        cr_cmds = {p.name for p in by["code-review"].primitives if p.kind == "command"}
        self.assertEqual(cr_cmds, {"code-review", "doubt", "simplify"})
        wm_cmds = {p.name for p in by["wiki"].primitives if p.kind == "command"}
        self.assertEqual(wm_cmds, {"recent-wiki-changes", "wiki-watch", "wiki-init"})


class TestBundleIgnore(unittest.TestCase):
    """R2.1 / cricketsBuild#3: a stray `.harness/` under a group's `scripts/`
    (or `templates/`) asset root must never leak into the emitted dist/."""

    def _fixture_group(self, root: Path) -> "src_model.Group":
        manifest = root / "fixture" / "group.yaml"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("name: F\ndescription: d\nstandalone: true\n", encoding="utf-8")
        return src_model.Group(
            slug="fixture", name="F", description="d", category="Coding",
            requires=[], standalone=True, manifest=manifest,
        )

    def test_planted_harness_dir_reproduces_the_gap_without_the_fix(self) -> None:
        # Direct reproduction of the pre-fix gap: bundle_ignore()'s patterns
        # alone (not the .harness fix) let a .harness/ dir through.
        old_patterns = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src_scripts = root / "fixture" / "scripts"
            (src_scripts / ".harness").mkdir(parents=True)
            (src_scripts / ".harness" / "PLAN.md").write_text("x", encoding="utf-8")
            (src_scripts / "real.py").write_text("x", encoding="utf-8")
            dest = root / "dist-fixture"
            shutil.copytree(src_scripts, dest, ignore=old_patterns)
            self.assertTrue((dest / ".harness").exists(), "reproduction fixture is wrong — .harness should leak pre-fix")

    def test_planted_harness_dir_excluded_after_the_fix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            group = self._fixture_group(root)
            src_scripts = root / "fixture" / "scripts"
            (src_scripts / ".harness").mkdir(parents=True)
            (src_scripts / ".harness" / "PLAN.md").write_text("x", encoding="utf-8")
            (src_scripts / "real.py").write_text("x", encoding="utf-8")
            plugin_dir = root / "dist" / "fixture"
            src_model.copy_group_scripts(group, plugin_dir)
            self.assertFalse((plugin_dir / "scripts" / ".harness").exists())
            self.assertTrue((plugin_dir / "scripts" / "real.py").exists())

    def test_planted_harness_dir_excluded_from_templates_too(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            group = self._fixture_group(root)
            src_templates = root / "fixture" / "templates"
            (src_templates / ".harness").mkdir(parents=True)
            (src_templates / "real.md").write_text("x", encoding="utf-8")
            plugin_dir = root / "dist" / "fixture"
            src_model.copy_group_templates(group, plugin_dir)
            self.assertFalse((plugin_dir / "templates" / ".harness").exists())
            self.assertTrue((plugin_dir / "templates" / "real.md").exists())


if __name__ == "__main__":
    unittest.main()
