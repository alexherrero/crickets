# crickets `src/` manifest schema

The source-of-truth schema the generator (part 2) reads. Two manifest layers:

1. **`group.yaml`** — one per group folder; describes the *plugin*.
2. **Primitive frontmatter** — the YAML frontmatter atop each primitive; describes the *primitive*. Unchanged from the v2 manifest (the group, formerly implied by `supported_hosts` + dispatch, is now the **folder** the primitive lives in — never a frontmatter field).

Validated by `scripts/lint_src.py` (task 4).

## `group.yaml`

One per `src/<group>/`. The group **slug** is the folder name (not a field).

| Field | Required | Type | Meaning |
|---|---|---|---|
| `name` | **yes** | string | Human-readable plugin name (marketplace `displayName`). |
| `description` | **yes** | string | One-line plugin description. |
| `category` | no | string | Marketplace category (e.g. `Coding`). Default: `Coding`. |
| `requires` | no | list of group slugs | Other groups this plugin depends on (**hard** dependency). Default: `[]`. Each entry must be an existing `src/<slug>/`. |
| `standalone` | **yes** | bool | Whether the plugin is independently installable (#42 dual-mode). |
| `capabilities` | **yes** | non-empty list of strings | The capabilities this plugin offers (e.g. `[setup, plan, work, review, release, bugfix]`), so other plugins' `enhances:` can target one by name and the resolver can answer "is `<capability>` available?". Required + non-empty since AG Phase-2 capability-declaration hygiene — every plugin declares what it provides. Capability name ≠ plugin name (e.g. `code-review` declares `[adversarial-review]`). |
| `enhances` | no | list | **Soft** composition: groups this plugin augments when both are installed. Each entry is either a group slug (shorthand) or `{group, capability?, effect}`. Default: `[]`. Declarative metadata — the runtime engages via a capability probe, not a host primitive. |
| `renamed_from` | no | list of strings | Prior marketplace slug(s) this group was known as, oldest-first, excluding the current slug (e.g. `[status-line-meter, token-audit]` for a group now slugged `tokens`). Default: `[]`. Feeds the Claude Code marketplace `renames` map (`build_renames_map` in `scripts/src_model.py`) — Claude Code-only (v2.1.193+; no Antigravity marketplace-schema equivalent exists, a named per-host skip). Never declare a chain that would resolve to a cycle (`claude plugin validate .` rejects one) — if a slug is later reclaimed after being vacated by an earlier rename, exclude the earlier rename from the chain rather than re-declaring it. |

**Invariant (lint-enforced):** `standalone: true` ⟺ `requires: []`. A plugin that requires another is *integrated*, not standalone; one that requires nothing is standalone. (`requires` non-empty ⇒ `standalone: false`.)

**`enhances` is orthogonal to `requires`/`standalone`.** It is a *soft* relationship — the plugin works without the target and merely augments it when present — so a `standalone: true` plugin may carry `enhances:` without violating the invariant. `enhances` never implies a hard dependency. (Validation lands in `lint_src.py` — task 2.)

### Example — `src/github-ci/group.yaml`

```yaml
name: GitHub CI
description: CI workflows + dependency-update tooling (dependabot-fixer) for GitHub projects.
category: Coding
requires: [developer-workflows]
standalone: false
capabilities: [ci-repair]
```

### Example — `src/privacy/group.yaml`

```yaml
name: PII Guardrail
description: Scan diffs/working tree for personal information before commit or push.
category: Coding
requires: []
standalone: true
capabilities: [privacy]
```

### Example — soft composition (`enhances` + `capabilities`)

The enhancee declares what it offers; the enhancer declares what it augments. Both stay `standalone: true` — no hard dependency.

```yaml
# src/developer-workflows/group.yaml — declares its capabilities
name: Developer Workflows
description: The phase-gated dev loop the other plugins build on.
requires: []
standalone: true
capabilities: [setup, plan, work, review, release, bugfix]
```

```yaml
# src/code-review/group.yaml — augments developer-workflows' `review` capability
name: Code Review
description: Adversarial review of any diff or PR.
requires: []
standalone: true
capabilities: [adversarial-review]
enhances:
  - group: developer-workflows
    capability: review
    effect: "/review dispatches the adversarial reviewers"
```

## Primitive frontmatter

YAML frontmatter atop each primitive (`SKILL.md`, agent `.md`, hook `hook.md`, …). Carried over verbatim from the v2 manifest schema.

| Field | Required | Type | Meaning |
|---|---|---|---|
| `name` | **yes** | string | Matches the primitive dir/file name. |
| `description` | **yes** | string | One-line primitive description. |
| `kind` | **yes** | enum | `skill` \| `agent` \| `hook` \| `command` \| `mcp-server` \| `status-line` \| `output-style` \| `workflow` \| `rule` \| `snippet` \| `settings-fragment`. |
| `supported_hosts` | **yes** | list | Subset of `[claude-code, antigravity]`. |
| `version` | no | string | Semver. |
| `install_scope` | no | enum | `user` \| `project` \| `either`. |

**Note:** the primitive's **group is its folder**, not a frontmatter field — there is no `group:` key. A primitive belongs to exactly one group; cross-plugin reuse is via the group's `requires:`, not multi-group membership.

### Example — primitive frontmatter

```yaml
name: pii-scrubber
description: Scan the current git diff for personal information before commit or push.
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
```

## Group-level assets — `scripts/` and `templates/`

A group may carry a `src/<group>/scripts/` directory of **verbatim helper scripts** (e.g. `code-review/scripts/cross-review.sh`) and/or a `src/<group>/templates/` directory of verbatim template assets (e.g. `wiki-maintenance/templates/` — its section-template library and `wiki-sync.yml`). Unlike the primitive kinds above, neither is a **discovered primitive** — no frontmatter, no `kind`; the generator copies each directory **wholesale** into the emitted plugin at `dist/<host>/plugins/<group>/scripts/` or `.../templates/` (both hosts, host-agnostic). A primitive (e.g. an agent) references a bundled script via the host's plugin-root path (`${CLAUDE_PLUGIN_ROOT}/scripts/<name>` on Claude Code). Both copies exclude `__pycache__`, `*.pyc`, `.DS_Store`, and `.harness` (`scripts/src_model.py`'s `bundle_ignore()`). `generate.py check` drift-gates the copied assets like any other emitted file.
