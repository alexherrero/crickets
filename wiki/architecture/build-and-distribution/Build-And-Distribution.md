<!-- mode: index -->
# Build & distribution

_How plugins are sourced, built, and distributed._

Author a plugin in `src/<group>/` — one folder per plugin. Authoring and shipping go through a single pipeline: edit source, regenerate, pass the gates, and install. All artifacts are generated out of `src/`.

## How it works

The generator (`scripts/generate.py`) reads each `src/<group>/` and writes a committed `dist/<host>/plugins/<group>/` for every supported host (i.e. Claude or Antigravity), each with its own marketplace pointer. Because `dist/` is committed, the marketplace serves files from the repo. A drift gate ensures that the output still matches a fresh build.

| Stage | What happens |
|---|---|
| **Author** | Edit one plugin under `src/<group>/` — its primitives plus a `group.yaml` manifest. |
| **Generate** | `python3 scripts/generate.py build` emits `dist/<host>/plugins/<group>/` for each host, deterministically. |
| **Gate** | The pre-push hook blocks anything personal; CI re-runs the PII detector, `gitleaks`, and `generate.py check` — the gate that fails if committed `dist/` drifts from a fresh build. |
| **Install** | The generated plugins are installed one of three ways: the bootstrap one-liner, the host plugin marketplace, or a manual `--plugin-dir`. |

## How it fits

- **[Plugins](Plugins)** — what flows through the pipeline. Each `src/<group>/` is one plugin; the generated `dist/<host>/plugins/<group>/` is the unit you install.
- **[Host adapters](Host-Adapters)** — where one authored primitive becomes per-host artifacts. Build & distribution runs the emit; host adapters define where each kind lands.

## Safety

- **PII guardrails.** The pre-push hook is the enforcer and CI re-runs the same check, so nothing personal reaches the public repo.

## See also

Detail:

- [Repo layout](Repo-Layout) — where `src/`, `dist/`, and the install plumbing sit.
- [Plugin anatomy](Plugin-Anatomy) — the shape of a generated plugin.
- [Install crickets plugins](Install-Into-Project) — the three install modes, step by step.
- [CI gates](CI-Gates) — the deterministic checks that guard every build.
- [Native plugins — the v3 design](crickets-v3-native-plugins) — why distribution is shaped this way.

[Architecture](Architecture) · [Reference](Reference) · [Home](Home)
