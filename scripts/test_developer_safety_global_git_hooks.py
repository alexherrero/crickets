#!/usr/bin/env python3
"""End-to-end tests for coauthor-guard's machine-wide install
(`src/developer-safety/hooks/coauthor-guard/install-global.sh`, the
`git-hook-dispatch.sh` it fans out, and the `check-global.sh` SessionStart check).

Every test runs real git against a throwaway global config: GIT_CONFIG_GLOBAL
points at a temp file and HOME / XDG_CONFIG_HOME at a temp dir, so nothing
here can read or write the operator's own ~/.gitconfig. POSIX-only (bash);
the pwsh installer gets a smaller pass when pwsh is on PATH.

Git LFS gets two passes. LfsHookGateTests puts a fake git-lfs on PATH to pin
which repos the dispatcher runs git-lfs's hooks for, so it needs no git-lfs.
GitLfsEndToEndTests runs the real one, when it is on PATH, against a local
bare repo and proves a push uploads its objects.

stdlib only -- no pytest.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parent
_GUARD_DIR = REPO_ROOT / "src" / "developer-safety" / "hooks" / "coauthor-guard"
_INSTALL = _GUARD_DIR / "install-global.sh"
_INSTALL_PS1 = _GUARD_DIR / "install-global.ps1"
_CHECK = _GUARD_DIR / "check-global.sh"
_DISPATCH = _GUARD_DIR / "git-hook-dispatch.sh"


def _at(local: str, domain: str) -> str:
    """Join an address at runtime, so the PII gate never sees one in source
    (test_check_no_pii.py's convention). These are agent vendors' public bot
    addresses and GitHub noreply shapes, not anyone's personal email."""
    return f"{local}@{domain}"

CLAUDE = "Co-Authored-By: Claude <" + _at("noreply", "anthropic.com") + ">"
HUMAN = "Co-authored-by: Jane Doe <jane@example.com>"
# coauthor-guard before 0.6.0, as it sits hand-copied in some repos' .git/hooks:
# it strips every co-author, humans included.
LEGACY_GUARD = (
    "#!/usr/bin/env bash\n"
    "# coauthor-guard — prepare-commit-msg hook.\n"
    "set -uo pipefail\n\n"
    'msg_file="${1:-}"\n'
    '[[ -n "$msg_file" && -f "$msg_file" ]] || exit 0\n'
    'tmp_file="${msg_file}.coauthor-guard.tmp"\n'
    "awk 'tolower($0) !~ /^co-authored-by:/' \"$msg_file\" > \"$tmp_file\" && mv \"$tmp_file\" \"$msg_file\"\n"
)


def _cfg(path) -> str:
    """A path as git config text needs it: forward slashes. A Windows path's
    backslashes are escape characters there ("bad config line")."""
    return Path(path).as_posix()


def _executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _own_hooks(repo: Path) -> list[str]:
    """The hooks in a repo's own .git/hooks, git's *.sample files aside."""
    hooks = repo / ".git" / "hooks"
    if not hooks.is_dir():
        return []
    return sorted(p.name for p in hooks.iterdir() if not p.name.endswith(".sample"))


def _git_exec_path_has_lfs() -> bool:
    """git looks in its exec path before PATH, so a git-lfs there would run
    instead of the fake one LfsHookGateTests puts on PATH."""
    try:
        exec_path = subprocess.run(["git", "--exec-path"], capture_output=True, text=True,
                                   timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(exec_path) and (Path(exec_path) / "git-lfs").exists()


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
        # Inherit the real environment (Windows needs PATHEXT, SYSTEMROOT, … to
        # resolve `git` at all) but drop every GIT_* variable, which could
        # otherwise point git at another repo or inject config.
        self.env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
        self.env.update({
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "GIT_CONFIG_GLOBAL": str(self.global_config),
            "GIT_CONFIG_NOSYSTEM": "1",
            "LANG": "C",
        })
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

    def bare(self, name="remote.git") -> Path:
        remote = self.root / name
        self.git("init", "-q", "--bare", str(remote), cwd=self.root)
        return remote

    def git_without_lfs(self, *args, cwd):
        """git with a PATH that holds git and nothing else, so no git-lfs."""
        git_only = self.root / "git-only"
        if not git_only.exists():
            git_only.mkdir()
            (git_only / "git").symlink_to(shutil.which("git"))
        return subprocess.run(["git", *args], cwd=cwd, env=dict(self.env, PATH=str(git_only)),
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)

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
        for left_out in ("push-to-checkout", "reference-transaction", "post-index-change"):
            self.assertFalse((self.hooks_dir / left_out).exists(), left_out)
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

    def test_check_fails_inside_a_repo_with_its_own_hooks_path(self):
        self.install()
        repo = self.new_repo()
        self.git("config", "core.hooksPath", ".husky", cwd=repo)
        result = self.run_cmd(["bash", str(_INSTALL), "--check"], cwd=repo, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("the guard does not run here", result.stderr)
        # From outside any repo the machine-level install is still healthy.
        self.assertEqual(self.install("--check").returncode, 0)

    def _work_include(self, core_first: bool) -> Path:
        corp = self.root / "corp-hooks"
        corp.mkdir()
        work_config = self.home / "work.gitconfig"
        work_config.write_text(f"[core]\n\thooksPath = {_cfg(corp)}\n", encoding="utf-8")
        text = self.global_config.read_text(encoding="utf-8")
        include = f'[includeIf "gitdir:{_cfg(self.root)}/work/"]\n\tpath = {_cfg(work_config)}\n'
        core = "[core]\n\teditor = vi\n"
        self.global_config.write_text(core + text + include if core_first else text + include,
                                      encoding="utf-8")
        return corp

    def test_install_refuses_a_hooks_path_set_through_include_if(self):
        for core_first in (False, True):
            with self.subTest(core_first=core_first):
                self.setUp()
                corp = self._work_include(core_first)
                self.assertEqual(self.install(check=False).returncode, 2)
                work = self.root / "work" / "repo"
                work.parent.mkdir()
                self.git("init", "-q", str(work), cwd=self.root)
                self.assertEqual(self.git("config", "--get", "core.hooksPath", cwd=work).stdout.strip(),
                                 str(corp))
                self.tearDown()
        self.setUp()

    def test_check_fails_inside_a_repo_an_include_if_added_later_redirects(self):
        self.install()
        self._work_include(core_first=True)
        work = self.root / "work" / "repo"
        work.parent.mkdir()
        self.git("init", "-q", str(work), cwd=self.root)
        result = self.run_cmd(["bash", str(_INSTALL), "--check"], cwd=work, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("the guard does not run here", result.stderr)

    def test_refresh_is_allowed_when_an_include_if_names_another_hooks_path(self):
        self.install()
        (self.hooks_dir / "git-hook-dispatch.sh").unlink()  # an install from before the reference copy
        self._work_include(core_first=False)
        self.assertIn("Re-run", self.run_cmd(["bash", str(_CHECK)]).stdout)
        self.install()
        self.assertEqual(self.install("--check").returncode, 0)

    def test_install_refuses_a_nested_include_if_hooks_path(self):
        corp = self.root / "corp-hooks"
        corp.mkdir()
        work_config = self.home / "work.gitconfig"
        work_config.write_text(f"[core]\n\thooksPath = {_cfg(corp)}\n", encoding="utf-8")
        middle = self.home / "middle.gitconfig"
        middle.write_text(f'[includeIf "gitdir:{_cfg(self.root)}/work/"]\n\tpath = work.gitconfig\n', encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f'[includeIf "gitdir:{_cfg(self.root)}/work/"]\n\tpath = {_cfg(middle)}\n')
        self.assertEqual(self.install(check=False).returncode, 2)
        self.assertEqual(self.global_hooks_path(), "")

    def test_uninstall_keeps_a_directory_an_include_if_still_names(self):
        self.install()
        work_config = self.home / "work.gitconfig"
        work_config.write_text(f"[core]\n\thooksPath = {_cfg(self.hooks_dir)}\n", encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f'[includeIf "gitdir:{_cfg(self.root)}/work/"]\n\tpath = {_cfg(work_config)}\n')
        self.assertEqual(self.install("--uninstall", check=False).returncode, 2)
        self.assertTrue(self.hooks_dir.is_dir())

    def test_check_global_ignores_an_exported_git_dir(self):
        self.install()
        repo = self.new_repo()
        self.git("config", "core.hooksPath", ".husky", cwd=repo)
        env = dict(self.env, GIT_DIR=str(repo / ".git"))
        result = subprocess.run(["bash", str(_CHECK)], cwd=repo, env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.stdout, "")

    def _plain_include_inside_include_if(self, hooks_path) -> None:
        leaf = self.home / "corp-hooks.gitconfig"
        leaf.write_text(f"[core]\n\thooksPath = {_cfg(hooks_path)}\n", encoding="utf-8")
        work = self.home / "work.gitconfig"
        work.write_text("[include]\n\tpath = corp-hooks.gitconfig\n", encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f'[includeIf "gitdir:{_cfg(self.root)}/work/"]\n\tpath = {_cfg(work)}\n')

    def test_install_refuses_a_hooks_path_behind_a_plain_include_in_an_include_if_file(self):
        corp = self.root / "corp-hooks"
        corp.mkdir()
        self._plain_include_inside_include_if(corp)
        self.assertEqual(self.install(check=False).returncode, 2)
        self.assertEqual(self.global_hooks_path(), "")

    def test_uninstall_keeps_a_dir_named_behind_a_plain_include_in_an_include_if_file(self):
        self.install()
        self._plain_include_inside_include_if(self.hooks_dir)
        self.assertEqual(self.install("--uninstall", check=False).returncode, 2)
        self.assertTrue(self.hooks_dir.is_dir())

    def test_refresh_is_refused_when_a_plain_include_overrides_it_everywhere(self):
        self.install()
        corp = self.root / "corp-hooks"
        corp.mkdir()
        leaf = self.home / "corp.gitconfig"
        leaf.write_text(f"[core]\n\thooksPath = {_cfg(corp)}\n", encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f"[include]\n\tpath = {_cfg(leaf)}\n")
        self.assertEqual(self.install(check=False).returncode, 2)

    def test_an_include_cycle_is_scanned_once(self):
        loop = self.home / "loop.gitconfig"
        loop.write_text(f'[includeIf "gitdir:{_cfg(self.root)}/nowhere/"]\n\tpath = loop.gitconfig\n'
                        f'[includeIf "gitdir:{_cfg(self.root)}/elsewhere/"]\n\tpath = loop.gitconfig\n',
                        encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f'[includeIf "gitdir:{_cfg(self.root)}/work/"]\n\tpath = {_cfg(loop)}\n')
        start = time.monotonic()
        self.install()
        self.assertLess(time.monotonic() - start, 5.0)

    def test_legacy_skip_keeps_a_repo_hook_that_only_shares_the_awk_line(self):
        self.install()
        repo = self.new_repo()
        self.git("commit", "-q", "-m", "base", cwd=repo)
        _executable(repo / ".git" / "hooks" / "prepare-commit-msg",
                    "#!/bin/sh\n{ printf 'PROJ-42 '; cat \"$1\"; } > \"$1.t\" && mv \"$1.t\" \"$1\"\n"
                    "awk 'tolower($0) !~ /^co-authored-by:/' \"$1\" > \"$1.t\" && mv \"$1.t\" \"$1\"\n")
        self.git("commit", "-q", "--allow-empty", "-m", "fix", cwd=repo)
        self.assertTrue(self.last_message(repo).startswith("PROJ-42 "))

    def test_repo_hook_found_when_git_common_dir_is_exported(self):
        self.install()
        repo = self.new_repo()
        self.git("commit", "-q", "-m", "base", cwd=repo)
        _executable(repo / ".git" / "hooks" / "pre-commit", "#!/bin/sh\nexit 7\n")
        private = self.root / "private"
        private.mkdir()
        shutil.copy(repo / ".git" / "HEAD", private / "HEAD")
        env = dict(self.env, GIT_DIR=str(private), GIT_COMMON_DIR=str(repo / ".git"),
                   GIT_WORK_TREE=str(repo))
        rc = subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "x"], cwd=repo, env=env,
                            stdin=subprocess.DEVNULL, capture_output=True).returncode
        self.assertNotEqual(rc, 0, "the repo's blocking pre-commit was bypassed")

    @unittest.skipIf(os.name == "nt", "symlinked ~/.config -- POSIX only")
    def test_reinstall_after_the_directory_is_deleted_under_a_symlinked_config(self):
        real_config = self.root / "dotfiles" / "config"
        real_config.mkdir(parents=True)
        (self.home / ".config").symlink_to(real_config)
        self.install()
        shutil.rmtree(real_config / "crickets")
        self.assertIn("does not exist", self.run_cmd(["bash", str(_CHECK)]).stdout)
        self.install()
        self.assertEqual(self.install("--check").returncode, 0)

    def test_check_global_from_an_older_copy_stays_silent_after_a_newer_install(self):
        newer = self.root / "newer"
        shutil.copytree(_GUARD_DIR, newer)
        with (newer / "coauthor-guard.sh").open("a", encoding="utf-8") as fh:
            fh.write("# a newer release\n")
        self.run_cmd(["bash", str(newer / "install-global.sh")])
        self.assertEqual(self.run_cmd(["bash", str(_CHECK)]).stdout, "")

    def test_refresh_removes_hooks_an_earlier_version_installed(self):
        self.install()
        _executable(self.hooks_dir / "reference-transaction",
                    (_GUARD_DIR / "git-hook-dispatch.sh").read_text(encoding="utf-8"))
        self.install()
        self.assertFalse((self.hooks_dir / "reference-transaction").exists())

    def test_git_am_strips_the_agent_trailer(self):
        self.install()
        repo = self.new_repo()
        self.git("commit", "-q", "-m", "base", cwd=repo)
        self.git("checkout", "-q", "-b", "feat", cwd=repo)
        (repo / "f.txt").write_text("f\n", encoding="utf-8")
        self.git("add", "f.txt", cwd=repo)
        self.git("-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "feat: f", "-m", f"{HUMAN}\n{CLAUDE}", cwd=repo)
        patch = self.git("format-patch", "-1", "--stdout", cwd=repo).stdout
        (self.root / "f.patch").write_text(patch, encoding="utf-8")
        self.git("checkout", "-q", "main", cwd=repo)
        self.git("am", "-q", str(self.root / "f.patch"), cwd=repo)
        message = self.last_message(repo)
        self.assertNotIn("anthropic", message)
        self.assertIn(HUMAN, message)

    def test_spaced_separator_agent_trailer_is_stripped(self):
        # git reads `Key : value` as the same trailer as `Key: value`.
        self.install()
        repo = self.new_repo()
        self.git("commit", "-q", "-m", "feat: x", "-m", "Co-authored-by : Claude <" + _at("noreply", "anthropic.com") + ">", cwd=repo)
        trailers = self.git("log", "-1", "--format=%(trailers:key=Co-authored-by)", cwd=repo).stdout
        self.assertNotIn("anthropic", trailers)

    def test_legacy_repo_copy_does_not_strip_humans(self):
        self.install()
        repo = self.new_repo()
        _executable(repo / ".git" / "hooks" / "prepare-commit-msg", LEGACY_GUARD)
        self.git("commit", "-q", "-m", "feat: x", "-m", f"{HUMAN}\n{CLAUDE}", cwd=repo)
        message = self.last_message(repo)
        self.assertIn(HUMAN, message)
        self.assertNotIn("anthropic", message)

    def test_repo_hook_runs_when_rev_parse_lacks_path_format(self):
        # git before 2.31 echoes an unknown --path-format flag and exits 0.
        self.install()
        repo = self.new_repo()
        _executable(repo / ".git" / "hooks" / "pre-commit", "#!/bin/sh\nexit 7\n")
        shim = self.root / "oldgit"
        shim.mkdir()
        real = shutil.which("git")
        _executable(shim / "git",
                    "#!/bin/sh\nfor a; do shift; case \"$a\" in --path-format=*) "
                    "set -- \"$@\" \"--unknown-${a#--}\";; *) set -- \"$@\" \"$a\";; esac; done\n"
                    f"exec {real} \"$@\"\n")
        env = dict(self.env, PATH=f"{shim}{os.pathsep}{self.env['PATH']}")
        rc = subprocess.run([str(self.hooks_dir / "pre-commit")], cwd=repo, env=env,
                            stdin=subprocess.DEVNULL).returncode
        self.assertEqual(rc, 7, "the repo's pre-commit was silently skipped")

    def test_repo_hook_runs_from_a_subdirectory_and_with_git_dir_set(self):
        self.install()
        repo = self.new_repo()
        _executable(repo / ".git" / "hooks" / "pre-commit", "#!/bin/sh\nexit 7\n")
        (repo / "sub").mkdir()
        self.assertNotEqual(self.git("commit", "-q", "-m", "x", cwd=repo / "sub", check=False).returncode, 0)
        env = dict(self.env, GIT_DIR=str(repo / ".git"))
        rc = subprocess.run([str(self.hooks_dir / "pre-commit")], cwd=self.root, env=env,
                            stdin=subprocess.DEVNULL).returncode
        self.assertEqual(rc, 7)

    def test_install_refuses_a_hooks_path_set_through_an_include(self):
        foreign = self.root / "dotfiles-hooks"
        foreign.mkdir()
        included = self.home / "dotfiles.gitconfig"
        included.write_text(f"[core]\n\thooksPath = {_cfg(foreign)}\n", encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f"[include]\n\tpath = {_cfg(included)}\n")
        self.assertEqual(self.install(check=False).returncode, 2)
        effective = self.git("config", "--get", "core.hooksPath", cwd=self.root).stdout.strip()
        self.assertEqual(effective, str(foreign))

    def test_check_fails_when_an_include_overrides_the_install(self):
        self.install()
        foreign = self.root / "dotfiles-hooks"
        foreign.mkdir()
        included = self.home / "dotfiles.gitconfig"
        included.write_text(f"[core]\n\thooksPath = {_cfg(foreign)}\n", encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f"[include]\n\tpath = {_cfg(included)}\n")
        self.assertEqual(self.install("--check", check=False).returncode, 1)

    def test_check_reports_a_replaced_dispatcher_copy(self):
        self.install()
        _executable(self.hooks_dir / "prepare-commit-msg", "#!/bin/sh\nexit 0\n")
        self.assertEqual(self.install("--check", check=False).returncode, 1)
        self.assertIn("WARNING", self.run_cmd(["bash", str(_CHECK)]).stdout)

    def test_uninstall_keeps_a_directory_another_config_still_names(self):
        self.install()
        included = self.home / "pinned.gitconfig"
        included.write_text(f"[core]\n\thooksPath = {_cfg(self.hooks_dir)}\n", encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f"[include]\n\tpath = {_cfg(included)}\n")
        self.assertEqual(self.install("--uninstall", check=False).returncode, 2)
        self.assertTrue(self.hooks_dir.is_dir(), "deleted a directory core.hooksPath still names")

    def test_rebase_overhead_is_bounded(self):
        repo = self.new_repo()
        self.git("commit", "-q", "-m", "base", cwd=repo)
        self.git("checkout", "-q", "-b", "feat", cwd=repo)
        for i in range(25):
            (repo / f"f{i}").write_text(f"{i}\n", encoding="utf-8")
            self.git("add", f"f{i}", cwd=repo)
            self.git("-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", f"c{i}", cwd=repo)
        self.git("checkout", "-q", "main", cwd=repo)
        (repo / "m").write_text("m\n", encoding="utf-8")
        self.git("add", "m", cwd=repo)
        self.git("commit", "-q", "-m", "main", cwd=repo)
        self.git("branch", "save", "feat", cwd=repo)

        def timed() -> float:
            self.git("checkout", "-q", "-B", "feat", "save", cwd=repo)
            start = time.monotonic()
            self.git("rebase", "-q", "main", "feat", cwd=repo)
            return time.monotonic() - start

        base = timed()
        self.install()
        with_hooks = timed()
        self.assertLess(with_hooks, max(1.0, 3 * base), f"{base:.2f}s -> {with_hooks:.2f}s")

    def test_hook_name_lists_match_across_twins(self):
        sh = _INSTALL.read_text(encoding="utf-8")
        ps1 = _INSTALL_PS1.read_text(encoding="utf-8")
        sh_names = re.search(r"HOOK_NAMES=\((.*?)\)", sh, re.S).group(1).split()
        ps1_names = re.findall(r"'([a-z0-9-]+)'", re.search(r"\$HookNames = @\((.*?)\)", ps1, re.S).group(1))
        self.assertEqual(sh_names, ps1_names)
        self.assertIn("prepare-commit-msg", sh_names)
        self.assertNotIn("push-to-checkout", sh_names)


class DispatcherNoticeTests(unittest.TestCase):
    def test_the_head_git_lfs_prints_warns_against_force(self):
        # git-lfs prints the first 1024 bytes of a hook it refuses to replace,
        # right above its own advice to run `git lfs update --force`.
        head = _DISPATCH.read_bytes()[:1024].decode("utf-8", "replace")
        text = " ".join(head.replace("#", " ").split())
        self.assertIn("NEVER run `git lfs update --force` or `git lfs install --force`", text)
        self.assertIn("re-run crickets' install-global.sh", text)


@unittest.skipIf(os.name == "nt", "bash installer -- POSIX only")
@unittest.skipIf(_git_exec_path_has_lfs(), "git-lfs sits in git's exec path, ahead of the fake one")
class LfsHookGateTests(_IsolatedGit):
    """Which repos the dispatcher runs git-lfs's four hooks for. git-lfs writes
    its hooks into core.hooksPath, finds the dispatcher there and installs
    nothing, so the dispatcher stands in. A fake git-lfs on PATH records every
    call: its arguments, then its stdin."""

    def setUp(self):
        super().setUp()
        self.install()
        self.calls = self.root / "git-lfs-calls.log"
        fake = self.root / "fake-lfs"
        fake.mkdir()
        _executable(fake / "git-lfs",
                    "#!/bin/sh\n"
                    f'{{ echo "git-lfs $*"; cat; }} >> "{self.calls}"\n'
                    'exit "${FAKE_LFS_EXIT:-0}"\n')
        self.env["PATH"] = f"{fake}{os.pathsep}{self.env['PATH']}"

    def lfs_calls(self) -> str:
        return self.calls.read_text(encoding="utf-8") if self.calls.exists() else ""

    def lfs_repo(self, name="repo") -> Path:
        """A repo whose LFS store holds an object, as after a clone or a first
        `git add` of a tracked file."""
        repo = self.new_repo(name)
        (repo / ".git" / "lfs" / "objects" / "ab").mkdir(parents=True)
        return repo

    def fire_each_hook(self, repo: Path) -> Path:
        """A commit, a checkout, a merge and a push: each hook git-lfs installs, fired."""
        self.git("commit", "-q", "-m", "base", cwd=repo)
        self.git("checkout", "-q", "-b", "side", cwd=repo)
        (repo / "b.txt").write_text("b\n", encoding="utf-8")
        self.git("add", "b.txt", cwd=repo)
        self.git("commit", "-q", "-m", "side", cwd=repo)
        self.git("checkout", "-q", "main", cwd=repo)
        self.git("merge", "-q", "--no-ff", "-m", "merge side", "side", cwd=repo)
        remote = self.bare(f"{repo.name}-remote.git")
        self.git("push", "-q", str(remote), "main", cwd=repo)
        return remote

    def test_a_repo_without_lfs_never_starts_git_lfs(self):
        self.fire_each_hook(self.new_repo())
        self.assertEqual(self.lfs_calls(), "")

    def test_what_a_read_only_lfs_query_leaves_does_not_count(self):
        # `git lfs env`, `ls-files`, `fetch` and the like leave an empty store
        # and a local lfs.repositoryformatversion. git-lfs installs no hooks
        # for them, and neither state starts it here.
        repo = self.new_repo()
        (repo / ".git" / "lfs" / "objects").mkdir(parents=True)
        (repo / ".git" / "lfs" / "tmp").mkdir()
        self.git("config", "lfs.repositoryformatversion", "0", cwd=repo)
        self.fire_each_hook(repo)
        self.assertEqual(self.lfs_calls(), "")

    def test_a_repo_that_uses_lfs_gets_all_four_git_lfs_hooks(self):
        repo = self.lfs_repo()
        remote = self.fire_each_hook(repo)
        self.assertEqual(_own_hooks(repo), [])
        head = self.git("rev-parse", "HEAD", cwd=repo).stdout.strip()
        calls = self.lfs_calls()
        self.assertIn("git-lfs post-commit\n", calls)
        self.assertRegex(calls, r"git-lfs post-checkout [0-9a-f]{40} [0-9a-f]{40} 1\n")
        self.assertIn("git-lfs post-merge 0\n", calls)
        # pre-push gets git's arguments and, on stdin, the refs being pushed.
        self.assertIn(f"git-lfs pre-push {remote} {remote}\n"
                      f"refs/heads/main {head} refs/heads/main {'0' * 40}\n", calls)

    def test_a_failing_git_lfs_pre_push_stops_the_push(self):
        repo = self.lfs_repo()
        self.git("commit", "-q", "-m", "base", cwd=repo)
        remote = self.bare()
        self.env["FAKE_LFS_EXIT"] = "3"
        result = self.git("push", "-q", str(remote), "main", cwd=repo, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("for-each-ref", cwd=remote).stdout, "")

    def test_lfs_attributes_alone_count_for_pre_push_only(self):
        # A clone that stored nothing (GIT_LFS_SKIP_SMUDGE) still has LFS
        # history to answer for at push time; the per-commit hooks stay a glob.
        repo = self.new_repo()
        (repo / ".gitattributes").write_text("*.psd filter=lfs diff=lfs merge=lfs -text\n", encoding="utf-8")
        self.git("add", ".gitattributes", cwd=repo)
        self.git("commit", "-q", "-m", "base", cwd=repo)
        self.assertEqual(self.lfs_calls(), "")
        self.git("push", "-q", str(self.bare()), "main", cwd=repo)
        self.assertIn("git-lfs pre-push", self.lfs_calls())

    def push_with_own_pre_push(self, repo: Path, body: str):
        _executable(repo / ".git" / "hooks" / "pre-push", body)
        self.git("commit", "-q", "-m", "base", cwd=repo)
        return self.git("push", "-q", str(self.bare(f"{repo.name}-remote.git")), "main", cwd=repo)

    def test_a_repo_hook_of_the_same_name_keeps_the_say_and_is_warned_about(self):
        # As without crickets: git-lfs won't replace a pre-push a repo already
        # has, and that hook has to call git-lfs itself. One that never does
        # gets a warning on each push, instead of leaving the objects silently.
        repo = self.lfs_repo()
        ran = self.root / "ran.log"
        push = self.push_with_own_pre_push(repo, f'#!/bin/sh\necho own-pre-push >> "{ran}"\n')
        self.assertIn("own-pre-push", ran.read_text(encoding="utf-8"))
        self.assertIn("does not call git-lfs", push.stderr)
        calls = self.lfs_calls()
        self.assertNotIn("git-lfs pre-push", calls)
        self.assertIn("git-lfs post-commit\n", calls)

    def test_a_repo_with_git_lfs_own_hook_runs_git_lfs_once(self):
        # A repo whose .git/hooks already hold git-lfs's hooks, written by hand
        # or before the global install: handed off as any repo hook, not doubled.
        repo = self.lfs_repo()
        push = self.push_with_own_pre_push(
            repo, '#!/bin/sh\ncommand -v git-lfs >/dev/null 2>&1 || exit 2\ngit lfs pre-push "$@"\n')
        self.assertEqual(self.lfs_calls().count("git-lfs pre-push"), 1)
        self.assertNotIn("does not call git-lfs", push.stderr)

    def test_a_repo_without_lfs_and_its_own_pre_push_is_not_warned_about(self):
        ran = self.root / "ran.log"
        push = self.push_with_own_pre_push(self.new_repo(), f'#!/bin/sh\necho own-pre-push >> "{ran}"\n')
        self.assertIn("own-pre-push", ran.read_text(encoding="utf-8"))
        self.assertEqual(push.stderr, "")

    def test_lfs_storage_elsewhere_counts_for_pre_push_only(self):
        # A store kept outside the git dir leaves no lfs/objects to glob.
        # pre-push asks git config for lfs.storage, so the upload still runs;
        # the per-commit hooks stay a glob.
        for scope in ("--local", "--global"):
            with self.subTest(scope=scope):
                repo = self.new_repo(f"repo{scope}")
                self.git("config", scope, "lfs.storage", str(self.root / "shared-lfs"), cwd=repo)
                self.git("commit", "-q", "-m", "base", cwd=repo)
                self.assertEqual(self.lfs_calls(), "")
                self.git("push", "-q", str(self.bare(f"remote{scope}.git")), "main", cwd=repo)
                self.assertIn("git-lfs pre-push", self.lfs_calls())
                self.git("config", scope, "--unset", "lfs.storage", cwd=repo)
                self.calls.unlink()

    def test_a_linked_worktree_finds_lfs_in_the_common_dir(self):
        repo = self.lfs_repo()
        self.git("commit", "-q", "-m", "base", cwd=repo)
        self.calls.unlink(missing_ok=True)
        wt = self.root / "wt"
        self.git("worktree", "add", "-q", "-b", "side", str(wt), cwd=repo)
        (wt / "w.txt").write_text("w\n", encoding="utf-8")
        self.git("add", "w.txt", cwd=wt)
        self.git("commit", "-q", "-m", "wt", cwd=wt)
        self.assertIn("git-lfs post-commit\n", self.lfs_calls())

    def test_missing_git_lfs_stops_the_push_and_says_why(self):
        repo = self.lfs_repo()
        self.git("commit", "-q", "-m", "base", cwd=repo)
        plain = self.new_repo("plain")
        self.git("commit", "-q", "-m", "base", cwd=plain)
        remote = self.bare()
        blocked = self.git_without_lfs("push", "-q", str(remote), "main", cwd=repo)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("'git-lfs' was not found on your PATH", blocked.stderr)
        self.assertEqual(self.git("for-each-ref", cwd=remote).stdout, "")
        # post-checkout fails the checkout too, as git-lfs's own hook does.
        self.assertNotEqual(self.git_without_lfs("checkout", "-q", "-b", "side", cwd=repo).returncode, 0)
        # A repo without LFS never needs git-lfs.
        for args in (("checkout", "-q", "-b", "side"), ("push", "-q", str(self.bare("plain.git")), "side")):
            result = self.git_without_lfs(*args, cwd=plain)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_uninstall_says_lfs_repos_need_hooks_of_their_own(self):
        self.assertIn("git lfs install", self.install("--uninstall").stdout)


def _older_guard_copy(root: Path) -> Path:
    """This plugin's coauthor-guard directory as a release from before the
    dispatcher-version line shipped it: the line removed, nothing else."""
    older = root / "older-guard"
    shutil.copytree(_GUARD_DIR, older)
    dispatch = older / "git-hook-dispatch.sh"
    text = dispatch.read_text(encoding="utf-8")
    stripped = re.sub(r"^# dispatcher-version: \d+\n", "", text, flags=re.M)
    assert stripped != text, "git-hook-dispatch.sh has no dispatcher-version line"
    dispatch.write_text(stripped, encoding="utf-8")
    return older


def _blob(name: str) -> bytes:
    return (name.encode("utf-8") + b"\0") * 300


@unittest.skipIf(os.name == "nt", "bash installer -- POSIX only")
@unittest.skipUnless(shutil.which("git-lfs"), "git-lfs not on PATH")
class GitLfsEndToEndTests(_IsolatedGit):
    """Real git-lfs behind the dispatcher. The remote is a local bare repo:
    git-lfs's file transfer copies each object into its lfs/objects, so an
    object's file there is the proof it was uploaded."""

    def setUp(self):
        super().setUp()
        self.install()
        # The machine-level half of `git lfs install`: the clean and smudge
        # filters in the global config, and no hooks.
        self.git("lfs", "install", "--skip-repo", cwd=self.root)

    def lfs_repo(self, name: str, remote: Path, storage: Path | None = None) -> Path:
        repo = self.root / name
        self.git("init", "-q", str(repo), cwd=self.root)
        if storage is not None:
            self.git("config", "lfs.storage", str(storage), cwd=repo)
        self.git("lfs", "track", "*.bin", cwd=repo)
        self.git("add", ".gitattributes", cwd=repo)
        self.git("commit", "-q", "-m", "track *.bin", cwd=repo)
        self.git("remote", "add", "origin", str(remote), cwd=repo)
        return repo

    def commit_blob(self, repo: Path, name: str) -> str:
        """Commit an LFS-tracked file and return its object id."""
        (repo / name).write_bytes(_blob(name))
        self.git("add", name, cwd=repo)
        self.git("commit", "-q", "-m", f"add {name}", cwd=repo)
        # The commit holds a pointer; the object itself travels only by git-lfs.
        pointer = self.git("cat-file", "-p", f"HEAD:{name}", cwd=repo).stdout
        self.assertTrue(pointer.startswith("version https://git-lfs"), pointer)
        return hashlib.sha256(_blob(name)).hexdigest()

    @staticmethod
    def on_remote(remote: Path, oid: str) -> bool:
        return (remote / "lfs" / "objects" / oid[:2] / oid[2:4] / oid).is_file()

    def test_a_push_from_a_fresh_lfs_clone_uploads_its_objects(self):
        origin = self.bare("origin.git")
        seed = self.lfs_repo("seed", origin)
        first = self.commit_blob(seed, "first.bin")
        self.git("push", "-q", "origin", "main", cwd=seed)
        self.assertTrue(self.on_remote(origin, first), "a repo created here left its object behind")

        clone = self.root / "clone"
        self.git("clone", "-q", str(origin), str(clone), cwd=self.root)
        # git-lfs found the dispatcher in core.hooksPath and wrote the clone no hooks.
        self.assertEqual(_own_hooks(clone), [])
        self.assertEqual((clone / "first.bin").read_bytes(), _blob("first.bin"))

        second = self.commit_blob(clone, "second.bin")
        self.git("push", "-q", "origin", "main", cwd=clone)
        self.assertTrue(self.on_remote(origin, second), "the fresh clone left its object behind")

        # A second, empty remote gets every object the pushed history points at.
        mirror = self.bare("mirror.git")
        self.git("remote", "add", "mirror", str(mirror), cwd=clone)
        self.git("push", "-q", "mirror", "main", cwd=clone)
        self.assertTrue(self.on_remote(mirror, first))
        self.assertTrue(self.on_remote(mirror, second))

    def test_a_clone_that_stored_nothing_cannot_push_lfs_history_it_lacks(self):
        # As with git-lfs's own hook: a GIT_LFS_SKIP_SMUDGE clone holds pointers
        # only, and pushing them to a new remote would leave it without objects.
        origin = self.bare("origin.git")
        seed = self.lfs_repo("seed", origin)
        self.commit_blob(seed, "first.bin")
        self.git("push", "-q", "origin", "main", cwd=seed)
        clone = self.root / "clone"
        self.env["GIT_LFS_SKIP_SMUDGE"] = "1"
        self.git("clone", "-q", str(origin), str(clone), cwd=self.root)
        del self.env["GIT_LFS_SKIP_SMUDGE"]
        mirror = self.bare("mirror.git")
        self.git("remote", "add", "mirror", str(mirror), cwd=clone)
        push = self.git("push", "mirror", "main", cwd=clone, check=False)
        self.assertNotEqual(push.returncode, 0)
        self.assertIn("missing", push.stdout + push.stderr)
        self.assertEqual(self.git("for-each-ref", cwd=mirror).stdout, "")

    def test_a_push_that_skips_the_hook_leaves_the_object_behind(self):
        # The control for the test above: the upload is the pre-push hook's
        # doing. `git lfs push --all` backfills a remote that an earlier push
        # left without its objects.
        origin = self.bare("origin.git")
        repo = self.lfs_repo("repo", origin)
        oid = self.commit_blob(repo, "left.bin")
        self.git("push", "-q", "--no-verify", "origin", "main", cwd=repo)
        self.assertFalse(self.on_remote(origin, oid))
        self.git("lfs", "push", "--all", "origin", cwd=repo)
        self.assertTrue(self.on_remote(origin, oid))

    def test_a_push_from_a_linked_worktree_uploads(self):
        origin = self.bare("origin.git")
        repo = self.lfs_repo("repo", origin)
        wt = self.root / "wt"
        self.git("worktree", "add", "-q", "-b", "side", str(wt), cwd=repo)
        oid = self.commit_blob(wt, "wt.bin")
        self.git("push", "-q", "origin", "side", cwd=wt)
        self.assertTrue(self.on_remote(origin, oid))

    def test_lfs_storage_outside_the_git_dir_still_uploads(self):
        origin = self.bare("origin.git")
        repo = self.lfs_repo("repo", origin, storage=self.root / "shared-lfs")
        oid = self.commit_blob(repo, "moved.bin")
        self.assertFalse((repo / ".git" / "lfs").exists())
        self.git("push", "-q", "origin", "main", cwd=repo)
        self.assertTrue(self.on_remote(origin, oid))

    def test_read_only_lfs_queries_leave_a_plain_repo_alone(self):
        # Each leaves git-lfs state behind but stores no object, and stock
        # git-lfs installs no hooks for them. The repo keeps working without
        # git-lfs on PATH, as it would on a machine without crickets.
        repo = self.new_repo()
        self.git("commit", "-q", "-m", "base", cwd=repo)
        for query in (("env",), ("ls-files",), ("status",), ("fetch",), ("logs", "last")):
            self.git("lfs", *query, cwd=repo, check=False)
        self.assertTrue((repo / ".git" / "lfs").is_dir())
        self.assertEqual(self.git("config", "--local", "lfs.repositoryformatversion", cwd=repo).stdout.strip(), "0")
        for args in (("checkout", "-q", "-b", "side"), ("commit", "-q", "--allow-empty", "-m", "x"),
                     ("push", "-q", str(self.bare()), "side")):
            result = self.git_without_lfs(*args, cwd=repo)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("LFS", result.stderr)

    def test_git_lfs_install_in_a_repo_is_refused_and_prints_the_notice(self):
        repo = self.new_repo()
        result = self.git("lfs", "install", cwd=repo, check=False)
        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn("Hook already exists", output)
        # The dispatcher's own head, which git-lfs prints above its advice to force.
        self.assertIn("NEVER run `git lfs update --force`", output)
        self.assertEqual(_own_hooks(repo), [])
        self.assertEqual(self.install("--check").returncode, 0)

    def test_a_forced_lfs_install_is_caught_and_a_reinstall_repairs_it(self):
        repo = self.new_repo()
        ran = self.root / "ran.log"
        _executable(repo / ".git" / "hooks" / "pre-push", f'#!/bin/sh\necho own-pre-push >> "{ran}"\n')
        self.git("commit", "-q", "-m", "base", cwd=repo)
        for forced in (("lfs", "update", "--force"), ("lfs", "install", "--force")):
            with self.subTest(command=" ".join(forced)):
                # The trap: git-lfs writes its hooks over four dispatcher copies, for every repo.
                self.git(*forced, cwd=repo)
                self.assertIn("git lfs pre-push", (self.hooks_dir / "pre-push").read_text(encoding="utf-8"))
                self.assertEqual(self.install("--check", check=False).returncode, 1)
                self.assertIn("WARNING", self.run_cmd(["bash", str(_CHECK)]).stdout)
                # The remedy the dispatcher's notice names.
                self.install()
                self.assertEqual(self.install("--check").returncode, 0)
        self.git("push", "-q", str(self.bare()), "HEAD:refs/heads/main", cwd=repo)
        self.assertIn("own-pre-push", ran.read_text(encoding="utf-8"))


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

    def test_silent_for_a_relative_hooks_path(self):
        # A relative core.hooksPath resolves per repo, and it works.
        self.git("config", "--global", "core.hooksPath", ".githooks", cwd=self.root)
        self.assertEqual(self.check(), "")

    def test_warns_when_the_config_was_unset_after_install(self):
        self.install()
        self.git("config", "--global", "--unset", "core.hooksPath", cwd=self.root)
        self.assertIn("global core.hooksPath is unset", self.check())

    def test_warns_when_the_install_is_older_than_this_plugin(self):
        # A plugin update changes nothing in the install, which is a copy. Say
        # so, or a dispatcher fix never reaches the machine.
        self.run_cmd(["bash", str(_older_guard_copy(self.root) / "install-global.sh")])
        self.assertEqual(self.install("--check").returncode, 0)  # intact, only older
        self.assertIn("older than this plugin's", self.check())

    def test_an_older_plugin_copy_stays_silent_about_a_newer_install(self):
        older = _older_guard_copy(self.root)
        self.install()
        self.assertEqual(self.run_cmd(["bash", str(older / "check-global.sh")]).stdout, "")


@unittest.skipUnless(shutil.which("pwsh"), "pwsh not on PATH")
class InstallGlobalPwshTests(_IsolatedGit):
    # Where pwsh() runs the installer: the filesystem root, which is where the
    # installer itself runs git to stay outside any repo, and where
    # check-global.ps1 runs its -Check. Not the checkout: inside a repo -Check
    # also reads that repo's core.hooksPath, and a checkout can set its own (the
    # Claude desktop app writes one into every worktree it creates), which
    # fails a check that is healthy machine-wide.
    pwsh_cwd = REPO_ROOT.anchor

    def setUp(self):
        super().setUp()
        # pwsh is slow to start when its HOME or its working directory is inside
        # a system temp dir that holds very many entries: 18-45s with 1.8 million
        # of them, 0.3s otherwise. So these tests keep the real HOME, and start
        # pwsh outside the temp dir unless they need a repo of their own. Git
        # stays isolated regardless: GIT_CONFIG_GLOBAL is the only global config
        # git reads or writes, and the hooks directory comes from the temp
        # XDG_CONFIG_HOME.
        self.env["HOME"] = os.environ.get("HOME", str(self.home))

    def pwsh(self, *extra, check=True):
        return self.run_cmd(["pwsh", "-NoProfile", "-File", str(_INSTALL_PS1), *extra],
                            cwd=self.pwsh_cwd, check=check, timeout=120)

    def test_pwsh_helper_runs_outside_any_repo(self):
        # From inside a checkout these tests pass in CI and fail wherever the
        # checkout sets a core.hooksPath, so CI has to catch a move back there.
        result = self.git("rev-parse", "--git-dir", cwd=self.pwsh_cwd, check=False)
        self.assertNotEqual(result.returncode, 0,
                            f"{self.pwsh_cwd} is inside a git repo ({result.stdout.strip()})")

    def test_pwsh_install_check_and_uninstall(self):
        self.assertEqual(self.pwsh("-Check", check=False).returncode, 1)
        self.pwsh()
        self.assertEqual(Path(self.global_hooks_path()), self.hooks_dir.resolve())
        self.assertEqual(self.pwsh("-Check").returncode, 0)
        # The bash check agrees with what pwsh installed (POSIX only: on Windows
        # `bash` on PATH can be WSL's rather than Git for Windows').
        if os.name != "nt":
            self.assertEqual(self.install("--check").returncode, 0)
        repo = self.new_repo()
        self.git("commit", "-q", "-m", "feat: x", "-m", CLAUDE, cwd=repo)
        self.assertNotIn("anthropic", self.last_message(repo))
        self.pwsh("-Uninstall")
        self.assertEqual(self.global_hooks_path(), "")
        self.assertFalse(self.hooks_dir.exists())

    @unittest.skipIf(os.name == "nt", "symlinked ~/.config -- POSIX only")
    def test_pwsh_uninstall_never_leaves_hooks_path_at_a_deleted_dir(self):
        # ~/.config is a symlink; bash records the resolved path, pwsh must match it.
        real_config = self.root / "dotfiles" / "config"
        real_config.mkdir(parents=True)
        (self.home / ".config").symlink_to(real_config)
        self.install()
        self.pwsh("-Uninstall")
        hooks_path = self.global_hooks_path()
        self.assertTrue(hooks_path == "" or Path(hooks_path).is_dir(),
                        f"core.hooksPath={hooks_path} names a deleted directory")
        self.assertEqual(hooks_path, "")

    def test_pwsh_refuses_a_hooks_path_set_through_include_if(self):
        corp = self.root / "corp-hooks"
        corp.mkdir()
        work_config = self.home / "work.gitconfig"
        work_config.write_text(f"[core]\n\thooksPath = {_cfg(corp)}\n", encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f'[includeIf "gitdir:{_cfg(self.root)}/work/"]\n\tpath = {_cfg(work_config)}\n')
        result = self.pwsh(check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("not replacing it", result.stderr)
        self.assertFalse(self.hooks_dir.exists())
        self.assertEqual(self.global_hooks_path(), "")

    def test_pwsh_refuses_a_hooks_path_behind_a_plain_include_in_an_include_if_file(self):
        corp = self.root / "corp-hooks"
        corp.mkdir()
        leaf = self.home / "corp-hooks.gitconfig"
        leaf.write_text(f"[core]\n\thooksPath = {_cfg(corp)}\n", encoding="utf-8")
        work = self.home / "work.gitconfig"
        work.write_text("[include]\n\tpath = corp-hooks.gitconfig\n", encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f'[includeIf "gitdir:{_cfg(self.root)}/work/"]\n\tpath = {_cfg(work)}\n')
        self.assertEqual(self.pwsh(check=False).returncode, 2)
        self.assertEqual(self.global_hooks_path(), "")

    def test_pwsh_installs_beside_an_unrelated_include_if(self):
        identity = self.home / "id.gitconfig"
        identity.write_text("[user]\n\temail = w@example.com\n", encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f'[includeIf "gitdir:{_cfg(self.root)}/work/"]\n\tpath = {_cfg(identity)}\n')
        self.pwsh()
        self.assertEqual(self.pwsh("-Check").returncode, 0)

    def test_pwsh_check_fails_inside_a_repo_with_its_own_hooks_path(self):
        self.pwsh()
        repo = self.new_repo()
        self.git("config", "core.hooksPath", ".husky", cwd=repo)
        result = self.run_cmd(["pwsh", "-NoProfile", "-File", str(_INSTALL_PS1), "-Check"],
                              cwd=repo, check=False, timeout=120)
        self.assertEqual(result.returncode, 1)
        self.assertIn("the guard does not run here", result.stderr)

    @unittest.skipIf(os.name == "nt", "bash installer -- POSIX only")
    def test_pwsh_check_global_warns_about_an_older_install(self):
        self.run_cmd(["bash", str(_older_guard_copy(self.root) / "install-global.sh")])
        check = ["pwsh", "-NoProfile", "-File", str(_GUARD_DIR / "check-global.ps1")]
        self.assertIn("older than this plugin's", self.run_cmd(check, cwd=REPO_ROOT, timeout=120).stdout)
        self.install()
        self.assertEqual(self.run_cmd(check, cwd=REPO_ROOT, timeout=120).stdout, "")

    def test_pwsh_refuses_a_foreign_global_hooks_path(self):
        foreign = self.root / "someone-elses-hooks"
        foreign.mkdir()
        self.git("config", "--global", "core.hooksPath", str(foreign), cwd=self.root)
        self.assertEqual(self.pwsh(check=False).returncode, 2)
        self.assertEqual(self.global_hooks_path(), str(foreign))


if __name__ == "__main__":
    unittest.main()
