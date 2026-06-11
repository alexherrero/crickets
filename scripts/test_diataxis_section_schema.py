#!/usr/bin/env python3
"""Tests for section-file shape v2 — the diataxis-author wiki composer's parser
(src/wiki-maintenance/skills/diataxis-author/scripts/section_schema.py) —
crickets wiki-composer part 1/4 (section-schema).

Covers the schema-v2 parse: the two optional frontmatter fields (`optional`,
`heading-variants`) with v1 defaults (Task 1); the strip rule — peel exactly the
first `SECTION `-prefixed opinion comment, preserve a later body comment (the
round-trip invariant) — plus the `<…>` placeholder convention (Task 2); and the
whole-library additive-over-v1 proof + the `safety` worked example (Task 3).
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SKILL_SCRIPTS = _ROOT / "src" / "wiki-maintenance" / "skills" / "diataxis-author" / "scripts"


def _load(name: str):
    if str(_SKILL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SKILL_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, _SKILL_SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


section_schema = _load("section_schema")


# A minimal v1 section file — no v2 fields (they must default off).
_V1_MINIMAL = """---
section: intro
reusable: true
applies-to: [home, reference]
---
<!-- SECTION intro — the opener the author fills -->

## Intro

Some scaffold text.
"""

# A v2 section file carrying both new fields.
_V2_FULL = """---
section: safety
reusable: true
applies-to: [component-overview]
optional: true
heading-variants: [Safety, Host gaps, Limitations]
---
<!-- SECTION safety — a concern callout -->

## Safety

- **<Guardrail>.** <name the enforcer + where it runs>.
"""

# An opinion comment followed by a BODY comment that must survive the strip.
_WITH_BODY_COMMENT = """---
section: demo
reusable: true
applies-to: [component-overview]
---
<!-- SECTION demo — opinion that must NOT publish -->

## Demo

<!-- a body comment that must survive the strip -->

- **<Slot>.** <fill me in>.
"""

# A file whose FIRST comment is not the opinion block — strip must not over-match.
_NON_OPINION_FIRST = """---
section: weird
reusable: true
applies-to: [x]
---
<!-- TODO: not an opinion block -->

## Weird

Body text.
"""


class TestFrontmatterFields(unittest.TestCase):
    """Task 1 — the two optional frontmatter fields + v1 defaults."""

    def test_v1_file_defaults_new_fields_off(self):
        sf = section_schema.parse_section(_V1_MINIMAL)
        self.assertFalse(sf.optional, "optional must default False on a v1 file")
        self.assertEqual(sf.heading_variants, [], "heading-variants absent → [] (fixed-heading fallback)")

    def test_v1_fields_still_parse(self):
        sf = section_schema.parse_section(_V1_MINIMAL)
        self.assertEqual(sf.section, "intro")
        self.assertTrue(sf.reusable)
        self.assertEqual(sf.applies_to, ["home", "reference"])

    def test_optional_true_parses_conditional(self):
        sf = section_schema.parse_section(_V2_FULL)
        self.assertTrue(sf.optional, "optional: true → conditional section")

    def test_heading_variants_parse_as_ordered_list(self):
        sf = section_schema.parse_section(_V2_FULL)
        self.assertEqual(
            sf.heading_variants,
            ["Safety", "Host gaps", "Limitations"],
            "heading-variants parses as an ORDERED list (order is the contract)",
        )

    def test_reusable_false_parses(self):
        sf = section_schema.parse_section(_V1_MINIMAL.replace("reusable: true", "reusable: false"))
        self.assertFalse(sf.reusable)


class TestStripRule(unittest.TestCase):
    """Task 2 — the strip rule + the placeholder convention."""

    def test_strips_first_section_opinion_comment(self):
        sf = section_schema.parse_section(_V2_FULL)
        self.assertEqual(sf.opinion, "SECTION safety — a concern callout")
        self.assertNotIn("a concern callout", sf.body, "opinion comment must not survive into the body")
        self.assertIn("## Safety", sf.body)

    def test_body_comment_after_opinion_is_preserved(self):
        # The round-trip invariant: only the single opinion comment comes off; a
        # later body comment is content and must survive (parent Data Integrity).
        sf = section_schema.parse_section(_WITH_BODY_COMMENT)
        self.assertEqual(sf.opinion, "SECTION demo — opinion that must NOT publish")
        self.assertNotIn("opinion that must NOT publish", sf.body)
        self.assertIn("<!-- a body comment that must survive the strip -->", sf.body)

    def test_placeholder_survives_parse(self):
        sf = section_schema.parse_section(_WITH_BODY_COMMENT)
        self.assertEqual(section_schema.find_placeholders(sf.body), ["<Slot>", "<fill me in>"])

    def test_first_non_opinion_comment_not_stripped(self):
        # Strip must not over-match: a non-`SECTION ` leading comment is left in
        # place (opinion is None). The strip-rule-thinness risk is enforcement's
        # to police, not the parser's to guess around.
        sf = section_schema.parse_section(_NON_OPINION_FIRST)
        self.assertIsNone(sf.opinion)
        self.assertIn("<!-- TODO: not an opinion block -->", sf.body)

    def test_find_placeholders_ignores_html_comments(self):
        self.assertEqual(section_schema.find_placeholders("<!-- not a placeholder --> <Real>"), ["<Real>"])


if __name__ == "__main__":
    unittest.main()
