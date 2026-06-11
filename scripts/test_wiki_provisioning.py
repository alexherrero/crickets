"""test_wiki_provisioning.py — wiki-sync-template part: the gate-distribution
mechanism (vendor helper + bundled workflow templates) and the single-source
invariant. Stdlib only; runs in the battery."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLUGIN_SRC = REPO / "src" / "wiki-maintenance"
DIST = REPO / "dist"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


vg = _load("vendor_gate_under_test", PLUGIN_SRC / "scripts" / "vendor_gate.py")


class TestVendorGate(unittest.TestCase):
    def test_gate_source_resolves_to_plugin_scripts(self):
        self.assertEqual(vg.gate_source(PLUGIN_SRC),
                         PLUGIN_SRC / "scripts" / "check-wiki.py")
        self.assertTrue(vg.gate_source(PLUGIN_SRC).is_file())

    def test_vendor_copies_to_github_scripts(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            dest = vg.vendor_gate(target, plugin_root=PLUGIN_SRC)
            self.assertEqual(dest, target / ".github" / "scripts" / "check-wiki.py")
            self.assertEqual(dest.read_bytes(),
                             (PLUGIN_SRC / "scripts" / "check-wiki.py").read_bytes())

    def test_resync_overwrites_stale_copy(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            dest = vg.vendor_gate(target, plugin_root=PLUGIN_SRC)
            dest.write_text("STALE", encoding="utf-8")          # simulate drift
            vg.vendor_gate(target, plugin_root=PLUGIN_SRC)      # --resync-gate
            self.assertEqual(dest.read_bytes(),
                             (PLUGIN_SRC / "scripts" / "check-wiki.py").read_bytes())

    def test_missing_source_raises(self):
        with tempfile.TemporaryDirectory() as td:
            empty = Path(td) / "plugin"
            (empty / "scripts").mkdir(parents=True)             # no check-wiki.py
            with self.assertRaises(FileNotFoundError):
                vg.vendor_gate(Path(td) / "target", plugin_root=empty)


class TestWorkflowTemplates(unittest.TestCase):
    SYNC = "templates/workflows/wiki-sync.yml"

    def test_template_lives_in_plugin_source(self):
        self.assertTrue((PLUGIN_SRC / self.SYNC).is_file())

    def test_template_bundles_to_both_hosts(self):
        for host in ("claude-code", "antigravity"):
            base = DIST / host / "plugins" / "wiki-maintenance"
            self.assertTrue((base / self.SYNC).is_file(), f"{host} missing wiki workflow")

    def test_workflow_job_name_is_opinionated(self):
        self.assertIn('name: "[W] Update Wiki"',
                      (PLUGIN_SRC / self.SYNC).read_text(encoding="utf-8"))

    def test_lint_job_gates_publish_via_vendored_gate(self):
        text = (PLUGIN_SRC / self.SYNC).read_text(encoding="utf-8")
        run_lines = [ln for ln in text.splitlines()
                     if "run:" in ln and "check-wiki.py" in ln]
        self.assertTrue(run_lines, "no run: step invoking check-wiki.py")
        # the lint job invokes the VENDORED gate (GH Actions has no ${CLAUDE_PLUGIN_ROOT})
        self.assertIn(".github/scripts/check-wiki.py", run_lines[0])
        # publish is gated on the lint job — a structurally-broken wiki never publishes
        self.assertIn("needs: lint-wiki", text)

    def test_single_source_no_repo_root_gate(self):
        # exactly one hand-maintained check-wiki.py — in the plugin, not repo root
        self.assertFalse((REPO / "scripts" / "check-wiki.py").exists())
        self.assertTrue((PLUGIN_SRC / "scripts" / "check-wiki.py").is_file())


if __name__ == "__main__":
    unittest.main()
