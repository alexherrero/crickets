# Contributing to crickets

## PII guardrails

This is a public repo. The customizations and configuration kept here are personal but **must not contain personal information that should stay private**.

### What NOT to commit

- **Email addresses** — use the GitHub handle `alexherrero` if you need an identifier; use `@example.com` / `@example.org` / `@example.net` (RFC 2606 reserved) for fake addresses in documentation.
- **Personal paths** — `/Users/<name>/`, `C:\Users\<name>\`, `/home/<name>/`. Use `<your-user>/` placeholder or `$HOME` in examples.
- **API keys / tokens** — anything matching common shapes (`sk-...`, `gho_...`, `ghp_...`, `glpat-...`, `AKIA...`). Never commit these. Use `<API_KEY>` placeholder if an example requires one.
- **Phone numbers** — use `555-0100` through `555-0199` (NANP reserved for fiction) for example phone numbers.
- **Private project names** — anything not already in your public GitHub.
- **Internal hostnames or IP addresses** — corporate VPN endpoints, dev servers, etc.

### Three-layer enforcement

| Layer | What | When it fires |
|---|---|---|
| **Pre-push git hook** | `templates/hooks/pre-push` — copy it in manually (`cp templates/hooks/pre-push .git/hooks/ && chmod +x .git/hooks/pre-push`) | On every `git push`. Runs `check-no-pii.sh --diff <range>`; non-zero exit blocks the push. **Mandatory enforcer** for this repo. |
| **`pii-scrubber` skill** | `skills/pii-scrubber/SKILL.md` — interactive agent-facing layer | Invoked by an agent before commit / push. Presents findings, offers redactions, loops until clean. |
| **CI gate** | GitHub Actions workflow (lands in task 4 of v0.1.0 plan) | On every push to GitHub. Runs the same script + gitleaks. Final safety net. |

### How to test locally

```bash
# Scan the entire working tree
bash scripts/check-no-pii.sh --all

# Scan only staged changes (mirrors pre-commit-style check)
bash scripts/check-no-pii.sh --staged

# Scan a git range (mirrors what the pre-push hook does)
bash scripts/check-no-pii.sh --diff origin/main..HEAD

# Run gitleaks against the repo
gitleaks detect --source . --config .gitleaks.toml
```

### False positives — the override protocol

If `check-no-pii.sh` flags something that's a real false positive (e.g. a documentation example that *looks* like PII but isn't):

1. **First option:** rephrase to avoid the regex match — use `alice@example.com` instead of a realistic-looking address, `555-0100` for phone numbers, `<API_KEY>` for credential placeholders. This is almost always what you want.
2. **Second option:** if the pattern legitimately needs to look real (e.g. testing the scanner itself), add it to the allowlist:
   - For `check-no-pii.sh`: append to the `ALLOWLIST_PATTERNS=` array in the script with a comment explaining why.
   - For `gitleaks`: append to `.gitleaks.toml`'s `[allowlist].regexes` list.
   - Document the reason in the same commit message.
3. **Override (last resort):** if neither of the above fits, the `pii-scrubber` skill supports explicit override with a documented reason. The override is appended to `.harness/.pii-overrides.log` with timestamp + reason. CI surfaces every override on the next run — there is no silent suppression.

## Authoring a plugin

Contributing a customization? Author it once under `src/<group>/`, then generate and dogfood it. These are the specs you'll need:

- [Modify a plugin](https://github.com/alexherrero/crickets/wiki/Modify-A-Plugin) — the source → generate → dogfood → commit loop.
- [Add a skill](https://github.com/alexherrero/crickets/wiki/Add-A-Skill) — package and ship a standalone skill.
- [Customization types](https://github.com/alexherrero/crickets/wiki/Customization-Types) — the kinds you can author and where each goes.
- [Manifest schema](https://github.com/alexherrero/crickets/wiki/Manifest-Schema) — the YAML frontmatter contract.
- [Per-host paths](https://github.com/alexherrero/crickets/wiki/Per-Host-Paths) — where each kind installs, per host.

## Local gates

One command runs every gate before pushing (the pre-push hook runs a subset automatically; the full battery catches things sooner):

```bash
bash scripts/check-all.sh
```

It prints a PASS/FAIL table per gate — source lint, unit tests, generated-output drift, wiki lint, shell syntax, PII scan. The full breakdown, and what CI adds on top, is in [CI gates](https://github.com/alexherrero/crickets/wiki/CI-Gates).

> These mirror the three per-OS CI workflows. The generator (`generate.py build` → commit `dist/`) is the only way to change shipped plugins — never hand-edit `dist/`. See [Modify a plugin](https://github.com/alexherrero/crickets/wiki/Modify-A-Plugin).

## Regenerating the brand banner

The Crickets brand banner (`assets/crickets/banner-1600.png` + `banner-3200.png`) ships in the README hero + the wiki Home page. The banner is rendered from `assets/banner.html` via headless Chrome.

**Run whenever you change `assets/banner.html`:**

```bash
bash scripts/regenerate-banner.sh
```

The script renders both PNG sizes (1600×430 + 3200×860 retina) and writes them to `assets/crickets/`. **Commit the regenerated PNGs alongside the `banner.html` change.**

Requirements: a Google Chrome install (macOS auto-detected; Linux `google-chrome`/`chromium` on `PATH`; Windows Chrome in default Program Files). If Chrome isn't found the script prints the install paths it checked.

The banner is a **static brand asset** — it does not carry release-version data (live version + CI status live in shields.io badges in the README), so regeneration is NOT tied to releases. Mirrors the equivalent setup in the sibling [`agentm`](https://github.com/alexherrero/agentm/blob/main/CONTRIBUTING.md#regenerating-the-brand-banner) repo.

## Licensing

Crickets is **multi-licensed by medium** — code under [Apache-2.0](LICENSE), documentation / prompts / skill definitions under [CC-BY-4.0](LICENSE-CONTENT), and the name + logos under a [trademark policy](TRADEMARK.md). The full split and the boundary rule (a prompt embedded as a string literal in a code file is *content*) live in the [README License section](README.md#license).

**Why this shape, not blanket MIT:** the toolkit's contribution lives in prose — prompts, skill definitions, phase specs, wiki — so one software license fit it poorly. The goal is **attribution + brand, not idea-protection**: no license can stop someone reimplementing the methodology (copyright protects expression, not ideas), so we secure credit on the words (CC-BY's medium-matched attribution beats MIT's bare notice) plus a trademark that makes a true rip-off *nameable*. We deliberately did **not** reach for copyleft (AGPL) or source-available / Fair-Source (FSL/BSL) — both chill the broad reuse this project wants and solve a hosted-revenue problem it doesn't have.

By contributing, you agree your contributions ship under the same split (code → Apache-2.0; prose → CC-BY-4.0).

## Commit messages

Do not append `Co-Authored-By:` trailers naming agents or models. Plain commit message only. See [AGENTS.md § Conventions § Commit messages](AGENTS.md#commit-messages) for the full rule.
