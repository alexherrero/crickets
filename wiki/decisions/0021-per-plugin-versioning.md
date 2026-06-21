# ADR 0021 — Per-plugin marketplace versioning sourced from `group.yaml`

> [!NOTE]
> Status: accepted
> Date: 2026-06-11

## Context

Crickets ships six native host plugins generated from one source-of-truth tree (`src/<slug>/`) into a committed `dist/` ([ADR 0013](crickets-v3-native-plugins)). Each emitted `plugin.json` and each `marketplace.json` entry carries a `version:`. Until now that value was a single hardcoded module constant — `PLUGIN_VERSION = "0.1.0"` — duplicated in both host emitters (`scripts/emit_claude.py`, `scripts/emit_antigravity.py`) and written verbatim into all six plugins. It was **never bumped**: the CHANGELOG framed it explicitly and repeatedly as *"plugins stay `0.1.0` per the repo-level versioning model"* — the repo is versioned via git tags (v3.x) + a Keep-a-Changelog `CHANGELOG.md`, and the plugins were deliberately pinned beneath that.

The pin turned out to break the one operation that matters to a consumer. `claude plugin update <slug>@crickets` decides whether to pull by comparing the marketplace `version:` against what's installed. With the version frozen at `0.1.0`, the comparison is always `0.1.0 == 0.1.0` → a permanent no-op. So a machine that installed `wiki-maintenance` at `0.1.0` could **never** pull the primitives shipped since (wiki-init, `wiki-sync.yml`, the single-sourced `check-wiki.py`, the seven-section composer) without a manual uninstall + reinstall. The published content was unreachable to existing installs — the plugins shipped new primitives that `claude plugin update` would never deliver.

**Open questions the decision resolves:**

- How does an existing install pull a plugin's new primitives through a plain `claude plugin update`?
- Where does a plugin's version live, and does one version cover all six plugins or one each?
- How do we keep "I shipped a new primitive but forgot to bump" from silently regressing the fix?

## Decision

### 1. Per-plugin semver, sourced from each plugin's `group.yaml`

Each plugin owns a `version:` field in its `src/<slug>/group.yaml`. The shared parser (`src_model.Group`) carries it as `group.version` (default `"0.1.0"` when the key is absent or a group is built positionally), and **both** host emitters write `group.version` into `plugin.json` and the Claude marketplace entry in place of the deleted `PLUGIN_VERSION` constant. `wiki-maintenance` is bumped to `0.2.0` — the first move past `0.1.0`, covering everything it shipped since the original publish. The other five plugins stay `0.1.0` (their content is unchanged); they bump independently when *their* content next changes.

**Why not keep the repo-level pin?** Because `claude plugin update` keys off the marketplace `version:`. A static version makes update a permanent no-op, which is the bug — the published primitives are unreachable to existing installs. Repo-level git tags + CHANGELOG remain the *human* release record; they are orthogonal to the *machine* update trigger, which has to be the per-plugin marketplace version.

**Why not one global version that bumps on every release (one number for all six)?** It couples unrelated plugins: a `wiki-maintenance` change would force-bump `code-review`, `pii`, etc., pushing a spurious "update" to consumers whose content didn't change. Per-plugin SemVer also lets the number communicate that plugin's change magnitude (patch/minor/major), which a shared counter cannot.

**Why source it from `group.yaml` rather than a separate version registry?** `group.yaml` is already the per-plugin manifest and the build's source of truth; one obvious place to bump, parsed by the model that already loads every other plugin field. A side registry would be a second source to drift.

### 2. An anti-recurrence guard (`check-version-bump.py`)

A deterministic gate fails when anything under `src/<slug>/**` changed versus a base ref but that plugin's `group.yaml` `version:` did not advance to a valid SemVer **strictly greater** than the published version. It is wired into `scripts/check-all.sh` and the CI `validate` job (which passes the PR base / push before-SHA as the baseline).

**Why a diff-based guard instead of trusting the author to remember?** The original bug *was* exactly a silent omission. A deterministic check is the only thing that keeps the fix from rotting back; LLM/author vigilance is not a gate.

**Why require a strict SemVer increase, not just any change?** The guard's purpose is "consumers on the published version can pull the new content." Checking mere *inequality* would let two failure modes through: a **downgrade** (`0.2.0` → `0.1.0`) differs from the base yet consumers on the higher version never pull "down" to it, and a **garbage value** (`version: banana`) differs too but isn't a version `claude plugin update` can order. So the guard parses both sides as SemVer and demands `current > base`; an unparseable current value is itself an offender. (A historical garbage value at the *base* replaced by a real version is the one accepted exception — that's a forward correction.)

**Why baseline = `origin/main` by default?** Crickets "publishes" by committing `dist/` to `main`; consumers pull from there. So "released" for a plugin == "what's on `main`," and a change to a plugin's shipped content relative to `main` is exactly what must carry a bump. Because the guard passes as soon as the version exceeds the base, it costs **one** bump per branch, not one per commit.

**Why measure the *content diff* from the merge-base but the *version* from the base tip?** Two refs, deliberately. The "did this branch change the plugin's content?" question diffs from `merge-base(base, HEAD)` so that a plugin another PR advanced on `main` *after* this branch forked isn't mis-attributed to this branch (which would be a spurious CI failure). The "is the version high enough?" question compares against the base ref's tip — what consumers actually have — so a bump must clear the *published* version, not merely the fork point. The diff stays 2-dot against the working tree (not 3-dot `merge-base...HEAD`) so the local pre-commit `check-all.sh` run still sees uncommitted edits.

**Why graceful-skip when the base ref is unresolvable?** A fresh clone without `origin/main` fetched, or a shallow CI checkout, has no baseline to compare; the guard prints a notice and exits 0 rather than blocking. CI passes an explicit base (and fetches full history) so the guard is real where it actually gates merges.

## Consequences

**Positive**

- An existing install pulls a plugin's new primitives through a plain `claude plugin update <slug>@crickets` — the operation works as users expect, no uninstall/reinstall.
- Per-plugin SemVer communicates per-plugin change magnitude; unrelated plugins don't get spurious version churn.
- "Shipped content but forgot to bump" is now a hard, deterministic CI failure, not a silent regression.
- The version is one field in the manifest already parsed by the build — no new source of truth.

**Negative / accepted debt**

- **A new release discipline:** every merge to `main` that changes a plugin's `src/<slug>/**` must bump that plugin's `version:`. The guard enforces it, but it is a real step authors now owe on each content change.
- **Antigravity update propagation is unverified.** The fix sets `group.version` in the AG `plugin.json`, but the AG marketplace *entry* still carries no `version:` field (it never did), and no `agy plugin update`-by-version path is tested here. Antigravity update propagation is out of scope for this ADR.
- **Historical CHANGELOG narrative is superseded, not rewritten.** Past release entries still read *"plugins stay `0.1.0` per the repo-level versioning model"*; those are append-only records of what was true then. This ADR + the new CHANGELOG entry are the forward-looking correction.

**Load-bearing assumptions + re-audit triggers**

- *`claude plugin update` compares the marketplace `version:` to decide whether to pull.* **Re-audit if** Claude changes the update trigger (e.g. to a content hash) — the per-plugin version would no longer be the load-bearing signal.
- *Crickets publishes by committing `dist/` to `main`, so `origin/main` is the correct guard baseline.* **Re-audit if** the publish model changes (e.g. tag-gated `dist` releases) — the baseline would move to the release tag.
- *Antigravity update propagation is out of scope.* **Re-audit if** Antigravity ships a marketplace-version-driven `agy plugin update` — then the AG marketplace entry must carry `version:` too, and the guard/emitter should cover it.

## Related

- [ADR 0013](crickets-v3-native-plugins) — bundles are native host plugins generated from one source of truth; defines the `plugin.json` / `marketplace.json` this ADR versions.
- [ADR 0014](0014-install-decoupling) — the install-decoupling that made `dist/`-on-`main` the consumer-facing distribution surface.
- `CHANGELOG.md` — the forward-looking entry that records the policy reversal for human release notes.
