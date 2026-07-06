---
section: plugin-composition
reusable: true
applies-to: [plugin-home]
---
<!-- SECTION plugin-composition — how ONE plugin relates to the others + its host
     reach. State standalone / requires / enhances explicitly (they're distinct:
     standalone works alone; `requires` is a hard dependency; `enhances` is soft —
     augments a target when both are installed). For host reach name each host and
     link Compatibility; where a host can't run something, say what it does instead,
     not just "unsupported". The generic model is [Plugin anatomy](Plugin-Anatomy);
     this section is the specific instance for one plugin. -->

## How it composes

- **Standalone:** <yes — installs and works on its own / no — see Requires>.
- **Requires:** <base plugin(s) this hard-depends on, or none>.
- **Enhances:** <plugin(s) it augments when both are installed, or none>.
- **Hosts:** <Claude Code + Antigravity reach — observe-only caveats / Claude-only primitives; link [Compatibility](Compatibility)>.
