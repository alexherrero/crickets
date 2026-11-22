#!/usr/bin/env python3
"""The old design standard is retired, and nothing still points at it (plan 103, step 12).

`/design` was a template walk with a draft -> review -> final gate, `translate` and
`sequence` verbs, three templates and five scripts. It is now one job: write or update
a living design note in the project's vault. These tests pin three things:

  1. what was removed is gone, from `src/` and from both built hosts, and no live
     surface (a command, a skill, a script, a wiki page, a root doc) still names it;
  2. what is left of `/design` calls the helper it says it calls, and writes where it
     says it writes;
  3. the things that read designs still find one: a repo `wiki/designs/` page through
     agentm's resolver, and a vault note through `vault_designs.py`.

History is not a live surface: CHANGELOG.md, comment lines in group.yaml and the
amendment logs in wiki/designs/ keep naming the old things, because they say what
happened.

stdlib only.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_DESIGN = _ROOT / "src" / "design"
_DL = _ROOT / "src" / "development-lifecycle"

REMOVED_FILES = (
    "scripts/architecture_rung.py", "scripts/design_doc.py", "scripts/design_finalize.py",
    "scripts/design_sequence.py", "scripts/design_template.py", "scripts/sibling_plugin.py",
    "templates/design-doc.md", "templates/abbreviated-design.md", "templates/architecture-hld.md",
)

# What a live surface must no longer say. `parent_design_doc` is a plan field that stays.
_NAMES = re.compile(
    r"design_template|design_finalize|design_sequence|architecture_rung|abbreviated-design|"
    r"architecture-hld|(?<![\w-])design-doc\.md|(?<![\w])design_doc(?:\.py)?\b|"
    r"/design (?:author|translate|sequence|finalize)\b|design (?:author|translate|sequence|finalize) <|"
    r"/design [a-z-]+ --rung|--rung (?:full|abbreviated|architecture)")

_TEXT_SUFFIXES = {".md", ".py", ".sh", ".ps1", ".yaml", ".yml", ".json", ".txt", ".toml"}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def _live_files():
    """Every file a reader or a running tool could meet, in the repo's live surfaces."""
    roots = [_ROOT / "src", _ROOT / "wiki"]
    for root in roots:
        for p in sorted(root.rglob("*")):
            if not p.is_file() or p.suffix not in _TEXT_SUFFIXES or "__pycache__" in p.parts:
                continue
            if root.name == "wiki" and "designs" in p.relative_to(root).parts[:1]:
                continue  # living designs keep their amendment logs
            yield p
    for p in sorted(_ROOT.glob("*.md")):
        if p.name != "CHANGELOG.md":
            yield p
    for p in sorted((_ROOT / "scripts").glob("*")):
        if p.is_file() and p.suffix in _TEXT_SUFFIXES and not p.name.startswith("test_"):
            yield p


def _live_lines(p: Path):
    for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if p.name == "group.yaml" and line.lstrip().startswith("#"):
            continue  # a group's version log is history
        yield n, line


class RemovedThingsAreGoneTests(unittest.TestCase):
    def test_the_files_are_gone_from_src_and_from_both_built_hosts(self):
        for rel in REMOVED_FILES:
            self.assertFalse((_DESIGN / rel).exists(), "src/design/%s still exists" % rel)
            for host in ("claude-code", "antigravity"):
                self.assertFalse((_ROOT / "dist" / host / "plugins" / "design" / rel).exists(),
                                 "dist/%s/plugins/design/%s still exists" % (host, rel))
        self.assertFalse((_DESIGN / "templates").exists())

    def test_their_tests_are_gone_too(self):
        for name in ("test_design_template", "test_design_finalize", "test_design_sequence", "test_design_doc",
                     "test_design_architecture_rung", "test_design_command",
                     "test_preflight_reconcile_frontmatter_re_parity"):
            self.assertFalse((_HERE / (name + ".py")).exists(), name)

    def test_no_live_surface_names_a_removed_command_template_or_script(self):
        hits = []
        for p in _live_files():
            for n, line in _live_lines(p):
                if _NAMES.search(line):
                    hits.append("%s:%d: %s" % (p.relative_to(_ROOT), n, line.strip()[:110]))
        self.assertEqual(hits, [], "\n".join(hits))

    def test_the_removal_is_recorded_as_a_major_bump_with_a_changelog_entry(self):
        gy = (_DESIGN / "group.yaml").read_text(encoding="utf-8")
        m = re.search(r"^version:\s*(\d+)\.", gy, re.MULTILINE)
        self.assertGreaterEqual(int(m.group(1)), 1)
        log = (_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        unreleased = log.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
        for needle in ("design_doc.py", "design_sequence.py", "abbreviated-design.md", "translate"):
            self.assertIn(needle, unreleased, "the CHANGELOG entry does not name %s" % needle)


class SlimDesignCommandTests(unittest.TestCase):
    def setUp(self):
        self.text = (_DESIGN / "commands" / "design.md").read_text(encoding="utf-8")

    def test_it_has_no_verbs_and_no_status_gate(self):
        for gone in ("translate", "sequence", "finalize", "Status: final", "draft → review", "--rung"):
            self.assertNotIn(gone, self.text, gone)

    def test_it_asks_agentm_where_designs_live_and_handles_no_answer(self):
        self.assertIn('scripts/project_homes.py" home designs', self.text)
        self.assertIn("**exit 3**", self.text)
        self.assertTrue((_DESIGN / "scripts" / "project_homes.py").is_file())

    def test_it_never_writes_to_wiki_designs(self):
        self.assertIn("never into `wiki/designs/`", self.text)

    def test_the_four_sections_and_the_amendment_entry_shape(self):
        for section in ("**Objective**", "**Current design**", "**Open questions**", "**Amendment log**"):
            self.assertIn(section, self.text)
        self.assertIn("*date · what changed · why not the alternative · the re-audit trigger*", self.text)
        self.assertIn("in the same edit", self.text)

    def test_the_frontmatter_it_writes_is_what_vault_designs_reads(self):
        vd = _load("vault_designs_for_retired_test", _DL / "scripts" / "vault_designs.py")
        block = re.search(r"```\n(---\n.*?\n---)\n```", self.text, re.DOTALL).group(1)
        block = block.replace("<slug>", "x").replace("<YYYY-MM-DD>", "2026-01-01")
        fm = vd.parse_frontmatter(block)
        for key in ("slug", "status", "updated", "aliases", "tags", "governs"):
            self.assertIn(key, fm, key)
        self.assertIn(fm["status"], vd.LIVE_STATUSES)

    def test_it_keeps_the_prose_pass_contract_the_callers_test_pins(self):
        for needle in ("PROSE-PASS-DEGRADED", "Claude-only", "never blocks", "prose_pass.py",
                       "No `--overlay` override needed"):
            self.assertIn(needle, self.text, needle)

    def test_it_is_built_for_both_hosts(self):
        self.assertTrue((_ROOT / "dist" / "claude-code" / "plugins" / "design" / "commands" / "design.md").is_file())
        self.assertTrue((_ROOT / "dist" / "antigravity" / "plugins" / "design" / "skills" / "design" / "SKILL.md").is_file())


class StillFindsADesignTests(unittest.TestCase):
    """/plan step 1b and the session-start hook read designs from two places."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.vd = _load("vault_designs_for_find_test", _DL / "scripts" / "vault_designs.py")
        self.bridge = _load("agentm_bridge_for_find_test", _DL / "scripts" / "agentm_bridge.py")

    def _resolver(self, repo: Path) -> Path:
        """A stand-in for agentm's governs resolver: it answers from the repo's wiki/designs/."""
        stub = self.tmp / "governs_resolver.py"
        stub.write_text(
            "import sys\nfrom pathlib import Path\n"
            "root = Path(sys.argv[sys.argv.index('--root') + 1]) if '--root' in sys.argv else Path('.')\n"
            "target = sys.argv[-1]\n"
            "for p in sorted((root / 'wiki' / 'designs').glob('*.md')):\n"
            "    if 'governs: [src/design]' in p.read_text() and target.startswith('src/design'):\n"
            "        print(p.relative_to(root)); sys.exit(0)\n"
            "sys.exit(1)\n", encoding="utf-8")
        return stub

    def test_a_repo_wiki_design_page_still_governs_through_the_resolver(self):
        repo = self.tmp / "repo-with-page"
        (repo / "wiki" / "designs").mkdir(parents=True)
        (repo / "wiki" / "designs" / "design.md").write_text(
            "---\nstatus: launched\ngoverns: [src/design]\n---\n# d\n", encoding="utf-8")
        out, rc = self.bridge.run_governing_design_resolve("src/design/commands/design.md", root=str(repo),
                                                           resolver=self._resolver(repo))
        self.assertEqual(rc, 0)
        self.assertEqual(Path(out), Path("wiki/designs/design.md"))  # the stub prints an OS-native path

    def test_a_repo_with_only_a_vault_note_resolves_through_vault_designs(self):
        repo = self.tmp / "repo-vault-only"
        repo.mkdir()
        vault = self.tmp / "vault-designs"
        vault.mkdir()
        note = vault / "design.md"
        note.write_text("---\ntype: design\nstatus: active\nslug: design\nupdated: 2026-11-21\n"
                        "aliases: [design]\ngoverns: [src/design]\n---\n# d\n", encoding="utf-8")
        # the repo has no wiki/designs/: the bridge answers "no page governs this" ...
        _out, rc = self.bridge.run_governing_design_resolve("src/design/commands/design.md", root=str(repo),
                                                            resolver=self._resolver(repo))
        self.assertEqual(rc, 1)
        # ... and the vault finds the note, by the path and by the area name.
        found = self.vd.find(self.vd.scan(vault), "src/design/commands/design.md")
        self.assertEqual(found.path, note)
        self.assertEqual(self.vd.find(self.vd.scan(vault), "design").path, note)

    def test_a_repo_with_neither_is_greenfield(self):
        repo = self.tmp / "greenfield"
        repo.mkdir()
        empty = self.tmp / "empty-vault-designs"
        empty.mkdir()
        _out, rc = self.bridge.run_governing_design_resolve("src/anything.py", root=str(repo),
                                                            resolver=self._resolver(repo))
        self.assertEqual(rc, 1)
        self.assertIsNone(self.vd.find(self.vd.scan(empty), "src/anything.py"))

    def test_plan_step_1b_names_both_lookups_and_the_greenfield_exits(self):
        plan = (_DL / "commands" / "plan.md").read_text(encoding="utf-8")
        self.assertIn("agentm_bridge.py\" governing-design <target>", plan)
        self.assertIn('scripts/vault_designs.py" find <target> --cwd .', plan)
        self.assertIn("**exit 3** (no vault, or agentm absent)", plan)

    def test_the_session_start_hook_lists_vault_designs_in_both_twins(self):
        hook = _DL / "hooks" / "harness-context-session-start"
        for name in ("harness-context-session-start.sh", "harness-context-session-start.ps1"):
            text = (hook / name).read_text(encoding="utf-8")
            self.assertIn("vault_designs.py", text, name)
            self.assertIn("--timeout 3", text, name)
            self.assertIn("Living designs (vault)", text, name)


if __name__ == "__main__":
    unittest.main()
