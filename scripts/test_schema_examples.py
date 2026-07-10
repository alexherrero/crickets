#!/usr/bin/env python3
"""A schema doc whose own examples don't pass its own lint is worse than no
examples at all (R2.1 / cricketsBuild#6). Extracts every `group.yaml`
example from `src/SCHEMA.md` and runs them all together through the real
`lint_src.lint_tree()` — together, not in isolation, because two of the
examples (the soft-composition pair) cross-reference each other via
`requires:`/`enhances:`, which lint_src validates against the sibling
groups actually present in the tree.
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCHEMA = _ROOT / "src" / "SCHEMA.md"

sys.path.insert(0, str(_HERE))
import lint_src  # noqa: E402

# A fenced yaml block, optionally preceded by a "### Example — `src/<slug>/group.yaml`"
# heading naming its slug, or (for blocks with no such heading) carrying its
# own leading "# src/<slug>/group.yaml" comment as the first line.
_HEADING_RE = re.compile(r"### Example.*?`src/([\w-]+)/group\.yaml`")
_LEADING_COMMENT_RE = re.compile(r"^#\s*src/([\w-]+)/group\.yaml")
_YAML_BLOCK_RE = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)


def _extract_group_yaml_examples() -> dict[str, str]:
    """Return {slug: yaml_body} for every group.yaml-shaped example (one that
    carries `standalone:`) in SCHEMA.md — the primitive-frontmatter example
    is a different schema, validated separately."""
    text = _SCHEMA.read_text(encoding="utf-8")
    examples: dict[str, str] = {}
    last_heading_slug: str | None = None
    pos = 0
    for m in re.finditer(r"### Example.*?\n|```yaml\n.*?\n```", text, re.DOTALL):
        chunk = m.group(0)
        if chunk.startswith("### Example"):
            hm = _HEADING_RE.search(chunk)
            last_heading_slug = hm.group(1) if hm else None
            continue
        body = _YAML_BLOCK_RE.match(chunk).group(1)
        if "standalone:" not in body:
            continue  # primitive frontmatter, not a group.yaml example
        cm = _LEADING_COMMENT_RE.match(body)
        slug = cm.group(1) if cm else last_heading_slug
        assert slug, f"could not determine the target slug for a SCHEMA.md example:\n{body}"
        examples[slug] = body
    return examples


class TestSchemaGroupYamlExamplesValidate(unittest.TestCase):
    def test_every_group_yaml_example_lints_clean_together(self) -> None:
        examples = _extract_group_yaml_examples()
        self.assertGreaterEqual(len(examples), 4, f"expected >= 4 group.yaml examples in SCHEMA.md, found {sorted(examples)}")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for slug, body in examples.items():
                group_dir = root / slug
                group_dir.mkdir()
                (group_dir / "group.yaml").write_text(body, encoding="utf-8")
            errors = lint_src.lint_tree(root)
            self.assertEqual(
                errors, [],
                f"SCHEMA.md's group.yaml examples fail lint_src.py:\n" + "\n".join(errors),
            )

    def test_extraction_actually_finds_the_known_examples(self) -> None:
        # A guard against the extractor itself silently finding zero/wrong
        # examples (which would make the test above vacuously pass).
        examples = _extract_group_yaml_examples()
        self.assertEqual(set(examples), {"github-ci", "privacy", "developer-workflows", "code-review"})


if __name__ == "__main__":
    unittest.main()
