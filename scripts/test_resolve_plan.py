#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/resolve_plan.py (multi-plan writers T2).

The bridge has two backends with one contract: **delegate** to agentm's
`resolve-active-plan` verb when a clone is installed, else a standalone
`.harness/` **fallback**. Every test is hermetic — the delegate branch is
exercised with a planted *stub* resolver and the locator with an injected `home`,
so nothing here depends on a real agentm clone (CI runs with none).
"""
from __future__ import annotations

import importlib.util
import io
import json
import contextlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "developer-workflows" / "scripts" / "resolve_plan.py"


def _load():
    spec = importlib.util.spec_from_file_location("resolve_plan", _SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["resolve_plan"] = m
    spec.loader.exec_module(m)
    return m


rp = _load()


def _write_stub(path: Path, body: str) -> Path:
    """A throwaway resolver script that stands in for agentm's verb."""
    path.write_text(body, encoding="utf-8")
    return path


class TestNameMapping(unittest.TestCase):
    """The filename contract the fallback shares with the agentm verb."""

    def test_normalize_singleton_forms(self):
        for form in ("", "   ", "PLAN", "PLAN.md"):
            self.assertEqual(rp._normalize_plan_name(form), "")

    def test_normalize_named_forms(self):
        for form in ("foo", "PLAN-foo", "PLAN-foo.md"):
            self.assertEqual(rp._normalize_plan_name(form), "foo")

    def test_plan_pair(self):
        self.assertEqual(rp._plan_pair(""), ("PLAN.md", "progress.md"))
        self.assertEqual(rp._plan_pair("foo"), ("PLAN-foo.md", "progress-foo.md"))

    def test_safe_slug(self):
        for ok in ("foo", "foo-bar", "foo.bar", "v2"):
            self.assertTrue(rp._is_safe_plan_slug(ok), ok)
        for bad in ("", ".", "..", "../etc", "a/b", "a\\b"):
            self.assertFalse(rp._is_safe_plan_slug(bad), bad)


class TestFallback(unittest.TestCase):
    """No agentm clone (`resolver=None`) → plain `.harness/` resolution."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-fallback-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _pair(self, *names: str) -> str:
        base = self.tmp / ".harness"
        return "\t".join(str(base / n) for n in names)

    def test_a_bare_is_byte_identical_singleton(self):
        # The load-bearing invariant: bare resolves to the unchanged singleton pair.
        rc, out, err = rp.resolve("", str(self.tmp), resolver=None)
        self.assertEqual(rc, 0)
        self.assertEqual(err, "")
        self.assertEqual(out.strip(), self._pair("PLAN.md", "progress.md"))

    def test_b_named_pair(self):
        rc, out, _ = rp.resolve("foo", str(self.tmp), resolver=None)
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), self._pair("PLAN-foo.md", "progress-foo.md"))

    def test_b_named_accepts_filename_form(self):
        rc, out, _ = rp.resolve("PLAN-foo.md", str(self.tmp), resolver=None)
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), self._pair("PLAN-foo.md", "progress-foo.md"))

    def test_c_unsafe_slug_rejected_no_path(self):
        rc, out, err = rp.resolve("../etc", str(self.tmp), resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertNotIn(".harness", out)
        self.assertIn("unsafe plan name", err)


class TestDelegation(unittest.TestCase):
    """A located resolver is authoritative — its line and exit code pass through."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-delegate-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_d_returns_stub_pair_unchanged(self):
        stub = _write_stub(
            self.tmp / "stub_ok.py",
            "import sys\nsys.stdout.write('/v/PLAN-foo.md\\t/v/progress-foo.md\\n')\n"
            "sys.exit(0)\n",
        )
        rc, out, err = rp.resolve("foo", str(self.tmp), resolver=stub)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "/v/PLAN-foo.md\t/v/progress-foo.md\n")
        self.assertEqual(err, "")

    def test_d_passes_plan_and_root_through(self):
        # Prove the bridge forwards --plan and --project-root to the resolver.
        stub = _write_stub(
            self.tmp / "stub_echo.py",
            "import sys\nsys.stdout.write('\\t'.join(sys.argv[1:]))\nsys.exit(0)\n",
        )
        rc, out, _ = rp.resolve("bar", "/proj/root", resolver=stub)
        self.assertEqual(rc, 0)
        self.assertIn("resolve-active-plan", out)
        self.assertIn("--plan", out)
        self.assertIn("bar", out)
        self.assertIn("--project-root", out)
        self.assertIn("/proj/root", out)

    def test_d_bare_omits_plan_flag(self):
        stub = _write_stub(
            self.tmp / "stub_echo2.py",
            "import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\nsys.exit(0)\n",
        )
        rc, out, _ = rp.resolve("", str(self.tmp), resolver=stub)
        self.assertEqual(rc, 0)
        self.assertNotIn("--plan", out)

    def test_e_dangling_exit_propagates_no_singleton_fallback(self):
        # Risk #7 across the second hop: a resolver that ran and refused must NOT
        # degrade to the singleton — its non-zero exit + stderr surface verbatim.
        stub = _write_stub(
            self.tmp / "stub_dangling.py",
            "import sys\n"
            "sys.stderr.write('[harness_memory] dangling .harness/active-plan marker\\n')\n"
            "sys.exit(2)\n",
        )
        rc, out, err = rp.resolve("", str(self.tmp), resolver=stub)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertNotIn("PLAN.md", out)      # never the singleton
        self.assertIn("active-plan", err)

    def test_e_graceful_skip_exit_one_propagates(self):
        # rc 1 (agentm present, no resolvable _harness/) also passes through — the
        # fallback is for *no clone*, never for a clone that returned a signal.
        stub = _write_stub(
            self.tmp / "stub_skip.py",
            "import sys\nsys.exit(1)\n",
        )
        rc, out, _ = rp.resolve("", str(self.tmp), resolver=stub)
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")


class TestLocateResolver(unittest.TestCase):
    """The agentm-clone lookup mirrors the session-start hook (config → fallback)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-locate-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_clone(self, root: Path) -> Path:
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        hm = root / "scripts" / "harness_memory.py"
        hm.write_text("# stub\n", encoding="utf-8")
        return hm

    def test_none_when_no_config_and_no_conventional_clone(self):
        # Injected empty home → neither the config nor ~/Antigravity/agentm exists.
        self.assertIsNone(
            rp.locate_resolver(config_path=self.tmp / "absent.json", home=self.tmp)
        )

    def test_found_via_config_source_clone(self):
        clone = self.tmp / "clones" / "agentm"
        hm = self._make_clone(clone)
        cfg = self.tmp / "cfg.json"
        cfg.write_text(
            json.dumps({"source_clones": {"agentm": str(clone)}}), encoding="utf-8"
        )
        self.assertEqual(rp.locate_resolver(config_path=cfg, home=self.tmp), hm)

    def test_found_via_conventional_fallback(self):
        # No config, but ~/Antigravity/agentm/scripts/harness_memory.py exists.
        hm = self._make_clone(self.tmp / "Antigravity" / "agentm")
        self.assertEqual(
            rp.locate_resolver(config_path=self.tmp / "absent.json", home=self.tmp), hm
        )

    def test_config_clone_missing_file_falls_through_to_none(self):
        # source_clones names a dir with no harness_memory.py, no conventional clone.
        cfg = self.tmp / "cfg.json"
        cfg.write_text('{"source_clones": {"agentm": "/nope/nowhere"}}', encoding="utf-8")
        self.assertIsNone(rp.locate_resolver(config_path=cfg, home=self.tmp))

    def test_malformed_config_is_graceful(self):
        cfg = self.tmp / "cfg.json"
        cfg.write_text("{not json", encoding="utf-8")
        self.assertIsNone(rp.locate_resolver(config_path=cfg, home=self.tmp))


class TestMainCLI(unittest.TestCase):
    """End-to-end main() over the fallback backend (delegate is unit-tested above)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rp-main-"))
        # Force the fallback deterministically regardless of the real machine's
        # agentm install by pointing the auto-locator at an empty home.
        self._saved = rp.locate_resolver
        rp.locate_resolver = lambda **_k: None

    def tearDown(self):
        rp.locate_resolver = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = rp.main(["resolve_plan.py", *argv])
        return rc, out.getvalue(), err.getvalue()

    def test_main_bare_singleton(self):
        rc, out, _ = self._run("--project-root", str(self.tmp))
        self.assertEqual(rc, 0)
        base = self.tmp / ".harness"
        self.assertEqual(out.strip(), f"{base / 'PLAN.md'}\t{base / 'progress.md'}")

    def test_main_named(self):
        rc, out, _ = self._run("foo", "--project-root", str(self.tmp))
        self.assertEqual(rc, 0)
        base = self.tmp / ".harness"
        self.assertEqual(out.strip(), f"{base / 'PLAN-foo.md'}\t{base / 'progress-foo.md'}")

    def test_main_unsafe_nonzero(self):
        rc, out, err = self._run("../etc", "--project-root", str(self.tmp))
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("unsafe plan name", err)


# ── Plan-name contract — golden vectors shared with the agentm twin ─────────────
# These two tables are duplicated VERBATIM in the agentm authority's test suite
# (agentm/scripts/test_resolve_active_plan.py, class PlanNameContractParity) so
# this standalone fallback normalizer can't drift from what agentm means. That's
# the disposition of the 2026-06-13 adversarial audit (finding ML2): no cross-repo
# import edge (DC-2), just one table asserted on both sides. Change a row here →
# change it there. `PLAN-PLAN.md` (singleton on both) and `foo\x00` (unsafe on
# both) are the two rows that encode the drifts the audit caught and this fix
# closed.
_PLAN_NAME_VECTORS = [
    ("", ("PLAN.md", "progress.md")),
    ("   ", ("PLAN.md", "progress.md")),
    ("PLAN", ("PLAN.md", "progress.md")),
    ("PLAN.md", ("PLAN.md", "progress.md")),
    ("PLAN-PLAN", ("PLAN.md", "progress.md")),
    ("PLAN-PLAN.md", ("PLAN.md", "progress.md")),
    ("foo", ("PLAN-foo.md", "progress-foo.md")),
    ("PLAN-foo", ("PLAN-foo.md", "progress-foo.md")),
    ("PLAN-foo.md", ("PLAN-foo.md", "progress-foo.md")),
    ("  PLAN-foo.md  ", ("PLAN-foo.md", "progress-foo.md")),
    ("my-plan", ("PLAN-my-plan.md", "progress-my-plan.md")),
]

_PLAN_SLUG_SAFETY = [
    ("foo", True), ("foo-bar", True), ("foo.bar", True), ("v2", True),
    (".", False), ("..", False), ("a/b", False), ("a\\b", False), ("foo\x00", False),
]


class PlanNameContractParity(unittest.TestCase):
    """The (name → pair) + slug-safety contract this fallback must match in agentm.

    agentm is the authority (this bridge delegates to it when a clone is present);
    these vectors pin the meaning so the standalone fallback can't drift from it.
    """

    def test_name_to_pair_golden_vectors(self):
        for name, expected in _PLAN_NAME_VECTORS:
            slug = rp._normalize_plan_name(name)
            self.assertEqual(rp._plan_pair(slug), expected, f"name={name!r}")

    def test_slug_safety_golden_vectors(self):
        for slug, expected in _PLAN_SLUG_SAFETY:
            self.assertEqual(rp._is_safe_plan_slug(slug), expected, f"slug={slug!r}")


if __name__ == "__main__":
    unittest.main()
