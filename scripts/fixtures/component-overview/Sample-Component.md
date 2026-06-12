<!-- mode: index -->
# Sample Component

**Crickets** is a toolkit of agent customizations. The sample component is an illustrative landing used as a proof-slice fixture for the section-structure checks — it carries the four required `component-overview` sections, filled, with no placeholders left.

## How it works

The sample component takes an input manifest, resolves each named part against the shipped library, and emits one assembled artifact. The pipeline is deterministic: the same manifest and library always produce the same output, which is what lets a fixture stand in as an acceptance test.

| Stage | What it does |
|---|---|
| **Load** | Read each named part from the library. |
| **Assemble** | Concatenate the parts in manifest order under the page title. |

## How it fits

- **[Sample Sibling](Sample-Sibling)** — the sibling component that consumes the assembled artifact and renders it for the reader.

## See also

- [Sample Reference](Sample-Reference) — the field-level reference for every part the sample component can assemble.
