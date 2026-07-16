"""Regression tests for wiki_publish_transform.py's asset-link rewriting.

Same bug shape confirmed live 2026-07-16 in agentm's sibling copy of this
script (independent implementation here, not parity-checked against
agentm's): a bare, extension-less page link — GitHub Wiki's other page-
link convention alongside the `.md`-suffixed form, pervasive throughout
this wiki — was rewritten into a broken raw.githubusercontent.com URL by
an overly broad "any non-.md relative href is an asset" rule.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wiki_publish_transform import rewrite_asset_links


class RewriteAssetLinksTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.wiki_root = Path(self._tmp.name)
        (self.wiki_root / "reference").mkdir()
        (self.wiki_root / "diagrams").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def _rewrite(self, text: str, page_rel: str) -> str:
        page_path = self.wiki_root / page_rel
        page_path.parent.mkdir(parents=True, exist_ok=True)
        return rewrite_asset_links(text, "alexherrero", "crickets", page_path, self.wiki_root)

    def test_bare_page_link_is_left_alone(self):
        # The real failure shape: a bare page-name link, no extension,
        # no directory prefix.
        text = "See [Capability resolver](Capability-Resolver) for details."
        out = self._rewrite(text, "reference/Reference.md")
        self.assertEqual(out, text)

    def test_md_suffixed_page_link_is_left_alone(self):
        text = "See [Capability resolver](Capability-Resolver.md) for details."
        out = self._rewrite(text, "reference/Reference.md")
        self.assertEqual(out, text)

    def test_relative_svg_asset_is_rewritten(self):
        text = "![diagram](diagrams/foo.svg)"
        out = self._rewrite(text, "reference/Reference.md")
        self.assertEqual(
            out,
            "![diagram](https://raw.githubusercontent.com/wiki/alexherrero/crickets/reference/diagrams/foo.svg)",
        )

    def test_relative_png_asset_is_rewritten(self):
        text = "![shot](images/screenshot.png)"
        out = self._rewrite(text, "how-to/Guide.md")
        self.assertEqual(
            out,
            "![shot](https://raw.githubusercontent.com/wiki/alexherrero/crickets/how-to/images/screenshot.png)",
        )

    def test_absolute_http_link_is_left_alone(self):
        text = "[repo](https://github.com/alexherrero/crickets)"
        out = self._rewrite(text, "reference/Reference.md")
        self.assertEqual(out, text)

    def test_link_inside_fenced_code_block_is_left_alone(self):
        text = "```\n![diagram](diagrams/foo.svg)\n```\n"
        out = self._rewrite(text, "reference/Reference.md")
        self.assertEqual(out, text)

    def test_href_escaping_wiki_tree_is_left_alone(self):
        text = "![x](../../../etc/passwd.png)"
        out = self._rewrite(text, "reference/Reference.md")
        self.assertEqual(out, text)


if __name__ == "__main__":
    unittest.main()
