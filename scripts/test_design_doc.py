#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/design_doc.py (V5-10 sibling #5).

The deterministic core behind the `/design` command: the `Status: final` hard
gate (`require_final`), the minimal stdlib-only frontmatter parser, and
harness-root resolution composed onto `resolve_plan`. Every test is hermetic —
docs are synthesized in throwaway temp dirs (never the real vault), and the
resolver is exercised through both backends (the `.harness/` fallback via
`resolver=None`, and a planted stub for the delegate branch) exactly as
`test_stage_plan.py` does, so no agentm clone is needed.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS = _ROOT / "src" / "developer-workflows" / "scripts"


def _load(name: str):
    src = _SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, src)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


dd = _load("design_doc")


def _doc(status_line: str, *, body: str = "# A design\n") -> str:
    """A minimal design doc with the given frontmatter status line."""
    return f"---\ntitle: A design\n{status_line}\nvisibility: confidential\n---\n\n{body}"


class TestRequireFinalPerState(unittest.TestCase):
    """`require_final` returns ok only for `final`; each other state its own refusal."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dd-final-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, status_line: str, name: str = "foo") -> Path:
        p = self.tmp / f"{name}.md"
        p.write_text(_doc(status_line), encoding="utf-8")
        return p

    def test_final_passes(self):
        ok, reason = dd.require_final(self._write("status: final"))
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_draft_refused_points_to_author(self):
        ok, reason = dd.require_final(self._write("status: draft"))
        self.assertFalse(ok)
        self.assertIn("draft", reason)
        self.assertIn("not 'final'", reason)
        self.assertIn("/design author", reason)

    def test_review_refused_mentions_review_pass(self):
        ok, reason = dd.require_final(self._write("status: review"))
        self.assertFalse(ok)
        self.assertIn("review", reason)
        self.assertIn("review pass", reason)
        self.assertIn("/design author", reason)

    def test_launched_refused_warns_about_orphaning(self):
        ok, reason = dd.require_final(self._write("status: launched"))
        self.assertFalse(ok)
        self.assertIn("launched", reason)
        self.assertIn("orphan", reason)

    def test_unknown_status_refused_not_repaired(self):
        ok, reason = dd.require_final(self._write("status: wibble"))
        self.assertFalse(ok)
        self.assertIn("wibble", reason)
        self.assertIn("recognized lifecycle", reason)

    def test_refusal_interpolates_the_slug(self):
        # The refusal names the actual doc slug so the operator can re-run /design
        # author against it directly.
        ok, reason = dd.require_final(self._write("status: draft", name="my-feature"))
        self.assertFalse(ok)
        self.assertIn("my-feature", reason)


class TestRequireFinalMalformed(unittest.TestCase):
    """Malformed / unreadable docs halt loudly — never auto-repaired."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dd-bad-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_missing_file_refused(self):
        ok, reason = dd.require_final(self.tmp / "nope.md")
        self.assertFalse(ok)
        self.assertIn("no design doc", reason)

    def test_no_frontmatter_refused(self):
        p = self.tmp / "plain.md"
        p.write_text("# Just a heading, no frontmatter\n", encoding="utf-8")
        ok, reason = dd.require_final(p)
        self.assertFalse(ok)
        self.assertIn("frontmatter", reason)
        self.assertIn("Not auto-repairing", reason)

    def test_frontmatter_without_status_refused(self):
        p = self.tmp / "nostatus.md"
        p.write_text("---\ntitle: A design\nvisibility: confidential\n---\n\nbody\n",
                     encoding="utf-8")
        ok, reason = dd.require_final(p)
        self.assertFalse(ok)
        self.assertIn("no 'status:'", reason)
        self.assertIn("Not auto-repairing", reason)


class TestParseFrontmatter(unittest.TestCase):
    """The minimal stdlib-only frontmatter parser: top-level scalars only."""

    def test_returns_none_without_a_block(self):
        self.assertIsNone(dd.parse_frontmatter("# no frontmatter here\n"))

    def test_parses_top_level_scalars(self):
        fm = dd.parse_frontmatter("---\nstatus: final\ntitle: Hi\n---\nbody\n")
        self.assertEqual(fm["status"], "final")
        self.assertEqual(fm["title"], "Hi")

    def test_skips_comments_and_nested_lines(self):
        fm = dd.parse_frontmatter(
            "---\n# a comment\nstatus: draft\nnested:\n  child: ignored\n---\nbody\n"
        )
        self.assertEqual(fm["status"], "draft")
        self.assertNotIn("child", fm)

    def test_strips_surrounding_quotes(self):
        fm = dd.parse_frontmatter('---\nstatus: "final"\n---\nx\n')
        self.assertEqual(fm["status"], "final")


class TestResolveHarnessRoot(unittest.TestCase):
    """Harness-root resolution composes `resolve_plan` — both backends."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dd-root-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_standalone_resolves_to_dot_harness(self):
        # Fallback: singleton PLAN.md is <root>/.harness/PLAN.md → its parent is
        # the harness root.
        rc, out, err = dd.resolve_harness_root(str(self.tmp), resolver=None)
        self.assertEqual(rc, 0, err)
        self.assertEqual(Path(out.strip()), self.tmp / ".harness")

    def test_delegate_tracks_resolver_not_dot_harness(self):
        # Agentm present: harness root is the parent of whatever PLAN.md the
        # resolver names (here a vault path) — proving we never re-derive .harness.
        stub = self.tmp / "stub_ok.py"
        stub.write_text(
            "import sys\n"
            "sys.stdout.write('/v/_harness/PLAN.md\\t/v/_harness/progress.md\\n')\n"
            "sys.exit(0)\n",
            encoding="utf-8",
        )
        rc, out, err = dd.resolve_harness_root(str(self.tmp), resolver=stub)
        self.assertEqual(rc, 0, err)
        self.assertEqual(Path(out.strip()), Path("/v/_harness"))
        self.assertNotIn(".harness", out)

    def test_resolver_refusal_propagates_no_root(self):
        # A located seam that exits non-zero is authoritative — surface it,
        # never a silent .harness fallback (Risk #7). The seam's stderr is
        # captured by the bridge internally; we verify the non-zero exit and
        # that no harness root is emitted (not the specific message text).
        stub = self.tmp / "stub_bad.py"
        stub.write_text(
            "import sys\n"
            "sys.stderr.write('dangling marker\\n')\n"
            "sys.exit(2)\n",
            encoding="utf-8",
        )
        rc, out, err = dd.resolve_harness_root(str(self.tmp), resolver=stub)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertNotEqual(err, "")  # error surfaced (message is bridge-generated)

    def test_confidential_path_composes_designs_subdir(self):
        rc, out, err = dd.confidential_design_path("my-doc", str(self.tmp), resolver=None)
        self.assertEqual(rc, 0, err)
        self.assertEqual(Path(out.strip()), self.tmp / ".harness" / "designs" / "my-doc.md")

    def test_published_path_is_wiki_designs_not_explanation(self):
        p = dd.published_design_path("my-doc", str(self.tmp))
        self.assertEqual(Path(p), self.tmp / "wiki" / "designs" / "my-doc.md")
        self.assertNotIn("explanation", p)  # crickets path, not agentm's


class TestGateCLI(unittest.TestCase):
    """The `gate` CLI: exit 0 on final, exit 2 + stderr otherwise."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dd-cli-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_gate_exit_zero_on_final(self):
        p = self.tmp / "ok.md"
        p.write_text(_doc("status: final"), encoding="utf-8")
        self.assertEqual(dd.main(["design_doc.py", "gate", str(p)]), 0)

    def test_gate_exit_two_on_draft(self):
        p = self.tmp / "wip.md"
        p.write_text(_doc("status: draft"), encoding="utf-8")
        self.assertEqual(dd.main(["design_doc.py", "gate", str(p)]), 2)


# Scaffold-only Detailed Design — exactly what the template seeds (heading +
# whole-line italic prompt + an HTML-comment block, no authored content). The
# gate must classify this as empty.
_SCAFFOLD = (
    "\n"
    "*The full design at the level a reader needs to evaluate it.*\n"
    "\n"
    "<!-- One subsection per major component of the design. -->\n"
)


def _design_with_dd(dd_body: str, *, trailing: str = "") -> str:
    """A `final` design whose `### Detailed Design` carries `dd_body`.

    `trailing` appends content *after* the Detailed Design section (under a fresh
    `##` heading) so a test can prove the section-boundary logic doesn't let a
    later section's content leak in and mask an empty Detailed Design.
    """
    return (
        "---\ntitle: A design\nstatus: final\nvisibility: confidential\n---\n\n"
        "## Design\n\n### Overview\n\nsome overview\n\n"
        f"### Detailed Design{dd_body}{trailing}"
    )


class TestDetailedDesignNonempty(unittest.TestCase):
    """`detailed_design_nonempty`: substantive content passes, scaffold refuses."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dd-detail-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, text: str, name: str = "doc") -> Path:
        p = self.tmp / f"{name}.md"
        p.write_text(text, encoding="utf-8")
        return p

    def test_scaffold_only_refused_as_too_sparse(self):
        ok, reason = dd.detailed_design_nonempty(self._write(_design_with_dd(_SCAFFOLD)))
        self.assertFalse(ok)
        self.assertIn("too sparse", reason)

    def test_scaffold_then_later_section_still_refused(self):
        # The next `##` heading bounds the section: a populated later section must
        # NOT mask an empty Detailed Design.
        text = _design_with_dd(
            _SCAFFOLD,
            trailing="\n## Alternatives Considered\n\nWe considered X and rejected it.\n",
        )
        ok, reason = dd.detailed_design_nonempty(self._write(text))
        self.assertFalse(ok)
        self.assertIn("too sparse", reason)

    def test_substantive_prose_passes(self):
        text = _design_with_dd("\n\nWe persist records in a table keyed by id.\n")
        ok, reason = dd.detailed_design_nonempty(self._write(text))
        self.assertTrue(ok, reason)
        self.assertEqual(reason, "")

    def test_subsection_heading_passes(self):
        # A `####` subsection is body (the split unit), not a section boundary —
        # its presence alone is enough content to translate.
        text = _design_with_dd("\n\n#### Data model\n\nschema details\n")
        ok, reason = dd.detailed_design_nonempty(self._write(text))
        self.assertTrue(ok, reason)

    def test_bare_subsection_heading_passes(self):
        # Even a bare `####` heading with no prose under it is a hangable part.
        text = _design_with_dd("\n\n#### Data model\n")
        ok, _ = dd.detailed_design_nonempty(self._write(text))
        self.assertTrue(ok)

    def test_whole_line_bold_is_content_not_scaffold(self):
        # `**bold**` lines start and end with `*` but are real content — only a
        # single-`*` italic prompt is scaffold (the `not startswith('**')` guard).
        text = _design_with_dd("\n\n**Invariant: ids are monotonic**\n")
        ok, _ = dd.detailed_design_nonempty(self._write(text))
        self.assertTrue(ok)

    def test_missing_section_refused(self):
        # A doc with no `### Detailed Design` heading at all.
        text = "---\ntitle: A\nstatus: final\n---\n\n## Design\n\n### Overview\n\nx\n"
        ok, reason = dd.detailed_design_nonempty(self._write(text))
        self.assertFalse(ok)
        self.assertIn("no '### Detailed Design'", reason)

    def test_missing_file_refused(self):
        ok, reason = dd.detailed_design_nonempty(self.tmp / "nope.md")
        self.assertFalse(ok)
        self.assertIn("no design doc", reason)

    def test_detailed_design_inside_fenced_code_block_refused(self):
        # Regression (post-review bugfix 2026-06-13): a `### Detailed Design`
        # heading appearing ONLY inside a fenced code example is not a real
        # authored section. The gate must refuse, not pass. Before the fix the
        # in-fence heading matched and the gate returned (True, '').
        text = (
            "---\ntitle: A\nstatus: final\nvisibility: confidential\n---\n\n"
            "## Design\n\n```markdown\n### Detailed Design\n\nexample text\n```\n\n"
            "## Notes\n\nno real DD section here\n"
        )
        ok, reason = dd.detailed_design_nonempty(self._write(text))
        self.assertFalse(ok)
        self.assertIn("no '### Detailed Design'", reason)

    def test_comment_only_with_hash_lines_refused(self):
        # Regression (post-review bugfix 2026-06-13): a comment-only Detailed
        # Design whose HTML comment contains a `##` line must be refused. Before
        # the fix the in-comment `##` was mistaken for the next heading, truncating
        # the body to an unterminated `<!--` the comment-stripper couldn't remove,
        # so the residue counted as content and the gate returned (True, '').
        text = _design_with_dd(
            "\n\n<!-- Example layout:\n## Component A\ndescribe it.\n-->\n",
            trailing="\n## Alternatives Considered\n\nWe weighed X.\n",
        )
        ok, reason = dd.detailed_design_nonempty(self._write(text))
        self.assertFalse(ok)
        self.assertIn("too sparse", reason)

    def test_detailed_design_only_inside_tilde_fence_refused(self):
        # Regression (post-review bugfix follow-on 2026-06-13): `~~~` fences are
        # code fences too (CommonMark). A `### Detailed Design` heading appearing
        # ONLY inside a `~~~` example block is not a real authored section. Before
        # this fix only ``` ``` fences were masked, so the in-fence heading matched
        # and the gate returned (True, '').
        text = (
            "---\ntitle: A\nstatus: final\nvisibility: confidential\n---\n\n"
            "## Design\n\nFollow this layout:\n\n"
            "~~~markdown\n### Detailed Design\n\n#### Component A\n*describe it*\n~~~\n\n"
            "## Notes\n\nno real DD section here\n"
        )
        ok, reason = dd.detailed_design_nonempty(self._write(text))
        self.assertFalse(ok)
        self.assertIn("no '### Detailed Design'", reason)

    def test_unterminated_comment_only_dd_refused(self):
        # Regression (post-review bugfix follow-on 2026-06-13): an HTML comment
        # opened with `<!--` but never closed is a comment to EOF — everything
        # after it is commented out. It must be masked for boundary detection AND
        # dropped from the residue. Before this fix the dangling comment was
        # neither masked nor stripped, so its text counted as content and a
        # comment-only Detailed Design returned (True, '').
        text = _design_with_dd(
            "\n\n<!-- One subsection per component (this comment is never closed)\n"
            "#### Component A\n",
            trailing="\n## Alternatives Considered\n\nWe weighed X.\n",
        )
        ok, reason = dd.detailed_design_nonempty(self._write(text))
        self.assertFalse(ok)
        self.assertIn("too sparse", reason)

    def test_detailed_design_only_inside_nested_fence_refused(self):
        # Regression (post-review bugfix follow-on 2026-06-13): a 4-backtick fence
        # wrapping an example 3-backtick block (the idiomatic way to *show* a fenced
        # block in Markdown) must stay fully masked. Before the CommonMark
        # fence-length fix the opener was truncated to 3 chars and the inner
        # 3-backtick line closed it early, un-masking an example `### Detailed
        # Design` that then matched as the real section.
        text = (
            "---\ntitle: A\nstatus: final\nvisibility: confidential\n---\n\n"
            "## Design\n\nAuthors should follow this template:\n\n"
            "````markdown\n```\n### Detailed Design\n\nDescribe each component here.\n"
            "````\n\n## Notes\n\nNo real Detailed Design section in this doc.\n"
        )
        ok, reason = dd.detailed_design_nonempty(self._write(text))
        self.assertFalse(ok)
        self.assertIn("no '### Detailed Design'", reason)

    def test_detailed_design_with_nested_fence_example_passes(self):
        # False-refuse guard for the fence-length fix: a *real* Detailed Design
        # whose body shows a nested 4-backtick fence example alongside prose is
        # substantive and must pass — the masking is for boundary detection only;
        # the body is still sliced from the original text.
        text = _design_with_dd(
            "\n\nWe persist records in a table keyed by id.\n\n"
            "````markdown\n```\nexample fenced block\n```\n````\n",
            trailing="\n## Alternatives Considered\n\nWe weighed X.\n",
        )
        ok, reason = dd.detailed_design_nonempty(self._write(text))
        self.assertTrue(ok, reason)


class TestDetailedDesignCLI(unittest.TestCase):
    """The `detailed-design` CLI: exit 0 on substantive, exit 2 on scaffold."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dd-detail-cli-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_exit_zero_on_substantive(self):
        p = self.tmp / "ok.md"
        p.write_text(_design_with_dd("\n\nReal prose under Detailed Design.\n"),
                     encoding="utf-8")
        self.assertEqual(dd.main(["design_doc.py", "detailed-design", str(p)]), 0)

    def test_exit_two_on_scaffold(self):
        p = self.tmp / "sparse.md"
        p.write_text(_design_with_dd(_SCAFFOLD), encoding="utf-8")
        self.assertEqual(dd.main(["design_doc.py", "detailed-design", str(p)]), 2)


if __name__ == "__main__":
    unittest.main()
