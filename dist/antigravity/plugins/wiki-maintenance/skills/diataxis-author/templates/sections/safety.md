---
section: safety
reusable: true
applies-to: [component-overview]
---
<!-- SECTION safety — an OPTIONAL cross-cutting-concern callout, included ONLY when the
     component carries a real guardrail or where-it-falls-short story (a public repo's PII
     defense, a destructive-action gate, a host capability with no authoring path). Comes
     AFTER `how-it-fits`, before `see-also`. A concern is not a composition, so it does not
     belong in `how-it-fits` (keep that for sibling-component couplings) — it earns its own
     short section. One bullet per concern, each a tight pointer: name the enforcer (or the
     gap) and where it runs (or is tracked); the full mechanism is the Reference page's job,
     named in See also. Heading is concern-specific — `## Safety` for a guardrail,
     `## Host gaps` / `## Limitations` for the where-it-falls-short variant. NOT in the
     default `component-overview` section list: insert it per-page when warranted, and omit
     it entirely when the component has no such concern (most don't). -->

## Safety

- **<Guardrail>.** <name the enforcer + where it runs — one line; nothing personal/unsafe gets through>.
