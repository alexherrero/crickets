#!/usr/bin/env python3
"""The session-start hook lists the project's vault living designs (plan 103, step 12).

`harness-context-session-start` already printed the paths of launched `wiki/designs/`
pages. It now also prints the paths of live notes in the project's vault designs
folder, found through `vault_designs.py` (which asks agentm where that folder is).
Each test drives the real hook script, `.sh` and `.ps1`, against a scratch plugin
root whose `project_homes.py` is a stub that names a scratch folder, so what is
pinned is the hook's behaviour: it prints the live notes, never a draft, keeps the
repo's own pages, and stays silent (exit 0) whenever anything it needs is missing.

The `.sh` twin is posix-only; the `.ps1` twin runs wherever `pwsh` is on PATH.

stdlib only.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_DL = _ROOT / "src" / "development-lifecycle"
_HOOK_DIR = _DL / "hooks" / "harness-context-session-start"
_SH = _HOOK_DIR / "harness-context-session-start.sh"
_PS1 = _HOOK_DIR / "harness-context-session-start.ps1"
_PWSH = shutil.which("pwsh")

_STUB_HOMES = """\
import os
from pathlib import Path


def home(kind, *, cwd=None, project=None, timeout=30):
    d = os.environ.get("STUB_DESIGNS_DIR", "")
    return Path(d) if d else None
"""

_HEADER = "Living designs (vault)"


def write_note(directory: Path, slug: str, status: str, updated: str) -> Path:
    p = directory / ("%s.md" % slug)
    p.write_text("---\nslug: %s\nstatus: %s\nupdated: %s\n---\n\n# %s\n" % (slug, status, updated, slug),
                 encoding="utf-8")
    return p


class HookCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="vdh-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.designs = self.tmp / "vault-designs"
        self.designs.mkdir()
        self.plugin = self.tmp / "plugin"
        (self.plugin / "scripts").mkdir(parents=True)
        shutil.copy(_DL / "scripts" / "vault_designs.py", self.plugin / "scripts" / "vault_designs.py")
        (self.plugin / "scripts" / "project_homes.py").write_text(_STUB_HOMES, encoding="utf-8")

    def env(self, **extra):
        env = dict(os.environ)
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        env["CLAUDE_PLUGIN_ROOT"] = str(self.plugin)
        env["STUB_DESIGNS_DIR"] = str(self.designs)
        env.update(extra)
        return {k: v for k, v in env.items() if v is not None}

    def run_hook(self, **extra) -> subprocess.CompletedProcess:
        raise NotImplementedError

    # ---- the behaviour, once for each twin

    def check_lists_live_notes_newest_first_and_never_a_draft(self):
        a = write_note(self.designs, "older", "active", "2026-01-01")
        b = write_note(self.designs, "newer", "launched", "2026-05-01")
        write_note(self.designs, "wip", "draft", "2026-09-01")
        r = self.run_hook()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(_HEADER, r.stdout)
        lines = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("design:")]
        self.assertEqual(lines, ["design: %s" % b, "design: %s" % a])
        self.assertNotIn("wip", r.stdout)

    def check_is_capped_at_four(self):
        for i in range(7):
            write_note(self.designs, "n%d" % i, "active", "2026-01-%02d" % (i + 1))
        r = self.run_hook()
        self.assertEqual(len([l for l in r.stdout.splitlines() if l.strip().startswith("design:")]), 4)

    def check_keeps_the_repos_own_launched_pages(self):
        (self.repo / "wiki" / "designs").mkdir(parents=True)
        (self.repo / "wiki" / "designs" / "x.md").write_text("---\nstatus: launched\n---\n", encoding="utf-8")
        write_note(self.designs, "vault-one", "active", "2026-01-01")
        r = self.run_hook()
        self.assertIn("Governing designs (launched)", r.stdout)
        self.assertIn(_HEADER, r.stdout)
        self.assertIn("x.md", r.stdout)
        self.assertIn("vault-one.md", r.stdout)

    def check_silent_when_there_are_no_live_notes(self):
        write_note(self.designs, "wip", "draft", "2026-01-01")
        r = self.run_hook()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(_HEADER, r.stdout)

    def check_silent_when_agentm_names_no_folder(self):
        r = self.run_hook(STUB_DESIGNS_DIR="")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(_HEADER, r.stdout)

    def check_silent_when_the_plugin_root_is_unset_or_the_script_is_missing(self):
        write_note(self.designs, "a", "active", "2026-01-01")
        r = self.run_hook(CLAUDE_PLUGIN_ROOT=str(self.tmp / "nowhere"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(_HEADER, r.stdout)

    def check_a_broken_helper_never_blocks_boot(self):
        (self.plugin / "scripts" / "vault_designs.py").write_text("raise SystemExit(7)\n", encoding="utf-8")
        write_note(self.designs, "a", "active", "2026-01-01")
        r = self.run_hook()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(_HEADER, r.stdout)


@unittest.skipUnless(os.name == "posix", "bash hooks are posix; Windows uses .ps1")
class TestShTwin(HookCase):
    def run_hook(self, **extra):
        payload = json.dumps({"cwd": str(self.repo)})
        return subprocess.run(["bash", str(_SH)], input=payload, capture_output=True, text=True,
                              timeout=30, env=self.env(**extra))

    test_lists_live_notes = HookCase.check_lists_live_notes_newest_first_and_never_a_draft
    test_capped_at_four = HookCase.check_is_capped_at_four
    test_keeps_repo_pages = HookCase.check_keeps_the_repos_own_launched_pages
    test_silent_no_live_notes = HookCase.check_silent_when_there_are_no_live_notes
    test_silent_no_folder = HookCase.check_silent_when_agentm_names_no_folder
    test_silent_no_plugin_root = HookCase.check_silent_when_the_plugin_root_is_unset_or_the_script_is_missing
    test_broken_helper = HookCase.check_a_broken_helper_never_blocks_boot


@unittest.skipUnless(_PWSH, "pwsh not on PATH; .ps1 behavior is exercised on the CI runners (all ship pwsh)")
class TestPs1Twin(HookCase):
    def run_hook(self, **extra):
        payload = json.dumps({"cwd": str(self.repo)})
        return subprocess.run([_PWSH, "-NoProfile", "-File", str(_PS1)], input=payload, capture_output=True,
                              text=True, timeout=60, env=self.env(**extra))

    test_lists_live_notes = HookCase.check_lists_live_notes_newest_first_and_never_a_draft
    test_capped_at_four = HookCase.check_is_capped_at_four
    test_keeps_repo_pages = HookCase.check_keeps_the_repos_own_launched_pages
    test_silent_no_live_notes = HookCase.check_silent_when_there_are_no_live_notes
    test_silent_no_folder = HookCase.check_silent_when_agentm_names_no_folder
    test_silent_no_plugin_root = HookCase.check_silent_when_the_plugin_root_is_unset_or_the_script_is_missing
    test_broken_helper = HookCase.check_a_broken_helper_never_blocks_boot


if __name__ == "__main__":
    unittest.main()
