#!/usr/bin/env python3
"""End-to-end tests for the coauthor-guard prepare-commit-msg hook
(`src/developer-safety/hooks/coauthor-guard/coauthor-guard.sh`).

Real subprocess execution against a fixture commit-msg file, mirroring
test_conflict_merger_hook.py's convention -- proves the strip end to end
rather than merely at a function level. POSIX-only (bash hook); the pwsh
twin mirrors the behavior and runs here only when pwsh is on PATH. A
parity test pins the agent pattern byte-identical across the two twins.
The machine-wide install is covered in test_developer_safety_global_git_hooks.py.

stdlib only -- no pytest.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parent
_HOOK = REPO_ROOT / "src" / "developer-safety" / "hooks" / "coauthor-guard" / "coauthor-guard.sh"


def _at(local: str, domain: str) -> str:
    """Join an address at runtime, so the PII gate never sees one in source
    (test_check_no_pii.py's convention). These are agent vendors' public bot
    addresses and GitHub noreply shapes, not anyone's personal email."""
    return f"{local}@{domain}"
_PS1 = _HOOK.with_name("coauthor-guard.ps1")

# One trailer per way a trailer can name an agent: vendor email domain, a
# GitHub App ([bot]) identity, or an agent product name.
AGENT_TRAILERS = [
        "Co-Authored-By: Claude Fable 5 <" + _at("noreply", "anthropic.com") + ">",
        "co-authored-by: Claude Sonnet 4.6 <" + _at("noreply", "anthropic.com") + ">",
        "Co-authored-by: Claude Opus <someone@example.com>",
        "Co-authored-by: Codex <" + _at("codex", "openai.com") + ">",
        "Co-authored-by: Cursor Agent <" + _at("cursoragent", "cursor.com") + ">",
        "Co-authored-by: aider (gpt-4o) <" + _at("noreply", "aider.chat") + ">",
        "Co-authored-by: Amp <" + _at("amp", "ampcode.com") + ">",
        "Co-authored-by: openhands <" + _at("openhands", "all-hands.dev") + ">",
        "Co-authored-by: Copilot <" + _at("175728472+Copilot", "users.noreply.github.com") + ">",
        "Co-authored-by: google-labs-jules[bot] <" + _at("161369871+google-labs-jules[bot]", "users.noreply.github.com") + ">",
        "Co-authored-by: devin-ai-integration[bot] <" + _at("158243242+devin-ai-integration[bot]", "users.noreply.github.com") + ">",
        "Co-Authored-By: Gemini <gemini@example.com>",
        "Co-Authored-By: Antigravity <agent@example.com>",
        "Co-Authored-By: ChatGPT <bot@example.com>",
        "Co-Authored-By: GPT-5 <model@example.com>",
        # git parses these as the same trailer: spaces or a tab before the colon,
        # an email with no brackets, a space inside the brackets.
        "Co-authored-by : Claude <" + _at("noreply", "anthropic.com") + ">",
        "Co-authored-by\t: Claude <" + _at("noreply", "anthropic.com") + ">",
        "Co-Authored-By: Claude " + _at("noreply", "anthropic.com"),
        "Co-Authored-By: Claude <" + _at("noreply", "anthropic.com") + " >",
]

# The operator's call: strip AI agents only. A person's trailer stays,
# including one whose first name happens to be Claude.
HUMAN_TRAILERS = [
        "Co-authored-by: Jane Doe <jane@example.com>",
        "Co-authored-by: Pat Lee <" + _at("12345+patlee", "users.noreply.github.com") + ">",
        "Co-authored-by: Claude Monet <" + _at("claude", "giverny.example") + ">",
        "Co-authored-by: Devin Smith <devin@example.org>",
        # A product name inside a person's email is not the name.
        "Co-authored-by: Jane Doe <" + _at("jane", "gemini.com") + ">",
        "Co-authored-by: Pat <" + _at("123+copilot-fan", "users.noreply.github.com") + ">",
]


@unittest.skipIf(os.name == "nt", "bash hook -- POSIX only")
@unittest.skipUnless(_HOOK.is_file(), f"{_HOOK} not present")
class CoauthorGuardHookTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.msg_file = Path(self._tmp.name) / "COMMIT_EDITMSG"

    def tearDown(self):
        self._tmp.cleanup()

    def _run_hook(self):
        result = subprocess.run(
            ["bash", str(_HOOK), str(self.msg_file)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def _strip(self, text: str) -> str:
        self.msg_file.write_text(text, encoding="utf-8")
        self._run_hook()
        return self.msg_file.read_text(encoding="utf-8")

    def test_claude_trailer_is_stripped_rest_untouched(self):
        original = (
            "feat: add the thing\n"
            "\n"
            "A body line that stays.\n"
            "\n"
            "Co-Authored-By: Claude <" + _at("noreply", "anthropic.com") + ">\n"
        )
        result = self._strip(original)
        self.assertNotIn("Co-Authored-By", result)
        self.assertEqual(result, "feat: add the thing\n\nA body line that stays.\n\n")

    def test_every_known_agent_identity_is_stripped(self):
        for trailer in AGENT_TRAILERS:
            with self.subTest(trailer=trailer):
                self.assertEqual(self._strip(f"fix: x\n\n{trailer}\n"), "fix: x\n\n")

    def test_human_co_authors_survive(self):
        for trailer in HUMAN_TRAILERS:
            with self.subTest(trailer=trailer):
                original = f"fix: x\n\n{trailer}\n"
                self.assertEqual(self._strip(original), original)

    def test_mixed_trailers_keep_the_human_drop_the_agent(self):
        original = (
            "feat: pair work\n"
            "\n"
            "Co-authored-by: Jane Doe <jane@example.com>\n"
            "Co-Authored-By: Claude <" + _at("noreply", "anthropic.com") + ">\n"
        )
        self.assertEqual(
            self._strip(original),
            "feat: pair work\n\nCo-authored-by: Jane Doe <jane@example.com>\n",
        )

    def test_body_mention_of_an_agent_is_not_a_trailer(self):
        original = "docs: note\n\nWritten with Claude Code and Gemini; see " + _at("noreply", "anthropic.com") + ".\n"
        self.assertEqual(self._strip(original), original)

    def test_trailer_strip_is_not_hardcoded_to_one_agent_name(self):
        original = (
            "fix: something\n"
            "\n"
            "Co-Authored-By: Gemini <gemini@example.com>\n"
        )
        self.msg_file.write_text(original, encoding="utf-8")
        self._run_hook()
        result = self.msg_file.read_text(encoding="utf-8")
        self.assertNotIn("Co-Authored-By", result)
        self.assertNotIn("Gemini", result)
        self.assertEqual(result, "fix: something\n\n")

    def test_message_with_no_trailer_is_byte_identical(self):
        original = "chore: routine cleanup\n\nNo trailer here at all.\n"
        self.msg_file.write_text(original, encoding="utf-8")
        before = self.msg_file.read_bytes()
        self._run_hook()
        after = self.msg_file.read_bytes()
        self.assertEqual(before, after)


class CoauthorGuardParityTests(unittest.TestCase):
    def test_agent_patterns_are_identical_in_both_twins(self):
        sh_text = _HOOK.read_text(encoding="utf-8")
        ps1_text = _PS1.read_text(encoding="utf-8")
        for sh_name, ps1_name in (("DOMAIN_RE", "domainRe"), ("NAME_RE", "nameRe")):
            with self.subTest(pattern=sh_name):
                sh = re.search(rf"^{sh_name}='([^']*)'$", sh_text, re.M)
                ps1 = re.search(rf"^\${ps1_name} = '([^']*)'$", ps1_text, re.M)
                self.assertIsNotNone(sh, f"{sh_name} not found in coauthor-guard.sh")
                self.assertIsNotNone(ps1, f"${ps1_name} not found in coauthor-guard.ps1")
                self.assertEqual(sh.group(1), ps1.group(1))
                self.assertNotIn("\\", sh.group(1), "awk -v would rewrite a backslash")


@unittest.skipUnless(shutil.which("pwsh"), "pwsh not on PATH")
class CoauthorGuardPwshTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.msg_file = Path(self._tmp.name) / "COMMIT_EDITMSG"

    def tearDown(self):
        self._tmp.cleanup()

    def _strip(self, text: str) -> str:
        self.msg_file.write_text(text, encoding="utf-8")
        result = subprocess.run(
            ["pwsh", "-NoProfile", "-File", str(_PS1), str(self.msg_file)],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.msg_file.read_text(encoding="utf-8")

    def test_agent_trailers_are_stripped(self):
        for trailer in AGENT_TRAILERS:
            with self.subTest(trailer=trailer):
                self.assertNotIn(trailer, self._strip(f"fix: x\n\n{trailer}\n"))

    def test_human_message_is_left_byte_identical(self):
        original = "fix: x\n\n" + "\n".join(HUMAN_TRAILERS) + "\n"
        self.assertEqual(self._strip(original), original)


if __name__ == "__main__":
    unittest.main()
