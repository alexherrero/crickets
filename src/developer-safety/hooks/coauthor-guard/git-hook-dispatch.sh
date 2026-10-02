#!/bin/sh
# git-hook-dispatch — the crickets global git-hook dispatcher.
#
# install-global.sh copies this file into the global hooks directory once per
# git hook name and points `git config --global core.hooksPath` at it. Once a
# global core.hooksPath is set, git stops looking in a repo's own .git/hooks,
# so every copy hands off to the repo's own hook of the same name (args and
# stdin intact, exit code propagated). The crickets layer is one hook:
# prepare-commit-msg runs the repo's own hook first, then coauthor-guard.sh,
# so no agent Co-Authored-By trailer survives whatever the repo hook wrote.
#
# A repo that sets its own local core.hooksPath (husky does this) overrides
# the global one, and this dispatcher never runs there.
#
# POSIX sh on purpose: Git for Windows runs hooks through its bundled sh, so
# the same file works on macOS, Linux and Windows.

hook_name=${0##*/}
self_dir=$(cd "$(dirname "$0")" && pwd -P)

# The repo's own hook lives in the common git dir, which linked worktrees share.
repo_hook=
common_dir=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) \
    || common_dir=$(git rev-parse --git-common-dir 2>/dev/null) \
    || common_dir=
if [ -n "$common_dir" ] && [ -d "$common_dir/hooks" ]; then
    repo_hooks_dir=$(cd "$common_dir/hooks" && pwd -P)
    # Never re-enter this dispatcher if the repo's hooks dir is this directory.
    if [ "$repo_hooks_dir" != "$self_dir" ] && [ -x "$repo_hooks_dir/$hook_name" ]; then
        repo_hook=$repo_hooks_dir/$hook_name
    fi
fi

if [ "$hook_name" != "prepare-commit-msg" ]; then
    [ -n "$repo_hook" ] && exec "$repo_hook" "$@"
    exit 0
fi

if [ -n "$repo_hook" ]; then
    "$repo_hook" "$@" || exit $?
fi
if [ -f "$self_dir/coauthor-guard.sh" ]; then
    bash "$self_dir/coauthor-guard.sh" "$@"
fi
exit 0
