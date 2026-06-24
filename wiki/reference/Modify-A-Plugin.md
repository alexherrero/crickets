<!-- mode: how-to -->
# How to modify a crickets plugin

> [!NOTE]
> **Goal:** Edit a crickets plugin's source, regenerate, and try it on a host before opening a PR.
> **Prereqs:** crickets cloned locally; Python 3 + PyYAML (`pip install pyyaml`); `claude` and/or `agy`.

crickets is a source of truth (`src/<group>/`) plus a generator that emits committed native plugins under `dist/`. You edit `src/`, rebuild, dogfood, then submit the source **and** `dist/` together. Never hand-edit `dist/` — it's generated.

## Steps

1. Edit a primitive under its group — e.g. a hook:

   ```bash
   $EDITOR src/developer-safety/hooks/kill-switch/kill-switch.sh
   ```

2. Regenerate `dist/` (both hosts) + the repo-root marketplace pointer:

   ```bash
   python3 scripts/generate.py build
   ```

3. Confirm the generated plugin has your changes:

   ```bash
   git diff dist/
   ```

4. Try it on a host — the two hosts differ:

   ```bash
   claude --plugin-dir dist/claude-code/plugins/developer-safety        # Claude: loads for one session, nothing installed
   agy plugin install "$PWD/dist/antigravity/plugins/developer-safety"  # Antigravity: actually installs — uninstall when done
   ```

5. _(Optional — CI runs this on your PR.)_ For faster feedback, run the full gate battery locally before pushing:

   ```bash
   bash scripts/check-all.sh
   ```

6. Open a PR — commit the source **and** the regenerated `dist/` together (they ship as one change):

   ```bash
   git checkout -b <branch>
   git add src/ dist/ .claude-plugin .agents
   git commit -m "feat(<group>): <what changed>"
   git push -u origin <branch>
   gh pr create --fill        # or open the PR on GitHub
   ```

   CI runs the drift gate + the unit/structural gates on the PR.

## Notes

- A new primitive kind or per-host mapping may need a generator/emitter change — see [Manifest-Schema](Manifest-Schema).
- Some hooks behave differently on Antigravity (it runs plugin hooks observe-only, so a veto/inject hook won't enforce there) — see [Compatibility](Compatibility).
- **Writing a host-portable hook?** Resolve the workspace from the host's stdin hook-input, not `cwd` — the two hosts invoke hooks differently. See [Hooks](Hooks) for the contract.
- **`generate.py` subcommands.** `build` writes `dist/` + the repo-root marketplace pointer from `src/`; `check` exits non-zero when `dist/` is out of sync with `src/` (the drift gate CI runs); `clean` removes `dist/` + the pointer.

## See also

- [Install crickets plugins](Install-Into-Project) — the three install modes.
- [Manifest-Schema](Manifest-Schema) — primitive frontmatter + `group.yaml`.
- [The source-of-truth + generator model](crickets-build-system#overview) — how crickets generates native plugins from one `src/`.
