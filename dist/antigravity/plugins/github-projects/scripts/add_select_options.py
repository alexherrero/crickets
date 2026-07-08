#!/usr/bin/env python3
"""add_select_options.py — safely ADD new options to a GitHub Project V2
single-select field via the `updateProjectV2Field` mutation, preserving
every existing option verbatim (PLAN-board-tracking-model task 2).

The mutation replaces a field's *entire* option set in one call — the
design doc's own documented failure mode is real: submitting an option
without its `id` creates a brand-new option and orphans every item
currently holding the old one. The safe shape (confirmed live against
GitHub's GraphQL schema, 2026-07-08): re-submit every existing option with
its `id` + `name` + `color` + `description` untouched, and append each new
option WITHOUT an `id` so GitHub assigns one. This tool only adds — it
raises rather than silently overwriting if a "new" option's name already
exists on the field.

Deliberately separate from `sync_fields()`'s routine per-post field sync,
which by design never creates options ("a field or option `gh project
field-list` doesn't already resolve is skipped, not auto-created" —
project_sync.py). This is the one-off migration tool that makes an option
resolvable *before* sync_fields() ever needs to write to it.

Uses `gh api graphql --input -` (the full JSON request body over stdin)
rather than `-f`/`-F` variable flags, so the nested `options` array never
depends on shell-escaping or gh's own type-coercion heuristics.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

_OPTIONS_QUERY = """
query($fieldId: ID!) {
  node(id: $fieldId) {
    ... on ProjectV2SingleSelectField {
      id
      name
      options { id name color description }
    }
  }
}
"""

_UPDATE_MUTATION = """
mutation($fieldId: ID!, $options: [ProjectV2SingleSelectFieldOptionInput!]!) {
  updateProjectV2Field(input: {fieldId: $fieldId, singleSelectOptions: $options}) {
    projectV2Field {
      ... on ProjectV2SingleSelectField {
        id
        name
        options { id name color description }
      }
    }
  }
}
"""


@dataclass(frozen=True)
class NewOption:
    name: str
    color: str
    description: str = ""


def _run_graphql(body: dict, *, runner=subprocess.run) -> dict:
    proc = runner(["gh", "api", "graphql", "--input", "-"], input=json.dumps(body), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"gh api graphql exited {proc.returncode}: {proc.stderr}")
    data = json.loads(proc.stdout)
    if "errors" in data:
        raise RuntimeError(f"gh api graphql returned errors: {data['errors']}")
    return data


def fetch_existing_options(field_id: str, *, runner=subprocess.run) -> list[dict]:
    """Read every current option (id, name, color, description) for
    `field_id` via a live GraphQL query. Raises `RuntimeError` on any
    non-zero exit, GraphQL error, or malformed response — a migration
    tool must fail loud, never guess at what's currently on the board."""
    data = _run_graphql({"query": _OPTIONS_QUERY, "variables": {"fieldId": field_id}}, runner=runner)
    node = data.get("data", {}).get("node")
    if node is None or "options" not in node:
        raise RuntimeError(f"fetch_existing_options: unexpected response shape: {data}")
    return node["options"]


def build_mutation_options(existing: list[dict], new_options: list[NewOption]) -> list[dict]:
    """The full `singleSelectOptions` array for the mutation: every
    existing option preserved VERBATIM (id + name + color + description,
    so nothing is orphaned or visually altered), plus each `new_options`
    entry appended WITHOUT an id (so GitHub creates a fresh option for
    it). Raises `ValueError` if a "new" option's name already exists —
    this tool adds, it never renames or overwrites.
    """
    existing_names = {opt["name"] for opt in existing}
    for new in new_options:
        if new.name in existing_names:
            raise ValueError(f"option {new.name!r} already exists — add_select_options only adds, never overwrites")

    preserved = [
        {"id": opt["id"], "name": opt["name"], "color": opt["color"], "description": opt.get("description") or ""}
        for opt in existing
    ]
    added = [{"name": n.name, "color": n.color, "description": n.description} for n in new_options]
    return preserved + added


def add_options(field_id: str, new_options: list[NewOption], *, dry_run: bool = True, runner=subprocess.run) -> dict:
    """Add `new_options` to the single-select field `field_id`, preserving
    every existing option. `dry_run=True` (the default) only fetches the
    current options and builds the mutation's variables, returning them
    without executing anything against the live board — the caller must
    explicitly pass `dry_run=False` to actually mutate it.
    """
    existing = fetch_existing_options(field_id, runner=runner)
    options = build_mutation_options(existing, new_options)

    if dry_run:
        return {"executed": False, "field_id": field_id, "options": options}

    data = _run_graphql({"query": _UPDATE_MUTATION, "variables": {"fieldId": field_id, "options": options}}, runner=runner)
    return {"executed": True, "field_id": field_id, "response": data}
