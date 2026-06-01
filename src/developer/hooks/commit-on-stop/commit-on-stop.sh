#!/usr/bin/env bash
# commit-on-stop — non-disruptive safety snapshot at Stop.
#
# Fires on Claude Code's Stop event. If the working tree has uncommitted changes
# (tracked, staged, or untracked), records a full snapshot as a commit object on
# the side ref refs/auto-save/<iso-timestamp> — WITHOUT switching branches,
# moving HEAD, or touching the working tree or index. The agent's working tree
# is left exactly as it was; the snapshot is recoverable later.
#
# This replaces the older stash+branch+checkout design, which parked changes off
# the current branch every turn (surprising for multi-turn work) and switched
# branches (unsafe when agents share a working tree). The snapshot model is
# concurrency-safe: independent Stop events just write independent refs, and the
# working tree is never mutated — so multiple agents (even in one tree) don't
# collide, and an agent's in-flight edits survive across turns.
#
# Recovery (restore a snapshot's files into your working tree):
#   git checkout refs/auto-save/<timestamp> -- .
# List snapshots:
#   git for-each-ref --sort=-refname refs/auto-save
# Inspect one:
#   git show refs/auto-save/<timestamp>
#
# See hook.md in this directory for full documentation.

set -euo pipefail

# Skip if git unavailable or not in a git work tree.
command -v git >/dev/null 2>&1 || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# Skip if working tree clean — nothing to save.
[ -z "$(git status --porcelain)" ] && exit 0

ts="$(date -u +%Y%m%dT%H%M%SZ)"
orig_branch="$(git symbolic-ref --short HEAD 2>/dev/null || git rev-parse --short HEAD)"
ref="refs/auto-save/${ts}"
msg="auto-save: stop at ${ts} on branch ${orig_branch}"

# Build the snapshot in a TEMPORARY index so the real index + working tree are
# never touched. Seed from HEAD when it exists (else an empty tree for an unborn
# branch), then stage every change — tracked + untracked. .gitignore is honored,
# so ignored build junk stays out.
tmp_index="$(mktemp "${TMPDIR:-/tmp}/commit-on-stop.idx.XXXXXX")"
trap 'rm -f "$tmp_index"' EXIT

# commit identity (scoped to this commit via env — never touches git config; and
# commit-tree, unlike commit, never signs, so no gpg prompt can hang the hook).
export GIT_AUTHOR_NAME='commit-on-stop hook'
export GIT_AUTHOR_EMAIL='commit-on-stop@crickets.local'
export GIT_COMMITTER_NAME='commit-on-stop hook'
export GIT_COMMITTER_EMAIL='commit-on-stop@crickets.local'

if parent="$(git rev-parse --verify --quiet HEAD)"; then
    GIT_INDEX_FILE="$tmp_index" git read-tree "$parent"
    GIT_INDEX_FILE="$tmp_index" git add -A
    tree="$(GIT_INDEX_FILE="$tmp_index" git write-tree)"
    commit="$(git commit-tree "$tree" -p "$parent" -m "$msg")"
else
    GIT_INDEX_FILE="$tmp_index" git read-tree --empty
    GIT_INDEX_FILE="$tmp_index" git add -A
    tree="$(GIT_INDEX_FILE="$tmp_index" git write-tree)"
    commit="$(git commit-tree "$tree" -m "$msg")"
fi

# Atomically publish the snapshot ref. HEAD, the current branch, the real index,
# and the working tree are all unchanged.
git update-ref "$ref" "$commit"

# Bound growth: keep only the most recent N snapshots (timestamp-sorted refs).
# Best-effort — a prune failure must never abort the hook (the snapshot is saved).
keep=10
old_refs="$(git for-each-ref --sort=-refname --format='%(refname)' refs/auto-save \
    | tail -n "+$((keep + 1))" || true)"
if [ -n "$old_refs" ]; then
    printf '%s\n' "$old_refs" | while IFS= read -r old; do
        [ -n "$old" ] && git update-ref -d "$old" 2>/dev/null || true
    done
fi

echo "commit-on-stop: snapshot of dirty tree on '${orig_branch}' -> ${ref}. Recover: git checkout ${ref} -- ." >&2
exit 0
