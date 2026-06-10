"""test_reconcile_plugins.py — the plugin-reconcile diff is correct, and the
real marketplace reflects the wiki→wiki-maintenance rename.

Runs in the battery (unittest discovery). Stdlib only; the host shell-out
(`installed_plugins`) is deliberately NOT exercised here — it graceful-skips
when `claude` is absent, which is the case in CI."""
import sys
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


class TestRealMarketplace(unittest.TestCase):
    def test_marketplace_reflects_the_rename(self):
        offered = rp.offered_plugins()
        self.assertIn("wiki-maintenance", offered)
        self.assertNotIn("wiki", offered, "the v3.2.0 rename should have removed 'wiki'")
        self.assertGreaterEqual(len(offered), 6)


if __name__ == "__main__":
    unittest.main()
