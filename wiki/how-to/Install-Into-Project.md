# How to install crickets into a project

> [!NOTE]
> **Goal:** Get every shipped customization (`pii-scrubber`, `dependabot-fixer`, `ship-release`, `example-bundle`) into a target project's host paths, plus the pre-push PII guardrail.
> **Prereqs:** `crickets` cloned somewhere on your machine; target project exists and is a git repo (for the pre-push hook).

## Steps

1. Clone the toolkit as a sibling of `agentm` (the canonical layout):

   ```bash
   cd ~/Antigravity   # or wherever you keep dev repos
   git clone https://github.com/alexherrero/crickets.git
   ```

   Skip this step if you already have `crickets` cloned.

2. Install everything into your target project:

   ```bash
   bash ~/Antigravity/crickets/install.sh /path/to/your-project
   ```

   On Windows / PowerShell:

   ```powershell
   pwsh -NoProfile -File C:\path\to\crickets\install.ps1 C:\path\to\your-project
   ```

3. Inspect what landed:

   ```bash
   cd /path/to/your-project
   ls .claude/skills/ .agent/skills/
   ls -la .git/hooks/pre-push
   ```

   You should see `pii-scrubber/`, `dependabot-fixer/`, `ship-release/`, `design/`, `memory/`, and `example-skill/` under each host's skills dir, plus an executable `pre-push` hook.

4. Stage and commit the installed scaffold on a branch:

   ```bash
   cd /path/to/your-project
   git checkout -b add-crickets
   git add .claude .agent
   git commit -m "Install crickets customizations"
   ```

   The pre-push hook is installed at `.git/hooks/pre-push` — git hooks aren't committed (they live outside the repo's tree), so subsequent clones of this project won't get the hook automatically. Either re-run `install.sh` on each clone, or add a project-level reminder.

## Variants

### Install only one skill

```bash
bash ~/Antigravity/crickets/install.sh --skill pii-scrubber /path/to/your-project
```

### Install only one bundle

```bash
bash ~/Antigravity/crickets/install.sh --bundle example-bundle /path/to/your-project
```

### Refresh an existing install (true-sync)

```bash
bash ~/Antigravity/crickets/install.sh --update /path/to/your-project
```

`--update` wipes toolkit-managed dirs (`.claude/skills/`, `.agent/skills/`) and recreates them from source. Orphan paths from previous toolkit versions get auto-cleaned. User state files (your project's `wiki/`, `AGENTS.md`, etc.) are never touched. (v0.9.0 removed `.agents/skills/` from the managed-dirs set along with Gemini CLI host support — see [ADR 0006](../explanation/decisions/0006-gemini-cli-host-removal).)

### Skip the pre-push hook

```bash
bash ~/Antigravity/crickets/install.sh --no-pre-push-hook /path/to/your-project
```

Use this if the project already has a pre-push hook the toolkit shouldn't replace, or if you don't want push-time PII enforcement.

## Verify

After install, confirm the structural sanity:

```bash
cd /path/to/your-project
ls .claude/skills/      # should list 6 dirs: pii-scrubber, dependabot-fixer, ship-release, design, memory, example-skill
ls .agent/skills/       # same (Antigravity)
test -x .git/hooks/pre-push && echo "hook installed"
```

If anything's missing, re-run with `--update` to force a clean recreate.

## Related

- [Installer CLI](Installer-CLI) — full flag reference.
- [Customization Types](Customization-Types) — what each installed customization is.
- [Add a Skill](Add-A-Skill) — how to add your own.
- [crickets ADR 0001](0001-crickets-purpose) — why this repo exists.
