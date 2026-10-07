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
_DIST_SCRIPT = _ROOT / "dist" / "claude-code" / "plugins" / "privacy" / "scripts" / "check-no-pii.sh"


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

# A 64-character lowercase-hex sha256 digest holding a ten-digit run that
# phone-us matches, the shape that tripped a pixelton art record
# (art/anchors/street-night.json line 7, 2026-10-06). About one random digest
# in six holds such a run. The run is split in two so this file's own source
# never holds it whole.
DIGIT_RUN = _join("59574", "54926")
SHA256_DIGEST = _join("1ca78c05be3f", DIGIT_RUN, "af0e7d3c9b1e4a6f2d8c0b7e5a3f1d9c4e2b6a8f0d")
COMMIT_SHA = "3f9a1c7e0b2d4f6a8c1e3b5d7f9a0c2e4b6d8f1a"  # 40 hex, no long digit run
PHONE = PLANTED["phone-us"]

# Lines holding only a sha256 key and its digest, in each form the line
# allowlist passes. crlf.json's lines end in a carriage return; on Windows
# every fixture file's do, since write_text turns each \n into \r\n.
SHA256_LINES: dict[str, str] = {
    "art/anchors/street-night.json": "\n".join([
        "{",
        '  "id": "street-night",',
        f'  "sha256": "{SHA256_DIGEST}",',
        '  "width": 320',
        "}",
        "",
    ]),
    "crlf.json": "\r\n".join(["{", f'  "sha256": "{SHA256_DIGEST}"', "}", ""]),
    "record.yaml": "\n".join([
        f"sha256: {SHA256_DIGEST}",
        "stand_ins:",
        f'  - sha256: "{SHA256_DIGEST}"',
        "    path: art/stand-ins/lamp.png",
        "",
    ]),
    "record.toml": f'sha256 = "{SHA256_DIGEST}"\n',
}

# What the sha256 entry must not pass: a phone number on another line, beside
# other hex, or beside the digest itself, and a digest outside that exact form.
SHA256_NEAR_MISSES: dict[str, str] = {
    "phone-below-digest.json": "\n".join([
        "{",
        f'  "sha256": "{SHA256_DIGEST}",',
        f'  "phone": "{PHONE}"',
        "}",
        "",
    ]),
    "commit-note.txt": f"Fixed in {COMMIT_SHA}; questions to {PHONE}.\n",
    "one-line.json": f'{{"sha256": "{SHA256_DIGEST}", "phone": "{PHONE}"}}\n',
    "checksum.json": "\n".join(["{", f'  "checksum": "{SHA256_DIGEST}"', "}", ""]),
    "not-64-lowercase.yaml": "\n".join([
        f"sha256: {SHA256_DIGEST}0",
        f"sha256: {SHA256_DIGEST.upper()}",
        "",
    ]),
}


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


def _run_scanner(repo: Path, script: Path = _SCRIPT) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_BASH, str(script), "--all"],
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


class TestSha256DigestLinesPass(unittest.TestCase):
    """A line holding only a sha256 key and its digest passes, though the
    digest's ten-digit run matches phone-us (LINE_ALLOWLIST_PATTERNS)."""

    @classmethod
    def setUpClass(cls):
        cls.repo = _make_fixture_repo(SHA256_LINES)
        cls.result = _run_scanner(cls.repo)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.repo, ignore_errors=True)

    def test_fixture_digest_is_a_sha256(self):
        self.assertRegex(SHA256_DIGEST, r"\A[0-9a-f]{64}\Z")

    def test_sha256_lines_pass(self):
        self.assertEqual(self.result.returncode, 0, f"stderr={self.result.stderr!r}")
        self.assertIn("clean (all mode)", self.result.stdout)


class TestSha256AllowlistStaysNarrow(unittest.TestCase):
    """The sha256 entry is anchored to the whole line, so it passes the digest
    and nothing else: every other finding near it still fails."""

    @classmethod
    def setUpClass(cls):
        cls.repo = _make_fixture_repo(SHA256_NEAR_MISSES)
        cls.result = _run_scanner(cls.repo)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.repo, ignore_errors=True)

    def assertPhoneFinding(self, where: str, match: str):
        self.assertIn(f"{where}: phone-us match: {match}", self.result.stderr)

    def test_scanner_exits_nonzero(self):
        self.assertEqual(self.result.returncode, 1, f"stdout={self.result.stdout!r}")

    def test_a_phone_number_on_a_non_sha256_line_fails(self):
        self.assertPhoneFinding("phone-below-digest.json:3", PHONE)
        # The sha256 line above it still passes: the entry is per line.
        self.assertNotIn("phone-below-digest.json:2:", self.result.stderr)

    def test_a_phone_number_beside_other_hex_fails(self):
        self.assertPhoneFinding("commit-note.txt:1", PHONE)

    def test_a_phone_number_beside_the_digest_fails(self):
        # One-line JSON: the line holds more than the key and its digest.
        self.assertPhoneFinding("one-line.json:1", PHONE)

    def test_the_digest_under_another_key_fails(self):
        # Also proves the fixture digest trips phone-us, so the passing class
        # above can't pass for want of a match.
        self.assertPhoneFinding("checksum.json:2", DIGIT_RUN)

    def test_a_digest_not_64_lowercase_hex_fails(self):
        self.assertPhoneFinding("not-64-lowercase.yaml:1", DIGIT_RUN)
        self.assertPhoneFinding("not-64-lowercase.yaml:2", DIGIT_RUN)


class TestPluginPayloadCopyCatchRate(unittest.TestCase):
    """R2.4 task 7: check-no-pii.sh must be reachable + fully functional from
    the *installed plugin location alone* — no sibling crickets checkout, no
    repo-root shim. Re-runs the exact same planted-PII fixture against the
    emitted dist/claude-code/plugins/pii/scripts/check-no-pii.sh copy.
    Skips gracefully (not a failure) if dist/ hasn't been built yet."""

    @classmethod
    def setUpClass(cls):
        if not _DIST_SCRIPT.is_file():
            raise unittest.SkipTest("dist/ not built — run scripts/generate.py build first")
        files = {f"planted-{kind}.txt": f"leading context\n{value}\ntrailing context\n"
                 for kind, value in PLANTED.items()}
        cls.repo = _make_fixture_repo(files)
        cls.result = _run_scanner(cls.repo, script=_DIST_SCRIPT)

    @classmethod
    def tearDownClass(cls):
        import shutil
        if hasattr(cls, "repo"):
            shutil.rmtree(cls.repo, ignore_errors=True)

    def test_dist_copy_catches_every_planted_category(self):
        stderr = self.result.stderr
        missing = [kind for kind in PLANTED if f"{kind} match:" not in stderr]
        self.assertEqual(missing, [], f"categories not caught by the dist copy: {missing}\nstderr={stderr}")
        self.assertEqual(self.result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
