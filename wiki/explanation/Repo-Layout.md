<!-- mode: explanation -->
# Repo layout

What lives where in the crickets repo.

```text
crickets/
├── src/                # SOURCE OF TRUTH — src/<group>/ (group.yaml + skills/ agents/ commands/ hooks/ scripts/)
├── dist/               # GENERATED native plugins (committed) — dist/<host>/plugins/<group>/
│   ├── claude-code/    #   + .claude-plugin/marketplace.json
│   └── antigravity/    #   + .agents/plugins/marketplace.json
├── .claude-plugin/     # repo-root marketplace pointer (`claude plugin marketplace add alexherrero/crickets`)
├── .agents/plugins/    # repo-root Antigravity marketplace pointer
├── scripts/            # generate.py (+ emit_*), lint_src.py, src_model.py, check-* gates, tests
├── bootstrap.sh        # one-line installer (curl | bash)
├── templates/          # scaffolding (e.g. hooks/pre-push)
├── wiki/               # the docs — get-started/ do/ reference/ plugins/ why/ designs/ decisions/
├── AGENTS.md           # universal instructions for any AGENTS.md-aware host
└── CLAUDE.md           # Claude Code entry point — points back at AGENTS.md
```

## The two trees that matter

- **`src/<group>/`** is where you work — one folder per plugin, primitives inside. [Plugin anatomy](Plugin-Anatomy) covers the shape; [Manifest schema](Manifest-Schema) the contracts.
- **`dist/<host>/plugins/<group>/`** is what ships — generated, committed, and drift-gated (`generate.py check` fails CI if it doesn't match a fresh build). Never hand-edit it; the loop is always edit `src/` → `python3 scripts/generate.py build` → commit both ([Modify a plugin](Modify-A-Plugin)).

## Everything else

- **`scripts/`** — the generator and the gate battery (`check-all.sh` runs it all — [CI gates](CI-Gates)).
- **`.claude-plugin/` + `.agents/plugins/`** — the repo-root marketplace pointers each host reads.
- **`bootstrap.sh`** — installs the recommended plugin set in one line; only ever calls the hosts' native `plugin install`.
- **`src/privacy/templates/hooks/pre-push`** — the PII enforcer a clone copies into `.git/hooks/` ([CONTRIBUTING](https://github.com/alexherrero/crickets/blob/main/CONTRIBUTING.md)).
- **`wiki/`** — this documentation, published to the GitHub wiki on every push ([Wiki design](crickets-wiki)).

## Forward-owned library code (dark registry)

This table is crickets' own instance of the **dark-registry** convention, now codified in the `conventions` capability's [`dark-registry`](https://github.com/alexherrero/crickets/blob/main/src/conventions/rules/dark-registry.md) rule (CONS-8, superseding this section's earlier "no standing convention existed yet" note from CONS-2). A **dark registration** records a future owner for code that already ships and already works — it changes nothing today. The code stays exactly where it is, under its current plugin's ownership, until the registered owner actually exists; then a real migration (not this table) moves it.

crickets keeps this convention as a markdown table because there is no scorecard machinery here to consume a structured record — agentm's sibling registry (`scripts/health/dark-checks.jsonl`) is JSONL because its nightly health scorecard actually reads it. Same convention, two repo-local formats; see the `dark-registry` rule for the full reasoning and the arc-exit reconciliation both formats share.

| Code | Current owner | Registered future owner | Note |
|---|---|---|---|
| `src/maintenance/scripts/agentm_bridge.py` (+ sibling library scripts under `src/maintenance/scripts/`) | `maintenance` plugin (crickets) | FRIDAY F1 | Cross-plugin agentm-reaching library code — see [Coordinator-Roles](Coordinator-Roles) for the pattern's shape. |
| `src/research/scripts/agentm_bridge.py` (+ sibling library scripts under `src/research/scripts/`) | `research` plugin (crickets) | FRIDAY F1 | Same pattern; `research`'s design already names the personal-knowledge-management trajectory FRIDAY converges on ([crickets-research](crickets-research)). |

## Related

- [Plugin anatomy](Plugin-Anatomy) — the structure inside `src/<group>/` and a generated plugin.
- [Per-Host Paths](Per-Host-Paths) — where each primitive kind lands, per host.
- [Modify a plugin](Modify-A-Plugin) — the edit → generate → dogfood loop.
- [CI gates](CI-Gates) — the gate battery the repo runs.
