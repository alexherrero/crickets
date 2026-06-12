<!-- mode: index -->
# Sample Guarded Component

**Crickets** is a toolkit of agent customizations. This sample component carries a cross-cutting host-gap story, so it adds the optional safety section between how-it-fits and see-also — the Host-Adapters shape, filled, with no placeholders left.

## How it works

The guarded component resolves each named part against the shipped library and emits one assembled artifact. The pipeline is deterministic, so the same manifest and library always produce the same output.

## How it fits

- **[Sample Sibling](Sample-Sibling)** — the sibling component that consumes the assembled artifact and renders it for the reader.

## Host gaps

- On one host the assembled artifact has no native slot, so that part is dropped with a logged note rather than emitted — a capability the host does not expose to the authoring path.

## See also

- [Sample Reference](Sample-Reference) — the field-level reference for every part the guarded component can assemble.
