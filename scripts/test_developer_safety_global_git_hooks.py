#!/usr/bin/env python3
"""End-to-end tests for coauthor-guard's machine-wide install
(`src/developer-safety/hooks/coauthor-guard/install-global.sh`, the
`git-hook-dispatch.sh` it fans out, and the `check-global.sh` SessionStart check).

Every test runs real git against a throwaway global config: GIT_CONFIG_GLOBAL
points at a temp file and HOME / XDG_CONFIG_HOME at a temp dir, so nothing
here can read or write the operator's own ~/.gitconfig. POSIX-only (bash);
the pwsh installer gets a smaller pass when pwsh is on PATH.

stdlib only -- no pytest.
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parent
_GUARD_DIR = REPO_ROOT / "src" / "developer-safety" / "hooks" / "coauthor-guard"
_INSTALL = _GUARD_DIR / "install-global.sh"
_INSTALL_PS1 = _GUARD_DIR / "install-global.ps1"
_CHECK = _GUARD_DIR / "check-global.sh"


def _at(local: str, domain: str) -> str:
    """Join an address at runtime, so the PII gate never sees one in source
    (test_check_no_pii.py's convention). These are agent vendors' public bot
    addresses and GitHub noreply shapes, not anyone's personal email."""
    return f"{local}@{domain}"

CLAUDE = "Co-Authored-By: Claude <" + _at("noreply", "anthropic.com") + ">"
HUMAN = "Co-authored-by: Jane Doe <jane@example.com>"


def _executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class _IsolatedGit(unittest.TestCase):
    """A temp HOME with its own global git config; nothing touches the real one."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.global_config = self.home / ".gitconfig"
        self.global_config.write_text(
            "[user]\n\tname = Test Operator\n\temail = operator@example.com\n"
            "[init]\n\tdefaultBranch = main\n",
            encoding="utf-8",
        )
        self.env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "GIT_CONFIG_GLOBAL": str(self.global_config),
            "GIT_CONFIG_NOSYSTEM": "1",
            "LANG": "C",
        }
        self.hooks_dir = self.home / ".config" / "crickets" / "git-hooks"

    def tearDown(self):
        self._tmp.cleanup()

    def run_cmd(self, args, cwd=None, check=True, timeout=60):
        # stdin=DEVNULL: pwsh -File otherwise waits on an inherited open stdin.
        result = subprocess.run(
            args, cwd=cwd or self.root, env=self.env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=timeout,
        )
        if check:
            self.assertEqual(result.returncode, 0,
                             f"{args} failed:\n{result.stdout}\n{result.stderr}")
        return result

    def git(self, *args, cwd, check=True):
        return self.run_cmd(["git", *args], cwd=cwd, check=check)

    def install(self, *extra, check=True):
        return self.run_cmd(["bash", str(_INSTALL), *extra], check=check)

    def global_hooks_path(self) -> str:
        return self.git("config", "--global", "--get", "core.hooksPath",
                        cwd=self.root, check=False).stdout.strip()

    def new_repo(self, name="repo") -> Path:
        repo = self.root / name
        self.git("init", "-q", str(repo), cwd=self.root)
        (repo / "a.txt").write_text("a\n", encoding="utf-8")
        self.git("add", "a.txt", cwd=repo)
        return repo

    def last_message(self, repo: Path) -> str:
        return self.git("log", "-1", "--format=%B", cwd=repo).stdout


@unittest.skipIf(os.name == "nt", "bash installer -- POSIX only")
class InstallGlobalTests(_IsolatedGit):
    def test_install_sets_global_hooks_path_and_check_passes(self):
        self.assertEqual(self.install("--check", check=False).returncode, 1)
        self.install()
        self.assertEqual(Path(self.global_hooks_path()), self.hooks_dir.resolve())
        for name in ("prepare-commit-msg", "pre-commit", "commit-msg", "pre-push"):
            self.assertTrue(os.access(self.hooks_dir / name, os.X_OK), name)
        self.assertFalse((self.hooks_dir / "push-to-checkout").exists())
        self.assertEqual(self.install("--check").returncode, 0)
        # Idempotent: a second run refreshes in place.
        self.install()
        self.assertEqual(self.install("--check").returncode, 0)

    def test_commit_in_a_repo_with_no_hooks_strips_the_agent_keeps_the_human(self):
        self.install()
        repo = self.new_repo()
        self.git("commit", "-q", "-m", "feat: x", "-m", f"{HUMAN}\n{CLAUDE}", cwd=repo)
        message = self.last_message(repo)
        self.assertNotIn("anthropic", message)
        self.assertIn(HUMAN, message)

    def test_no_verify_and_trailer_flag_are_still_stripped(self):
        self.install()
        repo = self.new_repo()
        self.git("commit", "-q", "--no-verify", "-m", "feat: x", "-m", CLAUDE, cwd=repo)
        self.assertNotIn("anthropic", self.last_message(repo))
        (repo / "b.txt").write_text("b\n", encoding="utf-8")
        self.git("add", "b.txt", cwd=repo)
        self.git("commit", "-q", "-m", "feat: y", "--trailer", CLAUDE, cwd=repo)
        self.assertNotIn("anthropic", self.last_message(repo))

    def test_repo_own_hooks_still_run_with_args_stdin_and_exit_codes(self):
        self.install()
        repo = self.new_repo()
        hooks = repo / ".git" / "hooks"
        ran = self.root / "ran.log"
        # pre-commit: proves a repo hook with no crickets layer is handed on.
        _executable(hooks / "pre-commit", f'#!/bin/sh\necho pre-commit >> "{ran}"\n')
        # prepare-commit-msg: the repo hook adds an agent trailer; the crickets
        # strip runs after it, so the trailer still never lands.
        _executable(hooks / "prepare-commit-msg",
                    f'#!/bin/sh\necho "prepare-commit-msg $2" >> "{ran}"\n'
                    f'printf "\\n{CLAUDE}\\n" >> "$1"\n')
        # commit-msg: a non-zero exit must still abort the commit.
        _executable(hooks / "commit-msg",
                    '#!/bin/sh\ngrep -q "^BLOCK" "$1" && exit 1\nexit 0\n')
        # pre-push: stdin must arrive intact.
        _executable(hooks / "pre-push", f'#!/bin/sh\necho "pre-push $1" >> "{ran}"\ncat >> "{ran}"\n')

        self.git("commit", "-q", "-m", "feat: x", cwd=repo)
        self.assertNotIn("anthropic", self.last_message(repo))
        log = ran.read_text(encoding="utf-8")
        self.assertIn("pre-commit", log)
        self.assertIn("prepare-commit-msg message", log)

        (repo / "b.txt").write_text("b\n", encoding="utf-8")
        self.git("add", "b.txt", cwd=repo)
        blocked = self.git("commit", "-q", "-m", "BLOCK this", cwd=repo, check=False)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertEqual(self.git("log", "-1", "--format=%s", cwd=repo).stdout.strip(), "feat: x")

        remote = self.root / "remote.git"
        self.git("init", "-q", "--bare", str(remote), cwd=self.root)
        self.git("push", "-q", str(remote), "HEAD:refs/heads/main", cwd=repo)
        head = self.git("rev-parse", "HEAD", cwd=repo).stdout.strip()
        log = ran.read_text(encoding="utf-8")
        self.assertIn(f"pre-push {remote}", log)
        self.assertRegex(log, rf"\S+ {head} refs/heads/main 0{{40}}")

    def test_linked_worktree_commits_are_stripped_and_run_repo_hooks(self):
        self.install()
        repo = self.new_repo()
        self.git("commit", "-q", "-m", "base", cwd=repo)
        ran = self.root / "ran.log"
        _executable(repo / ".git" / "hooks" / "pre-commit", f'#!/bin/sh\necho wt >> "{ran}"\n')
        wt = self.root / "wt"
        self.git("worktree", "add", "-q", "-b", "side", str(wt), cwd=repo)
        (wt / "w.txt").write_text("w\n", encoding="utf-8")
        self.git("add", "w.txt", cwd=wt)
        self.git("commit", "-q", "-m", "feat: wt", "-m", CLAUDE, cwd=wt)
        self.assertNotIn("anthropic", self.last_message(wt))
        self.assertIn("wt", ran.read_text(encoding="utf-8"))

    def test_rebase_and_cherry_pick_strip_a_trailer_made_without_hooks(self):
        self.install()
        repo = self.new_repo()
        self.git("commit", "-q", "-m", "base", cwd=repo)
        self.git("checkout", "-q", "-b", "feat", cwd=repo)
        (repo / "f.txt").write_text("f\n", encoding="utf-8")
        self.git("add", "f.txt", cwd=repo)
        # A commit made with hooks off (as a cloud session's would arrive).
        self.git("-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "feat: f", "-m", CLAUDE, cwd=repo)
        feat = self.git("rev-parse", "HEAD", cwd=repo).stdout.strip()
        self.assertIn("anthropic", self.last_message(repo))
        self.git("checkout", "-q", "main", cwd=repo)
        (repo / "m.txt").write_text("m\n", encoding="utf-8")
        self.git("add", "m.txt", cwd=repo)
        self.git("commit", "-q", "-m", "main", cwd=repo)
        self.git("cherry-pick", feat, cwd=repo)
        self.assertNotIn("anthropic", self.last_message(repo))
        self.git("reset", "-q", "--hard", "HEAD~1", cwd=repo)
        self.git("checkout", "-q", "feat", cwd=repo)
        self.git("rebase", "-q", "main", cwd=repo)
        self.assertNotIn("anthropic", self.last_message(repo))

    def test_refuses_to_replace_a_foreign_global_hooks_path(self):
        foreign = self.root / "someone-elses-hooks"
        foreign.mkdir()
        self.git("config", "--global", "core.hooksPath", str(foreign), cwd=self.root)
        result = self.install(check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.global_hooks_path(), str(foreign))
        self.assertFalse(self.hooks_dir.exists())

    def test_refuses_a_directory_it_does_not_manage(self):
        self.hooks_dir.mkdir(parents=True)
        (self.hooks_dir / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
        self.assertEqual(self.install(check=False).returncode, 2)
        self.assertEqual(self.global_hooks_path(), "")

    def test_uninstall_restores_repo_hooks_and_removes_the_directory(self):
        self.install()
        self.install("--uninstall")
        self.assertEqual(self.global_hooks_path(), "")
        self.assertFalse(self.hooks_dir.exists())
        self.assertEqual(self.install("--check", check=False).returncode, 1)

    def test_check_names_a_repo_local_override(self):
        self.install()
        repo = self.new_repo()
        self.git("config", "core.hooksPath", ".husky", cwd=repo)
        result = self.run_cmd(["bash", str(_INSTALL), "--check"], cwd=repo)
        self.assertIn("overrides the global one", result.stdout)

    def test_hook_name_lists_match_across_twins(self):
        sh = _INSTALL.read_text(encoding="utf-8")
        ps1 = _INSTALL_PS1.read_text(encoding="utf-8")
        sh_names = re.search(r"HOOK_NAMES=\((.*?)\)", sh, re.S).group(1).split()
        ps1_names = re.findall(r"'([a-z0-9-]+)'", re.search(r"\$HookNames = @\((.*?)\)", ps1, re.S).group(1))
        self.assertEqual(sh_names, ps1_names)
        self.assertIn("prepare-commit-msg", sh_names)
        self.assertNotIn("push-to-checkout", sh_names)


@unittest.skipIf(os.name == "nt", "bash check -- POSIX only")
class CheckGlobalTests(_IsolatedGit):
    def check(self) -> str:
        result = self.run_cmd(["bash", str(_CHECK)])
        return result.stdout

    def test_silent_when_never_installed(self):
        self.assertEqual(self.check(), "")

    def test_silent_when_healthy(self):
        self.install()
        self.assertEqual(self.check(), "")

    def test_warns_when_the_global_hooks_path_points_nowhere(self):
        self.git("config", "--global", "core.hooksPath", str(self.root / "gone"), cwd=self.root)
        self.assertIn("runs no hooks in any repo", self.check())

    def test_warns_when_an_install_is_damaged(self):
        self.install()
        (self.hooks_dir / "coauthor-guard.sh").unlink()
        self.assertIn("incomplete", self.check())

    def test_warns_when_the_config_was_unset_after_install(self):
        self.install()
        self.git("config", "--global", "--unset", "core.hooksPath", cwd=self.root)
        self.assertIn("global core.hooksPath is unset", self.check())


@unittest.skipUnless(shutil.which("pwsh"), "pwsh not on PATH")
class InstallGlobalPwshTests(_IsolatedGit):
    def setUp(self):
        super().setUp()
        # pwsh can take 10-20s to start under an empty HOME or with its working
        # directory in the system temp dir (0.3s otherwise), so these tests keep
        # the real HOME and run pwsh from the repo root. Git stays isolated
        # regardless: GIT_CONFIG_GLOBAL is the only global config git reads or
        # writes, and the hooks directory comes from the temp XDG_CONFIG_HOME.
        self.env["HOME"] = os.environ.get("HOME", str(self.home))

    def pwsh(self, *extra, check=True):
        return self.run_cmd(["pwsh", "-NoProfile", "-File", str(_INSTALL_PS1), *extra],
                            cwd=REPO_ROOT, check=check, timeout=120)

    def test_pwsh_install_check_and_uninstall(self):
        self.assertEqual(self.pwsh("-Check", check=False).returncode, 1)
        self.pwsh()
        self.assertEqual(Path(self.global_hooks_path()), self.hooks_dir.resolve())
        self.assertEqual(self.pwsh("-Check").returncode, 0)
        # The bash check agrees with what pwsh installed.
        self.assertEqual(self.install("--check").returncode, 0)
        repo = self.new_repo()
        self.git("commit", "-q", "-m", "feat: x", "-m", CLAUDE, cwd=repo)
        self.assertNotIn("anthropic", self.last_message(repo))
        self.pwsh("-Uninstall")
        self.assertEqual(self.global_hooks_path(), "")
        self.assertFalse(self.hooks_dir.exists())

    def test_pwsh_refuses_a_foreign_global_hooks_path(self):
        foreign = self.root / "someone-elses-hooks"
        foreign.mkdir()
        self.git("config", "--global", "core.hooksPath", str(foreign), cwd=self.root)
        self.assertEqual(self.pwsh(check=False).returncode, 2)
        self.assertEqual(self.global_hooks_path(), str(foreign))


if __name__ == "__main__":
    unittest.main()
