#!/usr/bin/env python3
"""Conformance: the integration flow never bypasses branch protection (LC-3).

The first concurrent auto-spawn run's worker landed via an `--admin` override on
`gh pr merge`, bypassing the branch protection it had just authored — the
anti-pattern part 3 (ADR 0030) removes. There is no legitimate use of the admin
bypass flag anywhere in the developer-workflows command surface or its scripts:
integration is a *local* merge+gate+rollback (`integrate_worker.py`, never pushes),
and the operator lands the integrated branch through the protected path (squash,
wait for required CI green, then merge). This test makes "no admin bypass" a
standing repo invariant so it can never silently reappear.

Scoped to the integration flow (`src/developer-workflows/{commands,scripts}`) on
purpose — and deliberately NOT to this `scripts/` dir, so the test does not match
its own description of the forbidden flag.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCAN_DIRS = (
    _ROOT / "src" / "development-lifecycle" / "commands",
    _ROOT / "src" / "development-lifecycle" / "scripts",
)
_SCAN_SUFFIXES = (".md", ".py", ".sh")
# The admin bypass as a CLI flag token (`gh pr merge --admin`), not the substring
# "administrator". A leading word/dash boundary keeps `--foo-admin` from matching.
_ADMIN_FLAG = re.compile(r"(?<![\w-])--admin(?![\w-])")


def _scanned_files() -> list[Path]:
    return [p for d in _SCAN_DIRS if d.is_dir()
            for p in sorted(d.rglob("*"))
            if p.is_file() and p.suffix in _SCAN_SUFFIXES]


class TestNoAdminBypass(unittest.TestCase):
    def test_no_admin_bypass_in_integration_flow(self):
        offenders = []
        for p in _scanned_files():
            text = p.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if _ADMIN_FLAG.search(line):
                    offenders.append(f"{p.relative_to(_ROOT)}:{i}: {line.strip()}")
        self.assertEqual(
            offenders, [],
            "branch-protection bypass flag found in the developer-workflows "
            "integration flow — LC-3 forbids it; land through the protected path "
            "(see ADR 0030 + the Integrate-A-Worker how-to):\n" + "\n".join(offenders))

    def test_scan_actually_covers_files(self):
        # A conformance scan that silently matches nothing is a false green. Pin
        # that it inspects the real integration flow.
        scanned = _scanned_files()
        self.assertGreater(
            len(scanned), 0,
            f"no command/script files found under {[str(d) for d in _SCAN_DIRS]} — "
            "the conformance scan would vacuously pass; check the src/ layout")


if __name__ == "__main__":
    unittest.main()
