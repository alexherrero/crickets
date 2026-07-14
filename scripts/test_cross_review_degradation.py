#!/usr/bin/env python3
"""End-to-end tests for cross-review.sh's fallback visibility (crickets
Consolidation follow-ups batch; retargeted from `gemini` to `agy` in V8
proving Lane G, 2026-07-13).

test_cross_review_validate.py already proves the output-contract validator
in isolation (sourced, never reaching main()). This file drives the real
main() end to end against a MOCKED `agy` binary placed on PATH — no live
LLM calls, no network, no dependency on the actual Antigravity CLI being
installed.

Covers the three scenarios the fallback-visibility gap named:
  (a) a well-formed mocked reply passes through cleanly (exit 0).
  (b) a malformed/garbage reply triggers exactly one retry, then a clean
      rejection (exit 2) -- never a crash or a hang.
  (c) a missing `agy` binary triggers the fallback (exit 1) AND prints
      the visible "CROSS-REVIEW-DEGRADED: ..." marker on stdout, so a broken
      or absent agy CLI can never silently downgrade a "cross-model" review
      into a same-model one without a trace.

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
        self.assertEqual(result.returncode, 1, f"stderr={result.stderr!r}")
        self.assertIn(
            "CROSS-REVIEW-DEGRADED: agy CLI unavailable, using same-model reviewer",
            result.stdout,
        )


if __name__ == "__main__":
    unittest.main()
