---
name: coauthor-guard
description: Deterministic prepare-commit-msg git hook that strips every Co-Authored-By trailer naming an AI agent from a commit message, installed once for every repo on the machine through a global core.hooksPath. Additive enforcement on top of the existing commit-no-coauthor snippet + host includeCoAuthoredBy setting — not a replacement for that floor.
kind: hook
supported_hosts: [claude-code, antigravity]
version: 0.2.4
---

# coauthor-guard — deterministic agent Co-Authored-By strip

A native git `prepare-commit-msg` hook, not a Claude Code lifecycle hook — it fires on every `git commit` regardless of which host or agent produced it, closing the gap the prose-only floor (the `commit-no-coauthor` snippet + a host's `includeCoAuthoredBy` setting) leaves when either is forgotten or the host ignores the setting.

## How it works

- **Trigger:** git's native `prepare-commit-msg` hook, called as `prepare-commit-msg <msg-file> <source> [<sha1>]`. Git runs it for `commit -m`, `--amend`, `--trailer`, merges, cherry-picks and rebases, and `--no-verify` does not skip it (it does skip `commit-msg`, which is why this hook uses the earlier slot). The machine-wide install also runs the strip on `applypatch-msg`, which covers `git am` and `git rebase --apply`.
- **Check:** each trailer line whose key is `Co-Authored-By` (case-insensitive, with optional spaces or a tab before the colon, as git parses it) is tested against three agent markers:
  - an email at an agent vendor's domain, with or without the `<>`: `anthropic.com`, `openai.com`, `cursor.com`, `aider.chat`, `ampcode.com`, `all-hands.dev` (subdomains too). A person writing from one of those domains is treated as that vendor's agent;
  - a GitHub App identity, `[bot]` anywhere in the value (Copilot's coding agent, Jules, Devin and Gemini Code Assist commit or co-author as one);
  - an agent product name as a whole word **in the name** (the part before `<`, or the words that aren't an email; a trailer with no name is judged by its email's local part): Gemini, Copilot, Codex, ChatGPT, GPT-*n*, Antigravity, Aider, OpenHands, Cursor Agent, or Claude followed by a model or product name (Opus, Sonnet, Haiku, Fable, Code, Instant). A product name inside a person's email, such as an address at `gemini.com`, doesn't count.
- **If a line matches:** it is removed. Every other line is left byte-identical.
- **A human co-author stays.** A trailer naming a person, including a person called Claude with their own email, is not touched.

Deterministic regex/string-match only, never LLM-judged — mirrors `content-refresh`'s mechanical-vs-judgment-bound split and the diagnostics privacy scrub's determinism discipline. The patterns (`DOMAIN_RE`, `NAME_RE`) live in `coauthor-guard.sh` and `coauthor-guard.ps1`, and a test keeps the two byte-identical. To cover a new agent, add its domain or name to both and a trailer for it to the test.

## Installing

Once per machine. `install-global.sh` (or its pwsh twin) sets git's **global** `core.hooksPath`, so the guard runs in every repo — the ones already cloned and every future clone — for every tool that commits through git: Claude Code, Antigravity, an IDE, or you by hand.

**Unix / macOS** (from a crickets checkout, or from the installed plugin's `hooks/coauthor-guard/`):

```bash
bash src/developer-safety/hooks/coauthor-guard/install-global.sh
bash src/developer-safety/hooks/coauthor-guard/install-global.sh --check
```

**Windows / pwsh:**

```powershell
pwsh -NoProfile -File src/developer-safety/hooks/coauthor-guard/install-global.ps1
pwsh -NoProfile -File src/developer-safety/hooks/coauthor-guard/install-global.ps1 -Check
```

What it does:

- Writes the hooks to `~/.config/crickets/git-hooks/` (`$XDG_CONFIG_HOME` is honoured; `--dir` / `-Dir` overrides it). These are copies, not a pointer into the plugin cache, so `claude plugin update` can't leave git pointing at a deleted directory. Re-run the installer to pick up a newer guard.
- Puts `git-hook-dispatch.sh` there under each git hook name. Once a global `core.hooksPath` is set, git stops looking in a repo's own `.git/hooks`, so each copy hands off to the repo's hook of the same name, with its arguments, stdin and exit code intact. Repo hooks such as `privacy`'s `pre-push` keep running. For `prepare-commit-msg` and `applypatch-msg`, the repo's hook runs first and the strip runs last. An exact pre-0.6.0 `coauthor-guard` copy left in `.git/hooks` (it stripped every co-author, humans too) is skipped; any other hook runs, even one containing the same `awk` line.
- Stands in for Git LFS, the one tool whose hooks a global `core.hooksPath` would otherwise silently drop: a repo that uses LFS and has no hook of its own gets git-lfs's four hooks from the dispatcher. See [Git LFS](#git-lfs) below, including the two commands never to run.
- Stays cheap: the dispatcher finds the repo's hooks with shell builtins rather than a `git` call, starts `bash` only when the message has a co-author line, and starts git-lfs only in a repo that uses LFS.
- Leaves three hook names out, so **a repo's own hook of that name stops running while the install is active**: `reference-transaction` and `post-index-change` (git fires them on every ref or index update; a shell per call made a 40-commit rebase take 8s instead of 0.2s), and `push-to-checkout` (its presence alone would replace git's built-in `updateInstead` behaviour).
- The files are POSIX `sh`, which Git for Windows runs through its bundled shell, so one set serves every OS.
- Refuses to replace a `core.hooksPath` it didn't set, wherever the machine's config sets one (system, global, or any file an `[include]` or `[includeIf]` pulls in, at any depth, whatever its condition), or to write into a directory holding files it didn't put there. A refresh of its own install is never refused: it rewrites the same value.
- `--check` / `-Check` passes only when git uses this directory and every hook in it is an intact, executable copy of the dispatcher, which the install keeps there as `git-hook-dispatch.sh` for reference. A hook another tool replaced reads as unhealthy. Run inside a repo, it also fails when that repo resolves `core.hooksPath` elsewhere (its own config, or a conditional include). After a plugin update, re-run the installer to pick up the newer guard.

`--uninstall` / `-Uninstall` unsets the global `core.hooksPath` and removes the directory, unless some other config still names it (a `core.hooksPath` pointing at a deleted directory would silence every repo's hooks). Repos' own `.git/hooks` then run natively again. A Git LFS repo cloned or created while the install was active has no LFS hooks of its own, so the uninstall says to run `git lfs install` in it before its next push.

**What a global install does not reach:**

- A repo that sets its own local `core.hooksPath` (husky does this) overrides the global one. `--check` names the override when run inside such a repo; put the guard in that repo's hooks directory instead.
- Commits made somewhere other than this machine: a claude.ai/code cloud session's VM, a collaborator's laptop, or a merge GitHub assembles on the server. A repo-committed `.claude/settings.json` (or a CI check) is the place for those.
- Tools that manage `.git/hooks` themselves don't cooperate with a global `core.hooksPath`. `pre-commit install` refuses to run. git-lfs cannot install its hooks either, so the dispatcher runs them for it (next section).

**One repo only:** copy `coauthor-guard.sh` to that repo's `.git/hooks/prepare-commit-msg` and `chmod +x` it.

**Keeping it installed.** On Claude Code a SessionStart check (`check-global.sh`) prints one warning line if the install breaks: the global `core.hooksPath` names a directory that no longer exists (git then runs no hooks at all), the installed files are incomplete or damaged, or the directory is there but the config was unset. It also warns when the install is older than the plugin running the check: a plugin update changes nothing in the install, which is a copy. Each dispatcher carries a `dispatcher-version` number for this, and an older plugin copy stays quiet about a newer install. The check is read-only and says nothing on a healthy machine, one that never installed, or one whose `core.hooksPath` is relative. Antigravity has no SessionStart event, so run `--check` by hand there, and re-run the installer after each plugin update.

## Git LFS

git-lfs installs its hooks into whatever directory `core.hooksPath` names. With the global install active it finds the dispatcher there, prints `Hook already exists: pre-push`, and writes nothing into the repo's own `.git/hooks`. The same refusal happens without a word whenever git-lfs stores or downloads a file in a repo, which is how a clone normally gets its hooks. A repo without the LFS `pre-push` hook pushes its pointer files, leaves the objects in the local clone, and exits 0.

So the dispatcher stands in. For the four hooks git-lfs installs (`pre-push`, `post-checkout`, `post-commit`, `post-merge`), a repo that uses LFS and has no hook of its own under that name gets git-lfs's hook from the dispatcher: `git lfs <hook> "$@"`, with git's arguments, stdin and exit code intact. Nothing is installed per repo.

- **Which repos count as using LFS.** A repo whose LFS store holds an object: an entry under `lfs/objects/` in its git directory. git-lfs writes one when it stores a file (`git add` of a tracked file) or downloads one (a clone or checkout). A read-only query such as `git lfs env`, `ls-files`, `status` or a `fetch` with nothing to fetch leaves other LFS state behind but no object, so it does not count, just as git-lfs installs no hooks for it. The test is a shell glob, so a repo without LFS never starts git-lfs (about 50ms a call). git-lfs installs its own hooks one step earlier, at `git lfs track`; here they start with the first file stored.
- **`pre-push` looks further, once per push.** A repo whose root `.gitattributes` routes files through LFS (`filter=lfs`) counts too, read with shell builtins. A clone made with `GIT_LFS_SKIP_SMUDGE=1` stores nothing, and git-lfs's `pre-push` must still refuse to push LFS history whose objects it lacks to a new remote. `pre-push` also asks `git config` for `lfs.storage`, so a repo that keeps its store outside its git directory still uploads. With `lfs.storage` set in the global config, every repo's push runs git-lfs. LFS attributes kept only in a subdirectory's `.gitattributes` are not read.
- **The `post-*` hooks look only at the store.** They keep lockable files read-only and guard no data, so they stay a single glob per commit. They do not run in a clone that has stored nothing yet, or in a repo that keeps its store elsewhere.
- **A repo's own hook keeps the say.** When `.git/hooks/pre-push` exists, the dispatcher hands off to it and does not run git-lfs, just as git-lfs refuses to replace such a hook on a machine without crickets. That hook has to call `git lfs pre-push "$@"` itself. In a repo that uses LFS, a `pre-push` whose text never mentions git-lfs gets a warning on each push; one that calls git-lfs through another tool gets it too. A repo whose `.git/hooks` already hold git-lfs's own hooks, like one set up by hand, keeps working unchanged.
- **`git-lfs` missing from `PATH`.** In a repo that uses LFS each of the four hooks says so and exits 2, as git-lfs's own hooks do: the push stops instead of leaving its objects behind, and a checkout or `git worktree add` exits non-zero after it has run.
- **The machine-level half is still a one-time step:** `git lfs install --skip-repo` sets the clean and smudge filters in the global config and touches no hooks.

**Never run `git lfs install --force` or `git lfs update --force` inside a repo while the global hooks path is set.** git-lfs suggests the second one when it refuses. Either overwrites four dispatcher copies in the global directory with plain git-lfs hooks. Every repo on the machine then loses its own `pre-push`, `post-checkout`, `post-commit` and `post-merge` hooks, `privacy`'s PII `pre-push` among them, and git-lfs runs in all of them. `git lfs update --manual` is no better: it says to edit the files in the global directory. A plain `git lfs install` inside a repo installs no hooks (it only records `lfs.repositoryformatversion` in the repo's config), and its error can be ignored. The dispatcher's first lines say all of this, and git-lfs prints them right above its own advice.

If a forced command did run, `--check` fails and the SessionStart check warns. Re-run the installer to put the dispatcher back.

A push made while the hook was missing left its objects in the local clone only, and later pushes do not go back for them. That covers every LFS push from a repo with no git-lfs hooks of its own on a machine running the global install before `developer-safety` 0.6.4, and any push made with `--no-verify`. `git lfs push --all <remote>` uploads whatever the remote lacks.

## Relationship to the existing floor

The `commit-no-coauthor` snippet (prose instructing an agent never to add the trailer) plus the host's `includeCoAuthoredBy` setting are the **floor** this hook sits on top of, not replaces:

- The snippet + setting are the first line of defense — most commits never carry the trailer in the first place.
- `coauthor-guard` is the deterministic backstop for when either is forgotten, misconfigured, or the host's setting is silently ignored — it catches the trailer at commit time, unconditionally.

Removing the snippet or the host setting because this hook exists would be a regression — see `AGENTS.md` and this repo's `CLAUDE.md` for the floor's own rules, unchanged by this hook.

## Failure modes

- **Hook not installed:** no effect — the floor above is all that's protecting the commit. `check-all.sh` does not verify installation; `install-global.sh --check` and the SessionStart check do.
- **The global hooks directory deleted while the config still points at it:** git runs no hooks in any repo, the repos' own included. The SessionStart check reports exactly this; re-run the installer.
- **An install older than the plugin:** a dispatcher fix never reaches the machine until the installer runs again. The SessionStart check reports it.
- **`git lfs update --force` or `git lfs install --force` run inside a repo:** four dispatcher copies become plain git-lfs hooks, and every repo loses its own hooks of those names. `--check` and the SessionStart check report it; re-run the installer. See [Git LFS](#git-lfs).
- **`<msg-file>` missing or unreadable:** the hook exits 0 (no-op) rather than blocking the commit — a guard that can fail a commit outright would be worse than one that occasionally misses a strip.
- **A message with no agent trailer:** left byte-identical — never a spurious edit.
- **An agent the pattern doesn't know yet:** its trailer survives until its domain or name is added (see How it works).

## Host support — effective on both

Unlike `kill-switch`/`steer` (Claude-Code-only-effective PreToolUse hooks), `coauthor-guard` is a **native git hook** — git invokes it identically regardless of which host or agent is driving the commit, so it is fully effective on both Claude Code and Antigravity (and even a human committing by hand).

## See also

- [`kill-switch`](../kill-switch/hook.md) / [`steer`](../steer/hook.md) / [`commit-on-stop`](../commit-on-stop/hook.md) — the Claude-Code-lifecycle hook trio this hook sits alongside.
- `snippets/commit-no-coauthor.md` — the prose floor this hook backs up.
- [developer-safety design](https://github.com/alexherrero/crickets/wiki/crickets-developer-safety) — design rationale.
