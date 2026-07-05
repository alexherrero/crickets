#!/usr/bin/env python3
"""Catch-rate fixture for check-no-pii.sh (R2.4 task 2).

check-no-pii.sh claims to detect 9 categories (its own PATTERNS array):
email, personal-path-{mac,linux,windows}, openai-key, github-token,
gitlab-token, aws-access-key, phone-us. There was no fixture proving it
actually catches each one, nor one proving clean content produces zero
false positives — coverage was purely incidental (whatever the real repo
happens to contain).

Every planted string below is assembled from concatenated parts rather than
written as one contiguous literal — a real, unescaped literal (e.g. a bare
email address) sitting in this file's own source would itself trip
check-no-pii.sh when it scans *this repo*. Assembling at import/call time
means the matching string exists only inside the disposable fixture repo
this test builds, never in this file's tracked source.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPT = _ROOT / "scripts" / "check-no-pii.sh"


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
    return "bash"


_BASH = _find_bash()


def _join(*parts: str) -> str:
    return "".join(parts)


# One assembled, non-allowlisted planted instance per PATTERNS category.
PLANTED: dict[str, str] = {
    "email": _join("bob", "@", "personalmail", ".", "com"),
    "personal-path-mac": _join("/Users/", "jsmith", "/secret-notes.txt"),
    "personal-path-linux": _join("/home/", "jsmith", "/secret-notes.txt"),
    "personal-path-windows": _join("C:", "\\", "Users", "\\", "jsmith", "\\secret.txt"),
    "openai-key": _join("sk-", "a1B2c3D4e5F6g7H8i9J0k1L2"),
    "github-token": _join("gh", "p_", "aB1cD2eF3gH4iJ5kL6mN7oP8"),
    "gitlab-token": _join("glpat-", "aB1cD2eF3gH4iJ5kL6mN7oP8"),
    "aws-access-key": _join("AKIA", "1234567890ABCDEF"),
    "phone-us": _join("(415) ", "867", "-", "5309"),
}

# Deliberately allowlist-shaped content: an RFC 2606 domain, the public
# handle, the NANP-reserved 555-01xx prefix, and the documented example
# key shapes — every category's "safe-looking twin," asserted to produce
# zero findings so the catch-rate isn't just "the scanner fires on anything."
CLEAN_CONTROL = "\n".join([
    _join("Contact: someone", "@", "example", ".", "com"),
    "Maintained by alexherrero.",
    _join("Support line: 555", "-", "0142"),
    _join("Example key: sk-", "abc123def456ghi789jkl"),
    _join("Example AWS key: AKIA", "123456789EXAMPLE"),  # AKIA+16 chars, ends in EXAMPLE
    "No real secrets here — just documentation prose.",
    "",
])


def _run_git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                    capture_output=True, text=True)


def _make_fixture_repo(files: dict[str, str]) -> Path:
    tmp = Path(tempfile.mkdtemp())
    _run_git(["init", "-q"], tmp)
    _run_git(["config", "user.email", "fixture@example.com"], tmp)
    _run_git(["config", "user.name", "fixture"], tmp)
    for rel, content in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    _run_git(["add", "-A"], tmp)
    return tmp


def _run_scanner(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_BASH, str(_SCRIPT), "--all"],
        cwd=repo, capture_output=True, text=True, timeout=30,
    )


class TestPlantedPiiCatchRate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        files = {f"planted-{kind}.txt": f"leading context\n{value}\ntrailing context\n"
                 for kind, value in PLANTED.items()}
        cls.repo = _make_fixture_repo(files)
        cls.result = _run_scanner(cls.repo)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.repo, ignore_errors=True)

    def test_scanner_exits_nonzero_on_findings(self):
        self.assertEqual(self.result.returncode, 1, f"stdout={self.result.stdout!r}")

    def test_every_planted_category_is_caught(self):
        stderr = self.result.stderr
        missing = [kind for kind in PLANTED if f"{kind} match:" not in stderr]
        self.assertEqual(missing, [], f"categories not caught: {missing}\nstderr={stderr}")

    def test_finding_count_matches_planted_count(self):
        # One finding per planted file — proves the catch-rate is exactly
        # 9-for-9, not "some matched, some over- or under-counted."
        self.assertIn(f"{len(PLANTED)} finding(s)", self.result.stderr)


class TestCleanControlZeroFalsePositives(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = _make_fixture_repo({"clean.txt": CLEAN_CONTROL})
        cls.result = _run_scanner(cls.repo)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.repo, ignore_errors=True)

    def test_scanner_exits_clean(self):
        self.assertEqual(self.result.returncode, 0, f"stderr={self.result.stderr!r}")

    def test_no_findings_reported(self):
        self.assertIn("clean (all mode)", self.result.stdout)
        self.assertNotIn("finding(s)", self.result.stderr)


if __name__ == "__main__":
    unittest.main()
