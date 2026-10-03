#!/bin/sh
# git-hook-dispatch — the crickets global git-hook dispatcher.
#
# Did git-lfs print this file under "Hook already exists"? Git LFS already
# works here. For a repo that uses LFS this
# dispatcher runs the git-lfs hooks itself, unless the repo has its own hook
# of that name in .git/hooks, which then has to call git-lfs. Change nothing
# in this directory, and NEVER run `git lfs update --force` or `git lfs
# install --force`: they overwrite this dispatcher, and every repo on this
# machine then loses its own pre-push, post-checkout, post-commit and
# post-merge hooks. If that already happened, re-run crickets'
# install-global.sh to put the dispatcher back.
#
# (That notice stays in the first 1024 bytes of this file: git-lfs prints that
# much of an existing hook when it refuses to replace it.)
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
# Git LFS is the one tool this dispatcher stands in for. git-lfs installs its
# hooks into whatever directory core.hooksPath names, finds this dispatcher
# there and writes nothing, so a repo cloned or created on this machine would
# push its pointer files and leave the objects behind. For the four hooks
# git-lfs installs (pre-push, post-checkout, post-commit, post-merge), a repo
# that uses LFS and has no hook of its own under that name gets git-lfs's own
# hook from here: `git lfs <hook> "$@"`. A repo's own hook keeps the say, as
# it would without crickets, where git-lfs refuses to replace it too; a
# pre-push that never mentions git-lfs gets a warning on each push instead.
#
# Cost matters: git runs this on every commit in every repo. The repo's hooks
# directory is found with shell builtins, not a `git` call, and bash starts
# only when the message has a co-author line at all. A repo counts as using
# LFS when its LFS store holds an object (an entry under lfs/objects/ in its
# git directory). git-lfs writes one only when it stores or downloads a file,
# never for a read-only query such as `git lfs env` or `git lfs ls-files`.
# That is a glob, not a process, so a repo without LFS never starts git-lfs
# (about 50ms a call). pre-push alone also reads the root .gitattributes for
# filter=lfs, so a clone that stored nothing cannot push LFS history it
# lacks, and asks `git config` for lfs.storage, a process per push rather
# than per commit, so a repo that keeps its store elsewhere still uploads.
# install-global.sh leaves out the hooks git fires per ref or index update
# (reference-transaction, post-index-change), which would otherwise run a
# shell hundreds of times in one rebase or fetch.
#
# A repo that sets its own local core.hooksPath (husky does this) overrides
# the global one, and this dispatcher never runs there.
#
# POSIX sh on purpose: Git for Windows runs hooks through its bundled sh, so
# the same file works on macOS, Linux and Windows.
#
# Bump the number below with any change to what this file does: check-global
# warns when the installed copy's number is lower than its own plugin's.
# dispatcher-version: 2

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

# Whether the repo uses Git LFS (see the header): its store holds an object.
# pre-push also counts a root .gitattributes that routes files through LFS
# (a clone that stored nothing yet must not push LFS history it lacks) and
# an lfs.storage that keeps the store somewhere else.
uses_lfs() {
    if [ -n "$common_dir" ]; then
        for lfs_entry in "$common_dir"/lfs/objects/*; do
            [ -e "$lfs_entry" ] && return 0
        done
    fi
    [ "$hook_name" = pre-push ] || return 1
    # git runs a hook from the root of the working tree.
    if [ -f .gitattributes ]; then
        while IFS= read -r attr_line || [ -n "$attr_line" ]; do
            case $attr_line in *filter=lfs*) return 0 ;; esac
        done < .gitattributes
    fi
    git config --get lfs.storage </dev/null >/dev/null 2>&1
}

case $hook_name in
    prepare-commit-msg | applypatch-msg) ;;
    pre-push | post-checkout | post-commit | post-merge)
        if [ -n "$repo_hook" ]; then
            # The repo's own pre-push decides whether LFS objects go up. Say so
            # when it never mentions git-lfs, rather than leave them silently.
            if [ "$hook_name" = pre-push ] && uses_lfs &&
                    ! grep -q -e 'git lfs' -e 'git-lfs' "$repo_hook" 2>/dev/null; then
                printf >&2 '%s\n' "warning: this repository uses Git LFS, but its own pre-push hook ($repo_hook) does not call git-lfs, so this push may leave LFS objects behind. Add: git lfs pre-push \"\$@\""
            fi
            exec "$repo_hook" "$@"
        fi
        uses_lfs || exit 0
        command -v git-lfs >/dev/null 2>&1 || {
            printf >&2 '\n%s\n\n' "This repository uses Git LFS but 'git-lfs' was not found on your PATH, so its $hook_name hook cannot run. Install git-lfs or put it on PATH."
            exit 2
        }
        exec git lfs "$hook_name" "$@"
        ;;
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
