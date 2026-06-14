#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/design_sequence.py (sibling #5).

The deterministic ordering core behind `/design sequence`: dependency-list
parsing (inline + block forms), part-frontmatter validation, the Kahn topo-sort
with its alphabetical tie-break, and cycle / missing-dependency refusals. Plus an
integration test that wires the helper's output through the *real* `stage_plan.py`
exactly as the command body prescribes — proving the crickets contract: first
part activated as a named plan, the rest queued, the singleton `PLAN.md`
untouched. Hermetic — parts + harness roots are synthesized in throwaway temp
dirs (never the real vault), `stage_plan` is driven with `resolver=None` (the
`.harness/` fallback), mirroring `test_stage_plan.py` / `test_design_doc.py`.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS = _ROOT / "src" / "developer-workflows" / "scripts"


def _load(name: str):
    src = _SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, src)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


ds = _load("design_sequence")
stage_plan = _load("stage_plan")


def _part(slug: str, deps: list[str], *, scope: str = "M") -> str:
    """A minimal valid part file with the given slug + inline dependency list."""
    inline = "[" + ", ".join(deps) + "]"
    return (
        f"---\ntitle: {slug.title()}\nstatus: draft\nvisibility: confidential\n"
        f"part_slug: {slug}\ndependencies: {inline}\nestimated_scope: {scope}\n---\n\n"
        f"# {slug}\n\n## Scope\n\nplaceholder scope for {slug}\n"
    )


class TestParseDependencies(unittest.TestCase):
    """`_dependencies_from_block`: inline, block, and empty forms."""

    def test_inline_list(self):
        self.assertEqual(
            ds._dependencies_from_block("part_slug: x\ndependencies: [a, b]\n"),
            ["a", "b"],
        )

    def test_empty_inline_list(self):
        self.assertEqual(ds._dependencies_from_block("dependencies: []\n"), [])

    def test_absent_is_empty(self):
        self.assertEqual(ds._dependencies_from_block("part_slug: x\n"), [])

    def test_block_form(self):
        # A hand-edited YAML block list must NOT silently drop its edges.
        fm = "part_slug: x\ndependencies:\n  - a\n  - b\nestimated_scope: S\n"
        self.assertEqual(ds._dependencies_from_block(fm), ["a", "b"])

    def test_block_form_stops_at_next_key(self):
        fm = "dependencies:\n  - a\nestimated_scope: S\n"
        self.assertEqual(ds._dependencies_from_block(fm), ["a"])

    def test_strips_quotes(self):
        self.assertEqual(ds._dependencies_from_block('dependencies: ["a", "b"]\n'),
                         ["a", "b"])


class TestReadPartsValidation(unittest.TestCase):
    """`read_parts` refuses on a bad dir or any invalid part frontmatter."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ds-read-"))
        self.parts = self.tmp / "parts"
        self.parts.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name: str, text: str):
        (self.parts / name).write_text(text, encoding="utf-8")

    def test_missing_dir_refused(self):
        parts, err = ds.read_parts(str(self.tmp / "nope"))
        self.assertIsNone(parts)
        self.assertIn("does not exist", err)
        self.assertIn("/design translate", err)

    def test_empty_dir_refused(self):
        parts, err = ds.read_parts(str(self.parts))
        self.assertIsNone(parts)
        self.assertIn("zero part files", err)

    def test_no_frontmatter_refused(self):
        self._write("a.md", "# just a heading\n")
        parts, err = ds.read_parts(str(self.parts))
        self.assertIsNone(parts)
        self.assertIn("no YAML frontmatter", err)

    def test_missing_part_slug_refused(self):
        self._write("a.md", "---\ntitle: A\ndependencies: []\nestimated_scope: S\n---\n")
        parts, err = ds.read_parts(str(self.parts))
        self.assertIsNone(parts)
        self.assertIn("part_slug", err)

    def test_missing_dependencies_key_refused(self):
        self._write("a.md", "---\npart_slug: a\nestimated_scope: S\n---\n")
        parts, err = ds.read_parts(str(self.parts))
        self.assertIsNone(parts)
        self.assertIn("dependencies", err)

    def test_bad_estimated_scope_refused(self):
        self._write("a.md", "---\npart_slug: a\ndependencies: []\nestimated_scope: XL\n---\n")
        parts, err = ds.read_parts(str(self.parts))
        self.assertIsNone(parts)
        self.assertIn("estimated_scope", err)

    def test_duplicate_slug_refused(self):
        self._write("a.md", _part("dup", []))
        self._write("b.md", _part("dup", []))
        parts, err = ds.read_parts(str(self.parts))
        self.assertIsNone(parts)
        self.assertIn("duplicate", err)

    def test_valid_parts_read(self):
        self._write("a.md", _part("foundations", []))
        self._write("b.md", _part("surface", ["foundations"]))
        parts, err = ds.read_parts(str(self.parts))
        self.assertEqual(err, "")
        self.assertEqual({p["slug"] for p in parts}, {"foundations", "surface"})


class TestTopoOrder(unittest.TestCase):
    """Kahn topo-sort: deterministic order, cycle + missing-dep refusals."""

    @staticmethod
    def _parts(spec: dict[str, list[str]]) -> list[dict]:
        return [{"slug": s, "deps": d, "scope": "M", "path": Path(f"{s}.md")}
                for s, d in spec.items()]

    def test_linear_chain(self):
        order, err = ds.topo_order(self._parts({"a": [], "b": ["a"], "c": ["b"]}))
        self.assertEqual(err, "")
        self.assertEqual(order, ["a", "b", "c"])

    def test_alphabetical_tie_break(self):
        # Three roots with no deps → strictly alphabetical.
        order, _ = ds.topo_order(self._parts({"charlie": [], "alpha": [], "bravo": []}))
        self.assertEqual(order, ["alpha", "bravo", "charlie"])

    def test_diamond_is_deterministic(self):
        # a → {b, c} → d. b and c tie at level 2 → alphabetical (b before c).
        spec = {"a": [], "b": ["a"], "c": ["a"], "d": ["b", "c"]}
        order, _ = ds.topo_order(self._parts(spec))
        self.assertEqual(order, ["a", "b", "c", "d"])

    def test_determinism_across_runs(self):
        spec = {"z": ["a"], "a": [], "m": ["a"], "b": ["m", "z"]}
        first, _ = ds.topo_order(self._parts(spec))
        second, _ = ds.topo_order(self._parts(spec))
        self.assertEqual(first, second)

    def test_input_order_does_not_change_output(self):
        # Same graph, parts listed in a different order → identical topo order.
        spec_a = {"a": [], "b": ["a"], "c": ["a"]}
        spec_b = {"c": ["a"], "b": ["a"], "a": []}
        order_a, _ = ds.topo_order(self._parts(spec_a))
        order_b, _ = ds.topo_order(self._parts(spec_b))
        self.assertEqual(order_a, order_b)

    def test_cycle_refused_with_path(self):
        order, err = ds.topo_order(self._parts({"a": ["b"], "b": ["a"]}))
        self.assertIsNone(order)
        self.assertIn("cycle", err.lower())
        self.assertIn("→", err)  # a concrete path, not just a flag

    def test_self_cycle_refused(self):
        order, err = ds.topo_order(self._parts({"a": ["a"]}))
        self.assertIsNone(order)
        self.assertIn("cycle", err.lower())

    def test_missing_dependency_refused(self):
        order, err = ds.topo_order(self._parts({"a": ["ghost"]}))
        self.assertIsNone(order)
        self.assertIn("ghost", err)
        self.assertIn("does not exist", err)


class TestSequenceCLI(unittest.TestCase):
    """The `order` CLI: exit 0 + ordered stdout, exit 2 on a graph failure."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ds-cli-"))
        self.parts = self.tmp / "parts"
        self.parts.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_order_exit_zero_and_sorted(self):
        (self.parts / "a.md").write_text(_part("foundations", []), encoding="utf-8")
        (self.parts / "b.md").write_text(_part("surface", ["foundations"]), encoding="utf-8")
        rc, out, err = ds.sequence(str(self.parts))
        self.assertEqual(rc, 0, err)
        self.assertEqual(out.split(), ["foundations", "surface"])

    def test_order_exit_two_on_cycle(self):
        (self.parts / "a.md").write_text(_part("a", ["b"]), encoding="utf-8")
        (self.parts / "b.md").write_text(_part("b", ["a"]), encoding="utf-8")
        self.assertEqual(ds.main(["design_sequence.py", "order", str(self.parts)]), 2)


class TestStagePlanWiring(unittest.TestCase):
    """Integration: the helper's order wired through the real `stage_plan.py`.

    Mirrors the command body's Step 4 — first part `activate`d → named active
    plan, the rest staged to `queued-plans/`, the singleton `PLAN.md` never
    touched. Proves the crickets divergence from agentm (which writes the first
    part to the singleton).
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ds-wire-"))
        self.parts = self.tmp / "parts"
        self.parts.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_first_activated_rest_queued_singleton_untouched(self):
        (self.parts / "f.md").write_text(_part("foundations", []), encoding="utf-8")
        (self.parts / "s.md").write_text(_part("surface", ["foundations"]), encoding="utf-8")
        (self.parts / "r.md").write_text(
            _part("rollout", ["foundations", "surface"]), encoding="utf-8")

        rc, out, err = ds.sequence(str(self.parts))
        self.assertEqual(rc, 0, err)
        order = out.split()
        self.assertEqual(order, ["foundations", "surface", "rollout"])

        doc_slug = "foo"
        root = str(self.tmp)
        # Stage every part as a NAMED plan; activate only the first (resolver=None
        # → the .harness/ fallback under our temp root).
        for i, slug in enumerate(order):
            name = f"{doc_slug}-{slug}"
            rc, staged, err = stage_plan.staging_path(name, root, resolver=None)
            self.assertEqual(rc, 0, err)
            sp = Path(staged.strip())
            sp.parent.mkdir(parents=True, exist_ok=True)
            sp.write_text(f"# Plan: {slug}\n\n**Status:** planning\n", encoding="utf-8")
            if i == 0:
                rc, active, err = stage_plan.activate(name, root, resolver=None)
                self.assertEqual(rc, 0, err)

        harness = self.tmp / ".harness"
        # First part is the active named plan.
        self.assertTrue((harness / "PLAN-foo-foundations.md").is_file())
        # The rest stay queued.
        self.assertTrue((harness / "queued-plans" / "PLAN-foo-surface.md").is_file())
        self.assertTrue((harness / "queued-plans" / "PLAN-foo-rollout.md").is_file())
        # The non-first parts are NOT activated.
        self.assertFalse((harness / "PLAN-foo-surface.md").exists())
        self.assertFalse((harness / "PLAN-foo-rollout.md").exists())
        # The singleton is never touched.
        self.assertFalse((harness / "PLAN.md").exists())


if __name__ == "__main__":
    unittest.main()
