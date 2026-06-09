<p align="center">
  <img src="https://raw.githubusercontent.com/alexherrero/crickets/main/assets/crickets/banner-1600.png" alt="Crickets — Inspired by the Noisy Cricket">
</p>

<p align="center"><em>Inspired by the <a href="https://en.wikipedia.org/wiki/Men_in_Black_(1997_film)">Noisy Cricket</a> — compact, composable agent primitives.</em></p>

<p align="center">
  <a href="https://github.com/alexherrero/crickets/actions/workflows/ci-all.yml"><img src="https://img.shields.io/github/actions/workflow/status/alexherrero/crickets/ci-all.yml?branch=main&style=for-the-badge&label=CI&labelColor=0a0a0a&logo=github&logoColor=f4efe6" alt="CI"></a>
  <a href="https://github.com/alexherrero/crickets/releases/latest"><img src="https://img.shields.io/github/v/release/alexherrero/crickets?label=LATEST&labelColor=0a0a0a&logo=github&logoColor=f4efe6&style=for-the-badge" alt="Latest release"></a>
  <a href="https://github.com/alexherrero/crickets/blob/main/LICENSE"><img src="https://img.shields.io/badge/LICENSE-MIT-f4efe6?labelColor=0a0a0a&style=for-the-badge" alt="License: MIT"></a>
</p>

<p align="center"><sub>Works with Claude Code + Antigravity — <a href="https://github.com/alexherrero/crickets/wiki/Compatibility">see compatibility</a></sub></p>

**Crickets** is a set of small, composable agent primitives — skills, hooks, sub-agents, MCP servers, commands, and more — grouped into native plugins for Claude Code and Antigravity. They're what **you** add to a project to make [Agent M (`agentm`)](https://github.com/alexherrero/agentm) effective.

## 📚 Get started

[Install](Install-Into-Project) the plugins alongside Agent M and [point them](https://github.com/alexherrero/agentm) at your project.

- [Install crickets plugins](Install-Into-Project) — one-liner, marketplace, or manual `--plugin-dir`, on Claude Code or Antigravity. (Quick version in the [repo README](https://github.com/alexherrero/crickets#readme).)

## 🔧 What do you want to do?

| What | Plugin | Example primitives |
|---|---|---|
| 🪶 **Maintain a wiki** — Diátaxis shape, your house voice, doc-watching | [wiki-maintenance](Wiki-Maintenance) | [style-learning loop](Style-Learning-Loop) · [wiki-watcher](Run-The-Wiki-Watcher) |
| 🔁 **Run a phase-gated dev process** — plan → work → review → release | [developer-workflows](Developer-Workflows) | [operator-control hooks](Operator-Control-Hooks) · [evaluator](Evaluator) |
| 🔎 **Review a change adversarially** — any diff or PR, no `/work` cycle | [code-review](Code-Review) | [code review](Use-Code-Review) |
| 🛡️ **Guard quality + secrets** — control + recovery hooks, a PII scan on push | [developer-safety](Developer-Safety) | [operator-control hooks](Operator-Control-Hooks) · [PII guardrail](PII) |
| 📋 **Plan & track a project** — roadmaps, plans, boards | `coming soon` (V5) | — |

## 📖 Look up a detail

For devs running the plugins:

- [Compatibility](Compatibility) — which hosts and OSes are supported, and the `supported_hosts` contract.
- [Antigravity limitations](Antigravity-Limitations) — known host gaps and the trigger that closes each.

## 💡 Why it works the way it does

Crickets is grounded in established practice and industry precedent — and it *adapts* that practice rather than following it to the letter. We take inspiration from [Diátaxis](https://diataxis.fr) for documentation (expanding from it toward a house voice, not applying it strictly), adversarial review for code, phase-gating for the dev loop, and deterministic gates ahead of LLM judgment.

- [Purpose and scope](Purpose-And-Scope) — what the repo is for, and what it isn't.
- [Why adversarial review](Why-Adversarial-Review) — a reviewer primed to assume bugs finds real ones; a neutral "looks good" doesn't.
- [Why deterministic gates run first](Why-Deterministic-Gates) — typecheck, lint, and tests gate before sycophantic LLM judgment.
- [Why phase-gating](Why-Phase-Gating) — discrete plan → work → review → release gates beat freestyling the whole lifecycle.

## 🧩 Major designs

**Architecture (Agent M)** — the substrate crickets runs on. These are Agent M's; see its design docs rather than re-reading them here.

- **Agent M memory** — the MemoryVault store, the device-wide architecture, and the memory-OS unbundling. → [Agent M design docs](https://github.com/alexherrero/agentm). Background: [MemoryVault](memoryvault) · [memory evolution](agent-memory-evolution) · [device-wide](device-wide-architecture) · [memory-OS](memory-os-architecture).

**Plugins (Crickets)** — what each adds, in plain terms.

- **Native host plugins** ([design](crickets-v3-native-plugins)) — author a primitive once; the generator emits native Claude Code **and** Antigravity plugins, installable three ways, with a CI gate that fails if `dist/` drifts from `src/`.
- **Developer plugin suite** ([design](developer-plugin-suite)) — the phase-gated dev loop, the safety controls, and adversarial review, as three composable plugins joined by `enhances:`.
- **Wiki maintenance** ([design](wiki-maintenance-design)) — a template-driven wiki maintainer that expands from Diátaxis toward your house voice via an operator-in-the-loop learning loop, plus the wiki-watcher.
- **diataxis-author** ([design](diataxis-author)) — Diátaxis authoring and repair for any repo. *(now an Agent M skill — see the [Agent M design](https://github.com/alexherrero/agentm).)*

## 📐 Architecture decisions

Every load-bearing call is recorded as an ADR — the "why X, and why not Y" trail, with re-audit triggers. → **[Browse all decisions](Decisions)**

## 🤝 Want to contribute?

Building a plugin to contribute? Start with [CONTRIBUTING](https://github.com/alexherrero/crickets/blob/main/CONTRIBUTING.md), then the developer specs under **Reference** in the sidebar.
