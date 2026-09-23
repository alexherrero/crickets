#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/design_sequence.py (sibling #5).

The deterministic ordering core behind `/design sequence`: dependency-list
parsing (inline + block forms), part-frontmatter validation, the Kahn topo-sort
with its alphabetical tie-break, and cycle / missing-dependency refusals. Plus
the placement of each part as a new queued task (agentm-vault part 15): stubbed
cases for every refusal, and a real-agentm class that places three parts into a
scratch vault in the task layout through development-lifecycle's resolver and
plan_tracker.py. Hermetic — parts and vaults are synthesized in throwaway temp
dirs (never the real vault).
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS = _ROOT / "src" / "design" / "scripts"


def _load(name: str, scripts_dir: Path = _SCRIPTS):
    src = scripts_dir / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, src)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


ds = _load("design_sequence")


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

    def test_block_form_survives_blank_line(self):
        # Regression (post-review bugfix 2026-06-13): a blank line between block
        # list items is a legal YAML continuation — it must NOT terminate the list
        # and silently drop every later edge (which silently corrupts the topo
        # order downstream). Fails before the fix (returns ['a']).
        fm = "dependencies:\n  - a\n\n  - b\nestimated_scope: S\n"
        self.assertEqual(ds._dependencies_from_block(fm), ["a", "b"])

    def test_block_form_survives_whitespace_only_line(self):
        # A whitespace-only line (spaces/tabs, no items) is also a continuation.
        fm = "dependencies:\n  - a\n   \n  - b\nestimated_scope: S\n"
        self.assertEqual(ds._dependencies_from_block(fm), ["a", "b"])

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

    def test_blank_line_in_block_deps_preserves_order(self):
        # Regression (post-review bugfix 2026-06-13): a part whose dependencies are
        # a YAML block list with a stray blank line between items must still be
        # sequenced AFTER all its prerequisites. Before the fix the second edge was
        # dropped and `rollout` sorted ahead of `surface`, the part it depends on.
        block = (
            "---\ntitle: Rollout\nstatus: draft\nvisibility: confidential\n"
            "part_slug: rollout\ndependencies:\n  - foundations\n\n  - surface\n"
            "estimated_scope: L\n---\n\n# rollout\n\n## Scope\n\nrollout scope\n"
        )
        (self.parts / "f.md").write_text(_part("foundations", []), encoding="utf-8")
        (self.parts / "s.md").write_text(_part("surface", ["foundations"]), encoding="utf-8")
        (self.parts / "r.md").write_text(block, encoding="utf-8")
        rc, out, err = ds.sequence(str(self.parts))
        self.assertEqual(rc, 0, err)
        order = out.split()
        self.assertEqual(order, ["foundations", "surface", "rollout"])
        self.assertLess(order.index("surface"), order.index("rollout"))


class _Answers:
    """Stands in for development-lifecycle's scripts: resolve_plan.py answers
    from a table, plan_tracker.py records its calls."""

    def __init__(self, table, *, open_rc=0):
        self.table, self.open_rc, self.calls = table, open_rc, []

    def __call__(self, rel, args):
        self.calls.append((rel, args))
        if rel.endswith("resolve_plan.py"):
            fields = self.table.get(args[0])
            if fields is None:
                return (2, "", f"no answer for {args[0]}")
            return (0, "\t".join(str(f) for f in fields) + "\n", "")
        return (self.open_rc, "", "" if self.open_rc == 0 else "tracker refused")


class TestPlacingParts(unittest.TestCase):
    """`check_names` and `place`, against stubbed answers."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ds-place-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.tasks = self.tmp / "vault" / "projects" / "demo" / "tasks"

    def task(self, name):
        d = self.tasks / name
        return [d / "plan.md", d / "progress.md", d / "tracker.md"]

    def test_a_new_task_is_written_and_its_tracker_opened(self):
        run = _Answers({"arc-one": self.task("043-arc-one")})
        rc, out = ds.place("arc-one", "# Plan: One\n", str(self.tmp), design="arc",
                           part="one", today="2026-09-22", run=run)
        plan = self.tasks / "043-arc-one" / "plan.md"
        self.assertEqual((rc, out), (0, str(plan)))
        self.assertEqual(plan.read_text(encoding="utf-8"), "# Plan: One\n")
        opened = [a for r, a in run.calls if r.endswith("plan_tracker.py")]
        self.assertEqual(opened, [["open", "--plan", str(plan), "--tracker",
                                   str(plan.parent / "tracker.md"), "--root", str(self.tmp)]])
        self.assertIn("/design sequence — queued task from design arc, part one",
                      (plan.parent / "progress.md").read_text(encoding="utf-8"))

    def test_a_flat_answer_is_refused_before_any_write(self):
        flat = self.tmp / "vault" / "projects" / "demo"
        run = _Answers({"arc-one": [flat / "PLAN-arc-one.md", flat / "progress-arc-one.md",
                                    flat / "tracker-arc-one.md"]})
        rc, reason = ds.check_names(["arc-one"], str(self.tmp), run=run)
        self.assertEqual(rc, 2)
        self.assertIn("keeps no tasks", reason)
        rc, _ = ds.place("arc-one", "x", str(self.tmp), design="arc", part="one",
                         today="2026-09-22", run=run)
        self.assertEqual(rc, 2)
        self.assertFalse(any(self.tmp.rglob("*.md")))

    def test_an_existing_task_is_refused_by_name(self):
        plan, _, _ = self.task("042-arc-one")
        plan.parent.mkdir(parents=True)
        plan.write_text("# Plan: kept\n", encoding="utf-8")
        run = _Answers({"arc-one": self.task("042-arc-one")})
        rc, reason = ds.check_names(["arc-one"], str(self.tmp), run=run)
        self.assertEqual(rc, 2)
        self.assertIn("already exists", reason)
        self.assertEqual(plan.read_text(encoding="utf-8"), "# Plan: kept\n")

    def test_no_tracker_is_refused(self):
        plan, progress, _ = self.task("043-arc-one")
        run = _Answers({"arc-one": [plan, progress, ""]})
        rc, reason = ds.check_names(["arc-one"], str(self.tmp), run=run)
        self.assertEqual(rc, 2)
        self.assertIn("no tracker", reason)

    def test_every_name_is_checked_before_the_first_write(self):
        run = _Answers({"arc-one": self.task("043-arc-one")})
        rc, reason = ds.check_names(["arc-one", "arc-two"], str(self.tmp), run=run)
        self.assertEqual(rc, 2)
        self.assertIn("'arc-two'", reason)
        self.assertFalse(self.tasks.exists())

    def test_a_tracker_that_does_not_open_is_reported(self):
        run = _Answers({"arc-one": self.task("043-arc-one")}, open_rc=1)
        rc, reason = ds.place("arc-one", "x", str(self.tmp), design="arc", part="one",
                              today="2026-09-22", run=run)
        self.assertEqual(rc, 1)
        self.assertIn("did not open", reason)


def _real_agentm():
    scripts = Path.home() / "Antigravity" / "agentm" / "scripts"
    seam, tracker = scripts / "process_seam.py", scripts / "tracker.py"
    if not (seam.is_file() and tracker.is_file()):
        return None
    r = subprocess.run([sys.executable, str(seam), "project-path", "--help"],
                       capture_output=True, text=True)
    return scripts if r.returncode == 0 else None


REAL = _real_agentm()


@unittest.skipIf(REAL is None, "no agentm checkout with project-path and tracker.py")
class TestSequencingIntoTheRealAgentm(unittest.TestCase):
    """Three parts become three numbered queued tasks, in topo order, through
    the real resolver and plan_tracker.py, in a scratch vault."""

    def setUp(self):
        sys.path.insert(0, str(_HERE))
        import no_harness_fixture as nhf
        self.nhf = nhf
        self.sp = nhf.ScratchProject()
        self.addCleanup(self.sp.cleanup)
        (self.sp.root / "home").mkdir()
        patcher = mock.patch.dict(os.environ, {
            "AGENTM_SCRIPTS_DIR": str(REAL),
            "MEMORY_ROOT": str(self.sp.vault),
            "OBSIDIAN_VAULT_SCRIPTS": str(_ROOT / "src" / "obsidian-vault" / "scripts"),
            "AGENTM_INSTALL_PREFIX": "",
            "HOME": str(self.sp.root / "home"),
            "XDG_CACHE_HOME": str(self.sp.root / "cache"),
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("MEMORY_VAULT_PATH", None)
        self.parts = self.sp.root / "parts"
        self.parts.mkdir()
        (self.parts / "f.md").write_text(_part("foundations", []), encoding="utf-8")
        (self.parts / "s.md").write_text(_part("surface", ["foundations"]), encoding="utf-8")
        (self.parts / "r.md").write_text(_part("rollout", ["foundations", "surface"]),
                                         encoding="utf-8")

    def tearDown(self):
        self.assertEqual(self.nhf.harness_dirs(self.sp.root), [])

    def body(self, slug):
        return ("---\nparent_design_doc: wiki/designs/arc.md\nparent_part_slug: "
                f"{slug}\n---\n\n# Plan: {slug}\n\n## Goal\n\n{slug} ships.\n\n"
                f"## Steps\n\n### 1. Build {slug}\n- **What:** build it.\n"
                "- **Verification:** it runs.\n- **Status:** [ ]\n")

    def test_three_parts_become_three_queued_tasks(self):
        rc, out, err = ds.sequence(str(self.parts))
        self.assertEqual(rc, 0, err)
        order = out.split()
        names = [f"arc-{s}" for s in order]
        root = str(self.sp.repo)
        self.assertEqual(ds.check_names(names, root), (0, ""))
        placed = []
        for slug, name in zip(order, names):
            rc, plan = ds.place(name, self.body(slug), root, design="arc", part=slug,
                                today="2026-09-22")
            self.assertEqual(rc, 0, plan)
            placed.append(Path(plan))
        self.assertEqual([p.parent.name for p in placed],
                         ["043-arc-foundations", "044-arc-surface", "045-arc-rollout"])
        for plan in placed:
            tracker = (plan.parent / "tracker.md").read_text(encoding="utf-8")
            self.assertIn("status: queued", tracker)
            self.assertIn("design: wiki/designs/arc.md", tracker)
            self.assertIn(f"task: {plan.parent.name}", tracker)
        rc, reason = ds.check_names(names[:1], root)
        self.assertEqual(rc, 2)
        self.assertIn("already exists", reason)


if __name__ == "__main__":
    unittest.main()
