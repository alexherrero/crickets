#!/usr/bin/env python3
"""Tests for src/code-review/scripts/review_material.py.

The builder picks what a reviewer is shown, so these tests pin the three things
that decide whether a review is any good: the blocks are exactly ARTIFACT /
CONTRACT / RULES in that order, the rules come from the anchor first and then
from the repo docs by a fixed method, and the builder never takes the author's
reasoning or a guess at the bug as input.

Runs against a fixture git repo built in a temp directory. stdlib only.
"""
from __future__ import annotations

import importlib.util
import inspect
import io
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
_ROOT = _HERE.parent
_SCRIPT = _ROOT / "src" / "code-review" / "scripts" / "review_material.py"
_CROSS = _ROOT / "src" / "code-review" / "scripts" / "cross-review.sh"

from test_cross_review_degradation import _run_cross_review, _write_fake_agy  # noqa: E402


def _load():
    spec = importlib.util.spec_from_file_location("review_material", _SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules["review_material"] = m
    spec.loader.exec_module(m)
    return m


rm = _load()

AGENTS_MD = """# Agents

Commit messages never carry a Co-Authored-By trailer; the user is the sole author of intent, so a commit message is plain text only.

Pushes to main go through pull requests with required checks, and nobody pushes to the protected branch directly.

Vault locations are resolved at run time and never cached as literals in code, config or memory.
"""

SPEC_MD = """# Spec: Message formatter

**Profile:** build

## Goal

Commit messages are formatted in one place.

## Done when

- `pytest` passes with 0 failures

## Rules

- No Co-Authored-By trailer on commits — source: AGENTS.md § Commit messages
- Helpers use the standard library only — source: CLAUDE.md

## Not doing

none

## Open questions

none
"""

PLAN_MD = """---
parent_design_doc: wiki/designs/x.md
---

# Plan: thing

## Constraints

- Keep helpers stdlib only.
- A step that changes a plugin bumps its version.

## Locked design calls

- **Tiers:** default, high and wording, chosen by one flag.
- Never open a worktree without authority.
  This one wraps onto a second line.
"""

BEFORE = "def format_commit_message(subject):\n    return subject\n"
AFTER = ("def format_commit_message(subject, trailer=''):\n"
         "    return subject + trailer\n")


def _git_env() -> dict:
    """No host git config: settings like core.quotePath or diff.noprefix change what git prints."""
    return dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
                GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com",
                GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, env=_git_env(), check=True, capture_output=True)


class Fixture(unittest.TestCase):
    """A repo with AGENTS.md, one commit, and a second commit that edits
    src/commit_msg.py."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        _git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "AGENTS.md").write_text(AGENTS_MD, encoding="utf-8")
        (self.repo / "src").mkdir()
        (self.repo / "src" / "commit_msg.py").write_text(BEFORE, encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "first")
        (self.repo / "src" / "commit_msg.py").write_text(AFTER, encoding="utf-8")
        _git(self.repo, "commit", "-q", "-am", "second")
        self.spec = self.repo / "spec.md"
        self.spec.write_text(SPEC_MD, encoding="utf-8")
        self.plan = self.repo / "plan.md"
        self.plan.write_text(PLAN_MD, encoding="utf-8")

    def run_cli(self, *argv: str, cwd: "Path | None" = None, path_prefix: "Path | None" = None):
        out, err = io.StringIO(), io.StringIO()
        saved_path = os.environ["PATH"]
        if path_prefix is not None:
            os.environ["PATH"] = f"{path_prefix}{os.pathsep}{saved_path}"
        try:
            with redirect_stdout(out), redirect_stderr(err):
                code = rm.main(["--repo-root", str(cwd or self.repo), *argv])
        finally:
            os.environ["PATH"] = saved_path
        return code, out.getvalue(), err.getvalue()

    def rules_of(self, text: str) -> "list[str]":
        return text.split("=== RULES ===\n", 1)[1].rstrip("\n").splitlines()


class BlockShapeTests(Fixture):
    def test_the_blocks_are_exactly_artifact_contract_rules_in_order(self):
        code, out, _ = self.run_cli("--range", "HEAD~1..HEAD", "--contract", "Format commit messages.",
                                    "--anchor", str(self.spec))
        self.assertEqual(code, 0)
        headers = [l for l in out.splitlines() if re.fullmatch(r"=== [A-Z]+ ===", l)]
        self.assertEqual(headers, ["=== ARTIFACT ===", "=== CONTRACT ===", "=== RULES ==="])
        self.assertTrue(out.startswith("=== ARTIFACT ===\n"))
        artifact, rest = out.split("\n=== CONTRACT ===\n")
        contract, rules = rest.split("\n=== RULES ===\n")
        self.assertIn("diff --git a/src/commit_msg.py b/src/commit_msg.py", artifact)
        self.assertEqual(contract.strip(), "Format commit messages.")
        self.assertTrue(rules.startswith("- "))

    def test_a_missing_contract_is_stated_not_dropped(self):
        _, out, _ = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(self.spec))
        self.assertIn("=== CONTRACT ===\n(none given)\n", out)

    def test_contract_can_come_from_a_file(self):
        f = self.repo / "contract.txt"
        f.write_text("From a file.\n", encoding="utf-8")
        _, out, _ = self.run_cli("--range", "HEAD~1..HEAD", "--contract-file", str(f))
        self.assertIn("=== CONTRACT ===\nFrom a file.\n", out)

    def test_the_working_tree_is_an_artifact_source(self):
        (self.repo / "src" / "commit_msg.py").write_text(AFTER + "# edited\n", encoding="utf-8")
        _, out, _ = self.run_cli("--worktree")
        self.assertIn("+# edited", out)

    def test_the_working_tree_includes_a_new_file_git_does_not_track_yet(self):
        # #287: `git diff HEAD` never lists an untracked path, so a task that adds a new
        # module sent its reviewers an empty ARTIFACT before it was committed.
        (self.repo / "src" / "new_module.py").write_text("def new_module():\n    return 42\n", encoding="utf-8")
        code, out, _ = self.run_cli("--worktree")
        self.assertEqual(code, 0)
        artifact = out.split("\n=== CONTRACT ===\n", 1)[0]
        self.assertIn("src/new_module.py", artifact)
        self.assertIn("+def new_module():", artifact)
        self.assertIn("src/new_module.py", rm.changed_paths(artifact))

    def test_the_working_tree_leaves_out_ignored_files(self):
        (self.repo / ".gitignore").write_text("build/\n", encoding="utf-8")
        (self.repo / "build").mkdir()
        (self.repo / "build" / "out.txt").write_text("generated\n", encoding="utf-8")
        _, out, _ = self.run_cli("--worktree")
        self.assertNotIn("build/out.txt", out)
        self.assertIn(".gitignore", out)  # itself untracked, so it is part of the change

    def test_a_change_with_nothing_in_it_is_refused_loudly(self):
        # A clean tree or an empty range must never reach a reviewer as an empty artifact.
        # The fixture leaves spec.md and plan.md untracked; commit them so the tree is clean.
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "anchors")
        code, out, err = self.run_cli("--worktree")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("nothing to review", err)
        code, _, err = self.run_cli("--range", "HEAD..HEAD")
        self.assertEqual(code, 2)
        self.assertIn("nothing to review", err)

    def test_a_file_list_shows_text_and_names_an_asset_with_its_size(self):
        (self.repo / "art.png").write_bytes(b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR" + b"\0" * 20)
        _, out, _ = self.run_cli("--files", "src/commit_msg.py", "art.png")
        # A Windows checkout writes CRLF; the material shows a file as it is, so compare lines.
        self.assertIn("--- src/commit_msg.py ---\n" + AFTER.rstrip(), out.replace("\r\n", "\n"))
        self.assertRegex(out, r"--- art\.png ---\n\(binary asset, \d+ bytes; not shown\)")

    def test_a_file_that_does_not_exist_is_a_usage_error(self):
        code, out, err = self.run_cli("--files", "nope.py")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("file not found", err)

    @unittest.skipIf(os.name == "nt", "the fake gh is a shell script")
    def test_a_pr_diff_comes_from_gh(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            gh = bin_dir / "gh"
            gh.write_text('#!/bin/sh\nprintf "%s\\n" "diff --git a/x.py b/x.py" "+added_by_pr"\n',
                          encoding="utf-8")
            gh.chmod(0o755)
            code, out, err = self.run_cli("--pr", "7", path_prefix=bin_dir)
        self.assertEqual(code, 0, err)
        self.assertIn("+added_by_pr", out)

    def test_a_bad_range_is_a_usage_error_with_the_reason(self):
        code, _, err = self.run_cli("--range", "nope..HEAD")
        self.assertEqual(code, 2)
        self.assertIn("failed", err)


def _diff(repo: Path, *args: str) -> str:
    """git's own diff output, so each case is the text git really prints."""
    return subprocess.run(["git", "diff", "--no-color", *args], cwd=repo, env=_git_env(),
                          capture_output=True, text=True, encoding="utf-8", check=True).stdout


class GeneratedFilesTests(Fixture):
    """A file the repo marks linguist-generated (a built copy of a source file)
    is left out of a diff's ARTIFACT, and the run says so on stderr."""

    def setUp(self):
        super().setUp()
        (self.repo / ".gitattributes").write_text("dist/** linguist-generated=true\n", encoding="utf-8")
        (self.repo / "dist").mkdir()
        (self.repo / "dist" / "commit_msg.py").write_text(BEFORE, encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "generated copy")

    def test_a_generated_copy_is_left_out_and_named(self):
        (self.repo / "src" / "commit_msg.py").write_text(AFTER + "# edited\n", encoding="utf-8")
        (self.repo / "dist" / "commit_msg.py").write_text(AFTER + "# edited\n", encoding="utf-8")
        code, out, err = self.run_cli("--worktree")
        self.assertEqual(code, 0, err)
        artifact = out.split("\n=== CONTRACT ===\n", 1)[0]
        self.assertIn("diff --git a/src/commit_msg.py b/src/commit_msg.py", artifact)
        self.assertNotIn("dist/commit_msg.py", artifact)
        self.assertIn("left out 1 generated file(s)", err)
        self.assertIn("dist/commit_msg.py", err)

    def test_a_change_to_generated_files_alone_is_refused_with_the_reason(self):
        (self.repo / "dist" / "commit_msg.py").write_text(AFTER, encoding="utf-8")
        code, out, err = self.run_cli("--worktree")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("every file the working tree changes is generated", err)

    def test_without_the_attribute_nothing_is_left_out(self):
        # git reads .gitattributes from the index when the file is gone from the tree,
        # so the removal is committed.
        _git(self.repo, "rm", "-q", ".gitattributes")
        _git(self.repo, "commit", "-q", "-m", "no attributes")
        (self.repo / "dist" / "commit_msg.py").write_text(AFTER, encoding="utf-8")
        artifact, dropped = rm.drop_generated(rm.artifact_from_worktree(self.repo), self.repo)
        self.assertEqual(dropped, [])
        self.assertIn("dist/commit_msg.py", artifact)

    def test_a_file_list_is_never_filtered(self):
        _, out, err = self.run_cli("--files", "dist/commit_msg.py")
        self.assertIn("--- dist/commit_msg.py ---", out)
        self.assertNotIn("generated", err)


class GoverningDesignTests(Fixture):
    """A rule that lives in the design governing the changed files reaches RULES:
    the re-test's misses had their deciding rule in a design page, not AGENTS.md."""

    LOCKED = "Commit trailers are parsed from the last paragraph only, never from the body."
    DESIGN_PARA = ("The commit_msg gate rejects a message whose trailer block names an agent "
                   "as co-author, and it reads trailers with git interpret-trailers.")

    def _design(self, name: str, governs: str, status: str = "launched", body: str = "") -> Path:
        folder = self.repo / "wiki" / "designs"
        folder.mkdir(parents=True, exist_ok=True)
        page = folder / name
        page.write_text(f"---\nstatus: {status}\n{governs}\n---\n\n# {name}\n\n"
                        f"## Objective\n\nThe objective paragraph says nothing about the change at all.\n\n"
                        f"{body}", encoding="utf-8")
        return page

    def _body(self) -> str:
        return (f"## Design\n\n{self.DESIGN_PARA}\n\n### Sub\n\n- A bullet in a subsection about "
                f"commit_msg trailers is its own paragraph.\n\n## Locked design calls\n\n- {self.LOCKED}\n\n"
                f"## Amendment log\n\nAn amendment about commit_msg trailers is history, not a rule here.\n")

    def _rules(self, *extra: str):
        code, out, err = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(self.plan), *extra)
        self.assertEqual(code, 0, err)
        return out.split("=== RULES ===", 1)[1], err

    def test_the_governing_designs_locked_calls_and_design_section_reach_rules(self):
        self._design("code.md", "governs: [src/]", body=self._body())
        rules, err = self._rules()
        self.assertIn(self.LOCKED, rules)
        self.assertIn("(source: code.md)", rules)
        self.assertIn("reads trailers with git interpret-trailers", rules)
        self.assertNotIn("history, not a rule", rules)
        self.assertNotIn("objective paragraph", rules)
        self.assertIn("rules also from the design(s) code.md", err)

    def test_locked_calls_come_before_the_ranked_paragraphs(self):
        self._design("code.md", "governs: [src/]", body=self._body())
        rules, _ = self._rules()
        self.assertLess(rules.index(self.LOCKED), rules.index("interpret-trailers"))

    def test_a_design_that_governs_nothing_changed_or_is_a_draft_is_left_out(self):
        self._design("other.md", "governs: [docs/]", body=self._body())
        self._design("draft.md", "governs: [src/]", status="draft", body=self._body())
        rules, err = self._rules()
        self.assertNotIn(self.LOCKED, rules)
        self.assertNotIn("rules also from", err)

    def test_governs_forms_and_specificity(self):
        self.assertEqual(rm._governs("governs:\n  - src/a.py\n  - 'scripts/emit_*.py'\nx: 1"),
                         ["src/a.py", "scripts/emit_*.py"])
        self.assertEqual(rm._governs('governs: [src/, "b.py"]'), ["src/", "b.py"])
        self.assertEqual(rm._governs("governs: []"), [])
        self.assertTrue(rm._governs_match("scripts/emit_*.py", "scripts/emit_claude.py"))
        self.assertTrue(rm._governs_match("src", "src/commit_msg.py"))
        self.assertFalse(rm._governs_match("src", "srcx/commit_msg.py"))
        self._design("broad.md", "governs: ['src/**', 'scripts/**']")
        self._design("narrow.md", "governs:\n  - src/commit_msg.py")
        self._design("tie.md", "governs: [src/commit_msg.py]")
        # A broad design speaks only for a path nothing narrower governs.
        self.assertEqual([p.name for p in rm.governing_designs(self.repo, ["src/commit_msg.py"])],
                         ["narrow.md", "tie.md"])
        self.assertEqual([p.name for p in rm.governing_designs(
            self.repo, ["src/commit_msg.py", "scripts/x.py"])], ["narrow.md", "tie.md", "broad.md"])

    def test_design_paragraphs_are_capped_and_locked_calls_are_not(self):
        paras = "".join(f"The commit_msg trailer rule number {i} says something about commit_msg trailers.\n\n"
                        for i in range(rm.MAX_DESIGN_PARAGRAPHS + 5))
        locked = "".join(f"- Locked commit_msg call {i}.\n" for i in range(rm.MAX_DESIGN_PARAGRAPHS + 2))
        self._design("code.md", "governs: [src/]",
                     body=f"## Design\n\n{paras}## Locked design calls\n\n{locked}")
        rules, _ = self._rules()
        self.assertEqual(rules.count("trailer rule number"), rm.MAX_DESIGN_PARAGRAPHS)
        self.assertEqual(rules.count("Locked commit_msg call"), rm.MAX_DESIGN_PARAGRAPHS + 2)

    def test_a_diff_path_is_read_against_the_repo_root_not_the_current_directory(self):
        # Found by the cross-model review: run with --repo-root from another checkout
        # that holds the same relative path, the path resolved into that checkout.
        self._design("code.md", "governs: [src/]")
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "src").mkdir()
            (Path(tmp) / "src" / "commit_msg.py").write_text("x = 1\n", encoding="utf-8")
            saved = Path.cwd()
            os.chdir(tmp)
            try:
                found = rm.governing_designs(self.repo, ["src/commit_msg.py"])
            finally:
                os.chdir(saved)
        self.assertEqual([p.name for p in found], ["code.md"])

    def test_a_design_named_outside_the_repo_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "living.md"
            vault.write_text("---\nstatus: active\n---\n\n" + self._body(), encoding="utf-8")
            rules, err = self._rules("--design", str(vault))
        self.assertIn(self.LOCKED, rules)
        self.assertIn("(source: living.md)", rules)

    def test_a_deleted_diff_path_is_matched_whatever_the_current_directory_holds(self):
        # Found by the cross-model review: a diff path is the repo's own even when the
        # file is gone from the repo and present where the command runs.
        self._design("code.md", "governs: [src/]", body=self._body())
        _git(self.repo, "rm", "-q", "src/commit_msg.py")
        _git(self.repo, "commit", "-q", "-m", "delete")
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "src").mkdir()
            (Path(tmp) / "src" / "commit_msg.py").write_text("x = 1\n", encoding="utf-8")
            saved = Path.cwd()
            os.chdir(tmp)
            try:
                rules, err = self._rules()
            finally:
                os.chdir(saved)
        self.assertIn(self.LOCKED, rules)

    def test_a_file_list_given_as_absolute_paths_is_matched(self):
        self._design("code.md", "governs: [src/]", body=self._body())
        code, out, err = self.run_cli("--files", str(self.repo / "src" / "commit_msg.py"),
                                      "--anchor", str(self.plan))
        self.assertEqual(code, 0, err)
        self.assertIn(self.LOCKED, out.split("=== RULES ===", 1)[1])

    def test_a_living_designs_current_design_section_is_read(self):
        # Found by the cross-model review: /design writes a living design's body under
        # "Current design", not "Design".
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "living.md"
            vault.write_text("---\nstatus: active\n---\n\n## Objective\n\nShort.\n\n"
                             f"## Current design\n\n- {self.DESIGN_PARA}\n\n## Open questions\n\nnone\n",
                             encoding="utf-8")
            rules, _ = self._rules("--design", str(vault))
        self.assertIn("reads trailers with git interpret-trailers", rules)
        self.assertIn("(source: living.md)", rules)

    def test_a_missing_named_design_is_a_note_not_an_error(self):
        rules, err = self._rules("--design", str(self.repo / "nope.md"))
        self.assertIn("nope.md was not found", err)

    def test_the_anchor_is_not_read_twice_as_a_design(self):
        page = self._design("code.md", "governs: [src/]", body=self._body())
        code, out, err = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(page))
        self.assertEqual(code, 0, err)
        self.assertEqual(out.count(self.LOCKED), 1)
        self.assertNotIn("rules also from", err)


class EmbeddedRepoTests(Fixture):
    """#288 item 2: an untracked folder that is its own repository is listed by
    `ls-files --others` as `dir/` and gives `git diff --no-index` nothing to read."""

    def _embedded(self, name: str, commit: bool = True) -> None:
        sub = self.repo / name
        sub.mkdir()
        _git(sub, "init", "-q", "-b", "main")
        if commit:
            (sub / "a.py").write_text("a = 1\n", encoding="utf-8")
            _git(sub, "add", "-A")
            _git(sub, "commit", "-q", "-m", "inner")

    def test_an_embedded_repository_alone_is_reviewed_as_a_gitlink(self):
        self._embedded("vendor lib")
        code, out, err = self.run_cli("--worktree")
        self.assertEqual(code, 0, err)
        self.assertIn("new file mode 160000", out)
        self.assertIn("+Subproject commit ", out)
        artifact = out.split("\n=== CONTRACT ===\n", 1)[0]
        self.assertIn("vendor lib", rm.changed_paths(artifact))

    def test_the_real_index_is_left_alone(self):
        self._embedded("sub")
        rm.artifact_from_worktree(self.repo)
        staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=self.repo,
                                env=_git_env(), capture_output=True, text=True, check=True)
        self.assertEqual(staged.stdout, "")

    def test_an_embedded_repository_with_no_commit_gives_nothing(self):
        self._embedded("empty", commit=False)
        (self.repo / "new.py").write_text("n = 1\n", encoding="utf-8")
        paths = rm.changed_paths(rm.artifact_from_worktree(self.repo))
        self.assertIn("new.py", paths)
        self.assertNotIn("empty", paths)


class ChangedPathsTests(Fixture):
    """#288: a path with a space, or one git prints quoted (non-ASCII, a quote, a
    backslash), still reaches the rule matching under its real name."""

    def _commit(self, *names: str) -> None:
        for name in names:
            p = self.repo / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"# {name}\nvalue = 1\n", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "named files")

    def test_untracked_files_with_a_space_or_a_non_ascii_name(self):
        (self.repo / "café.py").write_text("x = 1\n", encoding="utf-8")
        (self.repo / "sp dir").mkdir()
        (self.repo / "sp dir" / "f g.py").write_text("y = 2\n", encoding="utf-8")
        paths = rm.changed_paths(rm.artifact_from_worktree(self.repo))
        self.assertIn("café.py", paths)
        self.assertIn("sp dir/f g.py", paths)

    def test_an_edit_to_a_tracked_file_git_quotes(self):
        self._commit("sp café.py")
        (self.repo / "sp café.py").write_text("value = 2\n", encoding="utf-8")
        diff = _diff(self.repo, "HEAD")
        self.assertIn('"a/sp caf\\303\\251.py"', diff)  # the case really is quoted
        self.assertEqual(rm.changed_paths(diff), ["sp café.py"])

    @unittest.skipIf(os.name == "nt", "Windows file names cannot hold a quote or a backslash")
    def test_an_edit_to_a_name_with_a_quote_or_a_backslash(self):
        self._commit('café "q".py', "back\\slash.py")
        (self.repo / 'café "q".py').write_text("value = 2\n", encoding="utf-8")
        (self.repo / "back\\slash.py").write_text("value = 3\n", encoding="utf-8")
        diff = _diff(self.repo, "HEAD")
        self.assertIn('"a/caf\\303\\251 \\"q\\".py"', diff)  # the case really is quoted
        self.assertEqual(rm.changed_paths(diff), ["back\\slash.py", 'café "q".py'])

    def test_a_pure_rename_into_a_folder_named_b(self):
        # `rename to` lines carry the bare path: no a/ or b/ prefix to strip.
        self._commit("sp dir/f g.py")
        (self.repo / "b").mkdir()
        _git(self.repo, "mv", "sp dir/f g.py", "b/café.py")
        diff = _diff(self.repo, "-M", "--cached")
        self.assertIn("rename to ", diff)
        self.assertNotIn("+++ ", diff)
        self.assertEqual(rm.changed_paths(diff), ["b/café.py"])

    def test_a_deleted_file_is_named_by_its_old_side(self):
        self._commit("sp dir/f g.py", "café.py")
        _git(self.repo, "rm", "-q", "sp dir/f g.py", "café.py")
        diff = _diff(self.repo, "--cached")
        self.assertEqual(rm.changed_paths(diff), ["café.py", "sp dir/f g.py"])

    @unittest.skipIf(os.name == "nt", "Windows checkouts do not track the executable bit")
    def test_a_mode_only_change_is_named_from_the_header(self):
        self._commit("sp dir/f g.py", "café.py")
        for name in ("sp dir/f g.py", "café.py"):
            (self.repo / name).chmod(0o755)
        diff = _diff(self.repo, "HEAD")
        self.assertIn("new mode", diff)
        self.assertNotIn("+++ ", diff)
        self.assertEqual(rm.changed_paths(diff), ["café.py", "sp dir/f g.py"])

    @unittest.skipIf(os.name == "nt", "Windows file names are UTF-16; the case is git's raw UTF-8 output")
    def test_raw_names_when_quote_path_is_off(self):
        # core.quotePath=false prints non-ASCII names raw, U+2028 and U+0085 included.
        names = ["a\u2028b.py", "c\x85d.py", "e f.py"]
        for name in names:
            (self.repo / name).write_text("x = 1\n", encoding="utf-8")
        _git(self.repo, "add", "-N", *names)
        diff = subprocess.run(["git", "-c", "core.quotePath=false", "diff", "--no-color", "HEAD"],
                              cwd=self.repo, env=_git_env(), capture_output=True, text=True,
                              encoding="utf-8", check=True).stdout
        self.assertIn("+++ b/a\u2028b.py", diff)
        self.assertEqual(rm.changed_paths(diff), names)

    def test_the_operators_git_config_does_not_change_what_is_read(self):
        # review_material pins git's output: a host diff.noprefix or core.quotePath=false
        # would otherwise drop the a/ b/ prefixes and the quotes changed_paths() reads.
        (self.repo / "café.py").write_text("x = 1\n", encoding="utf-8")
        host = self.repo / "host.gitconfig"
        host.write_text("[core]\n\tquotePath = false\n[diff]\n\tnoprefix = true\n\tmnemonicPrefix = true\n",
                        encoding="utf-8")
        saved = os.environ.get("GIT_CONFIG_GLOBAL")
        os.environ["GIT_CONFIG_GLOBAL"] = str(host)
        try:
            artifact = rm.artifact_from_range("HEAD~1..HEAD", self.repo)
            worktree = rm.artifact_from_worktree(self.repo)
        finally:
            if saved is None:
                os.environ.pop("GIT_CONFIG_GLOBAL")
            else:
                os.environ["GIT_CONFIG_GLOBAL"] = saved
        self.assertIn("diff --git a/src/commit_msg.py b/src/commit_msg.py", artifact)
        self.assertIn('"b/caf\\303\\251.py"', worktree)
        self.assertIn("café.py", rm.changed_paths(worktree))

    def test_plain_paths_read_as_before(self):
        diff = _diff(self.repo, "HEAD~1..HEAD")
        self.assertEqual(rm.changed_paths(diff), ["src/commit_msg.py"])


class RuleSourceTests(Fixture):
    def test_a_specs_rules_come_first_with_their_sources(self):
        _, out, _ = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(self.spec))
        rules = self.rules_of(out)
        self.assertEqual(rules[0], "- No Co-Authored-By trailer on commits (source: AGENTS.md § Commit messages)")
        self.assertEqual(rules[1], "- Helpers use the standard library only (source: CLAUDE.md)")

    def test_a_plans_locked_calls_then_constraints_are_always_included(self):
        _, out, _ = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(self.plan))
        rules = self.rules_of(out)
        self.assertEqual(rules[0], "- Tiers: default, high and wording, chosen by one flag. (source: plan.md)")
        self.assertEqual(rules[1], "- Never open a worktree without authority. This one wraps onto a second line. "
                                   "(source: plan.md)")
        self.assertEqual(rules[2], "- Keep helpers stdlib only. (source: plan.md)")
        self.assertEqual(rules[3], "- A step that changes a plugin bumps its version. (source: plan.md)")

    def test_a_likeness_list_is_an_anchor_rule_too(self):
        spec = SPEC_MD.replace("## Not doing", "## Likeness list\n\n- Reads like the reference\n\n## Not doing")
        f = self.repo / "s2.md"
        f.write_text(spec, encoding="utf-8")
        _, out, _ = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(f))
        self.assertIn("- Reads like the reference (source: s2.md)", self.rules_of(out))

    def test_matching_repo_doc_paragraphs_follow_the_anchors_rules(self):
        _, out, _ = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(self.plan))
        rules = self.rules_of(out)
        self.assertEqual(len(rules), 5)
        self.assertTrue(rules[4].startswith("- Commit messages never carry a Co-Authored-By trailer"))
        self.assertTrue(rules[4].endswith("(source: AGENTS.md)"))
        # The two paragraphs that share nothing with the change stay out.
        blob = "\n".join(rules)
        self.assertNotIn("protected branch", blob)
        self.assertNotIn("Vault locations", blob)

    def test_selection_is_deterministic_for_a_fixed_input(self):
        a = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(self.plan))[1]
        b = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(self.plan))[1]
        self.assertEqual(a, b)

    def test_a_rarer_shared_term_outranks_a_common_one(self):
        paras = [("AGENTS.md", "Alpha rule about the widget cache and its eviction policy."),
                 ("AGENTS.md", "Widget handling is described in many places across the widget code."),
                 ("AGENTS.md", "Widget naming follows the widget guide; widgets are lower case.")]
        ranked = rm.rank_doc_rules(paras, ["eviction", "widget"])
        self.assertEqual(ranked[0][2], paras[0][1])

    def test_terms_come_from_paths_and_changed_identifiers_only(self):
        diff = ("diff --git a/src/commit_msg.py b/src/commit_msg.py\n--- a/src/commit_msg.py\n"
                "+++ b/src/commit_msg.py\n@@ -1 +1 @@\n unchanged_context_word\n"
                "-def legacy_handler(x):\n+def FormatTrailer(subject):\n")
        terms = rm.terms_from(["src/commit_msg.py"], diff)
        for want in ("commit", "msg", "format", "trailer", "subject", "legacy", "handler"):
            self.assertIn(want, terms)
        self.assertNotIn("unchanged", terms)  # a context line is not a change
        self.assertNotIn("def", terms)        # stop word
        self.assertEqual(terms, sorted(terms))

    def test_an_import_line_in_claude_md_is_not_a_rule(self):
        (self.repo / "CLAUDE.md").write_text(
            "@AGENTS.md\n\nUse the commit trailer rule as written; commit text is plain and a trailer is banned.\n",
            encoding="utf-8")
        _, out, _ = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(self.plan))
        self.assertNotIn("@AGENTS.md", out)
        self.assertIn("(source: CLAUDE.md)", out)


class CapTests(Fixture):
    def test_the_line_cap_is_enforced_and_reported(self):
        code, out, err = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(self.plan),
                                      "--max-rule-lines", "2")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.rules_of(out)), 2)
        self.assertIn("dropped at the 2-line cap", err)

    def test_the_default_cap_is_forty_lines(self):
        many = "\n".join(f"- rule number {i} for the thing" for i in range(60))
        f = self.repo / "big.md"
        f.write_text(f"# Plan\n\n## Constraints\n\n{many}\n", encoding="utf-8")
        _, out, _ = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(f))
        self.assertEqual(len(self.rules_of(out)), 40)

    def test_the_byte_ceiling_cuts_rules_not_the_artifact(self):
        _, full, _ = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(self.plan))
        ceiling = len(full.encode("utf-8")) - 60
        code, out, err = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(self.plan),
                                      "--max-bytes", str(ceiling))
        self.assertEqual(code, 0)
        self.assertLessEqual(len(out.encode("utf-8")), ceiling)
        self.assertLess(len(self.rules_of(out)), len(self.rules_of(full)))
        self.assertIn("to stay under the", err)
        # The same artifact block, untouched.
        self.assertEqual(out.split("=== CONTRACT ===")[0], full.split("=== CONTRACT ===")[0])

    def test_an_artifact_alone_over_the_ceiling_leaves_rules_empty_and_says_so(self):
        code, out, err = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(self.plan),
                                      "--max-bytes", "50")
        self.assertEqual(code, 0)
        self.assertEqual(self.rules_of(out), ["(none — no room under the byte ceiling)"])
        self.assertIn("over the 50-byte ceiling", err)

    def test_zero_turns_the_ceiling_off(self):
        _, out, _ = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(self.plan), "--max-bytes", "0")
        self.assertEqual(len(self.rules_of(out)), 5)

    def test_tier_ceilings_match_cross_review_sh(self):
        text = _CROSS.read_text(encoding="utf-8")
        table = dict(re.findall(r"^\s*(default|high|wording)\)\s+MODEL=.*?MAX_MATERIAL_BYTES=(\d+)",
                                text, re.MULTILINE))
        self.assertEqual({k: int(v) for k, v in table.items()}, rm.TIER_CEILINGS)


class MissingAnchorTests(Fixture):
    def test_no_anchor_gives_empty_rules_with_a_reason_and_exit_0(self):
        code, out, _ = self.run_cli("--range", "HEAD~1..HEAD")
        self.assertEqual(code, 0)
        self.assertEqual(self.rules_of(out), [
            "(none — no anchor was given, so there is nothing to hold the change to)"])

    def test_an_anchor_path_that_is_not_a_file_gives_empty_rules_with_a_reason(self):
        code, out, _ = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(self.repo / "gone.md"))
        self.assertEqual(code, 0)
        (line,) = self.rules_of(out)
        self.assertTrue(line.startswith("(none — the anchor "))
        self.assertIn("gone.md was not found", line)

    def test_an_anchor_with_no_rules_and_no_matching_docs_says_so(self):
        f = self.repo / "bare.md"
        f.write_text("# Notes\n\nJust prose.\n", encoding="utf-8")
        (self.repo / "AGENTS.md").write_text("# A\n\nNothing relevant lives in this paragraph at all, sorry.\n",
                                             encoding="utf-8")
        _, out, _ = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(f))
        (line,) = self.rules_of(out)
        self.assertIn("bare.md states no rules and no repo doc paragraph matches the change", line)


class WhatItNeverReadsTests(Fixture):
    def test_the_builder_takes_no_reasoning_and_no_suspected_bug(self):
        params = set(inspect.signature(rm.build).parameters)
        # designs: more places rules come from, never the author's reasoning.
        self.assertEqual(params, {"artifact", "paths", "contract", "anchor_path", "repo_root",
                                  "designs", "max_rule_lines", "ceiling", "diff_text"})
        flags = set(re.findall(r"--[a-z-]+", rm._build_parser().format_help()))
        for banned in ("--reasoning", "--notes", "--suspect", "--bug", "--hint", "--focus"):
            self.assertNotIn(banned, flags)

    def test_a_reasoning_file_in_the_repo_never_reaches_the_material(self):
        harness = self.repo / ".harness"
        harness.mkdir()
        (harness / "reasoning.md").write_text("I think the bug is in trailer handling.\n", encoding="utf-8")
        (harness / "progress.md").write_text("trailer handling was tricky\n", encoding="utf-8")
        _, out, _ = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(self.plan))
        self.assertNotIn("I think the bug", out)
        self.assertNotIn("was tricky", out)

    def test_no_agentm_import_or_call(self):
        text = _SCRIPT.read_text(encoding="utf-8")
        for banned in ("agentm_bridge", "project_homes", "process_seam", "harness_memory",
                       "resolve_plan", "sibling_plugin"):
            self.assertNotIn(banned, text)

    def test_it_runs_with_no_agentm_and_no_vault_on_the_path(self):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("AGENTM", "MEMORY_"))}
        # -I ignores PYTHONUTF8, so ask for UTF-8 with -X: the child writes UTF-8 and the
        # parent reads it as UTF-8 on every OS (a Windows parent would decode cp1252).
        proc = subprocess.run(
            [sys.executable, "-I", "-X", "utf8", str(_SCRIPT), "--repo-root", str(self.repo),
             "--range", "HEAD~1..HEAD", "--anchor", str(self.spec)],
            capture_output=True, text=True, encoding="utf-8", timeout=30, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("=== RULES ===", proc.stdout)

    def test_the_rules_never_name_a_defect(self):
        _, out, _ = self.run_cli("--range", "HEAD~1..HEAD", "--anchor", str(self.plan))
        rules = "\n".join(self.rules_of(out)).lower()
        for word in ("bug", "defect", "suspect", "look for", "watch out", "is wrong"):
            self.assertNotIn(word, rules)


class CrossReviewAcceptsItTests(Fixture):
    def test_cross_review_takes_the_three_block_material_unchanged(self):
        _, material, _ = self.run_cli("--range", "HEAD~1..HEAD", "--contract", "Format commit messages.",
                                      "--anchor", str(self.spec))
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            prompt_log = bin_dir / "prompt.txt"
            _write_fake_agy(bin_dir, f'printf \'%s\' "$2" > "{prompt_log}"\necho "NO ISSUES FOUND"')
            result = _run_cross_review(material, path_prefix=bin_dir)
            self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")
            self.assertIn("NO ISSUES FOUND", result.stdout)
            seen = prompt_log.read_text(encoding="utf-8")
        tail = seen.split("=== REVIEW MATERIAL ===\n", 1)[1]
        self.assertEqual(tail.strip(), material.strip())


if __name__ == "__main__":
    unittest.main()
