#!/usr/bin/env python3
"""Tests for rule_pack.py (PLAN-r3-voice-mechanism task 1).

Locks: schema validity, no-omission union coverage against the five source
stores voice.json named (docs-prose-style.md, base-style-guide.md:54, the
user-facing-prose lesson, the llm-tell-vocabulary lesson, writing-voice.md),
a malformed-fixture schema-validation failure, and the base-style-guide.md
banned-line round-trip renderer.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_RULE_PACK_SCRIPTS = (
    _HERE.parent / "src" / "wiki-maintenance" / "skills" / "diataxis-author" / "scripts"
)
sys.path.insert(0, str(_RULE_PACK_SCRIPTS))

import rule_pack  # noqa: E402

_PACK_PATH = _RULE_PACK_SCRIPTS.parent / "style" / "voice-rules.json"


class TestSchemaValidity(unittest.TestCase):
    def test_shipped_pack_loads_and_validates(self):
        pack = rule_pack.load_shipped_pack()
        self.assertIn("schema_version", pack)
        self.assertIn("era", pack)
        self.assertTrue(pack["rules"])

    def test_json_tool_exits_zero(self):
        result = subprocess.run(
            [sys.executable, "-m", "json.tool", str(_PACK_PATH)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_rule_has_required_fields(self):
        pack = rule_pack.load_shipped_pack()
        for r in pack["rules"]:
            for field in rule_pack._REQUIRED_RULE_FIELDS:
                self.assertIn(field, r, f"{r.get('id')} missing {field}")

    def test_no_duplicate_ids(self):
        pack = rule_pack.load_shipped_pack()
        ids = [r["id"] for r in pack["rules"]]
        self.assertEqual(len(ids), len(set(ids)))


class TestMalformedFixtureFails(unittest.TestCase):
    def test_missing_required_field_raises(self):
        bad = {
            "schema_version": 1, "era": "2026-07",
            "rules": [{"id": "x", "severity": "warning", "kind": "word", "pattern": "x"}],
        }
        with self.assertRaises(rule_pack.RulePackError):
            rule_pack.validate_rule_pack(bad)

    def test_invalid_severity_raises(self):
        bad = {
            "schema_version": 1, "era": "2026-07",
            "rules": [{"id": "x", "severity": "critical", "kind": "word",
                       "pattern": "x", "hint": "h", "weight": 1, "source-url": "u"}],
        }
        with self.assertRaises(rule_pack.RulePackError):
            rule_pack.validate_rule_pack(bad)

    def test_duplicate_id_raises(self):
        rule = {"id": "dupe", "severity": "warning", "kind": "word",
                "pattern": "x", "hint": "h", "weight": 1, "source-url": "u"}
        bad = {"schema_version": 1, "era": "2026-07", "rules": [rule, dict(rule)]}
        with self.assertRaises(rule_pack.RulePackError):
            rule_pack.validate_rule_pack(bad)

    def test_missing_top_level_field_raises(self):
        with self.assertRaises(rule_pack.RulePackError):
            rule_pack.validate_rule_pack({"rules": []})


class TestUnionCoverage(unittest.TestCase):
    """No omission against the five stores voice.json named, per Task 1 verification 1."""

    # Literal terms explicit in each store's own banned-term list (patterns/
    # rules that are prose-level constructions, not single terms — e.g. the
    # antithesis or prior-art-name-drop rules — are checked separately below.
    DOCS_PROSE_STYLE = {
        "groundbreaking", "deeply", "vital", "crucial", "truly", "this journey",
        "delve", "pioneering", "transformative", "visionary", "first-class",
        "seamless", "robust", "leverage", "comprehensive", "powerful",
        "cutting-edge", "load-bearing",
    }
    BASE_STYLE_GUIDE = {
        "groundbreaking", "deeply", "vital", "crucial", "truly", "delve",
        "pioneering", "transformative", "visionary", "this journey",
        "it should be noted that", "it is worth mentioning", "arguably",
        "essentially", "first-class", "seamless", "robust", "leverage",
        "comprehensive",
    }
    USER_FACING_PROSE = {
        "first-class", "seamless", "robust", "leverage", "comprehensive",
        "powerful", "delve", "structural backend", "execution layer",
        "substrate", "backbone",
    }
    LLM_TELL_VOCABULARY = {
        "first-class", "seamless", "robust", "leverage", "comprehensive",
        "load-bearing",
    }
    WRITING_VOICE = {
        "groundbreaking", "deeply", "vital", "crucial", "truly",
        "transformative", "visionary", "pioneering", "delve", "this journey",
        "first-class", "seamless", "robust", "leverage", "comprehensive",
        "load-bearing", "it should be noted that", "it is worth mentioning",
    }

    def setUp(self):
        self.pack = rule_pack.load_shipped_pack()
        self.literal_patterns = {
            r["pattern"].lower() for r in self.pack["rules"] if r["kind"] in ("word", "phrase")
        }

    def _assert_union_covered(self, store_name, terms):
        missing = {t for t in terms if t.lower() not in self.literal_patterns}
        self.assertFalse(missing, f"{store_name}: terms missing from rule pack: {missing}")

    def test_docs_prose_style_covered(self):
        self._assert_union_covered("docs-prose-style.md", self.DOCS_PROSE_STYLE)

    def test_base_style_guide_covered(self):
        self._assert_union_covered("base-style-guide.md:54", self.BASE_STYLE_GUIDE)

    def test_user_facing_prose_covered(self):
        self._assert_union_covered("user-facing-prose lesson", self.USER_FACING_PROSE)

    def test_llm_tell_vocabulary_covered(self):
        self._assert_union_covered("llm-tell-vocabulary lesson", self.LLM_TELL_VOCABULARY)

    def test_writing_voice_covered(self):
        self._assert_union_covered("writing-voice.md", self.WRITING_VOICE)

    def test_antithesis_and_prior_art_patterns_present(self):
        template_patterns = " ".join(
            r["pattern"] for r in self.pack["rules"] if r["kind"] == "template"
        )
        self.assertIn("not", template_patterns)
        self.assertIn("modeled after", template_patterns)


class TestOverlayHook(unittest.TestCase):
    def test_overlay_rule_overrides_shipped_id_by_narrower_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            gdir = vault / "projects" / "_global" / "wiki-style"
            gdir.mkdir(parents=True)
            (gdir / "voice-rules-overlay.json").write_text(json.dumps({
                "schema_version": 1, "era": "2026-07",
                "rules": [{"id": "voice-a4-delve", "severity": "error", "kind": "word",
                           "pattern": "delve", "hint": "overridden", "weight": 9,
                           "source-url": "overlay"}],
            }))
            composed = rule_pack.load_rule_pack(vault_path=vault)
            overridden = next(r for r in composed["rules"] if r["id"] == "voice-a4-delve")
            self.assertEqual(overridden["severity"], "error")
            self.assertEqual(overridden["source-url"], "overlay")

    def test_missing_overlay_graceful_skips(self):
        composed = rule_pack.load_rule_pack(vault_path=Path("/nonexistent-vault-path"))
        self.assertTrue(composed["rules"])


class TestBaseStyleBannedLineRenderer(unittest.TestCase):
    def test_renders_deterministic_comma_line(self):
        line = rule_pack.render_base_style_banned_line()
        self.assertTrue(line.startswith("banned: "))
        self.assertIn("delve", line)
        line2 = rule_pack.render_base_style_banned_line()
        self.assertEqual(line, line2)

    def test_only_word_and_phrase_kinds_render(self):
        pack = rule_pack.load_shipped_pack()
        line = rule_pack.render_base_style_banned_line(pack)
        template_only_terms = [r["pattern"] for r in pack["rules"] if r["kind"] == "template"]
        for t in template_only_terms:
            self.assertNotIn(t, line)

    def test_only_floor_eligible_terms_render(self):
        # Genre-scoped (user-facing-prose.md) and research-catalog-only
        # additions (tapestry, vibrant, ...) are NOT floor_eligible — they'd
        # trip check.py's untiered scanner on ordinary prose if promoted.
        pack = rule_pack.load_shipped_pack()
        line = rule_pack.render_base_style_banned_line(pack)
        non_floor_terms = [
            r["pattern"] for r in pack["rules"]
            if r["kind"] in ("word", "phrase") and not r.get("floor_eligible")
        ]
        self.assertTrue(non_floor_terms, "expected at least one non-floor-eligible term")
        for t in non_floor_terms:
            self.assertNotIn(t, line)
        self.assertIn("load-bearing", line)


class TestRoleNounCarveOutIsWritten(unittest.TestCase):
    """PLAN-r3-voice-mechanism task 5 verification 1 — the carve-out is a
    written rule in the shared store, not a private-memory-only reference."""

    def test_base_style_guide_carries_the_carve_out_clause(self):
        text = _HERE.parent / "src" / "wiki-maintenance" / "skills" / "diataxis-author" / "style" / "base-style-guide.md"
        content = text.read_text(encoding="utf-8")
        self.assertIn("Role-noun carve-out", content)
        self.assertIn("legitimate role noun", content)


if __name__ == "__main__":
    unittest.main()
