#!/usr/bin/env bash
# check-global — SessionStart check for the machine-wide coauthor-guard.
#
# Read-only, and silent unless something is wrong with an install the operator
# made: never sets config, never writes a file, always exits 0. Prints one
# line when
#   - the global core.hooksPath names a directory that doesn't exist (git
#     then runs no hooks at all, the repo's own included), or
#   - it names the crickets-managed directory and that install is broken, or
#   - the crickets-managed directory exists but the global core.hooksPath no
#     longer points at it.
# A machine that never ran install-global.sh hears nothing, and so does one
# whose core.hooksPath is relative (it resolves per repo).
#
# Mirrored by check-global.ps1.

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
dir="${XDG_CONFIG_HOME:-$HOME/.config}/crickets/git-hooks"
fix="bash \"$here/install-global.sh\""

# The core.hooksPath git uses outside a repo: system, global, and their includes.
current=$( (unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR; cd / && git config --includes --get core.hooksPath) 2>/dev/null || true)
current_expanded="${current/#\~/$HOME}"
# A relative core.hooksPath resolves per repo; nothing to say about it from here.
case "$current_expanded" in
    "" | /* | [A-Za-z]:* | \\\\*) ;;
    *) exit 0 ;;
esac

if [[ -n "$current" && ! -d "$current_expanded" ]]; then
    echo "[developer-safety] WARNING: global git core.hooksPath ($current) does not exist, so git runs no hooks in any repo. Re-run: $fix"
elif [[ -n "$current" && -f "$current_expanded/.crickets-managed" ]]; then
    # From /, so this is the machine-level check, not the session repo's.
    if ! (cd / && bash "$here/install-global.sh" --check --dir "$current_expanded") >/dev/null 2>&1; then
        echo "[developer-safety] WARNING: the global coauthor-guard git hooks at $current are incomplete or out of date. Re-run: $fix"
    fi
elif [[ -z "$current" && -f "$dir/.crickets-managed" ]]; then
    echo "[developer-safety] WARNING: coauthor-guard is installed at $dir but the global core.hooksPath is unset, so agent Co-Authored-By trailers are not being stripped. Re-run: $fix"
fi
exit 0
