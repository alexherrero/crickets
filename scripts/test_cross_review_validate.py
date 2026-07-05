#!/usr/bin/env python3
"""Contract test for cross-review.sh's validate() function (R2.2 task 5).

cross-review.sh dispatches an adversarial review to a different model
(Gemini) and requires the response to be exactly one of three shapes: a
failing test in a fenced code block, a `DEFECT: path:line` line, or
`NO ISSUES FOUND`. Prose-only responses must be rejected — otherwise a
sub-agent could satisfy the contract with hand-waving instead of a concrete
finding. This test sources the script (its bottom source-guard keeps that
from also running the gemini call, so no `gemini` binary or network access
is required) and exercises the real `validate()` against sample outputs.
"""
from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_SCRIPT = _REPO / "src" / "code-review" / "scripts" / "cross-review.sh"


def _find_bash() -> str:
    """See test_dist_hooks_functional.py's `_find_bash` for the rationale —
    a bare `bash` PATH lookup on windows-latest can resolve to the WSL
    launcher stub ahead of Git's real bash.exe."""
    if os.name != "nt":
        return "bash"
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    for candidate in (
        Path(program_files) / "Git" / "bin" / "bash.exe",
        Path(program_files) / "Git" / "usr" / "bin" / "bash.exe",
    ):
        if candidate.is_file():
            return str(candidate)
    return "bash"  # fall back to PATH lookup (may hit the WSL stub)


_BASH = _find_bash()


def _validate(sample: str) -> bool:
    """Source cross-review.sh and call its real `validate()` against
    `sample`, returning the function's own exit code as a bool."""
    script = f'source "{_SCRIPT.as_posix()}"\nvalidate "$1"\n'
    r = subprocess.run(
        [_BASH, "-c", script, "_", sample],
        capture_output=True, text=True, timeout=10,
    )
    return r.returncode == 0


class TestCrossReviewValidateContract(unittest.TestCase):
    def test_source_guard_skips_gemini_flow(self):
        # Sourcing must not fall into main() — no `gemini` binary or stdin
        # required just to reach validate().
        r = subprocess.run(
            [_BASH, "-c", f'source "{_SCRIPT.as_posix()}"; echo SOURCED'],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(r.returncode, 0, f"stderr={r.stderr!r}")
        self.assertIn("SOURCED", r.stdout)

    def test_no_issues_found_form_accepted(self):
        sample = (
            "NO ISSUES FOUND\n"
            "Reviewed: src/foo.py, src/bar.py\n"
            "Categories checked: spec adherence, edge cases, API design, "
            "security concerns without a lint rule, dead code, regressions"
        )
        self.assertTrue(_validate(sample))

    def test_defect_form_accepted(self):
        sample = (
            "DEFECT: src/code-review/scripts/cross-review.sh:42\n"
            "Spec says: validate() must reject prose\n"
            "Actual: it doesn't\n"
            "Minimal reproducer: 'looks good' -> accepted != rejected"
        )
        self.assertTrue(_validate(sample))

    def test_failing_test_fence_form_accepted(self):
        sample = (
            "```python\n"
            "# test_foo.py\n"
            "def test_it():\n"
            "    assert False\n"
            "```\n"
        )
        self.assertTrue(_validate(sample))

    def test_prose_only_response_rejected(self):
        sample = "This code looks good overall, consider adding error handling."
        self.assertFalse(_validate(sample))

    def test_fenced_block_without_path_comment_rejected(self):
        # A fence whose first line isn't a path comment doesn't satisfy
        # FORM 1 — otherwise a reviewer could fence arbitrary prose to slip
        # past the contract.
        sample = "```\nsome commentary, not a test\n```\n"
        self.assertFalse(_validate(sample))

    def test_defect_without_line_number_rejected(self):
        sample = "DEFECT: src/foo.py\nSpec says: x\nActual: y"
        self.assertFalse(_validate(sample))


if __name__ == "__main__":
    unittest.main()
