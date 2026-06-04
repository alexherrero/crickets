# How to install crickets plugins

> [!NOTE]
> **Goal:** Install the crickets plugins into Claude Code and/or Antigravity as native host plugins.
> **Prereqs:** `claude` (Claude Code) and/or `agy` (Antigravity) on your PATH; `git`. No clone needed for the one-liner or the Claude marketplace.

crickets ships as **native host plugins** generated from one source of truth ([ADR 0013](0013-bundles-native-plugins)) — the old `install.sh` dispatcher is gone ([ADR 0014](0014-install-decoupling)). The go-forward set is six plugins:

| Plugin | Standalone? | What it adds |
|---|---|---|
| `developer-workflows` | yes (base) | 6 phase commands (`/setup` `/plan` `/work` `/review` `/release` `/bugfix`) + explorer/evaluator agents + the `harness-context` SessionStart hook (Claude-only). |
| `developer-safety` | enhances `developer-workflows` | kill-switch / steer / commit-on-stop hooks + commit-no-coauthor / worktrees-never-auto conventions. |
| `code-review` | enhances `developer-workflows`' `review` | adversarial-reviewer + cross-model adversarial-reviewer-cross agents + the `evidence-tracker` hook + the standalone `/code-review` command. |
| `github-ci` | `requires: [developer-workflows]` | CI workflows + dependabot-fixer. |
| `pii` | standalone | PII guardrail (scrubber skill + pre-push detector). |
| `wiki` | `requires: [developer-workflows]` | Diátaxis wiki authoring + maintenance. |

> The v2.x `developer` seed plugin is **retired** (crickets v3.0). `github-ci` and `wiki` now require `developer-workflows`. Do not install `developer` — it no longer exists.

Pick one of three modes; all land the same plugins.

## Steps

The recommended one-liner — installs the default set on whichever host(s) are present:

```bash
curl -fsSL https://raw.githubusercontent.com/alexherrero/crickets/main/bootstrap.sh | bash
```

It detects `claude` / `agy` and installs the default set: `developer-workflows`, `developer-safety`, `code-review`, `github-ci`, `pii`, `wiki`. On Claude Code it adds the `crickets` marketplace and installs by name; on Antigravity it installs each plugin **by path** (see the asymmetry below).

## Mode 2 — Install by name (Claude) / by path (Antigravity)

> [!IMPORTANT]
> **The `name@crickets` marketplace syntax is Claude-only.** Antigravity's `agy` CLI has **no marketplace-registration command** — `agy plugin install <name>@crickets` fails with `Error: unknown marketplace: crickets`. On Antigravity, install each plugin by its `dist/antigravity/plugins/<group>` path instead. (`agy plugin link` only generates a share link for an *already-known* marketplace; it does not register a local directory.)

**Claude Code** — one word, straight from GitHub:

```bash
claude plugin marketplace add alexherrero/crickets
claude plugin install developer-workflows@crickets   # + developer-safety, code-review, github-ci, pii, wiki @crickets
```

**Antigravity** (`agy` 1.0.2) — install each plugin by path from a clone. Install `developer-workflows` **first** (`github-ci` and `wiki` require it):

```bash
git clone https://github.com/alexherrero/crickets.git ~/Antigravity/crickets
for p in developer-workflows developer-safety code-review github-ci pii wiki; do
  agy plugin install ~/Antigravity/crickets/dist/antigravity/plugins/$p
done
```

Migrating from the v2.x set? Drop the retired seed afterward: `agy plugin uninstall developer`.

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
- [Run a standalone code review](Use-Code-Review) — using the `/code-review` command from `code-review`.
- [Compatibility](Compatibility) — per-host component + hook effectiveness matrix.
- [ADR 0013](0013-bundles-native-plugins) · [ADR 0014](0014-install-decoupling) — why native plugins, why the installer was retired.
