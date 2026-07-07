#!/usr/bin/env python3
"""End-to-end tests for the coauthor-guard prepare-commit-msg hook
(`src/developer-safety/hooks/coauthor-guard/coauthor-guard.sh`).

Real subprocess execution against a fixture commit-msg file, mirroring
test_conflict_merger_hook.py's convention -- proves the strip end to end
rather than merely at a function level. POSIX-only (bash hook); the pwsh
twin mirrors the behavior but has no test harness here, matching the
repo's existing hook-test posture (test_conflict_merger_hook.py's own
docstring notes the same asymmetry).

stdlib only -- no pytest.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parent
_HOOK = REPO_ROOT / "src" / "developer-safety" / "hooks" / "coauthor-guard" / "coauthor-guard.sh"


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

    def test_claude_trailer_is_stripped_rest_untouched(self):
        original = (
            "feat: add the thing\n"
            "\n"
            "A body line that stays.\n"
            "\n"
            "Co-Authored-By: Claude <noreply@example.com>\n"
        )
        self.msg_file.write_text(original, encoding="utf-8")
        self._run_hook()
        result = self.msg_file.read_text(encoding="utf-8")
        self.assertNotIn("Co-Authored-By", result)
        self.assertEqual(result, "feat: add the thing\n\nA body line that stays.\n\n")

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


if __name__ == "__main__":
    unittest.main()
