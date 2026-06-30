<!--
  This README mirrors the wiki Home (wiki/Home.md): the opener, Get started,
  Learn more, and the latest-release note are kept in sync with it. The wiki
  Home is canonical; the README adds only the repo-local sections below it
  (Contributing, License). Convention: agentm harness/documentation.md
  § "Home.md and the repo README". Wiki-internal links here are written as full
  https://github.com/alexherrero/crickets/wiki/<Page> URLs (the README renders
  on the repo page, not inside the wiki).
-->
<p align="center">
  <img src="assets/crickets/banner-1600.png" alt="Crickets — Inspired by the Noisy Cricket">
</p>

<p align="center"><em>The composable plugins that give your agent its hands — so it can actually do the work.</em></p>

<!--
  Badge convention (plan #15 task 7) — mirrors the harness side (task 6 v2):
    labelColor = 0a0a0a (ink, brand)
    color      = auto (semantic green/red on CI; semver-colored on release)
                 OR f4efe6 (paper) for state-less metadata (e.g. LICENSE)
    style      = for-the-badge (brutalist, ALL CAPS, sharp corners — matches banner motif)
    logo       = github (logoColor f4efe6) on CI + release badges
  CI badge points at the dedicated `ci-all.yml` aggregator workflow which waits
  for the 3 per-OS workflows on the same commit and reports a combined status —
  insulates the badge from any other apps' check suites.
  Compatibility (hosts that run Crickets) lives at wiki/reference/Compatibility.md.
-->

<p align="center">
  <a href="https://github.com/alexherrero/crickets/actions/workflows/ci-all.yml"><img src="https://img.shields.io/github/actions/workflow/status/alexherrero/crickets/ci-all.yml?branch=main&style=for-the-badge&label=CI&labelColor=0a0a0a&logo=github&logoColor=f4efe6" alt="CI"></a>
  <a href="https://github.com/alexherrero/crickets/releases/latest"><img src="https://img.shields.io/github/v/release/alexherrero/crickets?label=LATEST&labelColor=0a0a0a&logo=github&logoColor=f4efe6&style=for-the-badge" alt="Latest release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/CODE-Apache--2.0-f4efe6?labelColor=0a0a0a&style=for-the-badge" alt="Code license: Apache-2.0"></a>
  <a href="LICENSE-CONTENT"><img src="https://img.shields.io/badge/DOCS-CC--BY--4.0-f4efe6?labelColor=0a0a0a&style=for-the-badge" alt="Docs license: CC-BY-4.0"></a>
</p>

<p align="center"><sub>Works with Claude Code + Antigravity — <a href="https://github.com/alexherrero/crickets/wiki/Compatibility">see compatibility</a></sub></p>

**Crickets** is the toolkit that gives your agent its hands — a set of small, composable plugins (capabilities, skills, hooks, and sub-agents) for the things an agent actually does: review a change, run a phased dev loop, build and maintain a wiki, sync a project board, watch token spend, and more. Each is a focused plugin you install into Claude Code or Antigravity. Add what you need, leave what you don't.

Crickets is designed as the capability half of [AgentM](https://github.com/alexherrero/agentm): AgentM brings the memory, judgment, and personas; crickets brings what they act through. The two are built to be used together, but can be used apart.

## 🚀 Get started

Crickets installs into Claude Code and Antigravity with one command. AgentM is its other half; for the full experience, [set it up first](https://github.com/alexherrero/agentm/wiki/Home), then add the crickets plugins.

```bash
curl -fsSL https://raw.githubusercontent.com/alexherrero/crickets/main/bootstrap.sh | bash
```

[See requirements](https://github.com/alexherrero/crickets/wiki/Compatibility) and [install modes](https://github.com/alexherrero/crickets/wiki/Install-Into-Project) for more information.

## 📖 Learn more

The [wiki](https://github.com/alexherrero/crickets/wiki) covers everything there is to know about crickets. A few links to get you started.

- [What it can do](https://github.com/alexherrero/crickets/wiki/How-To) — the plugins and the tasks each one handles.
- [Why it works this way](https://github.com/alexherrero/crickets/wiki/Explanation) — adversarial review, deterministic gates, phase-gating.
- [Architecture](https://github.com/alexherrero/crickets/wiki/Architecture) — how crickets is built and composed.
- [Reference](https://github.com/alexherrero/crickets/wiki/Reference) — plugin anatomy, the manifest schema, and the install modes.

> [!NOTE]
> **Latest release: [v3.22.0](https://github.com/alexherrero/crickets/releases/tag/v3.22.0).** The dev-loop plugin now reads your active plan and progress through AgentM's official interface instead of reaching into its files. A cleaner connection between the two, and nothing changes in how you use it.

---

## Contributing

Self-tested on every push by three per-OS workflows (Linux, Mac, Windows) running in parallel. Run the same deterministic battery locally with `bash scripts/check-all.sh`. Details and the full invariant list in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Crickets is multi-licensed so each layer carries the license that fits it:

| Layer | What it covers | License |
|---|---|---|
| **Code** | `.py`, `.sh`, `.ps1`, and configuration logic | [Apache-2.0](LICENSE) |
| **Content** | docs, prompts, agent instructions, skill / command / workflow definitions, wiki, and other prose (`.md`) | [CC-BY-4.0](LICENSE-CONTENT) |
| **Names & logos** | the "crickets" name and brand artwork | Trademark — see [TRADEMARK.md](TRADEMARK.md) |

**Boundary rule:** prompt or instruction text embedded as a string literal inside a code file (e.g. a prompt inside a `.py` script) is **content** (CC-BY-4.0), even though it lives in a code file.

Both licenses permit commercial use and derivative works; both require attribution. See [NOTICE](NOTICE) for the attribution string.
