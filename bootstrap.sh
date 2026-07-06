#!/usr/bin/env bash
# crickets one-line installer (crickets v3.0 #40 part 5).
#
#   curl -fsSL https://raw.githubusercontent.com/alexherrero/crickets/main/bootstrap.sh | bash
#
# Installs the recommended crickets plugin config onto whichever host(s) are
# present (Claude Code and/or Antigravity). A THIN wrapper over each host's
# NATIVE `plugin install` — it never parses manifests or copies primitives
# (that was the deleted v2 install.sh dispatch). The recommended set is read
# from the generator-emitted dist/default-set.json (data, not hard-coded).
set -euo pipefail

CRICKETS_REPO="${CRICKETS_REPO:-$HOME/Antigravity/crickets}"
CRICKETS_GIT="${CRICKETS_GIT:-https://github.com/alexherrero/crickets.git}"

if [ ! -e "$CRICKETS_REPO/.git" ]; then
    echo "==> cloning crickets to $CRICKETS_REPO"
    git clone --quiet --depth 1 "$CRICKETS_GIT" "$CRICKETS_REPO"
fi

DIST="$CRICKETS_REPO/dist"
SET_FILE="$DIST/default-set.json"
if [ ! -f "$SET_FILE" ]; then
    echo "bootstrap: $SET_FILE missing — run 'python3 scripts/generate.py build' in the crickets clone first" >&2
    exit 1
fi
DEFAULT_SET="$(python3 -c "import json; print(' '.join(json.load(open('$SET_FILE'))['plugins']))")"
echo "==> recommended plugins: $DEFAULT_SET"

installed_any=0

# ── Claude Code ─────────────────────────────────────────────────────────────
if command -v claude >/dev/null 2>&1; then
    echo "==> Claude Code: adding marketplace + installing"
    claude plugin marketplace add "$DIST/claude-code" >/dev/null 2>&1 \
        || claude plugin marketplace update crickets >/dev/null 2>&1 || true
    for p in $DEFAULT_SET; do
        claude plugin install "${p}@crickets" --scope user || \
            echo "    WARN: claude install ${p} failed (continuing)" >&2
    done
    installed_any=1
fi

# ── Antigravity ─────────────────────────────────────────────────────────────
# agy has NO marketplace-registration command — the `name@crickets` syntax is
# Claude-only (it errors "unknown marketplace: crickets" on agy). So install
# each plugin by its dist path. default-set.json is alphabetical, which already
# places `developer-workflows` ahead of its `requires:` dependents (github-ci,
# wiki). See wiki/how-to/Install-Into-Project.md § Mode 2.
if command -v agy >/dev/null 2>&1; then
    echo "==> Antigravity: installing (by path — agy has no marketplace)"
    for p in $DEFAULT_SET; do
        agy plugin install "$DIST/antigravity/plugins/${p}" \
            || echo "    WARN: agy install ${p} failed (continuing)" >&2
    done
    installed_any=1
fi

if [ "$installed_any" -eq 0 ]; then
    echo "bootstrap: neither 'claude' nor 'agy' found on PATH — nothing installed" >&2
    exit 1
fi

# ── Enhancer suggestions (soft composition) ─────────────────────────────────
# Surface any enhancer that augments an installed plugin but isn't in the set.
# Graceful + non-fatal: in the full-default-set flow this prints nothing (every
# enhancer is installed); it fires for partial / curated sets. The `enhances`
# metadata is host-agnostic, so the committed Claude marketplace render is the
# source whichever host(s) were installed.
SUGGEST="$CRICKETS_REPO/scripts/suggest_enhancers.py"
MKT="$DIST/claude-code/.claude-plugin/marketplace.json"
if [ -f "$SUGGEST" ] && [ -f "$MKT" ]; then
    python3 "$SUGGEST" "$MKT" $DEFAULT_SET 2>/dev/null || true
fi

echo "==> done. Installed crickets plugins for the detected host(s)."
