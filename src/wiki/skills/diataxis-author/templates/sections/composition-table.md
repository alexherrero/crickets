---
section: composition-table
reusable: true
applies-to: [plugin-reference]
---
<!-- SECTION composition-table — under ## Architecture. How this plugin relates to the
     others, in four explicit directions. `enhances` is soft (augments a target when both
     are installed); `requires` is hard (a base dependency). State the reverse directions
     too (Enhanced by / Required by) so the reader sees the whole coupling. Name the seam
     in the How column — what crosses, the division of labor — not a re-description of the
     other plugin. "— · None." where a direction is empty. This table is the source the
     composition diagram is drawn from, so keep the two in sync. -->

### Composition

| Direction | Plugin | How |
|---|---|---|
| Enhances (soft) | [<Plugin>](<link>) | <what this plugin adds to it, only when both are installed>. |
| Enhanced by (soft) | — | None. |
| Requires (hard) | — | None. |
| Required by (hard) | — | None. |
