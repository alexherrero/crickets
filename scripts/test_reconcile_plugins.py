"""test_reconcile_plugins.py — the plugin-reconcile diff is correct, and the
real marketplace reflects the wiki→wiki-maintenance rename.

Runs in the battery (unittest discovery). Stdlib only; the host shell-out
(`installed_plugins`) is deliberately NOT exercised here — it graceful-skips
when `claude` is absent, which is the case in CI."""
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


class TestRealMarketplace(unittest.TestCase):
    def test_marketplace_reflects_the_rename(self):
        offered = rp.offered_plugins()
        self.assertIn("wiki-maintenance", offered)
        self.assertNotIn("wiki", offered, "the v3.2.0 rename should have removed 'wiki'")
        self.assertGreaterEqual(len(offered), 6)


if __name__ == "__main__":
    unittest.main()
