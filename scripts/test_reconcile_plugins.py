"""test_reconcile_plugins.py — the plugin-reconcile diff is correct, and the
real marketplace reflects the wiki→wiki-maintenance rename.

Runs in the battery (unittest discovery). Stdlib only; the host shell-out
(`installed_plugins`) is deliberately NOT exercised here — it graceful-skips
when `claude` is absent, which is the case in CI."""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reconcile_plugins as rp  # noqa: E402


class TestComputeActions(unittest.TestCase):
    def test_rename_shows_stale_and_missing(self):
        # the exact v3.2.0 case: wiki renamed to wiki-maintenance
        a = rp.compute_actions(offered={"wiki-maintenance", "pii"}, installed={"wiki", "pii"})
        self.assertEqual(a["stale"], ["wiki"])           # uninstall the old name
        self.assertEqual(a["missing"], ["wiki-maintenance"])  # install the new
        self.assertEqual(a["ok"], ["pii"])

    def test_all_in_sync(self):
        a = rp.compute_actions(offered={"a", "b"}, installed={"a", "b"})
        self.assertEqual(a["stale"], [])
        self.assertEqual(a["missing"], [])
        self.assertEqual(a["ok"], ["a", "b"])

    def test_missing_only(self):
        a = rp.compute_actions(offered={"a", "b"}, installed={"a"})
        self.assertEqual(a["missing"], ["b"])
        self.assertEqual(a["stale"], [])

    def test_sorted_output(self):
        a = rp.compute_actions(offered={"z", "a", "m"}, installed=set())
        self.assertEqual(a["missing"], ["a", "m", "z"])


class TestComputePrimitiveActions(unittest.TestCase):
    # The keep-list: agentm-native / third-party standalones no crickets plugin
    # provides. These must ALWAYS survive.
    KEEP = {("command", "design"), ("command", "memory"), ("command", "doctor"),
            ("command", "last30days"), ("agent", "adapt-evaluator"),
            ("agent", "memory-idea-researcher")}

    def test_superseded_and_kept_split(self):
        offered = {("command", "work"), ("command", "plan"), ("agent", "explorer")}
        standalones = {("command", "work"), ("command", "plan"),
                       ("agent", "explorer")} | self.KEEP
        a = rp.compute_primitive_actions(offered, standalones, protected=set())
        self.assertEqual(a["superseded"],
                         [("agent", "explorer"), ("command", "plan"), ("command", "work")])
        # everything the plugins don't provide is kept
        self.assertEqual(set(a["kept"]), self.KEEP)

    def test_keep_list_always_survives(self):
        # even if a (buggy) offered set somehow lists nothing, keep-list survives;
        # and when offered is empty, NOTHING is superseded.
        a = rp.compute_primitive_actions(set(), self.KEEP)
        self.assertEqual(a["superseded"], [])
        self.assertEqual(set(a["kept"]), self.KEEP)

    def test_known_divergent_is_protected(self):
        # wiki-maintenance provides (agent, documenter), but the standalone differs
        # — it must be kept, not superseded, by default.
        offered = {("agent", "documenter"), ("command", "work")}
        standalones = {("agent", "documenter"), ("command", "work")}
        a = rp.compute_primitive_actions(offered, standalones)  # default protected
        self.assertEqual(a["superseded"], [("command", "work")])
        self.assertIn(("agent", "documenter"), a["kept"])

    def test_name_match_is_kind_scoped(self):
        # a skill named 'foo' is NOT superseded by a plugin *agent* named 'foo'
        offered = {("agent", "foo")}
        standalones = {("skill", "foo")}
        a = rp.compute_primitive_actions(offered, standalones, protected=set())
        self.assertEqual(a["superseded"], [])
        self.assertEqual(a["kept"], [("skill", "foo")])


class TestPrimitiveEnumeration(unittest.TestCase):
    def test_plugin_primitives_real_dist(self):
        dw = rp.plugin_primitives(rp.PLUGINS_ROOT / "developer-workflows")
        self.assertIn(("command", "work"), dw)
        self.assertIn(("command", "plan"), dw)
        self.assertIn(("agent", "explorer"), dw)
        # bundled scripts + hooks are NOT ~/.claude standalones
        self.assertNotIn(("command", "capability_probe"), dw)
        self.assertFalse(any(kind == "hook" for kind, _ in dw))

    def test_plugin_primitives_includes_skills_and_agents(self):
        wm = rp.plugin_primitives(rp.PLUGINS_ROOT / "wiki-maintenance")
        self.assertIn(("agent", "documenter"), wm)
        self.assertIn(("skill", "diataxis-author"), wm)

    def test_offered_map_none_installed_is_empty(self):
        # host CLI unavailable -> can't confirm installs -> nothing eligible
        self.assertEqual(rp.offered_primitive_map(installed=None), {})

    def test_offered_map_filters_to_installed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "alpha" / "commands").mkdir(parents=True)
            (root / "alpha" / "commands" / "foo.md").write_text("x", encoding="utf-8")
            (root / "beta" / "agents").mkdir(parents=True)
            (root / "beta" / "agents" / "bar.md").write_text("x", encoding="utf-8")
            self.assertEqual(rp.offered_primitive_map(root, installed={"alpha"}),
                             {("command", "foo"): "alpha"})  # beta not installed
            self.assertEqual(rp.offered_primitive_map(root, installed={"alpha", "beta"}),
                             {("command", "foo"): "alpha", ("agent", "bar"): "beta"})


class TestStandaloneScan(unittest.TestCase):
    def test_installed_standalones_scan(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / "skills" / "foo").mkdir(parents=True)
            (home / "agents").mkdir()
            (home / "agents" / "bar.md").write_text("x", encoding="utf-8")
            (home / "commands").mkdir()
            (home / "commands" / "baz.md").write_text("x", encoding="utf-8")
            self.assertEqual(rp.installed_standalones(home),
                             {("skill", "foo"), ("agent", "bar"), ("command", "baz")})

    def test_installed_standalones_missing_dirs_is_empty(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(rp.installed_standalones(Path(td)), set())

    def test_classify_supersedes_only_installed_provided(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            home = root / "home"
            (home / "commands").mkdir(parents=True)
            (home / "commands" / "work.md").write_text("x", encoding="utf-8")     # superseded
            (home / "commands" / "design.md").write_text("x", encoding="utf-8")   # keep-list
            plugins = root / "plugins"
            (plugins / "developer-workflows" / "commands").mkdir(parents=True)
            (plugins / "developer-workflows" / "commands" / "work.md").write_text("x", encoding="utf-8")
            rep = rp.classify_standalones(home, plugins, installed={"developer-workflows"})
            self.assertEqual(rep["superseded"], [("command", "work")])
            self.assertEqual(rep["kept"], [("command", "design")])  # no plugin provides it
            self.assertEqual(rep["provenance"], {("command", "work"): "developer-workflows"})

    def test_classify_installed_none_keeps_everything(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / "commands").mkdir(parents=True)
            (home / "commands" / "work.md").write_text("x", encoding="utf-8")
            rep = rp.classify_standalones(home, rp.PLUGINS_ROOT, installed=None)
            self.assertEqual(rep["superseded"], [])               # can't confirm installs
            self.assertEqual(rep["kept"], [("command", "work")])


class TestApplyRetirement(unittest.TestCase):
    def _fixture(self, root):
        """A ~/.claude home + a dist plugins root. home has: command/work (superseded),
        command/design (keep-list), agent/documenter (divergent -> kept), skill/wiki-author
        (superseded). Returns (home, plugins, installed)."""
        home = root / "home"
        (home / "commands").mkdir(parents=True)
        (home / "commands" / "work.md").write_text("x", encoding="utf-8")
        (home / "commands" / "design.md").write_text("x", encoding="utf-8")
        (home / "agents").mkdir()
        (home / "agents" / "documenter.md").write_text("x", encoding="utf-8")
        (home / "skills" / "wiki-author").mkdir(parents=True)
        plugins = root / "plugins"
        (plugins / "developer-workflows" / "commands").mkdir(parents=True)
        (plugins / "developer-workflows" / "commands" / "work.md").write_text("x", encoding="utf-8")
        (plugins / "wiki-maintenance" / "agents").mkdir(parents=True)
        (plugins / "wiki-maintenance" / "agents" / "documenter.md").write_text("x", encoding="utf-8")
        (plugins / "wiki-maintenance" / "skills" / "wiki-author").mkdir(parents=True)
        return home, plugins, {"developer-workflows", "wiki-maintenance"}

    def test_remove_standalone_file_and_dir(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / "agents").mkdir()
            f = home / "agents" / "bar.md"; f.write_text("x", encoding="utf-8")
            (home / "skills" / "foo").mkdir(parents=True)
            rp.remove_standalone(home, ("agent", "bar"))
            rp.remove_standalone(home, ("skill", "foo"))
            self.assertFalse(f.exists())
            self.assertFalse((home / "skills" / "foo").exists())

    def test_classify_then_apply_removes_only_superseded(self):
        with tempfile.TemporaryDirectory() as td:
            home, plugins, installed = self._fixture(Path(td))
            rep = rp.classify_standalones(home, plugins, installed)
            self.assertEqual(rep["superseded"],
                             [("command", "work"), ("skill", "wiki-author")])
            self.assertIn(("command", "design"), rep["kept"])
            self.assertIn(("agent", "documenter"), rep["kept"])   # divergent protected
            rp.apply_retirement(home, rep["superseded"])
            self.assertFalse((home / "commands" / "work.md").exists())
            self.assertFalse((home / "skills" / "wiki-author").exists())
            self.assertTrue((home / "commands" / "design.md").exists())     # keep-list survives
            self.assertTrue((home / "agents" / "documenter.md").exists())   # divergent survives

    def test_apply_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            home, plugins, installed = self._fixture(Path(td))
            rep = rp.classify_standalones(home, plugins, installed)
            rp.apply_retirement(home, rep["superseded"])
            rep2 = rp.classify_standalones(home, plugins, installed)
            self.assertEqual(rep2["superseded"], [])               # second run is a no-op

    def test_preview_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            home, plugins, installed = self._fixture(Path(td))
            with contextlib.redirect_stdout(io.StringIO()):
                rc = rp._reconcile_standalones(apply=False, claude_home=home,
                                               plugins_root=plugins, installed=installed)
            self.assertEqual(rc, 0)
            self.assertTrue((home / "commands" / "work.md").exists())   # untouched in preview

    def test_apply_via_cli_helper_assume_yes(self):
        with tempfile.TemporaryDirectory() as td:
            home, plugins, installed = self._fixture(Path(td))
            with contextlib.redirect_stdout(io.StringIO()):
                rc = rp._reconcile_standalones(apply=True, assume_yes=True, claude_home=home,
                                               plugins_root=plugins, installed=installed)
            self.assertEqual(rc, 0)
            self.assertFalse((home / "commands" / "work.md").exists())
            self.assertTrue((home / "agents" / "documenter.md").exists())  # divergent kept


class TestRealMarketplace(unittest.TestCase):
    def test_marketplace_reflects_the_rename(self):
        offered = rp.offered_plugins()
        self.assertIn("wiki-maintenance", offered)
        self.assertNotIn("wiki", offered, "the v3.2.0 rename should have removed 'wiki'")
        self.assertGreaterEqual(len(offered), 6)


if __name__ == "__main__":
    unittest.main()
