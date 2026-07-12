<p align="center">
  <img src="https://raw.githubusercontent.com/alexherrero/crickets/main/assets/crickets/banner-1600.png" alt="Crickets — Inspired by the Noisy Cricket">
</p>

<p align="center"><em>The composable plugins that give your agent its hands — so it can actually do the work.</em></p>

<p align="center">
  <a href="https://github.com/alexherrero/crickets/actions/workflows/ci-all.yml"><img src="https://img.shields.io/github/actions/workflow/status/alexherrero/crickets/ci-all.yml?branch=main&style=for-the-badge&label=CI&labelColor=0a0a0a&logo=github&logoColor=f4efe6" alt="CI"></a>
  <a href="https://github.com/alexherrero/crickets/releases/latest"><img src="https://img.shields.io/github/v/release/alexherrero/crickets?label=LATEST&labelColor=0a0a0a&logo=github&logoColor=f4efe6&style=for-the-badge" alt="Latest release"></a>
  <a href="https://github.com/alexherrero/crickets/blob/main/LICENSE"><img src="https://img.shields.io/badge/CODE-Apache--2.0-f4efe6?labelColor=0a0a0a&style=for-the-badge" alt="Code license: Apache-2.0"></a>
  <a href="https://github.com/alexherrero/crickets/blob/main/LICENSE-CONTENT"><img src="https://img.shields.io/badge/DOCS-CC--BY--4.0-f4efe6?labelColor=0a0a0a&style=for-the-badge" alt="Docs license: CC-BY-4.0"></a>
</p>

<p align="center"><sub>Works with Claude Code + Antigravity — <a href="https://github.com/alexherrero/crickets/wiki/Compatibility">see compatibility</a></sub></p>

If [AgentM](https://github.com/alexherrero/agentm) is the brain, **crickets** is the toolbox of hands: thirteen small, composable plugins (capabilities, skills, hooks, and sub-agents) for the things an agent actually does — review a change, run a phased dev loop, build and maintain a wiki, sync a project board, watch token spend, and more. Each is a focused plugin you install into Claude Code or Antigravity. Add what you need, leave what you don't. Nothing else is required — crickets runs standalone.

AgentM remembers; crickets acts. No crickets plugin hard-links to AgentM — each one reaches for it through a small discovery bridge and skips gracefully when AgentM isn't installed, so crickets works alone and works smarter the moment AgentM is there too.

## 🚀 Get started

Crickets installs into Claude Code and Antigravity with one command. AgentM is its other half; for the full experience, [set it up first](https://github.com/alexherrero/agentm/wiki/Home), then add the crickets plugins.

```bash
curl -fsSL https://raw.githubusercontent.com/alexherrero/crickets/main/bootstrap.sh | bash
```

[See requirements](Compatibility) and [install modes](Install-Into-Project) for more information.

## 📖 Learn more

The [wiki](https://github.com/alexherrero/crickets/wiki) covers everything there is to know about crickets. A few links to get you started.

- [What it can do](How-To) — the plugins and the tasks each one handles.
- [Why it works this way](Explanation) — adversarial review, deterministic gates, phase-gating.
- [Architecture](Architecture) — how crickets is built and composed.
- [Reference](Reference) — plugin anatomy, the manifest schema, and the install modes.

---

> [!NOTE]
> **Latest release: [v3.27.0](https://github.com/alexherrero/crickets/releases/tag/v3.27.0).** The Consolidation arc closes on crickets — the repo slims (dead scripts retired, four discovery bridges merged into one), `check-slop.py` starts blocking instead of just reporting, and eleven misfiled pages move to where they belong. Coordinated with agentm's own Consolidation-arc release; cross-link lands once both sides are confirmed.
