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
# allowlist passes, and a Git LFS pointer, whose oid line is one more such
# form. crlf.json's lines end in a carriage return; on Windows every fixture
# file's do, since write_text turns each \n into \r\n.
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
    # What a clone without the LFS objects holds in place of the image.
    "art/anchors/street-night.jpg": "\n".join([
        "version https://git-lfs.github.com/spec/v1",
        f"oid sha256:{SHA256_DIGEST}",
        "size 735812",
        "",
    ]),
}

# What the sha256 entries must not pass: a phone number on another line, beside
# other hex, or beside the digest itself.
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
    "pointer-near-miss.txt": f"oid sha256:{SHA256_DIGEST} {PHONE}\n",
}

# A phone-shaped run of digits inside something longer is not a phone number
# (privacy 0.6.5): inside hex, after a decimal point, or in a longer integer.
# These are the kinds behind all but one of the 1,215 findings on pixelton's
# townsfolk spike, in results files and rust/Cargo.lock (the other was a seed
# written alone, which still fails). The digests are 64 hex characters; the
# run sits inside one, opens another and closes a third, and a fourth holds an
# eleven-digit run. TASK_DIGEST is the one the task named.
RUN = _join("64845", "41710")
TASK_DIGEST = _join("8ce6a5fc2ba0e956d04e4afd", RUN, "bc4433e1e23d636d59fd44e97883c6")
DIGEST_OPENING_WITH_RUN = _join(RUN, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca49599")
DIGEST_CLOSING_WITH_RUN = _join("9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c", RUN)
DIGEST_WITH_ELEVEN = _join("a3f1c9e2b7d04f6a8c2e", "46955", "971101", "c8e4f2a6b0d9c7e5a3f1b9d7e5c3a1f9e")

CARGO_LOCK = "\n".join([
    "[[package]]",
    'name = "serde"',
    'version = "1.0.210"',
    'source = "registry+https://github.com/rust-lang/crates.io-index"',
    f'checksum = "{DIGEST_OPENING_WITH_RUN}"',
    "",
    "[[package]]",
    'name = "serde_json"',
    'version = "1.0.128"',
    'source = "registry+https://github.com/rust-lang/crates.io-index"',
    f'checksum = "{DIGEST_CLOSING_WITH_RUN}"',
    "",
    "[[package]]",
    'name = "libc"',
    'version = "0.2.159"',
    'source = "registry+https://github.com/rust-lang/crates.io-index"',
    f'checksum = "{DIGEST_WITH_ELEVEN}"',
    "",
])

FLOATS_AND_INTEGERS = "\n".join([
    "{",
    f'  "mean_s": {_join("1.58287", "30059")},',         # the task's decimal
    f'  "p99_s": {_join("0.64845", "41710")},',
    f'  "min_s": {_join("-2.64845", "41710")}e-05,',
    f'  "elapsed_ms": {_join("41586", "75309")}.25,',   # a decimal's whole part
    f'  "bytes": {_join("182050", "00000")}',           # the task's integer
    "}",
    "",
])

NOT_PHONE_NUMBERS: dict[str, str] = {
    "results/hashes.txt": f"hold-100000 {TASK_DIGEST}\n",
    "results/summary.json": FLOATS_AND_INTEGERS,
    "results/runs.csv": "\n".join([
        "run,bytes,mean_s,hash",
        f"grow,{_join('182050', '00000')},{_join('1.58287', '30059')},{DIGEST_WITH_ELEVEN}",
        "",
    ]),
    "rust/Cargo.lock": CARGO_LOCK,
    # Digests the sha256 and oid line allowlist entries don't pass. Before
    # 0.6.5 each one was a finding.
    "checksum.json": "\n".join(["{", f'  "checksum": "{SHA256_DIGEST}"', "}", ""]),
    "not-64-lowercase.yaml": "\n".join([
        f"sha256: {SHA256_DIGEST}0",
        f"sha256: {SHA256_DIGEST.upper()}",
        "",
    ]),
    "pointer-65-hex.txt": f"oid sha256:{SHA256_DIGEST}0\n",
}

# Phone numbers still fail, in each form the task named, and beside a digest.
# The task's 555-0123 sits in the reserved 555-0100..555-0199 range that
# ALLOWLIST_PATTERNS passes (CLEAN_CONTROL checks it), and seven digits were
# never a match, so its dashed form is tested as a ten-digit number.
DASHED = _join("415-", "867", "-5309")
BRACKETED = _join("(555) ", "010", "-", "1234")
DOTTED = _join("555.", "010", ".1234")
BARE = _join("41586", "75309")
E164 = _join("+1", "41586", "75309")

# (file, line, what the scanner reports for it)
PHONE_LINES: list[tuple[str, str, str]] = [
    ("dashed.txt", f"Call {DASHED} today", DASHED),
    ("bracketed.txt", f"Office: {BRACKETED}", BRACKETED),
    ("dotted.txt", f"Fax {DOTTED}", DOTTED),
    ("bare.txt", f"call {BARE} today", BARE),
    ("e164.json", f'{{"phone": "{E164}"}}', E164),
    # A full stop after a number is not a decimal point.
    ("sentence.md", f"Ring {BRACKETED}.", BRACKETED),
    # The run inside the digest passes; the number beside it doesn't.
    ("beside-a-digest.txt", f"{TASK_DIGEST} {BARE}", BARE),
]


def _run_git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                    capture_output=True, text=True)


def _make_fixture_repo(files: dict[str, str]) -> Path:
    tmp = Path(tempfile.mkdtemp())
    _run_git(["init", "-q"], tmp)
    _run_git(["config", "user.email", "fixture@example.com"], tmp)
    _run_git(["config", "user.name", "fixture"], tmp)
    _write_files(tmp, files)
    _run_git(["add", "-A"], tmp)
    return tmp


def _write_files(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def _make_history_repo(committed: dict[str, str], staged: dict[str, str]) -> Path:
    """A base commit, a second commit that adds `committed`, and `staged` in
    the index: --diff HEAD~1..HEAD scans `committed`, --staged scans `staged`,
    and --all scans both."""
    tmp = _make_fixture_repo({"README.md": "base\n"})
    _run_git(["config", "commit.gpgsign", "false"], tmp)
    _run_git(["commit", "-q", "-m", "base"], tmp)
    _write_files(tmp, committed)
    _run_git(["add", "-A"], tmp)
    _run_git(["commit", "-q", "-m", "data"], tmp)
    _write_files(tmp, staged)
    _run_git(["add", "-A"], tmp)
    return tmp


def _run_scanner(repo: Path, script: Path = _SCRIPT,
                 args: tuple[str, ...] = ("--all",)) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_BASH, str(script), *args],
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
    """A line holding only a sha256 key and its digest, or a Git LFS pointer's
    oid line, passes. The line allowlist passes it, and since 0.6.5 the
    stand-alone check does too."""

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

    def test_fixture_digest_holds_a_phone_shaped_run(self):
        # Ten digits starting with 2-9, which phone-us matches before the
        # stand-alone check, so these lines can't pass for want of a match.
        self.assertRegex(SHA256_DIGEST, r"[2-9][0-9]{9}")

    def test_sha256_lines_pass(self):
        self.assertEqual(self.result.returncode, 0, f"stderr={self.result.stderr!r}")
        self.assertIn("clean (all mode)", self.result.stdout)


class TestSha256AllowlistStaysNarrow(unittest.TestCase):
    """The sha256 entries are anchored to the whole line, so they pass the
    digest and nothing else: every other finding near it still fails."""

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

    def test_an_oid_line_holding_more_than_the_digest_fails(self):
        # A phone number after a 64-hex oid.
        self.assertPhoneFinding("pointer-near-miss.txt:1", PHONE)

    # Until 0.6.5 a digest under another key, at 65 characters or in
    # uppercase failed here, and so did a 65-hex oid line. Their runs are
    # inside hex, so they now pass: TestDigitRunsInLongerTokensPass covers them.


class TestDigitRunsInLongerTokensPass(unittest.TestCase):
    """A phone-shaped run inside hex, after a decimal point or in a longer
    integer is not a phone number (privacy 0.6.5)."""

    @classmethod
    def setUpClass(cls):
        cls.repo = _make_fixture_repo(NOT_PHONE_NUMBERS)
        cls.result = _run_scanner(cls.repo)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.repo, ignore_errors=True)

    def test_fixture_digests_are_64_hex(self):
        for digest in (TASK_DIGEST, DIGEST_OPENING_WITH_RUN,
                       DIGEST_CLOSING_WITH_RUN, DIGEST_WITH_ELEVEN):
            self.assertRegex(digest, r"\A[0-9a-f]{64}\Z")

    def test_every_fixture_holds_a_phone_shaped_run(self):
        # Ten digits starting with 2-9: before 0.6.5 phone-us reported each
        # of these files, so each passes now only by the stand-alone check.
        for rel, content in NOT_PHONE_NUMBERS.items():
            with self.subTest(file=rel):
                self.assertRegex(content, r"[2-9][0-9]{9}")

    def test_scanner_exits_clean(self):
        self.assertEqual(self.result.returncode, 0, f"stderr={self.result.stderr!r}")
        self.assertIn("clean (all mode)", self.result.stdout)
        self.assertNotIn("finding(s)", self.result.stderr)


class TestPhoneNumbersStillFail(unittest.TestCase):
    """A phone number still fails in each form the task named, alone or
    beside a digest whose own run passes."""

    @classmethod
    def setUpClass(cls):
        cls.repo = _make_fixture_repo({rel: f"{line}\n" for rel, line, _ in PHONE_LINES})
        cls.result = _run_scanner(cls.repo)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.repo, ignore_errors=True)

    def test_scanner_exits_nonzero(self):
        self.assertEqual(self.result.returncode, 1, f"stdout={self.result.stdout!r}")

    def test_each_number_is_reported_as_written(self):
        for rel, _, match in PHONE_LINES:
            with self.subTest(file=rel):
                self.assertIn(f"{rel}:1: phone-us match: {match}\n", self.result.stderr)

    def test_one_finding_for_each_number(self):
        # The digest beside the last number adds none.
        self.assertIn(f"check-no-pii: {len(PHONE_LINES)} finding(s) in all mode",
                      self.result.stderr)
        self.assertNotIn(f"match: {RUN}", self.result.stderr)


class TestEveryModeUsesTheStandAloneCheck(unittest.TestCase):
    """--all, --staged and --diff share one scan: each passes the digit runs
    and still fails a phone number, with the exit codes it always had."""

    MODES = {
        "all": ("--all",),
        "staged": ("--staged",),
        "diff": ("--diff", "HEAD~1..HEAD"),
    }

    @classmethod
    def setUpClass(cls):
        committed = {"results/summary.json": FLOATS_AND_INTEGERS, "rust/Cargo.lock": CARGO_LOCK}
        staged = {"results/hashes.txt": f"hold-100000 {TASK_DIGEST}\n"}
        cls.clean_repo = _make_history_repo(committed, staged)
        cls.phone_repo = _make_history_repo(
            {**committed, "contact.txt": f"Call {DASHED} today\n"},
            {**staged, "notes.txt": f"Office: {BRACKETED}\n"},
        )

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.clean_repo, ignore_errors=True)
        shutil.rmtree(cls.phone_repo, ignore_errors=True)

    def test_digit_runs_pass_in_every_mode(self):
        for mode, args in self.MODES.items():
            with self.subTest(mode=mode):
                result = _run_scanner(self.clean_repo, args=args)
                self.assertEqual(result.returncode, 0, f"stderr={result.stderr!r}")
                self.assertIn(f"clean ({mode} mode)", result.stdout)

    def test_a_phone_number_fails_in_every_mode(self):
        contact = f"contact.txt:1: phone-us match: {DASHED}"
        notes = f"notes.txt:1: phone-us match: {BRACKETED}"
        expected = {"all": [contact, notes], "staged": [notes], "diff": [contact]}
        for mode, args in self.MODES.items():
            with self.subTest(mode=mode):
                result = _run_scanner(self.phone_repo, args=args)
                self.assertEqual(result.returncode, 1, f"stdout={result.stdout!r}")
                for finding in expected[mode]:
                    self.assertIn(finding, result.stderr)
                self.assertIn(f"check-no-pii: {len(expected[mode])} finding(s) in {mode} mode",
                              result.stderr)


class TestArgumentErrorsExitTwo(unittest.TestCase):
    """A bad argument still exits 2, before any scan."""

    @classmethod
    def setUpClass(cls):
        cls.repo = _make_fixture_repo({"README.md": "base\n"})

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.repo, ignore_errors=True)

    def test_diff_without_a_range(self):
        self.assertEqual(_run_scanner(self.repo, args=("--diff",)).returncode, 2)

    def test_an_unknown_argument(self):
        self.assertEqual(_run_scanner(self.repo, args=("--everything",)).returncode, 2)


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
        cls.digits_repo = _make_fixture_repo(NOT_PHONE_NUMBERS)
        cls.digits_result = _run_scanner(cls.digits_repo, script=_DIST_SCRIPT)

    @classmethod
    def tearDownClass(cls):
        import shutil
        for name in ("repo", "digits_repo"):
            if hasattr(cls, name):
                shutil.rmtree(getattr(cls, name), ignore_errors=True)

    def test_dist_copy_catches_every_planted_category(self):
        stderr = self.result.stderr
        missing = [kind for kind in PLANTED if f"{kind} match:" not in stderr]
        self.assertEqual(missing, [], f"categories not caught by the dist copy: {missing}\nstderr={stderr}")
        self.assertEqual(self.result.returncode, 1)

    def test_dist_copy_passes_digit_runs_in_longer_tokens(self):
        self.assertEqual(self.digits_result.returncode, 0,
                         f"stderr={self.digits_result.stderr!r}")


if __name__ == "__main__":
    unittest.main()
