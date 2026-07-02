# Contributing to crickets

Contributions are welcome. Fork the repo, work on a branch, and open a pull request — here's what makes it land smoothly:

- **Get your bearings.** [Plugin anatomy](https://github.com/alexherrero/crickets/wiki/Plugin-Anatomy) explains what a plugin is and how it's built; see [Authoring a plugin](#authoring-a-plugin) below for the step-by-step.
- **Test locally before you push.** Run `bash scripts/check-all.sh` — the details are in [How to test locally](#how-to-test-locally) below.
- **Keep secrets and personal data out.** This is a public repo, so a PII scan runs in CI and blocks anything it finds. See [PII Guardrail](https://github.com/alexherrero/crickets/wiki/PII) for what's blocked and how to run the check yourself.
- **What CI does with your PR.** Every push runs three per-OS workflows (Linux, macOS, Windows) in parallel; all of them need to be green before a PR can merge.
- **Review turnaround.** Expect a first review within about a week.

## Authoring a plugin

Author your customization once under `src/<group>/`, then generate and dogfood it. The specs you'll need:

- [Modify a plugin](https://github.com/alexherrero/crickets/wiki/Modify-A-Plugin) — the source → generate → dogfood → commit loop.
- [Add a skill](https://github.com/alexherrero/crickets/wiki/Add-A-Skill) — package and ship a standalone skill.
- [Customization types](https://github.com/alexherrero/crickets/wiki/Customization-Types) — the kinds you can author, and where each goes.
- [Manifest schema](https://github.com/alexherrero/crickets/wiki/Manifest-Schema) — the YAML frontmatter contract.
- [Per-host paths](https://github.com/alexherrero/crickets/wiki/Per-Host-Paths) — where each kind installs, on each host.

The generator (`generate.py build`, then commit `dist/`) is the only way to change a shipped plugin — never hand-edit `dist/`.

## How to test locally

One command runs every gate before you push and prints a pass/fail table — source lint, unit tests, generated-output drift, wiki lint, shell syntax, and the PII scan:

```bash
bash scripts/check-all.sh
```

The full breakdown, and what CI adds on top, is on the [CI gates](https://github.com/alexherrero/crickets/wiki/CI-Gates) page.

## Commit messages

Don't add `Co-Authored-By:` trailers naming an agent or model — a plain commit message only. See [AGENTS.md](AGENTS.md#commit-messages) for the full rule.
