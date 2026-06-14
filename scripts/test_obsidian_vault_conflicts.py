#!/usr/bin/env python3
"""Function-level tests for the re-homed `obsidian-vault` conflict sweep (V5-2 task 2).

The vault-specific conflict-merger machinery — `_infer_conflict_base_path`,
`default_lost_and_found_root`, `detect_conflict_files` — moved byte-faithful out
of the agentm kernel's `harness_memory.py` into this plugin's
`scripts/vault_conflicts.py` (LC-1). Its proof travels with it: this file is the
port of the kernel's `TestDetectConflictFiles` (+ the named-plan janitor cases),
re-pointed at the plugin module.

`vault_conflicts.py` imports the pure filename classifier `_conflict_family` from
the present engine (LC-3 — it stays kernel-side, shared with
`queue_status_lite.py`). So this test locates the sibling agentm clone, puts its
`scripts/` on `sys.path` so that import resolves, and **graceful-skips** when no
clone is reachable (e.g. crickets CI in isolation) to keep the gate deterministic.
The classifier itself stays tested kernel-side; here we exercise the three moved
functions end to end.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
import unittest.mock as _mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_CONFLICTS = REPO_ROOT / "src" / "obsidian-vault" / "scripts" / "vault_conflicts.py"


def _locate_agentm_scripts() -> Path | None:
    """Find the agentm kernel `scripts/` dir, or None when no clone is reachable.

    Order: an explicit `AGENTM_SCRIPTS` override, then the conventional sibling
    checkout (`../agentm/scripts`). The module under test imports `_conflict_family`
    from `harness_memory` here.
    """
    override = os.environ.get("AGENTM_SCRIPTS")
    if override:
        p = Path(override).expanduser()
        return p if (p / "harness_memory.py").is_file() else None
    sibling = REPO_ROOT.parent / "agentm" / "scripts"
    return sibling if (sibling / "harness_memory.py").is_file() else None


def _load_plugin_conflicts(agentm_scripts: Path):
    """Import the plugin's vault_conflicts.py by path, under a present engine.

    Puts the agentm `scripts/` on `sys.path` (so the module's
    `from harness_memory import _conflict_family` resolves), then loads the file
    under a unique module name (avoiding any clash with the kernel module).
    """
    if str(agentm_scripts) not in sys.path:
        sys.path.insert(0, str(agentm_scripts))
    spec = importlib.util.spec_from_file_location(
        "obsidian_vault_vault_conflicts", PLUGIN_CONFLICTS
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(PLUGIN_CONFLICTS.is_file(), f"{PLUGIN_CONFLICTS} not present")
class TestDetectConflictFiles(unittest.TestCase):
    """The re-homed sweep detects conflict/duplicate files + infers base paths."""

    @classmethod
    def setUpClass(cls) -> None:
        agentm_scripts = _locate_agentm_scripts()
        if agentm_scripts is None:
            raise unittest.SkipTest(
                "agentm kernel clone not found (set AGENTM_SCRIPTS or check out "
                "../agentm) — vault_conflicts import skipped to keep CI deterministic"
            )
        cls.vc = _load_plugin_conflicts(agentm_scripts)

    # ── base set (was kernel TestDetectConflictFiles) ──────────────────────
    def test_returns_empty_when_no_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "PLAN.md").write_text("clean")
            self.assertEqual(self.vc.detect_conflict_files(Path(tmp)), [])

    def test_returns_empty_for_nonexistent_vault(self) -> None:
        self.assertEqual(self.vc.detect_conflict_files(Path("/nonexistent/path")), [])

    def test_detects_basic_conflict_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "PLAN.md").write_text("base")
            conflict = Path(tmp) / "PLAN (conflicted copy 2026-05-27).md"
            conflict.write_text("conflict")
            result = self.vc.detect_conflict_files(Path(tmp))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["conflict"], conflict)
        self.assertEqual(result[0]["base"], Path(tmp) / "PLAN.md")

    def test_detects_with_device_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conflict = Path(tmp) / "PLAN (conflicted copy 2026-05-27) - Mac.md"
            conflict.write_text("x")
            result = self.vc.detect_conflict_files(Path(tmp))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["base"], Path(tmp) / "PLAN.md")

    def test_detects_nested_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "projects" / "agentm" / "_harness").mkdir(parents=True)
            conflict = Path(tmp) / "projects" / "agentm" / "_harness" / "PLAN (conflicted copy 2026-05-27).md"
            conflict.write_text("nested")
            result = self.vc.detect_conflict_files(Path(tmp))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["conflict"], conflict)
        self.assertEqual(
            result[0]["rel"],
            Path("projects/agentm/_harness/PLAN (conflicted copy 2026-05-27).md"),
        )

    def test_detects_multiple_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "PLAN (conflicted copy 2026-05-27).md").write_text("a")
            (Path(tmp) / "FOLLOWUPS (conflicted copy 2026-05-27).md").write_text("b")
            result = self.vc.detect_conflict_files(Path(tmp))
        self.assertEqual(len(result), 2)

    def test_case_insensitive_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "PLAN (Conflicted Copy 2026-05-27).md").write_text("x")
            result = self.vc.detect_conflict_files(Path(tmp))
        self.assertEqual(len(result), 1)

    def test_ignores_files_without_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "PLAN.md").write_text("clean")
            (Path(tmp) / "progress.md").write_text("clean")
            (Path(tmp) / "ROADMAP-V4.md").write_text("clean")
            self.assertEqual(self.vc.detect_conflict_files(Path(tmp)), [])

    # ── broadened marker families (V5-0 task 4) ────────────────────────────
    def test_vault_entries_carry_source_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "PLAN (conflicted copy 2026-05-27).md").write_text("x")
            result = self.vc.detect_conflict_files(Path(tmp))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source"], "vault")

    def test_detects_bracket_conflict_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conflict = Path(tmp) / "PLAN [Conflict].md"
            conflict.write_text("x")
            result = self.vc.detect_conflict_files(Path(tmp))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["conflict"], conflict)
        self.assertEqual(result[0]["base"], Path(tmp) / "PLAN.md")

    def test_detects_bracket_conflict_marker_numbered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "PLAN [Conflict 2].md").write_text("x")
            result = self.vc.detect_conflict_files(Path(tmp))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["base"], Path(tmp) / "PLAN.md")

    def test_detects_copy_of_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conflict = Path(tmp) / "Copy of PLAN.md"
            conflict.write_text("x")
            result = self.vc.detect_conflict_files(Path(tmp))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["conflict"], conflict)
        self.assertEqual(result[0]["base"], Path(tmp) / "PLAN.md")

    def test_detects_numbered_duplicate_when_base_coexists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "PLAN.md").write_text("base")  # the de-numbered base
            conflict = Path(tmp) / "PLAN (1).md"
            conflict.write_text("dup")
            result = self.vc.detect_conflict_files(Path(tmp))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["conflict"], conflict)
        self.assertEqual(result[0]["base"], Path(tmp) / "PLAN.md")

    def test_numbered_duplicate_ignored_without_base(self) -> None:
        """Year-like false-positive guard: "report (2026).md" with no de-numbered
        "report.md" alongside is NOT a Drive duplicate."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "report (2026).md").write_text("a standalone file")
            self.assertEqual(self.vc.detect_conflict_files(Path(tmp)), [])

    def test_copy_of_takes_precedence_and_composes_with_number(self) -> None:
        """"Copy of PLAN (1).md" is flagged via the copy-of family (no co-exist
        guard) and base-inference strips BOTH markers down to "PLAN.md"."""
        with tempfile.TemporaryDirectory() as tmp:
            conflict = Path(tmp) / "Copy of PLAN (1).md"
            conflict.write_text("x")
            result = self.vc.detect_conflict_files(Path(tmp))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["base"], Path(tmp) / "PLAN.md")

    def test_case_insensitive_new_families(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "PLAN [CONFLICT].md").write_text("x")
            (Path(tmp) / "COPY OF NOTES.md").write_text("y")
            result = self.vc.detect_conflict_files(Path(tmp))
        self.assertEqual(len(result), 2)

    # ── named-plan janitor (was test_harness_memory_named_plans) ───────────
    def test_infer_base_strips_marker_to_named_plan(self) -> None:
        base = self.vc._infer_conflict_base_path(
            Path("/v/_harness/PLAN-foo (conflicted copy 2026-06-12) - Mac.md")
        )
        self.assertEqual(base.name, "PLAN-foo.md")

    def test_detect_conflict_files_finds_named_plan_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            harness = Path(tmp) / "_harness"
            harness.mkdir(parents=True)
            (harness / "PLAN-foo.md").write_text("base\n", encoding="utf-8")
            conflict = harness / "PLAN-foo (conflicted copy 2026-06-12).md"
            conflict.write_text("dupe\n", encoding="utf-8")
            found = self.vc.detect_conflict_files(Path(tmp))
        names = {f["conflict"].name for f in found}
        self.assertIn(conflict.name, names)
        match = next(f for f in found if f["conflict"].name == conflict.name)
        self.assertEqual(match["base"].name, "PLAN-foo.md")

    # ── DriveFS lost_and_found/ scan (opt-in, injectable) ──────────────────
    def test_lost_and_found_not_scanned_by_default(self) -> None:
        """Opt-in: with no lost_and_found_root passed, only the vault is swept —
        this is what keeps every other test hermetic against the real ~/Library."""
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            laf = Path(tmp) / "lost_and_found"
            vault.mkdir()
            laf.mkdir()
            (laf / "orphan.md").write_text("orphaned by DriveFS")
            self.assertEqual(self.vc.detect_conflict_files(vault), [])

    def test_lost_and_found_scanned_when_root_injected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            laf = Path(tmp) / "lost_and_found"
            vault.mkdir()
            laf.mkdir()
            orphan = laf / "orphan.md"
            orphan.write_text("orphaned by DriveFS")
            result = self.vc.detect_conflict_files(vault, lost_and_found_root=laf)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source"], "lost_and_found")
        self.assertEqual(result[0]["conflict"], orphan)
        self.assertEqual(result[0]["rel"], Path("orphan.md"))

    def test_lost_and_found_every_file_surfaced_no_marker_needed(self) -> None:
        """Unlike the vault sweep, the L&F dump surfaces ALL files (DriveFS only
        dumps orphans there) — even a clean, marker-less name."""
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            laf = Path(tmp) / "lost_and_found"
            vault.mkdir()
            laf.mkdir()
            (laf / "PLAN.md").write_text("a clean name, but orphaned")
            result = self.vc.detect_conflict_files(vault, lost_and_found_root=laf)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source"], "lost_and_found")

    def test_lost_and_found_root_absent_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            vault.mkdir()
            missing = Path(tmp) / "does-not-exist"
            self.assertEqual(
                self.vc.detect_conflict_files(vault, lost_and_found_root=missing), [],
            )

    @unittest.skipIf(os.name == "nt", "POSIX $HOME redirection")
    def test_default_lost_and_found_root_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            laf = home / "Library" / "Application Support" / "Google" / "DriveFS" / "lost_and_found"
            with _mock.patch.dict(os.environ, {"HOME": str(home)}):
                self.assertIsNone(self.vc.default_lost_and_found_root())  # absent → None
                laf.mkdir(parents=True)
                self.assertEqual(self.vc.default_lost_and_found_root(), laf)  # present → path

    @unittest.skipIf(os.name == "nt", "POSIX env redirection for the test setup")
    def test_default_lost_and_found_root_windows_candidate(self) -> None:
        """The Windows DriveFS lost_and_found under %LOCALAPPDATA% resolves too,
        so the operator's Windows machine no longer silently gets no sweep (ML1)."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            local_appdata = Path(tmp) / "AppData" / "Local"
            laf = local_appdata / "Google" / "DriveFS" / "lost_and_found"
            with _mock.patch.dict(
                os.environ, {"HOME": str(home), "LOCALAPPDATA": str(local_appdata)},
            ):
                self.assertIsNone(self.vc.default_lost_and_found_root())  # absent → None
                laf.mkdir(parents=True)
                self.assertEqual(self.vc.default_lost_and_found_root(), laf)  # present → path


if __name__ == "__main__":
    unittest.main()
