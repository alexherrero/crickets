#!/usr/bin/env bash
# install-global — install coauthor-guard for every repo on this machine.
#
#   bash install-global.sh               install (or refresh) and set the global core.hooksPath
#   bash install-global.sh --check       exit 0 if installed and healthy, 1 if not (read-only)
#   bash install-global.sh --uninstall   unset the global core.hooksPath and remove the directory
#   --dir <path>                         hooks directory (default:
#                                        ${XDG_CONFIG_HOME:-$HOME/.config}/crickets/git-hooks)
#
# Writes git-hook-dispatch.sh into the directory once per git hook name, plus
# coauthor-guard.sh and a .crickets-managed marker, then sets
# `git config --global core.hooksPath` to it. The dispatcher hands every hook
# on to the repo's own .git/hooks/<name>, so repo hooks keep running. Refuses
# to replace a global core.hooksPath it didn't set. Idempotent: re-running
# refreshes the files in place. The directory is a copy, not a pointer into
# the plugin cache, so `claude plugin update` can't leave git pointing at a
# deleted path.
#
# Mirrored by install-global.ps1 (same files, same config, same exit codes).

set -uo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
mode=install
dir="${XDG_CONFIG_HOME:-$HOME/.config}/crickets/git-hooks"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --check) mode=check ;;
        --uninstall) mode=uninstall ;;
        --dir) shift; dir="${1:?--dir needs a path}" ;;
        *) echo "install-global: unknown argument: $1" >&2; exit 2 ;;
    esac
    shift
done

# Every hook name git looks up in core.hooksPath (githooks(5)), so no repo hook
# goes dark. Left out: push-to-checkout (its mere presence replaces git's
# built-in updateInstead behavior) and fsmonitor-watchman (configured through
# core.fsmonitor, not looked up here).
HOOK_NAMES=(
    applypatch-msg pre-applypatch post-applypatch
    pre-commit pre-merge-commit prepare-commit-msg commit-msg post-commit
    pre-rebase post-checkout post-merge pre-push post-rewrite
    pre-receive update proc-receive post-receive post-update
    reference-transaction pre-auto-gc sendemail-validate post-index-change
    p4-changelist p4-prepare-changelist p4-post-changelist p4-pre-submit
)
MARKER=.crickets-managed

current=$(git config --global --get core.hooksPath 2>/dev/null || true)

# Compare paths by their resolved form, so ~ and symlinks don't cause a mismatch.
resolve() {
    local p="${1/#\~/$HOME}"
    if [[ -d "$p" ]]; then (cd "$p" && pwd -P); else printf '%s\n' "$p"; fi
}
points_here() {
    [[ -n "$current" && "$(resolve "$current")" == "$(resolve "$dir")" ]]
}

check() {
    local problem=""
    if [[ -z "$current" ]]; then
        problem="global core.hooksPath is not set"
    elif ! points_here; then
        problem="global core.hooksPath is $current, not $dir"
    elif [[ ! -f "$dir/$MARKER" ]]; then
        problem="$dir is missing or not crickets-managed"
    elif [[ ! -f "$dir/coauthor-guard.sh" ]]; then
        problem="$dir/coauthor-guard.sh is missing"
    else
        local name
        for name in "${HOOK_NAMES[@]}"; do
            if [[ ! -x "$dir/$name" ]]; then
                problem="$dir/$name is missing or not executable"
                break
            fi
        done
    fi
    if [[ -n "$problem" ]]; then
        echo "coauthor-guard: global git hooks NOT healthy — $problem" >&2
        return 1
    fi
    echo "coauthor-guard: global git hooks installed at $dir"
    # A repo-local core.hooksPath overrides the global one; name it if we're in one.
    local local_path
    local_path=$(git config --local --get core.hooksPath 2>/dev/null || true)
    if [[ -n "$local_path" ]]; then
        echo "coauthor-guard: note — this repo sets its own core.hooksPath ($local_path), which overrides the global one here"
    fi
    return 0
}

case "$mode" in
    check)
        check
        exit $?
        ;;
    uninstall)
        if points_here; then
            git config --global --unset core.hooksPath
            echo "coauthor-guard: unset global core.hooksPath ($current)"
        elif [[ -n "$current" ]]; then
            echo "coauthor-guard: global core.hooksPath is $current, not $dir — left as is"
        fi
        if [[ -f "$dir/$MARKER" ]]; then
            rm -rf "$dir"
            echo "coauthor-guard: removed $dir"
        fi
        exit 0
        ;;
esac

# install
if [[ -n "$current" ]] && ! points_here; then
    echo "install-global: global core.hooksPath is already $current — not replacing it." >&2
    echo "  Unset it (git config --global --unset core.hooksPath) or pass --dir $current" >&2
    echo "  only if that directory is meant to become crickets-managed." >&2
    exit 2
fi
if [[ -d "$dir" && ! -f "$dir/$MARKER" ]] && [[ -n "$(ls -A "$dir" 2>/dev/null)" ]]; then
    echo "install-global: $dir already holds files crickets didn't put there — not touching it." >&2
    exit 2
fi
for src in "$here/git-hook-dispatch.sh" "$here/coauthor-guard.sh"; do
    if [[ ! -f "$src" ]]; then
        echo "install-global: $src not found next to this script" >&2
        exit 2
    fi
done

mkdir -p "$dir" || exit 2
for name in "${HOOK_NAMES[@]}"; do
    cp "$here/git-hook-dispatch.sh" "$dir/$name" && chmod +x "$dir/$name" || exit 2
done
cp "$here/coauthor-guard.sh" "$dir/coauthor-guard.sh" && chmod +x "$dir/coauthor-guard.sh" || exit 2
printf 'Managed by crickets developer-safety (coauthor-guard/install-global).\nInstalled from %s\n' \
    "$here" > "$dir/$MARKER"

abs_dir=$(cd "$dir" && pwd -P)
git config --global core.hooksPath "$abs_dir" || exit 2
current=$abs_dir
echo "coauthor-guard: installed ${#HOOK_NAMES[@]} hooks in $abs_dir and set global core.hooksPath"
