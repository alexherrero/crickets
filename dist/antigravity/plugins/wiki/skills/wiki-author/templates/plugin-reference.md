---
page-template: plugin-reference
mode: reference
sections:
  - architecture-overview
  - diagram
  - how-it-works
  - composition-table
  - why-not
  - commands-and-skills
  - configuration
  - see-also
---
<!--
  PAGE TEMPLATE: plugin-reference — the per-plugin page. ONE page documents ONE
  plugin, and it lives in reference/ (GitHub Wiki flattens to basenames, so the
  file is reference/<Plugin>.md and links resolve by basename). It is a COMBINED
  page under two H2 parents:

    # <Plugin>
    ## Architecture      <- context: what it is, the picture, how it works,
      ### Diagram            how it composes, and why you might not use it
      ### How it works
      ### Composition
      ### Why not
    ## Reference         <- the lookup half: the primitives + configuration
      ### Commands & skills
      ### Configuration
    ## See also

  The two H2 parents give stable anchors for deep links (Page#architecture,
  Page#reference). check-wiki rule (e) accepts this shape: a reference page whose
  H2s include both `Architecture` and `Reference` is exempt from the
  open-with-a-table rule, because the reference tables sit under ## Reference
  after the architecture context.

  VOICE — the two prose sections stay plain and spoken, NOT in the weeds:
    - The opening (architecture-overview) says, in plain spoken English, what the
      plugin IS and WHY it is useful — generalized, the way you'd explain it to a
      colleague. Not a command list, not the implementation.
    - How it works explains the mechanism in plain speech, simplified. Name the
      moving parts and what they do; drop the internal jargon (hook-event names,
      install order, exact ref paths, class or function names). If a reader needs
      the exact field, that is the Reference half's job.
    Code-Review, Developer-Workflows, and Developer-Safety are the worked
    exemplars — match their register.

  DIAGRAM — every plugin page carries at least a composition diagram, and a second
  mechanism diagram when the plugin has a multi-step internal flow worth a picture.
  House SVG spec + palette + worked examples: ../style/diagram-style.md.
  `_None / not needed._` is retired here.

  Field-level detail (every flag, every path) is the Reference half; the
  Architecture half is context. Don't inline a wall of detail in How it works.
-->
