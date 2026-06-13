#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/queue_status.py (queue-status-lite bridge).

The bridge has two backends with one contract: **delegate** to agentm's shipped
`queue_status_lite.py` reader when a clone is installed, else a standalone
`.harness/` **fallback** that mirrors the reader's render. Every test is hermetic
— the delegate branch is exercised with a planted *stub* reader and the locator
with an injected `home`, so nothing here depends on a real agentm clone (CI runs
with none).
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "developer-workflows" / "scripts" / "queue_status.py"


def _load():
    spec = importlib.util.spec_from_file_location("queue_status", _SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["queue_status"] = m
    spec.loader.exec_module(m)
    return m


qs = _load()


def _write_stub(path: Path, body: str) -> Path:
    """A throwaway reader script that stands in for agentm's queue_status_lite."""
    path.write_text(body, encoding="utf-8")
    return path


class TestFallback(unittest.TestCase):
    """No agentm clone (`reader=None`) → minimal local `.harness/` dashboard."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="qs-fallback-"))
        self.hd = self.tmp / ".harness"
        self.hd.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _plant_fixture(self):
        (self.hd / "PLAN.md").write_text(
            "# Plan: singleton\n\n**Status:** in-progress\n", encoding="utf-8"
        )
        (self.hd / "progress.md").write_text(
            "2026-06-01 10:00 /plan — created\n"
            "2026-06-02 11:00 /work — completed task 1\n",
            encoding="utf-8",
        )
        (self.hd / "PLAN-foo.md").write_text(
            "# Plan: foo\n\nStatus: planning\n", encoding="utf-8"
        )
        (self.hd / "progress-foo.md").write_text(
            "2026-06-03 09:00 /plan — created plan foo\n", encoding="utf-8"
        )
        # Neither of these is an *active* plan — both must be skipped.
        (self.hd / "PLAN.archive.20260101-old.md").write_text(
            "**Status:** done\n", encoding="utf-8"
        )
        (self.hd / "PLAN-bar (conflicted copy 2026-01-01).md").write_text(
            "**Status:** planning\n", encoding="utf-8"
        )

    def test_a_lists_singleton_and_named_with_status_and_progress(self):
        self._plant_fixture()
        rc, out, err = qs.run(str(self.hd), reader=None)
        self.assertEqual(rc, 0)
        self.assertEqual(err, "")
        self.assertIn("PLAN.md", out)
        self.assertIn("PLAN-foo.md", out)
        self.assertIn("[in-progress]", out)   # bold **Status:** tolerated
        self.assertIn("[planning]", out)       # plain Status: too
        self.assertIn("2026-06-02 11:00 /work — completed task 1", out)  # last line
        self.assertIn("2026-06-03 09:00 /plan — created plan foo", out)

    def test_b_singleton_sorts_first(self):
        self._plant_fixture()
        _, out, _ = qs.run(str(self.hd), reader=None)
        # "PLAN.md" is not a substring of "PLAN-foo.md", so these indices are exact.
        self.assertLess(out.index("PLAN.md"), out.index("PLAN-foo.md"))

    def test_c_archives_and_conflict_copies_excluded(self):
        self._plant_fixture()
        _, out, _ = qs.run(str(self.hd), reader=None)
        self.assertNotIn("archive", out)
        self.assertNotIn("conflicted copy", out)

    def test_d_missing_progress_file_placeholder(self):
        (self.hd / "PLAN-lonely.md").write_text("**Status:** planning\n", encoding="utf-8")
        _, out, _ = qs.run(str(self.hd), reader=None)
        self.assertIn("PLAN-lonely.md", out)
        self.assertIn("(no progress file)", out)

    def test_e_status_missing_renders_dash(self):
        (self.hd / "PLAN.md").write_text("# Plan with no status line\n", encoding="utf-8")
        _, out, _ = qs.run(str(self.hd), reader=None)
        self.assertIn("[—]", out)

    def test_f_empty_dir_no_plans(self):
        rc, out, _ = qs.run(str(self.hd), reader=None)
        self.assertEqual(rc, 0)
        self.assertIn("No plans found", out)

    def test_g_missing_dir_is_graceful(self):
        rc, out, err = qs.run(str(self.tmp / "nope"), reader=None)
        self.assertEqual(rc, 0)
        self.assertEqual(err, "")
        self.assertIn("No _harness/ directory to read", out)


class TestDelegation(unittest.TestCase):
    """A located reader is authoritative — its stdout and exit code pass through."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="qs-delegate-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_passthrough_verbatim(self):
        stub = _write_stub(
            self.tmp / "stub_ok.py",
            "import sys\nsys.stdout.write('Active plans in /v/_harness:\\n')\n"
            "sys.exit(0)\n",
        )
        rc, out, err = qs.run("/v/_harness", reader=stub)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "Active plans in /v/_harness:\n")
        self.assertEqual(err, "")

    def test_b_forwards_harness_dir(self):
        stub = _write_stub(
            self.tmp / "stub_echo.py",
            "import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\nsys.exit(0)\n",
        )
        rc, out, _ = qs.run("/some/_harness", reader=stub)
        self.assertEqual(rc, 0)
        self.assertIn("--harness-dir", out)
        self.assertIn("/some/_harness", out)

    def test_c_none_harness_dir_omits_flag(self):
        stub = _write_stub(
            self.tmp / "stub_echo2.py",
            "import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\nsys.exit(0)\n",
        )
        rc, out, _ = qs.run(None, reader=stub)
        self.assertEqual(rc, 0)
        self.assertNotIn("--harness-dir", out)

    def test_d_nonzero_exit_propagates(self):
        # The reader exits 0 in normal use; if a located reader ever returns
        # non-zero + stderr, the bridge must surface it, never swallow it.
        stub = _write_stub(
            self.tmp / "stub_fail.py",
            "import sys\nsys.stderr.write('boom\\n')\nsys.exit(3)\n",
        )
        rc, out, err = qs.run("/x", reader=stub)
        self.assertEqual(rc, 3)
        self.assertEqual(out, "")
        self.assertIn("boom", err)


class TestLocateReader(unittest.TestCase):
    """The reader lookup rides on resolve_plan.locate_resolver (config → fallback)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="qs-locate-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_clone(self, root: Path, *, with_reader: bool = True) -> Path:
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "scripts" / "harness_memory.py").write_text("# stub\n", encoding="utf-8")
        reader = root / "scripts" / "queue_status_lite.py"
        if with_reader:
            reader.write_text("# stub reader\n", encoding="utf-8")
        return reader

    def test_none_when_no_config_and_no_conventional_clone(self):
        self.assertIsNone(
            qs.locate_reader(config_path=self.tmp / "absent.json", home=self.tmp)
        )

    def test_found_via_config_source_clone(self):
        clone = self.tmp / "clones" / "agentm"
        reader = self._make_clone(clone)
        cfg = self.tmp / "cfg.json"
        cfg.write_text(
            json.dumps({"source_clones": {"agentm": str(clone)}}), encoding="utf-8"
        )
        self.assertEqual(qs.locate_reader(config_path=cfg, home=self.tmp), reader)

    def test_found_via_conventional_fallback(self):
        reader = self._make_clone(self.tmp / "Antigravity" / "agentm")
        self.assertEqual(
            qs.locate_reader(config_path=self.tmp / "absent.json", home=self.tmp), reader
        )

    def test_clone_without_reader_is_none(self):
        # The decisive case: harness_memory.py is found (so the resolver locates),
        # but the sibling queue_status_lite.py is absent → no reader, not a crash.
        clone = self.tmp / "clones" / "agentm"
        self._make_clone(clone, with_reader=False)
        cfg = self.tmp / "cfg.json"
        cfg.write_text(
            json.dumps({"source_clones": {"agentm": str(clone)}}), encoding="utf-8"
        )
        self.assertIsNone(qs.locate_reader(config_path=cfg, home=self.tmp))

    def test_malformed_config_is_graceful(self):
        cfg = self.tmp / "cfg.json"
        cfg.write_text("{not json", encoding="utf-8")
        self.assertIsNone(qs.locate_reader(config_path=cfg, home=self.tmp))


class TestMainCLI(unittest.TestCase):
    """End-to-end main() over the fallback backend (delegate is unit-tested above)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="qs-main-"))
        self.hd = self.tmp / ".harness"
        self.hd.mkdir()
        # Force the fallback deterministically regardless of the real machine's
        # agentm install by pointing the auto-locator at no reader.
        self._saved = qs.locate_reader
        qs.locate_reader = lambda **_k: None

    def tearDown(self):
        qs.locate_reader = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = qs.main(["queue_status.py", *argv])
        return rc, out.getvalue(), err.getvalue()

    def test_main_lists_plans(self):
        (self.hd / "PLAN.md").write_text("**Status:** in-progress\n", encoding="utf-8")
        (self.hd / "progress.md").write_text("2026-06-02 /work — did a thing\n", encoding="utf-8")
        rc, out, _ = self._run("--harness-dir", str(self.hd))
        self.assertEqual(rc, 0)
        self.assertIn("PLAN.md", out)
        self.assertIn("[in-progress]", out)
        self.assertIn("did a thing", out)

    def test_main_missing_dir_graceful(self):
        rc, out, _ = self._run("--harness-dir", str(self.tmp / "nope"))
        self.assertEqual(rc, 0)
        self.assertIn("No _harness/ directory to read", out)


if __name__ == "__main__":
    unittest.main()
