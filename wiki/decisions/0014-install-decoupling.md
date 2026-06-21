# ADR 0014 — #40 install-decoupling: retire install.sh + the agentm↔crickets lib-sync

> [!NOTE]
> Status: accepted
> Date: 2026-06-02

## Context

[ADR 0006](0006-gemini-cli-host-removal) carved crickets out of agentm but kept the two repos' `lib/install/` layer **byte-identical**, propagated by `agentm/scripts/sync-lib.sh` and enforced by a `check-lib-parity.sh` CI gate. ADR 0006 recorded the load-bearing assumption explicitly: *"`lib/install/` byte-identity holds… if drift becomes chronic, we revisit submodules or extract a third repo."* By v3.0 that drift had become chronic (repeated catch-up `sync-lib` passes), and the v3.x catalog could not be built cleanly on top of the bespoke dispatch installer. #40 is that re-audit firing. This ADR records how it resolved and the cross-repo coordination it required. Architecture context: [ADR 0013](crickets-v3-native-plugins); HLD: [crickets-v3-native-plugins](../designs/crickets-v3-native-plugins).

**Open questions the decision resolves:**

- ADR 0006's re-audit named two options (shared lib / third repo). Which — or neither?
- Once crickets goes native, what happens to agentm's installer, which shared the lib?
- How does the operator's live machine migrate without a dangling install?

## Decision

### 1. Go native — delete the bespoke installer outright

Remove `install.sh` / `install.ps1`, `lib/install/`, `scripts/check-lib-parity.sh`, and the smoke/integrity machinery; replace the parity gate with `generate.py check` (ADR 0013). Installation moves entirely onto the hosts' native plugin systems.

**Why not extract `lib/install/` into a shared repo / submodule** (ADR 0006's other named option)? It solves the coupling but preserves a bespoke installer the native plugin systems have made unnecessary, and adds a third repo to maintain. Going native deletes the installer.

**Why not lower the parity tax in place?** That leaves the byte-sync coupling intact and keeps re-implementing dispatch the hosts now do natively; the tax only grows as the catalog grows.

### 2. agentm keeps its own `lib/install/`; the repos decouple at install time

agentm still ships a per-host dispatch installer, so it keeps its own `lib/install/`. The cross-repo coupling is severed from both sides: `agentm/scripts/sync-lib.sh` is patched to **local-only** (regenerates agentm's own checksums; no `../crickets/` targeting), and agentm's `install.sh` drops the block that auto-cloned + invoked crickets's now-deleted installer. agentm's `check-lib-parity.sh` verifies only its own tree, so the two CIs are independent.

**Why does agentm keep the lib when crickets dropped it?** agentm's installer is still its real install path; crickets's was replaced by native plugins. The decouple is asymmetric by design — each repo owns the install machinery it actually uses.

### 3. Three install modes + a one-word GitHub marketplace

Native install is offered in three modes: a one-line `bootstrap.sh` (`curl … | bash`) that installs the default set; the marketplace (`claude plugin marketplace add alexherrero/crickets` + `agy` equivalent); and manual (point a host at any committed `dist/<host>/plugins/<group>`). A generator-emitted, `check`-covered repo-root marketplace pointer enables the one-word GitHub `marketplace add` (part-6 T3).

**Why a repo-root pointer rather than the dist marketplace?** `claude plugin marketplace add <owner/repo>` resolves a manifest at the repo root; the root pointer's sources point back into `dist/<host>/`, and the `check` gate covers it so it can't drift from the catalog.

### 4. Clean break, single major release, coordinated cross-repo

Delivered as a single **crickets v3.0** major. The break is cross-repo (agentm patch) and machine-affecting (the operator's `~/.claude` symlinked into the old crickets dirs), so it was sequenced: install the native plugins first, confirm them working, then delete the old top-level dirs + machinery.

**Why not a gradual deprecation?** The installer + lib-sync are not a public API with external consumers; the operator is the only user. A clean major-version cut is cheaper than a long dual-path window.

## Consequences

### Positive

- **ADR 0006's lib-sync re-audit is CLOSED.** No more byte-sync tax, no `check-lib-parity` gate, no `sync-lib` catch-up passes into crickets.
- **The repos are independent at install time.** Each owns only the install machinery it uses.
- **Native install story.** Marketplace + one-word GitHub add + manual `--plugin-dir`, all off the same committed `dist/`.

### Negative

- **Breaking change (v3.0 major).** Anyone on a v2.x install must migrate to native plugins.
- **The migration was a manual coordinated step** for the operator's live machine (install native → remove symlinks → delete old dirs), done across sessions.
- **The dogfood surfaced an Antigravity host limitation** (plugin hooks can't veto/inject) — out of crickets' control, documented (see [ADR 0013](crickets-v3-native-plugins) + [Compatibility](../reference/Compatibility)).

### Load-bearing assumptions + re-audit triggers

1. **agentm's `lib/install/` stays self-contained.** agentm's `check-lib-parity.sh` reads only its own tree (verified at decouple). Re-audit if agentm's install model changes such that it again wants to share code with crickets.
2. **Operators install from native marketplaces.** Re-audit if either host drops or substantially changes plugin install (the three install modes would need rework).
3. **The Antigravity observe-only-hook limitation persists.** Same re-audit trigger as [ADR 0013](crickets-v3-native-plugins) assumption 2 — re-check if Antigravity ships hook-veto support.

## Related

- [ADR 0006](0006-gemini-cli-host-removal) — the split this revises; the lib-sync re-audit this ADR closes
- [ADR 0013](crickets-v3-native-plugins) — the native-plugin model that replaces the installer
- [ADR 0015](crickets-v3-native-plugins) — the #36 catalog moves deferred past this decoupling
- [crickets-v3-native-plugins](../designs/crickets-v3-native-plugins) — the HLD (Launch Plans: clean break, single major)
- [Compatibility](../reference/Compatibility) — per-host support matrix incl. the AG hook limitation
