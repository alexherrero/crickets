---
name: pii-patterns
description: Never write real emails, personal paths, API keys, or phone numbers into committed content — use RFC 2606 domains, $HOME, env-var references, and reserved phone ranges as stand-ins.
kind: rule
supported_hosts: [claude-code, antigravity]
version: 0.1.0
---

## Rule: pii-patterns

When writing or editing **any content that will be committed** — code, docs, config, templates, examples — never embed real personal information. Use the designated safe stand-ins below. This rule fires proactively while composing; `pii-scrubber` catches anything that slips through at scan time.

### Email addresses

| Don't use | Use instead |
|---|---|
| Any real-domain address (corp.com, gmail.com, etc.) | RFC 2606 reserved: `alice@example.com` · `bob@example.org` · `carol@example.net` |
| The operator's actual email | Same reserved domains — never the real address |

These domains (`example.com`, `example.org`, `example.net`) are IANA-reserved for documentation and will never resolve to a real inbox.

### Personal file paths

| Don't use | Use instead |
|---|---|
| `/Users/<realname>/…` (macOS) | `$HOME/…` or `~/<rest-of-path>` in shell; `<your-user>/` as a prose placeholder |
| `/home/<realname>/…` (Linux) | Same |
| `C:\Users\<realname>\…` (Windows) | `%USERPROFILE%\…` in batch/PowerShell; `<your-user>\` in prose |
| Any vault or operator-private absolute path | Never committed — if the path is operator-specific, it belongs in `.harness/` (gitignored), not in `src/` or docs |

### API keys and tokens

| Don't use | Use instead |
|---|---|
| Any real token (`sk-…`, `ghp_…`, `glpat-…`, `AKIA…`) | `<API_KEY>`, `<TOKEN>`, `<SECRET>`, or the specific var name: `$OPENAI_API_KEY` |
| A fake-but-plausible key shape | Still a placeholder shape — use angle-bracket form, not a key-shaped string |

**Never** replace a real key with a fake key-shaped string. Anyone copying it gets a credential-shaped value that tools may attempt to use. Use env-var references or explicit `<PLACEHOLDER>` forms only.

### Phone numbers

| Don't use | Use instead |
|---|---|
| Any real US phone number | NANP reserved range: `555-0100` through `555-0199` |
| International numbers for real people | Omit, or use a clearly fictional stand-in if the format is needed |

The `555-01xx` range is NANP-reserved for fiction and documentation; no real subscriber can hold these numbers.

### When this rule applies

- Inline code examples and README snippets
- Configuration file templates (`.env.example`, `config.yml.template`, …)
- Wiki and how-to pages
- Commit messages and PR bodies
- Test fixtures that will be committed

### When it does NOT apply

- Content inside `.harness/` (gitignored; operator-private working state lives there)
- Runtime values that never touch `git` (env vars, stdin, in-memory config)

### If you find a real value already in a file

Do not redact it silently. Surface it to the operator, propose the safe stand-in, and invoke `pii-scrubber` to run the full scan-and-remediate workflow. The pre-push hook is the final enforcer; this rule and the skill together keep it from ever triggering.
