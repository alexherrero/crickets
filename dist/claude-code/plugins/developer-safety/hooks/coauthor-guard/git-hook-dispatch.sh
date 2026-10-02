#!/bin/sh
# git-hook-dispatch — the crickets global git-hook dispatcher.
#
# install-global.sh copies this file into the global hooks directory once per
# git hook name and points `git config --global core.hooksPath` at it. Once a
# global core.hooksPath is set, git stops looking in a repo's own .git/hooks,
# so every copy hands off to the repo's own hook of the same name (args and
# stdin intact, exit code propagated). The crickets layer is the two hooks
# that may edit a commit message: prepare-commit-msg (commit, merge,
# cherry-pick, rebase) and applypatch-msg (git am). Each runs the repo's own
# hook first, then coauthor-guard.sh, so no agent Co-Authored-By trailer
# survives whatever the repo hook wrote.
#
# Cost matters: git runs this on every commit in every repo. The repo's hooks
# directory is found with shell builtins, not a `git` call, and bash starts
# only when the message has a co-author line at all. install-global.sh leaves
# out the hooks git fires per ref or index update (reference-transaction,
# post-index-change), which would otherwise run a shell hundreds of times in
# one rebase or fetch.
#
# A repo that sets its own local core.hooksPath (husky does this) overrides
# the global one, and this dispatcher never runs there.
#
# POSIX sh on purpose: Git for Windows runs hooks through its bundled sh, so
# the same file works on macOS, Linux and Windows.

hook_name=${0##*/}
case $0 in
    */*) self_path=${0%/*} ;;
    *) self_path=. ;;
esac

# The repo's hooks live in the common git dir, which linked worktrees share.
# git runs a hook from the worktree root (from $GIT_DIR in a bare repo) and
# usually exports GIT_DIR, so builtins find it; anything else asks git.
git_dir=${GIT_DIR:-}
if [ -z "$git_dir" ]; then
    if [ -d .git ]; then
        git_dir=.git
    elif [ -f .git ]; then
        IFS= read -r gitfile_line < .git
        git_dir=${gitfile_line#gitdir: }
    fi
fi
common_dir=
if [ -n "${GIT_COMMON_DIR:-}" ] && [ -d "$GIT_COMMON_DIR" ]; then
    # Git uses an exported GIT_COMMON_DIR over anything GIT_DIR implies.
    common_dir=$GIT_COMMON_DIR
elif [ -n "$git_dir" ] && [ -d "$git_dir" ]; then
    common_dir=$git_dir
    if [ -f "$git_dir/commondir" ]; then
        IFS= read -r common_rel < "$git_dir/commondir"
        case $common_rel in
            /* | [A-Za-z]:*) common_dir=$common_rel ;;
            *) common_dir=$git_dir/$common_rel ;;
        esac
    fi
else
    # No --path-format here: git before 2.31 echoes an unknown flag and exits 0.
    common_dir=$(git rev-parse --git-common-dir 2>/dev/null) || common_dir=
    case $common_dir in *"
"*) common_dir= ;; esac
fi

repo_hook=
if [ -n "$common_dir" ] && [ -x "$common_dir/hooks/$hook_name" ] && [ ! -d "$common_dir/hooks/$hook_name" ]; then
    # Never re-enter this dispatcher if the repo's hooks dir is this directory.
    if [ "$(cd "$common_dir/hooks" && pwd -P)" != "$(cd "$self_path" && pwd -P)" ]; then
        repo_hook=$common_dir/hooks/$hook_name
    fi
fi

case $hook_name in
    prepare-commit-msg | applypatch-msg) ;;
    *)
        [ -n "$repo_hook" ] && exec "$repo_hook" "$@"
        exit 0
        ;;
esac

# A pre-0.6.0 coauthor-guard copy in .git/hooks strips every co-author, humans
# too. The strip below supersedes it, so an exact copy (its code lines, comments
# aside) is skipped; a hook that merely contains the same awk line still runs.
LEGACY_GUARD_CODE='set -uo pipefail
msg_file="${1:-}"
[[ -n "$msg_file" && -f "$msg_file" ]] || exit 0
tmp_file="${msg_file}.coauthor-guard.tmp"
awk '"'"'tolower($0) !~ /^co-authored-by:/'"'"' "$msg_file" > "$tmp_file" && mv "$tmp_file" "$msg_file"'
is_legacy_guard() {
    [ "$(grep -v -e '^[[:space:]]*#' -e '^[[:space:]]*$' "$1" 2>/dev/null)" = "$LEGACY_GUARD_CODE" ]
}

if [ -n "$repo_hook" ] && ! is_legacy_guard "$repo_hook"; then
    "$repo_hook" "$@" || exit $?
fi

msg_file=${1:-}
[ -n "$msg_file" ] && [ -f "$msg_file" ] || exit 0
has_coauthor=
while IFS= read -r line || [ -n "$line" ]; do
    case $line in
        [Cc][Oo]-[Aa][Uu][Tt][Hh][Oo][Rr][Ee][Dd]-[Bb][Yy]*) has_coauthor=1; break ;;
    esac
done < "$msg_file"
if [ -n "$has_coauthor" ] && [ -f "$self_path/coauthor-guard.sh" ]; then
    bash "$self_path/coauthor-guard.sh" "$msg_file"
fi
exit 0
