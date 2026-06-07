# Why deterministic gates run first

Crickets gates every change on deterministic checks — typecheck, lint, tests, build — before any LLM judgment is consulted. Deterministic checks are cheap, repeatable, and truthful: a test either passes or it doesn't, and it says so the same way every time. LLM judgment is expensive and can be sycophantic — it may bless output a compiler would reject.

So the order is fixed: machines verify what machines can verify; the LLM augments at the margins — review, naming, intent — and never replaces the gate. A green LLM opinion sitting on top of red tests is worthless, so the red tests run first and win.

## Research & precedent

- **Continuous-integration gating** — the established practice of blocking a merge on automated checks rather than on human (or model) sign-off alone.
- **LLM-as-judge reliability** — using a model to grade output is useful but unreliable as a *sole* gate; deterministic checks anchor it so the judgment has something solid to stand on.

## Related

- [Why adversarial review](Why-Adversarial-Review)
- [Why phase-gating](Why-Phase-Gating)
