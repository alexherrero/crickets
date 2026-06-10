<!-- mode: reference -->
# Troubleshooting

Symptom-first lookup for when something stops working — find your symptom, follow the steps, and jump to the page that owns the detail.

## ⚡ Quick Reference

| Symptom | Start at |
|---|---|
| A plugin isn't loading / a command is missing | [plugin isn't loading](#a-plugin-isnt-loading-or-a-commandskill-is-missing) |
| A hook didn't fire | [hook didn't fire](#a-hook-didnt-fire) |
| A host update broke something | [host update broke something](#a-host-update-broke-something) |
| CI is red | [CI is red](#ci-is-red) |
| The wiki published wrong | [wiki published wrong](#the-wiki-published-wrong) |
| The wiki-watcher did nothing | [watcher did nothing](#the-wiki-watcher-did-nothing) |

## A plugin isn't loading (or a command/skill is missing)

1. Confirm the plugin is installed and enabled: `claude plugin list` should show it. Nothing lands in `.claude/` in the v3 model — everything runs from the plugin.
2. Re-sync: `claude plugin install <plugin>@crickets` (after `claude plugin marketplace update crickets` if the marketplace is stale). On Antigravity, reinstall by path against `dist/antigravity/plugins/<plugin>` ([Install crickets plugins](Install-Into-Project)).
3. If you're developing locally with `--plugin-dir`, check the path points at the **generated** plugin (`dist/claude-code/plugins/<plugin>`), not `src/` — and regenerate after edits ([Modify a plugin](Modify-A-Plugin)).
4. A primitive missing on one host only → check its `supported_hosts:`; the generator only emits it for the hosts it declares ([Manifest schema](Manifest-Schema)).
5. **Shows `✘ failed to load` after an upgrade** → the plugin was **renamed or removed** (e.g. `wiki` → `wiki-maintenance` in v3.2.0). The old install points at a name the marketplace no longer offers. Uninstall the old name and install the new one:
   ```bash
   claude plugin uninstall <old>@crickets && claude plugin install <new>@crickets
   ```
   To see every out-of-sync plugin + the exact swap commands in one shot: `python3 scripts/reconcile_plugins.py`.

## A hook didn't fire

- **On Claude Code:** confirm the plugin shows in `claude plugin list`; hooks run from `${CLAUDE_PLUGIN_ROOT}/hooks/…`, so a stale install means stale hooks — re-sync the plugin.
- **On Antigravity:** plugin hooks run **observe / side-effect-only** — a hook whose value is a veto (exit code) or an inject (stdout) runs but does nothing. That's the host, not a bug ([Compatibility](Compatibility)'s hook matrix says which hooks are effective where).
- The `developer-safety` trio (kill-switch / steer / commit-on-stop) has its own checks — trigger-file shapes, ordering, the auto-save no-op cases — on [its plugin page](Developer-Safety).

## A host update broke something

When a host release changes its plugin surface (paths, manifest schema, hook events):

1. **Check the host's release notes** for plugin-surface changes.
2. **Reproduce cheaply:** `claude plugin validate dist/claude-code/plugins/<plugin>` (or load it with `--plugin-dir`); the `agy` path-install on Antigravity.
3. **Fix at the right layer.** Host-specifics live in the generator's **per-host emitters** (`scripts/emit_claude.py` / `emit_antigravity.py`) — a surface change is usually a one-place emitter fix. If the host *dropped* a capability instead, narrow the affected primitive's `supported_hosts:`.
4. **Regenerate, dogfood, commit `src/` + `dist/` together** ([Modify a plugin](Modify-A-Plugin)). If it's an Antigravity gap, record it with a re-address trigger in [Antigravity limitations](Antigravity-Limitations).

## CI is red

1. Badge → Actions tab → the failing OS → the failing step (steps are named after gates).
2. Reproduce locally: `bash scripts/check-all.sh` runs the same gates ([CI gates](CI-Gates)).
3. Per-gate quick answers:
   - **generate drift** → you edited `src/` (or `dist/` by hand) without regenerating: `python3 scripts/generate.py build`, commit both.
   - **check-wiki** → the finding names the rule and the line; fix the page, not the linter.
   - **check-no-pii / gitleaks** → a real finding means scrub it; a false positive goes in the allowlist (match-level, or line-level for context-proven cases like SHA-pinned `uses:` lines) with the reason in the commit.
   - **A Windows-only failure** → usually an encoding or path-translation gotcha; the `validate` job pins `PYTHONUTF8=1`, and generated files are written as bytes — start from whichever of those assumptions the failing code violates.

## The wiki published wrong

- **A page shows the wrong content** → almost certainly a case-insensitive basename collision; `check-wiki` rule-g and the deploy job both guard it, so check the failing run first ([Wiki design](wiki-design)).
- **Nav/sidebar looks stale** → the wiki re-mirrors on every push that touches `wiki/**`; a bad publish self-heals on the next green push.

## The wiki-watcher did nothing

That's usually correct behavior — it's opt-in and cooldown-gated. Check, in order: the device toggle, the per-repo marker, `gh` availability, and the cooldown window. [Wiki Watch Config](Wiki-Watch-Config) has the contract; [Run the wiki-watcher](Run-The-Wiki-Watcher) the walkthrough.

## Related

- [Compatibility](Compatibility) — what's supposed to work where, before you debug it.
- [CI gates](CI-Gates) — the gate battery + the drill-down path.
- [Modify a plugin](Modify-A-Plugin) — the edit → generate → dogfood loop most fixes end in.
- [Antigravity limitations](Antigravity-Limitations) — known host gaps (check before debugging an AG-only symptom).
