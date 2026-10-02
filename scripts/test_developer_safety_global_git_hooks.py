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
import time
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
        work_config.write_text(f"[core]\n\thooksPath = {corp}\n", encoding="utf-8")
        text = self.global_config.read_text(encoding="utf-8")
        include = f'[includeIf "gitdir:{self.root}/work/"]\n\tpath = {work_config}\n'
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
        work_config.write_text(f"[core]\n\thooksPath = {corp}\n", encoding="utf-8")
        middle = self.home / "middle.gitconfig"
        middle.write_text(f'[includeIf "gitdir:{self.root}/work/"]\n\tpath = work.gitconfig\n', encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f'[includeIf "gitdir:{self.root}/work/"]\n\tpath = {middle}\n')
        self.assertEqual(self.install(check=False).returncode, 2)
        self.assertEqual(self.global_hooks_path(), "")

    def test_uninstall_keeps_a_directory_an_include_if_still_names(self):
        self.install()
        work_config = self.home / "work.gitconfig"
        work_config.write_text(f"[core]\n\thooksPath = {self.hooks_dir}\n", encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f'[includeIf "gitdir:{self.root}/work/"]\n\tpath = {work_config}\n')
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
        leaf.write_text(f"[core]\n\thooksPath = {hooks_path}\n", encoding="utf-8")
        work = self.home / "work.gitconfig"
        work.write_text("[include]\n\tpath = corp-hooks.gitconfig\n", encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f'[includeIf "gitdir:{self.root}/work/"]\n\tpath = {work}\n')

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
        leaf.write_text(f"[core]\n\thooksPath = {corp}\n", encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f"[include]\n\tpath = {leaf}\n")
        self.assertEqual(self.install(check=False).returncode, 2)

    def test_an_include_cycle_is_scanned_once(self):
        loop = self.home / "loop.gitconfig"
        loop.write_text(f'[includeIf "gitdir:{self.root}/nowhere/"]\n\tpath = loop.gitconfig\n'
                        f'[includeIf "gitdir:{self.root}/elsewhere/"]\n\tpath = loop.gitconfig\n',
                        encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f'[includeIf "gitdir:{self.root}/work/"]\n\tpath = {loop}\n')
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
        included.write_text(f"[core]\n\thooksPath = {foreign}\n", encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f"[include]\n\tpath = {included}\n")
        self.assertEqual(self.install(check=False).returncode, 2)
        effective = self.git("config", "--get", "core.hooksPath", cwd=self.root).stdout.strip()
        self.assertEqual(effective, str(foreign))

    def test_check_fails_when_an_include_overrides_the_install(self):
        self.install()
        foreign = self.root / "dotfiles-hooks"
        foreign.mkdir()
        included = self.home / "dotfiles.gitconfig"
        included.write_text(f"[core]\n\thooksPath = {foreign}\n", encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f"[include]\n\tpath = {included}\n")
        self.assertEqual(self.install("--check", check=False).returncode, 1)

    def test_check_reports_a_replaced_dispatcher_copy(self):
        self.install()
        _executable(self.hooks_dir / "prepare-commit-msg", "#!/bin/sh\nexit 0\n")
        self.assertEqual(self.install("--check", check=False).returncode, 1)
        self.assertIn("WARNING", self.run_cmd(["bash", str(_CHECK)]).stdout)

    def test_uninstall_keeps_a_directory_another_config_still_names(self):
        self.install()
        included = self.home / "pinned.gitconfig"
        included.write_text(f"[core]\n\thooksPath = {self.hooks_dir}\n", encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f"[include]\n\tpath = {included}\n")
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
        work_config.write_text(f"[core]\n\thooksPath = {corp}\n", encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f'[includeIf "gitdir:{self.root}/work/"]\n\tpath = {work_config}\n')
        result = self.pwsh(check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("not replacing it", result.stderr)
        self.assertFalse(self.hooks_dir.exists())
        self.assertEqual(self.global_hooks_path(), "")

    def test_pwsh_refuses_a_hooks_path_behind_a_plain_include_in_an_include_if_file(self):
        corp = self.root / "corp-hooks"
        corp.mkdir()
        leaf = self.home / "corp-hooks.gitconfig"
        leaf.write_text(f"[core]\n\thooksPath = {corp}\n", encoding="utf-8")
        work = self.home / "work.gitconfig"
        work.write_text("[include]\n\tpath = corp-hooks.gitconfig\n", encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f'[includeIf "gitdir:{self.root}/work/"]\n\tpath = {work}\n')
        self.assertEqual(self.pwsh(check=False).returncode, 2)
        self.assertEqual(self.global_hooks_path(), "")

    def test_pwsh_installs_beside_an_unrelated_include_if(self):
        identity = self.home / "id.gitconfig"
        identity.write_text("[user]\n\temail = w@example.com\n", encoding="utf-8")
        with self.global_config.open("a", encoding="utf-8") as fh:
            fh.write(f'[includeIf "gitdir:{self.root}/work/"]\n\tpath = {identity}\n')
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

    def test_pwsh_refuses_a_foreign_global_hooks_path(self):
        foreign = self.root / "someone-elses-hooks"
        foreign.mkdir()
        self.git("config", "--global", "core.hooksPath", str(foreign), cwd=self.root)
        self.assertEqual(self.pwsh(check=False).returncode, 2)
        self.assertEqual(self.global_hooks_path(), str(foreign))


if __name__ == "__main__":
    unittest.main()
