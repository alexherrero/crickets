<!-- mode: index -->
# Build & distribution

_How `src/` becomes shipped native host plugins, and the ways operators install them._

Authoring happens in `src/<group>/`; a generator emits committed `dist/` plugins for each supported host. Operators install via the bootstrap one-liner, the Claude Code plugin marketplace, or a manual `--plugin-dir`. The v2.x `install.sh` dispatcher was retired in v3.0 in favor of native host plugins.

Field-level detail lives in Reference:

- [Repo layout](Repo-Layout) — where `src/`, `dist/`, and the install plumbing sit.
- [Plugin anatomy](Plugin-Anatomy) — the generated plugin's internal shape.
- [Install crickets plugins](Install-Into-Project) — the install modes, step by step.
- [CI gates](CI-Gates) — the deterministic checks that guard every build.

## See also

[Architecture](Architecture) · [Reference](Reference) · [Home](Home)
