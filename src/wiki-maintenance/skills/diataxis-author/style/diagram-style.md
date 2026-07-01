# House diagram style — the reference-page SVG standard

Diagrams on a plugin reference page follow one house style, so every wiki reads
as one hand. This is the committed spec the `diataxis-author` skill, the
`documenter` agent, and any worker authoring a reference page follows. A diagram
that drifts from it is wrong.

## When a page needs a diagram

A plugin reference page carries **at least one diagram** — a **composition**
diagram, showing how the plugin relates to the others around it. Add a second
**mechanism** diagram when the plugin has a multi-step internal flow a picture
makes clearer: a phase loop, an authoring pipeline, hooks wrapping a workflow.
Skip the mechanism one when the plugin is simple enough that the prose carries
it. When both are present, put the mechanism diagram first (it explains the
plugin) and the composition diagram second (it places the plugin among the rest).

The old `_None / not needed._` default is retired for plugin pages: every plugin
composes with something — even if only "stands alone" — and that is worth one
small picture.

## The format

- **Store each diagram as its own `.svg`** under `wiki/reference/diagrams/`,
  named `<plugin>-composition.svg` or `<plugin>-<mechanism>.svg`. Reference it
  from the page with a one-line image, so it never pushes a table off-screen:
  `![<descriptive alt text>](diagrams/<file>.svg)`. The alt text describes the
  whole picture in a sentence — it is the accessible version, and what a reader
  sees if the SVG fails to load.
- **Root element:** `<svg viewBox="0 0 W H" width="~1.3×W" height="~1.3×H"
  xmlns="http://www.w3.org/2000/svg" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">`.
  Render at about 1.3× the viewBox so the text stays crisp.
- **Boxes:** rounded rects, `rx="9"`, `stroke-width="1.5"`.
- **Arrows:** `stroke-width="1.4"`; a solid line for a hard/required relationship,
  a dashed line (`stroke-dasharray="5 4"`) for a soft/enhances relationship or an
  operator input. Define one `<marker>` per arrow colour.
- **Type sizes:** about 12.5 bold for a box title, 10.5 for a sub-label, 10 for
  an edge label, 9.5 for a footnote.

## The palette

Colour carries meaning — reuse these roles, don't invent new ones:

| Role | Fill | Stroke | Text |
|---|---|---|---|
| This plugin / a gate | `#EAF1FB` | `#3A6EA5` | `#1e3a5f` |
| A workflow or phase (slate) | `#EAF0F6` | `#5B7C9E` | `#34516e` |
| Enhances / a safe outcome (green) | `#E9F6EE` | `#3A9D5D` | `#27613f` |
| A recovery or snapshot (gold) | `#FBF3E2` | `#C8961E` | `#8a6516` |
| The AgentM substrate (purple) | `#F2EEFB` | `#7E57C2` | `#5b3a8c` |
| A neutral actor — operator, host (grey) | `#F0F2F5` | `#8a93a0` | `#3a4250` |

Arrow-marker fills: solid slate `#5B7C9E` for a plain flow; green `#3A9D5D` for
an enhances edge; dashed grey `#9aa0a8` for a soft relationship; purple `#7E57C2`
for a substrate edge.

## The composition diagram

Put **this plugin** in the centre. Draw its neighbours around it, one edge per
relationship, straight from the page's own **Composition** table:

- **Requires (hard):** a solid slate arrow from this plugin **to** the base it needs.
- **Required by (hard):** a solid arrow **from** the dependent plugin in.
- **Enhances (soft):** a dashed green arrow from this plugin **to** the plugin it augments.
- **Enhanced by (soft):** a dashed green arrow **from** the enhancer in.

A standalone plugin with no couplings still gets a diagram: the plugin alone,
resting on the AgentM substrate, labelled "stands alone."

## Worked examples

Follow these three as templates — copy their structure, swap the content:

- `diagrams/code-review-composition.svg` — a composition diagram.
- `diagrams/dev-workflows-composition.svg` — a busier composition diagram.
- `diagrams/developer-safety-hooks.svg` — a mechanism diagram, hooks wrapping a workflow.
