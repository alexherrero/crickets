#!/usr/bin/env python3
"""Tests for the commit-msg-gate commit-msg hook
(`src/developer-safety/hooks/commit-msg-gate/`) — Consolidation ruling 4's
"Commit messages, go-forward" standard, shipped CONS-8.

Two layers, mirroring test_developer_safety_coauthor_guard.py's own split:

  - Unit tests against `commit_msg_gate.py`'s pure functions
    (`find_codenames` / `find_slop`), loaded by path since the hook dir name
    (`commit-msg-gate/`) isn't a valid Python package identifier. `find_slop`
    is exercised against a small in-test fixture rule list so this suite
    doesn't silently drift if the live voice-rules.json pack gains/loses
    rules later; one test additionally proves the *live* pack loads and a
    real warning-tier phrase from it ("this journey") is caught, so the
    reuse-not-fork wiring itself is covered too.
  - End-to-end subprocess tests via the `.sh` wrapper, mirroring
    test_developer_safety_coauthor_guard.py's convention (real subprocess,
    real fixture file). POSIX-only; the `.ps1` twin mirrors the behavior but
    has no test harness here, matching the repo's existing hook-test posture.

A final pair proves no regression against the existing coauthor-guard
hook: each hook is blind to the other's concern (a codename-shaped subject
doesn't confuse coauthor-guard's trailer strip; a Co-Authored-By trailer in
the body doesn't confuse commit-msg-gate's subject-only checks) and both can
run back-to-back on the same message file without conflict.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parent
_HOOK_DIR = REPO_ROOT / "src" / "developer-safety" / "hooks" / "commit-msg-gate"
_HOOK_SH = _HOOK_DIR / "commit-msg-gate.sh"
_HOOK_PY = _HOOK_DIR / "commit_msg_gate.py"
_COAUTHOR_GUARD_SH = (
    REPO_ROOT / "src" / "developer-safety" / "hooks" / "coauthor-guard" / "coauthor-guard.sh"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("commit_msg_gate", _HOOK_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


_MOD = _load_module() if _HOOK_PY.is_file() else None


# ── unit tests: find_codenames ──────────────────────────────────────────────
@unittest.skipUnless(_MOD is not None, f"{_HOOK_PY} not present")
class FindCodenamesTests(unittest.TestCase):
    def test_aa_and_c_family_both_flagged(self):
        hits = _MOD.find_codenames("AA5 C7: fake test commit")
        ids = {rule_id for rule_id, _ in hits}
        self.assertIn("codename-aa", ids)
        self.assertIn("codename-c", ids)

    def test_fin_family_flagged(self):
        hits = _MOD.find_codenames("fix: land FIN-2a's follow-through")
        self.assertTrue(any(rule_id == "codename-fin" for rule_id, _ in hits))

    def test_r_family_with_decimal_flagged(self):
        hits = _MOD.find_codenames("docs: fold R2.1 findings")
        self.assertTrue(any(rule_id == "codename-r" for rule_id, _ in hits))

    def test_g_family_flagged(self):
        hits = _MOD.find_codenames("chore: close out G12")
        self.assertTrue(any(rule_id == "codename-g" for rule_id, _ in hits))

    def test_wave_letter_flagged(self):
        hits = _MOD.find_codenames("feat: ship Wave A build")
        self.assertTrue(any(rule_id == "codename-wave" for rule_id, _ in hits))

    def test_wave_letter_flagged_without_following_noun(self):
        hits = _MOD.find_codenames("chore: close Wave C")
        self.assertTrue(any(rule_id == "codename-wave" for rule_id, _ in hits))

    def test_plan_slug_flagged(self):
        hits = _MOD.find_codenames("chore: reference PLAN-cons-8-commit-hook directly")
        self.assertTrue(any(rule_id == "codename-plan-slug" for rule_id, _ in hits))

    def test_roadmap_id_in_parens_is_exempt(self):
        hits = _MOD.find_codenames("feat: add the mapping table (V6-15)")
        self.assertEqual(hits, [])

    def test_plain_conventional_subject_is_clean(self):
        hits = _MOD.find_codenames("fix: correct off-by-one in the loader")
        self.assertEqual(hits, [])

    def test_r_pattern_does_not_match_r2d2_style_token(self):
        # A digit immediately followed by another letter (no word boundary
        # between them) must not be mistaken for the R<digits> codename shape.
        hits = _MOD.find_codenames("fix: rename the R2D2 fixture helper")
        self.assertEqual([h for h in hits if h[0] == "codename-r"], [])


# ── unit tests: find_slop (fixture rule list — pinned, not the live pack) ───
@unittest.skipUnless(_MOD is not None, f"{_HOOK_PY} not present")
class FindSlopFixtureTests(unittest.TestCase):
    _RULES = [
        {"id": "fixture-error-phrase", "severity": "error", "kind": "phrase",
         "pattern": "as an ai language model", "hint": "chat artifact"},
        {"id": "fixture-warning-phrase", "severity": "warning", "kind": "phrase",
         "pattern": "this journey", "hint": "stock phrase"},
        {"id": "fixture-warning-template", "severity": "warning", "kind": "template",
         "pattern": r"\b(the magic of)\b", "hint": "marketing boast"},
        {"id": "fixture-suggestion-word", "severity": "suggestion", "kind": "word",
         "pattern": "robust", "hint": "AI-tell adjective"},
        {"id": "fixture-warning-metric", "severity": "warning", "kind": "metric",
         "pattern": "em_dash_rate_per_1k", "hint": "document-level only"},
    ]

    def test_error_tier_phrase_blocks(self):
        findings = _MOD.find_slop("chore: as an AI language model I did the thing", self._RULES)
        self.assertTrue(any(f["id"] == "fixture-error-phrase" for f in findings))

    def test_warning_tier_phrase_blocks(self):
        findings = _MOD.find_slop("docs: begin this journey toward v2", self._RULES)
        self.assertTrue(any(f["id"] == "fixture-warning-phrase" for f in findings))

    def test_warning_tier_template_blocks(self):
        findings = _MOD.find_slop("feat: reveal the magic of caching", self._RULES)
        self.assertTrue(any(f["id"] == "fixture-warning-template" for f in findings))

    def test_suggestion_tier_word_is_allowed(self):
        findings = _MOD.find_slop("fix: a robust retry path", self._RULES)
        self.assertEqual(findings, [])

    def test_metric_kind_rule_never_applies_to_a_subject_line(self):
        findings = _MOD.find_slop("chore: — — — — — — — — — —", self._RULES)
        self.assertEqual(findings, [])

    def test_clean_subject_is_clean(self):
        findings = _MOD.find_slop("fix: correct off-by-one in the loader", self._RULES)
        self.assertEqual(findings, [])


# ── unit test: the live pack actually loads + a real warning-tier phrase trips
@unittest.skipUnless(_MOD is not None, f"{_HOOK_PY} not present")
class FindSlopLivePackTests(unittest.TestCase):
    def test_live_voice_rules_pack_loads_and_catches_a_real_warning_phrase(self):
        rules = _MOD._load_rules()
        self.assertTrue(rules, "the shared voice-rules.json pack should load in this checkout")
        findings = _MOD.find_slop("docs: begin this journey toward v2", rules)
        self.assertTrue(
            any(f["id"] == "voice-a2-this-journey" for f in findings),
            "expected the live pack's voice-a2-this-journey rule to fire",
        )


# ── end-to-end: the .sh wrapper via real subprocess ─────────────────────────
@unittest.skipIf(os.name == "nt", "bash hook -- POSIX only")
@unittest.skipUnless(_HOOK_SH.is_file(), f"{_HOOK_SH} not present")
class CommitMsgGateEndToEndTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.msg_file = Path(self._tmp.name) / "COMMIT_EDITMSG"

    def tearDown(self):
        self._tmp.cleanup()

    def _run_hook(self, hook_path: Path = _HOOK_SH):
        return subprocess.run(
            ["bash", str(hook_path), str(self.msg_file)],
            capture_output=True, text=True, timeout=10,
        )

    def test_codename_subject_is_rejected(self):
        self.msg_file.write_text("AA5 C7: fake test commit\n", encoding="utf-8")
        result = self._run_hook()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("codename", result.stderr.lower())

    def test_slop_vocabulary_subject_is_rejected(self):
        self.msg_file.write_text("docs: begin this journey toward v2\n", encoding="utf-8")
        result = self._run_hook()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("slop", result.stderr.lower())

    def test_clean_conventional_subject_passes(self):
        self.msg_file.write_text("fix: correct off-by-one in the loader\n", encoding="utf-8")
        result = self._run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_clean_subject_with_roadmap_id_in_parens_passes(self):
        self.msg_file.write_text(
            "docs(reference): rebuild the mapping table (V6-15)\n", encoding="utf-8",
        )
        result = self._run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_codename_in_body_only_is_not_checked(self):
        self.msg_file.write_text(
            "fix: correct off-by-one in the loader\n\nSee AA5 for background.\n",
            encoding="utf-8",
        )
        result = self._run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_message_file_is_a_no_op(self):
        result = subprocess.run(
            ["bash", str(_HOOK_SH), str(self.msg_file)],  # never written
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_works_when_installed_standalone_at_a_different_depth(self):
        # Regression lock for a real bug a live end-to-end install test
        # caught during CONS-8: copying just the .sh shim into .git/hooks/
        # without its sibling commit_msg_gate.py made the hook fail outright
        # ("no such file"), and commit_msg_gate.py's original repo-root
        # resolution (a fixed __file__.parents[N] walk) broke once the file
        # moved to a shallower depth. Simulate exactly that install shape:
        # copy BOTH files into a fresh dir (mimicking .git/hooks/) that is
        # NOT four levels under the repo root, and confirm the hook still
        # rejects a codename subject with its full rejection message (proving
        # rule_pack — resolved via `git rev-parse --show-toplevel`, not path
        # arithmetic — still loads from this shallower install location).
        with tempfile.TemporaryDirectory() as install_dir:
            install_dir = Path(install_dir)
            sh_dst = install_dir / "commit-msg"
            py_dst = install_dir / "commit_msg_gate.py"
            sh_dst.write_bytes(_HOOK_SH.read_bytes())
            py_dst.write_bytes(_HOOK_PY.read_bytes())
            sh_dst.chmod(0o755)

            self.msg_file.write_text("AA5 C7: fake test commit\n", encoding="utf-8")
            result = subprocess.run(
                ["bash", str(sh_dst), str(self.msg_file)],
                capture_output=True, text=True, timeout=10,
                cwd=str(REPO_ROOT),  # a real hook always runs inside the repo
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("codename", result.stderr.lower())


# ── regression: no conflict with the existing coauthor-guard hook ──────────
@unittest.skipIf(os.name == "nt", "bash hooks -- POSIX only")
@unittest.skipUnless(_HOOK_SH.is_file() and _COAUTHOR_GUARD_SH.is_file(),
                      "both hook .sh twins must be present")
class NoConflictWithCoauthorGuardTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.msg_file = Path(self._tmp.name) / "COMMIT_EDITMSG"

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, hook_path: Path):
        return subprocess.run(
            ["bash", str(hook_path), str(self.msg_file)],
            capture_output=True, text=True, timeout=10,
        )

    def test_coauthor_guard_ignores_a_codename_shaped_subject(self):
        # coauthor-guard only strips Co-Authored-By trailers -- a codename in
        # the subject is not its concern, and it must never reject a commit
        # (prepare-commit-msg hooks only edit, they don't gate).
        original = (
            "AA5 C7: fake test commit\n"
            "\n"
            "Co-Authored-By: Claude <noreply@example.com>\n"
        )
        self.msg_file.write_text(original, encoding="utf-8")
        result = self._run(_COAUTHOR_GUARD_SH)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = self.msg_file.read_text(encoding="utf-8")
        self.assertNotIn("Co-Authored-By", after)
        self.assertIn("AA5 C7: fake test commit", after)

    def test_commit_msg_gate_ignores_a_coauthor_trailer_in_the_body(self):
        # commit-msg-gate only reads the subject line -- a Co-Authored-By
        # trailer living in the body is coauthor-guard's concern, not this
        # hook's, and must not trip a rejection here.
        original = (
            "fix: correct off-by-one in the loader\n"
            "\n"
            "Co-Authored-By: Claude <noreply@example.com>\n"
        )
        self.msg_file.write_text(original, encoding="utf-8")
        result = self._run(_HOOK_SH)
        self.assertEqual(result.returncode, 0, result.stderr)
        # commit-msg-gate never rewrites the file, unlike coauthor-guard.
        self.assertIn("Co-Authored-By", self.msg_file.read_text(encoding="utf-8"))

    def test_both_hooks_run_back_to_back_without_conflict(self):
        # The realistic pipeline: git runs prepare-commit-msg (coauthor-guard)
        # then commit-msg (commit-msg-gate) on the same file, in that order.
        original = (
            "fix: correct off-by-one in the loader\n"
            "\n"
            "Co-Authored-By: Claude <noreply@example.com>\n"
        )
        self.msg_file.write_text(original, encoding="utf-8")
        prepare_result = self._run(_COAUTHOR_GUARD_SH)
        self.assertEqual(prepare_result.returncode, 0, prepare_result.stderr)
        commit_result = self._run(_HOOK_SH)
        self.assertEqual(commit_result.returncode, 0, commit_result.stderr)
        self.assertNotIn("Co-Authored-By", self.msg_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
