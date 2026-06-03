# How to install crickets plugins

> [!NOTE]
> **Goal:** Install the crickets plugins (`developer`, `github-ci`, `pii`, `wiki`) into Claude Code and/or Antigravity as native host plugins.
> **Prereqs:** `claude` (Claude Code) and/or `agy` (Antigravity) on your PATH; `git`. No clone needed for the one-liner or the Claude marketplace.

crickets ships as **native host plugins** generated from one source of truth ([ADR 0013](0013-bundles-native-plugins)) — the old `install.sh` dispatcher is gone ([ADR 0014](0014-install-decoupling)). Pick one of three modes; all land the same plugins.

## Steps

The recommended one-liner — installs the default set on whichever host(s) are present:

```bash
curl -fsSL https://raw.githubusercontent.com/alexherrero/crickets/main/bootstrap.sh | bash
```

It detects `claude` / `agy`, adds the marketplace, and installs `developer`, `github-ci`, `pii`, `wiki`.

## Mode 2 — Marketplace (browse + install by name)

**Claude Code** — one word, straight from GitHub:

```bash
claude plugin marketplace add alexherrero/crickets
claude plugin install developer@crickets      # + github-ci@crickets, pii@crickets, wiki@crickets
```

**Antigravity** (`agy` 1.0.2) — install by path from a clone:

```bash
git clone https://github.com/alexherrero/crickets.git ~/Antigravity/crickets
agy plugin install ~/Antigravity/crickets/dist/antigravity/plugins/developer
```

## Mode 3 — Manual (one plugin, no marketplace)

**Claude Code** — load a single plugin for one session (great for trying one out):

```bash
claude --plugin-dir ~/Antigravity/crickets/dist/claude-code/plugins/pii
```

**Antigravity** — the same `agy plugin install <path>` as above, pointed at any single `dist/antigravity/plugins/<group>` dir.

## Verify

```bash
claude plugin list      # the @crickets plugins, enabled (scope user)
agy plugin list         # the imported plugins
```

Hooks fire on both hosts. **Note:** on Antigravity, `kill-switch` / `steer` are advisory only (the host runs plugin hooks observe-only) — see [Compatibility](Compatibility).

## Related

- [Develop a crickets plugin locally](Develop-A-Plugin-Locally) — the source → generate → dogfood loop.
- [Compatibility](Compatibility) — per-host component + hook support matrix.
- [ADR 0013](0013-bundles-native-plugins) · [ADR 0014](0014-install-decoupling) — why native plugins, why the installer was retired.
