#!/usr/bin/env python3
"""The vault-content suite, run against scratch vaults so CI checks it too.

`test_voice_kernel.py` asserts facts about a real vault and skips wherever
none resolves, which includes CI. That is how it drifted. agentm-vault plan 05
moved the voice kernel into `standards/user-preferences.md`, prose_pass learned
the new home in #242, and the suite kept looking for `voice-kernel.md` until
the vault itself moved and three of its tests failed on the one machine that
runs them.

This module builds a small vault on each layout the kernel has lived on and
runs the suite's kernel class against it in a subprocess, pointed there through
`$MEMORY_ROOT`. A healthy vault must pass on every layout with nothing skipped,
so the suite and prose_pass disagreeing about where the kernel is on any of
them fails here. Each broken vault must fail the test written to catch it.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_SUITE = _SCRIPTS / "test_voice_kernel.py"
_GENRE_SLUGS = ("docs-prose-style", "personal-comms-style", "personal-narrative-style")

# Every layout the kernel has lived on. "nested" and "flat" come after the
# memory-root trims: the kernel is the `## Voice` section of
# `standards/user-preferences.md`, beside a nested memory root or inside a flat
# vault. "pen" and "graduated" come before them: `voice-kernel.md` in the
# always-load pen, or in the dated tree it graduated into. "nested+pen" is the
# transition, a migrated vault with a pen copy left behind.
_LAYOUTS = ("nested", "flat", "pen", "graduated", "nested+pen")


def _genre_file(slug: str) -> str:
    return f"---\nalways_load: false\ntrigger: {slug}\n---\n\nGuidance for {slug}.\n"


def _preferences(voice_lines: int) -> str:
    # Thirty lines of the operator's own under their own heading. The kernel
    # budget counts the voice section alone, so a healthy vault passes with them.
    voice = "\n\n".join(f"Voice rule {i}." for i in range(voice_lines))
    own = "\n".join(f"- a preference of mine, {i}" for i in range(30))
    return ("---\nslug: user-preferences\n---\n\n# User preferences\n\n"
            f"## Voice\n\n{voice}\n\n## How I want things done\n\n{own}\n")


def _build(tmp: Path, layout: str, *, voice_lines: int = 4, kernel: bool = True,
           leak: bool = False) -> Path:
    """Write a vault on `layout` under `tmp` and return its memory root."""
    vault = tmp / "vault"
    memory_root = vault if layout == "flat" else vault / "Agent"
    (vault / ".obsidian").mkdir(parents=True)
    (memory_root / "memory").mkdir(parents=True, exist_ok=True)
    if layout in ("nested", "flat", "nested+pen"):
        standards = vault / "standards"
        (standards / "voice").mkdir(parents=True)
        if kernel:
            (standards / "user-preferences.md").write_text(
                _preferences(voice_lines), encoding="utf-8")
        for slug in _GENRE_SLUGS:
            (standards / "voice" / f"2026-07-05-{slug}.md").write_text(
                _genre_file(slug), encoding="utf-8")
        if leak:
            (standards / "2026-07-05-docs-prose-style.md").write_text(
                _genre_file("docs-prose-style"), encoding="utf-8")
    else:
        library = vault / "Projects" / "_global" / "wiki-style"
        library.mkdir(parents=True)
        for slug in _GENRE_SLUGS:
            (library / f"2026-07-05-{slug}.md").write_text(_genre_file(slug), encoding="utf-8")
    if layout in ("pen", "graduated", "nested+pen"):
        home = memory_root / "memory" / ("2026/07" if layout == "graduated" else "_always-load")
        home.mkdir(parents=True)
        (home / "voice-kernel.md").write_text(
            "---\nslug: voice-kernel\n---\n\n" + "\n".join(f"rule {i}" for i in range(19)) + "\n",
            encoding="utf-8")
    return memory_root


def _run_suite(tmp: Path, memory_root: Path,
               target: str = "TestVoiceKernel") -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "MEMORY_VAULT_PATH"}
    env.update(
        MEMORY_ROOT=str(memory_root),
        # No config under this prefix, so nothing can fall through to a real vault.
        AGENTM_INSTALL_PREFIX=str(tmp / "no-agentm-prefix"),
        PYTHONIOENCODING="utf-8",
    )
    return subprocess.run([sys.executable, str(_SUITE), target], capture_output=True,
                          encoding="utf-8", errors="replace", timeout=120, env=env)


class TestTheKernelSuiteOnScratchVaults(unittest.TestCase):
    def test_a_healthy_vault_passes_on_every_layout(self):
        for layout in _LAYOUTS:
            with self.subTest(layout=layout), tempfile.TemporaryDirectory() as t:
                tmp = Path(t)
                r = _run_suite(tmp, _build(tmp, layout))
                self.assertEqual(r.returncode, 0, r.stderr)
                # A suite that skipped itself exits 0 too, and proves nothing.
                self.assertNotIn("skipped", r.stderr)

    def test_a_voice_section_past_25_lines_fails_the_length_test(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            r = _run_suite(tmp, _build(tmp, "nested", voice_lines=30),
                           "TestVoiceKernel.test_kernel_body_at_most_25_lines")
            self.assertNotEqual(r.returncode, 0, r.stderr)
            self.assertIn("grew to 30 lines", r.stderr)

    def test_a_genre_file_leaked_into_standards_fails_the_absence_test(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            r = _run_suite(tmp, _build(tmp, "nested", leak=True),
                           "TestVoiceKernel.test_three_heavy_files_absent_from_always_load")
            self.assertNotEqual(r.returncode, 0, r.stderr)
            self.assertIn("2026-07-05-docs-prose-style.md", r.stderr)

    def test_a_vault_with_no_kernel_fails_the_locate_test(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            r = _run_suite(tmp, _build(tmp, "nested", kernel=False),
                           "TestVoiceKernel.test_kernel_is_locatable")
            self.assertNotEqual(r.returncode, 0, r.stderr)
            self.assertIn("no voice kernel under", r.stderr)


if __name__ == "__main__":
    unittest.main()
