#!/usr/bin/env python3
"""Tests for scripts/src_model.py (crickets v3.0 #40, part 2)."""
from __future__ import annotations

import importlib.util
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
        self.assertEqual(set(by),
                         {"code-review", "developer", "developer-safety",
                          "developer-workflows", "github-ci", "pii", "wiki"})
        # composition (the original four, unchanged)
        self.assertEqual(by["github-ci"].requires, ["developer"])
        self.assertEqual(by["wiki"].requires, ["developer"])
        self.assertEqual(by["pii"].requires, [])
        self.assertTrue(by["pii"].standalone)
        self.assertFalse(by["github-ci"].standalone)
        # primitive counts: developer = 3 hooks + evaluator agent
        self.assertEqual(len(by["developer"].primitives), 4)
        self.assertEqual(len(by["pii"].primitives), 1)
        # the original four groups still hold 7 primitives between them (stable as
        # developer-workflows grows across its build parts)
        self.assertEqual(
            sum(len(by[s].primitives) for s in ("developer", "github-ci", "pii", "wiki")), 7)
        # developer-workflows (part 2/6): standalone, declares its capabilities,
        # carries phase commands (setup/plan/work this part; review/release/bugfix next).
        dw = by["developer-workflows"]
        self.assertTrue(dw.standalone)
        self.assertEqual(dw.requires, [])
        self.assertEqual(dw.capabilities,
                         ["setup", "plan", "work", "review", "release", "bugfix"])
        dw_cmds = {p.name for p in dw.primitives if p.kind == "command"}
        self.assertLessEqual({"setup", "plan", "work"}, dw_cmds)
        # developer-safety (part 3/6): standalone, enhances developer-workflows
        # (the first real enhances edge), carries the 3 control hooks.
        ds = by["developer-safety"]
        self.assertTrue(ds.standalone)
        self.assertEqual(ds.requires, [])
        self.assertEqual([e.group for e in ds.enhances], ["developer-workflows"])
        ds_hooks = {p.name for p in ds.primitives if p.kind == "hook"}
        self.assertLessEqual({"kill-switch", "steer", "commit-on-stop"}, ds_hooks)
        # code-review (part 4/6): standalone, capability-targeted enhances edge,
        # carries the adversarial-reviewer agents.
        cr = by["code-review"]
        self.assertTrue(cr.standalone)
        self.assertEqual(cr.requires, [])
        self.assertEqual(len(cr.enhances), 1)
        self.assertEqual((cr.enhances[0].group, cr.enhances[0].capability),
                         ("developer-workflows", "review"))
        cr_agents = {p.name for p in cr.primitives if p.kind == "agent"}
        self.assertLessEqual({"adversarial-reviewer", "adversarial-reviewer-cross"}, cr_agents)
        # a primitive's shape
        prims = {p.name: p for p in by["developer"].primitives}
        self.assertEqual(prims["commit-on-stop"].kind, "hook")
        self.assertIn("claude-code", prims["commit-on-stop"].supported_hosts)

    def test_supports_host(self):
        by = {g.slug: g for g in src_model.load_groups(_ROOT / "src")}
        self.assertTrue(by["developer"].supports("claude-code"))

    def test_deterministic_order(self):
        a = [g.slug for g in src_model.load_groups(_ROOT / "src")]
        b = [g.slug for g in src_model.load_groups(_ROOT / "src")]
        self.assertEqual(a, b)
        self.assertEqual(a, sorted(a))

    def test_missing_src_returns_empty(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(src_model.load_groups(Path(t) / "nope"), [])

    def test_backcompat_no_enhances_capabilities(self):
        # existing groups carry neither field → both default to empty lists
        by = {g.slug: g for g in src_model.load_groups(_ROOT / "src")}
        for slug in ("developer", "pii", "wiki", "github-ci"):
            self.assertEqual(by[slug].enhances, [])
            self.assertEqual(by[slug].capabilities, [])

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

    def test_real_tree_commands_belong_to_developer_workflows(self):
        # commands now exist in the real tree (the developer-workflows phase
        # commands); every discovered command primitive belongs to that group.
        groups = src_model.load_groups(_ROOT / "src")
        by = {g.slug: g for g in groups}
        for g in groups:
            for p in g.primitives:
                if p.kind == "command":
                    self.assertEqual(g.slug, "developer-workflows", p.name)
        dw_cmds = {p.name for p in by["developer-workflows"].primitives if p.kind == "command"}
        self.assertIn("plan", dw_cmds)


if __name__ == "__main__":
    unittest.main()
