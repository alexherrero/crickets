#!/usr/bin/env python3
"""Anti-recurrence guard: a plugin whose shipped content changed must bump its
`version:` in `group.yaml`.

The bug this guards against (fixed in the per-plugin-semver change): plugin
versions used to be one hardcoded global constant, so `claude plugin update
<slug>@crickets` no-opped forever — consumers could never pull new primitives.
The fix sources each plugin's marketplace version from its own
`src/<slug>/group.yaml` `version:`. This guard keeps that honest: if a change
touches anything under `src/<slug>/` but leaves that plugin's `version:`
identical to the baseline, consumers on the old version would never see the
update — so the guard fails and tells you which plugin to bump.

Baseline model
--------------
Crickets publishes by committing `dist/` to `main`; consumers pull from there.
So "released" for a plugin == "what's on main". The guard demands a bump for any
plugin whose `src/` content this branch changed without its `version:` moving
*past the published version* — a real SemVer increase, not just any difference
(a downgrade or a garbage value differs from the base yet still leaves consumers
unable to update). Two refs are involved, deliberately:

  - "Did this branch change the plugin's content?" is measured from the
    merge-base of the base ref and HEAD, so advances that landed on `main` after
    this branch forked aren't mis-attributed to it.
  - "Is the version a valid increase over what's published?" compares against
    the base ref's tip (what consumers actually have), so a bump has to clear
    the published version, not merely the fork point.

The diff is 2-dot against the working tree (not 3-dot), so uncommitted local
edits count too — the pre-commit `check-all.sh` run gates work before it's
committed. Once you've bumped past the base on a branch, further edits to the
same plugin pass (the version already exceeds the base), so it's one bump per
branch, not per commit.

Base ref resolution (first that resolves wins):
  1. `--base <ref>` CLI arg
  2. `$VERSION_BUMP_BASE` env var (CI passes the PR base / push before-SHA here)
  3. `origin/main`

Graceful-skip: if the chosen base ref can't be resolved (fresh clone without
`origin/main` fetched, first commit, shallow checkout missing the base), the
guard prints a notice and exits 0 — it never blocks on a missing baseline.
New plugins (no `group.yaml` at the base) and deleted plugins are skipped:
a first publish at 0.1.0 needs no bump.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIRNAME = "src"
_WORKER_BRANCH_PREFIX = "worker/"

_VERSION_RE = re.compile(r"^version:\s*(.+?)\s*$", re.MULTILINE)


# ── pure logic (unit-tested without a git fixture) ──────────────────────────
def changed_plugin_slugs(changed_paths) -> set[str]:
    """Map changed repo-relative paths to the set of plugin slugs they touch.

    A path counts only if it is under `src/<slug>/...` (the source-of-truth
    tree). Anything else — `dist/`, `scripts/`, `wiki/`, top-level files — is
    not a plugin's shipped content and is ignored.
    """
    slugs: set[str] = set()
    for raw in changed_paths:
        parts = Path(raw.strip()).parts
        if len(parts) >= 3 and parts[0] == SRC_DIRNAME:
            slugs.add(parts[1])
    return slugs


def parse_version(group_yaml_text: str | None) -> str | None:
    """Extract the top-level `version:` value from a group.yaml's text.

    Regex (not a YAML parse) so the guard carries no PyYAML dependency — the
    field is a flat top-level scalar. Strips surrounding quotes. Returns None
    when the text is None (file absent at that ref) or has no `version:` key
    (a group.yaml predating the field → its current value can't be proven a
    valid bump, so the caller flags it).
    """
    if group_yaml_text is None:
        return None
    m = _VERSION_RE.search(group_yaml_text)
    if not m:
        return None
    return m.group(1).strip().strip("'\"")


def semver_key(version: str | None):
    """Parse a version string into a comparable `(major, minor, patch)` tuple.

    Accepts the only shape crickets uses — three dotted non-negative integers —
    tolerating an optional leading `v` and ignoring SemVer pre-release/build
    metadata (`-rc1`, `+build`) for the comparison. Returns None for anything
    that isn't three dotted non-negative integers: `None` input, garbage like
    `banana`, or a partial `0.2`. A None result means "not a version I can
    prove is an increase," which the caller treats as a must-bump offender.
    """
    if version is None:
        return None
    core = version.strip()
    if core[:1] == "v":
        core = core[1:]
    # compare on the release core only — drop any -prerelease / +build suffix.
    core = re.split(r"[-+]", core, maxsplit=1)[0]
    parts = core.split(".")
    if len(parts) != 3:
        return None
    try:
        nums = tuple(int(p) for p in parts)
    except ValueError:
        return None
    if any(n < 0 for n in nums):
        return None
    return nums


def find_unbumped(changed_slugs, base_version, cur_version) -> list[str]:
    """Return the sorted slugs that changed but didn't validly bump their version.

    `base_version` / `cur_version` are callables `slug -> (text|None)` of the
    group.yaml at the base ref and in the working tree respectively. A changed
    slug passes ONLY when its current version is a valid SemVer **strictly
    greater** than the base version. It is an offender (must-bump) when:
      - it has a current group.yaml (still exists — not deleted), AND
      - it had a group.yaml at the base (not a brand-new plugin), AND
      - its current version is not a valid strict increase over the base, i.e.
        any of:
          * current version is missing / unparseable (garbage like `banana`,
            partial `0.2`, or no `version:` key at all) → can't prove a bump;
          * current == base (the original bug — a no-op `claude plugin update`);
          * current  < base (a downgrade — consumers on the published, higher
            version would never pull "down" to it, defeating the guard's whole
            purpose).
    Equality-only checking is not enough: a downgrade and a garbage value both
    *differ* from the base yet both leave consumers unable to update, so the
    guard requires a real monotonic SemVer increase, not mere inequality.

    Exception: when the base version itself is unparseable but the current one
    is a valid SemVer, that's accepted as a forward correction (replacing a
    historical garbage value with a real version is progress, not a regression).
    """
    offenders = []
    for slug in changed_slugs:
        cur_text = cur_version(slug)
        if cur_text is None:
            continue  # plugin deleted in the working tree — nothing to bump
        base_text = base_version(slug)
        if base_text is None:
            continue  # brand-new plugin (no baseline) — first publish, no bump
        cur_key = semver_key(parse_version(cur_text))
        if cur_key is None:
            offenders.append(slug)  # garbage / missing current version
            continue
        base_key = semver_key(parse_version(base_text))
        if base_key is not None and cur_key <= base_key:
            offenders.append(slug)  # unchanged or downgraded
        # base unparseable + current valid → forward correction, not an offender.
    # sorted for deterministic output — `changed_slugs` is a set (hash-ordered).
    return sorted(offenders)


def is_deferred_bump_context(branch_name: str | None, env) -> bool:
    """True iff the version bump is *deferred to the serialized integrator* (ADR 0030).

    Under the Model A defer-bump-only model, a `worker/<slug>` branch commits
    src + dist regenerated at the *current* version and does NOT bump — the
    serialized integrator owns the bump (and the shared marketplace.json
    registry), so the cross-plugin registry collision is structurally gone. In
    that context an absent bump is *expected*, so this guard treats it as an
    advisory pass rather than a failure (the integrator's own check-all run, on
    the non-worker integration branch, enforces the bump for real).

    Signal precedence — the explicit env wins so a CI topology that loses the
    branch name (ADR 0030's named re-audit trigger) can still assert the context:
      1. ``$VERSION_BUMP_DEFER`` set: ``1``/``true``/``yes``/``on`` → True;
         ``0``/``false``/``no``/``off`` (or anything else) → False;
      2. branch name starts with ``worker/`` → True;
      3. otherwise → False.
    """
    explicit = env.get("VERSION_BUMP_DEFER")
    if explicit is not None:
        return explicit.strip().lower() in {"1", "true", "yes", "on"}
    return bool(branch_name) and branch_name.startswith(_WORKER_BRANCH_PREFIX)


# ── git plumbing ────────────────────────────────────────────────────────────
def _git(args, **kw):
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, **kw)


def _resolve_base(explicit: str | None) -> str | None:
    candidates = [explicit, os.environ.get("VERSION_BUMP_BASE"), "origin/main"]
    for ref in candidates:
        if not ref:
            continue
        if _git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"]).returncode == 0:
            return ref
    return None


def _resolve_branch_name(env=None) -> str | None:
    """The current branch name, resolved CI-PR-safely.

    GitHub Actions checks out a *detached* HEAD for ``pull_request`` events but
    sets ``$GITHUB_HEAD_REF`` to the PR's source branch — so prefer it (ADR 0030
    names exactly this: a checkout that loses the branch name falls back to an
    explicit env signal). Then the local symbolic ref. Returns None when detached
    with no env hint (a plain ``push`` build on `main` has neither, which is
    correct — `main` is not a deferred-bump context).
    """
    env = os.environ if env is None else env
    head_ref = env.get("GITHUB_HEAD_REF")
    if head_ref and head_ref.strip():
        return head_ref.strip()
    res = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    name = res.stdout.strip()
    return name if res.returncode == 0 and name and name != "HEAD" else None


def _merge_base(base: str) -> str:
    """Fork point between `base` and HEAD; falls back to `base` itself.

    The diff measures *this branch's* contribution, so it must start at where
    the branch forked — not at the tip of `base`. If `base` advanced after the
    fork (another PR landed on main), diffing from its tip would mis-attribute
    those advances to this branch. The merge-base excludes them. Fallback to
    `base` when no merge-base exists (unrelated histories / no HEAD yet) — a
    plain base-vs-worktree diff is still correct there, just broader.
    """
    res = _git(["merge-base", base, "HEAD"])
    sha = res.stdout.strip()
    return sha if res.returncode == 0 and sha else base


def _diff_paths(base: str) -> list[str]:
    # Diff the fork point (merge-base of base and HEAD) against the working tree.
    #   - merge-base, not `base` tip → main's post-fork advances aren't blamed on
    #     this branch (fixes a CI false-fail when another PR lands on main).
    #   - 2-dot against the worktree, not 3-dot `merge-base...HEAD` → uncommitted
    #     local edits are still seen, so the pre-commit `check-all.sh` run gates
    #     work you haven't committed yet (3-dot only sees committed history).
    # Note: the *version* lookup still reads `base` itself (the published tip),
    # so a bump must clear what consumers already have, not just the fork point.
    diff_from = _merge_base(base)
    out = _git(["diff", "--name-only", diff_from, "--", SRC_DIRNAME])
    return [ln for ln in out.stdout.splitlines() if ln.strip()]


def _base_group_yaml(base: str, slug: str) -> str | None:
    res = _git(["show", f"{base}:{SRC_DIRNAME}/{slug}/group.yaml"])
    return res.stdout if res.returncode == 0 else None


def _cur_group_yaml(slug: str) -> str | None:
    p = ROOT / SRC_DIRNAME / slug / "group.yaml"
    return p.read_text(encoding="utf-8") if p.is_file() else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", help="base ref to compare against (default: origin/main)")
    args = ap.parse_args(argv)

    base = _resolve_base(args.base)
    if base is None:
        print("check-version-bump: base ref unresolvable "
              "(no --base / $VERSION_BUMP_BASE / origin/main) — skipping.")
        return 0

    changed = changed_plugin_slugs(_diff_paths(base))
    if not changed:
        print(f"check-version-bump: no src/ plugin changes vs {base} — OK.")
        return 0

    offenders = find_unbumped(
        changed,
        base_version=lambda s: _base_group_yaml(base, s),
        cur_version=_cur_group_yaml,
    )
    if offenders:
        branch = _resolve_branch_name()
        if is_deferred_bump_context(branch, os.environ):
            ctx = f"branch {branch!r}" if branch else "$VERSION_BUMP_DEFER"
            print("check-version-bump: deferred-bump worker context "
                  f"({ctx}) — the version bump is owned by the serialized "
                  "integrator (ADR 0030); treating the absent bump as advisory. "
                  "Pending the integrator's bump on the integration branch: "
                  f"{', '.join(offenders)}.")
            return 0
        print("check-version-bump: FAIL — these plugins changed shipped content "
              f"(src/<plugin>/**) vs {base} but did not bump their group.yaml "
              "`version:`. Consumers on the old version can't `claude plugin "
              "update` to the new primitives until you bump:")
        for slug in offenders:
            cur = parse_version(_cur_group_yaml(slug)) or "0.1.0 (no version: key)"
            print(f"  - {slug}  (still {cur}) → bump src/{slug}/group.yaml version:")
        return 1

    bumped = sorted(changed - set(offenders))
    print(f"check-version-bump: OK — changed plugin(s) bumped their version: "
          f"{', '.join(bumped)} (vs {base}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
