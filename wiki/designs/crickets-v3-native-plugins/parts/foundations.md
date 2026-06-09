---
title: "Foundations: SoT folder-per-group + evolved manifests"
status: draft
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-01
updated: 2026-06-01
last_major_revision: 2026-06-01
prd:
project:
parent_design: ../../crickets-v3-native-plugins.md
part_slug: foundations
dependencies: []
estimated_scope: M
---

# Foundations: SoT folder-per-group + evolved manifests

## Scope

Establish the source-of-truth layout and schema, with no generator yet. Create `src/<group>/` — one folder per functional group (Developer, Testing, Releasing, Wiki, Design-docs, GitHub-CI, PII, knowledge/personal) — each holding its primitive folders (`skills/`, `agents/`, `hooks/`, `commands/`, `mcp/`). Define the evolved manifest schema: a per-group `group.yaml` (`name`, `description`, `category`, `requires:`, `standalone:`) plus per-primitive frontmatter that retains `kind` + `supported_hosts`. Migrate crickets' existing primitives into the tree: `pii-scrubber` → `src/pii/`; the control hooks (`commit-on-stop`, `kill-switch`, `steer`) and the three evaluators into their groups.

## Dependencies

None — this is the foundational part.

## Verification criteria

- `src/<group>/group.yaml` parses for every group; the schema (fields + meaning) is documented.
- Every existing crickets primitive lives under exactly one `src/<group>/` folder with valid frontmatter (`kind`, `supported_hosts`).
- A schema lint (or unit test) rejects a malformed `group.yaml` or primitive frontmatter with a clear error.
- No behavior change shipped yet — the old install path may still exist until the clean-break part.

## Parent design

This part implements one slice of [Crickets v3.0 — Native Host Plugins from a Single Source of Truth](../../crickets-v3-native-plugins.md) (`Status: final`). See the parent for Context, Alternatives Considered, Quality Attributes, and Operations. Mid-execution scope changes must be appended to the parent's Document History.
