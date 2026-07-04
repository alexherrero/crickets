# Why adversarial review

A reviewer told "this code is probably fine, take a look" tends to confirm it. A reviewer told "this code contains bugs — find them" tends to find them. Crickets' code-review primitives are framed adversarially on purpose: the reviewer must produce a failing test, a specific `file:line` defect, or an explicit "no issues found" — never vague prose approval.

The reason is failure-mode coverage. A neutral review optimizes for plausibility ("looks reasonable"); an adversarial one optimizes for counterexamples ("here is where it breaks"). LLM reviewers in particular drift toward agreement when they aren't primed to disagree, so the framing is what makes the review do real work instead of decorating the diff.

## Research & precedent

- **Red teaming / adversarial testing** — attacking a system to surface weaknesses rather than confirming it works ([overview](https://en.wikipedia.org/wiki/Red_team)).
- **LLM sycophancy** — models tend to agree with the framing they're given, so a neutral review under-reports defects; the "assume bugs exist" framing counters it.

## Related

- [Why deterministic gates run first](Why-Deterministic-Gates) — the gate that runs before any LLM review.
- [Purpose and scope](Purpose-And-Scope)
