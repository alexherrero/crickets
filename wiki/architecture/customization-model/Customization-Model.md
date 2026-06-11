<!-- mode: index -->
# Customization model

_How a crickets customization is shaped: the primitive types, and the soft-composition model that lets plugins layer on each other._

crickets ships **primitives** — skills, commands, agents, hooks, MCP servers, status lines, output styles, workflows, rules, snippets, settings fragments — packaged as **plugins**. Each primitive carries YAML frontmatter (`name` · `description` · `kind` · `supported_hosts` · `version`); plugins additionally declare a `contents:` list. Plugins layer through the `enhances:` soft-composition model: a plugin names another it builds on, honored when present and skipped when absent — never a hard dependency.

Field-level detail lives in Reference:

- [Customization Types](Customization-Types) — the full primitive catalogue.
- [Manifest Schema](Manifest-Schema) — every frontmatter field and when it is required.
- [Add a skill](Add-A-Skill) · [Add a plugin](Add-A-Plugin) · [Modify a plugin](Modify-A-Plugin) — the authoring how-tos.

## See also

[Architecture](Architecture) · [Reference](Reference) · [Home](Home)
