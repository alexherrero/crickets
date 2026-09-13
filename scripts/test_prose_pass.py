#!/usr/bin/env python3
"""Tests for src/design/scripts/prose_pass.py (the cross-model prose pass,
step 1: Gemini simplifies).

Two layers, mirroring the cross-review.sh test pair:

  - Unit tests import the module directly and prove the pure pieces: the
    structural-contract validators (frontmatter / headings / table structure /
    Document History), the four-block prompt assembly, and the prompt-first
    agy argv ordering (flags placed before the prompt silently drop it — the
    hard-won invocation lesson this script inherits from cross-review.sh).
  - End-to-end tests drive main() against a fake agy wired in via
    `$PROSE_PASS_TEST_AGY_CMD` (a JSON argv-prefix list resolved by
    prose_pass.resolve_agy_cmd()) pointing directly at
    `[sys.executable, fake_agy_impl.py]` — plus a throwaway vault holding
    fake voice-pack files. No live LLM calls, no network, no dependency on
    the Antigravity CLI, and — deliberately — no OS shim script (a `.cmd`
    wrapper on Windows routes the invocation through cmd.exe's batch
    parser, which has no way to represent a literal newline inside a
    single command; a multi-line prompt gets truncated mid-argument before
    Python ever sees it. Invoking python.exe directly bypasses cmd.exe
    entirely, on every OS).

Covers the degradation contract: a missing `agy` exits 1 WITH the visible
"PROSE-PASS-DEGRADED: ..." stdout marker (an absent CLI must never silently
downgrade a cross-model pass into nothing); a structurally-violating reply
retries exactly once then exits 2; a missing fact-guard list is a usage
error, because the un-guarded pass is the failure mode the pattern exists to
prevent.

stdlib only.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_SCRIPTS_DIR = _REPO / "src" / "design" / "scripts"
_SCRIPT = _SCRIPTS_DIR / "prose_pass.py"

sys.path.insert(0, str(_SCRIPTS_DIR))
import prose_pass  # noqa: E402


SAMPLE_DOC = """\
---
name: sample-design
status: final
---

# Sample design

This design utilizes a mechanism whereby entries are subjected to decay.

## Decisions

| Decision | Call |
|---|---|
| storage | keep the vault as the canonical store of record |

## Document History

| Date | Change |
|---|---|
| 2026-07-01 | authored |
"""

# A faithful simplification: body prose + a table cell reworded; frontmatter,
# headings, table shapes, and Document History untouched.
SAMPLE_REVISED = SAMPLE_DOC.replace(
    "This design utilizes a mechanism whereby entries are subjected to decay.",
    "Entries decay.",
).replace(
    "keep the vault as the canonical store of record",
    "the vault is the store",
)


# ── unit: structural validators ──────────────────────────────────────────────
class FrontmatterTests(unittest.TestCase):
    def test_extracts_block_with_delimiters(self):
        fm = prose_pass.frontmatter_block(SAMPLE_DOC)
        self.assertEqual(fm, "---\nname: sample-design\nstatus: final\n---\n")

    def test_absent_frontmatter_is_none(self):
        self.assertIsNone(prose_pass.frontmatter_block("# No frontmatter\n"))


class HeadingTests(unittest.TestCase):
    def test_headings_in_order(self):
        self.assertEqual(
            prose_pass.heading_lines(SAMPLE_DOC),
            ["# Sample design", "## Decisions", "## Document History"],
        )

    def test_fenced_pseudo_heading_ignored(self):
        text = "# Real\n```\n# not a heading\n```\n"
        self.assertEqual(prose_pass.heading_lines(text), ["# Real"])


class TableStructureTests(unittest.TestCase):
    def test_cell_rewording_keeps_structure(self):
        self.assertEqual(
            prose_pass.table_structures(SAMPLE_DOC),
            prose_pass.table_structures(SAMPLE_REVISED),
        )

    def test_added_row_changes_structure(self):
        grown = SAMPLE_DOC.replace(
            "| storage | keep the vault as the canonical store of record |",
            "| storage | keep the vault |\n| indexing | new row |",
        )
        self.assertNotEqual(
            prose_pass.table_structures(SAMPLE_DOC),
            prose_pass.table_structures(grown),
        )

    def test_column_change_changes_structure(self):
        reshaped = SAMPLE_DOC.replace(
            "| Date | Change |\n|---|---|",
            "| Date | Change | Author |\n|---|---|---|",
        )
        self.assertNotEqual(
            prose_pass.table_structures(SAMPLE_DOC),
            prose_pass.table_structures(reshaped),
        )


class DocumentHistoryTests(unittest.TestCase):
    def test_section_extracted(self):
        section = prose_pass.document_history_section(SAMPLE_DOC)
        self.assertIsNotNone(section)
        self.assertTrue(section.startswith("## Document History"))
        self.assertIn("| 2026-07-01 | authored |", section)

    def test_absent_section_is_none(self):
        self.assertIsNone(prose_pass.document_history_section("# Doc\nbody\n"))


class ValidateOutputTests(unittest.TestCase):
    def test_faithful_simplification_passes(self):
        self.assertEqual(prose_pass.validate_output(SAMPLE_DOC, SAMPLE_REVISED), [])

    def test_empty_output_rejected(self):
        self.assertEqual(prose_pass.validate_output(SAMPLE_DOC, "  \n"), ["empty output"])

    def test_frontmatter_drift_rejected(self):
        bad = SAMPLE_REVISED.replace("status: final", "status: draft")
        self.assertTrue(any("frontmatter" in v for v in
                            prose_pass.validate_output(SAMPLE_DOC, bad)))

    def test_heading_drift_rejected(self):
        bad = SAMPLE_REVISED.replace("## Decisions", "## Key Decisions")
        self.assertTrue(any("headings" in v for v in
                            prose_pass.validate_output(SAMPLE_DOC, bad)))

    def test_document_history_drift_rejected(self):
        bad = SAMPLE_REVISED.replace("| 2026-07-01 | authored |",
                                     "| 2026-07-01 | written |")
        self.assertTrue(any("Document History" in v for v in
                            prose_pass.validate_output(SAMPLE_DOC, bad)))

    def test_outer_fence_unwrapped(self):
        wrapped = f"```markdown\n{SAMPLE_REVISED}```"
        self.assertEqual(
            prose_pass.validate_output(
                SAMPLE_DOC, prose_pass.unwrap_outer_fence(wrapped)),
            [],
        )


# ── unit: risky-tag escape/restore ───────────────────────────────────────────
class EscapeRiskyTagsTests(unittest.TestCase):
    def test_round_trips_every_risky_tag_open_close_any_case(self):
        text = "See <thought>note</thought> then <Thinking> and </ANSWER>."
        escaped = prose_pass.escape_risky_tags(text)
        self.assertEqual(prose_pass.restore_risky_tags(escaped), text)

    def test_escaped_text_no_longer_contains_the_literal_tag(self):
        # The placeholder must drop the `<`/`>` entirely, not just wrap them —
        # a wrapped-but-still-present "<thought>" substring would still trip
        # agy's reasoning-tag reader (the bug this escape exists to prevent).
        escaped = prose_pass.escape_risky_tags("before <thought>x</thought> after")
        self.assertNotIn("<thought>", escaped)
        self.assertNotIn("</thought>", escaped)

    def test_ordinary_tags_untouched(self):
        text = "No risky tags here, just <em>emphasis</em> and <br/>."
        self.assertEqual(prose_pass.escape_risky_tags(text), text)


# ── unit: FACT-GUARD leakage ─────────────────────────────────────────────────
class GuardLeakageTests(unittest.TestCase):
    GUARD = "single-operator system — no teams or users"

    def test_stapled_guard_sentence_flagged(self):
        revised = SAMPLE_DOC.replace(
            "## Decisions",
            "This is a single-operator system — no teams or users.\n\n## Decisions",
        )
        violations = prose_pass.guard_leakage(SAMPLE_DOC, revised, [self.GUARD])
        self.assertTrue(any("leaked into the document" in v for v in violations))

    def test_guard_already_present_verbatim_not_flagged(self):
        # A guard whose exact sentence was already in the original, and which
        # the revision leaves untouched while simplifying something else
        # entirely, is not new content — nothing leaked.
        original = SAMPLE_DOC.replace(
            "## Decisions", f"{self.GUARD}.\n\n## Decisions")
        revised = original.replace(
            "keep the vault as the canonical store of record", "the vault is the store")
        self.assertEqual(prose_pass.guard_leakage(original, revised, [self.GUARD]), [])

    def test_faithful_simplification_not_flagged(self):
        self.assertEqual(
            prose_pass.guard_leakage(SAMPLE_DOC, SAMPLE_REVISED, [self.GUARD]), [])

    def test_unrelated_new_sentence_not_flagged(self):
        revised = SAMPLE_DOC.replace(
            "## Decisions", "A short unrelated aside.\n\n## Decisions")
        self.assertEqual(prose_pass.guard_leakage(SAMPLE_DOC, revised, [self.GUARD]), [])

    def test_light_edit_of_a_sentence_the_guard_quotes_not_flagged(self):
        # From a real pass (2026-09-11): the guard quoted the draft, Gemini
        # changed one word, and the pass degraded on its own author's text.
        guard = "The captured pass trips 7 of its 8 guards."
        original = f"It adds a second pass. {guard} The rest held.\n"
        revised = "It adds a second pass. That captured pass trips 7 of its 8 guards. The rest held.\n"
        self.assertEqual(prose_pass.guard_leakage(original, revised, [guard]), [])

    # Verbatim from a documenter dry-run (2026-09-11): Gemini cut each guard
    # into short sentences, and the whole-line pass scored none of them.
    PIECES_ORIGINAL = (
        "It exits 1 when the plugin or file is not installed, and lists every path it "
        "tried on stderr. It exits 2 on a usage error: the wrong argument count, a "
        "malformed plugin name, or a relative path that leaves the plugin. Three rungs "
        "run in order, and the first hit wins. The flat rung looks beside the calling "
        "plugin's root, first as written and then through any symlink on it. The last "
        "two rungs run only when the plugin root has the cache's shape.\n")
    PIECES_REVISED = (
        "It exits 1 when the plugin or the file is missing from the install. It lists "
        "the tried paths on stderr. Exit 1 is never the usage-error code.\n\n"
        "The installed and newest rungs are appended only when the plugin root sits in "
        "Claude Code's cache layout. Its grandparent's parent must be named `cache`. "
        "The flat rung always runs.\n")
    PIECES_GUARDS = [
        "exit 1 means the plugin or the file is missing from the install, with the tried "
        "paths on stderr — exit 1 is never the usage-error code (sibling_plugin.py:107-110)",
        "installed and newest are appended only when the plugin root sits in Claude Code's "
        "cache layout (its grandparent's parent is named cache); the flat rung always runs "
        "(sibling_plugin.py:65-69)",
    ]

    def test_guard_cut_into_pieces_flagged(self):
        whole_line_only = prose_pass.guard_leakage(
            self.PIECES_ORIGINAL, self.PIECES_REVISED, self.PIECES_GUARDS, min_new_words=10**6)
        self.assertEqual(whole_line_only, [])  # the miss this pass exists for
        violations = prose_pass.guard_leakage(
            self.PIECES_ORIGINAL, self.PIECES_REVISED, self.PIECES_GUARDS)
        self.assertEqual(len(violations), 2)
        self.assertTrue(all("leaked into the document in pieces" in v for v in violations))
        self.assertIn("usage-error", violations[0])
        self.assertIn("grandparent", violations[1])

    def test_real_clean_rewording_not_flagged(self):
        # A real Gemini pass over crickets' Why-Deterministic-Gates page, with
        # guards paraphrased the way the documenter writes them: it split and
        # listed, and brought in no guard's vocabulary.
        original = (
            "Crickets gates every change on deterministic checks — typecheck, lint, tests, "
            "build — before any LLM judgment is consulted. Deterministic checks are cheap, "
            "repeatable, and truthful: a test either passes or it doesn't, and it says so the "
            "same way every time. LLM judgment is expensive and can be sycophantic — it may "
            "bless output a compiler would reject.\n\nSo the order is fixed: machines verify "
            "what machines can verify; the LLM augments at the margins — review, naming, "
            "intent — and never replaces the gate. A green LLM opinion sitting on top of red "
            "tests is worthless, so the red tests run first and win.\n")
        revised = (
            "Crickets gates every change on these deterministic checks before it consults an "
            "LLM:\n\n- typecheck\n- lint\n- tests\n- build\n\nDeterministic checks are:\n\n"
            "- cheap\n- repeatable\n- truthful\n\nA test either passes or fails. It says so "
            "the same way every time. LLM judgment is expensive. An LLM may bless output a "
            "compiler would reject.\n\nThe order is fixed. Machines verify what machines can "
            "verify.\n\nThe LLM augments:\n\n- review\n- naming\n- intent\n\nThe LLM never "
            "replaces the gate. A green LLM opinion on top of red tests means nothing. The "
            "red tests run first and win.\n")
        guards = [
            "deterministic checks (typecheck, lint, tests, build) execute ahead of any model-based judgment",
            "a deterministic check yields an identical verdict on every run",
            "model judgment costs more and may approve output a compiler rejects",
            "the LLM supplements review, naming and intent but never substitutes for the gate",
            "when tests are red, a green LLM opinion carries no weight; the failing tests take precedence",
        ]
        self.assertEqual(prose_pass.guard_leakage(original, revised, guards), [])

    def test_three_new_words_from_one_guard_is_the_line(self):
        guard = ["stale entries expire weekly unless pinned"]
        original = "The store keeps entries.\n"
        two = "The store keeps entries, and they expire weekly.\n"
        three = "The store keeps entries, and stale ones expire weekly.\n"
        self.assertEqual(prose_pass.guard_leakage(original, two, guard), [])
        violations = prose_pass.guard_leakage(original, three, guard)
        self.assertEqual(len(violations), 1)
        self.assertIn("expire, stale, weekly", violations[0])


# ── unit: truncation heuristic + section splitting ───────────────────────────
class LooksTruncatedTests(unittest.TestCase):
    def test_short_and_dirty_ending_is_truncated(self):
        cutoff = SAMPLE_DOC[:80]  # mid-word, well under half the length
        self.assertTrue(prose_pass.looks_truncated(SAMPLE_DOC, cutoff))

    def test_short_but_clean_ending_is_not_truncated(self):
        # A short, complete, off-contract reply (still a real problem — the
        # structural-contract check catches it) is not a truncation.
        garbage = "Here is a summary of the changes I would suggest making."
        self.assertFalse(prose_pass.looks_truncated(SAMPLE_DOC, garbage))

    def test_faithful_full_length_revision_not_truncated(self):
        self.assertFalse(prose_pass.looks_truncated(SAMPLE_DOC, SAMPLE_REVISED))

    def test_empty_output_is_truncated(self):
        self.assertTrue(prose_pass.looks_truncated(SAMPLE_DOC, "   \n"))


class SplitSectionsTests(unittest.TestCase):
    def test_sections_reassemble_to_the_original_byte_for_byte(self):
        self.assertEqual("".join(prose_pass.split_sections(SAMPLE_DOC)), SAMPLE_DOC)

    def test_splits_on_level_one_and_two_headings(self):
        sections = prose_pass.split_sections(SAMPLE_DOC)
        starts = [s.lstrip().splitlines()[0] if s.lstrip() else "" for s in sections]
        self.assertIn("# Sample design", starts)
        self.assertIn("## Decisions", starts)
        self.assertIn("## Document History", starts)


# ── unit: prompt assembly + argv ordering ────────────────────────────────────
class PromptAssemblyTests(unittest.TestCase):
    def test_four_blocks_in_order_and_verbatim(self):
        voice = "Sound like the operator. VERBATIM-VOICE-MARKER."
        prompt = prose_pass.assemble_prompt(
            prose_pass.TASK_HEADER,
            ["decay only lowers rank — nothing is deleted"],
            voice, SAMPLE_DOC)
        i_header = prompt.find("simplification/readability pass")
        i_guard = prompt.find("=== FACT-GUARD")
        i_voice = prompt.find("=== VOICE PACK")
        i_doc = prompt.find("=== DOCUMENT ===")
        self.assertTrue(0 <= i_header < i_guard < i_voice < i_doc)
        self.assertIn("- decay only lowers rank — nothing is deleted", prompt)
        # The voice pack is inlined verbatim — summarized rules don't hold.
        self.assertIn(voice, prompt)
        self.assertIn(SAMPLE_DOC, prompt)

    def test_argv_prompt_first_flags_after(self):
        argv = prose_pass.build_agy_argv("THE PROMPT", "Gemini 3.1 Pro (High)", "480s")
        # -p <prompt> must come before any flag: flags placed before the
        # prompt silently drop it (cross-review.sh's hard-won lesson).
        self.assertEqual(argv[:3], ["agy", "-p", "THE PROMPT"])
        self.assertEqual(argv[3:], ["--model", "Gemini 3.1 Pro (High)",
                                    "--print-timeout", "480s"])


class TimeoutTests(unittest.TestCase):
    """agy reads --print-timeout as a Go duration. A bare integer used to go
    through as-is, agy rejected it, and the run degraded as if agy were
    unavailable (seen 2026-09-10 with --timeout 300)."""

    def test_bare_integer_means_seconds(self):
        self.assertEqual(prose_pass.normalize_timeout("300"), "300s")

    def test_go_durations_pass_through(self):
        for value in ("90s", "5m", "5m0s", "1h30m", "1.5h", "480s"):
            with self.subTest(value=value):
                self.assertEqual(prose_pass.normalize_timeout(value), value)

    def test_non_durations_are_rejected(self):
        for value in ("", "abc", "5 m", "5min", "1.5", "s", "300x", "0", "0s", "-5s"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                prose_pass.normalize_timeout(value)

    def test_every_unit_counts_toward_seconds(self):
        cases = {"90s": 90, "5m": 300, "5m0s": 300, "1h30m": 5400,
                 "1.5h": 5400, "500ms": 0.5, ".5s": 0.5}
        for value, seconds in cases.items():
            with self.subTest(value=value):
                self.assertAlmostEqual(prose_pass.go_duration_seconds(value), seconds)

    def test_wall_clock_backstop_reads_the_unit(self):
        # The backstop used to read only the leading digits, so "5m" got a
        # 125s wall clock and killed agy long before its own 300s timeout.
        seen = {}

        def fake_run(argv, **kw):
            seen["timeout"] = kw["timeout"]
            return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

        with mock.patch.object(prose_pass.subprocess, "run", fake_run):
            prose_pass._call_agy(["agy"], "prompt", "model", "5m")
        self.assertEqual(seen["timeout"], 300 + 120)


class VaultResolutionTests(unittest.TestCase):
    def test_env_var_resolves_when_dir_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"MEMORY_ROOT": tmp}):
                self.assertEqual(prose_pass.resolve_vault_path(None), Path(tmp))

    def test_deprecated_alias_resolves_when_memory_root_unset(self):
        # The name agentm exported before 2026-09-11, kept as an alias for one
        # release — still honored on its own.
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"MEMORY_VAULT_PATH": tmp}):
                os.environ.pop("MEMORY_ROOT", None)
                self.assertEqual(prose_pass.resolve_vault_path(None), Path(tmp))

    def test_memory_root_wins_over_the_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            new, old = Path(tmp) / "new", Path(tmp) / "old"
            new.mkdir()
            old.mkdir()
            both = {"MEMORY_ROOT": str(new), "MEMORY_VAULT_PATH": str(old)}
            with mock.patch.dict(os.environ, both):
                self.assertEqual(prose_pass.resolve_vault_path(None), new)
            # Empty MEMORY_ROOT (CI's isolation value) falls through to the alias.
            with mock.patch.dict(os.environ, {**both, "MEMORY_ROOT": ""}):
                self.assertEqual(prose_pass.resolve_vault_path(None), old)

    def test_missing_dir_is_none(self):
        self.assertIsNone(prose_pass.resolve_vault_path("/nonexistent/vault/path"))

    def test_overlay_bare_filename_lands_in_wiki_style(self):
        # A vault path that doesn't exist has no project space to probe, so the
        # bare filename resolves into the current layout's store.
        vault = Path("/v")
        self.assertEqual(
            prose_pass.resolve_overlay(vault, "2026-06-09-design-doc-prose.md"),
            vault / "desk/projects/_global/wiki-style/2026-06-09-design-doc-prose.md",
        )

    def test_overlay_bare_filename_follows_an_unmigrated_vault(self):
        # The store still on the pre-stage-2 rung is found there, not shadowed
        # by the current-layout default. (Full layout matrix: test_vault_layout.py.)
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            (vault / "projects" / "_global" / "wiki-style").mkdir(parents=True)
            self.assertEqual(
                prose_pass.resolve_overlay(vault, "2026-06-09-design-doc-prose.md"),
                vault / "projects/_global/wiki-style/2026-06-09-design-doc-prose.md",
            )


# ── e2e: fake agy wired in via $PROSE_PASS_TEST_AGY_CMD ──────────────────────
def _write_fake_agy(bin_dir: Path, impl: str) -> Path:
    """Write a fake agy implementation as a plain Python script and return
    its path. No OS shim (bash/.cmd) — the test wires it in directly via
    prose_pass.resolve_agy_cmd()'s $PROSE_PASS_TEST_AGY_CMD override, so
    subprocess talks to python.exe/python3 straight, with no cmd.exe batch
    parsing in between (see the module docstring for why that matters)."""
    path = bin_dir / "agy_impl.py"
    path.write_text(impl, encoding="utf-8")
    return path


_ECHO_DOC_IMPL = """\
import json, sys
from pathlib import Path
here = Path(__file__).resolve().parent
(here / "args.json").write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
prompt = sys.argv[sys.argv.index("-p") + 1]
sys.stdout.write(prompt.split("=== DOCUMENT ===\\n", 1)[1])
"""

_GARBAGE_IMPL = """\
import sys
from pathlib import Path
counter = Path(__file__).resolve().parent / "calls.count"
n = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(n))
print("Here is a summary of the changes I would suggest making.")
"""

_LEAK_GUARD_IMPL = """\
import sys
from pathlib import Path
counter = Path(__file__).resolve().parent / "calls.count"
n = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(n))
prompt = sys.argv[sys.argv.index("-p") + 1]
doc = prompt.split("=== DOCUMENT ===\\n", 1)[1]
sys.stdout.write(doc.replace(
    "## Decisions",
    "This is a single-operator system — no teams or users.\\n\\n## Decisions",
))
"""

# Chokes on a literal "<thought>" reaching it — simulating agy's own
# reasoning-tag reader truncating the stream at that byte. Only sees it if
# prose_pass fails to escape the tag before sending.
_CHOKE_ON_LITERAL_TAG_IMPL = """\
import sys
prompt = sys.argv[sys.argv.index("-p") + 1]
doc = prompt.split("=== DOCUMENT ===\\n", 1)[1]
if "<thought>" in doc:
    sys.stdout.write(doc.split("<thought>", 1)[0])
else:
    sys.stdout.write(doc)
"""

# Truncates (short, dirty ending) on a full-document call but behaves
# normally on the smaller per-section calls the truncation fallback makes —
# simulating a cutoff that only manifests on the full document.
_SIZE_SENSITIVE_TRUNCATE_IMPL = """\
import sys
prompt = sys.argv[sys.argv.index("-p") + 1]
doc = prompt.split("=== DOCUMENT ===\\n", 1)[1]
if len(doc) > 150:
    sys.stdout.write(doc[:40])
else:
    sys.stdout.write(doc.replace(
        "This design utilizes a mechanism whereby entries are subjected to decay.",
        "Entries decay.",
    ))
"""


def _make_vault(root: Path) -> Path:
    # Deliberately built on the PRE-stage-2 `projects/` rung: the e2e path must
    # keep working on a vault that never migrated. The current `desk/projects/`
    # layout is covered in test_vault_layout.py.
    vault = root / "vault"
    kernel = vault / "personal" / "_always-load"
    style = vault / "projects" / "_global" / "wiki-style"
    kernel.mkdir(parents=True)
    style.mkdir(parents=True)
    (kernel / "voice-kernel.md").write_text(
        "Sound like the operator. KERNEL-MARKER.\n", encoding="utf-8")
    (style / "2026-06-09-design-doc-prose.md").write_text(
        "Short sentences. OVERLAY-MARKER.\n", encoding="utf-8")
    return vault


def _run_pass(tmp: Path, *extra_args: str, fake_impl: Path | None = None,
              env_extra: dict | None = None) -> subprocess.CompletedProcess:
    doc = tmp / "doc.md"
    if not doc.exists():
        doc.write_text(SAMPLE_DOC, encoding="utf-8")
    env = dict(os.environ)
    env.pop("PROSE_PASS_TEST_AGY_CMD", None)
    if fake_impl is not None:
        # Point resolve_agy_cmd() straight at [python, fake_impl.py] — no
        # PATH lookup, no OS shim, so cmd.exe never gets a look at the
        # (possibly multi-line) argv on Windows.
        env["PROSE_PASS_TEST_AGY_CMD"] = json.dumps([sys.executable, str(fake_impl)])
    else:
        # Prove the "agy unavailable" path without depending on PATH state.
        env["PATH"] = ""
    env.pop("MEMORY_VAULT_PATH", None)
    env["MEMORY_ROOT"] = str(tmp / "vault")
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(_SCRIPT), str(doc), *extra_args],
        capture_output=True, text=True, timeout=60, env=env,
    )


class EndToEndTests(unittest.TestCase):
    def test_missing_agy_degrades_visibly(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            _make_vault(tmp)
            r = _run_pass(tmp, "--fact-guard-text", "a truth")
            self.assertEqual(r.returncode, 1, f"stderr={r.stderr!r}")
            self.assertIn("PROSE-PASS-DEGRADED: agy CLI unavailable", r.stdout)

    def test_missing_fact_guard_is_usage_error(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            _make_vault(tmp)
            impl = _write_fake_agy(tmp, _ECHO_DOC_IMPL)
            r = _run_pass(tmp, fake_impl=impl)
            self.assertEqual(r.returncode, 2, f"stderr={r.stderr!r}")
            self.assertIn("FACT-GUARD", r.stderr)

    def test_unresolvable_vault_degrades_visibly(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            impl = _write_fake_agy(tmp, _ECHO_DOC_IMPL)
            # No vault dir; point the config prefix somewhere empty too.
            r = _run_pass(tmp, "--fact-guard-text", "a truth", fake_impl=impl,
                          env_extra={"MEMORY_ROOT": "", "MEMORY_VAULT_PATH": "",
                                     "AGENTM_INSTALL_PREFIX": str(tmp / "empty")})
            self.assertEqual(r.returncode, 1, f"stderr={r.stderr!r}")
            self.assertIn("PROSE-PASS-DEGRADED: vault unresolved", r.stdout)

    def test_unresolvable_kernel_degrades_naming_its_current_home(self):
        # A kernel found on no layout is reported as the file the current
        # layout expects; naming the retired voice-kernel.md would send the
        # operator after a file plan 05 deleted.
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            vault = _make_vault(tmp)
            (vault / "personal" / "_always-load" / "voice-kernel.md").unlink()
            impl = _write_fake_agy(tmp, _ECHO_DOC_IMPL)
            r = _run_pass(tmp, "--fact-guard-text", "a truth", fake_impl=impl)
            self.assertEqual(r.returncode, 1, f"stderr={r.stderr!r}")
            self.assertIn("PROSE-PASS-DEGRADED: voice pack unresolved", r.stdout)
            self.assertIn("missing voice file(s): user-preferences.md", r.stderr)

    def test_identity_pass_round_trips_and_orders_argv(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            _make_vault(tmp)
            impl = _write_fake_agy(tmp, _ECHO_DOC_IMPL)
            r = _run_pass(tmp, "--fact-guard-text",
                          "decay only lowers rank — nothing is deleted", fake_impl=impl)
            self.assertEqual(r.returncode, 0, f"stderr={r.stderr!r}")
            self.assertEqual(r.stdout, SAMPLE_DOC)
            self.assertNotIn("PROSE-PASS-DEGRADED", r.stdout)
            argv = json.loads((tmp / "args.json").read_text(encoding="utf-8"))
            # Prompt first, flags after — and the prompt carries the guard
            # and the voice pack verbatim, newlines and all.
            self.assertEqual(argv[0], "-p")
            prompt = argv[1]
            self.assertIn("decay only lowers rank — nothing is deleted", prompt)
            self.assertIn("KERNEL-MARKER", prompt)
            self.assertIn("OVERLAY-MARKER", prompt)
            self.assertEqual(argv[2:], ["--model", prose_pass.MODEL_DEFAULT,
                                        "--print-timeout", prose_pass.TIMEOUT_DEFAULT])

    def test_structural_violation_retries_once_then_exit_2(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            _make_vault(tmp)
            impl = _write_fake_agy(tmp, _GARBAGE_IMPL)
            r = _run_pass(tmp, "--fact-guard-text", "a truth", fake_impl=impl)
            self.assertEqual(r.returncode, 2, f"stderr={r.stderr!r}")
            self.assertIn("PROSE-PASS-DEGRADED: agy revision violated the "
                          "structural contract twice", r.stdout)
            calls = (tmp / "calls.count").read_text(encoding="utf-8").strip()
            self.assertEqual(calls, "2")  # initial call + exactly one retry

    def test_output_flag_writes_file_instead_of_stdout(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            _make_vault(tmp)
            impl = _write_fake_agy(tmp, _ECHO_DOC_IMPL)
            out = tmp / "revised.md"
            r = _run_pass(tmp, "--fact-guard-text", "a truth", "-o", str(out), fake_impl=impl)
            self.assertEqual(r.returncode, 0, f"stderr={r.stderr!r}")
            self.assertEqual(out.read_text(encoding="utf-8"), SAMPLE_DOC)
            self.assertNotIn("# Sample design", r.stdout)

    def test_guard_leakage_retries_once_then_exit_2(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            _make_vault(tmp)
            impl = _write_fake_agy(tmp, _LEAK_GUARD_IMPL)
            r = _run_pass(tmp, "--fact-guard-text",
                          "single-operator system — no teams or users", fake_impl=impl)
            self.assertEqual(r.returncode, 2, f"stderr={r.stderr!r}")
            self.assertIn("PROSE-PASS-DEGRADED: agy revision violated the "
                          "structural contract twice", r.stdout)
            self.assertIn("leaked into the document", r.stderr)
            calls = (tmp / "calls.count").read_text(encoding="utf-8").strip()
            self.assertEqual(calls, "2")  # initial call + exactly one retry

    def test_literal_risky_tag_survives_round_trip_without_choking(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            _make_vault(tmp)
            doc_with_tag = SAMPLE_DOC.replace(
                "This design utilizes a mechanism whereby entries are subjected to decay.",
                "Entries are tagged with a literal <thought> marker before decay.",
            )
            (tmp / "doc.md").write_text(doc_with_tag, encoding="utf-8")
            impl = _write_fake_agy(tmp, _CHOKE_ON_LITERAL_TAG_IMPL)
            r = _run_pass(tmp, "--fact-guard-text", "a truth", fake_impl=impl)
            self.assertEqual(r.returncode, 0, f"stderr={r.stderr!r}")
            self.assertEqual(r.stdout, doc_with_tag)
            self.assertNotIn("PROSE-PASS-DEGRADED", r.stdout)

    def test_truncation_falls_back_to_sectioned_pass(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            _make_vault(tmp)
            impl = _write_fake_agy(tmp, _SIZE_SENSITIVE_TRUNCATE_IMPL)
            r = _run_pass(tmp, "--fact-guard-text", "a truth", fake_impl=impl)
            self.assertEqual(r.returncode, 0, f"stderr={r.stderr!r}")
            expected = SAMPLE_DOC.replace(
                "This design utilizes a mechanism whereby entries are subjected to decay.",
                "Entries decay.",
            )
            self.assertEqual(r.stdout, expected)
            self.assertNotIn("PROSE-PASS-DEGRADED", r.stdout)
            self.assertIn("stream truncation suspected", r.stderr)

    def test_timeout_reaches_agy_as_a_go_duration(self):
        for value, sent in (("300", "300s"), ("90s", "90s"), ("5m", "5m")):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as t:
                tmp = Path(t)
                _make_vault(tmp)
                impl = _write_fake_agy(tmp, _ECHO_DOC_IMPL)
                r = _run_pass(tmp, "--fact-guard-text", "a truth",
                              "--timeout", value, fake_impl=impl)
                self.assertEqual(r.returncode, 0, f"stderr={r.stderr!r}")
                argv = json.loads((tmp / "args.json").read_text(encoding="utf-8"))
                self.assertEqual(argv[-2:], ["--print-timeout", sent])

    def test_bad_timeout_is_a_usage_error_not_a_degradation(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            _make_vault(tmp)
            impl = _write_fake_agy(tmp, _ECHO_DOC_IMPL)
            r = _run_pass(tmp, "--fact-guard-text", "a truth",
                          "--timeout", "five minutes", fake_impl=impl)
            self.assertEqual(r.returncode, 2, f"stderr={r.stderr!r}")
            self.assertNotIn("PROSE-PASS-DEGRADED", r.stdout)
            self.assertIn("--timeout", r.stderr)
            # Rejected before agy was ever called.
            self.assertFalse((tmp / "args.json").exists())



class TestWikiStyleDirWitness(unittest.TestCase):
    """The `../Projects` rung counts only when the memory root is nested
    inside an Obsidian vault; a flat vault's parent is never probed, and the
    flat `<memory-root>/Projects` rung needs no witness (agentm 2b review)."""

    def test_unwitnessed_sibling_is_ignored_and_the_default_stays_inside(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            vault = home / "Vault"
            (vault / ".obsidian").mkdir(parents=True)
            (home / "Projects" / "_global" / "wiki-style").mkdir(parents=True)
            self.assertEqual(prose_pass.wiki_style_dir(vault), vault / "desk" / "projects" / "_global" / "wiki-style")

    def test_witnessed_sibling_and_flat_rung_resolve(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "Vault"
            (root / ".obsidian").mkdir(parents=True)
            memory_root = root / "Agent"
            memory_root.mkdir()
            (root / "Projects" / "_global" / "wiki-style").mkdir(parents=True)
            self.assertEqual(prose_pass.wiki_style_dir(memory_root).resolve(),
                             (root / "Projects" / "_global" / "wiki-style").resolve())
            flat = Path(td) / "Flat"
            (flat / ".obsidian").mkdir(parents=True)
            (flat / "Projects" / "_global" / "wiki-style").mkdir(parents=True)
            self.assertEqual(prose_pass.wiki_style_dir(flat), flat / "Projects" / "_global" / "wiki-style")

class TestMemoryRootTrimsResolution(unittest.TestCase):
    """agentm-vault plan 05: the kernel is `standards/user-preferences.md` and
    the overlay store `standards/voice/` on a migrated vault; the pen and the
    project-space stores still resolve on one that never migrated."""

    def test_kernel_prefers_the_preferences_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "Vault"
            (root / ".obsidian").mkdir(parents=True)
            mr = root / "Agent"
            pen = mr / "memory" / "_always-load"
            pen.mkdir(parents=True)
            (pen / "voice-kernel.md").write_text("pen\n", encoding="utf-8")
            self.assertEqual(prose_pass.resolve_voice_kernel(mr), pen / "voice-kernel.md")
            (root / "standards").mkdir()
            (root / "standards" / "user-preferences.md").write_text("mine\n", encoding="utf-8")
            self.assertEqual(prose_pass.resolve_voice_kernel(mr).resolve(),
                             (root / "standards" / "user-preferences.md").resolve())

    def test_overlay_store_prefers_the_voice_library(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "Vault"
            (root / ".obsidian").mkdir(parents=True)
            mr = root / "Agent"
            mr.mkdir()
            (root / "Projects" / "_global" / "wiki-style").mkdir(parents=True)
            self.assertEqual(prose_pass.wiki_style_dir(mr).resolve(),
                             (root / "Projects" / "_global" / "wiki-style").resolve())
            (root / "standards" / "voice").mkdir(parents=True)
            self.assertEqual(prose_pass.wiki_style_dir(mr).resolve(),
                             (root / "standards" / "voice").resolve())


if __name__ == "__main__":
    unittest.main()
