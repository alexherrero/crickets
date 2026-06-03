# How to develop a crickets plugin locally

> [!NOTE]
> **Goal:** Edit a crickets plugin's source, regenerate, and try it on a host before committing.
> **Prereqs:** crickets cloned locally; Python 3 + PyYAML (`pip install pyyaml`); `claude` and/or `agy`.

crickets is a source-of-truth (`src/<group>/`) plus a generator that emits committed native plugins under `dist/`. You edit `src/`, rebuild, dogfood, then commit source **and** `dist/` together. Never hand-edit `dist/` — it is generated.

## Steps

1. Edit a primitive under its group — e.g. a hook:

   ```bash
   $EDITOR src/developer/hooks/kill-switch/kill-switch.sh
   ```

2. Regenerate `dist/` (both hosts) + the repo-root marketplace pointer:

   ```bash
   python3 scripts/generate.py build
   ```

3. Confirm `dist/` is in sync — the CI drift gate, run locally:

   ```bash
   python3 scripts/generate.py check
   ```

4. Try it on a host **without installing** — load the generated plugin for one session:

   ```bash
   claude --plugin-dir dist/claude-code/plugins/developer        # Claude Code
   agy plugin install "$PWD/dist/antigravity/plugins/developer"  # Antigravity
   ```

5. Run the unit + structural gates before committing:

   ```bash
   ( cd scripts && python3 -m unittest discover -p 'test_*.py' )
   python3 scripts/lint_src.py
   bash scripts/check-no-pii.sh --all
   ```

6. Commit the source **and** the regenerated output together (CI's `generate.py check` fails on drift):

   ```bash
   git add src/ dist/ .claude-plugin .agents
   git commit -m "feat(<group>): <what changed>"
   ```

## Notes

- A new primitive kind or per-host mapping may need a generator/emitter change — see [Manifest-Schema](Manifest-Schema).
- Antigravity runs plugin hooks observe/side-effect-only, so a veto/inject hook won't enforce there — see [Compatibility](Compatibility).

## Related

- [Install crickets plugins](Install-Into-Project) — the three install modes.
- [Manifest-Schema](Manifest-Schema) — primitive frontmatter + `group.yaml`.
- [ADR 0013](0013-bundles-native-plugins) — the source-of-truth + generator model.
