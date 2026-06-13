<!-- mode: index -->
# How-to

Task-focused recipes for getting things done with the crickets plugins — from a zero-to-working install through running each plugin on real work. New here? Start with the one-liner install, then watch a plugin work end-to-end.

## Start here

1. [Install crickets plugins](Install-Into-Project) — the three install modes (one-liner · marketplace · manual `--plugin-dir`), per host.
2. [Using code review](01-First-Code-Review) — a hands-on first run: install one plugin, plant a bug, watch `/code-review` catch it.

## What's here

- **[Install crickets plugins](Install-Into-Project)** — the three install modes, per host.
- **[Using code review](01-First-Code-Review)** — a hands-on first run, end-to-end.
- **[Review a change — code review](Use-Code-Review)** — run `/code-review` over a diff or PR for adversarial bug-finding.
- **[Provision a repo's wiki — wiki-init](Provision-A-Repo-Wiki)** — scaffold a repo's `wiki/` and its lint-then-publish CI from nothing.
- **[Declare a project's Architecture — architecture.yml](Declare-Architecture)** — write the per-project manifest that grows the wiki's Architecture section.
- **[Maintain a wiki — wiki-watcher](Run-The-Wiki-Watcher)** — keep a wiki in sync with its repo, automatically.
- **[Spawn a worker in a worktree — /spawn-worker](Spawn-A-Worker-In-A-Worktree)** — hand an activated named plan to a worker in its own isolated checkout.
- **[Integrate a worker — /integrate-worker](Integrate-A-Worker)** — land a finished worker's branch on `main`, gated on the integrated tree passing.

## Recent changes

<!-- maintained by the wiki tooling (recent-wiki-changes / the documenter) -->

- **2026-06-13** — Integrate-A-Worker how-to shipped (`/integrate-worker`, lands a finished worker; gate on the integrated tree; rolls back `main` on red; never pushes).
- **2026-06-13** — Spawn-A-Worker-In-A-Worktree how-to added (`/spawn-worker`, operator-initiated worktree per worker).
- **2026-06-12** — See-Every-Active-Plan how-to added (`/queue-status-lite`, the read-side glance over the plan queue).
- **2026-06-11** — Declare-Architecture how-to added (writing `wiki/architecture.yml`).
- **2026-06-11** — `do/` + `get-started/` folded into `how-to/` (wiki-section-taxonomy restructure); this index merged from both.
- **2026-06-10** — Provision-A-Repo-Wiki how-to added (the `wiki-init` walkthrough).
- **2026-06-08** — Run-The-Wiki-Watcher trimmed + de-jargoned.

## See also

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)
