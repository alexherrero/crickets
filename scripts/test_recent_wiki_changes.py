#!/usr/bin/env python3
"""Regression test for recent-wiki-changes.sh's kernel-dependency resolution
(R2.4 task 5).

The script resolves agentm's kernel scripts (agentm_config.py / repo_registry.py)
as dirname-siblings only — dist-installed copies ship neither file nor a lib/
fallback dir, so the command was dead on arrival in every distribution form
(cricketsPluginsB#2). The fix adds an $AGENTM_SCRIPTS_DIR env-override,
mirroring wiki_watch_config.py's find_agentm_script resolver.

CI has no sibling agentm checkout, so this test builds a minimal fixture
AGENTM_SCRIPTS_DIR with stub kernel scripts rather than depending on a real
one — it proves the *resolution* logic, not the real integration.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPT = _ROOT / "src" / "wiki-maintenance" / "scripts" / "recent-wiki-changes.sh"

def _stub_agentm_config(vault_dir: str) -> str:
    return (
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if '--get' in sys.argv and 'vault_path' in sys.argv:\n"
        f"    print({vault_dir!r})\n"
    )


_STUB_REPO_REGISTRY = """#!/usr/bin/env python3
import json
print(json.dumps({"repos": []}))
"""


def _find_bash() -> str:
    """See test_dist_hooks_functional.py's `_find_bash` for the rationale —
    a bare `bash` PATH lookup on windows-latest can resolve to the WSL
    launcher stub ahead of Git's real bash.exe."""
    if os.name != "nt":
        return "bash"
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    for candidate in (
        Path(program_files) / "Git" / "bin" / "bash.exe",
        Path(program_files) / "Git" / "usr" / "bin" / "bash.exe",
    ):
        if candidate.is_file():
            return str(candidate)
    return "bash"


_BASH = _find_bash()


def _run(env_overrides: dict) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    for k in ("MEMORY_VAULT_PATH", "AGENTM_SCRIPTS_DIR"):
        env.pop(k, None)
    env.update(env_overrides)
    return subprocess.run(
        [_BASH, str(_SCRIPT)], env=env, capture_output=True, text=True, timeout=30,
    )


class TestKernelDependencyResolution(unittest.TestCase):
    def test_graceful_skip_without_agentm_scripts_dir(self):
        # No sibling agentm checkout, no env override, no vault configured -> a
        # readable JSON skip marker + exit 1, never a crash or a bare stderr error.
        r = _run({})
        self.assertEqual(r.returncode, 1)
        self.assertIn('"skipped": true', r.stdout)
        self.assertIn("agentm_config.py unreachable", r.stdout)
        self.assertIn("AGENTM_SCRIPTS_DIR", r.stdout)

    def test_resolves_registry_script_via_agentm_scripts_dir_env_override(self):
        # MEMORY_VAULT_PATH set directly (bypasses the agentm_config.py branch,
        # which the next test exercises) so this isolates repo_registry.py's
        # resolution specifically — the fix's more directly cited defect.
        with tempfile.TemporaryDirectory() as td:
            scripts_dir = Path(td)
            (scripts_dir / "repo_registry.py").write_text(_STUB_REPO_REGISTRY, encoding="utf-8")
            vault_dir = scripts_dir / "vault"
            vault_dir.mkdir()
            r = _run({"AGENTM_SCRIPTS_DIR": str(scripts_dir), "MEMORY_VAULT_PATH": str(vault_dir)})
            self.assertNotIn("not found", r.stdout + r.stderr)
            self.assertIn("No repos registered", r.stderr)
            self.assertEqual(r.returncode, 0)

    def test_resolves_vault_path_via_agentm_config_py_env_override(self):
        # MEMORY_VAULT_PATH left unset -> forces the agentm_config.py branch
        # of vault-path resolution through the same env-override resolver.
        with tempfile.TemporaryDirectory() as td:
            scripts_dir = Path(td)
            vault_dir = scripts_dir / "vault"
            vault_dir.mkdir()
            (scripts_dir / "agentm_config.py").write_text(
                _stub_agentm_config(str(vault_dir)), encoding="utf-8")
            (scripts_dir / "repo_registry.py").write_text(_STUB_REPO_REGISTRY, encoding="utf-8")
            r = _run({"AGENTM_SCRIPTS_DIR": str(scripts_dir)})
            self.assertNotIn("unreachable", r.stdout + r.stderr)
            self.assertIn("No repos registered", r.stderr)
            self.assertEqual(r.returncode, 0)

    def test_missing_registry_script_still_gracefully_skips_not_crashes(self):
        with tempfile.TemporaryDirectory() as td:
            scripts_dir = Path(td)
            vault_dir = scripts_dir / "vault"
            vault_dir.mkdir()
            (scripts_dir / "agentm_config.py").write_text(
                _stub_agentm_config(str(vault_dir)), encoding="utf-8")
            # repo_registry.py deliberately absent.
            r = _run({"AGENTM_SCRIPTS_DIR": str(scripts_dir)})
            self.assertEqual(r.returncode, 1)
            self.assertIn('"skipped": true', r.stdout)
            self.assertIn("repo_registry.py not found", r.stdout)


if __name__ == "__main__":
    unittest.main()
