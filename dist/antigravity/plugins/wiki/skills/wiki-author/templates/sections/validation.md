---
section: validation
reusable: true
applies-to: [reference]
---
<!-- SECTION validation — for a reference documenting a CHECKED contract (a schema,
     config, or manifest), list what the validator asserts, grouped by scope, then the
     one command to run it. Ground every rule in the validator SOURCE, not the page's
     prose (§3 "ground a reference in the artifacts"). Name the actual validator script;
     don't invent rules the validator doesn't enforce. -->

## Validation

`<validator script>` asserts:

- **<scope>** — <rule>; <rule>; <rule>.

```bash
<command to run it>
```
