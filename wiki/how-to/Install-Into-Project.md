# How to install crickets plugins

> [!NOTE]
> **Goal:** Install the crickets plugins into Claude Code and/or Antigravity as native host plugins.
> **Prereqs:** `claude` (Claude Code) and/or `agy` (Antigravity) on your PATH; `git`. No clone needed for the one-liner or the Claude marketplace.

crickets ships as **native host plugins** generated from one source ([ADR 0013](0013-bundles-native-plugins)); the old `install.sh` dispatcher is gone ([ADR 0014](0014-install-decoupling)). There are six:

| Plugin | Standalone? | What it adds |
|---|---|---|
| `developer-workflows` | yes (base) | the six phase commands (`/setup` `/plan` `/work` `/review` `/release` `/bugfix`) + the explorer/evaluator agents + the `harness-context` SessionStart hook (Claude-only). |
| `developer-safety` | enhances `developer-workflows` | the kill-switch / steer / commit-on-stop hooks + the commit-no-coauthor / worktrees-never-auto conventions. |
| `code-review` | enhances `developer-workflows`' `review` | the adversarial-reviewer + cross-model adversarial-reviewer-cross agents, the `evidence-tracker` hook, and the standalone `/code-review` command. |
| `github-ci` | requires `developer-workflows` | CI workflows + dependabot-fixer. |
| `pii` | standalone | the PII guardrail — scrubber skill + pre-push detector. |
| `wiki-maintenance` | requires `developer-workflows` | Diátaxis wiki authoring + maintenance. |

Three ways in; all land the same plugins.

## Steps

**Option 1 — the one-liner (recommended).** Installs the default set on whichever host(s) are present:

```bash
curl -fsSL https://raw.githubusercontent.com/alexherrero/crickets/main/bootstrap.sh | bash
```

It detects `claude` / `agy`: on Claude Code it adds the `crickets` marketplace and installs by name; on Antigravity it installs each plugin by path (the asymmetry below).

**Option 2 — by name (Claude) or by path (Antigravity).**

> [!IMPORTANT]
> The `name@crickets` marketplace syntax is **Claude-only**. Antigravity's `agy` has no marketplace-registration command, so install each plugin by its `dist/antigravity/plugins/<group>` path instead.

Claude Code — add the marketplace once, then install each plugin you want **by name, one command per plugin** (the names below are examples — install only what you need):

```bash
claude plugin marketplace add alexherrero/crickets
claude plugin install developer-workflows@crickets
claude plugin install code-review@crickets
# repeat for any of: developer-safety, github-ci, pii, wiki-maintenance
```

Antigravity (`agy` 1.0.2 or later) — by path from a clone; install `developer-workflows` first (two plugins require it):

```bash
git clone https://github.com/alexherrero/crickets.git ~/Antigravity/crickets
for p in developer-workflows developer-safety code-review github-ci pii wiki-maintenance; do
  agy plugin install ~/Antigravity/crickets/dist/antigravity/plugins/$p
done
```

**Option 3 — one plugin, no marketplace.** Good for trying a single plugin. On Claude Code, load it for one session:

```bash
claude --plugin-dir ~/Antigravity/crickets/dist/claude-code/plugins/pii
```

On Antigravity, the same `agy plugin install <path>`, pointed at any one `dist/antigravity/plugins/<group>` dir.

## Verify

```bash
claude plugin list      # the @crickets plugins, enabled (user scope)
agy plugin list         # the imported plugins
```

Some plugins have limited compatibility on Antigravity — see [Compatibility](Compatibility) for the per-plugin details.

## See also

- [Using code review](01-First-Code-Review) — a hands-on first run of one plugin.
- [Develop a crickets plugin locally](Develop-A-Plugin-Locally) — the source → generate → dogfood loop.
- [Compatibility](Compatibility) — the per-host component + hook matrix.
