#!/usr/bin/env python3
"""Tests for scripts/integrate_prepare.py — the single-writer artifact-prepare step (ADR 0030).

Three layers:
  - pure logic (bump/rewrite/read version, slug mapping) with no git;
  - `run_prepare` over a real throwaway repo with a STUB `regenerate` (never the
    real `generate.py`, which a temp fixture has no src tree for);
  - the HEADLINE two-branch simulation that wires `integrate_worker` +
    `integrate_prepare` + a fake generate to prove Model A eliminates the
    cross-plugin `marketplace.json` collision for disjoint plugins while still
    surfacing a genuine same-plugin overlap as a clean, rolled-back conflict.

Both modules are loaded by path (integrate_prepare from this dir; integrate_worker
from src/developer-workflows/scripts), mirroring the sibling test files.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_DW_SCRIPTS = _ROOT / "src" / "development-lifecycle" / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


ip = _load("integrate_prepare", _HERE / "integrate_prepare.py")
iw = _load("integrate_worker", _DW_SCRIPTS / "integrate_worker.py")


# ── shared git + fake-generate plumbing (the simulation + run_prepare fixture) ──

def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo),
                          capture_output=True, text=True, check=check)


def _read_versions(root) -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    src = Path(root) / "src"
    if src.is_dir():
        for gy in sorted(src.glob("*/group.yaml")):
            versions[gy.parent.name] = ip.read_version(gy.read_text(encoding="utf-8"))
    return versions


def _fake_generate(root) -> tuple[int, str]:
    """Stand in for `generate.py build`: write `marketplace.json` from the current
    src/*/group.yaml versions + a per-plugin dist stamp. DETERMINISTIC, so a
    regenerate at an UNCHANGED version is byte-identical — the property that makes
    the disjoint two-branch merge conflict-free (the registry moves only on a bump,
    which only the serialized integrator performs).
    """
    root = Path(root)
    versions = _read_versions(root)
    mp = root / ".claude-plugin" / "marketplace.json"
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps({"plugins": versions}, indent=2, sort_keys=True) + "\n",
                  encoding="utf-8")
    for slug, v in versions.items():
        stamp = root / "dist" / slug / "plugin.txt"
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(f"{v}\n", encoding="utf-8")
    return (0, "[fake generate] wrote marketplace + dist stamps\n")


def _init_base_repo(repo: Path) -> None:
    """A repo on `main` with foo@1.0.0 + bar@1.0.0 and committed generated output."""
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".gitignore").write_text(".harness/\n", encoding="utf-8")
    for slug in ("foo", "bar"):
        gy = repo / "src" / slug / "group.yaml"
        gy.parent.mkdir(parents=True, exist_ok=True)
        gy.write_text(f"name: {slug}\nversion: 1.0.0\n", encoding="utf-8")
        skill = repo / "src" / slug / "skills" / slug / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("v1\n", encoding="utf-8")
    _fake_generate(repo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "M: foo@1.0.0 bar@1.0.0")


def _seed_harness(repo: Path, slug: str) -> None:
    """Seed the (gitignored) `.harness/` the `resolver=None` promotion resolves to."""
    h = repo / ".harness"
    h.mkdir(parents=True, exist_ok=True)
    (h / f"progress-{slug}.md").write_text(f"worker {slug} progress\n", encoding="utf-8")
    (h / "progress.md").write_text("mainline\n", encoding="utf-8")


def _spawn_worker(repo: Path, tmp: Path, slug: str, edit_path: str, edit_text: str):
    """A real `worker/<slug>` worktree that edits a plugin's src, regenerates dist
    at the CURRENT (unbumped) version, and commits — deferring the bump (ADR 0030).
    """
    branch = f"worker/{slug}"
    wt = tmp / f"wt-{slug}"
    _git(repo, "worktree", "add", "-b", branch, str(wt))
    target = wt / edit_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(edit_text, encoding="utf-8")
    _fake_generate(wt)  # worker regenerates — but at the current version, so the
    _git(wt, "add", "-A")  # shared marketplace.json is byte-identical (no delta).
    _git(wt, "commit", "-q", "-m", f"worker {slug}: edit + regen at current version")
    return branch, wt


def _green_gate(root):
    return (0, "stub gate: green\n")


def _make_prepare(level: str = "patch"):
    """An integrate_worker `prepare` that runs the REAL run_prepare with a stub
    regenerate — exercising both modules end to end through the injected seam."""
    def prepare(root, pre_sha):
        return ip.run_prepare(root, pre_sha, level=level, regenerate=_fake_generate)
    return prepare


# ── pure logic ────────────────────────────────────────────────────────────────

class TestBumpVersion(unittest.TestCase):
    def test_patch_minor_major(self):
        self.assertEqual(ip.bump_version("1.2.3", "patch"), "1.2.4")
        self.assertEqual(ip.bump_version("1.2.3", "minor"), "1.3.0")
        self.assertEqual(ip.bump_version("1.2.3", "major"), "2.0.0")

    def test_tolerates_v_prefix_and_suffix(self):
        self.assertEqual(ip.bump_version("v0.1.0", "patch"), "0.1.1")
        self.assertEqual(ip.bump_version("1.2.3-rc1", "minor"), "1.3.0")
        self.assertEqual(ip.bump_version("1.2.3+build", "major"), "2.0.0")

    def test_rejects_garbage(self):
        for bad in ("banana", "0.2", "1.2.3.4", "", "a.b.c", "-1.0.0"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    ip.bump_version(bad, "patch")

    def test_rejects_unknown_level(self):
        with self.assertRaises(ValueError):
            ip.bump_version("1.0.0", "ultra")


class TestRewriteAndReadVersion(unittest.TestCase):
    def test_rewrite_replaces_version_line(self):
        text = "name: foo\nversion: 0.1.0\ncategory: x\n"
        self.assertEqual(ip.rewrite_version(text, "0.2.0"),
                         "name: foo\nversion: 0.2.0\ncategory: x\n")

    def test_rewrite_replaces_only_the_first_top_level_line(self):
        text = "version: 1.0.0\ndesc: version: not-a-key\n"
        out = ip.rewrite_version(text, "1.0.1")
        self.assertIn("version: 1.0.1\n", out)
        self.assertIn("desc: version: not-a-key", out)  # the non-key line is untouched

    def test_rewrite_raises_without_version_line(self):
        with self.assertRaises(ValueError):
            ip.rewrite_version("name: foo\nstandalone: true\n", "0.2.0")

    def test_read_version(self):
        self.assertEqual(ip.read_version("name: x\nversion: 2.3.4\n"), "2.3.4")
        self.assertEqual(ip.read_version("version: '1.0.0'\n"), "1.0.0")
        self.assertIsNone(ip.read_version("name: x\n"))


class TestChangedPluginSlugs(unittest.TestCase):
    def test_maps_only_src_plugin_paths(self):
        paths = ["src/foo/group.yaml", "src/foo/skills/s/SKILL.md", "src/bar/x.md",
                 "dist/foo/p.json", "scripts/g.py", "src/lone", "wiki/Home.md"]
        self.assertEqual(ip.changed_plugin_slugs(paths), {"foo", "bar"})


# ── run_prepare over a real repo with a stub regenerate ─────────────────────────

class TestRunPrepare(unittest.TestCase):
    """run_prepare bumps the merge's changed plugin(s), regenerates, stages by
    explicit path, and commits. rc 0; a no-src merge is a graceful no-op; a
    regenerate failure or a garbage version surfaces non-zero (→ integrate rolls back).
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ip-run-"))
        self.repo = self.tmp / "repo"
        _init_base_repo(self.repo)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_bumps_changed_plugin_and_commits(self):
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        (self.repo / "src/foo/skills/foo/SKILL.md").write_text("changed\n", encoding="utf-8")
        _git(self.repo, "commit", "-qam", "merge brought a src/foo change")

        rc, out = ip.run_prepare(str(self.repo), pre, regenerate=_fake_generate)
        self.assertEqual(rc, 0, out)
        self.assertIn("foo 1.0.0→1.0.1", out)
        self.assertEqual(ip.read_version((self.repo / "src/foo/group.yaml").read_text()), "1.0.1")
        # The registry moved for foo only; bar (untouched) stays put.
        mp = json.loads((self.repo / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual(mp["plugins"], {"foo": "1.0.1", "bar": "1.0.0"})
        # The bump + regen landed in a single-writer commit.
        self.assertIn("single-writer", _git(self.repo, "log", "--oneline").stdout)

    def test_no_src_change_is_graceful_noop(self):
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        (self.repo / "README2.md").write_text("docs\n", encoding="utf-8")
        _git(self.repo, "add", "README2.md")
        _git(self.repo, "commit", "-qm", "docs only")
        rc, out = ip.run_prepare(str(self.repo), pre, regenerate=_fake_generate)
        self.assertEqual(rc, 0, out)
        self.assertIn("nothing to bump", out)

    def test_minor_level(self):
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        (self.repo / "src/bar/skills/bar/SKILL.md").write_text("feat\n", encoding="utf-8")
        _git(self.repo, "commit", "-qam", "feature in bar")
        rc, out = ip.run_prepare(str(self.repo), pre, level="minor", regenerate=_fake_generate)
        self.assertEqual(rc, 0, out)
        self.assertEqual(ip.read_version((self.repo / "src/bar/group.yaml").read_text()), "1.1.0")

    def test_regenerate_failure_propagates(self):
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        (self.repo / "src/foo/skills/foo/SKILL.md").write_text("x\n", encoding="utf-8")
        _git(self.repo, "commit", "-qam", "edit foo")

        rc, out = ip.run_prepare(str(self.repo), pre, regenerate=lambda r: (1, "boom\n"))
        self.assertEqual(rc, 1)
        self.assertIn("regenerate failed", out)

    def test_garbage_version_fails_loud(self):
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        (self.repo / "src/foo/group.yaml").write_text("name: foo\nversion: banana\n",
                                                       encoding="utf-8")
        (self.repo / "src/foo/skills/foo/SKILL.md").write_text("x\n", encoding="utf-8")
        _git(self.repo, "commit", "-qam", "garbage version + edit")
        rc, out = ip.run_prepare(str(self.repo), pre, regenerate=_fake_generate)
        self.assertEqual(rc, 1)
        self.assertIn("cannot bump foo", out)


# ── headline: two-branch concurrent integration simulation ──────────────────────

class TestTwoBranchSimulation(unittest.TestCase):
    """Model A (ADR 0030) end to end: integrate_worker + integrate_prepare + a fake
    generate, two workers landing through the serialized integrator one at a time.

    Disjoint plugins → ZERO marketplace.json conflict, BOTH bumped. Because no
    worker branch ever writes a version line, the shared registry moves only in the
    integrator's prepare step, so the second integration sees a one-sided registry
    change (git takes it cleanly) instead of the cross-plugin collision Model A was
    designed to remove. Same-plugin overlap → the second integration hits a real
    src content conflict and is cleanly refused + rolled back (Model A does not
    paper over a genuine same-file overlap, only the spurious registry collision).
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ip-sim-"))
        self.repo = self.tmp / "repo"
        _init_base_repo(self.repo)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_disjoint_plugins_zero_marketplace_conflict_both_bumped(self):
        _seed_harness(self.repo, "foo")
        _seed_harness(self.repo, "bar")
        _spawn_worker(self.repo, self.tmp, "foo",
                      "src/foo/skills/foo/SKILL.md", "v2-from-foo-worker\n")
        _spawn_worker(self.repo, self.tmp, "bar",
                      "src/bar/skills/bar/SKILL.md", "v2-from-bar-worker\n")
        prepare = _make_prepare()

        rc_a, _out_a, err_a = iw.integrate("foo", str(self.repo),
                                           gate=_green_gate, prepare=prepare, resolver=None)
        self.assertEqual(rc_a, 0, err_a)
        # THE HEADLINE: bar lands on a main already carrying foo's bump with no
        # marketplace.json conflict — the worker never touched the version line.
        rc_b, _out_b, err_b = iw.integrate("bar", str(self.repo),
                                           gate=_green_gate, prepare=prepare, resolver=None)
        self.assertEqual(rc_b, 0, err_b)

        mp = json.loads((self.repo / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual(mp["plugins"], {"foo": "1.0.1", "bar": "1.0.1"})
        # Both plugins' src changes are on main.
        self.assertEqual((self.repo / "src/foo/skills/foo/SKILL.md").read_text(),
                         "v2-from-foo-worker\n")
        self.assertEqual((self.repo / "src/bar/skills/bar/SKILL.md").read_text(),
                         "v2-from-bar-worker\n")

    def test_same_plugin_overlap_second_integration_conflicts_and_rolls_back(self):
        _seed_harness(self.repo, "foo")
        _seed_harness(self.repo, "foo2")
        # Both workers edit the SAME source line of the SAME plugin.
        _spawn_worker(self.repo, self.tmp, "foo",
                      "src/foo/skills/foo/SKILL.md", "A-version\n")
        _spawn_worker(self.repo, self.tmp, "foo2",
                      "src/foo/skills/foo/SKILL.md", "B-version\n")
        prepare = _make_prepare()

        rc_a, _out_a, err_a = iw.integrate("foo", str(self.repo),
                                           gate=_green_gate, prepare=prepare, resolver=None)
        self.assertEqual(rc_a, 0, err_a)
        pre_b = _git(self.repo, "rev-parse", "HEAD").stdout.strip()

        rc_b, out_b, err_b = iw.integrate("foo2", str(self.repo),
                                          gate=_green_gate, prepare=prepare, resolver=None)
        self.assertEqual(rc_b, 2, "a genuine same-plugin overlap must conflict")
        self.assertEqual(out_b, "")
        self.assertIn("conflicts with", err_b)
        # main rolled back to before the failed merge; foo keeps A's content + bump.
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD").stdout.strip(), pre_b)
        self.assertFalse(iw._merge_in_progress(self.repo))
        self.assertEqual((self.repo / "src/foo/skills/foo/SKILL.md").read_text(), "A-version\n")
        mp = json.loads((self.repo / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual(mp["plugins"]["foo"], "1.0.1")
        # The losing worker's worktree survives for the operator to rebase + re-run.
        self.assertTrue((self.tmp / "wt-foo2").is_dir())


if __name__ == "__main__":
    unittest.main()
