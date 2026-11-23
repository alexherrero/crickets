#!/usr/bin/env python3
"""Crickets plan 105 (clear out the dead weight): what retired stays gone.

Each entry is a (group, kind, name) primitive or a script the plan deleted. The
test asserts it is absent from `src/` and from both hosts' `dist/` trees, so a
stale copy or a reintroduction fails the build. `generate.py check` separately
proves `dist/` mirrors `src/`; this test pins the retirement itself.
"""
from __future__ import annotations

import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
_CC = _ROOT / "dist" / "claude-code" / "plugins"
_AG = _ROOT / "dist" / "antigravity" / "plugins"

# Step 2: development-lifecycle's unused commands and agents.
RETIRED = [
    ("development-lifecycle", "command", "ci-cd"),
    ("development-lifecycle", "command", "launch"),
    ("development-lifecycle", "command", "deprecate"),
    ("development-lifecycle", "command", "observe"),
    ("development-lifecycle", "command", "orient"),
    ("development-lifecycle", "command", "queue-status-lite"),
    ("development-lifecycle", "agent", "project-manager"),
    ("development-lifecycle", "agent", "tech-lead"),
    ("development-lifecycle", "agent", "researcher"),
    # Step 3: design's and conventions' unused primitives.
    ("design", "command", "document-decision"),
    ("design", "skill", "adr"),
    ("conventions", "skill", "agentic-engineering"),
    ("conventions", "skill", "testing-conventions"),
    # Step 4: folded into the correctness rubric, or merged.
    ("code-review", "skill", "testing-strategy"),
    ("code-review", "skill", "security-review"),
    ("privacy", "skill", "privacy-review"),
    # Step 5: the wiki group collapses to wiki-author plus its commands.
    ("wiki", "skill", "diataxis-author"),
    ("wiki", "agent", "diataxis-evaluator"),
    ("wiki", "agent", "style-scope-evaluator"),
]

RETIRED_SCRIPTS = [
    ("development-lifecycle", "queue_status.py"),
    ("conventions", "conventions_domain.py"),
    # Step 6: no caller outside their own tests.
    ("development-lifecycle", "fanout_announcement.py"),
    ("development-lifecycle", "check-plan-grounding.py"),
    ("maintenance", "content_refresh.py"),
    ("maintenance", "cve_security_patch.py"),
    ("maintenance", "deps_currency.py"),
    ("maintenance", "tech_debt_inventory.py"),
    ("maintenance", "agentm_bridge.py"),
]


def _paths(group: str, kind: str, name: str) -> list[Path]:
    """Every place the primitive could live: its source and each host's emit."""
    if kind == "command":
        return [_SRC / group / "commands" / f"{name}.md",
                _CC / group / "commands" / f"{name}.md",
                _AG / group / "skills" / name / "SKILL.md"]
    if kind == "agent":
        return [_SRC / group / "agents" / f"{name}.md",
                _CC / group / "agents" / f"{name}.md",
                _AG / group / "agents" / f"{name}.md"]
    if kind == "skill":
        return [_SRC / group / "skills" / name / "SKILL.md",
                _CC / group / "skills" / name / "SKILL.md",
                _AG / group / "skills" / name / "SKILL.md"]
    raise ValueError(kind)


class TestRetiredPrimitivesAreGone(unittest.TestCase):
    def test_retired_primitives_absent_from_src_and_both_hosts(self):
        for group, kind, name in RETIRED:
            for path in _paths(group, kind, name):
                with self.subTest(primitive=f"{group}:{kind}:{name}", path=str(path.relative_to(_ROOT))):
                    self.assertFalse(path.exists(), f"retired {kind} {name!r} is back at {path}")

    def test_retired_scripts_absent_from_src_and_both_hosts(self):
        for group, script in RETIRED_SCRIPTS:
            for base in (_SRC, _CC, _AG):
                path = base / group / "scripts" / script
                with self.subTest(path=str(path.relative_to(_ROOT))):
                    self.assertFalse(path.exists(), f"retired script {script!r} is back at {path}")

    def test_open_is_the_one_project_entry_point(self):
        text = (_SRC / "development-lifecycle" / "commands" / "open.md").read_text(encoding="utf-8")
        # The command, not the orient_render.py script /open still calls.
        self.assertNotRegex(text, r"/orient(?![_\w])")
        self.assertNotIn("queue-status-lite", text)

    def test_testing_strategy_points_fold_into_the_correctness_rubric(self):
        # Step 4: testing-strategy's Prove-It, regression-proof and DAMP points
        # the missing-test lens did not cover, in both correctness reviewers.
        for rel in ("code-review/scripts/cross-review.sh", "code-review/agents/adversarial-reviewer.md"):
            text = (_SRC / rel).read_text(encoding="utf-8")
            with self.subTest(file=rel):
                self.assertIn("a claimed behaviour with no test that fails if the claim is false", text)
                self.assertIn("never shown to fail on the pre-fix code in the real failure's shape", text)
                self.assertIn("assertions too generic to name the behaviour", text)

    def test_security_auditor_stays_the_security_pass(self):
        self.assertTrue((_SRC / "code-review" / "agents" / "security-auditor.md").is_file())

    def test_pii_scrubber_carries_the_privacy_review(self):
        text = (_SRC / "privacy" / "skills" / "pii-scrubber" / "SKILL.md").read_text(encoding="utf-8")
        for practice in ("ASVS-8.3.6", "ASVS-8.3.4", "ASVS-8.2.3", "ASVS-8.2.1", "ASVS-8.3.1", "ASVS-8.1.1",
                         "OWASP Top 10 Privacy Risks — P1/P8", "OWASP Top 10 Privacy Risks — P2",
                         "ICO data-protection-by-design", "NIST Privacy Framework"):
            self.assertIn(practice, text)
        self.assertIn("privacy-taint-pack.yml", text)

    def test_the_wiki_group_is_one_skill_and_its_commands(self):
        wiki = _SRC / "wiki"
        self.assertEqual({p.name for p in (wiki / "skills").iterdir() if p.is_dir()}, {"wiki-author"})
        self.assertEqual({p.stem for p in (wiki / "agents").glob("*.md")}, {"documenter"})
        self.assertEqual({p.stem for p in (wiki / "commands").glob("*.md")},
                         {"wiki-watch", "wiki-init", "recent-wiki-changes"})
        skill = (wiki / "skills" / "wiki-author" / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(skill.split()), 1500)
        # the files the gates and the documenter read moved with it
        for rel in ("scripts/rule_pack.py", "scripts/vault_layout.py", "scripts/section_schema.py",
                    "scripts/composer.py", "scripts/style_resolver.py", "style/voice-rules.json",
                    "style/base-style-guide.md", "templates/README.md"):
            self.assertTrue((wiki / "skills" / "wiki-author" / rel).is_file(), rel)
        # the wiki-watch skill folded into the command, which now ships on both hosts
        self.assertFalse((_CC / "wiki" / "skills" / "wiki-watch").exists())
        self.assertTrue((_AG / "wiki" / "skills" / "wiki-watch" / "SKILL.md").is_file())
        cmd = (wiki / "commands" / "wiki-watch.md").read_text(encoding="utf-8")
        self.assertIn("wiki_watch_cycle.py run", cmd)
        self.assertIn("finalize_cycle", cmd)

    def test_the_bridge_has_no_workflow_persona_verb(self):
        text = (_SRC / "development-lifecycle" / "scripts" / "agentm_bridge.py").read_text(encoding="utf-8")
        self.assertNotIn("workflow-persona", text)
        self.assertNotIn("workflow_persona", text)

    def test_scripts_with_a_caller_stay(self):
        # Step 6 checked each of these and found a live caller: CI and check-all
        # (check_status_invariant), the session-cost hook (dreaming_trend_stub),
        # /work's 3-failure stop and /handoff (routing_table, classify_work_type,
        # escalation_tripwire), and coordinator-dispatch's manual pre-flight
        # (fanout_cost_gate).
        for rel in ("github-projects/scripts/check_status_invariant.py", "tokens/scripts/dreaming_trend_stub.py",
                    "tokens/scripts/routing_table.py", "tokens/scripts/classify_work_type.py",
                    "development-lifecycle/scripts/escalation_tripwire.py", "tokens/scripts/fanout_cost_gate.py"):
            self.assertTrue((_SRC / rel).is_file(), rel)

    def test_no_stale_model_ids_outside_pricing_history(self):
        # Step 7: the routing, advisor, agent and command surfaces name the
        # current Claude 5.x ids; pricing.py keeps the old rows for old
        # transcripts, and group.yaml version comments are history.
        import re
        stale = re.compile(r"\bclaude-(?:fable-5|sonnet-5|opus-4-8|sonnet-4-6|haiku-4-5)\b(?!-\d)")
        hits = []
        for path in _SRC.rglob("*"):
            if not path.is_file() or path.suffix not in (".py", ".md", ".sh", ".json", ".yml"):
                continue
            if path.name in ("pricing.py", "advisor_rider.py"):
                # recognition tables, not routing: they keep the older ids
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if stale.search(line):
                    hits.append(f"{path.relative_to(_ROOT)}:{n}")
        self.assertEqual(hits, [])

    def test_agents_pin_aliases_not_dated_ids(self):
        for agent in (_SRC / "development-lifecycle" / "agents").glob("*.md"):
            for line in agent.read_text(encoding="utf-8").splitlines():
                if line.startswith("model:"):
                    self.assertIn(line.split(":", 1)[1].strip(), {"sonnet", "opus", "haiku", "inherit"}, agent.name)

    def test_worker_is_the_one_coordinator_role_left(self):
        agents = {p.stem for p in (_SRC / "development-lifecycle" / "agents").glob("*.md")}
        self.assertIn("worker", agents)
        self.assertFalse(agents & {"project-manager", "tech-lead", "researcher"})


if __name__ == "__main__":
    unittest.main()
