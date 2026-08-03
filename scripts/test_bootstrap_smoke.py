#!/usr/bin/env python3
"""Bootstrap smoke test (R2.1) — proves bootstrap.sh's own install-orchestration
logic actually works end-to-end, into a scratch $HOME, before this task no test
covered it at all.

`bootstrap.sh` is a THIN wrapper over each host's NATIVE `plugin install` — it
never parses manifests or copies primitives itself. So the thing worth proving
end-to-end is bootstrap.sh's OWN logic: `CRICKETS_REPO` resolution (skip the
clone when a checkout already exists), `default-set.json` parsing, the
per-plugin install loop for each host (continue-on-WARN), and the graceful
"neither host found" exit path.

Fakes `claude` and `agy` as recording stubs (log argv, always exit 0) rather
than the real CLIs — a smoke test must never perform a real
`claude plugin install --scope user` against the machine it runs on. `PATH` is
built from a stub-only dir + a minimal `/usr/bin:/bin` (never the real
`claude`/`agy` install location), so a test that forgets to write a stub
genuinely exercises the "host not found" path instead of silently reaching a
real host CLI.

POSIX-only (bash script) — matches the existing precedent for hook-execution
smoke tests (test_conflict_merger_hook.py).
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_BOOTSTRAP = _REPO / "bootstrap.sh"
_DEFAULT_SET = _REPO / "dist" / "default-set.json"


def _write_stub(path: Path, log_path: Path) -> None:
    """A fake host CLI: appends its own argv to `log_path`, always exits 0."""
    path.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$(basename "$0") $*" >> "{log_path}"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


@unittest.skipIf(os.name == "nt", "bootstrap.sh — POSIX bash script only")
@unittest.skipUnless(_BOOTSTRAP.is_file(), f"{_BOOTSTRAP} not present")
@unittest.skipUnless(_DEFAULT_SET.is_file(),
                      "dist/default-set.json not present — run `python3 scripts/generate.py build` first")
class TestBootstrapSmoke(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls.log"
        self.plugins = json.loads(_DEFAULT_SET.read_text(encoding="utf-8"))["plugins"]

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _log_lines(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.is_file() else []

    def _env(self, repo: Path = _REPO) -> dict:
        env = dict(os.environ)
        env["HOME"] = str(self.home)
        env["CRICKETS_REPO"] = str(repo)  # skip the network clone — use this checkout
        # Stub dir first, then a minimal real PATH for python3/git/bash the
        # script itself needs — deliberately NOT the real claude/agy location.
        env["PATH"] = f"{self.bin}:/usr/bin:/bin"
        return env

    def _run(self, repo: Path = _REPO) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(_BOOTSTRAP)], env=self._env(repo), cwd=str(self.home),
            capture_output=True, text=True, timeout=60,
        )

    def test_neither_host_present_exits_1_gracefully(self) -> None:
        result = self._run()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("neither 'claude' nor 'agy' found on PATH", result.stderr)
        self.assertEqual(self._log_lines(), [])

    def test_both_hosts_present_installs_every_default_set_plugin(self) -> None:
        _write_stub(self.bin / "claude", self.log)
        _write_stub(self.bin / "agy", self.log)
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("recommended plugins (install order):", result.stdout)
        for p in self.plugins:
            self.assertIn(p, result.stdout)
        self.assertIn("done. Installed crickets plugins for the detected host(s).", result.stdout)

        lines = self._log_lines()
        claude_installs = [ln for ln in lines if ln.startswith("claude plugin install ")]
        agy_installs = [ln for ln in lines if ln.startswith("agy plugin install ")]
        self.assertEqual(len(claude_installs), len(self.plugins), lines)
        self.assertEqual(len(agy_installs), len(self.plugins), lines)
        for p in self.plugins:
            self.assertTrue(any(f"{p}@crickets --scope user" in ln for ln in claude_installs), lines)
            self.assertTrue(any(f"antigravity/plugins/{p}" in ln for ln in agy_installs), lines)
        self.assertTrue(any(ln.startswith("claude plugin marketplace add") for ln in lines), lines)

    def test_agy_installs_development_lifecycle_before_everything_requiring_it(self) -> None:
        """`agy` resolves no cross-plugin deps, so bootstrap must order the loop.
        Real-catalog check; the adversarial-name case is the next test."""
        _write_stub(self.bin / "agy", self.log)
        self.assertEqual(self._run().returncode, 0)
        installed = [ln.rsplit("/", 1)[-1] for ln in self._log_lines()
                     if ln.startswith("agy plugin install ")]
        market = json.loads(
            (_REPO / "dist" / "claude-code" / ".claude-plugin" / "marketplace.json")
            .read_text(encoding="utf-8"))
        dependents = [e["name"] for e in market["plugins"]
                      if "development-lifecycle" in (e.get("dependencies") or [])]
        self.assertTrue(dependents, "no plugin requires development-lifecycle — fixture is stale")
        base = installed.index("development-lifecycle")
        for name in dependents:
            self.assertGreater(installed.index(name), base,
                               f"{name} requires development-lifecycle but installs first: {installed}")

    def test_agy_order_holds_when_the_dependent_sorts_first_alphabetically(self) -> None:
        """The case today's catalog cannot exercise: `development-lifecycle`
        already sorts ahead of all six dependents, so alphabetical order passes
        the test above by accident. Here the dependent (`aardvark`) sorts FIRST
        and requires a capability whose provider (`zulu`) sorts LAST — and the
        capability name matches neither directory, as a renamed plugin's would.
        """
        repo = self.root / "fixture-repo"
        (repo / ".git").mkdir(parents=True)          # present ⇒ bootstrap skips the clone
        (repo / "scripts").mkdir()
        (repo / "scripts" / "resolve_install_order.py").write_bytes(
            (_REPO / "scripts" / "resolve_install_order.py").read_bytes())
        dist = repo / "dist"
        (dist / "claude-code" / ".claude-plugin").mkdir(parents=True)
        (dist / "default-set.json").write_text(
            json.dumps({"plugins": ["aardvark", "zulu"]}), encoding="utf-8")
        (dist / "claude-code" / ".claude-plugin" / "marketplace.json").write_text(
            json.dumps({"name": "crickets", "plugins": [
                {"name": "aardvark", "dependencies": ["zebra-power"]},
                {"name": "zulu", "capabilities": ["zebra-power"]},
            ]}), encoding="utf-8")

        _write_stub(self.bin / "agy", self.log)
        result = self._run(repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = [ln.rsplit("/", 1)[-1] for ln in self._log_lines()
                     if ln.startswith("agy plugin install ")]
        self.assertEqual(installed, ["zulu", "aardvark"], result.stdout)

    def test_missing_order_script_warns_instead_of_ordering_silently(self) -> None:
        """The fallback is catalog order — but it says so, rather than looking
        like a resolved order."""
        repo = self.root / "no-order-script"
        (repo / ".git").mkdir(parents=True)
        dist = repo / "dist"
        dist.mkdir()
        (dist / "default-set.json").write_text(
            json.dumps({"plugins": ["aardvark", "zulu"]}), encoding="utf-8")

        _write_stub(self.bin / "agy", self.log)
        result = self._run(repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("installing in catalog order", result.stderr)
        installed = [ln.rsplit("/", 1)[-1] for ln in self._log_lines()
                     if ln.startswith("agy plugin install ")]
        self.assertEqual(installed, ["aardvark", "zulu"])

    def test_claude_only_installs_nothing_via_agy(self) -> None:
        _write_stub(self.bin / "claude", self.log)
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = self._log_lines()
        self.assertTrue(any(ln.startswith("claude plugin install ") for ln in lines))
        self.assertFalse(any(ln.startswith("agy ") for ln in lines))


if __name__ == "__main__":
    unittest.main()
