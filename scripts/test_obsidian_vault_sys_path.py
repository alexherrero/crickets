#!/usr/bin/env python3
"""Running the obsidian-vault suites leaves agentm's `scripts/` off `sys.path`.

The plugin suites in this directory put the sibling agentm kernel's `scripts/` on
`sys.path` so the plugin's present-engine imports resolve. The unit suite is one
process, so an entry left behind outlives the class that added it, and every
later bare import of a name agentm's `scripts/` also carries resolves to
*agentm's* module rather than crickets'. That is not hypothetical: the same leak
at import time in `test_obsidian_vault_conformance.py` made crickets'
`test_recent_wiki_changes` resolve to agentm's copy, and a full local run stopped
at discovery with "module incorrectly imported" before a single test ran (#254).

`test_obsidian_vault_conformance.py` pins its own *import*-time hygiene
(`ImportLeavesTheKernelOffSysPath`). This pins the *run*-time half, for the four
suites that set the path up in `setUpClass` and take it back in a class cleanup:
run them in a fresh interpreter, then assert the kernel dir is off `sys.path`
once they are done. The run happens in a subprocess, so no other test module's
`sys.path` changes count — and each suite's own counts are checked, because a
suite that skipped (or errored) would never reach the code this pins.

Needs the kernel clone, like the suites it runs: **graceful-skips** when none is
reachable (crickets CI in isolation), and runs for real in the dedicated
`obsidian-vault-conformance` job and on any box with `../agentm` checked out.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent

#: The suites that put agentm's `scripts/` on `sys.path` from `setUpClass`.
VAULT_SUITES = (
    "test_obsidian_vault_backend",
    "test_obsidian_vault_conflicts",
    "test_obsidian_vault_discovery",
    "test_obsidian_vault_doctor",
)

#: Both key modules: the four suites between them import from either.
KERNEL_MARKERS = ("storage_seam.py", "harness_memory.py")


def _locate_agentm_scripts() -> Path | None:
    """Find the agentm kernel `scripts/` dir, or None when no clone is reachable.

    Order: an explicit `AGENTM_SCRIPTS` override, then the conventional sibling
    checkout (`../agentm/scripts`) — the same locate-or-skip strategy as the
    suites this module runs.
    """
    override = os.environ.get("AGENTM_SCRIPTS")
    candidate = (
        Path(override).expanduser() if override else REPO_ROOT.parent / "agentm" / "scripts"
    )
    return candidate if all((candidate / m).is_file() for m in KERNEL_MARKERS) else None


_AGENTM_SCRIPTS = _locate_agentm_scripts()
_SKIP_REASON = (
    "agentm kernel clone not found (set AGENTM_SCRIPTS or check out ../agentm) — "
    "the four suites this runs would themselves skip, making the pin vacuous"
)


@unittest.skipUnless(_AGENTM_SCRIPTS is not None, _SKIP_REASON)
class RunningTheVaultSuitesLeavesTheKernelOffSysPath(unittest.TestCase):
    """Each suite takes its kernel `sys.path` entry back when its class is done."""

    def test_the_kernel_scripts_dir_is_off_sys_path_when_the_suites_finish(self) -> None:
        probe = "\n".join([
            "import json, os, sys, unittest",
            "from pathlib import Path",
            "sys.path.insert(0, sys.argv[1])",
            "target = Path(sys.argv[2]).resolve()",
            "counts = {}",
            "with open(os.devnull, 'w') as devnull:",
            "    for name in sys.argv[3:]:",
            "        suite = unittest.TestLoader().loadTestsFromName(name)",
            "        r = unittest.TextTestRunner(stream=devnull, verbosity=0).run(suite)",
            # Checked after EACH suite, not once at the end: a later suite that
            # tidies sys.path would otherwise cover for an earlier one's leak.
            # Resolved comparison, not a string one — a suite may insert the dir
            # under any spelling it was handed (a symlinked or relative
            # AGENTM_SCRIPTS, say), and every spelling of it is a leak.
            "        counts[name] = {",
            "            'ran': r.testsRun,",
            "            'skipped': len(r.skipped),",
            "            'bad': len(r.failures) + len(r.errors),",
            "            'left': [p for p in sys.path if p and Path(p).resolve() == target],",
            "        }",
            "print(json.dumps({'counts': counts}))",
        ])
        result = subprocess.run(
            [sys.executable, "-c", probe, str(SCRIPTS), str(_AGENTM_SCRIPTS), *VAULT_SUITES],
            capture_output=True, text=True, timeout=300, cwd=str(SCRIPTS),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout.strip().splitlines()[-1])

        for name in VAULT_SUITES:
            with self.subTest(suite=name):
                counts = report["counts"][name]
                # Non-vacuity: a suite that skipped or errored out never reached
                # the setUpClass whose cleanup this pins. (Platform skips are
                # fine — `ran - skipped` only has to be positive.)
                self.assertEqual(counts["bad"], 0, f"{name} did not run green: {report}")
                self.assertGreater(
                    counts["ran"] - counts["skipped"], 0, f"{name} ran nothing: {report}"
                )
                self.assertEqual(
                    counts["left"],
                    [],
                    f"{_AGENTM_SCRIPTS} is still on sys.path once {name} has run — left "
                    "there, it shadows every later test module whose bare name agentm's "
                    "scripts/ also carries, and a full run stops at discovery before any "
                    "test runs (#254). Set the path up in setUpClass through "
                    "agentm_isolation.isolate_agentm_imports, or in a try/finally around "
                    f"the one test that needs it. Probe: {report}",
                )


if __name__ == "__main__":
    unittest.main()
