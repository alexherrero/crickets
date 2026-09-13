#!/usr/bin/env python3
"""End-to-end tests for cross-review.sh's fallback visibility (crickets
Consolidation follow-ups batch; retargeted from `gemini` to `agy` in V8
proving Lane G, 2026-07-13; every fallback exit marked, 2026-09-13).

test_cross_review_validate.py already proves the output-contract validator
in isolation (sourced, never reaching main()). This file drives the real
main() end to end against a MOCKED `agy` binary placed on PATH — no live
LLM calls, no network, no dependency on the actual Antigravity CLI being
installed.

Covers:
  (a) a well-formed mocked reply passes through cleanly (exit 0).
  (b) a malformed/garbage reply triggers exactly one retry, then a clean
      rejection (exit 2) -- never a crash or a hang.
  (c) every fallback exit prints the visible "CROSS-REVIEW-DEGRADED: ..."
      marker as its only stdout line: a missing `agy`; agy printing nothing,
      on the first call or the retry; agy's print timeout, with or without
      part of an answer; a failed call; empty stdin; material over the size
      ceiling. A broken, absent or slow agy CLI can never silently downgrade
      a "cross-model" review into a same-model one without a trace.

The 2026-09-13 regression: agy ran into its 180s print timeout and exited 0
with nothing on stdout, and the script wrote only "agy call failed (exit
0)" to stderr. NoOutputTests reproduces that shape; it fails against 0.3.3.

stdlib only.
"""
from __future__ import annotations

import os
import stat
import subprocess
import tempfile
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


def _write_fake_agy(bin_dir: Path, body: str) -> Path:
    """Write an executable fake `agy` script into `bin_dir` that runs `body`
    on stdout. Ignores its own argv (`-p`/`--model`/`--print-timeout` etc.)
    same as a real CLI would just use them; the fake never needs to care
    what they are. Doesn't touch stdin -- the real cross-review.sh closes
    agy's stdin (`< /dev/null`) rather than piping the review material, so
    there is nothing to consume here (unlike the old `gemini` fake)."""
    path = bin_dir / "agy"
    path.write_text(f"#!/usr/bin/env bash\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _run_cross_review(material: str, *, path_prefix: "Path | None" = None,
                       env_extra: "dict | None" = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if path_prefix is not None:
        env["PATH"] = f"{path_prefix}{os.pathsep}{env.get('PATH', '')}"
    else:
        # Deliberately narrow PATH so a real `agy`, if one ever appeared on
        # this machine, can't leak into the "missing binary" scenario.
        env["PATH"] = os.pathsep.join(p for p in ("/usr/bin", "/bin") if Path(p).is_dir())
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [_BASH, str(_SCRIPT)],
        input=material, capture_output=True, text=True, timeout=15, env=env,
    )


# agy 1.2.2's stderr line when --print-timeout fires, verbatim from a live
# probe with a 1s timeout. agy then exits 0 with what it had, usually nothing.
_AGY_TIMEOUT_LINE = ("[agy] print timeout after 1s with turn in progress; "
                     "returning partial output")


def _run_main_with(material: str, prelude: str, *, path_prefix: Path) -> subprocess.CompletedProcess:
    """Source the script, run `prelude` (assignments standing in for values a
    test can't wait out, like the 180s print timeout), then call main()."""
    env = dict(os.environ)
    env["PATH"] = f"{path_prefix}{os.pathsep}{env.get('PATH', '')}"
    script = f'source "{_SCRIPT.as_posix()}"\n{prelude}\nmain\n'
    return subprocess.run(
        [_BASH, "-c", script],
        input=material, capture_output=True, text=True, timeout=15, env=env,
    )


def _degraded_line(test: unittest.TestCase, result: subprocess.CompletedProcess,
                   code: int) -> str:
    """The contract every fallback exit keeps: exit `code`, and stdout is one
    CROSS-REVIEW-DEGRADED line with nothing else. Returns that line."""
    test.assertEqual(result.returncode, code,
                     f"stdout={result.stdout!r} stderr={result.stderr!r}")
    lines = result.stdout.splitlines()
    test.assertEqual(len(lines), 1, f"stdout must be the marker alone: {result.stdout!r}")
    test.assertRegex(lines[0], r"^CROSS-REVIEW-DEGRADED: .+, using same-model reviewer$")
    return lines[0]


class WellFormedReplyTests(unittest.TestCase):
    def test_well_formed_reply_passes_through_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            _write_fake_agy(bin_dir, (
                'echo "NO ISSUES FOUND"\n'
                'echo "Reviewed: src/foo.py"\n'
                'echo "Categories checked: spec adherence, edge cases, API design, '
                'security concerns without a lint rule, dead code, regressions"\n'
            ))
            result = _run_cross_review("=== DIFF ===\nsome diff\n", path_prefix=bin_dir)
            self.assertEqual(result.returncode, 0, f"stderr={result.stderr!r}")
            self.assertIn("NO ISSUES FOUND", result.stdout)
            self.assertNotIn("CROSS-REVIEW-DEGRADED", result.stdout)


class MalformedReplyRetryTests(unittest.TestCase):
    def test_malformed_reply_retries_exactly_once_then_rejects_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            counter = Path(tmp) / "agy_calls.count"
            _write_fake_agy(bin_dir, (
                'n=0\n'
                f'[[ -f "{counter}" ]] && n=$(cat "{counter}")\n'
                'n=$((n + 1))\n'
                f'echo "$n" > "{counter}"\n'
                'echo "This looks fine overall, consider adding a few comments."\n'
            ))
            result = _run_cross_review("=== DIFF ===\nsome diff\n", path_prefix=bin_dir)
            # Never a crash/hang — a clean, deterministic rejection.
            self.assertEqual(result.returncode, 2, f"stderr={result.stderr!r}")
            self.assertIn(
                "CROSS-REVIEW-DEGRADED: agy response violated the output "
                "contract twice, using same-model reviewer",
                result.stdout,
            )
            # Exactly one retry: the initial call plus one more, never a
            # third attempt.
            self.assertEqual(counter.read_text(encoding="utf-8").strip(), "2")


class MissingBinaryTests(unittest.TestCase):
    def test_missing_binary_falls_back_with_visible_degradation_marker(self):
        result = _run_cross_review("=== DIFF ===\nsome diff\n")
        self.assertEqual(
            _degraded_line(self, result, 1),
            "CROSS-REVIEW-DEGRADED: agy CLI unavailable, using same-model reviewer",
        )


class NoOutputTests(unittest.TestCase):
    """agy ending without an answer is a fallback exit like any other."""

    def test_agy_printing_nothing_and_exiting_zero_prints_the_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            _write_fake_agy(bin_dir, "exit 0")
            result = _run_cross_review("=== DIFF ===\nsome diff\n", path_prefix=bin_dir)
            line = _degraded_line(self, result, 1)
            self.assertIn("agy returned no output (exit 0 after ", line)
            self.assertIn("before its 180s print timeout", line)

    def test_print_timeout_agy_reports_is_named_in_the_marker(self):
        # The 2026-09-13 shape: empty stdout, exit 0, and agy's own timeout
        # line on stderr, which 0.3.3 sent to /dev/null.
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            _write_fake_agy(bin_dir, f'echo "{_AGY_TIMEOUT_LINE}" >&2\nexit 0')
            result = _run_cross_review("=== DIFF ===\nsome diff\n", path_prefix=bin_dir)
            line = _degraded_line(self, result, 1)
            self.assertIn("agy returned no output (exit 0 after ", line)
            self.assertIn("its 180s print timeout fired", line)
            self.assertIn(_AGY_TIMEOUT_LINE, result.stderr)

    def test_silent_call_as_long_as_the_timeout_says_it_may_have_fired(self):
        # No timeout line from agy, but the call lasted the whole print
        # timeout. PRINT_TIMEOUT_SECS=1 stands in for the real 180s.
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            _write_fake_agy(bin_dir, "sleep 2\nexit 0")
            result = _run_main_with("=== DIFF ===\nsome diff\n", "PRINT_TIMEOUT_SECS=1",
                                    path_prefix=bin_dir)
            line = _degraded_line(self, result, 1)
            self.assertIn("agy returned no output (exit 0 after ", line)
            self.assertIn("its 1s print timeout may have fired", line)

    def test_nonzero_exit_with_no_output_prints_the_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            _write_fake_agy(bin_dir, 'echo "agy: not signed in" >&2\nexit 3')
            result = _run_cross_review("=== DIFF ===\nsome diff\n", path_prefix=bin_dir)
            line = _degraded_line(self, result, 1)
            self.assertIn("agy returned no output (exit 3 after ", line)
            self.assertIn("before its 180s print timeout", line)
            self.assertIn("agy: not signed in", result.stderr)

    def test_retry_that_returns_nothing_prints_the_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            counter = Path(tmp) / "agy_calls.count"
            _write_fake_agy(bin_dir, (
                'n=0\n'
                f'[[ -f "{counter}" ]] && n=$(cat "{counter}")\n'
                'n=$((n + 1))\n'
                f'echo "$n" > "{counter}"\n'
                'if [[ $n -eq 1 ]]; then echo "This looks fine overall."; fi\n'
                'exit 0\n'
            ))
            result = _run_cross_review("=== DIFF ===\nsome diff\n", path_prefix=bin_dir)
            line = _degraded_line(self, result, 1)
            self.assertIn("agy returned no output on retry (exit 0 after ", line)
            self.assertEqual(counter.read_text(encoding="utf-8").strip(), "2")


class CutOffOrFailedReplyTests(unittest.TestCase):
    def test_timeout_with_partial_output_is_not_passed_off_as_a_review(self):
        # A cut-off answer can open with a line validate() accepts.
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            _write_fake_agy(bin_dir, (
                f'echo "{_AGY_TIMEOUT_LINE}" >&2\n'
                'echo "DEFECT: src/foo.py:12"\n'
                'echo "Spec says: the parser rejects"\n'
            ))
            result = _run_cross_review("=== DIFF ===\nsome diff\n", path_prefix=bin_dir)
            line = _degraded_line(self, result, 1)
            self.assertIn("agy returned partial output (exit 0 after ", line)
            self.assertIn("its 180s print timeout fired", line)
            self.assertIn("DEFECT: src/foo.py:12", result.stderr)

    def test_timed_out_chatter_above_a_finished_answer_passes_through(self):
        # Only agy's own print-timeout line means the answer was cut off.
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            _write_fake_agy(bin_dir, (
                'echo "request timed out, retrying" >&2\n'
                'echo "NO ISSUES FOUND"\n'
                'echo "Reviewed: src/foo.py"\n'
            ))
            result = _run_cross_review("=== DIFF ===\nsome diff\n", path_prefix=bin_dir)
            self.assertEqual(result.returncode, 0, f"stderr={result.stderr!r}")
            self.assertIn("NO ISSUES FOUND", result.stdout)
            self.assertNotIn("CROSS-REVIEW-DEGRADED", result.stdout)

    def test_nonzero_exit_with_output_prints_the_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            _write_fake_agy(bin_dir, 'echo "NO ISSUES FOUND"\nexit 2')
            result = _run_cross_review("=== DIFF ===\nsome diff\n", path_prefix=bin_dir)
            line = _degraded_line(self, result, 1)
            self.assertIn("agy failed (exit 2 after ", line)
            self.assertIn("NO ISSUES FOUND", result.stderr)


class NoMaterialTests(unittest.TestCase):
    def test_empty_stdin_prints_the_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            _write_fake_agy(bin_dir, 'echo "NO ISSUES FOUND"')
            result = _run_cross_review("", path_prefix=bin_dir)
            self.assertEqual(
                _degraded_line(self, result, 2),
                "CROSS-REVIEW-DEGRADED: no review material on stdin, using same-model reviewer",
            )


class MaterialCeilingTests(unittest.TestCase):
    """Material too big for an answer inside agy's print timeout degrades
    before agy is called, instead of spending the timeout. Materials carry no
    newlines, so their byte counts match on every platform."""

    def test_the_agentm_plan_07_material_degrades_without_calling_agy(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            called = Path(tmp) / "agy_called"
            _write_fake_agy(bin_dir, f'touch "{called}"\necho "NO ISSUES FOUND"')
            # 216,549 bytes: that review's whole material.
            result = _run_cross_review("x" * 216_549, path_prefix=bin_dir)
            self.assertEqual(
                _degraded_line(self, result, 1),
                "CROSS-REVIEW-DEGRADED: review material is 216549 bytes, over the "
                "50000-byte ceiling for agy's 180s print timeout, using same-model reviewer",
            )
            self.assertFalse(called.exists(), "agy must not be called over the ceiling")

    def test_material_at_the_ceiling_still_goes_to_agy(self):
        # MAX_MATERIAL_BYTES=200 stands in for the real ceiling, so no test
        # pushes 50 KB through agy's argv.
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            _write_fake_agy(bin_dir, 'echo "NO ISSUES FOUND"')
            result = _run_main_with("x" * 200, "MAX_MATERIAL_BYTES=200", path_prefix=bin_dir)
            self.assertEqual(result.returncode, 0, f"stderr={result.stderr!r}")
            self.assertEqual(result.stdout, "NO ISSUES FOUND\n")

    def test_override_sets_another_ceiling(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            _write_fake_agy(bin_dir, 'echo "NO ISSUES FOUND"')
            result = _run_cross_review("x" * 200, path_prefix=bin_dir,
                                       env_extra={"CROSS_REVIEW_MAX_BYTES": "100"})
            line = _degraded_line(self, result, 1)
            self.assertIn("review material is 200 bytes, over the 100-byte ceiling", line)

    def test_override_of_zero_turns_the_check_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            _write_fake_agy(bin_dir, 'echo "NO ISSUES FOUND"')
            result = _run_main_with("x" * 200, "MAX_MATERIAL_BYTES=10\nCROSS_REVIEW_MAX_BYTES=0",
                                    path_prefix=bin_dir)
            self.assertEqual(result.returncode, 0, f"stderr={result.stderr!r}")
            self.assertEqual(result.stdout, "NO ISSUES FOUND\n")

    def test_override_that_is_not_a_byte_count_is_ignored_out_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            _write_fake_agy(bin_dir, 'echo "NO ISSUES FOUND"')
            result = _run_main_with("x" * 200, "MAX_MATERIAL_BYTES=100\nCROSS_REVIEW_MAX_BYTES=50KB",
                                    path_prefix=bin_dir)
            line = _degraded_line(self, result, 1)
            self.assertIn("over the 100-byte ceiling", line)
            self.assertIn("ignoring CROSS_REVIEW_MAX_BYTES='50KB'", result.stderr)


if __name__ == "__main__":
    unittest.main()
