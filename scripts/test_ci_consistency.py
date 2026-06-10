"""test_ci_consistency.py — the local battery and CI must agree on "green".

The both-places rule says every gate in scripts/check-all.sh also runs in CI.
Nothing enforced that until now — this test does, by parsing the real files:

  1. Every gate script that check-all.sh runs appears as a step in
     tests-linux.yml (Linux runs the full battery).
  2. The known gate flags ride along (--strict on check-wiki, --all on
     check-no-pii) in both places.
  3. macOS + Windows keep their portability subset: check-syntax.ps1 and
     check-no-pii.sh --all. (They deliberately do NOT run the full battery —
     the Python toolchain gates are Linux-resident; see the CI design.)
  4. ci-all.yml's WORKFLOWS list points at workflow FILES that exist —
     the aggregate waits by filename, so a rename silently breaks it.

Runs as part of the battery itself (unittest discovery over scripts/).
Stdlib only; text-level parsing on purpose — it asserts what the files say,
not what a YAML loader normalizes them into.
"""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHECK_ALL = REPO / "scripts" / "check-all.sh"
WORKFLOWS_DIR = REPO / ".github" / "workflows"
LINUX = WORKFLOWS_DIR / "tests-linux.yml"
MAC = WORKFLOWS_DIR / "tests-mac.yml"
WINDOWS = WORKFLOWS_DIR / "tests-windows.yml"
CI_ALL = WORKFLOWS_DIR / "ci-all.yml"

GATE_FILE_RE = re.compile(r"[\w./*-]+\.(?:py|sh|ps1)\b")


def battery_gate_lines():
    """The `run "<name>" <cmd...>` lines from check-all.sh."""
    lines = []
    for line in CHECK_ALL.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith('run "'):
            lines.append(stripped)
    return lines


class TestBatteryMatchesLinuxWorkflow(unittest.TestCase):
    """Rule 1+2: the full battery runs in tests-linux.yml, flags included."""

    def setUp(self):
        self.linux = LINUX.read_text(encoding="utf-8")
        self.gates = battery_gate_lines()
        self.assertGreaterEqual(
            len(self.gates), 6, "check-all.sh should declare at least 6 gates"
        )

    def test_every_battery_gate_file_runs_on_linux(self):
        for gate in self.gates:
            tokens = GATE_FILE_RE.findall(gate)
            self.assertTrue(tokens, f"no script token found in gate line: {gate}")
            for token in tokens:
                # check-all runs scripts via their path; the workflow may too —
                # match on the basename so `scripts/x.py` == `x.py`.
                basename = token.rsplit("/", 1)[-1]
                self.assertIn(
                    basename,
                    self.linux,
                    f"battery gate references {basename!r} but tests-linux.yml "
                    f"never runs it — the both-places rule is broken "
                    f"(gate line: {gate})",
                )

    def test_gate_flags_match(self):
        battery = CHECK_ALL.read_text(encoding="utf-8")
        for script, flag in (("check-wiki.py", "--strict"), ("check-no-pii.sh", "--all")):
            for name, text in (("check-all.sh", battery), ("tests-linux.yml", self.linux)):
                pattern = re.compile(re.escape(script) + r"[^\n]*" + re.escape(flag))
                self.assertRegex(
                    text,
                    pattern,
                    f"{name} must run {script} with {flag}",
                )


class TestPortabilitySubset(unittest.TestCase):
    """Rule 3: mac + windows keep the OS-portability checks."""

    def test_mac_and_windows_run_ps1_syntax_and_pii(self):
        for path in (MAC, WINDOWS):
            text = path.read_text(encoding="utf-8")
            self.assertIn("check-syntax.ps1", text, f"{path.name} must AST-parse .ps1")
            self.assertRegex(
                text,
                re.compile(r"check-no-pii\.sh[^\n]*--all"),
                f"{path.name} must run the PII scan with --all",
            )

    def test_mac_also_checks_shell_syntax(self):
        self.assertIn("check-syntax.sh", MAC.read_text(encoding="utf-8"))


class TestAggregateFilenameCoupling(unittest.TestCase):
    """Rule 4: ci-all.yml's WORKFLOWS list matches real workflow files."""

    def test_workflows_list_files_exist(self):
        text = CI_ALL.read_text(encoding="utf-8")
        m = re.search(r'WORKFLOWS="([^"]+)"', text)
        self.assertIsNotNone(m, "ci-all.yml must declare WORKFLOWS=\"...\"")
        names = m.group(1).split()
        self.assertEqual(
            sorted(names),
            ["tests-linux", "tests-mac", "tests-windows"],
            "ci-all.yml's WORKFLOWS list changed — update this test + the CI design",
        )
        for name in names:
            self.assertTrue(
                (WORKFLOWS_DIR / f"{name}.yml").is_file(),
                f"ci-all.yml waits on {name}.yml, which does not exist — "
                f"the aggregate (and the badge) would hang/fail",
            )


if __name__ == "__main__":
    unittest.main()
