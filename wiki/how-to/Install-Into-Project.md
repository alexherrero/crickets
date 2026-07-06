# How to install crickets plugins

> [!NOTE]
> **Goal:** Install the crickets plugins into Claude Code and/or Antigravity as native host plugins.
> **Prereqs:** `claude` (Claude Code) and/or `agy` (Antigravity) on your PATH; `git`. No clone needed for the one-liner or the Claude marketplace.

crickets ships as **native host plugins** generated from one source; the old `install.sh` dispatcher is gone ([Build system design](crickets-build-system)). There are six:

| Plugin | Standalone? | What it adds |
|---|---|---|
| `development-lifecycle` | yes (base) | the six phase commands (`/setup` `/plan` `/work` `/review` `/release` `/bugfix`) + the explorer/evaluator agents + the `harness-context` SessionStart hook (Claude-only). |
| `developer-safety` | enhances `development-lifecycle` | the kill-switch / steer / commit-on-stop hooks + the commit-no-coauthor / worktrees-operator-initiated conventions. |
| `code-review` | enhances `development-lifecycle`'s `review` | the adversarial-reviewer + cross-model adversarial-reviewer-cross agents, the `evidence-tracker` hook, and the standalone `/code-review` command. |
| `maintenance` | requires `development-lifecycle` | CI workflows + dependabot-fixer. |
| `privacy` | standalone | the PII guardrail — scrubber skill + pre-push detector. |
| `wiki` | requires `development-lifecycle` | Diátaxis wiki authoring + maintenance. |

There are three ways to install — the one-liner, per-plugin by name or path, or a single plugin with no marketplace — and every route lands the same plugins, so pick whichever fits how much setup you want.

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
claude plugin install development-lifecycle@crickets
claude plugin install code-review@crickets
# repeat for any of: developer-safety, maintenance, privacy, wiki
```

Antigravity (`agy` 1.0.2 or later) — by path from a clone; install `development-lifecycle` first (two plugins require it):

```bash
git clone https://github.com/alexherrero/crickets.git ~/Antigravity/crickets
for p in development-lifecycle developer-safety code-review maintenance privacy wiki; do
  agy plugin install ~/Antigravity/crickets/dist/antigravity/plugins/$p
done
```

**Option 3 — one plugin, no marketplace.** Good for trying a single plugin. On Claude Code, load it for one session:

```bash
claude --plugin-dir ~/Antigravity/crickets/dist/claude-code/plugins/privacy
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
- [Modify a crickets plugin](Modify-A-Plugin) — the source → generate → dogfood loop.
- [Compatibility](Compatibility) — the per-host component + hook matrix.
