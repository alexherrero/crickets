<!-- mode: reference -->
# Troubleshooting

Find your symptom here when something stops working. Follow the steps. Jump to the page that owns the detail.

## ⚡ Quick Reference

| Symptom | Start at |
|---|---|
| A plugin isn't loading / a command is missing | [plugin isn't loading](#a-plugin-isnt-loading-or-a-commandskill-is-missing) |
| A hook didn't fire | [hook didn't fire](#a-hook-didnt-fire) |
| A host update broke something | [host update broke something](#a-host-update-broke-something) |
| A custom agent's declared tools aren't honored | [agent tools aren't honored](#a-custom-agents-declared-tools-arent-honored) |
| CI is red | [CI is red](#ci-is-red) |
| The wiki published wrong | [wiki published wrong](#the-wiki-published-wrong) |
| The wiki-watcher did nothing | [watcher did nothing](#the-wiki-watcher-did-nothing) |

## A plugin isn't loading (or a command/skill is missing)

1. Confirm the plugin is installed and enabled. Run `claude plugin list`. It must show the plugin. Nothing lands in `.claude/` in the v3 model. Everything runs from the plugin.
2. Re-sync the plugin. Run `claude plugin install <plugin>@crickets`. Run `claude plugin marketplace update crickets` first if the marketplace is stale. On Antigravity, reinstall by path against `dist/antigravity/plugins/<plugin>` ([Install crickets plugins](Install-Into-Project)).
3. Check your path if you develop locally with `--plugin-dir`. It must point at the **generated** plugin (`dist/claude-code/plugins/<plugin>`). It must not point at `src/`. Regenerate the plugin after you make edits ([Modify a plugin](Modify-A-Plugin)).
4. Check a primitive's `supported_hosts:` if it is missing on one host only. The generator only emits it for the hosts it declares ([Manifest schema](Manifest-Schema)).
5. **Shows `✘ failed to load` after an upgrade** means the plugin was **renamed or removed**. For example, `wiki-maintenance` became `wiki` in the AG Wave A rename wave, v3.24.0. This reversed an earlier `wiki` to `wiki-maintenance` rename from v3.2.0 for this same plugin. The old install points at a name the marketplace no longer offers. Uninstall the old name and install the new one:
   ```bash
   claude plugin uninstall <old>@crickets && claude plugin install <new>@crickets
   ```
   Run `python3 scripts/reconcile_plugins.py` to see every out-of-sync plugin and the exact swap commands in one shot.

## A hook didn't fire

- **On Claude Code:** Confirm the plugin shows in `claude plugin list`. Hooks run from `${CLAUDE_PLUGIN_ROOT}/hooks/…`. A stale install means stale hooks. Re-sync the plugin.
- **On Antigravity:** Plugin hooks run **observe / side-effect-only**. A hook whose value is a veto (exit code) or an inject (stdout) runs but does nothing. That behavior belongs to the host, not a bug. Check the hook matrix in [Compatibility](Compatibility) to see which hooks are effective where.
- The `developer-safety` trio (kill-switch / steer / commit-on-stop) has its own checks. Find trigger-file shapes, ordering, and the auto-save no-op cases on [its plugin page](Developer-Safety).

## A host update broke something

A host release can change its plugin surface. This includes paths, the manifest schema, or hook events. Follow these steps:

1. **Check the host's release notes** for plugin-surface changes.
2. **Reproduce cheaply**. Run `claude plugin validate dist/claude-code/plugins/<plugin>`. Alternatively, load it with `--plugin-dir`. Use the `agy` path-install on Antigravity.
3. **Fix at the right layer**. Host-specifics live in the generator's **per-host emitters** (`scripts/emit_claude.py` / `emit_antigravity.py`). A surface change is usually a one-place emitter fix. Narrow the affected primitive's `supported_hosts:` if the host *dropped* a capability instead.
4. **Regenerate, dogfood, commit `src/` + `dist/` together** ([Modify a plugin](Modify-A-Plugin)). Record any Antigravity gap with a re-address trigger in [Antigravity limitations](Antigravity-Limitations).

## A custom agent's declared tools aren't honored

Symptom: You dispatch a plugin-defined custom agent (e.g. `development-lifecycle:explorer`, `tools: Read, Glob, Grep` in its frontmatter). It returns a sub-agent that reports it has **none** of its declared tools. It instead only sees the session's ambient MCP connector tools (Slack, Jira, a CRM, etc. — whatever happens to be attached to that session). Built-in agent types (`Explore`, `general-purpose`) dispatched in the same session get full, correct tool access.

1. **Check crickets' side first, but expect it to be clean.** Every crickets agent's `tools:` frontmatter is a plain comma-separated allowlist (`grep -rn "^tools:" src/*/agents/*.md`). The generator copies it byte-for-byte into `dist/`. It does no `tools:` transformation. Confirm this with `diff src/<plugin>/agents/<name>.md dist/claude-code/plugins/<plugin>/agents/<name>.md`. The frontmatter is not the bug if those match and the shape matches the [documented schema](https://code.claude.com/docs/en/sub-agents). `tools` is *not* one of the fields the docs list as "ignored for plugin subagents". Only `hooks`, `mcpServers`, and `permissionMode` are ignored.
2. **This is a host tool-dispatch gap, not a crickets bug.** Anthropic's own tracker has open reports of this class of fragility. Plugin-scoped subagents do not receive the tool set their frontmatter (or inheritance) implies (`anthropics/claude-code` issues #13605, #30280). The symptom here is a more complete inversion than either issue documents. A plugin agent loses its *entire* declared core-tool allowlist and falls back to the session's ambient MCP set. This was observed from a broad, connector-heavy "Cowork"-style session. Evidence points at that runtime's agent-dispatch layer not resolving plugin-scoped `tools:` allowlists correctly. The cause is not anything crickets ships.
3. **Workaround, not a fix:** Wait until the host confirms this is resolved. Until then, prefer the built-in `Explore` or `general-purpose` agent types over crickets' plugin-defined agents (`explorer`, `researcher`, `project-manager`, etc.) when you run in a host/session of uncertain tool-dispatch fidelity. Built-ins have reliably received correct tool access in every case observed so far. Do not change anything in crickets' agent manifests for this.

## CI is red

1. Click the Badge. Go to the Actions tab. Click the failing OS. Find the failing step. Steps are named after gates.
2. Reproduce locally. Run `bash scripts/check-all.sh`. This runs the same gates ([CI gates](CI-Gates)).
3. Use these per-gate quick answers:
   - **generate drift** means you edited `src/` (or `dist/` by hand) without regenerating. Run `python3 scripts/generate.py build`. Commit both.
   - **check-wiki** findings name the rule and the line. Fix the page, not the linter.
   - **check-no-pii / gitleaks** findings require you to scrub real leaks. Put a false positive in the allowlist (match-level, or line-level for context-proven cases like SHA-pinned `uses:` lines). Document the reason in the commit.
   - **A Windows-only failure** is usually an encoding or path-translation gotcha. The `validate` job pins `PYTHONUTF8=1`. Generated files are written as bytes. Start from whichever of those assumptions the failing code violates.

## The wiki published wrong

- **A page shows the wrong content.** This is almost certainly a case-insensitive basename collision. The `check-wiki` rule-g and the deploy job both guard it. Check the failing run first ([Wiki design](crickets-wiki)).
- **Nav/sidebar looks stale.** The wiki re-mirrors on every push that touches `wiki/**`. A bad publish self-heals on the next green push.

## The wiki-watcher did nothing

That is usually correct behavior. It is opt-in and cooldown-gated. Check these in order: the device toggle, the per-repo marker, `gh` availability, and the cooldown window. Read [Wiki Watch Config](Wiki-Watch-Config) for the contract. Follow [Run the wiki-watcher](Run-The-Wiki-Watcher) for the walkthrough.

## Related

- [Compatibility](Compatibility) — Read what is supposed to work where, before you debug it.
- [CI gates](CI-Gates) — Learn the gate battery and the drill-down path.
- [Modify a plugin](Modify-A-Plugin) — Understand the edit, generate, and dogfood loop where most fixes end.
- [Antigravity limitations](Antigravity-Limitations) — Read the known host gaps. Check this before you debug an AG-only symptom.
