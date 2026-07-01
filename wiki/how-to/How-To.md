<!-- mode: index -->
# How-to

Task-focused recipes for the crickets plugins. For field-level detail like plugin anatomy and the manifest schema, see [Reference](Reference).

## Get started

| How-to | What it does |
|---|---|
| [Run the development loop](Run-The-Development-Loop) | Take a change from brief to shipped through the phases. |
| [Install crickets plugins](Install-Into-Project) | Install the plugins on Claude Code or Antigravity. |
| [Using code review](01-First-Code-Review) | Hands-on first run: plant a bug, catch it. |
| [Install the vault backend](Install-The-Vault-Backend) | Set up the storage backend for the vault. |

## Build a plugin

| How-to | What it does |
|---|---|
| [Add a plugin](Add-A-Plugin) | Scaffold a new plugin, then build it. |
| [Add a skill](Add-A-Skill) | Add a skill to a plugin. |
| [Modify a plugin](Modify-A-Plugin) | Change a plugin and regenerate it. |
| [Plugin anatomy](Plugin-Anatomy) | How a crickets plugin is laid out. |

## Develop efficiently

| How-to | What it does |
|---|---|
| [Review a change — code review](Use-Code-Review) | Run `/code-review` over a diff or PR. |
| [In-flight decision review — /doubt](Use-Doubt-Review) | Review a decision in fresh context before committing. |
| [Simplify a diff](Simplify-A-Diff) | Run `/simplify` to cut accidental complexity. |

## Release with discipline

| How-to | What it does |
|---|---|
| [Add a launch-readiness gate](Add-Launch-Readiness-Gate) | Check observability, rollback, and flags before shipping. |
| [Add observability](Add-Observability-With-Observe) | Instrument the code as you build it. |
| [Author a CI/CD pipeline](Author-A-CICD-Pipeline) | Build the lint, test, deploy gate pipeline. |
| [Deprecate a surface](Deprecate-A-Surface-With-Deprecate) | Retire an old surface, migrate its callers. |

## Plan a project

| How-to | What it does |
|---|---|
| [Author a design](Author-A-Design) | Write a design doc at the right size. |
| [Run a named plan](Run-A-Named-Plan) | Work a specific plan when several are active. |
| [See every active plan](See-Every-Active-Plan) | A read-only glance over every active plan. |
| [Record an architectural decision](Record-An-Architectural-Decision) | Capture a decision in the governing design's log. |
| [Sync a project board](Sync-A-Project-Board) | Mirror your plans and progress onto a board. |

## Maintain a wiki

| How-to | What it does |
|---|---|
| [Provision a repo's wiki](Provision-A-Repo-Wiki) | Scaffold `wiki/` and its lint-then-publish CI. |
| [Declare a project's Architecture](Declare-Architecture) | Write the manifest that grows the Architecture section. |
| [Maintain a wiki — wiki-watcher](Run-The-Wiki-Watcher) | Keep the wiki in sync with its repo. |

## Run an agent team

| How-to | What it does |
|---|---|
| [Spawn a worker in a worktree](Spawn-A-Worker-In-A-Worktree) | Hand a named plan to an isolated worker. |
| [Run isolated tasks](Run-Isolated-Tasks) | Run work in an isolated checkout, away from main. |
| [Integrate a worker](Integrate-A-Worker) | Land a finished worker's branch, gated on green. |
| [Configure main branch protection](Configure-Main-Branch-Protection) | Set the rules the integration gate expects. |
| [Run a coordinator-directed worker team](Run-A-Coordinator-Directed-Worker-Team) | Coordinate several workers on one plan. |

## See also

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)
