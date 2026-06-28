# Fixture 30 — /cross-review

A user has a working-tree diff and wants an INDEPENDENT second opinion on it from
a different vendor's model (not Claude), to catch blind spots a Claude-only
`/review` would share with the code it produced.

Sample prompts that should route here:
- "сделай cross-review текущих изменений"
- "ревью другой моделью этот PR"
- "second opinion on the code from codex"
- "кросс-вендор ревью диффа"

Expected behavior: `/cross-review` resolves the diff, scrubs secrets/PII, runs an
external CLI (codex, else gemini), folds the findings back as a ranked list naming
the engine that ran, and — if no external CLI is available or it is out of quota —
gracefully degrades to a native Claude red-team self-review while saying so. It is
additive to `/review` (the mandatory floor) and never a gate.
